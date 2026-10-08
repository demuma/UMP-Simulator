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
// #include "QuadtreeSnapshot.hpp"

/**************************************/
/********** SIMULATION CLASS **********/
/**************************************/

// Simulation class
class Simulation {
public:

    // Simulation(std::queue<std::vector<Agent>> (&agentBuffer)[2], std::mutex &queueMutex, std::condition_variable &queueCond, std::atomic<float>& currentSimulationTimeStep, std::atomic<bool>& stop, std::atomic<int>& currentNumAgents, const YAML::Node& config, std::atomic<std::queue<std::vector<Agent>>*>& currentReadBuffer);
    Simulation(
        // SharedBuffer<std::vector<Agent>>& agentBuffer, 
        SharedBuffer<agentBufferFrameType>& agentBuffer,
        SharedBuffer<sensorBufferFrameType>& sensorBuffer,
        // std::unordered_map<std::string, std::shared_ptr<SharedBuffer<std::shared_ptr<QuadtreeSnapshot::Node>>>> sensorBuffers,
        std::atomic<float>& currentSimulationTimeStep, const YAML::Node& config);
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
    void initializeSensors();

private:
    void postMetadata();
    void postData(const std::vector<Agent>& agents);
     // Simulation parameters
    // ThreadPool threadPool;
    std::atomic<float>& currentSimulationTimeStep;
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
    std::shared_ptr<mongocxx::client> client;
    mongocxx::instance instance;
    mongocxx::collection collection; // For agent data storage
    std::vector<std::vector<bsoncxx::document::value>> documentBuffer;
    bool clearDatabase = false;

    // Sensors
    std::vector<std::unique_ptr<Sensor>> sensors;
};