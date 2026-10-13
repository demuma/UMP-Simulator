#include "PolicyTree.hpp"
#include <algorithm>
#include <iostream>
#include <limits>

namespace {
using namespace ump;
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
template<class F> void rejects(F work, const char* fragment) {
    try { work(); } catch (const std::exception& error) {
        require(std::string(error.what()).find(fragment) != std::string::npos, error.what()); return;
    }
    throw std::runtime_error(std::string("Expected rejection: ") + fragment);
}
PolicyTreeConfig setup() {
    return {"regional-demo", "1", "application", {0, 0, 80, 80, 3},
        {{MetricId::DistinctContributors, 3, {}}, {MetricId::CellSideM, {}, 40},
         {MetricId::WindowDurationMs, {}, 1000}}, 65536};
}
CellGeometry cell(int id, int depth, double x, double y, double side) { return {id, depth, x, y, side, side}; }
const MetricRequirement& bound(const EffectiveMetricPolicy& policy, MetricId id) {
    const auto found = std::find_if(policy.requirements.begin(), policy.requirements.end(),
        [&](const auto& requirement) { return requirement.id == id; });
    if (found == policy.requirements.end()) throw std::runtime_error("Missing inherited requirement");
    return *found;
}
AggregationCandidate candidate(std::vector<CellGeometry> cells) {
    AggregationCandidate result{"run", "sensor", "application", setup().grid, 0, 400, 400, false,
        3, 3, 0, 0, WindowCoverage::Complete, {}, {}};
    for (const auto& geometry : cells) result.cells.push_back({geometry, {4, 4, {{"pedestrian", 4}}, 4. / 3}});
    result.counts = {4 * cells.size(), cells.empty() ? 0u : 4u, {}, 4. * cells.size() / 3};
    return result;
}

void inheritanceAndEvaluation() {
    std::vector<PolicyRegion> regions{
        {"west", "residential", 0, 0, 40, 40, {{MetricId::DistinctContributors, 5, {}}},
            {{MetricId::DistinctContributors, 2, {}}, {MetricId::AgeAtEvaluationMs, {}, 1500}}},
        {"east", "traffic", 40, 0, 40, 40, {{MetricId::DistinctContributors, 1, {}}}, {}}};
    auto tree = std::make_shared<const PolicyTree>(setup(), regions);
    require(tree->nodeCount() == 5, "Homogeneous regions expanded unnecessary data leaves");
    const auto west = cell(192, 3, 0, 0, 10), east = cell(208, 3, 40, 0, 10), outside = cell(224, 3, 0, 40, 10);
    const auto& p = tree->resolve(west);
    require(bound(p, MetricId::DistinctContributors).min == 5, "Weaker regional rule relaxed inherited minimum");
    require(bound(tree->resolve(east), MetricId::DistinctContributors).min == 3, "Parent footprint contaminated a child");
    require(bound(tree->resolve(outside), MetricId::DistinctContributors).min == 3, "Root fallback lost");
    require(&p == &tree->resolve(cell(195, 3, 10, 10, 10)), "Homogeneous descendants do not share compiled policy");
    require(std::find(p.sources.begin(), p.sources.end(), "region_type:residential") != p.sources.end(), "Type provenance lost");
    const auto before = tree->nodeCount();
    for (int i = 0; i < 1000; ++i) tree->resolve(west);
    require(tree->nodeCount() == before, "Lookup mutated compiled tree");
    MetricEvaluator evaluator(tree);
    const auto assessed = evaluator.evaluate(candidate({west, east, outside}), 400);
    require(assessed.policyMode == "regional_tree" && assessed.policyId == "regional-demo"
        && assessed.policyVersion == "1", "Regional policy identity missing");
    require(assessed.status == AssessmentStatus::Fail && assessed.cells[0].status == AssessmentStatus::Fail
        && assessed.cells[1].status == AssessmentStatus::Pass && assessed.cells[2].status == AssessmentStatus::Pass,
        "Identical support did not follow local requirements");
    require(assessed.cells[0].effectivePolicyId == p.id && assessed.cells[0].policyFeasible,
        "Failed metric confused with an infeasible policy");
    auto missing = candidate({west}); missing.expectedSamples = 4; missing.missingSamples = 1;
    missing.coverage = WindowCoverage::Incomplete;
    require(evaluator.evaluate(missing, 400).status == AssessmentStatus::Unavailable, "Tree bypassed coverage gate");
    auto wrong = candidate({west}); wrong.applicationId = "different";
    rejects([&] { evaluator.evaluate(wrong, 400); }, "application/grid");
    wrong = candidate({west}); wrong.grid.leafDepth = 4;
    rejects([&] { evaluator.evaluate(wrong, 400); }, "application/grid");
    auto secondSetup = setup(); secondSetup.id = "other-app"; secondSetup.applicationId = "other";
    secondSetup.rootRequirements = {{MetricId::DistinctContributors, 9, {}}};
    PolicyTree independent(secondSetup, {});
    require(bound(independent.resolve(west), MetricId::DistinctContributors).min == 9
        && bound(tree->resolve(east), MetricId::DistinctContributors).min == 3,
        "Independent application policies shared mutable state");
    std::reverse(regions.begin(), regions.end());
    PolicyTree reordered(setup(), regions);
    require(reordered.resolve(west).id == p.id, "Region input order changed effective policy identifiers");
}

void crossRegionConflict() {
    std::vector<PolicyRegion> regions{
        {"fine", "fine-type", 0, 0, 20, 40, {{MetricId::CellSideM, 5, 10}}, {}},
        {"coarse", "coarse-type", 20, 0, 20, 40, {{MetricId::CellSideM, 20, 40}}, {}}};
    auto tree = std::make_shared<const PolicyTree>(setup(), regions);
    const auto parent = cell(12, 1, 0, 0, 40);
    const auto& combined = tree->resolve(parent);
    require(!combined.feasible && bound(combined, MetricId::CellSideM).min == 20
        && bound(combined, MetricId::CellSideM).max == 10, "Cross-region contradiction was weakened");
    require(combined.sources.size() == 5, "Parent ignored a touched region without observed contributions");
    const auto left = cell(192, 3, 0, 0, 10), right = cell(49, 2, 20, 0, 20);
    require(tree->resolve(left).feasible && tree->resolve(right).feasible, "Infeasible parent contaminated its children");
    MetricEvaluator evaluator(tree);
    const auto bad = evaluator.evaluate(candidate({parent}), 400);
    require(bad.status == AssessmentStatus::Fail && !bad.cells[0].policyFeasible, "Infeasible footprint passed");
    require(std::any_of(bad.cells[0].checks.begin(), bad.cells[0].checks.end(), [](const auto& check) {
        return check.reason == "contradictory_policy_bounds" && check.status == AssessmentStatus::Fail;
    }), "Missing policy conflict reason");
    require(evaluator.evaluate(candidate({left, right}), 400).status == AssessmentStatus::Pass,
        "Valid finer candidates rejected with their parent");
    require(tree->resolve(cell(13, 1, 40, 0, 40)).feasible, "Adjacent default cell inherited unrelated constraints");
}

void validationAndSparseDepth() {
    auto config = setup();
    const PolicyRegion good{"a", "type", 0, 0, 40, 40, {{MetricId::DistinctContributors, 5, {}}}, {}};
    rejects([&] { auto g = config; g.grid.height = 40; PolicyTree(g, {}); }, "square");
    rejects([&] { auto g = config; g.grid.leafDepth = 15; PolicyTree(g, {}); }, "depth");
    rejects([&] { auto g = config; g.version.clear(); PolicyTree(g, {}); }, "version");
    rejects([&] { auto g = config; g.rootRequirements.clear(); PolicyTree(g, {}); }, "empty");
    rejects([&] { PolicyTree(config, {good, good}); }, "unique");
    rejects([&] { auto other = good; other.id = "b"; PolicyTree(config, {good, other}); }, "Overlapping");
    rejects([&] { auto other = good; other.width = 10; other.x = 5; PolicyTree(config, {other}); }, "aligned");
    rejects([&] { auto other = good; other.x = 80; PolicyTree(config, {other}); }, "outside");
    rejects([&] { auto other = good; other.width = 0; PolicyTree(config, {other}); }, "dimensions");
    rejects([&] { auto other = good; other.x = std::numeric_limits<double>::quiet_NaN(); PolicyTree(config, {other}); }, "outside");
    rejects([&] { auto other = good; other.instanceRequirements = {{MetricId::CellSideM, 41, {}}}; PolicyTree(config, {other}); }, "Contradictory inherited");
    rejects([&] { auto other = good; other.id = "b"; other.x = 40;
        other.typeRequirements = {{MetricId::DistinctContributors, 6, {}}}; PolicyTree(config, {good, other}); }, "Inconsistent");
    PolicyTree tree(config, {good});
    rejects([&] { tree.resolve(cell(192, 2, 0, 0, 10)); }, "ID");
    rejects([&] { tree.resolve(cell(192, 3, 40, 0, 10)); }, "geometry");
    rejects([&] { tree.resolve(cell(192, 3, 0, 0, 20)); }, "geometry");
    rejects([&] { tree.resolve(cell(-1, 3, 0, 0, 10)); }, "ID");
    rejects([&] { tree.resolve(cell(3, 0, 0, 0, 80)); }, "ID");

    config.grid.leafDepth = 14;
    PolicyTree deep(config, {good});
    require(deep.nodeCount() == 5, "Depth limit caused full-tree materialization");
    auto tiny = good; tiny.width = tiny.height = 80. / (1 << 14);
    PolicyTree narrow(config, {tiny});
    require(narrow.nodeCount() == 57, "Single finest leaf did not create only its boundary path");
    require(bound(narrow.resolve(cell(3 << 28, 14, 0, 0, tiny.width)), MetricId::DistinctContributors).min == 5,
        "Deep cell lookup failed");
    config.maxNodes = 56;
    rejects([&] { PolicyTree(config, {tiny}); }, "max_nodes");
    config.maxNodes = 1;
    require(PolicyTree(config, {}).nodeCount() == 1, "Root-only tree unnecessarily subdivided");
}
}
int main() {
    try {
        inheritanceAndEvaluation(); crossRegionConflict(); validationAndSparseDepth();
        std::cout << "PASS: regional inheritance, footprint conflicts, independent child policies, provenance, geometry and sparse bounds.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n'; return 1;
    }
}
