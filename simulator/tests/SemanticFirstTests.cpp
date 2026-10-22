#include "AdaptiveAggregation.hpp"
#include "AggregationHistory.hpp"
#include "PolicyTree.hpp"
#include "PublicationCoordinator.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace ump;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class Operation> void rejects(Operation operation, const char* message) {
    bool rejected = false;
    try { operation(); } catch (const std::exception&) { rejected = true; }
    require(rejected, message);
}

std::shared_ptr<const SemanticTaxonomy> catalog(double cyclistLoss = .5) {
    return std::make_shared<const SemanticTaxonomy>("semantic-first-tests", "1", std::vector<SemanticNode>{
        {"road_user", "", 1, {}}, {"pedestrian", "road_user", 0, {"Pedestrian"}},
        {"cyclist", "road_user", cyclistLoss, {}},
        {"adult_cyclist", "cyclist", 0, {"Adult Cyclist"}},
        {"child_cyclist", "cyclist", 0, {"Child Cyclist"}}});
}
AggregationConfig settings(double cyclistLoss = .5) {
    AggregationConfig config{"semantic-first-run", "agbs", "application", {0, 0, 80, 80, 2}, 100, 400};
    config.history = HistoryLimits{2000, 32, 10000, 1000000, 128};
    config.semanticTaxonomy = catalog(cyclistLoss);
    return config;
}
TemporalAdaptationConfig preferenceTime(AggregationTime maximum) {
    TemporalAdaptationConfig temporal{AdaptationStrategy::SemanticFirst, 100, maximum, 16};
    temporal.releaseTrigger = ReleaseTrigger::PrioritySatisfied;
    return temporal;
}
MetricEvaluator metrics(const AggregationConfig& config, double support = 4,
    double maxLoss = 1, double maxSide = 40, std::optional<double> meanBound = std::nullopt) {
    MetricPolicy policy{"semantic-first-policy", "1", {{MetricId::DistinctContributors, 1, {}},
        {MetricId::CellSideM, {}, maxSide}, {MetricId::MinCategoryDistinctContributors, support, {}},
        {MetricId::SemanticMaxLoss, {}, maxLoss}}};
    if (meanBound) policy.requirements.push_back({MetricId::SemanticMeanLoss, {}, meanBound});
    return MetricEvaluator(std::move(policy), config.semanticTaxonomy);
}
void addPeople(std::vector<CellObservation>& people, const AggregationConfig& config,
    const std::string& prefix, const std::string& type, int count, int cell = 48) {
    for (int index = 0; index < count; ++index)
        people.push_back({prefix + std::to_string(index), type, historyCell(config.coverage, cell, 2)});
}
void append(AggregationHistory& history, const AggregationConfig& config, int time,
    const std::vector<CellObservation>& people, ObservationStatus status = ObservationStatus::Measured) {
    history.append({config.runId, config.sensorId, static_cast<std::uint64_t>(time / 100), time, status, people});
}
void initialHistory(AggregationHistory& history, const AggregationConfig& config,
    const std::vector<CellObservation>& people) {
    for (int time : {100, 200, 300}) append(history, config, time, people);
    history.advance(400);
}
std::vector<std::size_t> chosen(const SpatialSelection& selection) {
    std::vector<std::size_t> result;
    for (std::size_t index = 0; index < selection.candidate.cells.size(); ++index) {
        const auto id = selection.candidate.cells[index].cell.id;
        const auto decision = std::find_if(selection.decisions.begin(), selection.decisions.end(),
            [&](const auto& value) { return value.cellId == id; });
        require(decision != selection.decisions.end(), "Terminal cut lost an explicit cell decision");
        if (decision->selected) result.push_back(index);
    }
    return result;
}
std::uint64_t retained(const SpatialSelection& selection) {
    std::uint64_t result = 0;
    for (auto index : chosen(selection)) result += selection.candidate.cells[index].counts.observationContributions;
    return result;
}
double actualMaximumLoss(const SpatialSelection& selection) {
    double result = 0;
    for (auto index : chosen(selection)) {
        require(selection.assessment.cells[index].semantic.has_value(), "Selected cell has no semantic representation");
        result = std::max(result, selection.assessment.cells[index].semantic->maxLoss);
    }
    return result;
}
std::string signature(const SpatialSelection& selection) {
    std::ostringstream output;
    output << selection.candidate.startMs << ':' << selection.candidate.endMs << ':' << selection.strategy;
    for (auto index : chosen(selection)) {
        output << '/' << selection.candidate.cells[index].cell.id << ':' << selection.decisions[index].transition;
        for (const auto& bin : selection.assessment.cells[index].semantic->bins)
            output << ':' << bin.categoryId << ':' << bin.observationContributions << ':' << bin.distinctContributors;
    }
    return output.str();
}
void originalHardPolicy(const SpatialSelection& selection, double originalMaximum) {
    require(selection.assessment.policyId == std::optional<std::string>{"semantic-first-policy"}
        && selection.assessment.policyVersion == std::optional<std::string>{"1"},
        "Semantic preference altered hard-policy provenance");
    for (const auto& cell : selection.assessment.cells) {
        int maxima = 0;
        for (const auto& check : cell.checks)
            if (check.requirement.id == MetricId::SemanticMaxLoss) {
                ++maxima;
                require(check.requirement.max == std::optional<double>{originalMaximum},
                    "Synthetic preference ceiling appeared as a hard-policy requirement");
            }
        require(maxima == 1, "Semantic preference inserted or removed a hard loss check");
    }
}

void exactParentWinsOverFineGeneralizedRoadUser() {
    auto config = settings();
    auto evaluator = metrics(config, 5);
    std::vector<CellObservation> people;
    addPeople(people, config, "p", "Pedestrian", 19);
    addPeople(people, config, "rare", "Adult Cyclist", 1);
    addPeople(people, config, "neighbour", "Adult Cyclist", 5, 49);
    AggregationHistory history(config, *config.history);
    initialHistory(history, config, people);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(800),
        {1, 128, true}, evaluator, [&](const auto& selection) { output.push_back(selection); });
    engine.advance(400, history);
    require(output.size() == 1 && output[0].candidate.endMs == 400 && output[0].selectedCells == 1
        && output[0].candidate.cells[chosen(output[0])[0]].cell.id == 12
        && retained(output[0]) == 75 && actualMaximumLoss(output[0]) == 0,
        "Semantic First chose fine RoadUser generalization instead of a complete exact parent");
    require(output[0].strategy == "semantic_first" && output[0].temporalExtensions == 0
        && output[0].semanticPriority && output[0].semanticPriority->lossCeiling == 0
        && output[0].semanticPriority->actualMaxLoss == std::optional<double>{0}
        && output[0].semanticPriority->attemptedCeilings == 1 && !output[0].semanticPriority->terminalFallback,
        "Immediate exact spatial rescue has incorrect strategy/preference diagnostics");
    originalHardPolicy(output[0], 1);
}

void zeroCostInternalCategoryCountsAsPreferred() {
    auto config = settings(0);
    std::vector<CellObservation> people;
    addPeople(people, config, "a", "Adult Cyclist", 2);
    addPeople(people, config, "c", "Child Cyclist", 2);
    AggregationHistory history(config, *config.history);
    initialHistory(history, config, people);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(800),
        {1, 128, true}, metrics(config, 4, 1, 20), [&](const auto& selection) { output.push_back(selection); });
    engine.advance(400, history);
    require(output.size() == 1 && output[0].selectedCells == 1 && output[0].candidate.endMs == 400,
        "A zero-cost internal category was confused with a positive-loss fallback");
    const auto& semantic = *output[0].assessment.cells[chosen(output[0])[0]].semantic;
    require(semantic.bins.size() == 1 && semantic.bins[0].categoryId == "cyclist"
        && semantic.bins[0].observationContributions == 12 && semantic.bins[0].distinctContributors == 4
        && semantic.maxLoss == 0 && !output[0].semanticPriority->terminalFallback,
        "Zero-cost internal generalization lost observations or changed its declared cost");
}

std::vector<CellObservation> delayedParentPeople(const AggregationConfig& config) {
    std::vector<CellObservation> people;
    addPeople(people, config, "p48-", "Pedestrian", 19);
    addPeople(people, config, "a", "Adult Cyclist", 1);
    addPeople(people, config, "p49-", "Pedestrian", 5, 49);
    addPeople(people, config, "c", "Child Cyclist", 3, 49);
    return people;
}

SpatialSelection delayedParentFallback() {
    auto config = settings();
    const auto people = delayedParentPeople(config);
    AggregationHistory history(config, *config.history);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(800),
        {1, 128, true}, metrics(config), [&](const auto& selection) { output.push_back(selection); });
    for (int time = 100; time <= 700; time += 100) {
        append(history, config, time, people);
        engine.advance(time, history);
        require(output.empty(), "A positive-loss full candidate escaped before the semantic deadline");
        if (time >= 400)
            require(engine.debugState().windowStartMs == 0 && engine.debugState().hardDeadlineMs == 800,
                "Semantic waiting reset the protected interval start or hard deadline");
    }
    history.advance(800);
    engine.advance(800, history);
    require(output.size() == 1 && output[0].candidate.startMs == 0 && output[0].candidate.endMs == 800
        && output[0].temporalExtensions == 4 && output[0].selectedCells == 1
        && output[0].candidate.cells[chosen(output[0])[0]].cell.id == 12
        && retained(output[0]) == 196 && actualMaximumLoss(output[0]) == .5,
        "Terminal fallback chose fine RoadUser loss1 instead of the complete parent loss0.5");
    require(output[0].semanticPriority && output[0].semanticPriority->lossCeiling == .5
        && output[0].semanticPriority->actualMaxLoss == std::optional<double>{.5}
        && output[0].semanticPriority->attemptedCeilings == 2 && output[0].semanticPriority->terminalFallback,
        "Terminal ascending cost fallback has incorrect private diagnostics");
    originalHardPolicy(output[0], 1);
    return output[0];
}

void temporalExactRescueKeepsOriginalInterval() {
    auto config = settings();
    std::vector<CellObservation> first, later;
    addPeople(first, config, "p", "Pedestrian", 19);
    addPeople(first, config, "old-adult", "Adult Cyclist", 1);
    addPeople(later, config, "p", "Pedestrian", 19);
    addPeople(later, config, "new-adult", "Adult Cyclist", 4);
    AggregationHistory history(config, *config.history);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(800),
        {1, 128, true}, metrics(config, 5, 1, 20), [&](const auto& selection) { output.push_back(selection); });
    for (int time : {100, 200, 300, 400}) {
        append(history, config, time, time == 400 ? later : first);
        engine.advance(time, history);
    }
    require(output.empty(), "Exclusive endpoint observation leaked into the first semantic check");
    history.advance(500);
    engine.advance(500, history);
    require(output.size() == 1 && output[0].candidate.startMs == 0 && output[0].candidate.endMs == 500
        && output[0].temporalExtensions == 1 && actualMaximumLoss(output[0]) == 0
        && retained(output[0]) == 83 && output[0].semanticPriority->lossCeiling == 0
        && !output[0].semanticPriority->terminalFallback,
        "Temporal semantic rescue changed its old support or waited after zero-loss feasibility");
}

void terminalPartialRetentionPrecedesSemanticDetail() {
    auto config = settings();
    std::vector<CellObservation> people;
    addPeople(people, config, "p", "Pedestrian", 19);
    addPeople(people, config, "rare", "Adult Cyclist", 1);
    addPeople(people, config, "good", "Pedestrian", 5, 49);
    addPeople(people, config, "unrescuable", "Child Cyclist", 1, 50);
    AggregationHistory history(config, *config.history);
    initialHistory(history, config, people);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(400),
        {1, 128, true}, metrics(config, 4, 1, 20), [&](const auto& selection) { output.push_back(selection); });
    engine.advance(400, history);
    require(output.size() == 1 && output[0].selectedCells == 2 && output[0].suppressedCells == 1
        && retained(output[0]) == 75 && actualMaximumLoss(output[0]) == 1
        && output[0].semanticPriority->terminalFallback,
        "No-full fallback sacrificed feasible observations to prefer a smaller partial exact cut");
    require(output[0].finest.counts.observationContributions == 78,
        "Partial comparison silently shrank the original observation denominator");
}

void equallyRetainingPartialCutsPreferLowerActualMaximum() {
    auto config = settings();
    std::vector<CellObservation> people;
    addPeople(people, config, "p", "Pedestrian", 19);
    addPeople(people, config, "rare", "Adult Cyclist", 1);
    addPeople(people, config, "good", "Adult Cyclist", 5, 49);
    addPeople(people, config, "other-base", "Pedestrian", 1, 52);
    AggregationHistory history(config, *config.history);
    initialHistory(history, config, people);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(400),
        {1, 128, true}, metrics(config, 5, 1, 40), [&](const auto& selection) { output.push_back(selection); });
    engine.advance(400, history);
    require(output.size() == 1 && retained(output[0]) == 75 && actualMaximumLoss(output[0]) == 0
        && output[0].candidate.cells[chosen(output[0])[0]].cell.id == 12,
        "Equal-retention partial comparison prioritized fine space over lower actual semantic maximum");
    require(output[0].semanticPriority->actualMaxLoss == std::optional<double>{0}
        && output[0].semanticPriority->terminalFallback,
        "Partial fallback reported the search cap rather than the chosen actual loss");
}

void maximumLossPreferenceDoesNotClaimMeanLossOptimality() {
    auto config = settings();
    std::vector<CellObservation> people;
    addPeople(people, config, "p", "Pedestrian", 4);
    addPeople(people, config, "rare-child", "Child Cyclist", 1);
    addPeople(people, config, "many-adults", "Adult Cyclist", 100, 49);
    AggregationHistory history(config, *config.history);
    initialHistory(history, config, people);
    auto evaluator = metrics(config, 4, 1, 40);
    const auto source = history.queryFinest(0, 400);
    require(source.candidate.has_value(), "Mean-loss tradeoff lost its complete reference interval");
    const auto fine = SpatialSelector(config, {1, 128, true}).propose(*source.candidate, history, evaluator);
    require(fine.selectedCells == 2 && actualMaximumLoss(fine) == 1,
        "Mean-loss tradeoff reference lacks its complete fine-space alternative");
    double weightedFineMean = 0;
    for (auto index : chosen(fine))
        weightedFineMean += fine.candidate.cells[index].counts.observationContributions
            * fine.assessment.cells[index].semantic->meanLoss;
    weightedFineMean /= retained(fine);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(400),
        {1, 128, true}, evaluator, [&](const auto& selection) { output.push_back(selection); });
    engine.advance(400, history);
    require(output.size() == 1 && retained(output[0]) == 315 && actualMaximumLoss(output[0]) == .5
        && output[0].selectedCells == 1 && output[0].candidate.cells[chosen(output[0])[0]].cell.id == 12,
        "Max-loss fallback changed its priority to a lower-mean but higher-maximum fine cut");
    const auto chosenMean = output[0].assessment.cells[chosen(output[0])[0]].semantic->meanLoss;
    require(chosenMean > weightedFineMean && std::abs(chosenMean - 50.5 / 105) < 1e-12
        && std::abs(weightedFineMean - 5.0 / 105) < 1e-12,
        "Mean-loss reporting hid the deliberate maximum-versus-average tradeoff");
}

void regionalDetailAndMeanRemainHardConstraints() {
    auto config = settings();
    std::vector<CellObservation> people;
    addPeople(people, config, "a", "Adult Cyclist", 2);
    addPeople(people, config, "c", "Child Cyclist", 2);
    addPeople(people, config, "good", "Adult Cyclist", 4, 49);
    auto tree = std::make_shared<const PolicyTree>(PolicyTreeConfig{"regional", "1", config.applicationId,
        config.coverage, {{MetricId::DistinctContributors, 1, {}}, {MetricId::CellSideM, {}, 40},
            {MetricId::MinCategoryDistinctContributors, 4, {}}, {MetricId::SemanticMaxLoss, {}, 1}}},
        std::vector<PolicyRegion>{{"strict", "cycleway", 0, 0, 20, 20, {}, {{MetricId::SemanticMaxLoss, {}, 0}}}});
    MetricEvaluator regional(tree, config.semanticTaxonomy);
    AggregationHistory history(config, *config.history);
    initialHistory(history, config, people);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(400),
        {1, 128, true}, regional, [&](const auto& selection) { output.push_back(selection); });
    engine.advance(400, history);
    require(output.size() == 1 && output[0].selectedCells == 1 && retained(output[0]) == 12
        && output[0].candidate.cells[chosen(output[0])[0]].cell.id == 49,
        "Semantic fallback weakened a strict region through a coarse footprint");

    std::vector<CellObservation> cyclists;
    addPeople(cyclists, config, "a", "Adult Cyclist", 2);
    addPeople(cyclists, config, "c", "Child Cyclist", 2);
    AggregationHistory meanHistory(config, *config.history);
    initialHistory(meanHistory, config, cyclists);
    std::vector<SpatialSelection> meanOutput;
    AdaptiveAggregation meanEngine(config, preferenceTime(400),
        {1, 128, true}, metrics(config, 4, 1, 20, .25), [&](const auto& selection) { meanOutput.push_back(selection); });
    meanEngine.advance(400, meanHistory);
    require(meanOutput.size() == 1 && meanOutput[0].selectedCells == 0 && retained(meanOutput[0]) == 0,
        "Max-loss preference bypassed a mandatory lower mean-loss bound");
}

void unavailableCoverageTerminatesWithoutPositiveFallback() {
    auto config = settings();
    std::vector<CellObservation> people;
    addPeople(people, config, "a", "Adult Cyclist", 4);
    AggregationHistory history(config, *config.history);
    append(history, config, 100, people);
    append(history, config, 200, {}, ObservationStatus::Unavailable);
    append(history, config, 300, people);
    history.advance(400);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(800),
        {1, 128, true}, metrics(config), [&](const auto& selection) { output.push_back(selection); });
    engine.advance(400, history);
    require(output.size() == 1 && output[0].candidate.coverage == WindowCoverage::Incomplete
        && output[0].selectedCells == 0 && output[0].completionReason == "coverage_unavailable"
        && output[0].semanticPriority && output[0].semanticPriority->attemptedCeilings == 1
        && !output[0].semanticPriority->terminalFallback,
        "Missing measurement support was converted into a partial/positive semantic rescue");
}

void sinkExceptionPreservesPrivateProposalAndContiguousSuccessor() {
    auto config = settings();
    std::vector<CellObservation> people;
    addPeople(people, config, "p", "Pedestrian", 19);
    addPeople(people, config, "rare", "Adult Cyclist", 1);
    addPeople(people, config, "other", "Adult Cyclist", 5, 49);
    AggregationHistory history(config, *config.history);
    for (int time : {100, 200, 300, 400}) append(history, config, time, people);
    bool fail = true;
    std::vector<SpatialSelection> attempted, completed;
    AdaptiveAggregation engine(config, preferenceTime(800),
        {1, 128, true}, metrics(config, 5), [&](const auto& selection) {
            attempted.push_back(selection);
            if (fail) throw std::runtime_error("deliberate sink failure");
            completed.push_back(selection);
        });
    const auto before = engine.debugState();
    rejects([&] { engine.advance(400, history); }, "Deliberate semantic sink failure was swallowed");
    const auto after = engine.debugState();
    require(after.windowStartMs == before.windowStartMs && after.nextEndMs == before.nextEndMs
        && after.hardDeadlineMs == before.hardDeadlineMs && after.completedWindows == before.completedWindows
        && after.temporalEvaluations == before.temporalEvaluations,
        "Failed semantic sink committed the private candidate or evaluation clock");
    fail = false;
    engine.advance(400, history);
    require(attempted.size() == 2 && signature(attempted[0]) == signature(attempted[1])
        && completed.size() == 1 && engine.debugState().windowStartMs == 400,
        "Retry changed a private semantic proposal or transition state");
    for (int time : {500, 600, 700}) append(history, config, time, people);
    history.advance(800);
    engine.advance(800, history);
    require(completed.size() == 2 && completed[0].candidate.endMs == completed[1].candidate.startMs
        && completed[1].candidate.startMs == 400 && completed[1].candidate.endMs == 800
        && retained(completed[1]) == 100,
        "Semantic successor lost the retained boundary sample or reopened old support");
}

void eofFallbackAndImmutableOriginalEvaluatorPublication() {
    auto selected = delayedParentFallback();
    auto config = settings();
    auto evaluator = metrics(config);
    // Select uses one catalog instance; fresh trusted evidence is validated by
    // the same version/content before the publisher recomputes semantic bins.
    selected.assessment.cells[chosen(selected)[0]].semantic->bins[0].observationContributions = 999;
    PublicationCoordinator publisher(config, evaluator, {}, 800);
    const auto release = publisher.seal(selected, 800);
    require(release->cells.size() == 1 && release->cells[0].semantic
        && release->cells[0].aggregate.counts.observationContributions == 196
        && release->cells[0].semantic->maxLoss == .5
        && release->cells[0].aggregate.counts.typeObservationContributions.empty()
        && !release->cells[0].aggregate.counts.semanticEvidence
        && release->policyId == "semantic-first-policy" && release->policyVersion == "1",
        "Publication trusted preference annotations or exposed private semantic evidence");
    std::uint64_t categoryTotal = 0;
    for (const auto& bin : release->cells[0].semantic->bins) categoryTotal += bin.observationContributions;
    require(categoryTotal == 196, "Immutable semantic output copied corrupted diagnostic counts");
    require(!publisher.deliver(800, [](const auto&) { return SinkResult::Retry; })
        && publisher.pendingRelease() == release && publisher.state().retiredThroughMs == 0,
        "Recipient retry prematurely retired semantic support");
    require(publisher.deliver(800, [&](const auto& immutable) {
        require(immutable.cells[0].semantic->maxLoss == .5 && immutable.cells[0].aggregate.counts.observationContributions == 196,
            "Immutable recipient retry changed semantic content");
        return SinkResult::Acknowledged;
    }) && publisher.state().retiredThroughMs == 800 && !publisher.pendingRelease(),
        "Acknowledged semantic publication failed to retire its original interval");

    auto eofConfig = settings();
    std::vector<CellObservation> people;
    addPeople(people, eofConfig, "a", "Adult Cyclist", 2);
    addPeople(people, eofConfig, "c", "Child Cyclist", 2);
    AggregationHistory history(eofConfig, *eofConfig.history);
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(eofConfig, preferenceTime(800),
        {1, 128, true}, metrics(eofConfig, 4, 1, 20), [&](const auto& selection) { output.push_back(selection); });
    for (int time : {100, 200, 300, 400}) {
        append(history, eofConfig, time, people);
        engine.advance(time, history);
    }
    require(output.empty(), "EOF fixture used its positive-loss fallback before EOF");
    history.advance(450);
    engine.finish(450, history);
    require(output.size() == 1 && output[0].candidate.startMs == 0 && output[0].candidate.endMs == 450
        && output[0].completionReason == "end_of_stream" && retained(output[0]) == 16
        && actualMaximumLoss(output[0]) == .5 && output[0].semanticPriority->terminalFallback,
        "EOF did not terminate the original short semantic interval with a legal fallback");
}

void emptyWindowAndConfigurationGuards() {
    auto config = settings();
    AggregationHistory history(config, *config.history);
    initialHistory(history, config, {});
    std::vector<SpatialSelection> output;
    AdaptiveAggregation engine(config, preferenceTime(800),
        {1, 128, true}, metrics(config), [&](const auto& selection) { output.push_back(selection); });
    engine.advance(400, history);
    require(output.size() == 1 && output[0].selectedCells == 0 && output[0].suppressedCells == 0
        && output[0].candidate.endMs == 400 && output[0].semanticPriority
        && !output[0].semanticPriority->actualMaxLoss && !output[0].semanticPriority->terminalFallback,
        "Complete measured-empty support waited or fabricated semantic loss");
    require(std::string(adaptationStrategyName(AdaptationStrategy::SemanticFirst)) == "semantic_first",
        "Semantic strategy name is not stable");
    auto noCatalog = config;
    noCatalog.semanticTaxonomy.reset();
    rejects([&] {
        AdaptiveAggregation invalid(noCatalog, preferenceTime(800), {1, 128, true},
            MetricEvaluator(MetricPolicy{"plain", "1", {{MetricId::DistinctContributors, 1, {}}}}), [](const auto&) {});
    }, "Semantic First accepted missing taxonomy/evaluator context");
    rejects([&] {
        AdaptiveAggregation invalid(config, preferenceTime(800), {1, 128, true},
            metrics(settings()), [](const auto&) {});
    }, "Semantic First accepted a different trusted taxonomy instance");
    auto local = preferenceTime(800);
    local.coordination = CoordinationMode::CellLocal;
    rejects([&] { AdaptiveAggregation invalid(config, local, {1, 128, true}, metrics(config), [](const auto&) {}); },
        "Semantic First silently accepted cell-local coordination");
}

void resourceFailureAndInvalidPreferenceLeaveTheWindowPrivate() {
    auto config = settings();
    auto evaluator = metrics(config);
    std::vector<CellObservation> people;
    for (int id = 48; id <= 51; ++id) {
        addPeople(people, config, "p" + std::to_string(id) + "/", "Pedestrian", 19, id);
        addPeople(people, config, "a" + std::to_string(id) + "/", "Adult Cyclist", 1, id);
    }
    AggregationHistory history(config, *config.history);
    initialHistory(history, config, people);
    int sinkCalls = 0;
    // Four occupied finest cells fill the entire attempt budget. At ceiling0,
    // their hard-passing RoadUser bins are rejected as preferences, requiring a
    // fifth assessment for the exact parent. Fail before a terminal sink call.
    AdaptiveAggregation bounded(config, preferenceTime(800),
        {1, 4, true}, evaluator, [&](const auto&) { ++sinkCalls; });
    const auto before = bounded.debugState();
    bool lengthFailure = false;
    try { bounded.advance(400, history); }
    catch (const std::length_error&) { lengthFailure = true; }
    require(lengthFailure && sinkCalls == 0, "Preference coarsening ignored the fifth-attempt budget or disclosed output");
    const auto after = bounded.debugState();
    require(after.windowStartMs == before.windowStartMs && after.nextEndMs == before.nextEndMs
        && after.hardDeadlineMs == before.hardDeadlineMs && after.temporalEvaluations == before.temporalEvaluations
        && after.temporalExtensions == before.temporalExtensions && after.retainedDecisions == before.retainedDecisions
        && after.completedWindows == before.completedWindows && after.finished == before.finished,
        "Resource failure mutated the active private interval, evaluations or decisions");
    const auto finest = history.queryFinest(0, 400);
    require(finest.candidate && finest.candidate->counts.observationContributions == 240,
        "Resource failure consumed or altered retained source evidence");
    SpatialSelector selector(config, {1, 5, true});
    for (double ceiling : {std::numeric_limits<double>::quiet_NaN(), -0.1, 1.1}) {
        bool invalid = false;
        try { selector.propose(*finest.candidate, history, evaluator, ceiling); }
        catch (const std::invalid_argument&) { invalid = true; }
        require(invalid, "Optional semantic ceiling accepted NaN, a negative value or a value above one");
    }
    bool wrongCatalog = false;
    try { selector.propose(*finest.candidate, history, metrics(settings()), 0.0); }
    catch (const std::invalid_argument&) { wrongCatalog = true; }
    require(wrongCatalog, "Optional semantic ceiling accepted a mismatched trusted taxonomy instance");
    const auto sufficient = selector.propose(*finest.candidate, history, evaluator, 0.0);
    require(sufficient.selectedCells == 1 && retained(sufficient) == 240
        && sufficient.candidate.cells[chosen(sufficient)[0]].cell.id == 12
        && actualMaximumLoss(sufficient) == 0 && sinkCalls == 0,
        "Rejected preferences mutated selector state or prevented a bounded exact parent proposal");
}
} // namespace

int main() {
    try {
        exactParentWinsOverFineGeneralizedRoadUser();
        zeroCostInternalCategoryCountsAsPreferred();
        delayedParentFallback();
        temporalExactRescueKeepsOriginalInterval();
        terminalPartialRetentionPrecedesSemanticDetail();
        equallyRetainingPartialCutsPreferLowerActualMaximum();
        maximumLossPreferenceDoesNotClaimMeanLossOptimality();
        regionalDetailAndMeanRemainHardConstraints();
        unavailableCoverageTerminatesWithoutPositiveFallback();
        sinkExceptionPreservesPrivateProposalAndContiguousSuccessor();
        eofFallbackAndImmutableOriginalEvaluatorPublication();
        emptyWindowAndConfigurationGuards();
        resourceFailureAndInvalidPreferenceLeaveTheWindowPrivate();
        std::cout << "PASS: 13 native Semantic First acceptance cases, original policies, bounded fallback and immutable publication.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Semantic First acceptance failure: " << error.what() << '\n';
        return 1;
    }
}
