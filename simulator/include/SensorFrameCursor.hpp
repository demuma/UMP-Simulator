#pragma once
#include "SensorFrame.hpp"
#include "SharedBuffer.hpp"

// The single producer publishes all measurements for t before the agent frame for t.
// After reading that agent frame, the consumer can resolve a missing sensor frame
// immediately. Keep at most one future frame and consume each exact match once.
class SensorFrameCursor {
public:
    // Precondition: the corresponding agent frame has been received, confirming that
    // sensor production through timestamp is complete. This is not an asynchronous
    // sensor-arrival poll; an empty queue now means no measurement for this step.
    void selectCompletedStep(SensorTime timestamp, SharedBuffer<sensorBufferFrameType>& buffer) {
        if (selectedTime && timestamp < *selectedTime)
            throw std::invalid_argument("Renderer timestamps must not move backwards");
        if (selectedTime && *selectedTime == timestamp) return; // Pause/redraw.
        current.reset();
        selectedTime = timestamp;
        while (true) {
            if (!future) {
                auto next = buffer.tryRead();
                if (!next) return;
                future = std::move(*next);
                if (!future) continue;
                if (lastReceived && future->first <= *lastReceived)
                    throw std::invalid_argument("Sensor frames must have unique, increasing timestamps");
                lastReceived = future->first;
            }
            if (future->first < timestamp) { future.reset(); continue; }
            if (future->first == timestamp) current = std::exchange(future, {});
            return; // An exact match is consumed; a future frame stays buffered.
        }
    }
    const sensorBufferFrameType& frame() const { return current; }
private:
    sensorBufferFrameType future;
    sensorBufferFrameType current;
    std::optional<SensorTime> selectedTime;
    std::optional<SensorTime> lastReceived;
};
