#pragma once
#include "SensorFrame.hpp"
#include "SharedBuffer.hpp"

// The producer writes complete frames in chronological order. Keep at most one
// future frame locally; never drain the stream just to search for the current time.
class SensorFrameCursor {
public:
    bool select(SensorTime timestamp, SharedBuffer<sensorBufferFrameType>& buffer) {
        if (selectedTime && timestamp < *selectedTime)
            throw std::invalid_argument("Renderer timestamps must not move backwards");
        if (selectedTime && *selectedTime == timestamp && resolved) return true;
        if (!selectedTime || *selectedTime != timestamp) {
            current.reset();
            selectedTime = timestamp;
            resolved = false;
        }
        while (true) {
            if (!future) {
                auto next = buffer.tryRead();
                if (!next) {
                    resolved = buffer.isDrained();
                    return resolved; // Pending producer, or a confirmed missing frame at EOF.
                }
                future = std::move(*next);
                if (!future) continue;
                if (lastReceived && future->first <= *lastReceived)
                    throw std::invalid_argument("Sensor frames must have unique, increasing timestamps");
                lastReceived = future->first;
            }
            if (future->first < timestamp) { future.reset(); continue; }
            if (future->first == timestamp) current = std::exchange(future, {});
            // A future timestamp proves this timestamp is missing in an ordered stream.
            resolved = true;
            return true;
        }
    }
    const sensorBufferFrameType& frame() const { return current; }
private:
    sensorBufferFrameType future;
    sensorBufferFrameType current;
    std::optional<SensorTime> selectedTime;
    std::optional<SensorTime> lastReceived;
    bool resolved = false;
};
