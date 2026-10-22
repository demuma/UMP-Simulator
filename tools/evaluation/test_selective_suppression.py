"""A07 real-core acceptance with independent raw-observation policy/cut oracles.

The oracle reconstructs geometry, identity unions and requirements from the input,
not from production diagnostics. Its bounded cut enumerator compares retention for
one fixed interval only. These tests make no online-optimality or privacy claim.
All replay inputs, policies and outputs are created under TemporaryDirectory.
"""
from copy import deepcopy
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from oracle import reference_interval, validate_result

ROOT = Path(os.environ.get("UMP_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
BINARY = Path(os.environ.get("UMP_REPLAY_BINARY", ROOT / "simulator/build/AggregationReplay"))
GRID = dict(x=0, y=0, width=80, height=80, leaf_depth=2)
POSITIONS = {48: (1, 1), 49: (21, 1), 50: (1, 21), 51: (21, 21)}


def observation(identity, cell=48):
    # Explicit hand-calculated positions; do not call production/oracle geometry.
    x, y = POSITIONS[cell]
    return dict(id=identity, type="pedestrian", cell_id=cell, x=x, y=y)


def replay(samples, *, end=400):
    batches = []
    for sequence, observations in enumerate(samples, 1):
        if observations == "missing":
            continue
        batches.append(dict(sequence=sequence, observed_at_ms=sequence * 100,
                            status="unavailable" if observations is None else "measured",
                            observations=[] if observations is None else observations))
    return dict(schema="ump.observation-replay.v1", run_id="selective-acceptance",
                sensor_id="agbs", coverage=deepcopy(GRID), sampling_period_ms=100,
                end_ms=end, batches=batches)


def policy(*, selective=True, support=2, side=20, window=400, maximum=1000):
    result = dict(application_id="selective-acceptance", window_ms=window,
        max_observations_per_window=1000000,
        history=dict(retention_ms=2000, max_bins=32, max_observations=100000,
                     max_identity_bytes=16000000, max_buckets=128),
        spatial_selection=dict(min_depth=1, max_evaluations=4096),
        temporal_adaptation=dict(extension_step_ms=100, max_window_ms=maximum,
                                 max_evaluations=16, coordination="common_window"),
        policy_tree=dict(id="selective-policy", version="1", max_nodes=65536,
            execution=dict(publication_model="private_final_snapshot", strategy="spatial_first"),
            root=dict(distinct_contributors=dict(min=support), cell_side_m=dict(min=1.25, max=side),
                      window_duration_ms=dict(max=maximum), age_at_evaluation_ms=dict(max=maximum)),
            regions=[]), policy_regions=[])
    if selective is not None:
        result["spatial_selection"]["preserve_valid_descendants"] = selective
    return result


def retained(actual):
    return sum(cell["observation_contributions"]
               for release in actual["releases"] for cell in release["cells"])


def canonical_science(actual):
    # Runtime is nondeterministic. Configuration provenance must truthfully retain
    # implicit-vs-explicit spelling; compare scientific payloads, not that metadata.
    return json.dumps({key: value for key, value in actual.items()
                       if key not in ("runtime", "configuration_yaml")},
                      sort_keys=True, separators=(",", ":")).encode()


@unittest.skipUnless(BINARY.is_file(), "Build AggregationReplay for A07 real-core acceptance")
class SelectiveSuppressionReplayTests(unittest.TestCase):
    def run_core(self, source, config, mode="spatial", *, succeeds=True):
        with tempfile.TemporaryDirectory(prefix="ump-selective-replay-") as temporary:
            directory = Path(temporary)
            input_file, config_file, output_file = [directory / name for name in
                                                   ("input.json", "policy.json", "result.json")]
            input_file.write_text(json.dumps(source), encoding="utf-8")
            config_file.write_text(json.dumps(config), encoding="utf-8")
            completed = subprocess.run([str(BINARY), "--input", str(input_file),
                "--config", str(config_file), "--mode", mode, "--output", str(output_file)],
                capture_output=True, text=True, timeout=20)
            if not succeeds:
                self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertFalse(output_file.exists(), "Rejected configuration wrote a replay result")
                return completed
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            actual = json.loads(output_file.read_text(encoding="utf-8"))
        report = validate_result(source, config, actual)
        self.assertTrue(report["valid"], json.dumps(report["violations"][:10], indent=2))
        self.assertEqual(actual["input_observation_contributions"],
                         actual["accounted_observation_contributions"])
        return actual

    def assert_fixed_reference(self, source, config, actual, *, model="partial_child_rescue"):
        self.assertEqual(len(actual["windows"]), 1)
        reference = reference_interval(source, config, 0, source["end_ms"],
            min_depth=config["spatial_selection"]["min_depth"], max_nodes=128)
        self.assertEqual(retained(actual), reference[model]["best_retained_contributions"])
        return reference

    def test_size_blocked_parent_retains_six_of_nine_in_all_common_modes(self):
        source = replay([[observation("a"), observation("b"), observation("c", 49)]] * 3)
        for mode in ("spatial", "temporal_first", "spatial_first"):
            for enabled, expected in ((False, 0), (True, 6)):
                with self.subTest(mode=mode, enabled=enabled):
                    config = policy(selective=enabled)
                    actual = self.run_core(source, config, mode)
                    self.assertEqual(retained(actual), expected)
                    self.assert_fixed_reference(source, config, actual,
                        model="partial_child_rescue" if enabled else "whole_sibling")
                    if enabled:
                        self.assertEqual([c["cell_id"] for r in actual["releases"] for c in r["cells"]], [48])
                        self.assertEqual(actual["windows"][0]["suppressed_cells"], 1)
                        self.assertNotIn(12, [c["cell_id"] for c in actual["windows"][0]["cells"]])

    def test_regional_support_retains_eighteen_of_twenty_one(self):
        observations = [observation("strict", 48)] + [
            observation(f"{cell}-{person}", cell) for cell in (49, 50, 51) for person in (0, 1)]
        source = replay([observations] * 3)
        for enabled, expected in ((False, 0), (True, 18)):
            config = policy(selective=enabled, side=40)
            config["policy_tree"]["regions"] = ["strict"]
            config["policy_regions"] = [dict(id="strict", type="entrance", x=0, y=0,
                width=20, height=20, requirements=dict(distinct_contributors=dict(min=10)))]
            with self.subTest(enabled=enabled):
                actual = self.run_core(source, config)
                self.assertEqual(retained(actual), expected)
                self.assert_fixed_reference(source, config, actual,
                    model="partial_child_rescue" if enabled else "whole_sibling")
                if enabled:
                    self.assertEqual([c["cell_id"] for r in actual["releases"] for c in r["cells"]], [49, 50, 51])

    def test_legal_parent_keeps_all_nine_instead_of_partial_six(self):
        source = replay([[observation("a"), observation("b"), observation("c", 49)]] * 3)
        config = policy(side=40)
        actual = self.run_core(source, config)
        self.assertEqual(retained(actual), 9)
        self.assertEqual([c["cell_id"] for r in actual["releases"] for c in r["cells"]], [12])
        self.assert_fixed_reference(source, config, actual)

    def test_internal_descendant_survives_but_legal_higher_parent_still_wins(self):
        # At D3, leaves192 and193 each fail support2; their whole20m parent48
        # passes. Singleton196 fails. Its40m ancestor12 either fails size20 or
        # passes size40. These positions and IDs are hand-derived.
        observations = [dict(id="a", type="pedestrian", cell_id=192, x=1, y=1),
                        dict(id="b", type="pedestrian", cell_id=193, x=11, y=1),
                        dict(id="c", type="pedestrian", cell_id=196, x=21, y=1)]
        source = replay([observations] * 3)
        source["coverage"]["leaf_depth"] = 3
        for side, expected, cell_id in ((20, 6, 48), (40, 9, 12)):
            with self.subTest(side=side):
                config = policy(side=side)
                actual = self.run_core(source, config)
                self.assertEqual(retained(actual), expected)
                self.assertEqual([c["cell_id"] for r in actual["releases"] for c in r["cells"]], [cell_id])
                self.assert_fixed_reference(source, config, actual)

    def test_missing_and_unavailable_samples_never_become_valid_descendants(self):
        observations = [observation("a"), observation("b"), observation("c", 49)]
        for absent in ("missing", None):
            for mode in ("spatial", "temporal_first", "spatial_first"):
                with self.subTest(absent=absent, mode=mode):
                    source, config = replay([observations, absent, observations]), policy()
                    actual = self.run_core(source, config, mode)
                    self.assertEqual(retained(actual), 0)
                    self.assertEqual(actual["releases"], [])
                    self.assert_fixed_reference(source, config, actual)

    def test_implicit_and_explicit_false_have_byte_identical_scientific_payload(self):
        source = replay([[observation("a"), observation("b"), observation("c", 49)]] * 3)
        for mode in ("spatial", "temporal_first", "spatial_first"):
            with self.subTest(mode=mode):
                implicit = self.run_core(source, policy(selective=None), mode)
                explicit = self.run_core(source, policy(selective=False), mode)
                self.assertEqual(canonical_science(implicit), canonical_science(explicit))
                # Public/diagnostic output must match without removing any fields.
                for key in ("windows", "releases"):
                    self.assertEqual(json.dumps(implicit[key], separators=(",", ":")).encode(),
                                     json.dumps(explicit[key], separators=(",", ":")).encode())

    def test_enabled_cell_local_is_explicitly_rejected_before_output(self):
        config = policy()
        config["temporal_adaptation"]["coordination"] = "cell_local"
        completed = self.run_core(replay([[observation("a"), observation("b")]] * 3),
                                  config, "spatial_first", succeeds=False)
        self.assertIn("preserve_valid_descendants", completed.stderr)

    def test_permitted_temporal_opportunity_precedes_partial_fallback(self):
        samples = [[observation("a"), observation("b"), observation("c", 49)] +
                   ([observation("d", 49)] if time >= 500 else []) for time in range(100, 1000, 100)]
        source = replay(samples, end=1000)
        for mode in ("temporal_first", "spatial_first"):
            with self.subTest(mode=mode):
                actual = self.run_core(source, policy(maximum=800), mode)
                first = actual["windows"][0]
                self.assertEqual((first["start_ms"], first["end_ms"]), (0, 600))
                self.assertEqual(first["suppressed_cells"], 0)
                self.assertTrue(all(r["sealed_at_ms"] >= 600 for r in actual["releases"]))

    def test_partial_fallback_waits_until_hard_limit_with_original_start(self):
        source = replay([[observation("a"), observation("b"), observation("c", 49)]] * 9, end=1000)
        for mode in ("temporal_first", "spatial_first"):
            with self.subTest(mode=mode):
                actual = self.run_core(source, policy(maximum=800), mode)
                first = actual["windows"][0]
                self.assertEqual((first["start_ms"], first["end_ms"]), (0, 800))
                self.assertGreater(first["suppressed_cells"], 0)
                self.assertTrue(all(r["sealed_at_ms"] >= 800 for r in actual["releases"]))
                self.assertEqual(retained(actual), 18)

    def test_public_cut_excludes_failed_parent_private_ids_types_and_suppressed_counts(self):
        source = replay([[observation("a"), observation("b"), observation("c", 49)]] * 3)
        actual = self.run_core(source, policy())
        release = actual["releases"][0]
        self.assertEqual([cell["cell_id"] for cell in release["cells"]], [48])
        allowed = {"cell_id", "depth", "x", "y", "width", "height", "observation_contributions",
                   "distinct_road_users", "mean_sample_occupancy", "effective_policy_id"}
        for cell in release["cells"]:
            self.assertEqual(set(cell), allowed)
        self.assertNotIn("suppressed_cells", release)
        self.assertNotIn("input_observation_contributions", release)
        damaged = deepcopy(actual)
        damaged["releases"][0]["cells"][0]["observation_contributions"] += 1
        self.assertFalse(validate_result(source, policy(), damaged)["valid"])

    def test_all_162_depth_two_occupancy_patterns_match_independent_fixed_interval_oracle(self):
        # Exhaustive 0/1/2 disjoint-identity populations in all four children;
        # both parent-allowed and size-blocked policies. No production traversal
        # is reproduced in this test: expected retention comes from oracle.py.
        for counts in itertools.product(range(3), repeat=4):
            observations = [observation(f"cell-{cell}-person-{person}", cell)
                            for cell, count in zip(range(48, 52), counts) for person in range(count)]
            source = replay([observations], end=200)
            for side in (20, 40):
                with self.subTest(counts=counts, side=side):
                    config = policy(side=side)
                    actual = self.run_core(source, config)
                    self.assert_fixed_reference(source, config, actual)

    def test_all_sixteen_identity_swaps_do_not_sum_distinct_support(self):
        # Two fixed identities occupy any pair of leaves and swap at the next
        # sample. Same-cell and separated cases both occur; counts alone cannot
        # certify parent support. Test support 2 and impossible uniform support3.
        for left, right in itertools.product(range(48, 52), repeat=2):
            source = replay([[observation("a", left), observation("b", right)],
                             [observation("a", right), observation("b", left)], []])
            for support in (2, 3):
                with self.subTest(left=left, right=right, support=support):
                    config = policy(side=40, support=support)
                    actual = self.run_core(source, config)
                    self.assert_fixed_reference(source, config, actual)
                    if support == 3:
                        self.assertEqual(retained(actual), 0)


if __name__ == "__main__":
    unittest.main()
