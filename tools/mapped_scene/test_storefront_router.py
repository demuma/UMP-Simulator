#!/usr/bin/env python3
"""Bounded narrow-passage routing, frozen-map topology and independent body audit."""
import contextlib
import importlib.util
import io
import json
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
        self.assertEqual(first["motion"], second["motion"])
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
                         "unresolved_128_person_drain_timeout_180s")
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(max(row["body_outside_walkable_area_m2"] for row in audit["routes"].values()), 0)
        self.assertEqual(context["navigation"]["allowed_center_polygons_sha256"],
                         storefront.canonical_hash(second["motion"]["navigation"]["allowed_center_polygons"]))

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


if __name__ == "__main__":
    unittest.main()
