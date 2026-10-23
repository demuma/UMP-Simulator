"""Bounded frozen-map facade access construction; no OSM edits or indoor inference.

This deliberately small fixture is not a general routing engine. A 1.25-m
navigation lattice and line-of-sight simplification connect checked facade
approaches to the domain boundary. Every final swept route is audited exactly.
"""
from __future__ import annotations

import heapq
import math

from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union
from shapely.prepared import prep

SIDE = 80
BODY_CLEARANCE_M = .55
PORTAL_EXCEPTION_M = .85


def _polygons(geom):
    if geom.geom_type == "Polygon":
        return [geom] if not geom.is_empty else []
    return [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon" and not g.is_empty]


def building_context(local):
    """Keep each original ground/building footprint separate, including roofs.

    Exterior and hole rings are clipped for display only. Synthetic doors use
    *original* exterior wall segments; a clip edge can never become a facade.
    """
    domain = box(0, 0, SIDE, SIDE)
    records = []
    for props, geom in local:
        if props["kind"] != "building" or not geom.intersects(domain):
            continue
        parts = _polygons(geom.intersection(domain))
        if not parts:
            continue
        tags = props.get("tags", {})
        records.append({"id": f"osm-{props['osm_type']}-{props['osm_id']}",
            "osm_type": props["osm_type"], "osm_id": props["osm_id"],
            "name": tags.get("name", f"Building {props['osm_type']} {props['osm_id']}"), "building_type": tags.get("building", "yes"),
            "polygons": [[[float(x), float(y)] for x, y in p.exterior.coords] for p in parts],
            "holes": [[[float(x), float(y)] for x, y in ring.coords]
                      for p in parts for ring in p.interiors]})
    return {"schema": "ump.building-access.v1",
            "bounds": {"x": 0, "y": 0, "width": SIDE, "height": SIDE},
            "buildings": sorted(records, key=lambda r: r["id"]), "portals": []}


class BoundedRouter:
    """Finite D6 lattice with exact swept-footprint edge checks."""
    def __init__(self, local, layers, extra_obstacle=None):
        self.domain = box(0, 0, SIDE, SIDE)
        buildings = unary_union([g for p, g in local if p["kind"] == "building"])
        self.forbidden = self.domain.difference(layers["walking"]).union(buildings)
        self.prepared = prep(self.forbidden)
        self.extra = extra_obstacle
        self.points = [(x*1.25, y*1.25) for y in range(65) for x in range(65)]
        self.valid = set(i for i, p in enumerate(self.points) if self.clear([p, p]))
        self.edge_cache = {}

    def clear(self, points):
        footprint = LineString(points).buffer(BODY_CLEARANCE_M).intersection(self.domain)
        if self.prepared.intersects(footprint) and self.forbidden.intersection(footprint).area > 1e-8:
            return False
        return self.extra is None or not self.extra.intersects(LineString(points))

    def route(self, start, goal):
        start, goal = tuple(start), tuple(goal)
        if self.clear([start, goal]):
            return [list(start), list(goal)]
        # Each custom endpoint is attached only to nearby lattice nodes. No
        # interior map geometry is invented when that local attachment fails.
        def neighbors_to(p):
            nearby = sorted(self.valid, key=lambda i: math.dist(p, self.points[i]))
            return [(i, math.dist(p, self.points[i])) for i in nearby
                    if math.dist(p, self.points[i]) <= 5 and self.clear([p, self.points[i]])]
        sources, targets = neighbors_to(start), dict(neighbors_to(goal))
        if not sources or not targets:
            raise ValueError("Facade approach cannot attach to bounded walking lattice")
        dist, previous, queue = {}, {}, []
        for node, value in sources:
            dist[node] = value
            heapq.heappush(queue, (value+math.dist(self.points[node], goal), value, node))
        reached = None
        while queue:
            _, value, node = heapq.heappop(queue)
            if value != dist.get(node):
                continue
            if node in targets:
                reached = node
                break
            x, y = node % 65, node // 65
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                nx, ny = x+dx, y+dy
                if not (0 <= nx <= 64 and 0 <= ny <= 64):
                    continue
                nxt = ny*65+nx
                if nxt not in self.valid:
                    continue
                key = min(node,nxt), max(node,nxt)
                if key not in self.edge_cache:
                    self.edge_cache[key] = self.clear([self.points[node], self.points[nxt]])
                if not self.edge_cache[key]:
                    continue
                proposal = value + math.dist(self.points[node], self.points[nxt])
                if proposal < dist.get(nxt, math.inf):
                    dist[nxt], previous[nxt] = proposal, node
                    heapq.heappush(queue, (proposal+math.dist(self.points[nxt], goal), proposal, nxt))
        if reached is None:
            raise ValueError("No checked walking route within frozen D6 lattice")
        chain = [reached]
        while chain[-1] in previous:
            chain.append(previous[chain[-1]])
        raw = [start] + [self.points[i] for i in reversed(chain)] + [goal]
        result, index = [list(raw[0])], 0
        while index < len(raw)-1:
            nxt = next(j for j in range(len(raw)-1,index,-1) if self.clear([raw[index], raw[j]]))
            if math.dist(result[-1], raw[nxt]) > 1e-9:
                result.append(list(raw[nxt]))
            index = nxt
        if len(result) > 64:
            raise ValueError("Bounded route exceeded 64-vertex fixture budget")
        return result


def facade_candidates(local, layers):
    """One reachable original-wall midpoint per ground building, ranked centrally."""
    domain = box(0,0,SIDE,SIDE)
    union = unary_union([g for p,g in local if p["kind"] == "building"])
    candidates, rejected = [], []
    for props, geom in sorted(local, key=lambda row:(row[0]["kind"],row[0]["osm_id"])):
        if props["kind"] != "building" or not geom.intersects(domain):
            continue
        tags = props.get("tags", {})
        bid = f"osm-{props['osm_type']}-{props['osm_id']}"
        if tags.get("building") == "roof" or tags.get("layer", "0") not in ("0", ""):
            rejected.append({"building_id":bid,"reason":"roof_or_non_ground_layer_not_an_indoor_destination"})
            continue
        options = []
        for polygon in _polygons(geom):
            coords = list(polygon.exterior.coords)
            for a,b in zip(coords,coords[1:]):
                segment = LineString([a,b]); length = segment.length
                midpoint = segment.interpolate(.5,normalized=True)
                if length < 2 or not domain.buffer(-1.8).covers(midpoint):
                    continue
                tangent = ((b[0]-a[0])/length,(b[1]-a[1])/length)
                for normal in [(-tangent[1],tangent[0]),(tangent[1],-tangent[0])]:
                    center = tuple(midpoint.coords)[0]
                    approach = (center[0]+normal[0]*1.5,center[1]+normal[1]*1.5)
                    if geom.covers(Point(approach)):
                        continue
                    exception = midpoint.buffer(PORTAL_EXCEPTION_M)
                    footprint = LineString([center,approach]).buffer(BODY_CLEARANCE_M).intersection(domain)
                    if footprint.difference(layers["walking"].union(exception)).area > 1e-8:
                        continue
                    if footprint.intersection(union.difference(exception)).area > 1e-8:
                        continue
                    options.append((midpoint.distance(Point(40,40)),-length,center,a,b,normal,tangent))
        if not options:
            rejected.append({"building_id":bid,"reason":"no_original_wall_midpoint_with_checked_outward_body_clearance"})
            continue
        _,_,center,a,b,normal,tangent = min(options)
        candidates.append({"id":f"facade-{props['osm_id']}","building_id":bid,"point":list(center),
            "facade":[list(a),list(b)],"width_m":1.2,"provenance":"synthetic",
            "_normal":normal,"_tangent":tangent})
    return sorted(candidates,key=lambda p:(math.dist(p["point"],[40,40]),p["id"])), rejected


def through_corridor_exclusion():
    """Reserve the complete existing through-flow envelope for this fixture.

    Access traffic stays outside both directions instead of relying on a local
    collision stop to resolve a shallow-angle/head-on crossing. The reference
    covers all four declared lanes plus .22m bounded individual/seed variation
    and two .55m conservative body/clearance radii. This is a fixture-specific
    geometric separation, not a general crossing-priority algorithm.
    """
    lanes=[]
    for intercept in [69.4,70.6,67.0,68.2]:
        points=[[x,intercept-.315*x+(intercept-68.8)/1.2*.6*math.sin(math.pi*x/80)]
                for x in range(0,81,10)]
        lanes.append(LineString(points).buffer(2*BODY_CLEARANCE_M+.25))
    return unary_union(lanes)


def build_access(local, layers, limit=2):
    """Two contrasting reachable destinations, separate incoming/outgoing paths.

    The fixture deliberately caps active destinations; all original buildings
    are still displayed and every excluded candidate has a stated reason.
    """
    context = building_context(local)
    candidates, rejected = facade_candidates(local,layers)
    through_exclusion = through_corridor_exclusion()
    router = BoundedRouter(local,layers,through_exclusion)
    routes = []
    for portal in candidates:
        if len(context["portals"]) >= limit:
            rejected.append({"building_id":portal["building_id"],"reason":"bounded_two_destination_fixture_not_selected"})
            continue
        center, normal, tangent = portal["point"],portal["_normal"],portal["_tangent"]
        # Separate approach branches by 1.6m; only the final throat converges.
        approaches = [[center[0]+1.5*normal[0]+sign*.8*tangent[0],
                       center[1]+1.5*normal[1]+sign*.8*tangent[1]] for sign in [-1,1]]
        # Select boundary points in left-to-right flow. A sufficiently wide
        # checked separation from the inbound path prevents a shared head-on
        # route segment. Boundary clipping of the circular body is intentional.
        found = None
        left = sorted([[0,y] for y in range(2,79,2)],key=lambda p:math.dist(p,approaches[0]))
        right = sorted([[80,y] for y in range(2,79,2)],key=lambda p:math.dist(p,approaches[1]))
        for source in left:
            try:
                incoming = router.route(source,approaches[0])+[list(center)]
            except ValueError:
                continue
            exclusion = LineString(incoming).buffer(2*BODY_CLEARANCE_M+.03).difference(Point(center).buffer(1.3))
            outgoing_router = BoundedRouter(local,layers,exclusion.union(through_exclusion))
            for destination in right:
                try:
                    outgoing = [list(center)]+outgoing_router.route(approaches[1],destination)
                    found = incoming,outgoing
                    break
                except ValueError:
                    continue
            if found:
                break
        if not found:
            rejected.append({"building_id":portal["building_id"],"reason":"no_separated_checked_boundary_access_pair"})
            continue
        public = {key:value for key,value in portal.items() if not key.startswith("_")}
        context["portals"].append(public)
        for kind, points in zip(["in","out"],found):
            routes.append({"id":f"building-{kind}-{portal['id']}","points":points,
                "start_portal":"" if kind=="in" else portal["id"],
                "end_portal":portal["id"] if kind=="in" else ""})
    if len(context["portals"]) < 2:
        raise ValueError("Frozen scene needs at least two checked, distinct building destinations")
    construction = {"scope":"Synthetic original-facade midpoint portals and bounded walking paths; not real door locations, real access rights, shop entrances, indoor geometry or empirical visitor rates.",
        "portal_exception_radius_m":PORTAL_EXCEPTION_M,"max_route_vertices":64,
        "navigation_lattice_m":1.25,
        "access_through_minimum_centerline_separation_m":2*BODY_CLEARANCE_M,
        "crossing_scope":"Building access is geometrically separated from both through-flow directions; no crossing or head-on priority claim.",
        "rejected_or_unselected_buildings":rejected}
    return context,routes,construction


def audit_access(local,layers,routes,portals):
    domain=box(0,0,SIDE,SIDE)
    union=unary_union([g for p,g in local if p["kind"]=="building"])
    lookup={p["id"]:p for p in portals}
    if len(lookup) != len(portals):
        raise ValueError("Duplicate declared building portal")
    buildings={f"osm-{p['osm_type']}-{p['osm_id']}":g for p,g in local if p["kind"]=="building"}
    for portal in portals:
        building=buildings.get(portal["building_id"])
        if building is None:
            raise ValueError("Portal references an unknown original building")
        wall=LineString(portal["facade"])
        point=Point(portal["point"])
        if (wall.length < portal["width_m"] or portal["width_m"] < .1
                or not domain.covers(point) or portal["provenance"] != "synthetic"):
            raise ValueError("Invalid bounded synthetic facade portal")
        # Match a complete original wall, not a visually plausible clip edge or
        # a segment invented inside an existing building.
        walls=[LineString([a,b]) for polygon in _polygons(building)
               for a,b in zip(list(polygon.exterior.coords),list(polygon.exterior.coords)[1:])]
        if not any(wall.hausdorff_distance(original)<1e-7 and abs(wall.length-original.length)<1e-7 for original in walls):
            raise ValueError("Portal facade is not a complete original building wall")
        if point.distance(wall.interpolate(.5,normalized=True))>1e-9:
            raise ValueError("Synthetic access point is not original facade midpoint")
    results={}
    for route in routes:
        line=LineString(route["points"])
        if not domain.covers(line):
            raise ValueError(f"Building route outside scene: {route['id']}")
        exceptions=[]
        for endpoint,point in [(route["start_portal"],route["points"][0]),(route["end_portal"],route["points"][-1])]:
            if endpoint in lookup:
                portal=lookup[endpoint]
                if math.dist(point,portal["point"])>1e-9:
                    raise ValueError("Building route misses exact declared facade point")
                facade=LineString(portal["facade"])
                if Point(point).distance(facade.interpolate(.5,normalized=True))>1e-9:
                    raise ValueError("Synthetic access point is not original facade midpoint")
                exceptions.append(Point(point).buffer(PORTAL_EXCEPTION_M))
        exception=unary_union(exceptions)
        body=line.buffer(BODY_CLEARANCE_M).intersection(domain)
        wall=body.intersection(union.difference(exception)).area
        outside=body.difference(layers["walking"].union(exception)).area
        interior=line.intersection(union.buffer(-1e-7)).length
        if wall>1e-7 or outside>1e-7 or interior>1e-7:
            raise ValueError(f"Building route clearance failed: {route['id']}: wall={wall}, outside={outside}, interior={interior}")
        results[route["id"]]={"vertices":len(route["points"]),"length_m":line.length,
            "body_building_intersection_outside_portal_m2":wall,
            "body_outside_walkable_area_m2":outside,"building_interior_length_m":interior}
    access=[LineString(r["points"]) for r in routes if r["start_portal"] in lookup or r["end_portal"] in lookup]
    through=[LineString(r["points"]) for r in routes if r["start_portal"] not in lookup and r["end_portal"] not in lookup]
    minimum_separation=min((a.distance(b) for a in access for b in through),default=None)
    if minimum_separation is not None and minimum_separation < 2*BODY_CLEARANCE_M-1e-7:
        raise ValueError("Building access crosses or approaches the opposing through-flow corridor")
    return {"status":"pass","scope":"Exact centreline and swept .55m body/clearance checked; exceptions limited to referenced .85m facade transition disks; domain-edge body clipping allowed.",
        "minimum_access_through_centerline_separation_m":minimum_separation,
        "building_count":len({p["building_id"] for p in portals}),"portal_count":len(portals),
        "body_plus_clearance_radius_m":BODY_CLEARANCE_M,"facade_portal_exception_radius_m":PORTAL_EXCEPTION_M,"routes":results}
