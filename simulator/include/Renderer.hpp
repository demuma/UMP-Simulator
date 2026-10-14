#pragma once

#include <SFML/Graphics.hpp>
#include <atomic>
#include <deque>
#include <iostream>
#include <yaml-cpp/yaml.h>
#include <vector>
#include <iomanip>
#include <thread>
#include <iterator>

#include "Agent.hpp"
#include "SharedBuffer.hpp"
// #include "QuadtreeSnapshot.hpp"
#include "Logging.hpp"
#include "Obstacle.hpp"
#include "Utilities.hpp"
#include "Sensor.hpp"
#include "SensorFrameCursor.hpp"
#include "AdaptiveGridDisplayState.hpp"
#include "PlaybackClock.hpp"

/************************************/
/********** RENDERER CLASS **********/
/************************************/

// Renderer class
class Renderer {
public:
    Renderer(
        SharedBuffer<agentBufferFrameType>& agentBuffer,
        SharedBuffer<sensorBufferFrameType>& sensorBuffer,
        const YAML::Node& config);
    void run();
    void loadConfiguration();
    void loadAgentsAttributes();
    void loadObstacles();
    void initializeSensors();
    void initializeWindow();
    void initializeGUI();
    void updateFrameCountText();
    void updateFrameRateText();
    void updateAgentCountText();
    void updateTimeText();
    void updatePlayBackSpeedText();
    // void handleEvents(sf::Event& event); // Note: SFML 2.6.2 or prior
    void handleEvents();
    bool readNextFrame();

private:
// Struct for rendering agents
    struct RenderAgent {
        sf::Vector2f position;
        sf::Vector2f initialPosition;
        sf::Vector2f targetPosition;
        sf::Vector2f velocity;
        sf::Vector2f heading;
        float velocityMagnitude;
        std::vector<sf::Vector2f> trajectory;
        float bodyRadius;
        float bufferZoneRadius;
        sf::Color color;
        int nextWaypointIndex = -1;
        sf::Color waypointColor;
        float waypointRadius;
        float waypointDistance;
        std::string type;
        sf::Color bufferZoneColor;
    };

    void render();
    void drawAggregationOverlay(const ump::SpatialSelection& snapshot);
    void drawAggregationProgress(const ump::AggregationProgress& progress);
    void drawAggregationStatusPanels();
    float drawStatusPanel(const std::vector<std::string>& lines, sf::Vector2f position, float width);
    void appendBufferZones(sf::VertexArray& vertices, const RenderAgent& agent);
    void appendAgentBodies(sf::VertexArray& triangles, const RenderAgent& agent);

    // Current frame agents for rendering
    std::vector<RenderAgent> renderAgents;

    // Renderer parameters
    sf::RenderWindow window;
    const YAML::Node& config;

    // Display parameters
    sf::Font font;
    std::string title;
    bool showInfo = true;
    bool showText = true;

    // Event handling
    bool isShiftPressed = false;
    bool isCtrlPressed = false;

    // Window scaling
    unsigned int windowWidth;  // Pixels
    unsigned int windowHeight; // Pixels
    float simulationWidth;  // Pixels
    float simulationHeight; // Pixels
    float initialSimulationWidth;  // Pixels
    float initialSimulationHeight; // Pixels
    float initialScale;
    float scale;
    sf::Vector2f offset;
    bool isPanning = false; // Currently dragging
    sf::Vector2f lastMousePosition = {0, 0}; // Last mouse position

    // Renderer parameters
    float timeStep;
    double playbackSpeed;
    std::optional<ump::PlaybackClock> playbackClock;
    bool waitingForFrame = false;
    bool redrawRequested = true;
    bool paused = false;
    bool live_mode;
    int numAgents;
    bool showGrids = false;
    bool showAggregation = false;
    bool showAggregationProgress = false;
    bool showBufferZones = false;
    float EPSILON = 1e-6f;

    // Visualization elements
    sf::Text frameText;
    sf::Text frameRateText;
    sf::Text agentCountText;
    sf::Text timeText;
    sf::Text playbackSpeedText;
    sf::RectangleShape pauseButton;
    sf::Text pauseButtonText;
    sf::RectangleShape resetButton;
    sf::Text resetButtonText;

    // Vertex arrays
    sf::VertexArray bufferZonesVertexArray;
    sf::VertexArray agentBodyVertexArray;
    sf::VertexArray agentArrowHeadVertexArray;
    sf::VertexArray agentArrowBodyVertexArray;

    // Playback timing is independent of producer runtime and sensor sampling.
    int maxFrames = 0;
    float targetRenderTime;
    sf::Time renderSimulationTime;
    std::chrono::system_clock::time_point timestamp;

    // Shared buffers
    // SharedBuffer<std::vector<Agent>>& agentBuffer;
    SharedBuffer<agentBufferFrameType>& agentBuffer;
    SharedBuffer<sensorBufferFrameType>& sensorBuffer;
    SensorFrameCursor sensorFrames;
    std::unordered_map<std::string, AdaptiveGridDisplayState> adaptiveGridDisplays;

    // Sensors
    std::vector<std::unique_ptr<Sensor>> sensors;
    bool showSensors = false;
    bool showSensorGrid = true;
    bool overrideSensorGridVisibility = false;

    // Obstacles
    bool showObstacles = false;
    std::vector<Obstacle> obstacles;

    // Corridors
    bool showCorridors = false;

    // Agents and sensors
    std::shared_ptr<const agentFrame> currentAgentFrame;
    std::shared_ptr<const sensorFrame> currentSensorFrame;
    
    // Sensor buffer frame: timestamp, map (sensorID -> typed measurement payload)
    int currentNumAgents;
    float waypointRadius;
    bool showTrajectories = false;
    bool showWaypoints = false;
    bool showArrow = false;

    // Collision
    bool showCollisionGrid = false;
    float collisionGridCellSize;

    // Agent attributes
    std::map<std::string, Agent::AgentTypeAttributes> agentTypeAttributes;
};