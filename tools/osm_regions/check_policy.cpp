#include "PolicyTree.hpp"
#include "PolicyConfiguration.hpp"
#include <yaml-cpp/yaml.h>
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ump;
void require(bool yes, const std::string& message) { if (!yes) throw std::runtime_error(message); }
struct Bounds { std::optional<double> min, max; };
using Requirements = std::map<MetricId, Bounds>;
void tighten(Requirements& out, const std::vector<MetricRequirement>& in) {
    for (const auto& item : in) {
        auto& b = out[item.id];
        if (item.min) b.min = b.min ? std::max(*b.min, *item.min) : item.min;
        if (item.max) b.max = b.max ? std::min(*b.max, *item.max) : item.max;
    }
}
int integerGrid(double value, double origin, double side) {
    const double scaled = (value - origin) / side;
    const auto rounded = static_cast<int>(std::llround(scaled));
    require(std::abs(scaled - rounded) < 1e-7, "Input region is not aligned with finest grid");
    return rounded;
}
int cellId(int x, int y, int depth) {
    int id = 3;
    for (int bit = depth - 1; bit >= 0; --bit)
        id = (id << 2) | ((x >> bit) & 1) | (((y >> bit) & 1) << 1);
    return id;
}
CellGeometry geometry(int x, int y, int depth, const GridCoverage& grid) {
    const double side = grid.width / (1 << depth);
    return {cellId(x, y, depth), depth, grid.x + x * side, grid.y + y * side, side, side};
}
bool intersects(const CellGeometry& cell, const PolicyRegion& region) {
    return cell.x < region.x + region.width && region.x < cell.x + cell.width
        && cell.y < region.y + region.height && region.y < cell.y + cell.height;
}
void check(const PolicyTree& tree, const PolicyTreeConfig& config,
    const std::vector<PolicyRegion>& regions, const CellGeometry& cell) {
    Requirements expected;
    tighten(expected, config.rootRequirements);
    std::set<std::string> sources{"root:" + config.id};
    for (const auto& region : regions) if (intersects(cell, region)) {
        tighten(expected, region.typeRequirements); tighten(expected, region.instanceRequirements);
        sources.insert("region:" + region.id); sources.insert("region_type:" + region.type);
    }
    const auto& actual = tree.resolve(cell);
    require(actual.requirements.size() == expected.size(), "Wrong inherited requirement count");
    bool feasible = true;
    for (const auto& bound : actual.requirements) {
        const auto it = expected.find(bound.id);
        require(it != expected.end() && bound.min == it->second.min && bound.max == it->second.max,
            "Inherited policy differs from independently computed strict footprint intersection");
        if (bound.min && bound.max && *bound.min > *bound.max) feasible = false;
    }
    require(actual.feasible == feasible, "Wrong inherited feasibility flag");
    require(std::set<std::string>(actual.sources.begin(), actual.sources.end()) == sources,
        "Incorrect regional policy provenance");
}
template<class F> void rejects(F f, const char* message) {
    try { f(); } catch (const std::invalid_argument&) { return; }
    throw std::runtime_error(message);
}
}
int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: ump-osm-policy-probe policy.json");
        const auto input = YAML::LoadFile(argv[1]);
        const auto g = input["grid"];
        const GridCoverage grid{g["x"].as<double>(), g["y"].as<double>(),
            g["width"].as<double>(), g["height"].as<double>(), g["leaf_depth"].as<int>()};
        require(grid.leafDepth == 6, "This bounded OSM probe requires depth6");
        PolicyTreeConfig config{"osm-feasibility", "1", "osm-test", grid,
            readMetricRequirements(input["root_requirements"]), 65536};
        require(input["regions"].IsSequence(), "regions must be a sequence");
        std::vector<PolicyRegion> regions;
        for (const auto& r : input["regions"])
            regions.push_back({r["id"].as<std::string>(), r["type"].as<std::string>(),
                r["x"].as<double>(), r["y"].as<double>(), r["width"].as<double>(), r["height"].as<double>(),
                readMetricRequirements(r["type_requirements"], true),
                readMetricRequirements(r["requirements"], true)});
        const int units = 1 << grid.leafDepth;
        const double leafSide = grid.width / units;
        std::vector<int> coverage(units * units, 0);
        for (const auto& r : regions) {
            const int left = integerGrid(r.x, grid.x, leafSide);
            const int top = integerGrid(r.y, grid.y, leafSide);
            const int right = integerGrid(r.x + r.width, grid.x, leafSide);
            const int bottom = integerGrid(r.y + r.height, grid.y, leafSide);
            require(0 <= left && left < right && right <= units && 0 <= top && top < bottom && bottom <= units,
                "Invalid raster rectangle extent");
            for (int y = top; y < bottom; ++y) for (int x = left; x < right; ++x)
                require(++coverage[y * units + x] == 1, "Export rectangles overlap");
        }
        require(std::all_of(coverage.begin(), coverage.end(), [](int n) { return n == 1; }),
            "Raster export must tile all4096leaves exactly once including background");
        PolicyTree tree(config, regions);
        tree.validateContext(grid, "osm-test");
        std::size_t tested = 0, feasible = 0;
        std::set<int> leafIds;
        for (int depth = 1; depth <= grid.leafDepth; ++depth) {
            for (int y = 0; y < (1 << depth); ++y) for (int x = 0; x < (1 << depth); ++x) {
                const auto cell = geometry(x, y, depth, grid);
                check(tree, config, regions, cell); ++tested;
                if (tree.resolve(cell).feasible) ++feasible;
                if (depth == grid.leafDepth) {
                    require(leafIds.insert(cell.id).second, "Duplicate leaf ID");
                    if (depth > 1) {
                        const auto parent = geometry(x / 2, y / 2, depth - 1, grid);
                        require((cell.id >> 2) == parent.id, "Bitshift ancestry mismatch");
                    }
                }
            }
        }
        auto bad = geometry(0, 0, 6, grid); ++bad.x;
        rejects([&] { tree.resolve(bad); }, "Invalid geometry unexpectedly accepted");
        bad = geometry(0, 0, 6, grid); bad.id = 1;
        rejects([&] { tree.resolve(bad); }, "Invalid ID unexpectedly accepted");
        require(!regions.empty(), "A raster export must contain regions");
        auto overlap = regions; auto extra = regions.front(); extra.id += "-overlap-probe";
        overlap.push_back(extra);
        rejects([&] { PolicyTree rejected(config, overlap); }, "Overlapping geometry unexpectedly accepted");
        auto unaligned = regions; unaligned.front().x += leafSide / 3;
        rejects([&] { PolicyTree rejected(config, unaligned); }, "Unaligned geometry unexpectedly accepted");
        require(leafIds.size() == 4096 && *leafIds.begin() == 12288 && *leafIds.rbegin() == 16383,
            "Unexpected D6 leaf ID domain");
        std::cout << "{\"status\":\"pass\",\"depth\":6,\"coverage_side_m\":" << grid.width
            << ",\"leaf_side_m\":" << leafSide << ",\"rectangles\":" << regions.size()
            << ",\"covered_leaves\":4096,\"unique_leaf_ids\":4096,\"min_leaf_id\":12288,\"max_leaf_id\":16383"
            << ",\"resolved_cells_all_depths\":" << tested << ",\"resolved_nonroot_ancestors\":" << (tested-4096)
            << ",\"feasible_bounds_cells\":" << feasible << ",\"compiled_nodes\":" << tree.nodeCount()
            << ",\"effective_policies\":" << tree.effectivePolicyCount()
            << ",\"negative_checks\":4,\"distinct_support_is_privacy_guarantee\":false}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n'; return 1;
    }
}
