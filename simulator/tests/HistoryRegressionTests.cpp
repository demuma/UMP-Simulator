#include "AggregationManager.hpp"
#include "CandidateMetrics.hpp"
#include "PolicyTree.hpp"
#include <cmath>
#include <iostream>
#include <set>
#include <stdexcept>

namespace {
using namespace ump;
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected explicit rejection");
}
AggregationConfig config() { return {"run", "sensor", "app", {0, 0, 80, 80, 4}, 100, 400}; }
HistoryLimits limits() { return {1000, 32, 1000, 64000, 16}; }
CellGeometry cell(int id = 768, int depth = 4) { return historyCell(config().coverage, id, depth); }
CellObservation observation(std::string id, int leaf = 768, std::string type = "pedestrian") {
    return {std::move(id), std::move(type), cell(leaf)};
}
ObservationBatch sample(int time, std::vector<CellObservation> observations = {}) {
    return {"run", "sensor", static_cast<std::uint64_t>(time / 100), time,
        ObservationStatus::Measured, std::move(observations)};
}
AggregationCandidate result(const HistoryQuery& query) {
    require(query.candidate.has_value(), "Expected a reconstructed candidate");
    return *query.candidate;
}

void reconstructionAndBuckets() {
    AggregationHistory history(config(), limits());
    const BucketKey active{768, 4, 0, 1}, parent{192, 3, 0, 1}, nextSibling{769, 4, 400, 2};
    history.openBucket({active, 400, 600, 1000, BucketRole::Active});
    history.openBucket({parent, 400, 800, 1000, BucketRole::Preemptive});
    require(history.queryBucket(parent).status == HistoryQueryStatus::Future, "Future bucket pretended to be complete");
    auto first = sample(100, {observation("A")});
    history.append(first);
    first.observations[0].contributorId = "mutated"; // History must own its observations.
    history.append(sample(200, {observation("A"), observation("B", 768, "bike")}));
    history.append(sample(300, {observation("A", 769)}));
    history.advance(400);
    history.openBucket({nextSibling, 800, 1000, 1400, BucketRole::Active});
    const auto p = result(history.queryBucket(parent));
    const auto left = result(history.queryBucket(active)), right = result(history.query(cell(769), 0, 400));
    require(p.counts.observationContributions == 4 && p.counts.distinctContributors == 2,
        "Parent summed child uniques or retained references to mutable input");
    require(left.counts.distinctContributors == 2 && right.counts.distinctContributors == 1,
        "Leaf support incorrect");
    require(p.measuredSamples == 3 && std::abs(*p.counts.meanSampleOccupancy - 4. / 3.) < 1e-12,
        "Parent sample mean/coverage incorrect");
    require(p.counts.typeObservationContributions.at("pedestrian") == 3
        && p.counts.typeObservationContributions.at("bike") == 1, "Type counts changed meaning");
    require(history.bucket(parent)->state == BucketState::Closed
        && history.bucket(nextSibling)->state == BucketState::Collecting, "Sibling windows were synchronized implicitly");
    require(result(history.query(cell(12, 1), 0, 400)).counts.distinctContributors == 2,
        "Unprepared ancestor could not reconstruct complete history");
    const auto ancestor = historyAncestor(config().coverage, cell(), 3);
    require(ancestor.id == 12 && ancestor.depth == 1 && ancestor.width * ancestor.height == 64 * 25,
        "Three relative ancestor levels did not cover 64 finest-cell areas");
    rejects([&] { historyAncestor(config().coverage, cell(), 4); });
    const auto empty = result(history.query(cell(13, 1), 0, 400));
    require(empty.coverage == WindowCoverage::Complete && empty.cells.size() == 1
        && empty.counts.observationContributions == 0 && empty.counts.meanSampleOccupancy == 0,
        "Known-empty sibling support was lost");

    history.extendBucket(parent, 600);
    require(history.bucket(parent)->state == BucketState::Collecting, "Extension did not reopen observation collection");
    history.append(sample(400, {observation("C")}));
    history.append(sample(500));
    history.advance(600);
    require(result(history.query(cell(192, 3), 0, 400)).counts.observationContributions == 4,
        "Endpoint sample leaked into historical prefix");
    const auto extended = result(history.queryBucket(parent));
    require(extended.startMs == 0 && extended.endMs == 600 && extended.counts.distinctContributors == 3
        && extended.measuredSamples == 5 && extended.counts.meanSampleOccupancy == 1,
        "Temporal extension lost start, empty sample or exact unions");
    require(history.bucket(active)->endMs == 400 && history.bucket(nextSibling)->key.startMs == 400,
        "Parent query mutated independent sibling windows");
    const auto subset = result(history.query(cell(192, 3), 175, 350));
    require(subset.expectedSamples == 2 && subset.counts.observationContributions == 3, "Fine interval query failed");
    auto tree = std::make_shared<const PolicyTree>(PolicyTreeConfig{"p", "1", "app", config().coverage,
        {{MetricId::DistinctContributors, 3, {}}}}, std::vector<PolicyRegion>{});
    MetricEvaluator evaluate(tree);
    require(evaluate.evaluate(p, 600).status == AssessmentStatus::Fail
        && evaluate.evaluate(extended, 600).status == AssessmentStatus::Pass,
        "Reconstruction did not integrate with regional policy/metric evaluation");
    require(history.discardBucket(active) && !history.bucket(active)
        && result(history.queryBucket(parent)).counts.distinctContributors == 3,
        "Discarding a logical bucket consumed shared history");
    rejects([&] { history.extendBucket(parent, 900); });
    rejects([&] { history.openBucket({parent, 400, 800, 1000, BucketRole::Preemptive}); });
    history.advance(1000);
    require(history.bucket(parent).has_value(), "Inclusive evaluation deadline expired early");
    history.advance(1001);
    require(!history.bucket(parent) && history.debugState().expiredBuckets == 1,
        "Expired candidate record leaked or pinned history forever");
    require(history.query(cell(), 0, 400).status == HistoryQueryStatus::Evicted, "Evicted interval returned plausible counts");
    rejects([&] { history.queryBucket(parent); });
}

void completenessAndValidation() {
    AggregationHistory history(config(), limits());
    history.append(sample(100));
    auto unavailable = sample(300); unavailable.status = ObservationStatus::Unavailable;
    history.append(unavailable);
    history.advance(400);
    const auto incomplete = history.query(cell(), 0, 400);
    const auto c = result(incomplete);
    require(incomplete.status == HistoryQueryStatus::Incomplete && c.measuredSamples == 1
        && c.unavailableSamples == 1 && c.missingSamples == 1 && c.counts.meanSampleOccupancy == 0,
        "Missing/unavailable/empty sample coverage was conflated");
    require(history.query(cell(), 0, 50).status == HistoryQueryStatus::NoScheduledSamples,
        "t=0 became a fabricated measurement");
    require(history.query(cell(), 0, 500).status == HistoryQueryStatus::Future, "Future query returned counts");
    const auto before = history.debugState();
    rejects([&] { history.append(sample(300)); });
    rejects([&] { history.append(sample(450)); });
    rejects([&] { auto b = sample(500); b.runId = "other"; history.append(b); });
    rejects([&] { history.append(sample(500, {observation("A"), observation("A")})); });
    rejects([&] { auto b = sample(500, {observation("A")}); b.observations[0].cell.x += 5; history.append(b); });
    rejects([&] { auto b = sample(500, {observation("A")}); b.status = ObservationStatus::Unavailable; history.append(b); });
    rejects([&] { history.query({3, 0, 0, 0, 80, 80}, 0, 400); });
    rejects([&] { history.query(cell(), -1, 400); });
    rejects([&] { history.advance(399); });
    rejects([&] { history.openBucket({{768,4,0,1}, 400, 800, 1100, BucketRole::Active}); });
    require(history.debugState().bins == before.bins && history.debugState().watermarkMs == before.watermarkMs,
        "Invalid operations mutated retained state");
    auto bad = limits(); bad.retentionMs = 350;
    rejects([&] { AggregationHistory check(config(), bad); });
    auto g = config(); g.coverage.leafDepth = 15;
    rejects([&] { AggregationHistory check(g, limits()); });
}

void budgetsAndManagerIntegration() {
    for (int bound = 0; bound < 3; ++bound) {
        auto budget = limits();
        if (bound == 0) budget.maxBins = 1;
        if (bound == 1) budget.maxObservations = 1;
        if (bound == 2) budget.maxIdentityBytes = 2;
        AggregationHistory history(config(), budget);
        history.append(sample(100, {observation("A", 768, "p")}));
        rejects([&] { history.append(sample(200, {observation("B", 768, "p")})); });
        require(history.debugState().bins == 1 && history.debugState().watermarkMs == 100, "Budget error mutated history");
        history.append(sample(1200, {observation("B", 768, "p")}));
        require(history.debugState().bins == 1 && history.debugState().observations == 1,
            "Projected expiration did not free budget");
    }
    auto budget = limits(); budget.maxBuckets = 1;
    AggregationHistory limited(config(), budget);
    limited.openBucket({{768,4,0,1},400,400,1000,BucketRole::Active});
    rejects([&] { limited.openBucket({{769,4,0,1},400,400,1000,BucketRole::Preemptive}); });
    require(limited.debugState().buckets == 1, "Bucket budget not enforced");

    auto setup = config(); setup.history = limits();
    std::vector<AggregationCandidate> windows;
    AggregationManager manager(setup, [&](const auto& c) { windows.push_back(c); });
    manager.openBucket({{192,3,0,1},400,600,1000,BucketRole::Preemptive});
    manager.ingest(sample(100, {observation("A")}));
    manager.ingest(sample(200, {observation("A"), observation("B")}));
    manager.ingest(sample(300, {observation("A", 769)}));
    manager.advance(400);
    require(windows.size() == 1 && windows[0].counts.distinctContributors == 2
        && manager.debugState().retainedIdentityMemberships == 0
        && result(manager.history()->query(cell(192,3),0,400)).counts.distinctContributors == 2,
        "History did not survive fixed-window closure or altered output");
    manager.ingest(sample(400)); manager.finish(450);
    require(manager.history()->debugState().watermarkMs == 450
        && result(manager.history()->query(cell(192,3),0,450)).measuredSamples == 4,
        "Finished manager lost bounded research history");
    rejects([&] { manager.ingest(sample(500)); });

    setup.windowMs = 200; setup.history->maxObservations = 1;
    int outputs = 0;
    AggregationManager rejectBeforeOutput(setup,[&](const auto&) { ++outputs; });
    rejectBeforeOutput.ingest(sample(100,{observation("A")}));
    rejects([&] { rejectBeforeOutput.ingest(sample(200,{observation("B")})); });
    require(outputs == 0 && rejectBeforeOutput.debugState().windowStartMs == 0
        && rejectBeforeOutput.history()->debugState().watermarkMs == 100,
        "Failed history append emitted fixed output or advanced state");
}

// Independent brute-force rectangle/time oracle exercises every tree depth and retention.
void boundedReplayOracle() {
    auto setup = config(); auto budget = limits(); budget.retentionMs = 400; budget.maxBins = 5;
    AggregationHistory history(setup, budget);
    std::vector<ObservationBatch> oracle;
    for (int step = 1; step <= 300; ++step) {
        const int time = step * 100;
        if (step % 7 != 0) {
            auto b = sample(time);
            if (step % 11 == 0) b.status = ObservationStatus::Unavailable;
            else if (step % 5 != 0) for (int id = 0; id < 4; ++id)
                b.observations.push_back(observation(std::to_string(id), 768 + (step * 17 + id * 31) % 256));
            oracle.push_back(b); history.append(b);
        } else history.advance(time);
        const auto from = std::max(0, time - 400);
        for (const auto footprint : {cell(12,1),cell(48,2),cell(192,3),cell()}) {
            const auto actual = result(history.query(footprint, from, time));
            std::set<std::string> ids;
            std::uint64_t measured=0, unavailable=0, contributions=0, expected=0;
            for (int at = 100; at < time; at += 100) if (at >= from) ++expected;
            for (const auto& b : oracle) if (b.observedAtMs >= from && b.observedAtMs < time) {
                if (b.status == ObservationStatus::Unavailable) { ++unavailable; continue; }
                ++measured;
                for (const auto& o : b.observations) if (o.cell.x >= footprint.x && o.cell.y >= footprint.y
                    && o.cell.x < footprint.x + footprint.width && o.cell.y < footprint.y + footprint.height) {
                    ++contributions; ids.insert(o.contributorId);
                }
            }
            require(actual.expectedSamples == expected && actual.measuredSamples == measured
                && actual.unavailableSamples == unavailable && actual.missingSamples == expected-measured-unavailable
                && actual.counts.observationContributions == contributions && actual.counts.distinctContributors == ids.size(),
                "History query differs from independent replay oracle");
        }
        require(history.debugState().bins <= 5 && history.debugState().observations <= 20,
            "Retained data grew with run length");
    }
}
}
int main() {
    try {
        reconstructionAndBuckets(); completenessAndValidation(); budgetsAndManagerIntegration(); boundedReplayOracle();
        std::cout << "PASS: exact spatial/temporal reconstruction, logical buckets, deadlines, coverage, budgets and bounded replay.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
