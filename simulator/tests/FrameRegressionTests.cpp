#include "SensorFrameCursor.hpp"
#include "AdaptiveGridDisplayState.hpp"
#include <future>
#include <iostream>
#include <thread>

namespace {
using namespace std::chrono_literals;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
SensorTime at(int ms) { return SensorTime{1000000ms + std::chrono::milliseconds(ms)}; }
sensorBufferFrameType frame(int ms, bool withData = false) {
    SensorFrameBuilder builder(at(ms));
    if (withData) {
        AdaptiveGridSensorSample first, second;
        first.cells[12].totalAgents = 2;
        second.cells[15].totalAgents = 4;
        builder.add("agbs-a", at(ms), std::move(first));
        builder.add("agbs-b", at(ms), std::move(second));
        builder.add("abs", at(ms), AgentSensorSample{});
        builder.add("gbs", at(ms), GridSensorSample{});
    } else {
        builder.add("measured-empty", at(ms), AdaptiveGridSensorSample{});
    }
    return std::move(builder).finish();
}
void pairing() {
    SharedBuffer<sensorBufferFrameType> buffer("frames");
    SensorFrameCursor cursor;
    cursor.selectCompletedStep(at(0), buffer);
    require(!cursor.frame() && !buffer.isDrained(), "No-sample step must resolve while producer is still live");
    buffer.write(frame(100, true));
    buffer.write(frame(200, true));
    cursor.selectCompletedStep(at(50), buffer);
    require(!cursor.frame(), "Future frame used too early/stale frame retained");
    require(buffer.currentReadFrameIndex == 1, "Cursor drained beyond one future frame");
    cursor.selectCompletedStep(at(100), buffer);
    const auto selected = cursor.frame();
    require(selected && selected->first == at(100), "Wrong selected timestamp");
    require(buffer.currentReadFrameIndex == 1, "Read queue despite local exact match");
    const auto* a = findSensorSample<AdaptiveGridSensorSample>(selected->second, "agbs-a");
    const auto* b = findSensorSample<AdaptiveGridSensorSample>(selected->second, "agbs-b");
    require(a && b && a->cells.at(12).totalAgents == 2 && b->cells.at(15).totalAgents == 4,
            "Sensor IDs not independently routed");
    require(!findSensorSample<AdaptiveGridSensorSample>(selected->second, "abs"), "Payload type confusion");
    require(!findSensorSample<AdaptiveGridSensorSample>(selected->second, "absent"), "Unknown ID reused data");
    cursor.selectCompletedStep(at(100), buffer);
    require(cursor.frame() == selected && buffer.currentReadFrameIndex == 1,
            "Paused repaint consumed another frame");
    cursor.selectCompletedStep(at(150), buffer);
    require(!cursor.frame(), "Old data retained between measurements");
    cursor.selectCompletedStep(at(200), buffer);
    require(cursor.frame() && cursor.frame()->first == at(200), "Future frame lost");
    cursor.selectCompletedStep(at(250), buffer);
    require(!cursor.frame() && !buffer.isDrained(), "No-sample tail waited for EOF or retained old data");
    buffer.end();
    cursor.selectCompletedStep(at(300), buffer);
    require(!cursor.frame(), "Missing final frame did not resolve");

    SharedBuffer<sensorBufferFrameType> skipped("skipped");
    skipped.write(frame(0)); skipped.write(frame(50)); skipped.write(frame(100)); skipped.end();
    SensorFrameCursor skipCursor;
    skipCursor.selectCompletedStep(at(100), skipped);
    require(skipCursor.frame() && skipCursor.frame()->first == at(100)
            && skipped.currentReadFrameIndex == 3, "Old frames not discarded");
    require(skipped.isDrained(), "Exact frame left in queue");
    for (int malformedTime : {100, 50}) {
        SharedBuffer<sensorBufferFrameType> malformed("malformed");
        malformed.write(frame(100)); malformed.write(frame(malformedTime));
        SensorFrameCursor check;
        check.selectCompletedStep(at(100), malformed);
        bool rejected = false;
        try { check.selectCompletedStep(at(150), malformed); }
        catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "Duplicate/out-of-order frame silently accepted");
    }
}

// A bounded agent queue must keep advancing even when no sensor frame will arrive.
// Exercise both an entirely unsampled run and long gaps before/after observations.
void completedStepSequence() {
    for (bool sampled : {false, true}) {
        SharedBuffer<SensorTime> agents("agent times", 2);
        SharedBuffer<sensorBufferFrameType> sensors("sparse sensor frames", 2);
        auto producer = std::async(std::launch::async, [&] {
            for (int ms = 0; ms < 1000; ms += 50) {
                if (sampled && (ms == 400 || ms == 600)) sensors.write(frame(ms, ms == 600));
                agents.write(at(ms)); // Sensor capture and any write for this time are complete.
            }
            agents.end(); sensors.end();
        });
        SensorFrameCursor cursor;
        for (int ms = 0; ms < 1000; ms += 50) {
            const auto timestamp = agents.read();
            require(timestamp == at(ms), "Agent sequence lost a step");
            cursor.selectCompletedStep(timestamp, sensors);
            const bool measured = sampled && (ms == 400 || ms == 600);
            require(static_cast<bool>(cursor.frame()) == measured,
                    "Sparse producer/renderer pairing stalled or reused a measurement");
            if (measured) require(cursor.frame()->first == timestamp, "Measurement time mismatch");
        }
        producer.get();
        require(agents.currentReadFrameIndex == 20 && sensors.currentReadFrameIndex == (sampled ? 2u : 0u),
                "Non-sampling steps generated or required sensor frames");
        require(agents.isDrained() && sensors.isDrained(), "Sparse run did not drain");
    }
}
void gridDisplay() {
    SharedBuffer<sensorBufferFrameType> buffer("grid display");
    SensorFrameCursor cursor;
    AdaptiveGridDisplayState first, second;
    cursor.selectCompletedStep(at(0), buffer);
    require(!first.update(cursor.frame(), "agbs-a") && !first.measurementTime() && first.cellIds().empty(),
            "Initial display invented an observation");
    buffer.write(frame(100, true));
    cursor.selectCompletedStep(at(50), buffer);
    require(!first.update(cursor.frame(), "agbs-a") && !first.measurementTime(),
            "Future measurement displayed before its agent state");
    cursor.selectCompletedStep(at(100), buffer);
    require(first.update(cursor.frame(), "agbs-a") && second.update(cursor.frame(), "agbs-b"),
            "First measured geometry did not trigger reconstruction");
    require(first.cellIds() == std::unordered_set<int>{12} && second.cellIds() == std::unordered_set<int>{15},
            "Display geometry mixed sensor IDs");
    require(!first.update(cursor.frame(), "agbs-a"), "Paused display rebuilt identical geometry");

    cursor.selectCompletedStep(at(150), buffer);
    require(!cursor.frame(), "Display retention contaminated exact-step measurement matching");
    require(!first.update(cursor.frame(), "agbs-a") && first.cellIds().count(12)
            && first.measurementTime() == at(100), "Intermediate step erased geometry or relabelled its time");

    SensorFrameBuilder onlyFirst(at(200));
    AdaptiveGridSensorSample sameCells;
    sameCells.cells[12].totalAgents = 99; // Counts change, geometry does not.
    onlyFirst.add("agbs-a", at(200), std::move(sameCells));
    buffer.write(std::move(onlyFirst).finish());
    cursor.selectCompletedStep(at(200), buffer);
    require(!first.update(cursor.frame(), "agbs-a") && first.measurementTime() == at(200),
            "Identical cell set rebuilt the tree or failed to refresh measurement time");
    require(!second.update(cursor.frame(), "agbs-b") && second.measurementTime() == at(100)
            && second.cellIds().count(15), "Slower sensor was cleared/refreshed by another sensor");

    SensorFrameBuilder emptied(at(300));
    emptied.add("agbs-a", at(300), AdaptiveGridSensorSample{});
    buffer.write(std::move(emptied).finish());
    cursor.selectCompletedStep(at(300), buffer);
    require(first.update(cursor.frame(), "agbs-a") && first.cellIds().empty()
            && first.measurementTime() == at(300), "Measured empty retained old subdivisions");
    require(!second.update(cursor.frame(), "agbs-b") && second.cellIds().count(15),
            "One empty sensor removed another sensor's display");

    SensorFrameBuilder repopulated(at(400));
    AdaptiveGridSensorSample moved;
    moved.cells[13].totalAgents = 1;
    repopulated.add("agbs-a", at(400), std::move(moved));
    buffer.write(std::move(repopulated).finish());
    cursor.selectCompletedStep(at(400), buffer);
    require(first.update(cursor.frame(), "agbs-a") && first.cellIds() == std::unordered_set<int>{13},
            "New measurement accumulated old cell IDs");
    buffer.end();
    cursor.selectCompletedStep(at(450), buffer);
    require(!first.update(cursor.frame(), "agbs-a") && first.measurementTime() == at(400),
            "Run tail relabelled or erased the last dated geometry");
}

void contract() {
    SensorFrameBuilder noMeasurement(at(0));
    require(!std::move(noMeasurement).finish(), "No-sample step allocated an empty sensor frame");
    SensorFrameBuilder builder(at(100));
    builder.add("empty", at(100), AdaptiveGridSensorSample{});
    bool duplicate = false, wrongTime = false;
    try { builder.add("empty", at(100), AdaptiveGridSensorSample{}); }
    catch (const std::invalid_argument&) { duplicate = true; }
    try { builder.add("other", at(50), AdaptiveGridSensorSample{}); }
    catch (const std::invalid_argument&) { wrongTime = true; }
    require(duplicate && wrongTime, "Invalid combined frame accepted");
    auto empty = std::move(builder).finish();
    require(empty->second.count("empty") == 1 && std::get<AdaptiveGridSensorSample>(empty->second.at("empty")).cells.empty(),
            "Measured empty is indistinguishable from not due");
}
void transport() {
    SharedBuffer<int> buffer("drain");
    buffer.write(1); buffer.swap(); buffer.write(2); buffer.end();
    require(buffer.read() == 1 && buffer.read() == 2 && !buffer.tryRead() && buffer.isDrained(),
            "Final write queue was lost or reordered");
    require(buffer.read() == 0, "Read after EOF must terminate");
    for (bool cancel : {false, true}) {
        SharedBuffer<int> waiting("waiting");
        auto reader = std::async(std::launch::async, [&] { return waiting.read(); });
        require(reader.wait_for(20ms) == std::future_status::timeout, "Empty blocking read did not wait");
        if (cancel) waiting.requestStop(); else waiting.end();
        require(reader.wait_for(1s) == std::future_status::ready && reader.get() == 0,
                "Shutdown did not wake empty reader");
    }
    SharedBuffer<int> bounded("bounded", 1);
    bounded.write(1);
    auto writer = std::async(std::launch::async, [&] { bounded.write(2); });
    require(writer.wait_for(20ms) == std::future_status::timeout, "Capacity did not bound queue");
    require(bounded.read() == 1, "Bounded FIFO lost first value");
    require(writer.wait_for(1s) == std::future_status::ready, "Consumer did not wake producer");
    writer.get();
    auto cancelled = std::async(std::launch::async, [&] { bounded.write(3); });
    require(cancelled.wait_for(20ms) == std::future_status::timeout, "Second capacity wait missing");
    bounded.requestStop();
    require(cancelled.wait_for(1s) == std::future_status::ready, "Stop did not wake full-queue producer");
    cancelled.get();
    require(bounded.read() == 2 && bounded.isDrained() && bounded.currentWriteFrameIndex == 2,
            "Cancellation inserted data or dropped pending frame");

    SharedBuffer<int> concurrent("concurrent", 7);
    auto producer = std::async(std::launch::async, [&] {
        for (int i = 1; i <= 2000; ++i) concurrent.write(i);
        concurrent.end();
    });
    for (int i = 1; i <= 2000; ++i) require(concurrent.read() == i, "Concurrent FIFO reordered data");
    producer.get();
    require(concurrent.isDrained(), "Concurrent drain failed");
}
void aggregationDisplay() {
    AdaptiveGridDisplayState display;
    const auto snapshot = std::make_shared<const ump::SpatialSelection>();
    SensorFrameBuilder first(at(400));
    first.add("agbs", at(400), AdaptiveGridSensorSample{{{192, {}}}, snapshot});
    auto frame = std::move(first).finish();
    require(display.update(frame, "agbs") && display.aggregationSnapshot() == snapshot,
        "Closed-window snapshot was not routed with its sensor");
    frame.reset();
    require(!display.update({}, "agbs") && display.aggregationSnapshot() == snapshot,
        "No-sample step dropped the last dated aggregation snapshot");
    const auto next = std::make_shared<const ump::SpatialSelection>();
    SensorFrameBuilder second(at(500));
    second.add("agbs", at(500), AdaptiveGridSensorSample{{{192, {}}}, next});
    require(!display.update(std::move(second).finish(), "agbs") && display.aggregationSnapshot() == next,
        "Unchanged sensor geometry prevented a newer aggregation snapshot");
    SensorFrameBuilder empty(at(600));
    empty.add("agbs", at(600), AdaptiveGridSensorSample{});
    display.update(std::move(empty).finish(), "agbs");
    require(!display.aggregationSnapshot(), "Absent debug attachment retained unrelated decisions");
}

}
int main() {
    try {
        contract(); pairing(); completedStepSequence(); gridDisplay(); aggregationDisplay(); transport();
        std::cout << "PASS: complete frames, identity/type routing, old/exact/future selection, "
                     "pause, sparse completed steps, dated grid display, bounded FIFO, concurrent drain and shutdown.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
