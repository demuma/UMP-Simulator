#pragma once

#include "MappedScene.hpp"
#include <yaml-cpp/yaml.h>
#include <unordered_set>

// YAML adaptation stays outside the deterministic standard-C++ motion core.
ump::MappedSceneConfig readMappedSceneConfiguration(const YAML::Node& node,
    double width, double height, const std::unordered_set<std::string>& knownProfiles);

// No GT oracle is used to satisfy operational support. The first scene instead
// declares and validates an episode-separation assumption for retained windows.
void validateMappedSupportHorizon(const ump::MappedScene& scene, ump::AggregationTime horizonMs);

// Local-navigation velocities and lifecycle frames represent one motion step.
// A different outer capture cadence would silently discard realized substeps.
// Historical integration/corridor modes retain their established contract.
void validateMappedCaptureStep(const ump::MappedScene& scene, double simulationStepMs);
