#include "../include/QuadtreeSnapshot.hpp"

namespace QuadtreeSnapshot {

Node::Node(sf::FloatRect bounds) : bounds(bounds), isSplit(false) {
    children.fill(nullptr); // Initialize children to nullptr
}

} // namespace QuadtreeSnapshot