#include "MappedSceneConfiguration.hpp"
#include <iostream>
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
}
int main() {
    try {
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
        std::cout << "Mapped scene YAML and retained-history support guards passed\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
