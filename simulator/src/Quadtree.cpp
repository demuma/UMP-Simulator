#include <iostream>
#include <algorithm>
#include <functional>
#include <stdexcept>
#include <cmath>

#include "../include/Quadtree.hpp"
#include "../include/Logging.hpp"

// ========================
// Node Member Functions
// ========================

Quadtree::Node::Node(float x, float y, float size, int id, int depth, Node* parent)
    : bounds({x, y}, {size, size}), id(id), depth(depth), parent(parent), isSplit(false)
{
    // Initialize all child pointers to nullptr.
    children[0] = children[1] = children[2] = children[3] = nullptr;
}

void Quadtree::Node::split(std::unordered_map<int, Node*>& nodeMap) {
    if (isSplit)
        return;

    float x = bounds.position.x;
    float y = bounds.position.y;
    float size = bounds.size.x / 2.0f;

    DEBUG_MSG("Generated new parent node at position: (" << bounds.position.x << ", " << bounds.position.y << ")");
    DEBUG_MSG("Parent size: " << bounds.size.x << ", " << bounds.size.y);
    DEBUG_MSG("Parent id: " << id);

    // Create 4 children; child indexes are computed via bit shifts.
    for (int i = 0; i < 2; ++i) {
        for (int j = 0; j < 2; ++j) {
            int childIndex = (i << 1) | j;
            int childId = (id << 2) | childIndex;
            Node* child = new Node(x + j * size, y + i * size, size, childId, depth + 1, this);
            children[childIndex] = child;
            nodeMap[childId] = child;
            DEBUG_MSG("Generated new child node at position: (" << child->bounds.position.x << ", " << child->bounds.position.y << ")");
            DEBUG_MSG("Child size: " << child->bounds.size.x << ", " << child->bounds.size.y);
            DEBUG_MSG("Child id: " << childId);
        }
    }
    isSplit = true;
}

void Quadtree::Node::draw(sf::RenderWindow& window, sf::Font& font) {
    sf::RectangleShape shape;
    shape.setSize(sf::Vector2f(bounds.size.x, bounds.size.y));
    shape.setPosition({bounds.position.x, bounds.position.y});
    shape.setFillColor(sf::Color::Transparent);
    shape.setOutlineThickness(1);
    shape.setOutlineColor(sf::Color::Black);

    window.draw(shape);
    bool drawText = false;

    if(drawText){
        sf::Text text(font, "", 24);
        text.setFont(font);
        text.setString(std::to_string(id));
        text.setCharacterSize(9);
        text.setFillColor(sf::Color::Black);

        sf::FloatRect textBounds = text.getLocalBounds();
        text.setPosition({
            bounds.position.x + bounds.size.x / 2 - textBounds.size.x / 2,
            bounds.position.y + bounds.size.y / 2 - textBounds.size.y / 2
        });
        window.draw(text);
    }

    // **Recursively draw children if the node is split**
    if (isSplit) {
        for (int i = 0; i < 4; ++i) {
            if (children[i])
                children[i]->draw(window, font);
        }
    }
}

void Quadtree::Node::draw(sf::RenderWindow& window, sf::Font& font, float scale, const sf::Vector2f& offset, bool showCellId) {
    sf::RectangleShape shape;
    // Scale the size and offset the position
    shape.setSize(sf::Vector2f(bounds.size.x * scale, bounds.size.y * scale));
    shape.setPosition({bounds.position.x * scale + offset.x, bounds.position.y * scale + offset.y});
    shape.setFillColor(sf::Color::Transparent);
    shape.setOutlineThickness(1);
    shape.setOutlineColor(sf::Color::Black);
    window.draw(shape);
    
    // Draw the node id text (also apply scaling and offset)
    if(this->showCellId){
        sf::Text text(font, std::to_string(id), 0.5 * scale); // Initialize text with font, string and character size
        text.setFillColor(sf::Color::Black);
        sf::FloatRect textBounds = text.getLocalBounds();
        text.setPosition({
            bounds.position.x * scale + offset.x + (bounds.size.x * scale - textBounds.size.x) / 2,
            bounds.position.y * scale + offset.y + (bounds.size.y * scale - textBounds.size.y) / 2
        });
        window.draw(text);
    }

    // Recursively draw children nodes
    if (isSplit) {
        for (int i = 0; i < 4; ++i) {
            if (children[i])
            // children[i]->drawText = false;
            children[i]->draw(window, font, scale, offset, showCellId);
        }
    }
}

void Quadtree::Node::draw(sf::RenderWindow& window, sf::Font& font, float scale, const sf::Vector2f& offset) {
    sf::RectangleShape shape;
    // Scale the size and offset the position
    shape.setSize(sf::Vector2f(bounds.size.x * scale, bounds.size.y * scale));
    shape.setPosition({bounds.position.x * scale + offset.x, bounds.position.y * scale + offset.y});
    shape.setFillColor(sf::Color::Transparent);
    shape.setOutlineThickness(1);
    shape.setOutlineColor(sf::Color::Black);
    window.draw(shape);
    
    // Draw the node id text (also apply scaling and offset)
    if(showCellId){
        sf::Text text(font, std::to_string(id), 0.5 * scale); // Initialize text with font, string and character size
        text.setFillColor(sf::Color::Black);
        sf::FloatRect textBounds = text.getLocalBounds();
        text.setPosition({
            bounds.position.x * scale + offset.x + (bounds.size.x * scale - textBounds.size.x) / 2,
            bounds.position.y * scale + offset.y + (bounds.size.y * scale - textBounds.size.y) / 2
        });
        window.draw(text);
    }

    // Recursively draw children nodes
    if (isSplit) {
        for (int i = 0; i < 4; ++i) {
            if (children[i])
            // children[i]->drawText = false;
            children[i]->draw(window, font, scale, offset);
        }
    }
}

void Quadtree::draw(sf::RenderWindow& window, sf::Font& font, float scale, const sf::Vector2f& offset) {
    for (Node* n : baseNodes){
        n->draw(window, font, scale, offset, showCellId);
    }
}

void Quadtree::drawPositions(sf::RenderWindow& window, const std::vector<sf::Vector2f>& positions) {
    float circleSize = 4;
    sf::CircleShape circle(circleSize);
    circle.setFillColor(sf::Color::Red);
    for (const sf::Vector2f& pos : positions) {
        sf::Vector2f newPos = sf::Vector2f(pos.x, pos.y);
        newPos -= sf::Vector2f(circleSize, circleSize);
        circle.setPosition(newPos);
        window.draw(circle);
    }
}

// ========================
// Quadtree Member Functions
// ========================

// TO-DO: Add quadtree offset to the node bounds!!
Quadtree::Quadtree(float x, float y, float cellSize, int maxDepth)
    : cellSize(cellSize), maxDepth(maxDepth), origin(x, y)
{
    // Initialize the 4 base cells using 4-bit Morton codes.
    for (int i = 0; i < 2; ++i) {
        for (int j = 0; j < 2; ++j) {
            int baseNodeId = 0b1100 | mortonEncode(i, j);
            Node* n = new Node(origin.x + j * cellSize, origin.y + i * cellSize, cellSize, baseNodeId, 1);
            baseNodes.push_back(n);
            nodeMap[baseNodeId] = n;
        }
    }
}

Quadtree::~Quadtree() {
    // Recursively delete all nodes.
    std::function<void(Node*)> deleteNodeRecursive = [&](Node* node) {
        if (node != nullptr) {
            for (int i = 0; i < 4; ++i)
                deleteNodeRecursive(node->children[i]);
            delete node;
        }
    };

    for (Node* baseNode : baseNodes)
        deleteNodeRecursive(baseNode);

    nodeMap.clear();
    baseNodes.clear();
}

void Quadtree::reset() {
    // Recursively remove splits (but do not delete the base nodes).
    std::function<void(Node*)> resetNodeRecursive = [&](Node* node) {
        if (node != nullptr) {
            // Clear agents stored in this node
            node->agents.clear();
            for (int i = 0; i < 4; ++i) {
                if (node->children[i]) {
                    resetNodeRecursive(node->children[i]);
                    node->children[i] = nullptr;
                }
            }
            node->isSplit = false;
        }
    };

    for (Node* baseNode : baseNodes)
        resetNodeRecursive(baseNode);

    nodeMap.clear();
    for (Node* baseNode : baseNodes)
        nodeMap[baseNode->id] = baseNode;
}

void Quadtree::clear() {
    // Delete all non-base nodes.
    std::function<void(Node*)> deleteNodeRecursive = [&](Node* node) {
        if (node != nullptr) {
            // Clear agents stored in this node
            node->agents.clear();
            for (int i = 0; i < 4; ++i) {
                deleteNodeRecursive(node->children[i]);
                node->children[i] = nullptr;
            }
            delete node;
        }
    };

    for (Node* baseNode : baseNodes) {
        for (int i = 0; i < 4; ++i) {
            deleteNodeRecursive(baseNode->children[i]);
            baseNode->children[i] = nullptr;
        }
        baseNode->isSplit = false;
    }

    for (auto it = nodeMap.begin(); it != nodeMap.end();) {
        if (std::find(baseNodes.begin(), baseNodes.end(), it->second) == baseNodes.end())
            it = nodeMap.erase(it);
        else
            ++it;
    }
}

Quadtree::Node* Quadtree::getNodeById(int id) {
    auto it = nodeMap.find(id);
    return (it != nodeMap.end()) ? it->second : nullptr;
}

void Quadtree::splitCell(int firstId, const std::vector<int>& path) {
    Node* currentNode = getNodeById(firstId);
    if (!currentNode) {
        std::cerr << "Error: starting cell ID not found.\n";
        return;
    }
    splitRecursive(currentNode, path, 0, nodeMap);
}

void Quadtree::splitCell(std::vector<int>& sequence) {
    if (baseNodes.empty()) {
        std::cerr << "Error: Quadtree not initialized.\n";
        return;
    }
    auto baseNode = baseNodes[sequence[0]];

    if (!sequence.empty()) {
        sequence.erase(sequence.begin());
    }

    // splitRecursive(baseNodes[0], sequence, 0, nodeMap);
    splitRecursive(baseNode, sequence, 0, nodeMap);
}

sf::Vector2f Quadtree::getCellCenter(int id) const {
    auto it = nodeMap.find(id);
    if (it == nodeMap.end())
        throw std::runtime_error("Cell not found.");
    Node* currentNode = it->second;
    float x = currentNode->bounds.position.x;
    float y = currentNode->bounds.position.y;
    float size = currentNode->bounds.size.x;
    return sf::Vector2f(x + size / 2, y + size / 2);
}

sf::Vector2f Quadtree::getCellPosition(int id) const {
    auto it = nodeMap.find(id);
    if (it == nodeMap.end())
        throw std::runtime_error("Cell not found.");
    Node* currentNode = it->second;
    float x = currentNode->bounds.position.x;
    float y = currentNode->bounds.position.y;
    return sf::Vector2f(x, y);
}

sf::Vector2f Quadtree::getCellDimensions(int id) const {
    auto it = nodeMap.find(id);
    if (it == nodeMap.end())
        throw std::runtime_error("Cell not found.");
    Node* currentNode = it->second;
    return currentNode->bounds.size;
}

std::vector<int> Quadtree::getNeighboringCells(int id) {
    std::vector<int> neighbors;
    Node* targetNode = getNodeById(id);
    if (!targetNode) {
        std::cerr << "Error: Target cell for neighbor search not found.\n";
        return neighbors;
    }
    int targetDepth = getDepth(id);

    // Recursively collect neighbors.
    std::function<void(Node*, int)> findNeighborsRecursively = [&](Node* node, int depth) {
        if (!node || depth > targetDepth)
            return;
        if (depth == targetDepth || !node->isSplit) {
            neighbors.push_back(node->id);
            return;
        }
        if (node->isSplit) {
            for (int i = 0; i < 4; ++i)
                if (node->children[i])
                    findNeighborsRecursively(node->children[i], depth + 1);
        }
    };

    // Attempt to find neighbors in a given direction.
    std::function<void(Node*, int, int)> findNeighborsInDirection = [&](Node* node, int dx, int dy) {
        if (!node)
            return;
        while (node->parent) {
            int parentId = node->parent->id;
            int nodeRow, nodeCol;
            std::tie(nodeRow, nodeCol) = mortonDecode(node->id);
            int parentRow, parentCol;
            std::tie(parentRow, parentCol) = mortonDecode(parentId);

            int depthDiff = getDepth(node->id) - getDepth(parentId);

            if ((nodeRow + dy * pow(2, depthDiff)) >= parentRow &&
                (nodeRow + dy * pow(2, depthDiff)) < parentRow + pow(2, depthDiff + 1) &&
                (nodeCol + dx * pow(2, depthDiff)) >= parentCol &&
                (nodeCol + dx * pow(2, depthDiff)) < parentCol + pow(2, depthDiff)) {
                Node* neighbor = nullptr;
                int childIndex;
                if (dx == 0 && dy == -1)         childIndex = (node == node->parent->children[2]) ? 0 : 1;
                else if (dx == 1 && dy == -1)    childIndex = 2;
                else if (dx == 1 && dy == 0)     childIndex = (node == node->parent->children[0]) ? 1 : 3;
                else if (dx == 1 && dy == 1)     childIndex = 0;
                else if (dx == 0 && dy == 1)     childIndex = (node == node->parent->children[0]) ? 2 : 3;
                else if (dx == -1 && dy == 1)    childIndex = 1;
                else if (dx == -1 && dy == 0)    childIndex = (node == node->parent->children[1]) ? 0 : 2;
                else if (dx == -1 && dy == -1)   childIndex = 3;
                neighbor = node->parent->children[childIndex];

                if (neighbor)
                    findNeighborsRecursively(neighbor, getDepth(neighbor->id));
                break;
            }
            node = node->parent;
        }
    };

    int dx[] = {0, 1, 1, 0, -1, -1, -1, 0};
    int dy[] = {-1, -1, 0, 1, 1, 1, 0, -1};

    for (int i = 0; i < 8; ++i)
        findNeighborsInDirection(targetNode, dx[i], dy[i]);

    std::sort(neighbors.begin(), neighbors.end());
    neighbors.erase(std::unique(neighbors.begin(), neighbors.end()), neighbors.end());
    return neighbors;
}

int Quadtree::getNearestCell(sf::Vector2f position) {
    // Find which base cell contains the position.
    sf::Vector2f relativePos = position - origin;
    int col = static_cast<int>(relativePos.x / cellSize);
    int row = static_cast<int>(relativePos.y / cellSize);
    col = std::max(0, std::min(col, 1));
    row = std::max(0, std::min(row, 1));

    int baseId = mortonEncode(row, col);
    Node* currentNode = getNodeById(baseId);
    if (!currentNode) {
        std::cerr << "Error: Base cell not found during nearest cell search.\n";
        return -1;
    }
    // Traverse down the tree.
    while (currentNode->isSplit) {
        float midX = currentNode->bounds.position.x + currentNode->bounds.size.x / 2;
        float midY = currentNode->bounds.position.y + currentNode->bounds.size.y / 2;
        int childIndex = 0;
        if (position.y >= midY)
            childIndex |= 2;
        if (position.x >= midX)
            childIndex |= 1;
        Node* nextNode = currentNode->children[childIndex];
        if (!nextNode) {
            std::cerr << "Error: Child cell not found during nearest cell search.\n";
            return -1;
        }
        currentNode = nextNode;
    }
    return currentNode->id;
}
// TO-DO: Don't make cell when position is outside the grid!!
int Quadtree::makeCell(sf::Vector2f position) {
    float currentCellSize = cellSize * 2.0f; // Root cell size
    sf::Vector2f currentCenter(origin.x + currentCellSize / 2, origin.y + currentCellSize / 2);
    int cellID = 0b11; // Start with root cell ID (3)

    for (int i = 0; i < maxDepth; ++i) {
        cellID <<= 2; // Shift left by 2 bits.
        currentCellSize /= 2.0f;

        if (position.y >= currentCenter.y) {
            cellID += 2;
            currentCenter.y += currentCellSize / 2;
        } else {
            currentCenter.y -= currentCellSize / 2;
        }
        if (position.x >= currentCenter.x) {
            cellID += 1;
            currentCenter.x += currentCellSize / 2;
        } else {
            currentCenter.x -= currentCellSize / 2;
        }
    }
    return cellID;
}

std::vector<int> Quadtree::getSplitSequence(int cellID) {
    std::vector<int> splitSequence;
    for (int i = 0; i < maxDepth - 1; ++i)
        splitSequence.push_back((cellID >> (2 * (maxDepth - i - 1))) & 3);
    return splitSequence;
}

std::vector<std::vector<int>> Quadtree::getSplitSequences(const std::vector<sf::Vector2f>& positions) {
    std::vector<std::vector<int>> splitSequences;
    std::unordered_map<sf::Vector2f, int, Vector2fHash> positionToCellID;

    for (const auto& pos : positions) {
        // Check if the position is within the grid bounds.
        if (pos.x < origin.x || pos.x >= origin.x + cellSize * 2 ||
            pos.y < origin.y || pos.y >= origin.y + cellSize * 2)
        {
            ERROR_MSG("Error: Position (" << pos.x << ", " << pos.y 
                      << ") outside the grid bounds.");
            continue;
        }
        
        // Compute cell ID once for each unique position.
        auto it = positionToCellID.find(pos);
        if (it == positionToCellID.end()) {
            int cellID = makeCell(pos);
            positionToCellID[pos] = cellID;
            splitSequences.push_back(getSplitSequence(cellID));
        } else {
            splitSequences.push_back(getSplitSequence(it->second));
        }
    }

    // Remove duplicate sequences.
    std::sort(splitSequences.begin(), splitSequences.end());
    splitSequences.erase(std::unique(splitSequences.begin(), splitSequences.end()), splitSequences.end());

    return splitSequences;
}

void Quadtree::splitFromPositions() {
    if (!positions.empty()) {
        std::vector<std::vector<int>> splitSequences = getSplitSequences(positions);
        for (const auto& seq : splitSequences) {

            // Note: splitCell expects a non-const reference.
            splitCell(const_cast<std::vector<int>&>(seq));
        }
    } else {
        std::cerr << "Error: No positions provided for split.\n";
    }
}

void Quadtree::splitFromCellIds(std::unordered_set<int> cellIds) {

    for (const auto& cellId: cellIds) {
        auto splitSequence = getSplitSequence(cellId);
        // std::cout << "Split sequence for cell " << cellId << ": ";
        // for (const auto& morton : splitSequence) {
        //     std::cout << morton << " ";
        // }
        // std::cout << std::endl;
        std::vector<std::vector<int>> splitSequences;
        splitSequences.push_back(splitSequence);

        // Split the cells in the adaptive grid
        for(const auto& seq : splitSequences) {
            
            splitCell(seq);
        }
    }
}

void Quadtree::generatePositions(int number) {
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<> dis(0.0, cellSize);
    for (int i = 0; i < number; ++i)
        positions.push_back(sf::Vector2f(dis(gen), dis(gen)));
}

void Quadtree::movePositionsRight(float x) {
    for (auto& pos : positions) {
        pos.x += x;
        if (pos.x >= cellSize * 2 + origin.x)
            pos.x -= cellSize * 2 + origin.x;
    }
}

// void Quadtree::updateCell() {
//     // Placeholder for update logic.
//     for (sf::Vector2f position : positions) {
//         int cellId = getNearestCell(position);
//         Node* targetNode = getNodeById(cellId);
//         // (Update logic can be added here.)
//     }
// }

// Alternative to reset tree due to cell being aggregated
void Quadtree::update() {
    
}

void Quadtree::printChildren(int id) {
    Node* targetNode = getNodeById(id);
    if (!targetNode) {
        std::cout << "Children of cell " << id << ": Cell not found.\n";
        return;
    }
    if (!targetNode->isSplit) {
        std::cout << "Children of cell " << id << ": not split.\n";
        return;
    }
    std::function<void(Node*, int)> printChildrenRecursive = [&](Node* node, int depth) {
        if (!node)
            return;
        for (int i = 0; i < depth; ++i)
            std::cout << "  ";
        std::cout << "- " << node->id << "\n";
        if (node->isSplit) {
            for (int i = 0; i < 4; ++i)
                printChildrenRecursive(node->children[i], depth + 1);
        }
    };
    std::cout << "Children of cell " << id << ":\n";
    for (int i = 0; i < 4; ++i) {
        if (targetNode->children[i])
            printChildrenRecursive(targetNode->children[i], 1);
    }
}

// Add agent to the grid
int Quadtree::addAgent(Agent* agent) {

    int cellId = getNearestCell(agent->position);
    
    // Add agent to node with cellId
    Node* node = getNodeById(cellId);
    if (node) {
        node->agents.push_back(agent);
    }

    return cellId;
}

// ========================
// Private Helper Functions
// ========================

int Quadtree::getDepth(int id) const {
    int tempId = id;
    int depth = 0;
    while (tempId > 0) {
        tempId >>= 2;
        ++depth;
    }
    return depth - 1; // Base cells are depth 1.
}

int Quadtree::mortonEncode(int row, int col) const {
    int morton = 0b1100; // Start with "11" shifted left by 2.
    morton |= (col & 1) << 0;
    morton |= (row & 1) << 1;
    return morton;
}

std::pair<int, int> Quadtree::mortonDecode(int id) const {
    int row = 0, col = 0;
    id >>= 2; // Remove the initial "11"
    col |= (id & 1) << 0;
    row |= ((id >> 1) & 1) << 0;
    return {row, col};
}

void Quadtree::splitRecursive(Node* node, const std::vector<int>& path, int pathIndex,
                              std::unordered_map<int, Node*>& nodeMap) {
    if (!node)
        return;
    if (pathIndex == path.size()) {
        if (!node->isSplit)
            node->split(nodeMap);
        return;
    }
    if (!node->isSplit)
        node->split(nodeMap);
    int childIndex = path[pathIndex];
    if (childIndex < 0 || childIndex > 3) {
        std::cerr << "Error: Invalid child index in path.\n";
        return;
    }
    splitRecursive(node->children[childIndex], path, pathIndex + 1, nodeMap);
}

// ========================
// Vector2fHash Implementation
// ========================

std::size_t Quadtree::Vector2fHash::operator()(const sf::Vector2f& v) const {
    std::size_t h1 = std::hash<float>()(v.x);
    std::size_t h2 = std::hash<float>()(v.y);
    return h1 ^ (h2 << 1);
}