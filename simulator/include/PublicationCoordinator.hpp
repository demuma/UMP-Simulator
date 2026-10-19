#pragma once

#include "SpatialSelection.hpp"
#include "CellWindowLedger.hpp"
#include <functional>
#include <memory>

namespace ump {

struct PublicationLimits {
    std::size_t maxCells = 4096;
    std::size_t maxTypeEntries = 65536;
    std::size_t maxTypeBytes = 1048576;
    std::size_t maxCoordinationNodes = 16384;
};

struct ReleasedCell {
    AggregatedCell aggregate;
    std::string effectivePolicyId;
};

// Recipient payload: only approved cells. No suppressed counts, global totals, private
// identities, failed alternatives or debug provenance from which to reconstruct them.
struct ReleaseSnapshot {
    std::string releaseId, runId, sensorId, applicationId;
    std::string model = "private_final_snapshot";
    std::string policyId, policyVersion;
    AggregationTime startMs, endMs, sealedAtMs;
    std::vector<ReleasedCell> cells;
    std::optional<CellGeometry> coordinationCell = std::nullopt;
};

enum class SinkResult { Acknowledged, Retry };
struct PublicationState {
    AggregationTime retiredThroughMs;
    std::optional<AggregationTime> reservedStartMs, reservedEndMs;
    std::size_t selectedCells, suppressedCells;
};

// Default coordination covers a whole-grid interval; cell-local mode retires a scoped
// quadtree footprint on its own clock. Variable intervals require
// an explicit maximum; the default preserves fixed-window validation.
// All support stays private until sealing. One pending immutable output bounds memory;
// competing seals are rejected, not queued. Acknowledgement retires the entire interval.
// This in-memory core must not be restarted with the same run ID without durable recovery.
class PublicationCoordinator {
public:
    using Sink = std::function<SinkResult(const ReleaseSnapshot&)>;
    PublicationCoordinator(AggregationConfig config, MetricEvaluator evaluator,
        PublicationLimits limits = {}, std::optional<AggregationTime> maximumWindowMs = std::nullopt,
        bool cellLocal = false);
    PublicationCoordinator(const PublicationCoordinator&) = delete;
    PublicationCoordinator& operator=(const PublicationCoordinator&) = delete;

    std::shared_ptr<const ReleaseSnapshot> seal(const SpatialSelection& selection, AggregationTime nowMs);
    // Sink must atomically acknowledge the whole snapshot and deduplicate by releaseId.
    // Retry/exception preserves the exact snapshot and reservation. A late policy failure
    // also preserves them: ambiguous earlier disclosure cannot safely be rolled back.
    bool deliver(AggregationTime nowMs, const Sink& sink);
    std::shared_ptr<const ReleaseSnapshot> pendingRelease() const;
    PublicationState state() const;

private:
    struct Pending {
        AggregationCandidate candidate; // Private, bounded evidence for fresh deadline checks.
        std::vector<std::size_t> selectedIndices;
        std::shared_ptr<const ReleaseSnapshot> release;
        std::size_t suppressedCells;
        std::optional<CellWindowLedger> retiredLedgerAfterAck;
    };
    AggregationConfig config;
    MetricEvaluator evaluator;
    PublicationLimits limits;
    std::optional<AggregationTime> maximumWindowMs;
    bool cellLocal;
    std::optional<CellWindowLedger> retiredLedger;
    std::optional<Pending> pending;
    AggregationTime retiredThroughMs = 0, lastDeliveryMs = 0;
    bool delivering = false, finished = false;
};
} // namespace ump
