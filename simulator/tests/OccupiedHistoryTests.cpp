#include "AggregationHistory.hpp"
#include "SemanticTaxonomy.hpp"
#include <algorithm>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ump;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class F> void rejects(F work) {
    try { work(); } catch (const std::invalid_argument&) { return; }
    throw std::runtime_error("Expected explicit invalid-argument rejection");
}
std::shared_ptr<const SemanticTaxonomy> taxonomy() {
    return std::make_shared<const SemanticTaxonomy>("occupied-taxonomy", "1",
        std::vector<SemanticNode>{{"road_user", "", 1, {}},
            {"pedestrian", "road_user", .5, {}},
            {"adult", "pedestrian", 0, {"Adult", "Adult alias"}},
            {"child", "pedestrian", 0, {"Child"}},
            {"cyclist", "road_user", 0, {"Cyclist"}}});
}
AggregationConfig settings(int depth = 2, bool semantic = true) {
    AggregationConfig c{"occupied-run", "agbs", "app", {0,0,80,80,depth}, 100, 400};
    c.history = HistoryLimits{1000,32,10000,1000000,64};
    if (semantic) c.semanticTaxonomy = taxonomy();
    return c;
}
CellObservation row(const AggregationConfig& c, std::string id, int leaf,
    std::string type = "Adult") {
    return {std::move(id), std::move(type), historyCell(c.coverage, leaf, c.coverage.leafDepth)};
}
ObservationBatch sample(int time, std::vector<CellObservation> rows = {},
    ObservationStatus status = ObservationStatus::Measured) {
    return {"occupied-run", "agbs", static_cast<std::uint64_t>(time / 100), time,
        status, std::move(rows)};
}
std::vector<int> ids(const HistoryOccupiedLeavesQuery& found) {
    require(found.cells.has_value(), "A retained occupied query lost its sparse result");
    std::vector<int> out;
    for (const auto& cell : *found.cells) out.push_back(cell.id);
    return out;
}
void expect(const AggregationHistory& history, AggregationTime from, AggregationTime to,
    HistoryQueryStatus status, const std::vector<int>& expected) {
    const auto found = history.queryOccupiedLeaves(from,to);
    require(found.status == status && ids(found) == expected,
        "Occupied leaves/status differ from independently expected sample support");
    // The legacy full-evidence API is an additional compatibility check, not the oracle above.
    const auto full = history.queryFinest(from,to);
    require(full.status == status && full.candidate.has_value(),
        "Occupied discovery changed legacy full-evidence availability");
    std::vector<int> fullIds;
    for (const auto& cell : full.candidate->cells) fullIds.push_back(cell.cell.id);
    require(fullIds == expected, "Occupied discovery changed the legacy sparse finest cut");
}
void unchanged(const HistoryDebugState& before, const HistoryDebugState& after) {
    require(before.watermarkMs == after.watermarkMs && before.retainedFromMs == after.retainedFromMs
        && before.bins == after.bins && before.observations == after.observations
        && before.identityBytes == after.identityBytes && before.buckets == after.buckets
        && before.expiredBuckets == after.expiredBuckets,
        "Occupied discovery mutated the bounded private history");
}

void sparseSortedSupportOwnsInputAndNormalizesGeometry() {
    const auto c = settings(); AggregationHistory history(c,*c.history);
    auto first = sample(100,{row(c,"c",60,"Cyclist"),row(c,"a",48),row(c,"b",49,"Child")});
    // Append accepts a small floating tolerance, but queries expose canonical ID geometry.
    first.observations[1].cell.x = 0.0000005;
    history.append(first);
    first.observations[1].cell = historyCell(c.coverage,52,2);
    first.observations[1].type = "Unknown caller mutation";
    history.append(sample(200,{row(c,"a",49,"Adult alias"),row(c,"b",49,"Child"),
        row(c,"c",52,"Cyclist")}));
    history.append(sample(300,{row(c,"a",48),row(c,"c",60,"Cyclist")}));
    history.advance(400);
    const auto before = history.debugState();
    expect(history,0,400,HistoryQueryStatus::Complete,{48,49,52,60});
    auto found = history.queryOccupiedLeaves(0,400);
    const std::vector<double> xs{0,20,40,40}, ys{0,0,0,40};
    for (std::size_t i = 0; i < found.cells->size(); ++i) {
        const auto& cell = found.cells->at(i);
        require(cell.depth == 2 && cell.x == xs[i] && cell.y == ys[i]
            && cell.width == 20 && cell.height == 20,
            "Occupied discovery forwarded tolerated input geometry instead of canonical cells");
    }
    found.cells->clear();
    expect(history,0,400,HistoryQueryStatus::Complete,{48,49,52,60});
    unchanged(before,history.debugState());
}

void halfOpenSamplesAndCoverageStates() {
    const auto c = settings(); AggregationHistory history(c,*c.history);
    history.append(sample(100,{row(c,"a",48)}));
    history.append(sample(200,{row(c,"b",49)}));
    history.append(sample(300,{row(c,"c",52)}));
    history.append(sample(400,{row(c,"d",60)}));
    history.advance(450);
    expect(history,0,100,HistoryQueryStatus::NoScheduledSamples,{});
    expect(history,101,199,HistoryQueryStatus::NoScheduledSamples,{});
    expect(history,100,300,HistoryQueryStatus::Complete,{48,49});
    expect(history,175,350,HistoryQueryStatus::Complete,{49,52});
    expect(history,400,450,HistoryQueryStatus::Complete,{60});

    AggregationHistory partial(c,*c.history);
    partial.append(sample(100)); // Measured empty, not missing or unavailable.
    partial.append(sample(300,{},ObservationStatus::Unavailable)); // 200 is missing.
    partial.append(sample(400,{row(c,"a",48)}));
    partial.advance(500);
    expect(partial,0,200,HistoryQueryStatus::Complete,{});
    expect(partial,0,400,HistoryQueryStatus::Incomplete,{});
    expect(partial,0,500,HistoryQueryStatus::Incomplete,{48});
    expect(partial,200,400,HistoryQueryStatus::Incomplete,{});
}

void futureEvictionAndInvalidIntervalsDoNotMutate() {
    auto c = settings(); c.history->retentionMs = 400;
    AggregationHistory history(c,*c.history);
    history.append(sample(100,{row(c,"a",48)}));
    history.append(sample(200,{row(c,"b",49)}));
    history.append(sample(300,{row(c,"c",52)}));
    history.advance(500); // The inclusive retention boundary still includes t=100.
    expect(history,100,400,HistoryQueryStatus::Complete,{48,49,52});
    auto found = history.queryOccupiedLeaves(100,600);
    require(found.status == HistoryQueryStatus::Future && !found.cells,
        "Future discovery exposed plausible observed support");
    history.advance(501); // t=100 now expired.
    found = history.queryOccupiedLeaves(100,400);
    require(found.status == HistoryQueryStatus::Evicted && !found.cells,
        "Expired discovery exposed a plausible partial cut");
    found = history.queryOccupiedLeaves(100,700);
    require(found.status == HistoryQueryStatus::Evicted && !found.cells,
        "Occupied discovery changed eviction-before-future precedence");
    const auto before = history.debugState();
    for (const auto& interval : std::vector<std::pair<AggregationTime,AggregationTime>>{
        {-1,400},{200,200},{400,300}})
        rejects([&] { (void)history.queryOccupiedLeaves(interval.first,interval.second); });
    unchanged(before,history.debugState());
    expect(history,200,400,HistoryQueryStatus::Complete,{49,52});
}

void globalCanonicalValidationAliasesAndDisabledMode() {
    const auto c = settings(); AggregationHistory history(c,*c.history);
    history.append(sample(100,{row(c,"same",48)}));
    history.append(sample(200,{row(c,"same",60,"Child")}));
    history.advance(300);
    const auto before = history.debugState();
    // A conflict in different cells must not disappear when per-leaf evidence is removed.
    rejects([&] { (void)history.queryOccupiedLeaves(0,300); });
    rejects([&] { (void)history.queryFinest(0,300); });
    unchanged(before,history.debugState());
    expect(history,0,200,HistoryQueryStatus::Complete,{48});
    expect(history,200,300,HistoryQueryStatus::Complete,{60});
    require(history.queryOccupiedLeaves(0,400).status == HistoryQueryStatus::Future,
        "Future discovery validated unavailable future evidence before returning its status");
    expect(history,0,100,HistoryQueryStatus::NoScheduledSamples,{});

    AggregationHistory aliases(c,*c.history);
    aliases.append(sample(100,{row(c,"same",48)}));
    aliases.append(sample(200,{row(c,"same",60,"Adult alias")}));
    aliases.advance(300);
    expect(aliases,0,300,HistoryQueryStatus::Complete,{48,60});
    const auto good = aliases.debugState();
    rejects([&] { aliases.append(sample(300,{row(c,"new",49,"Unknown")})); });
    unchanged(good,aliases.debugState());

    const auto old = settings(2,false); AggregationHistory legacy(old,*old.history);
    legacy.append(sample(100,{row(old,"same",48,"Old Label")}));
    legacy.append(sample(200,{row(old,"same",60,"Different Old Label")}));
    legacy.advance(300);
    expect(legacy,0,300,HistoryQueryStatus::Complete,{48,60});
}

void sparseDepthFourteenAcrossAllBaseCells() {
    const auto c = settings(14); AggregationHistory history(c,*c.history);
    const std::vector<int> leaves{805306368,872415232,939524096,1073741823};
    std::vector<CellObservation> rows;
    for (auto it = leaves.rbegin(); it != leaves.rend(); ++it)
        rows.push_back(row(c,std::to_string(*it),*it));
    history.append(sample(100,rows)); history.append(sample(200,rows)); history.advance(300);
    expect(history,0,300,HistoryQueryStatus::Complete,leaves);
    const auto found = history.queryOccupiedLeaves(0,300);
    const double side = 80. / 16384;
    const std::vector<double> xs{0,40,0,80-side}, ys{0,0,40,80-side};
    for (std::size_t i = 0; i < leaves.size(); ++i) {
        const auto& cell = found.cells->at(i);
        require(cell.depth == 14 && cell.x == xs[i] && cell.y == ys[i]
            && cell.width == side && cell.height == side,
            "Sparse depth-14 discovery overflowed IDs or changed canonical geometry");
    }
    require(found.cells->size() == 4 && history.debugState().observations == 8,
        "Sparse discovery materialized empty leaves or consumed source observations");
}

// Time/row scanning below is independent of the history implementation and its counters.
void boundedMixedCoverageOracleAcrossAllDepths() {
    for (int depth : {1,2,4,6,14}) {
        auto c = settings(depth,false); c.history->retentionMs = 400; c.history->maxBins = 5;
        AggregationHistory history(c,*c.history);
        std::vector<ObservationBatch> raw;
        const int first = 3 << (2 * depth), count = 1 << (2 * depth);
        for (int step = 1; step <= 100; ++step) {
            const int time = step * 100;
            if (step % 7 == 0) history.advance(time);
            else {
                auto next = sample(time);
                if (step % 11 == 0) next.status = ObservationStatus::Unavailable;
                else if (step % 5 != 0)
                    for (int person = 0; person < 4; ++person)
                        next.observations.push_back(row(c,std::to_string(person),
                            first + (step * 17 + person * 31) % count));
                history.append(next); raw.push_back(next);
            }
            const int from = std::max(0,time-400);
            std::set<int> expected; int measured = 0, unavailable = 0, scheduled = 0;
            for (int at = 100; at < time; at += 100) if (at >= from) ++scheduled;
            for (const auto& batch : raw)
                if (from <= batch.observedAtMs && batch.observedAtMs < time) {
                    if (batch.status == ObservationStatus::Unavailable) { ++unavailable; continue; }
                    ++measured;
                    for (const auto& item : batch.observations) expected.insert(item.cell.id);
                }
            const auto status = scheduled == 0 ? HistoryQueryStatus::NoScheduledSamples
                : measured == scheduled && unavailable == 0 ? HistoryQueryStatus::Complete
                : HistoryQueryStatus::Incomplete;
            const auto before = history.debugState();
            expect(history,from,time,status,std::vector<int>(expected.begin(),expected.end()));
            unchanged(before,history.debugState());
            require(history.debugState().bins <= 5 && history.debugState().observations <= 20,
                "Occupied queries pinned expired source history across a long run");
        }
    }
}
}
int main() {
    try {
        sparseSortedSupportOwnsInputAndNormalizesGeometry();
        halfOpenSamplesAndCoverageStates();
        futureEvictionAndInvalidIntervalsDoNotMutate();
        globalCanonicalValidationAliasesAndDisabledMode();
        sparseDepthFourteenAcrossAllBaseCells();
        boundedMixedCoverageOracleAcrossAllDepths();
        std::cout << "PASS: occupied-leaf discovery, canonical sparse geometry, coverage/expiry, "
                     "semantic validation, nonmutation and 500 independent replay-oracle checks.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
