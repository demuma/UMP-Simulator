"""Contract tests for the scoped deterministic membership stress test."""

from copy import deepcopy
import unittest

from privacy import canonical_transcript, compare_pair, neighbouring_replay


def replay():
    return {
        "schema": "ump.observation-replay.v1", "run_id": "fixture-run", "sensor_id": "agbs",
        "coverage": {"x": 0, "y": 0, "width": 80, "height": 80, "leaf_depth": 1},
        "sampling_period_ms": 100, "end_ms": 400,
        "batches": [
            {"sequence": 1, "observed_at_ms": 100, "status": "measured", "observations": [
                {"id": "target", "type": "pedestrian", "cell_id": 12, "x": 2, "y": 3}]},
            {"sequence": 2, "observed_at_ms": 200, "status": "measured", "observations": [
                {"id": "target", "type": "pedestrian", "cell_id": 12, "x": 4, "y": 5},
                {"id": "background", "type": "pedestrian", "cell_id": 13, "x": 42, "y": 3}]},
            {"sequence": 3, "observed_at_ms": 300, "status": "unavailable", "observations": []},
        ],
    }


def result():
    return {
        "schema": "ump.replay-result.v1", "mode": "spatial_first",
        "configuration_yaml": "policy: unchanged", "parameters": {"window_ms": 400, "max_window_ms": 1000},
        "source": {"run_id": "run-a", "sensor_id": "agbs", "application_id": "occupancy",
                   "coverage": {"x": 0, "y": 0, "width": 80, "height": 80, "leaf_depth": 1},
                   "sampling_period_ms": 100, "end_ms": 1000, "all_observations_have_coordinates": True},
        "runtime": {"processing_ms": 1.2},
        "windows": [{"suppressed_cells": 4}],
        "releases": [{
            "release_id": "run-a/window-0", "start_ms": 0, "end_ms": 400, "sealed_at_ms": 400,
            "model": "private_final_snapshot", "policy_id": "policy", "policy_version": "1",
            "cells": [{"cell_id": 12, "depth": 1, "x": 0, "y": 0, "width": 40, "height": 40,
                       "observation_contributions": 4, "distinct_road_users": 2,
                       "mean_sample_occupancy": 4 / 3, "effective_policy_id": "root"}],
        }],
    }


class PrivacyComparisonTests(unittest.TestCase):
    def test_neighbour_preserves_measured_empty_batches_and_input(self):
        original = replay()
        before = deepcopy(original)
        neighbour = neighbouring_replay(original, "target")
        self.assertEqual(original, before)
        self.assertEqual(neighbour["batches"][0]["observations"], [])
        self.assertEqual(neighbour["batches"][0]["status"], "measured")
        self.assertEqual(neighbour["batches"][1]["observations"], [original["batches"][1]["observations"][1]])
        self.assertEqual(neighbour["batches"][2], original["batches"][2])
        for old, new in zip(original["batches"], neighbour["batches"]):
            self.assertEqual({k: v for k, v in old.items() if k != "observations"},
                             {k: v for k, v in new.items() if k != "observations"})
        neighbour["coverage"]["width"] = 10
        self.assertEqual(original["coverage"]["width"], 80)

    def test_absent_target_and_wrong_replay_schema_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "no observations"):
            neighbouring_replay(replay(), "unknown")
        malformed = replay()
        malformed["schema"] = "unsupported"
        with self.assertRaisesRegex(ValueError, "schema"):
            neighbouring_replay(malformed, "target")

    def test_random_ids_runtime_and_private_diagnostics_do_not_distinguish(self):
        left, right = result(), result()
        right["source"]["run_id"] = "different-random-id"
        right["releases"][0]["release_id"] = "different-random-id/window-0"
        right["runtime"]["processing_ms"] = 900
        right["windows"] = [{"suppressed_cells": 1000, "raw_identity": "private"}]
        right["input_observation_contributions"] = 999
        comparison = compare_pair(left, right)
        self.assertFalse(comparison["public_transcript_changed"])
        self.assertEqual(comparison["derived_perfect_knowledge_balanced_accuracy"], 0.5)

    def test_each_public_count_is_compared(self):
        for name, value in (("observation_contributions", 5), ("distinct_road_users", 3),
                            ("mean_sample_occupancy", 1.0)):
            with self.subTest(name=name):
                left, right = result(), result()
                right["releases"][0]["cells"][0][name] = value
                comparison = compare_pair(left, right)
                self.assertTrue(comparison["public_transcript_changed"])
                self.assertTrue(comparison["counts_changed"])
                self.assertFalse(comparison["geometry_or_time_changed"])
                self.assertEqual(comparison["derived_perfect_knowledge_balanced_accuracy"], 1.0)

    def test_geometry_and_logical_release_time_are_visible(self):
        for field, value in (("x", 1), ("width", 20)):
            with self.subTest(field=field):
                left, right = result(), result()
                right["releases"][0]["cells"][0][field] = value
                comparison = compare_pair(left, right)
                self.assertTrue(comparison["public_transcript_changed"])
                self.assertTrue(comparison["geometry_or_time_changed"])
                self.assertFalse(comparison["counts_changed"])
        left, right = result(), result()
        right["releases"][0]["sealed_at_ms"] = 500
        comparison = compare_pair(left, right)
        self.assertTrue(comparison["geometry_or_time_changed"])
        self.assertTrue(comparison["public_transcript_changed"])
        self.assertFalse(comparison["counts_changed"])

    def test_policy_metadata_and_release_absence_are_visible(self):
        left, right = result(), result()
        right["releases"][0]["cells"][0]["effective_policy_id"] = "regional"
        self.assertTrue(compare_pair(left, right)["public_policy_metadata_changed"])
        self.assertTrue(compare_pair(left, right)["public_transcript_changed"])
        right["releases"] = []
        self.assertTrue(compare_pair(left, right)["public_transcript_changed"])
        left["releases"] = []
        left["windows"].append({"suppressed_cells": 50})
        comparison = compare_pair(left, right)
        self.assertFalse(comparison["public_transcript_changed"])
        self.assertEqual(comparison["derived_perfect_knowledge_balanced_accuracy"], 0.5)

    def test_cell_order_is_canonical(self):
        left = result()
        extra = deepcopy(left["releases"][0]["cells"][0])
        extra.update({"cell_id": 13, "x": 40, "observation_contributions": 6})
        left["releases"][0]["cells"].append(extra)
        right = deepcopy(left)
        right["releases"][0]["cells"].reverse()
        self.assertEqual(canonical_transcript(left), canonical_transcript(right))

    def test_fixed_input_context_and_configuration_must_match(self):
        for field, value in (("sampling_period_ms", 50), ("end_ms", 2000), ("sensor_id", "other")):
            with self.subTest(field=field):
                left, right = result(), result()
                right["source"][field] = value
                with self.assertRaisesRegex(ValueError, "identical"):
                    compare_pair(left, right)
        for field, value in (("configuration_yaml", "policy: changed"), ("mode", "temporal_first"),
                             ("parameters", {"window_ms": 800})):
            with self.subTest(field=field):
                left, right = result(), result()
                right[field] = value
                with self.assertRaisesRegex(ValueError, "identical"):
                    compare_pair(left, right)

    def test_new_public_fields_are_rejected_instead_of_silently_ignored(self):
        for level in ("release", "cell"):
            with self.subTest(level=level):
                value = result()
                obj = value["releases"][0] if level == "release" else value["releases"][0]["cells"][0]
                obj["new_public_value"] = "must review this channel"
                with self.assertRaisesRegex(ValueError, "unknown fields"):
                    canonical_transcript(value)

    def test_malformed_public_data_are_rejected(self):
        mutations = [
            lambda r: r["releases"][0].update({"sealed_at_ms": 100}),
            lambda r: r["releases"][0].update({"cells": []}),
            lambda r: r["releases"][0]["cells"][0].update({"mean_sample_occupancy": float("nan")}),
            lambda r: r["releases"][0]["cells"][0].update({"distinct_road_users": True}),
            lambda r: r["releases"][0]["cells"][0].update({"distinct_road_users": 5}),
            lambda r: r["releases"][0]["cells"].append(deepcopy(r["releases"][0]["cells"][0])),
            lambda r: r["releases"].append(deepcopy(r["releases"][0])),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = result()
                mutate(value)
                with self.assertRaises(ValueError):
                    canonical_transcript(value)


if __name__ == "__main__":
    unittest.main()
