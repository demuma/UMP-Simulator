#pragma once

#include "AggregationHistory.hpp"
#include "CandidateMetrics.hpp"

namespace ump {

struct SpatialSelectionConfig {
    int minDepth = 1;
    std::size_t maxEvaluations = 4096;
};

struct SpatialCellDecision {
    int cellId;
    bool selected;
    std::string reason;
    std::vector<int> triggerCells;
    std::string transition = "initial";
};

enum class TemporalAction { EvaluateFinest, CoarsenSpatially, ExtendWindow, Finalize };
const char* temporalActionName(TemporalAction action);
struct TemporalDecision {
    TemporalAction action;
    AggregationTime startMs, endMs, evaluatedAtMs;
    AssessmentStatus status;
};

struct SpatialAttempt {
    AggregatedCell cell;
    CellMetricAssessment assessment;
};

// Immutable once sent to a renderer/sink. No live Node/Agent pointers or private IDs.
// Suppressed footprints remain in candidate.cells for diagnostics, never as releases.
struct SpatialSelection {
    AggregationCandidate candidate;
    WindowMetricAssessment assessment;
    AggregationCandidate finest;
    WindowMetricAssessment finestAssessment;
    std::vector<SpatialCellDecision> decisions;
    std::vector<SpatialAttempt> attempts;
    int minDepth;
    std::size_t selectedCells = 0, suppressedCells = 0, coarsenedCells = 0, refinedCells = 0;
    std::string strategy = "temporal_first_spatial_only";
    std::size_t temporalExtensions = 0;
    std::string completionReason = "fixed_window";
    std::vector<TemporalDecision> temporalDecisions = {};
    std::string publicationState = "disabled";
    std::string releaseId = {};
};

// Internal, synchronous selection for disjoint windows of one stream. Finest-first
// search coarsens entire sibling footprints; proposals do not mutate transition state.
class SpatialSelector {
public:
    SpatialSelector(AggregationConfig config, SpatialSelectionConfig limits);
    SpatialSelection select(const AggregationCandidate& finest, const AggregationHistory& history,
        const MetricEvaluator& evaluator);
    SpatialSelection propose(const AggregationCandidate& finest, const AggregationHistory& history,
        const MetricEvaluator& evaluator) const;
    void commit(const SpatialSelection& selection);
private:
    AggregationConfig config;
    SpatialSelectionConfig limits;
    std::optional<AggregationTime> previousEnd;
    std::vector<CellGeometry> previousSelected;
};

} // namespace ump
