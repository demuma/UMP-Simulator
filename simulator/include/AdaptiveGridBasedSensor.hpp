#pragma once

#include "Sensor.hpp"
#include "CollisionGrid.hpp"
#include "Quadtree.hpp"
#include "AggregationManager.hpp"

class AdaptiveGridBasedSensor : public Sensor {

public:

    // Adaptive grid cell data with counts per agent type and a total agents
    using AdaptiveGridDataPoint = CellCounts;

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
        std::string id = generateUUID()
    );

    // Alternative constructor for rendering
    AdaptiveGridBasedSensor(
        sf::FloatRect detectionArea, 
        sf::Color detectionAreaColor, 
        float cellSize,
        int maxDepth,
        bool showGrid
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

    // Shared startup validation: no sensor instance, DB writes or rendering are needed.
    static void validateAggregationConfig(const ump::AggregationConfig& config, float simulationStep,
        float frameRate, sf::FloatRect detectionArea, float cellSize, int maxDepth);
    // Optional internal aggregation. Render-only instances never enable this path.
    void enableAggregation(ump::AggregationConfig config, float simulationStep,
        std::chrono::system_clock::time_point origin, AggregationManager::Sink sink);
    void setAggregationProgressSink(AggregationManager::ProgressSink sink) {
        if (!aggregationManager) throw std::logic_error("Aggregation must be enabled before setting progress output");
        aggregationManager->setProgressSink(std::move(sink));
    }
    void finishAggregation(std::chrono::system_clock::time_point end);
    const AggregationManager* getAggregationManager() const { return aggregationManager.get(); }
    void setAggregationDebug(std::shared_ptr<const ump::SpatialSelection> snapshot) {
        aggregationDebug = std::move(snapshot);
    }

private:
    mongocxx::database db;
    mongocxx::collection collection;
    std::unique_ptr<AggregationManager> aggregationManager;
    std::shared_ptr<const ump::SpatialSelection> aggregationDebug;
    std::string aggregationRunId;
    std::chrono::system_clock::time_point aggregationOrigin;
    std::uint64_t aggregationSequence = 0;
    AdaptiveGridData adaptiveGridData;
    std::vector<std::pair<std::chrono::system_clock::time_point, AdaptiveGridData>> dataStorage; // Data Storage: timestamp, map(cell id, map(agent type, count)
};
