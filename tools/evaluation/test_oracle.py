"""Hand calculations, adversarial mutations and real-core EP01 integration checks."""

from copy import deepcopy
import json
import itertools
import os
from pathlib import Path
import subprocess
import sys
import stat
import tempfile
import unittest

from oracle import analyze_windows, decode_cell, enumerate_endpoints, reference_interval, validate_result

ROOT = Path(__file__).resolve().parents[2]
BINARY = Path(os.environ.get("UMP_REPLAY_BINARY", str(ROOT / "simulator/build/AggregationReplay")))
GRID = dict(x=0, y=0, width=80, height=80, leaf_depth=2)


def observation(identity, cid=48):
    # Explicit hand positions; fixture construction does not call oracle decoder.
    positions = {48: (1, 1), 49: (21, 1), 50: (1, 21), 51: (21, 21), 63: (61, 61)}
    x, y = positions[cid]
    return dict(id=identity, type="pedestrian", cell_id=cid, x=x, y=y)


def replay(samples=None, end=400):
    if samples is None:
        samples = [[observation("a"), observation("b")] for _ in range(3)]
    batches = []
    for index, observations in enumerate(samples, 1):
        if observations == "missing":
            continue
        batches.append(dict(sequence=index, observed_at_ms=index * 100,
                            status="unavailable" if observations is None else "measured",
                            observations=[] if observations is None else observations))
    return dict(schema="ump.observation-replay.v1", run_id="oracle-hand-case", sensor_id="agbs",
                coverage=deepcopy(GRID), sampling_period_ms=100, end_ms=end, batches=batches)


def policy(support=2, max_side=40):
    return dict(application_id="oracle-app", window_ms=400,
        max_observations_per_window=1000000,
        history=dict(retention_ms=2000, max_bins=32, max_observations=100000,
                     max_identity_bytes=16000000, max_buckets=128),
        spatial_selection=dict(min_depth=1, max_evaluations=4096),
        temporal_adaptation=dict(extension_step_ms=100, max_window_ms=1000, max_evaluations=16),
        policy_tree=dict(id="oracle-policy", version="1", max_nodes=65536,
            execution=dict(publication_model="private_final_snapshot", strategy="spatial_first"),
            root=dict(distinct_contributors=dict(min=support), cell_side_m=dict(min=1.25, max=max_side),
                      window_duration_ms=dict(max=1000), age_at_evaluation_ms=dict(max=1000)), regions=[]),
        policy_regions=[])


def result(source=None, config=None):
    """A hand-worked public cell and complete private retirement for [0,400)."""
    source = replay() if source is None else source
    config = policy() if config is None else config
    cell = dict(cell_id=48, depth=2, x=0, y=0, width=20, height=20,
                observation_contributions=6, distinct_road_users=2, mean_sample_occupancy=2)
    diagnostic = dict(cell, selected=True, assessment_status="pass")
    return dict(schema="ump.replay-result.v1", mode="spatial_first",
        source=dict(run_id=source["run_id"], sensor_id=source["sensor_id"], application_id=config["application_id"],
            coverage=deepcopy(GRID), sampling_period_ms=100, end_ms=400),
        input_observation_contributions=6, accounted_observation_contributions=6,
        windows=[dict(start_ms=0, end_ms=400, evaluated_at_ms=400, expected_samples=3,
            measured_samples=3, unavailable_samples=0, missing_samples=0, coverage="complete",
            input_observation_contributions=6, selected_cells=1, suppressed_cells=0, cells=[diagnostic])],
        releases=[dict(release_id="release-0", start_ms=0, end_ms=400, sealed_at_ms=400,
            model="private_final_snapshot", policy_id="oracle-policy", policy_version="1", cells=[cell])])


class DecodeAndInputTests(unittest.TestCase):
    def test_quadrants_and_nonzero_origin_are_hand_calculated(self):
        self.assertEqual(decode_cell(GRID, 49, 2),
                         dict(cell_id=49, depth=2, x=20, y=0, width=20, height=20))
        shifted = dict(GRID, x=-30, y=11)
        self.assertEqual(decode_cell(shifted, 15, 1),
                         dict(cell_id=15, depth=1, x=10, y=51, width=40, height=40))

    def test_synthetic_root_bad_prefix_and_depth_are_rejected(self):
        for cid, depth in ((3, 0), (3, 1), (48, 1), (12, 2), (192, 3), (True, 1)):
            with self.subTest(cid=cid, depth=depth), self.assertRaises(ValueError):
                decode_cell(GRID, cid, depth)

    def test_half_open_coordinate_boundary_and_duplicate_identity_rejected(self):
        for mutation in (lambda r: r["batches"][0]["observations"][0].update(x=20),
                         lambda r: r["batches"][0]["observations"].append(observation("a")),
                         lambda r: r["batches"][0].update(observed_at_ms=0),
                         lambda r: r["batches"][0].update(status="unavailable")):
            with self.subTest(mutation=mutation):
                source = replay()
                mutation(source)
                with self.assertRaises(ValueError):
                    reference_interval(source, policy(), 0, 400)

    def test_unknown_and_unavailable_policy_metrics_fail_closed(self):
        for metric in ("occupancy_mae", "made_up_privacy"):
            config = policy()
            config["policy_tree"]["root"][metric] = dict(max=1)
            with self.subTest(metric=metric), self.assertRaisesRegex(ValueError, "Unsupported"):
                reference_interval(replay(), config, 0, 400)

    def test_region_alignment_overlap_and_type_inconsistency_rejected(self):
        config = policy()
        config["policy_tree"]["regions"] = ["one", "two"]
        one = dict(id="one", type="footway", x=0, y=0, width=20, height=20,
                   type_requirements=dict(distinct_contributors=dict(min=2)))
        config["policy_regions"] = [one, dict(one, id="two", x=20)]
        self.assertTrue(reference_interval(replay(), config, 0, 400)["whole_sibling"]["any_output_feasible"])
        for mutation in (lambda c: c["policy_regions"][1].update(x=1),
                         lambda c: c["policy_regions"][1].update(x=0),
                         lambda c: c["policy_regions"][1].update(type_requirements={"distinct_contributors": {"min": 3}})):
            bad = deepcopy(config)
            mutation(bad)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                reference_interval(replay(), bad, 0, 400)


class TinyFeasibilityTests(unittest.TestCase):
    def test_sufficient_support_exact_counts_and_finest_cut(self):
        out = reference_interval(replay(), policy(), 0, 400)
        for model in ("whole_sibling", "partial_child_rescue"):
            self.assertEqual(out[model]["best_retained_contributions"], 6)
            self.assertEqual(out[model]["best_cell_ids"], [48])
            self.assertTrue(out[model]["full_retention_feasible"])
            # suppress, leaf release, parent release
            self.assertEqual(out[model]["legal_cut_count"], 3)
        self.assertEqual(out["expected_samples"], 3)
        self.assertEqual(out["coverage"], "complete")

    def test_impossible_support_is_proven_only_within_declared_domain(self):
        out = reference_interval(replay(), policy(support=3), 0, 400)
        self.assertFalse(out["whole_sibling"]["any_output_feasible"])
        self.assertFalse(out["whole_sibling"]["full_retention_feasible"])
        self.assertEqual(out["whole_sibling"]["best_retained_contributions"], 0)
        self.assertTrue(any(r["requirement"] == "distinct_contributors" for r in out["binding_requirements"]))
        self.assertEqual(out["scope"]["min_depth"], 1)

    def test_handover_parent_early_then_refinement_without_summing_support(self):
        source = replay([[observation("a", 48), observation("b", 49)],
                         [observation("c", 48), observation("d", 49)], []])
        endpoints = enumerate_endpoints(source, policy(), 0, [200, 300])
        early, late = endpoints["intervals"]
        self.assertEqual(early["whole_sibling"]["best_cell_ids"], [12])
        self.assertEqual(late["whole_sibling"]["best_cell_ids"], [48, 49])
        # Repeated IDs in different cells/times are one support member of parent.
        source = replay([[observation("same", 48)], [observation("same", 49)], []])
        self.assertFalse(reference_interval(source, policy(), 0, 400)["whole_sibling"]["any_output_feasible"])

    def test_failed_sibling_exposes_partial_rescue_model_gap(self):
        samples = [[observation("a", 48), observation("b", 48), observation("c", 49)] for _ in range(3)]
        out = reference_interval(replay(samples), policy(max_side=20), 0, 400)
        self.assertEqual(out["whole_sibling"]["best_retained_contributions"], 0)
        self.assertEqual(out["partial_child_rescue"]["best_retained_contributions"], 6)
        self.assertEqual(out["partial_child_rescue"]["best_cell_ids"], [48])
        self.assertFalse(out["partial_child_rescue"]["full_retention_feasible"])

    def test_strict_region_crossing_and_touching_boundary(self):
        config = policy()
        config["policy_tree"]["regions"] = ["strict"]
        config["policy_regions"] = [dict(id="strict", type="entrance", x=20, y=0, width=20, height=20,
            type_requirements=dict(distinct_contributors=dict(min=3)),
            requirements=dict(cell_side_m=dict(max=20)))]
        source = replay([[observation("a", 48), observation("b", 48), observation("c", 49)] for _ in range(3)])
        out = reference_interval(source, config, 0, 400)
        self.assertEqual(out["whole_sibling"]["best_retained_contributions"], 0)
        self.assertEqual(out["partial_child_rescue"]["best_cell_ids"], [48])
        parent_failures = [r for r in out["binding_requirements"] if r["cell_id"] == 12]
        self.assertTrue(any(r["requirement"] == "cell_side_m" for r in parent_failures))
        self.assertFalse(any(r["cell_id"] == 48 for r in out["binding_requirements"]))

    def test_accepted_region_alignment_roundoff_does_not_create_policy_slivers(self):
        config = policy()
        config["policy_tree"]["regions"] = ["strict"]
        config["policy_regions"] = [dict(id="strict", type="entrance", x=20 - 1e-9, y=0,
            width=20 + 1e-9, height=20, requirements=dict(distinct_contributors=dict(min=3)))]
        # The accepted near-grid boundary is snapped to x=20, so cell48 has
        # zero-area contact and continues to use root support2.
        out = reference_interval(replay(), config, 0, 400)
        self.assertTrue(out["whole_sibling"]["full_retention_feasible"])
        self.assertFalse(any(r["cell_id"] == 48 for r in out["binding_requirements"]))

    def test_missing_and_unavailable_samples_block_output(self):
        for absent in (None, "missing"):
            source = replay([[observation("a"), observation("b")], absent,
                             [observation("a"), observation("b")]])
            out = reference_interval(source, policy(), 0, 400)
            self.assertEqual(out["coverage"], "incomplete")
            self.assertEqual(out["unavailable_samples"] if absent is None else out["missing_samples"], 1)
            self.assertFalse(out["partial_child_rescue"]["any_output_feasible"])

    def test_no_scheduled_samples_and_measured_empty_are_distinct(self):
        source = replay([[], [], []])
        no_sample = reference_interval(source, policy(), 0, 100)
        empty = reference_interval(source, policy(), 0, 400)
        self.assertEqual(no_sample["coverage"], "no_scheduled_samples")
        self.assertEqual(empty["coverage"], "complete")
        for out in (no_sample, empty):
            self.assertTrue(out["empty_observed_support"])
            self.assertIsNone(out["whole_sibling"]["full_retention_feasible"])
            self.assertFalse(out["whole_sibling"]["any_output_feasible"])

    def test_age_size_and_duration_exact_bounds_inclusive(self):
        config = policy(max_side=20)
        config["policy_tree"]["root"].update(cell_area_m2=dict(min=400, max=400),
            window_duration_ms=dict(min=400, max=400), age_at_evaluation_ms=dict(max=400),
            measured_sample_fraction=dict(min=1), post_window_delay_ms=dict(max=0))
        self.assertTrue(reference_interval(replay(), config, 0, 400)["whole_sibling"]["any_output_feasible"])
        delayed = reference_interval(replay(), config, 0, 400, 401)
        self.assertFalse(delayed["whole_sibling"]["any_output_feasible"])
        self.assertTrue(any(r["requirement"] == "age_at_evaluation_ms" for r in delayed["binding_requirements"]))

    def test_empty_strict_region_affects_common_deadline_only_when_requested(self):
        config = policy()
        config["policy_tree"]["regions"] = ["empty-road"]
        config["policy_regions"] = [dict(id="empty-road", type="road", x=60, y=60, width=20, height=20,
            requirements=dict(window_duration_ms=dict(max=200)))]
        local = reference_interval(replay(), config, 0, 400)
        global_cap = reference_interval(replay(), config, 0, 400, common_deadline=True)
        self.assertTrue(local["whole_sibling"]["any_output_feasible"])
        self.assertFalse(global_cap["whole_sibling"]["any_output_feasible"])
        self.assertEqual(global_cap["common_deadline_failures"][0]["max"], 200)

    def test_endpoints_do_not_assume_policy_monotonicity(self):
        config = policy()
        config["policy_tree"]["root"]["window_duration_ms"] = dict(max=300)
        out = enumerate_endpoints(replay(), config, 0, [400, 200, 300])
        self.assertEqual([r["whole_sibling"]["any_output_feasible"] for r in out["intervals"]], [True, True, False])
        with self.assertRaises(ValueError):
            enumerate_endpoints(replay(), config, 0, [250])
        with self.assertRaises(ValueError):
            enumerate_endpoints(replay(), config, 0, [200, 200])

    def test_all_162_depth_two_support_patterns_match_direct_case_analysis(self):
        # All absent/single/double support patterns on four leaves; expected
        # totals follow direct complete-sibling and partial-rescue definitions.
        for counts in itertools.product(range(3), repeat=4):
            observations = [observation(f"leaf-{j}-road-user-{k}", 48 + j)
                            for j, count in enumerate(counts) for k in range(count)]
            for max_side in (20, 40):
                with self.subTest(counts=counts, max_side=max_side):
                    source = replay([observations], end=200)
                    out = reference_interval(source, policy(max_side=max_side), 0, 200)
                    parent_pass = max_side == 40 and sum(counts) >= 2
                    children_pass = all(n == 0 or n >= 2 for n in counts)
                    whole = sum(counts) if parent_pass or children_pass else 0
                    partial = sum(counts) if parent_pass else sum(n for n in counts if n >= 2)
                    self.assertEqual(out["whole_sibling"]["best_retained_contributions"], whole)
                    self.assertEqual(out["partial_child_rescue"]["best_retained_contributions"], partial)

    def test_budgets_fail_without_partial_feasibility_claim(self):
        with self.assertRaisesRegex(ValueError, "max_nodes"):
            reference_interval(replay(), policy(), 0, 400, max_nodes=1)
        with self.assertRaisesRegex(ValueError, "max_endpoints"):
            enumerate_endpoints(replay(), policy(), 0, [200, 300], max_endpoints=1)


class ComplianceMutationTests(unittest.TestCase):
    def test_hand_release_recomputed_from_raw_observations(self):
        out = validate_result(replay(), policy(), result())
        self.assertTrue(out["valid"], out["violations"])
        self.assertEqual(out["released_cell_count"], 1)
        self.assertEqual(out["released_observation_contributions"], 6)
        self.assertEqual(out["released_cells"][0]["metrics"]["distinct_contributors"], 2)
        self.assertFalse(out["scope"]["feasibility_enumerated"])
        json.dumps(out, allow_nan=False)

    def test_actual_window_feasibility_reports_scoped_retention_gap(self):
        out = analyze_windows(replay(), policy(), result())
        self.assertEqual(out["intervals"][0]["algorithm_retention_gap"],
                         {"whole_sibling": 0, "partial_child_rescue": 0})
        empty = result()
        empty["windows"][0].update(selected_cells=0, suppressed_cells=1)
        empty["windows"][0]["cells"][0]["selected"] = False
        empty["releases"] = []
        # Deliberate avoidable refusal is compliant, but the reference sees loss.
        out = analyze_windows(replay(), policy(), empty)
        self.assertEqual(out["intervals"][0]["algorithm_retention_gap"]["whole_sibling"], 6)
        with self.assertRaisesRegex(ValueError, "invalid"):
            bad = result()
            bad["releases"][0]["cells"][0]["distinct_road_users"] = 99
            analyze_windows(replay(), policy(), bad)

    def test_public_geometry_counts_identity_union_and_mean_mutations_detected(self):
        for field, value in (("x", 1), ("width", 40), ("cell_id", 49), ("depth", 1),
                             ("observation_contributions", 7), ("distinct_road_users", 3),
                             ("mean_sample_occupancy", 3), ("distinct_road_users", True)):
            with self.subTest(field=field, value=value):
                bad = result()
                bad["releases"][0]["cells"][0][field] = value
                self.assertFalse(validate_result(replay(), policy(), bad)["valid"])

    def test_stale_claimed_pass_does_not_bypass_independent_policy(self):
        bad = result()
        bad["windows"][0]["cells"][0]["checks"] = [{"metric": "distinct_contributors", "status": "pass"}]
        out = validate_result(replay(), policy(support=3), bad)
        self.assertFalse(out["valid"])
        self.assertTrue(any(v["reason"] == "published_cell_fails_independent_requirements" for v in out["violations"]))

    def test_sample_coverage_and_diagnostic_conservation_mutations_detected(self):
        for mutation in (lambda r: r["windows"][0].update(expected_samples=4),
                         lambda r: r["windows"][0].update(measured_samples=2),
                         lambda r: r["windows"][0].update(coverage="incomplete"),
                         lambda r: r["windows"][0].update(input_observation_contributions=7),
                         lambda r: r["windows"][0]["cells"][0].update(observation_contributions=7),
                         lambda r: r.update(accounted_observation_contributions=7),
                         lambda r: r["source"].update(sensor_id="wrong")):
            bad = result()
            mutation(bad)
            with self.subTest(mutation=mutation):
                self.assertFalse(validate_result(replay(), policy(), bad)["valid"])

    def test_missing_public_release_and_duplicated_support_detected(self):
        bad = result()
        bad["releases"] = []
        self.assertFalse(validate_result(replay(), policy(), bad)["valid"])
        bad = result()
        bad["releases"][0]["cells"].append(deepcopy(bad["releases"][0]["cells"][0]))
        out = validate_result(replay(), policy(), bad)
        self.assertFalse(out["valid"])
        self.assertTrue(any(v["reason"] == "public_support_overlap_in_space_and_time" for v in out["violations"]))

    def test_incomplete_reference_cannot_be_published_by_forging_complete_flag(self):
        source = replay()
        source["batches"][1]["status"] = "unavailable"
        source["batches"][1]["observations"] = []
        bad = result()
        out = validate_result(source, policy(), bad)
        self.assertFalse(out["valid"])
        self.assertTrue(any(v["reason"] == "published_cell_fails_independent_requirements" for v in out["violations"]))

    def test_no_release_is_vacuous_compliance_and_not_utility(self):
        bad = result()
        bad["windows"][0].update(selected_cells=0, suppressed_cells=1)
        bad["windows"][0]["cells"][0].update(selected=False, assessment_status="fail")
        bad["releases"] = []
        out = validate_result(replay(), policy(support=3), bad)
        self.assertTrue(out["valid"], out["violations"])
        self.assertTrue(out["no_release"])
        self.assertEqual(out["released_cell_count"], 0)

    def test_uniform_policy_and_malformed_result(self):
        config = policy()
        tree = config.pop("policy_tree")
        config.pop("policy_regions")
        config["metric_policy"] = dict(id=tree["id"], version=tree["version"], requirements=tree["root"])
        self.assertTrue(validate_result(replay(), config, result())["valid"])
        for malformed in (None, {}, {"schema": "wrong", "windows": [None], "releases": [None]}):
            with self.subTest(malformed=malformed):
                self.assertFalse(validate_result(replay(), policy(), malformed)["valid"])

    def test_bad_sealing_order_interval_and_resource_budget_detected(self):
        for mutation in (lambda r: r["releases"][0].update(sealed_at_ms=300),
                         lambda r: r["releases"][0].update(start_ms=100),
                         lambda r: r["releases"][0].update(end_ms=500),
                         lambda r: r["windows"][0].update(start_ms=100)):
            bad = result()
            mutation(bad)
            with self.subTest(mutation=mutation):
                self.assertFalse(validate_result(replay(), policy(), bad)["valid"])
        with self.assertRaisesRegex(ValueError, "budget"):
            validate_result(replay(), policy(), result(), max_cells=1)


class OracleCliTests(unittest.TestCase):
    def run_cli(self, directory, output, extra=()):
        command = [sys.executable, "-B", str(ROOT / "tools/evaluation/run_oracle.py"),
                   "--input", str(directory / "input.json"), "--config", str(directory / "config.json"),
                   "--result", str(directory / "result.json"), "--output", str(output), *extra]
        return subprocess.run(command, capture_output=True, text=True, timeout=10)

    def test_private_complete_report_and_exclusive_output(self):
        with tempfile.TemporaryDirectory(prefix="ump-oracle-cli-") as temporary:
            directory = Path(temporary)
            for name, data in (("input", replay()), ("config", policy()), ("result", result())):
                (directory / f"{name}.json").write_text(json.dumps(data))
            output = directory / "report.json"
            completed = self.run_cli(directory, output, ("--feasibility",))
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(json.loads(output.read_text())["valid"])
            self.assertIn("feasibility", json.loads(output.read_text()))
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            before = output.read_bytes()
            self.assertEqual(self.run_cli(directory, output).returncode, 2)
            self.assertEqual(output.read_bytes(), before)
            bad = result()
            bad["releases"][0]["cells"][0]["distinct_road_users"] = 99
            (directory / "result.json").write_text(json.dumps(bad))
            rejected = self.run_cli(directory, directory / "violations.json")
            self.assertEqual(rejected.returncode, 1)
            self.assertFalse(json.loads((directory / "violations.json").read_text())["valid"])

    def test_bad_json_and_budget_error_never_publish_partial_report(self):
        with tempfile.TemporaryDirectory(prefix="ump-oracle-cli-") as temporary:
            directory = Path(temporary)
            for name, data in (("input", replay()), ("config", policy()), ("result", result())):
                (directory / f"{name}.json").write_text(json.dumps(data))
            output = directory / "report.json"
            completed = self.run_cli(directory, output, ("--max-cells", "1"))
            self.assertEqual(completed.returncode, 2)
            self.assertFalse(output.exists())
            (directory / "input.json").write_text('{"schema":"one","schema":"two"}')
            self.assertEqual(self.run_cli(directory, output).returncode, 2)
            self.assertFalse(output.exists())
            self.assertFalse(list(directory.glob(".ump-oracle-*")))


@unittest.skipUnless(BINARY.is_file(), "Build AggregationReplay for real-core oracle integration")
class RealReplayIntegrationTests(unittest.TestCase):
    def test_all_seven_actual_modes_pass_and_mutations_fail(self):
        from make_fixture import make_fixture, make_policy
        variants = [("fixed", 3, 400), ("fixed", 3, 1000), ("fixed", 2, 400),
                    ("fixed", 2, 1000), ("spatial", None, None),
                    ("temporal_first", None, None), ("spatial_first", None, None)]
        source, config = make_fixture(), make_policy()
        source["end_ms"] = 1200
        source["batches"] = [b for b in source["batches"] if b["observed_at_ms"] < 1200]
        with tempfile.TemporaryDirectory(prefix="ump-oracle-core-") as temporary:
            directory = Path(temporary)
            source_file, config_file = directory / "input.json", directory / "policy.json"
            source_file.write_text(json.dumps(source))
            config_file.write_text(json.dumps(config))
            for index, (mode, depth, duration) in enumerate(variants):
                with self.subTest(mode=mode, depth=depth, duration=duration):
                    output = directory / f"result-{index}.json"
                    command = [str(BINARY), "--input", str(source_file), "--config", str(config_file),
                               "--mode", mode, "--output", str(output)]
                    if depth is not None:
                        command.extend(["--fixed-depth", str(depth), "--fixed-window-ms", str(duration)])
                    completed = subprocess.run(command, capture_output=True, text=True, timeout=20)
                    self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                    actual = json.loads(output.read_text())
                    report = validate_result(source, config, actual)
                    self.assertTrue(report["valid"], json.dumps(report["violations"], indent=2))
                    self.assertGreater(report["released_cell_count"], 0)
                    actual["releases"][0]["cells"][0]["distinct_road_users"] += 1
                    self.assertFalse(validate_result(source, config, actual)["valid"])


if __name__ == "__main__":
    unittest.main()
