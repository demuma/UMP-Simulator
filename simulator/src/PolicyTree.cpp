#include "PolicyTree.hpp"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <sstream>
#include <unordered_set>

namespace ump {
namespace {
EffectiveMetricPolicy intersect(const EffectiveMetricPolicy& a, const EffectiveMetricPolicy& b) {
    std::array<std::optional<MetricRequirement>, static_cast<std::size_t>(MetricId::Count)> byId;
    for (const auto* policy : {&a, &b}) {
        for (const auto& item : policy->requirements) {
            auto& target = byId.at(static_cast<std::size_t>(item.id));
            if (!target) target = item;
            else {
                if (item.min) target->min = target->min ? std::max(*target->min, *item.min) : item.min;
                if (item.max) target->max = target->max ? std::min(*target->max, *item.max) : item.max;
            }
        }
    }
    EffectiveMetricPolicy result;
    for (const auto& item : byId) if (item) {
        result.requirements.push_back(*item);
        if (item->min && item->max && *item->min > *item->max) result.feasible = false;
    }
    result.sources = a.sources;
    result.sources.insert(result.sources.end(), b.sources.begin(), b.sources.end());
    std::sort(result.sources.begin(), result.sources.end());
    result.sources.erase(std::unique(result.sources.begin(), result.sources.end()), result.sources.end());
    return result;
}

std::string signature(const EffectiveMetricPolicy& policy) {
    std::ostringstream key;
    key << std::setprecision(17);
    for (const auto& item : policy.requirements) {
        key << static_cast<int>(item.id) << ':';
        if (item.min) key << *item.min;
        key << ':';
        if (item.max) key << *item.max;
        key << ';';
    }
    for (const auto& source : policy.sources) key << source.size() << ':' << source;
    return key.str();
}
}

PolicyTree::PolicyTree(PolicyTreeConfig setup, std::vector<PolicyRegion> selected)
    : config(std::move(setup)) {
    const auto& g = config.grid;
    if (config.id.empty() || config.version.empty() || config.applicationId.empty() || !config.maxNodes)
        throw std::invalid_argument("Policy tree requires ID, version, application and positive max_nodes");
    if (!std::isfinite(g.x) || !std::isfinite(g.y) || !std::isfinite(g.width)
        || !std::isfinite(g.height) || g.width <= 0 || g.height != g.width
        || !std::isfinite(g.x + g.width) || !std::isfinite(g.y + g.height)
        || g.leafDepth < 1 || g.leafDepth > 14)
        throw std::invalid_argument("Policy tree requires finite square coverage and depth 1..14");
    units = 1 << g.leafDepth;
    leafSide = g.width / units;
    if (!(leafSide > 0) || g.x + leafSide == g.x || g.y + leafSide == g.y)
        throw std::invalid_argument("Policy leaf geometry is not numerically representable");
    validateMetricRequirements(config.rootRequirements);
    rootPolicy = intersect({}, {{}, config.rootRequirements, {"root:" + config.id}, true});
    std::sort(selected.begin(), selected.end(), [](const auto& a, const auto& b) { return a.id < b.id; });
    std::unordered_set<std::string> ids;
    std::unordered_map<std::string, std::string> typeDefinitions;
    for (const auto& region : selected) {
        if (region.id.empty() || region.type.empty() || !ids.insert(region.id).second)
            throw std::invalid_argument("Policy regions require unique nonempty IDs and nonempty types");
        validateMetricRequirements(region.typeRequirements, true);
        validateMetricRequirements(region.instanceRequirements, true);
        const auto typed = intersect({}, {{}, region.typeRequirements, {"region_type:" + region.type}, true});
        const auto key = signature(typed);
        const auto [existing, inserted] = typeDefinitions.emplace(region.type, key);
        if (!inserted && existing->second != key)
            throw std::invalid_argument("Inconsistent definitions of region type: " + region.type);
        auto effective = intersect(intersect(rootPolicy, typed),
            {{}, region.instanceRequirements, {"region:" + region.id}, true});
        if (!effective.feasible)
            throw std::invalid_argument("Contradictory inherited requirements in region: " + region.id);
        if (!std::isfinite(region.width) || !std::isfinite(region.height)
            || region.width <= 0 || region.height <= 0)
            throw std::invalid_argument("Policy region must have positive finite dimensions: " + region.id);
        const int x = coordinate(region.x, g.x), y = coordinate(region.y, g.y);
        const int right = coordinate(region.x + region.width, g.x);
        const int bottom = coordinate(region.y + region.height, g.y);
        Rect area{x, y, right - x, bottom - y};
        if (area.width <= 0 || area.height <= 0)
            throw std::invalid_argument("Policy region is smaller than the supported grid: " + region.id);
        for (const auto& earlier : regions) if (intersects(earlier.area, area))
            throw std::invalid_argument("Overlapping selected policy regions are not supported: " + region.id);
        regions.push_back({area, std::move(effective)});
    }
    std::vector<std::size_t> all;
    for (std::size_t i = 0; i < regions.size(); ++i) all.push_back(i);
    compile({0, 0, units, units}, 0, all);
    // Lookup is immutable; discard the construction-only interning index.
    policyKeys.clear(); policyKeys.rehash(0);
    regions.clear(); regions.shrink_to_fit();
}

bool PolicyTree::intersects(const Rect& a, const Rect& b) {
    return a.x < b.x + b.width && b.x < a.x + a.width
        && a.y < b.y + b.height && b.y < a.y + a.height;
}
bool PolicyTree::contains(const Rect& outer, const Rect& inner) {
    return outer.x <= inner.x && outer.y <= inner.y
        && outer.x + outer.width >= inner.x + inner.width
        && outer.y + outer.height >= inner.y + inner.height;
}
bool PolicyTree::sameCoordinate(double actual, double expected) const {
    const double tolerance = std::min(leafSide * 1e-4,
        1e-6 * std::max({1.0, std::abs(actual), std::abs(expected)}));
    return std::isfinite(actual) && std::abs(actual - expected) <= tolerance;
}
int PolicyTree::coordinate(double value, double origin) const {
    const double scaled = (value - origin) / leafSide;
    if (!std::isfinite(scaled) || scaled < -.001 || scaled > units + .001)
        throw std::invalid_argument("Selected policy region lies outside stream coverage");
    const int rounded = static_cast<int>(std::llround(scaled));
    if (rounded < 0 || rounded > units || !sameCoordinate(value, origin + rounded * leafSide))
        throw std::invalid_argument("Policy region boundary is not aligned with the finest grid");
    return rounded;
}

std::size_t PolicyTree::intern(EffectiveMetricPolicy policy) {
    const auto key = signature(policy);
    if (const auto existing = policyKeys.find(key); existing != policyKeys.end()) return existing->second;
    const auto index = policies.size();
    policy.id = config.id + "/" + config.version + "/p" + std::to_string(index);
    policies.push_back(std::move(policy));
    policyKeys.emplace(key, index);
    return index;
}

std::size_t PolicyTree::compile(Rect area, int depth, const std::vector<std::size_t>& indices) {
    if (nodes.size() >= config.maxNodes) throw std::invalid_argument("Policy tree exceeds max_nodes budget");
    auto effective = rootPolicy;
    for (auto i : indices) effective = intersect(effective, regions[i].policy);
    const auto index = nodes.size();
    nodes.push_back({area, depth, intern(std::move(effective))});
    if (indices.empty() || (indices.size() == 1 && contains(regions[indices[0]].area, area))) return index;
    if (depth == config.grid.leafDepth) throw std::logic_error("Aligned policy region cuts a finest leaf");
    const int half = area.width / 2;
    for (int quadrant = 0; quadrant < 4; ++quadrant) {
        Rect child{area.x + (quadrant & 1) * half, area.y + (quadrant >> 1) * half, half, half};
        std::vector<std::size_t> relevant;
        for (auto i : indices) if (intersects(child, regions[i].area)) relevant.push_back(i);
        const auto childIndex = compile(child, depth + 1, relevant);
        nodes[index].children[quadrant] = childIndex;
    }
    return index;
}

PolicyTree::Rect PolicyTree::checkedCell(const CellGeometry& cell) const {
    if (cell.id < 0 || cell.depth < 1 || cell.depth > config.grid.leafDepth
        || (cell.id >> (2 * cell.depth)) != 3)
        throw std::invalid_argument("Policy lookup requires a valid quadtree cell ID and depth");
    Rect expected{0, 0, units, units};
    for (int level = 1; level <= cell.depth; ++level) {
        const int quadrant = (cell.id >> (2 * (cell.depth - level))) & 3;
        expected.width /= 2; expected.height /= 2;
        expected.x += (quadrant & 1) * expected.width;
        expected.y += (quadrant >> 1) * expected.height;
    }
    if (!sameCoordinate(cell.x, config.grid.x + expected.x * leafSide)
        || !sameCoordinate(cell.y, config.grid.y + expected.y * leafSide)
        || !sameCoordinate(cell.width, expected.width * leafSide)
        || !sameCoordinate(cell.height, expected.height * leafSide))
        throw std::invalid_argument("Policy lookup cell geometry does not match its ID/depth");
    return expected;
}

const EffectiveMetricPolicy& PolicyTree::resolve(const CellGeometry& cell) const {
    const auto area = checkedCell(cell);
    std::size_t index = 0;
    while (nodes[index].depth < cell.depth && nodes[index].children[0] != absent) {
        const auto& node = nodes[index];
        const int half = node.area.width / 2;
        const int quadrant = (area.x >= node.area.x + half ? 1 : 0)
            | (area.y >= node.area.y + half ? 2 : 0);
        index = node.children[quadrant];
    }
    return policies[nodes[index].policy];
}

void PolicyTree::validateContext(const GridCoverage& grid, const std::string& applicationId) const {
    const auto& own = config.grid;
    if (applicationId != config.applicationId || grid.x != own.x || grid.y != own.y
        || grid.width != own.width || grid.height != own.height || grid.leafDepth != own.leafDepth)
        throw std::invalid_argument("Candidate application/grid differs from its policy tree");
}
} // namespace ump
