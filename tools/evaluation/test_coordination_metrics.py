"""Hand-computed contribution weighting and honest diagnostic availability."""

from copy import deepcopy
import unittest

from coordination_metrics import summarize


def cell(contributions):
    return dict(observation_contributions=contributions)


def release(cells, start=0, end=100, sealed=100):
    return dict(start_ms=start, end_ms=end, sealed_at_ms=sealed, cells=cells)


class CoordinationMetricTests(unittest.TestCase):
    def test_weighted_means_and_quantiles_ignore_release_count(self):
        result = dict(releases=[release([cell(9)]),
                                release([cell(1)], start=100, end=400, sealed=450)])
        timing = summarize(result)["public_release_timing"]
        self.assertEqual(timing["observation_contribution_weight"], 10)
        self.assertEqual(timing["window_duration_ms"],
                         dict(count=2, total_weight=10, min=100, mean=120,
                              p50=100, p95=300, p99=300, max=300))
        self.assertEqual(timing["simulated_age_upper_bound_ms"]["mean"], 125)
        self.assertEqual(timing["simulated_post_window_sealing_delay_ms"]["mean"], 5)
        self.assertEqual(timing["simulated_post_window_sealing_delay_ms"]["p95"], 50)

    def test_batching_same_cells_into_more_releases_is_invariant(self):
        grouped = dict(releases=[release([cell(2), cell(8)], end=500, sealed=650)])
        separated = dict(releases=[release([cell(2)], end=500, sealed=650),
                                  release([cell(8)], end=500, sealed=650)])
        self.assertEqual(summarize(grouped), summarize(separated))

    def test_zero_contributions_do_not_skew_percentiles(self):
        result = dict(releases=[release([cell(0)], end=900, sealed=10000),
                                release([cell(3)], end=200, sealed=200)])
        timing = summarize(result)["public_release_timing"]
        self.assertEqual(timing["zero_weight_cells"], 1)
        self.assertEqual(timing["window_duration_ms"]["max"], 200)
        self.assertEqual(timing["simulated_post_window_sealing_delay_ms"]["max"], 0)

    def test_empty_and_all_zero_output_have_no_claimed_timing(self):
        for result in (dict(releases=[]), dict(releases=[release([cell(0)])])):
            timing = summarize(result)["public_release_timing"]
            self.assertEqual(timing["observation_contribution_weight"], 0)
            for key in ("window_duration_ms", "simulated_age_upper_bound_ms",
                        "simulated_post_window_sealing_delay_ms"):
                self.assertEqual(timing[key]["total_weight"], 0)
                for statistic in ("min", "mean", "p50", "p95", "p99", "max"):
                    self.assertIsNone(timing[key][statistic])

    def test_quantile_at_exact_cumulative_boundary_uses_lower_value(self):
        result = dict(releases=[release([cell(1)]), release([cell(1)], end=200, sealed=200)])
        self.assertEqual(summarize(result)["public_release_timing"]["window_duration_ms"]["p50"], 100)

    def test_private_reasons_do_not_change_public_timing(self):
        result = dict(releases=[release([cell(1)])])
        before = summarize(result)["public_release_timing"]
        result["windows"] = [dict(input_observation_contributions=6,
            completion_reason="retired_support_overlap", cells=[
                dict(selected=True, observation_contributions=1, reason="selected"),
                dict(selected=False, observation_contributions=5, reason="deadline"),
                dict(selected=False, observation_contributions=0, reason="empty")])]
        summary = summarize(result)
        self.assertEqual(before, summary["public_release_timing"])
        private = summary["private_coordination_diagnostics"]
        self.assertEqual(private["categories"]["suppressed"], dict(cells=1, observation_contributions=5))
        self.assertEqual(private["categories"]["zero_contribution_retirement"],
                         dict(cells=1, observation_contributions=0))
        self.assertEqual(private["completion_reasons"],
                         [dict(reason="retired_support_overlap", windows=1, observation_contributions=6)])
        self.assertFalse(private["publication_blocking"]["available"])
        self.assertIsNone(private["publication_blocking"]["actual_public_overlap_candidates"])
        self.assertIsNone(private["publication_blocking"]["private_retirement_overlap_candidates"])

    def test_absent_private_diagnostics_are_unavailable_not_empty(self):
        result = summarize(dict(releases=[]))["private_coordination_diagnostics"]
        self.assertFalse(result["available"])
        self.assertNotIn("categories", result)

    def test_invalid_counts_and_time_are_rejected(self):
        for invalid in (-1, True, 1.5, None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    summarize(dict(releases=[release([cell(invalid)])]))
        with self.assertRaises(ValueError):
            summarize(dict(releases=[release([cell(1)], start=100, end=100)]))
        with self.assertRaises(ValueError):
            summarize(dict(releases=[release([cell(1)], sealed=99)]))

    def test_summarization_does_not_mutate_source(self):
        result = dict(releases=[release([cell(1)])], windows=[])
        before = deepcopy(result)
        summarize(result)
        self.assertEqual(before, result)


if __name__ == "__main__":
    unittest.main()
