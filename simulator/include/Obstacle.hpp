#pragma once

#include <SFML/Graphics.hpp>

#include "Logging.hpp"

/*************************************/
/********** OBSTACLES CLASS **********/
/*************************************/

// Obstacle class
class Obstacle {
public:
    Obstacle(sf::FloatRect bounds, sf::Color color = sf::Color::Black);

    sf::FloatRect getBounds() const { return bounds; }
    sf::Color getColor() const { return color; }

private:
    sf::FloatRect bounds;
    sf::Color color;
};