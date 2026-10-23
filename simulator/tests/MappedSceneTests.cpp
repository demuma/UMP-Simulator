#include "MappedScene.hpp"
#include <cmath>
#include <functional>
#include <iostream>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

namespace {
using namespace ump;
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}
bool near(double a, double b) { return std::abs(a - b) <= 1e-10; }
template<class Work> void rejects(Work work) {
    try { work(); } catch (const std::invalid_argument&) { return; }
    throw std::runtime_error("Expected mapped scene validation rejection");
}
template<class Value, class = void> struct hasPersonId : std::false_type {};
template<class Value> struct hasPersonId<Value, std::void_t<decltype(std::declval<Value>().personId)>>
    : std::true_type {};
static_assert(!hasPersonId<MappedVisibleTrack>::value,
    "Operational visible tracks must not expose private stable person identifiers");

MappedSceneConfig visitingScene() {
    return {10, 10,
        {{"inbound", {{0, 5}, {2, 5}}, "", "building-door"},
            {"outbound", {{2, 5}, {0, 5}}, "building-door", ""}},
        {{"private-person", "Pedestrian With Stroller", 2,
            {{"opaque-a", "inbound", 0}, {"opaque-b", "outbound", 2000}}}}};
}

void sameFrame(const std::vector<MappedVisibleTrack>& a, const std::vector<MappedVisibleTrack>& b) {
    require(a.size() == b.size(), "Visible population changed");
    for (std::size_t i = 0; i < a.size(); ++i)
        require(a[i].trackId == b[i].trackId && a[i].type == b[i].type
            && a[i].routeId == b[i].routeId && a[i].nextWaypointIndex == b[i].nextWaypointIndex
            && near(a[i].position.x, b[i].position.x)
            && near(a[i].position.y, b[i].position.y) && near(a[i].velocity.x, b[i].velocity.x)
            && near(a[i].velocity.y, b[i].velocity.y), "Visible frame changed");
}

void cornersAndLargeSteps() {
    MappedScene scene({10, 10,
        {{"corner-route", {{0, 0}, {3, 0}, {3, 4}, {10, 4}}, "", ""}},
        {{"corner-person", "Adult Pedestrian", 2, {{"corner-track", "corner-route", 1000}}}}});
    require(near(scene.routeLength("corner-route"), 14), "Polyline length ignored a corner");
    require(scene.episodeEndMs("corner-track") == 8000, "Arrival time must use full arc length");
    require(scene.frameAt(999).empty(), "Track appeared before arrival schedule");
    const auto start = scene.frameAt(1000).at(0);
    require(near(start.position.x, 0) && near(start.position.y, 0)
        && near(start.velocity.x, 2) && near(start.velocity.y, 0), "Initial route state is wrong");
    const auto firstCorner = scene.frameAt(2500).at(0);
    require(near(firstCorner.position.x, 3) && near(firstCorner.position.y, 0)
        && near(firstCorner.velocity.x, 0) && near(firstCorner.velocity.y, 2)
        && firstCorner.nextWaypointIndex == 2,
        "Exact corner must use the outgoing segment");
    const auto beyondTwoCorners = scene.frameAt(7500).at(0);
    require(near(beyondTwoCorners.position.x, 9) && near(beyondTwoCorners.position.y, 4),
        "Large query step cut a corner or lost remaining travel distance");
    require(scene.frameAt(8000).empty() && scene.frameAt(100000).empty(),
        "Arrival must end visibility without overshoot or a stale final position");
}

void halfOpenAndRoundedArrival() {
    MappedScene scene({10, 10,
        {{"short-route", {{0, 0}, {1, 0}}, "", "door"}},
        {{"short-person", "Adult Pedestrian", 3, {{"short-track", "short-route", 0}}}}});
    require(mappedEpisodeDurationMs(scene.configuration().routes.front(), 3) == 334
        && scene.episodeEndMs("short-track") == 334, "Noninteger travel duration must round up");
    require(near(scene.frameAt(333).at(0).position.x, .999) && scene.frameAt(334).empty(),
        "Episode interval is not half-open at its quantized arrival");
    const auto& events = scene.events();
    require(events.size() == 2 && events[0].kind == MappedEventKind::EpisodeStart
        && events[0].atMs == 0 && events[0].portalId.empty()
        && events[1].kind == MappedEventKind::EpisodeEnd && events[1].atMs == 334
        && events[1].portalId == "door", "Private source/portal events contradict motion");
}

void hiddenGapAndReentry() {
    MappedScene scene(visitingScene());
    require(scene.minimumHiddenGapMs() == 1000, "Hidden dwell gap is wrong");
    require(scene.frameAt(999).at(0).trackId == "opaque-a"
        && scene.frameAt(1000).empty() && scene.frameAt(1999).empty()
        && scene.frameAt(2000).at(0).trackId == "opaque-b" && scene.frameAt(3000).empty(),
        "Portal entry, invisible dwell or fresh-track reentry is wrong");
    require(scene.privatePersonForTrack("opaque-a") == "private-person"
        && scene.privatePersonForTrack("opaque-b") == "private-person",
        "Evaluation oracle lost stable person continuity");
    const auto& events = scene.events();
    require(events.size() == 4 && events[1].portalId == "building-door"
        && events[2].portalId == "building-door" && events[1].personId == events[2].personId
        && events[1].trackId != events[2].trackId, "Private visit events lost track/person separation");
}

void privateRenamingAndCallOrder() {
    auto input = visitingScene();
    input.people.push_back({"other-private-person", "Pedestrian With Mobility Aid", 1,
        {{"opaque-0", "inbound", 250}}});
    MappedScene a(input);
    input.people[0].personId = "unrelated-private-name";
    input.people[1].personId = "also-renamed";
    std::reverse(input.people.begin(), input.people.end());
    MappedScene b(input);
    for (auto time : {0, 500, 1000, 2000, 2500, 3000}) sameFrame(a.frameAt(time), b.frameAt(time));
    const auto expected = a.frameAt(500);
    a.frameAt(50000); a.frameAt(0); a.frameAt(1999);
    sameFrame(expected, a.frameAt(500));
    require(expected.at(0).trackId == "opaque-0" && expected.at(1).trackId == "opaque-a",
        "Frame ordering must depend on operational tracks, not private identities");
}

void shortGapInflatesTrackSupport() {
    const MappedScene scene(visitingScene());
    std::set<std::string> tracks, people;
    for (const auto time : {500, 2500})
        for (const auto& track : scene.frameAt(time)) {
            tracks.insert(track.trackId);
            people.insert(scene.privatePersonForTrack(track.trackId));
        }
    require(tracks.size() == 2 && people.size() == 1,
        "Short-gap counterexample must expose track inflation rather than silently use GT deduplication");
}

void touchingEpisodesAndSortedEvents() {
    auto input = visitingScene();
    input.people[0].episodes[1].startMs = 1000;
    std::reverse(input.people[0].episodes.begin(), input.people[0].episodes.end());
    MappedScene scene(input);
    require(scene.minimumHiddenGapMs() == 0 && scene.frameAt(1000).size() == 1
        && scene.frameAt(1000).front().trackId == "opaque-b", "Touching episodes overlap at boundary");
    require(scene.events()[1].atMs == 1000 && scene.events()[2].atMs == 1000
        && scene.events()[1].kind == MappedEventKind::EpisodeEnd
        && scene.events()[2].kind == MappedEventKind::EpisodeStart,
        "Same-time events must end the old episode before starting the new one");
    input.people[0].episodes.resize(1);
    require(!MappedScene(input).minimumHiddenGapMs(), "Single-episode scene fabricated a hidden gap");
}

void invalidConfigurations() {
    const auto valid = visitingScene();
    const auto bad = [&](const std::function<void(MappedSceneConfig&)>& mutate) {
        auto input = valid; mutate(input); rejects([&] { MappedScene scene(input); });
    };
    bad([](auto& c) { c.width = 0; });
    bad([](auto& c) { c.height = std::numeric_limits<double>::infinity(); });
    bad([](auto& c) { c.routes.clear(); });
    bad([](auto& c) { c.people.clear(); });
    bad([](auto& c) { c.routes[0].points.resize(1); });
    bad([](auto& c) { c.routes[0].points[1] = c.routes[0].points[0]; });
    bad([](auto& c) { c.routes[0].points[1].x = std::numeric_limits<double>::quiet_NaN(); });
    bad([](auto& c) { c.routes[0].points[0].x = -1; });
    bad([](auto& c) { c.routes[0].points[1].x = 11; });
    bad([](auto& c) { c.routes[0].points[0] = {1, 5}; });
    bad([](auto& c) { c.routes[0].endPortal.clear(); });
    bad([](auto& c) { c.routes[0].startPortal = " \t"; });
    bad([](auto& c) { c.routes[1].id = c.routes[0].id; });
    bad([](auto& c) { c.people[0].personId = c.routes[0].id; });
    bad([](auto& c) { c.people[0].type.clear(); });
    bad([](auto& c) { c.people[0].speedMps = 0; });
    bad([](auto& c) { c.people[0].speedMps = -1; });
    bad([](auto& c) { c.people[0].speedMps = std::numeric_limits<double>::infinity(); });
    bad([](auto& c) { c.people[0].speedMps = std::numeric_limits<double>::denorm_min(); });
    bad([](auto& c) { c.people[0].speedMps = 2000.0 / std::ldexp(1.0, 63); });
    bad([](auto& c) { c.people[0].episodes.clear(); });
    bad([](auto& c) { c.people[0].episodes[0].trackId.clear(); });
    bad([](auto& c) { c.people[0].episodes[0].trackId = c.people[0].personId; });
    bad([](auto& c) { c.people[0].episodes[1].trackId = c.people[0].episodes[0].trackId; });
    bad([](auto& c) { c.people[0].episodes[0].routeId = "unknown-route"; });
    bad([](auto& c) { c.people[0].episodes[0].startMs = -1; });
    bad([](auto& c) { c.people[0].episodes[1].startMs = 999; });
    bad([](auto& c) { c.people[0].episodes[1].startMs = std::numeric_limits<AggregationTime>::max(); });
    bad([](auto& c) { c.people.push_back(c.people.front()); });
    bad([](auto& c) { auto person = c.people.front(); person.personId = "new-person"; c.people.push_back(person); });
    bad([](auto& c) { auto person = c.people.front(); person.personId = c.people[0].episodes[0].trackId;
        person.episodes = {{"new-track", "inbound", 0}}; c.people.push_back(person); });
    const MappedScene scene(valid);
    rejects([&] { scene.frameAt(-1); });
    rejects([&] { scene.routeLength("unknown-route"); });
    rejects([&] { scene.episodeEndMs("unknown-track"); });
    rejects([&] { scene.privatePersonForTrack("unknown-track"); });
}
} // namespace

int main() {
    try {
        cornersAndLargeSteps();
        halfOpenAndRoundedArrival();
        hiddenGapAndReentry();
        privateRenamingAndCallOrder();
        shortGapInflatesTrackSupport();
        touchingEpisodesAndSortedEvents();
        invalidConfigurations();
        std::cout << "Mapped scene route, lifecycle, identity-boundary and validation tests passed\n";
    } catch (const std::exception& error) {
        std::cerr << "Mapped scene test failed: " << error.what() << '\n';
        return 1;
    }
}
