"""Frozen attack fitting, nonlinear controls and private model integrity."""

from copy import deepcopy
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
import unittest

from empirical_privacy import attack_metrics, fit_classifier, predict_scores
from robustness_attacks import (
    FAMILIES, HGB_PARAMETERS, LOGISTIC_PARAMETERS, SKLEARN_VERSION,
    fit_attack, predict_attack,
)


def optional_available():
    try:
        return importlib.metadata.version("scikit-learn") == SKLEARN_VERSION
    except importlib.metadata.PackageNotFoundError:
        return False


class LogisticAttackTests(unittest.TestCase):
    def test_matches_existing_baseline_and_json_round_trip(self):
        rows, labels = [[-2], [-1], [1], [2]], [0, 0, 1, 1]
        artifact = fit_attack(rows, labels, "logistic")
        expected = fit_classifier(rows, labels, **LOGISTIC_PARAMETERS)
        self.assertEqual(artifact["model"], expected)
        self.assertEqual(predict_attack(json.loads(json.dumps(artifact)), rows), predict_scores(expected, rows))
        self.assertEqual(artifact, fit_attack(rows, labels, "logistic"))

    def test_constant_balanced_control(self):
        artifact = fit_attack([[1, 7]] * 8, [0, 1] * 4, "logistic")
        self.assertEqual(predict_attack(artifact, [[1, 7], [1000, -999]]), [.5, .5])
        self.assertTrue(artifact["converged"])
        self.assertEqual(predict_attack(artifact, []), [])

    def test_prediction_does_not_modify_frozen_fit(self):
        artifact = fit_attack([[0], [1], [2], [3]], [0, 0, 1, 1], "logistic")
        before = deepcopy(artifact)
        first = predict_attack(artifact, [[1.5]])
        predict_attack(artifact, [[-1e4], [1e4]])
        self.assertEqual(first, predict_attack(artifact, [[1.5]]))
        self.assertEqual(artifact, before)

    def test_invalid_training_and_prediction_rejected(self):
        for rows, labels in (([], []), ([[1]], [0]), ([[1], [2]], [0, True]),
                             ([[1], [2, 3]], [0, 1]), ([[float("nan")], [2]], [0, 1])):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                fit_attack(rows, labels, "logistic")
        with self.assertRaises(ValueError):
            fit_attack([[0], [1]], [0, 1], "tuned_on_test")
        artifact = fit_attack([[0], [1]], [0, 1], "logistic")
        for change in ({"feature_count": True}, {"training_rows": 3}, {"parameters": {}},
                       {"extra": 1}, {"fit_partition": "test"}, {"schema": "other"}):
            broken = dict(artifact, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                predict_attack(broken, [[0]])
        with self.assertRaises(ValueError):
            predict_attack(artifact, [[0, 1]])
        with self.assertRaises(ValueError):
            fit_attack([[0], [1]], [0, 1], "logistic", "/private/tmp/not-used.joblib")

    def test_histogram_family_is_explicit_and_path_checked_before_optional_import(self):
        self.assertEqual(FAMILIES, ("logistic", "hist_gradient_boosting"))
        for path in (None, "relative.joblib", "/private/tmp/../bad.joblib", "/private/tmp/bad.json"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                fit_attack([[0], [1]], [0, 1], "hist_gradient_boosting", path)


@unittest.skipUnless(optional_available(), "optional pinned scikit-learn robustness environment not installed")
class HistogramAttackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()

    def fit(self, rows, labels, name="model.joblib"):
        return fit_attack(rows, labels, "hist_gradient_boosting", self.directory / name)

    def test_deterministic_fit_private_serialization_and_json_round_trip(self):
        rows = [[float(i % 8)] for i in range(128)]
        labels = [int(row[0] >= 4) for row in rows]
        first, second = self.fit(rows, labels), self.fit(rows, labels, "second.joblib")
        predicted = predict_attack(first, rows)
        self.assertEqual(predicted, predict_attack(second, rows))
        self.assertEqual(predicted, predict_attack(json.loads(json.dumps(first)), rows))
        self.assertEqual(first["parameters"], HGB_PARAMETERS)
        self.assertEqual(first["versions"]["scikit-learn"], SKLEARN_VERSION)
        self.assertEqual(first["iterations"], 64)
        self.assertFalse(first["convergence_evaluated"])
        self.assertEqual(Path(first["model_path"]).stat().st_mode & 0o777, 0o600)
        self.assertEqual(predict_attack(first, []), [])
        with self.assertRaises(FileExistsError):
            self.fit(rows, labels)

    def test_class_balanced_xor_interaction_exceeds_linear_baseline(self):
        # Equal class totals; the x=0 corners occur twice as often as x=1.
        # This lets a greedy depth-two tree discover XOR without a zero-gain
        # first split. Exact four-corner symmetry is a known greedy-tree limit.
        rows, labels = [], []
        for row, repeats in (([0, 0], 32), ([0, 1], 32), ([1, 0], 16), ([1, 1], 16)):
            rows.extend([row] * repeats)
            labels.extend([row[0] ^ row[1]] * repeats)
        query, truth = [[0, 0], [0, 1], [1, 0], [1, 1]], [0, 1, 1, 0]
        boosted = predict_attack(self.fit(rows, labels), query)
        linear = predict_attack(fit_attack(rows, labels, "logistic"), query)
        self.assertEqual(attack_metrics(boosted, truth, .5)["roc_auc"], 1.0)
        self.assertGreater(attack_metrics(boosted, truth, .5)["roc_auc"],
                           attack_metrics(linear, truth, .5)["roc_auc"])

    def test_constant_balanced_control(self):
        artifact = self.fit([[3, 4]] * 32, [0, 1] * 16)
        self.assertEqual(predict_attack(artifact, [[3, 4], [999, -999]]), [.5, .5])

    def test_corrupted_file_and_metadata_rejected_without_external_load(self):
        artifact = self.fit([[i % 4] for i in range(64)], [0, 0, 1, 1] * 16)
        for field, value in (("parameters", {}), ("threads", 2), ("iterations", 12),
                             ("model_sha256", "0" * 64), ("versions", {})):
            bad = deepcopy(artifact)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                predict_attack(bad, [[0]])
        unknown = deepcopy(artifact)
        unknown["model_path"] = str(self.directory / "external.joblib")
        Path(unknown["model_path"]).write_bytes(b"not a model; must never deserialize")
        with self.assertRaisesRegex(ValueError, "not fitted"):
            predict_attack(unknown, [[0]])
        with Path(artifact["model_path"]).open("ab") as destination:
            destination.write(b"corruption")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            predict_attack(artifact, [[0]])

    def test_symlink_paths_and_public_permissions_rejected(self):
        artifact = self.fit([[i % 4] for i in range(64)], [0, 0, 1, 1] * 16)
        link = self.directory / "link.joblib"
        link.symlink_to(artifact["model_path"])
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.fit([[0], [1]], [0, 1], "link.joblib")
        parent_link = self.directory / "parent"
        parent_link.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "canonical"):
            fit_attack([[0], [1]], [0, 1], "hist_gradient_boosting", parent_link / "escape.joblib")
        os.chmod(artifact["model_path"], 0o644)
        with self.assertRaisesRegex(ValueError, "owner"):
            predict_attack(artifact, [[0]])


if __name__ == "__main__":
    unittest.main()
