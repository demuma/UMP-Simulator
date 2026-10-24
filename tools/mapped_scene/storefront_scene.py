"""Frozen-map storefront targets, boundary sources and seeded pedestrian paths.

POI projections and frontage divisions are explicit modeling assumptions, never
claimed as surveyed doors, interior walls, access rights or calibrated demand.
"""
from __future__ import annotations
import copy
import hashlib
import heapq
import json
import math
import random
import uuid
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union, linemerge, nearest_points
from shapely.prepared import prep

SIDE = 80
CLEARANCE = .55
SHOP_NAMES = {"Apollo", "Ditsch", "Adidas Originals", "H&M HOME"}
EXPANDED_SOURCE_SHA256 = "afa2690e408f467af5ff679770bf872816cc568714d9171cf4efb493809e40ed"
CAFE_POI_ID = 442443891
CONCERT_POI_ID = 13739289193
CAFE_MAIN_ENTRANCE_ID = 9370793427
EXPANDED_ACCESS_SCOPE = "Exact frozen OSM entrance point; association to the named tenant is modeled."


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def parts(geom, kind="Polygon"):
    if geom.is_empty:
        return []
    if geom.geom_type == kind:
        return [geom]
    return [p for p in getattr(geom, "geoms", []) if p.geom_type == kind and not p.is_empty]


def polygon_rows(geometry):
    return [{"outer": [[float(x), float(y)] for x, y in p.exterior.coords],
             "holes": [[[float(x), float(y)] for x, y in ring.coords] for ring in p.interiors]}
            for p in sorted(parts(geometry), key=lambda p:(p.bounds, p.area))]


def geometry_from_rows(rows):
    return unary_union([Polygon(row["outer"], row["holes"]) for row in rows])


def _segments(geom):
    for polygon in parts(geom):
        ring = list(polygon.exterior.coords)
        for a, b in zip(ring, ring[1:]):
            yield a, b


def projected_shops(repo, local, layers, access, source_hash, overrides=None, expanded_shop_access=False):
    labels = json.loads((repo / "tools/osm_regions/data/moenckeberg/close/poi_labels.json").read_text())
    originals = {f"osm-{p['osm_type']}-{p['osm_id']}": g for p,g in local if p["kind"] == "building"}
    building_id = "osm-way-43117523"
    building = originals[building_id]
    all_buildings = unary_union(list(originals.values()))
    override_points = {}
    if overrides is not None:
        if (not isinstance(overrides, dict) or set(overrides) != {"schema", "source_geometry_sha256", "entrances"}
                or overrides["schema"] != "ump.shop-entrance-overrides.v1" or overrides["source_geometry_sha256"] != source_hash):
            raise ValueError("Shop overrides must declare the exact frozen source hash and supported schema")
        if not isinstance(overrides["entrances"], list) or len(overrides["entrances"]) > (6 if expanded_shop_access else 4):
            raise ValueError("Shop overrides require a bounded list matching the enabled destination inventory")
        for row in overrides["entrances"]:
            if not isinstance(row, dict) or set(row) != {"poi_osm_id", "point"} or row["poi_osm_id"] in override_points:
                raise ValueError("Duplicate or invalid shop override")
            point = row["point"]
            if not isinstance(point, list) or len(point) != 2 or any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in point):
                raise ValueError("Shop override requires a finite local coordinate pair")
            override_points[row["poi_osm_id"]] = point
    portals, fronts, internals = [], [], []
    selected = sorted([row for row in labels["labels"] if row["text"] in SHOP_NAMES], key=lambda r:r["x"])
    allowed_pois = {r["osm_id"] for r in selected} | ({CONCERT_POI_ID} if expanded_shop_access else set())
    if len(selected) != 4 or set(override_points)-allowed_pois:
        raise ValueError("Frozen storefronts or override targets do not match the enabled declared POIs")
    for row in selected:
        poi = Point(row["x"], row["y"])
        if not building.covers(poi):
            raise ValueError("Shop POI is not inside its declared original building")
        choices = []
        for a,b in _segments(building):
            wall = LineString([a,b]); length = wall.length
            projection = wall.interpolate(wall.project(poi))
            if projection.distance(Point(a)) < .65 or projection.distance(Point(b)) < .65:
                continue
            if row["osm_id"] in override_points:
                projection = Point(override_points[row["osm_id"]])
                if projection.distance(wall) > 1e-7 or min(projection.distance(Point(a)),projection.distance(Point(b))) < .65:
                    continue
            tangent = ((b[0]-a[0])/length, (b[1]-a[1])/length)
            for normal in [(-tangent[1],tangent[0]),(tangent[1],-tangent[0])]:
                center = list(projection.coords)[0]
                approach = [center[i]+normal[i]*1.5 for i in range(2)]
                if building.covers(Point(approach)) or not box(0,0,80,80).covers(projection):
                    continue
                # Only a 1.2m-wide facade throat may relax the circular body's
                # wall clearance; center paths never enter the building.
                throat = Polygon([[center[i]+normal[i]*d+tangent[i]*w for i in range(2)]
                                  for d,w in [(-.56,-.6),(1.7,-.6),(1.7,.6),(-.56,.6)]])
                footprint = LineString([center,approach]).buffer(CLEARANCE)
                if footprint.difference(layers["walking"].union(throat)).area > 1e-8:
                    continue
                if footprint.intersection(all_buildings.difference(throat)).area > 1e-8:
                    continue
                choices.append((poi.distance(projection),list(center),list(a),list(b),normal,tangent,throat))
        if not choices:
            raise ValueError(f"No reachable original facade projection for {row['text']}")
        _,center,a,b,normal,tangent,throat = min(choices,key=lambda q:q[0])
        identifier = f"shop-{row['osm_id']}"
        portal = {"id":identifier,"building_id":building_id,"point":center,"facade":[a,b],"width_m":1.2,"provenance":"synthetic"}
        portals.append(portal)
        fronts.append({"id":"front-"+identifier,"destination_id":identifier,"building_id":building_id,
                       "poi":{"osm_type":row["osm_type"],"osm_id":row["osm_id"],"name":row["text"],"point":[row["x"],row["y"]]},
                       "portal_id":identifier,"frontage":[],"provenance":"synthetic_poi_projection",
                       "projection_method":"manual_original_facade_override" if row["osm_id"] in override_points else "orthogonal_to_reachable_original_facade"})
        internals.append({"normal":normal,"tangent":tangent,"throat":throat,"approach":[center[i]+normal[i]*1.5 for i in range(2)]})
    # Divide the connected, original southern facade by nearest-door arclength.
    walls = unary_union([LineString(portal["facade"]) for portal in portals])
    wallchain = (linemerge(walls) if walls.geom_type == "MultiLineString" else walls).intersection(box(0,0,80,80))
    if wallchain.geom_type != "LineString":
        raise ValueError("Selected storefront facades do not form one original connected frontage")
    if wallchain.coords[0][0] > wallchain.coords[-1][0]:
        wallchain = LineString(list(wallchain.coords)[::-1])
    measures = [wallchain.project(Point(p["point"])) for p in portals]
    if any(b-a < 1.2 for a,b in zip(measures,measures[1:])):
        raise ValueError("Shop entrance overrides must preserve distinct ordered storefronts")
    separators = []
    cuts = [0]+[(a+b)/2 for a,b in zip(measures,measures[1:])]+[wallchain.length]
    for index,front in enumerate(fronts):
        left,right = wallchain.interpolate(cuts[index]),wallchain.interpolate(cuts[index+1])
        # Include real facade corners, never draw a chord across a wall bend.
        vertices=[list(left.coords)[0]]
        for vertex in list(wallchain.coords)[1:-1]:
            distance=wallchain.project(Point(vertex))
            if cuts[index]<distance<cuts[index+1]: vertices.append(vertex)
        vertices.append(list(right.coords)[0])
        front["frontage"] = [list(p) for p in vertices]
        if index < len(fronts)-1:
            center = wallchain.interpolate(cuts[index+1]); around=wallchain.interpolate(min(wallchain.length,cuts[index+1]+.01))
            dx,dy=around.x-center.x,around.y-center.y; length=math.hypot(dx,dy)
            normal=(-dy/length,dx/length)
            # Inward-facing short ticks are modeled storefront divisions,
            # explicitly not building partitions or inferred interior walls.
            a=[center.x,center.y]; b=[center.x+normal[0]*1.1,center.y+normal[1]*1.1]
            if not building.covers(Point(b)): b=[center.x-normal[0]*1.1,center.y-normal[1]*1.1]
            separators.append({"id":f"storefront-division-{index+1}","building_id":building_id,
                               "points":[a,b],"provenance":"synthetic_frontage_division_not_interior_wall"})
    context = access.building_context(local)
    context.update(schema="ump.building-access.v2",portals=portals,store_fronts=fronts,facade_separators=separators)
    if expanded_shop_access:
        _expand_shop_targets(context, internals, local, layers, labels, source_hash, override_points)
    return context, internals, all_buildings


def access_connector_surface(context, buildings):
    """Only explicit modeled approach surfaces, never implicit wall exceptions."""
    return unary_union([LineString(row["centerline"]).buffer(row["width_m"]/2, cap_style=2)
                        for row in context.get("navigation", {}).get("synthetic_access_connectors", [])]) \
        .intersection(box(0, 0, SIDE, SIDE)).difference(buildings)


def expanded_shop_inventory(context, source_hash):
    """Public destination assumptions, including source POIs that are excluded."""
    return {"schema":"ump.expanded-shop-access.v1", "source_geometry_sha256":source_hash,
        "destinations":[{"poi_osm_id":front["poi"]["osm_id"],"name":front["poi"]["name"],
                         "portal_id":front["portal_id"],"provenance":front["provenance"]}
                        for front in context["store_fronts"]],
        "excluded_pois":[{"poi_osm_id":4248082207,"name":"Mö Grill",
            "reason":"POI lies below the A1 overhead roof, without a source ground-level enclosing building/facade; a food-service counter is not modeled as disappearance into a building."}],
        "unselected_source_entrances":[
            {"osm_node_id":11062053180,"reason":"Civic building secondary entrance remains source context; the first extension uses one primary target per business rather than assuming this door belongs to another tenant."},
            {"osm_node_id":6244468529,"reason":"Rappolthaus main door is preserved in source context, but the snapshot does not identify which of the four southern tenants it serves; their existing synthetic storefront targets remain explicit assumptions."},
            {"osm_node_id":4616972979,"reason":"Entrance is tagged level=1; no validated ground-level access/stair connector is modeled."}],
        "scope":"Six named source POIs are explicit synthetic visit destinations. Door-to-tenant associations, forecourt width, demand and hidden dwell are modeling assumptions, not surveyed access rights or calibrated visitation."}


def _expand_shop_targets(context, internals, local, layers, labels, source_hash, override_points):
    """Add one exact source door and one POI projection on a second real building.

    The original four-shop fixture remains byte-for-byte unchanged when disabled.
    The civic building outline is never changed: a locally tangent admission line
    orients the finite throat at the exact OSM door vertex (sub-mm wall kink).
    """
    if source_hash != EXPANDED_SOURCE_SHA256:
        raise ValueError("Expanded shop access requires the exact reviewed frozen source hash")
    lookup={(props["kind"],props["osm_type"],props["osm_id"]):(props,geom) for props,geom in local}
    building_id="osm-way-32529387"
    _,building=lookup[("building","way",32529387)]
    buildings=unary_union([geom for props,geom in local if props["kind"]=="building"])
    pois={row["osm_id"]:row for row in labels["labels"]}
    if pois.get(CAFE_POI_ID,{}).get("text")!="Elbphilharmonie Kultur Café Starbucks" or pois.get(CONCERT_POI_ID,{}).get("text")!="Konzertkasse Mönckebergstraße":
        raise ValueError("Expanded shop POI identities differ from the reviewed source")
    if any(not building.covers(Point(pois[key]["x"],pois[key]["y"])) for key in (CAFE_POI_ID,CONCERT_POI_ID)):
        raise ValueError("Expanded shop POI is outside its original source building")
    props,door=lookup[("entrance","node",CAFE_MAIN_ENTRANCE_ID)]
    if (props["osm_version"]!=2 or props["osm_timestamp"]!="2023-07-22T18:14:47Z"
            or props["tags"]!={"entrance":"main"} or door.distance(building.boundary)>1e-8):
        raise ValueError("Café main entrance identity or exact original facade point differs from source")
    ring=list(building.exterior.coords)[:-1]
    index=min(range(len(ring)),key=lambda i:Point(ring[i]).distance(door))
    before,after=ring[(index-1)%len(ring)],ring[(index+1)%len(ring)]
    chord=LineString([before,after])
    if chord.distance(door)>.005:
        raise ValueError("Source café entrance corner is too sharp for a straight admission tangent")
    tangent=((after[0]-before[0])/chord.length,(after[1]-before[1])/chord.length)
    center=list(door.coords)[0]
    normals=[(-tangent[1],tangent[0]),(tangent[1],-tangent[0])]
    normal=next(n for n in normals if not building.covers(Point([center[i]+n[i]*1.5 for i in (0,1)])))
    approach=[center[i]+normal[i]*1.5 for i in (0,1)]
    body_safe=layers["walking"].difference(buildings).buffer(-(CLEARANCE+.002),resolution=16)
    if body_safe.is_empty:
        raise ValueError("Expanded source door has no existing body-safe walking connection")
    _,anchor=nearest_points(Point(approach),body_safe)
    centerline=[list(center),approach,list(anchor.coords[0])]
    if LineString(centerline).length>12 or LineString(centerline).intersection(buildings.buffer(-1e-7)).length>1e-8:
        raise ValueError("Bounded café source-door approach intersects a real building")
    connector={"id":"synthetic-cafe-main-access","portal_id":f"shop-{CAFE_POI_ID}",
        "centerline":centerline,"width_m":3.,"provenance":"synthetic_approach_to_source_osm_entrance"}
    context["navigation"]={"synthetic_access_connectors":[connector]}
    walking=layers["walking"].union(access_connector_surface(context,buildings))
    facade=[[center[i]+sign*tangent[i]*2 for i in (0,1)] for sign in (-1,1)]
    throat=Polygon([[center[i]+normal[i]*d+tangent[i]*w for i in (0,1)]
                    for d,w in [(-.56,-.6),(1.7,-.6),(1.7,.6),(-.56,.6)]])
    footprint=LineString(centerline).buffer(CLEARANCE)
    if footprint.difference(walking.union(throat)).area>1e-8 or footprint.intersection(buildings.difference(throat)).area>1e-8:
        raise ValueError("Café access fails full-body walking/building clearance")
    row=pois[CAFE_POI_ID];identifier=f"shop-{CAFE_POI_ID}"
    context["portals"].append({"id":identifier,"building_id":building_id,"point":list(center),
        "facade":facade,"width_m":1.2,"provenance":"osm"})
    context["store_fronts"].append({"id":"front-"+identifier,"destination_id":identifier,"building_id":building_id,
        "poi":{"osm_type":row["osm_type"],"osm_id":row["osm_id"],"name":row["text"],"point":[row["x"],row["y"]]},
        "portal_id":identifier,"frontage":copy.deepcopy(facade),"provenance":"osm_entrance_association",
        "projection_method":"source_entrance_on_original_facade",
        "entrance_source":{"osm_type":"node","osm_id":CAFE_MAIN_ENTRANCE_ID,"osm_version":props["osm_version"],
                           "osm_timestamp":props["osm_timestamp"],"scope":EXPANDED_ACCESS_SCOPE}})
    internals.append({"normal":normal,"tangent":tangent,"throat":throat,"approach":approach})
    row=pois[CONCERT_POI_ID];poi=Point(row["x"],row["y"]);choices=[]
    for a,b in _segments(building):
        wall=LineString([a,b]);length=wall.length
        projection=Point(override_points[row["osm_id"]]) if row["osm_id"] in override_points else wall.interpolate(wall.project(poi))
        if projection.distance(wall)>1e-7 or min(projection.distance(Point(a)),projection.distance(Point(b)))<.65:
            continue
        tangent=((b[0]-a[0])/length,(b[1]-a[1])/length)
        for normal in [(-tangent[1],tangent[0]),(tangent[1],-tangent[0])]:
            center=list(projection.coords)[0];approach=[center[i]+normal[i]*1.5 for i in (0,1)]
            if building.covers(Point(approach)) or not box(0,0,SIDE,SIDE).covers(projection):
                continue
            throat=Polygon([[center[i]+normal[i]*d+tangent[i]*w for i in (0,1)]
                            for d,w in [(-.56,-.6),(1.7,-.6),(1.7,.6),(-.56,.6)]])
            footprint=LineString([center,approach]).buffer(CLEARANCE)
            if footprint.difference(walking.union(throat)).area>1e-8 or footprint.intersection(buildings.difference(throat)).area>1e-8:
                continue
            choices.append((poi.distance(projection),center,list(a),list(b),normal,tangent,throat,approach))
    if not choices:
        raise ValueError("No body-safe original-facade projection for Konzertkasse")
    _,center,a,b,normal,tangent,throat,approach=min(choices,key=lambda q:q[0])
    identifier=f"shop-{CONCERT_POI_ID}"
    context["portals"].append({"id":identifier,"building_id":building_id,"point":center,"facade":[a,b],"width_m":1.2,"provenance":"synthetic"})
    context["store_fronts"].append({"id":"front-"+identifier,"destination_id":identifier,"building_id":building_id,
        "poi":{"osm_type":row["osm_type"],"osm_id":row["osm_id"],"name":row["text"],"point":[row["x"],row["y"]]},
        "portal_id":identifier,"frontage":[a,b],"provenance":"synthetic_poi_projection",
        "projection_method":"manual_original_facade_override" if CONCERT_POI_ID in override_points else "orthogonal_to_reachable_original_facade"})
    internals.append({"normal":normal,"tangent":tangent,"throat":throat,"approach":approach})


def build_geometry(repo, local, layers, access, source_hash, overrides=None,
                   walking_geometry=None, body_clearance_m=CLEARANCE, expanded_shop_access=False):
    context, internals, buildings = projected_shops(repo,local,layers,access,source_hash,overrides,expanded_shop_access)
    domain = box(0,0,SIDE,SIDE)
    # Outside-domain padding makes partial circular bodies at open map edges
    # valid. Actual buildings beyond the clipping edge remain obstacles.
    walking = layers["walking"] if walking_geometry is None else walking_geometry
    if expanded_shop_access:
        walking = walking.union(access_connector_surface(context, buildings))
    padded = walking.union(domain.buffer(1).difference(domain)).difference(buildings)
    safe = padded.buffer(-(body_clearance_m + .002), resolution=16).intersection(domain)
    strips = []
    for portal,internal in zip(context["portals"],internals):
        center=portal["point"]; normal=internal["normal"]; tangent=internal["tangent"]
        strip = Polygon([[center[i]+normal[i]*d+tangent[i]*w for i in range(2)]
                         for d,w in [(0,-.035),(1.6,-.035),(1.6,.035),(0,.035)]])
        strips.append(strip.difference(buildings.buffer(-1e-8)))
    safe = unary_union([safe]+strips).intersection(domain).buffer(0)
    rows = polygon_rows(safe)
    intervals = []
    sides = {"west":LineString([(0,0),(0,80)]),"east":LineString([(80,0),(80,80)]),
             "north":LineString([(0,0),(80,0)]),"south":LineString([(0,80),(80,80)])}
    for mode in ["walking","cycling","road"]:
        for side,edge in sides.items():
            intersection = layers[mode].intersection(edge)
            merged = unary_union(parts(intersection,"LineString"))
            if merged.geom_type == "MultiLineString": merged=linemerge(merged)
            for raw in sorted(parts(merged,"LineString"),key=lambda line:line.bounds):
                # Preserve contextual boundary geometry for unsupported modes;
                # actual pedestrian source intervals are eroded-body safe.
                intersection_safe = raw.intersection(safe) if mode == "walking" else raw
                if intersection_safe.geom_type == "MultiLineString": intersection_safe = linemerge(intersection_safe)
                lines = parts(intersection_safe,"LineString")
                for line in lines:
                    if line.length <= .05: continue
                    intervals.append({"id":f"boundary-{mode}-{side}-{sum(r['mode']==mode and r['side']==side for r in intervals)+1}",
                        "mode":mode,"side":side,"points":[list(line.coords[0]),list(line.coords[-1])],
                        "length_m":line.length,"spawn_supported":mode=="walking",
                        "provenance":"derived_frozen_functional_zone_boundary"})
    if len([r for r in intervals if r["spawn_supported"]]) < 2:
        raise ValueError("Insufficient positive-length body-safe walking boundaries")
    context["boundary_intervals"] = intervals
    context.setdefault("navigation", {}).update(body_clearance_m=body_clearance_m,allowed_center_polygons_sha256=canonical_hash(rows),
        scope="Pre-eroded derived walking geometry with clipped-edge circular-body access and narrow declared facade transitions. Road/cycle boundaries are context only; active sources are pedestrians.")
    return context, internals, safe, rows


class SafeRouter:
    """Coarse A* plus a bounded exact-geometry visibility fallback.

    The visibility repair is experimental and disabled by default until dense
    native narrow-passage coordination passes its separate acceptance gate.
    Keep previously routable queries on their original 0.5 m lattice paths.
    A connected narrow passage can contain no lattice edge: only after that
    search fails, attach exact polygon vertices with visibility edges. Neither
    this fallback nor its simplification widens the allowed center geometry.
    """
    def __init__(self, geometry, experimental_narrow_passages=False):
        self.geometry = geometry
        self.experimental_narrow_passages = experimental_narrow_passages
        self.prepared = prep(geometry.buffer(1e-8))
        self.grid_side = 161
        self.grid_step = .5
        self.points = [(x*self.grid_step,y*self.grid_step) for y in range(self.grid_side) for x in range(self.grid_side)]
        self.valid = {i for i,p in enumerate(self.points) if self.prepared.covers(Point(p))}
        self.cache = {}
        self.max_visibility_vertices = 1024
        # Lazily built per polygon component. Cached checks are undirected and
        # bounded by n*(n-1)/2 for each finite, capped visibility graph.
        self.visibility_graphs = {}
    def clear(self,a,b):
        return self.prepared.covers(LineString([a,b]))
    def route(self,start,goal):
        try:
            return self._lattice_route(start,goal)
        except ValueError:
            if not self.experimental_narrow_passages:raise
            return self._visibility_route(start,goal)
    def _lattice_route(self,start,goal):
        if self.clear(start,goal): return [list(start),list(goal)]
        def attach(p):
            return [(i,math.dist(p,self.points[i])) for i in sorted(self.valid,key=lambda i:math.dist(p,self.points[i]))[:24]
                    if math.dist(p,self.points[i])<=5 and self.clear(p,self.points[i])]
        sources,targets=attach(start),dict(attach(goal))
        if not sources or not targets: raise ValueError("Route endpoint cannot reach bounded walking lattice")
        distance={}; previous={}; queue=[]
        for i,d in sources:
            distance[i]=d;heapq.heappush(queue,(d+math.dist(self.points[i],goal),d,i))
        reached=None
        while queue:
            _,cost,i=heapq.heappop(queue)
            if cost != distance.get(i): continue
            if i in targets: reached=i;break
            x,y=i%self.grid_side,i//self.grid_side
            for dx,dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                nx,ny=x+dx,y+dy
                if not (0<=nx<self.grid_side and 0<=ny<self.grid_side):continue
                j=ny*self.grid_side+nx
                if j not in self.valid:continue
                key=min(i,j),max(i,j)
                if key not in self.cache:self.cache[key]=self.clear(self.points[i],self.points[j])
                if not self.cache[key]:continue
                candidate=cost+math.dist(self.points[i],self.points[j])
                if candidate<distance.get(j,math.inf):
                    distance[j]=candidate;previous[j]=i
                    heapq.heappush(queue,(candidate+math.dist(self.points[j],goal),candidate,j))
        if reached is None:raise ValueError("No connected boundary/door route")
        chain=[reached]
        while chain[-1] in previous:chain.append(previous[chain[-1]])
        raw=[start]+[self.points[i] for i in reversed(chain)]+[goal]
        return self._simplify(raw)
    def _simplify(self,raw):
        result=[list(raw[0])];i=0
        while i<len(raw)-1:
            j=next(j for j in range(len(raw)-1,i,-1) if self.clear(raw[i],raw[j]))
            if math.dist(result[-1],raw[j])>1e-8:result.append(list(raw[j]))
            i=j
        return result
    def _visibility_route(self,start,goal):
        # A full polygon visibility graph is finite and complete for polygonal
        # point-center paths. Component restriction avoids exploring unrelated
        # islands, while the explicit cap bounds nodes and potential edge work.
        # The existing 1e-8 containment tolerance is numerical only; body-safe
        # geometry was already eroded by clearance plus a 2 mm margin.
        component = next(((i,p) for i,p in enumerate(parts(self.geometry))
                          if p.buffer(1e-8).covers(Point(start))
                          and p.buffer(1e-8).covers(Point(goal))),None)
        if component is None:
            raise ValueError("No connected boundary/door route in allowed geometry")
        identifier,polygon=component
        if identifier not in self.visibility_graphs:
            vertices=sorted({tuple(p) for ring in [polygon.exterior,*polygon.interiors]
                             for p in list(ring.coords)[:-1]})
            if len(vertices)>self.max_visibility_vertices:
                raise ValueError("Exact visibility fallback exceeds bounded vertex limit")
            self.visibility_graphs[identifier]=(vertices,{})
        vertices,cache=self.visibility_graphs[identifier]
        # Endpoints are query-local: their visibility is never retained across
        # potentially numerous requests; only fixed geometry edges are cached.
        points=[tuple(start),tuple(goal)]+vertices
        distance={0:0.0};previous={};queue=[(math.dist(start,goal),0.0,0)];settled=set()
        while queue:
            _,cost,i=heapq.heappop(queue)
            if cost!=distance.get(i) or i in settled:continue
            settled.add(i)
            if i==1:
                chain=[i]
                while chain[-1] in previous:chain.append(previous[chain[-1]])
                return self._simplify([points[j] for j in reversed(chain)])
            for j,point in enumerate(points):
                if j in settled:continue
                candidate=cost+math.dist(points[i],point)
                if candidate>=distance.get(j,math.inf):continue
                if i>=2 and j>=2:
                    key=min(i,j),max(i,j)
                    if key not in cache:cache[key]=self.clear(points[i],point)
                    visible=cache[key]
                else:
                    visible=self.clear(points[i],point)
                if not visible:continue
                distance[j]=candidate;previous[j]=i
                heapq.heappush(queue,(candidate+math.dist(point,goal),candidate,j))
        raise ValueError("No connected boundary/door route in exact visibility graph")
    def varied_route(self,start,goal,rng):
        direct=self.route(start,goal)
        baseline=LineString(direct).length
        # Draw a geometrically admissible waypoint close to the route. A
        # bounded detour changes actual geometry, not just a route identifier.
        candidates=list(self.valid);rng.shuffle(candidates)
        for node in candidates[:160]:
            point=self.points[node]
            distance=LineString(direct).distance(Point(point))
            if not .7<=distance<=3.5 or min(math.dist(point,start),math.dist(point,goal))<3:continue
            try:left,right=self.route(start,point),self.route(point,goal)
            except ValueError:continue
            joined=left+right[1:]
            if LineString(joined).length<=baseline*1.35+2 and len(joined)<=64:return joined
        return direct



def controlled_barkhof_passage(router, routes, portal_ids):
    """Declare one explicit, geometry-safe experimental opposing-flow resource.

    This frozen-map modeling choice is separate from privacy policy regions.
    Every affected route receives the same complete centerline, in its travel
    direction, so native ownership has an unambiguous entry and full-body exit.
    The original walking geometry and facade approach transitions stay intact.
    """
    endpoint_a, endpoint_b = [65., 35.], [68., 45.]
    centerline = router.route(endpoint_a, endpoint_b)
    spine = LineString(centerline)

    def crosses_middle(points):
        crossings = []
        for index, (a, b) in enumerate(zip(points, points[1:])):
            if min(a[1], b[1]) < 39 < max(a[1], b[1]):
                x = a[0] + (b[0] - a[0]) * (39 - a[1]) / (b[1] - a[1])
                if 64 < x < 70:
                    crossings.append((index, b[1] > a[1]))
        return crossings

    affected = 0
    direction_counts = {True: 0, False: 0}
    participating = set()
    for route in routes:
        original = route["points"]
        crossings = crosses_middle(original)
        if not crossings:
            continue
        if len(crossings) != 1:
            raise ValueError("Barkhof passage requires exactly one directed route traversal")
        forward = crossings[0][1]
        entering, leaving = (endpoint_a, endpoint_b) if forward else (endpoint_b, endpoint_a)
        first = 1 if route["start_portal"] in portal_ids else 0
        last = len(original) - 2 if route["end_portal"] in portal_ids else len(original) - 1
        prefix = router.route(original[first], entering)
        suffix = router.route(leaving, original[last])
        if crosses_middle(prefix) or crosses_middle(suffix):
            raise ValueError("Barkhof approach rerouting would introduce a second passage traversal")
        points = original[:first] + prefix + (centerline if forward else centerline[::-1])[1:] + suffix[1:] + original[last + 1:]
        route["points"] = [point for index, point in enumerate(points)
                           if index == 0 or math.dist(point, points[index - 1]) > 1e-10]
        if len(route["points"]) > 64:
            raise ValueError("Controlled Barkhof route exceeds the existing 64-vertex source bound")
        affected += 1
        direction_counts[forward] += 1
        participating.add(route["id"])

    # A nonparticipant may skim a broad endpoint without traversing the neck.
    # Its planned path must bypass the protected resource; otherwise native
    # entry prevention would stop it permanently despite having no request.
    bypass_router = None
    for route in routes:
        if route["id"] in participating or LineString(route["points"]).distance(spine) >= 1.15:
            continue
        if bypass_router is None:
            # A .01 m margin covers the finite polygonal approximation of the
            # circular protection tube; native distance checks stay exact.
            bypass_router = SafeRouter(router.geometry.difference(spine.buffer(1.16, resolution=16)),
                                       experimental_narrow_passages=True)
        original = route["points"]
        first = 1 if route["start_portal"] in portal_ids else 0
        last = len(original) - 2 if route["end_portal"] in portal_ids else len(original) - 1
        points = original[:first] + bypass_router.route(original[first], original[last]) + original[last + 1:]
        if len(points) > 64 or LineString(points).distance(spine) <= 1.15:
            raise ValueError("Nonparticipating Barkhof route cannot safely bypass the protected passage")
        route["points"] = points

    def holding_points(endpoint, bounds, count):
        if count > 256:
            raise ValueError("Barkhof finite-cohort coordination supports at most 256 passage episodes per direction")
        candidates = []
        # A fixed 1.1 m lattice exceeds the largest pair of pedestrian radii
        # plus the .1 m native clearance; the queue cannot overlap by design.
        for iy in range(math.floor((bounds[3] - bounds[1]) / 1.1) + 1):
            for ix in range(math.floor((bounds[2] - bounds[0]) / 1.1) + 1):
                point = [bounds[0] + ix * 1.1, bounds[1] + iy * 1.1]
                geometry = Point(point)
                # Keep the entire 2.4 m outgoing apron clear in every
                # direction, plus the 1.15 m person/protection clearance.
                # This fixed geometry rule does not depend on cohort demand.
                if (router.geometry.covers(geometry) and geometry.distance(spine) > 1.30
                        and math.dist(endpoint, point) > 3.55
                        and router.geometry.covers(LineString([endpoint, point]))):
                    candidates.append(point)
        candidates.sort(key=lambda point: (math.dist(endpoint, point), point[1], point[0]))
        if len(candidates) < count:
            raise ValueError(f"Barkhof passage lacks {count} directly reachable safe staging positions on one side")
        return candidates[:count]

    return {"id": "barkhof-walking-neck", "centerline": centerline,
            "holding_points_a": holding_points(endpoint_a, (40., 10., 79., 35.), max(64, direction_counts[True])),
            "holding_points_b": holding_points(endpoint_b, (40., 45., 79., 65.), max(64, direction_counts[False])),
            "protection_radius_m": 1.15, "max_batch_size": 6}, affected


def make_scene(repo, local, layers, access, source_hash, seed, people, interval, overrides=None,
               experimental_narrow_passages=False, expanded_shop_access=False):
    context, internals, safe, rows = build_geometry(repo,local,layers,access,source_hash,overrides,
        expanded_shop_access=expanded_shop_access)
    router=SafeRouter(safe,experimental_narrow_passages=experimental_narrow_passages)
    rng=random.Random(seed ^ 0x6A09E667F3BCC909)
    tokens=random.Random(seed ^ 0xCBBB9D5DC1059ED8)
    boundaries=[r for r in context["boundary_intervals"] if r["spawn_supported"]]
    routes=[]
    portal_by_id={p["id"]:p for p in context["portals"]}
    def boundarypoint(row):
        return list(LineString(row["points"]).interpolate(rng.uniform(.02,.98),normalized=True).coords)[0]
    eligibility_cache={}
    def eligible(point):
        key=tuple(point)
        if key not in eligibility_cache:
            valid=[]
            for row in boundaries:
                mid=list(LineString(row["points"]).interpolate(.5,normalized=True).coords)[0]
                try: router.route(mid,point);valid.append(row)
                except ValueError: pass
            eligibility_cache[key]=valid
        return eligibility_cache[key]
    def add(points,start_portal,end_portal):
        identifier="storefront-route-"+str(uuid.UUID(int=tokens.getrandbits(128),version=4))
        routes.append({"id":identifier,"points":points,"start_portal":start_portal,"end_portal":end_portal})
        return identifier
    for index,person in enumerate(people):
        visit=index%2==0
        if visit:
            portal=context["portals"][(index//2)%len(context["portals"])]
            internal=internals[(index//2)%len(context["portals"])]
            options=eligible(internal["approach"])
            if not options:raise ValueError("Shop is disconnected from all walking boundaries")
            origin=rng.choice(options);destination=rng.choice(options)
            start,end=boundarypoint(origin),boundarypoint(destination)
            incoming=router.varied_route(start,internal["approach"],rng)+[portal["point"]]
            outgoing=[portal["point"]]+router.varied_route(internal["approach"],end,rng)
            first=person["episodes"][0]
            first["route_id"]=add(incoming,origin["id"],portal["id"])
            person["episodes"]=[first,{"track_id":str(uuid.UUID(int=tokens.getrandbits(128),version=4)),
                "route_id":add(outgoing,portal["id"],destination["id"]),"start_ms":0,"after_previous_ms":8000 if index%4==0 else 10000}]
        else:
            # Components with at least two distinct boundary intervals support
            # through trips. Sampling uses connected intervals and interior arclength,
            # not one fixed lane.
            viable=[]
            for origin in boundaries:
                midpoint=list(LineString(origin["points"]).interpolate(.5,normalized=True).coords)[0]
                options=[r for r in eligible(midpoint) if r["id"]!=origin["id"]]
                if options:viable.append((origin,options))
            if not viable:raise ValueError("No connected pair of walking source/sink intervals")
            origin,options=rng.choice(viable);destination=rng.choice(options)
            start,end=boundarypoint(origin),boundarypoint(destination)
            first=person["episodes"][0]
            first["route_id"]=add(router.varied_route(start,end,rng),origin["id"],destination["id"])
            person["episodes"]=[first]
    scene={"support_contract":"one_episode_per_retained_history",
        "motion":{"mode":"local_navigation","step_ms":50,"clearance_m":.1,"portal_gate_radius_m":1.3,
                  "navigation":{"center_clearance_m":CLEARANCE,"allowed_center_polygons":rows,"grid_resolution_m":.5,"max_replan_nodes":20000,
                                "replan_after_ms":1500,"replan_interval_ms":1000}},
        "portals":context["portals"],"routes":routes,"people":people}
    if experimental_narrow_passages:
        passage, affected_routes = controlled_barkhof_passage(router, routes, set(portal_by_id))
        scene["motion"]["navigation"]["narrow_passages"] = [passage]
    construction={"scope":"Four modeled POI storefronts share their true original building outline; frontages and entrances are synthetic, not surveyed doors or interior walls. Seeded finite pedestrian cohort with explicit boundary requests, geometric paths and relative hidden dwell.",
        "navigation_lattice_m":.5,
        "navigation_fallback":{"enabled":experimental_narrow_passages,
                               "status":"experimental_opt_in" if experimental_narrow_passages else "disabled_original_lattice_default",
                               "experimental_native_coordination_gate":"verified_128_person_sources_500_total_pending",
                               "method":"bounded_exact_polygon_visibility_after_lattice_failure",
                               "max_vertices_per_component":router.max_visibility_vertices,
                               "edge_oracle":"unchanged_allowed_center_segment_containment"},
        "max_route_vertices":64,"body_plus_clearance_radius_m":CLEARANCE,"erosion_numerical_margin_m":.002,
        "demand":{"visit_fraction":.5,"destination_weights":{p["id"]:1 for p in context["portals"]},
                  "boundary_selection":"uniform connected intervals; uniform interior arclength (.02,.98)","arrival_interval_ms":interval,
                  "scope":"Declared experimental demand, not empirical store visitation or calibrated arrival rates."},
        "overrides_sha256":canonical_hash(overrides) if overrides is not None else None}
    if experimental_narrow_passages:
        construction["navigation_fallback"]["native_passage_coordination"] = {
            "resource_id": passage["id"], "affected_routes": affected_routes,
            "method": "explicit_common_centerline_finite_direction_batches_with_safe_staging",
            "protection_radius_m": passage["protection_radius_m"],
            "max_batch_size": passage["max_batch_size"],
            "holding_points_per_side": {"a": len(passage["holding_points_a"]), "b": len(passage["holding_points_b"])},
            "holding_point_limit_per_side": 256, "exit_apron_length_m": 2.4,
            "holding_endpoint_exclusion_radius_m": 3.55,
            "nonparticipant_rule": "exact_safe_route_outside_protected_tube_with_polygon_margin",
            "scope": "Experimental frozen-map movement resource, independent of privacy PolicyTrees."}
    if expanded_shop_access:
        construction["scope"] = expanded_shop_inventory(context, source_hash)["scope"]
        construction["expanded_shop_access"] = expanded_shop_inventory(context, source_hash)
    audit=audit_scene(local,layers,scene,context)
    return scene,context,construction,audit


def audit_scene(local,layers,scene,context):
    domain=box(0,0,80,80)
    buildings=unary_union([g for p,g in local if p["kind"]=="building"])
    allowed=geometry_from_rows(scene["motion"]["navigation"]["allowed_center_polygons"])
    lookup={p["id"]:p for p in context["portals"]}
    boundary={r["id"]:r for r in context["boundary_intervals"] if r["spawn_supported"]}
    normals={}
    for portal in lookup.values():
        center=portal["point"];a,b=portal["facade"];length=math.dist(a,b)
        tangent=[(b[i]-a[i])/length for i in range(2)]
        normals[portal["id"]]=next(n for n in [(-tangent[1],tangent[0]),(tangent[1],-tangent[0])]
                                      if not buildings.covers(Point([center[i]+n[i] for i in range(2)])))
    result={}
    for route in scene["routes"]:
        points=route["points"];line=LineString(points)
        if len(points)>64 or not domain.covers(line) or not allowed.buffer(1e-7).covers(line):
            raise ValueError("Storefront route fails exact center navigation containment")
        exemptions=[]
        for key,point in [(route["start_portal"],points[0]),(route["end_portal"],points[-1])]:
            if key in lookup:
                portal=lookup[key]
                if math.dist(portal["point"],point)>1e-8:raise ValueError("Route misses exact shop facade point")
                a,b=portal["facade"];length=math.dist(a,b);tangent=[(b[i]-a[i])/length for i in range(2)];n=normals[key]
                exemptions.append(Polygon([[point[i]+n[i]*d+tangent[i]*w for i in range(2)]
                    for d,w in [(-.56,-.6),(1.7,-.6),(1.7,.6),(-.56,.6)]]))
            elif key not in boundary or Point(point).distance(LineString(boundary[key]["points"]))>1e-7:
                raise ValueError("Route endpoint is not on an eligible walking boundary interval")
        exemption=unary_union(exemptions)
        body=line.buffer(CLEARANCE,resolution=32).intersection(domain)
        outside=body.difference(layers["walking"].union(access_connector_surface(context,buildings)).union(exemption)).area
        wall=body.intersection(buildings.difference(exemption)).area
        interior=line.intersection(buildings.buffer(-1e-7)).length
        if outside>1e-6 or wall>1e-6 or interior>1e-6:
            raise ValueError(f"Storefront swept footprint failed: outside={outside}, wall={wall}, interior={interior}")
        result[route["id"]]={"vertices":len(points),"length_m":line.length,"body_outside_walkable_area_m2":outside,
                              "body_building_intersection_outside_portal_m2":wall,"building_interior_length_m":interior}
    return {"status":"pass","routes":result,"portal_count":len(lookup),"storefront_count":len(context["store_fronts"]),
        "building_count":len({p["building_id"] for p in lookup.values()}),"body_plus_clearance_radius_m":CLEARANCE,
        "scope":"Exact center paths and swept .55m body against frozen walking/building geometry; only referenced 1.2m-wide declared facade throats exempt body overlap. Domain-edge circular-body clipping is explicit; no false building walls."}
