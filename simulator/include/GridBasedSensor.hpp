#pragma once

#include "Sensor.hpp"
#include "CollisionGrid.hpp"

class GridBasedSensor : public Sensor {

public:

    // Grid cell data with counts per agent type and a total agents
    using GridDataPoint = CellCounts;

    // Every grid data stored with the cell id as key
    typedef std::unordered_map<sf::Vector2i, GridDataPoint, Vector2iHash> GridData;

    // Base constructor for simulation
    GridBasedSensor(
        float frameRate, 
        sf::FloatRect detectionArea, 
        float cellSize, 
        const std::string& databaseName, 
        const std::string& collectionName, 
        std::shared_ptr<mongocxx::client> client,
        std::string id = generateUUID()
    );

    // Alternative constructor for rendering
    GridBasedSensor(
        sf::FloatRect detectionArea, 
        sf::Color detectionAreaColor, 
        float cellSize, 
        bool showGrid
    );

    ~GridBasedSensor();
    float cellSize;
    bool showGrid = false;
    Grid currentGrid;
    Grid previousGrid;
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
    GridData gridData;
    std::vector<std::pair<std::chrono::system_clock::time_point, GridData>> dataStorage;
    
    sf::Vector2i getCellIndex(const sf::Vector2f& position) const;
    sf::Vector2f getCellPosition(const sf::Vector2i& cellIndex) const;
};