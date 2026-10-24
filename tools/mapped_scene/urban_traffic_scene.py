"""Opt-in mixed traffic on the frozen Mönckebergstraße crop.

The two modeled carriageway directions and crossing connectors are experimental
scenario assumptions. They do not establish surveyed crossings, signals, legal
access, calibrated arrivals, or cyclist/pedestrian priority rules.
"""
from __future__ import annotations

import copy
import math
import random
import uuid

from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

RIDER_PROFILES = ["Adult Cyclist", "Senior Cyclist", "Adult E-Scooter Driver"]
RIDER_RADII = {"Adult Cyclist": 1., "Senior Cyclist": 1., "Adult E-Scooter Driver": .65}


def validate_options(population, road_user_fraction, crossing_fraction, clearance):
    if population < 20:
        raise ValueError("Urban traffic requires at least 20 people to retain every declared profile")
    for name, value, lower, upper in [("road_user_fraction", road_user_fraction, .05, .5),
                                       ("distributed_crossing_fraction", crossing_fraction, .05, .5),
                                       ("pedestrian_clearance_m", clearance, .02, .2)]:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} must be finite and within {lower}..{upper}")
    if round(population * road_user_fraction) < len(RIDER_PROFILES):
        raise ValueError("Urban traffic requires at least three riders, one of each declared rider profile")


def crossing_connectors(local, layers):
    """Finite cross-road corridors, including explicit residual curb gaps.

    Frozen OSM buffers leave sub-meter gaps between the yellow carriageway and
    adjacent footways. Each connector spans those gaps explicitly and is clipped
    by real buildings; broad road coloring alone never grants pedestrian access.
    """
    domain = box(0, 0, 80, 80)
    roadline = next(g for p, g in local if p.get("osm_id") == 127716469).intersection(domain)
    centers = [15., 31., 47., 61.]
    connectors, rows = [], []
    for index, distance in enumerate(centers):
        center = roadline.interpolate(distance)
        a, b = roadline.interpolate(distance - .1), roadline.interpolate(distance + .1)
        length = a.distance(b)
        tangent = ((b.x-a.x)/length, (b.y-a.y)/length)
        normal = (-tangent[1], tangent[0])
        line = LineString([[center.x+normal[0]*offset, center.y+normal[1]*offset] for offset in (-7., 7.)])
        connector = line.buffer(2., cap_style=2).intersection(domain).difference(layers["building"])
        connectors.append(connector)
        rows.append({"id": f"synthetic-distributed-crossing-{index+1}", "centerline": [list(p) for p in line.coords],
                     "width_m": 4., "provenance": "synthetic_crossing_and_curb_gap_connector"})
    # The preferred Barkhof route also receives a four-meter explicit corridor;
    # it is no longer forced through the old very thin center-space neck.
    barkhof = next(g for p, g in local if p.get("osm_id") == 1015875382).intersection(domain)
    start, end = Point(barkhof.coords[0]), Point(barkhof.coords[-1])
    dx, dy = end.x-start.x, end.y-start.y
    length = math.hypot(dx, dy)
    barkhof = LineString([(start.x-dx/length*2, start.y-dy/length*2),
                         (end.x+dx/length*2, end.y+dy/length*2)])
    connectors.append(barkhof.buffer(2., cap_style=2).intersection(domain).difference(layers["building"]))
    rows.append({"id": "synthetic-barkhof-group-crossing", "centerline": [list(p) for p in barkhof.coords],
                 "width_m": 4., "provenance": "synthetic_widening_of_preferred_barkhof_crossing"})
    return roadline, unary_union(connectors), rows


def rider_people(people, seed, fraction):
    """Relabel a seeded subset while preserving at least one of each pedestrian type."""
    rng = random.Random(seed ^ 0x3C6EF372FE94F82B)
    count = round(len(people)*fraction)
    available = {}
    for index, person in enumerate(people):
        available.setdefault(person["type"], []).append(index)
    candidates = [index for group in available.values() for index in group[1:]]
    rng.shuffle(candidates)
    selected = set(candidates[:count])
    if len(selected) != count:
        raise ValueError("Insufficient pedestrians after retaining all declared profile categories")
    for number, index in enumerate(sorted(selected)):
        person = people[index]
        person["type"] = RIDER_PROFILES[number % len(RIDER_PROFILES)]
        person["radius_m"] = RIDER_RADII[person["type"]]
        person["speed_mps"] = round(rng.uniform(3., 4.), 6)
        person["episodes"] = person["episodes"][:1]
    return selected


def boundary_pair_measures(origin, source_side, sink_interval):
    """Check the actual nearest allowed sink, not a nominal route endpoint.

    Distinct interval IDs can share one edge, and adjacent intervals can both
    reach a corner. In either case native nearest-sink projection can finish
    immediately or keep the entire trip on an excluded max-x/max-y boundary.
    """
    a,b=sink_interval;dx,dy=b[0]-a[0],b[1]-a[1]
    squared=dx*dx+dy*dy
    if squared<=0:
        raise ValueError("Boundary sink interval must have positive length")
    phase=max(0.,min(1.,((origin[0]-a[0])*dx+(origin[1]-a[1])*dy)/squared))
    target=[a[0]+phase*dx,a[1]+phase*dy]
    offset=[target[i]-origin[i] for i in (0,1)]
    inward={"west":(1,0),"east":(-1,0),"north":(0,1),"south":(0,-1)}[source_side]
    distance=math.hypot(*offset)
    progress=offset[0]*inward[0]+offset[1]*inward[1]
    return {"distance_m":distance,"inward_progress_m":progress,
            "eligible":distance>=1. and progress>=.05}


def repair_boundary_pairs(routes, boundary_rows, router, seed):
    """Repair only invalid urban source/sink pairs using an independent RNG.

    Person/track tokens, profiles, speeds, schedules and valid routes remain
    unchanged. Public boundary geometry and half-open sensor coverage remain
    unchanged. Reselect a connected walking sink and retain the earlier guide
    prefix, replacing only its final connection to the new destination.
    """
    lookup={row["id"]:row for row in boundary_rows if row["spawn_supported"]}
    rng=random.Random(seed ^ 0xA54FF53A5F1D36F1)
    repaired=0;reasons={"source_on_sink_interval":0,"no_positive_inward_projection":0,"short_projected_trip":0}
    for route in routes:
        source=lookup.get(route["start_portal"]);sink=lookup.get(route["end_portal"])
        if source is None or sink is None:
            continue
        quality=boundary_pair_measures(route["points"][0],source["side"],sink["points"])
        if quality["eligible"]:
            continue
        if route.get("navigation_space"):
            raise ValueError("Rider direction requires a nondegenerate inward boundary pair")
        reasons["source_on_sink_interval"]+=quality["distance_m"]<=1e-7
        reasons["no_positive_inward_projection"]+=quality["inward_progress_m"]<.05
        reasons["short_projected_trip"]+=quality["distance_m"]<1.
        candidates=[row for row in boundary_rows if row["spawn_supported"] and row["mode"]==source["mode"]
            and boundary_pair_measures(route["points"][0],source["side"],row["points"])["eligible"]]
        rng.shuffle(candidates)
        original=route["points"]
        for candidate in candidates:
            target=list(LineString(candidate["points"]).interpolate(rng.uniform(.1,.9),normalized=True).coords)[0]
            try:
                suffix=router.route(original[-2],target)
            except ValueError:
                continue
            points=original[:-1]+suffix[1:]
            if len(points)>64:
                continue
            route.update(points=points,end_portal=candidate["id"])
            repaired+=1
            break
        else:
            raise ValueError("No connected inward sink interval for urban boundary source")
    return {"minimum_projected_trip_m":1.,"minimum_inward_projection_m":.05,
            "repaired_routes":repaired,"invalid_pair_reasons_before_repair":reasons,
            "scope":"Independent seeded repair of invalid urban boundary-to-boundary pairs only; source/sink geometry, people, labels, tokens, speeds, schedules and all valid routes are preserved. Static geometry does not replace the native sensor-observability gate."}


def make_scene(storefront, repo, local, layers, access, source_hash, seed, people, interval,
               overrides, road_user_fraction=.2, crossing_fraction=.2, clearance=.05):
    validate_options(len(people), road_user_fraction, crossing_fraction, clearance)
    people = copy.deepcopy(people)
    rider_indices = rider_people(people, seed, road_user_fraction)
    roadline, connectors, crossing_rows = crossing_connectors(local, layers)
    walking = layers["walking"].union(connectors)
    body_clearance = .45 + clearance
    context, internals, safe, rows = storefront.build_geometry(
        repo, local, layers, access, source_hash, overrides,
        walking_geometry=walking, body_clearance_m=body_clearance)
    router = storefront.SafeRouter(safe, experimental_narrow_passages=True)
    domain = box(0, 0, 80, 80)
    # Riders keep their existing circular envelopes. The largest rider plus
    # the shared hard clearance determines this conservative common space.
    road_clearance = max(RIDER_RADII.values()) + clearance
    points=list(roadline.coords)
    def extend(a,b):
        length=math.dist(a,b)
        return (a[0]+(a[0]-b[0])/length*5, a[1]+(a[1]-b[1])/length*5)
    extended=LineString([extend(points[0],points[1]), *points, extend(points[-1],points[-2])])
    carriageway = layers["road"].union(domain.buffer(road_clearance+.1).difference(domain))
    road_spaces={}
    for identifier,sign in [("carriageway-east",1),("carriageway-west",-1)]:
        # Erode the actual half-surface, including the centerline boundary,
        # before clipping the crop. End padding is also split by direction,
        # so opposite spaces never reopen into a shared funnel at map edges.
        half=carriageway.intersection(extended.buffer(sign*10,single_sided=True,cap_style=2,join_style=2))
        geometry=half.buffer(-(road_clearance+.002),resolution=16).intersection(domain).buffer(0)
        if geometry.is_empty:
            raise ValueError("Modeled carriageway direction has no body-safe rider center space")
        road_spaces[identifier]=geometry
    road_rows={key:storefront.polygon_rows(geometry) for key,geometry in road_spaces.items()}
    rng = random.Random(seed ^ 0x6A09E667F3BCC909)
    tokens = random.Random(seed ^ 0xCBBB9D5DC1059ED8)
    routes = []
    boundaries = [r for r in context["boundary_intervals"] if r["spawn_supported"]]
    eligible_cache = {}
    def endpoint(row):
        return list(LineString(row["points"]).interpolate(rng.uniform(.02, .98), normalized=True).coords)[0]
    def eligible(point):
        key = tuple(point)
        if key not in eligible_cache:
            result=[]
            for row in boundaries:
                mid=list(LineString(row["points"]).interpolate(.5, normalized=True).coords)[0]
                try:
                    router.route(mid, point)
                    result.append(row)
                except ValueError:
                    pass
            eligible_cache[key]=result
        return eligible_cache[key]
    def add(points, start, end, space=None):
        identifier="storefront-route-"+str(uuid.UUID(int=tokens.getrandbits(128), version=4))
        row={"id": identifier, "points": points, "start_portal": start, "end_portal": end}
        if space:
            row["navigation_space"]=space
        routes.append(row)
        return identifier
    # Extend before offsetting so the lane intersects the actual map edge rather
    # than inheriting a clipped endpoint slightly inside the domain.
    targeted=0
    for index, person in enumerate(people):
        first=person["episodes"][0]
        if index in rider_indices:
            forward=(sum(i in rider_indices for i in range(index)) % 2)==0
            lane=extended.parallel_offset(rng.uniform(1.2, 1.5), "left" if forward else "right", join_style=2).intersection(domain)
            if lane.geom_type!="LineString":
                raise ValueError("Modeled road direction does not form one bounded lane")
            coordinates=[list(p) for p in lane.coords]
            if (coordinates[0][0] < coordinates[-1][0]) != forward:
                coordinates.reverse()
            space="carriageway-east" if forward else "carriageway-west"
            if not road_spaces[space].buffer(1e-7).covers(LineString(coordinates)):
                raise ValueError("Rider lane violates its body-safe carriageway center space")
            start_side="west" if forward else "east"
            end_side="east" if forward else "west"
            first["route_id"]=add(coordinates, f"boundary-road-{start_side}-{space}", f"boundary-road-{end_side}-{space}", space)
            person["episodes"]=[first]
            continue
        visit=index%2==0
        if visit:
            portal=context["portals"][(index//2)%len(context["portals"])]
            approach=internals[(index//2)%len(context["portals"])]["approach"]
            options=eligible(approach)
            origin,destination=rng.choice(options),rng.choice(options)
            first["route_id"]=add(router.varied_route(endpoint(origin),approach,rng)+[portal["point"]], origin["id"],portal["id"])
            person["episodes"]=[first,{"track_id":str(uuid.UUID(int=tokens.getrandbits(128),version=4)),
                "route_id":add([portal["point"]]+router.varied_route(approach,endpoint(destination),rng),portal["id"],destination["id"]),
                "start_ms":0,"after_previous_ms":8000 if index%4==0 else 10000}]
        else:
            # A seeded subset explicitly traverses a distributed connector;
            # remaining trips select connected boundary intervals freely.
            if rng.random()<crossing_fraction:
                connector=crossing_rows[rng.randrange(len(crossing_rows)-1)]
                a,b=connector["centerline"]
                if rng.random()<.5:
                    a,b=b,a
                options_a,options_b=eligible(a),eligible(b)
                if not options_a or not options_b or not router.clear(a,b):
                    raise ValueError("Distributed crossing lacks body-safe connected approaches")
                origin,destination=rng.choice(options_a),rng.choice(options_b)
                points=router.route(endpoint(origin),a)+[b]+router.route(b,endpoint(destination))[1:]
                targeted+=1
            else:
                origin=rng.choice(boundaries)
                start=endpoint(origin)
                options=[r for r in eligible(start) if r["id"]!=origin["id"]]
                if not options:
                    raise ValueError("Urban pedestrian boundary lacks a connected destination")
                destination=rng.choice(options)
                points=router.varied_route(start,endpoint(destination),rng)
            if len(points)>64:
                raise ValueError("Urban pedestrian route exceeds the 64-vertex bound")
            first["route_id"]=add(points,origin["id"],destination["id"])
            person["episodes"]=[first]
    # Add rider source geometry as separate intervals, never as walking demand.
    for space,geometry in road_spaces.items():
        for side,edge in [("west",LineString([(0,0),(0,80)])),("east",LineString([(80,0),(80,80)]))]:
            intervals=storefront.parts(geometry.intersection(edge),"LineString")
            if len(intervals)!=1:
                raise ValueError("Modeled carriageway direction needs one body-safe interval per map edge")
            for line in intervals:
                context["boundary_intervals"].append({"id":f"boundary-road-{side}-{space}","mode":"road","side":side,
                    "points":[list(line.coords[0]),list(line.coords[-1])],"length_m":line.length,
                    "spawn_supported":True,"provenance":"synthetic_rider_source_on_body_safe_frozen_carriageway"})
    pair_repair=repair_boundary_pairs(routes,context["boundary_intervals"],router,seed)
    boundary_lookup={row["id"]:row for row in context["boundary_intervals"] if row["spawn_supported"]}
    for route in routes:
        if route["end_portal"] in boundary_lookup:
            route["end_boundary"]=copy.deepcopy(boundary_lookup[route["end_portal"]]["points"])
    context["navigation"].update(scope="Explicit pedestrian crossing/curb connectors plus original walking geometry; riders restricted to two independently body-safe direction spaces.",
        synthetic_crossing_connectors=crossing_rows,
        spaces=[{"id":key,"mode":"road","body_clearance_m":road_clearance,
                 "allowed_center_polygons_sha256":storefront.canonical_hash(rows)} for key,rows in road_rows.items()])
    scene={"support_contract":"one_episode_per_retained_history",
        "motion":{"mode":"local_navigation","step_ms":50,"clearance_m":clearance,"portal_gate_radius_m":1.3,
                  "navigation":{"center_clearance_m":body_clearance,"allowed_center_polygons":rows,
                      "grid_resolution_m":.5,"max_replan_nodes":20000,"replan_after_ms":1500,"replan_interval_ms":1000,
                      "door_max_batch_size":6,"spaces":[{"id":key,"center_clearance_m":road_clearance,"allowed_center_polygons":rows} for key,rows in road_rows.items()]}},
        "portals":context["portals"],"routes":routes,"people":people}
    construction={"scope":"Opt-in mixed traffic with explicit synthetic crossing connectors and two modeled rider directions; no surveyed crossing, signal, legal permission, calibrated demand or empirical behavior claim.",
        "urban_traffic":True,"boundary_source_guard":pair_repair,"navigation_lattice_m":.5,"body_plus_clearance_radius_m":body_clearance,
        "erosion_numerical_margin_m":.002,"max_route_vertices":64,
        "demand":{"arrival_interval_ms":interval,"road_user_fraction":road_user_fraction,"rider_people":len(rider_indices),
            "distributed_crossing_fraction_of_through_pedestrian_trips":crossing_fraction,"targeted_distributed_crossing_trips":targeted},
        "clearance":{"hard_pair_clearance_m":clearance,"largest_pedestrian_radius_m":.45,"largest_rider_radius_m":1.},
        "rider_direction_scope":"Two independently eroded half-carriageway spaces; shortcuts, local steering, replanning and exit intervals stay within the selected direction. Synthetic direction assignment, not inferred traffic law.",
        "minimum_opposing_center_space_distance_m":road_spaces["carriageway-east"].distance(road_spaces["carriageway-west"]),
        "rider_speed_mps":{"min":3.,"max":4.,"scope":"Conservative synthetic scenario parameter, not calibrated mode behavior"},
        "crossings":crossing_rows,
        "motion_limitations":"Conservative circular-body steering. No traffic signals, formal yield rules, explicit road priority, ORCA or hard real-time guarantee."}
    audit=audit_scene(storefront,local,layers,scene,context,walking,body_clearance,road_clearance)
    return scene,context,construction,audit


def audit_scene(storefront,local,layers,scene,context,walking,ped_clearance,road_clearance):
    domain=box(0,0,80,80)
    buildings=layers["building"]
    allowed=storefront.geometry_from_rows(scene["motion"]["navigation"]["allowed_center_polygons"])
    road_allowed={space["id"]:storefront.geometry_from_rows(space["allowed_center_polygons"])
                  for space in scene["motion"]["navigation"]["spaces"]}
    lookup={p["id"]:p for p in context["portals"]}
    boundaries={row["id"]:row for row in context["boundary_intervals"] if row["spawn_supported"]}
    routes={}
    for route in scene["routes"]:
        line=LineString(route["points"])
        rider=route.get("navigation_space") in road_allowed
        space=road_allowed[route["navigation_space"]] if rider else allowed
        if route["start_portal"] in boundaries and route["end_portal"] in boundaries:
            source=boundaries[route["start_portal"]];sink=boundaries[route["end_portal"]]
            if not boundary_pair_measures(route["points"][0],source["side"],sink["points"])["eligible"]:
                raise ValueError("Urban source/sink pair does not require meaningful inward movement")
        boundary=route.get("end_boundary")
        if boundary is not None:
            interval=LineString(boundary)
            if not space.buffer(1e-7).covers(interval) or interval.distance(Point(route["points"][-1]))>1e-7:
                raise ValueError("Urban exit interval is outside its mode-specific center space")
        if len(route["points"])>64 or not domain.covers(line) or not space.buffer(1e-7).covers(line):
            raise ValueError("Urban route fails exact mode-specific center-space containment")
        exemptions=[]
        for key, point in [(route["start_portal"],route["points"][0]),(route["end_portal"],route["points"][-1])]:
            if key in lookup:
                portal=lookup[key]
                if math.dist(point,portal["point"])>1e-8:
                    raise ValueError("Urban route misses its exact declared facade target")
                # The native portal segment is a single exact throat; this
                # exemption is only the already declared local facade approach.
                other=route["points"][1] if key==route["start_portal"] else route["points"][-2]
                exemptions.append(LineString([point,other]).buffer(.56,cap_style=1))
            elif abs(point[0])>1e-7 and abs(point[0]-80)>1e-7 and abs(point[1])>1e-7 and abs(point[1]-80)>1e-7:
                raise ValueError("Urban nonportal endpoint is not on the map boundary")
        exemption=unary_union(exemptions)
        footprint=line.buffer(road_clearance if rider else ped_clearance,resolution=32).intersection(domain)
        outside=footprint.difference((layers["road"] if rider else walking).union(exemption)).area
        wall=footprint.intersection(buildings.difference(exemption)).area
        interior=line.intersection(buildings.buffer(-1e-7)).length
        if max(outside,wall,interior)>1e-6:
            raise ValueError(f"Urban swept body fails mode surface/building audit: outside={outside},wall={wall},interior={interior}")
        routes[route["id"]]={"vertices":len(route["points"]),"length_m":line.length,
            "navigation_space":route["navigation_space"] if rider else "pedestrian", "body_outside_mode_surface_m2":outside,
            "body_building_intersection_outside_portal_m2":wall,"building_interior_length_m":interior}
    return {"status":"pass","routes":routes,"portal_count":len(lookup),"storefront_count":len(context["store_fronts"]),
        "body_plus_clearance_radius_m":ped_clearance,
        "scope":"Mode-specific exact center containment and conservative swept circular bodies against declared surfaces/buildings. Crossings, curb connectors, rider access and directions are explicit scenario assumptions."}
