#pragma once

#include <SFML/Graphics.hpp>
#include <yaml-cpp/yaml.h>
#include <mongocxx/instance.hpp>
#include <mongocxx/client.hpp>
#include <mongocxx/uri.hpp>
#include <bsoncxx/builder/stream/document.hpp>
#include <bsoncxx/json.hpp>
#include <bsoncxx/document/view.hpp>
// #include <bsoncxx/types/value.hpp
#include <mongocxx/exception/exception.hpp>
#include <iostream>
#include <queue>
#include <thread>

#include "Agent.hpp"
#include "Sensor.hpp"

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
    void testWriteDataBase();
    void testReadDataBase();
    void initializeWindow();
    void initializeSensors();
    void getAgentHeading();
    void getData();
    void getMetadata();
    void update();
    void getTimeStep();
    void handleEvents();
    void appendBufferZones(sf::VertexArray& vertices, const Agent& agent);
    void appendAgentBodies(sf::VertexArray& quads, const Agent& agent);
    Agent createAgentFromDocument(bsoncxx::document::view document);
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
    float gridCellSize = 10.0f;
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
    float EPSILON = 1e-6f;

private:
    sf::VertexArray gridLinesVertexArray;
    sf::VertexArray bufferZonesVertexArray;
    sf::VertexArray agentBodiesVertexArray;
    sf::VertexArray agentArrowHeadVertexArray;
    sf::VertexArray agentArrowBodyVertexArray;
    bool showGrids;
    bool showBufferZones;
    bool showArrow;
    bool makeVideo = false;
    
    std::queue<std::vector<Agent>> frameStorage;
    std::vector<Agent> currentFrame;
    std::unordered_map<std::string, sf::Vector2f> previousHeadings;  // Sorted by agent ID
    std::unordered_map<std::string, sf::Vector2f> previousPositions; // Sorted by agent ID
    int numFrames;
    float frameRate;
    std::map<std::string, Agent::AgentTypeAttributes> agentTypeAttributes;
    std::map<std::string, Sensor> sensorTypeAttributes;


public:
    struct AgentBasedSensor{
        std::string sensorID;
        sf::Vector2f position;
        float frameRate; // Only for single sensor (ABS)
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