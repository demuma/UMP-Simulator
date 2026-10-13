#include "CandidateMetrics.hpp"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
using namespace ump;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class F> void rejects(F function, const char* message) {
    bool rejected = false;
    try { function(); } catch (const std::exception&) { rejected = true; }
    require(rejected, message);
}
AggregateCounts counts(std::uint64_t contributions, std::uint64_t distinct, std::uint64_t samples) {
    AggregateCounts result{contributions, distinct, {{"pedestrian", contributions}}, {}};
    if (samples) result.meanSampleOccupancy = static_cast<double>(contributions) / samples;
    return result;
}
AggregationCandidate candidate() {
    return {"run", "sensor", "application", {0, 0, 20, 20, 2}, 0, 400, 400, false,
        3, 3, 0, 0, WindowCoverage::Complete, counts(4, 2, 3),
        {{{48, 2, 0, 0, 5, 5}, counts(4, 2, 3)}}};
}
MetricPolicy policy(std::vector<MetricRequirement> requirements) {
    return {"demonstration", "1", std::move(requirements)};
}
const MetricValue& metric(const WindowMetricAssessment& result, MetricId id) {
    return result.cells.at(0).metrics.at(static_cast<std::size_t>(id));
}

void handCalculatedExample() {
    const auto input = candidate();
    const auto measured = MetricEvaluator{}.evaluate(input, 450);
    require(measured.status == AssessmentStatus::NotConfigured && !measured.policyId
        && measured.cells[0].checks.empty(), "Missing policy silently selected thresholds");
    const std::vector<double> expected{4, 2, 4. / 3., 5, 25, 400, 450, 50, 1};
    for (std::size_t index = 0; index < expected.size(); ++index) {
        const auto& value = measured.cells[0].metrics[index];
        require(value.id == static_cast<MetricId>(index) && value.value
            && std::abs(*value.value - expected[index]) < 1e-12, "Metric differs from hand-computed value");
        require(metricIdFromName(metricDefinition(value.id).name) == value.id, "Metric registry lookup mismatch");
    }
    require(!metric(measured, MetricId::OccupancyMae).value
        && metric(measured, MetricId::OccupancyMae).unavailableReason == "offline_reference_required",
        "Online evaluator fabricated utility error without GT");

    MetricEvaluator evaluator(policy({{MetricId::DistinctContributors, 3, {}},
        {MetricId::AgeAtEvaluationMs, {}, 500}, {MetricId::OccupancyMae, {}, 1}}));
    const auto assessed = evaluator.evaluate(input, 450);
    require(assessed.policyId == "demonstration" && assessed.policyVersion == "1", "Policy provenance lost");
    require(assessed.status == AssessmentStatus::Fail && assessed.cells[0].status == AssessmentStatus::Fail,
        "Violated available bound did not fail a complete candidate");
    const auto& checks = assessed.cells[0].checks;
    require(checks[0].status == AssessmentStatus::Fail && checks[0].reason == "below_minimum"
        && checks[0].observed == 2, "Support failure reason/value wrong");
    require(checks[1].status == AssessmentStatus::Pass && checks[1].observed == 450, "Age check incorrect");
    require(checks[2].status == AssessmentStatus::Unavailable && !checks[2].observed, "Unavailable metric skipped");

    MetricEvaluator equality(policy({{MetricId::DistinctContributors, 2, 2},
        {MetricId::WindowDurationMs, 400, 400}, {MetricId::MeasuredSampleFraction, 1, 1}}));
    require(equality.evaluate(input, 400).status == AssessmentStatus::Pass, "Bounds are not inclusive");
    MetricEvaluator unavailable(policy({{MetricId::OccupancyMae, {}, 1}}));
    require(unavailable.evaluate(input, 450).status == AssessmentStatus::Unavailable, "Missing GT silently approved");
    MetricEvaluator delayed(policy({{MetricId::AgeAtEvaluationMs, {}, 450}, {MetricId::PostWindowDelayMs, {}, 50}}));
    const auto late = delayed.evaluate(input, 451);
    require(late.status == AssessmentStatus::Fail && late.cells[0].checks[1].reason == "above_maximum",
        "Late evaluation confused with unchanged window duration");
    require(*metric(late, MetricId::WindowDurationMs).value == 400, "Late evaluation enlarged the window");
}

void coverageAndEmptyIntervals() {
    MetricEvaluator evaluator(policy({{MetricId::DistinctContributors, 1, {}},
        {MetricId::MeasuredSampleFraction, 0, 1}}));
    auto partialCoverage = candidate();
    partialCoverage.expectedSamples = 4;
    partialCoverage.missingSamples = 1;
    partialCoverage.coverage = WindowCoverage::Incomplete;
    const auto missing = evaluator.evaluate(partialCoverage, 450);
    require(missing.status == AssessmentStatus::Unavailable && missing.coverageStatus == AssessmentStatus::Unavailable,
        "Thresholds bypassed incomplete observation coverage");
    require(missing.cells[0].checks[0].status == AssessmentStatus::Pass
        && missing.cells[0].status == AssessmentStatus::Unavailable,
        "Individual support pass concealed unavailable overall assessment");
    require(metric(missing, MetricId::MeasuredSampleFraction).value == .75,
        "Missing observations counted as measured empty");
    partialCoverage.missingSamples = 0; partialCoverage.unavailableSamples = 1;
    require(evaluator.evaluate(partialCoverage, 450).status == AssessmentStatus::Unavailable,
        "Explicit unavailability ignored");

    auto empty = candidate(); empty.counts = counts(0, 0, 3); empty.cells.clear();
    require(evaluator.evaluate(empty, 400).status == AssessmentStatus::NoCandidates,
        "Sparse empty output implicitly approved unenumerated cells");
    empty.endMs = empty.closedAtMs = 50; empty.truncated = true;
    empty.measuredSamples = empty.expectedSamples = 0;
    empty.coverage = WindowCoverage::NoScheduledSamples; empty.counts = counts(0, 0, 0);
    const auto early = evaluator.evaluate(empty, 50);
    require(early.status == AssessmentStatus::Unavailable && early.coverageReason == "no_scheduled_samples",
        "Initialization-only window became a successful assessment");

    auto truncated = candidate(); truncated.endMs = truncated.closedAtMs = 350; truncated.truncated = true;
    MetricEvaluator minimumDuration(policy({{MetricId::WindowDurationMs, 400, {}}}));
    const auto shortWindow = minimumDuration.evaluate(truncated, 350);
    require(shortWindow.coverageStatus == AssessmentStatus::Pass && shortWindow.status == AssessmentStatus::Fail,
        "Complete truncated window bypassed minimum actual duration");
    auto rectangular = candidate(); rectangular.cells[0].cell.height = 4;
    MetricEvaluator squareRequired(policy({{MetricId::CellSideM, {}, 10}}));
    const auto unsupported = squareRequired.evaluate(rectangular, 400);
    require(unsupported.status == AssessmentStatus::Unavailable
        && metric(unsupported, MetricId::CellAreaM2).value == 20,
        "Rectangular support silently chose an arbitrary side metric");
}

void invalidInputs() {
    rejects([] { metricIdFromName("k_anonymity"); }, "Unsupported anonymity name silently mapped to support");
    rejects([] { metricDefinition(MetricId::Count); }, "Invalid metric enum accepted");
    rejects([] { MetricEvaluator{policy({})}; }, "Empty configured policy accepted");
    for (const auto& bounds : std::vector<MetricRequirement>{
        {MetricId::DistinctContributors, 3, 2}, {MetricId::DistinctContributors, 1.5, {}},
        {MetricId::CellSideM, -1, {}}, {MetricId::CellSideM, {}, std::numeric_limits<double>::infinity()},
        {MetricId::CellSideM, std::numeric_limits<double>::quiet_NaN(), {}},
        {MetricId::MeasuredSampleFraction, {}, 1.1}, {MetricId::WindowDurationMs, {}, {}},
        {MetricId::DistinctContributors, 9007199254740992., {}}})
        rejects([&] { MetricEvaluator{policy({bounds})}; }, "Invalid metric bound accepted");
    rejects([] { MetricEvaluator{policy({{MetricId::CellSideM, 1, {}}, {MetricId::CellSideM, {}, 2}})}; },
        "Duplicate metric requirements accepted");
    auto unnamed = policy({{MetricId::CellSideM, {}, 10}}); unnamed.version.clear();
    rejects([&] { MetricEvaluator{unnamed}; }, "Unversioned policy accepted");

    MetricEvaluator evaluator;
    rejects([&] { evaluator.evaluate(candidate(), 399); }, "Evaluation before closure accepted");
    auto malformed = candidate(); malformed.missingSamples = 1;
    rejects([&] { evaluator.evaluate(malformed, 400); }, "Inconsistent sample counts accepted");
    malformed = candidate(); malformed.coverage = WindowCoverage::Incomplete;
    rejects([&] { evaluator.evaluate(malformed, 400); }, "Inconsistent coverage metadata accepted");
    malformed = candidate(); malformed.cells[0].counts.distinctContributors = 5;
    rejects([&] { evaluator.evaluate(malformed, 400); }, "Impossible contributor counts accepted");
    malformed = candidate(); malformed.cells[0].cell.width = -1;
    rejects([&] { evaluator.evaluate(malformed, 400); }, "Invalid cell geometry accepted");
    malformed = candidate(); malformed.counts.distinctContributors = 3;
    rejects([&] { evaluator.evaluate(malformed, 400); }, "Impossible window-wide identity union accepted");
    malformed = candidate(); malformed.cells.clear();
    rejects([&] { evaluator.evaluate(malformed, 400); }, "Missing cell contributions accepted");
}

void independentCellChecks() {
    auto input = candidate();
    input.cells.push_back({{49, 2, 5, 0, 5, 5}, counts(3, 3, 3)});
    input.counts = counts(7, 3, 3);
    MetricEvaluator evaluator(policy({{MetricId::DistinctContributors, 3, {}}}));
    const auto result = evaluator.evaluate(input, 400);
    require(result.cells[0].status == AssessmentStatus::Fail && result.cells[1].status == AssessmentStatus::Pass,
        "Stream-wide union was incorrectly substituted for cell support");
    require(result.status == AssessmentStatus::Fail, "Failed cell lost in overall summary");
    MetricEvaluator another(policy({{MetricId::DistinctContributors, 1, {}}}));
    require(another.evaluate(input, 400).status == AssessmentStatus::Pass
        && evaluator.evaluate(input, 400).status == AssessmentStatus::Fail,
        "Separate policy instances shared mutable requirements");
}
}

int main() {
    try {
        handCalculatedExample(); coverageAndEmptyIntervals(); invalidInputs(); independentCellChecks();
        std::cout << "PASS: metric values/units, bounds, completeness, unavailable references, "
                     "sample/window/age semantics and independent cell assessments.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
