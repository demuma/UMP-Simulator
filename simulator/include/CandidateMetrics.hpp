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
    MeasuredSampleFraction, OccupancyMae, MinCategoryDistinctContributors, SemanticMaxLoss, SemanticMeanLoss, SemanticSuppressionFraction, Count
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

// Private research accounting only: never add this to a recipient release.
// Suppression is local to one cell-window, not deletion of a physical person.
struct SemanticSuppressionAudit {
    std::uint64_t inputObservations = 0, inputDistinct = 0;
    std::uint64_t retainedObservations = 0, retainedDistinct = 0;
    std::uint64_t suppressedObservations = 0, suppressedDistinct = 0;
    std::map<std::string, std::uint64_t> suppressedTypeObservations;
    std::vector<std::string> suppressedLeaves;
    double fraction = 0, fullInputSemanticLoss = 0, unsuppressedSemanticLoss = 0;
    std::size_t evaluatedCandidates = 0;
    std::uint64_t evaluationNanoseconds = 0;
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
    // Original candidate evidence remains intact for retirement and revalidation.
    std::optional<AggregateCounts> retainedCounts = std::nullopt;
    std::optional<SemanticSuppressionAudit> semanticSuppression = std::nullopt;
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
        std::shared_ptr<const SemanticTaxonomy> taxonomy = nullptr,
        SemanticGeneralizationMode generalization = SemanticGeneralizationMode::Enabled);
    explicit MetricEvaluator(std::shared_ptr<const PolicyTree> tree,
        std::shared_ptr<const SemanticTaxonomy> taxonomy = nullptr,
        SemanticGeneralizationMode generalization = SemanticGeneralizationMode::Enabled);
    const std::shared_ptr<const SemanticTaxonomy>& semanticTaxonomy() const { return taxonomy; }
    SemanticGeneralizationMode semanticGeneralization() const { return generalization; }
    WindowMetricAssessment evaluate(const AggregationCandidate& candidate, AggregationTime evaluatedAtMs) const;

private:
    std::optional<MetricPolicy> policy;
    std::shared_ptr<const PolicyTree> tree;
    std::shared_ptr<const SemanticTaxonomy> taxonomy;
    SemanticGeneralizationMode generalization;
};

} // namespace ump
