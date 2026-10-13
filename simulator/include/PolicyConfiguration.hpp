#pragma once

#include "CandidateMetrics.hpp"
#include "Region.hpp"
#include <yaml-cpp/yaml.h>

// Configuration/Region adaptation is outside the standard-C++ policy core.
std::vector<ump::MetricRequirement> readMetricRequirements(const YAML::Node& node, bool allowEmpty = false);
ump::MetricEvaluator makeMetricEvaluator(const YAML::Node& aggregation, const ump::GridCoverage& grid,
    const std::string& applicationId, const std::vector<Region>& regions);
