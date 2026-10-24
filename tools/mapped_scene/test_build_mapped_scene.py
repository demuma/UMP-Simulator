#!/usr/bin/env python3
"""Offline generator/geometry gates; no sampled movement files or MongoDB."""
import copy
import importlib.util
import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml
from shapely.geometry import LineString, Point, Polygon, box

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("mapped_builder", HERE / "build_mapped_scene.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
REPO = pathlib.Path(os.environ.get("UMP_TEST_REPO", HERE.parents[1]))
DATABASE = "UMP_Mapped_94cf3e26a2a447c084c353f02695a2cb"


class MappedSceneGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.local, cls.layers, _, cls.provenance = builder.load_source(REPO)
        cls.cfg = builder.make_config(REPO, DATABASE, 90, False, 20261023)

    def test_frozen_source_and_actual_door_routes(self):
        self.assertEqual(self.provenance["source_geometry_sha256"],
                         "afa2690e408f467af5ff679770bf872816cc568714d9171cf4efb493809e40ed")
        report = builder.route_geometry_audit(self.local, self.layers)
        self.assertEqual(report["entrance_osm_node"], 6244468529)
        self.assertEqual(report["building_osm_way"], 43117523)
        for route in report["routes"].values():
            self.assertLess(route["building_interior_length_m"], 1e-6)
            self.assertLess(route["outside_derived_walking_length_m"], 1e-6)
        self.assertEqual(builder.ROUTE_POINTS["visit-in"][-1], builder.ROUTE_POINTS["visit-out"][0])

    def test_off_route_building_penetration_rejects(self):
        original = copy.deepcopy(builder.ROUTE_POINTS)
        try:
            builder.ROUTE_POINTS["through-east"] = [[0, 70], [40, 79], [80, 44]]
            with self.assertRaises(ValueError):
                builder.route_geometry_audit(self.local, self.layers)
        finally:
            builder.ROUTE_POINTS.clear()
            builder.ROUTE_POINTS.update(original)

    def test_exact_population_and_distinct_operational_tokens(self):
        report = builder.audit_config(self.cfg)
        self.assertEqual(report["scheduled_people"], 64)
        self.assertEqual(report["visible_episodes"], 80)
        self.assertEqual(report["scheduled_visitors"], 16)
        self.assertEqual(report["population_by_observed_profile"], {
            "Adult Pedestrian": 16, "Child Pedestrian": 12, "Senior Pedestrian": 12,
            "Pedestrian With Stroller": 12, "Pedestrian With Mobility Aid": 12})
        self.assertEqual(report["minimum_hidden_gap_ms"], 8000)
        self.assertEqual(len({p["priority"] for p in self.cfg["agents"]["road_user_taxonomy"]}), 1)

    def test_frozen_schedules_repeat_and_seed_changes_them(self):
        self.assertEqual(builder.people_rows(20261023), builder.people_rows(20261023))
        self.assertNotEqual(builder.people_rows(20261023), builder.people_rows(20261024))
        source = copy.deepcopy(self.cfg)
        for index, person in enumerate(source["mapped_scene"]["people"]):
            person["person_id"] = f"renamed-oracle-{index}"
        self.assertEqual(builder.audit_config(source), builder.audit_config(self.cfg))
        for left, right in zip(source["mapped_scene"]["people"], self.cfg["mapped_scene"]["people"]):
            self.assertEqual(left["episodes"], right["episodes"])

    def test_hidden_gap_must_exceed_all_retained_history(self):
        source = copy.deepcopy(self.cfg)
        person = next(p for p in source["mapped_scene"]["people"] if len(p["episodes"]) == 2)
        first = person["episodes"][0]
        end = first["start_ms"] + math.ceil(LineString(builder.ROUTE_POINTS[first["route_id"]]).length / person["speed_mps"] * 1000)
        person["episodes"][1]["start_ms"] = end + 6000
        with self.assertRaises(AssertionError):
            builder.audit_config(source)

    def test_normal_regions_and_complete_pedestrian_taxonomy(self):
        source = self.cfg
        agg = source["sensors"][0]["aggregation"]
        self.assertEqual(set(agg["policy_tree"]["regions"]), {r["id"] for r in source["regions"]})
        self.assertNotIn("policy_regions", agg)
        self.assertEqual(len(source["regions"]), 4)
        leaves = [n for n in agg["semantic_taxonomy"]["nodes"] if "input_types" in n]
        self.assertEqual({name for n in leaves for name in n["input_types"]}, set(builder.PROFILES))
        self.assertTrue(all(n["parent"] == "pedestrian" and n["loss"] == 0 for n in leaves))
        self.assertEqual(agg["diagnostics"], {"mode": "off"})
        self.assertEqual(agg["history"]["retention_ms"], 6000)

    def test_cli_writes_compact_config_and_exact_projected_image_only(self):
        with tempfile.TemporaryDirectory(prefix="ump-mapped-config-test-") as temp:
            output = pathlib.Path(temp) / "generated"
            command = [sys.executable, str(HERE / "build_mapped_scene.py"), "--repo", str(REPO),
                       "--output", str(output), "--database", DATABASE]
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual({p.name for p in output.iterdir()}, {"config.yaml", "scene_manifest.json", "map_background.png"})
            cfg = yaml.safe_load((output / "config.yaml").read_text())
            self.assertFalse(cfg["renderer"]["show_renderer"])
            self.assertEqual(cfg["database"]["db_name"], DATABASE)
            manifest = json.loads((output / "scene_manifest.json").read_text())
            self.assertEqual(manifest["status"], "pass")
            self.assertEqual(manifest["background_rendering"], builder.background_rendering())
            # PNG header gives width/height without adding a new image dependency.
            raw = (output / "map_background.png").read_bytes()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(int.from_bytes(raw[16:20], "big"), 800)
            self.assertEqual(int.from_bytes(raw[20:24], "big"), 800)
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn("already exists", again.stderr)

    def test_background_keeps_geometry_and_omits_baked_presentation_layers(self):
        import matplotlib.pyplot as plt
        from PIL import Image
        context = {"buildings": [{"polygons": [[[10, 10], [20, 10], [20, 20], [10, 10]]]}],
                   "portals": [{"point": [15, 10]}],
                   "store_fronts": [{"poi": {"name": "Duplicated shop name"}}],
                   "facade_separators": [{"points": [[15, 10], [15, 12]]}],
                   "boundary_intervals": [{"points": [[0, 0], [0, 5]]}]}
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary) / "background.png"
            with mock.patch.object(plt, "close"):
                rendering = builder.draw_background(self.layers, output, context)
                figure = plt.gcf()
                axes = figure.axes[0]
                self.assertEqual(axes.texts[:], [])
                self.assertGreater(len(axes.patches), 0)
                self.assertEqual(len(axes.lines), 1)  # Exact original footprint only.
                self.assertEqual(list(axes.lines[0].get_xdata()), [10, 20, 20, 10])
                self.assertEqual(list(axes.lines[0].get_ydata()), [10, 10, 20, 10])
            plt.close(figure)
            with Image.open(output) as image:
                self.assertEqual(image.size, (800, 800))
                self.assertEqual(json.loads(image.info["UMP.MapRendering"]), rendering)
                self.assertIn("OpenStreetMap contributors", image.info["Attribution"])
                self.assertIn("openstreetmap.org/copyright", image.info["Attribution"])
            self.assertFalse(rendering["baked_names"])
            self.assertFalse(rendering["baked_entrances"])
            self.assertFalse(rendering["baked_debug_annotations"])
            self.assertFalse(rendering["baked_attribution"])

    def test_background_without_access_still_has_no_legacy_door_glyph(self):
        import matplotlib.pyplot as plt
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(plt, "close"):
                builder.draw_background(self.layers, pathlib.Path(temporary) / "background.png")
                figure = plt.gcf()
                self.assertEqual(figure.axes[0].texts[:], [])
                self.assertEqual(figure.axes[0].lines[:], [])
                self.assertGreater(len(figure.axes[0].patches), 0)
            plt.close(figure)

    def test_reserved_database_rejected_before_output(self):
        with tempfile.TemporaryDirectory(prefix="ump-mapped-invalid-test-") as temp:
            output = pathlib.Path(temp) / "generated"
            result = subprocess.run([sys.executable, str(HERE / "build_mapped_scene.py"),
                                     "--repo", str(REPO), "--output", str(output), "--database", "Simulation"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_corridor_sustained_arrivals_and_relative_returns(self):
        source=builder.make_config(REPO,DATABASE,90,False,20261023,"corridor",128)
        report=builder.audit_config(source)
        self.assertEqual(report["scheduled_people"],128)
        self.assertEqual(report["visible_episodes"],160)
        self.assertGreater(report["last_source_request_ms"],88000)
        self.assertIsNone(report["last_scheduled_exit_ms"])
        self.assertEqual(source["mapped_scene"]["motion"]["mode"],"corridor_following")
        for person in source["mapped_scene"]["people"]:
            for episode in person["episodes"][1:]:
                self.assertGreater(episode["after_previous_ms"],6000)
                self.assertEqual(episode["start_ms"],0)
        fast=builder.make_config(REPO,DATABASE,90,False,20261023,"corridor",128,100)
        self.assertEqual(builder.audit_config(fast)["last_source_request_ms"],12700)

    def test_corridor_seeded_lane_diversity_and_swept_body_clearance(self):
        for seed in [20261023,20261024,20261025]:
            routes=builder.corridor_routes(seed)
            report=builder.route_geometry_audit(self.local,self.layers,routes,.55)
            self.assertEqual(len(routes),6)
            self.assertTrue(all(route["body_outside_walkable_area_m2"]<1e-6
                and route["body_building_intersection_outside_portal_m2"]<1e-6
                for route in report["routes"].values()))
        self.assertNotEqual(builder.corridor_routes(20261023),builder.corridor_routes(20261024))
        self.assertEqual(builder.corridor_routes(20261023),builder.corridor_routes(20261023))
        source=builder.make_config(REPO,DATABASE,90,False,20261023,"corridor",64)
        paths=source["mapped_scene"]["routes"]
        self.assertEqual(len(paths),80)
        self.assertEqual(len({row["id"] for row in paths}),80)
        builder.route_geometry_audit(self.local,self.layers,paths,.55)
        routes={row["id"]:row for row in paths}
        for person in source["mapped_scene"]["people"]:
            for episode in person["episodes"]:
                self.assertNotIn(person["person_id"],episode["route_id"])
                route=routes[episode["route_id"]]
                if route["start_portal"]=="building-rappolthaus": self.assertEqual(route["points"][0],builder.DOOR)
                if route["end_portal"]=="building-rappolthaus": self.assertEqual(route["points"][-1],builder.DOOR)

    def test_building_source_has_separate_footprints_and_original_wall_midpoints(self):
        context, routes, construction = builder.building_geometry(str(REPO))
        self.assertEqual(context["schema"], "ump.building-access.v1")
        self.assertEqual(len(context["buildings"]), 8)
        self.assertEqual(len(context["portals"]), 2)
        self.assertEqual(len({p["building_id"] for p in context["portals"]}), 2)
        original = {f"osm-{p['osm_type']}-{p['osm_id']}": g for p,g in self.local if p["kind"] == "building"}
        for portal in context["portals"]:
            self.assertEqual(portal["provenance"], "synthetic")
            wall = LineString(portal["facade"])
            self.assertLess(Point(portal["point"]).distance(wall.interpolate(.5, normalized=True)), 1e-9)
            self.assertLess(wall.difference(original[portal["building_id"]].boundary.buffer(1e-7)).length, 1e-7)
            self.assertGreaterEqual(wall.length, portal["width_m"])
            self.assertEqual(portal["width_m"], 1.2)
        domain = box(0,0,80,80)
        for building in context["buildings"]:
            self.assertTrue(building["name"])
            for ring in building["polygons"]:
                self.assertTrue(domain.covers(Polygon(ring)))
                self.assertEqual(ring[0], ring[-1])
        excluded = construction["rejected_or_unselected_buildings"]
        self.assertEqual(len(excluded), 6)
        self.assertEqual(sum(row["reason"] == "roof_or_non_ground_layer_not_an_indoor_destination" for row in excluded), 2)
        self.assertNotIn("people", context)
        self.assertNotIn("construction", context)
        self.assertEqual(len(routes), 4)

    def test_building_paths_have_checked_bodies_and_exact_portal_endpoints(self):
        cfg = builder.make_config(REPO,DATABASE,180,False,20261023,"buildings",64,1000)
        context, _, _ = builder.building_geometry(str(REPO))
        report = builder.access_module().audit_access(self.local,self.layers,cfg["mapped_scene"]["routes"],context["portals"])
        self.assertEqual(report["building_count"], 2)
        self.assertGreaterEqual(report["minimum_access_through_centerline_separation_m"],1.1-1e-7)
        self.assertTrue(all(row["body_building_intersection_outside_portal_m2"] < 1e-7
                            and row["body_outside_walkable_area_m2"] < 1e-7
                            for row in report["routes"].values()))
        self.assertTrue(all(row["vertices"] <= 64 for row in report["routes"].values()))
        portals = {p["id"]:p for p in cfg["mapped_scene"]["portals"]}
        for route in cfg["mapped_scene"]["routes"]:
            if route["start_portal"] in portals:
                self.assertEqual(route["points"][0], portals[route["start_portal"]]["point"])
            if route["end_portal"] in portals:
                self.assertEqual(route["points"][-1], portals[route["end_portal"]]["point"])
        corrupt = copy.deepcopy(cfg["mapped_scene"]["routes"])
        entry = next(row for row in corrupt if row["end_portal"] in portals)
        entry["points"][-1][0] += .01
        with self.assertRaisesRegex(ValueError,"exact declared facade point"):
            builder.access_module().audit_access(self.local,self.layers,corrupt,context["portals"])

    def test_building_visits_distributed_without_changing_taxonomy_or_policy(self):
        cfg = builder.make_config(REPO,DATABASE,180,False,20261023,"buildings",64,1000)
        again = builder.make_config(REPO,DATABASE,180,False,20261023,"buildings",64,1000)
        changed = builder.make_config(REPO,DATABASE,180,False,20261024,"buildings",64,1000)
        self.assertEqual(cfg,again)
        self.assertNotEqual(cfg["mapped_scene"]["people"],changed["mapped_scene"]["people"])
        self.assertEqual(cfg["mapped_scene"]["portals"],changed["mapped_scene"]["portals"])
        historical = builder.make_config(REPO,DATABASE,180,False,20261023,"corridor",64,1000)
        self.assertEqual(cfg["region_taxonomy"],historical["region_taxonomy"])
        self.assertEqual(cfg["regions"],historical["regions"])
        self.assertEqual(cfg["sensors"][0]["aggregation"],historical["sensors"][0]["aggregation"])
        report = builder.audit_config(cfg)
        self.assertEqual(report["scheduled_visitors"],32)
        self.assertEqual(report["visible_episodes"],96)
        self.assertEqual(report["minimum_hidden_gap_ms"],8000)
        routes={r["id"]:r for r in cfg["mapped_scene"]["routes"]}
        visited=[routes[p["episodes"][0]["route_id"]]["end_portal"] for p in cfg["mapped_scene"]["people"] if len(p["episodes"])==2]
        self.assertEqual(sorted(visited.count(portal["id"]) for portal in cfg["mapped_scene"]["portals"]),[16,16])
        self.assertEqual(len(routes),96)
        self.assertEqual(len({e["track_id"] for p in cfg["mapped_scene"]["people"] for e in p["episodes"]}),96)
        self.assertTrue(all(p["episodes"][0]["track_id"] != p["episodes"][1]["track_id"]
                            for p in cfg["mapped_scene"]["people"] if len(p["episodes"])==2))

    def test_building_audit_rejects_former_access_through_deadlock_crossing(self):
        cfg=builder.make_config(REPO,DATABASE,180,False,20261023,"buildings",64,1000)
        context,_,_=builder.building_geometry(str(REPO))
        routes=copy.deepcopy(cfg["mapped_scene"]["routes"])
        entry=next(r for r in routes if r["end_portal"]=="facade-43117523")
        # Former inlet was walkable and body-clear of buildings, but intersected
        # the opposing through stream near x=5..10m and deadlocked finite flow.
        entry["points"][0]=[0,66]
        with self.assertRaisesRegex(ValueError,"through-flow"):
            builder.access_module().audit_access(self.local,self.layers,routes,context["portals"])

    def test_building_audit_rejects_unrelated_facade_exemption(self):
        context, routes, _ = builder.building_geometry(str(REPO))
        corrupt = copy.deepcopy(routes)
        # A route cannot borrow another building's portal disk to cross a wall.
        entry = corrupt[0]
        original = next(g for p,g in self.local if p["kind"] == "building" and p["osm_id"] == 43117523)
        center = original.intersection(box(0,0,80,80)).representative_point()
        entry["points"].insert(1,list(center.coords)[0])
        with self.assertRaisesRegex(ValueError,"clearance failed"):
            builder.access_module().audit_access(self.local,self.layers,corrupt,context["portals"])

    def test_building_audit_rejects_invented_clipped_wall(self):
        context, routes, _ = copy.deepcopy(builder.building_geometry(str(REPO)))
        portal = next(p for p in context["portals"] if p["building_id"] == "osm-way-43117523")
        portal["facade"] = [[0,70],[0,78]]
        portal["point"] = [0,74]
        for route in routes:
            if route["start_portal"] == portal["id"]:
                route["points"][0] = list(portal["point"])
            if route["end_portal"] == portal["id"]:
                route["points"][-1] = list(portal["point"])
        with self.assertRaisesRegex(ValueError,"complete original building wall"):
            builder.access_module().audit_access(self.local,self.layers,routes,context["portals"])

    def test_building_cli_writes_public_geometry_and_no_movement_data(self):
        with tempfile.TemporaryDirectory(prefix="ump-building-config-test-") as temp:
            output=pathlib.Path(temp)/"scene"
            subprocess.run([sys.executable,str(HERE/"build_mapped_scene.py"),"--repo",str(REPO),
                "--output",str(output),"--database",DATABASE,"--motion-mode","buildings",
                "--duration-s","180","--population","64","--arrival-interval-ms","1000"],
                check=True,capture_output=True,text=True,timeout=60)
            self.assertEqual({p.name for p in output.iterdir()},
                {"config.yaml","map_background.png","scene_manifest.json","building_access.json"})
            context=json.loads((output/"building_access.json").read_text())
            self.assertEqual(set(context),{"schema","bounds","buildings","portals"})
            self.assertEqual(len(context["portals"]),2)
            manifest=json.loads((output/"scene_manifest.json").read_text())
            self.assertEqual(manifest["motion_mode"],"buildings")
            self.assertEqual(manifest["building_access_sha256"],builder.sha((output/"building_access.json").read_bytes()))
            self.assertEqual(manifest["route_geometry"]["status"],"pass")

    @unittest.skipUnless(os.environ.get("UMP_MAPPED_CORE_TEST_BINARY"),
                         "Set UMP_MAPPED_CORE_TEST_BINARY for the native finite-source drain gate")
    def test_dense_corridor_native_config_drains_without_dropped_tracks(self):
        # Reproduce the formerly deadlocked native source. The 180-s capture
        # horizon is censored; 360 s explicitly tests finite drainage, not a
        # latency promise. Only a temporary input config is written, no motion.
        source=builder.make_config(REPO,DATABASE,180,False,20261023,"corridor",128,500)
        with tempfile.TemporaryDirectory(prefix="ump-mapped-drain-test-") as temp:
            config=pathlib.Path(temp)/"config.yaml"
            config.write_text(yaml.safe_dump(source,sort_keys=False),encoding="utf-8")
            result=subprocess.run([os.environ["UMP_MAPPED_CORE_TEST_BINARY"],"--drain-config",
                str(config),"--end-ms","360000"],capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("scheduled=160 starts=160 ends=160 active=0 pending=0",result.stdout)
            self.assertIn("stalled=0 overlaps=0",result.stdout)

    @unittest.skipUnless(os.environ.get("UMP_MAPPED_CORE_TEST_BINARY"),
                         "Set UMP_MAPPED_CORE_TEST_BINARY for native multi-building finite-source drainage")
    def test_building_native_sources_drain_without_lost_tracks_or_overlap(self):
        # Exercise the complete generated paths, explicit facade portals,
        # admissions and relative returns. This catches branch/gate cycles that
        # geometric containment alone cannot detect. The finite drain horizon
        # is a source-completeness check, not a per-track latency guarantee.
        for population, seed, arrival_ms in [(64,20261023,1000),(128,20261024,500)]:
            with self.subTest(population=population, seed=seed, arrival_ms=arrival_ms):
                source=builder.make_config(REPO,DATABASE,180,False,seed,"buildings",population,arrival_ms)
                expected=sum(len(p["episodes"]) for p in source["mapped_scene"]["people"])
                self.assertEqual(expected,population*3//2)
                self.assertEqual(len({p["building_id"] for p in source["mapped_scene"]["portals"]}),2)
                with tempfile.TemporaryDirectory(prefix="ump-building-drain-test-") as temp:
                    config=pathlib.Path(temp)/"config.yaml"
                    config.write_text(yaml.safe_dump(source,sort_keys=False),encoding="utf-8")
                    result=subprocess.run([os.environ["UMP_MAPPED_CORE_TEST_BINARY"],"--drain-config",
                        str(config),"--end-ms","600000"],capture_output=True,text=True,timeout=120)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertIn(f"scheduled={expected} starts={expected} ends={expected} active=0 pending=0",result.stdout)
                    self.assertIn("stalled=0 overlaps=0",result.stdout)

    def test_storefronts_preserve_buildings_and_project_four_distinct_shop_targets(self):
        source=builder.make_config(REPO,DATABASE,180,False,20261023,"storefronts",64,1000)
        _,context,construction,audit=builder.storefront_scene(str(REPO),20261023,64,180,1000)
        self.assertEqual(context["schema"],"ump.building-access.v2")
        self.assertEqual(len(context["buildings"]),8)
        self.assertEqual(len(context["store_fronts"]),4)
        self.assertEqual(len(context["facade_separators"]),3)
        self.assertEqual(len({p["building_id"] for p in context["portals"]}),1)
        self.assertEqual({p["poi"]["name"] for p in context["store_fronts"]},
                         {"Apollo","Ditsch","Adidas Originals","H&M HOME"})
        original=next(g for p,g in self.local if p["kind"]=="building" and p["osm_id"]==43117523)
        portals={p["id"]:p for p in context["portals"]}
        for front in context["store_fronts"]:
            portal=portals[front["portal_id"]]
            point=Point(portal["point"]);wall=LineString(portal["facade"])
            poi=Point(front["poi"]["point"])
            self.assertLess(point.distance(wall.interpolate(wall.project(poi))),1e-8)
            self.assertLess(wall.difference(original.boundary.buffer(1e-7)).length,1e-7)
            self.assertLess(point.distance(LineString(front["frontage"])),1e-8)
            self.assertTrue(box(0,0,80,80).covers(LineString(front["frontage"])))
            self.assertEqual(set(portal),{"id","building_id","point","facade","width_m","provenance"})
        self.assertEqual(audit["status"],"pass")
        self.assertEqual(source["mapped_scene"]["motion"]["mode"],"local_navigation")
        self.assertEqual(source["simulation"]["datetime"],"2026-10-24T00:00:00Z")
        self.assertEqual(construction["demand"]["visit_fraction"],.5)

    def test_storefront_boundary_intervals_are_body_safe_and_mode_compatible(self):
        source,context,_,_=builder.storefront_scene(str(REPO),20261023,64,180,1000)
        module=builder.storefront_module()
        allowed=module.geometry_from_rows(source["motion"]["navigation"]["allowed_center_polygons"])
        boundaries={r["id"]:r for r in context["boundary_intervals"]}
        self.assertEqual(set(r["mode"] for r in boundaries.values()),{"walking","cycling","road"})
        endpoints=set()
        for interval in boundaries.values():
            line=LineString(interval["points"])
            self.assertGreater(line.length,.05)
            self.assertLess(line.difference(box(0,0,80,80).boundary).length,1e-7)
            self.assertAlmostEqual(line.length,interval["length_m"])
            self.assertEqual(interval["spawn_supported"],interval["mode"]=="walking")
            if interval["spawn_supported"]:self.assertLess(line.difference(allowed.buffer(1e-7)).length,1e-7)
        for route in source["routes"]:
            for key,point in [(route["start_portal"],route["points"][0]),(route["end_portal"],route["points"][-1])]:
                if key.startswith("boundary-"):
                    self.assertTrue(boundaries[key]["spawn_supported"])
                    self.assertEqual(boundaries[key]["mode"],"walking")
                    self.assertLess(Point(point).distance(LineString(boundaries[key]["points"])),1e-7)
                    endpoints.add(tuple(point))
        self.assertGreater(len(endpoints),60)
        self.assertEqual(context["navigation"]["allowed_center_polygons_sha256"],
            module.canonical_hash(source["motion"]["navigation"]["allowed_center_polygons"]))
        buildings=__import__("shapely.ops",fromlist=["unary_union"]).unary_union([g for p,g in self.local if p["kind"]=="building"])
        self.assertLess(allowed.intersection(buildings.buffer(-1e-7)).area,1e-6)

    def test_storefront_seed_changes_actual_paths_without_changing_policy(self):
        first=builder.make_config(REPO,DATABASE,180,False,20261023,"storefronts",64,1000)
        same=builder.make_config(REPO,DATABASE,180,False,20261023,"storefronts",64,1000)
        other=builder.make_config(REPO,DATABASE,180,False,20261024,"storefronts",64,1000)
        self.assertEqual(first,same)
        self.assertNotEqual([r["points"] for r in first["mapped_scene"]["routes"]],
                            [r["points"] for r in other["mapped_scene"]["routes"]])
        routes=first["mapped_scene"]["routes"]
        self.assertEqual(len({json.dumps(r["points"]) for r in routes}),len(routes))
        historical=builder.make_config(REPO,DATABASE,180,False,20261023,"buildings",64,1000)
        for field in ["regions","region_taxonomy","sensors"]:self.assertEqual(first[field],historical[field])
        self.assertEqual(first["agents"],historical["agents"])
        report=builder.audit_config(first)
        self.assertEqual(report["scheduled_visitors"],32)
        self.assertEqual(report["minimum_hidden_gap_ms"],8000)
        lookup={r["id"]:r for r in routes}
        targets=[lookup[p["episodes"][0]["route_id"]]["end_portal"]
                 for p in first["mapped_scene"]["people"] if len(p["episodes"])>1]
        self.assertEqual(sorted(targets.count(portal["id"]) for portal in first["mapped_scene"]["portals"]),[8,8,8,8])

    def test_storefront_manual_overrides_are_hash_bound_and_checked_against_real_facades(self):
        module=builder.storefront_module()
        _,context,_,_=builder.storefront_scene(str(REPO),20261023,64,180,1000)
        front=context["store_fronts"][0];portal=context["portals"][0]
        override={"schema":"ump.shop-entrance-overrides.v1","source_geometry_sha256":self.provenance["source_geometry_sha256"],
                  "entrances":[{"poi_osm_id":front["poi"]["osm_id"],"point":portal["point"]}]}
        source=builder.make_config(REPO,DATABASE,180,False,20261023,"storefronts",64,1000,override)
        self.assertEqual(source["mapped_scene"]["portals"],context["portals"])
        shifted=copy.deepcopy(override)
        a,b=portal["facade"];length=math.dist(a,b)
        shifted["entrances"][0]["point"]=[portal["point"][i]+.5*(b[i]-a[i])/length for i in range(2)]
        changed,_,_,_=module.build_geometry(REPO,self.local,self.layers,builder.access_module(),self.provenance["source_geometry_sha256"],shifted)
        self.assertNotEqual(changed["portals"][0]["point"],portal["point"])
        self.assertEqual(changed["store_fronts"][0]["projection_method"],"manual_original_facade_override")
        for bad in [{**override,"source_geometry_sha256":"0"*64},
                    {**override,"entrances":[{"poi_osm_id":front["poi"]["osm_id"],"point":[40,79]}]},
                    {**override,"entrances":override["entrances"]*2}]:
            with self.assertRaises(ValueError):
                module.build_geometry(REPO,self.local,self.layers,builder.access_module(),self.provenance["source_geometry_sha256"],bad)
        with self.assertRaises(ValueError):
            builder.make_config(REPO,DATABASE,180,False,20261023,"buildings",64,1000,override)

    def test_storefront_geometry_rejects_wall_crossing_and_wrong_boundary(self):
        source,context,_,_=copy.deepcopy(builder.storefront_scene(str(REPO),20261023,64,180,1000))
        module=builder.storefront_module()
        corrupt=copy.deepcopy(source)
        corrupt["routes"][0]["points"].insert(1,[40,79])
        with self.assertRaises(ValueError):module.audit_scene(self.local,self.layers,corrupt,context)
        corrupt=copy.deepcopy(source)
        corrupt["routes"][0]["start_portal"]="boundary-road-west-1"
        with self.assertRaisesRegex(ValueError,"eligible walking boundary"):
            module.audit_scene(self.local,self.layers,corrupt,context)

    def test_storefront_cli_writes_v2_geometry_and_no_sampled_movement(self):
        with tempfile.TemporaryDirectory(prefix="ump-storefront-config-test-") as temp:
            output=pathlib.Path(temp)/"scene"
            subprocess.run([sys.executable,str(HERE/"build_mapped_scene.py"),"--repo",str(REPO),
                "--output",str(output),"--database",DATABASE,"--motion-mode","storefronts",
                "--duration-s","180","--population","64","--arrival-interval-ms","1000"],
                check=True,capture_output=True,text=True,timeout=60)
            self.assertEqual({p.name for p in output.iterdir()},
                {"config.yaml","map_background.png","scene_manifest.json","building_access.json"})
            manifest=json.loads((output/"scene_manifest.json").read_text())
            self.assertEqual(manifest["motion_mode"],"storefronts")
            self.assertEqual(manifest["route_geometry"]["status"],"pass")
            self.assertEqual(manifest["building_access_sha256"],builder.sha((output/"building_access.json").read_bytes()))
            self.assertEqual(json.loads((output/"building_access.json").read_text())["schema"],"ump.building-access.v2")

    @unittest.skipUnless(os.environ.get("UMP_MAPPED_CORE_TEST_BINARY"),
                         "Set UMP_MAPPED_CORE_TEST_BINARY for native storefront finite-source drainage")
    def test_storefront_native_sources_drain_without_lost_tracks_or_overlap(self):
        for population,seed,arrival_ms in [(64,20261023,1000),(128,20261024,500)]:
            with self.subTest(population=population,seed=seed):
                source=builder.make_config(REPO,DATABASE,180,False,seed,"storefronts",population,arrival_ms)
                expected=sum(len(p["episodes"]) for p in source["mapped_scene"]["people"])
                with tempfile.TemporaryDirectory(prefix="ump-storefront-drain-test-") as temp:
                    config=pathlib.Path(temp)/"config.yaml";config.write_text(yaml.safe_dump(source,sort_keys=False),encoding="utf-8")
                    result=subprocess.run([os.environ["UMP_MAPPED_CORE_TEST_BINARY"],"--drain-config",str(config),"--end-ms","600000"],
                        capture_output=True,text=True,timeout=180)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertIn(f"scheduled={expected} starts={expected} ends={expected} active=0 pending=0",result.stdout)
                    self.assertIn("stalled=0 overlaps=0",result.stdout)

    def test_historical_population_and_corridor_flow_guards(self):
        for kwargs in [{"population":128},{"arrival_interval_ms":1000}]:
            with self.assertRaises(ValueError):
                builder.make_config(REPO,DATABASE,90,False,20261023,**kwargs)
        for population,interval in [(4,None),(2049,None),(64,51),(64,0)]:
            with self.assertRaises(ValueError): builder.corridor_people(20261023,population,90,interval)


if __name__ == "__main__":
    unittest.main()
