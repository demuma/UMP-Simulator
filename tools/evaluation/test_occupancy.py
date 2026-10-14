"""Hand-computed fixed-query reconstruction and missing-output regressions."""

import copy
import unittest

from occupancy import evaluate


def replay(width=20, height=10, end=1000, occupied=None):
    """occupied(time) returns positions; empty measured samples remain explicit."""
    occupied = occupied or (lambda _: [])
    return {
        "schema": "ump.observation-replay.v1", "run_id": "fixture", "sensor_id": "agbs",
        "coverage": {"x": 0, "y": 0, "width": width, "height": height, "leaf_depth": 3},
        "sampling_period_ms": 100, "end_ms": end,
        "batches": [
            {"sequence": time // 100, "observed_at_ms": time, "status": "measured",
             "observations": [{"id": str(index), "type": "pedestrian", "cell_id": 192,
                               "x": x, "y": y}
                              for index, (x, y) in enumerate(occupied(time))]}
            for time in range(100, end, 100)],
    }


def cell(x=0, y=0, width=20, height=10, mean=0):
    return {"cell_id": 12, "depth": 1, "x": x, "y": y, "width": width,
            "height": height, "mean_sample_occupancy": mean,
            "distinct_road_users": 1, "observation_contributions": 9}


def release(cells, start=0, end=1000, sealed=None, name="release"):
    return {"release_id": name, "start_ms": start, "end_ms": end,
            "sealed_at_ms": end if sealed is None else sealed, "cells": cells}


def result(source, releases):
    return {"schema": "ump.replay-result.v1", "mode": "fixture",
            "source": {key: copy.deepcopy(source[key]) for key in
                       ("run_id", "sensor_id", "coverage", "sampling_period_ms", "end_ms")},
            "releases": releases, "windows": []}


class OccupancyTests(unittest.TestCase):
    def test_coarse_uniform_counterexample_keeps_reference_fixed(self):
        source = replay(occupied=lambda _: [(1, 1)] * 4)
        evaluation = evaluate(source, result(source, [release([cell(mean=4)])]))
        self.assertEqual(evaluation["summary"]["reference_queries"], 2)
        self.assertEqual(evaluation["summary"]["occupancy_mae"], 2)
        self.assertEqual(evaluation["summary"]["answered_query_coverage"], 1)
        self.assertEqual([q["reference"] for q in evaluation["queries"]], [4, 0])
        self.assertEqual([q["prediction"] for q in evaluation["queries"]], [2, 2])

    def test_finer_cells_sum_to_reference_occupancy(self):
        source = replay(width=10, occupied=lambda _: [(1, 1)] * 4)
        cells = [cell(x=x, y=y, width=5, height=5, mean=1)
                 for x in (0, 5) for y in (0, 5)]
        evaluation = evaluate(source, result(source, [release(cells)]))
        self.assertEqual(evaluation["queries"][0]["prediction"], 4)
        self.assertEqual(evaluation["summary"]["occupancy_mae"], 0)

    def test_suppression_and_sparse_empty_cells_remain_unknown(self):
        source = replay(occupied=lambda _: [(1, 1)] * 4)
        evaluation = evaluate(source, result(source, [release([cell(width=10, mean=4)])]))
        self.assertEqual(evaluation["summary"]["occupancy_mae"], 0)
        self.assertEqual(evaluation["summary"]["answered_query_coverage"], .5)
        missing = evaluation["queries"][1]
        self.assertEqual(missing["reference"], 0)
        self.assertIsNone(missing["prediction"])
        self.assertFalse(missing["answered"])

    def test_spatial_gap_inside_reference_cell_is_not_zero_filled(self):
        source = replay(width=10)
        cells = [cell(width=5, height=10, mean=0)]
        evaluation = evaluate(source, result(source, [release(cells)]))
        self.assertIsNone(evaluation["summary"]["occupancy_mae"])
        self.assertEqual(evaluation["summary"]["answered_query_coverage"], 0)

    def test_measured_empty_truth_is_zero_but_absent_prediction_is_unknown(self):
        source = replay()
        evaluation = evaluate(source, result(source, []))
        self.assertEqual(evaluation["summary"]["reference_available_queries"], 2)
        self.assertEqual(evaluation["summary"]["answered_queries"], 0)
        self.assertEqual([q["reference"] for q in evaluation["queries"]], [0, 0])
        self.assertIsNone(evaluation["summary"]["occupancy_mae"])
        # A hypothetical explicit public zero-valued full footprint is usable;
        # current sparse releases do not provide this certificate implicitly.
        explicit = evaluate(source, result(source, [release([cell(mean=0)])]))
        self.assertEqual(explicit["summary"]["occupancy_mae"], 0)
        self.assertEqual(explicit["summary"]["answered_query_coverage"], 1)

    def test_missing_reference_sample_is_not_zero(self):
        source = replay()
        source["batches"].pop(2)
        evaluation = evaluate(source, result(source, [release([cell(mean=0)])]))
        self.assertEqual(evaluation["summary"]["reference_available_queries"], 0)
        self.assertEqual(evaluation["summary"]["answered_queries"], 2)
        self.assertEqual(evaluation["summary"]["scored_queries"], 0)
        self.assertIsNone(evaluation["summary"]["occupancy_mae"])
        self.assertTrue(all(q["reference"] is None for q in evaluation["queries"]))

    def test_unavailable_sample_is_not_a_measured_empty_sample(self):
        source = replay()
        source["batches"][3]["status"] = "unavailable"
        evaluation = evaluate(source, result(source, []))
        self.assertEqual(evaluation["summary"]["reference_available_queries"], 0)

    def test_first_interval_has_nine_discrete_samples(self):
        source = replay(width=10, occupied=lambda time: [(1, 1)] * (3 if time < 400 else 6))
        outputs = [release([cell(width=10, mean=3)], end=400, name="early"),
                   release([cell(width=10, mean=6)], start=400, name="late")]
        evaluation = evaluate(source, result(source, outputs))
        query = evaluation["queries"][0]
        self.assertEqual(query["scheduled_samples"], 9)
        self.assertEqual(query["reference"], 5)
        self.assertEqual(query["prediction"], 5)
        self.assertNotEqual(query["prediction"], 3 * .4 + 6 * .6)
        self.assertEqual(evaluation["summary"]["occupancy_mae"], 0)

    def test_later_interval_includes_left_boundary_has_ten_samples(self):
        source = replay(width=10, end=2000, occupied=lambda time: [(1, 1)] if time == 1000 else [])
        evaluation = evaluate(source, result(source, [release([cell(width=10, mean=0)],
                                                             end=2000)]))
        self.assertEqual([q["scheduled_samples"] for q in evaluation["queries"]], [9, 10])
        self.assertEqual([q["reference"] for q in evaluation["queries"]], [0, .1])
        self.assertEqual(evaluation["summary"]["occupancy_mae"], .05)

    def test_temporal_uniformity_can_hide_changes_across_query_intervals(self):
        source = replay(width=10, end=2000,
                        occupied=lambda time: [(1, 1)] * (4 if time < 1000 else 0))
        mean = 36 / 19  # 9 samples at 4, then 10 samples at 0.
        evaluation = evaluate(source, result(source, [release([cell(width=10, mean=mean)],
                                                             end=2000)]))
        for query in evaluation["queries"]:
            self.assertAlmostEqual(query["prediction"], mean)
        self.assertAlmostEqual(evaluation["summary"]["occupancy_mae"], 2)

    def test_missing_temporal_sample_support_makes_whole_query_unanswered(self):
        source = replay(width=10)
        outputs = [release([cell(width=10, mean=0)], end=500, name="early"),
                   release([cell(width=10, mean=0)], start=600, name="late")]
        evaluation = evaluate(source, result(source, outputs))
        self.assertFalse(evaluation["queries"][0]["answered"])
        self.assertIsNone(evaluation["queries"][0]["prediction"])

    def test_gap_between_discrete_samples_does_not_change_sampled_query(self):
        source = replay(width=10)
        outputs = [release([cell(width=10, mean=0)], end=501, name="early"),
                   release([cell(width=10, mean=0)], start=599, name="late")]
        evaluation = evaluate(source, result(source, outputs))
        self.assertTrue(evaluation["queries"][0]["answered"])
        self.assertEqual(evaluation["queries"][0]["prediction"], 0)

    def test_private_counts_and_checks_never_supply_predictions(self):
        source = replay()
        outputs = result(source, [])
        before = evaluate(source, outputs)
        outputs["windows"] = [{"cells": [dict(cell(mean=999), selected=True)],
                               "counts": {"mean_sample_occupancy": 999},
                               "coverage": "complete"}]
        after = evaluate(source, outputs)
        self.assertEqual(after, before)

    def test_overlap_is_rejected_instead_of_double_counted(self):
        source = replay()
        with self.assertRaisesRegex(ValueError, "overlap"):
            evaluate(source, result(source, [release([cell(), cell(width=10)])]))
        with self.assertRaisesRegex(ValueError, "overlap"):
            evaluate(source, result(source, [release([cell()], end=600, name="first"),
                                             release([cell()], start=500, name="second")]))

    def test_simultaneous_disjoint_public_support_can_jointly_answer(self):
        source = replay()
        outputs = [release([cell(width=10)], name="west"),
                   release([cell(x=10, width=10)], name="east")]
        evaluation = evaluate(source, result(source, outputs))
        self.assertEqual(evaluation["summary"]["answered_query_coverage"], 1)

    def test_nonfinite_and_mismatched_inputs_rejected(self):
        source = replay()
        outputs = result(source, [release([cell(mean=float("nan"))])])
        with self.assertRaises(ValueError):
            evaluate(source, outputs)
        outputs = result(source, [])
        outputs["source"]["end_ms"] = 2000
        with self.assertRaisesRegex(ValueError, "end_ms"):
            evaluate(source, outputs)
        source["batches"][0]["observed_at_ms"] = 0
        with self.assertRaises(ValueError):
            evaluate(source, result(source, []))

    def test_half_open_spatial_boundary_places_agent_in_right_cell(self):
        source = replay(occupied=lambda _: [(10, 1)])
        evaluation = evaluate(source, result(source, []))
        self.assertEqual([q["reference"] for q in evaluation["queries"]], [0, 1])

    def test_standard_area_has_64_queries_per_full_second(self):
        source = replay(width=80, height=80, end=2500)
        evaluation = evaluate(source, result(source, []))
        self.assertEqual(evaluation["summary"]["reference_queries"], 128)
        self.assertEqual(evaluation["reference"]["query_end_ms"], 2000)
        self.assertEqual(evaluation["reference"]["excluded_trailing_ms"], 500)

    def test_age_and_resolution_are_simulated_sealing_statistics(self):
        source = replay()
        evaluation = evaluate(source, result(source, [release([cell()], sealed=1250)]))
        stats = evaluation["release_resolution_and_age"]
        self.assertEqual(stats["cell_area_m2"]["mean"], 200)
        self.assertEqual(stats["simulated_age_at_sealing_ms"]["mean"], 1250)
        self.assertEqual(stats["simulated_post_window_sealing_delay_ms"]["mean"], 250)
        self.assertEqual(stats["cell_size_distribution"],
                         [{"width_m": 20, "height_m": 10, "cells": 1}])


if __name__ == "__main__":
    unittest.main()
