#pragma once

#include "AggregationInput.hpp"
#include "AggregationHistory.hpp"
#include <memory>
#include <functional>
#include <unordered_map>
#include <unordered_set>

// Sensor-independent fixed-window output with optional bounded private reconstruction.
// All calls and the output sink are synchronous; history is separate from renderer transport.
class AggregationManager {
public:
    using Sink = std::function<void(const ump::AggregationCandidate&)>;
    using ProgressSink = std::function<void(ump::AggregationTime, bool finishing)>;
    AggregationManager(ump::AggregationConfig config, Sink sink);
    // Runs after the history watermark advances; callback may query but never mutate this manager.
    void setProgressSink(ProgressSink output) { progressSink = std::move(output); }

    void ingest(const ump::ObservationBatch& batch);
    void advance(ump::AggregationTime nowMs);
    void finish(ump::AggregationTime endMs);
    ump::AggregationDebugState debugState() const;
    const ump::AggregationHistory* history() const { return retainedHistory.get(); }
    void openBucket(ump::CandidateBucket bucket);
    void extendBucket(const ump::BucketKey& key, ump::AggregationTime endMs);
    bool discardBucket(const ump::BucketKey& key);

private:
    struct CellAccumulator {
        ump::CellGeometry geometry;
        ump::AggregateCounts counts;
        std::unordered_set<std::string> contributors;
    };

    void validate(const ump::ObservationBatch& batch) const;
    void advanceTo(ump::AggregationTime nowMs, bool notifyProgress);
    void closeWindow(ump::AggregationTime endMs, ump::AggregationTime closedAtMs, bool truncated);

    ump::AggregationConfig config;
    Sink sink;
    ProgressSink progressSink;
    std::unique_ptr<ump::AggregationHistory> retainedHistory;
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
