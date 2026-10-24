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
// A second integration path mirrors the native sensor's actual call order,
// including the pre-ingest progress call. It uses publication callbacks directly
// rather than replay's event-consumption lambda or its scheduling helper.
void nativeProgressClock() {
    auto config = configuration();
    config["temporal_adaptation"]["coordination"] = "cell_local";
    config["temporal_adaptation"]["max_active_cells"] = 64;
    config["spatial_selection"]["max_evaluations"] = 256;
    const auto input = umpReplay::parseInput(source());
    umpReplay::Options options; options.mode = "spatial_first"; options.progressStepMs = 50;
    const auto settings = umpReplay::parseSettings(config, input, options);
    const auto recorded = YAML::Load(umpReplay::run(input, settings, options));
    require(recorded["parameters"]["progress_step_ms"].as<int>() == 50
        && recorded["parameters"]["progress_origin_ms"].as<int>() == 0,
        "Explicit native progress clock was not recorded");

    const auto& aggregation = settings.aggregation;
    ump::PublicationLimits limits; limits.maxCoordinationNodes = settings.temporal->maxActiveCells * 2;
    ump::PublicationCoordinator publication(aggregation, settings.evaluator, limits,
        settings.temporal->maxWindowMs, true);
    std::vector<std::string> windows, releases;
    const auto terminal = [&](const ump::SpatialSelection& selection) {
        publication.seal(selection, selection.candidate.closedAtMs);
        require(publication.deliver(selection.candidate.closedAtMs, [&](const auto& release) {
            releases.push_back(umpReplay::serializeRelease(release));
            return ump::SinkResult::Acknowledged;
        }), "Direct native-like sink did not acknowledge");
        windows.push_back(umpReplay::serializeWindow(selection));
    };
    AggregationManager manager(aggregation, [](const auto&) {});
    ump::CellLocalAggregation local(aggregation, *settings.temporal, settings.spatial,
        settings.evaluator, terminal, settings.temporal->maxActiveCells);
    std::vector<ump::AggregationTime> callbacks;
    manager.setProgressSink([&](auto now, bool finishing) {
        callbacks.push_back(now);
        if (finishing) local.finish(now, *manager.history());
        else local.advance(now, *manager.history());
    });
    manager.advance(0);
    require(manager.history()->debugState().observations == 0 && manager.debugState().measuredSamples == 0,
        "Origin progress fabricated a measurement");
    std::size_t next = 0;
    for (ump::AggregationTime now = 50; now < input.endMs; now += 50) {
        manager.advance(now);
        if (next < input.batches.size() && input.batches[next].observedAtMs == now)
            manager.ingest(input.batches[next++]);
    }
    manager.finish(input.endMs);
    require(next == input.batches.size() && callbacks.front() == 0
        && std::count(callbacks.begin(), callbacks.end(), 50) == 1
        && std::count(callbacks.begin(), callbacks.end(), 100) == 2,
        "Native-like progress did not distinguish sensor sampling from simulation ticks");
    require(YAML::Dump(recorded["windows"]) == YAML::Dump(YAML::Load(umpReplay::array(windows)))
        && YAML::Dump(recorded["releases"]) == YAML::Dump(YAML::Load(umpReplay::array(releases))),
        "Explicit progress replay differs from direct native-like CellLocal callbacks");
    require(recorded["input_observation_contributions"].as<int>() == 8
        && recorded["accounted_observation_contributions"].as<int>() == 8,
        "Extra progress ticks changed observed support");
    auto legacyOptions = options; legacyOptions.progressStepMs.reset();
    const auto legacy = YAML::Load(umpReplay::run(input, settings, legacyOptions));
    require(!legacy["parameters"]["progress_step_ms"] && !legacy["parameters"]["progress_origin_ms"],
        "Default replay output gained explicit-clock metadata");
}

void progressClockCoverageAndValidation() {
    auto inputNode = source();
    inputNode["batches"][1]["status"] = "unavailable";
    inputNode["batches"][1]["observations"] = YAML::Node(YAML::NodeType::Sequence);
    inputNode["batches"].remove(2);
    const auto input = umpReplay::parseInput(inputNode);
    umpReplay::Options options; options.mode = "fixed"; options.progressStepMs = 50;
    const auto settings = umpReplay::parseSettings(configuration(), input, options);
    const auto actual = YAML::Load(umpReplay::run(input, settings, options));
    const auto first = actual["windows"][0];
    require(first["expected_samples"].as<int>() == 3 && first["measured_samples"].as<int>() == 1
        && first["unavailable_samples"].as<int>() == 1 && first["missing_samples"].as<int>() == 1
        && first["coverage"].as<std::string>() == "incomplete",
        "Nonmeasurement progress ticks became sampled or measured-empty data");
    require(actual["input_observation_contributions"].as<int>() == 4
        && actual["accounted_observation_contributions"].as<int>() == 4,
        "Explicit progress altered source contribution conservation");
    for (const ump::AggregationTime invalid : {0, -50, 75, 101, 200}) {
        options.progressStepMs = invalid;
        rejects([&] { umpReplay::parseSettings(configuration(), input, options); },
            "Invalid progress step was accepted");
    }
    options.progressStepMs = 100;
    auto unaligned = input; unaligned.endMs = 850;
    rejects([&] { umpReplay::parseSettings(configuration(), unaligned, options); },
        "Explicit progress accepted an unaligned horizon");
    options.progressStepMs = 50;
    require(umpReplay::progressStepFor(unaligned, options) == 50,
        "A horizon on a finer progress tick was rejected");
    auto excessive = input; excessive.endMs = umpReplay::maxReplayTicks * 50;
    rejects([&] { umpReplay::progressStepFor(excessive, options); },
        "Origin and finish were excluded from the explicit event budget");
    excessive.endMs = 100000 * 50; options.paceRate = 100.;
    rejects([&] { umpReplay::progressStepFor(excessive, options); },
        "Explicit paced progress exceeded its event budget");
}

void pacedProgressClockEquivalence() {
    auto config = configuration();
    config["temporal_adaptation"]["coordination"] = "cell_local";
    config["temporal_adaptation"]["max_active_cells"] = 64;
    config["spatial_selection"]["max_evaluations"] = 256;
    auto inputNode = source(); inputNode["end_ms"] = 850;
    const auto input = umpReplay::parseInput(inputNode);
    umpReplay::Options options; options.mode = "spatial_first"; options.progressStepMs = 50;
    const auto settings = umpReplay::parseSettings(config, input, options);
    auto offline = YAML::Load(umpReplay::run(input, settings, options));
    options.paceRate = 100.; options.queueCapacity = 64;
    auto paced = YAML::Load(umpReplay::run(input, settings, options));
    const auto events = paced["runtime"]["pacing"]["events"];
    require(events.size() == 17 && events[0]["logical_time_ms"].as<int>() == 50
        && events[0]["kind"].as<std::string>() == "cadence"
        && events[16]["logical_time_ms"].as<int>() == 850
        && events[16]["kind"].as<std::string>() == "finish",
        "Paced explicit clock did not schedule every positive progress tick plus finish");
    for (std::size_t i = 0; i < events.size(); ++i)
        require(events[i]["logical_time_ms"].as<int>() == static_cast<int>((i+1)*50),
            "Paced progress skipped or fabricated a logical tick");
    offline.remove("runtime"); paced.remove("runtime");
    require(YAML::Dump(offline) == YAML::Dump(paced),
        "Pacing changed explicit-clock core output beyond runtime");
}

void sha256AndCanonicalEncoding() {
    umpReplay::ReplaySha256 empty;
    require(empty.hex() == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "SHA-256 empty vector failed");
    umpReplay::ReplaySha256 abc; abc.update(std::string("abc"));
    require(abc.hex() == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "SHA-256 abc vector failed");
    umpReplay::ReplaySha256 longValue;
    longValue.update(std::string("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"));
    require(longValue.hex() == "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1", "SHA-256 multiblock vector failed");
    umpReplay::ReplaySha256 million;
    for (int i = 0; i < 1000; ++i) million.update(std::string(1000,'a'));
    require(million.hex() == "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0", "SHA-256 streaming million-a vector failed");
    require(abc.hex() == abc.hex(), "Finalizing audit hash mutated its state");
    umpReplay::ReplayCanonicalHash a("test"), b("test"), c("test"), d("test");
    a.text("ab"); a.text("c"); b.text("a"); b.text("bc");
    require(a.hex() != b.hex(), "Canonical string boundaries were ambiguous");
    c.unsignedValue(1); d.signedValue(1);
    require(c.hex() != d.hex(), "Canonical scalar types were ambiguous");
}

ump::SpatialSelection digestFixture() {
    using namespace ump;
    AggregateCounts counts{3,2,{{"pedestrian",3}},1.5,SemanticEvidence{"types","1",{{"pedestrian",{3,2}}}}};
    AggregationCandidate candidate{"run","sensor","app",{0,0,80,80,3},0,400,450,false,3,3,0,0,
        WindowCoverage::Complete,counts,{{{192,3,0,0,10,10},counts}}};
    SemanticSuppressionAudit suppression;
    suppression.inputObservations=3;suppression.inputDistinct=2;suppression.retainedObservations=2;
    suppression.retainedDistinct=1;suppression.suppressedObservations=1;suppression.suppressedDistinct=1;
    suppression.suppressedTypeObservations={{"cyclist",1}};suppression.suppressedLeaves={"cyclist"};
    suppression.fraction=1./3;suppression.fullInputSemanticLoss=.5;suppression.unsuppressedSemanticLoss=1;
    suppression.evaluatedCandidates=2;suppression.evaluationNanoseconds=123;
    CellMetricAssessment cell{192,AssessmentStatus::Pass,
        {{MetricId::DistinctContributors,2,""}},
        {{{MetricId::DistinctContributors,2,{}},2,AssessmentStatus::Pass,"met"}},
        "effective",{"root"},true,SemanticRepresentation{"types","1",{{"pedestrian",2,1}},1,.5,.5},counts,suppression};
    WindowMetricAssessment assessment{450,"policy","1",AssessmentStatus::Pass,"complete",AssessmentStatus::Pass,{cell},"tree"};
    SpatialSelection result{candidate,assessment,candidate,assessment,
        {{192,true,"approved",{193},"merged"}},{{candidate.cells[0],cell}},2};
    result.selectedCells=1;result.suppressedCells=0;result.coarsenedCells=1;result.refinedCells=0;
    result.temporalDecisions={{TemporalAction::Finalize,0,400,450,AssessmentStatus::Pass}};
    result.coordinationCell=CellGeometry{48,2,0,0,20,20};
    result.semanticPriority=SemanticPrioritySelection{.5,.5,2,false,"spatial_first","policy_satisfied",true};
    return result;
}
void completeDecisionDigestCoverage() {
    using ump::MetricId;
    auto base=digestFixture();
    const auto digest=[](const auto& value){umpReplay::ReplayDecisionDigest h;h.selection(value);return h.retirementSha256();};
    const auto original=digest(base);
    const std::vector<std::function<void(ump::SpatialSelection&)>> mutations{
        [](auto& s){s.candidate.runId += "x";},[](auto& s){s.candidate.sensorId += "x";},[](auto& s){s.candidate.applicationId += "x";},
        [](auto& s){s.candidate.grid.x=1;},[](auto& s){s.candidate.grid.y=1;},[](auto& s){s.candidate.grid.width=81;},
        [](auto& s){s.candidate.grid.height=81;},[](auto& s){s.candidate.grid.leafDepth=4;},
        [](auto& s){s.candidate.startMs=1;},[](auto& s){s.candidate.endMs=401;},[](auto& s){s.candidate.closedAtMs=451;},
        [](auto& s){s.candidate.truncated=true;},[](auto& s){s.candidate.expectedSamples=4;},[](auto& s){s.candidate.measuredSamples=4;},
        [](auto& s){s.candidate.unavailableSamples=1;},[](auto& s){s.candidate.missingSamples=1;},
        [](auto& s){s.candidate.coverage=ump::WindowCoverage::Incomplete;},
        [](auto& s){s.candidate.counts.observationContributions=4;},[](auto& s){s.candidate.counts.distinctContributors=3;},
        [](auto& s){s.candidate.counts.typeObservationContributions["pedestrian"]=4;},
        [](auto& s){s.candidate.counts.meanSampleOccupancy.reset();},
        [](auto& s){s.candidate.counts.semanticEvidence->taxonomyId += "x";},
        [](auto& s){s.candidate.counts.semanticEvidence->taxonomyVersion += "x";},
        [](auto& s){s.candidate.counts.semanticEvidence->nodes["pedestrian"].distinctContributors=3;},
        [](auto& s){s.candidate.counts.semanticEvidence->nodes["pedestrian"].observationContributions=4;},
        [](auto& s){s.candidate.cells[0].cell.id=193;},[](auto& s){s.candidate.cells[0].cell.depth=2;},
        [](auto& s){s.candidate.cells[0].cell.x=1;},[](auto& s){s.candidate.cells[0].cell.y=1;},
        [](auto& s){s.candidate.cells[0].cell.width=std::nextafter(10.,11.);},[](auto& s){s.candidate.cells[0].cell.height=11;},
        [](auto& s){s.candidate.cells[0].counts.distinctContributors=3;},[](auto& s){s.candidate.cells.clear();},
        [](auto& s){s.finest.startMs=1;},[](auto& s){s.finestAssessment.coverageReason += "x";},
        [](auto& s){s.assessment.evaluatedAtMs=451;},[](auto& s){s.assessment.policyId.reset();},
        [](auto& s){s.assessment.policyVersion="2";},[](auto& s){s.assessment.coverageStatus=ump::AssessmentStatus::Fail;},
        [](auto& s){s.assessment.coverageReason += "x";},[](auto& s){s.assessment.status=ump::AssessmentStatus::Fail;},
        [](auto& s){s.assessment.policyMode += "x";},[](auto& s){s.assessment.cells[0].cellId=193;},
        [](auto& s){s.assessment.cells[0].status=ump::AssessmentStatus::Fail;},
        [](auto& s){s.assessment.cells[0].metrics[0].id=MetricId::CellSideM;},
        [](auto& s){s.assessment.cells[0].metrics[0].value.reset();},
        [](auto& s){s.assessment.cells[0].metrics[0].unavailableReason="missing";},
        [](auto& s){s.assessment.cells[0].checks[0].requirement.id=MetricId::CellSideM;},
        [](auto& s){s.assessment.cells[0].checks[0].requirement.min=3;},
        [](auto& s){s.assessment.cells[0].checks[0].requirement.max=3;},
        [](auto& s){s.assessment.cells[0].checks[0].observed=3;},
        [](auto& s){s.assessment.cells[0].checks[0].status=ump::AssessmentStatus::Fail;},
        [](auto& s){s.assessment.cells[0].checks[0].reason += "x";},
        [](auto& s){s.assessment.cells[0].effectivePolicyId="other";},
        [](auto& s){s.assessment.cells[0].policySources.push_back("local");},
        [](auto& s){s.assessment.cells[0].policyFeasible=false;},
        [](auto& s){s.assessment.cells[0].semantic->taxonomyId += "x";},
        [](auto& s){s.assessment.cells[0].semantic->taxonomyVersion += "x";},
        [](auto& s){s.assessment.cells[0].semantic->bins[0].categoryId += "x";},
        [](auto& s){s.assessment.cells[0].semantic->bins[0].observationContributions=4;},
        [](auto& s){s.assessment.cells[0].semantic->bins[0].distinctContributors=3;},
        [](auto& s){s.assessment.cells[0].semantic->minimumDistinctContributors=2;},
        [](auto& s){s.assessment.cells[0].semantic->maxLoss=1;},[](auto& s){s.assessment.cells[0].semantic->meanLoss=1;},
        [](auto& s){s.assessment.cells[0].retainedCounts->distinctContributors=3;},
        [](auto& s){s.assessment.cells[0].retainedCounts.reset();},
        [](auto& s){s.assessment.cells[0].semanticSuppression->inputObservations=4;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->inputDistinct=3;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->retainedObservations=3;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->retainedDistinct=2;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->suppressedObservations=2;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->suppressedDistinct=2;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->suppressedTypeObservations["cyclist"]=2;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->suppressedLeaves.push_back("other");},
        [](auto& s){s.assessment.cells[0].semanticSuppression->fraction=.4;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->fullInputSemanticLoss=.6;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->unsuppressedSemanticLoss=.9;},
        [](auto& s){s.assessment.cells[0].semanticSuppression->evaluatedCandidates=3;},
        [](auto& s){s.assessment.cells[0].semanticSuppression.reset();},
        [](auto& s){s.decisions[0].cellId=193;},[](auto& s){s.decisions[0].selected=false;},
        [](auto& s){s.decisions[0].reason += "x";},[](auto& s){s.decisions[0].triggerCells.push_back(194);},
        [](auto& s){s.decisions[0].transition += "x";},[](auto& s){s.attempts[0].cell.counts.distinctContributors=3;},
        [](auto& s){s.attempts[0].assessment.policyFeasible=false;},[](auto& s){s.minDepth=1;},
        [](auto& s){s.selectedCells=2;},[](auto& s){s.suppressedCells=1;},[](auto& s){s.coarsenedCells=2;},[](auto& s){s.refinedCells=1;},
        [](auto& s){s.strategy += "x";},[](auto& s){s.temporalExtensions=1;},[](auto& s){s.completionReason += "x";},
        [](auto& s){s.temporalDecisions[0].action=ump::TemporalAction::ExtendWindow;},
        [](auto& s){s.temporalDecisions[0].startMs=1;},[](auto& s){s.temporalDecisions[0].endMs=401;},
        [](auto& s){s.temporalDecisions[0].evaluatedAtMs=451;},[](auto& s){s.temporalDecisions[0].status=ump::AssessmentStatus::Fail;},
        [](auto& s){s.publicationState += "x";},[](auto& s){s.releaseId += "x";},
        [](auto& s){s.coordinationCell.reset();},[](auto& s){s.semanticPriority->lossCeiling=.6;},
        [](auto& s){s.semanticPriority->actualMaxLoss.reset();},[](auto& s){s.semanticPriority->attemptedCeilings=3;},
        [](auto& s){s.semanticPriority->terminalFallback=true;},[](auto& s){s.semanticPriority->secondaryStrategy += "x";},
        [](auto& s){s.semanticPriority->releaseTrigger += "x";},[](auto& s){s.semanticPriority->policySatisfiedRelease=false;}
    };
    for (std::size_t i=0;i<mutations.size();++i) {
        auto changed=base;mutations[i](changed);
        if(digest(changed)==original) throw std::runtime_error("Logical audit omitted mutation " + std::to_string(i));
    }
    auto runtimeOnly=base;runtimeOnly.assessment.cells[0].semanticSuppression->evaluationNanoseconds=999;
    require(digest(runtimeOnly)==original,"Runtime suppression duration contaminated decision equality");
    umpReplay::ReplayDecisionDigest ordered, reversed;
    ordered.selection(base);ordered.selection(runtimeOnly);
    reversed.selection(base);auto changed=base;changed.suppressedCells=1;reversed.selection(changed);
    require(ordered.retirementSha256()!=reversed.retirementSha256(),"Later retirement was omitted from complete audit");
    ump::ReleaseSnapshot release{"id","run","sensor","app","private_final_snapshot","policy","1",0,400,450,
        {{base.candidate.cells[0],"effective",base.assessment.cells[0].semantic}},base.coordinationCell};
    const auto releaseDigest=[](const auto& v){umpReplay::ReplayDecisionDigest h;h.release(v);return h.releaseSha256();};
    const auto releaseOriginal=releaseDigest(release);
    const std::vector<std::function<void(ump::ReleaseSnapshot&)>> releaseMutations{
        [](auto& r){r.releaseId+="x";},[](auto& r){r.runId+="x";},[](auto& r){r.sensorId+="x";},[](auto& r){r.applicationId+="x";},
        [](auto& r){r.model+="x";},[](auto& r){r.policyId+="x";},[](auto& r){r.policyVersion+="x";},
        [](auto& r){r.startMs=1;},[](auto& r){r.endMs=401;},[](auto& r){r.sealedAtMs=451;},
        [](auto& r){r.cells[0].aggregate.counts.observationContributions=4;},[](auto& r){r.cells[0].effectivePolicyId+="x";},
        [](auto& r){r.cells[0].semantic.reset();},[](auto& r){r.coordinationCell.reset();},[](auto& r){r.cells.clear();}
    };
    for(const auto& mutate:releaseMutations){auto changed=release;mutate(changed);require(releaseDigest(changed)!=releaseOriginal,"Public release field missing from audit");}
}

void fullMinimalLogicalEquivalence() {
    auto semantic=configuration();
    semantic["semantic_taxonomy"]=YAML::Load(R"(
id: audit-types
version: '1'
nodes:
  - {id: road_user, loss: 1}
  - {id: pedestrian, parent: road_user, loss: 0, input_types: [pedestrian]}
)");
    semantic["policy_tree"]["root"]["min_category_distinct_contributors"]["min"]=2;
    semantic["policy_tree"]["root"]["semantic_max_loss"]["max"]=1;
    const auto parsed=umpReplay::parseInput(source());
    for(const std::string mode:{"fixed","spatial","temporal_first","spatial_first","semantic_first"}) {
        for(bool local:{false,true}) {
            if(local&&(mode=="fixed"||mode=="spatial"))continue;
            auto config=YAML::Clone(mode=="semantic_first"?semantic:configuration());
            config["policy_tree"]["execution"]["strategy"]=mode=="fixed"||mode=="spatial"?"spatial_first":mode;
            if(local){config["temporal_adaptation"]["coordination"]="cell_local";config["temporal_adaptation"]["max_active_cells"]=64;config["spatial_selection"]["max_evaluations"]=256;}
            umpReplay::Options options;options.mode=mode;options.progressStepMs=50;
            const auto settings=umpReplay::parseSettings(config,parsed,options);
            auto legacy=YAML::Load(umpReplay::run(parsed,settings,options));
            require(!legacy["runtime"]["decision_audit"],"Historical full default gained opt-in decision audit");
            options.decisionDigest=true;
            auto full=YAML::Load(umpReplay::run(parsed,settings,options));
            require(YAML::Dump(full["runtime"]["decision_audit"])!="","Full decision audit absent");
            options.diagnostics="minimal";
            auto minimal=YAML::Load(umpReplay::run(parsed,settings,options));
            require(minimal["windows"].size()==0&&full["windows"].size()>0,"Minimal path retained heavy private windows or removed full diagnostics");
            require(YAML::Dump(full["runtime"]["decision_audit"])==YAML::Dump(minimal["runtime"]["decision_audit"]),"Full/minimal complete logical digests differ");
            require(full["runtime"]["decision_audit"]["retirement_count"].as<std::size_t>()==full["windows"].size(),"Private empty/suppressed retirements omitted from audit");
            require(minimal["runtime"]["phases"]["private_window_json"]["calls"].as<int>()==0,"Minimal mode still executes private JSON serializer");
            full.remove("runtime");legacy.remove("runtime");
            require(YAML::Dump(full)==YAML::Dump(legacy),"Opt-in audit changed historical full payload");
            full.remove("windows");minimal.remove("windows");minimal.remove("runtime");
            require(YAML::Dump(full)==YAML::Dump(minimal),"Minimal path changed public output or input/accounted conservation");
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
    require(!defaults.paceRate && !defaults.progressStepMs && defaults.diagnostics=="full" && !defaults.decisionDigest && !defaults.failureOutput,
        "Historical CLI implicitly enabled pacing, minimal diagnostics or auditing");
    require(parse({"--diagnostics","minimal"}).diagnostics=="minimal" && parse({"--decision-digest","sha256"}).decisionDigest,
        "Opt-in minimal/digest CLI not retained");
    rejects([&]{parse({"--diagnostics","off"});},"Unknown diagnostics accepted");
    rejects([&]{parse({"--decision-digest","fnv"});},"Unknown digest accepted");
    rejects([&]{parse({"--failure-output","/unused/failure.json"});},"Failure output accepted without pacing");
    const auto sidecar=(std::filesystem::temp_directory_path()/("ump-failure-unused-"+std::to_string(::getpid())+".json")).string();
    require(parse({"--pace-rate","1","--failure-output",sidecar.c_str()}).failureOutput.has_value(),"Failure sidecar CLI lost");
    rejects([&]{parse({"--pace-rate","1","--failure-output",base.back().c_str()});},"Failure/result path collision accepted");
    require(parse({"--progress-step-ms", "50"}).progressStepMs == std::optional<ump::AggregationTime>{50},
        "CLI did not retain the explicit progress step");
    for (const char* value : {"0", "-1", "nan", "1.5", "50junk"})
        rejects([&] { parse({"--progress-step-ms", value}); }, "Malformed progress step accepted");
    rejects([&] { parse({"--progress-step-ms", "50", "--progress-step-ms", "100"}); },
        "Duplicate progress step accepted");
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
        pacedCoreEquivalence(); pacingCliValidation(); nativeProgressClock();
        progressClockCoverageAndValidation(); pacedProgressClockEquivalence();
        sha256AndCanonicalEncoding(); completeDecisionDigestCoverage(); fullMinimalLogicalEquivalence();
        std::cout << "PASS: frozen replay, actual core modes, policy-controlled fixed baselines, conservation, determinism, gaps, native progress-clock equivalence, paced equivalence, CLI validation and private/public separation.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << "FAIL: " << error.what() << '\n'; return 1; }
}
