#include "MappedSceneConfiguration.hpp"
#include <set>
#include <stdexcept>

namespace {
void keys(const YAML::Node& node, const std::set<std::string>& allowed, const char* name) {
    if (!node || !node.IsMap()) throw std::invalid_argument(std::string(name) + " must be a map");
    std::set<std::string> seen;
    for (const auto& pair : node) {
        if (!pair.first.IsScalar()) throw std::invalid_argument(std::string(name) + " keys must be strings");
        const auto key = pair.first.as<std::string>();
        if (!allowed.count(key) || !seen.insert(key).second)
            throw std::invalid_argument(std::string(name) + " has an unknown or duplicate key: " + key);
    }
}
std::string text(const YAML::Node& node, const char* name) {
    if (!node || !node.IsScalar() || node.as<std::string>().empty())
        throw std::invalid_argument(std::string(name) + " must be a nonempty scalar");
    return node.as<std::string>();
}
}

ump::MappedSceneConfig readMappedSceneConfiguration(const YAML::Node& node,
    double width, double height, const std::unordered_set<std::string>& knownProfiles) {
    keys(node, {"support_contract", "routes", "people"}, "mapped_scene");
    if (text(node["support_contract"], "mapped_scene.support_contract") != "one_episode_per_retained_history")
        throw std::invalid_argument("Mapped scene requires the explicit one_episode_per_retained_history support contract");
    if (!node["routes"].IsSequence() || !node["people"].IsSequence())
        throw std::invalid_argument("mapped_scene routes and people must be sequences");
    ump::MappedSceneConfig result;
    result.width = width; result.height = height;
    for (const auto& r : node["routes"]) {
        keys(r, {"id", "points", "start_portal", "end_portal"}, "mapped route");
        ump::MappedRoute route;
        route.id = text(r["id"], "route id");
        route.startPortal = r["start_portal"].as<std::string>("");
        route.endPortal = r["end_portal"].as<std::string>("");
        if (!r["points"].IsSequence()) throw std::invalid_argument("Mapped route points must be a sequence");
        for (const auto& p : r["points"]) {
            if (!p.IsSequence() || p.size() != 2 || !p[0].IsScalar() || !p[1].IsScalar())
                throw std::invalid_argument("Mapped route point requires exactly two coordinates");
            route.points.push_back({p[0].as<double>(), p[1].as<double>()});
        }
        result.routes.push_back(std::move(route));
    }
    for (const auto& p : node["people"]) {
        keys(p, {"person_id", "type", "speed_mps", "episodes"}, "mapped person");
        ump::MappedPerson person;
        person.personId = text(p["person_id"], "private person id");
        person.type = text(p["type"], "observed profile type");
        if (!knownProfiles.count(person.type)) throw std::invalid_argument("Unknown mapped behavior profile: " + person.type);
        person.speedMps = p["speed_mps"].as<double>();
        if (!p["episodes"].IsSequence()) throw std::invalid_argument("Mapped person episodes must be a sequence");
        for (const auto& e : p["episodes"]) {
            keys(e, {"track_id", "route_id", "start_ms"}, "mapped episode");
            person.episodes.push_back({text(e["track_id"], "track id"),
                text(e["route_id"], "route id"), e["start_ms"].as<ump::AggregationTime>()});
        }
        result.people.push_back(std::move(person));
    }
    // Validate route/identity/lifecycle invariants before any database is opened.
    ump::MappedScene checked(result);
    return result;
}

void validateMappedSupportHorizon(const ump::MappedScene& scene, ump::AggregationTime horizonMs) {
    if (horizonMs <= 0) throw std::invalid_argument("Mapped support horizon must be positive");
    if (const auto gap = scene.minimumHiddenGapMs(); gap && *gap <= horizonMs)
        throw std::invalid_argument("Mapped indoor gap must exceed the complete retained aggregation history; track IDs are not person IDs");
}
