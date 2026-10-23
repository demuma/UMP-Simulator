#include <cmath>
#include <iostream>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <random>
#include <stdexcept>
#include <uuid/uuid.h>

#include "../include/Sensor.hpp"

// Base Sensor constructor for simulation
Sensor::Sensor(
    float frameRate,
    sf::FloatRect detectionArea,
    std::shared_ptr<mongocxx::client> client,
    std::string id
) : frameRate(frameRate),
    client(std::move(client)),
    sensorId(std::move(id))
{}

// Base Sensor constructor for rendering
Sensor::Sensor(
    const sf::FloatRect& detectionArea, 
    const sf::Color& detectionAreaColor
):  detectionArea(detectionArea), 
    detectionAreaColor(detectionAreaColor)
{}

// Shared observation-time sampling gate for ABS, GBS and AGBS.
bool Sensor::isSamplingDue(float timeStep) {
    if (!std::isfinite(timeStep) || timeStep <= 0)
        throw std::invalid_argument("Sensor simulation step must be positive and finite");
    if (!samplingInitialized) {
        const double periodUs = 1000000.0 / static_cast<double>(frameRate);
        if (!std::isfinite(frameRate) || frameRate <= 0 || !std::isfinite(periodUs)
            || periodUs < 1 || periodUs >= std::ldexp(1.0, 63))
            throw std::invalid_argument("Sensor frame rate needs a representable period of at least one microsecond");
        samplingPeriod = std::chrono::microseconds{std::llround(periodUs)};
        samplingOrigin = previousUpdateTimestamp = timestamp;
        initializedFrameRate = frameRate;
        samplingInitialized = true;
        return false;
    }
    if (frameRate != initializedFrameRate)
        throw std::invalid_argument("Changing sensor frame rate after initialization is unsupported");
    if (timestamp < previousUpdateTimestamp)
        throw std::invalid_argument("Sensor observation timestamps must not move backwards");
    previousUpdateTimestamp = timestamp;
    const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(timestamp - samplingOrigin).count();
    const auto slot = elapsed / samplingPeriod.count();
    if (slot <= previousSamplingSlot) return false;
    // Preserve the origin phase even when an unaligned source tick arrives late.
    // All skipped slots remain unobserved; only this timestamp is measured.
    previousSamplingSlot = slot;
    return true;
}
