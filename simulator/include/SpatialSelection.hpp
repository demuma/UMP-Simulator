#pragma once

#include "AggregationHistory.hpp"
#include "CandidateMetrics.hpp"

namespace ump {

struct SpatialSelectionConfig {
    int minDepth = 1;
    std::size_t maxEvaluations = 4096;
    // Common-window A07 fallback. Keep the whole-candidate baseline reproducible.
    // A partial proposal stays private while the temporal controller can extend.
    bool preserveValidDescendants = false;
};

struct SpatialCellDecision {
    int cellId;
    bool selected;
    std::string reason;
    std::vector<int> triggerCells;
    std::string transition = "initial";
};

enum class TemporalAction { EvaluateFinest, CoarsenSpatially, ExtendWindow, CoordinationHold, RequestHandoff, Finalize };
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

// Private action-selection diagnostics, separate from immutable hard policy
// checks. A zero ceiling permits declared zero-cost internal taxonomy nodes.
// Undefined actual loss means no observed support was selected for release.
struct SemanticPrioritySelection {
    double lossCeiling = 0;
    std::optional<double> actualMaxLoss = std::nullopt;
    std::size_t attemptedCeilings = 0;
    bool terminalFallback = false;
    std::string secondaryStrategy = "temporal_first";
    std::string releaseTrigger = "priority_satisfied";
    bool policySatisfiedRelease = false;
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
    // Local ownership domain, including measured-empty and suppressed support.
    // Absent in the common-window baseline. Never inferred from occupied output.
    std::optional<CellGeometry> coordinationCell = std::nullopt;
    std::optional<SemanticPrioritySelection> semanticPriority = std::nullopt;
};

// Internal, synchronous selection for disjoint windows of one stream. Finest-first
// search coarsens entire sibling footprints; proposals do not mutate transition state.
class SpatialSelector {
public:
    SpatialSelector(AggregationConfig config, SpatialSelectionConfig limits);
    SpatialSelection select(const AggregationCandidate& finest, const AggregationHistory& history,
        const MetricEvaluator& evaluator);
    // An optional preference filters hard-passing semantic representations;
    // all reported metric requirements/checks remain the original policy's.
    // No ceiling preserves the established TF/SF selection behavior.
    SpatialSelection propose(const AggregationCandidate& finest, const AggregationHistory& history,
        const MetricEvaluator& evaluator,
        std::optional<double> semanticLossCeiling = std::nullopt,
        bool allowSpatialMerges = true) const;
    void commit(const SpatialSelection& selection);
private:
    AggregationConfig config;
    SpatialSelectionConfig limits;
    std::optional<AggregationTime> previousEnd;
    std::vector<CellGeometry> previousSelected;
};

} // namespace ump
