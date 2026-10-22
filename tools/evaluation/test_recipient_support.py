"""Hand-computed support partitions and distinct exact/estimated recipient modes."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import recipient_support as diagnostic
import scoped_semantic_queries as exact
from test_scoped_semantic_queries import configuration, source, cell, release, q


class RecipientSupportTests(unittest.TestCase):
    def evaluate(self, releases=(), replay=None, **kwargs):
        options = dict(target_cells=[{'cell_id': 12, 'depth': 1}],
                       categories=['road_user'], lags_ms=(0, 400), uniform_estimate=True)
        options.update(kwargs)
        return diagnostic.evaluate(source() if replay is None else replay, configuration(),
                                   list(releases), **options)

    def support(self, result, **kwargs):
        return q(result, **kwargs)['recipient_support']

    def estimate(self, result, **kwargs):
        return q(result, **kwargs)['uniform_estimate']

    def test_complete_parent_exact_and_estimate_agree(self):
        result = self.evaluate([release()])
        support = self.support(result)
        self.assertEqual(support['required_leaf_samples'], 12)  # Four leaves x three samples.
        self.assertEqual(support['leaf_samples_by_mask']['0'], 12)
        self.assertEqual(support['unpublished_leaf_samples_at_eof'], 0)
        self.assertEqual(support['signature_mask'], 0)
        self.assertEqual(self.estimate(result)['estimated_observation_contributions'], 12)
        self.assertEqual(self.estimate(result)['estimated_mean_sample_occupancy'], 4)
        self.assertEqual(self.estimate(result)['absolute_error'], 0)
        self.assertTrue(q(result)['answered'])

    def test_spatial_crossing_keeps_exact_unknown_but_estimates_uniformly(self):
        result = self.evaluate([release()], target_cells=[{'cell_id': 48, 'depth': 2}])
        support = self.support(result, identity=48)
        self.assertEqual(support['required_leaf_samples'], 3)
        self.assertEqual(support['leaf_samples_by_mask']['1'], 3)
        self.assertEqual(support['signature_mask'], 1)
        self.assertFalse(q(result, identity=48)['answered'])
        self.assertEqual(self.estimate(result, identity=48)['estimated_observation_contributions'], 3)

    def test_temporal_crossing_uses_sample_fraction_not_wall_duration(self):
        public = release(0, 800, cells=[cell(12, [('road_user', 35, 4)])])
        result = self.evaluate([public])
        self.assertEqual(self.support(result)['leaf_samples_by_mask']['10'], 12)
        self.assertEqual(self.support(result, lag=400)['leaf_samples_by_mask']['2'], 12)
        self.assertFalse(q(result, lag=400)['answered'])
        # [0,800) has seven samples, first query three: 35 * 3/7 = 15.
        estimate = self.estimate(result, lag=400)
        self.assertEqual(estimate['estimated_observation_contributions'], 15)
        self.assertEqual(estimate['absolute_error'], 3)
        self.assertEqual(estimate['mean_sample_occupancy_absolute_error'], 1)
        self.assertEqual(self.estimate(result, start=400)['estimated_observation_contributions'], 20)

    def test_joint_spatial_temporal_semantic_and_late_mask(self):
        result = self.evaluate([release(0, 800, cells=[cell(12, [('road_user', 28, 4)])])],
            target_cells=[{'cell_id': 48, 'depth': 2}], categories=['cyclist'])
        support = self.support(result, identity=48, category='cyclist')
        self.assertEqual(support['leaf_samples_by_mask']['15'], 3)
        self.assertEqual(support['signature_mask'], 15)
        self.assertEqual(support['visible_leaf_samples_at_deadline'], 0)
        self.assertFalse(self.estimate(result, identity=48, category='cyclist', lag=400)['answered'])

    def test_joint_spatial_temporal_uniform_fraction(self):
        public = release(0, 800, cells=[cell(12, [('road_user', 56, 4)])])
        result = self.evaluate([public], target_cells=[{'cell_id': 48, 'depth': 2}])
        # 56 * 1/4 leaves * 3/7 samples = 6, reference is 3.
        self.assertEqual(self.estimate(result, identity=48, lag=400)['estimated_observation_contributions'], 6)
        self.assertEqual(self.estimate(result, identity=48, lag=400)['absolute_error'], 3)
        self.assertEqual(self.support(result, identity=48, lag=400)['signature_mask'], 3)

    def test_late_record_is_distinct_from_unpublished(self):
        result = self.evaluate([release(sealed=450)], lags_ms=(0, 50))
        late = self.support(result)
        self.assertEqual(late['leaf_samples_by_mask']['8'], 12)
        self.assertEqual(late['unpublished_leaf_samples_at_eof'], 0)
        self.assertEqual(late['signature_mask'], 8)
        self.assertFalse(self.estimate(result)['answered'])
        self.assertTrue(self.estimate(result, lag=50)['answered'])
        self.assertEqual(self.support(result, lag=50)['signature_mask'], 0)

    def test_late_and_unpublished_have_disjoint_volumes(self):
        result = self.evaluate([release(sealed=500, cells=[cell(48, [('road_user', 3, 1)])])])
        support = self.support(result)
        self.assertEqual(support['leaf_samples_by_mask']['8'], 3)
        self.assertEqual(support['unpublished_leaf_samples_at_eof'], 9)
        self.assertEqual(support['signature_mask'], 24)
        self.assertFalse(self.estimate(result, lag=400)['answered'])
        self.assertEqual(self.support(result, lag=400)['signature_mask'], 16)

    def test_different_support_restrictions_union_in_one_query_signature(self):
        first = release(cells=[cell(48, [('cyclist', 3, 1)])])
        second = release(0, 800, cells=[cell(49, [('adult_cyclist', 7, 1)])])
        result = self.evaluate([first, second], categories=['adult_cyclist'])
        support = self.support(result, category='adult_cyclist')
        self.assertEqual(support['leaf_samples_by_mask']['4'], 3)
        self.assertEqual(support['leaf_samples_by_mask']['10'], 3)
        self.assertEqual(support['unpublished_leaf_samples_at_eof'], 6)
        self.assertEqual(support['signature_mask'], 30)  # 4 | 2 | 8 | 16.

    def test_semantic_ambiguity_is_never_imputed(self):
        result = self.evaluate([release(cells=[cell(12, [('cyclist', 12, 4)])])],
                               categories=['cyclist', 'adult_cyclist'])
        self.assertTrue(q(result, category='cyclist')['answered'])
        support = self.support(result, category='adult_cyclist')
        self.assertEqual(support['leaf_samples_by_mask']['4'], 12)
        self.assertFalse(self.estimate(result, category='adult_cyclist')['answered'])
        self.assertIsNone(self.estimate(result, category='adult_cyclist')['estimated_observation_contributions'])

    def test_disjoint_category_certifies_public_zero(self):
        result = self.evaluate([release(cells=[cell(12, [('pedestrian', 12, 4)])])], categories=['cyclist'])
        self.assertEqual(q(result, category='cyclist')['prediction'], 0)
        self.assertEqual(self.support(result, category='cyclist')['signature_mask'], 0)
        self.assertEqual(self.estimate(result, category='cyclist')['estimated_observation_contributions'], 0)
        self.assertEqual(self.estimate(result, category='cyclist')['absolute_error'], 6)

    def test_coarse_disjoint_zero_remains_conservative_exact_unknown(self):
        result = self.evaluate([release(cells=[cell(12, [('pedestrian', 12, 4)])])],
            categories=['cyclist'], target_cells=[{'cell_id': 48, 'depth': 2}])
        row = q(result, identity=48, category='cyclist')
        self.assertFalse(row['answered'])  # Legacy decoder is deliberately not maximal zero inference.
        self.assertEqual(row['recipient_support']['signature_mask'], 1)
        self.assertEqual(row['uniform_estimate']['estimated_observation_contributions'], 0)

    def test_no_public_records_does_not_mean_empty(self):
        result = self.evaluate()
        support = self.support(result)
        self.assertEqual(support['required_leaf_samples'], 12)
        self.assertEqual(support['unpublished_leaf_samples_at_eof'], 12)
        self.assertEqual(support['signature_mask'], 16)
        self.assertFalse(self.estimate(result)['answered'])
        self.assertIsNone(self.estimate(result)['estimated_observation_contributions'])

    def test_partial_visible_support_never_becomes_estimate(self):
        result = self.evaluate([release(cells=[cell(48, [('road_user', 3, 1)])])])
        self.assertEqual(self.support(result)['exact_usable_leaf_samples_at_deadline'], 3)
        self.assertEqual(self.estimate(result)['covered_leaf_samples_at_deadline'], 3)
        self.assertFalse(self.estimate(result)['answered'])

    def test_three_short_records_cover_initial_samples(self):
        releases = [release(t, t + 100, cells=[cell(12, [('road_user', 4, 4)])]) for t in (100, 200, 300)]
        result = self.evaluate(releases)
        self.assertEqual(self.support(result)['required_leaf_samples'], 12)
        self.assertEqual(self.support(result)['signature_mask'], 0)
        self.assertEqual(self.estimate(result)['estimated_observation_contributions'], 12)

    def test_unavailable_reference_cannot_change_public_partition_or_estimate(self):
        a = self.evaluate([release()])
        missing = source()
        for batch in missing['batches']:
            batch['observations'] = []
            batch['status'] = 'unavailable'
        b = self.evaluate([release()], replay=missing)
        for lag in ('0', '400'):
            for left, right in zip(a['evaluations_by_lag_ms'][lag]['queries'], b['evaluations_by_lag_ms'][lag]['queries']):
                self.assertEqual(left['recipient_support'], right['recipient_support'])
                for key in ('answered', 'estimated_observation_contributions', 'estimated_mean_sample_occupancy', 'covered_leaf_samples_at_deadline'):
                    self.assertEqual(left['uniform_estimate'][key], right['uniform_estimate'][key])
        self.assertIsNone(self.estimate(b)['absolute_error'])
        summary = b['evaluations_by_lag_ms']['0']['recipient_support_summary']['interior']['uniform_estimate']
        self.assertEqual(summary['receiver_answered_query_count'], 1)
        self.assertEqual(summary['answered_query_count'], 0)

    def test_changed_reference_affects_only_score_and_strata(self):
        replay = source()
        for batch in replay['batches']:
            batch['observations'] = []
        result = self.evaluate([release()], replay=replay)
        self.assertEqual(self.support(result)['signature_mask'], 0)
        self.assertEqual(self.estimate(result)['estimated_observation_contributions'], 12)
        self.assertEqual(self.estimate(result)['absolute_error'], 12)

    def test_eof_and_censored_deadlines_are_explicit(self):
        result = self.evaluate([release(1200, 1600)], lags_ms=(0, 400))
        at_eof = q(result, start=1200)
        self.assertTrue(at_eof['deadline_at_eof'])
        self.assertEqual(at_eof['cohort'], 'boundary')
        self.assertTrue(at_eof['uniform_estimate']['answered'])
        censored = q(result, start=1200, lag=400)
        self.assertTrue(censored['recipient_support']['deadline_censored'])
        self.assertIsNone(censored['recipient_support']['signature_mask'])
        self.assertIsNone(censored['recipient_support']['visible_leaf_samples_at_deadline'])
        self.assertFalse(censored['uniform_estimate']['answered'])
        summary = result['evaluations_by_lag_ms']['400']['recipient_support_summary']['boundary']
        self.assertEqual(summary['query_count'], 2)
        self.assertEqual(summary['censored_query_count'], 1)
        self.assertEqual(sum(summary['query_counts_by_signature_mask'].values()), 1)

    def test_unsampled_initial_query_separate_from_signature_zero(self):
        result = self.evaluate(window_ms=100, lags_ms=(0,))
        row = q(result)
        self.assertEqual(row['scheduled_sample_count'], 0)
        self.assertIsNone(row['recipient_support']['signature_mask'])
        self.assertTrue(row['recipient_support']['no_scheduled_samples'])
        self.assertFalse(row['uniform_estimate']['answered'])
        summary = result['evaluations_by_lag_ms']['0']['recipient_support_summary']['interior']
        self.assertEqual(summary['no_scheduled_samples_query_count'], 1)
        self.assertEqual(summary['signature_query_count'], 14)
        self.assertEqual(summary['required_leaf_samples'], 56)

    def test_exact_fields_and_compact_summary_are_byte_structure_unchanged(self):
        releases = [release(0, 800)]
        options = dict(target_cells=[{'cell_id': 48, 'depth': 2}], categories=['road_user', 'cyclist'], lags_ms=(0, 400))
        old = exact.evaluate(source(), configuration(), releases, **options)
        new = diagnostic.evaluate(source(), configuration(), releases, uniform_estimate=True, **options)
        self.assertEqual(exact.compact(old), exact.compact({**new, 'schema': exact.SCHEMA}))
        for lag in ('0', '400'):
            for previous, current in zip(old['evaluations_by_lag_ms'][lag]['queries'], new['evaluations_by_lag_ms'][lag]['queries']):
                self.assertEqual(previous, {key: value for key, value in current.items() if key not in ('recipient_support', 'uniform_estimate')})

    def test_signature_and_volume_summaries_partition_denominators(self):
        result = self.evaluate([release(sealed=500, cells=[cell(48, [('road_user', 3, 1)])])], categories=['road_user', 'cyclist'])
        for value in result['evaluations_by_lag_ms'].values():
            for summary in value['recipient_support_summary'].values():
                self.assertEqual(sum(summary['query_counts_by_signature_mask'].values()), summary['signature_query_count'])
                self.assertEqual(sum(summary['leaf_samples_by_mask'].values()) + summary['unpublished_leaf_samples_at_eof'], summary['required_leaf_samples'])
                self.assertEqual(sum(row['required_leaf_samples'] for row in summary['by_category'].values()), summary['required_leaf_samples'])

    def test_root_estimate_matches_existing_online_occupancy_on_same_public_means(self):
        import online_occupancy
        replay = source()
        public = release(0, 800, cells=[cell(12, [('road_user', 35, 4)])])
        public['cells'][0]['mean_sample_occupancy'] = 5  # 35 contributions / seven samples.
        result = self.evaluate([public], target_cells=[{'cell_id': 48, 'depth': 2}])
        scalar = online_occupancy.evaluate(replay, dict(schema='ump.replay-result.v1',
            source={key: replay[key] for key in ('run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms')},
            releases=[public]), reference_cell_m=2, reference_window_ms=400, deadline_lags_ms=(0, 400))
        for lag in ('0', '400'):
            previous = next(row for row in scalar['evaluations_by_lag_ms'][lag]['queries']
                            if row['x'] == 0 and row['y'] == 0 and row['start_ms'] == 0)
            estimate = self.estimate(result, identity=48, lag=int(lag))
            self.assertEqual(previous['answered'], estimate['answered'])
            self.assertEqual(previous['prediction'], estimate['estimated_mean_sample_occupancy'])
            self.assertEqual(previous['absolute_error'], estimate['mean_sample_occupancy_absolute_error'])
        self.assertEqual(self.estimate(result, identity=48, lag=400)['estimated_mean_sample_occupancy'], 1.25)

    def test_depth_14_support_stays_sparse(self):
        replay = source()
        replay['coverage']['leaf_depth'] = 14
        for batch in replay['batches']:
            batch['observations'] = []
        finest_id = 3 << 28
        result = self.evaluate([release(cells=[cell(3)], owner=3)], replay=replay,
            target_cells=[{'cell_id': 3, 'depth': 0}, {'cell_id': finest_id, 'depth': 14}])
        parent = self.support(result, identity=3)
        self.assertEqual(parent['required_leaf_samples'], (1 << 28) * 3)
        self.assertEqual(parent['leaf_samples_by_mask']['0'], (1 << 28) * 3)
        finest = self.support(result, identity=finest_id)
        self.assertEqual(finest['required_leaf_samples'], 3)
        self.assertEqual(finest['leaf_samples_by_mask']['1'], 3)
        self.assertEqual(self.estimate(result, identity=finest_id)['estimated_observation_contributions'], 12 / (1 << 28))
        summary = result['evaluations_by_lag_ms']['0']['recipient_support_summary']['interior']['uniform_estimate']
        self.assertEqual(summary['receiver_estimated_only_answered_query_count'], 1)
        self.assertEqual(summary['scored_estimated_only_answered_query_count'], 1)

    def test_exact_subset_invariant_is_enforced_at_runtime(self):
        previous = exact.evaluate(source(), configuration(), [release()],
            target_cells=[{'cell_id': 12, 'depth': 1}], categories=['road_user'], lags_ms=(0, 400))
        q(previous)['prediction'] = 999
        with patch.object(exact, 'evaluate', return_value=previous):
            with self.assertRaisesRegex(ValueError, 'preserve every conservative exact answer'):
                self.evaluate([release()])

    def test_optional_estimator_disabled_by_default(self):
        result = self.evaluate([release()], uniform_estimate=False)
        self.assertNotIn('uniform_estimate', q(result))
        self.assertNotIn('uniform_estimate', result['evaluations_by_lag_ms']['0']['recipient_support_summary']['interior'])
        self.assertFalse(result['recipient_contract']['uniform_estimate_enabled'])

    def test_compact_removes_rows_without_mutating_summary(self):
        full = self.evaluate([release()])
        result = diagnostic.compact(full)
        self.assertNotIn('queries', result['evaluations_by_lag_ms']['0'])
        result['query_definition']['categories'].append('invented')
        self.assertNotIn('invented', full['query_definition']['categories'])
        with self.assertRaises(ValueError):
            diagnostic.compact({'schema': exact.SCHEMA})

    def test_pair_estimates_and_exact_results_separately(self):
        a = self.evaluate([release()])
        b = self.evaluate([release(cells=[cell(12, [('road_user', 24, 4)])])])
        result = diagnostic.paired_summary(a, b)
        pair = result['evaluations_by_lag_ms']['0']['summary']['interior']
        self.assertEqual(pair['both_answered_query_count'], 1)
        self.assertEqual(pair['uniform_estimate']['both_answered_query_count'], 1)
        self.assertEqual(pair['uniform_estimate']['intersection_a_mae'], 0)
        self.assertEqual(pair['uniform_estimate']['intersection_b_mae'], 12)
        self.assertEqual(pair['uniform_estimate']['intersection_b_mean_sample_occupancy_mae'], 4)
        self.assertEqual(pair['uniform_estimate']['by_category']['road_user']['scored_intersection_query_count'], 1)
        self.assertEqual(pair['uniform_estimate']['positive']['both_answered_query_count'], 1)

    def test_pair_rejects_different_modes_and_references(self):
        a = self.evaluate([release()])
        with self.assertRaisesRegex(ValueError, 'same recipient contract'):
            diagnostic.paired_summary(a, self.evaluate([release()], uniform_estimate=False))
        replay = source()
        replay['batches'][0]['observations'] = []
        with self.assertRaisesRegex(ValueError, 'reference counts disagree'):
            diagnostic.paired_summary(a, self.evaluate([release()], replay=replay))

    def test_pair_unanswered_intersection_has_no_mae(self):
        pair = diagnostic.paired_summary(self.evaluate(), self.evaluate())
        summary = pair['evaluations_by_lag_ms']['0']['summary']['interior']['uniform_estimate']
        self.assertEqual(summary['both_answered_query_count'], 0)
        self.assertIsNone(summary['intersection_a_mae'])

    def test_boolean_mode_required(self):
        with self.assertRaisesRegex(ValueError, 'boolean'):
            self.evaluate(uniform_estimate=1)

    def test_existing_query_budget_is_enforced(self):
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.evaluate(max_queries=1)

    def test_existing_candidate_budget_is_enforced(self):
        with patch.object(exact, 'MAX_CANDIDATE_CHECKS', 1):
            with self.assertRaisesRegex(ValueError, 'comparison budget'):
                self.evaluate([release()])

    def test_public_overlap_is_rejected_before_partitioning(self):
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.evaluate([release(), release(identity='other')])

    def test_malformed_public_geometry_is_rejected(self):
        public = release()
        public['cells'][0]['width'] = 5
        with self.assertRaisesRegex(ValueError, 'geometry'):
            self.evaluate([public])

    def test_future_after_eof_release_is_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate([release(sealed=1601)])

    def test_private_diagnostics_not_read(self):
        replay = source()
        replay['windows'] = [{'secret': object()}]
        result = self.evaluate([release()], replay=replay)
        self.assertEqual(self.support(result)['signature_mask'], 0)


if __name__ == '__main__':
    unittest.main()
