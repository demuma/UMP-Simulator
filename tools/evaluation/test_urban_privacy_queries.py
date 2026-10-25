"""Hand-calculated P25.4 scalar exact/estimated occupancy decoder checks."""
from copy import deepcopy
import math
import unittest

import occupancy
import semantic_privacy
import urban_privacy_queries as queries


def replay(side=20, end=1000, positions=None):
    positions = positions or (lambda _time: [])
    return {"schema": "ump.observation-replay.v1", "run_id": "query-source",
            "sensor_id": "agbs", "coverage": {"x": 0, "y": 0, "width": side,
            "height": side, "leaf_depth": 2}, "sampling_period_ms": 100,
            "end_ms": end, "batches": [{"observed_at_ms": time, "sequence": time // 100,
            "status": "measured", "observations": [{"id": str(index),
                "type": "Adult Pedestrian", "cell_id": 48, "x": x, "y": y}
                for index, (x, y) in enumerate(positions(time))]}
            for time in range(100, end, 100)]}


def cell(x=0, y=0, side=10, mean=1, identity=12, depth=1, observations=9):
    return {"cell_id": identity, "depth": depth, "x": x, "y": y,
            "width": side, "height": side, "mean_sample_occupancy": mean,
            "observation_contributions": observations, "distinct_road_users": 1,
            "effective_policy_id": "query-policy/effective"}


def release(cells, start=0, end=1000, name="release", sealed=None):
    return {"release_id": name, "start_ms": start, "end_ms": end,
            "sealed_at_ms": end if sealed is None else sealed, "cells": cells,
            "model": "private_final_snapshot", "policy_id": "query-policy",
            "policy_version": "1"}


def result(source, releases):
    return {"schema": "ump.replay-result.v1", "mode": "fixture",
            "source": {key: deepcopy(source[key]) for key in
                       ("run_id", "sensor_id", "coverage", "sampling_period_ms", "end_ms")},
            "releases": releases, "windows": []}


def complete_cells(mean=1):
    return [cell(x=x, y=y, mean=mean, identity=12 + (x // 10) + 2 * (y // 10))
            for y in (0, 10) for x in (0, 10)]


def evaluate(source=None, releases=(), **kwargs):
    source = replay() if source is None else source
    return queries.evaluate(source, result(source, list(releases)), include_queries=True, **kwargs)


class UrbanPrivacyQueriesTests(unittest.TestCase):
    def test_exact_tiling_known_values_and_world_specific_reference(self):
        source = replay(positions=lambda _t: [(1, 1)] * 4)
        cells = complete_cells(mean=0)
        cells[0]["mean_sample_occupancy"] = 4
        output = evaluate(source, [release(cells)])
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 4)
        self.assertEqual(output["exact"]["summary"]["occupancy_mae"], 0)
        self.assertEqual([q["prediction"] for q in output["exact"]["queries"]], [4, 0, 0, 0])
        self.assertEqual(output["estimate"]["summary"]["occupancy_mae"], 0)

    def test_spatially_coarse_estimates_are_not_exact(self):
        source = replay(positions=lambda _t: [(1, 1)] * 4)
        output = evaluate(source, [release([cell(side=20, mean=4, identity=3, depth=0)])])
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 0)
        self.assertEqual(output["estimate"]["summary"]["answered_queries"], 4)
        self.assertEqual(output["estimate"]["summary"]["occupancy_mae"], 1.5)
        self.assertTrue(all(q["prediction"] is None for q in output["exact"]["queries"]))

    def test_temporally_coarse_estimate_is_not_exact(self):
        source = replay(end=2000, positions=lambda t: [(1, 1)] * (4 if t < 1000 else 0))
        cells = complete_cells(mean=0)
        cells[0]["mean_sample_occupancy"] = 36 / 19
        output = evaluate(source, [release(cells, end=2000)])
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 0)
        self.assertEqual(output["estimate"]["summary"]["answered_queries"], 8)
        self.assertAlmostEqual(output["estimate"]["summary"]["occupancy_mae"], .5)

    def test_four_fine_cells_form_one_exact_query(self):
        cells = [cell(x=x, y=y, side=5, mean=1, identity=48 + x // 5 + 2 * (y // 5), depth=2)
                 for y in (0, 5) for x in (0, 5)]
        output = evaluate(replay(positions=lambda _t: [(1, 1)] * 4), [release(cells)])
        self.assertEqual(output["exact"]["summary"]["answered_query_coverage"], .25)
        self.assertEqual(output["exact"]["queries"][0]["prediction"], 4)
        self.assertEqual(output["exact"]["queries"][0]["absolute_error"], 0)

    def test_asynchronous_spatial_temporal_tiles_can_answer(self):
        releases = [release([cell(mean=2)], end=400, name="west-early"),
                    release([cell(mean=5)], start=400, name="west-late"),
                    release([cell(x=10)], name="east"),
                    release([cell(y=10)], name="southwest"),
                    release([cell(x=10, y=10)], name="southeast")]
        output = evaluate(releases=releases)
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 4)
        self.assertEqual(output["exact"]["queries"][0]["prediction"], 4)

    def test_partial_spatial_support_and_measured_empty_remain_unknown(self):
        output = evaluate(releases=[release([cell(side=5, mean=0, identity=48, depth=2)])])
        self.assertEqual(output["exact"]["summary"]["reference_available_queries"], 4)
        self.assertEqual(output["exact"]["summary"]["known_zero_reference_queries"], 4)
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 0)
        self.assertEqual(output["estimate"]["summary"]["answered_queries"], 0)
        self.assertIsNone(output["exact"]["queries"][0]["prediction"])

    def test_missing_temporal_sample_is_unknown(self):
        output = evaluate(releases=[release(complete_cells(), end=500, name="early"),
                                   release(complete_cells(), start=600, name="late")])
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 0)
        self.assertEqual(output["estimate"]["summary"]["answered_queries"], 0)

    def test_gaps_between_sample_times_do_not_invent_measurements(self):
        output = evaluate(releases=[release(complete_cells(), end=501, name="early"),
                                   release(complete_cells(), start=599, name="late")])
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 4)
        self.assertEqual([q["prediction"] for q in output["exact"]["queries"]], [1] * 4)

    def test_explicit_zero_is_known_but_absent_support_is_not(self):
        output = evaluate(releases=[release(complete_cells(mean=0))])
        self.assertEqual(output["exact"]["summary"]["answered_query_coverage"], 1)
        self.assertEqual(output["exact"]["summary"]["occupancy_mae"], 0)
        absent = evaluate()
        self.assertEqual(absent["exact"]["summary"]["answered_queries"], 0)
        self.assertIsNone(absent["exact"]["summary"]["occupancy_mae"])

    def test_straddling_zero_is_not_specially_inferred(self):
        output = evaluate(releases=[release([cell(side=20, mean=0, identity=3, depth=0)])])
        self.assertEqual(output["estimate"]["summary"]["answered_queries"], 4)
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 0)

    def test_unknown_mean_cannot_supply_exact_or_estimated_support(self):
        cells = complete_cells()
        cells[0]["mean_sample_occupancy"] = None
        output = evaluate(releases=[release(cells)])
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 3)
        self.assertIsNone(output["exact"]["queries"][0]["prediction"])

    def test_missing_and_unavailable_reference_do_not_change_public_answers(self):
        for absent in (True, False):
            with self.subTest(absent=absent):
                source = replay()
                if absent:
                    source["batches"].pop(2)
                else:
                    source["batches"][2].update(status="unavailable", observations=[])
                output = evaluate(source, [release(complete_cells(mean=0))])
                self.assertEqual(output["exact"]["summary"]["answered_queries"], 4)
                self.assertEqual(output["exact"]["summary"]["scored_queries"], 0)
                self.assertEqual(output["exact"]["summary"]["reference_available_queries"], 0)
                self.assertTrue(all(q["reference"] is None for q in output["exact"]["queries"]))

    def test_predictions_ignore_changed_private_truth_and_debug_windows(self):
        source = replay()
        public = result(source, [release(complete_cells())])
        a = queries.evaluate(source, public, include_queries=True)
        public["windows"] = [{"selected": True, "mean_sample_occupancy": 999, "coverage": "full"}]
        public["input_observation_contributions"] = 999
        changed = replay(positions=lambda _t: [(1, 1)] * 2)
        b = queries.evaluate(changed, public, include_queries=True)
        self.assertEqual([q["prediction"] for q in a["exact"]["queries"]],
                         [q["prediction"] for q in b["exact"]["queries"]])
        self.assertEqual(a["exact"]["queries"][0]["reference"], 0)
        self.assertEqual(b["exact"]["queries"][0]["reference"], 2)

    def test_first_query_nine_samples_later_queries_ten(self):
        source = replay(end=2000)
        output = evaluate(source, [release(complete_cells(mean=0), name="first"),
                                   release(complete_cells(mean=1), start=1000, end=2000, name="second")])
        self.assertEqual([q["scheduled_samples"] for q in output["exact"]["queries"]], [9] * 4 + [10] * 4)
        self.assertEqual([q["prediction"] for q in output["exact"]["queries"]], [0] * 4 + [1] * 4)

    def test_half_open_boundary_truth_belongs_to_next_query(self):
        source = replay(end=2000, positions=lambda t: [(10, 1)] if t == 1000 else [])
        output = evaluate(source)
        rows = output["exact"]["queries"]
        self.assertEqual(rows[1]["reference"], 0)
        self.assertEqual(rows[5]["reference"], .1)

    def test_full_frozen_workload_is_19200_queries(self):
        output = evaluate(replay(side=80, end=300000))
        self.assertEqual(output["exact"]["summary"]["reference_queries"], 19200)
        self.assertEqual(output["exact"]["summary"]["reference_available_queries"], 19200)
        self.assertEqual(output["estimate"]["summary"]["reference_queries"], 19200)
        self.assertEqual(output["reference"]["excluded_trailing_ms"], 0)

    def test_partial_trailing_window_is_excluded_identically(self):
        output = evaluate(replay(end=2500))
        self.assertEqual(output["exact"]["summary"]["reference_queries"], 8)
        self.assertEqual(output["reference"]["excluded_trailing_ms"], 500)

    def test_estimator_is_unchanged_occupancy_evaluate(self):
        source = replay(positions=lambda t: [(1, 1)] * (t // 100))
        raw = result(source, [release([cell(side=20, mean=6, identity=3, depth=0)])])
        expected = occupancy.evaluate(source, raw)
        output = queries.evaluate(source, raw, include_queries=True)
        self.assertEqual(output["estimate"]["queries"], expected["queries"])
        for key, value in expected["summary"].items():
            self.assertEqual(output["estimate"]["summary"][key], value)
        self.assertEqual(output["reference"], expected["reference"])

    def test_v2_semantic_channel_is_used_without_private_fields(self):
        source = replay()
        taxonomy = {"id": "query", "version": "1", "nodes": [
            {"id": "road_user", "loss": 1},
            {"id": "adult_pedestrian", "parent": "road_user", "loss": 0,
             "input_types": ["Adult Pedestrian"]}]}
        cells = complete_cells()
        for c in cells:
            c["semantic"] = {"schema": "ump.semantic-release.v1", "taxonomy_id": "query",
                "taxonomy_version": "1", "categories": [{"category_id": "adult_pedestrian",
                "observation_contributions": 9, "distinct_contributors": 1}],
                "min_category_distinct_contributors": 1, "semantic_mean_loss": 0, "semantic_max_loss": 0}
        native = result(source, [release(cells)])
        public = semantic_privacy.export_public(native, taxonomy)
        output = queries.evaluate(source, public)
        self.assertEqual(output["exact"]["summary"]["answered_queries"], 4)
        bad = deepcopy(public)
        bad["private_target_id"] = "secret"
        with self.assertRaises(ValueError):
            queries.evaluate(source, bad)

    def test_overlap_nan_and_source_mismatch_rejected(self):
        source = replay()
        for cells in ([cell(), cell()], [cell(mean=math.nan)]):
            with self.subTest(cells=cells), self.assertRaises(ValueError):
                evaluate(source, [release(cells)])
        raw = result(source, [])
        raw["source"]["end_ms"] = 2000
        with self.assertRaises(ValueError):
            queries.evaluate(source, raw)

    def test_sealed_after_horizon_not_visible_in_final_snapshot(self):
        with self.assertRaisesRegex(ValueError, "after its horizon"):
            evaluate(releases=[release(complete_cells(), sealed=1001)])

    def test_compact_default_and_invalid_option(self):
        source = replay()
        output = queries.evaluate(source, result(source, []))
        self.assertNotIn("queries", output["exact"])
        self.assertNotIn("queries", output["estimate"])
        with self.assertRaises(ValueError):
            queries.evaluate(source, result(source, []), include_queries=1)


if __name__ == "__main__":
    unittest.main()
