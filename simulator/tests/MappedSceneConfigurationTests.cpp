#include "MappedSceneConfiguration.hpp"
#include <algorithm>
#include <iostream>
#include <optional>
#include <set>
#include <stdexcept>

namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
int rejectionCase=0;
template<class F> void rejects(F work) {
    ++rejectionCase;
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected mapped configuration rejection case "+std::to_string(rejectionCase));
}
YAML::Node fixture() {
    return YAML::Load(R"(
support_contract: one_episode_per_retained_history
routes:
  - id: in
    points: [[0,5], [2,5]]
    end_portal: door
  - id: out
    points: [[2,5], [0,5]]
    start_portal: door
people:
  - person_id: private-person
    type: Pedestrian With Stroller
    speed_mps: 2
    episodes:
      - {track_id: opaque-first, route_id: in, start_ms: 0}
      - {track_id: opaque-return, route_id: out, start_ms: 10000}
)");
}

ump::AggregationTime observedPeriod(const std::string& text) {
    require(!text.empty() && text.find_first_not_of("0123456789")==std::string::npos,
        "Observation period must be a positive decimal integer");
    const auto value=std::stoll(text);
    require(value>0,"Observation period must be a positive decimal integer");
    return value;
}

std::set<std::string> advanceAndObserve(ump::MappedScene& scene,ump::AggregationTime endMs,
    ump::AggregationTime periodMs) {
    const auto& cfg=scene.configuration();
    require(cfg.motionMode!=ump::MappedMotionMode::Integration,
        "Observation drain requires stateful mapped motion");
    require(periodMs>0 && periodMs%cfg.motionStepMs==0,
        "Observation period must be positive and aligned with the motion step");
    require(endMs>0 && endMs%cfg.motionStepMs==0,
        "Observation drain horizon must be positive and aligned with the motion step");
    std::set<std::string> observed;
    // Follow the numerical source cadence (50 ms in the mapped fixture), then
    // observe only at positive sensor timestamps. t=0 is not a sensor sample.
    for (ump::AggregationTime now=0;now<endMs;) {
        now+=cfg.motionStepMs;
        scene.advanceTo(now);
        if (now%periodMs) continue;
        for (const auto& track:scene.frameAt(now)) {
            const auto point=track.position;
            // Match grid sensor ownership exactly: upper edges are excluded.
            // A lifecycle-complete track tangent to x=width is not observed.
            if (point.x>=0 && point.x<cfg.width && point.y>=0 && point.y<cfg.height)
                observed.insert(track.trackId);
        }
    }
    return observed;
}

ump::MappedSceneConfig observedFixture(std::vector<ump::Point> points) {
    ump::MappedSceneConfig cfg;
    cfg.width=10;cfg.height=10;cfg.motionMode=ump::MappedMotionMode::CorridorFollowing;
    cfg.motionStepMs=50;
    ump::MappedRoute route;route.id="observation-route";route.points=std::move(points);
    cfg.routes.push_back(route);
    ump::MappedPerson person;person.personId="private-observation-person";
    person.type="Pedestrian With Stroller";person.speedMps=2;
    person.episodes.push_back({"observation-track",route.id,0});
    cfg.people.push_back(person);
    return cfg;
}

void observationGuardTests() {
    ump::MappedScene transverse(observedFixture({{0,5},{10,5}}));
    require(advanceAndObserve(transverse,6000,100).size()==1
        && transverse.motionDiagnostics().realizedEnds==1,
        "An interior transverse route was not observed before safe drainage");
    ump::MappedScene lowerEdge(observedFixture({{0,1},{0,3}}));
    require(advanceAndObserve(lowerEdge,2000,100).size()==1,
        "The included lower-x coverage boundary was rejected");
    ump::MappedScene tangent(observedFixture({{10,1},{10,3}}));
    const auto missing=advanceAndObserve(tangent,2000,100);
    require(missing.empty() && tangent.motionDiagnostics().realizedEnds==1,
        "A max-x tangent route incorrectly counted as observed inside half-open coverage");
    rejects([&]{require(missing.size()==1,"Lifecycle completion cannot replace sensor observation");});
    auto shortConfig=observedFixture({{0,5},{.1,5}});
    shortConfig.routes[0].endPortal="short-fixture-door"; // Legacy implicit portal at the internal endpoint.
    ump::MappedScene shortEpisode(shortConfig);
    require(advanceAndObserve(shortEpisode,200,100).empty()
        && shortEpisode.motionDiagnostics().realizedEnds==1,
        "An unsampled 50-ms episode was incorrectly rescued by a t=0 sample");
    for (const auto* text:{"","0","-100","100x","100.0","+100"," 100"})
        rejects([&]{observedPeriod(text);});
    require(observedPeriod("100")==100,"A valid observation period changed");
    for (const auto period:{0,75,-100}) {
        ump::MappedScene invalid(observedFixture({{0,5},{10,5}}));
        rejects([&]{advanceAndObserve(invalid,6000,period);});
    }
}

int drainConfiguration(const std::string& path, ump::AggregationTime endMs,
    std::optional<ump::AggregationTime> requiredObservedPeriod=std::nullopt) {
    const auto cfg=YAML::LoadFile(path);
    std::unordered_set<std::string> profiles;
    for (const auto& row:cfg["agents"]["road_user_taxonomy"])
        profiles.insert(row["type"].as<std::string>());
    const double width=cfg["simulation"]["width"].as<double>();
    const double height=cfg["simulation"]["height"].as<double>();
    ump::MappedScene scene(readMappedSceneConfiguration(cfg["mapped_scene"],width,height,profiles));
    require(scene.configuration().motionMode!=ump::MappedMotionMode::Integration,
        "Drain gate requires stateful mapped motion");
    require(endMs>0 && endMs%scene.configuration().motionStepMs==0,
        "Drain horizon must be positive and aligned with the motion step");
    std::size_t expected=0;
    for (const auto& person:scene.configuration().people) expected+=person.episodes.size();
    std::set<std::string> observed;
    if(requiredObservedPeriod) observed=advanceAndObserve(scene,endMs,*requiredObservedPeriod);
    else scene.advanceTo(endMs);
    const auto d=scene.motionDiagnostics();
    ump::AggregationTime lastEnd=0;
    std::set<std::string> starts,ends;
    for (const auto& event:scene.events()) {
        auto& seen=event.kind==ump::MappedEventKind::EpisodeStart ? starts : ends;
        require(seen.insert(event.trackId).second,"A realized lifecycle event was duplicated");
        if(event.kind==ump::MappedEventKind::EpisodeEnd) lastEnd=std::max(lastEnd,event.atMs);
    }
    std::cout << "Mapped finite drain: scheduled="<<expected<<" starts="<<d.realizedStarts
        <<" ends="<<d.realizedEnds<<" active="<<d.activeTracks<<" pending="<<d.pendingTracks
        <<" stalled="<<d.activeStalledTracks<<" overlaps="<<d.overlapViolations
        <<" max_stop_ms="<<d.maxConsecutiveStopMs<<" merge_wait_steps="<<d.mergeAdmissionWaitSteps
        <<" navigation_steering="<<d.navigationSteeringSteps<<" navigation_replans="<<d.navigationReplans
        <<" navigation_replan_failures="<<d.navigationReplanFailures<<" navigation_search_max="<<d.navigationMaxSearchNodes
        <<" passage_wait_steps="<<d.passageWaitSteps<<" passage_batches="<<d.passageBatches
        <<" passage_cleared_tracks="<<d.passageClearedTracks<<" max_passage_wait_ms="<<d.maxPassageWaitMs;
    if(requiredObservedPeriod) std::cout<<" observed="<<observed.size()<<" observed_period_ms="<<*requiredObservedPeriod;
    std::cout<<" last_end_ms="<<lastEnd<<" horizon_ms="<<endMs<<'\n';
    require(d.realizedStarts==expected && d.realizedEnds==expected && starts==ends
        && starts.size()==expected && scene.events().size()==2*expected,
        "Scheduled finite source did not produce exactly one realized start/end per track");
    require(d.activeTracks==0 && d.pendingTracks==0 && d.activeStalledTracks==0
        && d.overlapViolations==0,"Finite source did not drain safely within the declared horizon");
    if(requiredObservedPeriod) require(observed.size()==expected && observed==starts,
        "Finite source drained but some scheduled tracks were never observed inside half-open sensor coverage");
    return 0;
}

}
int main(int argc,char** argv) {
    try {
        if(argc>1) {
            require((argc==5 || argc==7) && std::string(argv[1])=="--drain-config"
                && std::string(argv[3])=="--end-ms"
                && (argc==5 || std::string(argv[5])=="--require-observed-period-ms"),
                "Usage: MappedSceneConfigurationTests --drain-config <config.yaml> --end-ms <horizon> [--require-observed-period-ms <period>]");
            return drainConfiguration(argv[2],std::stoll(argv[4]),
                argc==7 ? std::optional<ump::AggregationTime>{observedPeriod(argv[6])} : std::nullopt);
        }
        observationGuardTests();
        const std::unordered_set<std::string> profiles{"Pedestrian With Stroller"};
        const auto read = [&](const YAML::Node& n) { return readMappedSceneConfiguration(n, 10, 10, profiles); };
        const ump::MappedScene scene(read(fixture()));
        require(scene.configuration().people.size() == 1 && scene.minimumHiddenGapMs() == 9000,
            "Explicit people or gap was not preserved");
        validateMappedSupportHorizon(scene, 6000);
        validateMappedSupportHorizon(scene, 8999);
        rejects([&] { validateMappedSupportHorizon(scene, 9000); });
        rejects([&] { validateMappedSupportHorizon(scene, 10000); });
        rejects([&] { validateMappedSupportHorizon(scene, 0); });
        rejects([&] { auto n=fixture(); n["support_contract"]="oracle_person_deduplication"; read(n); });
        rejects([&] { auto n=fixture(); n.remove("support_contract"); read(n); });
        rejects([&] { auto n=fixture(); n["typo"]=1; read(n); });
        rejects([&] { auto n=fixture(); n["people"][0]["type"]="Unknown Pedestrian"; read(n); });
        rejects([&] { auto n=fixture(); n["routes"][0]["points"][0]=YAML::Load("[0,5,7]"); read(n); });
        rejects([&] { auto n=fixture(); n["routes"][0]["points"][0][0]=".nan"; read(n); });
        rejects([&] { auto n=fixture(); n["people"][0]["episodes"][0]["route_id"]="missing"; read(n); });
        rejects([&] { auto n=fixture(); n["people"][0]["episodes"][0]["extra"]=true; read(n); });
        rejects([&] { auto n=fixture(); n["people"][0]["episodes"][0]["start_ms"]=1.5; read(n); });
        rejects([&] { auto n=fixture(); n["people"][0]["episodes"][1]["track_id"]="opaque-first"; read(n); });
        rejects([&] { auto n=fixture(); n["people"][0]["speed_mps"]=0; read(n); });
        rejects([&] { auto n=fixture(); n["people"]=YAML::Node(YAML::NodeType::Sequence); read(n); });
        rejects([&] { auto n=fixture(); n["routes"][0]["id"]=YAML::Node(YAML::NodeType::Null); read(n); });
        auto corridor=fixture();
        corridor["motion"]=YAML::Load("{mode: corridor_following, step_ms: 50, clearance_m: 0.1, portal_gate_radius_m: 1}");
        corridor["people"][0]["episodes"][1]["start_ms"]=0;
        corridor["people"][0]["episodes"][1]["after_previous_ms"]=8000;
        corridor["people"][0]["radius_m"]=.4;
        ump::MappedScene queued(read(corridor));
        validateMappedSupportHorizon(queued,6000);
        queued.advanceTo(12000);
        require(queued.motionDiagnostics().realizedEnds==2 && queued.minimumHiddenGapMs()==8000,
            "Corridor YAML did not preserve relative realized-arrival return scheduling");
        rejects([&]{auto n=YAML::Clone(corridor);n["motion"]["step_ms"]=30;read(n);});
        rejects([&]{auto n=YAML::Clone(corridor);n["motion"]["clearance_m"]=-1;read(n);});
        rejects([&]{auto n=YAML::Clone(corridor);n["motion"]["mode"]="orca";read(n);});
        rejects([&]{auto n=YAML::Clone(corridor);n["people"][0]["radius_m"]=0;read(n);});
        rejects([&]{auto n=YAML::Clone(corridor);n["people"][0]["episodes"][1].remove("after_previous_ms");read(n);});
        rejects([&]{auto n=fixture();n["people"][0]["episodes"][1]["after_previous_ms"]=8000;read(n);});
        auto explicitDoors=YAML::Clone(corridor);
        explicitDoors["portals"]=YAML::Load(R"([{
            id: door, building_id: mapped-building, point: [2,5],
            facade: [[2,3],[2,7]], width_m: 1.2, provenance: synthetic}])");
        const auto precise=read(explicitDoors);
        require(precise.portals.size()==1 && precise.portals[0].buildingId=="mapped-building"
            && precise.portals[0].point.x==2 && precise.portals[0].facadeEnd.y==7
            && precise.portals[0].widthM==1.2 && precise.portals[0].provenance=="synthetic",
            "Explicit building door geometry was not preserved");
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"][0]["typo"]=1;read(n);});
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"]=YAML::Load("{id: door}");read(n);});
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"][0]["facade"]=YAML::Load("[[2,3]]");read(n);});
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"][0]["point"]=YAML::Load("[2,5,7]");read(n);});
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"][0].remove("building_id");read(n);});
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"][0]["provenance"]="unknown";read(n);});
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"][0]["point"][0]=".nan";read(n);});
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"].push_back(YAML::Clone(n["portals"][0]));read(n);});
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"][0]["width_m"]=.7;read(n);});
        rejects([&]{auto n=YAML::Clone(explicitDoors);n["portals"][0]["id"]="different-door";read(n);});
        auto navigating=YAML::Clone(corridor);
        navigating["motion"]=YAML::Load(R"({mode: local_navigation, step_ms: 50, clearance_m: .1,
            navigation: {center_clearance_m: .55, grid_resolution_m: .5, max_replan_nodes: 500,
            replan_after_ms: 1500, replan_interval_ms: 1000,
            allowed_center_polygons: [{outer: [[0,0],[10,0],[10,10],[0,10]], holes: []}]}})");
        const auto navigationConfig=read(navigating);
        require(navigationConfig.motionMode==ump::MappedMotionMode::LocalNavigation
            && navigationConfig.navigation.centerClearanceM==.55
            && navigationConfig.navigation.allowedCenterPolygons.size()==1
            && navigationConfig.navigation.maxReplanNodes==500
            && navigationConfig.navigation.narrowPassages.empty(),
            "Local navigation YAML lost its explicit geometry and bounded settings");
        auto spaced=YAML::Clone(navigating);
        spaced["motion"]["navigation"]["spaces"]=YAML::Load(R"([{id: road, center_clearance_m: .6,
            allowed_center_polygons: [{outer: [[0,0],[10,0],[10,10],[0,10]], holes: []}]}])");
        spaced["routes"][0]["navigation_space"]="road";
        const auto spacedConfig=read(spaced);
        require(spacedConfig.routes[0].navigationSpace=="road" && spacedConfig.navigation.spaces.size()==1,
            "Movement-space YAML lost route-specific permissions");
        rejects([&]{auto n=YAML::Clone(spaced);n["routes"][0]["navigation_space"]="missing";read(n);});
        rejects([&]{auto n=YAML::Clone(spaced);n["motion"]["navigation"]["spaces"][0]["typo"]=true;read(n);});
        rejects([&]{auto n=YAML::Clone(spaced);n["motion"]["navigation"]["spaces"]=YAML::Load("{}");read(n);});
        rejects([&]{auto n=YAML::Clone(spaced);n["motion"]["navigation"]["spaces"][0]["center_clearance_m"]=.49;read(n);});
        rejects([&]{auto n=YAML::Clone(spaced);n["motion"]["navigation"]["spaces"][0]["allowed_center_polygons"]=YAML::Load("[]");read(n);});
        rejects([&]{auto n=YAML::Clone(spaced);n["motion"]["navigation"]["spaces"][0]["allowed_center_polygons"][0]["holes"]=YAML::Load("{}");read(n);});
        require(navigationConfig.navigation.doorMaxBatchSize==1,"Legacy door batch default changed");
        auto pipelined=YAML::Clone(navigating);pipelined["motion"]["navigation"]["door_max_batch_size"]=6;
        require(read(pipelined).navigation.doorMaxBatchSize==6,"Door batch option was not preserved");
        for (const auto invalid:{0,65,-1})
            rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["navigation"]["door_max_batch_size"]=invalid;read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["navigation"]["door_max_batch_size"]=1.5;read(n);});
        auto boundarySink=YAML::Clone(navigating);
        // This fixture returns to x=0,y=5 on its second episode.
        const auto sinkPoint=boundarySink["routes"][1]["points"];
        const auto last=sinkPoint[sinkPoint.size()-1];
        if(last[0].as<double>()==0) {
            boundarySink["routes"][1]["end_boundary"]=YAML::Load("[[0,1],[0,9]]");
            require(read(boundarySink).routes[1].endBoundary.size()==2,"Boundary sink YAML was lost");
            rejects([&]{auto n=YAML::Clone(boundarySink);n["routes"][1]["end_boundary"]=YAML::Load("[[0,1]]");read(n);});
            rejects([&]{auto n=YAML::Clone(boundarySink);n["routes"][1]["end_boundary"]=YAML::Load("[[0,1],[1,9]]");read(n);});
        }
        ump::MappedScene navigatingScene(navigationConfig);
        validateMappedCaptureStep(navigatingScene,50);
        rejects([&]{validateMappedCaptureStep(navigatingScene,100);});
        rejects([&]{validateMappedCaptureStep(navigatingScene,25);});
        rejects([&]{validateMappedCaptureStep(navigatingScene,0);});
        rejects([&]{validateMappedCaptureStep(navigatingScene,50.4);});
        validateMappedCaptureStep(scene,100);validateMappedCaptureStep(queued,100);
        navigatingScene.advanceTo(20000);
        require(navigatingScene.motionDiagnostics().realizedEnds==2,
            "Local navigation YAML visit failed to finish");
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["step_ms"]=1.5;read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["clearance_m"]="invalid";read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["people"][0]["radius_m"]="invalid";read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"].remove("navigation");read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["mode"]="corridor_following";read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["navigation"]["typo"]=true;read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["navigation"]["allowed_center_polygons"]=YAML::Load("[]");read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["navigation"]["allowed_center_polygons"][0]["outer"][0]=YAML::Load("[0,0,1]");read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["navigation"]["allowed_center_polygons"][0]["holes"]=YAML::Load("[[[20,20],[21,20],[20,21]]]");read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["navigation"]["center_clearance_m"]=.49;read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["navigation"]["max_replan_nodes"]=-1;read(n);});
        rejects([&]{auto n=YAML::Clone(navigating);n["motion"]["navigation"]["replan_interval_ms"]=0;read(n);});
        auto passageNavigation=YAML::Clone(navigating);
        passageNavigation["motion"]["navigation"]["narrow_passages"]=YAML::Load(R"([{
            id: shared-passage, centerline: [[4,5],[6,5]],
            holding_points_a: [[2,3],[2,7]], holding_points_b: [[8,3],[8,7]],
            protection_radius_m: 1.15, max_batch_size: 6}])");
        const auto coordinated=read(passageNavigation);
        require(coordinated.navigation.narrowPassages.size()==1
            && coordinated.navigation.narrowPassages[0].id=="shared-passage"
            && coordinated.navigation.narrowPassages[0].centerline.size()==2
            && coordinated.navigation.narrowPassages[0].centerline[1].x==6
            && coordinated.navigation.narrowPassages[0].holdingPointsA[0].y==3
            && coordinated.navigation.narrowPassages[0].holdingPointsB[1].x==8
            && coordinated.navigation.narrowPassages[0].protectionRadiusM==1.15
            && coordinated.navigation.narrowPassages[0].maxBatchSize==6,
            "Optional narrow-passage YAML lost its identity, geometry or finite batch settings");
        auto defaultPassage=YAML::Clone(passageNavigation);
        defaultPassage["motion"]["navigation"]["narrow_passages"][0].remove("protection_radius_m");
        defaultPassage["motion"]["navigation"]["narrow_passages"][0].remove("max_batch_size");
        const auto defaultCoordinated=read(defaultPassage);
        require(defaultCoordinated.navigation.narrowPassages[0].protectionRadiusM==1.15
            && defaultCoordinated.navigation.narrowPassages[0].maxBatchSize==6,
            "Optional narrow-passage numeric defaults changed");
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"]=YAML::Load("{}");read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["typo"]=1;read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0].remove("id");read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["id"]="";read(n);});
        for (const auto* name:{"centerline","holding_points_a","holding_points_b"}) {
            rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0].remove(name);read(n);});
            rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0][name]=YAML::Load("{}");read(n);});
            rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0][name][0]=YAML::Load("[1,2,3]");read(n);});
        }
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["protection_radius_m"]="invalid";read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["max_batch_size"]=1.5;read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["max_batch_size"]=0;read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["max_batch_size"]=65;read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["protection_radius_m"]=0;read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["protection_radius_m"]=".nan";read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["centerline"]=YAML::Load("[[4,5]]");read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["centerline"][1]=YAML::Load("[4,5]");read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["holding_points_a"]=YAML::Load("[]");read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"][0]["holding_points_b"][0]=YAML::Load("[4,5]");read(n);});
        rejects([&]{auto n=YAML::Clone(passageNavigation);n["motion"]["navigation"]["narrow_passages"].push_back(YAML::Clone(n["motion"]["navigation"]["narrow_passages"][0]));read(n);});
        std::cout << "Mapped scene YAML and retained-history support guards passed\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
