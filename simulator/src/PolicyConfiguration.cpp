#include "PolicyConfiguration.hpp"
#include "AggregationConfiguration.hpp"
#include "PolicyTree.hpp"
#include <algorithm>
#include <iostream>
#include <unordered_set>

namespace {
void allowedKeys(const YAML::Node& node, const std::vector<std::string>& allowed, const char* context) {
    if (!node.IsMap()) throw std::invalid_argument(std::string(context) + " must be a map");
    std::unordered_set<std::string> seen;
    for (const auto& item : node) {
        const auto key = item.first.as<std::string>();
        if (std::find(allowed.begin(), allowed.end(), key) == allowed.end())
            throw std::invalid_argument(std::string("Unknown ") + context + " setting: " + key);
        if (!seen.insert(key).second)
            throw std::invalid_argument(std::string("Duplicate ") + context + " setting: " + key);
    }
}
}

std::vector<ump::MetricRequirement> readMetricRequirements(const YAML::Node& node, bool allowEmpty) {
    if (!node && allowEmpty) return {};
    if (!node.IsMap()) throw std::invalid_argument("Metric requirements must be a map");
    std::vector<ump::MetricRequirement> requirements;
    for (const auto& item : node) {
        ump::MetricRequirement requirement{ump::metricIdFromName(item.first.as<std::string>()), {}, {}};
        allowedKeys(item.second, {"min", "max"}, "metric bound");
        if (item.second["min"]) requirement.min = item.second["min"].as<double>();
        if (item.second["max"]) requirement.max = item.second["max"].as<double>();
        requirements.push_back(requirement);
    }
    ump::validateMetricRequirements(requirements, allowEmpty);
    return requirements;
}

ump::MetricEvaluator makeMetricEvaluator(const YAML::Node& aggregation, const ump::GridCoverage& grid,
    const std::string& applicationId, const std::vector<Region>& regions,
    std::shared_ptr<const ump::SemanticTaxonomy> taxonomy) {
    if (!taxonomy && aggregation["semantic_taxonomy"]) taxonomy = readSemanticTaxonomy(aggregation);
    const auto uniform = aggregation["metric_policy"], tree = aggregation["policy_tree"];
    if (uniform && tree) throw std::invalid_argument("Select metric_policy or policy_tree, not both");
    validatePolicyExecution(aggregation);
    if (uniform) {
        allowedKeys(uniform, {"id", "version", "requirements"}, "metric_policy");
        return ump::MetricEvaluator(ump::MetricPolicy{uniform["id"].as<std::string>(),
            uniform["version"].as<std::string>(), readMetricRequirements(uniform["requirements"])}, taxonomy);
    }
    if (!tree) return ump::MetricEvaluator{};
    allowedKeys(tree, {"id", "version", "root", "regions", "max_nodes", "execution"}, "policy_tree");
    const auto budget = tree["max_nodes"].as<std::int64_t>(65536);
    if (budget <= 0) throw std::invalid_argument("policy_tree.max_nodes must be positive");
    ump::PolicyTreeConfig settings{tree["id"].as<std::string>(), tree["version"].as<std::string>(),
        applicationId, grid, readMetricRequirements(tree["root"]), static_cast<std::size_t>(budget)};
    const auto references = tree["regions"];
    if (!references.IsSequence()) throw std::invalid_argument("policy_tree.regions must be a sequence of Region IDs");
    std::unordered_set<std::string> seen;
    std::vector<ump::PolicyRegion> selected;
    for (const auto& reference : references) {
        if (!reference.IsScalar())
            throw std::invalid_argument("Regional execution settings are not supported; policy_tree.regions must contain Region ID strings");
        const auto id = reference.as<std::string>();
        if (!seen.insert(id).second) throw std::invalid_argument("Duplicate policy region reference: " + id);
        const auto found = std::find_if(regions.begin(), regions.end(), [&](const Region& region) { return region.id == id; });
        if (found == regions.end()) throw std::invalid_argument("Unknown policy region: " + id);
        const auto& area = found->area;
        selected.push_back({found->id, found->type, area.position.x, area.position.y,
            area.size.x, area.size.y, found->attributes.metricRequirements, found->metricRequirements});
    }
    if (taxonomy) ump::validateSemanticMetricRequirements(settings.rootRequirements);
    auto compiled = std::make_shared<const ump::PolicyTree>(std::move(settings), std::move(selected));
    std::cout << "Regional policy " << compiled->id() << ": " << compiled->nodeCount()
        << " nodes, " << compiled->effectivePolicyCount() << " effective policies\n";
    return ump::MetricEvaluator(std::move(compiled), std::move(taxonomy));
}
