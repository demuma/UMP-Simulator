#include "../include/CollisionAvoidance.hpp"
#include <cmath>
#include <iostream>

// Check for collision between two agents (sampling-based collision detection)
bool predictCollisionAgents_v1(Agent& agent1, Agent& agent2) {

    const float lookaheadStep = 0.2f; // Time step for predictions
    const float maxLookahead = 2.0f; // Maximum lookahead time

    for (float t = 0; t <= maxLookahead; t += lookaheadStep) {
        sf::Vector2f futurePos1 = agent1.getFuturePositionAtTime(t);
        sf::Vector2f futurePos2 = agent2.getFuturePositionAtTime(t);

        // Check if the future positions (including buffer radius) intersect
        float dx = futurePos1.x - futurePos2.x;
        float dy = futurePos1.y - futurePos2.y;
        float distance = std::sqrt(dx * dx + dy * dy);

        if (distance < agent1.bufferZoneRadius + agent2.bufferZoneRadius) {
            agent1.bufferZoneColor = sf::Color::Red;
            agent2.bufferZoneColor = sf::Color::Red;
            agent1.collisionPredicted = true;
            agent2.collisionPredicted = true;

            // Implement collision avoidance: stop the slower agent
            float speed1 = std::sqrt(agent1.velocity.x * agent1.velocity.x + agent1.velocity.y * agent1.velocity.y);
            float speed2 = std::sqrt(agent2.velocity.x * agent2.velocity.x + agent2.velocity.y * agent2.velocity.y);

            // Stop the slower agent TODO: Implement corridor-based priority
            if (speed1 < speed2) {
                agent1.stop(); // Slower agent stops
            } else {
                agent2.stop(); // Slower agent stops
            }

            return true; // Collision detected
        }
    }

    return false; // No collision detected in the lookahead time frame
}

// Check for future collision between two agents with gradual slowdown
bool predictCollisionAgents_v2(Agent& agent1, Agent& agent2) {

    const float lookaheadStep = 0.2f; // Time step for predictions
    const float maxLookahead = agent1.lookAheadTime; // Maximum lookahead time

    for (float t = 0; t <= maxLookahead; t += lookaheadStep) {
        sf::Vector2f futurePos1 = agent1.getFuturePositionAtTime(t);
        sf::Vector2f futurePos2 = agent2.getFuturePositionAtTime(t);
        
        // Check if the future positions (including buffer radius) intersect
        float dx = futurePos1.x - futurePos2.x;
        float dy = futurePos1.y - futurePos2.y;
        float distance = std::sqrt(dx * dx + dy * dy);
        float combinedRadius = agent1.bufferZoneRadius + agent2.bufferZoneRadius;

        // // Early prediction with gradual slowdown
        // if (distance < combinedRadius * 2.0f) { // Start predicting earlier
        //     //float slowdownFactor = std::max(0.0f, 1.0f - (distance - combinedRadius) / combinedRadius);
        //     float slowdownFactor = 0.99999f; // Fixed slowdown factor
        //     agent1.velocity *= slowdownFactor;
        //     agent2.velocity *= slowdownFactor;
        // }

        if (distance < combinedRadius) {
            agent1.bufferZoneColor = sf::Color::Red;
            agent2.bufferZoneColor = sf::Color::Red;
            agent1.collisionPredicted = true;
            agent2.collisionPredicted = true;

            // Implement collision avoidance: stop the slower agent
            float speed1 = std::sqrt(agent1.velocity.x * agent1.velocity.x + agent1.velocity.y * agent1.velocity.y);
            float speed2 = std::sqrt(agent2.velocity.x * agent2.velocity.x + agent2.velocity.y * agent2.velocity.y);

            if (speed1 < speed2) {
                agent1.stop(); // Slower agent stops
            } else {
                agent2.stop(); // Slower agent stops
            }

            return true; // Collision detected
        }
    }

    return false; // No collision detected in the lookahead time frame
}

// Check for collision between two agents without slowdown
bool predictCollisionAgents(Agent& agent1, Agent& agent2) {

    const float lookaheadStep = 0.2f; // Time step for predictions
    const float maxLookahead = 2.0f; // Maximum lookahead time
    float speed1;
    float speed2;

    // Check for collision between two agents
    for (float t = 0; t <= maxLookahead; t += lookaheadStep) {
        sf::Vector2f futurePos1 = agent1.getFuturePositionAtTime(t);
        sf::Vector2f futurePos2 = agent2.getFuturePositionAtTime(t);

        // Check if the future positions (including buffer radius) intersect
        float dx = futurePos1.x - futurePos2.x;
        float dy = futurePos1.y - futurePos2.y;
        float distance = std::sqrt(dx * dx + dy * dy);

        if (distance < agent1.bufferZoneRadius + agent2.bufferZoneRadius) {
            agent1.bufferZoneColor = sf::Color::Red;
            agent2.bufferZoneColor = sf::Color::Red;
            agent1.collisionPredicted = true;
            agent2.collisionPredicted = true;

            // Implement collision avoidance: stop the slower agent
            speed1 = std::sqrt(agent1.velocity.x * agent1.velocity.x + agent1.velocity.y * agent1.velocity.y);
            speed2 = std::sqrt(agent2.velocity.x * agent2.velocity.x + agent2.velocity.y * agent2.velocity.y);

            // Stop the agent with lower priority or slower velocity TODO: Implement corridor-based priority
            if (agent1.priority == agent2.priority) {
                if (speed1 < speed2) {
                    agent1.stop(); // Slower agent stops
                    agent1.collisionPredicted = true;
                } else {
                    agent2.stop(); // Slower agent stops
                    agent2.collisionPredicted = true;
                }
            } else if (agent1.priority < agent2.priority) {
                agent2.stop(); // Agent 1 stops
                agent2.collisionPredicted = true;
            } else {
                agent1.stop(); // Agent 2 stops
                agent1.collisionPredicted = true;
            }

            return true; // Collision detected
        }
    }

    return false; // No collision detected in the lookahead time frame
}

// Check for future collision between an agent and an obstacle
bool predictCollisionObstacle(Agent& agent, const std::vector<Obstacle>& obstacles) {

    const float lookaheadStep = 0.2f; // Time step for predictions
    const float maxLookahead = 2.0f; // Maximum lookahead time

    for (float t = 0; t <= maxLookahead; t += lookaheadStep) {
        sf::Vector2f futurePos = agent.getFuturePositionAtTime(t);

        // Calculate agent's future bounds (including buffer radius)
        // Note: SFML 2.6.2 and prior
        // sf::FloatRect agentBounds(
        //     futurePos.x - agent.bufferZoneRadius,
        //     futurePos.y - agent.bufferZoneRadius,
        //     2 * agent.bufferZoneRadius,
        //     2 * agent.bufferZoneRadius
        // );
        sf::FloatRect agentBounds(
            {
                futurePos.x - agent.bufferZoneRadius,
                futurePos.y - agent.bufferZoneRadius
            },
            {
                2 * agent.bufferZoneRadius,
                2 * agent.bufferZoneRadius
            }
        );

        for (const Obstacle& obstacle : obstacles) {
            std::cout << "Obstacle: " << obstacle.getBounds().position.x << ", " << obstacle.getBounds().position.y << std::endl;
            std:: cout << "Agent: " << agentBounds.position.x << ", " << agentBounds.position.y << std::endl;
            if (obstacle.getBounds().findIntersection(agentBounds)) {
                agent.stop(); // or agent->adjustDirection() 
                return true; // Collision detected
            }
        }

        // Note: SFML 2.6.2 and prior
        // for (const Obstacle& obstacle : obstacles) {
        //     std::cout << "Obstacle: " << obstacle.getBounds().top << ", " << obstacle.getBounds().left << std::endl; // Error: top=y, left=x
        //     std:: cout << "Agent: " << agentBounds.top << ", " << agentBounds.left << std::endl;
        //     if (obstacle.getBounds().intersects(agentBounds)) {
        //         agent.stop(); // or agent->adjustDirection() 
        //         return true; // Collision detected
        //     }
        // }
    }
    return false; // No collision detected in the lookahead time frame
}

// Check for collision between two agents
bool agentAgentCollision(Agent& agent1, Agent& agent2) {

    float dx = agent1.position.x - agent2.position.x;
    float dy = agent1.position.y - agent2.position.y;
    float distanceSquared = dx * dx + dy * dy;

    float combinedRadius = agent1.bufferZoneRadius + agent2.bufferZoneRadius;
    float combinedRadiusSquared = combinedRadius * combinedRadius;

    if(distanceSquared < combinedRadiusSquared) {
        agent1.bufferZoneColor = sf::Color::Red;
        agent2.bufferZoneColor = sf::Color::Red;
        agent1.collisionPredicted = true;
        agent2.collisionPredicted = true;

        return true; // Collision detected
    }
    return false; // No collision detected
}

// Check for collision between two agents
bool agentAgentsCollision(Agent& agent, std::vector<Agent>& agents) {

    // Check for collision with each agent
    for(Agent& otherAgent : agents) {

        if(&otherAgent == &agent) continue; // Skip self-comparison

        // Calculate distance between agents
        float dx = agent.position.x - otherAgent.position.x;
        float dy = agent.position.y - otherAgent.position.y;
        float distanceSquared = dx * dx + dy * dy;

        // Calculate combined radius
        float combinedRadius = agent.bufferZoneRadius + otherAgent.bufferZoneRadius;
        float combinedRadiusSquared = combinedRadius * combinedRadius;

        // Collision occurs if the distance is less than the combined radius
        if(distanceSquared < combinedRadiusSquared) {
            
            return true; // Collision detected
        }
    }
    return false; // No collision detected
}

// Check for collision between an agent and an obstacle
bool agentObstaclesCollision(Agent& agent, const std::vector<Obstacle>& obstacles) {

    // Extract circle information from the Agent
    sf::Vector2f circleCenter = agent.position;
    float circleRadius = agent.bufferZoneRadius;

    // Check for collision with each obstacle
    for(const Obstacle& obstacle : obstacles) {

        // Extract rectangle information from the Obstacle
        sf::FloatRect rect = obstacle.getBounds();
    
        // Find the closest point on the rectangle to the circle's center
        // Note: SFML 2.6.2 and prior
        // float closestX = std::max(rect.left, std::min(circleCenter.x, rect.left + rect.width));
        // float closestY = std::max(rect.top, std::min(circleCenter.y, rect.top + rect.height));
        float closestX = std::max(rect.position.x, std::min(circleCenter.x, rect.position.x + rect.size.x));
        float closestY = std::max(rect.position.y, std::min(circleCenter.y, rect.position.y + rect.size.y));

        // Calculate the distance between the circle's center and the closest point
        float distanceX = circleCenter.x - closestX;
        float distanceY = circleCenter.y - closestY;
        float distanceSquared = distanceX * distanceX + distanceY * distanceY;

        // Collision occurs if the distance is less than or equal to the circle's radius
        if(distanceSquared <= circleRadius * circleRadius) {
            agent.bufferZoneColor = sf::Color::Red;
            agent.collisionPredicted = true;
            agent.stop(); // Stop the agent

            return true; // Collision detected
        }
    }
    return false; // No collision detected
}

// Check if a collision is possible between two agents
bool collisionPossible(Agent& agent1, Agent& agent2) {

    // Calculate relative velocity and position
    sf::Vector2f relativeVector = agent2.velocity - agent1.velocity;
    sf::Vector2f relativePosition = agent2.position - agent1.position;

    // Check if agents are moving towards each other (dot product)
    if (relativeVector.x * relativePosition.x + 
        relativeVector.y * relativePosition.y < 0) {

        return true;
    }
    
    return false;
}