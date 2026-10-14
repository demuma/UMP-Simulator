"""Comparison integrity checks and a small real seven-variant replay experiment."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from make_fixture import cell_id, make_fixture, make_policy
from run_comparison import VARIANTS, scientific_result, summarize


ROOT = Path(__file__).resolve().parents[2]
BINARY = Path(os.environ.get("UMP_REPLAY_BINARY", str(ROOT / "simulator/build/AggregationReplay")))


def summary_inputs():
    selected = {"selected": True, "assessment_status": "pass", "observation_contributions": 3,
                "checks": [{"metric": "distinct_contributors", "status": "pass"}]}
    suppressed = {"selected": False, "assessment_status": "fail", "observation_contributions": 2,
                  "checks": [{"metric": "distinct_contributors", "status": "fail"}]}
    result = {"input_observation_contributions": 5, "accounted_observation_contributions": 5,
              "windows": [{"cells": [selected, suppressed]}],
              "releases": [{"start_ms": 0, "end_ms": 400, "sealed_at_ms": 450,
                            "cells": [{"observation_contributions": 3}]}],
              "runtime": {"processing_ms": 1.0}}
    utility = {"summary": {"occupancy_mae": 2.0, "answered_query_coverage": .5}}
    return result, utility


class SummaryIntegrityTests(unittest.TestCase):
    def test_retention_and_utility_are_separate(self):
        result, utility = summary_inputs()
        summary = summarize(result, utility)
        self.assertEqual(summary["retained_observation_fraction"], .6)
        self.assertEqual(summary["answered_query_coverage"], .5)
        self.assertEqual(summary["occupancy_mae"], 2)
        self.assertEqual(summary["selected_policy_failures"], 0)
        self.assertEqual(summary["mean_release_age_ms"], 450)

    def test_selected_policy_failure_is_rejected(self):
        result, utility = summary_inputs()
        result["windows"][0]["cells"][0]["assessment_status"] = "fail"
        with self.assertRaises(ValueError):
            summarize(result, utility)

    def test_selected_failed_requirement_is_rejected(self):
        result, utility = summary_inputs()
        result["windows"][0]["cells"][0]["checks"][0]["status"] = "fail"
        with self.assertRaises(ValueError):
            summarize(result, utility)

    def test_public_selected_count_mismatch_is_rejected(self):
        result, utility = summary_inputs()
        result["releases"][0]["cells"][0]["observation_contributions"] = 2
        with self.assertRaises(ValueError):
            summarize(result, utility)

    def test_lost_or_duplicated_observations_are_rejected(self):
        result, utility = summary_inputs()
        result["accounted_observation_contributions"] = 4
        with self.assertRaises(ValueError):
            summarize(result, utility)
        result, utility = summary_inputs()
        result["releases"][0]["cells"][0]["observation_contributions"] = 6
        result["windows"][0]["cells"][0]["observation_contributions"] = 6
        with self.assertRaises(ValueError):
            summarize(result, utility)

    def test_impossible_matching_counts_are_rejected(self):
        for count in (-1, .5, True):
            with self.subTest(count=count):
                result, utility = summary_inputs()
                result["releases"][0]["cells"][0]["observation_contributions"] = count
                result["windows"][0]["cells"][0]["observation_contributions"] = count
                with self.assertRaises(ValueError):
                    summarize(result, utility)

    def test_runtime_is_the_only_excluded_determinism_field(self):
        original = {"runtime": {"processing_ms": 1}, "releases": [{"start_ms": 0}], "mode": "fixed"}
        repeated = copy.deepcopy(original)
        repeated["runtime"]["processing_ms"] = 2
        self.assertEqual(scientific_result(original), scientific_result(repeated))
        repeated["releases"][0]["start_ms"] = 100
        self.assertNotEqual(scientific_result(original), scientific_result(repeated))


class FixtureTests(unittest.TestCase):
    def test_fixture_is_deterministic_and_empty_measurements_stay_explicit(self):
        first = make_fixture()
        self.assertEqual(first, make_fixture())
        self.assertEqual(len(first["batches"]), 79)
        empty = [batch for batch in first["batches"] if not batch["observations"]]
        self.assertEqual([b["observed_at_ms"] for b in empty], list(range(6000, 7000, 100)))
        self.assertTrue(all(b["status"] == "measured" for b in empty))
        expected_ids = {observation["id"] for observation in first["batches"][0]["observations"]}
        self.assertEqual(len(expected_ids), 36)
        for batch in first["batches"]:
            if batch["observations"]:
                self.assertEqual({observation["id"] for observation in batch["observations"]}, expected_ids)

    def test_quadrant_ids_and_half_open_boundaries_match_core_convention(self):
        grid = {"x": 0, "y": 0, "width": 80, "height": 80, "leaf_depth": 1}
        self.assertEqual([cell_id(x, y, grid) for x, y in [(0, 0), (40, 0), (0, 40), (40, 40)]],
                         [12, 13, 14, 15])
        with self.assertRaises(ValueError):
            cell_id(80, 0, grid)
        with self.assertRaises(ValueError):
            cell_id(0, -1, grid)
        fixture = make_fixture()
        grid = fixture["coverage"]
        for batch in fixture["batches"]:
            for observation in batch["observations"]:
                x, y, side = grid["x"], grid["y"], grid["width"]
                for level in range(grid["leaf_depth"] - 1, -1, -1):
                    side /= 2
                    quadrant = (observation["cell_id"] >> (2 * level)) & 3
                    x += side * (quadrant & 1)
                    y += side * ((quadrant >> 1) & 1)
                self.assertTrue(x <= observation["x"] < x + side)
                self.assertTrue(y <= observation["y"] < y + side)


@unittest.skipUnless(BINARY.is_file(), "Build AggregationReplay to run the real comparison integration test")
class ComparisonIntegrationTests(unittest.TestCase):
    def test_all_seven_variants_share_frozen_input_and_repeat_exactly(self):
        fixture = make_fixture()
        fixture["end_ms"] = 1000
        fixture["batches"] = [b for b in fixture["batches"] if b["observed_at_ms"] < 1000]
        with tempfile.TemporaryDirectory(prefix="ump-comparison-test-") as temporary:
            directory = Path(temporary)
            source = directory / "input.json"
            config = directory / "policy.json"
            source.write_text(json.dumps(fixture))
            config.write_text(json.dumps(make_policy()))
            original_source, original_config = source.read_bytes(), config.read_bytes()
            bundle_paths = [directory / "first", directory / "second"]
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            for output in bundle_paths:
                command = [sys.executable, "-B", str(ROOT / "tools/evaluation/run_comparison.py"),
                           "--input", str(source), "--config", str(config),
                           "--binary", str(BINARY), "--output", str(output)]
                completed = subprocess.run(command, text=True, capture_output=True,
                                           env=environment, timeout=15)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                manifest = json.loads((output / "manifest.json").read_text())
                self.assertTrue(manifest["deterministic_repeat_verified"])
                self.assertEqual(len(manifest["variants"]), 7)
                self.assertEqual(manifest["input_sha256"], hashlib.sha256(original_source).hexdigest())
                self.assertEqual(manifest["config_sha256"], hashlib.sha256(original_config).hexdigest())
                self.assertEqual((output / "observations.json").read_bytes(), original_source)
                self.assertFalse((output / "determinism-repeat.json").exists())
                for variant in manifest["variants"]:
                    args = variant["command"]
                    self.assertEqual(args[args.index("--input") + 1], str((output / "observations.json").resolve()))
                    self.assertEqual(args[args.index("--config") + 1], str((output / "policy.yaml").resolve()))
                summary = json.loads((output / "summary.json").read_text())
                self.assertEqual(set(summary), {name for name, *_ in VARIANTS})
                sources = []
                for name, mode, depth, window in VARIANTS:
                    result = json.loads((output / f"{name}.json").read_text())
                    utility = json.loads((output / f"{name}.utility.json").read_text())
                    self.assertEqual(result["mode"], mode)
                    self.assertEqual(result["input_observation_contributions"], 324)
                    self.assertEqual(result["accounted_observation_contributions"], 324)
                    self.assertEqual(sum(w["input_observation_contributions"] for w in result["windows"]), 324)
                    self.assertEqual(utility["summary"]["reference_queries"], 64)
                    self.assertEqual(summary[name]["selected_policy_failures"], 0)
                    if depth is not None:
                        self.assertEqual(result["parameters"]["fixed_depth"], depth)
                        self.assertEqual(result["parameters"]["window_ms"], window)
                    sources.append(result["source"])
                self.assertTrue(all(source == sources[0] for source in sources))
            for name, *_ in VARIANTS:
                first = json.loads((bundle_paths[0] / f"{name}.json").read_text())
                second = json.loads((bundle_paths[1] / f"{name}.json").read_text())
                self.assertEqual(scientific_result(first), scientific_result(second))
            self.assertEqual(source.read_bytes(), original_source)
            self.assertEqual(config.read_bytes(), original_config)
            manifest_bytes = (bundle_paths[1] / "manifest.json").read_bytes()
            # Reusing a bundle directory must fail rather than replacing its evidence.
            repeated = subprocess.run(command, text=True, capture_output=True,
                                      env=environment, timeout=5)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual((bundle_paths[1] / "manifest.json").read_bytes(), manifest_bytes)


if __name__ == "__main__":
    unittest.main()
