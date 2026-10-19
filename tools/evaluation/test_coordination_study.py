"""Study protocol, paired-unit accounting and real nine-configuration replay checks."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coordination_scenarios import make_case
from run_comparison import digest
import run_coordination_study as study

ROOT = Path(__file__).resolve().parents[2]
BINARY = Path(os.environ.get("UMP_REPLAY_BINARY", str(ROOT / "simulator/build/AggregationReplay")))


def _query(column=0, row=0, start=0, end=1000, error=None):
    return dict(column=column, row=row, start_ms=start, end_ms=end, absolute_error=error)


def _evaluation(queries):
    return dict(reference=dict(cell_m=10, window_ms=1000), queries=queries)


def _pair(case, seed, values, kind="replicate", family="mixed_density", strategy="spatial_first"):
    return dict(case=case, seed=seed, kind=kind, family=family, strategy=strategy,
                metrics={metric: study.paired_value(*values.get(metric, (1, 1)))
                         for metric in study.METRICS})


class CoordinationStudyTests(unittest.TestCase):
    def test_effective_policy_is_independent_and_explicit_for_all_nine_variants(self):
        source = make_case("homogeneous_dense_control")["policy"]
        source["temporal_adaptation"]["coordination"] = "cell_local"
        original = deepcopy(source)
        self.assertEqual(len(study.STUDY_VARIANTS), 9)
        self.assertEqual(len({v[0] for v in study.STUDY_VARIANTS}), 9)
        for index, variant in enumerate(study.STUDY_VARIANTS):
            with self.subTest(variant=variant[0]):
                actual = study.effective_policy(source, variant)
                self.assertEqual(actual["temporal_adaptation"]["coordination"], variant[4])
                if index < 5:
                    self.assertEqual(actual["temporal_adaptation"]["coordination"], "common_window")
                if variant[1] in ("temporal_first", "spatial_first"):
                    self.assertEqual(actual["policy_tree"]["execution"]["strategy"], variant[1])
                actual["policy_tree"]["root"]["distinct_contributors"]["min"] = 999
                self.assertEqual(source, original)

    def test_matched_errors_uses_only_identically_scored_queries(self):
        first = _evaluation([_query(error=2), _query(column=1, error=None),
                             _query(column=2, error=8), _query(column=3, error=4)])
        second = _evaluation([_query(error=6), _query(column=1, error=2),
                              _query(column=2, error=None), _query(column=3, error=2)])
        original = deepcopy((first, second))
        self.assertEqual(study.matched_errors(first, second),
                         dict(scored_queries=2, common_mae=3, local_mae=4))
        self.assertEqual((first, second), original)
        self.assertEqual(study.matched_errors(_evaluation([_query()]), _evaluation([_query()])),
                         dict(scored_queries=0, common_mae=None, local_mae=None))
        self.assertEqual(study.matched_errors(_evaluation([]), _evaluation([])),
                         dict(scored_queries=0, common_mae=None, local_mae=None))

    def test_matched_errors_rejects_different_reference_count_and_query_identity(self):
        first = _evaluation([_query(error=1)])
        variants = []
        different_reference = deepcopy(first)
        different_reference["reference"]["cell_m"] = 5
        variants.append(different_reference)
        variants.append(_evaluation([]))
        for field in ("column", "row", "start_ms", "end_ms"):
            altered = deepcopy(first)
            altered["queries"][0][field] += 1
            variants.append(altered)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                study.matched_errors(first, variant)

    def test_query_subset_uses_complete_intervals_and_preserves_reference(self):
        original = _evaluation([_query(start=0, end=1000), _query(start=1000, end=2000),
                                _query(start=1500, end=2500), _query(start=2000, end=3000)])
        actual = study.query_subset(original, 1000, 2500)
        self.assertEqual([(q["start_ms"], q["end_ms"]) for q in actual["queries"]],
                         [(1000, 2000), (1500, 2500)])
        self.assertEqual(actual["reference"], original["reference"])
        self.assertEqual(len(original["queries"]), 4)

    def test_aggregate_pairs_counts_independent_complete_cases_and_metric_nulls(self):
        pairs = [
            _pair("mixed_density-seed-19", 19, {"occupancy_mae": (2, 3)}),
            _pair("mixed_density-seed-20", 20, {"occupancy_mae": (4, 1)}),
            _pair("mixed_density-seed-21", 21, {"occupancy_mae": (None, 5)}),
            _pair("mechanism", None, {"occupancy_mae": (0, 999)}, kind="mechanism"),
            _pair("regional_latency-seed-19", 19, {"occupancy_mae": (None, None)},
                  family="regional_latency"),
            _pair("mixed_density-seed-19", 19, {"occupancy_mae": (1, 1)}, strategy="temporal_first"),
        ]
        original = deepcopy(pairs)
        rows = study.aggregate_pairs(pairs)
        self.assertEqual(len(rows), 3)
        mixed = next(r for r in rows if r["family"] == "mixed_density" and r["strategy"] == "spatial_first")
        self.assertEqual(mixed["n"], 3)
        self.assertEqual(mixed["metrics"]["occupancy_mae"],
                         dict(n=2, mean=-1, median=-1, min=-3, max=1))
        self.assertEqual(mixed["metrics"]["retained_observation_fraction"]["n"], 3)
        regional = next(r for r in rows if r["family"] == "regional_latency")
        self.assertEqual(regional["metrics"]["occupancy_mae"],
                         dict(n=0, mean=None, median=None, min=None, max=None))
        self.assertEqual(pairs, original)
        self.assertEqual(study.aggregate_pairs([]), [])
        self.assertEqual(study.aggregate_pairs([pairs[3]]), [])

    def test_pair_delta_requires_both_measurements(self):
        self.assertEqual(study.paired_value(3, 1), dict(common=3, local=1, delta_local_minus_common=-2))
        self.assertIsNone(study.paired_value(None, 1)["delta_local_minus_common"])
        self.assertIsNone(study.paired_value(1, None)["delta_local_minus_common"])
        self.assertIsNone(study.paired_value(None, None)["delta_local_minus_common"])

    def test_run_study_rejects_duplicate_or_empty_units_before_creating_output(self):
        with tempfile.TemporaryDirectory(prefix="ump-study-invalid-") as temporary:
            output = Path(temporary) / "output"
            for names, seeds in (([], [19]), (["mixed_density"], []),
                                 (["mixed_density", "mixed_density"], [19]),
                                 (["mixed_density"], [19, 19]), (["unknown"], [19])):
                with self.subTest(names=names, seeds=seeds), self.assertRaises(ValueError):
                    study.run_study(output, BINARY, names, seeds)
                self.assertFalse(output.exists())


@unittest.skipUnless(BINARY.is_file(), "Build AggregationReplay for coordination study integration")
class CoordinationStudyIntegrationTests(unittest.TestCase):
    def _verify_case(self, name, directory):
        case = make_case(name)
        original = deepcopy(case)
        with patch.object(study, "run_variant", wraps=study.run_variant) as execute:
            pairs, summaries = study.run_case(BINARY, directory, name, case, rotation=3)
        self.assertEqual(execute.call_count, 13)
        self.assertEqual(case, original)
        self.assertEqual(len(pairs), 2)
        self.assertEqual(set(summaries), {variant[0] for variant in study.STUDY_VARIANTS})
        manifest = json.loads((directory / "manifest.json").read_text())
        self.assertEqual(manifest["input_sha256"], digest(directory / "observations.json"))
        self.assertEqual(manifest["policy_sha256"], digest(directory / "policy.json"))
        self.assertEqual(manifest["adaptive_deterministic_repeats"], 4)
        self.assertEqual(len(manifest["variants"]), 9)
        self.assertEqual(json.loads((directory / "observations.json").read_text()), original["observations"])
        for variant in study.STUDY_VARIANTS:
            variant_name, mode, _, _, coordination = variant
            config_file, result_file = directory / (variant_name + ".policy.json"), directory / (variant_name + ".json")
            config = json.loads(config_file.read_text())
            self.assertEqual(config["temporal_adaptation"]["coordination"], coordination)
            result = json.loads(result_file.read_text())
            self.assertEqual(result["parameters"]["coordination"], coordination)
            self.assertEqual(result["input_observation_contributions"], result["accounted_observation_contributions"])
            audit = json.loads((directory / (variant_name + ".audit.json")).read_text())
            self.assertTrue(audit["valid"], audit["violations"])
            self.assertTrue(summaries[variant_name]["independently_audited"])
            recorded = next(row for row in manifest["variants"] if row["name"] == variant_name)
            self.assertEqual(recorded["config_sha256"], digest(config_file))
            self.assertEqual(recorded["result_sha256"], digest(result_file))
            self.assertTrue(recorded["independent_audit_valid"])
            self.assertFalse((directory / (variant_name + ".repeat.json")).exists())
            for preset in study.QUERY_PRESETS:
                self.assertTrue((directory / (variant_name + "." + preset + ".utility.json")).is_file())
            self.assertTrue((directory / (variant_name + ".metrics.json")).is_file())
        for filename, expected in manifest["artifact_sha256"].items():
            self.assertEqual(digest(directory / filename), expected)
        before = digest(directory / "observations.json")
        with self.assertRaises(FileExistsError):
            study.run_case(BINARY, directory, name, case)
        self.assertEqual(digest(directory / "observations.json"), before)
        return summaries

    def test_dense_control_all_nine_variants_audited_and_immutable(self):
        with tempfile.TemporaryDirectory(prefix="ump-study-dense-") as temporary:
            summaries = self._verify_case("homogeneous_dense_control", Path(temporary) / "case")
            for name in ("common_temporal_first", "common_spatial_first", "local_temporal_first", "local_spatial_first"):
                self.assertEqual(summaries[name]["retained_observation_fraction"], 1)

    def test_heterogeneous_deadlines_expose_common_local_difference(self):
        with tempfile.TemporaryDirectory(prefix="ump-study-heterogeneous-") as temporary:
            summaries = self._verify_case("heterogeneous_sibling_deadlines", Path(temporary) / "case")
            self.assertEqual(summaries["common_temporal_first"]["released_observations"], 0)
            self.assertEqual(summaries["common_spatial_first"]["released_observations"], 0)
            self.assertEqual(summaries["local_temporal_first"]["retained_observation_fraction"], 1)
            self.assertEqual(summaries["local_spatial_first"]["retained_observation_fraction"], 1)

    def test_study_freezes_protocol_binary_source_and_case_manifest_before_execution(self):
        stable_source = ROOT / "tools/evaluation/coordination_scenarios.py"
        original_digest = digest(stable_source)
        execute = study.run_case
        with tempfile.TemporaryDirectory(prefix="ump-study-protocol-") as temporary:
            output = Path(temporary) / "study"

            def checked_run(binary, case_output, name, case, rotation=0):
                self.assertTrue((output / "protocol.json").is_file())
                self.assertFalse((output / "summary.json").exists())
                protocol = json.loads((output / "protocol.json").read_text())
                self.assertEqual(protocol["binary_sha256"], digest(binary))
                relative = str(stable_source.relative_to(ROOT))
                self.assertEqual(protocol["source_sha256"], {relative: original_digest})
                self.assertEqual(digest(output / "source" / relative), original_digest)
                return execute(binary, case_output, name, case, rotation)

            # Freeze one stable source for this protocol test while other workers
            # may still be editing unrelated plotting or documentation modules.
            with patch.object(study, "source_files", return_value=[stable_source]), \
                    patch.object(study, "run_case", side_effect=checked_run) as checked:
                summary = study.run_study(output, BINARY, ["homogeneous_dense_control"], [19])
            self.assertEqual(checked.call_count, 1)
            self.assertEqual(summary["completed_cases"], 1)
            self.assertEqual(summary["audited_replays"], 9)
            self.assertEqual(summary["deterministic_repeats"], 4)
            self.assertEqual(summary["aggregates"], [])
            self.assertFalse((output / "failure.json").exists())
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertTrue(manifest["source_unchanged"])
            self.assertEqual(manifest["summary_sha256"], digest(output / "summary.json"))
            self.assertEqual(manifest["protocol_sha256"], digest(output / "protocol.json"))
            case_manifest = output / "cases" / "homogeneous_dense_control" / "manifest.json"
            self.assertEqual(manifest["case_manifests"]["homogeneous_dense_control"], digest(case_manifest))
            self.assertTrue((output / "paired-results.csv").is_file())
            protocol_digest = digest(output / "protocol.json")
            with self.assertRaises(FileExistsError):
                study.run_study(output, BINARY, ["homogeneous_dense_control"], [19])
            self.assertEqual(digest(output / "protocol.json"), protocol_digest)
        self.assertEqual(digest(stable_source), original_digest)


if __name__ == "__main__":
    unittest.main()
