#include "MappedScene.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <queue>
#include <tuple>
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

double polylineDistance(Point point, const std::vector<Point>& line) {
    return pathDistance({point,point},line);
}
bool samePoint(Point a, Point b) {
    return std::hypot(a.x-b.x,a.y-b.y)<1e-8;
}

// Ring boundaries are closed sets. A center exactly on an eroded boundary is
// allowed; an interval inside a hole is not. Segment validation splits at EVERY
// boundary crossing rather than relying on sampling, so thin walls and holes
// cannot be skipped by a long integration step or a grid diagonal.
int ringLocation(Point p, const std::vector<Point>& ring) {
    bool inside=false;
    for (std::size_t i=0,j=ring.size()-1;i<ring.size();j=i++) {
        const auto a=ring[j],b=ring[i];
        // A point closer than the existing boundary tolerance must lie inside
        // this padded edge box. Reject only distant boundary-distance work;
        // the original distance predicate and ray-crossing arithmetic below
        // still decide containment. Coordinate-scaled rounding slack keeps
        // near-corner/large-coordinate cases on the original exact path.
        const double padding=1e-8 + 64*std::numeric_limits<double>::epsilon()
            * (1 + std::abs(p.x) + std::abs(p.y) + std::abs(a.x)
                + std::abs(a.y) + std::abs(b.x) + std::abs(b.y));
        if (p.x>=std::min(a.x,b.x)-padding && p.x<=std::max(a.x,b.x)+padding
            && p.y>=std::min(a.y,b.y)-padding && p.y<=std::max(a.y,b.y)+padding
            && pointSegmentDistance(p,a,b)<1e-8) return 0;
        if ((a.y>p.y)!=(b.y>p.y)
            && p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x) inside=!inside;
    }
    return inside ? 1 : -1;
}
bool polygonContains(Point point,const MappedNavigationPolygon& polygon) {
    if (ringLocation(point,polygon.outer)<0) return false;
    for (const auto& hole:polygon.holes) if (ringLocation(point,hole)>0) return false;
    return true;
}
bool navigationContains(Point point,const std::vector<MappedNavigationPolygon>& polygons) {
    return std::any_of(polygons.begin(),polygons.end(),[&](const auto& polygon){return polygonContains(point,polygon);});
}
void segmentCuts(Point a,Point b,const std::vector<Point>& ring,std::vector<double>& cuts) {
    const Point r{b.x-a.x,b.y-a.y};
    const double length2=r.x*r.x+r.y*r.y;
    for (std::size_t i=0,j=ring.size()-1;i<ring.size();j=i++) {
        const Point c=ring[j],d=ring[i],s{d.x-c.x,d.y-c.y},q{c.x-a.x,c.y-a.y};
        const double denominator=r.x*s.y-r.y*s.x;
        if (std::abs(denominator)>1e-12) {
            const double t=(q.x*s.y-q.y*s.x)/denominator,u=(q.x*r.y-q.y*r.x)/denominator;
            if (t>0 && t<1 && u>=-1e-10 && u<=1+1e-10) cuts.push_back(t);
        } else if (std::abs(q.x*r.y-q.y*r.x)<1e-10 && length2>0) {
            for (const auto p:{c,d}) {
                const double t=((p.x-a.x)*r.x+(p.y-a.y)*r.y)/length2;
                if (t>0 && t<1) cuts.push_back(t);
            }
        }
    }
}
bool navigationSegment(Point a,Point b,const std::vector<MappedNavigationPolygon>& polygons) {
    if (!navigationContains(a,polygons) || !navigationContains(b,polygons)) return false;
    if (std::hypot(a.x-b.x,a.y-b.y)<1e-12) return true;
    std::vector<double> cuts{0,1};
    for (const auto& polygon:polygons) {
        segmentCuts(a,b,polygon.outer,cuts);
        for (const auto& hole:polygon.holes) segmentCuts(a,b,hole,cuts);
    }
    std::sort(cuts.begin(),cuts.end());
    for (std::size_t i=1;i<cuts.size();++i) {
        if (cuts[i]-cuts[i-1]<1e-12) continue;
        const double t=(cuts[i]+cuts[i-1])/2;
        if (!navigationContains({a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t},polygons)) return false;
    }
    return true;
}
void validateNavigationRing(std::vector<Point>& ring,double width,double height) {
    if (ring.size()>1 && std::hypot(ring.front().x-ring.back().x,ring.front().y-ring.back().y)<1e-10)
        ring.pop_back();
    if (ring.size()<3 || ring.size()>10000)
        throw std::invalid_argument("Navigation rings require 3..10000 distinct vertices");
    double twiceArea=0;
    for (std::size_t i=0;i<ring.size();++i) {
        const auto a=ring[i],b=ring[(i+1)%ring.size()];
        if (!finite(a) || a.x<0 || a.y<0 || a.x>width || a.y>height
            || std::hypot(a.x-b.x,a.y-b.y)<1e-9)
            throw std::invalid_argument("Navigation ring contains an invalid, out-of-domain or repeated adjacent point");
        twiceArea+=a.x*b.y-a.y*b.x;
        for (std::size_t j=i+2;j<ring.size();++j) {
            if (i==0 && j+1==ring.size()) continue;
            if (segmentDistance(a,b,ring[j],ring[(j+1)%ring.size()])<1e-9)
                throw std::invalid_argument("Navigation ring must be simple, without crossing or touching nonadjacent edges");
        }
    }
    if (std::abs(twiceArea)<1e-8) throw std::invalid_argument("Navigation ring has zero area");
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
    if (config.motionMode==MappedMotionMode::LocalNavigation) {
        auto& navigation=config.navigation;
        const double cellsX=std::ceil(config.width/navigation.gridResolutionM)+1;
        const double cellsY=std::ceil(config.height/navigation.gridResolutionM)+1;
        if (navigation.allowedCenterPolygons.empty() || navigation.allowedCenterPolygons.size()>1024
            || !std::isfinite(navigation.gridResolutionM) || navigation.gridResolutionM<.05
            || !std::isfinite(navigation.centerClearanceM) || navigation.centerClearanceM<=0
            || !std::isfinite(cellsX*cellsY) || cellsX*cellsY>1000000
            || navigation.maxReplanNodes==0 || navigation.maxReplanNodes>250000
            || navigation.replanAfterMs<=0 || navigation.replanIntervalMs<=0)
            throw std::invalid_argument("Local navigation requires bounded center-safe geometry and positive bounded search settings");
        for (auto& polygon:navigation.allowedCenterPolygons) {
            validateNavigationRing(polygon.outer,config.width,config.height);
            for (auto& hole:polygon.holes) {
                validateNavigationRing(hole,config.width,config.height);
                for (const auto point:hole) if (ringLocation(point,polygon.outer)!=1)
                    throw std::invalid_argument("Navigation hole must lie strictly inside its outer ring");
                for (std::size_t i=0;i<hole.size();++i)
                    for (std::size_t j=0;j<polygon.outer.size();++j)
                        if (segmentDistance(hole[i],hole[(i+1)%hole.size()],polygon.outer[j],
                                polygon.outer[(j+1)%polygon.outer.size()])<1e-9)
                            throw std::invalid_argument("Navigation hole crosses its outer ring");
            }
            for (std::size_t i=0;i<polygon.holes.size();++i)
                for (std::size_t j=i+1;j<polygon.holes.size();++j) {
                    const auto& a=polygon.holes[i];const auto& b=polygon.holes[j];
                    if (ringLocation(a.front(),b)>=0 || ringLocation(b.front(),a)>=0)
                        throw std::invalid_argument("Navigation holes must not overlap or nest");
                    for (std::size_t x=0;x<a.size();++x) for (std::size_t y=0;y<b.size();++y)
                        if (segmentDistance(a[x],a[(x+1)%a.size()],b[y],b[(y+1)%b.size()])<1e-9)
                            throw std::invalid_argument("Navigation holes must not intersect");
                }
        }
    }
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
        if (config.motionMode==MappedMotionMode::LocalNavigation)
            for (std::size_t segment=1;segment<route.points.size();++segment)
                if (!navigationSegmentAllowed(route.points[segment-1],route.points[segment],&route))
                    throw std::invalid_argument("Local-navigation route leaves its center-safe polygon union");
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

    // Passage resources are explicit opt-in movement metadata. With no resources
    // this compilation and every run-time guard below are empty (legacy path).
    if (!config.navigation.narrowPassages.empty() && config.motionMode!=MappedMotionMode::LocalNavigation)
        throw std::invalid_argument("Narrow passages require local navigation");
    double largestPassageBody=0;
    for (const auto& person:config.people) largestPassageBody=std::max(largestPassageBody,person.radiusM);
    if (config.navigation.narrowPassages.size()>64)
        throw std::invalid_argument("At most 64 explicit narrow passages are supported");
    for (std::size_t index=0;index<config.navigation.narrowPassages.size();++index) {
        const auto& passage=config.navigation.narrowPassages[index];
        identifier(passage.id,"passage identifier");
        if (!identifiers.insert(passage.id).second || passage.centerline.size()<2 || passage.centerline.size()>128
            || !std::isfinite(passage.protectionRadiusM)
            || passage.protectionRadiusM<2*largestPassageBody+config.clearanceM+.05
            || passage.maxBatchSize==0 || passage.maxBatchSize>64)
            throw std::invalid_argument("Passage requires unique ID, bounded centerline/batch and body-clear protected apron");
        for (std::size_t i=0;i<passage.centerline.size();++i) {
            const auto point=passage.centerline[i];
            if (!finite(point) || !navigationContains(point,config.navigation.allowedCenterPolygons)
                || (i && (samePoint(point,passage.centerline[i-1])
                    || !navigationSegmentAllowed(passage.centerline[i-1],point))))
                throw std::invalid_argument("Passage centerline must be nondegenerate and center-safe");
        }
        for (const bool forward:{true,false}) {
            const auto& holding=forward?passage.holdingPointsA:passage.holdingPointsB;
            const auto ownEnd=forward?passage.centerline.front():passage.centerline.back();
            const auto farEnd=forward?passage.centerline.back():passage.centerline.front();
            if (holding.empty() || holding.size()>256)
                throw std::invalid_argument("Passage needs 1..256 holding points on each side");
            for (std::size_t i=0;i<holding.size();++i) {
                if (!finite(holding[i]) || !navigationContains(holding[i],config.navigation.allowedCenterPolygons)
                    || polylineDistance(holding[i],passage.centerline)<passage.protectionRadiusM+.05
                    || !navigationSegmentAllowed(holding[i],ownEnd)
                    || std::hypot(holding[i].x-ownEnd.x,holding[i].y-ownEnd.y)
                        <=passage.protectionRadiusM+2*largestPassageBody+config.clearanceM+.05
                    || std::hypot(holding[i].x-ownEnd.x,holding[i].y-ownEnd.y)
                        >=std::hypot(holding[i].x-farEnd.x,holding[i].y-farEnd.y))
                    throw std::invalid_argument("Passage holding points need reachable own-side positions and body-clear exits");
                for (std::size_t j=0;j<i;++j)
                    if (std::hypot(holding[i].x-holding[j].x,holding[i].y-holding[j].y)
                            <2*largestPassageBody+config.clearanceM+.05)
                        throw std::invalid_argument("Passage holding points need body-clear spacing");
            }
        }
        for (std::size_t previous=0;previous<index;++previous)
            if (pathDistance(passage.centerline,config.navigation.narrowPassages[previous].centerline)
                    <passage.protectionRadiusM+config.navigation.narrowPassages[previous].protectionRadiusM)
                throw std::invalid_argument("Protected passage resources must not overlap");
        for (std::size_t routeIndex=0;routeIndex<config.routes.size();++routeIndex) {
            const auto& points=config.routes[routeIndex].points;
            if (polylineDistance(points.front(),passage.centerline)<passage.protectionRadiusM
                || polylineDistance(points.back(),passage.centerline)<passage.protectionRadiusM)
                throw std::invalid_argument("Route endpoints must be outside protected passages");
            bool found=false;
            for (std::size_t begin=1;begin+passage.centerline.size()<points.size();++begin)
                for (const bool forward:{true,false}) {
                    bool match=true;
                    for (std::size_t k=0;k<passage.centerline.size();++k)
                        match=match && samePoint(points[begin+k],passage.centerline[forward?k:passage.centerline.size()-1-k]);
                    if (!match) continue;
                    if (found) throw std::invalid_argument("A route may traverse a passage only once");
                    routePassages[routeIndex].push_back({index,begin,begin+passage.centerline.size()-1,forward});
                    found=true;
                }
            if (!found && pathDistance(points,passage.centerline)<passage.protectionRadiusM-1e-8)
                throw std::invalid_argument("A route touching a protected passage must include its complete centerline");
        }
        for (const auto& portal:config.portals)
            if (polylineDistance(portal.point,passage.centerline)<passage.protectionRadiusM+7.5)
                throw std::invalid_argument("Door and passage waiting resources must have separate approaches");
        navigationPassages.emplace_back();
    }
    for (auto& [route,passages]:routePassages)
        std::sort(passages.begin(),passages.end(),[](const auto& a,const auto& b){return a.entryWaypoint<b.entryWaypoint;});
    for (std::size_t index=0;index<navigationPassages.size();++index) {
        std::size_t forward=0,reverse=0;
        for (const auto& person:config.people) for (const auto& episode:person.episodes) {
            const auto route=routeIndices.find(episode.routeId);
            if (route==routeIndices.end()) continue; // Existing identifier validation follows below.
            for (const auto& traversal:routePassages[route->second]) if (traversal.passage==index)
                (traversal.forward?forward:reverse)++;
        }
        const auto& passage=config.navigation.narrowPassages[index];
        if (forward>passage.holdingPointsA.size() || reverse>passage.holdingPointsB.size())
            throw std::invalid_argument("Finite passage cohort exceeds declared holding capacity on one side");
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

    if (config.motionMode==MappedMotionMode::LocalNavigation) {
        for (const auto& [id,portal]:declaredPortals) {
            Point normal{portal->facadeEnd.y-portal->facadeStart.y,
                portal->facadeStart.x-portal->facadeEnd.x};
            const double length=std::hypot(normal.x,normal.y);
            normal.x/=length;normal.y/=length;
            Point positive{portal->point.x+normal.x*1.5,portal->point.y+normal.y*1.5};
            Point negative{portal->point.x-normal.x*1.5,portal->point.y-normal.y*1.5};
            if (!navigationSegmentAllowed(portal->point,positive)) {
                if (!navigationSegmentAllowed(portal->point,negative))
                    throw std::invalid_argument("Local-navigation door needs a clear 1.5m perpendicular public approach");
                positive=negative;
            }
            navigationDoors.emplace(id,NavigationDoor{positive,{},{},{}});
            for(const auto& route:config.routes) {
                std::optional<Point> approach;
                if(route.startPortal==id) approach=route.points[1];
                if(route.endPortal==id) approach=route.points[route.points.size()-2];
                if(!approach) continue;
                const double dx=approach->x-portal->point.x,dy=approach->y-portal->point.y;
                const double distance=std::hypot(dx,dy);
                const double tangent=dx*(portal->facadeEnd.x-portal->facadeStart.x)
                    +dy*(portal->facadeEnd.y-portal->facadeStart.y);
                if(distance<config.navigation.centerClearanceM-1e-9
                    || std::abs(tangent)>1e-7*length
                    || dx*(positive.x-portal->point.x)+dy*(positive.y-portal->point.y)<=0)
                    throw std::invalid_argument("Local-navigation door routes need a perpendicular, outward, body-clearance-length approach");
            }
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
        if (config.motionMode==MappedMotionMode::LocalNavigation
            && person.radiusM+config.clearanceM>config.navigation.centerClearanceM+1e-10)
            throw std::invalid_argument("Local-navigation center geometry clearance is insufficient for a configured body");
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
                    || config.motionMode == MappedMotionMode::Integration))
                throw std::invalid_argument("Relative indoor gaps require a preceding corridor episode");
            if (config.motionMode != MappedMotionMode::Integration && e && !episode.afterPreviousMs)
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
                        || nextDoor->second->buildingId!=previousDoor->second->buildingId
                        || (config.motionMode==MappedMotionMode::LocalNavigation
                            && referencedRoute.startPortal!=previousRoute.endPortal))
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
    if (config.motionMode != MappedMotionMode::Integration) advanceTo(0);
}

std::vector<MappedVisibleTrack> MappedScene::frameAt(AggregationTime nowMs) const {
    if (nowMs < 0) throw std::invalid_argument("Mapped scene time cannot precede the simulation origin");
    std::vector<MappedVisibleTrack> result;
    if (config.motionMode != MappedMotionMode::Integration) {
        if (nowMs != currentMs) throw std::invalid_argument("Advance corridor motion before reading its current frame");
        for (const auto& [id,state] : runtime) if (state.state == RuntimeTrack::State::Active) {
            if (config.motionMode==MappedMotionMode::LocalNavigation) {
                const auto& data=tracks.at(id);
                result.push_back({id,config.people[data.person].type,config.routes[data.route].id,
                    state.position,state.velocity,static_cast<int>(state.navigationWaypoint)});
            } else result.push_back(visibleState(id,state.progress,state.velocity));
        }
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
    if (config.motionMode==MappedMotionMode::LocalNavigation) updateNavigationDoors(nowMs);
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
        for (std::size_t i=0;i<navigationPassages.size();++i)
            if (!navigationPassages[i].granted.count(id)
                && polylineDistance(point,config.navigation.narrowPassages[i].centerline)
                    <config.navigation.narrowPassages[i].protectionRadiusM) available=false;
        if (config.motionMode==MappedMotionMode::LocalNavigation) {
            const auto door=navigationDoors.find(config.routes[data.route].startPortal);
            if (door!=navigationDoors.end() && door->second.owner!=id) {
                ++diagnostics.admissionWaitSteps;continue;
            }
        }
        for (const auto& [otherId,other] : runtime) {
            if (other.state!=RuntimeTrack::State::Active) continue;
            const auto& otherPerson=config.people[tracks.at(otherId).person];
            if (std::hypot(point.x-other.position.x,point.y-other.position.y)
                    <person.radiusM+otherPerson.radiusM+config.clearanceM-1e-9) available=false;
            if (config.motionMode==MappedMotionMode::LocalNavigation) continue;
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

bool MappedScene::navigationSegmentAllowed(Point from,Point to,const MappedRoute* route) const {
    if (!navigationSegment(from,to,config.navigation.allowedCenterPolygons)) return false;
    if (!route) return true;
    // The shared polygon union contains short facade throats for every door.
    // Only a track explicitly entering/leaving that door may use its exception
    // to the otherwise body-eroded facade clearance. Incidental passers cannot
    // cut through another shop's strip while steering or replanning.
    for (const auto& portal:config.portals) {
        if (route->startPortal==portal.id || route->endPortal==portal.id) continue;
        const double length=std::hypot(portal.facadeEnd.x-portal.facadeStart.x,
            portal.facadeEnd.y-portal.facadeStart.y);
        const Point tangent{(portal.facadeEnd.x-portal.facadeStart.x)/length,
            (portal.facadeEnd.y-portal.facadeStart.y)/length};
        const Point normal{-tangent.y,tangent.x};
        const double halfWidth=std::max(portal.widthM/2,config.navigation.centerClearanceM+.15);
        const double depth=config.navigation.centerClearanceM-1e-7;
        std::vector<Point> forbidden;
        for (const auto offsets:{Point{-halfWidth,-depth},Point{halfWidth,-depth},
                Point{halfWidth,depth},Point{-halfWidth,depth}})
            forbidden.push_back({portal.point.x+tangent.x*offsets.x+normal.x*offsets.y,
                portal.point.y+tangent.y*offsets.x+normal.y*offsets.y});
        if (ringLocation(from,forbidden)>0 || ringLocation(to,forbidden)>0) return false;
        std::vector<double> cuts{0,1};segmentCuts(from,to,forbidden,cuts);std::sort(cuts.begin(),cuts.end());
        for (std::size_t i=1;i<cuts.size();++i) {
            const double t=(cuts[i]+cuts[i-1])/2;
            if (ringLocation({from.x+(to.x-from.x)*t,from.y+(to.y-from.y)*t},forbidden)>0) return false;
        }
    }
    return true;
}

bool MappedScene::replanNavigation(const std::string& id,Point goal) {
    auto& state=runtime.at(id);
    state.lastReplanMs=currentMs;
    ++diagnostics.navigationReplans;
    const auto& settings=config.navigation;
    const double resolution=settings.gridResolutionM;
    const std::size_t columns=static_cast<std::size_t>(std::ceil(config.width/resolution))+1;
    const std::size_t rows=static_cast<std::size_t>(std::ceil(config.height/resolution))+1;
    const std::size_t count=columns*rows;
    const auto point=[&](std::size_t node) {
        return Point{std::min(config.width,(node%columns)*resolution),
            std::min(config.height,(node/columns)*resolution)};
    };
    const auto& person=config.people[tracks.at(id).person];
    // Bounded static-grid replanning treats other CURRENT bodies as obstacles.
    // This is a temporary geometric detour, not a prediction or a global crowd
    // liveness guarantee. Exact per-step reservations remain authoritative.
    const auto clear=[&](Point from,Point to) {
        if (!navigationSegmentAllowed(from,to,&config.routes[tracks.at(id).route])) return false;
        if (!passageSegmentAllowed(id,from,to)) return false;
        for (const auto& [otherId,other]:runtime) {
            if (otherId==id || other.state!=RuntimeTrack::State::Active) continue;
            const auto radius=person.radiusM+config.people[tracks.at(otherId).person].radiusM+config.clearanceM;
            // A currently legal close formation must still be able to
            // attach to the search graph. Adding an unconditional extra buffer
            // here previously made every start edge impossible near queues.
            if (pointSegmentDistance(other.position,from,to)<radius-1e-8) return false;
        }
        return true;
    };
    std::vector<double> cost(count,std::numeric_limits<double>::infinity());
    std::vector<std::int64_t> parent(count,-2);
    std::vector<bool> closed(count,false);
    using Work=std::tuple<double,double,std::size_t>;
    std::priority_queue<Work,std::vector<Work>,std::greater<Work>> queue;
    const auto startColumn=static_cast<std::int64_t>(std::llround(state.position.x/resolution));
    const auto startRow=static_cast<std::int64_t>(std::llround(state.position.y/resolution));
    for (std::int64_t y=startRow-2;y<=startRow+2;++y) for (std::int64_t x=startColumn-2;x<=startColumn+2;++x) {
        if (x<0 || y<0 || x>=static_cast<std::int64_t>(columns) || y>=static_cast<std::int64_t>(rows)) continue;
        const auto node=static_cast<std::size_t>(y)*columns+static_cast<std::size_t>(x);
        const auto p=point(node);
        if (!clear(state.position,p)) continue;
        cost[node]=std::hypot(state.position.x-p.x,state.position.y-p.y);
        parent[node]=-1;
        queue.emplace(cost[node]+std::hypot(p.x-goal.x,p.y-goal.y),cost[node],node);
    }
    std::size_t expanded=0,found=count;
    while (!queue.empty() && expanded<settings.maxReplanNodes) {
        const auto [estimate,travelled,node]=queue.top();queue.pop();
        if (closed[node] || travelled>cost[node]+1e-10) continue;
        closed[node]=true;++expanded;
        const auto p=point(node);
        if (std::hypot(p.x-goal.x,p.y-goal.y)<=resolution*2.1 && clear(p,goal)) {found=node;break;}
        const auto x=static_cast<std::int64_t>(node%columns),y=static_cast<std::int64_t>(node/columns);
        for (std::int64_t dy=-1;dy<=1;++dy) for (std::int64_t dx=-1;dx<=1;++dx) {
            if (!dx && !dy) continue;
            const auto nx=x+dx,ny=y+dy;
            if (nx<0 || ny<0 || nx>=static_cast<std::int64_t>(columns) || ny>=static_cast<std::int64_t>(rows)) continue;
            const auto next=static_cast<std::size_t>(ny)*columns+static_cast<std::size_t>(nx);
            if (closed[next]) continue;
            const auto q=point(next);
            const auto nextCost=travelled+std::hypot(p.x-q.x,p.y-q.y);
            if (nextCost+1e-10>=cost[next] || !clear(p,q)) continue;
            cost[next]=nextCost;parent[next]=static_cast<std::int64_t>(node);
            queue.emplace(nextCost+std::hypot(q.x-goal.x,q.y-goal.y),nextCost,next);
        }
    }
    diagnostics.navigationMaxSearchNodes=std::max(diagnostics.navigationMaxSearchNodes,expanded);
    if (found==count) {++diagnostics.navigationReplanFailures;return false;}
    std::vector<Point> reversed{goal};
    for (std::int64_t node=static_cast<std::int64_t>(found);node>=0;node=parent[static_cast<std::size_t>(node)])
        reversed.push_back(point(static_cast<std::size_t>(node)));
    std::reverse(reversed.begin(),reversed.end());
    state.detour.clear();
    Point from=state.position;
    for (std::size_t i=0;i<reversed.size();) {
        // Exact visibility simplification preserves holes and obstacle clearance.
        std::size_t furthest=i;
        for (std::size_t j=i+1;j<reversed.size();++j) {
            if (clear(from,reversed[j])) furthest=j; else break;
        }
        const auto next=reversed[furthest];
        if (std::hypot(next.x-from.x,next.y-from.y)>1e-7) {state.detour.push_back(next);from=next;}
        i=furthest+1;
    }
    state.detourWaypoint=0;
    return !state.detour.empty();
}

void MappedScene::updateNavigationDoors(AggregationTime nowMs) {
    double largestRadius=0;
    for (const auto& person:config.people) largestRadius=std::max(largestRadius,person.radiusM);
    for (auto& [portalId,door]:navigationDoors) {
        const auto portal=portalPoints.at(portalId);
        if (!door.owner.empty()) {
            const auto& owner=runtime.at(door.owner);
            const auto& route=config.routes[tracks.at(door.owner).route];
            const auto& person=config.people[tracks.at(door.owner).person];
            const bool cleared=owner.state==RuntimeTrack::State::Finished
                || (route.startPortal==portalId && owner.state==RuntimeTrack::State::Active
                    && pointSegmentDistance(owner.position,portal,door.approach)>person.radiusM+largestRadius+config.clearanceM+.15
                    && std::hypot(owner.position.x-portal.x,owner.position.y-portal.y)>2.0);
            if (cleared) {door.requests.erase(door.owner);door.waitingPoints.erase(door.owner);door.owner.clear();}
        }
        for (const auto& [id,state]:runtime) {
            const auto& data=tracks.at(id);const auto& person=config.people[data.person];
            const auto& route=config.routes[data.route];const auto& episode=person.episodes[data.episode];
            if (state.state==RuntimeTrack::State::Active && route.endPortal==portalId
                && std::hypot(state.position.x-portal.x,state.position.y-portal.y)<4.5)
                door.requests.emplace(id,nowMs);
            if (state.state!=RuntimeTrack::State::Pending || route.startPortal!=portalId) continue;
            AggregationTime ready=episode.startMs;
            if (episode.afterPreviousMs) {
                const auto& previous=runtime.at(person.episodes[data.episode-1].trackId);
                if (previous.state!=RuntimeTrack::State::Finished) continue;
                if (previous.arrivedAtMs>std::numeric_limits<AggregationTime>::max()-*episode.afterPreviousMs)
                    throw std::overflow_error("Realized mapped return exceeds time range");
                ready=std::max(ready,previous.arrivedAtMs+*episode.afterPreviousMs);
            }
            if (ready<=nowMs) door.requests.emplace(id,ready);
        }
        for (auto it=door.requests.begin();it!=door.requests.end();) {
            if (runtime.at(it->first).state==RuntimeTrack::State::Finished) {
                door.waitingPoints.erase(it->first);it=door.requests.erase(it);
            } else ++it;
        }
        if (door.owner.empty() && !door.requests.empty()) {
            const auto next=std::min_element(door.requests.begin(),door.requests.end(),
                [](const auto& a,const auto& b){return std::tie(a.second,a.first)<std::tie(b.second,b.first);});
            door.owner=next->first;door.waitingPoints.erase(door.owner);
        }
        const double nx=(door.approach.x-portal.x)/1.5,ny=(door.approach.y-portal.y)/1.5;
        for (const auto& [id,requested]:door.requests) {
            if (id==door.owner || runtime.at(id).state!=RuntimeTrack::State::Active
                || door.waitingPoints.count(id)) continue;
            const auto& state=runtime.at(id);const auto& person=config.people[tracks.at(id).person];
            const double required=person.radiusM+largestRadius+config.clearanceM+.3;
            double best=std::numeric_limits<double>::infinity();Point chosen=state.position;
            bool found=false;
            // A deterministic set of public-space waiting positions around the
            // approach mouth, rather than an exclusive 3m entrance disk. These
            // are temporary goals, not teleports or pre-scripted entry routes.
            for (double distance:{2.5,3.25,4.0,5.0,6.0,7.0})
                for (double angle:{.7853981634,-.7853981634,1.0471975512,-1.0471975512,
                        .5235987756,-.5235987756,0.0,1.5707963268,-1.5707963268}) {
                    const double cosine=std::cos(angle),sine=std::sin(angle);
                    const Point point{portal.x+distance*(nx*cosine-ny*sine),
                        portal.y+distance*(ny*cosine+nx*sine)};
                    if (!navigationSegmentAllowed(point,point,&config.routes[tracks.at(id).route])
                        || pointSegmentDistance(point,portal,door.approach)<required) continue;
                    bool clear=true;
                    for (const auto& [otherId,other]:door.waitingPoints) {
                        const double radius=person.radiusM+config.people[tracks.at(otherId).person].radiusM+config.clearanceM+.15;
                        if (std::hypot(point.x-other.x,point.y-other.y)<radius) {clear=false;break;}
                    }
                    if (!clear) continue;
                    const double score=std::hypot(state.position.x-point.x,state.position.y-point.y)
                        +(navigationSegmentAllowed(state.position,point,&config.routes[tracks.at(id).route])?0:10);
                    if (score<best) {best=score;chosen=point;found=true;}
                }
            if (found) door.waitingPoints.emplace(id,chosen);
        }
    }
}

const MappedScene::PassageTraversal* MappedScene::pendingPassage(const std::string& id) const {
    const auto found=routePassages.find(tracks.at(id).route);
    if (found==routePassages.end()) return nullptr;
    for (const auto& traversal:found->second)
        if (!navigationPassages[traversal.passage].completed.count(id)) return &traversal;
    return nullptr;
}

bool MappedScene::passageEntryAllowed(const std::string& id) const {
    const auto* traversal=pendingPassage(id);
    if (!traversal) return false;
    const auto& resource=navigationPassages[traversal->passage];
    if (!resource.granted.count(id)) return false;
    const auto& state=runtime.at(id);
    if (state.navigationWaypoint>traversal->entryWaypoint) return true;
    const auto& request=resource.requests.at(id);
    const auto entry=config.routes[tracks.at(id).route].points[traversal->entryWaypoint];
    const auto radius=config.people[tracks.at(id).person].radiusM;
    // A batch shares a direction, not the same entry target simultaneously.
    // Let the preceding body clear the mouth before the next approaches it.
    for (const auto& [other,entered]:resource.granted) {
        if (other==id) continue;
        const auto& previous=resource.requests.at(other);
        if (std::tie(previous.atMs,other)>=std::tie(request.atMs,id)) continue;
        const auto* preceding=pendingPassage(other);const auto& body=runtime.at(other);
        const double clearance=radius+config.people[tracks.at(other).person].radiusM+config.clearanceM+.2;
        if (preceding && (body.navigationWaypoint<=preceding->entryWaypoint
                || std::hypot(body.position.x-entry.x,body.position.y-entry.y)<clearance)) return false;
    }
    return true;
}

bool MappedScene::passageSegmentAllowed(const std::string& id, Point from, Point to) const {
    for (std::size_t index=0;index<navigationPassages.size();++index) {
        if (navigationPassages[index].granted.count(id) && passageEntryAllowed(id)) continue;
        const auto& passage=config.navigation.narrowPassages[index];
        const double before=polylineDistance(from,passage.centerline);
        if (before<passage.protectionRadiusM-1e-7) {
            if (polylineDistance(to,passage.centerline)<before+1e-7) return false;
        } else if (pathDistance({from,to},passage.centerline)<passage.protectionRadiusM-1e-9) return false;
    }
    return true;
}

void MappedScene::updateNavigationPassages(AggregationTime nowMs) {
    for (std::size_t index=0;index<navigationPassages.size();++index) {
        auto& resource=navigationPassages[index];const auto& passage=config.navigation.narrowPassages[index];
        for (auto it=resource.granted.begin();it!=resource.granted.end();) {
            const auto& state=runtime.at(it->first);const auto* traversal=pendingPassage(it->first);
            // Never relinquish an occupied resource on a timer. In particular,
            // reaching the last spine point does not yet clear the exit apron.
            if (state.state==RuntimeTrack::State::Finished || (it->second && traversal
                    && state.navigationWaypoint>traversal->exitWaypoint
                    && polylineDistance(state.position,passage.centerline)>passage.protectionRadiusM+1e-7)) {
                resource.completed.insert(it->first);resource.requests.erase(it->first);
                resource.waitingPoints.erase(it->first);resource.staged.erase(it->first);it=resource.granted.erase(it);
                ++diagnostics.passageClearedTracks;
            } else ++it;
        }
        for (const auto& [id,state]:runtime) {
            if (state.state!=RuntimeTrack::State::Active) continue;
            const auto* traversal=pendingPassage(id);
            if (!traversal || traversal->passage!=index) continue;
            const auto entry=config.routes[tracks.at(id).route].points[traversal->entryWaypoint];
            if (std::hypot(entry.x-state.position.x,entry.y-state.position.y)<=8.0)
                resource.requests.emplace(id,NavigationPassage::Request{nowMs,traversal->forward});
        }
        for (const auto& [id,request]:resource.requests) {
            const auto* traversal=pendingPassage(id);
            const auto& state=runtime.at(id);
            if (passageEntryAllowed(id) && state.navigationWaypoint>traversal->entryWaypoint) {
                resource.waitingPoints.erase(id);continue;
            }
            diagnostics.maxPassageWaitMs=std::max(diagnostics.maxPassageWaitMs,nowMs-request.atMs);
            const auto existing=resource.waitingPoints.find(id);
            if (existing!=resource.waitingPoints.end()) {
                if (samePoint(state.position,existing->second)) resource.staged.insert(id);
                continue;
            }
            const auto& slots=request.forward?passage.holdingPointsA:passage.holdingPointsB;
            const auto& person=config.people[tracks.at(id).person];
            double best=std::numeric_limits<double>::infinity();std::optional<Point> chosen;
            for (const auto point:slots) {
                bool occupied=false;
                for (const auto& [other,held]:resource.waitingPoints) {
                    const auto radius=person.radiusM+config.people[tracks.at(other).person].radiusM+config.clearanceM+.05;
                    if (std::hypot(point.x-held.x,point.y-held.y)<radius) {occupied=true;break;}
                }
                if (occupied) continue;
                const auto entry=config.routes[tracks.at(id).route].points[traversal->entryWaypoint];
                // Fill from the mouth outwards. Nearest-current-position
                // assignment can place older requests behind later stationary
                // rows, preventing the next FIFO owner from reaching entry.
                const double score=100*std::hypot(point.x-entry.x,point.y-entry.y)
                    +std::hypot(point.x-state.position.x,point.y-state.position.y)
                    +(navigationSegmentAllowed(state.position,point)?0:20);
                if (score<best) {best=score;chosen=point;}
            }
            if (chosen) resource.waitingPoints.emplace(id,*chosen);
        }
        if (resource.granted.empty()) {
            std::vector<std::string> queue;
            for (const auto& [id,request]:resource.requests)
                if (resource.staged.count(id)) queue.push_back(id);
            std::sort(queue.begin(),queue.end(),[&](const auto& a,const auto& b){
                return std::tie(resource.requests.at(a).atMs,a)<std::tie(resource.requests.at(b).atMs,b);});
            if (queue.empty()) continue;
            const bool direction=resource.requests.at(queue.front()).forward;
            // Acquire only after physical staging. An unready older request
            // must not hold the passage while ready waiters block its approach.
            // Request age still orders the currently ready candidates.
            // Freeze this finite snapshot. Late arrivals cannot extend a batch
            // indefinitely while opposite demand waits for a clear passage.
            for (const auto& id:queue) if (resource.requests.at(id).forward==direction
                    && resource.granted.size()<passage.maxBatchSize) {
                resource.granted.emplace(id,false);
            }
            ++diagnostics.passageBatches;
        }
    }
}

void MappedScene::advanceNavigationStep(AggregationTime nextMs) {
    updateNavigationDoors(currentMs);
    updateNavigationPassages(currentMs);
    const auto elapsed=nextMs-currentMs;
    const double dt=static_cast<double>(elapsed)/1000;
    std::vector<std::string> active;
    std::map<std::string,std::vector<Point>> reservations;
    std::map<std::string,Point> oldPositions,oldVelocities;
    for (const auto& [id,state]:runtime) if (state.state==RuntimeTrack::State::Active) {
        active.push_back(id);reservations.emplace(id,std::vector<Point>{state.position,state.position});
        oldPositions.emplace(id,state.position);oldVelocities.emplace(id,state.velocity);
    }
    // Rotating opaque-track priority prevents a fixed lexicographic owner from
    // monopolizing every simultaneous conflict. Private person identifiers are
    // never consulted by the operational motion decisions.
    if (!active.empty()) std::rotate(active.begin(),active.begin()+
        static_cast<std::size_t>((currentMs/config.motionStepMs)%active.size()),active.end());
    for (const auto& id:active) {
        auto& state=runtime.at(id);const auto& data=tracks.at(id);
        const auto& person=config.people[data.person];const auto& route=config.routes[data.route];
        // Original guide points constrain static topology, not mandatory
        // revisits. After a detour or a doorway wait, a point behind the body
        // must not pull it backwards when a later guide is directly reachable.
        // Preserve the explicit final perpendicular doorway approach.
        const auto* passageTraversal=pendingPassage(id);
        bool waitingForPassage=false, followingPassage=false;
        if (passageTraversal) {
            const auto& resource=navigationPassages[passageTraversal->passage];
            waitingForPassage=resource.requests.count(id)
                && (!passageEntryAllowed(id) || !resource.staged.count(id));
            followingPassage=passageEntryAllowed(id) && state.navigationWaypoint>passageTraversal->entryWaypoint
                && state.navigationWaypoint<=passageTraversal->exitWaypoint;
        }
        std::size_t lastVisible=route.points.size()-1;
        if (passageTraversal && state.navigationWaypoint<=passageTraversal->exitWaypoint)
            lastVisible=state.navigationWaypoint<passageTraversal->entryWaypoint
                ? passageTraversal->entryWaypoint : state.navigationWaypoint;
        if (navigationDoors.count(route.endPortal) && state.navigationWaypoint+1<route.points.size())
            --lastVisible;
        const bool leavingThroat=navigationDoors.count(route.startPortal)
            && state.navigationWaypoint==1;
        if (!leavingThroat) for (std::size_t next=state.navigationWaypoint+1;next<=lastVisible;++next)
            if (navigationSegmentAllowed(state.position,route.points[next],&route)
                && passageSegmentAllowed(id,state.position,route.points[next])) {
                state.navigationWaypoint=next;state.detour.clear();state.detourWaypoint=0;
            }
        auto goal=route.points[state.navigationWaypoint];
        if (std::hypot(goal.x-state.position.x,goal.y-state.position.y)<1e-7
            && state.navigationWaypoint+1<route.points.size()) {
            ++state.navigationWaypoint;state.detour.clear();state.detourWaypoint=0;
            state.navigationBestGoalDistance=1e300;state.navigationNoProgressMs=0;
            goal=route.points[state.navigationWaypoint];
        }
        // Recompute after exact guide advancement: the first step leaving the
        // entry is already a lane step. One free-steering step can leave the
        // centerline at a tight corner and make its next straight chord invalid.
        if (passageTraversal) followingPassage=passageEntryAllowed(id)
            && state.navigationWaypoint>passageTraversal->entryWaypoint
            && state.navigationWaypoint<=passageTraversal->exitWaypoint;
        bool waitingForDoor=false;
        const auto door=navigationDoors.find(route.endPortal);
        if (door!=navigationDoors.end() && door->second.owner!=id) {
            const auto wait=door->second.waitingPoints.find(id);
            if (wait!=door->second.waitingPoints.end()) {goal=wait->second;waitingForDoor=true;}
        }
        if (waitingForPassage) {
            const auto& resource=navigationPassages[passageTraversal->passage];
            const auto wait=resource.waitingPoints.find(id);
            goal=wait==resource.waitingPoints.end()?state.position:wait->second;
            ++diagnostics.passageWaitSteps;
        }
        if (std::hypot(goal.x-state.navigationTarget.x,goal.y-state.navigationTarget.y)>1e-7) {
            state.navigationTarget=goal;state.navigationBestGoalDistance=1e300;
            state.navigationNoProgressMs=0;state.detour.clear();state.detourWaypoint=0;
        }
        const double remainingGoalDistance=std::hypot(goal.x-state.position.x,goal.y-state.position.y);
        if (remainingGoalDistance<state.navigationBestGoalDistance-std::min(.01,person.speedMps*dt*.1)) {
            state.navigationBestGoalDistance=remainingGoalDistance;state.navigationNoProgressMs=0;
        } else state.navigationNoProgressMs+=elapsed;
        if (!followingPassage && !(waitingForPassage && remainingGoalDistance<.15)
            && remainingGoalDistance>.1 && (state.stoppedForMs>=config.navigation.replanAfterMs
                || state.navigationNoProgressMs>=config.navigation.replanAfterMs)
            && (state.lastReplanMs<0 || currentMs-state.lastReplanMs>=config.navigation.replanIntervalMs))
            replanNavigation(id,goal);
        if (state.detourWaypoint<state.detour.size()) {
            if (std::hypot(state.detour[state.detourWaypoint].x-state.position.x,
                    state.detour[state.detourWaypoint].y-state.position.y)<1e-7) ++state.detourWaypoint;
            if (state.detourWaypoint<state.detour.size()) goal=state.detour[state.detourWaypoint];
        }
        const double gx=goal.x-state.position.x,gy=goal.y-state.position.y;
        const double distance=std::hypot(gx,gy),base=std::atan2(gy,gx);
        const double maximum=person.speedMps*dt;
        Point chosen=state.position;
        double best=std::numeric_limits<double>::infinity();
        const auto allowed=[&](Point to) {
            ++diagnostics.navigationCandidateChecks;
            if (!navigationSegmentAllowed(state.position,to,&route)) return false;
            for (const auto& [portalId,door]:navigationDoors) {
                if (door.owner==id || door.owner.empty()
                    || (route.startPortal!=portalId && route.endPortal!=portalId)) continue;
                const auto portal=portalPoints.at(portalId);
                double largestRadius=0;
                for(const auto& p:config.people) largestRadius=std::max(largestRadius,p.radiusM);
                const double required=person.radiusM+largestRadius+config.clearanceM+.05;
                const double before=pointSegmentDistance(state.position,portal,door.approach);
                const double after=pointSegmentDistance(to,portal,door.approach);
                if (before<required-1e-7) {
                    if (after<before+1e-7) return false;
                } else if (segmentDistance(state.position,to,portal,door.approach)<required-1e-9) return false;
            }
            const std::vector<Point> path{state.position,to};
            if (!passageSegmentAllowed(id,state.position,to)) return false;
            for (const auto& [otherId,otherPath]:reservations) {
                if (otherId==id) continue;
                const double radius=person.radiusM+config.people[tracks.at(otherId).person].radiusM+config.clearanceM;
                // Conservative swept disks: also reserves old positions of
                // not-yet-planned bodies. Safe, but can delay tight crossings.
                if (pathDistance(path,otherPath)<radius-1e-9) return false;
            }
            return true;
        };
        const auto consider=[&](Point to,double angularPenalty) {
            if (!allowed(to)) return;
            const Point velocity{(to.x-state.position.x)/dt,(to.y-state.position.y)/dt};
            const double speed=std::hypot(velocity.x,velocity.y);
            const double progress=distance-std::hypot(goal.x-to.x,goal.y-to.y);
            double score=angularPenalty+.6*(1-progress/std::max(maximum,1e-12))
                +.25*(1-speed/person.speedMps);
            const auto previous=oldVelocities.at(id);
            score+=.06*std::hypot(velocity.x-previous.x,velocity.y-previous.y)/person.speedMps;
            for (const auto& [otherId,otherPosition]:oldPositions) {
                if (otherId==id) continue;
                const auto otherVelocity=oldVelocities.at(otherId);
                const double rx=state.position.x-otherPosition.x,ry=state.position.y-otherPosition.y;
                if (rx*rx+ry*ry>49) continue;
                const double vx=velocity.x-otherVelocity.x,vy=velocity.y-otherVelocity.y;
                const double v2=vx*vx+vy*vy;
                const double closestAt=v2>1e-12?std::clamp(-(rx*vx+ry*vy)/v2,0.0,2.0):0;
                const double predicted=std::hypot(rx+vx*closestAt,ry+vy*closestAt);
                const double margin=person.radiusM+config.people[tracks.at(otherId).person].radiusM+config.clearanceM+.25;
                if (predicted<margin) score+=4*(1-predicted/margin)*(1-closestAt/2.5);
            }
            if (score<best-1e-10) {best=score;chosen=to;}
        };
        // Positive angles are right-hand deviations in our x-east/y-south map.
        // This shared geometric convention makes opposing agents choose
        // compatible passing sides without sharing hidden identities.
        const std::vector<double> angles{0,.2617993878,-.2617993878,.5235987756,-.5235987756,
            .7853981634,-.7853981634,1.0471975512,-1.0471975512,1.5707963268,-1.5707963268,
            2.0943951024,-2.0943951024,3.1415926536};
        for (double factor:{1.0,.5}) for (double angle:angles) {
            // The explicit nonpassing resource uses its audited guide as a
            // single-file lane. Free-space steering resumes after its exit.
            if (followingPassage && angle!=0) continue;
            const double travel=std::min(maximum*factor,distance);
            const Point to=angle==0 && distance<=maximum*factor ? goal : Point{
                state.position.x+std::cos(base+angle)*travel,state.position.y+std::sin(base+angle)*travel};
            consider(to,.18*std::abs(angle)+(angle<0?.025:0));
        }
        consider(state.position,.8);
        const double moved=std::hypot(chosen.x-state.position.x,chosen.y-state.position.y);
        if (moved<1e-7) {chosen=state.position;++diagnostics.blockedMotionSteps;}
        else if (pointSegmentDistance(chosen,state.position,goal)>1e-6) ++diagnostics.navigationSteeringSteps;
        state.velocity={(chosen.x-state.position.x)/dt,(chosen.y-state.position.y)/dt};
        state.stoppedForMs=moved<1e-7 && !((waitingForDoor && remainingGoalDistance<.1) || (waitingForPassage && remainingGoalDistance<.15))
            ? state.stoppedForMs+elapsed : 0;
        if ((waitingForDoor && remainingGoalDistance<.1) || (waitingForPassage && remainingGoalDistance<.15)) state.navigationNoProgressMs=0;
        if (passageTraversal) {
            auto& resource=navigationPassages[passageTraversal->passage];
            auto grant=resource.granted.find(id);
            if (grant!=resource.granted.end() && pathDistance({state.position,chosen},
                    config.navigation.narrowPassages[passageTraversal->passage].centerline)
                    <config.navigation.narrowPassages[passageTraversal->passage].protectionRadiusM+1e-7)
                grant->second=true;
        }
        diagnostics.maxConsecutiveStopMs=std::max(diagnostics.maxConsecutiveStopMs,state.stoppedForMs);
        reservations.at(id)={state.position,chosen};state.position=chosen;
        if (std::hypot(chosen.x-route.points.back().x,chosen.y-route.points.back().y)<1e-7
            && state.navigationWaypoint+1==route.points.size()) {
            state.state=RuntimeTrack::State::Finished;state.arrivedAtMs=nextMs;
            ++diagnostics.realizedEnds;
            lifecycle.push_back({MappedEventKind::EpisodeEnd,person.personId,id,route.id,route.endPortal,nextMs});
        }
    }
    for (std::size_t i=0;i<active.size();++i) for (std::size_t j=i+1;j<active.size();++j) {
        const auto& a=runtime.at(active[i]);const auto& b=runtime.at(active[j]);
        const double physical=config.people[tracks.at(active[i]).person].radiusM+config.people[tracks.at(active[j]).person].radiusM;
        if (std::hypot(a.position.x-b.position.x,a.position.y-b.position.y)<physical-1e-7) {
            ++diagnostics.overlapViolations;
            throw std::logic_error("Mapped local navigation allowed a physical body overlap");
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
    while (currentMs<nowMs) {
        const auto next=currentMs+std::min(config.motionStepMs,nowMs-currentMs);
        if (config.motionMode==MappedMotionMode::LocalNavigation) advanceNavigationStep(next);
        else advanceCorridorStep(next);
    }
}

MappedMotionDiagnostics MappedScene::motionDiagnostics() const {
    auto result=diagnostics;
    for (const auto& [id,state] : runtime) {
        result.pendingTracks+=state.state==RuntimeTrack::State::Pending;
        result.activeTracks+=state.state==RuntimeTrack::State::Active;
        result.activeStalledTracks+=state.state==RuntimeTrack::State::Active
            && (state.stoppedForMs>=10000 || (config.motionMode==MappedMotionMode::LocalNavigation
                && state.navigationNoProgressMs>=10000));
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
    if (config.motionMode!=MappedMotionMode::Integration) {
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
