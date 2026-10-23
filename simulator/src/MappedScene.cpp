#include "MappedScene.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <stdexcept>
#include <utility>

namespace ump {
namespace {
void identifier(const std::string& value, const char* kind) {
    if (value.empty() || value.find_first_not_of(" \t\r\n") == std::string::npos
        || value.find('\0') != std::string::npos)
        throw std::invalid_argument(std::string("Mapped scene requires a nonempty ") + kind);
}

bool finite(Point point) { return std::isfinite(point.x) && std::isfinite(point.y); }

std::vector<double> cumulativeLength(const MappedRoute& route) {
    identifier(route.id, "route identifier");
    if (route.points.size() < 2)
        throw std::invalid_argument("Mapped route requires at least two points");
    std::vector<double> cumulative{0};
    cumulative.reserve(route.points.size());
    if (!finite(route.points.front())) throw std::invalid_argument("Mapped route point is nonfinite");
    for (std::size_t i = 1; i < route.points.size(); ++i) {
        const auto before = route.points[i - 1], after = route.points[i];
        if (!finite(after)) throw std::invalid_argument("Mapped route point is nonfinite");
        const double segment = std::hypot(after.x - before.x, after.y - before.y);
        const double total = cumulative.back() + segment;
        if (!std::isfinite(segment) || segment <= 0 || !std::isfinite(total)
            || total <= cumulative.back())
            throw std::invalid_argument("Mapped route requires positive finite, distinguishable segment lengths");
        cumulative.push_back(total);
    }
    return cumulative;
}

AggregationTime durationMs(double length, double speedMps) {
    if (!std::isfinite(speedMps) || speedMps <= 0)
        throw std::invalid_argument("Mapped person speed must be finite and positive");
    const long double duration = std::ceil(static_cast<long double>(length)
        / static_cast<long double>(speedMps) * 1000.0L);
    // The exclusive power-of-two upper bound is exact even where long double
    // has only double precision and INT64_MAX would round upward to 2^63.
    const long double upperExclusive = std::ldexp(1.0L, std::numeric_limits<AggregationTime>::digits);
    if (!std::isfinite(duration) || duration < 1 || duration >= upperExclusive)
        throw std::invalid_argument("Mapped episode duration exceeds simulation time range");
    return static_cast<AggregationTime>(duration);
}

bool boundary(Point p, double width, double height) {
    const double tolerance = 1e-9 * std::max({1.0, width, height});
    return p.x <= tolerance || p.y <= tolerance
        || width - p.x <= tolerance || height - p.y <= tolerance;
}
} // namespace

double mappedRouteLength(const MappedRoute& route) { return cumulativeLength(route).back(); }

AggregationTime mappedEpisodeDurationMs(const MappedRoute& route, double speedMps) {
    return durationMs(mappedRouteLength(route), speedMps);
}

MappedScene::MappedScene(MappedSceneConfig configured) : config(std::move(configured)) {
    if (!std::isfinite(config.width) || !std::isfinite(config.height)
        || config.width <= 0 || config.height <= 0)
        throw std::invalid_argument("Mapped scene extent must be finite and positive");
    if (config.routes.empty() || config.people.empty())
        throw std::invalid_argument("Mapped scene requires routes and people");
    std::set<std::string> identifiers;
    routeData.reserve(config.routes.size());
    for (std::size_t i = 0; i < config.routes.size(); ++i) {
        const auto& route = config.routes[i];
        auto cumulative = cumulativeLength(route);
        if (!identifiers.insert(route.id).second)
            throw std::invalid_argument("Mapped scene identifiers must be globally unique");
        for (auto p : route.points)
            if (p.x < 0 || p.y < 0 || p.x > config.width || p.y > config.height)
                throw std::invalid_argument("Mapped route point lies outside scene extent");
        if ((route.startPortal.empty() && !boundary(route.points.front(), config.width, config.height))
            || (route.endPortal.empty() && !boundary(route.points.back(), config.width, config.height)))
            throw std::invalid_argument("An endpoint without a portal must lie on the scene boundary");
        if (!route.startPortal.empty()) identifier(route.startPortal, "start portal");
        if (!route.endPortal.empty()) identifier(route.endPortal, "end portal");
        routeIndices.emplace(route.id, i);
        const double length = cumulative.back();
        routeData.push_back({std::move(cumulative), length});
    }

    for (std::size_t p = 0; p < config.people.size(); ++p) {
        auto& person = config.people[p];
        identifier(person.personId, "private person identifier");
        identifier(person.type, "observed type");
        if (!identifiers.insert(person.personId).second)
            throw std::invalid_argument("Mapped scene identifiers must be globally unique");
        if (!std::isfinite(person.speedMps) || person.speedMps <= 0 || person.episodes.empty())
            throw std::invalid_argument("Mapped person requires positive finite speed and visible episodes");
        std::sort(person.episodes.begin(), person.episodes.end(), [](const auto& a, const auto& b) {
            return a.startMs < b.startMs;
        });
        std::optional<AggregationTime> previousEnd;
        for (std::size_t e = 0; e < person.episodes.size(); ++e) {
            const auto& episode = person.episodes[e];
            identifier(episode.trackId, "observation track identifier");
            if (!identifiers.insert(episode.trackId).second)
                throw std::invalid_argument("Mapped scene identifiers must be globally unique");
            const auto routeFound = routeIndices.find(episode.routeId);
            if (routeFound == routeIndices.end())
                throw std::invalid_argument("Mapped episode references an unknown route");
            if (episode.startMs < 0)
                throw std::invalid_argument("Mapped episode cannot start before the simulation origin");
            const auto r = routeFound->second;
            const auto duration = durationMs(routeData[r].length, person.speedMps);
            if (episode.startMs > std::numeric_limits<AggregationTime>::max() - duration)
                throw std::invalid_argument("Mapped episode end exceeds simulation time range");
            const auto endMs = episode.startMs + duration;
            if (previousEnd) {
                if (episode.startMs < *previousEnd)
                    throw std::invalid_argument("One private person cannot have overlapping visible episodes");
                const auto gap = episode.startMs - *previousEnd;
                minimumGap = minimumGap ? std::min(*minimumGap, gap) : gap;
            }
            previousEnd = endMs;
            tracks.emplace(episode.trackId, EpisodeData{p, r, e, endMs});
            const auto& route = config.routes[r];
            lifecycle.push_back({MappedEventKind::EpisodeStart, person.personId, episode.trackId,
                route.id, route.startPortal, episode.startMs});
            lifecycle.push_back({MappedEventKind::EpisodeEnd, person.personId, episode.trackId,
                route.id, route.endPortal, endMs});
        }
    }
    std::sort(lifecycle.begin(), lifecycle.end(), [](const auto& a, const auto& b) {
        if (a.atMs != b.atMs) return a.atMs < b.atMs;
        // End a completed half-open episode before beginning another at the same time.
        if (a.kind != b.kind) return a.kind == MappedEventKind::EpisodeEnd;
        return a.trackId < b.trackId;
    });
}

std::vector<MappedVisibleTrack> MappedScene::frameAt(AggregationTime nowMs) const {
    if (nowMs < 0) throw std::invalid_argument("Mapped scene time cannot precede the simulation origin");
    std::vector<MappedVisibleTrack> result;
    for (const auto& entry : tracks) {
        const auto& episodeData = entry.second;
        const auto& person = config.people[episodeData.person];
        const auto& episode = person.episodes[episodeData.episode];
        if (nowMs < episode.startMs || nowMs >= episodeData.endMs) continue;
        const auto& route = config.routes[episodeData.route];
        const auto& compiled = routeData[episodeData.route];
        const double travelled = std::min(compiled.length, person.speedMps
            * (static_cast<double>(nowMs - episode.startMs) / 1000.0));
        const auto next = std::upper_bound(compiled.cumulative.begin(), compiled.cumulative.end(), travelled);
        const std::size_t segment = std::min(static_cast<std::size_t>(next - compiled.cumulative.begin() - 1),
            route.points.size() - 2);
        const auto before = route.points[segment], after = route.points[segment + 1];
        const double length = compiled.cumulative[segment + 1] - compiled.cumulative[segment];
        const double fraction = std::clamp((travelled - compiled.cumulative[segment]) / length, 0.0, 1.0);
        result.push_back({episode.trackId, person.type, route.id,
            {before.x + (after.x - before.x) * fraction, before.y + (after.y - before.y) * fraction},
            {(after.x - before.x) / length * person.speedMps,
                (after.y - before.y) / length * person.speedMps}, static_cast<int>(segment + 1)});
    }
    return result;
}

double MappedScene::routeLength(const std::string& routeId) const {
    const auto found = routeIndices.find(routeId);
    if (found == routeIndices.end()) throw std::invalid_argument("Unknown mapped route identifier");
    return routeData[found->second].length;
}

AggregationTime MappedScene::episodeEndMs(const std::string& trackId) const {
    const auto found = tracks.find(trackId);
    if (found == tracks.end()) throw std::invalid_argument("Unknown mapped track identifier");
    return found->second.endMs;
}

const std::string& MappedScene::privatePersonForTrack(const std::string& trackId) const {
    const auto found = tracks.find(trackId);
    if (found == tracks.end()) throw std::invalid_argument("Unknown mapped track identifier");
    return config.people[found->second.person].personId;
}

} // namespace ump
