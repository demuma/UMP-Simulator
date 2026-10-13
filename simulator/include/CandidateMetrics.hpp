#pragma once

#include "AggregationInput.hpp"
#include <array>
#include <string_view>

namespace ump {

enum class MetricId {
    ObservationContributions, DistinctContributors, MeanSampleOccupancy,
    CellSideM, CellAreaM2, WindowDurationMs, AgeAtEvaluationMs, PostWindowDelayMs,
    MeasuredSampleFraction, OccupancyMae, Count
};

struct MetricDefinition {
    MetricId id;
    const char* name;
    const char* unit;
    bool integral;
};

const std::array<MetricDefinition, static_cast<std::size_t>(MetricId::Count)>& metricDefinitions();
const MetricDefinition& metricDefinition(MetricId id);
MetricId metricIdFromName(std::string_view name);

struct MetricValue {
    MetricId id;
    std::optional<double> value;
    std::string unavailableReason;
};

struct MetricRequirement {
    MetricId id;
    std::optional<double> min;
    std::optional<double> max;
};

struct MetricPolicy {
    std::string id;
    std::string version;
    std::vector<MetricRequirement> requirements;
};

enum class AssessmentStatus { NotConfigured, NoCandidates, Pass, Fail, Unavailable };
const char* assessmentStatusName(AssessmentStatus status);

struct MetricCheck {
    MetricRequirement requirement;
    std::optional<double> observed;
    AssessmentStatus status;
    std::string reason;
};

struct CellMetricAssessment {
    int cellId;
    AssessmentStatus status;
    std::vector<MetricValue> metrics;
    std::vector<MetricCheck> checks;
};

struct WindowMetricAssessment {
    AggregationTime evaluatedAtMs;
    std::optional<std::string> policyId, policyVersion;
    AssessmentStatus coverageStatus;
    std::string coverageReason;
    AssessmentStatus status;
    std::vector<CellMetricAssessment> cells;
};

// Stateless candidate evaluation apart from immutable, validated requirements.
// A policy tree can supply an effective policy later; this initial policy is uniform.
class MetricEvaluator {
public:
    explicit MetricEvaluator(std::optional<MetricPolicy> policy = std::nullopt);
    WindowMetricAssessment evaluate(const AggregationCandidate& candidate, AggregationTime evaluatedAtMs) const;

private:
    std::optional<MetricPolicy> policy;
};

} // namespace ump
