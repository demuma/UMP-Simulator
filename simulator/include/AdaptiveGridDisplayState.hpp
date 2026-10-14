#pragma once

#include "SensorFrame.hpp"
#include <unordered_set>

// Render-only geometry from the latest measurement. Never exposes held counts as a
// current observation; the exact-step cursor and aggregation input remain separate.
class AdaptiveGridDisplayState {
public:
    // Returns true only when the tree needs rebuilding. An absent sensor contributes
    // nothing; an identified empty measurement replaces the previous geometry.
    bool update(const sensorBufferFrameType& frame, const std::string& sensorId) {
        if (!frame) return false;
        const auto* sample = findSensorSample<AdaptiveGridSensorSample>(frame->second, sensorId);
        if (!sample) return false;
        if (lastMeasurement && frame->first < *lastMeasurement)
            throw std::invalid_argument("Grid display measurement time moved backwards");
        if (lastMeasurement && frame->first == *lastMeasurement) return false;

        std::unordered_set<int> nextCells;
        nextCells.reserve(sample->cells.size());
        for (const auto& [id, counts] : sample->cells) nextCells.insert(id);
        const bool changed = nextCells != cells;
        cells = std::move(nextCells);
        lastMeasurement = frame->first;
        aggregation = sample->aggregationDebug;
        progress = sample->aggregationProgress;
        return changed;
    }

    const std::unordered_set<int>& cellIds() const { return cells; }
    std::optional<SensorTime> measurementTime() const { return lastMeasurement; }
    const std::shared_ptr<const ump::SpatialSelection>& aggregationSnapshot() const { return aggregation; }
    const std::shared_ptr<const ump::AggregationProgress>& progressSnapshot() const { return progress; }

private:
    std::unordered_set<int> cells;
    std::optional<SensorTime> lastMeasurement;
    std::shared_ptr<const ump::SpatialSelection> aggregation;
    std::shared_ptr<const ump::AggregationProgress> progress;
};
