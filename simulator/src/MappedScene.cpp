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

double pointSegmentDistance(Point p, Point a, Point b) {
    const double dx = b.x-a.x, dy = b.y-a.y, length2 = dx*dx+dy*dy;
    const double t = length2 ? std::clamp(((p.x-a.x)*dx+(p.y-a.y)*dy)/length2, 0.0, 1.0) : 0;
    return std::hypot(p.x-a.x-t*dx, p.y-a.y-t*dy);
}
double cross(Point a, Point b, Point c) {
    return (b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
}
double segmentDistance(Point a, Point b, Point c, Point d) {
    const double ac=cross(a,b,c), ad=cross(a,b,d), ca=cross(c,d,a), cb=cross(c,d,b);
    if (((ac>0 && ad<0)||(ac<0 && ad>0)) && ((ca>0 && cb<0)||(ca<0 && cb>0))) return 0;
    return std::min({pointSegmentDistance(a,c,d),pointSegmentDistance(b,c,d),
        pointSegmentDistance(c,a,b),pointSegmentDistance(d,a,b)});
}
double pathDistance(const std::vector<Point>& first, const std::vector<Point>& second) {
    double result=std::numeric_limits<double>::infinity();
    for (std::size_t i=1;i<first.size();++i)
        for (std::size_t j=1;j<second.size();++j)
            result=std::min(result,segmentDistance(first[i-1],first[i],second[j-1],second[j]));
    return result;
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
    if (config.motionStepMs <= 0 || config.motionStepMs > 50 || 50 % config.motionStepMs
        || !std::isfinite(config.clearanceM) || config.clearanceM < 0
        || !std::isfinite(config.portalGateRadiusM) || config.portalGateRadiusM <= 0)
        throw std::invalid_argument("Mapped corridor motion requires step <=50ms, finite clearance and positive portal gate");
    std::set<std::string> identifiers;
    std::map<std::string,const MappedPortal*> declaredPortals;
    std::map<std::string,double> portalBodyClearance;
    for (const auto& portal:config.portals) {
        identifier(portal.id,"portal identifier");
        identifier(portal.buildingId,"portal building identifier");
        const double facadeLength=std::hypot(portal.facadeEnd.x-portal.facadeStart.x,
            portal.facadeEnd.y-portal.facadeStart.y);
        if (!identifiers.insert(portal.id).second)
            throw std::invalid_argument("Mapped scene identifiers must be globally unique");
        if (!finite(portal.point) || !finite(portal.facadeStart) || !finite(portal.facadeEnd)
            || !std::isfinite(facadeLength) || facadeLength<=0
            || !std::isfinite(portal.widthM) || portal.widthM<=0 || portal.widthM>facadeLength+1e-9
            || portal.point.x<0 || portal.point.y<0 || portal.point.x>config.width || portal.point.y>config.height
            || pointSegmentDistance(portal.point,portal.facadeStart,portal.facadeEnd)>1e-7)
            throw std::invalid_argument("Mapped portal requires a finite in-domain point on a nondegenerate facade and fitting positive width");
        if (portal.provenance!="osm" && portal.provenance!="synthetic")
            throw std::invalid_argument("Mapped portal provenance must be osm or synthetic");
        // The door opening is centered at the point and must fit on its facade,
        // including when a mapped entrance is not at the wall midpoint.
        if (std::hypot(portal.point.x-portal.facadeStart.x,portal.point.y-portal.facadeStart.y)+1e-7<portal.widthM/2
            || std::hypot(portal.point.x-portal.facadeEnd.x,portal.point.y-portal.facadeEnd.y)+1e-7<portal.widthM/2)
            throw std::invalid_argument("Mapped portal opening extends beyond its declared facade");
        declaredPortals.emplace(portal.id,&portal);
        portalPoints.emplace(portal.id,portal.point);
        explicitPortalGateRadii.emplace(portal.id,portal.widthM/2);
    }
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
        for (const auto& endpoint : {std::make_pair(route.startPortal,route.points.front()),
                std::make_pair(route.endPortal,route.points.back())}) {
            if (endpoint.first.empty()) continue;
            const auto declared=declaredPortals.find(endpoint.first);
            if (!declaredPortals.empty() && declared==declaredPortals.end()
                && !boundary(endpoint.second,config.width,config.height))
                throw std::invalid_argument("Interior route endpoint references an undeclared building portal");
            if (declared==declaredPortals.end() && boundary(endpoint.second,config.width,config.height)) continue;
            const auto old=portalPoints.find(endpoint.first);
            if (old!=portalPoints.end() && std::hypot(old->second.x-endpoint.second.x,
                    old->second.y-endpoint.second.y)>1e-7)
                throw std::invalid_argument("An interior portal must have one consistent position");
            portalPoints.emplace(endpoint.first,endpoint.second);
        }
    }

    if (config.motionMode == MappedMotionMode::CorridorFollowing) {
        // Locate the beginning of each exit branch's join into an aligned
        // boundary-through corridor. Do not let an exiting body and a through
        // body reach mutually blocking contact before deciding admission.
        std::map<std::string,std::vector<Point>> joins;
        for (const auto& exit : config.routes) {
            if (!portalPoints.count(exit.startPortal)) continue;
            for (std::size_t i=1;i+1<exit.points.size();++i) {
                const auto p=exit.points[i], next=exit.points[i+1];
                const double dx=next.x-p.x,dy=next.y-p.y,length=std::hypot(dx,dy);
                bool joinsThrough=false;
                for (const auto& through : config.routes) {
                    if (!boundary(through.points.front(),config.width,config.height)
                        || !boundary(through.points.back(),config.width,config.height)) continue;
                    for (std::size_t j=1;j<through.points.size();++j) {
                        const auto a=through.points[j-1],b=through.points[j];
                        const double sx=b.x-a.x,sy=b.y-a.y,segment=std::hypot(sx,sy);
                        if (pointSegmentDistance(p,a,b)<.75 && (dx*sx+dy*sy)/(length*segment)>.8)
                            joinsThrough=true;
                    }
                }
                if (joinsThrough) {joins[exit.startPortal].push_back(p);break;}
            }
        }
        for (const auto& [portal,points] : joins) {
            Point centre{0,0};
            for (auto p:points) {centre.x+=p.x;centre.y+=p.y;}
            centre.x/=points.size();centre.y/=points.size();
            mergeGatePoints.emplace(portal,centre);
        }
    }

    for (std::size_t p = 0; p < config.people.size(); ++p) {
        auto& person = config.people[p];
        identifier(person.personId, "private person identifier");
        identifier(person.type, "observed type");
        if (!identifiers.insert(person.personId).second)
            throw std::invalid_argument("Mapped scene identifiers must be globally unique");
        if (!std::isfinite(person.speedMps) || person.speedMps <= 0 || person.episodes.empty()
            || !std::isfinite(person.radiusM) || person.radiusM <= 0)
            throw std::invalid_argument("Mapped person requires positive finite speed and visible episodes");
        if (config.motionMode == MappedMotionMode::Integration)
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
            const auto& referencedRoute=config.routes[r];
            for (const auto& portalId:{referencedRoute.startPortal,referencedRoute.endPortal}) {
                const auto portal=declaredPortals.find(portalId);
                if (portal==declaredPortals.end()) continue;
                if (person.radiusM*2>portal->second->widthM+1e-9)
                    throw std::invalid_argument("Mapped person body does not fit through its declared portal opening");
                // One exact center is shared by arrivals and departures. Reserve
                // a short body-aware throat, not the historical exclusive 3m
                // disk. Route-specific separated approaches are still needed;
                // this is not a general bidirectional path planner.
                auto& radius=explicitPortalGateRadii.at(portalId);
                radius=std::max(radius,person.radiusM*2+config.clearanceM);
                portalBodyClearance[portalId]=std::max(portalBodyClearance[portalId],
                    person.radiusM*2+config.clearanceM);
            }
            const auto duration = durationMs(routeData[r].length, person.speedMps);
            if (episode.startMs > std::numeric_limits<AggregationTime>::max() - duration)
                throw std::invalid_argument("Mapped episode end exceeds simulation time range");
            const auto endMs = episode.startMs + duration;
            if (episode.afterPreviousMs && (!e || *episode.afterPreviousMs < 0
                    || config.motionMode != MappedMotionMode::CorridorFollowing))
                throw std::invalid_argument("Relative indoor gaps require a preceding corridor episode");
            if (config.motionMode == MappedMotionMode::CorridorFollowing && e && !episode.afterPreviousMs)
                throw std::invalid_argument("Corridor return episodes require after_previous_ms from realized arrival");
            if (previousEnd) {
                if (!episode.afterPreviousMs && episode.startMs < *previousEnd)
                    throw std::invalid_argument("One private person cannot have overlapping visible episodes");
                const auto gap = episode.afterPreviousMs.value_or(episode.startMs - *previousEnd);
                minimumGap = minimumGap ? std::min(*minimumGap, gap) : gap;
            }
            if (e && episode.afterPreviousMs && !declaredPortals.empty()) {
                const auto& previousRoute=config.routes[routeIndices.at(person.episodes[e-1].routeId)];
                const auto previousDoor=declaredPortals.find(previousRoute.endPortal);
                if (previousDoor!=declaredPortals.end()) {
                    const auto nextDoor=declaredPortals.find(referencedRoute.startPortal);
                    if (nextDoor==declaredPortals.end()
                        || nextDoor->second->buildingId!=previousDoor->second->buildingId)
                        throw std::invalid_argument("A hidden building visit must return through the same declared building");
                }
            }
            previousEnd = endMs;
            tracks.emplace(episode.trackId, EpisodeData{p, r, e, endMs});
            const auto& route = config.routes[r];
            if (config.motionMode == MappedMotionMode::Integration) {
                lifecycle.push_back({MappedEventKind::EpisodeStart, person.personId, episode.trackId,
                    route.id, route.startPortal, episode.startMs});
                lifecycle.push_back({MappedEventKind::EpisodeEnd, person.personId, episode.trackId,
                    route.id, route.endPortal, endMs});
            } else runtime.emplace(episode.trackId,RuntimeTrack{});
        }
    }
    // Opposing arrivals/departures meet at one exact doorway center. Their
    // split approach rays need enough lateral separation before we release the
    // local throat. Diameter alone is insufficient for a shallow split: both
    // fronts could otherwise wait at body contact on either side of its edge.
    // This bound concerns only the incident endpoint segments. Arbitrary route
    // crossings elsewhere remain the route planner's responsibility.
    for (auto& [portal,radius]:explicitPortalGateRadii) {
        const auto body=portalBodyClearance.find(portal);
        if (body==portalBodyClearance.end()) continue;
        for (const auto& arrival:config.routes) {
            if (arrival.endPortal!=portal) continue;
            const auto p=arrival.points.back(), a=arrival.points[arrival.points.size()-2];
            const double ax=a.x-p.x, ay=a.y-p.y, al=std::hypot(ax,ay);
            for (const auto& departure:config.routes) {
                if (departure.startPortal!=portal) continue;
                const auto b=departure.points[1];
                const double bx=b.x-p.x, by=b.y-p.y, bl=std::hypot(bx,by);
                const double cosine=std::clamp((ax*bx+ay*by)/(al*bl),-1.0,1.0);
                // Closest approach need not occur at equal radial distances:
                // an outgoing body may pass the waiting front along its ray.
                const double separation=cosine<=0 ? 1 : std::sqrt(std::max(0.0,1-cosine*cosine));
                const double throat=separation>1e-6 ? body->second/separation+config.clearanceM
                    : std::max(al,bl)+body->second;
                if (!std::isfinite(throat)) throw std::invalid_argument("Mapped portal approach throat is nonfinite");
                radius=std::max(radius,throat);
            }
        }
    }
    std::sort(lifecycle.begin(), lifecycle.end(), [](const auto& a, const auto& b) {
        if (a.atMs != b.atMs) return a.atMs < b.atMs;
        // End a completed half-open episode before beginning another at the same time.
        if (a.kind != b.kind) return a.kind == MappedEventKind::EpisodeEnd;
        return a.trackId < b.trackId;
    });
    if (config.motionMode == MappedMotionMode::CorridorFollowing) advanceTo(0);
}

std::vector<MappedVisibleTrack> MappedScene::frameAt(AggregationTime nowMs) const {
    if (nowMs < 0) throw std::invalid_argument("Mapped scene time cannot precede the simulation origin");
    std::vector<MappedVisibleTrack> result;
    if (config.motionMode == MappedMotionMode::CorridorFollowing) {
        if (nowMs != currentMs) throw std::invalid_argument("Advance corridor motion before reading its current frame");
        for (const auto& [id,state] : runtime) if (state.state == RuntimeTrack::State::Active)
            result.push_back(visibleState(id,state.progress,state.velocity));
        return result;
    }
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

MappedVisibleTrack MappedScene::visibleState(const std::string& id, double travelled, Point velocity) const {
    const auto& data=tracks.at(id); const auto& person=config.people[data.person];
    const auto& route=config.routes[data.route]; const auto& compiled=routeData[data.route];
    const auto next=std::upper_bound(compiled.cumulative.begin(),compiled.cumulative.end(),travelled);
    const auto segment=std::min(static_cast<std::size_t>(next-compiled.cumulative.begin()-1),route.points.size()-2);
    const auto a=route.points[segment], b=route.points[segment+1];
    const double part=(travelled-compiled.cumulative[segment])/(compiled.cumulative[segment+1]-compiled.cumulative[segment]);
    return {id,person.type,route.id,{a.x+(b.x-a.x)*part,a.y+(b.y-a.y)*part},velocity,static_cast<int>(segment+1)};
}

void MappedScene::admitPending(AggregationTime nowMs) {
    std::vector<std::pair<AggregationTime,std::string>> requests;
    for (const auto& [id,state] : runtime) {
        if (state.state!=RuntimeTrack::State::Pending) continue;
        const auto& data=tracks.at(id); const auto& person=config.people[data.person];
        const auto& episode=person.episodes[data.episode];
        AggregationTime ready=episode.startMs;
        if (episode.afterPreviousMs) {
            const auto& previous=runtime.at(person.episodes[data.episode-1].trackId);
            if (previous.state!=RuntimeTrack::State::Finished) continue;
            if (previous.arrivedAtMs>std::numeric_limits<AggregationTime>::max()-*episode.afterPreviousMs)
                throw std::overflow_error("Realized mapped return exceeds time range");
            ready=std::max(ready,previous.arrivedAtMs+*episode.afterPreviousMs);
        }
        if (ready>nowMs) continue;
        requests.emplace_back(ready,id);
    }
    std::sort(requests.begin(),requests.end()); // FIFO source requests; opaque ID breaks ties.
    for (const auto& [ready,id] : requests) {
        auto& state=runtime.at(id);
        const auto& data=tracks.at(id);const auto& person=config.people[data.person];
        const auto point=config.routes[data.route].points.front();
        bool available=true;
        for (const auto& [otherId,other] : runtime) {
            if (other.state!=RuntimeTrack::State::Active) continue;
            const auto& otherPerson=config.people[tracks.at(otherId).person];
            if (std::hypot(point.x-other.position.x,point.y-other.position.y)
                    <person.radiusM+otherPerson.radiusM+config.clearanceM-1e-9) available=false;
            // A building exit waits indoors until the shared facade approach is free.
            for (const auto& [portal,centre] : portalPoints) {
                const auto explicitGate=explicitPortalGateRadii.find(portal);
                const double radius=explicitGate==explicitPortalGateRadii.end()
                    ? config.portalGateRadiusM : explicitGate->second;
                if (explicitGate!=explicitPortalGateRadii.end()) {
                    const auto& route=config.routes[data.route];
                    const auto& otherRoute=config.routes[tracks.at(otherId).route];
                    if (route.startPortal!=portal || (otherRoute.startPortal!=portal && otherRoute.endPortal!=portal)) continue;
                }
                if (std::hypot(point.x-centre.x,point.y-centre.y)<radius
                    && std::hypot(other.position.x-centre.x,other.position.y-centre.y)<radius)
                    available=false;
            }
        }
        if (!available) { ++diagnostics.admissionWaitSteps; continue; }
        state.state=RuntimeTrack::State::Active; state.position=point;
        state.velocity={0,0}; state.admittedAtMs=nowMs;
        ++diagnostics.realizedStarts;
        const auto& route=config.routes[data.route];
        lifecycle.push_back({MappedEventKind::EpisodeStart,person.personId,id,route.id,route.startPortal,nowMs});
    }
}

void MappedScene::advanceCorridorStep(AggregationTime nextMs) {
    const double dt=static_cast<double>(nextMs-currentMs)/1000;
    const auto elapsed=nextMs-currentMs;
    std::vector<std::string> active;
    std::map<std::string,std::vector<Point>> reservations;
    std::map<std::string,std::string> gateOwner;
    for (const auto& [id,state] : runtime) if (state.state==RuntimeTrack::State::Active) {
        active.push_back(id); reservations.emplace(id,std::vector<Point>{state.position,state.position});
        for (const auto& [portal,centre] : portalPoints) {
            const auto explicitGate=explicitPortalGateRadii.find(portal);
            const auto& route=config.routes[tracks.at(id).route];
            if (explicitGate!=explicitPortalGateRadii.end() && route.startPortal!=portal && route.endPortal!=portal) continue;
            const double radius=explicitGate==explicitPortalGateRadii.end()?config.portalGateRadiusM:explicitGate->second;
            if (std::hypot(state.position.x-centre.x,state.position.y-centre.y)<radius-1e-6)
                gateOwner.emplace(portal,id);
        }
    }
    std::sort(active.begin(),active.end(),[&](const auto& a,const auto& b) {
        const auto& x=runtime.at(a);const auto& y=runtime.at(b);
        return x.admittedAtMs!=y.admittedAtMs ? x.admittedAtMs<y.admittedAtMs : a<b;
    });
    struct MergeAdmission {
        Point centre;
        std::string portal, owner;
        bool closing = false;
        std::set<std::string> throughGrants;
    };
    constexpr double mergeRadius=2.0;
    std::vector<MergeAdmission> mergeAdmissions;
    const auto desiredPath=[&](const std::string& id) {
        const auto& state=runtime.at(id);const auto& data=tracks.at(id);
        const auto& person=config.people[data.person];const auto& compiled=routeData[data.route];
        const auto& route=config.routes[data.route];
        const double end=std::min(compiled.length,state.progress+person.speedMps*dt);
        std::vector<Point> path{state.position};
        for (std::size_t i=1;i<compiled.cumulative.size();++i)
            if (compiled.cumulative[i]>state.progress && compiled.cumulative[i]<end) path.push_back(route.points[i]);
        path.push_back(visibleState(id,end,{0,0}).position);return path;
    };
    for (const auto& [portal,centre] : mergeGatePoints) {
        MergeAdmission gate{centre,portal,"",false,{}};
        auto& reservation=mergeReservations[portal];
        auto& requests=mergeRequests[portal];
        if (!reservation.owner.empty()) {
            const auto& owner=runtime.at(reservation.owner);
            const double radius=mergeRadius+config.people[tracks.at(reservation.owner).person].radiusM+config.clearanceM;
            const double distance=std::hypot(owner.position.x-centre.x,owner.position.y-centre.y);
            if (distance<radius-1e-6) reservation.entered=true;
            if (owner.state==RuntimeTrack::State::Finished || (reservation.entered && distance>radius+1e-6)) {
                requests.erase(reservation.owner);
                reservation=MergeReservation{};
            }
        }
        for (auto it=reservation.throughBatch.begin();it!=reservation.throughBatch.end();) {
            const auto& state=runtime.at(it->first);
            const double radius=mergeRadius+config.people[tracks.at(it->first).person].radiusM+config.clearanceM;
            const double distance=std::hypot(state.position.x-centre.x,state.position.y-centre.y);
            if (distance<radius-1e-6) it->second=true;
            if (state.state==RuntimeTrack::State::Finished || (it->second && distance>radius+1e-6)) {
                requests.erase(it->first);it=reservation.throughBatch.erase(it);
            } else ++it;
        }
        bool throughInside=false;
        for (const auto& id:active) {
            const auto& state=runtime.at(id);const auto& route=config.routes[tracks.at(id).route];
            const double radius=mergeRadius+config.people[tracks.at(id).person].radiusM+config.clearanceM;
            const bool inside=std::hypot(state.position.x-centre.x,state.position.y-centre.y)<radius-1e-6;
            if (route.startPortal!=portal && inside) {
                throughInside=true;
                if (!reservation.throughBatch.count(id)) requests.erase(id);
            } else if (pathDistance(desiredPath(id),{centre,centre})<radius+.001)
                requests.emplace(id,currentMs);
        }
        const auto none=std::make_pair(std::numeric_limits<AggregationTime>::max(),std::string{});
        auto exitRequest=none,throughRequest=none;
        for (auto it=requests.begin();it!=requests.end();) {
            if (runtime.at(it->first).state!=RuntimeTrack::State::Active) {it=requests.erase(it);continue;}
            const auto request=std::make_pair(it->second,it->first);
            if (config.routes[tracks.at(it->first).route].startPortal==portal) exitRequest=std::min(exitRequest,request);
            else throughRequest=std::min(throughRequest,request);
            ++it;
        }
        const bool exitWaiting=exitRequest!=none;
        if (reservation.owner.empty() && reservation.throughBatch.empty() && !throughInside && exitWaiting) {
            if (throughRequest<exitRequest) {
                // Serve the compatible through front that arrived first. New
                // requests cannot grow this batch and starve the waiting exit.
                for (const auto& [id,time]:requests)
                    if (config.routes[tracks.at(id).route].startPortal!=portal
                        && std::make_pair(time,id)<exitRequest) reservation.throughBatch.emplace(id,false);
            } else reservation.owner=exitRequest.second;
        }
        gate.owner=reservation.owner;
        for (const auto& [id,entered]:reservation.throughBatch) gate.throughGrants.insert(id);
        gate.closing=!gate.owner.empty() || !reservation.throughBatch.empty() || exitWaiting;
        mergeAdmissions.push_back(std::move(gate));
    }
    for (const auto& id : active) {
        auto& state=runtime.at(id); const auto& data=tracks.at(id);
        const auto& person=config.people[data.person]; const auto& compiled=routeData[data.route];
        const auto& route=config.routes[data.route];
        const double desired=std::min(compiled.length,state.progress+person.speedMps*dt);
        const auto pathTo=[&](double end) {
            std::vector<Point> path{state.position};
            for (std::size_t i=1;i<compiled.cumulative.size();++i)
                if (compiled.cumulative[i]>state.progress && compiled.cumulative[i]<end) path.push_back(route.points[i]);
            path.push_back(visibleState(id,end,{0,0}).position);return path;
        };
        bool mergeBlocked=false;
        const auto allowed=[&](double end) {
            const auto path=pathTo(end);
            for (const auto& gate:mergeAdmissions) {
                const double radius=mergeRadius+person.radiusM+config.clearanceM;
                if (pathDistance(path,{gate.centre,gate.centre})>=radius+1e-6) continue;
                const bool inside=std::hypot(state.position.x-gate.centre.x,state.position.y-gate.centre.y)<radius-1e-6;
                const bool exit=route.startPortal==gate.portal;
                if ((exit && gate.owner!=id) || (!exit && ((!gate.owner.empty())
                        || (gate.closing && !inside && !gate.throughGrants.count(id))))) {
                    mergeBlocked=true;return false;
                }
            }
            for (const auto& [otherId,otherPath] : reservations) {
                if (otherId==id) continue;
                const auto& otherPerson=config.people[tracks.at(otherId).person];
                if (pathDistance(path,otherPath)<person.radiusM+otherPerson.radiusM+config.clearanceM-1e-9) return false;
            }
            for (const auto& [portal,owner] : gateOwner) {
                if (owner==id) continue;
                const auto centre=portalPoints.at(portal);
                const auto explicitGate=explicitPortalGateRadii.find(portal);
                if (explicitGate!=explicitPortalGateRadii.end() && route.startPortal!=portal && route.endPortal!=portal) continue;
                const double radius=explicitGate==explicitPortalGateRadii.end()?config.portalGateRadiusM:explicitGate->second;
                if (pathDistance(path,{centre,centre})<radius+1e-6) return false;
            }
            return true;
        };
        double reached=desired;
        if (!allowed(reached)) {
            ++diagnostics.blockedMotionSteps;
            diagnostics.mergeAdmissionWaitSteps+=mergeBlocked;
            double low=state.progress,high=reached;
            for (int iteration=0;iteration<25;++iteration) {
                const double mid=(low+high)/2;
                if (allowed(mid)) low=mid;else high=mid;
            }
            reached=low;
        }
        if (reached-state.progress<1e-7) reached=state.progress;
        const auto path=pathTo(reached); const auto position=path.back();
        state.velocity={(position.x-state.position.x)/dt,(position.y-state.position.y)/dt};
        state.stoppedForMs=reached==state.progress ? state.stoppedForMs+elapsed : 0;
        diagnostics.maxConsecutiveStopMs=std::max(diagnostics.maxConsecutiveStopMs,state.stoppedForMs);
        state.progress=reached;state.position=position;reservations.at(id)=path;
        // Latch a realized crossing from the swept path as well as the next
        // step's position: a fast body may cross the entire resource in one
        // bounded substep and must still release ownership after clearing it.
        for (const auto& [portal,centre] : mergeGatePoints) {
            auto& reservation=mergeReservations[portal];
            const double radius=mergeRadius+person.radiusM+config.clearanceM;
            if (pathDistance(path,{centre,centre})<radius-1e-6) {
                if (reservation.owner==id) reservation.entered=true;
                const auto grant=reservation.throughBatch.find(id);
                if (grant!=reservation.throughBatch.end()) grant->second=true;
            }
        }
        for (const auto& [portal,centre] : portalPoints) {
            const auto explicitGate=explicitPortalGateRadii.find(portal);
            if (explicitGate!=explicitPortalGateRadii.end() && route.startPortal!=portal && route.endPortal!=portal) continue;
            const double radius=explicitGate==explicitPortalGateRadii.end()?config.portalGateRadiusM:explicitGate->second;
            if (pathDistance(path,{centre,centre})<radius-1e-6) gateOwner.emplace(portal,id);
        }
        if (compiled.length-reached<1e-9) {
            state.state=RuntimeTrack::State::Finished;state.arrivedAtMs=nextMs;
            ++diagnostics.realizedEnds;
            lifecycle.push_back({MappedEventKind::EpisodeEnd,person.personId,id,route.id,route.endPortal,nextMs});
        }
    }
    for (std::size_t i=0;i<active.size();++i) for (std::size_t j=i+1;j<active.size();++j) {
        const auto& a=runtime.at(active[i]);const auto& b=runtime.at(active[j]);
        if (a.state!=RuntimeTrack::State::Active || b.state!=RuntimeTrack::State::Active) continue;
        const double physical=config.people[tracks.at(active[i]).person].radiusM+config.people[tracks.at(active[j]).person].radiusM;
        if (std::hypot(a.position.x-b.position.x,a.position.y-b.position.y)<physical-1e-7) {
            ++diagnostics.overlapViolations;
            throw std::logic_error("Mapped corridor reservation allowed a physical body overlap");
        }
    }
    currentMs=nextMs;admitPending(currentMs);
}

void MappedScene::advanceTo(AggregationTime nowMs) {
    if (nowMs<0) throw std::invalid_argument("Mapped scene time cannot precede the simulation origin");
    if (config.motionMode==MappedMotionMode::Integration) return;
    if (nowMs % config.motionStepMs) throw std::invalid_argument("Mapped corridor queries must align with its fixed motion step");
    if (nowMs<currentMs) throw std::invalid_argument("Stateful mapped corridor time cannot move backwards");
    if (!runtimeInitialized) {admitPending(0);runtimeInitialized=true;}
    while (currentMs<nowMs) advanceCorridorStep(currentMs+std::min(config.motionStepMs,nowMs-currentMs));
}

MappedMotionDiagnostics MappedScene::motionDiagnostics() const {
    auto result=diagnostics;
    for (const auto& [id,state] : runtime) {
        result.pendingTracks+=state.state==RuntimeTrack::State::Pending;
        result.activeTracks+=state.state==RuntimeTrack::State::Active;
        result.activeStalledTracks+=state.state==RuntimeTrack::State::Active && state.stoppedForMs>=10000;
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
    if (config.motionMode==MappedMotionMode::CorridorFollowing) {
        const auto& state=runtime.at(trackId);
        if (state.state!=RuntimeTrack::State::Finished) throw std::logic_error("Mapped arrival has not been realized");
        return state.arrivedAtMs;
    }
    return found->second.endMs;
}

const std::string& MappedScene::privatePersonForTrack(const std::string& trackId) const {
    const auto found = tracks.find(trackId);
    if (found == tracks.end()) throw std::invalid_argument("Unknown mapped track identifier");
    return config.people[found->second.person].personId;
}

} // namespace ump
