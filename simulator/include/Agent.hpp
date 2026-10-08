#pragma once

#include <SFML/Graphics.hpp>
#include <vector>
#include <string>
#include <iostream>
#include <random>
#include <cmath>
#include <uuid/uuid.h>

#include "PerlinNoise.hpp"
#include "Logging.hpp"

/*********************************/
/********** AGENT CLASS **********/
/*********************************/

// Agent class
class Agent {
public:

    // From Taxonomy
    struct AgentTypeAttributes {    
        float probability;
        int priority;
        float bodyRadius;
        std::string color;
        struct Velocity {
            float min;
            float max;
            float mu;
            float sigma;
            float noiseScale = 0.05f;
            float noiseFactor = 0.5f;
        } velocity;
        struct Acceleration {
            float min;
            float max;
        } acceleration;
        float lookAheadTime;
    };

    Agent(const AgentTypeAttributes& attributes);
    ~Agent();

    // Position
    void calculateTrajectory(float waypointDistance);
    void getNextWaypoint();
    void updatePosition(float deltaTime);
    sf::Vector2f getFuturePositionAtTime(float time) const;

    // Velocity
    void calculateVelocity(sf::Vector2f waypoint);
    void updateVelocity(float deltaTime, sf::Time simulationTime);

    // States
    void stop();
    bool canResume(const std::vector<Agent>& agents);
    void resume(const std::vector<Agent>& agents);
    void resetCollisionState();
    void setBufferZoneSize();
    sf::FloatRect getBufferZoneBounds() const;

    // Agent features
    std::string agentId;
    std::string sensorId;
    std::string type;
    sf::Color color;
    sf::Color initialColor;
    int priority;
    float bodyRadius;
    AgentTypeAttributes attributes;
    std::chrono::system_clock::time_point timestamp;

    // Positions
    sf::Vector2f position;
    sf::Vector2f initialPosition;
    sf::Vector2f targetPosition;
    sf::Vector2f heading;
    float theta;

    // Velocity
    sf::Vector2f velocity;
    sf::Vector2f initialVelocity;
    float velocityMagnitude;

    // Acceleration
    sf::Vector2f acceleration;
    sf::Vector2f initialAcceleration;
    float accelerationMagnitude;

    // Trajectory
    std::vector<sf::Vector2f>(trajectory);
    float waypointDistance;
    // sf::Color waypointColor;
    int nextWaypointIndex = -1;

    // Visuals
    float bufferZoneRadius;
    float minBufferZoneRadius;
    sf::Color bufferZoneColor;

    // States
    bool collisionPredicted;
    bool stopped;
    bool isActive;
    int stoppedFrameCounter;
    float lookAheadTime;

    // Perlin noise
    unsigned int noiseSeed;
    PerlinNoise perlinNoise;  // TODO: Change to simplex noise -> Huge savings in performance
};