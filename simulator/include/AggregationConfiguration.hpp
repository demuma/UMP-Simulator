#pragma once
#include "AggregationInput.hpp"
#include "AdaptiveAggregation.hpp"
#include "SpatialSelection.hpp"
#include <yaml-cpp/yaml.h>

// Parse opt-in history limits; stream/geometry compatibility is validated by the core.
std::optional<ump::HistoryLimits> readHistoryLimits(const YAML::Node& node);
// Opt-in, internal fixed-window spatial decisions; validated before database initialization.
std::shared_ptr<const ump::SemanticTaxonomy> readSemanticTaxonomy(const YAML::Node& aggregation);
std::optional<ump::SpatialSelectionConfig> readSpatialSelection(const YAML::Node& aggregation, int leafDepth);

// Execution choices belong to the stream policy tree, never individual regions.
void validatePolicyExecution(const YAML::Node& aggregation);
std::optional<ump::TemporalAdaptationConfig> readTemporalAdaptation(const YAML::Node& aggregation);

// Database adapter settings remain plain values so configuration checks need no MongoDB client.
struct PublicationConfiguration {
    std::string database;
    std::string collection = "releases";
    std::string journalDatabase;
    std::string journalCollection = "publication_journal";
    std::size_t maxDocumentBytes = 8 * 1024 * 1024;
    std::size_t maxAttempts = 3;
    // Recipient delivery is always durable; optional private no-output checkpoints.
    bool journalEmptyRetirements = true;
};
std::optional<PublicationConfiguration> readPublicationConfiguration(const YAML::Node& aggregation);
void validatePublicationDestinations(const PublicationConfiguration& settings,
    const std::vector<std::string>& rawDatabases);
