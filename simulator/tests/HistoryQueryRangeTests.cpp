#include "AggregationHistory.hpp"
#include "SemanticTaxonomy.hpp"
#include <algorithm>
#include <cmath>
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
AggregationConfig settings(int depth = 6) {
    AggregationConfig c{"range-run", "agbs", "app", {-40,-20,80,80,depth}, 100, 400};
    c.history = HistoryLimits{400,8,1000,1000000,64};
    c.semanticTaxonomy = std::make_shared<const SemanticTaxonomy>("range-taxonomy", "1",
        std::vector<SemanticNode>{{"road_user","",1,{}},
            {"pedestrian","road_user",.5,{}}, {"adult","pedestrian",0,{"Adult","Adult alias"}},
            {"child","pedestrian",0,{"Child"}}, {"cyclist","road_user",0,{"Cyclist"}}});
    return c;
}
CellObservation row(const AggregationConfig& c, std::string identity, int leaf,
    std::string type = "Adult") {
    return {std::move(identity),std::move(type),historyCell(c.coverage,leaf,c.coverage.leafDepth)};
}
ObservationBatch sample(int time, std::vector<CellObservation> rows = {},
    ObservationStatus status = ObservationStatus::Measured) {
    return {"range-run","agbs",static_cast<std::uint64_t>(time / 100),time,status,std::move(rows)};
}
AggregationCandidate candidate(const HistoryQuery& found) {
    require(found.candidate.has_value(),"A retained query lost its candidate");
    return *found.candidate;
}
void unchanged(const HistoryDebugState& a, const HistoryDebugState& b) {
    require(a.watermarkMs == b.watermarkMs && a.retainedFromMs == b.retainedFromMs
        && a.bins == b.bins && a.observations == b.observations && a.identityBytes == b.identityBytes
        && a.buckets == b.buckets && a.expiredBuckets == b.expiredBuckets,
        "A read or rejected append changed retained history");
}
bool sameCell(const CellGeometry& a, const CellGeometry& b) {
    return a.id == b.id && a.depth == b.depth && a.x == b.x && a.y == b.y
        && a.width == b.width && a.height == b.height;
}
void sameCounts(const AggregateCounts& a, const AggregateCounts& b) {
    require(a.observationContributions == b.observationContributions
        && a.distinctContributors == b.distinctContributors
        && a.typeObservationContributions == b.typeObservationContributions
        && a.meanSampleOccupancy == b.meanSampleOccupancy
        && a.semanticEvidence.has_value() == b.semanticEvidence.has_value(),
        "History range changed scalar, identity, source-type or occupancy statistics");
    if (!a.semanticEvidence) return;
    const auto& x = *a.semanticEvidence; const auto& y = *b.semanticEvidence;
    require(x.taxonomyId == y.taxonomyId && x.taxonomyVersion == y.taxonomyVersion
        && x.nodes.size() == y.nodes.size(),"Semantic evidence provenance or node set changed");
    for (const auto& [id,n] : x.nodes) {
        const auto& other = y.nodes.at(id);
        require(n.observationContributions == other.observationContributions
            && n.distinctContributors == other.distinctContributors,
            "History range changed exact semantic identity unions");
    }
}

// Independent oracle: scan the original, unsorted rows by rectangle and time.
// Its identity sets and taxonomy parent lists do not call history queries,
// prefix arithmetic, SemanticAccumulator or SemanticTaxonomy::select.
void compareOracle(const AggregationHistory& history, const std::vector<ObservationBatch>& raw,
    const CellGeometry& cell, int start, int end) {
    const auto found = history.query(cell,start,end);
    const auto actual = candidate(found);
    AggregateCounts expected;
    expected.semanticEvidence = SemanticEvidence{"range-taxonomy","1",{}};
    const std::vector<std::string> nodes{"road_user","pedestrian","adult","child","cyclist"};
    std::map<std::string,std::set<std::string>> nodeIdentities;
    for (const auto& node : nodes) expected.semanticEvidence->nodes.emplace(node,SemanticNodeCounts{});
    std::set<std::string> identities;
    std::uint64_t scheduled = 0, measured = 0, unavailable = 0;
    for (int time = 100; time < end; time += 100) if (time >= start) ++scheduled;
    for (const auto& batch : raw) {
        if (batch.observedAtMs < start || batch.observedAtMs >= end) continue;
        if (batch.status == ObservationStatus::Unavailable) { ++unavailable; continue; }
        ++measured;
        for (const auto& observation : batch.observations) {
            const auto& at = observation.cell;
            if (at.x < cell.x || at.y < cell.y || at.x >= cell.x + cell.width
                || at.y >= cell.y + cell.height) continue;
            ++expected.observationContributions;
            ++expected.typeObservationContributions[observation.type];
            identities.insert(observation.contributorId);
            const std::string leaf = observation.type == "Child" ? "child"
                : observation.type == "Cyclist" ? "cyclist" : "adult";
            std::vector<std::string> path{"road_user",leaf};
            if (leaf != "cyclist") path.push_back("pedestrian");
            for (const auto& node : path) {
                ++expected.semanticEvidence->nodes.at(node).observationContributions;
                nodeIdentities[node].insert(observation.contributorId);
            }
        }
    }
    expected.distinctContributors = identities.size();
    if (measured) expected.meanSampleOccupancy = static_cast<double>(expected.observationContributions) / measured;
    for (const auto& node : nodes)
        expected.semanticEvidence->nodes.at(node).distinctContributors = nodeIdentities[node].size();
    const auto missing = scheduled - measured - unavailable;
    const auto status = !scheduled ? HistoryQueryStatus::NoScheduledSamples
        : missing || unavailable ? HistoryQueryStatus::Incomplete : HistoryQueryStatus::Complete;
    require(found.status == status && actual.expectedSamples == scheduled && actual.measuredSamples == measured
        && actual.unavailableSamples == unavailable && actual.missingSamples == missing,
        "History range changed empty, missing, unavailable or half-open sample coverage");
    require(actual.startMs == start && actual.endMs == end && !actual.truncated
        && actual.closedAtMs == history.debugState().watermarkMs
        && actual.cells.size() == 1 && sameCell(actual.cells.front().cell,cell),
        "History range changed interval, requested geometry or explicit zero-support cell");
    sameCounts(actual.counts,expected); sameCounts(actual.cells.front().counts,expected);
}

void unsortedSparseRangeOracleAcrossDepths() {
    std::size_t checks = 0;
    for (int depth : {1,2,6,14}) {
        const auto c = settings(depth); AggregationHistory history(c,*c.history);
        std::vector<ObservationBatch> raw;
        const int first = 3 << (2 * depth), count = 1 << (2 * depth), quarter = count / 4;
        // Include the highest legal leaf and both sides of every base-cell edge.
        const std::vector<int> leaves{first + count - 1,first,first + quarter,
            first + quarter - 1,first + 2 * quarter,first + 3 * quarter - 1,
            first + 3 * quarter,first + 2 * quarter - 1};
        for (int step = 1; step <= 24; ++step) {
            const int time = step * 100;
            if (step % 7 == 0) history.advance(time);
            else {
                auto batch = sample(time);
                if (step % 11 == 0) batch.status = ObservationStatus::Unavailable;
                else if (step % 5 != 0) {
                    for (std::size_t person = 0; person < leaves.size(); ++person) {
                        const auto type = person % 3 == 0 ? "Cyclist" : person % 3 == 1 ? "Child"
                            : step % 2 ? "Adult" : "Adult alias";
                        batch.observations.push_back(row(c,"p" + std::to_string(person),
                            leaves[(person + step) % leaves.size()],type));
                    }
                    std::rotate(batch.observations.begin(),batch.observations.begin() + step % leaves.size(),
                        batch.observations.end());
                }
                raw.push_back(batch); history.append(batch);
            }
            const auto before = history.debugState();
            const int start = std::max(0,time - 400);
            for (int level = 1; level <= depth; ++level) {
                std::set<int> domains;
                for (int leaf : leaves) domains.insert(leaf >> (2 * (depth - level)));
                // An interior zero-support cell exists when the tree is deep enough.
                domains.insert((3 << (2 * level)) + (1 << (2 * level)) / 2);
                for (int id : domains) {
                    const auto domain = historyCell(c.coverage,id,level);
                    compareOracle(history,raw,domain,start,time); ++checks;
                    if (time > 200) {
                        compareOracle(history,raw,domain,time - 175,time - 50); ++checks;
                    }
                }
            }
            unchanged(before,history.debugState());
            require(before.bins <= 5 && before.observations <= 40,"Range queries pinned expired samples");
        }
    }
    require(checks > 5000,"Sparse range oracle unexpectedly lost depth/time coverage");
}

void permutationOwnershipAndGeometry() {
    const auto c = settings(2); AggregationHistory left(c,*c.history), right(c,*c.history);
    for (int step = 1; step <= 3; ++step) {
        auto batch = sample(step * 100,{row(c,"a",63),row(c,"b",48,"Child"),
            row(c,"c",52,"Cyclist"),row(c,"d",49),row(c,"e",48,"Adult alias")});
        const auto original = batch.observations;
        left.append(batch);
        for (std::size_t i = 0; i < original.size(); ++i)
            require(batch.observations[i].contributorId == original[i].contributorId
                && sameCell(batch.observations[i].cell,original[i].cell),"Append sorted caller-owned rows");
        std::reverse(batch.observations.begin(),batch.observations.end());
        right.append(batch);
        batch.observations.clear();
    }
    left.advance(400); right.advance(400);
    for (const auto domain : {std::optional<CellGeometry>{},std::optional<CellGeometry>{historyCell(c.coverage,12,1)}}) {
        const auto a = candidate(left.queryFinest(0,400,domain));
        const auto b = candidate(right.queryFinest(0,400,domain));
        sameCounts(a.counts,b.counts);
        require(a.cells.size() == b.cells.size(),"Input permutation changed finest sparse cut");
        for (std::size_t i = 0; i < a.cells.size(); ++i) {
            require(sameCell(a.cells[i].cell,b.cells[i].cell),"Input permutation changed finest geometry");
            sameCounts(a.cells[i].counts,b.cells[i].counts);
        }
    }
    const auto a = left.queryOccupiedLeaves(0,400), b = right.queryOccupiedLeaves(0,400);
    require(a.cells && b.cells && a.cells->size() == b.cells->size(),"Input permutation changed occupied support");
    for (std::size_t i = 0; i < a.cells->size(); ++i)
        require(sameCell(a.cells->at(i),b.cells->at(i)),"Input permutation changed occupied geometry");
    auto tolerated = historyCell(c.coverage,48,2); tolerated.x += 0.0000005;
    const auto requested = candidate(left.query(tolerated,0,400));
    require(sameCell(requested.cells.front().cell,tolerated),"Range query normalized accepted caller geometry");
    require(requested.counts.observationContributions == 6,"Geometry tolerance changed ID-based ownership");
}

void conflictScopeAndRejectedAppendAreUnchanged() {
    const auto c = settings(2); AggregationHistory history(c,*c.history);
    history.append(sample(100,{row(c,"stable",48),row(c,"moving",63,"Child")}));
    history.append(sample(200,{row(c,"moving",62,"Cyclist"),row(c,"stable",49,"Adult alias")}));
    history.advance(300);
    const auto before = history.debugState();
    const auto safe = candidate(history.query(historyCell(c.coverage,12,1),0,300));
    require(safe.counts.observationContributions == 2 && safe.counts.distinctContributors == 1,
        "Unrelated type conflict contaminated a scoped range query");
    rejects([&] { (void)history.query(historyCell(c.coverage,15,1),0,300); });
    rejects([&] { (void)history.queryFinest(0,300); });
    rejects([&] { (void)history.queryOccupiedLeaves(0,300); });
    unchanged(before,history.debugState());
    rejects([&] { history.append(sample(1000,{row(c,"new",63),row(c,"bad",48,"Unknown")})); });
    rejects([&] { history.append(sample(1000,{row(c,"duplicate",63),row(c,"duplicate",48)})); });
    auto invalid = sample(1000,{row(c,"new",63),row(c,"bad",48)});
    invalid.observations.back().cell.x += 5;
    rejects([&] { history.append(invalid); });
    unchanged(before,history.debugState());
    // Rejections did not consume the later sequence or evict rows; a valid retry is accepted.
    history.append(sample(1000,{row(c,"new",63)})); history.advance(1100);
    const auto retained = candidate(history.query(historyCell(c.coverage,63,2),1000,1100));
    require(retained.counts.observationContributions == 1 && history.debugState().observations == 1,
        "Sort/append changed sequence retry, retention or highest-leaf inclusion");
    require(history.query(historyCell(c.coverage,12,1),0,2000).status == HistoryQueryStatus::Evicted,
        "Range query changed eviction-before-future precedence");
    require(history.query(historyCell(c.coverage,63,2),1000,1200).status == HistoryQueryStatus::Future,
        "Range query returned future support");
}
}
int main() {
    try {
        unsortedSparseRangeOracleAcrossDepths(); permutationOwnershipAndGeometry();
        conflictScopeAndRejectedAppendAreUnchanged();
        std::cout << "PASS: sparse history ranges, >5000 independent rectangle/time oracle checks, "
            "depth-14 boundaries, semantic scope, permutation, input ownership and atomic rejection.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
