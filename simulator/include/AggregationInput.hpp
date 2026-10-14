#pragma once

#include <cstdint>
#include <cstddef>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace ump {

// Milliseconds relative to this run's simulation origin, never wall-clock elapsed time.
using AggregationTime = std::int64_t;

struct CellGeometry {
    int id;
    int depth;
    double x, y, width, height;
};

struct GridCoverage {
    double x, y, width, height;
    int leafDepth;
};

enum class InputCapabilities { IdentityCellObservations, CountsOnly };
enum class ObservationStatus { Measured, Unavailable };

struct CellObservation {
    std::string contributorId; // Internal only; never copied into candidate output.
    std::string type;
    CellGeometry cell;
};

struct ObservationBatch {
    std::string runId;
    std::string sensorId;
    std::uint64_t sequence;
    AggregationTime observedAtMs;
    ObservationStatus status = ObservationStatus::Measured;
    std::vector<CellObservation> observations;
};

// Explicit private-history resource budgets; omitted configuration retains fixed-window-only mode.
struct HistoryLimits {
    AggregationTime retentionMs;
    std::size_t maxBins, maxObservations, maxIdentityBytes, maxBuckets;
};

struct AggregationConfig {
    std::string runId;
    std::string sensorId;
    std::string applicationId;
    GridCoverage coverage;
    AggregationTime samplingPeriodMs;
    AggregationTime windowMs;
    std::uint64_t maxObservationsPerWindow = 1000000;
    InputCapabilities capabilities = InputCapabilities::IdentityCellObservations;
    std::optional<HistoryLimits> history = std::nullopt;
};

struct AggregateCounts {
    std::uint64_t observationContributions = 0;
    std::uint64_t distinctContributors = 0;
    std::map<std::string, std::uint64_t> typeObservationContributions;
    std::optional<double> meanSampleOccupancy;
};

struct AggregatedCell {
    CellGeometry cell;
    AggregateCounts counts;
};

enum class WindowCoverage { Complete, Incomplete, NoScheduledSamples };

// An internal research candidate, not a privacy-approved publication.
struct AggregationCandidate {
    std::string runId, sensorId, applicationId;
    GridCoverage grid;
    AggregationTime startMs, endMs, closedAtMs;
    bool truncated;
    std::uint64_t expectedSamples, measuredSamples, unavailableSamples, missingSamples;
    WindowCoverage coverage;
    AggregateCounts counts;
    std::vector<AggregatedCell> cells; // Sorted by cell ID; unlisted covered cells are empty only at measured samples.
};

struct AggregationDebugState {
    AggregationTime windowStartMs, windowEndMs;
    std::uint64_t measuredSamples, observationContributions;
    std::size_t retainedCells, retainedIdentityMemberships;
    bool finished;
};

} // namespace ump
