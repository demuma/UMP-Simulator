#pragma once

#include <SFML/Graphics.hpp>
#include <yaml-cpp/yaml.h>
#include <mongocxx/instance.hpp>
#include <mongocxx/client.hpp>
#include <mongocxx/uri.hpp>
#include <bsoncxx/builder/stream/document.hpp>
#include <bsoncxx/json.hpp>
#include <bsoncxx/document/view.hpp>
#include <mongocxx/exception/exception.hpp>
#include <iostream>
#include <queue>
#include <thread>
#include <memory> // For std::unique_ptr
#include <unordered_set>

#include "Agent.hpp"
#include "Sensor.hpp"
#include "Utilities.hpp"
#include "Quadtree.hpp" // <-- REQUIRED: Include the Quadtree header

// Data structure for a single cell from the adaptive grid database
struct AdaptiveCellData {
    sf::Vector2f position;
    float size;
    std::unordered_map<std::string, int> agentCounts;
};


class Visualizer {
public:
    Visualizer();
    ~Visualizer();
    void run();

private:
    void render();
    void loadConfiguration();
    void loadAgentsAttributes();
    void loadSensorAttributes();
    void initializeDatabase();
    void initializeWindow();
    void getData();
    void getMetadata();
    void update();
    void handleEvents();
    void captureFrame(int frameNumber);
    void createVideoFromFrames(int totalFrames);
    void cleanupFrames(int frameNumber);

public:
    sf::RenderWindow window;
    sf::RenderTexture renderTexture;
    sf::Vector2f windowSize;
    bool paused = false;
    std::string title;

    sf::Vector2f simulationSize;
    sf::Vector2f offset;
    float scale = 10;
    YAML::Node config;
    std::vector<Sensor> sensors;

    std::shared_ptr<mongocxx::client> client;
    mongocxx::database db;
    mongocxx::instance instance;
    mongocxx::collection collection;
    std::string collectionName;
    std::string databaseName;
    std::string dbUri;


private:
    sf::Font font; // Font for drawing debug info if needed
    std::unique_ptr<Quadtree> quadtree; // Quadtree to reconstruct the grid structure
    int maxDepth;

    float frameRate;
    bool showGrids;
    bool showText;
    bool makeVideo = false;

    // Data structures for adaptive grid data
    std::queue<std::unordered_map<int, AdaptiveCellData>> frameStorage;
    std::unordered_map<int, AdaptiveCellData> currentFrameData;

    // Ghost cell (can be adapted if needed, but likely unused for adaptive grid)
    std::unordered_map<std::string, int> ghostCellAgentCounts;

    // List of all agent types
    std::vector<std::string> allAgentTypes;

    std::map<std::string, Agent::AgentTypeAttributes> agentTypeAttributes;
    int numFrames;
    std::map<std::string, Sensor> sensorTypeAttributes;
};