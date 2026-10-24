#pragma once

#include "AggregationInput.hpp"
#include <map>
#include <optional>
#include <set>
#include <string>
#include <tuple>
#include <vector>

namespace ump {

struct Point {
    double x, y;
};

// Coordinates use local metres, x east / y south. An empty endpoint portal
// denotes a domain boundary; named portals identify declared sources or passages.
struct MappedRoute {
    std::string id;
    std::vector<Point> points;
    std::string startPortal, endPortal;
    std::string navigationSpace; // Empty selects the legacy/default movement space.
    std::vector<Point> endBoundary; // Optional two-point sink interval on one domain edge.
};

// A deliberate source-model access point on a building facade. OSM provenance
// denotes a mapped entrance; synthetic portals are simulation assumptions. This
// geometry does not grant entry on incidental contact with any building wall.
struct MappedPortal {
    std::string id, buildingId;
    Point point, facadeStart, facadeEnd;
    double widthM;
    std::string provenance; // Exactly "osm" or "synthetic".
};

struct MappedEpisode {
    std::string trackId, routeId;
    AggregationTime startMs;
    // Corridor returns are scheduled from the preceding REALIZED arrival.
    std::optional<AggregationTime> afterPreviousMs = std::nullopt;
};

struct MappedPerson {
    std::string personId, type;
    double speedMps;
    std::vector<MappedEpisode> episodes;
    double radiusM = .25;
};

// Local navigation uses an explicitly supplied union of center-safe polygons.
// Geometry is generated from body-eroded walking space; holes remain obstacles.
struct MappedNavigationPolygon {
    std::vector<Point> outer;
    std::vector<std::vector<Point>> holes;
};
// Optional movement resource, independent of aggregation/policy quadtrees.
// A route traverses it by including the complete centerline in either direction.
// Holding points keep waiting bodies out of the protected passage and exit apron.
struct MappedNavigationPassage {
    std::string id;
    std::vector<Point> centerline, holdingPointsA, holdingPointsB;
    double protectionRadiusM = 1.15;
    std::size_t maxBatchSize = 6;
};
// A separate body-eroded movement permission, e.g. a carriageway for riders.
struct MappedNavigationSpace {
    std::string id;
    std::vector<MappedNavigationPolygon> allowedCenterPolygons;
    double centerClearanceM = .55;
};
struct MappedNavigationConfig {
    std::vector<MappedNavigationSpace> spaces;
    std::vector<MappedNavigationPolygon> allowedCenterPolygons;
    std::vector<MappedNavigationPassage> narrowPassages;
    double gridResolutionM = .5, centerClearanceM = .55;
    std::size_t maxReplanNodes = 20000;
    // Optional finite same-direction door pipeline. One preserves legacy flow.
    std::size_t doorMaxBatchSize = 1;
    AggregationTime replanAfterMs = 1500, replanIntervalMs = 1000;
};

enum class MappedMotionMode { Integration, CorridorFollowing, LocalNavigation };

struct MappedSceneConfig {
    double width, height;
    std::vector<MappedRoute> routes;
    std::vector<MappedPerson> people;
    MappedMotionMode motionMode = MappedMotionMode::Integration;
    AggregationTime motionStepMs = 50;
    double clearanceM = .1;
    double portalGateRadiusM = 3; // Historical undeclared-portal mode only.
    std::vector<MappedPortal> portals;
    MappedNavigationConfig navigation;
};

struct MappedMotionDiagnostics {
    std::uint64_t blockedMotionSteps = 0, admissionWaitSteps = 0;
    std::uint64_t realizedStarts = 0, realizedEnds = 0, overlapViolations = 0;
    std::uint64_t mergeAdmissionWaitSteps = 0;
    // Opt-in deterministic local-navigation work and bounded-search telemetry.
    std::uint64_t navigationSteeringSteps = 0, navigationReplans = 0;
    std::uint64_t navigationReplanFailures = 0, navigationCandidateChecks = 0;
    std::size_t navigationMaxSearchNodes = 0;
    std::uint64_t passageWaitSteps = 0, passageBatches = 0, passageClearedTracks = 0;
    AggregationTime maxPassageWaitMs = 0;
    AggregationTime maxConsecutiveStopMs = 0;
    std::size_t activeStalledTracks = 0, pendingTracks = 0, activeTracks = 0;
};

// The operational motion boundary deliberately contains no stable person ID,
// future visit schedule, hidden-state label or cross-episode correspondence.
struct MappedVisibleTrack {
    std::string trackId, type, routeId;
    Point position, velocity;
    int nextWaypointIndex; // Outgoing polyline segment endpoint; no identity linkage.
};

enum class MappedEventKind { EpisodeStart, EpisodeEnd };

// Private simulation/evaluation oracle. Never supply this to a sensor or to
// an aggregation accumulator as a way to reconnect interrupted tracks.
struct MappedSceneEvent {
    MappedEventKind kind;
    std::string personId, trackId, routeId, portalId;
    AggregationTime atMs;
    std::optional<Point> position = std::nullopt; // Realized interval exit, private GT only.
};

double mappedRouteLength(const MappedRoute& route);
AggregationTime mappedEpisodeDurationMs(const MappedRoute& route, double speedMps);

// Pure simulation-time route/lifecycle model. No SFML, MongoDB, wall clock or
// random source is used. The caller allocates explicit opaque episode tokens.
class MappedScene {
public:
    explicit MappedScene(MappedSceneConfig config);

    // Visibility uses half-open intervals [startMs, episodeEndMs). Results are
    // ordered by track token, independently of private person names/call order.
    std::vector<MappedVisibleTrack> frameAt(AggregationTime nowMs) const;
    // Historical integration mode remains stateless. Corridor mode progresses
    // monotonically in bounded simulation-time substeps and keeps actual stops.
    void advanceTo(AggregationTime nowMs);
    MappedMotionDiagnostics motionDiagnostics() const;
    const MappedSceneConfig& configuration() const { return config; }
    double routeLength(const std::string& routeId) const;
    AggregationTime episodeEndMs(const std::string& trackId) const;

    // Explicitly private oracle accessors, for Simulator GT and evaluation only.
    const std::string& privatePersonForTrack(const std::string& trackId) const;
    const std::vector<MappedSceneEvent>& events() const { return lifecycle; }
    std::optional<AggregationTime> minimumHiddenGapMs() const { return minimumGap; }

private:
    struct RouteData {
        std::vector<double> cumulative;
        double length;
    };
    struct EpisodeData {
        std::size_t person, route, episode;
        AggregationTime endMs;
    };
    struct RuntimeTrack {
        enum class State { Pending, Active, Finished } state = State::Pending;
        double progress = 0;
        Point position{0, 0}, velocity{0, 0};
        AggregationTime admittedAtMs = -1, arrivedAtMs = -1, stoppedForMs = 0;
        std::size_t navigationWaypoint = 1, detourWaypoint = 0;
        std::vector<Point> detour;
        AggregationTime lastReplanMs = -1, navigationNoProgressMs = 0;
        double navigationBestGoalDistance = 1e300;
        Point navigationTarget{1e300,1e300};
        std::optional<Point> boundaryGoal; // Stabilize an occluded sink target until visible outflow resumes.
    };
    void admitPending(AggregationTime nowMs);
    void advanceCorridorStep(AggregationTime nextMs);
    void advanceNavigationStep(AggregationTime nextMs);
    void updateNavigationDoors(AggregationTime nowMs);
    void updateNavigationDoorPipelines(AggregationTime nowMs);
    bool doorEntryAllowed(const std::string& trackId, const std::string& portalId) const;
    void updateNavigationPassages(AggregationTime nowMs);
    struct PassageTraversal {
        std::size_t passage, entryWaypoint, exitWaypoint;
        bool forward;
    };
    const PassageTraversal* pendingPassage(const std::string& trackId) const;
    bool passageEntryAllowed(const std::string& trackId) const;
    bool passageSegmentAllowed(const std::string& trackId, Point from, Point to) const;
    bool navigationSegmentAllowed(Point from, Point to, const MappedRoute* route = nullptr) const;
    bool replanNavigation(const std::string& trackId, Point goal);
    MappedVisibleTrack visibleState(const std::string& trackId, double travelled, Point velocity) const;
    MappedSceneConfig config;
    std::map<std::string,std::size_t> navigationSpaceIndices;
    struct FacadeExclusion {
        std::string portalId;
        std::vector<Point> ring;
        Point minimum, maximum;
    };
    std::vector<FacadeExclusion> facadeExclusions;
    // Ordered grid edges retain direction-specific floating-point predicates.
    // Only immutable geometry is cached; bodies and resource ownership are not.
    using NavigationEdgeKey = std::tuple<std::string,std::string,std::string,std::size_t,std::size_t>;
    std::map<NavigationEdgeKey,bool> navigationEdgeCache; // At most 65,536 entries.
    std::vector<RouteData> routeData;
    std::map<std::string, std::size_t> routeIndices;
    std::map<std::string, EpisodeData> tracks;
    std::vector<MappedSceneEvent> lifecycle;
    std::optional<AggregationTime> minimumGap;
    std::map<std::string, RuntimeTrack> runtime;
    std::map<std::string, Point> portalPoints;
    struct NavigationDoor {
        Point approach;
        std::string owner;
        std::map<std::string,AggregationTime> requests;
        std::map<std::string,Point> waitingPoints;
        std::set<std::string> granted;
        bool outbound = false;
    };
    std::map<std::string,NavigationDoor> navigationDoors;
    struct NavigationPassage {
        struct Request { AggregationTime atMs; bool forward; };
        std::map<std::string, Request> requests;
        std::map<std::string, bool> granted; // Value latches actual entry.
        std::map<std::string, Point> waitingPoints;
        std::set<std::string> completed, staged;
    };
    std::vector<NavigationPassage> navigationPassages;
    std::map<std::size_t,std::vector<PassageTraversal>> routePassages;
    // Explicit doors reserve only a local body-clearance throat for tracks
    // that actually enter/exit that door. Unrelated passers use the same swept
    // body collision checks without acquiring an artificial entrance resource.
    std::map<std::string, double> explicitPortalGateRadii;
    // One bounded branch/through-flow merge resource per building portal.
    // Persistent FIFO exit ownership or finite compatible through batches keep
    // later arrivals from growing a batch indefinitely. The owner retains the
    // resource until its full swept body clears; physical reservations still
    // govern every move. This is not a general multi-junction deadlock proof.
    std::map<std::string, Point> mergeGatePoints;
    struct MergeReservation {
        std::string owner;
        bool entered = false;
        std::map<std::string,bool> throughBatch;
    };
    std::map<std::string, MergeReservation> mergeReservations;
    std::map<std::string,std::map<std::string,AggregationTime>> mergeRequests;
    AggregationTime currentMs = 0;
    bool runtimeInitialized = false;
    MappedMotionDiagnostics diagnostics;
};

} // namespace ump
