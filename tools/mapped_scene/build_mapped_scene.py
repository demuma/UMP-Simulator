#!/usr/bin/env python3
"""Create one bounded, deterministic mapped scene for the maintained Simulator.

Writes a new local directory only. Does not run the Simulator, touch MongoDB,
download data, or generate sampled movement/observation files.
"""
from __future__ import annotations

import argparse
import copy
import functools
import gzip
import hashlib
import importlib.util
import json
import math
import pathlib
import random
import re
import uuid

import yaml
from shapely.affinity import affine_transform
from shapely.geometry import LineString, Point, Polygon, box, shape
from shapely.ops import unary_union

SIDE = 80
DEPTH = 6
STEP = SIDE / 2**DEPTH
DOOR = [23.792485125362873, 68.79053797014058]
DOOR_OSM_ID = 6244468529
BUILDING_OSM_ID = 43117523
PROFILES = ["Adult Pedestrian", "Child Pedestrian", "Senior Pedestrian",
            "Pedestrian With Stroller", "Pedestrian With Mobility Aid"]
ROUTE_POINTS = {
    "through-east": [[0, 70], [20, 64], [60, 52], [80, 44]],
    "through-west": [[80, 43], [60, 50], [20, 62], [0, 68]],
    "visit-in": [[0, 70], [20, 64], [DOOR[0], 64], DOOR],
    "visit-out": [DOOR, [DOOR[0], 64], [20, 64], [0, 70]],
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_source(repo: pathlib.Path):
    folder = repo / "tools/osm_regions/data/moenckeberg"
    raw = (folder / "source_geometry.geojson.gz").read_bytes()
    source_bytes = gzip.decompress(raw)
    source = json.loads(source_bytes)
    cfg = json.loads((folder / "close/policy.json").read_text())
    tf = cfg["coordinate_transform"]
    spec = importlib.util.spec_from_file_location("ump_osm_builder", repo / "tools/osm_regions/build_map.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    layers, _, assumptions, _ = module.corridor_layers(source, tf["x_equals_easting_minus"],
                                                    tf["y_equals_top_northing_minus_northing"], SIDE)
    shift = [1, 0, 0, -1, -tf["x_equals_easting_minus"], tf["y_equals_top_northing_minus_northing"]]
    local = [(f["properties"], affine_transform(shape(f["geometry"]), shift)) for f in source["features"]]
    return source, local, layers, assumptions, {
        "compressed_source_sha256": sha(raw), "source_geometry_sha256": sha(source_bytes),
        "coordinate_transform": tf, "map_builder_sha256": sha((repo / "tools/osm_regions/build_map.py").read_bytes()),
        "source_attribution": "© OpenStreetMap contributors; ODbL 1.0",
        "copyright_url": "https://www.openstreetmap.org/copyright",
    }


def route_geometry_audit(local, layers, routes=None, body_clearance_m=None):
    buildings = [g for p, g in local if p["kind"] == "building"]
    union = unary_union(buildings)
    door_features = [(p, g) for p, g in local if p["kind"] == "entrance" and p["osm_id"] == DOOR_OSM_ID]
    building_features = [(p, g) for p, g in local if p["kind"] == "building" and p["osm_id"] == BUILDING_OSM_ID]
    if len(door_features) != 1 or len(building_features) != 1:
        raise ValueError("Expected one frozen Rappolthaus building and portal")
    door_geom, building_geom = door_features[0][1], building_features[0][1]
    if Point(DOOR).distance(door_geom) > 1e-6 or door_geom.distance(building_geom.boundary) > 1e-6:
        raise ValueError("The declared door is not the frozen building facade node")
    results = {}
    supplied = ROUTE_POINTS if routes is None else {r["id"]: r["points"] for r in routes}
    for name, points in supplied.items():
        line = LineString(points)
        if not box(0, 0, SIDE, SIDE).covers(line):
            raise ValueError(f"Route outside declared domain: {name}")
        # Tolerate projected floating-point boundary coincidence, not wall penetration.
        interior_length = line.intersection(union.buffer(-1e-7)).length
        outside_walking = line.difference(layers["walking"].buffer(1e-7)).length
        if interior_length > 1e-6 or outside_walking > 1e-6:
            raise ValueError(f"Route geometry failed: {name}: building={interior_length}, outside walking={outside_walking}")
        results[name] = {"length_m": line.length, "building_interior_length_m": interior_length,
                         "outside_derived_walking_length_m": outside_walking,
                         "vertices": len(points), "geometry_sha256": sha(line.wkb)}
        if body_clearance_m is not None:
            # Facade transitions deliberately end/start at the door centre. Only
            # this explicitly bounded portal disk is exempt from wall clearance.
            portal_exception = door_geom.buffer(.85)
            body = line.buffer(body_clearance_m).intersection(box(0, 0, SIDE, SIDE))
            outside = body.difference(layers["walking"].union(portal_exception)).area
            wall = body.intersection(union.difference(portal_exception)).area
            if outside > 1e-6 or wall > 1e-6:
                raise ValueError(f"Route body clearance failed: {name}: outside={outside}, wall={wall}")
            results[name].update(body_plus_clearance_radius_m=body_clearance_m,
                                 body_outside_walkable_area_m2=outside,
                                 body_building_intersection_outside_portal_m2=wall,
                                 facade_portal_exception_radius_m=.85)
    directional_clearance = None
    if routes is not None and body_clearance_m is not None:
        east = [LineString(r["points"]) for r in routes if r["start_portal"]!="boundary-east"]
        west = [LineString(r["points"]) for r in routes if r["start_portal"]=="boundary-east"]
        if east and west:
            directional_clearance = min(a.distance(b) for a in east for b in west)
            if directional_clearance < 2*body_clearance_m-1e-7:
                raise ValueError("Opposing individualized corridors do not preserve swept-body separation")
    return {"status": "pass", "domain_side_m": SIDE, "leaf_depth": DEPTH, "leaf_side_m": STEP,
            "entrance_osm_node": DOOR_OSM_ID, "building_osm_way": BUILDING_OSM_ID,
            "entrance_facade_distance_m": door_geom.distance(building_geom.boundary),
            "routes": results,
            **({"minimum_opposing_route_centerline_distance_m":directional_clearance,
                "opposing_direction_body_clearance_checked":True} if body_clearance_m is not None else {}),
            "scope": ("Swept circular body plus clearance checked against derived walking/building geometry, except the explicitly bounded facade portal disk and domain-edge clipping. Collision response is checked separately."
                if body_clearance_m is not None else "Centre-line containment only. Frozen OSM width interpretation is inherited; circular body clearance and collision avoidance are not established.")}


def corridor_routes(seed):
    """Separated direction lanes with bounded smooth lateral variation.

    These remain declared polylines, not a city route planner. Their full swept
    body footprint is checked against frozen walk/building geometry before use.
    """
    rng = random.Random(seed ^ 0xA54FF53A)
    rows = []
    lane_points = []
    common_phase=rng.uniform(0,2*math.pi)
    # Eastbound lanes border the visited frontage, so entry/exit branches do
    # not cross the opposing northern stream. Visits continue east on exit.
    for index, intercept in enumerate([69.4, 70.6, 67.0, 68.2]):
        # The mapped footway widens inside the footprint. Expand lane spacing
        # there, then taper it at both boundaries before introducing individual
        # smooth offsets. Shared curvature preserves opposing-lane separation.
        points = [[x, intercept - .315*x + (intercept-68.8)/1.2*.6*math.sin(math.pi*x/80)
                   +.04*math.sin(x/80*2*math.pi+common_phase)] for x in range(0,81,10)]
        lane_points.append(points)
        east = index < 2
        ordered = points if east else list(reversed(points))
        rows.append({"id": f"corridor-{'east' if east else 'west'}-{index%2}", "points": ordered,
                     "start_portal": "boundary-west" if east else "boundary-east",
                     "end_portal": "boundary-east" if east else "boundary-west"})
    # Inbound and outbound branches separate outside the door admission zone.
    # The actual facade node is unchanged from the integration fixture.
    inbound = [lane_points[1][0], lane_points[1][1], lane_points[1][2],
               [22,66.0], DOOR]
    outbound = [DOOR, [DOOR[0],66.0], [26,64.5], [28,63.0], *lane_points[1][3:]]
    rows.extend([{"id":"corridor-visit-in","points":inbound,"start_portal":"boundary-west","end_portal":"building-rappolthaus"},
                 {"id":"corridor-visit-out","points":outbound,"start_portal":"building-rappolthaus","end_portal":"boundary-east"}])
    return rows


def corridor_people(seed, population, duration_s, interval_ms=None):
    if not 5 <= population <= 2048:
        raise ValueError("Corridor population must be 5..2048 explicit people")
    interval = interval_ms if interval_ms is not None else max(50, round(duration_s*1000/population/50)*50)
    if interval < 50 or interval % 50:
        raise ValueError("Corridor arrival interval must be a positive multiple of 50 ms")
    weights = [16,12,12,12,12]
    counts = [population*w//64 for w in weights]
    remainder = population-sum(counts)
    order = sorted(range(5),key=lambda i:(-(population*weights[i]%64),i))
    for i in order[:remainder]: counts[i]+=1
    labels = [label for label,count in zip(PROFILES,counts) for _ in range(count)]
    rng=random.Random(seed); rng.shuffle(labels)
    tokens=random.Random(seed ^ 0x1B8735936D748A2F)
    radii={row["type"]:row["radius"] for row in profiles()}
    people=[]
    for index,label in enumerate(labels):
        visit=index%4==0
        route="corridor-visit-in" if visit else f"corridor-{'east' if index%2==0 else 'west'}-{rng.randrange(2)}"
        episodes=[{"track_id":str(uuid.UUID(int=tokens.getrandbits(128),version=4)),"route_id":route,"start_ms":index*interval}]
        if visit:
            episodes.append({"track_id":str(uuid.UUID(int=tokens.getrandbits(128),version=4)),
                             "route_id":"corridor-visit-out","start_ms":0,"after_previous_ms":8000 if index%8==0 else 10000})
        people.append({"person_id":f"private-person-{index+1:04d}","type":label,
                       "speed_mps":round(rng.uniform(1.1,1.5),6),"radius_m":radii[label],"episodes":episodes})
    return people,interval


def individual_corridor_paths(routes, people, seed):
    """One reproducible smooth polyline per visible episode, never frame jitter.

    All variants retain the directional corridor and exact facade/boundary
    endpoints. Lane spacing expands inside the footprint before path offsets.
    Source identity spelling does not enter route shape or identifiers.
    """
    original={row["id"]:row for row in routes}
    rng=random.Random(seed ^ 0x510E527FADE682D1)
    result=[]
    for person in people:
        for episode in person["episodes"]:
            base=original[episode["route_id"]]
            phase=rng.uniform(0,2*math.pi)
            points=copy.deepcopy(base["points"])
            for index,point in enumerate(points[1:-1],1):
                x,y=point
                envelope=math.sin(math.pi*x/80)
                shift=.18*envelope*math.sin(phase+x/12)
                # Preserve the facade-normal departure segment and both exact
                # portal endpoints. Full swept geometry is checked before emit.
                if base["id"]=="corridor-visit-out" and index==1: shift=0
                point[1]=y+shift
            identifier="corridor-route-"+str(uuid.UUID(int=rng.getrandbits(128),version=4))
            episode["route_id"]=identifier
            result.append({"id":identifier,"points":points,
                           "start_portal":base["start_portal"],"end_portal":base["end_portal"]})
    return result


def access_module():
    spec = importlib.util.spec_from_file_location("ump_building_access", pathlib.Path(__file__).with_name("building_access.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.lru_cache(maxsize=2)
def building_geometry(repo):
    """Cache only immutable geometry construction; no movement data is cached."""
    _, local, layers, _, _ = load_source(pathlib.Path(repo))
    return access_module().build_access(local, layers)


def building_scene(repo, seed, population, duration_s, interval_ms=None):
    context, access_routes, construction = copy.deepcopy(building_geometry(str(repo)))
    people, interval = corridor_people(seed, population, duration_s, interval_ms)
    # Every second person visits. Hidden identities and return timing retain the
    # same private-oracle/observed-episode separation as the corridor fixture.
    base_routes = corridor_routes(seed)[:4] + access_routes
    rng = random.Random(seed ^ 0x3C6EF372FE94F82B)
    tokens = random.Random(seed ^ 0xBB67AE8584CAA73B)
    for index, person in enumerate(people):
        if index % 2 == 0:
            portal = context["portals"][(index//2) % len(context["portals"])]
            first = person["episodes"][0]
            first["route_id"] = "building-in-" + portal["id"]
            person["episodes"] = [first, {"track_id": str(uuid.UUID(int=tokens.getrandbits(128), version=4)),
                "route_id": "building-out-" + portal["id"], "start_ms": 0,
                "after_previous_ms": 8000 if index % 4 == 0 else 10000}]
        else:
            person["episodes"] = [person["episodes"][0]]
            person["episodes"][0]["route_id"] = f"corridor-{'east' if index%4==1 else 'west'}-{rng.randrange(2)}"
    routes = {row["id"]: row for row in base_routes}
    individual = []
    # Identifiers are independent of private identity spelling. Individual
    # through corridors retain their existing smooth variation. Access paths
    # remain exact checked polylines: no unchecked jitter beside a facade.
    through_people = [p for p in people if len(p["episodes"]) == 1]
    individual.extend(individual_corridor_paths(base_routes, through_people, seed))
    for person in people:
        if len(person["episodes"]) < 2:
            continue
        for episode in person["episodes"]:
            base = routes[episode["route_id"]]
            identifier = "building-route-" + str(uuid.UUID(int=rng.getrandbits(128), version=4))
            individual.append({**copy.deepcopy(base), "id": identifier})
            episode["route_id"] = identifier
    return {"support_contract": "one_episode_per_retained_history",
        "motion": {"mode": "corridor_following", "step_ms": 50, "clearance_m": .1,
                   "portal_gate_radius_m": 1.3},
        "portals": context["portals"], "routes": individual, "people": people}, context, construction


def storefront_module():
    spec = importlib.util.spec_from_file_location("ump_storefront_scene", pathlib.Path(__file__).with_name("storefront_scene.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@functools.lru_cache(maxsize=8)
def storefront_scene(repo, seed, population, duration_s, interval_ms=None, overrides_json=None,
                     experimental_narrow_passages=False):
    repo = pathlib.Path(repo)
    _, local, layers, _, provenance = load_source(repo)
    people, interval = corridor_people(seed, population, duration_s, interval_ms)
    overrides = json.loads(overrides_json) if overrides_json is not None else None
    return storefront_module().make_scene(repo, local, layers, access_module(),
        provenance["source_geometry_sha256"], seed, people, interval, overrides, experimental_narrow_passages)


def profiles():
    result = []
    colors = ["blue", "magenta", "purple", "orange", "green"]
    radii = [.25, .20, .225, .45, .35]
    probabilities = [16/64, 12/64, 12/64, 12/64, 12/64]
    for name, color, radius, probability in zip(PROFILES, colors, radii, probabilities):
        result.append({"type": name, "probability": probability, "priority": 3, "radius": radius,
                       "color": color,
                       "velocity": {"min": 1.1, "max": 1.5, "mu": 1.3, "sigma": .1,
                                    "noise_scale": .05, "noise_factor": 0},
                       "acceleration": {"min": .5, "max": 1.5}, "look_ahead_time": 2.0})
    return result


def route_rows():
    endpoints = {"through-east": ("boundary-west", "boundary-east"),
                 "through-west": ("boundary-east", "boundary-west"),
                 "visit-in": ("boundary-west", "building-rappolthaus"),
                 "visit-out": ("building-rappolthaus", "boundary-west")}
    return [{"id": name, "points": points, "start_portal": endpoints[name][0],
             "end_portal": endpoints[name][1]} for name, points in ROUTE_POINTS.items()]


def people_rows(seed):
    # Independent streams ensure person-ID spelling never determines observations.
    schedule = random.Random(seed)
    tokens = random.Random(seed ^ 0x1B8735936D748A2F)
    labels = [PROFILES[0]] * 16 + [name for name in PROFILES[1:] for _ in range(12)]
    schedule.shuffle(labels)
    people = []
    for index, label in enumerate(labels):
        speed = round(schedule.uniform(1.1, 1.5), 6)
        start = index * 200
        visit = index % 4 == 0
        first = "visit-in" if visit else ("through-east" if index % 2 == 0 else "through-west")
        episode = {"track_id": str(uuid.UUID(int=tokens.getrandbits(128), version=4)),
                   "route_id": first, "start_ms": start}
        episodes = [episode]
        if visit:
            end = start + math.ceil(LineString(ROUTE_POINTS[first]).length / speed * 1000)
            episodes.append({"track_id": str(uuid.UUID(int=tokens.getrandbits(128), version=4)),
                             "route_id": "visit-out", "start_ms": end + (8000 if index % 8 == 0 else 10000)})
        people.append({"person_id": f"private-person-{index + 1:03d}", "type": label,
                       "speed_mps": speed, "episodes": episodes})
    return people


def regions():
    # Deliberately small set of disjoint D6-aligned policy patches. These experimental
    # footprints are not the complete OSM functional partition and not inferred law.
    defs = [
        ("entrance-vicinity", "mapped_entrance", [20, 65, 10, 10], {"distinct_contributors": {"min": 10}}),
        ("west-footway-control", "mapped_fresh_footway", [0, 62.5, 15, 12.5],
         {"cell_side_m": {"max": 5}, "window_duration_ms": {"max": 1000}, "age_at_evaluation_ms": {"max": 1000}, "semantic_max_loss": {"max": .5}}),
        ("central-through-footway", "mapped_through", [40, 50, 20, 12.5],
         {"semantic_max_loss": {"max": .5}}),
        ("east-footway-control", "mapped_fresh_footway", [65, 40, 15, 12.5],
         {"cell_side_m": {"max": 5}, "window_duration_ms": {"max": 1000}, "age_at_evaluation_ms": {"max": 1000}, "semantic_max_loss": {"max": .5}}),
    ]
    types = {}
    rows = []
    for name, kind, coords, requirements in defs:
        types[kind] = {"type": kind, "color": "orange" if kind == "mapped_entrance" else "green", "alpha": .08,
                       "granularities": {"spatial": {"min": 0, "max": 1000}, "temporal": {"min": 0, "max": 10}},
                       "privacy": {"k_anonymity": {"min": 1}, "l_diversity": {"min": 1}},
                       "metric_requirements": requirements}
        rows.append({"id": name, "type": kind, "area": dict(zip(["x", "y", "width", "height"], coords))})
    return list(types.values()), rows


def make_config(repo, database, duration, render, seed, motion_mode="integration", population=64,
                arrival_interval_ms=None, shop_overrides=None, experimental_narrow_passages=False):
    if experimental_narrow_passages and motion_mode != "storefronts":
        raise ValueError("Experimental narrow passages require storefronts mode")
    cfg = yaml.safe_load((repo / "simulator/examples/temporal-aggregation/config.yaml").read_text())
    cfg["display"].update(width=1000, height=900, pixels_per_meter=10, title="UMP Mönckebergstraße — mapped visit scene")
    cfg["renderer"].update(show_renderer=render, show_trajectories=True, show_waypoints=False,
                          buffer_capacity=8, map_background="map_background.png",
                          map_attribution="© OpenStreetMap contributors; ODbL 1.0 | synthetic motion")
    cfg["simulation"].update(scenario="mapped_visits", duration_seconds=duration, playback_speed=1.0,
                            datetime="2026-10-23T10:30:00", time_step=.05)
    cfg["agents"].update(num_agents=64, road_user_taxonomy=profiles())
    cfg["database"].update(db_name=database, clear_database=False)
    cfg["mapped_scene"] = {"support_contract": "one_episode_per_retained_history",
                            "routes": route_rows(), "people": people_rows(seed)}
    cfg["region_taxonomy"], cfg["regions"] = regions()
    sensor = cfg["sensors"][0]
    sensor["id"] = "mapped-visits-agbs"
    sensor["database"].update(db_name=database, collection_name="AGB_Sensor_Data_V3")
    agg = sensor["aggregation"]
    agg.update(application_id="mapped-entrance-occupancy", diagnostics={"mode": "off"})
    agg["publication"].update(database=database + "_Releases", journal_database=database + "_Private")
    agg["spatial_selection"].update(min_depth=3, max_evaluations=8192, preserve_valid_descendants=False)
    agg["temporal_adaptation"].update(coordination="cell_local", extension_step_ms=100,
                                     max_window_ms=4000, max_evaluations=64, max_active_cells=4096)
    agg["history"].update(retention_ms=6000, max_bins=64, max_observations=100000,
                           max_identity_bytes=16000000, max_buckets=8192)
    agg["policy_tree"].update(id="mapped-entrance-illustrative-policy", regions=[r["id"] for r in cfg["regions"]])
    agg["policy_tree"]["execution"].update(strategy="semantic_first", semantic_secondary_strategy="temporal_first",
                                             release_trigger="policy_satisfied")
    agg["policy_tree"]["root"] = {
        "distinct_contributors": {"min": 5}, "min_category_distinct_contributors": {"min": 5},
        "cell_side_m": {"min": 1.25, "max": 10}, "window_duration_ms": {"min": 400, "max": 4000},
        "age_at_evaluation_ms": {"max": 4000}, "semantic_max_loss": {"max": 1}}
    leaves = ["adult_pedestrian", "child_pedestrian", "senior_pedestrian", "pedestrian_with_stroller", "pedestrian_with_mobility_aid"]
    agg["semantic_taxonomy"] = {"id": "ump-mapped-pedestrian-release", "version": "1", "nodes":
        [{"id": "road_user", "loss": 1}, {"id": "pedestrian", "parent": "road_user", "loss": .5}] +
        [{"id": node, "parent": "pedestrian", "loss": 0, "input_types": [label]} for node, label in zip(leaves, PROFILES)]}
    if shop_overrides is not None and motion_mode != "storefronts":
        raise ValueError("Shop entrance overrides apply only to storefronts mode")
    if motion_mode == "storefronts":
        cfg["simulation"]["datetime"] = "2026-10-24T00:00:00Z"
        cfg["mapped_scene"], _, _, _ = copy.deepcopy(storefront_scene(str(repo), seed, population, duration, arrival_interval_ms,
            json.dumps(shop_overrides, sort_keys=True) if shop_overrides is not None else None,
            experimental_narrow_passages))
        cfg["agents"]["num_agents"] = population
        for row in cfg["agents"]["road_user_taxonomy"]:
            row["probability"] = sum(p["type"] == row["type"] for p in cfg["mapped_scene"]["people"]) / population
    elif motion_mode == "buildings":
        cfg["mapped_scene"], _, _ = building_scene(repo, seed, population, duration, arrival_interval_ms)
        cfg["agents"]["num_agents"] = population
        for row in cfg["agents"]["road_user_taxonomy"]:
            row["probability"] = sum(p["type"] == row["type"] for p in cfg["mapped_scene"]["people"]) / population
    elif motion_mode == "corridor":
        people,interval=corridor_people(seed,population,duration,arrival_interval_ms)
        routes=individual_corridor_paths(corridor_routes(seed),people,seed)
        cfg["mapped_scene"]={"support_contract":"one_episode_per_retained_history",
            "motion":{"mode":"corridor_following","step_ms":50,"clearance_m":.1,"portal_gate_radius_m":3},
            "routes":routes,"people":people}
        cfg["agents"]["num_agents"]=population
        for row in cfg["agents"]["road_user_taxonomy"]:
            row["probability"]=sum(p["type"]==row["type"] for p in people)/population
    elif motion_mode != "integration" or population != 64 or arrival_interval_ms is not None:
        raise ValueError("Historical integration mode preserves exactly 64 people and its original 200-ms schedule")
    return cfg


def audit_config(cfg):
    import collections
    people = cfg["mapped_scene"]["people"]
    route_lengths = {r["id"]: LineString(r["points"]).length for r in cfg["mapped_scene"]["routes"]}
    person_ids, track_ids, counts = set(), set(), collections.Counter()
    minimum_gap = math.inf
    last_end = 0
    visits = 0
    motion_mode = cfg["mapped_scene"].get("motion",{}).get("mode")
    corridor = motion_mode in ("corridor_following", "local_navigation")
    for person in people:
        assert person["person_id"] not in person_ids
        person_ids.add(person["person_id"])
        counts[person["type"]] += 1
        if len(person["episodes"]) > 1:
            visits += 1
        previous_end = None
        for episode in person["episodes"]:
            token = episode["track_id"]
            assert token not in track_ids and person["person_id"] not in token
            assert uuid.UUID(token).version == 4
            track_ids.add(token)
            end = episode["start_ms"] + math.ceil(route_lengths[episode["route_id"]] / person["speed_mps"] * 1000)
            if previous_end is not None:
                minimum_gap = min(minimum_gap, episode.get("after_previous_ms",episode["start_ms"] - previous_end))
            previous_end = end
            last_end = max(last_end, end)
    areas = [box(r["area"]["x"], r["area"]["y"], r["area"]["x"] + r["area"]["width"], r["area"]["y"] + r["area"]["height"]) for r in cfg["regions"]]
    for i, first in enumerate(areas):
        for other in areas[i+1:]:
            assert first.intersection(other).area == 0
    for region in cfg["regions"]:
        assert all(abs(value / STEP - round(value / STEP)) < 1e-9 for value in region["area"].values())
    assert len(people) == cfg["agents"]["num_agents"]
    if not corridor: assert len(people)==64
    assert set(counts) == set(PROFILES)
    assert minimum_gap > cfg["sensors"][0]["aggregation"]["history"]["retention_ms"]
    result = {"status": "pass", "scheduled_people": len(people), "visible_episodes": len(track_ids),
            "scheduled_visitors": visits, "population_by_observed_profile": dict(sorted(counts.items())),
            "minimum_hidden_gap_ms": minimum_gap, "history_horizon_ms": 6000,
            "last_scheduled_exit_ms": last_end, "regions": len(areas),
            "disjoint_D6_aligned_policy_patches": True,
            "person_ids_private_and_disjoint_from_track_tokens": True,
            "motion_scope": "Synthetic schedules and speeds on real OSM geometry; not empirical visitation or calibrated group behavior.",
            "support_scope": "Operational distinct track support. Hidden gaps exceed retained history only for this controlled scene.",
            "profile_assumptions": "Five observed categories; type-independent explicit 1.1–1.5 m/s speeds; one mover plus equipment is one modeled contributor. Circular radii are declared conservative visualization assumptions; priority is identical across profiles."}
    if corridor:
        result.update(last_scheduled_exit_ms=None,
            last_source_request_ms=max(p["episodes"][0]["start_ms"] for p in people),
            motion_scope="Stateful route progress, bounded conservative swept-body following, source/door admission and realized lifecycle events. Not ORCA, overtaking or a globally complete collision solver.",
            arrival_scope="Explicit sustained source requests; actual admissions may queue. Future return timing is anchored to realized arrival.",
            individual_route_count=len(cfg["mapped_scene"]["routes"]),
            route_variation_scope="Each visible episode has a seeded smooth lateral path variant within a directional corridor; facade and boundary endpoints are pinned. No per-frame jitter or overtaking guarantee.",
            support_scope="Distinct observed tracks; declared relative hidden gaps exceed retained history. No GT association reaches aggregation.")
    if cfg["mapped_scene"].get("portals"):
        result.update(building_destinations=len({p["building_id"] for p in cfg["mapped_scene"]["portals"]}),
            portal_scope="Synthetic, reachable original-facade midpoints. Exact endpoint admission, not arbitrary wall contact. Exterior geometry does not establish real doors, shops or access permission.",
            route_variation_scope="Individual smooth through corridors; checked fixed access branches at two distinct buildings, with exact facade endpoints. No per-frame access jitter or general route-planner claim.")
    if motion_mode == "local_navigation":
        result.update(motion_scope="Individual seeded boundary-to-boundary and storefront paths on body-safe derived walking geometry; native local steering, bounded replanning and realized lifecycle events.",
            portal_scope="Four distinct synthetic POI-projected shop entrances on original building facades, with modeled storefront divisions. No invented physical building separations or surveyed-door claim.",
            route_variation_scope="Individual continuous boundary endpoints and seeded bounded geometric detours, with exact shop endpoints. No fixed through lanes.")
    return result


def background_rendering():
    """Describe the raster independently of toggle-controlled replay overlays.

    Names, entrances and attribution belong to the presentation layer. Keeping
    them out of the bitmap prevents small baked glyphs from surviving a hidden
    overlay or duplicating the viewer's readable labels and entrance markers.
    """
    return {"schema": "ump.map-background.v1", "content": "functional_geometry",
            "baked_names": False, "baked_entrances": False,
            "baked_debug_annotations": False, "baked_attribution": False,
            "attribution_location": "map_metadata_and_png_metadata"}


def draw_background(layers, output, building_access=None):
    """Render map geometry only; all interactive overlays remain vector layers.

    Original building boundaries remain visible. POI labels, route/access debug
    marks and entrance glyphs are deliberately omitted from this raster. The
    attribution stays in image metadata and the exported map's readable footer.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path
    colors = {"building": "#CBD1D9", "road": "#E4B66B", "walking": "#B8DDD5", "cycling": "#B9CAE4", "crossing": "#D5BFDF"}
    fig = plt.figure(figsize=(8, 8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor("#F4F5F7")
    for kind in ["road", "walking", "cycling", "crossing", "building"]:
        geometry = layers[kind]
        parts = [geometry] if geometry.geom_type == "Polygon" else getattr(geometry, "geoms", [])
        for polygon in parts:
            if polygon.geom_type != "Polygon" or polygon.is_empty:
                continue
            # Orient rings to keep holes transparent in the nonzero winding fill.
            from shapely.geometry.polygon import orient
            polygon = orient(polygon)
            vertices, codes = [], []
            for ring in [polygon.exterior] + list(polygon.interiors):
                pts = list(ring.coords)
                vertices.extend(pts)
                codes.extend([Path.MOVETO] + [Path.LINETO] * (len(pts)-2) + [Path.CLOSEPOLY])
            ax.add_patch(PathPatch(Path(vertices, codes), facecolor=colors[kind],
                                   edgecolor="#7A8590" if kind == "building" else "none", linewidth=.5))
    if building_access:
        # Keep original footprint boundaries distinct, including clipped/shared
        # edges. These are geometry, not assumed shopfront/entrance annotations.
        for building in building_access["buildings"]:
            for ring in building["polygons"] + building.get("holes", []):
                ax.plot([p[0] for p in ring], [p[1] for p in ring], color="#59636F", linewidth=1.1)
    ax.set_xlim(0, SIDE); ax.set_ylim(SIDE, 0); ax.set_aspect("equal"); ax.set_axis_off()
    rendering = background_rendering()
    fig.savefig(output, dpi=100, facecolor="#F4F5F7", pad_inches=0,
                metadata={"Attribution": "© OpenStreetMap contributors; ODbL 1.0; https://www.openstreetmap.org/copyright",
                          "UMP.MapRendering": json.dumps(rendering, sort_keys=True, separators=(",", ":"))})
    plt.close(fig)
    return rendering


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=pathlib.Path, required=True, help="New output directory; never overwrite")
    parser.add_argument("--database", required=True, help="Fresh owned UMP_Mapped_<uuid> base name; no DB is touched")
    parser.add_argument("--duration-s", type=int, default=90)
    parser.add_argument("--seed", type=int, default=20261023)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--motion-mode",choices=["integration","corridor","buildings","storefronts"],default="integration")
    parser.add_argument("--population",type=int,default=64,help="Stateful corridor/building/storefront population; historical mode stays at 64")
    parser.add_argument("--arrival-interval-ms",type=int,help="Stateful source interval, multiple of 50 ms; default spreads requests across horizon")
    parser.add_argument("--shop-overrides", type=pathlib.Path, help="Optional source-hash-bound synthetic shop entrance overrides")
    parser.add_argument("--experimental-narrow-passages", action="store_true",
        help="EXPERIMENTAL storefront routing and passage coordination; larger-cohort acceptance remains open")
    args = parser.parse_args()
    if args.experimental_narrow_passages and args.motion_mode != "storefronts":
        parser.error("--experimental-narrow-passages requires --motion-mode storefronts")
    repo = args.repo.resolve()
    if not re.fullmatch(r"UMP_Mapped_[0-9a-f]{32}", args.database):
        parser.error("Use an owned UMP_Mapped_<32 lower-case UUID hex> namespace")
    if not 1 <= args.duration_s <= 3600 or not 0 <= args.seed < 2**64:
        parser.error("duration must be 1..3600 s and seed uint64")
    if args.output.exists():
        parser.error("output directory already exists; choose a fresh output")
    _, local, layers, assumptions, provenance = load_source(repo)
    cfg = make_config(repo, args.database, args.duration_s, args.render, args.seed,args.motion_mode,args.population,args.arrival_interval_ms,
        json.loads(args.shop_overrides.read_text()) if args.shop_overrides else None, args.experimental_narrow_passages)
    context, construction = None, None
    if args.motion_mode == "storefronts":
        _, context, construction, geometry = copy.deepcopy(storefront_scene(str(repo), args.seed, args.population, args.duration_s, args.arrival_interval_ms,
            json.dumps(json.loads(args.shop_overrides.read_text()), sort_keys=True) if args.shop_overrides else None,
            args.experimental_narrow_passages))
    elif args.motion_mode == "buildings":
        context, _, construction = copy.deepcopy(building_geometry(str(repo)))
        geometry = access_module().audit_access(local, layers, cfg["mapped_scene"]["routes"], context["portals"])
    else:
        geometry = route_geometry_audit(local, layers,
            cfg["mapped_scene"]["routes"] if args.motion_mode=="corridor" else None,
            max(p["radius_m"] for p in cfg["mapped_scene"]["people"])+cfg["mapped_scene"]["motion"]["clearance_m"] if args.motion_mode=="corridor" else None)
    scene = audit_config(cfg)
    args.output.mkdir(parents=True)
    config_bytes = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True).encode()
    (args.output / "config.yaml").write_bytes(config_bytes)
    rendering = draw_background(layers, args.output / "map_background.png", context)
    if context is not None:
        (args.output / "building_access.json").write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n")
    report = {"status": "pass", "seed": args.seed, "configuration_sha256": sha(config_bytes),
              "background_sha256": sha((args.output / "map_background.png").read_bytes()),
              "background_rendering": rendering,
              "generator_sha256": sha(pathlib.Path(__file__).read_bytes()), **provenance,
              "route_geometry": geometry, "scene_contract": scene,
              "map_width_assumptions": assumptions,
              "policy_scope": "Four illustrative disjoint raster-aligned regions through the normal Region/PolicyTree adapter. Requirements are declared experimental choices, not validated privacy protection or map-derived law.",
              "execution": "cd to this output folder, then run the maintained simulator/build/Simulator; no simulation or DB operation was executed by this generator."}
    if args.motion_mode in ("corridor", "buildings", "storefronts"): report["motion_mode"] = args.motion_mode
    if context is not None:
        report["building_access"] = construction
        report["building_access_sha256"] = sha((args.output / "building_access.json").read_bytes())
        if args.motion_mode == "storefronts":
            report["storefront_generator_sha256"] = sha(pathlib.Path(__file__).with_name("storefront_scene.py").read_bytes())
    (args.output / "scene_manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": "pass", "output": str(args.output), "config_sha256": report["configuration_sha256"],
                      "people": scene["scheduled_people"], "episodes": scene["visible_episodes"], "visitors": scene["scheduled_visitors"]}))


if __name__ == "__main__":
    main()
