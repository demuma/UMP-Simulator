#pragma once

#include "AggregationHistory.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <memory>
#include <optional>
#include <stdexcept>

namespace ump {

// A bounded spatial retirement frontier, independent of retained sample history.
// Four depth-1 roots cover the grid. Uniform subtrees occupy one node; only distinct
// cell clocks create branches. Immutable nodes let pending publications retain an
// allocation-free commit snapshot without copying the whole frontier or past releases.
class CellWindowLedger {
public:
    explicit CellWindowLedger(GridCoverage coverage, std::size_t maximumNodes = 16384)
        : grid(coverage), maxNodes(maximumNodes) {
        historyCell(grid, 12, 1);
        if (maxNodes < 4) throw std::invalid_argument("Cell retirement ledger needs four root nodes");
        const auto initial = std::make_shared<const Node>(AggregationTime{0});
        roots.fill(initial);
    }

    bool canRetire(const CellGeometry& cell, AggregationTime startMs, AggregationTime endMs) const {
        if (startMs < 0 || endMs <= startMs) { validate(cell); return false; }
        const auto current = retiredThrough(cell);
        return current && *current == startMs;
    }

    // Strong exception guarantee. Path-copying allocates O(depth) nodes; unchanged
    // branches are shared. Budget/allocation failure leaves every frontier unchanged.
    void retire(const CellGeometry& cell, AggregationTime startMs, AggregationTime endMs) {
        if (!canRetire(cell, startMs, endMs))
            throw std::invalid_argument("Cell retirement requires one uniform unretired interval");
        const auto root = static_cast<std::size_t>((cell.id >> (2 * (cell.depth - 1))) - 12);
        auto replacement = replace(roots[root], cell, 1, endMs);
        const auto unchanged = nodeCount() - roots[root]->nodeCount;
        if (replacement->nodeCount > maxNodes - unchanged)
            throw std::length_error("Cell retirement ledger node budget exceeded");
        roots[root] = std::move(replacement);
    }

    // A mixed subtree has no single frontier and cannot be retired as a whole yet.
    std::optional<AggregationTime> retiredThrough(const CellGeometry& cell) const {
        validate(cell);
        const auto root = static_cast<std::size_t>((cell.id >> (2 * (cell.depth - 1))) - 12);
        auto node = roots[root];
        for (int depth = 1; depth < cell.depth && !node->through; ++depth) {
            const auto quadrant = (cell.id >> (2 * (cell.depth - depth - 1))) & 3;
            node = node->children[quadrant];
        }
        return node->through;
    }

    AggregationTime minimumRetiredThrough() const {
        auto result = roots[0]->minimumThrough;
        for (std::size_t i = 1; i < roots.size(); ++i)
            result = std::min(result, roots[i]->minimumThrough);
        return result;
    }
    // Logical nodes bound the complete frontier even when identical immutable leaves
    // happen to share one allocation. One pending retirement adds O(depth) allocations.
    std::size_t nodeCount() const {
        std::size_t total = 0;
        for (const auto& root : roots) total += root->nodeCount;
        return total;
    }

private:
    struct Node {
        using Pointer = std::shared_ptr<const Node>;
        std::optional<AggregationTime> through;
        std::array<Pointer,4> children{};
        std::size_t nodeCount = 1;
        AggregationTime minimumThrough;
        explicit Node(AggregationTime value) : through(value), minimumThrough(value) {}
        explicit Node(std::array<Pointer,4> descendants) : children(std::move(descendants)),
            minimumThrough(children[0]->minimumThrough) {
            for (const auto& child : children) {
                nodeCount += child->nodeCount;
                minimumThrough = std::min(minimumThrough, child->minimumThrough);
            }
        }
    };
    GridCoverage grid;
    std::size_t maxNodes;
    std::array<Node::Pointer,4> roots;

    static Node::Pointer replace(const Node::Pointer& node, const CellGeometry& cell,
        int depth, AggregationTime endMs) {
        if (depth == cell.depth) return std::make_shared<const Node>(endMs);
        auto children = node->children;
        if (node->through) children.fill(node);
        const auto quadrant = (cell.id >> (2 * (cell.depth - depth - 1))) & 3;
        children[quadrant] = replace(children[quadrant], cell, depth + 1, endMs);
        const auto through = children[0]->through;
        if (through && children[1]->through == through && children[2]->through == through
            && children[3]->through == through)
            return children[0]; // Equal clocks compact back into one uniform node.
        return std::make_shared<const Node>(std::move(children));
    }

    void validate(const CellGeometry& cell) const {
        const auto canonical = historyCell(grid, cell.id, cell.depth);
        const auto close = [&](double actual, double expected) {
            const auto tolerance = std::min(std::ldexp(grid.width, -grid.leafDepth) * 1e-4,
                1e-6 * std::max({1.0, std::abs(actual), std::abs(expected)}));
            return std::isfinite(actual) && std::abs(actual - expected) <= tolerance;
        };
        if (!close(cell.x, canonical.x) || !close(cell.y, canonical.y)
            || !close(cell.width, canonical.width) || !close(cell.height, canonical.height))
            throw std::invalid_argument("Cell retirement geometry differs from its ID/depth");
    }
};
} // namespace ump
