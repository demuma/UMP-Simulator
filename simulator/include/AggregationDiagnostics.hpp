#pragma once

#include "CandidateMetrics.hpp"
#include <functional>
#include <chrono>
#include <string>

// External file sink; persistence dependencies stay outside the aggregation core.
using AggregationDiagnosticsSink = std::function<void(const ump::AggregationCandidate&, const ump::WindowMetricAssessment&)>;
AggregationDiagnosticsSink makeAggregationDiagnosticsSink(const std::string& directory,
    std::chrono::system_clock::time_point simulationOrigin);
