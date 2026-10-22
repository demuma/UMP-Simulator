#pragma once

#include "AggregationInput.hpp"
#include "SemanticTaxonomy.hpp"
#include <array>
#include <string_view>
#include <memory>

namespace ump {

enum class MetricId {
    ObservationContributions, DistinctContributors, MeanSampleOccupancy,
    CellSideM, CellAreaM2, WindowDurationMs, AgeAtEvaluationMs, PostWindowDelayMs,
    MeasuredSampleFraction, OccupancyMae, MinCategoryDistinctContributors, SemanticMaxLoss, SemanticMeanLoss, Count
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

void validateMetricRequirements(const std::vector<MetricRequirement>& requirements, bool allowEmpty = false);
void validateSemanticMetricRequirements(const std::vector<MetricRequirement>& requirements);

// Compiled requirements may be infeasible for a cross-region footprint. Keep the
// contradictory bounds visible so assessment can fail explicitly without losing children.
struct EffectiveMetricPolicy {
    std::string id;
    std::vector<MetricRequirement> requirements;
    std::vector<std::string> sources;
    bool feasible = true;
};
class PolicyTree;

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
    std::optional<std::string> effectivePolicyId = std::nullopt;
    std::vector<std::string> policySources = {};
    bool policyFeasible = true;
    std::optional<SemanticRepresentation> semantic = std::nullopt;
};

struct WindowMetricAssessment {
    AggregationTime evaluatedAtMs;
    std::optional<std::string> policyId, policyVersion;
    AssessmentStatus coverageStatus;
    std::string coverageReason;
    AssessmentStatus status;
    std::vector<CellMetricAssessment> cells;
    std::string policyMode = "none";
};

// Stateless candidate evaluation apart from immutable, validated requirements.
// Uniform requirements or an immutable regional tree supply the cell-specific bounds.
class MetricEvaluator {
public:
    explicit MetricEvaluator(std::optional<MetricPolicy> policy = std::nullopt,
        std::shared_ptr<const SemanticTaxonomy> taxonomy = nullptr);
    explicit MetricEvaluator(std::shared_ptr<const PolicyTree> tree,
        std::shared_ptr<const SemanticTaxonomy> taxonomy = nullptr);
    const std::shared_ptr<const SemanticTaxonomy>& semanticTaxonomy() const { return taxonomy; }
    WindowMetricAssessment evaluate(const AggregationCandidate& candidate, AggregationTime evaluatedAtMs) const;

private:
    std::optional<MetricPolicy> policy;
    std::shared_ptr<const PolicyTree> tree;
    std::shared_ptr<const SemanticTaxonomy> taxonomy;
};

} // namespace ump
