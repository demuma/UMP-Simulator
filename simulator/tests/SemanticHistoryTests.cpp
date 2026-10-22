#include "AggregationHistory.hpp"
#include "AggregationManager.hpp"
#include "SemanticTaxonomy.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ump;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected explicit rejection");
}

std::shared_ptr<const SemanticTaxonomy> taxonomy() {
    return std::make_shared<const SemanticTaxonomy>("history-taxonomy", "1",
        std::vector<SemanticNode>{{"road_user", "", 1, {}},
            {"pedestrian", "road_user", .5, {}},
            {"adult", "pedestrian", 0, {"Adult Pedestrian", "Adult alias"}},
            {"child", "pedestrian", 0, {"Child Pedestrian"}},
            {"bicycle", "road_user", 0, {"Bicycle"}}});
}

AggregationConfig settings(bool enabled = true) {
    AggregationConfig c{"semantic-run", "agbs", "semantic-app", {0, 0, 80, 80, 2}, 100, 400};
    c.history = HistoryLimits{2000, 32, 10000, 1000000, 64};
    if (enabled) c.semanticTaxonomy = taxonomy();
    return c;
}
CellObservation observation(std::string identity, int leaf = 48, std::string type = "Adult Pedestrian") {
    return {std::move(identity), std::move(type), historyCell(settings(false).coverage, leaf, 2)};
}
ObservationBatch batch(int time, std::vector<CellObservation> observations = {}) {
    return {"semantic-run", "agbs", static_cast<std::uint64_t>(time / 100), time,
        ObservationStatus::Measured, std::move(observations)};
}
AggregationCandidate candidate(const HistoryQuery& found) {
    require(found.candidate.has_value(), "Expected a retained private candidate");
    return *found.candidate;
}
const SemanticEvidence& evidence(const AggregateCounts& counts) {
    require(counts.semanticEvidence.has_value(), "Enabled private semantic evidence is absent");
    const auto& value = *counts.semanticEvidence;
    require(value.taxonomyId == "history-taxonomy" && value.taxonomyVersion == "1",
        "Private semantic evidence lost taxonomy provenance");
    return value;
}
void expectNode(const AggregateCounts& counts, const std::string& id,
    std::uint64_t observations, std::uint64_t distinct) {
    const auto& nodes = evidence(counts).nodes;
    const auto found = nodes.find(id);
    if (!observations && !distinct && found == nodes.end()) return;
    require(found != nodes.end(), "Expected taxonomy node is absent from private evidence");
    require(found->second.observationContributions == observations
        && found->second.distinctContributors == distinct,
        "Taxonomy-node evidence differs from hand-computed contributions/identity union");
}
void sameEvidence(const AggregateCounts& a, const AggregateCounts& b) {
    require(a.observationContributions == b.observationContributions
        && a.distinctContributors == b.distinctContributors
        && a.typeObservationContributions == b.typeObservationContributions
        && a.meanSampleOccupancy == b.meanSampleOccupancy,
        "Reconstructed semantic candidate changed scalar/source-type statistics");
    const auto& x = evidence(a);
    const auto& y = evidence(b);
    require(x.taxonomyId == y.taxonomyId && x.taxonomyVersion == y.taxonomyVersion
        && x.nodes.size() == y.nodes.size(), "Semantic evidence provenance/node sets differ");
    for (const auto& [id, counts] : x.nodes) {
        const auto found = y.nodes.find(id);
        require(found != y.nodes.end()
            && counts.observationContributions == found->second.observationContributions
            && counts.distinctContributors == found->second.distinctContributors,
            "Fixed-window and history queries disagree on exact semantic evidence");
    }
}

std::vector<ObservationBatch> crossingSamples() {
    return {
        batch(100, {observation("a"), observation("b", 48, "Child Pedestrian"),
                    observation("c", 49, "Bicycle")}),
        batch(200, {observation("a", 49), observation("b", 48, "Child Pedestrian"),
                    observation("c", 49, "Bicycle")}),
        batch(300, {observation("a", 48, "Adult alias"), observation("b", 49, "Child Pedestrian"),
                    observation("c", 48, "Bicycle")})};
}

void exactSpatialTemporalUnionsAndAliases() {
    const auto config = settings();
    AggregationHistory history(config, *config.history);
    for (const auto& sample : crossingSamples()) history.append(sample);
    history.advance(400);
    const auto whole = candidate(history.query(historyCell(config.coverage, 12, 1), 0, 400));
    expectNode(whole.counts, "road_user", 9, 3);
    expectNode(whole.counts, "pedestrian", 6, 2);
    expectNode(whole.counts, "adult", 3, 1);
    expectNode(whole.counts, "child", 3, 1);
    expectNode(whole.counts, "bicycle", 3, 1);
    require(whole.counts.typeObservationContributions.at("Adult Pedestrian") == 2
        && whole.counts.typeObservationContributions.at("Adult alias") == 1,
        "Aliases silently changed raw type-count semantics");

    const auto left = candidate(history.query(historyCell(config.coverage, 48, 2), 0, 400));
    const auto right = candidate(history.query(historyCell(config.coverage, 49, 2), 0, 400));
    expectNode(left.counts, "road_user", 5, 3);
    expectNode(left.counts, "pedestrian", 4, 2);
    expectNode(left.counts, "adult", 2, 1);
    expectNode(left.counts, "child", 2, 1);
    expectNode(left.counts, "bicycle", 1, 1);
    expectNode(right.counts, "road_user", 4, 3);
    require(left.counts.distinctContributors + right.counts.distinctContributors == 6
        && whole.counts.distinctContributors == 3,
        "Test fixture no longer distinguishes child support sums from parent unions");
    const auto fine = candidate(history.queryFinest(0, 400));
    sameEvidence(whole.counts, fine.counts);
    require(fine.cells.size() == 2 && fine.cells[0].cell.id == 48 && fine.cells[1].cell.id == 49,
        "Semantic finest reconstruction lost its sparse sorted spatial cut");
    sameEvidence(left.counts, fine.cells[0].counts);
    sameEvidence(right.counts, fine.cells[1].counts);
    const auto restricted = candidate(history.queryFinest(0, 400, historyCell(config.coverage, 48, 2)));
    sameEvidence(left.counts, restricted.counts);
    require(restricted.cells.size() == 1, "Domain-scoped semantic reconstruction included another cell");
}

void emptyIncompleteAndExclusiveEndpoints() {
    const auto config = settings();
    AggregationHistory history(config, *config.history);
    history.append(batch(100, {observation("a")}));
    auto unavailable = batch(200); unavailable.status = ObservationStatus::Unavailable;
    history.append(unavailable);
    history.advance(400);
    const auto incomplete = candidate(history.query(historyCell(config.coverage, 48, 2), 0, 400));
    require(incomplete.coverage == WindowCoverage::Incomplete && incomplete.measuredSamples == 1
        && incomplete.unavailableSamples == 1 && incomplete.missingSamples == 1,
        "Semantic evidence fabricated complete measurement coverage");
    expectNode(incomplete.counts, "road_user", 1, 1);
    const auto empty = candidate(history.query(historyCell(config.coverage, 13, 1), 0, 400));
    expectNode(empty.counts, "road_user", 0, 0);
    require(empty.counts.observationContributions == 0 && empty.counts.meanSampleOccupancy == 0,
        "Empty semantic footprint became nonempty");
    const auto noSamples = candidate(history.query(historyCell(config.coverage, 48, 2), 0, 100));
    expectNode(noSamples.counts, "road_user", 0, 0);
    require(noSamples.coverage == WindowCoverage::NoScheduledSamples,
        "Semantic query included its exclusive endpoint measurement");
    require(history.queryFinest(0, 500).status == HistoryQueryStatus::Future,
        "Semantic reconstruction fabricated future evidence");
}

void unknownLabelsRejectBeforeMutationAndOutput() {
    auto config = settings();
    AggregationHistory history(config, *config.history);
    history.append(batch(100, {observation("a")}));
    const auto before = history.debugState();
    rejects([&] { history.append(batch(400, {observation("bad", 48, "Unknown Label")})); });
    const auto after = history.debugState();
    require(after.watermarkMs == before.watermarkMs && after.bins == before.bins
        && after.observations == before.observations && after.identityBytes == before.identityBytes,
        "Unknown history label advanced/evicted retained input");
    history.append(batch(200, {observation("b", 48, "Bicycle")}));

    std::vector<AggregationCandidate> outputs;
    AggregationManager manager(config, [&](const auto& output) { outputs.push_back(output); });
    for (const auto& sample : crossingSamples()) manager.ingest(sample);
    const auto managerBefore = manager.debugState();
    const auto historyBefore = manager.history()->debugState();
    rejects([&] { manager.ingest(batch(400, {observation("bad", 48, "Unknown Label")})); });
    require(outputs.empty() && manager.debugState().windowStartMs == managerBefore.windowStartMs
        && manager.debugState().observationContributions == managerBefore.observationContributions
        && manager.history()->debugState().watermarkMs == historyBefore.watermarkMs
        && manager.history()->debugState().bins == historyBefore.bins,
        "Unknown boundary sample emitted output or changed manager/history state");
    // Same timestamp and sequence remain usable after rejection. Endpoint400 is
    // excluded from the old window and belongs only to its successor.
    manager.ingest(batch(400, {observation("later")}));
    require(outputs.size() == 1 && outputs[0].counts.observationContributions == 9,
        "Rejected semantic sample consumed sequence or contaminated old window");
    expectNode(outputs[0].counts, "road_user", 9, 3);
}

void conflictingCanonicalTypesFailQueriesWithoutInventingAClass() {
    const auto config = settings();
    AggregationHistory history(config, *config.history);
    history.append(batch(100, {observation("same")}));
    history.append(batch(200, {observation("same", 49, "Child Pedestrian")}));
    history.advance(300);
    const auto before = history.debugState();
    rejects([&] { (void)history.query(historyCell(config.coverage, 12, 1), 0, 300); });
    rejects([&] { (void)history.queryFinest(0, 300); });
    require(history.debugState().watermarkMs == before.watermarkMs
        && history.debugState().observations == before.observations,
        "Conflicting-class query consumed or altered raw observations");
    expectNode(candidate(history.queryFinest(0, 200)).counts, "adult", 1, 1);
    expectNode(candidate(history.queryFinest(200, 300)).counts, "child", 1, 1);

    std::size_t outputs = 0;
    AggregationManager manager(config, [&](const auto&) { ++outputs; });
    manager.ingest(batch(100, {observation("same")}));
    manager.ingest(batch(200, {observation("same", 49, "Child Pedestrian")}));
    rejects([&] { manager.advance(400); });
    require(outputs == 0 && manager.debugState().windowStartMs == 0,
        "Fixed-window manager emitted conflicting semantic evidence");
}

void managerAndHistoryEvidenceMatchIncludingTruncation() {
    const auto config = settings();
    std::vector<AggregationCandidate> outputs;
    AggregationManager manager(config, [&](const auto& output) { outputs.push_back(output); });
    for (const auto& sample : crossingSamples()) manager.ingest(sample);
    manager.advance(450);
    require(outputs.size() == 1 && outputs[0].closedAtMs == 450 && !outputs[0].truncated,
        "Semantic reconstruction changed closure/evaluation metadata");
    const auto raw = candidate(manager.history()->queryFinest(0, 400));
    sameEvidence(outputs[0].counts, raw.counts);
    require(outputs[0].cells.size() == raw.cells.size(), "Manager and history finest cuts differ");
    for (std::size_t i = 0; i < raw.cells.size(); ++i) {
        require(outputs[0].cells[i].cell.id == raw.cells[i].cell.id, "Manager changed finest-cell IDs");
        sameEvidence(outputs[0].cells[i].counts, raw.cells[i].counts);
    }
    manager.finish(475);
    require(outputs.size() == 2 && outputs[1].startMs == 400 && outputs[1].endMs == 475
        && outputs[1].closedAtMs == 475 && outputs[1].truncated,
        "Truncated semantic suffix lost its original interval or flags");
    expectNode(outputs[1].counts, "road_user", 0, 0);
}

void disabledCompatibilityAndBoundedHistoryRequirement() {
    auto config = settings(); config.history.reset();
    rejects([&] { AggregationManager invalid(config, [](const auto&) {}); });
    config = settings(false);
    std::vector<AggregationCandidate> outputs;
    AggregationManager old(config, [&](const auto& output) { outputs.push_back(output); });
    old.ingest(batch(100, {observation("a", 48, "Unknown Old Label")}));
    old.ingest(batch(200, {observation("a", 49, "Another Old Label")}));
    old.ingest(batch(300));
    old.advance(400);
    require(outputs.size() == 1 && !outputs[0].counts.semanticEvidence
        && outputs[0].counts.observationContributions == 2
        && outputs[0].counts.distinctContributors == 1,
        "Disabled semantic option changed old scalar/unknown-label behavior");
    const auto fromHistory = candidate(old.history()->queryFinest(0, 400));
    require(!fromHistory.counts.semanticEvidence, "Disabled history generated semantic evidence");
    for (const auto& cell : outputs[0].cells)
        require(!cell.counts.semanticEvidence, "Disabled finest cell generated semantic evidence");

    config = settings(); config.history->retentionMs = 400;
    std::size_t released = 0;
    AggregationManager expired(config, [&](const auto&) { ++released; });
    expired.ingest(batch(100, {observation("a")}));
    rejects([&] { expired.advance(1000); });
    require(released == 0 && expired.debugState().windowStartMs == 0,
        "Unavailable bounded semantic history produced a plausible fixed output");
}
}

int main() {
    try {
        exactSpatialTemporalUnionsAndAliases();
        emptyIncompleteAndExclusiveEndpoints();
        unknownLabelsRejectBeforeMutationAndOutput();
        conflictingCanonicalTypesFailQueriesWithoutInventingAClass();
        managerAndHistoryEvidenceMatchIncludingTruncation();
        disabledCompatibilityAndBoundedHistoryRequirement();
        std::cout << "PASS: exact private semantic identity unions, aliases, bounded history, "
                     "unknown/conflicting labels, manager reconstruction and legacy compatibility.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
