#include "AggregationConfiguration.hpp"
#include <algorithm>
#include <cctype>
#include <set>
#include <stdexcept>

namespace {
void allowedKeys(const YAML::Node& node, const std::set<std::string>& allowed, const char* context) {
    if (!node.IsMap()) throw std::invalid_argument(std::string(context) + " must be a map");
    std::set<std::string> seen;
    for (const auto& item : node) {
        const auto key = item.first.as<std::string>();
        if (!allowed.count(key) || !seen.insert(key).second)
            throw std::invalid_argument(std::string("Unknown or duplicate ") + context + " setting: " + key);
    }
}

std::int64_t positive(const YAML::Node& node, const char* key, const char* context) {
    if (!node[key]) throw std::invalid_argument(std::string(context) + "." + key + " must be explicit");
    const auto value = node[key].as<std::int64_t>();
    if (value <= 0) throw std::invalid_argument(std::string(context) + "." + key + " must be positive");
    return value;
}

std::string folded(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) { return std::tolower(c); });
    return value;
}

void validateDatabaseName(const std::string& name) {
    if (name.empty() || name.size() > 63 || name.find_first_of("/\\.\"$*<>:|? \t\r\n") != std::string::npos
        || name.find('\0') != std::string::npos)
        throw std::invalid_argument("Publication database names must be nonempty valid database names");
    const auto normalized = folded(name);
    if (normalized == "simulation" || normalized == "admin" || normalized == "local" || normalized == "config")
        throw std::invalid_argument("Publication cannot use a reserved database: " + name);
}

void validateCollectionName(const std::string& name) {
    if (name.empty() || name.find('\0') != std::string::npos || name.find('$') != std::string::npos
        || name.rfind("system.", 0) == 0)
        throw std::invalid_argument("Publication collection names must be nonempty user collection names");
}

std::string publicationName(const YAML::Node& node, const char* key) {
    if (!node[key].IsScalar())
        throw std::invalid_argument(std::string("publication.") + key + " must be a string");
    return node[key].as<std::string>();
}
}

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

void validatePolicyExecution(const YAML::Node& aggregation) {
    const auto tree = aggregation["policy_tree"];
    if (tree && !tree.IsMap()) throw std::invalid_argument("policy_tree must be a map");
    const auto execution = tree ? tree["execution"] : YAML::Node(YAML::NodeType::Undefined);
    if (execution) {
        allowedKeys(execution, {"publication_model", "strategy"}, "policy_tree.execution");
        if (execution["publication_model"]
            && execution["publication_model"].as<std::string>() != "private_final_snapshot")
            throw std::invalid_argument("Unsupported policy_tree.execution.publication_model");
        if (execution["strategy"]) {
            const auto strategy = execution["strategy"].as<std::string>();
            if (strategy != "temporal_first" && strategy != "spatial_first")
                throw std::invalid_argument("Unsupported policy_tree.execution.strategy");
        }
    }
    if (aggregation["publication"] && (!execution || !execution["publication_model"]))
        throw std::invalid_argument("publication requires policy_tree.execution.publication_model");
    if (aggregation["temporal_adaptation"] && (!execution || !execution["strategy"]))
        throw std::invalid_argument("temporal_adaptation requires policy_tree.execution.strategy");
}

std::optional<ump::TemporalAdaptationConfig> readTemporalAdaptation(const YAML::Node& aggregation) {
    const auto node = aggregation["temporal_adaptation"];
    if (!node) return std::nullopt;
    allowedKeys(node, {"extension_step_ms", "max_window_ms", "max_evaluations",
        "coordination", "max_active_cells"}, "temporal_adaptation");
    if (!aggregation["history"] || !aggregation["spatial_selection"])
        throw std::invalid_argument("temporal_adaptation requires history and spatial_selection");
    validatePolicyExecution(aggregation);
    const auto strategy = aggregation["policy_tree"]["execution"]["strategy"].as<std::string>();
    ump::TemporalAdaptationConfig settings{
        strategy == "temporal_first" ? ump::AdaptationStrategy::TemporalFirst : ump::AdaptationStrategy::SpatialFirst,
        positive(node, "extension_step_ms", "temporal_adaptation"),
        positive(node, "max_window_ms", "temporal_adaptation"),
        static_cast<std::size_t>(positive(node, "max_evaluations", "temporal_adaptation"))};
    if (node["coordination"]) {
        const auto mode = node["coordination"].as<std::string>();
        if (mode == "cell_local") settings.coordination = ump::CoordinationMode::CellLocal;
        else if (mode != "common_window") throw std::invalid_argument("Unsupported temporal_adaptation.coordination");
    }
    if (node["max_active_cells"]) settings.maxActiveCells = static_cast<std::size_t>(
        positive(node, "max_active_cells", "temporal_adaptation"));
    if (settings.maxActiveCells < 4)
        throw std::invalid_argument("max_active_cells must cover the four base cells");
    return settings;
}

std::optional<PublicationConfiguration> readPublicationConfiguration(const YAML::Node& aggregation) {
    const auto node = aggregation["publication"];
    if (!node) return std::nullopt;
    allowedKeys(node, {"database", "collection", "journal_database", "journal_collection",
        "max_document_bytes", "max_attempts", "journal_empty_retirements"}, "publication");
    if (!aggregation["spatial_selection"])
        throw std::invalid_argument("publication requires spatial_selection");
    validatePolicyExecution(aggregation);
    if (!node["database"] || !node["journal_database"])
        throw std::invalid_argument("publication.database and publication.journal_database must be explicit");
    PublicationConfiguration settings;
    settings.database = publicationName(node, "database");
    if (node["collection"]) settings.collection = publicationName(node, "collection");
    settings.journalDatabase = publicationName(node, "journal_database");
    if (node["journal_collection"]) settings.journalCollection = publicationName(node, "journal_collection");
    if (node["max_document_bytes"])
        settings.maxDocumentBytes = static_cast<std::size_t>(positive(node, "max_document_bytes", "publication"));
    if (node["max_attempts"])
        settings.maxAttempts = static_cast<std::size_t>(positive(node, "max_attempts", "publication"));
    if (node["journal_empty_retirements"])
        settings.journalEmptyRetirements = node["journal_empty_retirements"].as<bool>();
    validateDatabaseName(settings.database);
    validateDatabaseName(settings.journalDatabase);
    validateCollectionName(settings.collection);
    validateCollectionName(settings.journalCollection);
    if (folded(settings.database) == folded(settings.journalDatabase))
        throw std::invalid_argument("Publication recipient and private journal require distinct databases");
    return settings;
}

void validatePublicationDestinations(const PublicationConfiguration& settings,
    const std::vector<std::string>& rawDatabases) {
    for (const auto& raw : rawDatabases)
        if (folded(settings.database) == folded(raw) || folded(settings.journalDatabase) == folded(raw))
            throw std::invalid_argument("Publication recipient/journal database overlaps raw database: " + raw);
}
