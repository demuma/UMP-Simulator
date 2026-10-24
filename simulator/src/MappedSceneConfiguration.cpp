#include "MappedSceneConfiguration.hpp"
#include <cmath>
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
ump::Point point(const YAML::Node& node, const char* name) {
    if (!node || !node.IsSequence() || node.size()!=2 || !node[0].IsScalar() || !node[1].IsScalar())
        throw std::invalid_argument(std::string(name) + " requires exactly two scalar coordinates");
    return {node[0].as<double>(),node[1].as<double>()};
}
std::string text(const YAML::Node& node, const char* name) {
    if (!node || !node.IsScalar() || node.as<std::string>().empty())
        throw std::invalid_argument(std::string(name) + " must be a nonempty scalar");
    return node.as<std::string>();
}
}

ump::MappedSceneConfig readMappedSceneConfiguration(const YAML::Node& node,
    double width, double height, const std::unordered_set<std::string>& knownProfiles) {
    keys(node, {"support_contract", "routes", "people", "motion", "portals"}, "mapped_scene");
    if (text(node["support_contract"], "mapped_scene.support_contract") != "one_episode_per_retained_history")
        throw std::invalid_argument("Mapped scene requires the explicit one_episode_per_retained_history support contract");
    if (!node["routes"].IsSequence() || !node["people"].IsSequence())
        throw std::invalid_argument("mapped_scene routes and people must be sequences");
    ump::MappedSceneConfig result;
    result.width = width; result.height = height;
    if (node["motion"]) {
        const auto motion=node["motion"];
        keys(motion,{"mode","step_ms","clearance_m","portal_gate_radius_m","navigation"},"mapped_scene.motion");
        const auto mode=text(motion["mode"],"mapped motion mode");
        if (mode=="corridor_following") result.motionMode=ump::MappedMotionMode::CorridorFollowing;
        else if (mode=="local_navigation") result.motionMode=ump::MappedMotionMode::LocalNavigation;
        else throw std::invalid_argument("Mapped motion mode must be corridor_following or local_navigation");
        if (motion["navigation"]) {
            if (result.motionMode!=ump::MappedMotionMode::LocalNavigation)
                throw std::invalid_argument("Navigation geometry requires local_navigation motion");
            const auto navigation=motion["navigation"];
            keys(navigation,{"allowed_center_polygons","grid_resolution_m","center_clearance_m","max_replan_nodes",
                "replan_after_ms","replan_interval_ms","narrow_passages"},"mapped_scene.motion.navigation");
            const auto polygons=navigation["allowed_center_polygons"];
            if (!polygons || !polygons.IsSequence())
                throw std::invalid_argument("Navigation allowed_center_polygons must be a sequence");
            const auto ring=[](const YAML::Node& nodes) {
                if (!nodes || !nodes.IsSequence()) throw std::invalid_argument("Navigation ring must be a sequence");
                std::vector<ump::Point> result;
                for (const auto& value:nodes) result.push_back(point(value,"navigation ring point"));
                return result;
            };
            for (const auto& polygon:polygons) {
                keys(polygon,{"outer","holes"},"navigation polygon");
                ump::MappedNavigationPolygon value;
                value.outer=ring(polygon["outer"]);
                if (polygon["holes"]) {
                    if (!polygon["holes"].IsSequence()) throw std::invalid_argument("Navigation holes must be a sequence");
                    for (const auto& hole:polygon["holes"]) value.holes.push_back(ring(hole));
                }
                result.navigation.allowedCenterPolygons.push_back(std::move(value));
            }
            result.navigation.gridResolutionM=navigation["grid_resolution_m"] ? navigation["grid_resolution_m"].as<double>() : .5;
            result.navigation.centerClearanceM=navigation["center_clearance_m"] ? navigation["center_clearance_m"].as<double>() : .55;
            result.navigation.maxReplanNodes=navigation["max_replan_nodes"] ? navigation["max_replan_nodes"].as<std::size_t>() : 20000;
            result.navigation.replanAfterMs=navigation["replan_after_ms"] ? navigation["replan_after_ms"].as<ump::AggregationTime>() : 1500;
            result.navigation.replanIntervalMs=navigation["replan_interval_ms"] ? navigation["replan_interval_ms"].as<ump::AggregationTime>() : 1000;
            // Passage geometry is an explicit source-model assumption. Missing
            // declarations retain the historical uncoordinated navigation mode.
            if (const auto passages=navigation["narrow_passages"]) {
                if (!passages.IsSequence()) throw std::invalid_argument("Navigation narrow_passages must be a sequence");
                for (const auto& passage:passages) {
                    keys(passage,{"id","centerline","holding_points_a","holding_points_b",
                        "protection_radius_m","max_batch_size"},"navigation narrow passage");
                    ump::MappedNavigationPassage value;
                    value.id=text(passage["id"],"navigation narrow passage id");
                    value.centerline=ring(passage["centerline"]);
                    value.holdingPointsA=ring(passage["holding_points_a"]);
                    value.holdingPointsB=ring(passage["holding_points_b"]);
                    if (passage["protection_radius_m"]) value.protectionRadiusM=passage["protection_radius_m"].as<double>();
                    if (passage["max_batch_size"]) value.maxBatchSize=passage["max_batch_size"].as<std::size_t>();
                    result.navigation.narrowPassages.push_back(std::move(value));
                }
            }
        }
        result.motionStepMs=motion["step_ms"] ? motion["step_ms"].as<ump::AggregationTime>() : 50;
        result.clearanceM=motion["clearance_m"] ? motion["clearance_m"].as<double>() : .1;
        result.portalGateRadiusM=motion["portal_gate_radius_m"] ? motion["portal_gate_radius_m"].as<double>() : 3;
    }
    if (node["portals"]) {
        if (!node["portals"].IsSequence()) throw std::invalid_argument("mapped_scene.portals must be a sequence");
        for (const auto& p : node["portals"]) {
            keys(p,{"id","building_id","point","facade","width_m","provenance"},"mapped portal");
            const auto facade=p["facade"];
            if (!facade || !facade.IsSequence() || facade.size()!=2)
                throw std::invalid_argument("Mapped portal facade requires exactly two endpoints");
            result.portals.push_back({text(p["id"],"portal id"),text(p["building_id"],"portal building id"),
                point(p["point"],"portal point"),point(facade[0],"portal facade endpoint"),
                point(facade[1],"portal facade endpoint"),p["width_m"].as<double>(),
                text(p["provenance"],"portal provenance")});
        }
    }
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
        keys(p, {"person_id", "type", "speed_mps", "episodes", "radius_m"}, "mapped person");
        ump::MappedPerson person;
        person.personId = text(p["person_id"], "private person id");
        person.type = text(p["type"], "observed profile type");
        if (!knownProfiles.count(person.type)) throw std::invalid_argument("Unknown mapped behavior profile: " + person.type);
        person.speedMps = p["speed_mps"].as<double>();
        person.radiusM = p["radius_m"] ? p["radius_m"].as<double>() : .25;
        if (!p["episodes"].IsSequence()) throw std::invalid_argument("Mapped person episodes must be a sequence");
        for (const auto& e : p["episodes"]) {
            keys(e, {"track_id", "route_id", "start_ms", "after_previous_ms"}, "mapped episode");
            person.episodes.push_back({text(e["track_id"], "track id"),
                text(e["route_id"], "route id"), e["start_ms"].as<ump::AggregationTime>(),
                e["after_previous_ms"] ? std::optional<ump::AggregationTime>{e["after_previous_ms"].as<ump::AggregationTime>()} : std::nullopt});
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

void validateMappedCaptureStep(const ump::MappedScene& scene, double simulationStepMs) {
    if (scene.configuration().motionMode==ump::MappedMotionMode::LocalNavigation
        && (!std::isfinite(simulationStepMs)
            || std::abs(simulationStepMs-scene.configuration().motionStepMs)>1e-6))
        throw std::invalid_argument("Local navigation requires the simulation capture step to equal its motion step");
}
