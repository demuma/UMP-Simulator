#pragma once
#include <chrono>

#include "Sensor.hpp"

class AgentBasedSensor : public Sensor {
public:

    struct AgentData {

        // Sensor data structure
        std::string sensorId;
        std::string agentId;
        std::chrono::system_clock::time_point timestamp;
        std::string type;
        sf::Vector2f position;
        sf::Vector2f estimatedVelocity;
    };

    // Base constructor for simulation
    AgentBasedSensor(
        float frameRate, 
        sf::FloatRect detectionArea, 
        const std::string& databaseName,
        const std::string& collectionName,
        std::shared_ptr<mongocxx::client> client,
        SharedBuffer<sensorBufferFrameType>& sensorBuffer
    );

    // Alternative constructor for rendering
    AgentBasedSensor( 
        sf::FloatRect detectionArea, 
        sf::Color detectionAreaColor,
        SharedBuffer<sensorBufferFrameType>& sensorBuffer
    );

    ~AgentBasedSensor();
    sf::Vector2f position = sf::Vector2f(detectionArea.position.x, detectionArea.position.y);

    void update(std::vector<Agent>& agents, float timeStep, std::chrono::system_clock::time_point timestamp) override;
    void captureAgentData(std::vector<Agent>& agents);
    void postData() override;
    void postMetadata() override;
    void printData() override;
    void clearDatabase() override;

private:
    mongocxx::database db;
    mongocxx::collection collection;

    // Mapping of agent ID to estimated velocity
    std::unordered_map<std::string, sf::Vector2f> estimatedVelocities;

    // Data storage structure
    std::vector<AgentData> agentData;
    SharedBuffer<sensorBufferFrameType>& sensorBuffer;
    std::pair<std::chrono::system_clock::time_point, std::vector<AgentData>> dataStorage;
};