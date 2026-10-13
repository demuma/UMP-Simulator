#include "AggregationDiagnostics.hpp"
#include "Utilities.hpp"
#include <bsoncxx/builder/basic/array.hpp>
#include <bsoncxx/builder/basic/document.hpp>
#include <bsoncxx/json.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>

namespace {
using bsoncxx::builder::basic::kvp;
using bsoncxx::builder::basic::make_document;

bsoncxx::document::value countDocument(const ump::AggregateCounts& counts) {
    bsoncxx::builder::basic::array types;
    for (const auto& [type, count] : counts.typeObservationContributions)
        types.append(make_document(kvp("type", type), kvp("contributions", static_cast<std::int64_t>(count))));
    bsoncxx::builder::basic::document result;
    result.append(kvp("observation_contributions", static_cast<std::int64_t>(counts.observationContributions)),
        kvp("distinct_contributors", static_cast<std::int64_t>(counts.distinctContributors)),
        kvp("type_observation_contributions", types));
    if (counts.meanSampleOccupancy) result.append(kvp("mean_sample_occupancy", *counts.meanSampleOccupancy));
    else result.append(kvp("mean_sample_occupancy", bsoncxx::types::b_null{}));
    return result.extract();
}

void appendOptional(bsoncxx::builder::basic::document& document, const char* key, std::optional<double> value) {
    if (value) document.append(kvp(std::string(key), *value));
    else document.append(kvp(std::string(key), bsoncxx::types::b_null{}));
}

bsoncxx::document::value metricDocument(const std::vector<ump::MetricValue>& values) {
    bsoncxx::builder::basic::document metrics;
    for (const auto& metric : values) {
        const auto& definition = ump::metricDefinition(metric.id);
        bsoncxx::builder::basic::document value;
        value.append(kvp("unit", std::string(definition.unit)));
        appendOptional(value, "value", metric.value);
        if (!metric.value) value.append(kvp("reason", metric.unavailableReason));
        metrics.append(kvp(std::string(definition.name), value));
    }
    return metrics.extract();
}

bsoncxx::array::value checkArray(const std::vector<ump::MetricCheck>& checks) {
    bsoncxx::builder::basic::array results;
    for (const auto& check : checks) {
        const auto& definition = ump::metricDefinition(check.requirement.id);
        bsoncxx::builder::basic::document row;
        row.append(kvp("metric", std::string(definition.name)), kvp("unit", std::string(definition.unit)),
            kvp("status", std::string(ump::assessmentStatusName(check.status))), kvp("reason", check.reason));
        appendOptional(row, "min", check.requirement.min);
        appendOptional(row, "max", check.requirement.max);
        appendOptional(row, "observed", check.observed);
        results.append(row);
    }
    return results.extract();
}

bsoncxx::document::value assessmentDocument(const ump::WindowMetricAssessment& assessment) {
    bsoncxx::builder::basic::document row;
    row.append(kvp("kind", "configured_thresholds_only"), kvp("policy_mode", assessment.policyMode),
        kvp("evaluated_at_ms", assessment.evaluatedAtMs),
        kvp("status", std::string(ump::assessmentStatusName(assessment.status))),
        kvp("coverage_gate", make_document(
            kvp("status", std::string(ump::assessmentStatusName(assessment.coverageStatus))),
            kvp("reason", assessment.coverageReason))));
    if (assessment.policyId) row.append(kvp("policy_id", *assessment.policyId), kvp("policy_version", *assessment.policyVersion));
    else row.append(kvp("policy_id", bsoncxx::types::b_null{}), kvp("policy_version", bsoncxx::types::b_null{}));
    return row.extract();
}
}

AggregationDiagnosticsSink makeAggregationDiagnosticsSink(const std::string& directory,
    std::chrono::system_clock::time_point simulationOrigin) {
    if (directory.empty()) throw std::invalid_argument("Aggregation diagnostics_directory must not be empty");
    std::filesystem::create_directories(directory);
    const auto path = std::filesystem::path(directory) / ("candidates-" + generateUUID() + ".jsonl");
    if (std::filesystem::exists(path)) throw std::runtime_error("Aggregation diagnostic file already exists");
    auto file = std::make_shared<std::ofstream>(path);
    file->exceptions(std::ios::badbit | std::ios::failbit);
    std::cout << "Internal aggregation diagnostics: " << std::filesystem::absolute(path) << '\n';
    return [file, simulationOrigin](const ump::AggregationCandidate& candidate, const ump::WindowMetricAssessment& assessment) {
        if (assessment.cells.size() != candidate.cells.size())
            throw std::invalid_argument("Metric assessment does not match candidate cells");
        const auto& grid = candidate.grid;
        bsoncxx::builder::basic::array cells;
        for (std::size_t index = 0; index < candidate.cells.size(); ++index) {
            const auto& cell = candidate.cells[index];
            const auto& evaluated = assessment.cells[index];
            if (evaluated.cellId != cell.cell.id)
                throw std::invalid_argument("Metric assessment cell order differs from candidate");
            bsoncxx::builder::basic::document appliedPolicy;
            if (evaluated.effectivePolicyId) {
                bsoncxx::builder::basic::array sources;
                for (const auto& source : evaluated.policySources) sources.append(source);
                appliedPolicy.append(kvp("effective_id", *evaluated.effectivePolicyId),
                    kvp("sources", sources), kvp("feasible", evaluated.policyFeasible));
            }
            const auto& g = cell.cell;
            cells.append(make_document(kvp("cell_id", g.id), kvp("depth", g.depth),
                kvp("x", g.x), kvp("y", g.y), kvp("width", g.width), kvp("height", g.height),
                kvp("counts", countDocument(cell.counts)), kvp("policy", appliedPolicy),
                kvp("metrics", metricDocument(evaluated.metrics)),
                kvp("threshold_status", std::string(ump::assessmentStatusName(evaluated.status))),
                kvp("checks", checkArray(evaluated.checks))));
        }
        const char* coverage = candidate.coverage == ump::WindowCoverage::Complete ? "complete"
            : candidate.coverage == ump::WindowCoverage::Incomplete ? "incomplete" : "no_scheduled_samples";
        auto row = make_document(kvp("schema", "ump.fixed-candidate.v3"),
            kvp("data_role", "internal_research_candidate"),
            kvp("simulation_origin", bsoncxx::types::b_date{simulationOrigin}),
            kvp("run_id", candidate.runId), kvp("sensor_id", candidate.sensorId),
            kvp("application_id", candidate.applicationId),
            kvp("start_ms", candidate.startMs), kvp("end_ms", candidate.endMs),
            kvp("closed_at_ms", candidate.closedAtMs), kvp("truncated", candidate.truncated),
            kvp("expected_samples", static_cast<std::int64_t>(candidate.expectedSamples)),
            kvp("measured_samples", static_cast<std::int64_t>(candidate.measuredSamples)),
            kvp("unavailable_samples", static_cast<std::int64_t>(candidate.unavailableSamples)),
            kvp("missing_samples", static_cast<std::int64_t>(candidate.missingSamples)),
            kvp("coverage", std::string(coverage)),
            kvp("grid", make_document(kvp("x", grid.x), kvp("y", grid.y), kvp("width", grid.width),
                kvp("height", grid.height), kvp("leaf_depth", grid.leafDepth))),
            kvp("counts", countDocument(candidate.counts)),
            kvp("assessment", assessmentDocument(assessment)), kvp("cells", cells));
        *file << bsoncxx::to_json(row.view(), bsoncxx::ExtendedJsonMode::k_relaxed) << '\n';
        file->flush();
    };
}
