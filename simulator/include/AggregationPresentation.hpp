#pragma once

#include "AggregationProgress.hpp"
#include "SpatialSelection.hpp"
#include <string>
#include <vector>

namespace ump {

// Presentation names describe which detail is preserved, not the first operation.
inline std::string aggregationStrategyLabel(const std::string& strategy) {
    if (strategy == "spatial_first") return "Spatial First: preserve space";
    if (strategy == "temporal_first") return "Temporal First: preserve time";
    if (strategy == "temporal_first_spatial_only") return "Spatial aggregation only";
    return strategy;
}

inline bool pendingAggregationCell(AssessmentStatus status) {
    return status == AssessmentStatus::Fail || status == AssessmentStatus::Unavailable;
}

inline std::string aggregationInterval(AggregationTime start, AggregationTime end) {
    return "[" + std::to_string(start) + ", " + std::to_string(end) + ") ms";
}

inline std::vector<std::string> aggregationCompletedLines(const SpatialSelection* selection) {
    if (!selection) return {"Completed decision (G)", "Waiting for a closed window"};
    const auto& snapshot = *selection;
    std::vector<std::string> lines{
        snapshot.publicationState == "committed" ? "Released output (G)" : "Completed decision (G)",
        aggregationInterval(snapshot.candidate.startMs, snapshot.candidate.endMs),
        "Selected: " + std::to_string(snapshot.selectedCells) + " | Suppressed: "
            + std::to_string(snapshot.suppressedCells),
        "Coarser: " + std::to_string(snapshot.coarsenedCells) + " | Finer: "
            + std::to_string(snapshot.refinedCells)
    };
    if (snapshot.coordinationCell)
        lines.insert(lines.begin() + 1, "Latest local decision: cell " + std::to_string(snapshot.coordinationCell->id));
    if (snapshot.publicationState == "retired_without_release") lines.push_back("No cells released");
    lines.push_back("Solid: green selected, orange coarser, blue finer, red suppressed");
    return lines;
}

inline std::vector<std::string> aggregationProgressLines(const AggregationProgress* progress) {
    if (!progress) return {"Active window (P)", "Waiting for aggregation state"};
    const auto& state = *progress;
    if (state.phase == AggregationProgressPhase::Finished)
        return {"Aggregation finished (P)", "State at " + std::to_string(state.observedThroughMs) + " ms"};
    if (state.cellLocal) {
        std::size_t extending = 0;
        for (const auto& cell : state.cells) extending += cell.temporalExtensions != 0;
        return {"Cell-local coordination (P)", aggregationStrategyLabel(state.strategy),
            "Active domains: " + std::to_string(state.cells.size()) + " | Extending: " + std::to_string(extending),
            "Earliest next check: " + std::to_string(state.nextEndMs) + " ms",
            "State at " + std::to_string(state.observedThroughMs) + " ms",
            "Each domain has its own interval and policy deadline",
            "Dashed amber: pending local policy checks"};
    }
    std::vector<std::string> lines{
        state.phase == AggregationProgressPhase::Extending ? "Active: extending time (P)" : "Active: collecting (P)",
        aggregationStrategyLabel(state.strategy),
        "Next check: " + aggregationInterval(state.startMs, state.nextEndMs),
        "Hard deadline: " + std::to_string(state.hardDeadlineMs) + " ms",
        "State at " + std::to_string(state.observedThroughMs) + " ms | Extensions: "
            + std::to_string(state.temporalExtensions)
    };
    if (!state.lastCheck) {
        lines.push_back("First policy check pending");
        return lines;
    }
    const auto& check = *state.lastCheck;
    std::size_t passed = 0, failed = 0, unavailable = 0;
    for (const auto& cell : check.assessment.cells) {
        if (cell.status == AssessmentStatus::Pass) ++passed;
        else if (cell.status == AssessmentStatus::Fail) ++failed;
        else if (cell.status == AssessmentStatus::Unavailable) ++unavailable;
    }
    lines.push_back("Last check: " + aggregationInterval(check.candidate.startMs, check.candidate.endMs));
    lines.push_back("Checked at " + std::to_string(check.assessment.evaluatedAtMs) + " ms");
    lines.push_back("Checked cells: " + std::to_string(passed) + " pass, " + std::to_string(failed)
        + " fail, " + std::to_string(unavailable) + " unavailable");
    lines.push_back("Checked window RU: " + std::to_string(check.candidate.counts.distinctContributors)
        + " (distinct, not current)");
    lines.push_back("Dashed amber: pending policy checks");
    return lines;
}

} // namespace ump
