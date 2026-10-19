#pragma once

#include "AdaptiveAggregation.hpp"
#include <map>
#include <optional>

namespace ump {

// A member of the disjoint, full-domain ownership frontier. These are private
// windows, not published cells. Empty subtrees remain compressed whenever possible.
struct CellLocalWindow {
    CellGeometry cell;
    AggregationTime startMs, nextEndMs, hardDeadlineMs;
    std::size_t extensions = 0, evaluations = 0;
};

// Independent cell windows over one immutable source history. Parent takeover is
// possible only for an unpublished, common-start descendant frontier. A sink
// exception retains the exact immutable proposal and blocks all later work until
// that proposal is acknowledged by a successful retry.
class CellLocalAggregation {
public:
    using Sink = AdaptiveAggregation::Sink;
    CellLocalAggregation(AggregationConfig config, TemporalAdaptationConfig temporal,
        SpatialSelectionConfig spatial, MetricEvaluator evaluator, Sink sink,
        std::size_t maxActiveCells = 16384);
    void advance(AggregationTime nowMs, const AggregationHistory& history);
    void finish(AggregationTime endMs, const AggregationHistory& history);
    AdaptiveAggregationDebugState debugState() const;
    AggregationProgress progressSnapshot() const;
    std::vector<CellLocalWindow> windows() const;

    // Immediate, pure-until-accepted parent proposal. A false return changes no
    // ownership, progress or publication state. Differing next endpoints are fine;
    // differing retired starts require a future handoff instead.
    bool requestMerge(const CellGeometry& domain, AggregationTime endMs,
        const AggregationHistory& history);
    // Bring all current descendants to a bounded future common boundary. Earlier
    // prefixes resolve under their own deadlines; no old support is resurrected.
    bool scheduleMerge(const CellGeometry& domain);

private:
    struct Window {
        CellLocalWindow publicState;
        std::vector<TemporalDecision> decisions;
        std::shared_ptr<const AggregationProgressCheck> lastCheck;
        std::optional<CellGeometry> previousSelected;
    };
    using Frontier = std::map<int, Window>;
    struct Pending {
        SpatialSelection selection;
        Frontier replacements;
        std::vector<int> retiredIds;
    };
    Window makeWindow(const CellGeometry& cell, AggregationTime startMs,
        std::optional<CellGeometry> previous = std::nullopt) const;
    AggregationCandidate query(const CellGeometry& cell, AggregationTime startMs,
        AggregationTime endMs, const AggregationHistory& history, bool final = false) const;
    void validateTime(AggregationTime nowMs, const AggregationHistory& history) const;
    void validateDomain(const CellGeometry& cell) const;
    void retryPending(AggregationTime nowMs);
    void emit(SpatialSelection selection, Frontier replacements, std::vector<int> retiredIds);
    void refineDue(AggregationTime endpoint, const AggregationHistory& history);
    void refineToDomain(Frontier& cut, const CellGeometry& domain) const;
    bool canMerge(const Frontier& cut, const CellGeometry& domain,
        AggregationTime endMs, AggregationTime& startMs) const;
    SpatialSelection selectionFor(const Window& source, AggregationCandidate candidate,
        WindowMetricAssessment assessment, const AggregationHistory& history,
        bool selected, const std::string& reason, bool final) const;
    bool tryMerge(const CellGeometry& domain, AggregationTime endMs,
        const AggregationHistory& history, bool final);
    void process(AggregationTime nowMs, const AggregationHistory& history, bool final);
    void applyHandoffs();
    void compactFreshOwners(AggregationTime nowMs, const AggregationHistory& history);
    std::optional<AggregationTime> handoffBoundary(const CellGeometry& cell) const;
    AggregationConfig config;
    TemporalAdaptationConfig temporal;
    SpatialSelectionConfig spatial;
    MetricEvaluator evaluator;
    Sink sink;
    std::size_t maxActiveCells;
    Frontier frontier;
    std::map<int, std::pair<CellGeometry, AggregationTime>> handoffs;
    std::optional<Pending> pending;
    AggregationTime lastNowMs = 0;
    std::uint64_t completedWindows = 0;
    bool finished = false, emitting = false;
};

} // namespace ump
