"""Study orchestration gates and actual replay checks, independent of controller code.

The full 360-case orchestration test mocks costly scientific evaluators, but checks
the submitted policies, frozen inputs, pairing and repeat schedule. Real-binary
tests separately run the scalar and semantic references without mocking them.
Artifacts live only in fresh temporary directories; MongoDB is not used.
"""
from collections import Counter
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import io
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_semantic_priority_study as study


ROOT = Path(os.environ.get("UMP_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
BINARY = Path(os.environ.get("UMP_REPLAY_BINARY", ROOT / "simulator/build/AggregationReplay"))


def public_cell():
    """Three observations of each of two different, stable pedestrians."""
    return dict(cell_id=48, depth=2, x=0, y=0, width=20, height=20,
        observation_contributions=6, distinct_road_users=2,
        mean_sample_occupancy=2, effective_policy_id="test",
        semantic=dict(schema="ump.semantic-release.v1", taxonomy_id="semantic-priority",
            taxonomy_version="1", min_category_distinct_contributors=2,
            semantic_max_loss=0, semantic_mean_loss=0,
            categories=[dict(category_id="pedestrian", observation_contributions=6,
                             distinct_contributors=2)]))


def empty_result(runtime=0):
    return dict(runtime=dict(cpu_ms=runtime), input_observation_contributions=3,
        windows=[dict(start_ms=0, end_ms=400, evaluated_at_ms=400,
            completion_reason="test", temporal_extensions=0, selected_cells=0, cells=[])],
        releases=[])


class RunnerContractTests(unittest.TestCase):
    def test_fixtures_distinguish_repeat_samples_from_new_people(self):
        expected = {"dense_exact": (1380, 60), "rare_local": (805, 35),
                    "regional_detail": (805, 35), "temporal_turnover": (1840, 168),
                    "infeasible_support": (92, 4)}
        for scenario, (contributions, identities) in expected.items():
            with self.subTest(scenario=scenario):
                source = study.fixture(scenario)
                self.assertEqual(source["end_ms"], 2400)
                self.assertEqual([b["observed_at_ms"] for b in source["batches"]],
                                 list(range(100, 2400, 100)))
                rows = [row for batch in source["batches"] for row in batch["observations"]]
                self.assertEqual(len(rows), contributions)
                self.assertEqual(len({row["id"] for row in rows}), identities)
                classes = {}
                for row in rows:
                    self.assertEqual(classes.setdefault(row["id"], row["type"]), row["type"])
                self.assertEqual({row["cell_id"] for row in rows}, {48, 49, 50, 51})
        for kind, expected_overlap in (("pedestrian", 76), ("adult_cyclist", 0)):
            first, second = [
                {row["id"] for row in study.observations("temporal_turnover", time)
                 if row["type"] == kind} for time in (100, 200)]
            self.assertEqual(len(first & second), expected_overlap)
        # Adding the regional policy does not secretly alter movement evidence.
        rare, regional = study.fixture("rare_local"), study.fixture("regional_detail")
        self.assertEqual(rare["batches"], regional["batches"])

    def test_region_uses_replay_requirements_and_only_declared_footprint(self):
        config = study.policy("regional_detail", 5, 1, 40, 800, "spatial_first")
        self.assertEqual(config["policy_tree"]["regions"], ["strict-detail"])
        region, = config["policy_regions"]
        self.assertEqual({key: region[key] for key in ("x", "y", "width", "height")},
                         dict(x=0, y=0, width=20, height=20))
        self.assertEqual(region["requirements"], {"semantic_max_loss": {"max": 0}})
        self.assertNotIn("metric_requirements", region)
        self.assertEqual(config["policy_tree"]["root"]["semantic_max_loss"], {"max": 1})
        self.assertEqual(study.policy("rare_local", 5, 1, 40, 800, "spatial_first")["policy_regions"], [])

    def test_scalar_projection_does_not_weaken_scalar_checks_or_mutate_inputs(self):
        config = study.policy("regional_detail", 5, 1, 40, 800, "spatial_first")
        config["policy_regions"][0]["type_requirements"] = {
            "window_duration_ms": {"max": 600}, "semantic_mean_loss": {"max": .5}}
        config["policy_regions"][0]["requirements"]["cell_side_m"] = {"max": 20}
        scalar_check = dict(metric="distinct_contributors", status="fail", reason="below_minimum", observed=2)
        semantic_check = dict(metric="min_category_distinct_contributors", status="fail", reason="below_minimum")
        cell = dict(public_cell(), selected=False, assessment_status="fail",
            metrics=dict(distinct_contributors=2, cell_side_m=20,
                         min_category_distinct_contributors=2, semantic_max_loss=0, semantic_mean_loss=0),
            checks=[scalar_check, semantic_check])
        actual = dict(windows=[dict(cells=[cell])], releases=[dict(cells=[public_cell()])])
        original_config, original_actual = deepcopy(config), deepcopy(actual)
        projected_config, projected_actual = study.scalar_projection(config, actual)
        self.assertEqual(config, original_config)
        self.assertEqual(actual, original_actual)
        self.assertNotIn("semantic_taxonomy", projected_config)
        self.assertEqual(projected_config["policy_regions"][0]["type_requirements"],
                         {"window_duration_ms": {"max": 600}})
        self.assertEqual(projected_config["policy_regions"][0]["requirements"], {"cell_side_m": {"max": 20}})
        self.assertEqual(projected_config["policy_tree"]["root"]["distinct_contributors"], {"min": 1})
        projected_cell = projected_actual["windows"][0]["cells"][0]
        self.assertFalse(projected_cell["selected"])
        self.assertEqual(projected_cell["observation_contributions"], 6)
        self.assertEqual(projected_cell["checks"], [scalar_check])
        self.assertEqual(projected_cell["metrics"], dict(distinct_contributors=2, cell_side_m=20))
        self.assertNotIn("assessment_status", projected_cell)
        self.assertNotIn("semantic", projected_cell)
        self.assertNotIn("semantic", projected_actual["releases"][0]["cells"][0])
        projected_config["policy_tree"]["root"]["distinct_contributors"]["min"] = 99
        projected_cell["checks"][0]["observed"] = 99
        self.assertEqual(config, original_config)
        self.assertEqual(actual, original_actual)

    def test_signature_compares_counts_support_losses_catalog_and_geometry(self):
        original = public_cell()
        paths = [("observation_contributions",), ("distinct_road_users",), ("x",),
            ("semantic", "min_category_distinct_contributors"),
            ("semantic", "semantic_max_loss"), ("semantic", "semantic_mean_loss"),
            ("semantic", "taxonomy_id"), ("semantic", "taxonomy_version"),
            ("semantic", "categories", 0, "category_id"),
            ("semantic", "categories", 0, "observation_contributions"),
            ("semantic", "categories", 0, "distinct_contributors")]
        signature = study.signature([original])
        for path in paths:
            with self.subTest(path=path):
                changed = deepcopy(original)
                cursor = changed
                for key in path[:-1]:
                    cursor = cursor[key]
                value = cursor[path[-1]]
                cursor[path[-1]] = value + 1 if isinstance(value, (int, float)) else value + "-changed"
                self.assertNotEqual(study.signature([changed]), signature)

    def test_signature_accepts_equivalent_json_numeric_representations(self):
        integer_form = public_cell()
        decimal_form = deepcopy(integer_form)
        for name in ("x", "y", "width", "height"):
            decimal_form[name] = float(decimal_form[name])
        for name in ("min_category_distinct_contributors", "semantic_max_loss", "semantic_mean_loss"):
            decimal_form["semantic"][name] = float(decimal_form["semantic"][name])
        self.assertEqual(study.signature([integer_form]), study.signature([decimal_form]))
        # Independently summed weighted costs may differ only in the last bit.
        integer_form["semantic"]["semantic_mean_loss"] = .1 + .2
        decimal_form["semantic"]["semantic_mean_loss"] = .3
        self.assertEqual(study.signature([integer_form]), study.signature([decimal_form]))
        decimal_form["semantic"]["semantic_mean_loss"] = .30001
        self.assertNotEqual(study.signature([integer_form]), study.signature([decimal_form]))

    def test_audit_uses_release_counts_not_a_matching_diagnostic_claim(self):
        cell = public_cell()
        reference = dict(candidates=[dict(cells=[deepcopy(cell)])])
        actual = dict(windows=[dict(start_ms=0, end_ms=400, evaluated_at_ms=400,
            selected_cells=1, cells=[deepcopy(cell)])],
            releases=[dict(start_ms=0, end_ms=400, cells=[deepcopy(cell)])])
        actual["releases"][0]["cells"][0]["semantic"]["categories"][0]["distinct_contributors"] = 3
        with patch.object(study, "reference_candidates", return_value=reference):
            with self.assertRaisesRegex(ValueError, "Actual cut not in legal"):
                study.audit_choices({}, {}, actual)
        actual["releases"].append(deepcopy(actual["releases"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate common-window release"):
            study.audit_choices({}, {}, actual)

    def test_scientific_repeat_excludes_runtime_only(self):
        one, two = empty_result(1), empty_result(99)
        self.assertEqual(study.scientific(one), study.scientific(two))
        two["input_observation_contributions"] += 1
        self.assertNotEqual(study.scientific(one), study.scientific(two))


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ump-semantic-study-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        docs = self.root / "docs"; docs.mkdir()
        (docs / "SEMANTIC_PRIORITY_PROTOCOL_2026-10-21.md").write_text("Frozen test protocol\n")
        self.sources = self.root / "tools/evaluation"; self.sources.mkdir(parents=True)
        for name in ("run_semantic_priority_study.py", "semantic_tradeoffs.py", "semantic_queries.py", "oracle.py"):
            (self.sources / name).write_text("# Frozen test source: " + name + "\n")
        self.binary = self.root / "source-binary"
        self.binary.write_bytes(b"frozen binary test fixture\n")
        self.output = self.root / "new-output"
        self.calls = []

    def mocked_study(self, *, alter_repeat=False):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(study, "ROOT", self.root))
        stack.enter_context(patch.object(study, "__file__", str(self.sources / "run_semantic_priority_study.py")))

        def core(binary, input_path, config_path, output_path, mode):
            config, source = json.loads(config_path.read_text()), json.loads(input_path.read_text())
            self.calls.append((config, source, mode, output_path.name))
            result = empty_result(len(self.calls))
            if alter_repeat and output_path.name == "repeat.json":
                result["input_observation_contributions"] = 4
            study.write_json(output_path, result)
            return result, [str(binary), "--input", str(input_path), "--config", str(config_path), "--mode", mode]

        stack.enter_context(patch.object(study, "run_core", side_effect=core))
        stack.enter_context(patch.object(study, "validate_result", return_value={"valid": True}))
        stack.enter_context(patch.object(study, "audit_choices", return_value=[
            dict(nonempty_feasible=False, actual_is_nondominated=True)]))
        stack.enter_context(patch.object(study, "evaluate_queries", return_value={"by_scale": {}}))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack

    def test_exact_matrix_pairs_frozen_sources_and_checks_twelve_repeats(self):
        self.mocked_study()
        summary = study.run_study(self.binary, self.output)
        cases = summary["cases"]
        expected = set(itertools.product(
            ("dense_exact", "rare_local", "temporal_turnover", "infeasible_support", "regional_detail"),
            (2, 4, 5), (0, .5, 1), (20, 40), (400, 800), ("temporal_first", "spatial_first")))
        actual = {(c["scenario"], c["support_min"], c["semantic_loss_max"],
                   c["cell_side_max_m"], c["duration_max_ms"], c["mode"]) for c in cases}
        self.assertEqual(len(cases), 360)
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.calls), 372)
        self.assertEqual([r["case"] for r in summary["repeats"]], [cases[i]["id"] for i in range(0, 360, 30)])
        self.assertEqual(Counter(c["scenario"] for c in cases), {name: 72 for name in study.SCENARIOS})
        self.assertEqual(len({c["policy_sha256"] for c in cases}), 360)
        for scenario in study.SCENARIOS:
            self.assertEqual(len({c["input_sha256"] for c in cases if c["scenario"] == scenario}), 1)
        policies = [config for config, _, _, filename in self.calls if filename == "result.json"]
        self.assertEqual(len({p["policy_tree"]["version"] for p in policies}), 360)
        for config, _, mode, _ in self.calls:
            self.assertEqual(config["policy_tree"]["execution"]["strategy"], mode)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertTrue(manifest["matrix_complete"])
        self.assertEqual(manifest["completed_executions"], 360)
        self.assertEqual(manifest["deterministic_repeats"], 12)
        self.assertEqual(manifest["binary_sha256"], study.digest(self.binary))
        self.assertEqual((self.output / "AggregationReplay").read_bytes(), self.binary.read_bytes())

    def test_changed_repeat_fails_before_success_summary(self):
        self.mocked_study(alter_repeat=True)
        with self.assertRaisesRegex(ValueError, "Scientific output changed"):
            study.run_study(self.binary, self.output, scenarios=("dense_exact",), limit=1)
        self.assertFalse((self.output / "summary.json").exists())
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertNotIn("completed_executions", manifest)

    def test_runtime_change_passes_but_subset_is_marked_incomplete(self):
        self.mocked_study()
        summary = study.run_study(self.binary, self.output, scenarios=("dense_exact",), limit=1)
        self.assertEqual(summary["executions"], 1)
        self.assertEqual(len(summary["repeats"]), 1)
        self.assertFalse(json.loads((self.output / "manifest.json").read_text())["matrix_complete"])

    def test_existing_output_is_not_reused_or_overwritten(self):
        self.mocked_study()
        self.output.mkdir()
        sentinel = self.output / "manifest.json"
        sentinel.write_text("previous research result\n")
        with self.assertRaises(FileExistsError):
            study.run_study(self.binary, self.output, limit=1)
        self.assertEqual(sentinel.read_text(), "previous research result\n")
        self.assertEqual(self.calls, [])

    def test_invalid_plan_fails_without_creating_an_output(self):
        for kwargs in ({"scenarios": ()}, {"scenarios": ("dense_exact", "dense_exact")},
                       {"scenarios": ("undeclared",)}, {"limit": 0}, {"limit": True}, {"limit": 1.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                study.run_study(self.binary, self.output, **kwargs)
            self.assertFalse(self.output.exists())


@unittest.skipUnless(BINARY.is_file(), "Build AggregationReplay or set UMP_REPLAY_BINARY")
class ActualReplayTests(unittest.TestCase):
    def execute(self, scenario, support, loss, side):
        temporary = tempfile.TemporaryDirectory(prefix="ump-semantic-study-replay-")
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        source = study.fixture(scenario)
        config = study.policy(scenario, support, loss, side, 400, "spatial_first")
        study.write_json(directory / "input.json", source)
        study.write_json(directory / "policy.json", config)
        result, _ = study.run_core(BINARY, directory / "input.json", directory / "policy.json",
                                   directory / "result.json", "spatial_first")
        scalar_config, scalar_result = study.scalar_projection(config, result)
        audit = study.validate_result(source, scalar_config, scalar_result)
        self.assertTrue(audit["valid"], audit.get("violations"))
        choices = study.audit_choices(source, config, result)
        self.assertEqual(len(choices), len(result["windows"]))
        return source, config, result

    def test_dense_feasible_replay_preserves_exact_full_run_query_workload(self):
        source, config, result = self.execute("dense_exact", 2, 0, 20)
        summary = study.summarize(result)
        self.assertEqual(summary["source_contributions"], 1380)
        self.assertEqual(summary["retained_contributions"], 1380)
        self.assertEqual(summary["mean_semantic_loss"], 0)
        self.assertEqual(summary["contribution_weighted_cell_side_m"], 20)
        self.assertEqual(len(result["releases"]), 6)
        for window in (400, 800):
            evaluation = study.evaluate_queries(source, config, result["releases"], window_ms=window)
            all_queries = [query for scale in evaluation["by_scale"].values()
                for projection in scale["by_lag_ms"].values() for query in projection["queries"]]
            self.assertEqual(len(all_queries), (2400 // window) * 5 * 4 * 2)
            for query in all_queries:
                if query["deadline_observed"]:
                    self.assertTrue(query["answered"], query)
                    self.assertEqual(query["absolute_error"], 0)
                else:
                    self.assertFalse(query["answered"])
                    self.assertIsNone(query["prediction"])

    def test_regional_zero_loss_really_changes_release_with_same_input(self):
        _, _, ordinary = self.execute("rare_local", 5, 1, 20)
        source, config, strict = self.execute("regional_detail", 5, 1, 20)
        self.assertEqual(study.summarize(ordinary)["retained_contributions"], 805)
        self.assertEqual(study.summarize(strict)["retained_contributions"], 345)
        self.assertEqual({cell["cell_id"] for release in strict["releases"] for cell in release["cells"]},
                         {49, 50, 51})
        queries = study.evaluate_queries(source, config, strict["releases"], window_ms=400)
        for query in queries["by_scale"]["20"]["by_lag_ms"]["0"]["queries"]:
            if query["cell_id"] == 48:
                self.assertFalse(query["answered"])
                self.assertIsNone(query["prediction"])
            else:
                self.assertTrue(query["answered"], query)
                self.assertEqual(query["absolute_error"], 0)


if __name__ == "__main__":
    unittest.main()
