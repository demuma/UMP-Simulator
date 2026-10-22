#pragma once

#include "AggregationInput.hpp"
#include <deque>
#include <tuple>

namespace ump {

// Data-tree geometry only: four depth-1 base cells, no representable depth-0 data root.
CellGeometry historyCell(const GridCoverage& grid, int id, int depth);
CellGeometry historyAncestor(const GridCoverage& grid, const CellGeometry& cell, int levels);

enum class HistoryQueryStatus { Complete, Incomplete, NoScheduledSamples, Future, Evicted };
struct HistoryQuery {
    HistoryQueryStatus status;
    std::optional<AggregationCandidate> candidate;
};

// Geometry needed for refinement, without candidate statistics or public output.
// A present empty vector is retained empty/no-sample history; nullopt means that
// the interval is future or evicted. Incomplete history can still contain cells.
struct HistoryOccupiedLeavesQuery {
    HistoryQueryStatus status;
    std::optional<std::vector<CellGeometry>> cells;
};

enum class BucketRole { Active, Preemptive };
enum class BucketState { Collecting, Closed }; // Observation progress, not publication approval.
struct BucketKey {
    int cellId, depth;
    AggregationTime startMs;
    std::uint64_t generation;
    bool operator<(const BucketKey& other) const {
        return std::tie(cellId, depth, startMs, generation)
            < std::tie(other.cellId, other.depth, other.startMs, other.generation);
    }
};
struct CandidateBucket {
    BucketKey key;
    AggregationTime endMs, maxEndMs, retainUntilMs;
    BucketRole role;
    BucketState state = BucketState::Collecting;
};
struct HistoryDebugState {
    AggregationTime watermarkMs, retainedFromMs;
    std::size_t bins, observations, identityBytes, buckets;
    std::uint64_t expiredBuckets;
};

// Synchronous, private, bounded sample history. Candidate queries never consume data.
// All returned candidates contain statistics only; owned contributor IDs stay internal.
class AggregationHistory {
public:
    AggregationHistory(AggregationConfig config, HistoryLimits limits);
    void validateAppend(const ObservationBatch& batch) const; // No mutation, including on rejection.
    void append(const ObservationBatch& batch);
    void advance(AggregationTime nowMs);
    HistoryQuery query(const CellGeometry& cell, AggregationTime startMs, AggregationTime endMs) const;
    // Reconstruct the finest occupied cut and exact whole-domain identity union.
    HistoryQuery queryFinest(AggregationTime startMs, AggregationTime endMs,
        std::optional<CellGeometry> domain = std::nullopt) const;
    // Whole-domain occupied leaves in canonical ID order. Preserve queryFinest's
    // coverage and semantic identity validation, without per-leaf accumulation.
    HistoryOccupiedLeavesQuery queryOccupiedLeaves(AggregationTime startMs, AggregationTime endMs) const;
    void openBucket(CandidateBucket bucket);
    void extendBucket(const BucketKey& key, AggregationTime endMs);
    bool discardBucket(const BucketKey& key);
    std::optional<CandidateBucket> bucket(const BucketKey& key) const;
    HistoryQuery queryBucket(const BucketKey& key) const;
    HistoryDebugState debugState() const;

private:
    struct Bin {
        AggregationTime timeMs;
        ObservationStatus status;
        // Owned payload sorted by finest cell ID; descendant rows are contiguous.
        std::vector<CellObservation> observations;
        std::size_t identityBytes;
    };
    AggregationTime retainedFrom(AggregationTime nowMs) const;
    AggregationConfig config;
    HistoryLimits limits;
    std::deque<Bin> bins;
    std::map<BucketKey, CandidateBucket> buckets;
    AggregationTime watermarkMs = 0;
    std::optional<AggregationTime> lastObservationMs;
    std::uint64_t lastSequence = 0, expiredBuckets = 0;
    std::size_t retainedObservations = 0, retainedBytes = 0;
};
} // namespace ump
