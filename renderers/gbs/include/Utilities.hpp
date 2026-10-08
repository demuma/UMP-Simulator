#pragma once

#include <SFML/Graphics.hpp>
#include <iostream>
#include <iomanip>
#include <unordered_map>
#include <random>
#include <chrono>
#include <ctime>
#include <uuid/uuid.h>
#include <algorithm>
#include <bsoncxx/types.hpp>
#include <sstream>
#include <cmath>


/*******************************/
/********** UTILITIES **********/
/*******************************/

std::string generateUUID();
std::string generateISOTimestamp();
std::string generateISOTimestampString(const std::chrono::system_clock::time_point& timestamp);
bsoncxx::types::b_date generateBsonDate(const std::string& dateTimeString);
std::chrono::system_clock::time_point generateISOTimestamp(sf::Time simulationWallTime, const std::string& dateTimeString);
float generateRandomNumberFromTND(float mean, float stddev, float min, float max);
sf::Vector2f generateRandomVelocityVector(float mu, float sigma, float min, float max);
// std::string generateISOTimestamp(sf::Time simulationWallTime);
// Structure to hash a 2D vector for use in unordered_map
struct Vector2iHash {
    std::size_t operator()(const sf::Vector2i& v) const {
        std::hash<int> hasher;
        return hasher(v.x) ^ (hasher(v.y) << 1); // Combine hash values of x and y
    }
};
sf::Color stringToColor(std::string colorStr);