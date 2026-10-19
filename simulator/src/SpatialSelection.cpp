#include "SpatialSelection.hpp"
#include <algorithm>
#include <functional>
#include <cmath>
#include <map>
#include <set>
#include <stdexcept>

namespace ump {
namespace {
bool contains(const CellGeometry& parent, const CellGeometry& child) {
    return parent.depth <= child.depth &&
        (child.id >> (2 * (child.depth - parent.depth))) == parent.id;
}
}

const char* temporalActionName(TemporalAction action) {
    switch (action) {
        case TemporalAction::EvaluateFinest: return "evaluate_finest";
        case TemporalAction::CoarsenSpatially: return "coarsen_spatially";
        case TemporalAction::ExtendWindow: return "extend_window";
        case TemporalAction::CoordinationHold: return "coordination_hold";
        case TemporalAction::RequestHandoff: return "handoff_requested";
        case TemporalAction::Finalize: return "finalize";
    }
    throw std::invalid_argument("Unknown temporal action");
}

SpatialSelector::SpatialSelector(AggregationConfig settings, SpatialSelectionConfig bounds)
    : config(std::move(settings)), limits(bounds) {
    historyCell(config.coverage, 12, 1); // Validate the supported data-tree geometry.
    if (!config.history || limits.minDepth < 1 || limits.minDepth > config.coverage.leafDepth
        || !limits.maxEvaluations)
        throw std::invalid_argument("Spatial selection requires history, valid min_depth and a positive evaluation budget");
}

SpatialSelection SpatialSelector::select(const AggregationCandidate& finest,
    const AggregationHistory& history, const MetricEvaluator& evaluator) {
    auto result = propose(finest, history, evaluator);
    commit(result);
    return result;
}

SpatialSelection SpatialSelector::propose(const AggregationCandidate& finest,
    const AggregationHistory& history, const MetricEvaluator& evaluator) const {
    const auto& g = finest.grid;
    const auto& expected = config.coverage;
    if (finest.runId != config.runId || finest.sensorId != config.sensorId
        || finest.applicationId != config.applicationId || g.x != expected.x || g.y != expected.y
        || g.width != expected.width || g.height != expected.height || g.leafDepth != expected.leafDepth
        || (previousEnd && finest.startMs != *previousEnd))
        throw std::invalid_argument("Spatial selection requires one stream and contiguous, non-repeated windows");

    if (finest.cells.size() > limits.maxEvaluations)
        throw std::length_error("Spatial selection evaluation budget exceeded");
    auto evaluated = evaluator.evaluate(finest, finest.closedAtMs);
    SpatialSelection result{finest, evaluated, finest, evaluated, {}, {}, limits.minDepth};
    result.candidate.cells.clear();
    // Build only paths that contain observed support, not an exponential full tree.
    std::set<std::pair<int, int>> occupied;
    std::set<int> domains;
    std::map<int, SpatialAttempt> cache;
    for (std::size_t i = 0; i < finest.cells.size(); ++i) {
        const auto& cell = finest.cells[i];
        if (cell.cell.depth != g.leafDepth)
            throw std::invalid_argument("Spatial selector input must contain finest-depth cells");
        const auto canonical = historyCell(g, cell.cell.id, cell.cell.depth);
        const auto close = [&](double a, double b) {
            const double tolerance = std::min(std::ldexp(g.width, -g.leafDepth) * 1e-4,
                1e-6 * std::max({1.0, std::abs(a), std::abs(b)}));
            return std::abs(a - b) <= tolerance;
        };
        if (!close(canonical.x, cell.cell.x) || !close(canonical.y, cell.cell.y)
            || !close(canonical.width, cell.cell.width) || !close(canonical.height, cell.cell.height))
            throw std::invalid_argument("Spatial selector input geometry differs from cell ID");
        if (cache.size() >= limits.maxEvaluations)
            throw std::length_error("Spatial selection evaluation budget exceeded");
        cache.emplace(cell.cell.id, SpatialAttempt{cell, evaluated.cells[i]});
        for (int depth = g.leafDepth; depth >= limits.minDepth; --depth) {
            const int id = cell.cell.id >> (2 * (g.leafDepth - depth));
            occupied.emplace(id, depth);
            if (depth == limits.minDepth) domains.insert(id);
        }
    }

    const auto assess = [&](int id, int depth) -> const SpatialAttempt& {
        const auto known = cache.find(id);
        if (known != cache.end()) return known->second;
        if (cache.size() >= limits.maxEvaluations)
            throw std::length_error("Spatial selection evaluation budget exceeded");
        const auto query = history.query(historyCell(g, id, depth), finest.startMs, finest.endMs);
        if (!query.candidate)
            throw std::runtime_error("Spatial selection interval is not reconstructable from retained history");
        const auto& candidate = *query.candidate;
        if (candidate.runId != finest.runId || candidate.sensorId != finest.sensorId
            || candidate.applicationId != finest.applicationId || candidate.closedAtMs > finest.closedAtMs)
            throw std::invalid_argument("Spatial selection history context/time differs from its input");
        auto checked = evaluator.evaluate(candidate, finest.closedAtMs);
        return cache.emplace(id, SpatialAttempt{candidate.cells.at(0), checked.cells.at(0)}).first->second;
    };

    struct Branch { bool eligible; std::vector<SpatialCellDecision> cells; };
    std::function<Branch(int, int)> visit = [&](int id, int depth) -> Branch {
        if (!occupied.count({id, depth})) return {true, {}}; // Known-empty support, no zero release.
        std::vector<SpatialCellDecision> children;
        std::vector<int> failingChildren;
        if (depth < g.leafDepth) {
            for (int q = 0; q < 4; ++q) {
                const int childId = (id << 2) | q;
                auto child = visit(childId, depth + 1);
                if (!child.eligible) failingChildren.push_back(childId);
                children.insert(children.end(), child.cells.begin(), child.cells.end());
            }
            if (failingChildren.empty()) return {true, std::move(children)};
        }
        const auto& attempt = assess(id, depth);
        const bool eligible = finest.coverage == WindowCoverage::Complete
            && attempt.assessment.status == AssessmentStatus::Pass;
        const std::string reason = eligible ? (depth == g.leafDepth ? "finest_requirements_met" : "sibling_failure_parent_passed")
            : attempt.assessment.status == AssessmentStatus::Unavailable ? "assessment_unavailable"
            : attempt.assessment.status == AssessmentStatus::NotConfigured ? "policy_not_configured"
            : "requirements_failed_at_depth_cap";
        // A failed subtree is provisional until its parent is tried. Even passing siblings
        // are replaced as a group; none have been released while the private cut is built.
        return {eligible, {{id, eligible, reason, std::move(failingChildren), "initial"}}};
    };

    for (int domain : domains) {
        auto branch = visit(domain, limits.minDepth);
        for (auto& decision : branch.cells) {
            const auto& attempt = cache.at(decision.cellId);
            const auto& cell = attempt.cell.cell;
            if (decision.selected) {
                ++result.selectedCells;
                if (previousEnd) {
                    decision.transition = "new_support";
                    for (const auto& old : previousSelected) {
                        if (old.id == cell.id) { decision.transition = "unchanged"; break; }
                        if (contains(old, cell)) { decision.transition = "refined"; break; }
                        if (contains(cell, old)) decision.transition = "coarsened";
                    }
                }
                result.coarsenedCells += decision.transition == "coarsened";
                result.refinedCells += decision.transition == "refined";
            } else {
                ++result.suppressedCells;
                decision.transition = "suppressed";
            }
            result.candidate.cells.push_back(attempt.cell);
            result.decisions.push_back(std::move(decision));
        }
    }
    std::sort(result.decisions.begin(), result.decisions.end(), [](const auto& a, const auto& b) {
        return a.cellId < b.cellId;
    });
    std::sort(result.candidate.cells.begin(), result.candidate.cells.end(), [](const auto& a, const auto& b) {
        return a.cell.id < b.cell.id;
    });
    // This also verifies that the disjoint final footprints account for every input
    // contribution, including diagnostic suppression footprints. Global distinct support
    // remains the input's exact union; it is never a sum of per-cell distinct counts.
    result.assessment = evaluator.evaluate(result.candidate, finest.closedAtMs);
    for (auto& [id, attempt] : cache) result.attempts.push_back(std::move(attempt));
    return result;
}

void SpatialSelector::commit(const SpatialSelection& selection) {
    const auto& candidate = selection.candidate;
    const auto& g = candidate.grid;
    const auto& expected = config.coverage;
    if (candidate.runId != config.runId || candidate.sensorId != config.sensorId
        || candidate.applicationId != config.applicationId || g.x != expected.x || g.y != expected.y
        || g.width != expected.width || g.height != expected.height || g.leafDepth != expected.leafDepth
        || candidate.startMs < 0 || candidate.endMs <= candidate.startMs
        || (previousEnd && candidate.startMs != *previousEnd)
        || candidate.cells.size() != selection.decisions.size())
        throw std::invalid_argument("Spatial commit requires the next disjoint selection of one stream");
    std::vector<CellGeometry> next;
    for (std::size_t i = 0; i < selection.decisions.size(); ++i) {
        if (selection.decisions[i].cellId != candidate.cells[i].cell.id)
            throw std::invalid_argument("Spatial commit cell and decision mismatch");
        if (selection.decisions[i].selected) next.push_back(candidate.cells[i].cell);
    }
    previousSelected = std::move(next);
    previousEnd = candidate.endMs;
}
} // namespace ump
