#pragma once

#include "AggregationManager.hpp"
#include <chrono>
#include <string>

// External file sink; persistence dependencies stay outside the aggregation core.
AggregationManager::Sink makeAggregationDiagnosticsSink(const std::string& directory,
    std::chrono::system_clock::time_point simulationOrigin);
