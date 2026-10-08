#pragma once

#include <SFML/Graphics.hpp>
#include <vector>
#include <string>
#include <iostream>
#include <cmath>

#include "Logging.hpp"
#include "Utilities.hpp"

class Region {
public:

    // Structs
    struct RegionTypeAttributes {
        std::string color;
        float alpha;
        struct granularities {
            struct spatial {
                float min;
                float max;
            } spatial;
            struct temporal {
                float min;
                float max;
            } temporal;
        } granularities;
        struct privacy {
            struct k_anonymity {
                int min = 1; // Default value
            } k_anonymity;
            struct l_diversity {
                int min = 1; // Default value
            } l_diversity;
        } privacy;
    };

    Region(const RegionTypeAttributes& attributes);
    ~Region();

    RegionTypeAttributes attributes;
    std::string type;
    sf::FloatRect area;
    sf::Color colorAlpha;  // sf::Color colorAlpha = sf::Color(color.r, color.g, color.b, alpha * 255);
};