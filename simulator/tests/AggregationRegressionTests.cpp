#include "AggregationManager.hpp"
#include <cmath>
#include <iostream>
#include <set>
#include <stdexcept>

namespace {
using namespace ump;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}
template<class Function> void rejects(Function action, const std::string& message) {
    bool rejected = false;
    try { action(); } catch (const std::exception&) { rejected = true; }
    require(rejected, message);
}

AggregationConfig config() {
    return {"run", "agbs", "test", {0, 0, 20, 20, 2}, 100, 400, 1000};
}
CellObservation observation(const std::string& id, int cell = 1, std::string type = "pedestrian") {
    return {id, std::move(type), {cell, 2, cell == 1 ? 0. : 10., 0., 10., 10.}};
}
ObservationBatch batch(AggregationTime time, std::vector<CellObservation> observations = {}) {
    return {"run", "agbs", static_cast<std::uint64_t>(time / 100), time,
        ObservationStatus::Measured, std::move(observations)};
}

void countsAndBoundaries() {
    std::vector<AggregationCandidate> output;
    AggregationManager manager(config(), [&](const auto& candidate) { output.push_back(candidate); });
    manager.advance(0);
    manager.advance(50);
    require(output.empty(), "Initialization fabricated a measurement/output");
    manager.ingest(batch(100, {observation("A")}));
    manager.ingest(batch(200, {observation("A"), observation("B", 1, "bike")}));
    manager.ingest(batch(300, {observation("A", 2)}));
    manager.advance(400);
    require(output.size() == 1, "Non-sampling advance did not close elapsed window");
    const auto& first = output.front();
    require(first.startMs == 0 && first.endMs == 400 && first.closedAtMs == 400 && !first.truncated,
        "Half-open window boundaries incorrect");
    require(first.expectedSamples == 3 && first.measuredSamples == 3 && first.coverage == WindowCoverage::Complete,
        "t=0 incorrectly expected as a measurement");
    require(first.counts.observationContributions == 4 && first.counts.distinctContributors == 2,
        "Repeated/cross-cell observations counted as distinct people");
    require(first.counts.typeObservationContributions.at("pedestrian") == 3
        && first.counts.typeObservationContributions.at("bike") == 1, "Type contribution semantics incorrect");
    require(std::abs(*first.counts.meanSampleOccupancy - 4. / 3.) < 1e-12, "Stream sample mean incorrect");
    require(first.cells.size() == 2 && first.cells[0].cell.id == 1 && first.cells[1].cell.id == 2,
        "Sparse cell output must be sorted");
    require(first.cells[0].counts.distinctContributors == 2 && first.cells[1].counts.distinctContributors == 1,
        "Per-cell identity union incorrect");
    require(*first.cells[0].counts.meanSampleOccupancy == 1
        && std::abs(*first.cells[1].counts.meanSampleOccupancy - 1. / 3.) < 1e-12,
        "Absent cells must contribute zero only at measured samples");
    require(manager.debugState().retainedCells == 0 && manager.debugState().retainedIdentityMemberships == 0,
        "Closed window retained identities");

    manager.ingest(batch(400, {observation("A")})); // Exactly at watermark is allowed.
    manager.ingest(batch(500)); // Measured empty.
    manager.finish(550);
    require(output.size() == 2 && output.back().truncated && output.back().endMs == 550,
        "Partial stream end not emitted exactly once");
    require(output.back().expectedSamples == 2 && output.back().measuredSamples == 2
        && output.back().coverage == WindowCoverage::Complete, "Partial interval coverage incorrect");
    require(output.back().counts.observationContributions == 1
        && *output.back().counts.meanSampleOccupancy == .5, "Measured-empty sample omitted from denominator");
    require(manager.debugState().finished && manager.debugState().retainedIdentityMemberships == 0,
        "Finished stream still retains contributor IDs");
    rejects([&] { manager.advance(600); }, "Finished stream accepted more time");
}

void missingAndUnavailable() {
    std::vector<AggregationCandidate> output;
    AggregationManager manager(config(), [&](const auto& candidate) { output.push_back(candidate); });
    manager.ingest(batch(100));
    auto unavailable = batch(200);
    unavailable.status = ObservationStatus::Unavailable;
    manager.ingest(unavailable);
    manager.advance(800); // Missing 300 and every observation in [400,800).
    require(output.size() == 2, "Advance did not report empty trailing intervals");
    require(output[0].measuredSamples == 1 && output[0].unavailableSamples == 1
        && output[0].missingSamples == 1 && output[0].coverage == WindowCoverage::Incomplete,
        "Missing/unavailable/empty were conflated");
    require(output[0].counts.meanSampleOccupancy == 0. && output[0].cells.empty(),
        "Measured empty should have zero sample mean and sparse cells");
    require(output[1].missingSamples == 4 && !output[1].counts.meanSampleOccupancy,
        "Unobserved interval was treated as zero occupancy");
    manager.finish(800);
    require(output.size() == 2, "Exact-boundary finish duplicated output");

    std::vector<AggregationCandidate> early;
    AggregationManager shortRun(config(), [&](const auto& c) { early.push_back(c); });
    shortRun.finish(50);
    require(early.size() == 1 && early[0].coverage == WindowCoverage::NoScheduledSamples
        && !early[0].counts.meanSampleOccupancy, "Startup-only interval fabricated zero occupancy");
}

void invalidInputAndBounds() {
    const auto sink = [](const AggregationCandidate&) {};
    auto invalid = config();
    invalid.capabilities = InputCapabilities::CountsOnly;
    rejects([&] { AggregationManager m(invalid, sink); }, "Count-only input promised distinct people");
    invalid = config(); invalid.windowMs = 250;
    rejects([&] { AggregationManager m(invalid, sink); }, "Unaligned window accepted");
    invalid = config(); invalid.maxObservationsPerWindow = 0;
    rejects([&] { AggregationManager m(invalid, sink); }, "Unbounded/zero budget accepted");
    invalid = config(); invalid.coverage.width = -1;
    rejects([&] { AggregationManager m(invalid, sink); }, "Invalid grid accepted");

    std::vector<AggregationCandidate> output;
    auto limited = config(); limited.maxObservationsPerWindow = 2;
    AggregationManager manager(limited, [&](const auto& c) { output.push_back(c); });
    manager.ingest(batch(100, {observation("A")}));
    rejects([&] { manager.ingest(batch(100, {observation("A")})); }, "Duplicate batch accepted");
    auto wrong = batch(200); wrong.sensorId = "another";
    rejects([&] { manager.ingest(wrong); }, "Wrong sensor accepted");
    wrong = batch(200); wrong.runId = "another";
    rejects([&] { manager.ingest(wrong); }, "Wrong run accepted");
    rejects([&] { manager.ingest(batch(200, {observation("A"), observation("A", 2)})); },
        "Same identity counted twice in one batch");
    auto changed = observation("A"); changed.cell.width = 5;
    rejects([&] { manager.ingest(batch(200, {changed})); }, "Changing cell support accepted");
    auto outside = observation("A"); outside.cell.x = 30;
    rejects([&] { manager.ingest(batch(200, {outside})); }, "Out-of-coverage observation accepted");
    auto unknown = batch(200, {observation("A")}); unknown.status = ObservationStatus::Unavailable;
    rejects([&] { manager.ingest(unknown); }, "Unavailable input with observations accepted");
    rejects([&] { manager.ingest(batch(150)); }, "Off-cadence measurement accepted");
    unknown = batch(200); unknown.status = static_cast<ObservationStatus>(99);
    rejects([&] { manager.ingest(unknown); }, "Unknown observation status accepted");
    require(manager.debugState().observationContributions == 1 && output.empty(),
        "Invalid input mutated the active window");
    manager.ingest(batch(200, {observation("A")}));
    rejects([&] { manager.ingest(batch(300, {observation("B")})); }, "Capacity silently exceeded");
    require(manager.debugState().observationContributions == 2, "Budget rejection partially counted input");
    manager.advance(350);
    rejects([&] { manager.ingest(batch(300)); }, "Late observation crossed watermark");
    rejects([&] { manager.advance(300); }, "Clock reversal accepted");
    manager.finish(400);
    require(output.size() == 1 && output[0].missingSamples == 1, "Rejected data silently counted as empty");

    AggregationManager endCheck(config(), sink);
    endCheck.ingest(batch(100));
    rejects([&] { endCheck.finish(100); }, "Exclusive end discarded last observation");
    endCheck.finish(101);

    AggregationManager failedSink(config(), [](const auto&) { throw std::runtime_error("sink failure"); });
    failedSink.ingest(batch(100, {observation("A")}));
    rejects([&] { failedSink.advance(400); }, "Sink failure was swallowed");
}

void repeatedWindowsAndIndependentStreams() {
    std::uint64_t completed = 0;
    std::set<std::string> expectedIds;
    std::uint64_t expectedContributions = 0;
    AggregationManager manager(config(), [&](const auto& c) {
        require(c.counts.distinctContributors == expectedIds.size()
            && c.counts.observationContributions == expectedContributions,
            "Repeated-window output differs from independent set/count oracle");
        require(c.coverage == WindowCoverage::Complete, "Complete stream lost coverage");
        expectedIds.clear(); expectedContributions = 0; ++completed;
    });
    for (int time = 100; time < 40000; time += 100) {
        manager.advance(time); // Closes previous interval before updating the oracle.
        std::vector<CellObservation> observations;
        for (int agent = 0; agent < (time / 100) % 4; ++agent) {
            const auto id = "person-" + std::to_string(agent);
            observations.push_back(observation(id, (time / 100 + agent) % 2 + 1));
            expectedIds.insert(id); ++expectedContributions;
        }
        manager.ingest(batch(time, std::move(observations)));
        require(manager.debugState().retainedCells <= 2 && manager.debugState().retainedIdentityMemberships <= 9,
            "State grew beyond the current window's identities/cells");
    }
    manager.finish(40000);
    require(completed == 100, "Wrong number of fixed windows");

    std::vector<AggregationCandidate> isolated;
    auto other = config(); other.applicationId = "another-application";
    AggregationManager independent(other, [&](const auto& c) { isolated.push_back(c); });
    independent.ingest(batch(100, {observation("new")}));
    independent.finish(150);
    require(isolated[0].applicationId == "another-application"
        && isolated[0].counts.distinctContributors == 1, "Application state contaminated another stream");
}
}

int main() {
    try {
        countsAndBoundaries();
        missingAndUnavailable();
        invalidInputAndBounds();
        repeatedWindowsAndIndependentStreams();
        std::cout << "PASS: aggregation counts/unions, boundaries, coverage, empty/missing input, "
                     "validation, budget, finalization and bounded independent streams.\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << '\n';
        return 1;
    }
}
