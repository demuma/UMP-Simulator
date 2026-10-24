#!/usr/bin/env python3
"""Bounded narrow-passage routing, frozen-map topology and independent body audit."""
import contextlib
import copy
import importlib.util
import io
import json
import math
import pathlib
import subprocess
import sys
import tempfile
import unittest

import yaml
from unittest import mock

from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location("storefront_router_builder", HERE / "build_mapped_scene.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
storefront = builder.storefront_module()
RUNNER_SPEC = importlib.util.spec_from_file_location("storefront_test_runner", HERE / "run_scene.py")
runner = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(runner)
DATABASE = "UMP_Mapped_94cf3e26a2a447c084c353f02695a2cb"


class SafeRouterTests(unittest.TestCase):
    def test_existing_lattice_route_and_direct_route_do_not_use_fallback(self):
        router = storefront.SafeRouter(box(0, 0, 10, 10).difference(box(4, 2, 6, 8)),
                                       experimental_narrow_passages=True)
        with mock.patch.object(router, "_visibility_route", side_effect=AssertionError("Unexpected fallback")):
            self.assertEqual(router.route([1, 5], [9, 5]), [[1, 5], [4.0, 2.0], [6.0, 2.0], [9, 5]])
            self.assertEqual(router.route([1, 1], [9, 1]), [[1, 1], [9, 1]])
        self.assertEqual(router.visibility_graphs, {})

    def test_connected_bend_without_any_lattice_node_uses_exact_vertices(self):
        geometry = LineString([(1.13, 1.13), (1.13, 5.13), (5.13, 5.13)]).buffer(
            .02, cap_style=2, join_style=2)
        router = storefront.SafeRouter(geometry, experimental_narrow_passages=True)
        self.assertEqual(router.valid, set())
        with self.assertRaisesRegex(ValueError, "Route endpoint cannot reach"):
            router._lattice_route([1.13, 1.2], [5.0, 5.13])
        path = router.route([1.13, 1.2], [5.0, 5.13])
        self.assertTrue(geometry.covers(LineString(path)))
        self.assertLessEqual(len(path), 4)
        self.assertTrue(router.visibility_graphs)

    def test_visibility_graph_keeps_holes_blocked_and_caches_only_static_edges(self):
        hole = box(4, 2, 6, 8)
        geometry = box(0, 0, 10, 10).difference(hole)
        router = storefront.SafeRouter(geometry)
        first = router._visibility_route([1, 5], [9, 5])
        line = LineString(first)
        self.assertTrue(geometry.covers(line))
        self.assertEqual(line.intersection(hole.buffer(-1e-7)).length, 0)
        vertices, cache = router.visibility_graphs[0]
        original_edges = set(cache)
        self.assertTrue(original_edges)
        self.assertTrue(all(2 <= a < b < len(vertices) + 2 for a, b in cache))
        self.assertEqual(router._visibility_route([1, 5], [9, 5]), first)
        self.assertLessEqual(len(cache), len(vertices) * (len(vertices) - 1) // 2)
        self.assertTrue(original_edges.issubset(cache))

    def test_disconnected_islands_and_outside_endpoints_stay_unroutable(self):
        router = storefront.SafeRouter(unary_union([box(0, 0, 5, 5), box(6, 0, 10, 5)]),
                                       experimental_narrow_passages=True)
        for start, goal in [([4, 2], [7, 2]), ([7, 2], [4, 2]), ([-1, 2], [2, 2])]:
            with self.subTest(start=start, goal=goal):
                with self.assertRaisesRegex(ValueError, "No connected boundary/door route"):
                    router.route(start, goal)
        self.assertEqual(router.visibility_graphs, {})

    def test_visibility_vertex_budget_is_explicit_and_never_relaxes_geometry(self):
        geometry = Point(10, 10).buffer(9, resolution=300).difference(box(9, 9, 11, 11))
        router = storefront.SafeRouter(geometry)
        with self.assertRaisesRegex(ValueError, "bounded vertex limit"):
            router._visibility_route([5, 10], [15, 10])
        self.assertEqual(router.visibility_graphs, {})


class FrozenBarkhofRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.local, cls.layers, _, provenance = builder.load_source(REPO)
        _, _, cls.safe, cls.rows = storefront.build_geometry(
            REPO, cls.local, cls.layers, builder.access_module(), provenance["source_geometry_sha256"])
        cls.buildings = unary_union([g for props, g in cls.local if props["kind"] == "building"])

    def test_barkhof_routes_both_directions_without_changing_allowed_geometry(self):
        before = storefront.canonical_hash(self.rows)
        router = storefront.SafeRouter(self.safe, experimental_narrow_passages=True)
        with self.assertRaisesRegex(ValueError, "No connected boundary/door route"):
            storefront.SafeRouter(self.safe).route([65, 35], [68, 45])
        for start, goal in [([65, 35], [68, 45]), ([68, 45], [65, 35])]:
            with self.subTest(start=start, goal=goal):
                # Regression trigger: this exact connected polygon was missed
                # by the existing coarse graph. Keep proving that the fallback,
                # rather than accidentally changing the original grid, repairs it.
                with self.assertRaisesRegex(ValueError, "No connected boundary/door route"):
                    router._lattice_route(start, goal)
                path = router.route(start, goal)
                self.assertEqual(path[0], start)
                self.assertEqual(path[-1], goal)
                self.assertLessEqual(len(path), 64)
                line = LineString(path)
                self.assertTrue(self.safe.buffer(1e-8).covers(line))
                self.assertGreater(line.intersection(self.layers["road"]).length, 1)
                # Independent full-body checks use the original walking/building
                # layers, no facade exemptions and no widened router geometry.
                body = line.buffer(storefront.CLEARANCE, resolution=32)
                self.assertLess(body.difference(self.layers["walking"]).area, 1e-6)
                self.assertLess(body.intersection(self.buildings).area, 1e-6)
                self.assertEqual(router.route(start, goal), path)
                self.assertEqual(storefront.SafeRouter(self.safe, experimental_narrow_passages=True).route(start, goal), path)
        self.assertEqual(storefront.canonical_hash(storefront.polygon_rows(self.safe)), before)
        self.assertEqual(router.grid_step, .5)
        self.assertEqual(router.grid_side, 161)
        vertices, cache = router.visibility_graphs[0]
        self.assertEqual(len(vertices), 525)
        self.assertLessEqual(len(cache), len(vertices) * (len(vertices) - 1) // 2)

    def test_finite_cohort_holding_capacity_scales_per_direction_with_explicit_limit(self):
        router = storefront.SafeRouter(self.safe, experimental_narrow_passages=True)
        guide = router.route([65, 35], [68, 45])
        routes = [{"id": f"forward-{index}", "points": copy.deepcopy(guide),
                   "start_portal": "a", "end_portal": "b"} for index in range(65)]
        routes += [{"id": f"reverse-{index}", "points": copy.deepcopy(guide[::-1]),
                    "start_portal": "b", "end_portal": "a"} for index in range(70)]
        passage, affected = storefront.controlled_barkhof_passage(router, routes, set())
        self.assertEqual(affected, 135)
        self.assertEqual(len(passage["holding_points_a"]), 65)
        self.assertEqual(len(passage["holding_points_b"]), 70)
        overflow = [{"id": f"overflow-{index}", "points": copy.deepcopy(guide),
                     "start_portal": "a", "end_portal": "b"} for index in range(257)]
        with self.assertRaisesRegex(ValueError, "at most 256 passage episodes per direction"):
            storefront.controlled_barkhof_passage(router, overflow, set())

    def test_barkhof_fallback_still_rejects_real_building_interior(self):
        router = storefront.SafeRouter(self.safe, experimental_narrow_passages=True)
        with self.assertRaisesRegex(ValueError, "No connected boundary/door route"):
            router.route([65, 35], [40, 79])


class ExperimentalNarrowPassageConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.default = builder.make_config(REPO, DATABASE, 180, False, 20261023,
                                          "storefronts", 64, 1000)
        cls.experimental = builder.make_config(REPO, DATABASE, 180, False, 20261023,
                                               "storefronts", 64, 1000,
                                               experimental_narrow_passages=True)
        _, cls.local, cls.layers, _, _ = builder.load_source(REPO)

    def test_default_source_matches_accepted_frozen_source_without_storing_motion(self):
        # Aggregate digest of the accepted, frozen seed20261023/64/1000-ms
        # mapped_scene. The production source, paths, profiles and schedules
        # remain unchanged; generated movement files are not a test dependency.
        self.assertEqual(storefront.canonical_hash(self.default["mapped_scene"]),
                         "cada80b07538aa5c8add0eb6b233e7653d5e15c2409405b0a579a4c7e04b00a6")
        self.assertEqual(sum(LineString(row["points"]).intersection(self.layers["road"]).length > 1e-7
                             for row in self.default["mapped_scene"]["routes"]), 0)
        _, _, construction, _ = builder.storefront_scene(str(REPO), 20261023, 64, 180, 1000, None, False)
        self.assertFalse(construction["navigation_fallback"]["enabled"])
        self.assertEqual(construction["navigation_fallback"]["status"], "disabled_original_lattice_default")

    def test_opt_in_repairs_new_guidance_only_with_identical_geometry_and_policy(self):
        first, second = self.default["mapped_scene"], self.experimental["mapped_scene"]
        self.assertNotIn("narrow_passages", first["motion"]["navigation"])
        experimental_motion = copy.deepcopy(second["motion"])
        experimental_motion["navigation"].pop("narrow_passages")
        self.assertEqual(first["motion"], experimental_motion)
        self.assertNotEqual(first["routes"], second["routes"])
        crossing = sum(LineString(row["points"]).intersection(self.layers["road"]).length > 1e-7
                       for row in second["routes"])
        self.assertEqual(crossing, 54)
        for key in ["agents", "region_taxonomy", "regions", "sensors"]:
            self.assertEqual(self.default[key], self.experimental[key])
        _, context, construction, audit = builder.storefront_scene(str(REPO), 20261023, 64, 180, 1000, None, True)
        self.assertTrue(construction["navigation_fallback"]["enabled"])
        self.assertEqual(construction["navigation_fallback"]["status"], "experimental_opt_in")
        self.assertEqual(construction["navigation_fallback"]["experimental_native_coordination_gate"],
                         "verified_128_person_sources_500_total_pending")
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(max(row["body_outside_walkable_area_m2"] for row in audit["routes"].values()), 0)
        self.assertEqual(context["navigation"]["allowed_center_polygons_sha256"],
                         storefront.canonical_hash(second["motion"]["navigation"]["allowed_center_polygons"]))

    def test_explicit_passage_has_safe_staging_and_complete_directed_route_guides(self):
        scene = self.experimental["mapped_scene"]
        allowed = storefront.geometry_from_rows(scene["motion"]["navigation"]["allowed_center_polygons"])
        passages = scene["motion"]["navigation"]["narrow_passages"]
        self.assertEqual(len(passages), 1)
        passage = passages[0]
        self.assertEqual(passage["id"], "barkhof-walking-neck")
        self.assertEqual(passage["protection_radius_m"], 1.15)
        self.assertEqual(passage["max_batch_size"], 6)
        guide = passage["centerline"]
        self.assertEqual(guide[0], [65, 35])
        self.assertEqual(guide[-1], [68, 45])
        self.assertTrue(allowed.buffer(1e-8).covers(LineString(guide)))
        for field, endpoint in [("holding_points_a", guide[0]), ("holding_points_b", guide[-1])]:
            points = passage[field]
            self.assertEqual(len(points), 64)
            self.assertEqual(len({tuple(point) for point in points}), len(points))
            for index, point in enumerate(points):
                self.assertTrue(allowed.covers(Point(point)))
                self.assertTrue(allowed.covers(LineString([endpoint, point])))
                self.assertGreater(Point(point).distance(LineString(guide)), 1.3)
                self.assertGreater(math.dist(endpoint, point), 3.55)
                self.assertTrue(all(math.dist(point, other) >= 1.1 - 1e-10 for other in points[index + 1:]))
        controlled_routes = 0
        for route in scene["routes"]:
            points = route["points"]
            matches = sum(points[index:index + len(guide)] in (guide, guide[::-1])
                          for index in range(len(points) - len(guide) + 1))
            crossing = LineString(points).intersection(LineString([(64, 39), (70, 39)]))
            if not crossing.is_empty:
                self.assertEqual(matches, 1)
                controlled_routes += 1
            else:
                self.assertEqual(matches, 0)
                self.assertGreater(LineString(points).distance(LineString(guide)), 1.15)
        self.assertEqual(controlled_routes, 54)
        _, _, construction, _ = builder.storefront_scene(str(REPO), 20261023, 64, 180, 1000, None, True)
        metadata = construction["navigation_fallback"]["native_passage_coordination"]
        self.assertEqual(metadata["affected_routes"], controlled_routes)
        self.assertEqual(metadata["holding_points_per_side"], {"a": 64, "b": 64})
        self.assertEqual(metadata["holding_point_limit_per_side"], 256)
        self.assertEqual(metadata["exit_apron_length_m"], 2.4)
        self.assertEqual(metadata["holding_endpoint_exclusion_radius_m"], 3.55)

    def test_experimental_option_requires_storefronts_before_source_or_database_work(self):
        for mode in ["integration", "corridor", "buildings"]:
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, "require storefronts mode"):
                    builder.make_config(REPO, DATABASE, 90, False, 20261023, mode,
                                        experimental_narrow_passages=True)
                for module, arguments in [(builder, ["--output", "/not-created", "--database", DATABASE]),
                                           (runner, [])]:
                    error = io.StringIO()
                    with mock.patch.object(sys, "argv", ["scene", *arguments, "--motion-mode", mode,
                                                          "--experimental-narrow-passages"]), \
                            mock.patch.object(module, "load_source", create=True,
                                              side_effect=AssertionError("Source work before validation")), \
                            mock.patch.object(runner, "mongo", side_effect=AssertionError("Unexpected database work")), \
                            contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as raised:
                        module.main()
                    self.assertEqual(raised.exception.code, 2)
                    self.assertIn("--experimental-narrow-passages requires --motion-mode storefronts", error.getvalue())

    def test_generator_cli_records_experimental_gate_in_manifest(self):
        with tempfile.TemporaryDirectory(prefix="ump-experimental-topology-cli-") as temp:
            output = pathlib.Path(temp) / "scene"
            result = subprocess.run([sys.executable, str(HERE / "build_mapped_scene.py"),
                "--repo", str(REPO), "--database", DATABASE, "--output", str(output),
                "--motion-mode", "storefronts", "--population", "5", "--duration-s", "30",
                "--arrival-interval-ms", "1000", "--experimental-narrow-passages"],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((output / "scene_manifest.json").read_text())
            self.assertTrue(manifest["building_access"]["navigation_fallback"]["enabled"])
            self.assertEqual(manifest["building_access"]["navigation_fallback"]["status"], "experimental_opt_in")
            self.assertEqual(manifest["route_geometry"]["status"], "pass")
            self.assertEqual(len(yaml.safe_load((output / "config.yaml").read_text())["mapped_scene"]["people"]), 5)

    def test_runner_forwards_opt_in_only_when_requested_without_database_actions(self):
        class BuilderInvocation(Exception):
            pass
        for enabled in [False, True]:
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory(prefix="ump-runner-forward-") as temp:
                arguments = ["run_scene", "--output", str(pathlib.Path(temp) / "scene"), "--no-record"]
                if enabled:
                    arguments.append("--experimental-narrow-passages")
                with mock.patch.object(sys, "argv", arguments), \
                        mock.patch.object(pathlib.Path, "is_file", return_value=True), \
                        mock.patch.object(runner.shutil, "which", return_value="mock-mongosh"), \
                        mock.patch.object(runner.importlib.util, "find_spec", return_value=object()), \
                        mock.patch.object(runner, "mongo", return_value=[]) as mongo_call, \
                        mock.patch.object(runner.subprocess, "run", side_effect=BuilderInvocation) as invoke, \
                        self.assertRaises(BuilderInvocation):
                    runner.main()
                command = invoke.call_args.args[0]
                self.assertEqual("--experimental-narrow-passages" in command, enabled)
                self.assertEqual(command[command.index("--motion-mode") + 1], "storefronts")
                self.assertEqual(mongo_call.call_count, 1)


class UrbanBoundarySourcePairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location("urban_boundary_test",HERE/"urban_traffic_scene.py")
        cls.urban=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.urban)

    def test_nearest_sink_projection_rejects_same_edge_and_adjacent_corner_skims(self):
        measure=self.urban.boundary_pair_measures
        self.assertFalse(measure([80,75],"east",[[80,70],[80,80]])["eligible"])
        # Different interval labels cannot make a same-edge tangent observable.
        self.assertFalse(measure([80,75],"east",[[80,0],[80,65]])["eligible"])
        corner=measure([80,78.4],"east",[[60,80],[80,80]])
        self.assertGreater(corner["distance_m"],1)
        self.assertEqual(corner["inward_progress_m"],0)
        self.assertFalse(corner["eligible"])
        self.assertTrue(measure([80,78.4],"east",[[60,80],[79,80]])["eligible"])
        self.assertFalse(measure([80,79.9],"east",[[79.9,80],[80,80]])["eligible"])
        for start,side,sink in [([80,50],"east",[[0,0],[0,80]]),([0,50],"west",[[80,0],[80,80]]),
                                ([50,0],"north",[[0,80],[80,80]]),([50,80],"south",[[0,0],[80,0]])]:
            self.assertTrue(measure(start,side,sink)["eligible"])

    def test_repair_is_deterministic_preserves_valid_routes_and_does_not_relabel_sources(self):
        class Router:
            def route(self,a,b):return [copy.deepcopy(a),copy.deepcopy(b)]
        boundaries=[{"id":name,"mode":"walking","side":name,"points":points,"spawn_supported":True}
            for name,points in [("east",[[80,0],[80,80]]),("west",[[0,0],[0,80]]),
                                ("north",[[0,0],[80,0]]),("south",[[0,80],[80,80]])]]
        original=[{"id":"same-edge","points":[[80,50],[40,30],[80,60]],"start_portal":"east","end_portal":"east"},
                  {"id":"corner","points":[[80,78.4],[79.5,80]],"start_portal":"east","end_portal":"south"},
                  {"id":"valid","points":[[80,50],[0,50]],"start_portal":"east","end_portal":"west"}]
        first,second=copy.deepcopy(original),copy.deepcopy(original)
        report=self.urban.repair_boundary_pairs(first,boundaries,Router(),20261024)
        self.assertEqual(report["repaired_routes"],2)
        self.assertEqual(first[-1],original[-1])
        self.assertEqual([r["id"] for r in first],[r["id"] for r in original])
        self.assertEqual([r["start_portal"] for r in first],[r["start_portal"] for r in original])
        self.assertEqual(report,self.urban.repair_boundary_pairs(second,boundaries,Router(),20261024))
        self.assertEqual(first,second)
        lookup={r["id"]:r for r in boundaries}
        for route in first:
            self.assertTrue(self.urban.boundary_pair_measures(route["points"][0],lookup[route["start_portal"]]["side"],
                lookup[route["end_portal"]]["points"])["eligible"])

    def test_no_valid_inward_sink_fails_instead_of_emitting_a_degenerate_source(self):
        boundaries=[{"id":"east","mode":"walking","side":"east","points":[[80,0],[80,80]],"spawn_supported":True}]
        routes=[{"id":"bad","points":[[80,50],[80,60]],"start_portal":"east","end_portal":"east"}]
        with self.assertRaisesRegex(ValueError,"No connected inward sink"):
            self.urban.repair_boundary_pairs(routes,boundaries,None,1)


class UrbanTrafficTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=builder.make_config(REPO,DATABASE,120,False,20261024,"storefronts",128,150,urban_traffic=True)
        cls.scene,cls.context,cls.construction,cls.audit=builder.storefront_scene(str(REPO),20261024,128,120,150,None,False,True)
        _,cls.local,cls.layers,_,_=builder.load_source(REPO)

    def test_mode_specific_road_routes_keep_envelopes_and_taxonomy(self):
        navigation=self.scene["motion"]["navigation"]
        self.assertNotIn("narrow_passages",navigation)
        self.assertEqual(navigation["door_max_batch_size"],6)
        self.assertEqual(self.scene["motion"]["clearance_m"],.05)
        self.assertEqual(navigation["center_clearance_m"],.5)
        self.assertEqual(len(navigation["spaces"]),2)
        self.assertTrue(all(s["center_clearance_m"]==1.05 for s in navigation["spaces"]))
        east,west=[storefront.geometry_from_rows(s["allowed_center_polygons"]) for s in navigation["spaces"]]
        self.assertGreater(east.distance(west),2.1)
        routes={r["id"]:r for r in self.scene["routes"]}
        rider_types={"Adult Cyclist","Senior Cyclist","Adult E-Scooter Driver"}
        riders=[p for p in self.scene["people"] if p["type"] in rider_types]
        self.assertEqual(len(riders),26)
        self.assertEqual({p["type"] for p in riders},rider_types)
        directions=set()
        for person in riders:
            self.assertGreaterEqual(person["speed_mps"],3)
            self.assertLessEqual(person["speed_mps"],4)
            self.assertEqual(person["radius_m"],.65 if "Scooter" in person["type"] else 1)
            self.assertEqual(len(person["episodes"]),1)
            route=routes[person["episodes"][0]["route_id"]]
            self.assertIn(route["navigation_space"],("carriageway-east","carriageway-west"))
            self.assertIn("end_boundary",route)
            self.assertLess(LineString(route["end_boundary"]).distance(Point(route["points"][-1])),1e-7)
            directions.add(route["points"][0][0] < route["points"][-1][0])
            self.assertLess(LineString(route["points"]).buffer(1.05,resolution=32).intersection(box(0,0,80,80)).difference(self.layers["road"]).area,1e-6)
        self.assertEqual(directions,{False,True})
        taxonomy=self.cfg["sensors"][0]["aggregation"]["semantic_taxonomy"]["nodes"]
        self.assertEqual({r["id"]:r["loss"] for r in taxonomy if r["id"] in ("pedestrian","cyclist","e_scooter_rider")},
                         {"pedestrian":.5,"cyclist":.5,"e_scooter_rider":.5})
        self.assertEqual(builder.audit_config(self.cfg)["scheduled_people"],128)

    def test_seeded_connectors_are_explicit_wide_and_not_whole_road_permissions(self):
        self.assertEqual(len(self.construction["crossings"]),5)
        self.assertTrue(all(r["width_m"]==4 for r in self.construction["crossings"]))
        self.assertGreater(self.construction["demand"]["targeted_distributed_crossing_trips"],0)
        allowed=storefront.geometry_from_rows(self.scene["motion"]["navigation"]["allowed_center_polygons"])
        self.assertGreater(self.layers["road"].difference(allowed).area,100)
        self.assertEqual(self.audit["status"],"pass")
        self.assertEqual(max(r["body_building_intersection_outside_portal_m2"] for r in self.audit["routes"].values()),0)
        second=builder.storefront_scene(str(REPO),20261024,128,120,150,None,False,True)[0]
        self.assertEqual(storefront.canonical_hash(self.scene),storefront.canonical_hash(second))
        self.assertTrue(all(r["provenance"].startswith("synthetic_") for r in self.construction["crossings"]))

    def test_options_reject_unsupported_combinations_before_database_actions(self):
        for mode in ("integration","corridor","buildings"):
            with self.assertRaisesRegex(ValueError,"requires storefronts"):
                builder.make_config(REPO,DATABASE,120,False,20261024,mode,128,150,urban_traffic=True)
        with self.assertRaisesRegex(ValueError,"separate scenario"):
            builder.make_config(REPO,DATABASE,120,False,20261024,"storefronts",128,150,
                                urban_traffic=True,experimental_narrow_passages=True)
        for arguments,expected in [(["--motion-mode","corridor","--urban-traffic"],"requires --motion-mode storefronts"),
                                   (["--urban-traffic","--experimental-narrow-passages"],"mutually exclusive")]:
            for module,prefix in [(builder,["--output","/not-created","--database",DATABASE]),(runner,[])]:
                with mock.patch.object(sys,"argv",["scene",*prefix,*arguments]), \
                     mock.patch.object(runner,"mongo",side_effect=AssertionError("Unexpected database operation")), \
                     contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as raised:
                    module.main()
                self.assertEqual(raised.exception.code,2)

    def test_runner_forwards_urban_controls(self):
        class Invocation(Exception):
            pass
        arguments=["run_scene","--urban-traffic","--population","256","--arrival-interval-ms","100",
                   "--road-user-fraction",".25","--distributed-crossing-fraction",".3","--pedestrian-clearance-m",".04","--no-record"]
        with mock.patch.object(sys,"argv",arguments),mock.patch.object(pathlib.Path,"is_file",return_value=True), \
             mock.patch.object(runner.shutil,"which",return_value="mock-mongosh"), \
             mock.patch.object(runner.importlib.util,"find_spec",return_value=object()), \
             mock.patch.object(runner,"mongo",return_value=[]), \
             mock.patch.object(runner.subprocess,"run",side_effect=Invocation) as invoke,self.assertRaises(Invocation):
            runner.main()
        command=invoke.call_args.args[0]
        for flag,value in [("--road-user-fraction","0.25"),("--distributed-crossing-fraction","0.3"),("--pedestrian-clearance-m","0.04")]:
            self.assertEqual(command[command.index(flag)+1],value)
        self.assertIn("--urban-traffic",command)


if __name__ == "__main__":
    unittest.main()
