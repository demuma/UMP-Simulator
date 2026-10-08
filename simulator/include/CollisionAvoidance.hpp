#pragma once

#include "../include/Agent.hpp"
#include "../include/Obstacle.hpp"

// Function declaration
bool predictCollisionAgents_v1(Agent& agent1, Agent& agent2);
bool predictCollisionAgents_v2(Agent& agent1, Agent& agent2);
bool predictCollisionAgents(Agent& agent1, Agent& agent2);
// bool predictCollisionObstacle(Agent& agent, const std::vector<Obstacle>& obstacles);
bool agentAgentCollision(Agent& agent1, Agent& agent2);
bool agentAgentsCollision(Agent& agent, std::vector<Agent>& agents);
// bool agentObstaclesCollision(Agent& agent, const std::vector<Obstacle>& obstacles);
bool collisionPossible(Agent& agent1, Agent& agent2);