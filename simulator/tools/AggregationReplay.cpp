#include "AdaptiveAggregation.hpp"
#include "CellLocalAggregation.hpp"
#include "AggregationConfiguration.hpp"
#include "AggregationManager.hpp"
#include "PolicyConfiguration.hpp"
#include "PolicyTree.hpp"
#include "PublicationCoordinator.hpp"
#include "PacedReplay.hpp"
#include <yaml-cpp/yaml.h>
#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <fcntl.h>
#include <unistd.h>
#include <sys/resource.h>
#ifdef __APPLE__
#include <mach/mach.h>
#endif

// This executable is an offline, private research adapter. It uses the same
// aggregation/policy/publication cores as the simulator; it never opens MongoDB.
namespace umpReplay {
using namespace ump;
constexpr std::uintmax_t maxDocumentBytes = 256ULL * 1024 * 1024;
constexpr AggregationTime maxReplayTicks = 10000000;

void keys(const YAML::Node& node, std::initializer_list<const char*> allowed, const char* context) {
    if (!node.IsMap()) throw std::invalid_argument(std::string(context) + " must be a map");
    std::set<std::string> seen;
    for (const auto& item : node) {
        const auto key = item.first.as<std::string>();
        bool known = false;
        for (const auto* value : allowed) known = known || key == value;
        if (!known || !seen.insert(key).second)
            throw std::invalid_argument(std::string("Unknown or duplicate ") + context + " key: " + key);
    }
}
std::string nonempty(const YAML::Node& node, const char* key) {
    const auto value = node[key].as<std::string>();
    if (value.empty()) throw std::invalid_argument(std::string(key) + " must be nonempty");
    return value;
}
YAML::Node load(const std::filesystem::path& file) {
    if (!std::filesystem::is_regular_file(file) || std::filesystem::file_size(file) > maxDocumentBytes)
        throw std::invalid_argument("Replay input/config must be regular files of at most 256 MiB");
    return YAML::LoadFile(file.string());
}
std::string quoted(const std::string& value) {
    std::ostringstream out; out << '"';
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') out << '\\' << char(c);
        else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c) << std::dec;
        else out << char(c);
    }
    out << '"'; return out.str();
}
template<class T> std::string number(T value) {
    if (!std::isfinite(static_cast<double>(value))) throw std::invalid_argument("Non-finite JSON number");
    std::ostringstream out; out << std::setprecision(17) << value; return out.str();
}
std::string optionalNumber(std::optional<double> value) { return value ? number(*value) : "null"; }
using Fields = std::vector<std::pair<std::string, std::string>>;
std::string object(const Fields& fields) {
    std::string result = "{"; bool first = true;
    for (const auto& [key, value] : fields) {
        if (!first) result += ',';
        first = false; result += quoted(key) + ':' + value;
    }
    return result + '}';
}
std::string array(const std::vector<std::string>& values) {
    std::string result = "["; bool first = true;
    for (const auto& value : values) {
        if (!first) result += ',';
        first = false; result += value;
    }
    return result + ']';
}
Fields geometry(const CellGeometry& cell) {
    return {{"cell_id", number(cell.id)}, {"depth", number(cell.depth)},
        {"x", number(cell.x)}, {"y", number(cell.y)}, {"width", number(cell.width)}, {"height", number(cell.height)}};
}
std::string scopedObject(Fields fields, const std::optional<CellGeometry>& scope) {
    if (scope) fields.emplace_back("coordination_cell", object(geometry(*scope)));
    return object(fields);
}
void counts(Fields& fields, const AggregateCounts& value) {
    fields.emplace_back("observation_contributions", number(value.observationContributions));
    fields.emplace_back("distinct_road_users", number(value.distinctContributors));
    fields.emplace_back("mean_sample_occupancy", optionalNumber(value.meanSampleOccupancy));
}
std::string coverageName(WindowCoverage value) {
    switch (value) {
        case WindowCoverage::Complete: return "complete";
        case WindowCoverage::Incomplete: return "incomplete";
        case WindowCoverage::NoScheduledSamples: return "no_scheduled_samples";
    }
    throw std::invalid_argument("Unknown coverage status");
}

struct Input {
    std::string runId, sensorId;
    GridCoverage grid;
    AggregationTime periodMs, endMs;
    std::vector<ObservationBatch> batches;
    bool hasCoordinates = true;
};
Input parseInput(const YAML::Node& node) {
    keys(node, {"schema", "run_id", "sensor_id", "coverage", "sampling_period_ms", "end_ms", "batches"}, "replay input");
    if (node["schema"].as<std::string>() != "ump.observation-replay.v1")
        throw std::invalid_argument("Unsupported replay input schema");
    const auto grid = node["coverage"];
    keys(grid, {"x", "y", "width", "height", "leaf_depth"}, "coverage");
    Input input{nonempty(node, "run_id"), nonempty(node, "sensor_id"),
        {grid["x"].as<double>(), grid["y"].as<double>(), grid["width"].as<double>(), grid["height"].as<double>(), grid["leaf_depth"].as<int>()},
        node["sampling_period_ms"].as<AggregationTime>(), node["end_ms"].as<AggregationTime>(), {}, true};
    historyCell(input.grid, 12, 1);
    if (input.periodMs <= 0 || input.endMs <= 0 || input.endMs / input.periodMs > maxReplayTicks)
        throw std::invalid_argument("Positive cadence/end and at most ten million replay ticks are required");
    if (!node["batches"].IsSequence()) throw std::invalid_argument("batches must be a sequence");
    AggregationTime previousTime = 0;
    std::uint64_t previousSequence = 0;
    for (const auto& item : node["batches"]) {
        keys(item, {"sequence", "observed_at_ms", "status", "observations"}, "batch");
        const auto sequence = item["sequence"].as<std::int64_t>();
        const auto time = item["observed_at_ms"].as<AggregationTime>();
        const auto status = item["status"].as<std::string>();
        if (sequence <= 0 || static_cast<std::uint64_t>(sequence) <= previousSequence || time <= previousTime
            || time >= input.endMs || time % input.periodMs != 0)
            throw std::invalid_argument("Batches require increasing sequence/time on cadence, strictly inside (0,end_ms)");
        if (status != "measured" && status != "unavailable") throw std::invalid_argument("Unknown batch status");
        ObservationBatch batch{input.runId, input.sensorId, static_cast<std::uint64_t>(sequence), time,
            status == "measured" ? ObservationStatus::Measured : ObservationStatus::Unavailable, {}};
        if (!item["observations"].IsSequence()) throw std::invalid_argument("observations must be a sequence");
        std::set<std::string> identities;
        for (const auto& observation : item["observations"]) {
            keys(observation, {"id", "type", "cell_id", "x", "y"}, "observation");
            const auto id = nonempty(observation, "id"), type = nonempty(observation, "type");
            if (!identities.insert(id).second) throw std::invalid_argument("Duplicate identity within one sample");
            const auto cell = historyCell(input.grid, observation["cell_id"].as<int>(), input.grid.leafDepth);
            if (bool(observation["x"]) != bool(observation["y"]))
                throw std::invalid_argument("Ground-truth coordinates require both x and y");
            if (observation["x"]) {
                const double x = observation["x"].as<double>(), y = observation["y"].as<double>();
                if (!std::isfinite(x) || !std::isfinite(y) || x < cell.x || y < cell.y
                    || x >= cell.x + cell.width || y >= cell.y + cell.height)
                    throw std::invalid_argument("Ground-truth coordinates are outside their half-open declared cell");
            } else input.hasCoordinates = false;
            batch.observations.push_back({id, type, cell});
        }
        if (batch.status == ObservationStatus::Unavailable && !batch.observations.empty())
            throw std::invalid_argument("Unavailable batches cannot contain observations");
        previousTime = time; previousSequence = batch.sequence;
        input.batches.push_back(std::move(batch));
    }
    return input;
}

MetricEvaluator evaluatorFrom(const YAML::Node& config, const AggregationConfig& settings) {
    const auto uniform = config["metric_policy"], tree = config["policy_tree"];
    if (bool(uniform) == bool(tree)) throw std::invalid_argument("Exactly one metric_policy or policy_tree is required");
    validatePolicyExecution(config);
    if (uniform) {
        keys(uniform, {"id", "version", "requirements"}, "metric_policy");
        if (config["policy_regions"] && config["policy_regions"].size())
            throw std::invalid_argument("policy_regions requires policy_tree");
        return MetricEvaluator(MetricPolicy{nonempty(uniform, "id"), nonempty(uniform, "version"),
            readMetricRequirements(uniform["requirements"])}, settings.semanticTaxonomy);
    }
    keys(tree, {"id", "version", "root", "regions", "max_nodes", "execution"}, "policy_tree");
    const auto budget = tree["max_nodes"].as<std::int64_t>(65536);
    if (budget <= 0) throw std::invalid_argument("policy_tree.max_nodes must be positive");
    std::map<std::string, PolicyRegion> definitions;
    const auto regions = config["policy_regions"];
    if (regions && !regions.IsSequence()) throw std::invalid_argument("policy_regions must be a sequence");
    if (regions) for (const auto& region : regions) {
        keys(region, {"id", "type", "x", "y", "width", "height", "type_requirements", "requirements"}, "policy region");
        PolicyRegion value{nonempty(region, "id"), region["type"].as<std::string>("replay_region"),
            region["x"].as<double>(), region["y"].as<double>(), region["width"].as<double>(), region["height"].as<double>(),
            readMetricRequirements(region["type_requirements"], true), readMetricRequirements(region["requirements"], true)};
        if (!definitions.emplace(value.id, std::move(value)).second) throw std::invalid_argument("Duplicate policy region");
    }
    if (!tree["regions"].IsSequence()) throw std::invalid_argument("policy_tree.regions must be a sequence of IDs");
    std::set<std::string> seen;
    std::vector<PolicyRegion> selected;
    for (const auto& reference : tree["regions"]) {
        const auto id = reference.as<std::string>();
        if (!seen.insert(id).second || !definitions.count(id)) throw std::invalid_argument("Duplicate or unknown policy region reference");
        selected.push_back(definitions.at(id));
    }
    if (seen.size() != definitions.size()) throw std::invalid_argument("Unreferenced policy_regions are not applied");
    const auto rootRequirements = readMetricRequirements(tree["root"]);
    if (settings.semanticTaxonomy) validateSemanticMetricRequirements(rootRequirements);
    return MetricEvaluator(std::make_shared<const PolicyTree>(PolicyTreeConfig{
        nonempty(tree, "id"), nonempty(tree, "version"), settings.applicationId, settings.coverage,
        rootRequirements, static_cast<std::size_t>(budget)}, std::move(selected)), settings.semanticTaxonomy);
}

struct Options {
    std::filesystem::path input, config, output;
    std::string mode;
    std::optional<int> fixedDepth;
    std::optional<AggregationTime> fixedWindowMs;
    std::optional<double> paceRate;
    std::optional<AggregationTime> progressStepMs;
    std::size_t queueCapacity = 64;
};
// Optional native-style progress is a separate clock from sensor sampling.
// Leave the historical replay path unchanged unless the option is explicit.
AggregationTime progressStepFor(const Input& input, const Options& options) {
    if (!options.progressStepMs) return input.periodMs;
    const auto step = *options.progressStepMs;
    if (step <= 0 || step > input.periodMs || input.periodMs % step != 0 || input.endMs % step != 0)
        throw std::invalid_argument("Progress step must be positive, divide the sensor period, not exceed it, and align the horizon");
    // Include initialization at zero and finalization in the event budget.
    const auto events = static_cast<std::uint64_t>(input.endMs / step) + 1;
    if (events > static_cast<std::uint64_t>(maxReplayTicks))
        throw std::invalid_argument("Explicit progress supports at most ten million initialization/progress/finish events");
    if (options.paceRate && events > 100000)
        throw std::invalid_argument("Pacing supports at most 100000 initialization/progress/finish events");
    return step;
}
struct Settings {
    AggregationConfig aggregation;
    SpatialSelectionConfig spatial;
    std::optional<TemporalAdaptationConfig> temporal;
    MetricEvaluator evaluator;
    int fixedDepth;
    std::string configurationYaml;
};
Settings parseSettings(YAML::Node node, const Input& input, const Options& options) {
    (void)progressStepFor(input, options);
    keys(node, {"application_id", "window_ms", "max_observations_per_window", "history", "spatial_selection",
        "temporal_adaptation", "metric_policy", "policy_tree", "policy_regions", "semantic_taxonomy"}, "replay configuration");
    if (options.mode != "fixed" && options.mode != "spatial" && options.mode != "temporal_first"
        && options.mode != "spatial_first" && options.mode != "semantic_first")
        throw std::invalid_argument("mode must be fixed, spatial, temporal_first, spatial_first or semantic_first");
    if (options.mode != "fixed" && (options.fixedDepth || options.fixedWindowMs))
        throw std::invalid_argument("Fixed-grid overrides require --mode fixed");
    validatePolicyExecution(node); // Reject malformed execution settings before an explicit mode override.
    const auto configuredWindow = node["window_ms"].as<AggregationTime>();
    AggregationConfig settings{input.runId, input.sensorId, nonempty(node, "application_id"), input.grid,
        input.periodMs, options.fixedWindowMs.value_or(configuredWindow)};
    const auto maxObservations = node["max_observations_per_window"].as<std::int64_t>(1000000);
    if (maxObservations <= 0) throw std::invalid_argument("max_observations_per_window must be positive");
    settings.maxObservationsPerWindow = static_cast<std::uint64_t>(maxObservations);
    settings.history = readHistoryLimits(node["history"]);
    settings.semanticTaxonomy = readSemanticTaxonomy(node);
    if (!settings.history) throw std::invalid_argument("Replay requires explicit bounded history");
    const auto spatial = readSpatialSelection(node, input.grid.leafDepth);
    if (!spatial) throw std::invalid_argument("Replay requires explicit spatial_selection limits");
    const bool adaptive = options.mode == "temporal_first" || options.mode == "spatial_first"
        || options.mode == "semantic_first";
    // The CLI changes execution order only. It never changes a metric threshold.
    std::optional<TemporalAdaptationConfig> temporal;
    if (adaptive) {
        if (!node["policy_tree"] || !node["temporal_adaptation"])
            throw std::invalid_argument("Adaptive replay requires policy_tree and temporal_adaptation");
        node["policy_tree"]["execution"]["strategy"] = options.mode;
        // The original execution contract was validated above. A CLI override
        // to TF/SF replaces semantic ordering, so its secondary no longer applies.
        // Keep the taxonomy and every hard regional metric bound unchanged.
        if (options.mode != "semantic_first")
            node["policy_tree"]["execution"].remove("semantic_secondary_strategy");
        temporal = readTemporalAdaptation(node);
    } else {
        // Validate optional adaptation configuration even when this baseline does not use it.
        if (node["temporal_adaptation"]) (void)readTemporalAdaptation(node);
    }
    const int depth = options.fixedDepth.value_or(input.grid.leafDepth);
    if (depth < 1 || depth > input.grid.leafDepth) throw std::invalid_argument("Fixed depth is outside [1,leaf_depth]");
    auto evaluator = evaluatorFrom(node, settings);
    // Full preflight happens before the result or any partial output is written.
    AggregationManager validate(settings, [](const auto&) {});
    for (const auto& batch : input.batches) validate.ingest(batch);
    validate.finish(input.endMs);
    return {std::move(settings), *spatial, temporal, std::move(evaluator), depth, YAML::Dump(node)};
}

SpatialSelection fixedSelection(const AggregationCandidate& finest, const AggregationHistory& history,
    const MetricEvaluator& evaluator, int depth) {
    auto candidate = finest;
    candidate.cells.clear();
    std::set<int> parents;
    for (const auto& cell : finest.cells) parents.insert(cell.cell.id >> (2 * (cell.cell.depth - depth)));
    for (int id : parents) {
        const auto query = history.query(historyCell(finest.grid, id, depth), finest.startMs, finest.endMs);
        if (!query.candidate) throw std::runtime_error("Fixed baseline is no longer reconstructable");
        candidate.cells.push_back(query.candidate->cells.at(0));
    }
    auto assessed = evaluator.evaluate(candidate, candidate.closedAtMs);
    SpatialSelection result{candidate, assessed, finest, evaluator.evaluate(finest, finest.closedAtMs), {}, {}, depth};
    result.strategy = "fixed";
    for (std::size_t i = 0; i < candidate.cells.size(); ++i) {
        const bool selected = candidate.coverage == WindowCoverage::Complete && assessed.cells[i].status == AssessmentStatus::Pass;
        result.decisions.push_back({candidate.cells[i].cell.id, selected,
            selected ? "fixed_requirements_met" : "fixed_requirements_failed", {}, selected ? "fixed" : "suppressed"});
        result.selectedCells += selected;
        result.suppressedCells += !selected;
    }
    return result;
}

std::string serializeSemantic(const SemanticRepresentation& value) {
    std::vector<std::string> bins;
    for (const auto& bin : value.bins)
        bins.push_back(object({{"category_id", quoted(bin.categoryId)},
            {"observation_contributions", number(bin.observationContributions)},
            {"distinct_contributors", number(bin.distinctContributors)}}));
    return object({{"schema", quoted("ump.semantic-release.v1")},
        {"taxonomy_id", quoted(value.taxonomyId)}, {"taxonomy_version", quoted(value.taxonomyVersion)},
        {"min_category_distinct_contributors", number(value.minimumDistinctContributors)},
        {"semantic_max_loss", number(value.maxLoss)}, {"semantic_mean_loss", number(value.meanLoss)},
        {"categories", array(bins)}});
}

std::string serializeWindow(const SpatialSelection& selection) {
    const auto& c = selection.candidate;
    std::vector<std::string> cells, decisions;
    for (std::size_t i = 0; i < c.cells.size(); ++i) {
        auto fields = geometry(c.cells[i].cell);
        counts(fields, c.cells[i].counts);
        fields.emplace_back("selected", selection.decisions[i].selected ? "true" : "false");
        fields.emplace_back("reason", quoted(selection.decisions[i].reason));
        fields.emplace_back("assessment_status", quoted(assessmentStatusName(selection.assessment.cells[i].status)));
        Fields metrics;
        std::vector<std::string> checks;
        for (const auto& metric : selection.assessment.cells[i].metrics) {
            if (metric.unavailableReason == "semantic_not_enabled") continue;
            metrics.emplace_back(metricDefinition(metric.id).name, optionalNumber(metric.value));
        }
        if (selection.assessment.cells[i].semantic)
            fields.emplace_back("semantic", serializeSemantic(*selection.assessment.cells[i].semantic));
        for (const auto& check : selection.assessment.cells[i].checks)
            checks.push_back(object({{"metric", quoted(metricDefinition(check.requirement.id).name)},
                {"min", optionalNumber(check.requirement.min)}, {"max", optionalNumber(check.requirement.max)},
                {"observed", optionalNumber(check.observed)}, {"status", quoted(assessmentStatusName(check.status))},
                {"reason", quoted(check.reason)}}));
        fields.emplace_back("metrics", object(metrics));
        fields.emplace_back("checks", array(checks));
        cells.push_back(object(fields));
    }
    for (const auto& decision : selection.temporalDecisions)
        decisions.push_back(object({{"action", quoted(temporalActionName(decision.action))},
            {"start_ms", number(decision.startMs)}, {"end_ms", number(decision.endMs)},
            {"evaluated_at_ms", number(decision.evaluatedAtMs)}, {"status", quoted(assessmentStatusName(decision.status))}}));
    Fields windowFields = {{"start_ms", number(c.startMs)}, {"end_ms", number(c.endMs)},
        {"evaluated_at_ms", number(c.closedAtMs)}, {"truncated", c.truncated ? "true" : "false"},
        {"expected_samples", number(c.expectedSamples)}, {"measured_samples", number(c.measuredSamples)},
        {"unavailable_samples", number(c.unavailableSamples)}, {"missing_samples", number(c.missingSamples)},
        {"coverage", quoted(coverageName(c.coverage))}, {"strategy", quoted(selection.strategy)},
        {"completion_reason", quoted(selection.completionReason)}, {"temporal_extensions", number(selection.temporalExtensions)},
        {"selected_cells", number(selection.selectedCells)}, {"suppressed_cells", number(selection.suppressedCells)},
        {"input_observation_contributions", number(c.counts.observationContributions)},
        {"policy_id", quoted(selection.assessment.policyId.value_or(""))},
        {"policy_version", quoted(selection.assessment.policyVersion.value_or(""))},
        {"cells", array(cells)}, {"temporal_decisions", array(decisions)}};
    if (selection.semanticPriority) {
        const auto& preference = *selection.semanticPriority;
        windowFields.emplace_back("semantic_priority", object({
            {"schema", quoted("ump.semantic-priority.v1")},
            {"secondary_strategy", quoted(preference.secondaryStrategy)},
            {"release_trigger", quoted(preference.releaseTrigger)},
            {"policy_satisfied_release", preference.policySatisfiedRelease ? "true" : "false"},
            {"preferred_max_loss", number(0)},
            {"selected_max_loss_ceiling", number(preference.lossCeiling)},
            {"actual_max_loss", optionalNumber(preference.actualMaxLoss)},
            {"attempted_ceilings", number(preference.attemptedCeilings)},
            {"terminal_fallback", preference.terminalFallback ? "true" : "false"}}));
    }
    return scopedObject(std::move(windowFields), selection.coordinationCell);
}
std::string serializeRelease(const ReleaseSnapshot& release) {
    std::vector<std::string> cells;
    for (const auto& cell : release.cells) {
        auto fields = geometry(cell.aggregate.cell); counts(fields, cell.aggregate.counts);
        fields.emplace_back("effective_policy_id", quoted(cell.effectivePolicyId));
        if (cell.semantic) fields.emplace_back("semantic", serializeSemantic(*cell.semantic));
        cells.push_back(object(fields));
    }
    return scopedObject({{"release_id", quoted(release.releaseId)}, {"start_ms", number(release.startMs)},
        {"end_ms", number(release.endMs)}, {"sealed_at_ms", number(release.sealedAtMs)},
        {"model", quoted(release.model)}, {"policy_id", quoted(release.policyId)},
        {"policy_version", quoted(release.policyVersion)}, {"cells", array(cells)}}, release.coordinationCell);
}

// Process RSS includes parsed input, allocators and retained research output.
// History counters below identify bounded algorithm storage separately.
std::optional<std::uint64_t> residentBytes() {
#ifdef __APPLE__
    mach_task_basic_info_data_t info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO, reinterpret_cast<task_info_t>(&info), &count) == KERN_SUCCESS)
        return static_cast<std::uint64_t>(info.resident_size);
#elif defined(__linux__)
    std::ifstream statm("/proc/self/statm");
    std::uint64_t total = 0, resident = 0;
    const long pageSize = ::sysconf(_SC_PAGESIZE);
    if (statm >> total >> resident && pageSize > 0) return resident * static_cast<std::uint64_t>(pageSize);
#endif
    return std::nullopt;
}
std::optional<std::uint64_t> peakResidentBytes() {
    struct rusage usage {};
    if (::getrusage(RUSAGE_SELF, &usage) != 0) return std::nullopt;
#ifdef __APPLE__
    return static_cast<std::uint64_t>(usage.ru_maxrss);
#else
    return static_cast<std::uint64_t>(usage.ru_maxrss) * 1024;
#endif
}
std::string optionalBytes(std::optional<std::uint64_t> bytes) { return bytes ? number(*bytes) : "null"; }

std::string run(const Input& input, const Settings& settings, const Options& options) {
    const auto progressStepMs = progressStepFor(input, options);
    const auto started = std::chrono::steady_clock::now();
    const auto& config = settings.aggregation;
    const bool localMode = settings.temporal && settings.temporal->coordination == CoordinationMode::CellLocal;
    PublicationLimits publicationLimits;
    if (localMode) publicationLimits.maxCoordinationNodes = settings.temporal->maxActiveCells * 2;
    PublicationCoordinator publication(config, settings.evaluator, publicationLimits,
        settings.temporal ? std::optional<AggregationTime>{settings.temporal->maxWindowMs} : std::nullopt, localMode);
    std::vector<std::string> windows, releases, releaseTimings, memorySamples;
    ReplayClock::time_point pacingEpoch;
    std::optional<PacingReport> pacing;
    AggregationTime currentEventMs = 0;
    std::size_t serializedBytes = 0;
    const auto retain = [&](std::vector<std::string>& destination, std::string value) {
        if (value.size() > maxDocumentBytes - serializedBytes)
            throw std::length_error("Replay result exceeds the 256 MiB output budget");
        serializedBytes += value.size(); destination.push_back(std::move(value));
    };
    std::uint64_t inputContributions = 0, accountedContributions = 0;
    for (const auto& batch : input.batches) inputContributions += batch.observations.size();
    const auto terminal = [&](const SpatialSelection& selection) {
        publication.seal(selection, selection.candidate.closedAtMs);
        if (!publication.deliver(selection.candidate.closedAtMs, [&](const auto& release) {
            retain(releases, serializeRelease(release));
            if (options.paceRate) retain(releaseTimings, object({
                {"release_id", quoted(release.releaseId)},
                {"input_event_ms", number(currentEventMs)},
                {"logical_window_end_ms", number(release.endMs)},
                {"logical_sealed_at_ms", number(release.sealedAtMs)},
                {"in_memory_ack_ms", number(replayOffsetMs(pacingEpoch))}}));
            return SinkResult::Acknowledged;
        })) throw std::runtime_error("Offline release was not acknowledged");
        accountedContributions += selection.candidate.counts.observationContributions;
        retain(windows, serializeWindow(selection));
    };
    SpatialSelector spatial(config, settings.spatial);
    AggregationManager* managerPtr = nullptr;
    AggregationManager manager(config, [&](const auto& candidate) {
        if (settings.temporal) return;
        if (options.mode == "fixed") terminal(fixedSelection(candidate, *managerPtr->history(), settings.evaluator, settings.fixedDepth));
        else {
            auto selected = spatial.propose(candidate, *managerPtr->history(), settings.evaluator);
            selected.strategy = "spatial";
            terminal(selected); spatial.commit(selected);
        }
    });
    managerPtr = &manager;
    std::unique_ptr<AdaptiveAggregation> adaptive;
    std::unique_ptr<CellLocalAggregation> local;
    if (localMode) {
        local = std::make_unique<CellLocalAggregation>(config, *settings.temporal, settings.spatial,
            settings.evaluator, terminal, settings.temporal->maxActiveCells);
        manager.setProgressSink([&](auto now, bool finishing) {
            if (finishing) local->finish(now, *manager.history());
            else local->advance(now, *manager.history());
        });
    } else if (settings.temporal) {
        adaptive = std::make_unique<AdaptiveAggregation>(config, *settings.temporal, settings.spatial, settings.evaluator, terminal);
        manager.setProgressSink([&](auto now, bool finishing) {
            if (finishing) adaptive->finish(now, *manager.history());
            else adaptive->advance(now, *manager.history());
        });
    }
    std::size_t batchIndex = 0;
    const auto consume = [&](AggregationTime time, bool finishing) {
        currentEventMs = time;
        if (finishing) manager.finish(time);
        else {
            // The native sensor first advances its manager on every simulator
            // tick, then ingests an actual due measurement. ingest() appends
            // history and notifies progress again at the same sample time.
            // Merely inserting extra no-sample ticks would miss this ordering.
            if (options.progressStepMs) manager.advance(time);
            if (batchIndex < input.batches.size() && input.batches[batchIndex].observedAtMs == time)
                manager.ingest(input.batches[batchIndex++]);
            else if (!options.progressStepMs) manager.advance(time);
        }
    };
    if (options.paceRate) {
        // Build a small immutable arrival schedule, not copies of observations.
        // Sensor sampling remains unchanged when a finer progress clock is used.
        // Origin initialization is processed directly at the pacing epoch; the
        // positive event schedule retains the existing PacedReplay contract.
        const auto count = static_cast<std::uint64_t>((input.endMs - 1) / progressStepMs) + 1;
        if (count > 100000) throw std::invalid_argument("Pacing supports at most 100000 cadence/finish events");
        std::vector<PacedEvent> events;
        events.reserve(static_cast<std::size_t>(count));
        for (AggregationTime time = progressStepMs; time < input.endMs;) {
            events.push_back({time, false});
            if (time > std::numeric_limits<AggregationTime>::max() - progressStepMs) break;
            time += progressStepMs;
        }
        events.push_back({input.endMs, true});
        validatePacing(events, *options.paceRate, options.queueCapacity);
        const auto sampleMemory = [&](AggregationTime logicalTime) {
            const auto state = manager.history()->debugState();
            retain(memorySamples, object({{"logical_time_ms", number(logicalTime)},
                {"wall_ms", number(replayOffsetMs(pacingEpoch))},
                {"process_resident_bytes", optionalBytes(residentBytes())},
                {"process_peak_resident_bytes", optionalBytes(peakResidentBytes())},
                {"history_bins", number(state.bins)}, {"history_observations", number(state.observations)},
                {"history_identity_bytes", number(state.identityBytes)}, {"history_buckets", number(state.buckets)},
                {"retained_result_bytes", number(serializedBytes)}}));
        };
        // Parsing, validation and core construction precede the arrival origin.
        pacingEpoch = ReplayClock::now();
        if (options.progressStepMs) consume(0, false);
        sampleMemory(0);
        AggregationTime nextMemorySample = 1000;
        pacing = runPaced(events, *options.paceRate, options.queueCapacity, pacingEpoch, [&](const auto& event) {
            consume(event.logicalTimeMs, event.finishing);
            if (event.logicalTimeMs >= nextMemorySample || event.finishing) {
                sampleMemory(event.logicalTimeMs);
                nextMemorySample = event.logicalTimeMs + 1000;
            }
        });
    } else {
        // Default: historical sensor-cadence clock. Explicit: native-style
        // initialization and progress, including ticks without measurements.
        if (options.progressStepMs) consume(0, false);
        for (AggregationTime time = progressStepMs; time < input.endMs;) {
            consume(time, false);
            if (time > std::numeric_limits<AggregationTime>::max() - progressStepMs) break;
            time += progressStepMs;
        }
        consume(input.endMs, true);
    }
    if (batchIndex != input.batches.size() || publication.state().retiredThroughMs != input.endMs
        || inputContributions != accountedContributions)
        throw std::runtime_error("Replay failed interval retirement or observation conservation");
    const auto elapsed = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - started).count();
    const auto& g = input.grid;
    std::vector<std::pair<std::string, std::string>> parameters{
        {"coordination", quoted(localMode ? "cell_local" : "common_window")},
        {"window_ms", number(config.windowMs)}, {"fixed_depth", options.mode == "fixed" ? number(settings.fixedDepth) : "null"},
        {"min_depth", number(settings.spatial.minDepth)},
        {"extension_step_ms", settings.temporal ? number(settings.temporal->extensionStepMs) : "null"},
        {"max_window_ms", settings.temporal ? number(settings.temporal->maxWindowMs) : number(config.windowMs)}};
    if (options.progressStepMs) {
        parameters.emplace_back("progress_step_ms", number(*options.progressStepMs));
        parameters.emplace_back("progress_origin_ms", number(0));
    }
    if (settings.temporal && settings.temporal->strategy == AdaptationStrategy::SemanticFirst) {
        parameters.emplace_back("semantic_secondary_strategy", quoted(semanticSecondaryStrategyName(
            settings.temporal->semanticSecondaryStrategy)));
        parameters.emplace_back("release_trigger", quoted(releaseTriggerName(settings.temporal->releaseTrigger)));
    }
    Fields runtime{{"processing_ms", number(elapsed)}, {"clock", quoted("steady_clock")},
        {"scope", quoted(options.paceRate
            ? "core replay, pacing waits, telemetry and in-memory serialization; excludes input validation and file I/O"
            : "core replay and in-memory result serialization; excludes input validation and file I/O")}};
    if (pacing) {
        std::vector<std::string> timings;
        for (const auto& event : pacing->events) retain(timings, object({
            {"logical_time_ms", number(event.event.logicalTimeMs)},
            {"kind", quoted(event.event.finishing ? "finish" : "cadence")},
            {"scheduled_arrival_ms", number(event.scheduledArrivalMs)},
            {"enqueue_attempt_ms", number(event.enqueueAttemptMs)}, {"enqueued_ms", number(event.enqueuedMs)},
            {"service_start_ms", number(event.serviceStartMs)}, {"service_finish_ms", number(event.serviceFinishMs)},
            {"queue_depth_after_enqueue", number(event.queueDepthAfterEnqueue)}}));
        runtime.emplace_back("pacing", object({{"schema", quoted("ump.paced-replay.v1")},
            {"rate", number(*options.paceRate)}, {"queue_capacity", number(options.queueCapacity)},
            {"peak_queue_depth", number(pacing->peakQueueDepth)}, {"overload_behavior", quoted("fail_without_successful_output")},
            {"arrival_origin", quoted("steady_clock after parsing, validation and core setup")},
            {"release_timing_scope", quoted("serialized in-memory sink acknowledgement; file publication occurs after replay")},
            {"memory_scope", quoted("process RSS includes preloaded input and retained diagnostics; history counters separately describe bounded core storage")},
            {"service_scope", quoted("aggregation plus per-step in-memory serialization and telemetry")},
            {"events", array(timings)}, {"release_acknowledgements", array(releaseTimings)},
            {"memory_samples", array(memorySamples)}}));
    }
    return object({{"schema", quoted("ump.replay-result.v1")}, {"classification", quoted("private_research_diagnostics")},
        {"mode", quoted(options.mode)},
        {"configuration_yaml", quoted(settings.configurationYaml)},
        {"source", object({{"run_id", quoted(input.runId)}, {"sensor_id", quoted(input.sensorId)},
            {"application_id", quoted(config.applicationId)}, {"sampling_period_ms", number(input.periodMs)},
            {"end_ms", number(input.endMs)}, {"all_observations_have_coordinates", input.hasCoordinates ? "true" : "false"},
            {"coverage", object({{"x", number(g.x)}, {"y", number(g.y)}, {"width", number(g.width)},
                {"height", number(g.height)}, {"leaf_depth", number(g.leafDepth)}})}})},
        {"parameters", object(parameters)},
        {"runtime", object(runtime)},
        {"input_observation_contributions", number(inputContributions)},
        {"accounted_observation_contributions", number(accountedContributions)},
        {"empty_area_semantics", quoted("Only occupied footprints are released; absent public cells are unknown, never assumed zero")},
        {"windows", array(windows)}, {"releases", array(releases)}});
}

void writeNew(const std::filesystem::path& destination, const std::string& text) {
    if (destination.empty() || std::filesystem::exists(destination))
        throw std::invalid_argument("Output must name a new file; existing files are never replaced");
    const auto temporary = destination.string() + ".tmp-" + std::to_string(::getpid());
    const int fd = ::open(temporary.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (fd < 0) throw std::runtime_error("Cannot create temporary replay output");
    bool closed = false;
    try {
        std::size_t offset = 0;
        while (offset < text.size()) {
            const auto written = ::write(fd, text.data() + offset, text.size() - offset);
            if (written < 0 && errno == EINTR) continue;
            if (written <= 0) throw std::runtime_error("Cannot write replay output");
            offset += static_cast<std::size_t>(written);
        }
        if (::fsync(fd) != 0) throw std::runtime_error("Cannot flush replay output");
        const auto result = ::close(fd); closed = true;
        if (result != 0) throw std::runtime_error("Cannot close replay output");
        // Same-directory hard linking publishes a complete file atomically and
        // fails rather than replacing a concurrently created destination.
        std::filesystem::create_hard_link(temporary, destination);
        std::filesystem::remove(temporary);
    } catch (...) {
        if (!closed) ::close(fd);
        std::error_code ignored; std::filesystem::remove(temporary, ignored); throw;
    }
}
Options arguments(int argc, char** argv) {
    Options result;
    std::set<std::string> seen;
    for (int i = 1; i < argc; i += 2) {
        const std::string key = argv[i];
        if (i + 1 >= argc || !seen.insert(key).second) throw std::invalid_argument("Missing or duplicate CLI option");
        const std::string value = argv[i + 1];
        const auto integer = [&]() {
            std::size_t consumed = 0;
            const auto n = std::stoll(value, &consumed);
            if (consumed != value.size()) throw std::invalid_argument("Invalid numeric CLI option");
            return n;
        };
        if (key == "--input") result.input = value;
        else if (key == "--config") result.config = value;
        else if (key == "--output") result.output = value;
        else if (key == "--mode") result.mode = value;
        else if (key == "--fixed-window-ms") result.fixedWindowMs = integer();
        else if (key == "--progress-step-ms") {
            const auto step = integer();
            if (step <= 0) throw std::invalid_argument("Progress step must be positive");
            result.progressStepMs = step;
        }
        else if (key == "--pace-rate") {
            std::size_t consumed = 0;
            const double rate = std::stod(value, &consumed);
            if (consumed != value.size() || !std::isfinite(rate) || rate <= 0 || rate > 1000)
                throw std::invalid_argument("Pace rate must be finite and in (0,1000]");
            result.paceRate = rate;
        } else if (key == "--queue-capacity") {
            const auto capacity = integer();
            if (capacity < 1 || capacity > 100000) throw std::invalid_argument("Queue capacity must be in [1,100000]");
            result.queueCapacity = static_cast<std::size_t>(capacity);
        }
        else if (key == "--fixed-depth") {
            const auto depth = integer();
            if (depth < 1 || depth > 14) throw std::invalid_argument("Fixed depth must be in [1,14]");
            result.fixedDepth = static_cast<int>(depth);
        } else throw std::invalid_argument("Unknown CLI option: " + key);
    }
    if (result.input.empty() || result.config.empty() || result.output.empty() || result.mode.empty())
        throw std::invalid_argument("Required: --input FILE --config FILE --mode fixed|spatial|temporal_first|spatial_first|semantic_first --output NEW_FILE");
    if (seen.count("--queue-capacity") && !result.paceRate)
        throw std::invalid_argument("--queue-capacity requires --pace-rate");
    if (std::filesystem::exists(result.output)) throw std::invalid_argument("Output already exists");
    return result;
}
} // namespace umpReplay

#ifndef UMP_REPLAY_LIBRARY
int main(int argc, char** argv) {
    try {
        const auto options = umpReplay::arguments(argc, argv);
        const auto input = umpReplay::parseInput(umpReplay::load(options.input));
        const auto settings = umpReplay::parseSettings(umpReplay::load(options.config), input, options);
        umpReplay::writeNew(options.output, umpReplay::run(input, settings, options) + '\n');
        std::cout << "Replay completed: " << options.output << '\n'; return 0;
    } catch (const std::exception& error) {
        std::cerr << "AggregationReplay: " << error.what() << '\n'; return 1;
    }
}
#endif
