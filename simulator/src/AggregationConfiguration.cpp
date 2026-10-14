#include "AggregationConfiguration.hpp"
#include <set>
#include <stdexcept>

std::optional<ump::HistoryLimits> readHistoryLimits(const YAML::Node& node) {
    if (!node) return std::nullopt;
    if (!node.IsMap()) throw std::invalid_argument("aggregation.history must be a map");
    const std::set<std::string> keys{"retention_ms", "max_bins", "max_observations", "max_identity_bytes", "max_buckets"};
    std::set<std::string> seen;
    for (const auto& item : node) {
        const auto key = item.first.as<std::string>();
        if (!keys.count(key) || !seen.insert(key).second)
            throw std::invalid_argument("Unknown or duplicate history setting: " + key);
    }
    if (seen != keys) throw std::invalid_argument("All history resource limits must be explicit");
    const auto positive = [&](const char* key) {
        const auto value = node[key].as<std::int64_t>();
        if (value <= 0) throw std::invalid_argument(std::string("History limit must be positive: ") + key);
        return value;
    };
    return ump::HistoryLimits{positive("retention_ms"), static_cast<std::size_t>(positive("max_bins")),
        static_cast<std::size_t>(positive("max_observations")), static_cast<std::size_t>(positive("max_identity_bytes")),
        static_cast<std::size_t>(positive("max_buckets"))};
}

std::optional<ump::SpatialSelectionConfig> readSpatialSelection(const YAML::Node& aggregation, int leafDepth) {
    const auto node = aggregation["spatial_selection"];
    if (!node) return std::nullopt;
    if (!node.IsMap()) throw std::invalid_argument("spatial_selection must be a map");
    std::set<std::string> seen;
    for (const auto& item : node) {
        const auto key = item.first.as<std::string>();
        if ((key != "min_depth" && key != "max_evaluations") || !seen.insert(key).second)
            throw std::invalid_argument("Unknown or duplicate spatial_selection setting: " + key);
    }
    if (!aggregation["history"] || (!aggregation["metric_policy"] && !aggregation["policy_tree"]))
        throw std::invalid_argument("spatial_selection requires history and an explicit metric policy");
    const int depth = node["min_depth"].as<int>();
    const auto budget = node["max_evaluations"].as<std::int64_t>();
    if (depth < 1 || depth > leafDepth || budget <= 0)
        throw std::invalid_argument("Invalid spatial_selection depth or evaluation budget");
    return ump::SpatialSelectionConfig{depth, static_cast<std::size_t>(budget)};
}
