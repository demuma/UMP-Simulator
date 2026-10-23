#define UMP_REPLAY_LIBRARY
#include "../tools/AggregationReplay.cpp"

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class F> void rejects(F work, const char* message) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error(message);
}
YAML::Node source() {
    return YAML::Load(R"(
schema: ump.observation-replay.v1
run_id: frozen-run
sensor_id: sensor
coverage: {x: 0, y: 0, width: 80, height: 80, leaf_depth: 3}
sampling_period_ms: 100
end_ms: 900
batches:
  - {sequence: 1, observed_at_ms: 100, status: measured, observations: [{id: A, type: pedestrian, cell_id: 192, x: 1, y: 1}, {id: X, type: pedestrian, cell_id: 193, x: 11, y: 1}]}
  - {sequence: 2, observed_at_ms: 200, status: measured, observations: [{id: A, type: pedestrian, cell_id: 192, x: 2, y: 1}, {id: X, type: pedestrian, cell_id: 193, x: 12, y: 1}]}
  - {sequence: 3, observed_at_ms: 300, status: measured, observations: [{id: A, type: pedestrian, cell_id: 192, x: 3, y: 1}, {id: X, type: pedestrian, cell_id: 193, x: 13, y: 1}]}
  - {sequence: 4, observed_at_ms: 400, status: measured, observations: [{id: B, type: pedestrian, cell_id: 192, x: 4, y: 1}, {id: Y, type: pedestrian, cell_id: 193, x: 14, y: 1}]}
  - {sequence: 5, observed_at_ms: 500, status: measured, observations: []}
  - {sequence: 6, observed_at_ms: 600, status: measured, observations: []}
  - {sequence: 7, observed_at_ms: 700, status: measured, observations: []}
  - {sequence: 8, observed_at_ms: 800, status: measured, observations: []}
)");
}
YAML::Node configuration() {
    return YAML::Load(R"(
application_id: traffic
window_ms: 400
history: {retention_ms: 2000, max_bins: 32, max_observations: 1000, max_identity_bytes: 64000, max_buckets: 16}
spatial_selection: {min_depth: 2, max_evaluations: 64}
temporal_adaptation: {extension_step_ms: 100, max_window_ms: 800, max_evaluations: 32}
policy_tree:
  id: traffic
  version: '1'
  root: {distinct_contributors: {min: 2}, cell_side_m: {max: 40}}
  regions: []
  execution: {strategy: spatial_first, publication_model: private_final_snapshot}
)");
}
YAML::Node replay(std::string mode, YAML::Node input = source(), YAML::Node config = configuration(),
    std::optional<int> depth = {}) {
    umpReplay::Options options; options.mode = std::move(mode); options.fixedDepth = depth;
    const auto parsed = umpReplay::parseInput(input);
    const auto settings = umpReplay::parseSettings(config, parsed, options);
    return YAML::Load(umpReplay::run(parsed, settings, options));
}
void policiesAndStrategies() {
    auto fixed = replay("fixed");
    require(fixed["windows"][0]["selected_cells"].as<int>() == 0
        && fixed["windows"][0]["suppressed_cells"].as<int>() == 2,
        "Fine fixed baseline bypassed policy or silently adapted");
    auto coarse = replay("fixed", source(), configuration(), 2);
    require(coarse["windows"][0]["selected_cells"].as<int>() == 1
        && coarse["releases"][0]["cells"][0]["depth"].as<int>() == 2,
        "Fixed depth override did not use exact parent support");
    auto spatial = replay("spatial");
    require(spatial["releases"][0]["end_ms"].as<int>() == 400
        && spatial["releases"][0]["cells"][0]["depth"].as<int>() == 2,
        "Spatial baseline failed to use the real spatial selector");
    auto temporalFirst = replay("temporal_first"), spatialFirst = replay("spatial_first");
    require(temporalFirst["releases"][0]["end_ms"].as<int>() == 400
        && spatialFirst["releases"][0]["end_ms"].as<int>() == 500
        && spatialFirst["releases"][0]["cells"].size() == 2
        && spatialFirst["releases"][0]["cells"][0]["depth"].as<int>() == 3,
        "CLI modes did not preserve the project's Temporal/Spatial First convention");
    for (auto result : {fixed, coarse, spatial, temporalFirst, spatialFirst}) {
        require(result["input_observation_contributions"].as<int>() == 8
            && result["accounted_observation_contributions"].as<int>() == 8,
            "Replay lost or duplicated input support");
        for (const auto& release : result["releases"]) {
            require(release["model"].as<std::string>() == "private_final_snapshot"
                && release["policy_id"].as<std::string>() == "traffic", "Public policy/model provenance missing");
            for (const auto& cell : release["cells"])
                require(!cell["id"] && !cell["type"] && !cell["type_observation_contributions"]
                    && cell["effective_policy_id"], "Private identity/type or missing policy in public projection");
        }
    }
    auto again = replay("spatial_first");
    spatialFirst.remove("runtime"); again.remove("runtime");
    require(YAML::Dump(spatialFirst) == YAML::Dump(again), "Same-input replay was not deterministic");

    auto regional = configuration();
    regional["policy_regions"] = YAML::Load("[{id: strict, x: 0, y: 0, width: 10, height: 10, type_requirements: {distinct_contributors: {min: 5}}, requirements: {distinct_contributors: {min: 2}}}]");
    regional["policy_tree"]["regions"].push_back("strict");
    const auto constrained = replay("fixed", source(), regional, 2);
    require(constrained["windows"][0]["selected_cells"].as<int>() == 0,
        "Cross-region fixed footprint escaped stricter inherited policy");

    umpReplay::Options options; options.mode = "fixed"; options.fixedWindowMs = 600;
    const auto parsed = umpReplay::parseInput(source());
    const auto settings = umpReplay::parseSettings(configuration(), parsed, options);
    const auto wider = YAML::Load(umpReplay::run(parsed, settings, options));
    require(wider["windows"][0]["end_ms"].as<int>() == 600
        && wider["windows"][0]["selected_cells"].as<int>() == 2,
        "Fixed-window override was not evaluated with exact temporal union");
}
void missingEmptyAndTruncation() {
    auto input = source();
    input["batches"][1]["status"] = "unavailable";
    input["batches"][1]["observations"] = YAML::Node(YAML::NodeType::Sequence);
    input["batches"].remove(2);
    input["end_ms"] = 850;
    const auto result = replay("fixed", input);
    require(result["windows"][0]["coverage"].as<std::string>() == "incomplete"
        && result["windows"][0]["unavailable_samples"].as<int>() == 1
        && result["windows"][0]["missing_samples"].as<int>() == 1
        && result["windows"][0]["selected_cells"].as<int>() == 0,
        "Missing/unavailable input became complete zero data");
    const auto last = result["windows"][result["windows"].size() - 1];
    require(last["truncated"].as<bool>() && last["end_ms"].as<int>() == 850
        && last["measured_samples"].as<int>() == 1 && last["cells"].size() == 0,
        "Final measured-empty partial window was lost or turned into a public zero certificate");
}
void strictValidationAndIsolation() {
    const auto bad = [&](auto mutation) {
        auto input = source(); mutation(input);
        rejects([&] { replay("fixed", input); }, "Malformed replay input was accepted");
    };
    bad([](auto n) { n["batches"][0]["observations"][0]["x"] = 10; });
    bad([](auto n) { n["batches"][0]["observations"][0].remove("y"); });
    bad([](auto n) { n["batches"][0]["observations"][1]["id"] = "A"; });
    bad([](auto n) { n["batches"][0]["observed_at_ms"] = 0; });
    bad([](auto n) { n["batches"][1]["sequence"] = 1; });
    bad([](auto n) { n["batches"][0]["status"] = "empty"; });
    bad([](auto n) { n["batches"][0]["status"] = "unavailable"; });
    bad([](auto n) { n["batches"][0]["observed_at_ms"] = 150; });
    bad([](auto n) { n["coverage"]["height"] = 79; });
    bad([](auto n) { n["batches"][0]["unexpected"] = true; });
    bad([](auto n) { n["schema"] = "unknown"; });
    auto config = configuration(); config["history"]["max_observations"] = 1;
    rejects([&] { replay("fixed", source(), config); }, "Replay ignored configured private history budget");
    rejects([&] { replay("spatial", source(), configuration(), 2); }, "Fixed override leaked into adaptive mode");
    config = configuration(); config["policy_tree"]["regions"].push_back("unknown");
    rejects([&] { replay("fixed", source(), config); }, "Unknown region was silently ignored");
    const auto path = std::filesystem::temp_directory_path() / ("ump-replay-test-" + std::to_string(::getpid()) + ".json");
    if (std::filesystem::exists(path)) throw std::runtime_error("Test refuses existing temporary path");
    umpReplay::writeNew(path, "first");
    try {
        rejects([&] { umpReplay::writeNew(path, "second"); }, "Replay overwrote an existing output");
        std::ifstream file(path); std::string actual; file >> actual;
        require(actual == "first", "Existing output changed");
    } catch (...) { std::filesystem::remove(path); throw; }
    std::filesystem::remove(path);
}

// Pacing changes arrival scheduling only. Compare the complete parsed result,
// including all private decisions and public fields, with only runtime removed.
void pacedCoreEquivalence() {
    auto semantic = configuration();
    semantic["semantic_taxonomy"] = YAML::Load(R"(
id: replay-pacing-types
version: '1'
nodes:
  - {id: road_user, loss: 1}
  - {id: pedestrian, parent: road_user, loss: 0, input_types: [pedestrian]}
)");
    semantic["policy_tree"]["root"]["min_category_distinct_contributors"]["min"] = 2;
    semantic["policy_tree"]["root"]["semantic_max_loss"]["max"] = 1;
    for (const std::string mode : {"fixed", "spatial", "temporal_first", "spatial_first", "semantic_first"}) {
        for (bool local : {false, true}) {
            if (local && (mode == "fixed" || mode == "spatial")) continue;
            auto config = YAML::Clone(mode == "semantic_first" ? semantic : configuration());
            config["policy_tree"]["execution"]["strategy"] = mode == "fixed" || mode == "spatial"
                ? "spatial_first" : mode;
            if (local) {
                config["temporal_adaptation"]["coordination"] = "cell_local";
                config["temporal_adaptation"]["max_active_cells"] = 64;
                config["spatial_selection"]["max_evaluations"] = 256;
            }
            auto input = source();
            // Unavailable and missing cadence events, measured empties and an
            // off-cadence EOF all have to retain their original meaning.
            input["batches"][1]["status"] = "unavailable";
            input["batches"][1]["observations"] = YAML::Node(YAML::NodeType::Sequence);
            input["batches"].remove(2);
            input["end_ms"] = 850;
            const auto parsed = umpReplay::parseInput(input);
            umpReplay::Options options; options.mode = mode;
            const auto settings = umpReplay::parseSettings(config, parsed, options);
            auto expected = YAML::Load(umpReplay::run(parsed, settings, options));
            options.paceRate = 100.; options.queueCapacity = 16;
            auto actual = YAML::Load(umpReplay::run(parsed, settings, options));
            const auto timing = actual["runtime"]["pacing"];
            require(timing && timing["events"].size() == 9
                && timing["events"][8]["kind"].as<std::string>() == "finish"
                && timing["events"][8]["logical_time_ms"].as<int>() == 850,
                "Paced replay omitted missing/empty cadence steps or off-cadence EOF");
            require(timing["peak_queue_depth"].as<int>() <= 16,
                "Paced replay exceeded its pending-input budget");
            expected.remove("runtime"); actual.remove("runtime");
            require(YAML::Dump(actual) == YAML::Dump(expected),
                "Pacing changed a full core output beyond runtime");
        }
    }
}
void pacingCliValidation() {
    const std::vector<std::string> base{"AggregationReplay", "--input", "/unused/input.json",
        "--config", "/unused/policy.json", "--mode", "fixed", "--output",
        (std::filesystem::temp_directory_path() / ("ump-paced-unused-" + std::to_string(::getpid()) + ".json")).string()};
    const auto parse = [&](std::initializer_list<const char*> extra) {
        auto args = base;
        for (const char* value : extra) args.emplace_back(value);
        std::vector<char*> argv;
        for (auto& value : args) argv.push_back(value.data());
        return umpReplay::arguments(static_cast<int>(argv.size()), argv.data());
    };
    const auto defaults = parse({});
    require(!defaults.paceRate, "Offline CLI implicitly enabled pacing");
    const auto paced = parse({"--pace-rate", "1", "--queue-capacity", "8"});
    require(paced.paceRate == std::optional<double>{1} && paced.queueCapacity == 8,
        "Valid paced CLI options not retained");
    for (const char* value : {"0", "-1", "nan", "inf", "1001", "1junk"})
        rejects([&] { parse({"--pace-rate", value}); }, "Malformed pace rate accepted");
    for (const char* value : {"0", "-1", "100001", "2.5", "1junk"})
        rejects([&] { parse({"--pace-rate", "1", "--queue-capacity", value}); }, "Malformed queue capacity accepted");
    rejects([&] { parse({"--queue-capacity", "8"}); }, "Queue option silently ignored without pacing");
    rejects([&] { parse({"--pace-rate", "1", "--pace-rate", "2"}); }, "Duplicate pace rate accepted");
    rejects([&] { parse({"--pace-rate"}); }, "Missing pace rate accepted");
    require(!std::filesystem::exists(base.back()), "CLI parsing wrote a result file");
}

}
int main() {
    try {
        policiesAndStrategies(); missingEmptyAndTruncation(); strictValidationAndIsolation();
        pacedCoreEquivalence(); pacingCliValidation();
        std::cout << "PASS: frozen replay, actual core modes, policy-controlled fixed baselines, conservation, determinism, gaps, paced equivalence, CLI validation and private/public separation.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
