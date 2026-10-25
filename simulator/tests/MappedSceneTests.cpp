#include "MappedScene.hpp"
#include <algorithm>
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

void conservativeFollowersAndActualVelocity() {
    MappedSceneConfig input{20,10,{{"lane",{{0,2},{8,2},{8,6},{20,6}},"",""}},
        {{"leader-person","Adult Pedestrian",1,{{"leader","lane",0}}},
            {"follower-person","Adult Pedestrian",2,{{"follower","lane",200}}}}};
    input.motionMode=MappedMotionMode::CorridorFollowing;
    MappedScene scene(input);
    bool sawBlocked=false;
    std::map<std::string,Point> previousPositions;
    for (int time=0;time<=30000;time+=50) {
        scene.advanceTo(time);const auto frame=scene.frameAt(time);
        for (std::size_t a=0;a<frame.size();++a) for (std::size_t b=a+1;b<frame.size();++b)
            require(std::hypot(frame[a].position.x-frame[b].position.x,
                    frame[a].position.y-frame[b].position.y)>=.5-1e-7,
                "Follower body overlapped its leader at a corner");
        if (scene.motionDiagnostics().blockedMotionSteps) sawBlocked=true;
        for (const auto& track:frame) {
            require(std::hypot(track.velocity.x,track.velocity.y)<=2+1e-9,
                "Realized velocity exceeded the declared preferred speed");
            const auto previous=previousPositions.find(track.trackId);
            if (previous!=previousPositions.end())
                require(std::abs(track.velocity.x-(track.position.x-previous->second.x)/.05)<1e-8
                    && std::abs(track.velocity.y-(track.position.y-previous->second.y)/.05)<1e-8,
                    "Reported actual velocity differs from realized finite-step displacement");
        }
        previousPositions.clear();
        for (const auto& track:frame) previousPositions.emplace(track.trackId,track.position);
    }
    require(sawBlocked && scene.motionDiagnostics().admissionWaitSteps>0
        && scene.motionDiagnostics().overlapViolations==0,"Follower/admission collision response did not occur");
    require(scene.episodeEndMs("follower")>12000,"Faster follower ignored collision delay");
    rejects([&]{scene.advanceTo(0);});
}

void separatedOpposingLanesAndRealizedPortalGap() {
    MappedSceneConfig input{12,10,
        {{"east",{{0,2},{12,2}},"",""},{"west",{{12,4},{0,4}},"",""},
            {"door-in",{{0,7},{6,7}},"","door"},
            {"door-out",{{6,7},{6,5},{0,5}},"door",""}},
        {{"east-person","Adult Pedestrian",2,{{"east-track","east",0}}},
            {"west-person","Adult Pedestrian",2,{{"west-track","west",0}}},
            {"door-leader-person","Adult Pedestrian",1,{{"door-leader","door-in",0}}},
            {"visitor-person","Adult Pedestrian",2,
                {{"in-track","door-in",200},{"out-track","door-out",0,8000}}}}};
    input.motionMode=MappedMotionMode::CorridorFollowing;input.portalGateRadiusM=1;
    MappedScene scene(input);
    for (int time=0;time<=20000;time+=50) scene.advanceTo(time);
    require(scene.motionDiagnostics().realizedEnds==5 && scene.motionDiagnostics().overlapViolations==0,
        "Separated opposing lanes or the portal visit failed to finish");
    AggregationTime entry=-1,reentry=-1;
    for (const auto& event:scene.events()) {
        if (event.trackId=="in-track" && event.kind==MappedEventKind::EpisodeEnd) entry=event.atMs;
        if (event.trackId=="out-track" && event.kind==MappedEventKind::EpisodeStart) reentry=event.atMs;
    }
    require(entry>3200 && reentry-entry>=8000,"Indoor gap was based on planned rather than delayed realized arrival");
    MappedScene coarse(input);
    coarse.advanceTo(20000);
    require(coarse.motionDiagnostics().realizedEnds==5 && coarse.events().size()==scene.events().size(),
        "A large caller step changed bounded motion or lifecycle counts");
    for (std::size_t i=0;i<scene.events().size();++i)
        require(scene.events()[i].trackId==coarse.events()[i].trackId
            && scene.events()[i].atMs==coarse.events()[i].atMs,
            "Caller cadence changed realized admission or departure time");
    rejects([&]{coarse.advanceTo(20001);});
}


void boundedBranchMergeAdmitsWaitingExitsAndDrains() {
    MappedSceneConfig input{30,16,
        {{"through",{{0,6},{15,6},{30,6}},"",""},
            {"exit",{{10,12},{10,10},{12,8},{14,6.3},{16,6},{30,6}},"door",""}}, {}};
    input.motionMode=MappedMotionMode::CorridorFollowing;
    input.portalGateRadiusM=2;
    // Requests use intentionally reversed opaque names: admission order must
    // depend on arrival time, and shared through batches must stay finite.
    for (int i=0;i<24;++i) {
        const auto token="through-"+std::to_string(100-i);
        input.people.push_back({"private-through-"+std::to_string(i),"Adult Pedestrian",
            1.1+(i%3)*.2,{{token,"through",i*500}},i%2 ? .45 : .35});
    }
    for (int i=0;i<4;++i)
        input.people.push_back({"private-exit-"+std::to_string(i),"Pedestrian With Stroller",
            1.2,{{"exit-"+std::to_string(100-i),"exit",i*4000}},.45});
    MappedScene scene(input);
    AggregationTime firstExitCrossing=-1, lateThroughCrossing=-1;
    for (int time=0;time<=150000;time+=50) {
        scene.advanceTo(time);
        for (const auto& track:scene.frameAt(time)) {
            if (track.position.x>=16.5 && track.trackId=="exit-100" && firstExitCrossing<0)
                firstExitCrossing=time;
            if (track.position.x>=16.5 && track.trackId=="through-77" && lateThroughCrossing<0)
                lateThroughCrossing=time;
        }
    }
    const auto diagnostic=scene.motionDiagnostics();
    require(diagnostic.realizedStarts==28 && diagnostic.realizedEnds==28
        && diagnostic.activeTracks==0 && diagnostic.pendingTracks==0
        && diagnostic.overlapViolations==0 && diagnostic.mergeAdmissionWaitSteps>0,
        "Bounded building/through merge did not safely drain every scheduled track");
    require(firstExitCrossing>=0 && lateThroughCrossing>firstExitCrossing,
        "A stream of later through requests starved an earlier building exit");
    std::map<std::string,int> starts,ends;
    for (const auto& event:scene.events()) {
        if (event.kind==MappedEventKind::EpisodeStart) ++starts[event.trackId];
        else ++ends[event.trackId];
    }
    for (const auto& person:input.people) for (const auto& episode:person.episodes)
        require(starts[episode.trackId]==1 && ends[episode.trackId]==1,
            "Merge completion dropped, teleported or duplicated a scheduled lifecycle");
    // Caller cadence must not change reservations or realized lifecycle times.
    MappedScene coarse(input);coarse.advanceTo(150000);
    require(coarse.events().size()==scene.events().size(),"Coarse caller step lost a merge lifecycle");
    for (std::size_t i=0;i<scene.events().size();++i)
        require(scene.events()[i].trackId==coarse.events()[i].trackId
            && scene.events()[i].atMs==coarse.events()[i].atMs,
            "Merge reservations depend on caller cadence");
}


void fastSweptMergeCrossingReleasesReservation() {
    MappedSceneConfig input{1000,16,
        {{"through",{{0,6},{1000,6}},"",""},
            {"exit",{{14,10},{14,8},{14,6.3},{16,6},{1000,6}},"door",""}},
        {{"private-fast","Adult Pedestrian",400,{{"a-exit","exit",0}}},
            {"private-through","Adult Pedestrian",10,{{"z-through","through",0}}}}};
    input.motionMode=MappedMotionMode::CorridorFollowing;input.portalGateRadiusM=1;
    MappedScene scene(input);scene.advanceTo(2000);
    const auto frame=scene.frameAt(2000);
    const auto through=std::find_if(frame.begin(),frame.end(),[](const auto& t){return t.trackId=="z-through";});
    require(through!=frame.end() && through->position.x>15,
        "A body crossing the whole merge resource in one substep retained stale ownership");
    require(scene.motionDiagnostics().overlapViolations==0,"Fast swept merge crossed another physical body");
}


MappedSceneConfig explicitVisitingScene() {
    MappedSceneConfig input{12,10,
        {{"precise-in",{{0,5},{6,5}},"","precise-door"},
            {"precise-out",{{6,5},{6.8,3.8},{12,3.8}},"precise-door",""}},
        {{"precise-person","Adult Pedestrian",1,
            {{"precise-first","precise-in",0},{"precise-return","precise-out",0,2000}},.25}}};
    input.motionMode=MappedMotionMode::CorridorFollowing;
    input.portals={{"precise-door","building-a",{6,5},{4,5},{8,5},1.2,"synthetic"}};
    return input;
}

void preciseDoorArrivalAndRealizedReentry() {
    const auto input=explicitVisitingScene();
    MappedScene scene(input);
    scene.advanceTo(3500);
    const auto approaching=scene.frameAt(3500);
    require(approaching.size()==1 && near(approaching[0].position.x,3.5),
        "Entering a historical 3m approach disk must not swallow a visible visitor");
    scene.advanceTo(5950);
    require(scene.frameAt(5950).size()==1 && near(scene.frameAt(5950)[0].position.x,5.95),
        "A precise entry must remain visible up to the quantized route endpoint");
    scene.advanceTo(6000);
    require(scene.frameAt(6000).empty() && scene.episodeEndMs("precise-first")==6000,
        "A precise entry must end exactly when its facade point is reached");
    scene.advanceTo(7950);
    require(scene.frameAt(7950).empty(),"Hidden dwell ended before realized arrival plus its minimum gap");
    scene.advanceTo(8000);
    const auto returning=scene.frameAt(8000);
    require(returning.size()==1 && returning[0].trackId=="precise-return"
        && near(returning[0].position.x,6) && near(returning[0].position.y,5),
        "A return must begin at the precise same-building door with a new visible token");
    scene.advanceTo(20000);
    require(scene.motionDiagnostics().realizedEnds==2 && scene.motionDiagnostics().overlapViolations==0,
        "Precise visit source failed to drain");
    MappedScene coarse(input);coarse.advanceTo(20000);
    require(coarse.events().size()==scene.events().size(),"Coarse precise motion lost lifecycle events");
    for (std::size_t i=0;i<scene.events().size();++i)
        require(scene.events()[i].trackId==coarse.events()[i].trackId
            && scene.events()[i].atMs==coarse.events()[i].atMs,
            "Caller cadence changed a precise entrance lifecycle");
}

void independentDoorsAndUnrelatedPassers() {
    MappedSceneConfig input{12,10,
        {{"first-exit",{{5,5},{5,0}},"first-door",""},
            {"second-exit",{{6.5,5},{6.5,0}},"second-door",""},
            {"passing-route",{{0,5.8},{12,5.8}},"",""}},
        {{"first-person","Adult Pedestrian",1,{{"first-visible","first-exit",0}}},
            {"second-person","Adult Pedestrian",1,{{"second-visible","second-exit",0}}},
            {"passing-person","Adult Pedestrian",1,{{"passing-visible","passing-route",0}}}}};
    input.motionMode=MappedMotionMode::CorridorFollowing;
    input.portals={{"first-door","first-building",{5,5},{4.2,5},{5.8,5},1,"osm"},
        {"second-door","second-building",{6.5,5},{5.8,5},{7.2,5},1,"synthetic"}};
    MappedScene scene(input);
    require(scene.frameAt(0).size()==3 && scene.motionDiagnostics().admissionWaitSteps==0,
        "Independent nearby doors were serialized by the historical broad entrance disk");
    scene.advanceTo(6000);
    require(scene.frameAt(6000).size()==1 && scene.frameAt(6000)[0].trackId=="passing-visible"
        && near(scene.frameAt(6000)[0].position.x,6),
        "An unrelated passer was captured by an entrance or its broad admission zone");
    scene.advanceTo(15000);
    require(scene.motionDiagnostics().realizedEnds==3 && scene.motionDiagnostics().overlapViolations==0,
        "Nearby independent doors failed to drain safely");
}

void splitDoorThroatPreventsOpposingContactDeadlock() {
    MappedSceneConfig input{20,12,
        {{"split-in",{{0,8.5},{9.2,8.5},{10,10}},"","split-door"},
            {"split-out",{{10,10},{10.8,8.5},{20,8.5}},"split-door",""}},
        {{"arriving-person","Pedestrian With Stroller",1,{{"arriving-track","split-in",0}},.45},
            {"departing-person","Pedestrian With Stroller",1,{{"departing-track","split-out",9700}},.45}}};
    input.motionMode=MappedMotionMode::CorridorFollowing;
    input.portals={{"split-door","split-building",{10,10},{8,10},{12,10},1.2,"synthetic"}};
    MappedScene scene(input);scene.advanceTo(40000);
    const auto d=scene.motionDiagnostics();
    require(d.realizedStarts==2 && d.realizedEnds==2 && d.activeTracks==0
        && d.pendingTracks==0 && d.overlapViolations==0
        && (d.blockedMotionSteps>0 || d.admissionWaitSteps>0),
        "Opposing split door approaches stalled at body contact or overlapped instead of safely draining");
}

void invalidExplicitDoors() {
    const auto bad=[](const std::function<void(MappedSceneConfig&)>& mutate) {
        auto input=explicitVisitingScene();mutate(input);rejects([&]{MappedScene scene(input);});
    };
    bad([](auto& c){c.portals.push_back(c.portals.front());});
    bad([](auto& c){c.portals[0].buildingId="  ";});
    bad([](auto& c){c.portals[0].id=c.routes[0].id;});
    bad([](auto& c){c.portals[0].point={6,5.001};});
    bad([](auto& c){c.portals[0].point={-1,5};});
    bad([](auto& c){c.portals[0].facadeStart=c.portals[0].facadeEnd;});
    bad([](auto& c){c.portals[0].facadeStart.x=std::numeric_limits<double>::infinity();});
    bad([](auto& c){c.portals[0].widthM=0;});
    bad([](auto& c){c.portals[0].widthM=5;});
    bad([](auto& c){c.portals[0].widthM=.4;});
    bad([](auto& c){c.portals[0].point={4.2,5};c.routes[0].points.back()={4.2,5};c.routes[1].points.front()={4.2,5};});
    bad([](auto& c){c.portals[0].provenance="assumed-osm";});
    bad([](auto& c){c.routes[0].points.back().x+=.001;});
    bad([](auto& c){c.routes[0].endPortal="undeclared-door";});
    bad([](auto& c){c.routes[1].startPortal="";c.routes[1].points.front()={0,5};});
    bad([](auto& c){c.portals.push_back({"other-door","different-building",{8,5},{7,5},{9,5},1,"osm"});
        c.routes[1].startPortal="other-door";c.routes[1].points.front()={8,5};});
    auto allowed=explicitVisitingScene();
    allowed.portals.push_back({"other-door","building-a",{8,5},{7,5},{9,5},1,"osm"});
    allowed.routes[1].startPortal="other-door";allowed.routes[1].points.front()={8,5};
    MappedScene sameBuildingDifferentDoor(allowed);
    sameBuildingDifferentDoor.advanceTo(8000);
    require(near(sameBuildingDifferentDoor.frameAt(8000)[0].position.x,8),
        "A building visit should be allowed to exit through another declared door of the same building");
}

void opposedSingleLaneStopsSafelyWithoutClaimingCompletion() {
    MappedSceneConfig input{10,10,
        {{"east",{{0,5},{10,5}},"",""},{"west",{{10,5},{0,5}},"",""}},
        {{"a-person","Adult Pedestrian",1,{{"a-track","east",0}}},
            {"b-person","Adult Pedestrian",1,{{"b-track","west",0}}}}};
    input.motionMode=MappedMotionMode::CorridorFollowing;
    MappedScene scene(input);
    scene.advanceTo(20000);
    const auto diagnostic=scene.motionDiagnostics();
    require(diagnostic.overlapViolations==0 && diagnostic.activeTracks==2
        && diagnostic.activeStalledTracks==2 && diagnostic.maxConsecutiveStopMs>=10000,
        "Conservative head-on stall was hidden or allowed overlap");
    for (const auto& track:scene.frameAt(20000))
        require(track.velocity.x==0 && track.velocity.y==0,"A stopped track was overwritten by preferred velocity");
}

MappedSceneConfig localScene(double width=20,double height=12) {
    MappedSceneConfig config;config.width=width;config.height=height;
    config.motionMode=MappedMotionMode::LocalNavigation;
    config.navigation.allowedCenterPolygons={{{{0,0},{width,0},{width,height},{0,height}}, {}}};
    return config;
}

// Separate permissions must survive guide shortcuts, steering and replanning.
void localSurfaceAccessIsTypedAndOnlyTerminatesOwningTrips() {
    auto input=localScene(20,14);input.clearanceM=.05;input.navigation.doorMaxBatchSize=6;
    MappedPortal surface;surface.id="station-A";surface.point={10,10};surface.widthM=1.2;
    surface.provenance="osm";surface.kind=MappedPortalKind::SurfaceAccess;
    surface.surfaceApproach=Point{10,8.5};surface.admissionSegment={{9.4,10},{10.6,10}};
    input.portals.push_back(surface);
    input.routes={{"surface-in",{{0,8.5},{10,8.5},{10,10}},"","station-A"},
        {"surface-out",{{10,10},{10,8.5},{20,7}},"station-A",""},
        {"surface-passer",{{0,10.7},{20,10.7}},"",""}};
    input.people={{"private-in","Adult Pedestrian",1.3,{{"surface-visible-in","surface-in",0}},.25},
        {"private-out","Adult Pedestrian",1.3,{{"surface-visible-out","surface-out",3000}},.25},
        {"private-passer","Adult Pedestrian",1.3,{{"surface-visible-passer","surface-passer",0}},.25}};
    MappedScene scene(input);bool passerNearSurface=false;
    for(int now=0;now<=60000;now+=50) {
        scene.advanceTo(now);
        for(const auto& track:scene.frameAt(now)) {
            require(std::hypot(track.velocity.x,track.velocity.y)<=1.3+1e-8,"Surface access exceeded preferred speed");
            if(track.trackId=="surface-visible-passer" && std::hypot(track.position.x-10,track.position.y-10)<1)
                passerNearSurface=true;
        }
    }
    const auto d=scene.motionDiagnostics();
    require(passerNearSurface && d.realizedStarts==3 && d.realizedEnds==3 && d.activeTracks==0
        && d.pendingTracks==0 && d.overlapViolations==0,"Typed surface access failed finite source drainage");
    for(const auto& event:scene.events()) if(event.kind==MappedEventKind::EpisodeEnd && event.trackId=="surface-visible-passer")
        require(event.portalId.empty(),"Incidental passage through surface access caused hidden disappearance");
    const auto bad=[&](auto mutate) {auto c=input;mutate(c);rejects([&]{MappedScene scene(c);});};
    bad([](auto& c){c.portals[0].buildingId="fake-building";});
    bad([](auto& c){c.portals[0].surfaceApproach.reset();});
    bad([](auto& c){c.portals[0].admissionSegment.resize(1);});
    bad([](auto& c){c.portals[0].admissionSegment[1]={9.4,10};});
    bad([](auto& c){c.portals[0].surfaceApproach=Point{11,8.5};});
    bad([](auto& c){c.portals[0].widthM=1.3;});
    bad([](auto& c){c.navigation.allowedCenterPolygons[0].holes.push_back({{9.9,9.9},{10.1,9.9},{10.1,10.1},{9.9,10.1}});});
    bad([](auto& c){c.motionMode=MappedMotionMode::CorridorFollowing;});
}

MappedSceneConfig crossingPriorityFixture() {
    auto c=localScene(30,20);c.clearanceM=.05;
    c.navigation.spaces.push_back({"rider",{{{{0,7},{30,7},{30,13},{0,13}}, {}}},.55});
    MappedNavigationCrossing crossing;crossing.id="explicit-crossing";
    crossing.conflictRing={{12,7},{18,7},{18,13},{12,13}};crossing.prioritySpaces={"rider"};
    c.navigation.crossings.push_back(crossing);
    c.routes={{"ped-cross",{{15,0},{15,20}},"",""},
        {"rider-through",{{0,10},{30,10}},"","","rider",{{30,7},{30,13}}}};
    c.people={{"private-ped","Adult Pedestrian",1.3,{{"ped-visible","ped-cross",0}},.25},
        {"private-rider","Adult Cyclist",3,{{"rider-visible","rider-through",0}},.45}};
    return c;
}
void localCrossingPriorityYieldsBeforeEntryAndKeepsPhysicalChecks() {
    auto input=crossingPriorityFixture();MappedScene scene(input);
    std::map<std::string,Point> previous;bool pedestrianWaited=false;
    for(int now=0;now<=40000;now+=50) {
        scene.advanceTo(now);const auto frame=scene.frameAt(now);
        for(const auto& track:frame) {
            const double maxSpeed=track.trackId=="ped-visible"?1.3:3;
            require(std::hypot(track.velocity.x,track.velocity.y)<=maxSpeed+1e-8,"Priority exceeded preferred speed");
            if(previous.count(track.trackId)) require(std::hypot(track.position.x-previous[track.trackId].x,
                track.position.y-previous[track.trackId].y)<=maxSpeed*.05+1e-8,"Priority teleported a road user");
            previous[track.trackId]=track.position;
            if(track.trackId=="ped-visible" && now>4000 && std::hypot(track.velocity.x,track.velocity.y)<1e-8) {
                pedestrianWaited=true;require(track.position.y<=6.7+1e-7,"Pedestrian waited inside the carriageway");
            }
        }
        if(frame.size()==2) require(std::hypot(frame[0].position.x-frame[1].position.x,
            frame[0].position.y-frame[1].position.y)>=.75-1e-7,"Priority bypassed circular-body clearance");
    }
    const auto d=scene.motionDiagnostics();
    require(pedestrianWaited && d.crossingPedestrianWaitSteps>0 && d.realizedEnds==2 && d.overlapViolations==0
        && scene.episodeEndMs("rider-visible")==10000,"Pedestrian priority wait blocked uncongested rider throughput");
    MappedScene coarse(input);coarse.advanceTo(40000);
    require(coarse.events().size()==scene.events().size(),"Crossing caller cadence changed lifecycle");
    for(std::size_t i=0;i<scene.events().size();++i)
        require(coarse.events()[i].trackId==scene.events()[i].trackId && coarse.events()[i].atMs==scene.events()[i].atMs,
            "Crossing priority is not deterministic across call cadence");
    // Once a pedestrian is already crossing, a newly arriving rider must wait.
    auto pedestrianOnly=input;pedestrianOnly.people.resize(1);MappedScene reference(pedestrianOnly);
    AggregationTime riderArrival=-1;
    for(AggregationTime now=0;now<=20000 && riderArrival<0;now+=50) {
        reference.advanceTo(now);
        for(const auto& track:reference.frameAt(now)) if(track.position.y>=7.2) riderArrival=now;
    }
    require(riderArrival>=0,"Pedestrian reference never entered the crossing");
    input.people[1].episodes[0].startMs=riderArrival;MappedScene alreadyCrossing(input);
    alreadyCrossing.advanceTo(40000);
    const auto crossing=alreadyCrossing.motionDiagnostics();
    require(crossing.realizedEnds==2 && crossing.crossingRiderWaitSteps>0 && crossing.overlapViolations==0,
        "A newly arriving rider prevented an admitted pedestrian from clearing");
}
void localCrossingEmptyRoadDoesNotRequireImpossibleEntryStaging() {
    auto input=crossingPriorityFixture();input.height=14;
    input.navigation.allowedCenterPolygons=localScene(30,14).navigation.allowedCenterPolygons;
    input.navigation.crossings[0].conflictRing={{0,1},{30,1},{30,7},{0,7}};
    input.routes[0].points={{15,0},{15,14}};
    input.people.resize(1);
    MappedScene scene(input);scene.advanceTo(14000);
    const auto d=scene.motionDiagnostics();
    require(d.realizedEnds==1 && d.activeTracks==0 && d.pendingTracks==0 && d.overlapViolations==0,
        "Empty-road singleton deadlocked because its narrow entry sidewalk had no off-apron staging room");
}

void localCrossingPendingWaitIsMeasuredBeforeGrant() {
    MappedScene scene(crossingPriorityFixture());scene.advanceTo(5500);
    const auto waiting=scene.motionDiagnostics();
    require(waiting.crossingPedestrianWaitSteps>0 && waiting.crossingBatches==0
        && waiting.maxCrossingPedestrianWaitMs>0,
        "An outstanding crossing request was invisible until a later grant");
    scene.advanceTo(40000);const auto drained=scene.motionDiagnostics();
    require(drained.realizedEnds==2 && drained.activeTracks==0 && drained.overlapViolations==0,
        "Measuring pending crossing waits changed safe completion");
}

void localCrossingProjectedBoundaryIntentDrainsTangentialBodies() {
    auto input=crossingPriorityFixture();input.people.resize(1);
    input.routes[0]={"projected-ped",{{0,6.7001},{30,0}},"","","",{{30,0},{30,6.7001}}};
    input.people[0].episodes[0].routeId="projected-ped";
    input.navigation.crossings[0].maxBatchSize=1;
    const auto check=[&](const MappedSceneConfig& config) {
        MappedScene scene(config);std::map<std::string,Point> previous;
        for(int now=0;now<=60000;now+=50) {
            scene.advanceTo(now);const auto frame=scene.frameAt(now);
            if(frame.size()==2 && previous.count(frame[0].trackId) && previous.count(frame[1].trackId)) {
                const auto a=previous.at(frame[0].trackId),b=previous.at(frame[1].trackId);
                const double rx=a.x-b.x,ry=a.y-b.y;
                const double vx=frame[0].position.x-a.x-frame[1].position.x+b.x;
                const double vy=frame[0].position.y-a.y-frame[1].position.y+b.y;
                const double squared=vx*vx+vy*vy;
                const double at=squared>1e-20?std::clamp(-(rx*vx+ry*vy)/squared,0.0,1.0):0;
                require(std::hypot(rx+at*vx,ry+at*vy)>=.55-1e-7,
                    "Projected crossing intent bypassed swept body clearance");
            }
            for(const auto& track:frame) {
                require(std::hypot(track.velocity.x,track.velocity.y)<=1.3+1e-8,
                    "Projected crossing intent exceeded preferred speed");
                if(previous.count(track.trackId)) require(std::hypot(track.position.x-previous[track.trackId].x,
                    track.position.y-previous[track.trackId].y)<=1.3*.05+1e-8,
                    "Projected crossing intent teleported a pedestrian");
                previous[track.trackId]=track.position;
            }
            if(frame.size()==2) require(std::hypot(frame[0].position.x-frame[1].position.x,
                frame[0].position.y-frame[1].position.y)>=.55-1e-7,
                "Projected crossing intent bypassed body clearance");
        }
        const auto d=scene.motionDiagnostics();
        require(d.realizedEnds==config.people.size() && d.activeTracks==0 && d.pendingTracks==0
            && d.overlapViolations==0 && d.crossingBatches>0,
            "Terminal boundary projection caused a tangential crossing request to be discarded forever");
        MappedScene coarse(config);coarse.advanceTo(60000);
        require(coarse.events().size()==scene.events().size(),"Projected crossing cadence changed lifecycle");
        for(std::size_t i=0;i<scene.events().size();++i)
            require(coarse.events()[i].trackId==scene.events()[i].trackId
                && coarse.events()[i].atMs==scene.events()[i].atMs,
                "Projected crossing intent is not deterministic across caller cadence");
    };
    check(input);
    // An opposite crosser's receiving apron contains the tangent wait position.
    // Its body must stay authoritative until the projected-boundary walker clears.
    input.routes.push_back({"opposite-projected",{{12.1,20},{12.1,0}},"",""});
    input.people.push_back({"opposite-projected-private","Adult Pedestrian",1.3,
        {{"opposite-projected-visible","opposite-projected",5000}},.25});
    check(input);
}

void localCrossingOppositeReceivingApronsRemainClear() {
    auto input=crossingPriorityFixture();input.navigation.crossings[0].maxBatchSize=1;
    input.routes.push_back({"opposite-ped-cross",{{15,20},{15,0}},"",""});
    input.people.push_back({"opposite-private","Adult Pedestrian",1.3,
        {{"opposite-visible","opposite-ped-cross",800}},.25});
    input.people.push_back({"later-rider-private","Adult Cyclist",3,
        {{"later-rider-visible","rider-through",6000}},.45});
    MappedScene scene(input);bool observedClearReceivingApron=false;
    const auto distance=[](Point p) {
        const double dx=std::max({12-p.x,0.0,p.x-18});
        const double dy=std::max({7-p.y,0.0,p.y-13});return std::hypot(dx,dy);
    };
    for(int now=0;now<=60000;now+=50) {
        scene.advanceTo(now);const auto frame=scene.frameAt(now);
        for(const auto& crosser:frame) if((crosser.trackId=="ped-visible" || crosser.trackId=="opposite-visible")
                && distance(crosser.position)<.3) {
            for(const auto& other:frame) if(other.trackId!=crosser.trackId
                    && (other.trackId=="ped-visible" || other.trackId=="opposite-visible")) {
                require(distance(other.position)>=1.55-1e-7,
                    "An ungranted opposite pedestrian occupied the receiving apron");
                observedClearReceivingApron=true;
            }
        }
    }
    const auto d=scene.motionDiagnostics();
    require(observedClearReceivingApron && d.realizedEnds==4 && d.activeTracks==0
        && d.pendingTracks==0 && d.overlapViolations==0,"Opposite-apron staging did not drain pedestrians and riders");
}

void localCrossingPriorityFiniteFairnessAndValidation() {
    auto input=crossingPriorityFixture();input.navigation.crossings[0].pedestrianMaxWaitMs=1000;
    for(int index=1;index<12;++index) input.people.push_back({"private-rider-"+std::to_string(index),"Adult Cyclist",3,
        {{"rider-visible-"+std::to_string(index),"rider-through",index*900}},.45});
    MappedScene scene(input);scene.advanceTo(60000);const auto d=scene.motionDiagnostics();
    require(d.realizedEnds==input.people.size() && d.activeTracks==0 && d.pendingTracks==0
        && d.overlapViolations==0 && d.crossingFairnessClosures==1 && d.crossingRiderWaitSteps>0
        && d.maxCrossingPedestrianWaitMs<=5000,"Finite rider stream starved pedestrians or failed to drain");
    const auto bad=[&](auto mutate) {auto c=input;mutate(c);rejects([&]{MappedScene scene(c);});};
    bad([](auto& c){c.navigation.crossings[0].prioritySpaces={"missing"};});
    bad([](auto& c){c.navigation.crossings[0].prioritySpaces={"rider","rider"};});
    bad([](auto& c){c.navigation.crossings[0].pedestrianMaxWaitMs=0;});
    bad([](auto& c){c.navigation.crossings[0].maxBatchSize=0;});
    bad([](auto& c){c.navigation.crossings[0].conflictRing={{1,1},{2,2}};});
    bad([](auto& c){c.navigation.crossings.push_back(c.navigation.crossings[0]);});
    bad([](auto& c){auto near=c.navigation.crossings[0];near.id="too-close";for(auto& p:near.conflictRing)p.x+=6.5;c.navigation.crossings.push_back(near);});
    bad([](auto& c){for(auto& p:c.people)p.radiusM=.25;auto near=c.navigation.crossings[0];near.id="inflation-gap";for(auto& p:near.conflictRing)p.x+=6.575;c.navigation.crossings.push_back(near);});
    bad([](auto& c){c.routes[0].points.front()={15,10};});
    bad([](auto& c){c.navigation.crossings[0].conflictRing={{0,7},{18,7},{18,13},{0,13}};});
    auto plain=localScene();plain.routes={{"legacy-off",{{0,5},{20,5}},"",""}};
    plain.people={{"legacy-private","Adult Pedestrian",1.3,{{"legacy-visible","legacy-off",0}},.25}};
    MappedScene off(plain),empty(plain);
    for(int now=0;now<=20000;now+=50) {off.advanceTo(now);empty.advanceTo(now);sameFrame(off.frameAt(now),empty.frameAt(now));}
    require(off.motionDiagnostics().crossingBatches==0,"Disabled priority changed legacy diagnostics");
}

void localBoundaryIntervalsAvoidPointSinkConvergence() {
    auto input=localScene(20,12);
    input.routes={{"exit-upper",{{0,2},{18,2},{20,5}},"","","",{{20,1},{20,10}}},
        {"exit-lower",{{0,8},{18,8},{20,5}},"","","",{{20,1},{20,10}}}};
    input.people={{"upper","Adult Cyclist",3.5,{{"upper-visible","exit-upper",0}},.45},
        {"lower","Adult Cyclist",3.5,{{"lower-visible","exit-lower",0}},.45}};
    MappedScene scene(input);
    for(int time=0;time<=10000;time+=50) scene.advanceTo(time);
    require(scene.motionDiagnostics().realizedEnds==2 && scene.motionDiagnostics().overlapViolations==0,
        "Interval sinks did not drain separated bodies");
    std::map<std::string,Point> exits;
    for(const auto& event:scene.events()) if(event.kind==MappedEventKind::EpisodeEnd) {
        require(event.position.has_value(),"Interval exit omitted actual terminal position");
        require(std::abs(event.position->x-20)<1e-7 && event.position->y>=1 && event.position->y<=10,
            "Interval exit left its permitted domain-edge segment");
        exits[event.trackId]=*event.position;
    }
    require(std::abs(exits.at("upper-visible").y-exits.at("lower-visible").y)>4,
        "Boundary intervals collapsed back to an artificial common point sink");
    const auto bad=[&](auto change) {auto invalid=input;change(invalid);bool rejected=false;
        try {MappedScene checked(invalid);} catch(const std::invalid_argument&) {rejected=true;}
        require(rejected,"Invalid boundary sink accepted");};
    bad([](auto& c){c.routes[0].endBoundary={{20,1}};});
    bad([](auto& c){c.routes[0].endBoundary={{20,1},{20,1}};});
    bad([](auto& c){c.routes[0].endBoundary={{20,1},{19,10}};});
    bad([](auto& c){c.routes[0].endBoundary={{20,1},{20,3}};});
    bad([](auto& c){c.routes[0].endBoundary={{20,-1},{20,10}};});
    bad([](auto& c){c.motionMode=MappedMotionMode::CorridorFollowing;});
}

void localMovementSpacesStaySeparate() {
    auto input=localScene(20,12);
    input.navigation.allowedCenterPolygons={{{{0,0},{20,0},{20,4},{0,4}}, {}}};
    input.navigation.spaces={{"road",{{{{0,7},{20,7},{20,12},{0,12}}, {}}},1.1}};
    input.routes={{"walk",{{0,2},{20,2}},"",""},
        {"ride",{{20,9},{0,9}},"","","road"}};
    input.people={{"walking-person","Adult Pedestrian",1.3,{{"walk-track","walk",0}}},
        {"riding-person","Adult Cyclist",3.5,{{"ride-track","ride",0}},1.0}};
    MappedScene scene(input);
    for (int time=0;time<=20000;time+=50) {
        scene.advanceTo(time);
        for (const auto& track:scene.frameAt(time)) {
            if (track.trackId=="walk-track") require(track.position.y<=4,"Pedestrian left walking permission");
            else require(track.position.y>=7,"Rider left carriageway permission");
        }
    }
    require(scene.motionDiagnostics().realizedEnds==2 && scene.motionDiagnostics().overlapViolations==0,
        "Separated walking/riding routes did not drain safely");
    const auto rejects=[&](auto change) {auto bad=input;change(bad);bool rejected=false;
        try {MappedScene invalid(bad);} catch(const std::invalid_argument&) {rejected=true;}
        require(rejected,"Invalid movement-space configuration accepted");};
    rejects([](auto& c){c.routes[1].navigationSpace="missing";});
    rejects([](auto& c){c.routes[1].navigationSpace.clear();});
    rejects([](auto& c){c.navigation.spaces[0].centerClearanceM=1.0;});
    rejects([](auto& c){c.navigation.spaces.push_back(c.navigation.spaces[0]);});
    rejects([](auto& c){c.navigation.spaces[0].allowedCenterPolygons.clear();});
    rejects([](auto& c){c.navigation.spaces[0].centerClearanceM=std::numeric_limits<double>::quiet_NaN();});
    rejects([](auto& c){c.navigation.spaces[0].allowedCenterPolygons[0].outer[0].x=-1;});
    rejects([](auto& c){c.motionMode=MappedMotionMode::CorridorFollowing;});
}

void localBoundarySinkRetainsGoalAroundConcaveObstacle() {
    auto input=localScene(20,14);
    input.navigation.allowedCenterPolygons[0].outer={{0,0},{14,0},{14,4},{16,4},{16,0},{20,0},{20,14},{0,14}};
    // The original diagonal guide is visible, while the nearest boundary point
    // is hidden behind the obstacle and requires a real navigation detour.
    input.routes={{"concave-sink",{{0,.5},{20,13}},"","","",{{20,0},{20,14}}}};
    input.people={{"concave-private","Adult Pedestrian",1.3,{{"concave-visible","concave-sink",0}}}};
    MappedScene scene(input);
    for (int time=0;time<=60000;time+=50) {
        scene.advanceTo(time);
        for (const auto& track:scene.frameAt(time)) {
            require(!(track.position.x>14 && track.position.x<16 && track.position.y>=0 && track.position.y<4),
                "Boundary detour entered the static obstacle");
            require(std::hypot(track.velocity.x,track.velocity.y)<=1.3+1e-8,
                "Boundary detour exceeded configured preferred speed");
        }
    }
    const auto diagnostics=scene.motionDiagnostics();
    require(diagnostics.realizedEnds==1 && diagnostics.activeTracks==0 && diagnostics.overlapViolations==0,
        "Stable boundary sink target failed to drain around a concave obstacle");
    require(diagnostics.navigationReplans>diagnostics.navigationReplanFailures,
        "Concave boundary regression did not exercise a successful A* detour");
    require(scene.events().back().position && near(scene.events().back().position->x,20),
        "Boundary detour did not record its actual permitted interval exit");
}

void localVisibleBoundaryOutflowsKeepSeparateExitPoints() {
    auto input=localScene(20,14);
    input.routes={{"outflow-a",{{0,6},{20,5}},"","","",{{20,0},{20,14}}},
        {"outflow-b",{{0,8},{20,5}},"","","",{{20,0},{20,14}}}};
    input.people={{"outflow-private-a","Adult Pedestrian",1.3,{{"outflow-visible-a","outflow-a",0}}},
        {"outflow-private-b","Adult Pedestrian",1.3,{{"outflow-visible-b","outflow-b",0}}}};
    MappedScene scene(input);scene.advanceTo(30000);
    std::vector<double> exitY;
    for (const auto& event:scene.events()) if (event.kind==MappedEventKind::EpisodeEnd) {
        require(event.position && near(event.position->x,20),"Visible boundary outflow omitted its actual exit");
        exitY.push_back(event.position->y);
    }
    std::sort(exitY.begin(),exitY.end());
    require(exitY.size()==2 && near(exitY[0],6) && near(exitY[1],8)
        && scene.motionDiagnostics().overlapViolations==0,
        "Visible interval outflows collapsed onto the shared nominal route endpoint");
}

void localOpposingTrafficSteersAndDrains() {
    auto input=localScene();
    input.routes={{"east-nav",{{0,6},{20,6}},"",""},{"west-nav",{{20,6},{0,6}},"",""}};
    input.people={{"east-private","Adult Pedestrian",1.3,{{"east-visible","east-nav",0}}},
        {"west-private","Adult Pedestrian",1.3,{{"west-visible","west-nav",0}}}};
    MappedScene scene(input);
    bool lateral=false;std::map<std::string,Point> previous;
    for(int time=0;time<=40000;time+=50) {
        scene.advanceTo(time);const auto frame=scene.frameAt(time);
        for(const auto& track:frame) {
            lateral|=std::abs(track.position.y-6)>.2;
            require(std::hypot(track.velocity.x,track.velocity.y)<=1.3+1e-8,"Local steering exceeded preferred speed");
            if(previous.count(track.trackId)) {
                const auto before=previous.at(track.trackId);
                require(std::abs(track.velocity.x-(track.position.x-before.x)/.05)<1e-8
                    && std::abs(track.velocity.y-(track.position.y-before.y)/.05)<1e-8,
                    "Local steering velocity was projected onto the original route");
            }
        }
        previous.clear();for(const auto& track:frame) previous[track.trackId]=track.position;
    }
    const auto d=scene.motionDiagnostics();
    require(lateral && d.navigationSteeringSteps>0 && d.realizedEnds==2
        && d.activeTracks==0 && d.overlapViolations==0,
        "Opposing local traffic did not pass laterally and finish safely");
    auto renamed=input;std::reverse(renamed.people.begin(),renamed.people.end());
    renamed.people[0].personId="hidden-rename-1";renamed.people[1].personId="hidden-rename-2";
    MappedScene other(renamed);other.advanceTo(40000);
    require(other.events().size()==scene.events().size(),"Private renaming changed local lifecycle count");
    for(std::size_t i=0;i<scene.events().size();++i)
        require(scene.events()[i].trackId==other.events()[i].trackId
            && scene.events()[i].atMs==other.events()[i].atMs,
            "Private identity/order or caller cadence changed local navigation");
}

void localCrossingFlowsAndStaticHole() {
    auto input=localScene();
    input.routes={{"cross-east",{{0,6},{20,6}},"",""},
        {"cross-west",{{20,6},{0,6}},"",""},
        {"cross-south",{{10,0},{10,12}},"",""},
        {"cross-north",{{10,12},{10,0}},"",""}};
    for(std::size_t i=0;i<input.routes.size();++i)
        input.people.push_back({"private-cross-"+std::to_string(i),"Adult Pedestrian",1.2,
            {{"visible-cross-"+std::to_string(i),input.routes[i].id,0}}});
    MappedScene crossing(input);crossing.advanceTo(45000);
    require(crossing.motionDiagnostics().realizedEnds==4
        && crossing.motionDiagnostics().overlapViolations==0,"Intersecting local flows failed to drain safely");
    auto hole=localScene();
    hole.navigation.allowedCenterPolygons[0].holes={{{8,4},{12,4},{12,8},{8,8}}};
    hole.routes={{"around-wall",{{0,6},{7,3},{13,3},{20,6}},"",""}};
    hole.people={{"hole-private","Adult Pedestrian",1.4,{{"hole-visible","around-wall",0}}}};
    MappedScene avoiding(hole);
    for(int time=0;time<=40000;time+=50) {
        avoiding.advanceTo(time);
        for(const auto& track:avoiding.frameAt(time))
            require(!(track.position.x>8 && track.position.x<12 && track.position.y>4 && track.position.y<8),
                "Local center entered a static hole");
    }
    require(avoiding.motionDiagnostics().realizedEnds==1,"Static obstacle route failed to finish");
    auto thin=hole;thin.routes[0].points={{0,6},{20,6}};
    thin.navigation.allowedCenterPolygons[0].holes={{{9.999,1},{10.001,1},{10.001,11},{9.999,11}}};
    rejects([&]{MappedScene unsafe(thin);});
}

void localFiniteDenseSourceAndDoorVisits() {
    auto input=localScene(20,14);
    input.routes={{"walk-east",{{0,4},{20,4}},"",""},{"walk-west",{{20,8},{0,8}},"",""},
        {"shop-in",{{0,10},{10,10.5},{10,12}},"","shop-door"},
        {"shop-out",{{10,12},{10,10.5},{20,10}},"shop-door",""}};
    input.portals={{"shop-door","shop-building",{10,12},{8,12},{12,12},1.2,"synthetic"}};
    for(int i=0;i<16;++i)
        input.people.push_back({"dense-private-"+std::to_string(i),"Adult Pedestrian",1.1+(i%4)*.1,
            {{"dense-visible-"+std::to_string(i),i%2?"walk-east":"walk-west",i*250}}});
    input.people.push_back({"shop-private","Pedestrian With Stroller",1.2,
        {{"shop-arrival","shop-in",500},{"shop-return","shop-out",0,8000}},.45});
    MappedScene scene(input);scene.advanceTo(90000);
    const auto d=scene.motionDiagnostics();
    require(d.realizedStarts==18 && d.realizedEnds==18 && d.pendingTracks==0
        && d.activeTracks==0 && d.overlapViolations==0,"Finite local source and building visit failed to drain");
    AggregationTime arrival=-1,returned=-1;
    for(const auto& event:scene.events()) {
        if(event.trackId=="shop-arrival" && event.kind==MappedEventKind::EpisodeEnd) arrival=event.atMs;
        if(event.trackId=="shop-return" && event.kind==MappedEventKind::EpisodeStart) returned=event.atMs;
    }
    require(arrival>0 && returned-arrival>=8000,"Local building dwell was not based on realized arrival");
}

void localBoundedReplanningAndValidation() {
    auto input=localScene(10,10);
    input.navigation.allowedCenterPolygons={{{{0,4.99},{10,4.99},{10,5.01},{0,5.01}}, {}}};
    input.navigation.maxReplanNodes=5;input.navigation.replanAfterMs=100;input.navigation.replanIntervalMs=500;
    input.routes={{"narrow-east",{{0,5},{10,5}},"",""},{"narrow-west",{{10,5},{0,5}},"",""}};
    input.people={{"narrow-a-private","Adult Pedestrian",1,{{"narrow-a","narrow-east",0}}},
        {"narrow-b-private","Adult Pedestrian",1,{{"narrow-b","narrow-west",0}}}};
    MappedScene narrow(input);narrow.advanceTo(20000);
    const auto d=narrow.motionDiagnostics();
    require(d.overlapViolations==0 && d.activeTracks==2 && d.navigationReplans>0
        && d.navigationReplanFailures>0 && d.navigationMaxSearchNodes<=5,
        "A blocked local corridor hid its bounded failed searches or teleported through traffic");
    const auto bad=[&](const std::function<void(MappedSceneConfig&)>& mutate) {
        auto config=input;mutate(config);rejects([&]{MappedScene checked(config);});
    };
    bad([](auto& c){c.navigation.allowedCenterPolygons.clear();});
    bad([](auto& c){c.navigation.gridResolutionM=0;});
    bad([](auto& c){c.navigation.gridResolutionM=std::numeric_limits<double>::quiet_NaN();});
    bad([](auto& c){c.navigation.gridResolutionM=.0001;});
    bad([](auto& c){c.navigation.maxReplanNodes=0;});
    bad([](auto& c){c.navigation.replanAfterMs=0;});
    bad([](auto& c){c.navigation.allowedCenterPolygons[0].outer={{0,0},{10,10},{0,10},{10,0}};});
    bad([](auto& c){c.navigation.allowedCenterPolygons[0].holes={{{1,1},{2,1},{2,2},{1,2}}};});
    auto visit=explicitVisitingScene();visit.motionMode=MappedMotionMode::LocalNavigation;
    visit.navigation=localScene(visit.width,visit.height).navigation;
    visit.portals.push_back({"different-door","building-a",{8,5},{7,5},{9,5},1,"synthetic"});
    visit.routes[1].startPortal="different-door";visit.routes[1].points.front()={8,5};
    rejects([&]{MappedScene wrongReturn(visit);});
}


void localDoorArrivalDoesNotBacktrackToPassedMouth() {
    auto input=localScene(20,14);input.clearanceM=.05;input.navigation.doorMaxBatchSize=6;
    input.routes={{"side-arrival",{{0,11.99},{10,10.5},{10,12}},"","side-door"}};
    input.portals={{"side-door","side-building",{10,12},{8,12},{12,12},1.2,"synthetic"}};
    input.people={{"side-private","Adult Pedestrian",1.3,{{"side-visible","side-arrival",0}},.25}};
    MappedScene scene(input);bool progressedInsideThroat=false;
    for (int time=0;time<=20000;time+=50) {
        scene.advanceTo(time);
        for (const auto& track:scene.frameAt(time)) {
            // A lateral approach may already be beyond the mouth plane. Once
            // inside its body-width throat, the next step must target entry,
            // rather than insist on returning to the obsolete mouth waypoint.
            if (progressedInsideThroat) require(track.nextWaypointIndex==2,
                "Granted arrival returned to a passed mouth guide instead of entering");
            if (track.position.x>9.75 && track.position.y>10.5) progressedInsideThroat=true;
        }
    }
    require(progressedInsideThroat && scene.motionDiagnostics().realizedEnds==1,
        "Lateral arrival never advanced directly through its already-entered throat");
}

void localDoorPipelinesShareThroatAndDrainOpposingDemand() {
    const auto make=[](bool arrivals,bool exits) {
        auto input=localScene(20,14);
        input.clearanceM=.05;input.navigation.doorMaxBatchSize=6;
        input.routes={{"pipeline-in",{{0,10.5},{10,10.5},{10,12}},"","pipeline-door"},
            {"pipeline-out",{{10,12},{10,10.5},{20,7}},"pipeline-door",""}};
        input.portals={{"pipeline-door","pipeline-building",{10,12},{8,12},{12,12},1.2,"synthetic"}};
        if (arrivals) for (int i=0;i<6;++i)
            input.people.push_back({"pipeline-private-in-"+std::to_string(i),"Adult Pedestrian",1.3,
                {{"pipeline-visible-in-"+std::to_string(i),"pipeline-in",0}},.2});
        if (exits) for (int i=0;i<6;++i)
            input.people.push_back({"pipeline-private-out-"+std::to_string(i),"Adult Pedestrian",1.3,
                {{"pipeline-visible-out-"+std::to_string(i),"pipeline-out",arrivals?6500:0}},.2});
        return input;
    };
    for (const auto demand:{std::pair<bool,bool>{true,false},{false,true},{true,true}}) {
        const auto input=make(demand.first,demand.second);MappedScene scene(input);
        std::size_t peakThroat=0;
        for (int time=0;time<=90000;time+=50) {
            scene.advanceTo(time);const auto frame=scene.frameAt(time);
            std::size_t throat=0;
            for (const auto& track:frame) {
                if (std::abs(track.position.x-10)<=.3 && track.position.y>10.5 && track.position.y<=12) ++throat;
                require(std::hypot(track.velocity.x,track.velocity.y)<=1.3+1e-8,
                    "Door pipeline exceeded the configured preferred speed");
            }
            peakThroat=std::max(peakThroat,throat);
        }
        const auto diagnostics=scene.motionDiagnostics();
        require(peakThroat>=2,"Same-direction door pipeline serialized the complete throat");
        require(diagnostics.realizedEnds==input.people.size() && diagnostics.activeTracks==0
            && diagnostics.pendingTracks==0 && diagnostics.overlapViolations==0,
            "Finite incoming/outgoing door pipeline failed to drain safely");
        MappedScene coarse(input);coarse.advanceTo(90000);
        require(coarse.events().size()==scene.events().size(),"Door pipeline caller cadence changed lifecycle count");
        for (std::size_t i=0;i<scene.events().size();++i)
            require(coarse.events()[i].trackId==scene.events()[i].trackId
                && coarse.events()[i].atMs==scene.events()[i].atMs,
                "Door pipeline is not deterministic across caller cadence");
    }
    auto invalid=make(true,false);invalid.navigation.doorMaxBatchSize=0;
    rejects([&]{MappedScene scene(invalid);});
    invalid.navigation.doorMaxBatchSize=65;rejects([&]{MappedScene scene(invalid);});
}

void localVisibleGuidesDoNotCauseBacktrackingAfterDoorWaits() {
    auto simple=localScene(20,14);
    simple.routes={{"guide-route",{{0,7},{4,11},{6,3},{10,10},{14,4},{20,7}},"",""}};
    simple.people={{"guide-private","Adult Pedestrian",1,{{"guide-visible","guide-route",0}}}};
    MappedScene direct(simple);direct.advanceTo(21000);
    require(direct.motionDiagnostics().realizedEnds==1 && direct.episodeEndMs("guide-visible")==20000,
        "Visible guide points were treated as mandatory historical visits rather than topology hints");
    auto input=localScene(20,14);
    input.portals={{"queue-door","queue-building",{10,12},{8,12},{12,12},1.2,"synthetic"}};
    for(int i=0;i<8;++i) {
        const auto suffix=std::to_string(i);
        input.routes.push_back({"queue-in-"+suffix,
            {{0,3+i*.8},{4,4+i*.6},{8,9},{10,10.5},{10,12}},"","queue-door"});
        input.routes.push_back({"queue-out-"+suffix,
            {{10,12},{10,10.5},{15,8+i*.3},{20,7+i*.3}},"queue-door",""});
        input.people.push_back({"queue-private-"+suffix,"Adult Pedestrian",1.2,
            {{"queue-arrival-"+suffix,"queue-in-"+suffix,i*250},
                {"queue-return-"+suffix,"queue-out-"+suffix,0,8000}}});
    }
    MappedScene queued(input);queued.advanceTo(180000);
    const auto d=queued.motionDiagnostics();
    require(d.realizedEnds==16 && d.activeTracks==0 && d.pendingTracks==0
        && d.overlapViolations==0 && d.navigationSteeringSteps>0,
        "Doorway waiting followed by rejoining later visible guides failed to drain safely");
    AggregationTime last=0;
    for(const auto& event:queued.events()) if(event.kind==MappedEventKind::EpisodeEnd) last=std::max(last,event.atMs);
    require(last<120000,"Stale guide backtracking reintroduced excessive post-door detours");
    auto invalid=input;invalid.routes[0].points[invalid.routes[0].points.size()-2].x+=.1;
    rejects([&]{MappedScene obliqueEntry(invalid);});
    invalid=input;invalid.routes[1].points[1].x+=.1;
    rejects([&]{MappedScene obliqueExit(invalid);});
    invalid=input;invalid.routes[0].points[invalid.routes[0].points.size()-2]={10,11.8};
    rejects([&]{MappedScene insufficientThroat(invalid);});
    // Another shop's facade exception never belongs to an unrelated passer.
    invalid=localScene(20,14);invalid.portals=input.portals;
    invalid.routes={{"unrelated",{{0,12},{20,12}},"",""}};
    invalid.people={{"unrelated-private","Adult Pedestrian",1,{{"unrelated-visible","unrelated",0}}}};
    rejects([&]{MappedScene wrongFacadeException(invalid);});
}


MappedSceneConfig localNarrowPassageScene() {
    auto input=localScene(24,14);
    // These are center-safe chambers connected by a nonpassing neck. Physical
    // body clearance is still enforced by the native swept-motion checks.
    input.navigation.allowedCenterPolygons={{{{0,0},{9,0},{9,6.95},{15,6.95},
        {15,0},{24,0},{24,14},{15,14},{15,7.05},{9,7.05},{9,14},{0,14}}, {}}};
    input.navigation.narrowPassages={{"test-neck",{{8,7},{12,7},{16,7}},
        {{5,4},{5,10},{3,4},{3,10},{1.5,4},{1.5,10},{5,1.5},{5,12.5}},
        {{19,4},{19,10},{21,4},{21,10},{22.5,4},{22.5,10},{19,1.5},{19,12.5}},1.15,2}};
    input.routes={{"neck-east",{{0,7},{8,7},{12,7},{16,7},{24,7}},"",""},
        {"neck-west",{{24,7},{16,7},{12,7},{8,7},{0,7}},"",""}};
    return input;
}

void requirePassageFrameSafety(const std::vector<MappedVisibleTrack>& frame,
        const std::map<std::string,double>& radii) {
    bool eastInNeck=false,westInNeck=false;
    for (std::size_t i=0;i<frame.size();++i) {
        const auto& track=frame[i];
        if (track.position.x>9+1e-7 && track.position.x<15-1e-7) {
            require(std::abs(track.position.y-7)<=.05+1e-7,
                "Narrow-passage motion left the center-safe neck");
            eastInNeck|=track.routeId=="neck-east";
            westInNeck|=track.routeId=="neck-west";
        }
        for (std::size_t j=i+1;j<frame.size();++j)
            require(std::hypot(track.position.x-frame[j].position.x,
                    track.position.y-frame[j].position.y)
                    >=radii.at(track.trackId)+radii.at(frame[j].trackId)+.1-1e-7,
                "A passage queue or grant violated pairwise body clearance");
    }
    require(!(eastInNeck && westInNeck),
        "Opposing tracks occupied a nonpassing neck at the same time");
}

void localNarrowPassageOpposingFlowsAndDeterminism() {
    auto input=localNarrowPassageScene();
    input.people={{"private-east","Adult Pedestrian",1.2,{{"a-east","neck-east",0}},.25},
        {"private-west","Pedestrian With Stroller",1,{{"b-west","neck-west",0}},.45}};
    auto renamed=input;std::reverse(renamed.people.begin(),renamed.people.end());
    renamed.people[0].personId="different-private-one";
    renamed.people[1].personId="different-private-two";
    MappedScene scene(input),coarse(renamed);
    const std::map<std::string,double> radii{{"a-east",.25},{"b-west",.45}};
    AggregationTime holdingWithoutReplan=0,longestHoldingWithoutReplan=0;
    auto previous=scene.motionDiagnostics();
    for (AggregationTime now=0;now<=120000;now+=50) {
        scene.advanceTo(now);
        const auto frame=scene.frameAt(now);
        requirePassageFrameSafety(frame,radii);
        const auto diagnostic=scene.motionDiagnostics();
        bool atHoldingPoint=false;
        for (const auto& track:frame) {
            const auto& passage=input.navigation.narrowPassages.front();
            const auto& points=track.routeId=="neck-east"
                ? passage.holdingPointsA : passage.holdingPointsB;
            for (const auto point:points)
                if (std::hypot(track.position.x-point.x,track.position.y-point.y)<1e-7
                    && std::hypot(track.velocity.x,track.velocity.y)<1e-7)
                    atHoldingPoint=true;
        }
        // Deliberately holding for a conflicting grant should not repeatedly
        // search the occupied corridor as though the static route were broken.
        if (atHoldingPoint && diagnostic.navigationReplans==previous.navigationReplans)
            holdingWithoutReplan+=50;
        else holdingWithoutReplan=0;
        longestHoldingWithoutReplan=std::max(longestHoldingWithoutReplan,holdingWithoutReplan);
        previous=diagnostic;
        if (now%250==0) {
            coarse.advanceTo(now);
            sameFrame(frame,coarse.frameAt(now));
        }
    }
    const auto d=scene.motionDiagnostics();
    require(d.realizedStarts==2 && d.realizedEnds==2 && d.activeTracks==0
        && d.pendingTracks==0 && d.overlapViolations==0 && d.passageWaitSteps>0
        && d.passageBatches>=2 && d.passageClearedTracks==2,
        "Explicit narrow-passage opposing flows failed to safely drain");
    require(d.maxPassageWaitMs>0 && longestHoldingWithoutReplan>=1500,
        "Intentional passage holding was not observable without a replanning storm");
    require(scene.events().size()==coarse.events().size(),
        "Private renaming or caller cadence changed passage lifecycle count");
    for (std::size_t i=0;i<scene.events().size();++i)
        require(scene.events()[i].trackId==coarse.events()[i].trackId
            && scene.events()[i].kind==coarse.events()[i].kind
            && scene.events()[i].atMs==coarse.events()[i].atMs,
            "Private identity, person ordering or caller cadence changed passage service");
}

void localNarrowPassageFiniteBatchesDoNotStarveOpposition() {
    auto input=localNarrowPassageScene();
    // Both sides have older demand before the later eastbound source arrives.
    // A finite batch must not keep admitting that later source ahead of west.
    input.people={{"first-east-person","Adult Pedestrian",1.2,
            {{"a-first-east","neck-east",0}},.25},
        {"first-west-person","Adult Pedestrian",1.2,
            {{"b-first-west","neck-west",0}},.25}};
    for (int i=0;i<6;++i) {
        const auto suffix=std::to_string(i);
        input.people.push_back({"later-east-person-"+suffix,"Adult Pedestrian",1.2,
            {{"later-east-"+suffix,"neck-east",8000+i*750}},i%2?.35:.25});
    }
    MappedScene scene(input);
    std::map<std::string,double> radii;
    for (const auto& person:input.people) radii.emplace(person.episodes.front().trackId,person.radiusM);
    for (AggregationTime now=0;now<=180000;now+=50) {
        scene.advanceTo(now);
        requirePassageFrameSafety(scene.frameAt(now),radii);
    }
    const auto d=scene.motionDiagnostics();
    require(d.realizedStarts==8 && d.realizedEnds==8 && d.pendingTracks==0
        && d.activeTracks==0 && d.overlapViolations==0 && d.passageClearedTracks==8
        && d.passageBatches>=3 && d.passageWaitSteps>0,
        "Finite narrow-passage batches failed to drain queued opposing demand");
    AggregationTime westEnd=-1;std::vector<AggregationTime> laterEastEnds;
    for (const auto& event:scene.events()) if (event.kind==MappedEventKind::EpisodeEnd) {
        if (event.trackId=="b-first-west") westEnd=event.atMs;
        if (event.trackId.find("later-east-")==0) laterEastEnds.push_back(event.atMs);
    }
    require(westEnd>=0 && !laterEastEnds.empty()
        && westEnd<*std::max_element(laterEastEnds.begin(),laterEastEnds.end()),
        "Late compatible arrivals indefinitely extended a batch ahead of older opposing demand");
}


void localNarrowPassageSharedDirectionBatchEntersSingleFile() {
    auto input=localNarrowPassageScene();
    auto& passage=input.navigation.narrowPassages.front();
    passage.maxBatchSize=4;
    // Close lateral staging lets a shared batch enter efficiently while keeping
    // both the centerline and the westbound clearing path free of waiting bodies.
    passage.holdingPointsA={{6.5,6},{6.5,8},{6.5,4},{6.5,10}};
    input.people={{"initial-west-person","Adult Pedestrian",1.2,
        {{"a-initial-west","neck-west",0}},.25}};
    for (int i=0;i<4;++i) {
        const auto suffix=std::to_string(i);
        input.people.push_back({"shared-east-person-"+suffix,"Adult Pedestrian",1.2,
            {{"z-shared-east-"+suffix,"neck-east",i*500}},.25});
    }
    MappedScene scene(input);
    std::map<std::string,double> radii;
    for (const auto& person:input.people) radii.emplace(person.episodes.front().trackId,person.radiusM);
    std::size_t maxEastInNeck=0;
    for (AggregationTime now=0;now<=120000;now+=50) {
        scene.advanceTo(now);
        const auto frame=scene.frameAt(now);
        requirePassageFrameSafety(frame,radii);
        std::size_t eastInNeck=0;
        for (const auto& track:frame) {
            if (track.nextWaypointIndex>1 && track.nextWaypointIndex<=3)
                require(std::abs(track.position.y-7)<1e-8
                    && track.position.x>=8-1e-8 && track.position.x<=16+1e-8,
                    "A controlled passage step left its centerline at entry or an internal vertex");
            if (track.routeId=="neck-east" && track.position.x>9 && track.position.x<15)
                ++eastInNeck;
        }
        maxEastInNeck=std::max(maxEastInNeck,eastInNeck);
    }
    const auto d=scene.motionDiagnostics();
    require(d.realizedStarts==5 && d.realizedEnds==5 && d.activeTracks==0
        && d.pendingTracks==0 && d.overlapViolations==0 && d.passageClearedTracks==5
        && d.passageBatches==2,
        "A finite compatible-direction batch failed to drain after opposing service");
    require(maxEastInNeck>=2,
        "Compatible batch entry serialized the whole passage instead of only its mouth");
}




void localNarrowPassageReadyDemandAvoidsUnstagedHeadOfLineBlocking() {
    auto input=localNarrowPassageScene();
    input.people={{"older-slow-person","Adult Pedestrian",.1,
            {{"older-slow-west","neck-west",0}},.25},
        {"younger-fast-person","Adult Pedestrian",1.2,
            {{"younger-fast-east","neck-east",1000}},.25}};
    MappedScene scene(input);
    const std::map<std::string,double> radii{{"older-slow-west",.25},{"younger-fast-east",.25}};
    std::map<std::string,Point> previous;
    for (AggregationTime now=0;now<=400000;now+=50) {
        scene.advanceTo(now);
        const auto frame=scene.frameAt(now);
        requirePassageFrameSafety(frame,radii);
        for (const auto& track:frame) {
            const double speed=track.trackId=="older-slow-west"?.1:1.2;
            require(std::hypot(track.velocity.x,track.velocity.y)<=speed+1e-8,
                "Passage readiness accelerated a slow or waiting track");
            const auto before=previous.find(track.trackId);
            if (before!=previous.end())
                require(std::hypot(track.position.x-before->second.x,
                    track.position.y-before->second.y)<=speed*.05+1e-8,
                    "Passage readiness teleported a track to its staging position");
        }
        previous.clear();
        for (const auto& track:frame) previous.emplace(track.trackId,track.position);
        if (now==40000) {
            bool fastFinished=false,slowFinished=false;
            for (const auto& event:scene.events()) if (event.kind==MappedEventKind::EpisodeEnd) {
                fastFinished|=event.trackId=="younger-fast-east";
                slowFinished|=event.trackId=="older-slow-west";
            }
            // The older request is still approaching/using the resource. It
            // must not reserve an empty passage before it is physically ready
            // and prevent already staged opposite traffic from being served.
            require(fastFinished && !slowFinished,
                "An unstaged older request blocked ready opposing demand for 40 seconds");
        }
    }
    const auto d=scene.motionDiagnostics();
    require(d.realizedStarts==2 && d.realizedEnds==2 && d.pendingTracks==0
        && d.activeTracks==0 && d.overlapViolations==0 && d.passageClearedTracks==2
        && d.passageBatches==2,
        "Ready-first passage service failed to eventually drain the older slow request");
}

void localNarrowPassageBentEntryRemainsOnSpineNearPassingTraffic() {
    auto input=localScene(24,14);
    // A thin static divider preserves the passer's approach until its turn.
    // The unrelated route stays outside the passage, while its approaching
    // velocity can influence the local TTC score at the owner's entry step.
    input.navigation.allowedCenterPolygons[0].holes={
        {{6.49,7.01},{6.51,7.01},{6.51,10.1},{6.49,10.1}}};
    input.navigation.narrowPassages={{"bent-neck",{{8,7},{12,6},{16,7}},
        {{5,4}},{{19,4}},1.15,1}};
    input.routes={{"bent-owner",{{0,7},{8,7},{12,6},{16,7},{24,7}},"",""},
        {"nearby-passer",{{0,7},{6.75,7},{6.75,10},{24,10}},"",""}};
    input.people={{"bent-private","Adult Pedestrian",1.3,
            {{"bent-track","bent-owner",0}},.25},
        {"passer-private","Adult Pedestrian",2,
            {{"passer-track","nearby-passer",3000}},.25}};
    input.navigation.replanAfterMs=120000;
    MappedScene scene(input);std::size_t controlledSteps=0;
    const auto& points=input.routes[0].points;
    for (AggregationTime now=0;now<=60000;now+=50) {
        scene.advanceTo(now);
        for (const auto& track:scene.frameAt(now)) {
            if (track.trackId!="bent-track" || track.nextWaypointIndex<=1
                || track.nextWaypointIndex>3) continue;
            const auto a=points[track.nextWaypointIndex-1],b=points[track.nextWaypointIndex];
            const double dx=b.x-a.x,dy=b.y-a.y;
            const double fraction=std::clamp(((track.position.x-a.x)*dx
                +(track.position.y-a.y)*dy)/(dx*dx+dy*dy),0.0,1.0);
            require(std::hypot(track.position.x-(a.x+fraction*dx),
                    track.position.y-(a.y+fraction*dy))<1e-8,
                "A bent passage's first controlled entry/vertex step used free-space steering");
            ++controlledSteps;
        }
    }
    const auto d=scene.motionDiagnostics();
    require(controlledSteps>0 && d.realizedStarts==2 && d.realizedEnds==2
        && d.activeTracks==0 && d.pendingTracks==0 && d.overlapViolations==0
        && d.passageBatches==1 && d.passageClearedTracks==1,
        "Bent passage control or nearby unrelated traffic failed to drain");
}

void localNarrowPassageUnrelatedGuideBypassesIdleResource() {
    auto input=localNarrowPassageScene();
    input.navigation.allowedCenterPolygons=localScene(24,14).navigation.allowedCenterPolygons;
    input.routes={{"resource-bypass",{{0,7},{6,4},{18,4},{24,7}},"",""}};
    input.people={{"bypass-person","Adult Pedestrian",1.3,
        {{"bypass-track","resource-bypass",0}},.25}};
    // The supplied guide already bypasses the resource. Delay dynamic repair
    // beyond this test so a forbidden shortcut cannot be rescued by A*.
    input.navigation.replanAfterMs=120000;
    MappedScene scene(input);
    for (AggregationTime now=0;now<=60000;now+=50) {
        scene.advanceTo(now);
        for (const auto& track:scene.frameAt(now)) {
            const double centerlineX=std::clamp(track.position.x,8.0,16.0);
            require(std::hypot(track.position.x-centerlineX,track.position.y-7)
                    >=input.navigation.narrowPassages[0].protectionRadiusM-1e-7,
                "An unrelated route shortcut crossed an idle protected passage");
        }
    }
    const auto d=scene.motionDiagnostics();
    require(d.realizedStarts==1 && d.realizedEnds==1 && d.activeTracks==0
        && d.pendingTracks==0 && d.overlapViolations==0
        && d.passageBatches==0 && d.passageWaitSteps==0 && d.passageClearedTracks==0
        && d.navigationReplans==0,
        "An unrelated valid bypass stalled at a forbidden shortcut or acquired the passage");
}

void localNarrowPassageOptionalOffAndValidation() {
    auto plain=localScene(24,14);
    plain.routes={{"unchanged-local",{{0,7},{8,7},{12,7},{16,7},{24,7}},"",""}};
    plain.people={{"unchanged-person","Adult Pedestrian",1,{{"unchanged-track","unchanged-local",0}}}};
    auto explicitlyEmpty=plain;explicitlyEmpty.navigation.narrowPassages.clear();
    MappedScene original(plain),empty(explicitlyEmpty);
    for (AggregationTime now=0;now<=25000;now+=250) {
        original.advanceTo(now);empty.advanceTo(now);
        sameFrame(original.frameAt(now),empty.frameAt(now));
    }
    const auto d=original.motionDiagnostics();
    require(d.realizedEnds==1 && original.episodeEndMs("unchanged-track")==24000
        && d.passageWaitSteps==0 && d.passageBatches==0 && d.passageClearedTracks==0,
        "An absent optional passage altered historical local motion or telemetry");
    const auto bad=[&](const std::function<void(MappedSceneConfig&)>& mutate) {
        auto input=localNarrowPassageScene();
        input.people={{"validation-person","Adult Pedestrian",1,
            {{"validation-track","neck-east",0}},.25}};
        mutate(input);rejects([&]{MappedScene checked(input);});
    };
    bad([](auto& c){c.navigation.narrowPassages[0].id.clear();});
    bad([](auto& c){c.navigation.narrowPassages.push_back(c.navigation.narrowPassages[0]);});
    bad([](auto& c){c.navigation.narrowPassages[0].centerline.clear();});
    bad([](auto& c){c.navigation.narrowPassages[0].centerline={{8,7}};});
    bad([](auto& c){c.navigation.narrowPassages[0].centerline[1]=c.navigation.narrowPassages[0].centerline[0];});
    bad([](auto& c){c.navigation.narrowPassages[0].holdingPointsA.clear();});
    bad([](auto& c){c.navigation.narrowPassages[0].holdingPointsB.clear();});
    bad([](auto& c){c.navigation.narrowPassages[0].holdingPointsA[0]={12,7};});
    bad([](auto& c){c.navigation.narrowPassages[0].holdingPointsA[0]={-1,4};});
    bad([](auto& c){c.navigation.narrowPassages[0].protectionRadiusM=0;});
    bad([](auto& c){c.navigation.narrowPassages[0].protectionRadiusM=std::numeric_limits<double>::quiet_NaN();});
    bad([](auto& c){c.navigation.narrowPassages[0].maxBatchSize=0;});
    bad([](auto& c){c.motionMode=MappedMotionMode::Integration;});
    // Every route touching the resource needs a compiled traversal. Silently
    // accepting an unmanaged crossing would create an impassable static tube.
    bad([](auto& c){c.routes[0].points={{0,7},{24,7}};});
    bad([](auto& c){c.routes.push_back({"unmanaged-apron",{{0,7},{8,7},{8,0}},"",""});});
    bad([](auto& c){
        c.navigation.narrowPassages[0].holdingPointsA.resize(1);
        c.people.push_back({"second-validation-person","Adult Pedestrian",1,
            {{"second-validation-track","neck-east",1000}},.25});
    });
    bad([](auto& c){
        c.portals.push_back({"nearby-door","nearby-building",{8,4},{7,4},{9,4},1,"synthetic"});
    });
    bad([](auto& c){c.navigation.narrowPassages[0].holdingPointsA[0]={19,7};});
    bad([](auto& c){c.navigation.narrowPassages[0].holdingPointsA[0]={6.79,7};});
    bad([](auto& c){
        c.navigation.allowedCenterPolygons[0].holes.push_back(
            {{5.9,4.9},{6.1,4.9},{6.1,5.1},{5.9,5.1}});
    });
}

} // namespace

int main() {
    try {
        localSurfaceAccessIsTypedAndOnlyTerminatesOwningTrips();
        localCrossingPriorityYieldsBeforeEntryAndKeepsPhysicalChecks();
        localCrossingPriorityFiniteFairnessAndValidation();
        localCrossingOppositeReceivingApronsRemainClear();
        localCrossingProjectedBoundaryIntentDrainsTangentialBodies();
        localCrossingPendingWaitIsMeasuredBeforeGrant();
        localCrossingEmptyRoadDoesNotRequireImpossibleEntryStaging();
        localBoundaryIntervalsAvoidPointSinkConvergence();
        localMovementSpacesStaySeparate();
        cornersAndLargeSteps();
        halfOpenAndRoundedArrival();
        hiddenGapAndReentry();
        privateRenamingAndCallOrder();
        shortGapInflatesTrackSupport();
        touchingEpisodesAndSortedEvents();
        invalidConfigurations();
        conservativeFollowersAndActualVelocity();
        separatedOpposingLanesAndRealizedPortalGap();
        boundedBranchMergeAdmitsWaitingExitsAndDrains();
        fastSweptMergeCrossingReleasesReservation();
        preciseDoorArrivalAndRealizedReentry();
        independentDoorsAndUnrelatedPassers();
        splitDoorThroatPreventsOpposingContactDeadlock();
        invalidExplicitDoors();
        opposedSingleLaneStopsSafelyWithoutClaimingCompletion();
        localBoundarySinkRetainsGoalAroundConcaveObstacle();
        localVisibleBoundaryOutflowsKeepSeparateExitPoints();
        localOpposingTrafficSteersAndDrains();
        localCrossingFlowsAndStaticHole();
        localFiniteDenseSourceAndDoorVisits();
        localBoundedReplanningAndValidation();
        localDoorArrivalDoesNotBacktrackToPassedMouth();
        localDoorPipelinesShareThroatAndDrainOpposingDemand();
        localVisibleGuidesDoNotCauseBacktrackingAfterDoorWaits();
        localNarrowPassageOpposingFlowsAndDeterminism();
        localNarrowPassageFiniteBatchesDoNotStarveOpposition();
        localNarrowPassageSharedDirectionBatchEntersSingleFile();
        localNarrowPassageReadyDemandAvoidsUnstagedHeadOfLineBlocking();
        localNarrowPassageBentEntryRemainsOnSpineNearPassingTraffic();
        localNarrowPassageUnrelatedGuideBypassesIdleResource();
        localNarrowPassageOptionalOffAndValidation();
        std::cout << "Mapped scene route, lifecycle, identity-boundary and validation tests passed\n";
    } catch (const std::exception& error) {
        std::cerr << "Mapped scene test failed: " << error.what() << '\n';
        return 1;
    }
}
