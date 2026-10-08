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

// Base Sensor velocity estimation
void Sensor::estimateVelocities(std::unordered_map<std::string, sf::Vector2f>& estimatedVelocities) {

    // Estimate the velocities of the agents
    for (const auto& kvp : previousPositions) {

        const std::string& agentUUID = kvp.first;
        const sf::Vector2f& previousPosition = kvp.second;

        // If the agent is still in the detection area
        if (currentPositions.find(agentUUID) != currentPositions.end()) {

            const sf::Vector2f& currentPosition = currentPositions[agentUUID];
            sf::Vector2f estimatedVelocity = (currentPosition - previousPosition) * frameRate;
            estimatedVelocities[agentUUID] = estimatedVelocity;
        }
    }
}