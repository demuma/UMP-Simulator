#include "AdaptiveAggregation.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace ump {
namespace {
struct SemanticCutQuality {
    std::uint64_t retained = 0, accounted = 0;
    std::optional<double> maxLoss;
    // At equal retained support, this sum orders the observation-weighted
    // mean cell side without an extra floating-point division.
    long double weightedSide = 0;
    std::vector<int> selectedCellIds;
};

SemanticCutQuality semanticCutQuality(const SpatialSelection& selection,
    std::uint64_t originalContributions) {
    if (selection.decisions.size() != selection.candidate.cells.size()
        || selection.assessment.cells.size() != selection.candidate.cells.size())
        throw std::logic_error("Semantic preference proposal has inconsistent cell accounting");
    SemanticCutQuality quality;
    for (std::size_t i = 0; i < selection.decisions.size(); ++i) {
        if (!selection.decisions[i].selected) continue;
        const auto& cell = selection.candidate.cells[i];
        const auto& assessment = selection.assessment.cells[i];
        if (selection.decisions[i].cellId != cell.cell.id || assessment.cellId != cell.cell.id
            || assessment.status != AssessmentStatus::Pass || !assessment.semantic
            || cell.counts.observationContributions > originalContributions - quality.accounted)
            throw std::logic_error("Semantic preference selected invalid or duplicated observed support");
        const auto& retained = assessment.retainedCounts ? *assessment.retainedCounts : cell.counts;
        quality.accounted += cell.counts.observationContributions;
        quality.retained += retained.observationContributions;
        quality.maxLoss = std::max(quality.maxLoss.value_or(0), assessment.semantic->maxLoss);
        quality.weightedSide += static_cast<long double>(retained.observationContributions) * cell.cell.width;
        quality.selectedCellIds.push_back(cell.cell.id);
    }
    return quality;
}

bool completeSemanticCut(const SpatialSelection& selection, const SemanticCutQuality& quality,
    const AggregationCandidate& finest) {
    return finest.coverage == WindowCoverage::Complete && selection.suppressedCells == 0
        && quality.accounted == finest.counts.observationContributions
        && (selection.assessment.status == AssessmentStatus::Pass
            || selection.assessment.status == AssessmentStatus::NoCandidates);
}

bool betterSemanticPartial(const SemanticCutQuality& candidate, const SemanticCutQuality& previous) {
    if (candidate.retained != previous.retained) return candidate.retained > previous.retained;
    const double candidateLoss = candidate.maxLoss.value_or(std::numeric_limits<double>::infinity());
    const double previousLoss = previous.maxLoss.value_or(std::numeric_limits<double>::infinity());
    if (candidateLoss != previousLoss) return candidateLoss < previousLoss;
    if (candidate.weightedSide != previous.weightedSide) return candidate.weightedSide < previous.weightedSide;
    return candidate.selectedCellIds < previous.selectedCellIds;
}
}

const char* adaptationStrategyName(AdaptationStrategy strategy) {
    switch (strategy) {
        case AdaptationStrategy::TemporalFirst: return "temporal_first";
        case AdaptationStrategy::SpatialFirst: return "spatial_first";
        case AdaptationStrategy::SemanticFirst: return "semantic_first";
    }
    throw std::invalid_argument("Unknown adaptation strategy");
}

const char* semanticSecondaryStrategyName(SemanticSecondaryStrategy strategy) {
    switch (strategy) {
        case SemanticSecondaryStrategy::TemporalFirst: return "temporal_first";
        case SemanticSecondaryStrategy::SpatialFirst: return "spatial_first";
    }
    throw std::invalid_argument("Unknown semantic secondary strategy");
}

const char* releaseTriggerName(ReleaseTrigger trigger) {
    switch (trigger) {
        case ReleaseTrigger::PolicySatisfied: return "policy_satisfied";
        case ReleaseTrigger::PrioritySatisfied: return "priority_satisfied";
    }
    throw std::invalid_argument("Unknown semantic release trigger");
}

AdaptiveAggregation::AdaptiveAggregation(AggregationConfig settings,
    TemporalAdaptationConfig timeSettings, SpatialSelectionConfig spatial,
    MetricEvaluator metrics, Sink output)
    : config(std::move(settings)), temporal(timeSettings), evaluator(std::move(metrics)),
      selector(config, spatial), sink(std::move(output)), durationCapMs(temporal.maxWindowMs) {
    if (config.semanticGeneralization != evaluator.semanticGeneralization())
        throw std::invalid_argument("Adaptive aggregation requires the same immutable semantic action mode as its evaluator");
    adaptationStrategyName(temporal.strategy);
    semanticSecondaryStrategyName(temporal.semanticSecondaryStrategy);
    releaseTriggerName(temporal.releaseTrigger);
    if (temporal.coordination != CoordinationMode::CommonWindow)
        throw std::invalid_argument("Cell-local configuration requires CellLocalAggregation");
    if (temporal.strategy == AdaptationStrategy::SemanticFirst
        && (!config.semanticTaxonomy || config.semanticTaxonomy != evaluator.semanticTaxonomy()))
        throw std::invalid_argument("Semantic First requires the same immutable taxonomy in configuration and evaluator");
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
    bool selectedAll = false;
    if (temporal.strategy == AdaptationStrategy::SemanticFirst) {
        const bool finestPreferred = finestPass && std::all_of(checked.cells.begin(), checked.cells.end(),
            [](const auto& cell) { return cell.semantic && cell.semantic->maxLoss == 0; });
        const bool immediatePolicy = temporal.releaseTrigger == ReleaseTrigger::PolicySatisfied;
        // Immediate policy release searches all legal spatial cuts now. With
        // explicit preference waiting, Spatial secondary protects the finest
        // geometry until the deadline; Temporal secondary merges before waiting.
        // Neither choice rewrites the immutable regional metric requirements.
        const bool allowMerges = immediatePolicy || terminal
            || temporal.semanticSecondaryStrategy == SemanticSecondaryStrategy::TemporalFirst;
        if (!finestPreferred && allowMerges)
            next.decisions.push_back({TemporalAction::CoarsenSpatially, next.startMs, endMs, nowMs, checked.status});
        proposal = selector.propose(finest, history, evaluator, 0.0, allowMerges);
        auto quality = semanticCutQuality(*proposal, finest.counts.observationContributions);
        selectedAll = completeSemanticCut(*proposal, quality, finest);
        double selectedCeiling = 0;
        std::size_t attemptedCeilings = 1;
        bool terminalFallback = false;
        if (evaluator.semanticGeneralization() == SemanticGeneralizationMode::Enabled
            && (terminal || immediatePolicy) && complete && !selectedAll) {
            std::vector<double> ceilings;
            for (const auto& node : config.semanticTaxonomy->nodes())
                if (node.loss > 0) ceilings.push_back(node.loss);
            std::sort(ceilings.begin(), ceilings.end());
            ceilings.erase(std::unique(ceilings.begin(), ceilings.end()), ceilings.end());
            // Each proposal has the existing independent spatial budget; the
            // validated catalog bounds this loop to at most 256 total ceilings.
            // Proposals do not mutate selector history or publication state.
            for (double ceiling : ceilings) {
                auto alternative = selector.propose(finest, history, evaluator, ceiling);
                ++attemptedCeilings;
                terminalFallback = terminal;
                auto alternativeQuality = semanticCutQuality(alternative, finest.counts.observationContributions);
                const bool alternativeFull = completeSemanticCut(alternative, alternativeQuality, finest);
                // Prefer the first full cut in ascending loss ceilings. If no
                // full cut exists, retain as much observed support as possible,
                // then prefer lower worst loss and finer spatial detail. This
                // is a bounded proposal comparison, not global cut optimization.
                if (alternativeFull || betterSemanticPartial(alternativeQuality, quality)) {
                    proposal = std::move(alternative);
                    quality = std::move(alternativeQuality);
                    selectedCeiling = ceiling;
                }
                if (alternativeFull) {
                    selectedAll = true;
                    break;
                }
            }
        }
        proposal->semanticPriority = SemanticPrioritySelection{
            selectedCeiling, quality.maxLoss, attemptedCeilings, terminalFallback,
            semanticSecondaryStrategyName(temporal.semanticSecondaryStrategy),
            releaseTriggerName(temporal.releaseTrigger), selectedAll && immediatePolicy};
    } else {
        // Keep the legacy TF/SF branch and its diagnostic output unchanged.
        if (finestPass || terminal || temporal.strategy == AdaptationStrategy::TemporalFirst) {
            if (!finestPass)
                next.decisions.push_back({TemporalAction::CoarsenSpatially, next.startMs, endMs, nowMs, checked.status});
            proposal = selector.propose(finest, history, evaluator);
        }
        selectedAll = proposal && proposal->suppressedCells == 0 && complete
            && (proposal->assessment.status == AssessmentStatus::Pass
                || proposal->assessment.status == AssessmentStatus::NoCandidates);
    }
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
