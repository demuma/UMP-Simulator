#include "AggregationManager.hpp"
#include "SemanticTaxonomy.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace {
bool sameGeometry(const ump::CellGeometry& a, const ump::CellGeometry& b) {
    return a.id == b.id && a.depth == b.depth && a.x == b.x && a.y == b.y
        && a.width == b.width && a.height == b.height;
}

bool validRectangle(double x, double y, double width, double height) {
    return std::isfinite(x) && std::isfinite(y) && std::isfinite(width)
        && std::isfinite(height) && width > 0 && height > 0
        && std::isfinite(x + width) && std::isfinite(y + height);
}

void finalizeCounts(ump::AggregateCounts& counts, std::size_t distinct, std::uint64_t samples) {
    counts.distinctContributors = distinct;
    if (samples) counts.meanSampleOccupancy = static_cast<double>(counts.observationContributions) / samples;
}
}

AggregationManager::AggregationManager(ump::AggregationConfig settings, Sink output)
    : config(std::move(settings)), sink(std::move(output)) {
    const auto& g = config.coverage;
    if (config.runId.empty() || config.sensorId.empty() || config.applicationId.empty() || !sink)
        throw std::invalid_argument("Aggregation needs run/sensor/application IDs and an output sink");
    if (config.samplingPeriodMs <= 0 || config.windowMs <= 0
        || config.windowMs % config.samplingPeriodMs != 0 || !config.maxObservationsPerWindow)
        throw std::invalid_argument("Aggregation needs positive aligned periods/windows and an observation budget");
    if (!validRectangle(g.x, g.y, g.width, g.height) || g.leafDepth < 1)
        throw std::invalid_argument("Invalid aggregation grid coverage");
    if (config.capabilities != ump::InputCapabilities::IdentityCellObservations)
        throw std::invalid_argument("Distinct contributors require identity-bearing input");
    if (config.semanticTaxonomy && !config.history)
        throw std::invalid_argument("Semantic aggregation requires bounded private history");
    if (config.history) retainedHistory = std::make_unique<ump::AggregationHistory>(config, *config.history);
}

void AggregationManager::validate(const ump::ObservationBatch& batch) const {
    if (finished) throw std::logic_error("Aggregation stream already finished");
    if (batch.runId != config.runId || batch.sensorId != config.sensorId)
        throw std::invalid_argument("Aggregation batch belongs to a different stream");
    if (!batch.sequence || batch.sequence <= lastSequence)
        throw std::invalid_argument("Duplicate or decreasing aggregation batch sequence");
    if (batch.observedAtMs <= 0 || batch.observedAtMs < watermarkMs
        || (lastObservationMs && batch.observedAtMs <= *lastObservationMs)
        || batch.observedAtMs % config.samplingPeriodMs != 0)
        throw std::invalid_argument("Late, duplicate or off-cadence aggregation observation");
    if (batch.status != ump::ObservationStatus::Measured && batch.status != ump::ObservationStatus::Unavailable)
        throw std::invalid_argument("Unknown aggregation observation status");
    if (batch.status != ump::ObservationStatus::Measured && !batch.observations.empty())
        throw std::invalid_argument("Unavailable batch must not contain observations");
    const bool sameWindow = batch.observedAtMs - batch.observedAtMs % config.windowMs == windowStartMs;
    const auto retained = sameWindow ? counts.observationContributions : 0;
    if (batch.observations.size() > config.maxObservationsPerWindow - retained)
        throw std::length_error("Aggregation observation budget exceeded; no candidate approved or data dropped");

    std::unordered_set<std::string> batchIds;
    std::unordered_map<int, ump::CellGeometry> batchCells;
    const auto& g = config.coverage;
    for (const auto& observation : batch.observations) {
        const auto& c = observation.cell;
        if (observation.contributorId.empty() || observation.type.empty()
            || !batchIds.insert(observation.contributorId).second)
            throw std::invalid_argument("Empty or duplicate contributor identity/type in aggregation batch");
        if (config.semanticTaxonomy) (void)config.semanticTaxonomy->leafForType(observation.type);
        if (c.id < 0 || c.depth != g.leafDepth || !validRectangle(c.x, c.y, c.width, c.height)
            || c.x < g.x || c.y < g.y || c.x + c.width > g.x + g.width
            || c.y + c.height > g.y + g.height)
            throw std::invalid_argument("Observation cell is outside declared fixed-depth coverage");
        const auto inserted = batchCells.emplace(c.id, c);
        if (!inserted.second && !sameGeometry(inserted.first->second, c))
            throw std::invalid_argument("Inconsistent cell geometry inside aggregation batch");
        const auto existing = cells.find(c.id);
        if (sameWindow && existing != cells.end() && !sameGeometry(existing->second.geometry, c))
            throw std::invalid_argument("Cell geometry changed inside aggregation window");
    }
    if (batch.observedAtMs > std::numeric_limits<ump::AggregationTime>::max() - config.windowMs)
        throw std::overflow_error("Aggregation clock exceeds supported range");
}

void AggregationManager::ingest(const ump::ObservationBatch& batch) {
    validate(batch); // Invalid input must not mutate active state or emit output.
    // History validates its geometry/budgets once, before fixed-window emission. Its
    // half-open queries exclude the new endpoint sample while an old window closes.
    if (retainedHistory) retainedHistory->append(batch);
    advance(batch.observedAtMs);
    lastSequence = batch.sequence;
    lastObservationMs = batch.observedAtMs;
    if (batch.status == ump::ObservationStatus::Unavailable) {
        ++unavailableSamples;
        return;
    }
    ++measuredSamples;
    for (const auto& observation : batch.observations) {
        auto [entry, inserted] = cells.try_emplace(observation.cell.id,
            CellAccumulator{observation.cell, {}, {}});
        auto& cell = entry->second;
        ++cell.counts.observationContributions;
        ++cell.counts.typeObservationContributions[observation.type];
        cell.contributors.insert(observation.contributorId);
        ++counts.observationContributions;
        ++counts.typeObservationContributions[observation.type];
        contributors.insert(observation.contributorId);
    }
}

void AggregationManager::advance(ump::AggregationTime nowMs) {
    advanceTo(nowMs, true);
}

void AggregationManager::advanceTo(ump::AggregationTime nowMs, bool notifyProgress) {
    if (finished) throw std::logic_error("Aggregation stream already finished");
    if (nowMs < watermarkMs) throw std::invalid_argument("Aggregation clock moved backwards");
    if (nowMs > std::numeric_limits<ump::AggregationTime>::max() - config.windowMs)
        throw std::overflow_error("Aggregation clock exceeds supported range");
    if (retainedHistory) retainedHistory->advance(nowMs);
    while (windowStartMs + config.windowMs <= nowMs)
        closeWindow(windowStartMs + config.windowMs, nowMs, false);
    watermarkMs = nowMs;
    if (notifyProgress && progressSink) progressSink(nowMs, false);
}

void AggregationManager::finish(ump::AggregationTime endMs) {
    if (lastObservationMs && endMs <= *lastObservationMs)
        throw std::invalid_argument("Exclusive stream end must follow its last observation");
    advanceTo(endMs, false); // Final progress must not schedule an extension beyond stream end.
    if (endMs > windowStartMs) closeWindow(endMs, endMs, true);
    if (progressSink) progressSink(endMs, true);
    finished = true;
}

void AggregationManager::closeWindow(ump::AggregationTime endMs, ump::AggregationTime closedAtMs, bool truncated) {
    const auto slotsBefore = [this](ump::AggregationTime t) -> std::uint64_t {
        return t > 0 ? static_cast<std::uint64_t>((t - 1) / config.samplingPeriodMs) : 0;
    };
    const auto expected = slotsBefore(endMs) - slotsBefore(windowStartMs);
    const auto missing = expected - measuredSamples - unavailableSamples;
    const auto coverage = expected == 0 ? ump::WindowCoverage::NoScheduledSamples
        : (missing || unavailableSamples ? ump::WindowCoverage::Incomplete : ump::WindowCoverage::Complete);
    ump::AggregationCandidate output{config.runId, config.sensorId, config.applicationId,
        config.coverage, windowStartMs, endMs, closedAtMs, truncated,
        expected, measuredSamples, unavailableSamples, missing, coverage, counts, {}};
    if (config.semanticTaxonomy) {
        // Reconstruct the identical private interval rather than introducing a
        // second incremental identity-by-category cache. This shares the exact
        // union and stable-class contract with later ancestor/history queries.
        auto reconstructed = retainedHistory->queryFinest(windowStartMs, endMs);
        if (!reconstructed.candidate)
            throw std::runtime_error("Semantic aggregation interval is unavailable from bounded private history");
        output = std::move(*reconstructed.candidate);
        output.closedAtMs = closedAtMs;
        output.truncated = truncated;
    } else {
        finalizeCounts(output.counts, contributors.size(), measuredSamples);
        output.cells.reserve(cells.size());
        for (const auto& [id, cell] : cells) {
            auto result = cell.counts;
            finalizeCounts(result, cell.contributors.size(), measuredSamples);
            output.cells.push_back({cell.geometry, std::move(result)});
        }
        std::sort(output.cells.begin(), output.cells.end(), [](const auto& a, const auto& b) {
            return a.cell.id < b.cell.id;
        });
    }
    sink(output); // Fatal on failure; no retries or reentrant calls are supported.
    windowStartMs = endMs;
    measuredSamples = unavailableSamples = 0;
    counts = {};
    cells.clear();
    contributors.clear();
}

ump::AggregationDebugState AggregationManager::debugState() const {
    std::size_t memberships = contributors.size();
    for (const auto& [id, cell] : cells) memberships += cell.contributors.size();
    return {windowStartMs, windowStartMs + config.windowMs, measuredSamples,
        counts.observationContributions, cells.size(), memberships, finished};
}

void AggregationManager::openBucket(ump::CandidateBucket bucket) {
    if (!retainedHistory) throw std::logic_error("History is not enabled for this stream");
    retainedHistory->openBucket(std::move(bucket));
}
void AggregationManager::extendBucket(const ump::BucketKey& key, ump::AggregationTime endMs) {
    if (!retainedHistory) throw std::logic_error("History is not enabled for this stream");
    retainedHistory->extendBucket(key, endMs);
}
bool AggregationManager::discardBucket(const ump::BucketKey& key) {
    if (!retainedHistory) throw std::logic_error("History is not enabled for this stream");
    return retainedHistory->discardBucket(key);
}
