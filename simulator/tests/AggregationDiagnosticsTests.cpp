#include "AggregationDiagnostics.hpp"
#include "CandidateMetrics.hpp"
#include "Utilities.hpp"
#include <bsoncxx/json.hpp>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ump;
void require(bool condition, const char* why) { if (!condition) throw std::runtime_error(why); }
template<class F> void rejects(F f, const char* why) {
    try { f(); } catch (const std::exception&) { return; }
    throw std::runtime_error(why);
}
struct TemporaryDirectory {
    std::filesystem::path path = std::filesystem::temp_directory_path() / ("ump-diagnostic-test-" + generateUUID());
    TemporaryDirectory() { std::filesystem::create_directory(path); }
    ~TemporaryDirectory() { std::error_code ignored; std::filesystem::remove_all(path, ignored); }
};
std::string text(bsoncxx::document::element value) {
    const auto string = value.get_string().value;
    return std::string(string.data(), string.size());
}
double number(bsoncxx::document::element value) {
    if (value.type() == bsoncxx::type::k_int32) return value.get_int32().value;
    if (value.type() == bsoncxx::type::k_int64) return static_cast<double>(value.get_int64().value);
    return value.get_double().value;
}
std::vector<bsoncxx::document::value> rows(const std::filesystem::path& directory, const char* prefix) {
    std::vector<std::filesystem::path> matches;
    for (const auto& file : std::filesystem::directory_iterator(directory))
        if (file.path().filename().string().rfind(prefix, 0) == 0) matches.push_back(file.path());
    require(matches.size() == 1, "Expected exactly one diagnostic file for the requested sink");
    std::ifstream input(matches.front());
    std::vector<bsoncxx::document::value> output;
    for (std::string line; std::getline(input, line); ) {
        require(!line.empty(), "Diagnostics contains an empty JSONL record");
        output.push_back(bsoncxx::from_json(line));
    }
    return output;
}
std::vector<bsoncxx::document::view> documents(bsoncxx::document::element array) {
    std::vector<bsoncxx::document::view> result;
    for (const auto& element : array.get_array().value) result.push_back(element.get_document().value);
    return result;
}
AggregationCandidate candidate() {
    AggregateCounts counts{12, 4, {{"Adult Pedestrian", 9}, {"Child Pedestrian", 3}}, 4.0};
    return {"diagnostic-run", "sensor-fixture", "application-fixture", {0,0,20,20,2},
        0, 400, 450, false, 3,3,0,0, WindowCoverage::Complete, counts,
        {{{48,2,0,0,5,5}, counts}}};
}
MetricEvaluator evaluator() {
    return MetricEvaluator(MetricPolicy{"threshold-policy", "version-2", {
        {MetricId::DistinctContributors, 5, {}},
        {MetricId::PostWindowDelayMs, {}, 100},
        {MetricId::OccupancyMae, {}, 1}}});
}
void assertCommon(bsoncxx::document::view row, const AggregationCandidate& c) {
    require(text(row["run_id"]) == c.runId && text(row["sensor_id"]) == c.sensorId
        && text(row["application_id"]) == c.applicationId, "Diagnostic stream identity changed");
    require(number(row["start_ms"]) == 0 && number(row["end_ms"]) == 400
        && number(row["closed_at_ms"]) == 450, "Diagnostic logical interval changed");
    require(row["simulation_origin"].get_date().value.count() == 123,
        "Simulation origin lost its BSON date precision");
    require(text(row["coverage"]) == "complete" && number(row["measured_samples"]) == 3,
        "Observed coverage was changed by serialization");
    const auto counts = row["counts"].get_document().value;
    require(number(counts["observation_contributions"]) == 12
        && number(counts["distinct_contributors"]) == 4 && number(counts["mean_sample_occupancy"]) == 4,
        "Serialized aggregate differs from hand-computed support");
    const auto types = documents(counts["type_observation_contributions"]);
    require(types.size() == 2 && text(types[0]["type"]) == "Adult Pedestrian"
        && number(types[0]["contributions"]) == 9 && text(types[1]["type"]) == "Child Pedestrian"
        && number(types[1]["contributions"]) == 3, "Type support or canonical ordering changed");
}
void candidateArtifactAndSynchronousVisibility() {
    TemporaryDirectory temporary;
    auto sink = makeAggregationDiagnosticsSink(temporary.path.string(),
        std::chrono::system_clock::time_point{std::chrono::milliseconds{123}});
    auto c = candidate();
    auto assessment = evaluator().evaluate(c, c.closedAtMs);
    sink(c, assessment);
    // Read with the sink still alive: default full diagnostics exposes each completed line.
    auto output = rows(temporary.path, "candidates-");
    require(output.size() == 1, "Completed diagnostic line was not readable before sink destruction");
    const auto row = output[0].view();
    assertCommon(row, c);
    require(text(row["schema"]) == "ump.fixed-candidate.v3"
        && text(row["data_role"]) == "internal_research_candidate", "Candidate schema contract changed");
    const auto assessed = row["assessment"].get_document().value;
    require(text(assessed["kind"]) == "configured_thresholds_only"
        && text(assessed["policy_id"]) == "threshold-policy"
        && text(assessed["policy_version"]) == "version-2" && text(assessed["status"]) == "fail",
        "Threshold provenance/status was changed or overstated");
    const auto cells = documents(row["cells"]);
    require(cells.size() == 1 && number(cells[0]["cell_id"]) == 48
        && number(cells[0]["width"]) == 5 && text(cells[0]["threshold_status"]) == "fail",
        "Cell geometry/status changed");
    require(!cells[0]["decision"] && !cells[0]["semantic"], "Candidate fabricated selection or semantic information");
    const auto checks = documents(cells[0]["checks"]);
    require(checks.size() == 3 && text(checks[0]["status"]) == "fail"
        && text(checks[0]["reason"]) == "below_minimum" && number(checks[0]["min"]) == 5
        && checks[0]["max"].type() == bsoncxx::type::k_null && number(checks[0]["observed"]) == 4,
        "Failed bound did not preserve the exact configured and observed values");
    require(text(checks[1]["status"]) == "pass" && number(checks[1]["observed"]) == 50
        && text(checks[2]["status"]) == "unavailable"
        && checks[2]["observed"].type() == bsoncxx::type::k_null,
        "Available and unavailable checks became indistinguishable");
    const auto metrics = cells[0]["metrics"].get_document().value;
    require(text(metrics["occupancy_mae"].get_document().value["reason"]) == "offline_reference_required"
        && !metrics["semantic_max_loss"], "Missing-reference or disabled semantic metrics changed");
    auto empty = c; empty.cells.clear(); empty.counts = {}; empty.truncated = true;
    sink(empty, evaluator().evaluate(empty, empty.closedAtMs));
    output = rows(temporary.path, "candidates-");
    require(output.size() == 2 && documents(output[1].view()["cells"]).empty()
        && output[1].view()["truncated"].get_bool().value
        && text(output[1].view()["assessment"].get_document().value["status"]) == "no_candidates",
        "Empty truncated retirement was dropped or turned into a passing candidate");
}
void spatialArtifact() {
    TemporaryDirectory temporary;
    auto sink = makeSpatialDiagnosticsSink(temporary.path.string(),
        std::chrono::system_clock::time_point{std::chrono::milliseconds{123}});
    auto c = candidate();
    auto assessment = evaluator().evaluate(c, c.closedAtMs);
    assessment.cells[0].effectivePolicyId = "regional-effective";
    assessment.cells[0].policySources = {"root", "crossing"};
    assessment.cells[0].policyFeasible = false;
    assessment.cells[0].semantic = SemanticRepresentation{"road-user-fixture", "3", {{"pedestrian",12,4}},4,.5,.5};
    SpatialSelection selection{c,assessment,c,assessment,{}, {},1};
    selection.decisions.push_back({48,false,"policy_limit",{49,50},"suppressed"});
    selection.attempts.push_back({c.cells[0],assessment.cells[0]});
    selection.coordinationCell = c.cells[0].cell;
    selection.strategy = "semantic_first"; selection.completionReason = "hard_deadline";
    selection.suppressedCells = 1; selection.temporalExtensions = 2;
    selection.temporalDecisions.push_back({TemporalAction::ExtendWindow,0,400,450,AssessmentStatus::Fail});
    selection.semanticPriority = SemanticPrioritySelection{1,std::nullopt,3,true,"spatial_first","policy_satisfied",false};
    selection.publicationState = "retired_without_release"; selection.releaseId = "fixture-retirement";
    sink(selection);
    const auto output = rows(temporary.path, "selection-");
    require(output.size() == 1, "Spatial sink failed synchronous record visibility");
    const auto row = output[0].view(); assertCommon(row,c);
    require(text(row["schema"]) == "ump.spatial-selection.v1"
        && text(row["data_role"]) == "internal_spatial_selection", "Spatial schema contract changed");
    const auto cells = documents(row["cells"]), source = documents(row["source_cells"]), attempts = documents(row["attempts"]);
    require(cells.size() == 1 && source.size() == 1 && attempts.size() == 1,
        "Selected/source/attempt records were omitted");
    const auto decision = cells[0]["decision"].get_document().value;
    require(text(decision["state"]) == "suppressed" && text(decision["reason"]) == "policy_limit"
        && text(decision["transition"]) == "suppressed", "Selection decision changed");
    std::vector<int> triggers;
    for (const auto value : decision["trigger_cells"].get_array().value) triggers.push_back(value.get_int32().value);
    require(triggers == std::vector<int>({49,50}) && !source[0]["decision"] && !attempts[0]["decision"],
        "Decision annotations leaked into source/attempt cells or lost triggers");
    const auto policy = cells[0]["policy"].get_document().value;
    require(text(policy["effective_id"]) == "regional-effective" && !policy["feasible"].get_bool().value,
        "Regional policy provenance or contradictory-bound status was lost");
    const auto semantic = cells[0]["semantic"].get_document().value;
    const auto categories = documents(semantic["categories"]);
    require(text(semantic["schema"]) == "ump.semantic-release.v1" && text(semantic["taxonomy_id"]) == "road-user-fixture"
        && number(semantic["semantic_max_loss"]) == .5 && categories.size() == 1
        && text(categories[0]["category_id"]) == "pedestrian" && number(categories[0]["distinct_contributors"]) == 4,
        "Semantic representation contract changed");
    const auto priority = row["semantic_priority"].get_document().value;
    require(text(priority["secondary_strategy"]) == "spatial_first"
        && priority["actual_max_loss"].type() == bsoncxx::type::k_null
        && priority["terminal_fallback"].get_bool().value && number(priority["attempted_ceilings"]) == 3,
        "Semantic preference diagnostics fabricated released loss");
    const auto temporal = documents(row["temporal_decisions"]);
    require(temporal.size() == 1 && text(temporal[0]["action"]) == "extend_window"
        && text(temporal[0]["status"]) == "fail", "Temporal action history changed");
    const auto spatial = row["spatial_selection"].get_document().value;
    require(text(spatial["publication"]) == "retired_without_release" && text(spatial["release_id"]) == "fixture-retirement"
        && number(spatial["suppressed_cells"]) == 1 && number(row["coordination_cell"].get_document().value["cell_id"]) == 48,
        "Private no-output retirement lost its scope/state");
    // Exercise the selected branch independently of the suppressed artifact.
    selection.decisions[0].selected = true;
    selection.decisions[0].transition = "coarsened";
    selection.selectedCells = 1; selection.suppressedCells = 0;
    selection.publicationState = "committed";
    sink(selection);
    const auto second = rows(temporary.path,"selection-");
    require(second.size() == 2 && text(documents(second[1].view()["cells"])[0]["decision"].get_document().value["state"]) == "selected",
        "Selected diagnostic branch was lost");
}
void invalidInputDoesNotWriteSuccessfulRows() {
    TemporaryDirectory temporary;
    rejects([] { makeAggregationDiagnosticsSink("", {}); }, "Empty diagnostic directory was accepted");
    const auto notDirectory = temporary.path / "regular-file";
    { std::ofstream file(notDirectory); file << "fixture"; }
    rejects([&] { makeSpatialDiagnosticsSink(notDirectory.string(), {}); }, "Non-directory diagnostic path was accepted");
    auto sink = makeAggregationDiagnosticsSink(temporary.path.string(), {});
    auto c = candidate(); auto assessed = evaluator().evaluate(c,c.closedAtMs);
    auto shortAssessment = assessed; shortAssessment.cells.clear();
    rejects([&] { sink(c,shortAssessment); }, "Mismatched cell/assessment lengths were accepted");
    auto wrongOrder = assessed; wrongOrder.cells[0].cellId = 49;
    rejects([&] { sink(c,wrongOrder); }, "Mismatched cell/assessment IDs were accepted");
    require(rows(temporary.path,"candidates-").empty(), "Invalid assessment produced a successful JSONL record");
    sink(c,assessed);
    require(rows(temporary.path,"candidates-").size() == 1, "Validation failure corrupted a subsequent valid write");
    auto spatialSink = makeSpatialDiagnosticsSink(temporary.path.string(), {});
    SpatialSelection valid{c,assessed,c,assessed,{{48,false,"fixture",{},"suppressed"}},
        {{c.cells[0],assessed.cells[0]}},1};
    auto invalid = valid; invalid.decisions.clear();
    rejects([&] { spatialSink(invalid); }, "Spatial decision/cell length mismatch was accepted");
    invalid = valid; invalid.finestAssessment.cells.clear();
    rejects([&] { spatialSink(invalid); }, "Spatial source assessment length mismatch was accepted");
    invalid = valid; invalid.finestAssessment.cells[0].cellId = 49;
    rejects([&] { spatialSink(invalid); }, "Spatial source assessment ID mismatch was accepted");
    invalid = valid; invalid.attempts[0].assessment.cellId = 49;
    rejects([&] { spatialSink(invalid); }, "Spatial attempt assessment ID mismatch was accepted");
    require(rows(temporary.path,"selection-").empty(), "Malformed spatial arrays produced a successful JSONL record");
    spatialSink(valid);
    require(rows(temporary.path,"selection-").size() == 1, "Rejected spatial data corrupted a subsequent valid write");
}
}
int main() {
    try {
        candidateArtifactAndSynchronousVisibility(); spatialArtifact(); invalidInputDoesNotWriteSuccessfulRows();
        std::cout << "Aggregation diagnostics artifact, synchronous visibility and rejection tests passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
