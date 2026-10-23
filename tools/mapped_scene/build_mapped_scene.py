#!/usr/bin/env python3
"""Create one bounded, deterministic mapped scene for the maintained Simulator.

Writes a new local directory only. Does not run the Simulator, touch MongoDB,
download data, or generate sampled movement/observation files.
"""
from __future__ import annotations

import argparse
import copy
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


def route_geometry_audit(local, layers):
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
    for name, points in ROUTE_POINTS.items():
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
    return {"status": "pass", "domain_side_m": SIDE, "leaf_depth": DEPTH, "leaf_side_m": STEP,
            "entrance_osm_node": DOOR_OSM_ID, "building_osm_way": BUILDING_OSM_ID,
            "entrance_facade_distance_m": door_geom.distance(building_geom.boundary),
            "routes": results,
            "scope": "Centre-line containment only. Frozen OSM width interpretation is inherited; circular body clearance and collision avoidance are not established."}


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


def make_config(repo, database, duration, render, seed):
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
    return cfg


def audit_config(cfg):
    import collections
    people = cfg["mapped_scene"]["people"]
    route_lengths = {r["id"]: LineString(r["points"]).length for r in cfg["mapped_scene"]["routes"]}
    person_ids, track_ids, counts = set(), set(), collections.Counter()
    minimum_gap = math.inf
    last_end = 0
    visits = 0
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
                minimum_gap = min(minimum_gap, episode["start_ms"] - previous_end)
            previous_end = end
            last_end = max(last_end, end)
    areas = [box(r["area"]["x"], r["area"]["y"], r["area"]["x"] + r["area"]["width"], r["area"]["y"] + r["area"]["height"]) for r in cfg["regions"]]
    for i, first in enumerate(areas):
        for other in areas[i+1:]:
            assert first.intersection(other).area == 0
    for region in cfg["regions"]:
        assert all(abs(value / STEP - round(value / STEP)) < 1e-9 for value in region["area"].values())
    assert len(people) == cfg["agents"]["num_agents"] == 64
    assert set(counts) == set(PROFILES)
    assert minimum_gap > cfg["sensors"][0]["aggregation"]["history"]["retention_ms"]
    return {"status": "pass", "scheduled_people": len(people), "visible_episodes": len(track_ids),
            "scheduled_visitors": visits, "population_by_observed_profile": dict(sorted(counts.items())),
            "minimum_hidden_gap_ms": minimum_gap, "history_horizon_ms": 6000,
            "last_scheduled_exit_ms": last_end, "regions": len(areas),
            "disjoint_D6_aligned_policy_patches": True,
            "person_ids_private_and_disjoint_from_track_tokens": True,
            "motion_scope": "Synthetic schedules and speeds on real OSM geometry; not empirical visitation or calibrated group behavior.",
            "support_scope": "Operational distinct track support. Hidden gaps exceed retained history only for this controlled scene.",
            "profile_assumptions": "Five observed categories; type-independent explicit 1.1–1.5 m/s speeds; one mover plus equipment is one modeled contributor. Circular radii are declared conservative visualization assumptions; priority is identical across profiles."}


def draw_background(layers, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path
    colors = {"building": "#CBD1D9", "road": "#E4B66B", "walking": "#B8DDD5", "cycling": "#B9CAE4", "crossing": "#D5BFDF", "entrance": "#E4B295"}
    fig = plt.figure(figsize=(8, 8), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor("#F4F5F7")
    for kind in ["road", "walking", "cycling", "crossing", "building", "entrance"]:
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
    ax.plot(DOOR[0], DOOR[1], marker="o", color="#A64422", markersize=4)
    ax.set_xlim(0, SIDE); ax.set_ylim(SIDE, 0); ax.set_aspect("equal"); ax.set_axis_off()
    fig.savefig(output, dpi=100, facecolor="#F4F5F7", pad_inches=0)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=pathlib.Path, required=True, help="New output directory; never overwrite")
    parser.add_argument("--database", required=True, help="Fresh owned UMP_Mapped_<uuid> base name; no DB is touched")
    parser.add_argument("--duration-s", type=int, default=90)
    parser.add_argument("--seed", type=int, default=20261023)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not re.fullmatch(r"UMP_Mapped_[0-9a-f]{32}", args.database):
        parser.error("Use an owned UMP_Mapped_<32 lower-case UUID hex> namespace")
    if not 1 <= args.duration_s <= 3600 or not 0 <= args.seed < 2**64:
        parser.error("duration must be 1..3600 s and seed uint64")
    if args.output.exists():
        parser.error("output directory already exists; choose a fresh output")
    _, local, layers, assumptions, provenance = load_source(repo)
    geometry = route_geometry_audit(local, layers)
    cfg = make_config(repo, args.database, args.duration_s, args.render, args.seed)
    scene = audit_config(cfg)
    args.output.mkdir(parents=True)
    config_bytes = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True).encode()
    (args.output / "config.yaml").write_bytes(config_bytes)
    draw_background(layers, args.output / "map_background.png")
    report = {"status": "pass", "seed": args.seed, "configuration_sha256": sha(config_bytes),
              "background_sha256": sha((args.output / "map_background.png").read_bytes()),
              "generator_sha256": sha(pathlib.Path(__file__).read_bytes()), **provenance,
              "route_geometry": geometry, "scene_contract": scene,
              "map_width_assumptions": assumptions,
              "policy_scope": "Four illustrative disjoint raster-aligned regions through the normal Region/PolicyTree adapter. Requirements are declared experimental choices, not validated privacy protection or map-derived law.",
              "execution": "cd to this output folder, then run the maintained simulator/build/Simulator; no simulation or DB operation was executed by this generator."}
    (args.output / "scene_manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": "pass", "output": str(args.output), "config_sha256": report["configuration_sha256"],
                      "people": scene["scheduled_people"], "episodes": scene["visible_episodes"], "visitors": scene["scheduled_visitors"]}))


if __name__ == "__main__":
    main()
