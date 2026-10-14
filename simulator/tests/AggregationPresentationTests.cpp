#include "AggregationPresentation.hpp"
#include <iostream>
#include <stdexcept>

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
std::string joined(const std::vector<std::string>& lines) {
    std::string result;
    for (const auto& line : lines) result += line + '\n';
    return result;
}
void activeEvidenceIsDated() {
    ump::AggregationProgress progress;
    progress.strategy = "spatial_first";
    progress.startMs = 0;
    progress.nextEndMs = 400;
    progress.hardDeadlineMs = 1000;
    progress.observedThroughMs = 250;
    const auto collecting = joined(ump::aggregationProgressLines(&progress));
    require(collecting.find("collecting") != std::string::npos, "Collection state missing");
    require(collecting.find("First policy check pending") != std::string::npos,
        "Unchecked window presented as evaluated");
    require(collecting.find("Checked window RU") == std::string::npos,
        "Counts invented before a policy check");

    auto check = std::make_shared<ump::AggregationProgressCheck>();
    check->candidate.startMs = 0;
    check->candidate.endMs = 400;
    check->candidate.counts.distinctContributors = 7;
    check->assessment.evaluatedAtMs = 400;
    check->assessment.cells = {{12, ump::AssessmentStatus::Fail, {}, {}},
                              {13, ump::AssessmentStatus::Unavailable, {}, {}},
                              {14, ump::AssessmentStatus::Pass, {}, {}}};
    progress.lastCheck = check;
    progress.phase = ump::AggregationProgressPhase::Extending;
    progress.nextEndMs = 500;
    progress.observedThroughMs = 450;
    progress.temporalExtensions = 1;
    const auto extending = joined(ump::aggregationProgressLines(&progress));
    require(extending.find("Next check: [0, 500) ms") != std::string::npos,
        "Extension interval not visible");
    require(extending.find("Last check: [0, 400) ms") != std::string::npos &&
        extending.find("Checked at 400 ms") != std::string::npos &&
        extending.find("State at 450 ms") != std::string::npos,
        "Old check evidence mixed with progress time");
    require(extending.find("7 (distinct, not current)") != std::string::npos,
        "Window union mislabeled as current occupancy");
    require(extending.find("1 pass, 1 fail, 1 unavailable") != std::string::npos,
        "Unavailable policy evidence hidden");
    require(extending.find("suppressed") == std::string::npos,
        "Pending failure mislabeled as suppression");
    require(ump::pendingAggregationCell(ump::AssessmentStatus::Fail) &&
        ump::pendingAggregationCell(ump::AssessmentStatus::Unavailable) &&
        !ump::pendingAggregationCell(ump::AssessmentStatus::Pass) &&
        !ump::pendingAggregationCell(ump::AssessmentStatus::NotConfigured),
        "Pending overlay includes cells without failed or unavailable checks");

    progress.phase = ump::AggregationProgressPhase::Finished;
    const auto finished = joined(ump::aggregationProgressLines(&progress));
    require(finished.find("finished") != std::string::npos &&
        finished.find("Next check") == std::string::npos && finished.find("Checked window RU") == std::string::npos,
        "Finished aggregation retains an active or stale check label");
}
void releaseStatusIsTruthful() {
    ump::SpatialSelection selection{};
    selection.candidate.startMs = 0;
    selection.candidate.endMs = 500;
    auto lines = joined(ump::aggregationCompletedLines(&selection));
    require(lines.find("Completed decision") != std::string::npos && lines.find("Released output") == std::string::npos,
        "Unpublished decision presented as a release");
    selection.publicationState = "retired_without_release";
    lines = joined(ump::aggregationCompletedLines(&selection));
    require(lines.find("No cells released") != std::string::npos && lines.find("Released output") == std::string::npos,
        "Empty retirement presented as released data");
    selection.publicationState = "committed";
    require(joined(ump::aggregationCompletedLines(&selection)).find("Released output") != std::string::npos,
        "Committed release not distinguished from internal decisions");
    require(ump::aggregationStrategyLabel("temporal_first").find("preserve time") != std::string::npos &&
        ump::aggregationStrategyLabel("spatial_first").find("preserve space") != std::string::npos,
        "Strategy labels reverse the agreed convention");
}
}
int main() {
    try {
        activeEvidenceIsDated();
        releaseStatusIsTruthful();
        std::cout << "PASS: dated active evidence, pending checks, strategy names and truthful release labels.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
