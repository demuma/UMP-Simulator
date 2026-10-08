#pragma once

#include <random>
#include <algorithm>

#include "Logging.hpp"

class PerlinNoise {
public:
    PerlinNoise(unsigned int seed = std::default_random_engine::default_seed); // Constructor
    double noise(double x, double y, double z);

private:
    std::vector<int> p;
    double fade(double t);
    double lerp(double t, double a, double b);
    double grad(int hash, double x, double y, double z);
};