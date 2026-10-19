"""Leakage boundaries, hand-derived metrics and out-of-sample attack controls."""

from copy import deepcopy
import json
import math
import random
import unittest

from empirical_privacy import (
    attack_metrics, calibrate_threshold, export_public, feature_names, feature_vector,
    fit_classifier, predict_scores, precision_at_prior,
)


def private_result():
    return {
        "schema": "ump.replay-result.v1", "mode": "spatial_first",
        "source": {"run_id": "secret-run-name", "sensor_id": "sensor", "application_id": "app",
                   "coverage": {"x": 0, "y": 0, "width": 80, "height": 80, "leaf_depth": 2},
                   "sampling_period_ms": 100, "end_ms": 1000},
        "windows": [{"raw_ids": ["secret-target"], "suppressed": 999}],
        "input_observation_contributions": 999, "runtime": {"ms": 999},
        "releases": [{
            "release_id": "secret-run-name/window-0", "start_ms": 0, "end_ms": 400,
            "sealed_at_ms": 500, "model": "private_final_snapshot", "policy_id": "policy",
            "policy_version": "1", "cells": [{
                "cell_id": 12, "depth": 1, "x": 0, "y": 0, "width": 40, "height": 40,
                "observation_contributions": 6, "distinct_road_users": 2,
                "mean_sample_occupancy": 2, "effective_policy_id": "root"}]}],
    }


def point(time=100, x=1, y=1, cell_id=48):
    return {"observed_at_ms": time, "x": x, "y": y, "cell_id": cell_id}


def feature_dict(public, knowledge, full=True):
    return dict(zip(feature_names(full), feature_vector(public, knowledge, full)))


class PublicBoundaryTests(unittest.TestCase):
    def test_export_whitelists_private_fields_and_normalizes_ids(self):
        left = private_result()
        original = deepcopy(left)
        first = export_public(left)
        right = deepcopy(left)
        right["source"]["run_id"] = "different-secret"
        right["windows"] = [{"ids": ["another-person"]}]
        right["input_observation_contributions"] = 123456
        right["accounted_observation_contributions"] = 100
        right["releases"][0]["release_id"] = "different-secret/window-0"
        right["configuration_yaml"] = "private scenario"
        right["label"] = 1
        right["target_id"] = "a-person"
        self.assertEqual(first, export_public(right))
        self.assertEqual(left, original)
        encoded = json.dumps(first, allow_nan=False)
        for secret in ("secret-run-name", "secret-target", "input_observation", "windows", "runtime"):
            self.assertNotIn(secret, encoded)
        self.assertEqual(first["releases"][0]["release_id"], "release-000000")
        self.assertEqual(set(first), {"schema", "coverage", "sampling_period_ms", "end_ms", "releases"})
        first["releases"][0]["cells"][0]["mean_sample_occupancy"] = 999
        self.assertEqual(left["releases"][0]["cells"][0]["mean_sample_occupancy"], 2)

    def test_unknown_public_channel_rejected(self):
        for target in ("release", "cell"):
            value = private_result()
            obj = value["releases"][0] if target == "release" else value["releases"][0]["cells"][0]
            obj["new_public_field"] = "requires channel review"
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "unknown"):
                export_public(value)
        public = export_public(private_result())
        public["private_labels"] = [1]
        with self.assertRaisesRegex(ValueError, "unknown"):
            feature_vector(public, [])

    def test_unknown_knowledge_fields_and_identity_are_rejected(self):
        public = export_public(private_result())
        for field in ("target_id", "label", "member", "observed_empty"):
            knowledge = point()
            knowledge[field] = 1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "unknown"):
                feature_vector(public, [knowledge])

    def test_private_data_never_change_features(self):
        left, right = private_result(), private_result()
        right["windows"] = [{"predicted_occupancy": 1e8, "suppressed_cell_id": 12}]
        right["source"]["target_id"] = "secret"
        self.assertEqual(feature_vector(export_public(left), [point()]),
                         feature_vector(export_public(right), [point()]))

    def test_strict_geometry_and_release_horizon(self):
        mutations = [
            lambda r: r["source"]["coverage"].update(width=40),
            lambda r: r["source"]["coverage"].update(leaf_depth=True),
            lambda r: r["source"].update(sampling_period_ms=0),
            lambda r: r["releases"][0].update(sealed_at_ms=1001),
            lambda r: r["releases"][0]["cells"][0].update(x=1),
            lambda r: r["releases"][0]["cells"][0].update(width=20),
        ]
        for mutation in mutations:
            value = private_result()
            mutation(value)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                export_public(value)

    def test_overlapping_parent_and_child_rejected(self):
        value = private_result()
        child = deepcopy(value["releases"][0]["cells"][0])
        child.update(cell_id=48, depth=2, width=20, height=20)
        value["releases"][0]["cells"].append(child)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            export_public(value)


class PublicFeatureTests(unittest.TestCase):
    def test_hand_computed_history_and_target_features(self):
        public = export_public(private_result())
        features = feature_dict(public, [point(), point(time=700)])
        self.assertEqual(features["release_count"], 1)
        self.assertEqual(features["public_contributions_sum"], 6)
        self.assertEqual(features["public_distinct_support_sum"], 2)
        self.assertEqual(features["target_cell_matched_fraction"], .5)
        self.assertEqual(features["target_mean_known_fraction"], .5)
        self.assertEqual(features["target_mean_occupancy_mean"], 2)
        self.assertEqual(features["target_first_half_mean_known_fraction"], 1)
        self.assertEqual(features["target_second_half_mean_known_fraction"], 0)
        self.assertEqual(features["target_matched_release_age_mean_ms"], 400)
        self.assertEqual(features["release_seal_delay_mean_ms"], 100)
        self.assertEqual(features["public_released_area_time_fraction"], .1)

    def test_temporal_and_spatial_half_open_matching(self):
        public = export_public(private_result())
        cases = [
            (point(time=399), 1), (point(time=400), 0),
            (point(x=39.999, cell_id=49), 1), (point(x=40, cell_id=52), 0),
            (point(y=40, cell_id=56), 0),
        ]
        for knowledge, expected in cases:
            with self.subTest(point=knowledge):
                self.assertEqual(feature_dict(public, [knowledge])["target_cell_matched_fraction"], expected)

    def test_sparse_missing_unknown_and_explicit_zero_are_distinct(self):
        known_zero = private_result()
        known_zero["releases"][0]["cells"][0]["mean_sample_occupancy"] = 0
        unknown_mean = deepcopy(known_zero)
        unknown_mean["releases"][0]["cells"][0]["mean_sample_occupancy"] = None
        zero = feature_dict(export_public(known_zero), [point()])
        unknown = feature_dict(export_public(unknown_mean), [point()])
        missing = feature_dict(export_public(known_zero), [point(x=50, cell_id=52)])
        self.assertEqual(zero["target_mean_occupancy_mean"], 0)
        self.assertEqual(unknown["target_mean_occupancy_mean"], 0)
        self.assertEqual(missing["target_mean_occupancy_mean"], 0)
        self.assertEqual((zero["target_cell_matched_fraction"], zero["target_mean_known_fraction"]), (1, 1))
        self.assertEqual((unknown["target_cell_matched_fraction"], unknown["target_mean_known_fraction"]), (1, 0))
        self.assertEqual((missing["target_cell_matched_fraction"], missing["target_mean_known_fraction"]), (0, 0))

    def test_no_output_features_constant_independent_of_candidate_trace(self):
        value = private_result()
        value["releases"] = []
        public = export_public(value)
        empty = feature_vector(public, [])
        one = feature_vector(public, [point()])
        other = feature_vector(public, [point(time=800, x=70, y=70, cell_id=63)])
        self.assertEqual(empty, [0] * len(feature_names()))
        self.assertEqual(empty, one)
        self.assertEqual(empty, other)

    def test_geometry_ablation_preserves_count_availability_projection(self):
        value = private_result()
        public = export_public(value)
        full = feature_vector(public, [point()])
        counts = feature_vector(public, [point()], include_geometry=False)
        self.assertEqual(full[:len(counts)], counts)
        changed = deepcopy(value)
        changed["releases"][0]["sealed_at_ms"] = 600
        changed_public = export_public(changed)
        self.assertEqual(counts, feature_vector(changed_public, [point()], False))
        self.assertNotEqual(full, feature_vector(changed_public, [point()], True))

    def test_all_public_history_contributes_not_only_target_match(self):
        value = private_result()
        baseline = feature_vector(export_public(value), [point()])
        late = deepcopy(value["releases"][0])
        late.update(release_id="private/window-1", start_ms=500, end_ms=900, sealed_at_ms=900)
        late["cells"][0]["mean_sample_occupancy"] = 8
        value["releases"].append(late)
        features = feature_dict(export_public(value), [point()])
        self.assertEqual(features["target_mean_occupancy_mean"], 2)
        self.assertEqual(features["public_mean_occupancy_mean"], 5)
        self.assertEqual(len(baseline), len(feature_vector(export_public(value), [])))
        self.assertNotEqual(baseline, feature_vector(export_public(value), [point()]))

    def test_invalid_candidate_knowledge_fails_instead_of_using_gt(self):
        public = export_public(private_result())
        for knowledge in ([point(time=1000)], [point(x=80, cell_id=52)], [point(cell_id=49)],
                          [point(), point()], [point(time=True)], [point(x=float("nan"))]):
            with self.subTest(knowledge=knowledge), self.assertRaises(ValueError):
                feature_vector(public, knowledge)


class AttackMetricsTests(unittest.TestCase):
    def test_rank_auc_with_ties_matches_pairwise_definition(self):
        scores, labels = [.1, .5, .5, .8, .8, .9], [0, 0, 1, 0, 1, 1]
        positives = [s for s, y in zip(scores, labels) if y]
        negatives = [s for s, y in zip(scores, labels) if not y]
        expected = sum((positive > negative) + .5 * (positive == negative)
                       for positive in positives for negative in negatives) / 9
        metrics = attack_metrics(scores, labels, .8)
        self.assertAlmostEqual(metrics["roc_auc"], expected)
        self.assertEqual(metrics["true_positive"], 2)
        self.assertEqual(metrics["false_positive"], 1)
        self.assertEqual(metrics["tpr"], 2 / 3)
        self.assertEqual(metrics["fpr"], 1 / 3)
        self.assertAlmostEqual(metrics["advantage"], 1 / 3)
        self.assertEqual(metrics["precision_at_evaluation_prior"], 2 / 3)

    def test_constant_perfect_and_reversed_auc(self):
        self.assertEqual(attack_metrics([.5] * 4, [0, 1, 0, 1], .5)["roc_auc"], .5)
        self.assertEqual(attack_metrics([0, .1, .8, 1], [0, 0, 1, 1], .5)["roc_auc"], 1)
        self.assertEqual(attack_metrics([1, .8, .1, 0], [0, 0, 1, 1], .5)["roc_auc"], 0)

    def test_undefined_metrics_explicit_null_no_nan(self):
        metrics = attack_metrics([.2, .4], [0, 0], .9)
        self.assertIsNone(metrics["roc_auc"])
        self.assertIsNone(metrics["tpr"])
        self.assertIsNone(metrics["balanced_accuracy"])
        self.assertIsNone(metrics["precision_at_evaluation_prior"])
        self.assertEqual(metrics["fpr"], 0)
        empty = attack_metrics([], [], .5)
        self.assertIsNone(empty["evaluation_prior"])
        json.dumps([metrics, empty], allow_nan=False)

    def test_calibration_caps_empirical_fpr_and_never_splits_ties(self):
        calibration = calibrate_threshold([.1, .2, .3, .4, .3, .5, .6, .8],
                                          [0, 0, 0, 0, 1, 1, 1, 1], target_fpr=.25)
        self.assertEqual(calibration["threshold"], .5)
        self.assertEqual(calibration["calibration"]["fpr"], 0)
        self.assertEqual(calibration["calibration"]["tpr"], .75)
        self.assertEqual(calibration["negative_case_fpr_resolution"], .25)
        tied = calibrate_threshold([1, 1, 1, 1], [0, 0, 1, 1], .1)
        self.assertGreater(tied["threshold"], 1)
        self.assertTrue(math.isfinite(tied["threshold"]))
        self.assertEqual(tied["calibration"]["tpr"], 0)
        json.dumps(tied, allow_nan=False)

    def test_frozen_calibration_does_not_claim_test_fpr_cap(self):
        calibration = calibrate_threshold([.1, .2, .7, .8], [0, 0, 1, 1], .1)
        before = deepcopy(calibration)
        test = attack_metrics([.9, .95, .8, .85], [0, 0, 1, 1], calibration["threshold"])
        self.assertEqual(calibration, before)
        self.assertEqual(test["fpr"], 1)
        self.assertEqual(test["tpr"], 1)

    def test_prevalence_interpretation_uses_bayes_rule(self):
        self.assertAlmostEqual(precision_at_prior(.8, .1, .01), .008 / .107)
        self.assertIsNone(precision_at_prior(0, 0, .5))
        self.assertEqual(precision_at_prior(1, 0, .01), 1)

    def test_invalid_metrics_and_calibration_data_rejected(self):
        for scores, labels in (([float("nan")], [0]), ([1.1], [1]), ([.5], [True]),
                               ([.5], []), ([.5], [2])):
            with self.subTest(scores=scores, labels=labels), self.assertRaises(ValueError):
                attack_metrics(scores, labels, .5)
        for labels in ([0, 0], [1, 1], []):
            with self.assertRaises(ValueError):
                calibrate_threshold([.5] * len(labels), labels)
        with self.assertRaises(ValueError):
            precision_at_prior(1, .1, 1.1)


class TransparentClassifierTests(unittest.TestCase):
    def test_learns_clear_out_of_sample_signal_with_irrelevant_constant_feature(self):
        rows = [[i / 20, 7] for i in range(-20, 21) if i]
        labels = [int(row[0] > 0) for row in rows]
        model = fit_classifier(rows, labels)
        scores = predict_scores(model, [[-.9, 7], [-.2, 7], [.2, 7], [.9, 7]])
        metrics = attack_metrics(scores, [0, 0, 1, 1], .5)
        self.assertEqual(metrics["roc_auc"], 1)
        self.assertEqual(metrics["balanced_accuracy"], 1)
        self.assertEqual(model["weights"][1], 0)
        self.assertTrue(model["converged"])

    def test_balanced_no_output_control_cannot_learn_membership(self):
        model = fit_classifier([[0] * 31 for _ in range(20)], [0, 1] * 10)
        scores = predict_scores(model, [[0] * 31 for _ in range(10)])
        self.assertEqual(scores, [.5] * 10)
        self.assertEqual(attack_metrics(scores, [0, 1] * 5, .5)["roc_auc"], .5)

    def test_unbalanced_constant_features_return_training_prior(self):
        model = fit_classifier([[4, 8]] * 10, [0] * 8 + [1] * 2)
        scores = predict_scores(model, [[4, 8]])
        self.assertAlmostEqual(scores[0], .2)
        self.assertAlmostEqual(model["training_prior"], .2)

    def test_randomized_balanced_control_has_no_feature_signal(self):
        # The identical feature multiset appears once in each class. Labels are
        # shuffled to ensure order does not encode membership in the optimizer.
        randomizer = random.Random(912)
        base = [[randomizer.gauss(0, 1), randomizer.random()] for _ in range(30)]
        cases = [(row, label) for row in base for label in (0, 1)]
        randomizer.shuffle(cases)
        model = fit_classifier([row for row, _ in cases], [label for _, label in cases])
        scores = predict_scores(model, base + base)
        metrics = attack_metrics(scores, [0] * len(base) + [1] * len(base), .5)
        self.assertEqual(metrics["roc_auc"], .5)
        self.assertTrue(all(abs(score - .5) < 1e-12 for score in scores))

    def test_training_scaling_stays_frozen_for_extreme_test_rows(self):
        rows = [[0, 99], [2, 99], [4, 99], [6, 99]]
        original = deepcopy(rows)
        model = fit_classifier(rows, [0, 0, 1, 1])
        self.assertEqual(model["means"], [3, 99])
        self.assertAlmostEqual(model["scales"][0], math.sqrt(5))
        self.assertEqual(model["scales"][1], 1)
        before = deepcopy(model)
        first = predict_scores(model, [[1, 99]])
        predict_scores(model, [[1e7, -1e7]])
        self.assertEqual(predict_scores(model, [[1, 99]]), first)
        self.assertEqual(model, before)
        self.assertEqual(rows, original)

    def test_json_roundtrip_and_deterministic_fit(self):
        rows, labels = [[-2, .1], [-1, .3], [1, .6], [2, 1]], [0, 0, 1, 1]
        first = fit_classifier(rows, labels)
        second = fit_classifier(rows, labels)
        self.assertEqual(first, second)
        restored = json.loads(json.dumps(first, allow_nan=False))
        self.assertEqual(predict_scores(first, rows), predict_scores(restored, rows))
        self.assertEqual(predict_scores(restored, []), [])

    def test_invalid_training_and_models_fail_explicitly(self):
        for rows, labels in (([], []), ([[0], [1]], [0, 0]), ([[0], [1, 2]], [0, 1]),
                             ([[float("nan")], [1]], [0, 1]), ([[0], [1]], [True, 1])):
            with self.subTest(rows=rows, labels=labels), self.assertRaises(ValueError):
                fit_classifier(rows, labels)
        model = fit_classifier([[0], [1]], [0, 1])
        with self.assertRaises(ValueError):
            predict_scores(model, [[0, 1]])
        model["scales"][0] = 0
        with self.assertRaises(ValueError):
            predict_scores(model, [[0]])


if __name__ == "__main__":
    unittest.main()
