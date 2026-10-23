#include "MappedSceneConfiguration.hpp"
#include <iostream>
#include <set>
#include <stdexcept>

namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
template<class F> void rejects(F work) {
    try { work(); } catch (const std::exception&) { return; }
    throw std::runtime_error("Expected mapped configuration rejection");
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
    require(scene.configuration().motionMode==ump::MappedMotionMode::CorridorFollowing,
        "Drain gate requires stateful corridor motion");
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
        std::cout << "Mapped scene YAML and retained-history support guards passed\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
