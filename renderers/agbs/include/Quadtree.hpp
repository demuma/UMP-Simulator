#pragma once

#include <SFML/Graphics.hpp>
#include <vector>
#include <unordered_set>
#include <unordered_map>
#include <functional>
#include <stdexcept>
#include <cmath>
#include <random>
#include "Agent.hpp"

// The Quadtree class encapsulates the data‐structure logic.
// Nodes store their geometry in an sf::FloatRect (left, top, width, height).
class Quadtree {
public:
    // A Node stores its bounds, pointers to its children, its unique id, and depth.
    struct Node {
        sf::FloatRect bounds; // Defines the cell's position and size.
        bool isSplit;
        Node* parent;
        Node* children[4];
        int id;    // Unique integer ID (using a Morton-code style bit‐encoding)
        int depth; // Depth level (base nodes are depth 1)
        std::vector<Agent*> agents;
        bool showCellId = false;

        // Constructor: creates a node with the given position and size.
        Node(float x, float y, float size, int id, int depth, Node* parent = nullptr);

        // Splits the node into 4 children and registers them in nodeMap.
        void split(std::unordered_map<int, Node*>& nodeMap);
        void draw(sf::RenderTexture& renderTexture, sf::Font& font);
        void draw(sf::RenderTexture& renderTexture, sf::Font& font, float scale, const sf::Vector2f& offset, bool showCellId);
    };

    // Data members
    float cellSize;
    sf::Vector2f origin;
    int maxDepth;
    std::vector<Node*> baseNodes;               // The four base cells.
    std::unordered_map<int, Node*> nodeMap;     // Maps cell IDs to nodes.
    std::vector<sf::Vector2f> positions;        // Agent positions (or any positions)
    std::vector<Agent*> agents;                 // Agents in the quadtree
    bool showCellId = false;

    // Constructor & destructor
    Quadtree(float x, float y, float cellSize, int maxDepth);
    ~Quadtree();

    // Tree management functions
    void reset(); // Undo splits without deallocating base nodes.
    void clear(); // Delete non-base nodes.

    Node* getNodeById(int id);

    // Split a cell by following a path of child indexes.
    void splitCell(int firstId, const std::vector<int>& path);
    // Start splitting from a root-based sequence (using the NW base cell).
    void splitCell(std::vector<int>& sequence);

    // A variadic overload for splitCell.
    template <typename... Args>
    void splitCell(Args... args) {
        std::vector<int> pathVec = {args...};
        if (pathVec.empty()) {
            throw std::runtime_error("No path specified for splitCell.");
        }
        // If the first argument is a valid cell ID, then use it as the start.
        if (pathVec.size() > 1 && getNodeById(pathVec[0]) != nullptr) {
            int firstId = pathVec[0];
            pathVec.erase(pathVec.begin());
            splitCell(firstId, pathVec);
        } else {
            splitCell(pathVec);
        }
    }

    // Returns the center of the cell given its id.
    sf::Vector2f getCellCenter(int id) const;

    // Returns the positon of the cell (top-left corner) given its id.
    sf::Vector2f getCellPosition(int id) const;

    // Returns the dimensions of the cell given its id. // Not yet implemented.
    sf::Vector2f getCellDimensions(int id) const;

    // Returns the IDs of neighboring cells (at the same depth or leaves).
    std::vector<int> getNeighboringCells(int id);

    // Given a position, returns the smallest cell (leaf) that contains it.
    int getNearestCell(sf::Vector2f position);

    // Computes a cell id for a given position (using the maxDepth).
    int makeCell(sf::Vector2f position);

    // Compute the split sequence (list of child indexes) for a cell id.
    std::vector<int> getSplitSequence(int cellID);

    // Compute split sequences for a set of positions.
    std::vector<std::vector<int>> getSplitSequences(const std::vector<sf::Vector2f>& positions);
    
    // Split the quadtree according to the current positions.
    void splitFromPositions();
    void splitFromCellIds(std::unordered_set<int> seq);

    // Utility functions to generate and update positions.
    void generatePositions(int number);  // DELETE
    void movePositionsRight(float x);    // DELETE

    // (A placeholder for any per-frame update logic.)
    void update();  // DELETE

    // Draw the quadtree structure and the positions.
    void draw(sf::RenderTexture& renderTexture, sf::Font& font);  // MOVE TO RENDERER

    void draw(sf::RenderTexture& renderTexture, sf::Font& font, float scale, const sf::Vector2f& offset);

    // Draw the positions as red circles.
    void drawPositions(sf::RenderTexture& renderTexture, const std::vector<sf::Vector2f>& positions);  // DELETE

    int addAgent(Agent* agent);

    // Debug: prints the children of a node.
    void printChildren(int id);

    // Custom hash function for sf::Vector2f so it can be used in unordered_map.
    struct Vector2fHash {
        std::size_t operator()(const sf::Vector2f& v) const;
    };

private:
    // Returns the depth of a cell based on the number of bits in its id.
    int getDepth(int id) const;
    // Helper functions for Morton-code encoding/decoding.
    int mortonEncode(int row, int col) const;
    std::pair<int, int> mortonDecode(int id) const;
    // Recursively splits cells based on a given path.
    void splitRecursive(Node* node, const std::vector<int>& path, int pathIndex,
                        std::unordered_map<int, Node*>& nodeMap);
};