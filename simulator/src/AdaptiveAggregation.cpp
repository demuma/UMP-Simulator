#include "AdaptiveAggregation.hpp"
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

namespace ump {
const char* adaptationStrategyName(AdaptationStrategy strategy) {
    switch (strategy) {
        case AdaptationStrategy::TemporalFirst: return "temporal_first";
        case AdaptationStrategy::SpatialFirst: return "spatial_first";
    }
    throw std::invalid_argument("Unknown adaptation strategy");
}

AdaptiveAggregation::AdaptiveAggregation(AggregationConfig settings,
    TemporalAdaptationConfig timeSettings, SpatialSelectionConfig spatial,
    MetricEvaluator metrics, Sink output)
    : config(std::move(settings)), temporal(timeSettings), evaluator(std::move(metrics)),
      selector(config, spatial), sink(std::move(output)), durationCapMs(temporal.maxWindowMs) {
    adaptationStrategyName(temporal.strategy);
    if (!sink || config.samplingPeriodMs <= 0 || config.windowMs <= 0
        || config.windowMs % config.samplingPeriodMs || temporal.extensionStepMs <= 0
        || temporal.extensionStepMs % config.samplingPeriodMs
        || temporal.maxWindowMs < config.windowMs
        || temporal.maxWindowMs % config.samplingPeriodMs || !temporal.maxEvaluations
        || temporal.maxWindowMs > 9007199254740991LL
        || !config.history || config.history->retentionMs < temporal.maxWindowMs)
        throw std::invalid_argument("Adaptive aggregation needs aligned bounded windows, sufficient history and a sink");
    const auto extra = temporal.maxWindowMs - config.windowMs;
    const auto probes = 1 + extra / temporal.extensionStepMs + (extra % temporal.extensionStepMs != 0);
    if (static_cast<std::uint64_t>(probes) > temporal.maxEvaluations)
        throw std::length_error("Adaptive window schedule exceeds temporal evaluation budget");

    // Resolve each complete base footprint, including empty regions. Requirements
    // are immutable, so their time maxima can safely bound every later common cut.
    AggregationCandidate footprint{config.runId, config.sensorId, config.applicationId,
        config.coverage, 0, 1, 1, false, 0, 0, 0, 0, WindowCoverage::NoScheduledSamples, {}, {}};
    for (int id = 12; id <= 15; ++id)
        footprint.cells.push_back({historyCell(config.coverage, id, 1), {}});
    const auto requirements = evaluator.evaluate(footprint, 1);
    for (const auto& cell : requirements.cells)
        for (const auto& check : cell.checks)
            if ((check.requirement.id == MetricId::WindowDurationMs
                    || check.requirement.id == MetricId::AgeAtEvaluationMs) && check.requirement.max) {
                const auto maximum = *check.requirement.max;
                if (maximum < 0)
                    throw std::invalid_argument("Adaptive time maxima must be nonnegative");
                // Only a bound already below the representable configured cap needs
                // conversion. An arbitrarily large upper bound cannot tighten it.
                if (maximum < static_cast<double>(durationCapMs))
                    durationCapMs = static_cast<AggregationTime>(maximum);
            }
    durationCapMs -= durationCapMs % config.samplingPeriodMs;
    if (durationCapMs <= 0)
        throw std::invalid_argument("Regional time maxima allow no positive aligned adaptive interval");
    regionalDeadline = durationCapMs < temporal.maxWindowMs;
    pending.nextEndMs = std::min(config.windowMs, durationCapMs);
}

void AdaptiveAggregation::validateTime(AggregationTime nowMs, const AggregationHistory& history) const {
    if (finished || emitting) throw std::logic_error("Adaptive stream is finished or its sink is reentrant");
    if (nowMs < lastNowMs || nowMs < pending.startMs
        || history.debugState().watermarkMs != nowMs)
        throw std::invalid_argument("Adaptive evaluation requires monotonic, already advanced shared history");
    if (nowMs > 9007199254740991LL - temporal.maxWindowMs)
        throw std::overflow_error("Adaptive clock exceeds supported numeric range");
}

void AdaptiveAggregation::advance(AggregationTime nowMs, const AggregationHistory& history) {
    validateTime(nowMs, history);
    while (pending.nextEndMs <= nowMs)
        evaluate(pending.nextEndMs, nowMs, history, false);
    lastNowMs = nowMs;
}

void AdaptiveAggregation::finish(AggregationTime endMs, const AggregationHistory& history) {
    validateTime(endMs, history);
    // At an exact scheduled endpoint, finalization must prevent another extension.
    // Earlier due endpoints retain their normal strategy semantics.
    while (pending.nextEndMs < endMs)
        evaluate(pending.nextEndMs, endMs, history, false);
    if (pending.startMs < endMs) evaluate(endMs, endMs, history, true);
    lastNowMs = endMs;
    finished = true;
}

void AdaptiveAggregation::evaluate(AggregationTime endMs, AggregationTime nowMs,
    const AggregationHistory& history, bool final) {
    auto next = pending; // A failed proposal or sink must not advance the private cut.
    if (++next.evaluations > temporal.maxEvaluations)
        throw std::length_error("Adaptive temporal evaluation budget exceeded");
    const auto query = history.queryFinest(next.startMs, endMs);
    if (!query.candidate)
        throw std::runtime_error("Adaptive interval is unavailable from bounded shared history");
    auto finest = *query.candidate;
    const auto& grid = finest.grid;
    const auto& expected = config.coverage;
    if (finest.runId != config.runId || finest.sensorId != config.sensorId
        || finest.applicationId != config.applicationId || grid.x != expected.x || grid.y != expected.y
        || grid.width != expected.width || grid.height != expected.height
        || grid.leafDepth != expected.leafDepth)
        throw std::invalid_argument("Adaptive history belongs to another stream or grid");
    finest.truncated = final;
    auto checked = evaluator.evaluate(finest, nowMs);
    next.decisions.push_back({TemporalAction::EvaluateFinest, next.startMs, endMs, nowMs, checked.status});
    const bool complete = finest.coverage == WindowCoverage::Complete;
    const bool finestPass = complete && (checked.status == AssessmentStatus::Pass
        || checked.status == AssessmentStatus::NoCandidates);
    const auto hardEnd = next.startMs + durationCapMs;
    const bool atLimit = endMs >= hardEnd;
    const bool deadlineReached = nowMs >= hardEnd;
    const bool terminal = final || atLimit || deadlineReached || !complete;
    std::optional<SpatialSelection> proposal;
    if (finestPass || terminal || temporal.strategy == AdaptationStrategy::TemporalFirst) {
        if (!finestPass)
            next.decisions.push_back({TemporalAction::CoarsenSpatially, next.startMs, endMs, nowMs, checked.status});
        proposal = selector.propose(finest, history, evaluator);
    }
    const bool selectedAll = proposal && proposal->suppressedCells == 0 && complete
        && (proposal->assessment.status == AssessmentStatus::Pass
            || proposal->assessment.status == AssessmentStatus::NoCandidates);
    if (selectedAll || terminal) {
        auto& result = *proposal;
        result.strategy = adaptationStrategyName(temporal.strategy);
        const auto extraDuration = std::max<AggregationTime>(0,
            endMs - next.startMs - std::min(config.windowMs, durationCapMs));
        result.temporalExtensions = static_cast<std::size_t>(extraDuration / temporal.extensionStepMs
            + (extraDuration % temporal.extensionStepMs != 0));
        result.completionReason = final ? "end_of_stream"
            : !complete ? "coverage_unavailable"
            : selectedAll ? "requirements_met"
            : regionalDeadline && (atLimit || deadlineReached) ? "policy_deadline" : "max_window";
        next.decisions.push_back({TemporalAction::Finalize, next.startMs, endMs, nowMs, result.assessment.status});
        result.temporalDecisions = std::move(next.decisions);
        emitting = true;
        try { sink(result); }
        catch (...) { emitting = false; throw; }
        emitting = false;
        selector.commit(result);
        ++completedWindows;
        pending = {};
        pending.startMs = endMs;
        pending.nextEndMs = endMs + std::min(config.windowMs, durationCapMs);
        return;
    }
    const auto extension = std::min(temporal.extensionStepMs, hardEnd - endMs);
    if (extension <= 0) throw std::logic_error("Adaptive extension cannot progress");
    next.nextEndMs = endMs + extension;
    ++next.extensions;
    next.decisions.push_back({TemporalAction::ExtendWindow, next.startMs, next.nextEndMs,
        nowMs, checked.status});
    // Retain already computed evidence only after an extension is accepted.
    // Terminal sink failures leave the prior snapshot and private cut intact.
    next.lastCheck = std::make_shared<const AggregationProgressCheck>(
        AggregationProgressCheck{std::move(finest), std::move(checked)});
    pending = std::move(next);
}

AdaptiveAggregationDebugState AdaptiveAggregation::debugState() const {
    return {pending.startMs, pending.nextEndMs, pending.startMs + durationCapMs,
        pending.extensions, pending.evaluations, pending.decisions.size(), completedWindows, finished};
}

AggregationProgress AdaptiveAggregation::progressSnapshot() const {
    return {adaptationStrategyName(temporal.strategy), pending.startMs, pending.nextEndMs,
        pending.startMs + durationCapMs, lastNowMs, pending.extensions, pending.evaluations,
        finished ? AggregationProgressPhase::Finished
            : pending.extensions ? AggregationProgressPhase::Extending : AggregationProgressPhase::Collecting,
        pending.lastCheck};
}
} // namespace ump
