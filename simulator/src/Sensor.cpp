#include <cmath>
#include <iostream>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <random>
#include <uuid/uuid.h>

#include "../include/Sensor.hpp"

// Base Sensor constructor for simulation
Sensor::Sensor(
    float frameRate,
    sf::FloatRect detectionArea,
    std::shared_ptr<mongocxx::client> client,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer
) : frameRate(frameRate),
    timeSinceLastUpdate(0.0f),
    client(std::move(client)),
    sensorId(generateUUID()),
    sensorBuffer(sensorBuffer)
{}

// Base Sensor constructor for rendering
Sensor::Sensor(
    const sf::FloatRect& detectionArea, 
    const sf::Color& detectionAreaColor,
    SharedBuffer<sensorBufferFrameType>& sensorBuffer
):  detectionArea(detectionArea), 
    detectionAreaColor(detectionAreaColor), 
    sensorBuffer(sensorBuffer) 
{}

// Shared fixed-step sampling gate for ABS, GBS and AGBS.
bool Sensor::isSamplingDue(float timeStep) {
    if (!samplingInitialized) {
        samplingInitialized = true;
        return false;
    }

    timeSinceLastUpdate += timeStep;
    if (timeSinceLastUpdate < 1.0f / frameRate) {
        return false;
    }

    // Reset even for an empty detection area so occupancy cannot change the cadence.
    timeSinceLastUpdate = 0.0f;
    return true;
}
