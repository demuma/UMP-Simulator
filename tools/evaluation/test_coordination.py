"""Cell-local production replay, independent space-time oracle and corruption tests.

The source is deliberately analytical. These checks establish coordination and
raw-observation accounting, not a physical mobility model or privacy guarantee.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from oracle import decode_cell, validate_result
from empirical_privacy import export_public, feature_names, feature_vector

ROOT = Path(__file__).resolve().parents[2]
BINARY = Path(os.environ.get("UMP_REPLAY_BINARY", str(ROOT / "simulator/build/AggregationReplay")))


def grid(depth=3):
    return dict(x=0, y=0, width=80, height=80, leaf_depth=depth)


def observation(identity, cell_id=192, depth=3, kind="pedestrian"):
    geometry = decode_cell(grid(depth), cell_id, depth)
    return dict(id=identity, type=kind, cell_id=cell_id,
                x=geometry["x"] + geometry["width"] / 3,
                y=geometry["y"] + geometry["height"] / 3)


def source(end=1200, depth=3, observations=None, absent=None):
    observations = observations or (lambda time: [observation("a", 192), observation("b", 193)])
    absent = absent or {}
    batches = []
    for sequence, time in enumerate(range(100, end, 100), 1):
        if absent.get(time) == "missing":
            continue
        unavailable = absent.get(time) == "unavailable"
        batches.append(dict(sequence=sequence, observed_at_ms=time,
                            status="unavailable" if unavailable else "measured",
                            observations=[] if unavailable else observations(time)))
    return dict(schema="ump.observation-replay.v1", run_id="coordination-regression", sensor_id="agbs",
                coverage=grid(depth), sampling_period_ms=100, end_ms=end, batches=batches)


def policy(support=2, side=40, window=200, extension=100, maximum=800,
           regions=(), max_active=128):
    return dict(application_id="coordination-app", window_ms=window,
        max_observations_per_window=1000000,
        history=dict(retention_ms=2000, max_bins=32, max_observations=100000,
                     max_identity_bytes=16000000, max_buckets=128),
        spatial_selection=dict(min_depth=2, max_evaluations=4096),
        temporal_adaptation=dict(extension_step_ms=extension, max_window_ms=maximum,
                                 max_evaluations=32, coordination="cell_local", max_active_cells=max_active),
        policy_tree=dict(id="coordination-policy", version="1", max_nodes=65536,
            execution=dict(publication_model="private_final_snapshot", strategy="spatial_first"),
            root=dict(distinct_contributors=dict(min=support), cell_side_m=dict(max=side),
                      window_duration_ms=dict(max=maximum), age_at_evaluation_ms=dict(max=maximum)),
            regions=[region["id"] for region in regions]), policy_regions=list(regions))


def region(cell_id, requirements, depth=3):
    geometry = decode_cell(grid(depth), cell_id, depth)
    return dict(id=f"region-{cell_id}", type=f"type-{cell_id}",
                **{key: geometry[key] for key in ("x", "y", "width", "height")}, requirements=requirements)


@unittest.skipUnless(BINARY.is_file(), "Build AggregationReplay for cell-local integration")
class CoordinationReplayTests(unittest.TestCase):
    def run_core(self, data, config, mode="spatial_first", timeout=30):
        with tempfile.TemporaryDirectory(prefix="ump-coordination-") as temporary:
            directory = Path(temporary)
            input_file, config_file, output = (directory / name for name in ("input.json", "policy.json", "result.json"))
            input_file.write_text(json.dumps(data), encoding="utf-8")
            config_file.write_text(json.dumps(config), encoding="utf-8")
            completed = subprocess.run([str(BINARY), "--input", str(input_file), "--config", str(config_file),
                                        "--mode", mode, "--output", str(output)],
                                       capture_output=True, text=True, timeout=timeout)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            actual = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(actual["parameters"]["coordination"], "cell_local")
        report = validate_result(data, config, actual, max_cells=200000)
        self.assertTrue(report["valid"], json.dumps(report["violations"][:20], indent=2))
        self.assertEqual(actual["input_observation_contributions"], actual["accounted_observation_contributions"])
        self.assertTrue(all("coordination_cell" in window for window in actual["windows"]))
        return actual, report

    def test_sibling_policies_generate_independent_duration_windows(self):
        config = policy(support=1, side=10, regions=[
            region(192, dict(window_duration_ms=dict(min=400))),
            region(193, dict(window_duration_ms=dict(max=200)))])
        actual, _ = self.run_core(source(end=950), config)
        windows = {(w["coordination_cell"]["cell_id"], w["start_ms"], w["end_ms"])
                   for w in actual["windows"]}
        self.assertIn((193, 0, 200), windows)
        self.assertIn((192, 0, 400), windows)
        self.assertIn((193, 200, 400), windows)
        self.assertNotIn((192, 0, 200), windows)
        self.assertTrue(any(w["end_ms"] == 950 and w["truncated"] for w in actual["windows"]))

    def test_sparse_siblings_fallback_spatially_under_both_strategy_orders(self):
        data, config = source(end=1800), policy()
        for mode, expected_end in (("temporal_first", 200), ("spatial_first", 800)):
            with self.subTest(mode=mode):
                actual, report = self.run_core(data, config, mode)
                coarsened = [(release, cell) for release in actual["releases"]
                             for cell in release["cells"] if cell["depth"] < 3]
                self.assertTrue(coarsened)
                self.assertTrue(any(release["start_ms"] == 0 and release["end_ms"] == expected_end
                                    for release, _ in coarsened))
                self.assertGreater(report["released_observation_contributions"], 0)

    def test_mixed_depth_frontier_deduplicates_moving_identities(self):
        def observations(time):
            left, right = (768, 769) if time % 200 else (769, 768)
            return [observation("a", left, 4), observation("b", right, 4), observation("c", 770, 4)]
        data, config = source(end=1800, depth=4, observations=observations), policy(support=3)
        actual, _ = self.run_core(data, config)
        cells = [cell for release in actual["releases"] for cell in release["cells"]]
        self.assertTrue(any(cell["depth"] < 4 for cell in cells))
        self.assertTrue(all(cell["distinct_road_users"] == 3 for cell in cells))
        self.assertTrue(any(w["coordination_cell"]["depth"] < 4
                            and w["input_observation_contributions"] == 0 for w in actual["windows"]),
                        "The sparse ownership frontier did not preserve known-empty coarser areas")

    def test_missing_unavailable_and_fractional_final_window_are_preserved(self):
        for status in ("missing", "unavailable"):
            with self.subTest(status=status):
                data = source(end=950, absent={200: status})
                actual, _ = self.run_core(data, policy())
                self.assertTrue(any(w["coverage"] == "incomplete" for w in actual["windows"]))
                self.assertTrue(any(w[f"{status}_samples"] > 0 for w in actual["windows"]))
                self.assertTrue(any(w["end_ms"] == 950 and w["truncated"] for w in actual["windows"]))

    def test_measured_empty_domain_retires_without_public_zero_counts(self):
        actual, report = self.run_core(source(end=450, observations=lambda _: []), policy())
        self.assertTrue(report["no_release"])
        self.assertFalse(actual["releases"])
        self.assertTrue(actual["windows"])
        self.assertTrue(all(w["input_observation_contributions"] == 0 for w in actual["windows"]))

    def test_two_minute_sustained_replay_preserves_every_source_contribution(self):
        def observations(time):
            # Eight continuously observed identities turn over every second. Four
            # occupied leaves remain sparse inside a depth-four input domain.
            return [observation(f"person-{time // 1000}-{index}", cell, 4,
                                "bicycle" if index % 2 else "pedestrian")
                    for index, cell in enumerate((768, 768, 769, 769, 832, 832, 833, 833))]
        data = source(end=120000, depth=4, observations=observations)
        actual, report = self.run_core(data, policy(support=3), timeout=60)
        self.assertEqual(actual["input_observation_contributions"], 1199 * 8)
        self.assertGreater(report["released_cell_count"], 100)
        self.assertEqual(max(w["end_ms"] for w in actual["windows"]), 120000)

    def test_public_export_and_features_accept_disjoint_local_intervals_without_private_leakage(self):
        data = source(end=950)
        config = policy(support=1, side=10, regions=[
            region(192, dict(window_duration_ms=dict(min=400))),
            region(193, dict(window_duration_ms=dict(max=200)))])
        actual, _ = self.run_core(data, config)
        public = export_public(actual)
        self.assertEqual(len(public["releases"]), len(actual["releases"]))
        encoded = json.dumps(public, allow_nan=False)
        for private_key in ("coordination_cell", "windows", "runtime", "input_observation_contributions",
                            "configuration_yaml", data["run_id"]):
            self.assertNotIn(private_key, encoded)
        first = data["batches"][0]["observations"][0]
        knowledge = [dict(observed_at_ms=100, x=first["x"], y=first["y"], cell_id=first["cell_id"])]
        self.assertEqual(len(feature_vector(public, knowledge)), len(feature_names()))
        changed_private = deepcopy(actual)
        changed_private["windows"] = [{"private_road_users": ["secret-person"]}]
        changed_private["runtime"] = {"processing_ms": 999999}
        self.assertEqual(export_public(changed_private), public)
        for mutation in (lambda r: r["releases"][0]["coordination_cell"].update(x=-1),
                         lambda r: r["releases"][0]["coordination_cell"].update(secret="private"),
                         lambda r: r["releases"].append(deepcopy(r["releases"][0]))):
            broken = deepcopy(actual)
            mutation(broken)
            with self.assertRaises(ValueError):
                export_public(broken)

    def test_corrupt_local_scope_interval_counts_and_empty_retirement_are_detected(self):
        data, config = source(end=950), policy()
        original, _ = self.run_core(data, config)
        self.assertTrue(original["releases"])
        empty_index = next(i for i, w in enumerate(original["windows"])
                           if w["input_observation_contributions"] == 0)
        occupied_index = next(i for i, w in enumerate(original["windows"])
                              if w["input_observation_contributions"] > 0)
        mutations = {
            "missing_scope": lambda r: r["windows"][0].pop("coordination_cell"),
            "wrong_scope_geometry": lambda r: r["windows"][0]["coordination_cell"].update(x=-1),
            "duplicate_window": lambda r: r["windows"].append(deepcopy(r["windows"][0])),
            "dropped_empty_domain": lambda r: r["windows"].pop(empty_index),
            "duplicate_public_interval": lambda r: r["releases"].append(deepcopy(r["releases"][0])),
            "changed_public_count": lambda r: r["releases"][0]["cells"][0].update(distinct_road_users=999),
            "overlapping_retirement": lambda r: r["windows"][-1].update(start_ms=0),
            "public_scope_excludes_cell": lambda r: r["releases"][0].update(
                coordination_cell=decode_cell(data["coverage"], 15, 1)),
            "diagnostic_scope_excludes_cell": lambda r: r["windows"][occupied_index].update(
                coordination_cell=decode_cell(data["coverage"], 15, 1)),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                bad = deepcopy(original)
                mutate(bad)
                report = validate_result(data, config, bad)
                self.assertFalse(report["valid"], name)


if __name__ == "__main__":
    unittest.main()
