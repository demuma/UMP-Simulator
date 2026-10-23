#include "PolicyTree.hpp"
#include "CellLocalAggregation.hpp"
#include <algorithm>
#include <iostream>
#include <limits>
#include <map>
#include <set>

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

// An independent physical-rectangle oracle: no production region/cell
// intersection, policy intersection or lookup helper is used here.
struct ExpectedBounds { std::optional<double> min, max; };
void checkIndependent(const PolicyTree& tree, const PolicyTreeConfig& config,
    const std::vector<PolicyRegion>& regions, const CellGeometry& geometry) {
    std::map<MetricId, ExpectedBounds> expected;
    std::set<std::string> sources{"root:" + config.id};
    const auto add = [&](const std::vector<MetricRequirement>& requirements) {
        for (const auto& requirement : requirements) {
            auto& value = expected[requirement.id];
            if (requirement.min && (!value.min || *requirement.min > *value.min)) value.min = requirement.min;
            if (requirement.max && (!value.max || *requirement.max < *value.max)) value.max = requirement.max;
        }
    };
    add(config.rootRequirements);
    for (const auto& region : regions) {
        const double width = std::min(geometry.x + geometry.width, region.x + region.width)
            - std::max(geometry.x, region.x);
        const double height = std::min(geometry.y + geometry.height, region.y + region.height)
            - std::max(geometry.y, region.y);
        if (width <= 0 || height <= 0) continue;
        add(region.typeRequirements); add(region.instanceRequirements);
        sources.insert("region_type:" + region.type); sources.insert("region:" + region.id);
    }
    const auto& resolved = tree.resolve(geometry);
    require(resolved.requirements.size() == expected.size(), "Independent policy requirement count differs");
    bool feasible = true;
    for (const auto& requirement : resolved.requirements) {
        const auto found = expected.find(requirement.id);
        require(found != expected.end() && found->second.min == requirement.min
            && found->second.max == requirement.max, "Independent strict overlap bounds differ");
        if (requirement.min && requirement.max && *requirement.min > *requirement.max) feasible = false;
    }
    require(resolved.feasible == feasible, "Independent overlap feasibility differs");
    require(std::vector<std::string>(sources.begin(), sources.end()) == resolved.sources,
        "Overlap provenance omitted, duplicated or reordered a relevant source");
}

CellGeometry gridCell(const GridCoverage& grid, int x, int y, int depth) {
    int id = 3;
    for (int bit = depth - 1; bit >= 0; --bit)
        id = (id << 2) | ((x >> bit) & 1) | (((y >> bit) & 1) << 1);
    const double side = grid.width / (1 << depth);
    return {id, depth, grid.x + x * side, grid.y + y * side, side, side};
}

void partialOverlapAndWholeFootprint() {
    const auto config = setup();
    std::vector<PolicyRegion> regions{
        {"a", "walking", 0, 0, 40, 40, {{MetricId::DistinctContributors, 5, {}}},
            {{MetricId::DistinctContributors, 2, {}}}},
        {"b", "entrance", 20, 20, 40, 40,
            {{MetricId::DistinctContributors, 8, {}}, {MetricId::WindowDurationMs, {}, 600}},
            {{MetricId::WindowDurationMs, {}, 800}}}};
    PolicyTree tree(config, regions);
    const auto onlyA = gridCell(config.grid, 0, 0, 3);
    const auto both = gridCell(config.grid, 2, 2, 3);
    const auto onlyB = gridCell(config.grid, 5, 5, 3);
    const auto neither = gridCell(config.grid, 7, 7, 3);
    for (const auto& geometry : {onlyA, both, onlyB, neither}) checkIndependent(tree, config, regions, geometry);
    require(bound(tree.resolve(onlyA), MetricId::DistinctContributors).min == 5
        && bound(tree.resolve(both), MetricId::DistinctContributors).min == 8
        && bound(tree.resolve(onlyB), MetricId::DistinctContributors).min == 8
        && bound(tree.resolve(neither), MetricId::DistinctContributors).min == 3,
        "Partial overlap leaked into a region-exclusive or default leaf");
    require(bound(tree.resolve(both), MetricId::WindowDurationMs).max == 600,
        "Weaker overlap instance relaxed a type maximum");
    const auto parent = gridCell(config.grid, 0, 0, 1);
    checkIndependent(tree, config, regions, parent);
    require(bound(tree.resolve(parent), MetricId::DistinctContributors).min == 8,
        "Ancestor ignored a strict overlapping patch in its complete footprint");
    // Six people occur only in the A-only leaf. A coarser footprint still
    // intersects B; zero observations there do not switch off its requirement.
    auto local = candidate({onlyA});
    local.counts = local.cells[0].counts = {6, 6, {{"pedestrian", 6}}, 2.};
    MetricEvaluator evaluator(std::make_shared<const PolicyTree>(config, regions));
    require(evaluator.evaluate(local, 400).status == AssessmentStatus::Pass,
        "Strict empty patch contaminated an exclusive fine candidate");
    local.cells[0].cell = parent;
    const auto ancestor = evaluator.evaluate(local, 400);
    require(ancestor.status == AssessmentStatus::Fail
        && std::any_of(ancestor.cells[0].checks.begin(), ancestor.cells[0].checks.end(), [](const auto& check) {
            return check.requirement.id == MetricId::DistinctContributors
                && check.requirement.min == 8 && check.reason == "below_minimum";
        }), "Empty strict patch was ignored by an occupied ancestor");
}

void nestedIdenticalAndTouchingRegions() {
    auto config = setup();
    PolicyRegion outer{"outer", "walking", 0, 0, 40, 40, {{MetricId::DistinctContributors, 5, {}}}, {}};
    PolicyRegion inner{"inner", "entrance", 10, 10, 20, 20, {{MetricId::DistinctContributors, 7, {}}}, {}};
    PolicyTree nested(config, {outer, inner});
    require(bound(nested.resolve(gridCell(config.grid, 1, 1, 3)), MetricId::DistinctContributors).min == 7
        && bound(nested.resolve(gridCell(config.grid, 0, 0, 3)), MetricId::DistinctContributors).min == 5,
        "Nested overlap lost its local inheritance boundary");
    auto identical = outer; identical.id = "same-footprint"; identical.type = "second-type";
    identical.instanceRequirements = {{MetricId::DistinctContributors, 9, {}}};
    PolicyTree same(config, {outer, identical});
    require(same.nodeCount() == 5 && same.resolve(gridCell(config.grid, 0, 0, 3)).sources.size() == 5,
        "Identical overlapping footprints were rejected, overexpanded or lost provenance");
    require(&same.resolve(gridCell(config.grid, 0, 0, 3)) == &same.resolve(gridCell(config.grid, 3, 3, 3)),
        "Homogeneous multiple-region descendants do not share an immutable policy");
    PolicyRegion edge{"edge", "edge-type", 40, 0, 40, 40, {{MetricId::DistinctContributors, 11, {}}}, {}};
    PolicyRegion corner{"corner", "corner-type", 40, 40, 40, 40, {{MetricId::DistinctContributors, 13, {}}}, {}};
    PolicyTree touching(config, {outer, edge, corner});
    const auto& left = touching.resolve(gridCell(config.grid, 0, 0, 1));
    require(bound(left, MetricId::DistinctContributors).min == 5 && left.sources.size() == 3,
        "Edge/corner contact incorrectly contributed a regional requirement");
    require(bound(touching.resolve(gridCell(config.grid, 1, 0, 1)), MetricId::DistinctContributors).min == 11,
        "Touching region failed to apply within its own footprint");

    config.grid.leafDepth = 14;
    require(PolicyTree(config, {outer, identical}).nodeCount() == 5,
        "Homogeneous overlapping D14 regions materialized every data leaf");
    auto tiny = outer; tiny.width = tiny.height = 80. / (1 << 14);
    auto secondTiny = tiny; secondTiny.id = "same-tiny-footprint";
    config.maxNodes = 57;
    require(PolicyTree(config, {tiny, secondTiny}).nodeCount() == 57,
        "Two identical finest-leaf regions expanded beyond their shared boundary path");
    config.maxNodes = 56;
    rejects([&] { PolicyTree rejected(config, {tiny, secondTiny}); }, "max_nodes");
}

void contradictoryOverlapAndValidNeighbors() {
    const auto config = setup();
    std::vector<PolicyRegion> regions{
        {"coarse", "coarse-type", 0, 0, 40, 40, {{MetricId::CellSideM, 20, {}}}, {}},
        {"fine", "fine-type", 20, 20, 40, 40, {{MetricId::CellSideM, {}, 10}}, {}}};
    auto tree = std::make_shared<const PolicyTree>(config, regions);
    const auto overlap = gridCell(config.grid, 2, 2, 3);
    const auto coarseOnly = gridCell(config.grid, 0, 0, 2);
    const auto fineOnly = gridCell(config.grid, 5, 5, 3);
    const auto parent = gridCell(config.grid, 0, 0, 1);
    require(!tree->resolve(overlap).feasible && !tree->resolve(parent).feasible
        && tree->resolve(coarseOnly).feasible && tree->resolve(fineOnly).feasible,
        "Overlap contradiction was discarded or propagated into exclusive children");
    MetricEvaluator evaluator(tree);
    const auto failed = evaluator.evaluate(candidate({overlap}), 400);
    require(failed.status == AssessmentStatus::Fail && !failed.cells[0].policyFeasible
        && std::any_of(failed.cells[0].checks.begin(), failed.cells[0].checks.end(), [](const auto& check) {
            return check.reason == "contradictory_policy_bounds";
        }), "Contradictory overlap did not retain an explicit failing metric reason");
    require(evaluator.evaluate(candidate({coarseOnly, fineOnly}), 400).status == AssessmentStatus::Pass,
        "Valid exclusive candidates were rejected with their infeasible overlap");
}

void exhaustiveOverlappingD6Oracle() {
    auto config = setup(); config.grid.leafDepth = 6;
    const std::vector<PolicyRegion> regions{
        {"walking", "walking-type", 0, 0, 50, 50, {{MetricId::DistinctContributors, 5, {}}}, {}},
        {"entrance", "entrance-type", 20, 20, 40, 40,
            {{MetricId::DistinctContributors, 9, {}}, {MetricId::CellSideM, {}, 10}},
            {{MetricId::WindowDurationMs, {}, 600}}},
        {"coarse", "coarse-type", 10, 10, 20, 60, {{MetricId::CellSideM, 20, {}}}, {}},
        {"same-walking-footprint", "walking-type", 0, 0, 50, 50,
            {{MetricId::DistinctContributors, 5, {}}}, {{MetricId::AgeAtEvaluationMs, {}, 700}}},
        {"tiny", "tiny-type", 21.25, 21.25, 1.25, 1.25, {}, {}},
        {"touching", "touching-type", 60, 20, 20, 40, {{MetricId::DistinctContributors, 4, {}}}, {}}};
    PolicyTree tree(config, regions);
    auto permuted = regions; std::reverse(permuted.begin(), permuted.end());
    PolicyTree reordered(config, permuted);
    std::size_t leaves = 0, ancestors = 0, infeasible = 0;
    const auto beforeNodes = tree.nodeCount(), beforePolicies = tree.effectivePolicyCount();
    for (int depth = 1; depth <= 6; ++depth)
        for (int y = 0; y < (1 << depth); ++y) for (int x = 0; x < (1 << depth); ++x) {
            const auto geometry = gridCell(config.grid, x, y, depth);
            checkIndependent(tree, config, regions, geometry);
            const auto& resolved = tree.resolve(geometry);
            const auto& other = reordered.resolve(geometry);
            require(resolved.id == other.id && resolved.sources == other.sources && resolved.feasible == other.feasible,
                "Region input order changed compiled overlap identities or provenance");
            if (!resolved.feasible) ++infeasible;
            if (depth == 6) ++leaves; else ++ancestors;
        }
    require(leaves == 4096 && ancestors == 1364 && infeasible > 0,
        "Independent D6 audit omitted leaves, ancestors or contradictory overlaps");
    require(tree.nodeCount() == beforeNodes && tree.effectivePolicyCount() == beforePolicies,
        "Overlap lookup rebuilt or mutated the compiled tree");
}

void overlappingPoliciesInCellLocalController() {
    AggregationConfig config{"overlap-run", "overlap-sensor", "application", setup().grid, 100, 200};
    config.history = HistoryLimits{2000, 32, 10000, 1000000, 1024};
    auto settings = setup();
    settings.rootRequirements = {{MetricId::DistinctContributors, 1, {}},
        {MetricId::CellSideM, {}, 40}, {MetricId::WindowDurationMs, {}, 400}};
    const std::vector<PolicyRegion> regions{
        {"door-minimum", "door-minimum-type", 0, 0, 10, 10, {{MetricId::CellSideM, 10, {}}}, {}},
        {"task-maximum", "task-maximum-type", 0, 0, 10, 10, {{MetricId::CellSideM, {}, 5}}, {}}};
    MetricEvaluator evaluator(std::make_shared<const PolicyTree>(settings, regions));
    AggregationHistory history(config, *config.history);
    std::vector<SpatialSelection> outputs;
    TemporalAdaptationConfig temporal{AdaptationStrategy::SpatialFirst, 100, 400, 16};
    temporal.coordination = CoordinationMode::CellLocal;
    CellLocalAggregation engine(config, temporal, {1, 4096}, evaluator,
        [&](const auto& selection) { outputs.push_back(selection); });
    const auto bad = gridCell(config.coverage, 0, 0, 3);
    const auto good = gridCell(config.coverage, 1, 0, 3);
    for (AggregationTime time = 100; time <= 900; time += 100) {
        history.append({config.runId, config.sensorId, static_cast<std::uint64_t>(time / 100),
            time, ObservationStatus::Measured,
            {{"blocked-track", "pedestrian", bad}, {"valid-neighbor-track", "pedestrian", good}}});
        engine.advance(time, history);
    }
    history.advance(1000); engine.finish(1000, history);
    require(engine.debugState().finished, "Infeasible overlapping policies caused an unfinished waiting cascade");
    std::uint64_t selected = 0, suppressed = 0;
    for (std::size_t i = 0; i < outputs.size(); ++i) {
        const auto& output = outputs[i];
        require(output.coordinationCell.has_value(), "Local overlap decision omitted its retirement footprint");
        require(output.candidate.endMs - output.candidate.startMs <= 400,
            "Overlap conflict exceeded the configured time limit");
        for (std::size_t j = 0; j < i; ++j) {
            const auto& other = outputs[j];
            const auto& a = *output.coordinationCell; const auto& b = *other.coordinationCell;
            const bool spatial = std::min(a.x + a.width, b.x + b.width) > std::max(a.x, b.x)
                && std::min(a.y + a.height, b.y + b.height) > std::max(a.y, b.y);
            const bool temporalOverlap = std::min(output.candidate.endMs, other.candidate.endMs)
                > std::max(output.candidate.startMs, other.candidate.startMs);
            require(!(spatial && temporalOverlap), "Overlap handling consumed the same space-time footprint twice");
        }
        for (const auto& decision : output.decisions) {
            const auto found = std::find_if(output.candidate.cells.begin(), output.candidate.cells.end(),
                [&](const auto& item) { return item.cell.id == decision.cellId; });
            require(found != output.candidate.cells.end(), "Overlap decision lost its source statistics");
            const auto assessed = evaluator.evaluate(output.candidate, output.candidate.closedAtMs);
            if (decision.selected) {
                require(found->cell.id == good.id && assessed.status == AssessmentStatus::Pass,
                    "Controller published an infeasible overlap or suppressed a valid neighbor through a parent");
                selected += found->counts.observationContributions;
            } else {
                require(found->cell.id == bad.id && !assessed.cells[0].policyFeasible,
                    "Controller suppression escaped the contradictory overlap footprint");
                suppressed += found->counts.observationContributions;
            }
        }
    }
    require(selected == 9 && suppressed == 9,
        "Overlap conflict lost support or blocked valid neighboring observations");
}

void validationAndSparseDepth() {
    auto config = setup();
    const PolicyRegion good{"a", "type", 0, 0, 40, 40, {{MetricId::DistinctContributors, 5, {}}}, {}};
    rejects([&] { auto g = config; g.grid.height = 40; PolicyTree(g, {}); }, "square");
    rejects([&] { auto g = config; g.grid.leafDepth = 15; PolicyTree(g, {}); }, "depth");
    rejects([&] { auto g = config; g.version.clear(); PolicyTree(g, {}); }, "version");
    rejects([&] { auto g = config; g.rootRequirements.clear(); PolicyTree(g, {}); }, "empty");
    rejects([&] { PolicyTree(config, {good, good}); }, "unique");
    rejects([&] { auto other = good; other.width = 10; other.x = 5; PolicyTree(config, {other}); }, "aligned");
    rejects([&] { auto other = good; other.x = 80; PolicyTree(config, {other}); }, "outside");
    rejects([&] { auto other = good; other.width = 0; PolicyTree(config, {other}); }, "dimensions");
    rejects([&] { auto other = good; other.x = std::numeric_limits<double>::quiet_NaN(); PolicyTree(config, {other}); }, "outside");
    rejects([&] { auto other = good; other.instanceRequirements = {{MetricId::CellSideM, 41, {}}}; PolicyTree(config, {other}); }, "Contradictory inherited");
    rejects([&] { auto other = good; other.instanceRequirements = {{MetricId::DistinctContributors, 7, 5}}; PolicyTree(config, {other}); }, "Contradictory bounds");
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
        partialOverlapAndWholeFootprint(); nestedIdenticalAndTouchingRegions();
        contradictoryOverlapAndValidNeighbors(); exhaustiveOverlappingD6Oracle();
        overlappingPoliciesInCellLocalController();
        std::cout << "PASS: regional inheritance, strict overlaps, D6 independent oracle, bounded local coordination, provenance and sparse bounds.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n'; return 1;
    }
}
