#pragma once
#include "AggregationInput.hpp"
#include "SpatialSelection.hpp"
#include <yaml-cpp/yaml.h>

// Parse opt-in history limits; stream/geometry compatibility is validated by the core.
std::optional<ump::HistoryLimits> readHistoryLimits(const YAML::Node& node);
// Opt-in, internal fixed-window spatial decisions; validated before database initialization.
std::optional<ump::SpatialSelectionConfig> readSpatialSelection(const YAML::Node& aggregation, int leafDepth);
