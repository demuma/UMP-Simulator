#pragma once

#include "SpatialSelection.hpp"
#include "AggregationProgress.hpp"
#include <functional>

namespace ump {

enum class AdaptationStrategy { TemporalFirst, SpatialFirst, SemanticFirst };
const char* adaptationStrategyName(AdaptationStrategy strategy);

enum class CoordinationMode { CommonWindow, CellLocal };
enum class SemanticSecondaryStrategy { TemporalFirst, SpatialFirst };
enum class ReleaseTrigger { PolicySatisfied, PrioritySatisfied };
const char* semanticSecondaryStrategyName(SemanticSecondaryStrategy strategy);
const char* releaseTriggerName(ReleaseTrigger trigger);

struct TemporalAdaptationConfig {
    AdaptationStrategy strategy = AdaptationStrategy::TemporalFirst;
    AggregationTime extensionStepMs = 100;
    AggregationTime maxWindowMs = 1000;
    std::size_t maxEvaluations = 1024;
    CoordinationMode coordination = CoordinationMode::CommonWindow;
    std::size_t maxActiveCells = 16384;
    // Semantic controller only: secondary order and hard-eligibility versus
    // intentional preference waiting. Appended for aggregate-initializer safety.
    SemanticSecondaryStrategy semanticSecondaryStrategy = SemanticSecondaryStrategy::TemporalFirst;
    ReleaseTrigger releaseTrigger = ReleaseTrigger::PolicySatisfied;
};

struct AdaptiveAggregationDebugState {
    AggregationTime windowStartMs, nextEndMs, hardDeadlineMs;
    std::size_t temporalExtensions, temporalEvaluations, retainedDecisions;
    std::uint64_t completedWindows;
    bool finished;
};

// One application and one whole-grid coordination domain. All cells share the
// interval; no support becomes public until a terminal cut reaches the sink.
// History is shared with the input manager and must already be advanced to nowMs.
class AdaptiveAggregation {
public:
    using Sink = std::function<void(const SpatialSelection&)>;
    AdaptiveAggregation(AggregationConfig config, TemporalAdaptationConfig temporal,
        SpatialSelectionConfig spatial, MetricEvaluator evaluator, Sink sink);
    void advance(AggregationTime nowMs, const AggregationHistory& history);
    void finish(AggregationTime endMs, const AggregationHistory& history);
    AdaptiveAggregationDebugState debugState() const;
    AggregationProgress progressSnapshot() const;

private:
    struct Pending {
        AggregationTime startMs = 0, nextEndMs = 0;
        std::size_t extensions = 0, evaluations = 0;
        std::vector<TemporalDecision> decisions;
        std::shared_ptr<const AggregationProgressCheck> lastCheck;
    };
    void validateTime(AggregationTime nowMs, const AggregationHistory& history) const;
    void evaluate(AggregationTime endMs, AggregationTime nowMs,
        const AggregationHistory& history, bool final);
    AggregationConfig config;
    TemporalAdaptationConfig temporal;
    MetricEvaluator evaluator;
    SpatialSelector selector;
    Sink sink;
    AggregationTime durationCapMs, lastNowMs = 0;
    bool regionalDeadline = false, finished = false, emitting = false;
    std::uint64_t completedWindows = 0;
    Pending pending;
};

} // namespace ump
