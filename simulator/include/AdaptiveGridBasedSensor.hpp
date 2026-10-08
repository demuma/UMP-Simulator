#pragma once

#include "Sensor.hpp"
#include "CollisionGrid.hpp"
#include "Quadtree.hpp"
#include "AggregationManager.hpp"

class AdaptiveGridBasedSensor : public Sensor {

public:

    // Adaptive grid cell data with counts per agent type and a total agents
    typedef struct AdaptiveGridDataPoint {
        std::unordered_map<std::string, int> agentTypeCount;
        int totalAgents;
    } AdaptiveGridDataPoint;

    // Every adaptive grid data stored with the cell id as key
    typedef std::unordered_map<int, AdaptiveGridDataPoint> AdaptiveGridData;

    // Base constructor for simulation
    AdaptiveGridBasedSensor(
        float frameRate, 
        sf::FloatRect detectionArea, 
        float cellSize, 
        int maxDepth, 
        const std::string& databaseName, 
        const std::string& collectionName, 
        std::shared_ptr<mongocxx::client> client,
        SharedBuffer<sensorBufferFrameType>& sensorBuffer
    );

    // Alternative constructor for rendering
    AdaptiveGridBasedSensor(
        sf::FloatRect detectionArea, 
        sf::Color detectionAreaColor, 
        float cellSize,
        int maxDepth,
        bool showGrid,
        SharedBuffer<sensorBufferFrameType>& sensorBuffer
    );

    ~AdaptiveGridBasedSensor();
    float cellSize;
    bool showGrid = false;
    int maxDepth;
    Quadtree adaptiveGrid;
    sf::Vector2f position = sf::Vector2f(detectionArea.position.x, detectionArea.position.y);
    
    // void update(std::vector<Agent>& agents, float timeStep, sf::Time simulationTime, std::string date) override;
    void update(std::vector<Agent>& agents, float timeStep, std::chrono::system_clock::time_point timestamp) override;
    void postData() override;
    void postMetadata() override;
    void printData() override;
    void clearDatabase() override;
    void calculateCellDensity();

private:
    mongocxx::database db;
    mongocxx::collection collection;
    AggregationManager aggregationManager;
    AdaptiveGridData adaptiveGridData;
    SharedBuffer<sensorBufferFrameType>& sensorBuffer;
    sensorFrame currentCellIds;
    std::vector<std::pair<std::chrono::system_clock::time_point, AdaptiveGridData>> dataStorage; // Data Storage: timestamp, map(cell id, map(agent type, count)
};