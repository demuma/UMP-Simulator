#pragma once

#include <vector>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <future>
#include <iostream>
#include <yaml-cpp/yaml.h>
#include <atomic>
#include <cmath>
#include <mongocxx/client.hpp>
#include <bsoncxx/builder/stream/document.hpp>
#include <mongocxx/instance.hpp>
#include <mongocxx/exception/exception.hpp>

#include "Agent.hpp"
#include "Region.hpp"
#include "ThreadPool.hpp"
#include "SharedBuffer.hpp"
#include "Obstacle.hpp"
#include "Utilities.hpp"
#include "Logging.hpp"
#include "CollisionGrid.hpp"
#include "Sensor.hpp"
#include "Quadtree.hpp"
#include "MappedScene.hpp"
// #include "QuadtreeSnapshot.hpp"

/**************************************/
/********** SIMULATION CLASS **********/
/**************************************/

// Simulation class
class Simulation {
public:

    Simulation(
        // SharedBuffer<std::vector<Agent>>& agentBuffer, 
        SharedBuffer<agentBufferFrameType>& agentBuffer,
        SharedBuffer<sensorBufferFrameType>& sensorBuffer,
        // std::unordered_map<std::string, std::shared_ptr<SharedBuffer<std::shared_ptr<QuadtreeSnapshot::Node>>>> sensorBuffers,
        const YAML::Node& config);
    ~Simulation();
    void run();
    void update();
    float getCurrentFrameRate();
    void loadConfiguration();
    void loadAgentsAttributes();
    void loadRegionsAttributes();
    void loadObstacles();
    void initializeGrid();
    void initializeAdaptiveGrid();
    void initializeDatabase();
    void initializeAgents();
    void initializeRegions();
    void initializeMetricPolicies();
    void initializeSensors();

private:
    void postMetadata();
    void initializeMappedScene();
    void updateMappedAgents(ump::AggregationTime nowMs);
    void postMappedEventsThrough(ump::AggregationTime nowMs);
    // Private simulator oracle; never supplied to a Sensor or aggregation input.
    std::unique_ptr<ump::MappedScene> mappedScene;
    std::size_t mappedEventCursor = 0;
    std::string aggregationRunId = generateUUID();
    void postData(const std::vector<Agent>& agents);
     // Simulation parameters
    // ThreadPool threadPool;
    const YAML::Node& config;
    int numThreads;

    // Timing parameters
    float timeStep;
    size_t maxFrames;
    int targetSimulationTime;
    sf::Time simulationRealTime = sf::Time::Zero;
    sf::Time simulationTime = sf::Time::Zero;
    std::string datetime;
    std::chrono::system_clock::time_point timestamp;

    // Window parameters
    float simulationWidth; // Meters
    float simulationHeight; // Meters
    float scale;
    double tolerance = 1e-7;

    // Agent parameters
    int numAgentTypes;
    int numAgents;
    int numRegionTypes;
    int numRegions;
    std::vector<Region> regions;
    std::unordered_map<std::string, ump::MetricEvaluator> metricEvaluators;
    std::vector<Agent> agents;
    float waypointDistance;
    std::unordered_map<std::string, Agent::AgentTypeAttributes> agentTypeAttributes;
    std::unordered_map<std::string, Region::RegionTypeAttributes> regionTypeAttributes;


    // Shared buffer reference
    // SharedBuffer<std::vector<Agent>>& agentBuffer;
    SharedBuffer<agentBufferFrameType>& agentBuffer;
    SharedBuffer<sensorBufferFrameType>& sensorBuffer;

    // Obstacles
    std::vector<Obstacle> obstacles;

    // Grid
    Grid collisionGrid;
    float collisionGridCellSize = 100.0f;

    // Scenario
    std::string scenario;

    // MongoDB
    std::string dbUri;
    std::string databaseName;
    std::string collectionName;
    // Declared first, destroyed last: the driver must outlive every MongoDB object.
    mongocxx::instance instance;
    std::shared_ptr<mongocxx::client> client;
    mongocxx::collection collection; // For agent data storage
    std::vector<std::vector<bsoncxx::document::value>> documentBuffer;
    bool clearDatabase = false;

    // Sensors
    std::vector<std::unique_ptr<Sensor>> sensors;
};