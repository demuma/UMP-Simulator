#include "SpatialSelection.hpp"
#include "AggregationManager.hpp"
#include "PolicyTree.hpp"
#include <iostream>
#include <stdexcept>

namespace {
using namespace ump;
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected rejection");
}
AggregationConfig settings() {
    AggregationConfig c{"run", "sensor", "app", {0, 0, 80, 80, 3}, 100, 400};
    c.history = HistoryLimits{4000, 64, 10000, 1000000, 32};
    return c;
}
MetricEvaluator policy(double support, double maxSide = 40) {
    return MetricEvaluator(MetricPolicy{"p", "1", {{MetricId::DistinctContributors, support, {}},
        {MetricId::CellSideM, {}, maxSide}}});
}
CellObservation observation(std::string id, int cell) {
    return {std::move(id), "pedestrian", historyCell(settings().coverage, cell, 3)};
}
struct Fixture {
    AggregationConfig c = settings();
    std::vector<AggregationCandidate> windows;
    AggregationManager manager{c, [&](const auto& candidate) { windows.push_back(candidate); }};
    void sample(int time, std::vector<CellObservation> observations) {
        manager.ingest({c.runId, c.sensorId, static_cast<std::uint64_t>(time / 100), time,
            ObservationStatus::Measured, std::move(observations)});
    }
    void period(int start, int perCell) {
        std::vector<CellObservation> observations;
        for (int cell = 192; cell < 196; ++cell)
            for (int n = 0; n < perCell; ++n)
                observations.push_back(observation(std::to_string(cell) + ":" + std::to_string(n), cell));
        for (int t = start ? start : 100; t < start + 400; t += 100) sample(t, observations);
        manager.advance(start + 400);
    }
};

void mergeRefineMerge() {
    Fixture f;
    SpatialSelector selector(f.c, {2, 64});
    const auto evaluator = policy(2);
    f.period(0, 1);
    auto first = selector.select(f.windows.back(), *f.manager.history(), evaluator);
    require(first.selectedCells == 1 && first.suppressedCells == 0
        && first.candidate.cells[0].cell.id == 48 && first.candidate.cells[0].cell.width == 20,
        "Failing leaves did not merge as one sibling group");
    require(first.candidate.cells[0].counts.distinctContributors == 4
        && first.decisions[0].triggerCells.size() == 4, "Parent support or trigger provenance incorrect");
    require(first.attempts.size() == 5, "Search did not stop at the first eligible parent");
    f.period(400, 2);
    auto second = selector.select(f.windows.back(), *f.manager.history(), evaluator);
    require(second.selectedCells == 4 && second.refinedCells == 4, "Next window did not refine the eligible cut");
    for (const auto& cell : second.candidate.cells)
        require(cell.cell.depth == 3 && cell.counts.distinctContributors == 2, "Refined leaf metrics incorrect");
    f.period(800, 1);
    auto third = selector.select(f.windows.back(), *f.manager.history(), evaluator);
    require(third.selectedCells == 1 && third.coarsenedCells == 1, "Later window failed to coarsen again");
    rejects([&] { selector.select(f.windows.back(), *f.manager.history(), evaluator); });
}

void distinctUnionAndNoPartialSiblingRelease() {
    Fixture f;
    f.sample(100, {observation("A", 192), observation("B", 193)});
    f.sample(200, {observation("A", 193), observation("B", 192)});
    f.sample(300, {});
    f.manager.advance(400);
    SpatialSelector selector(f.c, {2, 64});
    const auto result = selector.select(f.windows[0], *f.manager.history(), policy(3));
    require(result.selectedCells == 0 && result.suppressedCells == 1
        && result.candidate.cells[0].counts.distinctContributors == 2,
        "Child distinct counts were summed into a false approval");
    require(result.candidate.cells[0].counts.observationContributions == 4
        && *result.candidate.cells[0].counts.meanSampleOccupancy == 4. / 3.,
        "Spatial selection lost measured-empty samples");

    Fixture sibling;
    std::vector<CellObservation> data{observation("A",192)};
    for (int id = 193; id <= 195; ++id) {
        data.push_back(observation(std::to_string(id)+"A", id));
        data.push_back(observation(std::to_string(id)+"B", id));
    }
    for (int t : {100,200,300}) sibling.sample(t,data);
    sibling.manager.advance(400);
    SpatialSelector limited(sibling.c, {2,64});
    auto noLegalParent = limited.select(sibling.windows[0], *sibling.manager.history(), policy(2,10));
    require(noLegalParent.selectedCells == 0 && noLegalParent.suppressedCells == 1
        && noLegalParent.candidate.cells[0].cell.id == 48,
        "Failed parent released passing siblings or crossed the configured depth cap");
}

void coverageUnknownMetricsAndBudgets() {
    Fixture missing;
    missing.sample(100, {observation("A",192),observation("B",193)});
    missing.manager.advance(400);
    SpatialSelector selector(missing.c, {1,64});
    auto incomplete = selector.select(missing.windows[0], *missing.manager.history(), policy(1));
    require(incomplete.selectedCells == 0 && incomplete.suppressedCells == 1
        && incomplete.assessment.coverageStatus == AssessmentStatus::Unavailable,
        "Missing coverage selected a numeric passing candidate");

    Fixture f; f.period(0,1);
    SpatialSelector unavailable(f.c,{1,64});
    MetricEvaluator offline(MetricPolicy{"p","1",{{MetricId::OccupancyMae,{},2}}});
    require(unavailable.select(f.windows[0], *f.manager.history(), offline).selectedCells == 0,
        "Unavailable required metric selected a candidate");
    SpatialSelector budget(f.c,{1,4});
    rejects([&] { budget.select(f.windows[0], *f.manager.history(), policy(2)); });
    require(budget.select(f.windows[0], *f.manager.history(), policy(1)).selectedCells == 4,
        "Rejected search advanced state or failed to reuse passing leaves");
    rejects([&] { SpatialSelector invalid(f.c,{0,64}); });
    rejects([&] { SpatialSelector invalid(f.c,{4,64}); });
    auto noHistory=f.c; noHistory.history.reset();
    rejects([&] { SpatialSelector invalid(noHistory,{1,64}); });
}

void strictEmptyRegionAndEmptyWindow() {
    Fixture f;
    for (int t : {100,200,300}) f.sample(t,{observation("A",192),observation("B",194)});
    f.manager.advance(400);
    auto tree=std::make_shared<const PolicyTree>(PolicyTreeConfig{"p","1","app",f.c.coverage,
        {{MetricId::DistinctContributors,2,{}}}},
        std::vector<PolicyRegion>{{"empty-strict","test",10,0,10,10,{{MetricId::DistinctContributors,10,{}}},{}}});
    SpatialSelector selector(f.c,{2,64});
    const auto result=selector.select(f.windows[0],*f.manager.history(),MetricEvaluator(tree));
    require(result.selectedCells==0 && result.candidate.cells[0].counts.distinctContributors==2,
        "Parent ignored stricter policy in an empty sibling region");
    require(result.assessment.cells[0].checks[0].requirement.min==10,
        "Parent footprint policy was not re-evaluated");
    f.period(400,0);
    const auto empty=selector.select(f.windows.back(),*f.manager.history(),MetricEvaluator(tree));
    require(empty.candidate.cells.empty() && empty.selectedCells==0 && empty.suppressedCells==0,
        "Measured-empty window retained the previous cut");
}
}

int main() {
    try {
        mergeRefineMerge();
        distinctUnionAndNoPartialSiblingRelease();
        coverageUnknownMetricsAndBudgets();
        strictEmptyRegionAndEmptyWindow();
        std::cout << "Spatial selection passed: merge/refine/merge, unions, complete siblings, depth cap, "
                     "missing coverage, unavailable metrics, budgets and whole-footprint policies.\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
