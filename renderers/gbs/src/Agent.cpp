#include "../include/Agent.hpp"

// Default constructor for the Agent class
Agent::Agent(const AgentTypeAttributes& attributes) : attributes(attributes) {

    collisionPredicted = false;
    stopped = false;
    isActive = true;
    stoppedFrameCounter = 0;
    minBufferZoneRadius = 0.5f;
    bufferZoneRadius = minBufferZoneRadius;
    bufferZoneColor = sf::Color::Green;
};

Agent::Agent() {
    
}

Agent::~Agent() {
    trajectory.clear();
}

// Initialize the agent with default values and calculate buffer zone radius
void Agent::setBufferZoneSize() {

    float velocityMagnitude = std::sqrt(velocity.x * velocity.x + velocity.y * velocity.y);
    bufferZoneRadius = minBufferZoneRadius + bodyRadius + (velocityMagnitude / attributes.velocity.max) * bodyRadius; 
}

// Calculate the velocity based on the next waypoint
void Agent::calculateVelocity(sf::Vector2f waypoint) {
    
    // Calculate velocity based on heading to the next waypoint
    float angle = std::atan2(waypoint.y - position.y, waypoint.x - position.x);
    
    // Calculate the heading vector
    // sf::Vector2f heading;
    heading.x = std::cos(angle);
    heading.y = std::sin(angle);

    // Set the velocity vector based on the heading
    velocity = heading * velocityMagnitude;
}

// Update the agent's velocity based on Perlin noise
void Agent::updateVelocity(float deltaTime, sf::Time simulationTime) {
    
    // Use the agent's own Perlin noise generator to fluctuate velocity
    float noiseX = perlinNoise.noise(position.x * attributes.velocity.noiseScale, position.y * attributes.velocity.noiseScale, simulationTime.asSeconds()) * 2.0f - 1.0f;
    float noiseY = perlinNoise.noise(position.x * attributes.velocity.noiseScale, position.y * attributes.velocity.noiseScale, simulationTime.asSeconds() + 1000.0f) * 2.0f - 1.0f;

    // Apply noise to velocity
    velocity.x = initialVelocity.x + noiseX / 3.6 * attributes.velocity.noiseFactor;
    velocity.y = initialVelocity.y + noiseY / 3.6 * attributes.velocity.noiseFactor;
}

// Update the agent's position based on velocity
void Agent::updatePosition(float timeStep) {

    // Update the position based on the velocity
    position.x += velocity.x * timeStep;
    position.y += velocity.y * timeStep;
}

// Get the future position of the agent at a given time
sf::Vector2f Agent::getFuturePositionAtTime(float time) const {

    return position + velocity * time;
}

// Calculate the trajectory based on the target position and waypoint distance
void Agent::calculateTrajectory(float waypointDistance) {
    
    // Clear existing trajectory data
    trajectory.clear();

    // Add the initial position as the starting waypoint
    trajectory.push_back(initialPosition);

    // Save the initial position
    sf::Vector2f currentPosition = initialPosition;

    // Calculate total distance to target
    double totalDistance = sqrt(pow((targetPosition.x - initialPosition.x), 2) + pow((targetPosition.y - initialPosition.y), 2));
    
    // Round down to the nearest integer
    int numWaypoints = floor(totalDistance / waypointDistance);
    
    // If there are no waypoints, go directly to the target
    if (numWaypoints < 1) {
        trajectory.push_back(targetPosition);
        return;
    }
    
    // Calculate angle to the target
    double angle = atan2(targetPosition.y - initialPosition.y, targetPosition.x - initialPosition.x); // in radians
    
    // Compute delta positions
    double deltaX = waypointDistance * cos(angle);
    double deltaY = waypointDistance * sin(angle);

    // Add intermediate waypoints
    for (int i = 0; i < numWaypoints; ++i) {
        currentPosition.x += deltaX;
        currentPosition.y += deltaY;
        trajectory.push_back(currentPosition);
    }

    // Add the final target position as the last waypoint
    trajectory.push_back(targetPosition);
}

// Get the next waypoint based on the agent's trajectory
void Agent::getNextWaypoint() {

    // Get the next waypoint based on trajectory, position, and velocity
    for (int i = 0; i < trajectory.size(); ++i) {
        sf::Vector2f directionToWaypoint = trajectory[i] - position;
        float dotProduct = directionToWaypoint.x * velocity.x + directionToWaypoint.y * velocity.y;
        if (dotProduct > 0) {
            nextWaypointIndex = i;
            break;
        }
    }
}

// Reset the collision state of the agent
void Agent::resetCollisionState() {

    bufferZoneColor = sf::Color::Green;
    collisionPredicted = false;
}

// Stop the agent
void Agent::stop() {

    // Stop the agent if it is not already stopped
    if (!stopped) {
        velocity = sf::Vector2f(0.0f, 0.0f);
        stopped = true;
        stoppedFrameCounter = 0;
    }
}

// Check if the agent can resume movement without colliding with other agents
bool Agent::canResume(const std::vector<Agent>& agents) {

    for (const auto& other : agents) {
        if (&other == this) continue;

        float dx = position.x - other.position.x;
        float dy = position.y - other.position.y;
        float distance = std::sqrt(dx * dx + dy * dy);
        
        if (distance < bodyRadius + other.bodyRadius) {
            
            return false;
        }
    }
    return true;
}

// Resume the agent's movement if there are no collisions
void Agent::resume(const std::vector<Agent>& agents) {

    // Resume the agent if it is stopped and has been stopped for at least 20 frames
    if (stopped) {
        velocity = initialVelocity;
        stopped = false;
    }
}