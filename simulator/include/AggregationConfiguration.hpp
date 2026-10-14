#pragma once
#include "AggregationInput.hpp"
#include <yaml-cpp/yaml.h>

// Parse opt-in history limits; stream/geometry compatibility is validated by the core.
std::optional<ump::HistoryLimits> readHistoryLimits(const YAML::Node& node);
