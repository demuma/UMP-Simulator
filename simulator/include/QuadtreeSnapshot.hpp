#pragma once

#include <SFML/Graphics.hpp>
#include <memory>
#include <array>

namespace QuadtreeSnapshot { // Namespace to avoid name clashes

struct Node {
    sf::FloatRect bounds; // Defines the cell's position and size.
    bool isSplit;
    std::array<std::shared_ptr<Node>, 4> children; // Array of shared pointers to children

    // Constructor
    Node(sf::FloatRect bounds);
};

} // namespace QuadtreeSnapshot