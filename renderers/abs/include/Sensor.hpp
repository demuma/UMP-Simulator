#pragma once

#include <SFML/Graphics.hpp>
#include <iostream>

class Sensor {
public:
    Sensor();
    ~Sensor();
    std::string sensorID;
    sf::Vector2f position;
    float frameRate;
    sf::FloatRect detectionArea;
    std::string databaseName;
    std::string collectionName;
    std::string type;
    sf::Color color;
    int alpha;
    float cellSize;
    bool showGrid = false;
};