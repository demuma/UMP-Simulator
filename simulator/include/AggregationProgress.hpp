#pragma once

#include "CandidateMetrics.hpp"
#include <memory>
#include <string>

namespace ump {

enum class AggregationProgressPhase { Collecting, Extending, Finished };

// Evidence from the last completed finest-cell check of the current window.
// Its candidate interval and evaluation time remain explicit: this is not a
// continuously updated measurement or a publication decision. No private IDs.
struct AggregationProgressCheck {
    AggregationCandidate candidate;
    WindowMetricAssessment assessment;
};

struct CellAggregationProgress {
    CellGeometry cell;
    AggregationTime startMs, nextEndMs, hardDeadlineMs;
    std::size_t temporalExtensions = 0, evaluations = 0;
    std::shared_ptr<const AggregationProgressCheck> lastCheck;
};

// Internal renderer diagnostics, separate from the last finalized spatial cut.
// Copies share immutable check evidence; waiting ticks do not query history or
// recalculate metrics. A new window always starts without a previous check.
struct AggregationProgress {
    std::string strategy;
    AggregationTime startMs = 0;
    AggregationTime nextEndMs = 0;
    AggregationTime hardDeadlineMs = 0;
    // Successfully processed simulation time, including ticks without a sample.
    AggregationTime observedThroughMs = 0;
    std::size_t temporalExtensions = 0;
    std::size_t evaluations = 0;
    AggregationProgressPhase phase = AggregationProgressPhase::Collecting;
    std::shared_ptr<const AggregationProgressCheck> lastCheck;
    // In local mode top-level clocks are a summary; these are the actual owners.
    bool cellLocal = false;
    std::vector<CellAggregationProgress> cells;
};

} // namespace ump
