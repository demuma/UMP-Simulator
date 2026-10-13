#include "SensorFrameCursor.hpp"
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
    }
    return std::move(builder).finish();
}
void pairing() {
    SharedBuffer<sensorBufferFrameType> buffer("frames");
    SensorFrameCursor cursor;
    require(!cursor.select(at(0), buffer) && !cursor.frame(), "Empty live queue must stay pending");
    buffer.write(frame(0));
    require(cursor.select(at(0), buffer) && cursor.frame()->second.empty(), "Empty step completion lost");
    buffer.write(frame(100, true));
    buffer.write(frame(200, true));
    require(cursor.select(at(50), buffer) && !cursor.frame(), "Future frame used too early/stale frame retained");
    require(buffer.currentReadFrameIndex == 2, "Cursor drained beyond one future frame");
    require(cursor.select(at(100), buffer), "Buffered exact match not returned");
    const auto selected = cursor.frame();
    require(selected && selected->first == at(100), "Wrong selected timestamp");
    require(buffer.currentReadFrameIndex == 2, "Read queue despite local exact match");
    const auto* a = findSensorSample<AdaptiveGridSensorSample>(selected->second, "agbs-a");
    const auto* b = findSensorSample<AdaptiveGridSensorSample>(selected->second, "agbs-b");
    require(a && b && a->cells.at(12).totalAgents == 2 && b->cells.at(15).totalAgents == 4,
            "Sensor IDs not independently routed");
    require(!findSensorSample<AdaptiveGridSensorSample>(selected->second, "abs"), "Payload type confusion");
    require(!findSensorSample<AdaptiveGridSensorSample>(selected->second, "absent"), "Unknown ID reused data");
    require(cursor.select(at(100), buffer) && cursor.frame() == selected
            && buffer.currentReadFrameIndex == 2, "Paused repaint consumed another frame");
    require(cursor.select(at(150), buffer) && !cursor.frame(), "Old data retained between measurements");
    require(cursor.select(at(200), buffer) && cursor.frame()->first == at(200), "Future frame lost");
    require(!cursor.select(at(250), buffer) && !cursor.frame(), "Pending new time retained old measurement");
    buffer.end();
    require(cursor.select(at(250), buffer) && !cursor.frame(), "Missing final frame did not resolve");

    SharedBuffer<sensorBufferFrameType> skipped("skipped");
    skipped.write(frame(0)); skipped.write(frame(50)); skipped.write(frame(100)); skipped.end();
    SensorFrameCursor skipCursor;
    require(skipCursor.select(at(100), skipped) && skipCursor.frame()->first == at(100)
            && skipped.currentReadFrameIndex == 3, "Old frames not discarded");
    require(skipped.isDrained(), "Exact frame left in queue");
    for (int malformedTime : {100, 50}) {
        SharedBuffer<sensorBufferFrameType> malformed("malformed");
        malformed.write(frame(100)); malformed.write(frame(malformedTime));
        SensorFrameCursor check;
        require(check.select(at(100), malformed), "Initial selection failed");
        bool rejected = false;
        try { check.select(at(150), malformed); }
        catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "Duplicate/out-of-order frame silently accepted");
    }
}
void contract() {
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
}
int main() {
    try {
        contract(); pairing(); transport();
        std::cout << "PASS: complete frames, identity/type routing, old/exact/future selection, "
                     "pause, empty steps, bounded FIFO, concurrent drain and shutdown.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
