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
};

struct MappedPerson {
    std::string personId, type;
    double speedMps;
    std::vector<MappedEpisode> episodes;
};

struct MappedSceneConfig {
    double width, height;
    std::vector<MappedRoute> routes;
    std::vector<MappedPerson> people;
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
    MappedSceneConfig config;
    std::vector<RouteData> routeData;
    std::map<std::string, std::size_t> routeIndices;
    std::map<std::string, EpisodeData> tracks;
    std::vector<MappedSceneEvent> lifecycle;
    std::optional<AggregationTime> minimumGap;
};

} // namespace ump
