#pragma once

#include "AggregationInput.hpp"
#include <map>
#include <optional>
#include <string>
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

enum class MappedMotionMode { Integration, CorridorFollowing };

struct MappedSceneConfig {
    double width, height;
    std::vector<MappedRoute> routes;
    std::vector<MappedPerson> people;
    MappedMotionMode motionMode = MappedMotionMode::Integration;
    AggregationTime motionStepMs = 50;
    double clearanceM = .1;
    double portalGateRadiusM = 3;
};

struct MappedMotionDiagnostics {
    std::uint64_t blockedMotionSteps = 0, admissionWaitSteps = 0;
    std::uint64_t realizedStarts = 0, realizedEnds = 0, overlapViolations = 0;
    std::uint64_t mergeAdmissionWaitSteps = 0;
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
    };
    void admitPending(AggregationTime nowMs);
    void advanceCorridorStep(AggregationTime nextMs);
    MappedVisibleTrack visibleState(const std::string& trackId, double travelled, Point velocity) const;
    MappedSceneConfig config;
    std::vector<RouteData> routeData;
    std::map<std::string, std::size_t> routeIndices;
    std::map<std::string, EpisodeData> tracks;
    std::vector<MappedSceneEvent> lifecycle;
    std::optional<AggregationTime> minimumGap;
    std::map<std::string, RuntimeTrack> runtime;
    std::map<std::string, Point> portalPoints;
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
