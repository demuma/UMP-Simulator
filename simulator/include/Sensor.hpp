#pragma once

#include <SFML/Graphics.hpp>
#include <unordered_map>
#include <vector>
#include <chrono>
#include <string>
#include <iostream>
#include <mongocxx/client.hpp>
#include <mongocxx/database.hpp>
#include <mongocxx/collection.hpp>
#include <unordered_set>

#include "Agent.hpp"
#include "Utilities.hpp"
#include "SharedBuffer.hpp"
#include "SensorFrame.hpp"

using agentFrame = std::vector<Agent>;
using agentFrameType = std::pair<SensorTime, const agentFrame>;
using agentBufferFrameType = std::shared_ptr<const agentFrameType>;

class Sensor {
public:
    Sensor(
        float frameRate, 
        sf::FloatRect detectionArea, 
        std::shared_ptr<mongocxx::client> client,
        std::string id = generateUUID()
    );
    Sensor(
        const sf::FloatRect& detectionArea, 
        const sf::Color& detectionAreaColor
    );
    // virtual void update(std::vector<Agent>& agents, float timeStep, sf::Time simulationTime, std::string datetime) = 0;
    virtual void update(std::vector<Agent>& agents, float timeStep, std::chrono::system_clock::time_point timestamp) = 0;
    virtual void printData() = 0;
    virtual void postData() = 0;
    virtual void postMetadata() = 0;
    virtual void clearDatabase() = 0;
    virtual ~Sensor() = default;
    std::optional<SensorSample> takeSample() { return std::exchange(pendingSample, std::nullopt); }

    sf::Color detectionAreaColor;
    sf::FloatRect detectionArea;
    float frameRate;
    int scale;
    std::chrono::system_clock::time_point timestamp;
    std::unordered_map<std::string, sf::Vector2f> previousPositions;
    std::unordered_map<std::string, sf::Vector2f> currentPositions;
    std::string sensorId;

protected:
    std::shared_ptr<mongocxx::client> client;
    std::optional<SensorSample> pendingSample;
    float timeSinceLastUpdate = 0.0f;

    // The first update observes the initial state; no simulation step has elapsed yet.
    bool samplingInitialized = false;
    bool isSamplingDue(float timeStep);
};
