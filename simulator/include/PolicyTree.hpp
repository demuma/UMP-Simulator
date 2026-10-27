#pragma once

#include "CandidateMetrics.hpp"
#include <array>
#include <limits>
#include <unordered_map>

namespace ump {
struct PolicyTreeConfig {
    std::string id, version, applicationId;
    GridCoverage grid;
    std::vector<MetricRequirement> rootRequirements;
    std::size_t maxNodes = 65536;
};

// Plain values adapted from existing Region objects; no SFML or YAML dependency.
struct PolicyRegion {
    std::string id, type;
    double x, y, width, height;
    std::vector<MetricRequirement> typeRequirements, instanceRequirements;
};

class PolicyTree {
public:
    PolicyTree(PolicyTreeConfig config, std::vector<PolicyRegion> regions);
    const EffectiveMetricPolicy& resolve(const CellGeometry& cell) const;
    void validateContext(const GridCoverage& grid, const std::string& applicationId) const;
    const std::string& id() const { return config.id; }
    const std::string& version() const { return config.version; }
    std::size_t nodeCount() const { return nodes.size(); }
    std::size_t effectivePolicyCount() const { return policies.size(); }
    // Inspect all compiled footprints, including unoccupied regions, without
    // weakening an inherited bound or consulting current observations.
    bool permitsSemanticSuppression() const;

private:
    static constexpr std::size_t absent = std::numeric_limits<std::size_t>::max();
    struct Rect { int x, y, width, height; };
    struct CompiledRegion { Rect area; EffectiveMetricPolicy policy; };
    struct Node {
        Rect area;
        int depth;
        std::size_t policy;
        std::array<std::size_t, 4> children{absent, absent, absent, absent};
    };
    static bool intersects(const Rect& a, const Rect& b);
    static bool contains(const Rect& outer, const Rect& inner);
    bool sameCoordinate(double actual, double expected) const;
    int coordinate(double value, double origin) const;
    Rect checkedCell(const CellGeometry& cell) const;
    std::size_t compile(Rect area, int depth, const std::vector<std::size_t>& regionIndices);
    std::size_t intern(EffectiveMetricPolicy policy);

    PolicyTreeConfig config;
    int units;
    double leafSide;
    EffectiveMetricPolicy rootPolicy;
    std::vector<CompiledRegion> regions;
    std::vector<Node> nodes;
    std::vector<EffectiveMetricPolicy> policies;
    std::unordered_map<std::string, std::size_t> policyKeys;
};
} // namespace ump
