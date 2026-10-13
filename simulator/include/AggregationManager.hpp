#pragma once

#include "AggregationInput.hpp"
#include <functional>
#include <unordered_map>
#include <unordered_set>

// Sensor-independent fixed-window core. All calls and its output sink are synchronous.
class AggregationManager {
public:
    using Sink = std::function<void(const ump::AggregationCandidate&)>;
    AggregationManager(ump::AggregationConfig config, Sink sink);

    void ingest(const ump::ObservationBatch& batch);
    void advance(ump::AggregationTime nowMs);
    void finish(ump::AggregationTime endMs);
    ump::AggregationDebugState debugState() const;

private:
    struct CellAccumulator {
        ump::CellGeometry geometry;
        ump::AggregateCounts counts;
        std::unordered_set<std::string> contributors;
    };

    void validate(const ump::ObservationBatch& batch) const;
    void closeWindow(ump::AggregationTime endMs, ump::AggregationTime closedAtMs, bool truncated);

    ump::AggregationConfig config;
    Sink sink;
    ump::AggregationTime windowStartMs = 0;
    ump::AggregationTime watermarkMs = 0;
    std::optional<ump::AggregationTime> lastObservationMs;
    std::uint64_t lastSequence = 0;
    std::uint64_t measuredSamples = 0, unavailableSamples = 0;
    ump::AggregateCounts counts;
    std::unordered_set<std::string> contributors;
    std::unordered_map<int, CellAccumulator> cells;
    bool finished = false;
};
