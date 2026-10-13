#include "CandidateMetrics.hpp"
#include <algorithm>
#include <cmath>
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
        {MetricId::OccupancyMae, "occupancy_mae", "agents", false}
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

MetricEvaluator::MetricEvaluator(std::optional<MetricPolicy> configured) : policy(std::move(configured)) {
    if (!policy) return;
    if (policy->id.empty() || policy->version.empty() || policy->requirements.empty())
        throw std::invalid_argument("Metric policy requires ID, version and nonempty requirements");
    std::unordered_set<int> seen;
    for (const auto& requirement : policy->requirements) {
        const auto& definition = metricDefinition(requirement.id);
        if (!seen.insert(static_cast<int>(requirement.id)).second)
            throw std::invalid_argument("Duplicate metric requirement: " + std::string(definition.name));
        if (!requirement.min && !requirement.max)
            throw std::invalid_argument("Metric requirement needs at least one bound");
        for (const auto& bound : {requirement.min, requirement.max}) {
            if (!bound) continue;
            if (!std::isfinite(*bound) || *bound < 0 || (definition.integral && std::floor(*bound) != *bound)
                || (definition.integral && *bound > 9007199254740991.0)
                || (requirement.id == MetricId::MeasuredSampleFraction && *bound > 1))
                throw std::invalid_argument("Invalid bound for metric: " + std::string(definition.name));
        }
        if (requirement.min && requirement.max && *requirement.min > *requirement.max)
            throw std::invalid_argument("Contradictory bounds for metric: " + std::string(definition.name));
    }
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
    return values;
}
}

WindowMetricAssessment MetricEvaluator::evaluate(const AggregationCandidate& candidate, AggregationTime now) const {
    validateCandidate(candidate, now);
    const bool complete = candidate.coverage == WindowCoverage::Complete;
    WindowMetricAssessment output{now, {}, {}, complete ? AssessmentStatus::Pass : AssessmentStatus::Unavailable,
        complete ? "complete_observation_coverage" : candidate.expectedSamples ? "incomplete_observation_coverage" : "no_scheduled_samples",
        AssessmentStatus::NotConfigured, {}};
    if (policy) { output.policyId = policy->id; output.policyVersion = policy->version; }
    output.cells.reserve(candidate.cells.size());
    bool anyFailed = false, anyUnavailable = false;
    for (const auto& cell : candidate.cells) {
        CellMetricAssessment result{cell.cell.id, AssessmentStatus::NotConfigured, measure(candidate, cell, now), {}};
        bool failed = false, unavailable = false;
        if (policy) {
            for (const auto& required : policy->requirements) {
                const auto& metric = result.metrics.at(static_cast<std::size_t>(required.id));
                MetricCheck check{required, metric.value, AssessmentStatus::Pass, "within_bounds"};
                if (!metric.value) {
                    unavailable = true;
                    check.status = AssessmentStatus::Unavailable;
                    check.reason = metric.unavailableReason;
                } else if (required.min && *metric.value < *required.min) {
                    failed = true; check.status = AssessmentStatus::Fail; check.reason = "below_minimum";
                } else if (required.max && *metric.value > *required.max) {
                    failed = true; check.status = AssessmentStatus::Fail; check.reason = "above_maximum";
                }
                result.checks.push_back(std::move(check));
            }
            result.status = !complete ? AssessmentStatus::Unavailable : failed ? AssessmentStatus::Fail
                : unavailable ? AssessmentStatus::Unavailable : AssessmentStatus::Pass;
        }
        anyFailed |= failed;
        anyUnavailable |= unavailable;
        output.cells.push_back(std::move(result));
    }
    if (policy) output.status = !complete ? AssessmentStatus::Unavailable
        : output.cells.empty() ? AssessmentStatus::NoCandidates : anyFailed ? AssessmentStatus::Fail
        : anyUnavailable ? AssessmentStatus::Unavailable : AssessmentStatus::Pass;
    return output;
}
} // namespace ump
