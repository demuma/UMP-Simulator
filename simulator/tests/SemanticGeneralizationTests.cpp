#define UMP_REPLAY_LIBRARY
#include "../tools/AggregationReplay.cpp"

namespace {
using namespace ump;
void require(bool value, const char* why) { if (!value) throw std::runtime_error(why); }
template<class Work> void rejects(Work work, const char* why) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error(why);
}
YAML::Node configuration(bool local=false) {
    auto config=YAML::Load(R"(
application_id: semantic-action
window_ms: 400
history: {retention_ms: 2000, max_bins: 32, max_observations: 10000, max_identity_bytes: 1000000, max_buckets: 128}
spatial_selection: {min_depth: 2, max_evaluations: 128}
temporal_adaptation: {extension_step_ms: 100, max_window_ms: 800, max_evaluations: 16, coordination: common_window, max_active_cells: 128}
policy_tree:
  id: same-hard-policy
  version: '1'
  root:
    distinct_contributors: {min: 5}
    min_category_distinct_contributors: {min: 5}
    semantic_max_loss: {max: 1}
    semantic_suppression_fraction: {max: 0}
    cell_side_m: {max: 40}
    window_duration_ms: {min: 400, max: 800}
    age_at_evaluation_ms: {max: 800}
  regions: []
  execution: {strategy: semantic_first, semantic_secondary_strategy: temporal_first, release_trigger: policy_satisfied, publication_model: private_final_snapshot}
semantic_taxonomy:
  id: action-taxonomy
  version: '1'
  nodes:
    - {id: road_user, loss: 1}
    - {id: pedestrian, parent: road_user, loss: 0.5}
    - {id: adult, parent: pedestrian, loss: 0, input_types: [Adult]}
    - {id: child, parent: pedestrian, loss: 0, input_types: [Child]}
)");
    if (local) config["temporal_adaptation"]["coordination"]="cell_local";
    return config;
}
YAML::Node source(int adults=2,int children=3,bool validNeighbour=false) {
    auto data=YAML::Load(R"(
schema: ump.observation-replay.v1
run_id: excluded-semantic-action-unit
sensor_id: sensor
coverage: {x: 0, y: 0, width: 80, height: 80, leaf_depth: 3}
sampling_period_ms: 100
end_ms: 800
batches: []
)");
    for (int time=100;time<800;time+=100) {
        YAML::Node batch;batch["sequence"]=time/100;batch["observed_at_ms"]=time;
        batch["status"]="measured";batch["observations"]=YAML::Node(YAML::NodeType::Sequence);
        const auto add=[&](const std::string& prefix,const std::string& type,int n,int cell,double x) {
            for (int i=0;i<n;++i) {
                YAML::Node row;row["id"]=prefix+std::to_string(i);row["type"]=type;
                row["cell_id"]=cell;row["x"]=x;row["y"]=1.;batch["observations"].push_back(row);
            }
        };
        add("a","Adult",adults,192,1.);add("c","Child",children,192,1.);
        if (validNeighbour) {add("na","Adult",5,196,21.);add("nc","Child",5,196,21.);}
        data["batches"].push_back(batch);
    }
    return data;
}
YAML::Node replay(const std::string& mode,SemanticGeneralizationMode action,YAML::Node data=source(),
    YAML::Node config=configuration(),bool wait=false,bool spatialSecondary=false,bool minimal=false) {
    config["policy_tree"]["execution"]["release_trigger"]=wait?"priority_satisfied":"policy_satisfied";
    config["policy_tree"]["execution"]["semantic_secondary_strategy"]=spatialSecondary?"spatial_first":"temporal_first";
    umpReplay::Options options;options.mode=mode;options.semanticGeneralization=action;
    options.progressStepMs=50;options.decisionDigest=true;options.diagnostics=minimal?"minimal":"full";
    if (mode=="fixed") options.fixedDepth=2;
    const auto input=umpReplay::parseInput(data);const auto settings=umpReplay::parseSettings(config,input,options);
    return YAML::Load(umpReplay::run(input,settings,options));
}
void checkExactReleases(const YAML::Node& result) {
    require(result["parameters"]["semantic_generalization"].as<std::string>()=="exact_only","Action mode missing from private header");
    require(result["parameters"]["progress_step_ms"].as<int>()==50,"Action flag changed progress metadata");
    require(result["input_observation_contributions"].as<int>()==result["accounted_observation_contributions"].as<int>(),"Action restriction lost input retirement/accounting");
    for (const auto& release : result["releases"]) for (const auto& cell : release["cells"]) {
        std::uint64_t total=0;
        require(cell["semantic"]["semantic_max_loss"].as<double>()==0 && cell["semantic"]["semantic_mean_loss"].as<double>()==0,"Exact-only release generalized a category");
        for (const auto& bin : cell["semantic"]["categories"]) {
            const auto id=bin["category_id"].as<std::string>();
            require(id=="adult"||id=="child","Exact-only output contains a nonterminal");
            require(bin["distinct_contributors"].as<int>()>=5,"Exact-only release bypassed category support");
            total+=bin["observation_contributions"].as<std::uint64_t>();
        }
        require(total==cell["observation_contributions"].as<std::uint64_t>(),"Exact bins omitted or duplicated retained observations");
    }
    for (const auto& window : result["windows"]) if (window["semantic_priority"]) {
        const auto priority=window["semantic_priority"];
        require(priority["selected_max_loss_ceiling"].as<double>()==0
            && priority["attempted_ceilings"].as<int>()==1 && !priority["terminal_fallback"].as<bool>(),
            "Exact-only diagnostics claim forbidden generalized tiers");
    }
}
void truthfulTerminalRepresentation() {
    const auto taxonomy=readSemanticTaxonomy(configuration());SemanticAccumulator evidence(taxonomy);
    for (int repeat=0;repeat<4;++repeat) {
        for(int n=0;n<2;++n)evidence.add("a"+std::to_string(n),"Adult");
        for(int n=0;n<3;++n)evidence.add("c"+std::to_string(n),"Child");
    }
    const auto raw=evidence.evidence();
    const auto ordinary=taxonomy->select(raw,20,5,5);
    const auto exact=taxonomy->select(raw,20,5,5,SemanticGeneralizationMode::ExactOnly);
    require(ordinary.bins.size()==1&&ordinary.bins[0].categoryId=="pedestrian"&&ordinary.maxLoss==.5,"Default semantic selection changed");
    require(exact.bins.size()==2&&exact.minimumDistinctContributors==2&&exact.maxLoss==0&&exact.meanLoss==0,"Rare leaves removed or support fabricated");
    require(exact.bins[0].observationContributions+exact.bins[1].observationContributions==20,"Terminal representation not a complete partition");
    auto zeroCost=std::make_shared<const SemanticTaxonomy>("zero-parent","1",std::vector<SemanticNode>{
        {"root","",1,{}},{"family","root",0,{}},{"a","family",0,{"A"}},{"b","family",0,{"B"}}});
    SemanticAccumulator zero(zeroCost);zero.add("a","A");zero.add("b","B");
    const auto cut=zeroCost->select(zero.evidence(),2,2,2,SemanticGeneralizationMode::ExactOnly);
    require(cut.bins.size()==2&&cut.bins[0].categoryId=="a"&&cut.bins[1].categoryId=="b","Zero-loss internal node mistaken for terminal");
    auto malformed=raw;malformed.nodes.at("adult").distinctContributors=9;
    rejects([&]{taxonomy->select(malformed,20,5,5,SemanticGeneralizationMode::ExactOnly);},"Exact action skipped semantic evidence validation");
}
void fixedControlAndWholeFootprintSuppression() {
    auto control=replay("fixed",SemanticGeneralizationMode::Enabled);
    auto exact=replay("fixed",SemanticGeneralizationMode::ExactOnly);
    require(control["releases"].size()==2&&exact["releases"].size()==0,"Fixed ablation did not distinguish legal generalized release from exact support failure");
    checkExactReleases(exact);
    auto supported=replay("fixed",SemanticGeneralizationMode::ExactOnly,source(5,5));checkExactReleases(supported);
    auto enabled=replay("fixed",SemanticGeneralizationMode::Enabled,source(5,5));
    require(YAML::Dump(supported["releases"])==YAML::Dump(enabled["releases"]),"Already-supported exact types changed recipient output");
    auto neighbour=replay("fixed",SemanticGeneralizationMode::ExactOnly,source(2,3,true));checkExactReleases(neighbour);
    require(neighbour["releases"].size()==2,"Valid independent fixed cells unnecessarily suppressed");
    for(const auto& release:neighbour["releases"])
        require(release["cells"].size()==1&&release["cells"][0]["cell_id"].as<int>()==49,"Rare type was selectively removed instead of suppressing its footprint");
}
void regionalFloorsAndSuppressionRejection() {
    auto config=configuration();config["policy_tree"]["regions"].push_back("stricter");
    config["policy_regions"]=YAML::Load(R"([{id: stricter, type: test-region, x: 0, y: 0, width: 20, height: 20, requirements: {min_category_distinct_contributors: {min: 6}}}])");
    auto result=replay("fixed",SemanticGeneralizationMode::ExactOnly,source(5,5),config);checkExactReleases(result);
    require(result["releases"].size()==0,"Exact mode relaxed a regional category floor");
    config=configuration();config["policy_tree"]["root"]["semantic_suppression_fraction"]["max"]=.2;
    rejects([&]{replay("fixed",SemanticGeneralizationMode::ExactOnly,source(),config);},"Exact-only accepted selective suppression");
    config["policy_tree"]["regions"].push_back("zero-here");
    config["policy_regions"]=YAML::Load(R"([{id: zero-here, type: test-region, x: 0, y: 0, width: 20, height: 20, requirements: {semantic_suppression_fraction: {max: 0}}}])");
    rejects([&]{replay("fixed",SemanticGeneralizationMode::ExactOnly,source(),config);},"Unoccupied positive-suppression region bypassed preflight");
    config["policy_tree"]["root"]["semantic_suppression_fraction"]["max"]=0;
    config["policy_regions"][0]["requirements"]["semantic_suppression_fraction"]["max"]=.2;
    checkExactReleases(replay("fixed",SemanticGeneralizationMode::ExactOnly,source(),config));
    config=configuration();config.remove("semantic_taxonomy");
    rejects([&]{replay("fixed",SemanticGeneralizationMode::ExactOnly,source(),config);},"Exact-only without taxonomy was accepted");
}
void everyAdaptiveStrategyAndPreferencePath() {
    struct Strategy { const char* mode;bool wait,spatial; };
    for(bool local:{false,true}) for(const auto strategy:{Strategy{"temporal_first",false,false},Strategy{"spatial_first",false,false},
            Strategy{"semantic_first",false,false},Strategy{"semantic_first",true,false},Strategy{"semantic_first",true,true}}) {
        const auto sparse=replay(strategy.mode,SemanticGeneralizationMode::ExactOnly,source(),configuration(local),strategy.wait,strategy.spatial);
        checkExactReleases(sparse);require(sparse["releases"].size()==0,"An adaptive fallback generalized when actions were restricted");
        const auto supported=replay(strategy.mode,SemanticGeneralizationMode::ExactOnly,source(5,5),configuration(local),strategy.wait,strategy.spatial);
        checkExactReleases(supported);require(supported["releases"].size()>0,"Exact supported adaptive release was blocked");
        const auto minimal=replay(strategy.mode,SemanticGeneralizationMode::ExactOnly,source(5,5),configuration(local),strategy.wait,strategy.spatial,true);
        require(YAML::Dump(minimal["releases"])==YAML::Dump(supported["releases"]),"Diagnostic mode changed exact-only releases");
    }
}
void publicationRetryAndModeGuards() {
    umpReplay::Options options;options.mode="fixed";options.fixedDepth=2;options.semanticGeneralization=SemanticGeneralizationMode::ExactOnly;
    const auto input=umpReplay::parseInput(source(5,5));const auto settings=umpReplay::parseSettings(configuration(),input,options);
    auto config=settings.aggregation;std::vector<AggregationCandidate> windows;
    AggregationManager manager(config,[&](const auto& candidate){windows.push_back(candidate);});
    for(const auto& batch:input.batches)manager.ingest(batch);manager.finish(input.endMs);
    auto selected=umpReplay::fixedSelection(windows.at(0),*manager.history(),settings.evaluator,2);
    selected.assessment.cells[0].semantic->bins[0].observationContributions=999;
    PublicationCoordinator publisher(config,settings.evaluator);const auto frozen=publisher.seal(selected,400);
    require(frozen->cells[0].semantic->bins[0].observationContributions==15,"Publication trusted modified exact diagnostics instead of revalidating");
    require(!publisher.deliver(400,[](const auto&){return SinkResult::Retry;}),"Retry retired exact-only support");
    require(publisher.pendingRelease()==frozen,"Retry changed immutable exact payload");
    require(publisher.deliver(400,[](const auto&){return SinkResult::Acknowledged;}),"Exact publication ACK failed");
    auto enabledConfig=config;enabledConfig.semanticGeneralization=SemanticGeneralizationMode::Enabled;
    const auto wrong=umpReplay::evaluatorFrom(configuration(),enabledConfig);
    rejects([&]{PublicationCoordinator mismatch(config,wrong);},"Publication accepted mismatched action modes");
    SpatialSelector selector(config,{2,128});
    rejects([&]{selector.propose(windows[0],*manager.history(),wrong,0.);},"Zero-loss preference silently used default-generalizing evaluator");
    auto temporal=readTemporalAdaptation(configuration());
    rejects([&]{AdaptiveAggregation mismatch(config,*temporal,{2,128},wrong,[](const auto&){});},"Common adaptive action mismatch accepted");
    temporal->coordination=CoordinationMode::CellLocal;
    rejects([&]{CellLocalAggregation mismatch(config,*temporal,{2,128},wrong,[](const auto&){});},"Cell-local adaptive action mismatch accepted");
    auto copied=settings.evaluator;require(copied.semanticGeneralization()==SemanticGeneralizationMode::ExactOnly,"Evaluator copy lost immutable restriction");
}
void cliAndDefaultBehavior() {
    const auto parse=[](std::vector<std::string> values) {
        std::vector<char*> argv;for(auto& value:values)argv.push_back(value.data());return umpReplay::arguments(static_cast<int>(argv.size()),argv.data());
    };
    std::vector<std::string> values{"replay","--input","unused-input","--config","unused-config","--mode","fixed","--output","/private/tmp/ump-semantic-action-never-created.json"};
    require(parse(values).semanticGeneralization==SemanticGeneralizationMode::Enabled,"Default action restriction changed");
    values.insert(values.end(),{"--semantic-generalization","exact_only"});
    require(parse(values).semanticGeneralization==SemanticGeneralizationMode::ExactOnly,"Exact CLI mode not applied");
    values.back()="enabled";require(parse(values).semanticGeneralization==SemanticGeneralizationMode::Enabled,"Enabled CLI mode not applied");
    values.back()="off";rejects([&]{parse(values);},"Unknown action mode accepted");
    values.back()="exact_only";values.insert(values.end(),{"--semantic-generalization","enabled"});rejects([&]{parse(values);},"Duplicate action mode accepted");
}
}
int main() {
    try {
        truthfulTerminalRepresentation();fixedControlAndWholeFootprintSuppression();regionalFloorsAndSuppressionRejection();
        everyAdaptiveStrategyAndPreferencePath();publicationRetryAndModeGuards();cliAndDefaultBehavior();
        std::cout<<"PASS: exact-only terminal evidence, unchanged policy/support, whole-footprint suppression, all five adaptive strategies/common-local preferences, progress/conservation, publication retry and mode guards, CLI defaults.\n";
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
