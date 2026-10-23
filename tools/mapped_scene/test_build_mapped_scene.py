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

import yaml
from shapely.geometry import LineString

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
            # PNG header gives width/height without adding a new image dependency.
            raw = (output / "map_background.png").read_bytes()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(int.from_bytes(raw[16:20], "big"), 800)
            self.assertEqual(int.from_bytes(raw[20:24], "big"), 800)
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn("already exists", again.stderr)

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

    def test_historical_population_and_corridor_flow_guards(self):
        for kwargs in [{"population":128},{"arrival_interval_ms":1000}]:
            with self.assertRaises(ValueError):
                builder.make_config(REPO,DATABASE,90,False,20261023,**kwargs)
        for population,interval in [(4,None),(2049,None),(64,51),(64,0)]:
            with self.assertRaises(ValueError): builder.corridor_people(20261023,population,90,interval)


if __name__ == "__main__":
    unittest.main()
