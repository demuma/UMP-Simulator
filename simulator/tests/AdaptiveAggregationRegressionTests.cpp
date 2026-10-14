#include "AdaptiveAggregation.hpp"
#include "AggregationManager.hpp"
#include "PolicyTree.hpp"
#include <iostream>
#include <stdexcept>

namespace {
using namespace ump;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected explicit rejection");
}
AggregationConfig settings() {
    AggregationConfig c{"run", "sensor", "app", {0, 0, 80, 80, 3}, 100, 400};
    c.history = HistoryLimits{2000, 32, 2000, 100000, 16};
    return c;
}
MetricEvaluator policy(double distinct = 2, double side = 40) {
    return MetricEvaluator(MetricPolicy{"p", "1", {{MetricId::DistinctContributors, distinct, {}},
        {MetricId::CellSideM, {}, side}}});
}
CellObservation observation(std::string id, int cell = 192) {
    return {std::move(id), "pedestrian", historyCell(settings().coverage, cell, 3)};
}
struct Fixture {
    AggregationConfig config = settings();
    AggregationHistory history{config, *config.history};
    std::vector<SpatialSelection> outputs;
    AdaptiveAggregation engine;
    Fixture(AdaptationStrategy strategy = AdaptationStrategy::SpatialFirst,
        MetricEvaluator evaluator = policy(), AggregationTime maxWindow = 800,
        AggregationTime step = 100)
        : engine(config, {strategy, step, maxWindow, 32}, {2, 64}, std::move(evaluator),
            [this](const auto& selection) { outputs.push_back(selection); }) {}
    void sample(AggregationTime time, std::vector<CellObservation> observations = {},
        ObservationStatus status = ObservationStatus::Measured) {
        history.append({config.runId, config.sensorId, static_cast<std::uint64_t>(time / 100),
            time, status, std::move(observations)});
        engine.advance(time, history);
    }
    void advance(AggregationTime time) { history.advance(time); engine.advance(time, history); }
    void finish(AggregationTime time) { history.advance(time); engine.finish(time, history); }
};
bool hasAction(const SpatialSelection& output, TemporalAction action) {
    for (const auto& decision : output.temporalDecisions) if (decision.action == action) return true;
    return false;
}

void exactUnionEarlyReleaseAndOriginalStart() {
    Fixture f;
    for (int time : {100, 200, 300}) f.sample(time, {observation("A")});
    f.sample(400, {observation("B")});
    require(f.outputs.empty() && f.engine.debugState().windowStartMs == 0
        && f.engine.debugState().nextEndMs == 500, "Spatial First did not hold the original window start");
    f.advance(500);
    require(f.outputs.size() == 1, "An eligible extended candidate waited until the global maximum");
    const auto& result = f.outputs[0];
    require(result.candidate.startMs == 0 && result.candidate.endMs == 500
        && result.candidate.counts.distinctContributors == 2
        && result.candidate.counts.observationContributions == 4
        && result.candidate.measuredSamples == 4 && result.candidate.counts.meanSampleOccupancy == 1,
        "Temporal support was summed, lost its original start, or lost measured sample coverage");
    require(result.selectedCells == 1 && result.candidate.cells[0].cell.depth == 3
        && result.temporalExtensions == 1 && result.completionReason == "requirements_met"
        && hasAction(result, TemporalAction::ExtendWindow)
        && !hasAction(result, TemporalAction::CoarsenSpatially), "Unexpected early-release strategy or provenance");
    f.advance(500);
    require(f.outputs.size() == 1, "Repeated progress emitted the same interval twice");
}

void immutableProgressThroughCollectionExtensionAndRelease() {
    Fixture f;
    auto initial = f.engine.progressSnapshot();
    require(initial.strategy == "spatial_first" && initial.startMs == 0 && initial.nextEndMs == 400
        && initial.hardDeadlineMs == 800 && initial.observedThroughMs == 0
        && initial.temporalExtensions == 0 && initial.evaluations == 0
        && initial.phase == AggregationProgressPhase::Collecting && !initial.lastCheck,
        "Initial progress invented a completed check or an incorrect window");
    for (int time : {100,200,300}) f.sample(time, {observation("A")});
    f.advance(350);
    const auto collecting = f.engine.progressSnapshot();
    require(collecting.observedThroughMs == 350 && collecting.evaluations == 0
        && !collecting.lastCheck && collecting.phase == AggregationProgressPhase::Collecting,
        "An unsampled collection tick invented metric evidence or lost simulation progress");

    f.sample(400, {observation("B")});
    const auto extending = f.engine.progressSnapshot();
    require(extending.phase == AggregationProgressPhase::Extending && extending.startMs == 0
        && extending.nextEndMs == 500 && extending.hardDeadlineMs == 800
        && extending.observedThroughMs == 400 && extending.temporalExtensions == 1
        && extending.evaluations == 1 && extending.lastCheck,
        "An accepted extension did not expose its actual pending interval and check");
    require(extending.lastCheck->candidate.startMs == 0 && extending.lastCheck->candidate.endMs == 400
        && extending.lastCheck->candidate.closedAtMs == 400
        && extending.lastCheck->candidate.counts.distinctContributors == 1
        && extending.lastCheck->candidate.counts.observationContributions == 3
        && extending.lastCheck->assessment.status == AssessmentStatus::Fail,
        "Progress evidence was labeled as current support or included the excluded endpoint");
    f.advance(450);
    const auto waiting = f.engine.progressSnapshot();
    require(waiting.observedThroughMs == 450 && waiting.lastCheck == extending.lastCheck
        && waiting.evaluations == 1 && waiting.nextEndMs == 500,
        "Waiting ticks recalculated or copied check evidence instead of sharing its immutable snapshot");

    f.advance(500);
    const auto nextWindow = f.engine.progressSnapshot();
    require(nextWindow.startMs == 500 && nextWindow.nextEndMs == 900
        && nextWindow.hardDeadlineMs == 1300 && nextWindow.observedThroughMs == 500
        && nextWindow.temporalExtensions == 0 && nextWindow.evaluations == 0
        && nextWindow.phase == AggregationProgressPhase::Collecting && !nextWindow.lastCheck,
        "A new window reused the prior window's check or extension state");
    require(extending.lastCheck->candidate.endMs == 400
        && extending.lastCheck->candidate.counts.distinctContributors == 1,
        "A published progress snapshot changed after a later window completed");
    f.sample(500, {observation("C")});
    f.finish(550);
    const auto finished = f.engine.progressSnapshot();
    require(finished.phase == AggregationProgressPhase::Finished
        && finished.observedThroughMs == 550 && !finished.lastCheck,
        "Final progress retained a stale window check or lost the end-of-stream state");
}

void failedSinkPreservesProgressEvidence() {
    auto config = settings();
    AggregationHistory history(config, *config.history);
    bool fail = true;
    AdaptiveAggregation engine(config, {AdaptationStrategy::SpatialFirst,100,800,32}, {2,64}, policy(),
        [&](const SpatialSelection&) { if (fail) throw std::runtime_error("sink failure"); });
    for (int time : {100,200,300,400}) {
        history.append({"run", "sensor", static_cast<std::uint64_t>(time / 100), time,
            ObservationStatus::Measured, {observation(time == 400 ? "B" : "A")}});
        engine.advance(time, history);
    }
    const auto before = engine.progressSnapshot();
    history.advance(500);
    rejects([&] { engine.advance(500, history); });
    const auto after = engine.progressSnapshot();
    require(after.lastCheck == before.lastCheck && after.startMs == before.startMs
        && after.nextEndMs == before.nextEndMs && after.observedThroughMs == before.observedThroughMs
        && after.evaluations == before.evaluations && after.temporalExtensions == before.temporalExtensions
        && after.phase == before.phase,
        "A failed terminal sink changed the accepted progress snapshot");
    fail = false;
    engine.advance(500, history);
    require(engine.progressSnapshot().startMs == 500 && !engine.progressSnapshot().lastCheck,
        "Successful retry failed to retire the old progress evidence");
}

void exactGlobalUnionAcrossMovingCells() {
    Fixture f;
    f.sample(100,{observation("A",192)});
    f.sample(200,{observation("A",193)});
    f.sample(300,{observation("A",192)});
    f.sample(400,{observation("B",192)});
    f.sample(500,{observation("B",193)});
    f.advance(600);
    require(f.outputs.size() == 1 && f.outputs[0].candidate.startMs == 0
        && f.outputs[0].candidate.endMs == 600 && f.outputs[0].candidate.counts.distinctContributors == 2
        && f.outputs[0].candidate.cells.size() == 2
        && f.outputs[0].candidate.cells[0].counts.distinctContributors == 2
        && f.outputs[0].candidate.cells[1].counts.distinctContributors == 2,
        "Whole-grid reconstruction summed cell distinct counts for moving contributors");
}

void sharedManagerProgressAndFinalFlush() {
    for (AggregationTime end : {400,450,500}) {
        auto config = settings();
        std::vector<AggregationCandidate> fixed;
        std::vector<SpatialSelection> adaptive;
        AggregationManager manager(config,[&](const auto& result) { fixed.push_back(result); });
        AdaptiveAggregation engine(config,{AdaptationStrategy::SpatialFirst,100,800,32},{2,64},policy(),
            [&](const auto& result) { adaptive.push_back(result); });
        manager.setProgressSink([&](AggregationTime now, bool finishing) {
            if (finishing) engine.finish(now,*manager.history());
            else engine.advance(now,*manager.history());
        });
        for (int time = 100; time < end; time += 100)
            manager.ingest({"run","sensor",static_cast<std::uint64_t>(time/100),time,
                ObservationStatus::Measured,{observation("A")}});
        manager.finish(end);
        require(adaptive.size() == 1 && adaptive[0].candidate.startMs == 0
            && adaptive[0].candidate.endMs == end && adaptive[0].candidate.truncated
            && adaptive[0].completionReason == "end_of_stream" && engine.debugState().finished,
            "Shared manager progress/final callbacks duplicated or lost an unresolved adaptive interval");
        require(adaptive[0].temporalExtensions == static_cast<std::size_t>(end > 400),
            "A canceled extension at the exact stream end was reported as collected support");
        require(fixed.size() == static_cast<std::size_t>(end > 400 ? 2 : 1),
            "Adaptive progress changed fixed-window diagnostic output");
    }
}

void trueStrategyOrdering() {
    Fixture temporal(AdaptationStrategy::TemporalFirst), spatial(AdaptationStrategy::SpatialFirst);
    for (int time : {100, 200, 300}) {
        temporal.sample(time, {observation("A",192), observation("B",193)});
        spatial.sample(time, {observation("A",192), observation("B",193)});
    }
    temporal.sample(400, {observation("C",192), observation("D",193)});
    spatial.sample(400, {observation("C",192), observation("D",193)});
    require(temporal.outputs.size() == 1 && temporal.outputs[0].candidate.endMs == 400
        && temporal.outputs[0].candidate.cells[0].cell.id == 48
        && temporal.outputs[0].temporalExtensions == 0
        && hasAction(temporal.outputs[0], TemporalAction::CoarsenSpatially),
        "Temporal First did not prefer legal spatial coarsening over temporal extension");
    require(spatial.outputs.empty(), "Spatial First coarsened while temporal extension remained legal");
    spatial.advance(500);
    require(spatial.outputs.size() == 1 && spatial.outputs[0].candidate.endMs == 500
        && spatial.outputs[0].candidate.cells.size() == 2
        && spatial.outputs[0].candidate.cells[0].cell.depth == 3
        && spatial.outputs[0].candidate.cells[1].cell.depth == 3,
        "Spatial First did not preserve the finest spatial cut through extension");
}

void maximumAndConfiguredSteps() {
    Fixture f(AdaptationStrategy::SpatialFirst, policy(2), 800, 200);
    for (int time = 100; time <= 800; time += 100) f.sample(time, {observation("A")});
    require(f.outputs.size() == 1 && f.outputs[0].candidate.endMs == 800
        && f.outputs[0].selectedCells == 0 && f.outputs[0].suppressedCells == 1
        && f.outputs[0].candidate.counts.distinctContributors == 1
        && f.outputs[0].temporalExtensions == 2 && f.outputs[0].completionReason == "max_window",
        "Maximum duration, configured extension steps, or repeated-identity suppression failed");
    std::vector<AggregationTime> probes;
    for (const auto& step : f.outputs[0].temporalDecisions)
        if (step.action == TemporalAction::EvaluateFinest) probes.push_back(step.endMs);
    require(probes == std::vector<AggregationTime>({400,600,800}), "Temporal probes ignored configured extension steps");
    require(hasAction(f.outputs[0], TemporalAction::CoarsenSpatially), "Spatial First omitted spatial fallback at its maximum");
}

void regionalDeadlineIncludingEmptyFootprintAndPassingNeighbor() {
    for (auto metric : {MetricId::WindowDurationMs, MetricId::AgeAtEvaluationMs}) {
        auto config = settings();
        auto tree = std::make_shared<const PolicyTree>(PolicyTreeConfig{"regional","1","app",config.coverage,
            {{MetricId::DistinctContributors,2,{}}, {MetricId::CellSideM,{},10}}},
            std::vector<PolicyRegion>{{"empty-deadline","test",10,0,10,10,{{metric,{},500}},{}}});
        Fixture f(AdaptationStrategy::SpatialFirst, MetricEvaluator(tree), 1000);
        for (int time : {100,200,300,400,500})
            f.sample(time, {observation("A",192), observation("B",192), observation("C",208)});
        require(f.outputs.size() == 1 && f.outputs[0].candidate.endMs == 500
            && f.outputs[0].selectedCells == 1 && f.outputs[0].suppressedCells == 1
            && f.outputs[0].completionReason == "policy_deadline"
            && f.outputs[0].temporalExtensions == 1,
            "An empty region's hard deadline held a passing neighbor until the global maximum");
        require(f.outputs[0].candidate.cells[1].cell.id == 192 && f.outputs[0].decisions[1].selected,
            "Deadline finalization lost independently eligible support");
    }
    // The conservative common deadline can precede the nominal initial window.
    auto config = settings();
    auto tree = std::make_shared<const PolicyTree>(PolicyTreeConfig{"short","1","app",config.coverage,
        {{MetricId::DistinctContributors,2,{}}, {MetricId::WindowDurationMs,{},350}}}, std::vector<PolicyRegion>{});
    Fixture shortWindow(AdaptationStrategy::SpatialFirst, MetricEvaluator(tree));
    for (int time : {100,200,300}) shortWindow.sample(time, {observation("A")});
    require(shortWindow.outputs.size() == 1 && shortWindow.outputs[0].candidate.endMs == 300,
        "A regional deadline before the initial window was not aligned down and honored");
}

void missingUnavailableAndLateEvaluation() {
    Fixture missing;
    missing.sample(100, {observation("A"), observation("B")});
    missing.advance(400);
    require(missing.outputs.size() == 1 && missing.outputs[0].selectedCells == 0
        && missing.outputs[0].completionReason == "coverage_unavailable"
        && missing.outputs[0].candidate.missingSamples == 2,
        "Numeric support bypassed missing coverage or extended irreparable history");
    Fixture unavailable;
    unavailable.sample(100, {observation("A"), observation("B")});
    unavailable.sample(200, {}, ObservationStatus::Unavailable);
    unavailable.sample(300);
    unavailable.advance(400);
    require(unavailable.outputs.size() == 1 && unavailable.outputs[0].selectedCells == 0
        && unavailable.outputs[0].candidate.unavailableSamples == 1,
        "Unavailable sampling coverage selected a candidate");
    auto config = settings();
    auto tree = std::make_shared<const PolicyTree>(PolicyTreeConfig{"age","1","app",config.coverage,
        {{MetricId::DistinctContributors,2,{}}, {MetricId::AgeAtEvaluationMs,{},500}}}, std::vector<PolicyRegion>{});
    Fixture late(AdaptationStrategy::SpatialFirst, MetricEvaluator(tree));
    for (int time : {100,200,300}) late.sample(time, {observation("A"),observation("B")});
    late.advance(600);
    require(!late.outputs.empty() && late.outputs[0].selectedCells == 0
        && late.outputs[0].candidate.closedAtMs == 600,
        "A late evaluation pretended to release at a historical deadline");
}

void finalFlushAndTransactionalSelection() {
    Fixture f;
    for (int time : {100,200,300,400}) f.sample(time, {observation("A")});
    require(f.outputs.empty(), "Failed initial candidate unexpectedly finalized");
    f.finish(450);
    require(f.outputs.size() == 1 && f.outputs[0].candidate.startMs == 0
        && f.outputs[0].candidate.endMs == 450 && f.outputs[0].candidate.truncated
        && f.outputs[0].candidate.measuredSamples == 4
        && f.outputs[0].completionReason == "end_of_stream" && f.engine.debugState().finished,
        "Final partial extension failed to retain complete support and original start");
    rejects([&] { f.engine.finish(450,f.history); });
    rejects([&] { f.engine.advance(500,f.history); });
    Fixture exact;
    for (int time : {100,200,300}) exact.sample(time,{observation("A")});
    exact.finish(400);
    require(exact.outputs.size() == 1 && exact.outputs[0].candidate.endMs == 400,
        "An exact-boundary final flush extended beyond the stream end");

    auto config = settings();
    AggregationHistory history(config,*config.history);
    bool fail = true;
    std::vector<SpatialSelection> outputs;
    AdaptiveAggregation engine(config,{AdaptationStrategy::TemporalFirst,100,800,32},{2,64},policy(),
        [&](const auto& output) {
            if (fail) throw std::runtime_error("sink failure");
            outputs.push_back(output);
        });
    for (int time : {100,200,300})
        history.append({"run","sensor",static_cast<std::uint64_t>(time/100),time,ObservationStatus::Measured,
            {observation("A"),observation("B",193)}});
    history.advance(400);
    rejects([&] { engine.advance(400,history); });
    require(engine.debugState().windowStartMs == 0 && engine.debugState().completedWindows == 0
        && engine.debugState().temporalEvaluations == 0, "A failed terminal sink committed provisional state");
    fail = false;
    engine.advance(400,history);
    require(outputs.size() == 1 && outputs[0].decisions[0].transition == "initial",
        "Retry after sink failure reused an already committed spatial transition");
    engine.advance(400,history);
    require(outputs.size() == 1, "Retry emitted duplicate support");
}

void refinementAndBoundedLongRun() {
    Fixture f(AdaptationStrategy::TemporalFirst);
    for (int time : {100,200,300}) f.sample(time,{observation("A",192),observation("B",193)});
    f.advance(400);
    for (int time : {400,500,600,700})
        f.sample(time,{observation("A",192),observation("B",192),observation("C",193),observation("D",193),
            observation("E",208),observation("F",209)});
    f.advance(800);
    require(f.outputs.size() == 2 && f.outputs[1].refinedCells == 2 && f.outputs[1].selectedCells == 3
        && f.outputs[1].candidate.cells[0].cell.id == 52,
        "Adaptive transitions lost a valid mixed-depth cut or next-window refinement");
    AggregationTime expectedStart = 0;
    for (const auto& output : f.outputs) {
        require(output.candidate.startMs == expectedStart, "Adaptive terminal windows overlap or skip support");
        expectedStart = output.candidate.endMs;
    }
    for (int time = 800; time <= 20000; time += 100)
        f.sample(time,{observation("A",192),observation("B",193)});
    require(f.engine.debugState().retainedDecisions <= 3 && f.history.debugState().bins <= 21
        && f.history.debugState().observations <= 50,
        "Adaptive state or shared history grew with run duration");
    expectedStart = 0;
    for (const auto& output : f.outputs) {
        require(output.candidate.startMs == expectedStart && output.candidate.endMs > expectedStart,
            "Long replay repeated or skipped a released interval");
        expectedStart = output.candidate.endMs;
    }
}

void validationAndHistoryLoss() {
    auto c = settings();
    const auto sink = [](const SpatialSelection&) {};
    rejects([&] { AdaptiveAggregation e(c,{AdaptationStrategy::SpatialFirst,150,800,32},{2,64},policy(),sink); });
    rejects([&] { AdaptiveAggregation e(c,{AdaptationStrategy::SpatialFirst,100,300,32},{2,64},policy(),sink); });
    rejects([&] { AdaptiveAggregation e(c,{AdaptationStrategy::SpatialFirst,100,800,2},{2,64},policy(),sink); });
    rejects([&] { AdaptiveAggregation e(c,{static_cast<AdaptationStrategy>(99),100,800,32},{2,64},policy(),sink); });
    for (auto metric : {MetricId::WindowDurationMs, MetricId::AgeAtEvaluationMs}) {
        MetricEvaluator largeMaximum(MetricPolicy{"large","1",{
            {MetricId::DistinctContributors,2,{}}, {metric,{},9007199254740991.0}}});
        AdaptiveAggregation e(c,{AdaptationStrategy::SpatialFirst,100,800,32},{2,64},largeMaximum,sink);
        require(e.debugState().hardDeadlineMs == 800 && e.debugState().nextEndMs == 400,
            "A large positive policy maximum tightened or overflowed the configured cap");
    }
    c.history->retentionMs=400;
    rejects([&] { AdaptiveAggregation e(c,{AdaptationStrategy::SpatialFirst,100,800,32},{2,64},policy(),sink); });
    auto otherConfig = settings();
    otherConfig.applicationId = "other-application";
    AggregationHistory otherHistory(otherConfig,*otherConfig.history);
    for (int time : {100,200,300})
        otherHistory.append({"run","sensor",static_cast<std::uint64_t>(time/100),time,
            ObservationStatus::Measured,{observation("A")}});
    otherHistory.advance(400);
    Fixture wrongStream;
    rejects([&] { wrongStream.engine.advance(400,otherHistory); });
    require(wrongStream.engine.debugState().temporalEvaluations == 0
        && wrongStream.engine.debugState().nextEndMs == 400,
        "A deferred Spatial First proposal advanced with another application's history");
    Fixture evicted;
    evicted.history.append({"run","sensor",1,100,ObservationStatus::Measured,{observation("A")}});
    evicted.history.advance(2500);
    rejects([&] { evicted.engine.advance(2500,evicted.history); });
    require(evicted.outputs.empty() && evicted.engine.debugState().windowStartMs == 0,
        "An evicted interval produced a plausible release or advanced the cut");
    rejects([&] { evicted.engine.advance(2600,evicted.history); });
}
}
int main() {
    try {
        exactUnionEarlyReleaseAndOriginalStart(); immutableProgressThroughCollectionExtensionAndRelease();
        failedSinkPreservesProgressEvidence(); exactGlobalUnionAcrossMovingCells();
        sharedManagerProgressAndFinalFlush(); trueStrategyOrdering(); maximumAndConfiguredSteps();
        regionalDeadlineIncludingEmptyFootprintAndPassingNeighbor(); missingUnavailableAndLateEvaluation();
        finalFlushAndTransactionalSelection(); refinementAndBoundedLongRun(); validationAndHistoryLoss();
        std::cout << "PASS: adaptive strategy order, exact temporal unions, early release, regional deadlines, "
            "coverage, final flush, provisional cuts, immutable progress, refinement, disjointness and bounded replay.\n";
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
