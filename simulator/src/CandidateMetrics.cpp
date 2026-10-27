#include "CandidateMetrics.hpp"
#include "PolicyTree.hpp"
#include <algorithm>
#include <cmath>
#include <chrono>
#include <set>
#include <limits>
#include <stdexcept>
#include <unordered_set>
#include <utility>

namespace ump {
const std::array<MetricDefinition, static_cast<std::size_t>(MetricId::Count)>& metricDefinitions() {
    static const std::array<MetricDefinition, static_cast<std::size_t>(MetricId::Count)> definitions{{
        {MetricId::ObservationContributions, "observation_contributions", "observations", true},
        {MetricId::DistinctContributors, "distinct_contributors", "contributors", true},
        {MetricId::MeanSampleOccupancy, "mean_sample_occupancy", "agents", false},
        {MetricId::CellSideM, "cell_side_m", "m", false},
        {MetricId::CellAreaM2, "cell_area_m2", "m2", false},
        {MetricId::WindowDurationMs, "window_duration_ms", "ms", true},
        {MetricId::AgeAtEvaluationMs, "age_at_evaluation_ms", "ms", true},
        {MetricId::PostWindowDelayMs, "post_window_delay_ms", "ms", true},
        {MetricId::MeasuredSampleFraction, "measured_sample_fraction", "fraction", false},
        {MetricId::OccupancyMae, "occupancy_mae", "agents", false},
        {MetricId::MinCategoryDistinctContributors, "min_category_distinct_contributors", "road_users", true},
        {MetricId::SemanticMaxLoss, "semantic_max_loss", "fraction", false},
        {MetricId::SemanticMeanLoss, "semantic_mean_loss", "fraction", false},
        {MetricId::SemanticSuppressionFraction, "semantic_suppression_fraction", "fraction", false}
    }};
    return definitions;
}

const MetricDefinition& metricDefinition(MetricId id) {
    const auto index = static_cast<std::size_t>(id);
    if (index >= metricDefinitions().size()) throw std::invalid_argument("Unknown metric ID");
    return metricDefinitions()[index];
}

MetricId metricIdFromName(std::string_view name) {
    for (const auto& definition : metricDefinitions())
        if (name == definition.name) return definition.id;
    throw std::invalid_argument("Unknown metric: " + std::string(name));
}

const char* assessmentStatusName(AssessmentStatus status) {
    switch (status) {
        case AssessmentStatus::NotConfigured: return "not_configured";
        case AssessmentStatus::NoCandidates: return "no_candidates";
        case AssessmentStatus::Pass: return "pass";
        case AssessmentStatus::Fail: return "fail";
        case AssessmentStatus::Unavailable: return "unavailable";
    }
    throw std::invalid_argument("Unknown assessment status");
}

MetricEvaluator::MetricEvaluator(std::optional<MetricPolicy> configured,
    std::shared_ptr<const SemanticTaxonomy> catalog, SemanticGeneralizationMode action)
    : policy(std::move(configured)), taxonomy(std::move(catalog)), generalization(action) {
    semanticGeneralizationModeName(generalization);
    if (generalization == SemanticGeneralizationMode::ExactOnly && !taxonomy)
        throw std::invalid_argument("Exact-only semantic release requires a taxonomy");
    if (taxonomy && !policy) throw std::invalid_argument("Semantic release requires an explicit metric policy");
    if (!policy) return;
    if (policy->id.empty() || policy->version.empty())
        throw std::invalid_argument("Metric policy requires ID and version");
    validateMetricRequirements(policy->requirements);
    if (generalization == SemanticGeneralizationMode::ExactOnly
        && std::any_of(policy->requirements.begin(), policy->requirements.end(), [](const auto& requirement) {
            return requirement.id == MetricId::SemanticSuppressionFraction && requirement.max && *requirement.max > 0;
        })) throw std::invalid_argument("Exact-only semantic release does not support selective suppression");
    if (!taxonomy && std::any_of(policy->requirements.begin(), policy->requirements.end(), [](const auto& requirement) {
            return requirement.id == MetricId::SemanticSuppressionFraction && requirement.max && *requirement.max > 0;
        })) throw std::invalid_argument("Semantic contribution suppression requires a semantic taxonomy");
    if (taxonomy) validateSemanticMetricRequirements(policy->requirements);
}

MetricEvaluator::MetricEvaluator(std::shared_ptr<const PolicyTree> compiled,
    std::shared_ptr<const SemanticTaxonomy> catalog, SemanticGeneralizationMode action)
    : tree(std::move(compiled)), taxonomy(std::move(catalog)), generalization(action) {
    if (!tree) throw std::invalid_argument("Regional metric evaluator requires a policy tree");
    semanticGeneralizationModeName(generalization);
    if (generalization == SemanticGeneralizationMode::ExactOnly) {
        if (!taxonomy) throw std::invalid_argument("Exact-only semantic release requires a taxonomy");
        if (tree->permitsSemanticSuppression())
            throw std::invalid_argument("Exact-only semantic release does not support selective suppression");
    }
}

void validateMetricRequirements(const std::vector<MetricRequirement>& requirements, bool allowEmpty) {
    if (requirements.empty() && !allowEmpty) throw std::invalid_argument("Metric requirements must not be empty");
    std::unordered_set<int> seen;
    for (const auto& requirement : requirements) {
        const auto& definition = metricDefinition(requirement.id);
        if (!seen.insert(static_cast<int>(requirement.id)).second)
            throw std::invalid_argument("Duplicate metric requirement: " + std::string(definition.name));
        if (!requirement.min && !requirement.max)
            throw std::invalid_argument("Metric requirement needs at least one bound");
        for (const auto& bound : {requirement.min, requirement.max}) {
            if (!bound) continue;
            if (!std::isfinite(*bound) || *bound < 0 || (definition.integral && std::floor(*bound) != *bound)
                || (definition.integral && *bound > 9007199254740991.0)
                || ((requirement.id == MetricId::MeasuredSampleFraction
                    || requirement.id == MetricId::SemanticMaxLoss || requirement.id == MetricId::SemanticMeanLoss
                    || requirement.id == MetricId::SemanticSuppressionFraction) && *bound > 1))
                throw std::invalid_argument("Invalid bound for metric: " + std::string(definition.name));
        }
        if (requirement.id == MetricId::MinCategoryDistinctContributors
            && (!requirement.min || *requirement.min < 1 || requirement.max))
            throw std::invalid_argument("min_category_distinct_contributors requires a positive minimum only");
        if ((requirement.id == MetricId::SemanticMaxLoss || requirement.id == MetricId::SemanticMeanLoss
                || requirement.id == MetricId::SemanticSuppressionFraction)
            && (requirement.min || !requirement.max))
            throw std::invalid_argument("Semantic loss requires an upper bound only");
        if (requirement.min && requirement.max && *requirement.min > *requirement.max)
            throw std::invalid_argument("Contradictory bounds for metric: " + std::string(definition.name));
    }
}

void validateSemanticMetricRequirements(const std::vector<MetricRequirement>& requirements) {
    bool support = false, maximumLoss = false;
    for (const auto& r : requirements) {
        support |= r.id == MetricId::MinCategoryDistinctContributors && r.min && *r.min >= 1;
        maximumLoss |= r.id == MetricId::SemanticMaxLoss && r.max.has_value();
    }
    if (!support || !maximumLoss)
        throw std::invalid_argument("Semantic taxonomy requires min_category_distinct_contributors.min and semantic_max_loss.max");
}

namespace {
void validateCounts(const AggregateCounts& counts, std::uint64_t measured) {
    if (counts.distinctContributors > counts.observationContributions
        || (!measured && counts.observationContributions))
        throw std::invalid_argument("Impossible candidate contribution counts");
    if (counts.observationContributions > 9007199254740991ULL)
        throw std::invalid_argument("Candidate count exceeds exact numeric metric range");
}

void validateCandidate(const AggregationCandidate& candidate, AggregationTime now) {
    if (candidate.startMs < 0 || candidate.endMs <= candidate.startMs
        || candidate.closedAtMs < candidate.endMs || now < candidate.closedAtMs
        || now > 9007199254740991LL)
        throw std::invalid_argument("Invalid candidate/evaluation times");
    if (candidate.measuredSamples > candidate.expectedSamples
        || candidate.unavailableSamples > candidate.expectedSamples - candidate.measuredSamples
        || candidate.missingSamples != candidate.expectedSamples - candidate.measuredSamples - candidate.unavailableSamples)
        throw std::invalid_argument("Inconsistent candidate sample counts");
    const auto expectedCoverage = !candidate.expectedSamples ? WindowCoverage::NoScheduledSamples
        : (candidate.missingSamples || candidate.unavailableSamples ? WindowCoverage::Incomplete : WindowCoverage::Complete);
    if (candidate.coverage != expectedCoverage)
        throw std::invalid_argument("Candidate coverage flag contradicts its sample counts");
    validateCounts(candidate.counts, candidate.measuredSamples);
    const auto& grid = candidate.grid;
    if (!std::isfinite(grid.x) || !std::isfinite(grid.y) || !std::isfinite(grid.width)
        || !std::isfinite(grid.height) || grid.width <= 0 || grid.height <= 0 || grid.leafDepth < 1
        || !std::isfinite(grid.x + grid.width) || !std::isfinite(grid.y + grid.height))
        throw std::invalid_argument("Invalid candidate grid geometry");
    std::unordered_set<int> ids;
    std::uint64_t contributions = 0, summedDistinct = 0;
    for (const auto& entry : candidate.cells) {
        const auto& cell = entry.cell;
        if (cell.id < 0 || cell.depth < 1 || cell.depth > grid.leafDepth || !ids.insert(cell.id).second
            || !std::isfinite(cell.x) || !std::isfinite(cell.y) || !std::isfinite(cell.width * cell.height)
            || cell.width <= 0 || cell.height <= 0 || cell.x < grid.x || cell.y < grid.y
            || cell.x + cell.width > grid.x + grid.width || cell.y + cell.height > grid.y + grid.height)
            throw std::invalid_argument("Invalid or duplicate candidate cell geometry");
        validateCounts(entry.counts, candidate.measuredSamples);
        if (entry.counts.distinctContributors > candidate.counts.distinctContributors
            || entry.counts.observationContributions > candidate.counts.observationContributions - contributions)
            throw std::invalid_argument("Cell counts exceed their window totals");
        contributions += entry.counts.observationContributions;
        summedDistinct += entry.counts.distinctContributors;
    }
    if (contributions != candidate.counts.observationContributions || candidate.counts.distinctContributors > summedDistinct)
        throw std::invalid_argument("Candidate cell contributions do not sum to window total");
}

std::vector<MetricValue> measure(const AggregationCandidate& candidate, const AggregatedCell& cell, AggregationTime now) {
    std::vector<MetricValue> values;
    values.reserve(metricDefinitions().size());
    const auto add = [&](MetricId id, double value) { values.push_back({id, value, {}}); };
    const auto absent = [&](MetricId id, const char* reason) { values.push_back({id, {}, reason}); };
    add(MetricId::ObservationContributions, cell.counts.observationContributions);
    if (candidate.measuredSamples) {
        add(MetricId::DistinctContributors, cell.counts.distinctContributors);
        add(MetricId::MeanSampleOccupancy,
            static_cast<double>(cell.counts.observationContributions) / candidate.measuredSamples);
    } else {
        absent(MetricId::DistinctContributors, "no_measured_samples");
        absent(MetricId::MeanSampleOccupancy, "no_measured_samples");
    }
    if (cell.cell.width == cell.cell.height) add(MetricId::CellSideM, cell.cell.width);
    else absent(MetricId::CellSideM, "non_square_support");
    add(MetricId::CellAreaM2, cell.cell.width * cell.cell.height);
    add(MetricId::WindowDurationMs, candidate.endMs - candidate.startMs);
    add(MetricId::AgeAtEvaluationMs, now - candidate.startMs);
    add(MetricId::PostWindowDelayMs, now - candidate.endMs);
    if (candidate.expectedSamples)
        add(MetricId::MeasuredSampleFraction, static_cast<double>(candidate.measuredSamples) / candidate.expectedSamples);
    else absent(MetricId::MeasuredSampleFraction, "no_scheduled_samples");
    absent(MetricId::OccupancyMae, "offline_reference_required");
    absent(MetricId::MinCategoryDistinctContributors, "semantic_not_enabled");
    absent(MetricId::SemanticMaxLoss, "semantic_not_enabled");
    absent(MetricId::SemanticMeanLoss, "semantic_not_enabled");
    values.push_back({MetricId::SemanticSuppressionFraction, 0, "semantic_suppression_not_configured"});
    return values;
}
}

WindowMetricAssessment MetricEvaluator::evaluate(const AggregationCandidate& candidate, AggregationTime now) const {
    validateCandidate(candidate, now);
    if (tree) tree->validateContext(candidate.grid, candidate.applicationId);
    const bool configured = policy.has_value() || static_cast<bool>(tree);
    const bool complete = candidate.coverage == WindowCoverage::Complete;
    WindowMetricAssessment output{now, {}, {}, complete ? AssessmentStatus::Pass : AssessmentStatus::Unavailable,
        complete ? "complete_observation_coverage" : candidate.expectedSamples ? "incomplete_observation_coverage" : "no_scheduled_samples",
        AssessmentStatus::NotConfigured, {}};
    if (policy) { output.policyId = policy->id; output.policyVersion = policy->version; output.policyMode = "uniform"; }
    if (tree) { output.policyId = tree->id(); output.policyVersion = tree->version(); output.policyMode = "regional_tree"; }
    output.cells.reserve(candidate.cells.size());
    bool anyFailed = false, anyUnavailable = false;
    for (const auto& cell : candidate.cells) {
        CellMetricAssessment result{cell.cell.id, AssessmentStatus::NotConfigured, measure(candidate, cell, now), {}};
        if (!configured) { output.cells.push_back(std::move(result)); continue; }
        const std::vector<MetricRequirement>* requirements = nullptr;
        if (tree) {
            const auto& effective = tree->resolve(cell.cell);
            requirements = &effective.requirements;
            result.effectivePolicyId = effective.id;
            result.policySources = effective.sources;
            result.policyFeasible = effective.feasible;
        } else {
            requirements = &policy->requirements;
            result.effectivePolicyId = policy->id;
            result.policySources = {"uniform:" + policy->id};
        }
        double suppressionCap = 0;
        bool suppressionConfigured = false;
        std::uint64_t support = 1;
        for (const auto& required : *requirements) {
            if (required.id == MetricId::MinCategoryDistinctContributors && required.min)
                support = static_cast<std::uint64_t>(*required.min);
            if (required.id == MetricId::SemanticSuppressionFraction && required.max) {
                suppressionCap = *required.max; suppressionConfigured = true;
            }
        }
        if (suppressionConfigured)
            result.metrics.at(static_cast<std::size_t>(MetricId::SemanticSuppressionFraction)).unavailableReason.clear();
        if (suppressionCap > 0 && !taxonomy)
            throw std::invalid_argument("Semantic contribution suppression requires a semantic taxonomy");
        if (suppressionCap > 0 && generalization == SemanticGeneralizationMode::ExactOnly)
            throw std::invalid_argument("Exact-only semantic release does not support selective suppression");
        const auto setSemanticMetrics = [](CellMetricAssessment& target, const SemanticRepresentation& representation) {
            const auto set = [&](MetricId id, double value) {
                auto& measured = target.metrics.at(static_cast<std::size_t>(id));
                measured.value = value; measured.unavailableReason.clear();
            };
            target.semantic = representation;
            set(MetricId::MinCategoryDistinctContributors, representation.minimumDistinctContributors);
            set(MetricId::SemanticMaxLoss, representation.maxLoss);
            set(MetricId::SemanticMeanLoss, representation.meanLoss);
        };
        // All hard requirements are reassessed on the retained union, including
        // total distinct support and occupancy. Suppression never repairs k by
        // counting removed identities or repeated observations.
        const auto assess = [&](CellMetricAssessment& target) {
            target.checks.clear();
            bool failed = false, unavailable = false;
            for (const auto& required : *requirements) {
                const auto& metric = target.metrics.at(static_cast<std::size_t>(required.id));
                MetricCheck check{required, metric.value, AssessmentStatus::Pass, "within_bounds"};
                if (required.min && required.max && *required.min > *required.max) {
                    failed = true; check.status = AssessmentStatus::Fail; check.reason = "contradictory_policy_bounds";
                } else if (!metric.value) {
                    unavailable = true; check.status = AssessmentStatus::Unavailable; check.reason = metric.unavailableReason;
                } else if (required.min && *metric.value < *required.min) {
                    failed = true; check.status = AssessmentStatus::Fail; check.reason = "below_minimum";
                } else if (required.max && *metric.value > *required.max) {
                    failed = true; check.status = AssessmentStatus::Fail; check.reason = "above_maximum";
                }
                target.checks.push_back(std::move(check));
            }
            target.status = !complete ? AssessmentStatus::Unavailable : failed ? AssessmentStatus::Fail
                : unavailable ? AssessmentStatus::Unavailable : AssessmentStatus::Pass;
        };
        if (taxonomy) {
            validateSemanticMetricRequirements(*requirements);
            for (const auto id : {MetricId::MinCategoryDistinctContributors,
                    MetricId::SemanticMaxLoss, MetricId::SemanticMeanLoss})
                result.metrics.at(static_cast<std::size_t>(id)).unavailableReason = "semantic_evidence_unavailable";
            if (cell.counts.semanticEvidence) {
                std::map<std::string, std::uint64_t> leafObservations;
                std::uint64_t total = 0;
                for (const auto& entry : cell.counts.typeObservationContributions) {
                    if (entry.second > cell.counts.observationContributions - total)
                        throw std::invalid_argument("Semantic raw type counts exceed candidate support");
                    total += entry.second;
                    leafObservations[taxonomy->leafForType(entry.first)] += entry.second;
                }
                if (total != cell.counts.observationContributions)
                    throw std::invalid_argument("Semantic raw type counts omit candidate observations");
                for (const auto& node : taxonomy->nodes()) if (!node.inputTypes.empty()) {
                    const auto at = cell.counts.semanticEvidence->nodes.find(node.id);
                    if (at == cell.counts.semanticEvidence->nodes.end()
                        || at->second.observationContributions != leafObservations[node.id])
                        throw std::invalid_argument("Semantic evidence contradicts raw type observations");
                }
                setSemanticMetrics(result, taxonomy->select(*cell.counts.semanticEvidence,
                    cell.counts.observationContributions, cell.counts.distinctContributors, support, generalization));
            }
        }
        assess(result);
        if (suppressionCap > 0 && complete && cell.counts.semanticEvidence && result.semantic) {
            const auto started = std::chrono::steady_clock::now();
            SemanticSuppressionAudit audit;
            audit.inputObservations = audit.retainedObservations = cell.counts.observationContributions;
            audit.inputDistinct = audit.retainedDistinct = cell.counts.distinctContributors;
            audit.fullInputSemanticLoss = audit.unsuppressedSemanticLoss = result.semantic->meanLoss;
            for (auto& proposal : taxonomy->suppressionCandidates(*cell.counts.semanticEvidence,
                    cell.counts.observationContributions, cell.counts.distinctContributors, support)) {
                const auto totals = proposal.retainedEvidence.nodes.at(taxonomy->root());
                const auto removed = cell.counts.observationContributions - totals.observationContributions;
                const double fraction = static_cast<double>(removed) / cell.counts.observationContributions;
                if (!removed || fraction > suppressionCap) continue;
                ++audit.evaluatedCandidates;
                auto alternative = result;
                alternative.retainedCounts = cell.counts;
                auto& retained = *alternative.retainedCounts;
                retained.observationContributions = totals.observationContributions;
                retained.distinctContributors = totals.distinctContributors;
                retained.meanSampleOccupancy = candidate.measuredSamples
                    ? std::optional<double>{static_cast<double>(totals.observationContributions) / candidate.measuredSamples}
                    : std::nullopt;
                retained.semanticEvidence = std::move(proposal.retainedEvidence);
                const std::set<std::string> removedLeaves(proposal.suppressedLeaves.begin(), proposal.suppressedLeaves.end());
                for (auto at = retained.typeObservationContributions.begin(); at != retained.typeObservationContributions.end();) {
                    if (removedLeaves.count(taxonomy->leafForType(at->first))) at = retained.typeObservationContributions.erase(at);
                    else ++at;
                }
                alternative.metrics = measure(candidate, {cell.cell, retained}, now);
                auto& fractionMetric = alternative.metrics.at(static_cast<std::size_t>(MetricId::SemanticSuppressionFraction));
                fractionMetric.value = fraction; fractionMetric.unavailableReason.clear();
                setSemanticMetrics(alternative, proposal.retainedRepresentation);
                assess(alternative);
                if (alternative.status != AssessmentStatus::Pass) continue;
                const auto& old = *result.semantic;
                const auto& proposed = *alternative.semantic;
                // Removing an observation costs one full unit. This conservative
                // full-input objective prevents a prettier conditional semantic
                // average obtained by discarding more information than it saves.
                const double fullLoss = static_cast<double>((static_cast<long double>(removed)
                    + static_cast<long double>(retained.observationContributions) * proposed.meanLoss)
                    / cell.counts.observationContributions);
                constexpr double tolerance = 1e-12;
                if (!(fullLoss < audit.unsuppressedSemanticLoss - tolerance)) continue;
                const bool better = fullLoss < audit.fullInputSemanticLoss - tolerance
                    || (std::abs(fullLoss - audit.fullInputSemanticLoss) <= tolerance
                        && (proposed.maxLoss < old.maxLoss
                            || (proposed.maxLoss == old.maxLoss && proposed.meanLoss < old.meanLoss)
                            || (result.retainedCounts && proposed.maxLoss == old.maxLoss && proposed.meanLoss == old.meanLoss
                                && retained.observationContributions > result.retainedCounts->observationContributions)));
                if (!better) continue;
                result = std::move(alternative);
                audit.retainedObservations = totals.observationContributions;
                audit.retainedDistinct = totals.distinctContributors;
                audit.suppressedObservations = removed;
                audit.suppressedDistinct = audit.inputDistinct - totals.distinctContributors;
                audit.suppressedLeaves = std::move(proposal.suppressedLeaves);
                audit.fraction = fraction;
                audit.fullInputSemanticLoss = fullLoss;
                audit.suppressedTypeObservations.clear();
                for (const auto& entry : cell.counts.typeObservationContributions)
                    if (removedLeaves.count(taxonomy->leafForType(entry.first))) audit.suppressedTypeObservations.insert(entry);
            }
            audit.evaluationNanoseconds = static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now() - started).count());
            result.semanticSuppression = std::move(audit);
        }
        anyFailed |= result.status == AssessmentStatus::Fail;
        anyUnavailable |= result.status == AssessmentStatus::Unavailable;
        output.cells.push_back(std::move(result));
    }
    if (configured) output.status = !complete ? AssessmentStatus::Unavailable
        : output.cells.empty() ? AssessmentStatus::NoCandidates : anyFailed ? AssessmentStatus::Fail
        : anyUnavailable ? AssessmentStatus::Unavailable : AssessmentStatus::Pass;
    return output;
}
} // namespace ump
