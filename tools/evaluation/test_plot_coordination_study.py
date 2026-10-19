"""Plot data-contract checks and deterministic optional-matplotlib smoke test."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest

from plot_coordination_study import export, jitter, prepare


def metric(common, local):
    return dict(common=common, local=local,
                delta_local_minus_common=local-common if common is not None and local is not None else None)


def fixture():
    pairs = []
    for strategy in ("temporal_first", "spatial_first"):
        for seed in range(2):
            pairs.append(dict(case=f"case-{seed}", kind="replicate", family="heterogeneous", seed=seed,
                              strategy=strategy, metrics=dict(
                                  retained_observation_fraction=metric(.5, .6), answered_query_coverage=metric(.1, .15),
                                  mean_observation_age_ms=metric(500, 400), matched_occupancy_mae=metric(.4, .3))))
    mechanism = deepcopy(pairs[0])
    mechanism.update(case="mechanism", kind="mechanism", seed=None)
    return dict(pairs=pairs+[mechanism], aggregates=[])


class CoordinationPlotTests(unittest.TestCase):
    def test_excludes_mechanism_and_preserves_paired_differences(self):
        rows = prepare(fixture())
        self.assertEqual(len(rows), 4)
        self.assertEqual({r["values"]["mean_observation_age_ms"] for r in rows}, {-100})
        self.assertEqual(jitter(rows[0]), jitter(rows[0]))
        same_case = [r for r in rows if r["case"] == rows[0]["case"]]
        self.assertEqual(jitter(same_case[0]), jitter(same_case[1]))

    def test_rejects_duplicate_and_inconsistent_or_nonfinite_records(self):
        summary = fixture()
        summary["pairs"].append(deepcopy(summary["pairs"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            prepare(summary)
        for invalid in (0, float("nan"), True):
            summary = fixture()
            summary["pairs"][0]["metrics"]["mean_observation_age_ms"]["delta_local_minus_common"] = invalid
            with self.assertRaises(ValueError):
                prepare(summary)

    def test_null_age_is_not_replaced_with_zero(self):
        summary = fixture()
        summary["pairs"][0]["metrics"]["mean_observation_age_ms"] = metric(None, None)
        rows = prepare(summary)
        self.assertIsNone(rows[0]["values"]["mean_observation_age_ms"])

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Optional matplotlib is not installed")
    def test_plot_labels_smaller_defined_pair_counts(self):
        summary = fixture()
        summary["pairs"][0]["metrics"]["matched_occupancy_mae"] = metric(None, None)
        with tempfile.TemporaryDirectory(prefix="ump-coordination-plot-counts-") as temporary:
            outputs = export(summary, Path(temporary) / "counts")
            svg = outputs[1].read_text()
            self.assertIn("1/2 defined", svg)
            self.assertIn("panel annotations show defined pairs", svg)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "Optional matplotlib is not installed")
    def test_export_is_deterministic_and_never_overwrites(self):
        with tempfile.TemporaryDirectory(prefix="ump-coordination-plot-") as temporary:
            directory = Path(temporary)
            first = export(fixture(), directory / "first")
            second = export(fixture(), directory / "second")
            self.assertEqual(first[0].read_bytes(), second[0].read_bytes())
            self.assertEqual(first[1].read_bytes(), second[1].read_bytes())
            self.assertTrue(first[0].read_bytes().startswith(b"\x89PNG"))
            svg = first[1].read_text()
            self.assertIn("retained contributions", svg)
            self.assertIn("No privacy claim", svg)
            original = first[0].read_bytes()
            with self.assertRaisesRegex(ValueError, "already exist"):
                export(fixture(), directory / "first")
            self.assertEqual(first[0].read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
