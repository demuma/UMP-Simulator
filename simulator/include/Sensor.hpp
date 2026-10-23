#pragma once

#include <SFML/Graphics.hpp>
#include <unordered_map>
#include <vector>
#include <chrono>
#include <cstdint>
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
    // The first update observes the initial state. Integer timestamp slots preserve
    // the sampling phase without accumulating floating-point simulation steps.
    // A late update yields one actual observation, never invented catch-up frames.
    bool samplingInitialized = false;
    bool isSamplingDue(float timeStep);

private:
    SensorTime samplingOrigin{};
    SensorTime previousUpdateTimestamp{};
    std::chrono::microseconds samplingPeriod{0};
    std::int64_t previousSamplingSlot = 0;
    float initializedFrameRate = 0;
};
