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

#include "Agent.hpp"
#include "Sensor.hpp"
#include "Utilities.hpp"

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
    void getTimeStep();
    void handleEvents();
    void captureFrame(int frameNumber);
    void createVideoFromFrames(int totalFrames);
    void cleanupFrames(int frameNumber);

public:
    float timeStep;
    sf::RenderWindow window;
    sf::RenderTexture renderTexture; // For video capture
    sf::Vector2f windowSize;
    bool paused = false;
    std::string title;

    sf::Vector2f simulationSize;
    sf::Vector2f offset;
    float scale = 10;
    float gridCellSize = 30.0f;
    YAML::Node config;
    std::vector<Sensor> sensors;

    int windowWidth;
    int windowHeight;
    float simulationWidth;
    float simulationHeight;
    float initialSimulationWidth;
    float initialSimulationHeight;
    float initialScale;
    bool isShiftPressed = false;
    bool isCtrlPressed = false;
    
    std::shared_ptr<mongocxx::client> client;
    mongocxx::database db;
    mongocxx::instance instance;
    mongocxx::collection collection;
    std::string collectionName;
    std::string databaseName;
    std::string dbUri;


private:
    sf::VertexArray gridLinesVertexArray;

    float frameRate; // Only for single sensor (GBS)
    bool showGrids;
    bool makeVideo = false;

    // Data structures for grid-based data
    std::queue<std::unordered_map<sf::Vector2i, std::unordered_map<std::string, int>, Vector2iHash>> frameStorage;
    std::unordered_map<sf::Vector2i, std::unordered_map<std::string, int>, Vector2iHash> currentGridData;

    // Ghost cell
    std::unordered_map<std::string, int> ghostCellAgentCounts;

    // List of all agent types
    std::vector<std::string> allAgentTypes;

    std::map<std::string, Agent::AgentTypeAttributes> agentTypeAttributes;
    int numFrames;
    std::map<std::string, Sensor> sensorTypeAttributes;


public:
    struct AgentBasedSensor{
        std::string sensorID;
        sf::Vector2f position;
        float frameRate;
        sf::FloatRect detectionArea;
        std::string collectionName;
        std::string type;
        sf::Color color;
        int alpha;
    };
    struct GridBasedSensor{
        std::string sensorID;
        sf::Vector2f position;
        float frameRate;
        float cellSize;
        sf::FloatRect detectionArea;
        std::string collectionName;
        std::string type;
        sf::Color color;
        int alpha;
    };
};