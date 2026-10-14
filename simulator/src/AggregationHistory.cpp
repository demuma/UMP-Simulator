#include "AggregationHistory.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <unordered_set>

namespace ump {
namespace {
void validateGrid(const GridCoverage& g) {
    if (!std::isfinite(g.x) || !std::isfinite(g.y) || !std::isfinite(g.width)
        || !std::isfinite(g.height) || g.width <= 0 || g.height != g.width
        || !std::isfinite(g.x + g.width) || !std::isfinite(g.y + g.height)
        || g.leafDepth < 1 || g.leafDepth > 14)
        throw std::invalid_argument("History requires finite square quadtree coverage and depth 1..14");
    const auto side = std::ldexp(g.width, -g.leafDepth);
    if (side <= 0 || g.x + side == g.x || g.y + side == g.y)
        throw std::invalid_argument("History leaf geometry is not numerically representable");
}
void validateCell(const GridCoverage& grid, const CellGeometry& cell) {
    const auto expected = historyCell(grid, cell.id, cell.depth);
    const auto close = [&](double a, double b) {
        const auto tolerance = std::min(std::ldexp(grid.width, -grid.leafDepth) * 1e-4,
            1e-6 * std::max({1.0, std::abs(a), std::abs(b)}));
        return std::isfinite(a) && std::abs(a - b) <= tolerance;
    };
    if (!close(cell.x, expected.x) || !close(cell.y, expected.y)
        || !close(cell.width, expected.width) || !close(cell.height, expected.height))
        throw std::invalid_argument("History cell geometry differs from its ID/depth");
}
std::size_t payloadBytes(const ObservationBatch& batch) {
    std::size_t total = 0;
    for (const auto& item : batch.observations) {
        for (const auto* value : {&item.contributorId, &item.type}) {
            if (value->size() > std::numeric_limits<std::size_t>::max() - total)
                throw std::length_error("History string-byte accounting overflow");
            total += value->size();
        }
    }
    return total;
}
}

CellGeometry historyCell(const GridCoverage& grid, int id, int depth) {
    validateGrid(grid);
    if (id < 0 || depth < 1 || depth > grid.leafDepth || (id >> (2 * depth)) != 3)
        throw std::invalid_argument("History requires a representable quadtree cell ID/depth");
    CellGeometry cell{id, depth, grid.x, grid.y, grid.width, grid.height};
    for (int level = 1; level <= depth; ++level) {
        const int quadrant = (id >> (2 * (depth - level))) & 3;
        cell.width /= 2; cell.height /= 2;
        cell.x += (quadrant & 1) * cell.width;
        cell.y += (quadrant >> 1) * cell.height;
    }
    return cell;
}

CellGeometry historyAncestor(const GridCoverage& grid, const CellGeometry& cell, int levels) {
    validateCell(grid, cell);
    if (levels < 0 || levels >= cell.depth)
        throw std::invalid_argument("History ancestor crosses the four-base-cell boundary");
    return historyCell(grid, cell.id >> (2 * levels), cell.depth - levels);
}

AggregationHistory::AggregationHistory(AggregationConfig settings, HistoryLimits bounds)
    : config(std::move(settings)), limits(bounds) {
    validateGrid(config.coverage);
    if (config.runId.empty() || config.sensorId.empty() || config.applicationId.empty()
        || config.capabilities != InputCapabilities::IdentityCellObservations)
        throw std::invalid_argument("History requires identified identity-bearing stream/application input");
    if (config.samplingPeriodMs <= 0 || config.windowMs <= 0
        || config.windowMs % config.samplingPeriodMs != 0 || limits.retentionMs < config.windowMs
        || limits.retentionMs % config.samplingPeriodMs != 0 || !limits.maxBins
        || !limits.maxObservations || !limits.maxIdentityBytes || !limits.maxBuckets)
        throw std::invalid_argument("History requires positive budgets and aligned retention covering the fixed window");
}

AggregationTime AggregationHistory::retainedFrom(AggregationTime nowMs) const {
    return nowMs > limits.retentionMs ? nowMs - limits.retentionMs : 0;
}

void AggregationHistory::validateAppend(const ObservationBatch& batch) const {
    if (batch.runId != config.runId || batch.sensorId != config.sensorId
        || !batch.sequence || batch.sequence <= lastSequence)
        throw std::invalid_argument("History batch has a wrong stream or duplicate/decreasing sequence");
    if (batch.observedAtMs <= 0 || batch.observedAtMs < watermarkMs
        || batch.observedAtMs % config.samplingPeriodMs != 0
        || (lastObservationMs && batch.observedAtMs <= *lastObservationMs))
        throw std::invalid_argument("History batch is late, duplicate or off cadence");
    if ((batch.status != ObservationStatus::Measured && batch.status != ObservationStatus::Unavailable)
        || (batch.status == ObservationStatus::Unavailable && !batch.observations.empty()))
        throw std::invalid_argument("History batch has inconsistent measurement status");
    // Preflight the post-expiry occupancy without evicting anything on a failed append.
    auto usedBins = bins.size(), observations = retainedObservations, bytes = retainedBytes;
    for (const auto& bin : bins) {
        if (bin.timeMs >= retainedFrom(batch.observedAtMs)) break;
        --usedBins; observations -= bin.observations.size(); bytes -= bin.identityBytes;
    }
    const auto incomingBytes = payloadBytes(batch);
    if (usedBins >= limits.maxBins || batch.observations.size() > limits.maxObservations - observations
        || incomingBytes > limits.maxIdentityBytes - bytes)
        throw std::length_error("History budget exceeded; no observations silently discarded");
    std::unordered_set<std::string> ids;
    for (const auto& observation : batch.observations) {
        if (observation.contributorId.empty() || observation.type.empty()
            || !ids.insert(observation.contributorId).second)
            throw std::invalid_argument("History requires nonempty, unique contributor identities and types per sample");
        if (observation.cell.depth != config.coverage.leafDepth)
            throw std::invalid_argument("History observations must use the declared finest depth");
        validateCell(config.coverage, observation.cell);
    }
}

void AggregationHistory::append(const ObservationBatch& batch) {
    validateAppend(batch);
    // Own the payload before advancing/pruning; retain no references to the caller's batch.
    Bin incoming{batch.observedAtMs, batch.status, batch.observations, payloadBytes(batch)};
    advance(batch.observedAtMs);
    bins.push_back(std::move(incoming));
    retainedObservations += batch.observations.size();
    retainedBytes += bins.back().identityBytes;
    lastSequence = batch.sequence;
    lastObservationMs = batch.observedAtMs;
}

void AggregationHistory::advance(AggregationTime nowMs) {
    if (nowMs < watermarkMs) throw std::invalid_argument("History clock moved backwards");
    if (nowMs == watermarkMs) return;
    watermarkMs = nowMs;
    for (auto it = buckets.begin(); it != buckets.end();) {
        if (nowMs > it->second.retainUntilMs) {
            it = buckets.erase(it); ++expiredBuckets;
        } else {
            it->second.state = nowMs >= it->second.endMs ? BucketState::Closed : BucketState::Collecting;
            ++it;
        }
    }
    while (!bins.empty() && bins.front().timeMs < retainedFrom(nowMs)) {
        retainedObservations -= bins.front().observations.size();
        retainedBytes -= bins.front().identityBytes;
        bins.pop_front();
    }
}

HistoryQuery AggregationHistory::query(const CellGeometry& cell, AggregationTime startMs,
    AggregationTime endMs) const {
    validateCell(config.coverage, cell);
    if (startMs < 0 || endMs <= startMs)
        throw std::invalid_argument("History queries require a nonempty nonnegative half-open interval");
    if (startMs < retainedFrom(watermarkMs)) return {HistoryQueryStatus::Evicted, std::nullopt};
    if (endMs > watermarkMs) return {HistoryQueryStatus::Future, std::nullopt};
    const auto before = [&](AggregationTime time) -> std::uint64_t {
        return time > 0 ? static_cast<std::uint64_t>((time - 1) / config.samplingPeriodMs) : 0;
    };
    AggregationCandidate result{config.runId, config.sensorId, config.applicationId, config.coverage,
        startMs, endMs, watermarkMs, false, before(endMs) - before(startMs), 0, 0, 0,
        WindowCoverage::NoScheduledSamples, {}, {}};
    std::unordered_set<std::string> contributors;
    const int shift = 2 * (config.coverage.leafDepth - cell.depth);
    for (const auto& bin : bins) {
        if (bin.timeMs < startMs) continue;
        if (bin.timeMs >= endMs) break;
        if (bin.status == ObservationStatus::Unavailable) { ++result.unavailableSamples; continue; }
        ++result.measuredSamples; // Empty/other-cell observations still establish coverage here.
        for (const auto& observation : bin.observations) {
            if ((observation.cell.id >> shift) != cell.id) continue;
            ++result.counts.observationContributions;
            ++result.counts.typeObservationContributions[observation.type];
            contributors.insert(observation.contributorId);
        }
    }
    result.missingSamples = result.expectedSamples - result.measuredSamples - result.unavailableSamples;
    result.counts.distinctContributors = contributors.size();
    if (result.measuredSamples)
        result.counts.meanSampleOccupancy = static_cast<double>(result.counts.observationContributions) / result.measuredSamples;
    result.coverage = !result.expectedSamples ? WindowCoverage::NoScheduledSamples
        : result.missingSamples || result.unavailableSamples ? WindowCoverage::Incomplete : WindowCoverage::Complete;
    result.cells.push_back({cell, result.counts}); // Explicit zero-support requested cells are meaningful.
    const auto status = result.coverage == WindowCoverage::Complete ? HistoryQueryStatus::Complete
        : result.coverage == WindowCoverage::Incomplete ? HistoryQueryStatus::Incomplete : HistoryQueryStatus::NoScheduledSamples;
    return {status, std::move(result)};
}

void AggregationHistory::openBucket(CandidateBucket record) {
    historyCell(config.coverage, record.key.cellId, record.key.depth);
    if (!record.key.generation || record.key.startMs < retainedFrom(watermarkMs)
        || record.key.startMs > watermarkMs || record.endMs <= record.key.startMs
        || record.maxEndMs < record.endMs || record.retainUntilMs < record.maxEndMs
        || record.retainUntilMs - record.key.startMs > limits.retentionMs
        || record.retainUntilMs < watermarkMs
        || (record.role != BucketRole::Active && record.role != BucketRole::Preemptive))
        throw std::invalid_argument("Bucket requires retained start, bounded extension/deadline and a valid role/generation");
    if (buckets.count(record.key)) throw std::invalid_argument("Duplicate logical bucket key");
    if (buckets.size() >= limits.maxBuckets) throw std::length_error("History bucket budget exceeded");
    record.state = watermarkMs >= record.endMs ? BucketState::Closed : BucketState::Collecting;
    buckets.emplace(record.key, record);
}

void AggregationHistory::extendBucket(const BucketKey& key, AggregationTime endMs) {
    auto& record = buckets.at(key);
    if (endMs <= record.endMs || endMs > record.maxEndMs)
        throw std::invalid_argument("Bucket extension must increase end within its original maximum");
    record.endMs = endMs;
    record.state = watermarkMs >= endMs ? BucketState::Closed : BucketState::Collecting;
}
bool AggregationHistory::discardBucket(const BucketKey& key) { return buckets.erase(key) != 0; }
std::optional<CandidateBucket> AggregationHistory::bucket(const BucketKey& key) const {
    const auto found = buckets.find(key);
    return found == buckets.end() ? std::nullopt : std::optional<CandidateBucket>{found->second};
}
HistoryQuery AggregationHistory::queryBucket(const BucketKey& key) const {
    const auto& record = buckets.at(key);
    return query(historyCell(config.coverage, key.cellId, key.depth), key.startMs, record.endMs);
}
HistoryDebugState AggregationHistory::debugState() const {
    return {watermarkMs, retainedFrom(watermarkMs), bins.size(), retainedObservations,
        retainedBytes, buckets.size(), expiredBuckets};
}
} // namespace ump
