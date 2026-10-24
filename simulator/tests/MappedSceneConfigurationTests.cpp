#include "MappedSceneConfiguration.hpp"
#include <iostream>
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

int drainConfiguration(const std::string& path, ump::AggregationTime endMs) {
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
    scene.advanceTo(endMs);
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
        <<" passage_cleared_tracks="<<d.passageClearedTracks<<" max_passage_wait_ms="<<d.maxPassageWaitMs
        <<" last_end_ms="<<lastEnd<<" horizon_ms="<<endMs<<'\n';
    require(d.realizedStarts==expected && d.realizedEnds==expected && starts==ends
        && starts.size()==expected && scene.events().size()==2*expected,
        "Scheduled finite source did not produce exactly one realized start/end per track");
    require(d.activeTracks==0 && d.pendingTracks==0 && d.activeStalledTracks==0
        && d.overlapViolations==0,"Finite source did not drain safely within the declared horizon");
    return 0;
}

}
int main(int argc,char** argv) {
    try {
        if(argc>1) {
            require(argc==5 && std::string(argv[1])=="--drain-config" && std::string(argv[3])=="--end-ms",
                "Usage: MappedSceneConfigurationTests --drain-config <config.yaml> --end-ms <horizon>");
            return drainConfiguration(argv[2],std::stoll(argv[4]));
        }
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
