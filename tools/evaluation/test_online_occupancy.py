"""Causal availability, fixed query cohorts, and hand-computed deadline utility."""

import copy
import json
import math
import unittest

import occupancy
from online_occupancy import (compact, evaluate, paired_rollup, pool_paired_rollups,
                              rollup, summarize_at_checkpoint)


def replay(width=10, height=10, end=4000, occupied=None):
    occupied = occupied or (lambda _: [])
    return {"schema": "ump.observation-replay.v1", "run_id": "online-fixture",
            "sensor_id": "agbs", "sampling_period_ms": 100, "end_ms": end,
            "coverage": {"x": 0, "y": 0, "width": width, "height": height, "leaf_depth": 2},
            "batches": [{"sequence": t // 100, "observed_at_ms": t, "status": "measured",
                         "observations": [{"id": str(i), "type": "pedestrian", "cell_id": 48,
                                           "x": x, "y": y}
                                          for i, (x, y) in enumerate(occupied(t))]}
                        for t in range(100, end, 100)]}


def cell(x=0, y=0, width=10, height=10, mean=0, cell_id=12):
    return {"cell_id": cell_id, "depth": 1, "x": x, "y": y, "width": width,
            "height": height, "mean_sample_occupancy": mean, "observation_contributions": 9,
            "distinct_road_users": 1, "effective_policy_id": "fixture"}


def release(cells, start=0, end=1000, sealed=None, name="release"):
    return {"release_id": name, "start_ms": start, "end_ms": end,
            "sealed_at_ms": end if sealed is None else sealed,
            "model": "fixture", "policy_id": "fixture", "policy_version": "1", "cells": cells}


def result(source, releases):
    return {"schema": "ump.replay-result.v1", "mode": "fixture",
            "source": {key: copy.deepcopy(source[key]) for key in
                       ("run_id", "sensor_id", "coverage", "sampling_period_ms", "end_ms")},
            "releases": releases, "windows": []}


def projection(evaluation, lag=0, boundary=False):
    return evaluation["boundary_by_lag_ms" if boundary else "evaluations_by_lag_ms"][str(lag)]


class OnlineOccupancyTests(unittest.TestCase):
    def test_strict_interior_cohort_is_fixed_across_deadlines(self):
        source = replay(width=80, height=80, end=16000)
        value = evaluate(source, result(source, []))
        identities = None
        for lag in (0, 200, 500, 1000):
            current = projection(value, lag)
            self.assertEqual(current["summary"]["reference_queries"], 896)
            self.assertEqual(current["summary"]["answered_queries"], 0)
            keys = [(q["column"], q["row"], q["start_ms"], q["end_ms"])
                    for q in current["queries"]]
            self.assertEqual(max(key[-1] for key in keys), 14000)
            if identities is not None:
                self.assertEqual(keys, identities)
            identities = keys
        self.assertEqual(len(projection(value, 1000, True)["queries"]), 128)

    def test_delayed_aggregate_is_available_at_seal_never_before(self):
        source = replay(occupied=lambda _: [(1, 1)] * 3)
        value = evaluate(source, result(source, [release([cell(mean=3)], sealed=1200)]),
                         deadline_lags_ms=(0, 199, 200, 500))
        for lag in (0, 199):
            query = projection(value, lag)["queries"][0]
            self.assertEqual(query["ready_at_ms"], 1200)
            self.assertFalse(query["answered"])
            self.assertIsNone(query["prediction"])
            self.assertIsNone(query["absolute_error"])
        for lag in (200, 500):
            query = projection(value, lag)["queries"][0]
            self.assertTrue(query["answered"])
            self.assertEqual(query["prediction"], 3)
            self.assertEqual(query["absolute_error"], 0)

    def test_readiness_is_latest_required_spatial_piece(self):
        source = replay(occupied=lambda _: [(1, 1)] * 4)
        pieces = [release([cell(x=x, y=y, width=5, height=5, mean=1)],
                          sealed=1000 + 100 * i, name=str(i))
                  for i, (x, y) in enumerate(((0, 0), (5, 0), (0, 5), (5, 5)))]
        value = evaluate(source, result(source, pieces))
        for lag in (0, 200):
            self.assertFalse(projection(value, lag)["queries"][0]["answered"])
        query = projection(value, 500)["queries"][0]
        self.assertEqual(query["ready_at_ms"], 1300)
        self.assertEqual(query["prediction"], 4)
        self.assertEqual(query["absolute_error"], 0)

    def test_partial_spatial_or_temporal_support_is_unknown(self):
        source = replay()
        outputs = [result(source, [release([cell(width=5)])]),
                   result(source, [release([cell()], end=500, name="a"),
                                   release([cell()], start=600, name="b")])]
        for output in outputs:
            value = evaluate(source, output)
            for lag in (0, 200, 500, 1000):
                query = projection(value, lag)["queries"][0]
                self.assertFalse(query["answered"])
                self.assertIsNone(query["ready_at_ms"])
                self.assertIsNone(query["prediction"])

    def test_explicit_zero_valid_null_and_absence_unknown(self):
        source = replay(width=30)
        value = evaluate(source, result(source, [release([cell(), cell(x=10, mean=None)])]))
        rows = projection(value, 1000)["queries"][:3]
        self.assertEqual([q["answered"] for q in rows], [True, False, False])
        self.assertEqual([q["prediction"] for q in rows], [0, None, None])
        self.assertEqual([q["reference"] for q in rows], [0, 0, 0])
        self.assertEqual([q["ready_at_ms"] for q in rows], [1000, None, None])

    def test_crossing_aggregate_is_not_clipped_or_partially_revealed(self):
        source = replay(occupied=lambda t: [(1, 1)] * (4 if t < 1000 else 0))
        mean = 36 / 19
        value = evaluate(source, result(source, [release([cell(mean=mean)], end=2000)]),
                         deadline_lags_ms=(0, 500, 1000))
        first = projection(value, 500)["queries"][0]
        self.assertEqual(first["ready_at_ms"], 2000)
        self.assertFalse(first["answered"])
        self.assertIsNone(first["prediction"])
        self.assertAlmostEqual(projection(value, 1000)["queries"][0]["prediction"], mean)
        second = projection(value)["queries"][1]
        self.assertAlmostEqual(second["prediction"], mean)
        self.assertEqual(second["reference"], 0)

    def test_existing_normalization_errors_contributions_preserved(self):
        source = replay(width=20, occupied=lambda t: [(1, 1)] * (3 if t < 400 else 6))
        output = result(source, [release([cell(mean=3)], end=400, name="a"),
                                 release([cell(mean=6)], start=400, name="b"),
                                 release([cell(width=20, mean=6)], start=1000, end=2000, name="c"),
                                 release([cell(width=20, mean=6)], start=2000, end=3000, name="d")])
        value = evaluate(source, output, deadline_lags_ms=(0,))
        legacy = occupancy.evaluate(source, output)
        rows = projection(value)["queries"]
        self.assertEqual([q["scheduled_samples"] for q in rows], [9, 9, 10, 10, 10, 10])
        for row, original in zip(rows, legacy["queries"]):
            for key in original:
                self.assertEqual(row[key], original[key], key)
        expected = occupancy._summarize_query_subset(legacy["queries"][:6])
        for key in expected:
            self.assertEqual(projection(value)["summary"][key], expected[key], key)

    def test_source_boundary_belongs_to_following_discrete_query(self):
        source = replay(occupied=lambda t: [(1, 1)] if t == 1000 else [])
        output = result(source, [release([cell()], name="early"),
                                 release([cell(mean=.1)], start=1000, end=2000, name="late")])
        rows = projection(evaluate(source, output, deadline_lags_ms=(0,)))["queries"]
        self.assertEqual([q["reference"] for q in rows[:2]], [0, .1])
        for query in rows[:2]:
            self.assertAlmostEqual(query["absolute_error"], 0)
        self.assertEqual([q["ready_at_ms"] for q in rows[:2]], [1000, 2000])

    def test_missing_reference_retains_public_answered_coverage(self):
        source = replay()
        source["batches"][3]["status"] = "unavailable"
        value = evaluate(source, result(source, [release([cell()])]))
        query = projection(value)["queries"][0]
        self.assertTrue(query["answered"])
        self.assertFalse(query["reference_available"])
        self.assertIsNone(query["reference"])
        self.assertIsNone(query["absolute_error"])
        self.assertEqual(projection(value)["summary"]["answered_queries"], 1)
        self.assertEqual(projection(value)["summary"]["scored_queries"], 0)

    def test_future_public_values_cannot_change_past_predictions(self):
        source = replay()
        output = result(source, [release([cell(mean=1)], sealed=1300)])
        before = evaluate(source, output)
        output["releases"][0]["cells"][0]["mean_sample_occupancy"] = 999
        after = evaluate(source, output)
        for lag in (0, 200):
            for key in ("answered", "prediction", "absolute_error"):
                self.assertEqual(projection(before, lag)["queries"][0][key],
                                 projection(after, lag)["queries"][0][key])
        self.assertEqual(projection(before, 500)["queries"][0]["prediction"], 1)
        self.assertEqual(projection(after, 500)["queries"][0]["prediction"], 999)

    def test_whole_release_filtering_matches_direct_deadline_reference(self):
        source = replay(width=20)
        output = result(source, [release([cell(mean=3)], sealed=1200, name="a"),
                                 release([cell(x=10, mean=2)], sealed=1500, name="b"),
                                 release([cell(width=20, mean=1)], start=1000, end=2500,
                                         sealed=2700, name="c")])
        value = evaluate(source, output)
        for lag in (0, 200, 500, 1000):
            for query in projection(value, lag)["queries"]:
                filtered = copy.deepcopy(output)
                filtered["releases"] = [r for r in output["releases"]
                                         if r["sealed_at_ms"] <= query["deadline_ms"]]
                direct = occupancy.evaluate(source, filtered)
                same = next(q for q in direct["queries"] if all(
                    q[k] == query[k] for k in ("column", "row", "start_ms", "end_ms")))
                for key in ("answered", "prediction", "absolute_error"):
                    self.assertEqual(query[key], same[key])

    def test_coverage_monotone_with_identical_denominators(self):
        source = replay(width=20)
        output = result(source, [release([cell()], sealed=1100, name="a"),
                                 release([cell(x=10)], sealed=1400, name="b"),
                                 release([cell(width=20)], start=1000, end=2000, sealed=2800, name="c")])
        value = evaluate(source, output)
        counts = [projection(value, lag)["summary"]["answered_queries"]
                  for lag in (0, 200, 500, 1000)]
        self.assertEqual(counts, sorted(counts))
        self.assertEqual([projection(value, lag)["summary"]["reference_queries"]
                          for lag in (0, 200, 500, 1000)], [4] * 4)

    def test_boundary_eof_censoring_do_not_become_primary_misses(self):
        source = replay()
        value = evaluate(source, result(source, [release([cell()], start=3000, end=4000)]))
        zero, long = projection(value, 0, True), projection(value, 1000, True)
        self.assertEqual(zero["summary"]["reference_queries"], 2)
        self.assertEqual(zero["summary"]["deadline_at_eof_queries"], 1)
        self.assertEqual(long["summary"]["cohort_queries"], 2)
        self.assertEqual(long["summary"]["reference_queries"], 1)
        self.assertEqual(long["summary"]["censored_queries"], 1)
        self.assertEqual(long["summary"]["deadline_at_eof_queries"], 1)
        self.assertEqual(long["summary"]["answered_queries"], 0)
        self.assertFalse(long["queries"][1]["deadline_observed"])
        self.assertIsNone(long["queries"][1]["absolute_error"])

    def test_checkpoint_excludes_future_and_never_backfills_misses(self):
        source = replay()
        value = evaluate(source, result(source, [release([cell()], sealed=1300)]))
        early = summarize_at_checkpoint(value, 999)["by_lag_ms"]
        self.assertEqual(early["0"]["primary"]["reference_queries"], 0)
        self.assertIsNone(early["0"]["primary"]["answered_query_coverage"])
        due = summarize_at_checkpoint(value, 1200)["by_lag_ms"]
        self.assertEqual(due["0"]["primary"]["reference_queries"], 1)
        self.assertEqual(due["200"]["primary"]["reference_queries"], 1)
        self.assertEqual(due["500"]["primary"]["reference_queries"], 0)
        later = summarize_at_checkpoint(value, 4000)["by_lag_ms"]
        self.assertEqual(later["0"]["primary"]["answered_queries"], 0)
        self.assertEqual(later["500"]["primary"]["answered_queries"], 1)
        with self.assertRaises(ValueError):
            summarize_at_checkpoint(value, 4001)

    def test_public_and_private_result_same_queries_without_mutation(self):
        from empirical_privacy import export_public
        source = replay(width=20, height=20)
        cells = [cell(x=10 * (q & 1), y=10 * (q >> 1), cell_id=12 + q) for q in range(4)]
        output = result(source, [release(cells)])
        public = export_public(output)
        saved = copy.deepcopy((source, output, public))
        direct, projected = evaluate(source, output), evaluate(source, public)
        self.assertEqual(direct["evaluations_by_lag_ms"], projected["evaluations_by_lag_ms"])
        self.assertEqual(direct["boundary_by_lag_ms"], projected["boundary_by_lag_ms"])
        self.assertEqual((source, output, public), saved)

    def test_compact_pool_uses_error_sums_not_average_conditional_means(self):
        source = replay(occupied=lambda _: [(1, 1)] * 2)
        first = evaluate(source, result(source, [release([cell(mean=2)])]), deadline_lags_ms=(0,))
        releases = [release([cell(mean=4)], start=t, end=t + 1000, name=str(t))
                    for t in (0, 1000, 2000)]
        second = evaluate(source, result(source, releases), deadline_lags_ms=(0,))
        pooled = rollup([compact(first), compact(second)])
        self.assertEqual(pooled, rollup([first, second]))
        row = pooled["by_lag_ms"]["0"]["primary"]
        for key, value in {"reference_queries": 6, "scored_queries": 4, "absolute_error_sum": 6,
                           "occupancy_mae": 1.5, "answered_query_coverage": 4 / 6,
                           "reference_observation_contributions": 116,
                           "answered_reference_observation_contributions": 76,
                           "reconstructed_answered_observation_contribution_equivalents": 134}.items():
            self.assertEqual(row[key], value, key)
        self.assertNotIn("queries", compact(first)["evaluations_by_lag_ms"]["0"])

    def test_matched_errors_intersect_and_preserve_observed_denominator(self):
        source = replay(occupied=lambda _: [(1, 1)] * 2)
        first = evaluate(source, result(source, [release([cell(mean=2)])]), deadline_lags_ms=(0,))
        second = evaluate(source, result(source, [release([cell(mean=4)]),
                          release([cell(mean=10)], start=1000, end=2000, name="b")]),
                          deadline_lags_ms=(0,))
        comparison = paired_rollup([(first, second)])
        row = comparison["by_lag_ms"]["0"]["primary"]
        for key, value in {"reference_queries": 3, "matched_scored_queries": 1,
                           "matched_query_coverage": 1 / 3, "first_mae": 0,
                           "second_mae": 2, "delta_second_minus_first": 2}.items():
            self.assertEqual(row[key], value, key)
        pooled = pool_paired_rollups([comparison, comparison])
        self.assertEqual(pooled["world_pairs"], 2)
        self.assertEqual(pooled, paired_rollup([(first, second), (first, second)]))
        changed = copy.deepcopy(second)
        changed["evaluations_by_lag_ms"]["0"]["queries"][0]["column"] = 9
        with self.assertRaisesRegex(ValueError, "identities"):
            paired_rollup([(first, changed)])

    def test_all_helpers_immutable_and_json_finite(self):
        source = replay()
        output = result(source, [release([cell()], sealed=1200)])
        original = copy.deepcopy((source, output))
        value = evaluate(source, output)
        saved = copy.deepcopy(value)
        comparison = paired_rollup([(value, value)])
        for artifact in (value, compact(value), rollup([value]), comparison,
                         pool_paired_rollups([comparison]), summarize_at_checkpoint(value, 1600)):
            json.dumps(artifact, allow_nan=False)
        self.assertEqual((source, output), original)
        self.assertEqual(value, saved)

    def test_bad_lags_schema_nonfinite_and_overlaps_rejected(self):
        source = replay()
        for lags in ((), [], (True,), (0, .5), (200, 0), (0, 0), (-1,)):
            with self.subTest(lags=lags), self.assertRaises(ValueError):
                evaluate(source, result(source, []), deadline_lags_ms=lags)
        with self.assertRaises(ValueError):
            evaluate(source, result(source, [release([cell(mean=math.nan)])]))
        with self.assertRaisesRegex(ValueError, "overlap"):
            evaluate(source, result(source, [release([cell(), cell()])]))
        with self.assertRaises(ValueError):
            evaluate(source, {"schema": "wrong"})
        mismatch = result(source, [])
        mismatch["source"]["end_ms"] += 100
        with self.assertRaises(ValueError):
            evaluate(source, mismatch)
        for helper in (rollup, paired_rollup, pool_paired_rollups):
            with self.assertRaises(ValueError):
                helper([])
        value = evaluate(source, result(source, []))
        different = copy.deepcopy(value)
        different["reference"]["cell_side_m"] = 20
        with self.assertRaisesRegex(ValueError, "identical"):
            rollup([value, different])


if __name__ == "__main__":
    unittest.main()
