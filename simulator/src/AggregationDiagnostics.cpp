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
}

AggregationManager::Sink makeAggregationDiagnosticsSink(const std::string& directory,
    std::chrono::system_clock::time_point simulationOrigin) {
    if (directory.empty()) throw std::invalid_argument("Aggregation diagnostics_directory must not be empty");
    std::filesystem::create_directories(directory);
    const auto path = std::filesystem::path(directory) / ("candidates-" + generateUUID() + ".jsonl");
    if (std::filesystem::exists(path)) throw std::runtime_error("Aggregation diagnostic file already exists");
    auto file = std::make_shared<std::ofstream>(path);
    file->exceptions(std::ios::badbit | std::ios::failbit);
    std::cout << "Internal aggregation diagnostics: " << std::filesystem::absolute(path) << '\n';
    return [file, simulationOrigin](const ump::AggregationCandidate& candidate) {
        const auto& grid = candidate.grid;
        bsoncxx::builder::basic::array cells;
        for (const auto& cell : candidate.cells) {
            const auto& g = cell.cell;
            cells.append(make_document(kvp("cell_id", g.id), kvp("depth", g.depth),
                kvp("x", g.x), kvp("y", g.y), kvp("width", g.width), kvp("height", g.height),
                kvp("counts", countDocument(cell.counts))));
        }
        const char* coverage = candidate.coverage == ump::WindowCoverage::Complete ? "complete"
            : candidate.coverage == ump::WindowCoverage::Incomplete ? "incomplete" : "no_scheduled_samples";
        auto row = make_document(kvp("schema", "ump.fixed-candidate.v1"),
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
            kvp("counts", countDocument(candidate.counts)), kvp("cells", cells));
        *file << bsoncxx::to_json(row.view(), bsoncxx::ExtendedJsonMode::k_relaxed) << '\n';
        file->flush();
    };
}
