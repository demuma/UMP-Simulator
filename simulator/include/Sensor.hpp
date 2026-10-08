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

// using agentFrameType = const std::vector<Agent>; // only for renderer
// using sensorFrameType = const std::unordered_map<std::string, std::unordered_set<int>>; // only for renderer
using agentFrame = std::vector<Agent>;
using sensorFrame = std::unordered_map<std::string, std::unordered_set<int>>;
using agentFrameType = std::pair<std::chrono::system_clock::time_point, const agentFrame>; // only for renderer
using sensorFrameType = std::pair<std::chrono::system_clock::time_point, const sensorFrame>;
using agentBufferFrameType = std::shared_ptr<agentFrameType>;
using sensorBufferFrameType = std::shared_ptr<sensorFrameType>;

class Sensor {
public:
    Sensor(
        float frameRate, 
        sf::FloatRect detectionArea, 
        std::shared_ptr<mongocxx::client> client,
        SharedBuffer<sensorBufferFrameType>& sensorBuffer
    );
    Sensor(
        const sf::FloatRect& detectionArea, 
        const sf::Color& detectionAreaColor,
        SharedBuffer<sensorBufferFrameType>& sensorBuffer
    );
    // virtual void update(std::vector<Agent>& agents, float timeStep, sf::Time simulationTime, std::string datetime) = 0;
    virtual void update(std::vector<Agent>& agents, float timeStep, std::chrono::system_clock::time_point timestamp) = 0;
    virtual void printData() = 0;
    virtual void postData() = 0;
    virtual void postMetadata() = 0;
    virtual void clearDatabase() = 0;
    virtual ~Sensor() = default;

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
    SharedBuffer<sensorBufferFrameType>& sensorBuffer;
    float timeSinceLastUpdate = 0.0f;

    void estimateVelocities(std::unordered_map<std::string, sf::Vector2f>& estimatedVelocities);
};