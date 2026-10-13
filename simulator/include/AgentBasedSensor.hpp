#pragma once
#include <chrono>

#include "Sensor.hpp"

class AgentBasedSensor : public Sensor {
public:

    using AgentData = AgentObservation;

    // Base constructor for simulation
    AgentBasedSensor(
        float frameRate, 
        sf::FloatRect detectionArea, 
        const std::string& databaseName,
        const std::string& collectionName,
        std::shared_ptr<mongocxx::client> client,
        std::string id = generateUUID()
    );

    // Alternative constructor for rendering
    AgentBasedSensor( 
        sf::FloatRect detectionArea, 
        sf::Color detectionAreaColor
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

    // Pending output batch; observations are assembled locally in captureAgentData().
    std::pair<std::chrono::system_clock::time_point, std::vector<AgentData>> dataStorage;
};
