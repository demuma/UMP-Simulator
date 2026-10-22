"""Independent expected-answer tests for asynchronous semantic query utility.

The literal fixtures deliberately contain public/reference discrepancies.  The
recipient must answer from complete public tiles without correcting them using
private source data, clipping whole aggregates, or summing distinct people.
"""
from copy import deepcopy
import math
import unittest

from scoped_semantic_queries import compact, evaluate, paired_summary


LOSSES = {'road_user': 1, 'pedestrian': .5, 'adult_pedestrian': 0,
          'child_pedestrian': 0, 'cyclist': .5, 'adult_cyclist': 0,
          'child_cyclist': 0, 'scooter': .5, 'scooter_rider': 0}
GEOMETRY = {
    3: (0, 0, 8, 0), 12: (0, 0, 4, 1), 13: (4, 0, 4, 1),
    48: (0, 0, 2, 2), 49: (2, 0, 2, 2),
    50: (0, 2, 2, 2), 51: (2, 2, 2, 2), 52: (4, 0, 2, 2),
}


def configuration():
    return {'semantic_taxonomy': {'id': 'query-test', 'version': '1', 'nodes': [
        {'id': 'road_user', 'loss': 1},
        {'id': 'pedestrian', 'parent': 'road_user', 'loss': .5},
        {'id': 'adult_pedestrian', 'parent': 'pedestrian', 'loss': 0,
         'input_types': ['Adult Pedestrian']},
        {'id': 'child_pedestrian', 'parent': 'pedestrian', 'loss': 0,
         'input_types': ['Child Pedestrian']},
        {'id': 'cyclist', 'parent': 'road_user', 'loss': .5},
        {'id': 'adult_cyclist', 'parent': 'cyclist', 'loss': 0,
         'input_types': ['Adult Cyclist', 'Cyclist Adult Alias']},
        {'id': 'child_cyclist', 'parent': 'cyclist', 'loss': 0,
         'input_types': ['Child Cyclist']},
        {'id': 'scooter', 'parent': 'road_user', 'loss': .5},
        {'id': 'scooter_rider', 'parent': 'scooter', 'loss': 0,
         'input_types': ['Scooter Rider']},
    ]}}


def source(horizon=1600):
    observations = [
        {'id': 'a', 'type': 'Adult Cyclist', 'cell_id': 48, 'x': 1, 'y': 1},
        {'id': 'b', 'type': 'Child Cyclist', 'cell_id': 49, 'x': 3, 'y': 1},
        {'id': 'c', 'type': 'Adult Pedestrian', 'cell_id': 50, 'x': 1, 'y': 3},
        {'id': 'd', 'type': 'Child Pedestrian', 'cell_id': 51, 'x': 3, 'y': 3},
    ]
    return {'schema': 'ump.observation-replay.v1', 'run_id': 'scoped-query-test',
            'sensor_id': 'agbs', 'coverage': {'x': 0, 'y': 0, 'width': 8,
            'height': 8, 'leaf_depth': 2}, 'sampling_period_ms': 100,
            'end_ms': horizon, 'batches': [
                {'sequence': index, 'observed_at_ms': time, 'status': 'measured',
                 'observations': deepcopy(observations)}
                for index, time in enumerate(range(100, horizon, 100), 1)]}


def scope(identity):
    x, y, side, depth = GEOMETRY[identity]
    return {'cell_id': identity, 'depth': depth, 'x': x, 'y': y,
            'width': side, 'height': side}


def cell(identity=12, bins=None):
    if bins is None:
        bins = [('adult_cyclist', 3, 1), ('child_cyclist', 3, 1),
                ('adult_pedestrian', 3, 1), ('child_pedestrian', 3, 1)]
    total = sum(count for _, count, _ in bins)
    return {**scope(identity), 'observation_contributions': total,
            'distinct_road_users': sum(distinct for _, _, distinct in bins),
            'mean_sample_occupancy': 4, 'effective_policy_id': 'test/effective',
            'semantic': {'schema': 'ump.semantic-release.v1',
                'taxonomy_id': 'query-test', 'taxonomy_version': '1',
                'min_category_distinct_contributors': min(n for _, _, n in bins),
                'semantic_max_loss': max(LOSSES[c] for c, _, _ in bins),
                'semantic_mean_loss': sum(LOSSES[c] * n for c, n, _ in bins) / total,
                'categories': [{'category_id': c, 'observation_contributions': n,
                    'distinct_contributors': distinct} for c, n, distinct in bins]}}


def release(start=0, end=400, sealed=None, cells=None, owner=12, identity=None):
    result = {'release_id': identity or f'release-{owner}-{start}-{end}',
              'start_ms': start, 'end_ms': end, 'sealed_at_ms': end if sealed is None else sealed,
              'model': 'private_final_snapshot', 'policy_id': 'query-policy',
              'policy_version': '1', 'cells': [cell()] if cells is None else cells}
    if owner is not None:
        result['coordination_cell'] = scope(owner)
    return result


def q(result, *, start=0, identity=12, category='road_user', lag=0):
    return next(row for row in result['evaluations_by_lag_ms'][str(lag)]['queries']
                if row['start_ms'] == start and row['target_cell_id'] == identity
                and row['category_id'] == category)


class ScopedSemanticQueryTests(unittest.TestCase):
    def evaluate(self, releases=(), replay=None, config=None, **kwargs):
        options = {'target_cells': [{'cell_id': 12, 'depth': 1}],
                   'categories': ['road_user', 'cyclist', 'adult_cyclist']}
        options.update(kwargs)
        return evaluate(source() if replay is None else replay,
                        configuration() if config is None else config,
                        list(releases), **options)

    def test_parent_counts_observations_and_categories(self):
        result = self.evaluate([release()])
        self.assertEqual(result['schema'], 'ump.scoped-semantic-queries.v1')
        self.assertEqual(q(result)['prediction'], 12)
        self.assertEqual(q(result, category='cyclist')['prediction'], 6)
        self.assertEqual(q(result, category='adult_cyclist')['prediction'], 3)
        self.assertEqual(q(result)['reference_observation_contributions'], 12)
        self.assertEqual(q(result)['absolute_error'], 0)
        self.assertEqual(q(result)['scheduled_sample_count'], 3)

    def test_disjoint_local_owners_with_different_windows_tile_one_query(self):
        releases = [
            release(0, 200, cells=[cell(48, [('adult_cyclist', 1, 1)])], owner=48),
            release(200, 300, cells=[cell(48, [('adult_cyclist', 1, 1)])], owner=48),
            release(0, 300, cells=[cell(50, [('adult_pedestrian', 2, 1)])], owner=50),
            release(300, 400, cells=[cell(48, [('adult_cyclist', 1, 1)])], owner=48),
            release(0, 400, cells=[cell(49, [('child_cyclist', 3, 1)])], owner=49),
            release(300, 400, cells=[cell(50, [('adult_pedestrian', 1, 1)])], owner=50),
            release(0, 400, cells=[cell(51, [('child_pedestrian', 3, 1)])], owner=51),
        ]
        result = self.evaluate(releases)
        self.assertTrue(q(result)['answered'])
        self.assertEqual(q(result)['prediction'], 12)
        self.assertEqual(q(result, category='cyclist')['prediction'], 6)
        self.assertEqual(q(result)['absolute_error'], 0)

    def test_parent_then_four_children_tile_time_without_summing_distinct_people(self):
        first = release()
        second = release(400, 800, cells=[cell(i, [(category, 4, 1)]) for i, category in
            [(48, 'adult_cyclist'), (49, 'child_cyclist'),
             (50, 'adult_pedestrian'), (51, 'child_pedestrian')]])
        result = self.evaluate([first, second], window_ms=800)
        self.assertEqual(q(result)['prediction'], 28)
        self.assertEqual(q(result)['reference_observation_contributions'], 28)
        self.assertEqual(q(result)['absolute_error'], 0)
        self.assertEqual(q(result, category='adult_cyclist')['prediction'], 7)

    def test_three_short_intervals_cover_samples_without_inventing_t0(self):
        releases = [release(t, t + 100, cells=[cell(12, [('road_user', 4, 4)])])
                    for t in (100, 200, 300)]
        result = self.evaluate(releases)
        self.assertEqual(q(result)['prediction'], 12)
        self.assertEqual(q(result)['scheduled_sample_count'], 3)

    def test_missing_spatial_tile_is_unknown_even_if_reference_is_empty(self):
        replay = source()
        for batch in replay['batches']:
            batch['observations'] = [o for o in batch['observations'] if o['cell_id'] != 51]
        public = release(cells=[cell(i, [('road_user', 3, 1)]) for i in (48, 49, 50)])
        result = self.evaluate([public], replay=replay)
        self.assertFalse(q(result)['answered'])
        self.assertIsNone(q(result)['prediction'])
        self.assertEqual(q(result)['reference_observation_contributions'], 9)

    def test_missing_time_tile_is_unknown(self):
        result = self.evaluate([release()], window_ms=800)
        self.assertFalse(q(result)['answered'])
        self.assertIsNone(q(result)['prediction'])

    def test_no_spatial_clipping_of_parent(self):
        result = self.evaluate([release()], target_cells=[{'cell_id': 48, 'depth': 2}])
        row = q(result, identity=48)
        self.assertFalse(row['answered'])
        self.assertIn('crossing_public_support', row['unknown_reasons'])

    def test_no_time_clipping_of_long_interval(self):
        public = release(0, 800, cells=[cell(12, [('road_user', 28, 4)])])
        result = self.evaluate([public])
        self.assertFalse(q(result, lag=400)['answered'])
        self.assertIn('crossing_public_support', q(result, lag=400)['unknown_reasons'])
        exact = self.evaluate([public], window_ms=800)
        self.assertEqual(q(exact)['prediction'], 28)

    def test_unary_ancestor_is_exact_semantically(self):
        public = release(cells=[cell(12, [('scooter', 12, 4)])])
        result = self.evaluate([public], categories=['scooter_rider', 'scooter', 'road_user'])
        for category in ('scooter_rider', 'scooter', 'road_user'):
            self.assertEqual(q(result, category=category)['prediction'], 12)

    def test_straddling_semantic_ancestor_stays_unknown(self):
        result = self.evaluate([release(cells=[cell(12, [('road_user', 12, 4)])])])
        self.assertEqual(q(result)['prediction'], 12)
        self.assertFalse(q(result, category='cyclist')['answered'])
        self.assertIn('semantic_generalization', q(result, category='cyclist')['unknown_reasons'])

    def test_disjoint_semantic_partition_certifies_zero(self):
        result = self.evaluate([release(cells=[cell(12, [('pedestrian', 12, 4)])])])
        row = q(result, category='cyclist')
        self.assertTrue(row['answered'])
        self.assertEqual(row['prediction'], 0)
        self.assertEqual(row['reference_observation_contributions'], 6)
        self.assertEqual(row['absolute_error'], 6)

    def test_predictions_ignore_changed_private_reference(self):
        replay = source()
        for batch in replay['batches']:
            batch['observations'] = []
        a, b = self.evaluate([release()]), self.evaluate([release()], replay=replay)
        for lag in ('0', '400'):
            ra = a['evaluations_by_lag_ms'][lag]['queries']
            rb = b['evaluations_by_lag_ms'][lag]['queries']
            self.assertEqual([(r['answered'], r['prediction']) for r in ra],
                             [(r['answered'], r['prediction']) for r in rb])
        self.assertEqual(q(b)['absolute_error'], 12)

    def test_missing_and_unavailable_source_do_not_change_public_answer(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                replay = source()
                if missing:
                    replay['batches'].pop(1)
                else:
                    replay['batches'][1].update(status='unavailable', observations=[])
                row = q(self.evaluate([release()], replay=replay))
                self.assertEqual(row['prediction'], 12)
                self.assertFalse(row['reference_available'])
                self.assertIsNone(row['reference_observation_contributions'])
                self.assertIsNone(row['absolute_error'])

    def test_sealed_exactly_at_deadline_is_available_but_one_ms_later_is_not(self):
        exact = self.evaluate([release(sealed=800)])
        late = self.evaluate([release(sealed=801)])
        self.assertFalse(q(exact)['answered'])
        self.assertTrue(q(exact, lag=400)['answered'])
        self.assertFalse(q(late, lag=400)['answered'])

    def test_fixed_interior_cohort_does_not_change_with_lag(self):
        result = self.evaluate([], categories=['road_user'])
        a, b = (result['evaluations_by_lag_ms'][str(lag)] for lag in (0, 400))
        self.assertEqual([r['cohort'] for r in a['queries']],
                         [r['cohort'] for r in b['queries']])
        for evaluation in (a, b):
            interior = evaluation['summary']['interior']
            self.assertEqual(interior['query_count'], 2)
            self.assertEqual(interior['answered_query_count'], 0)
            self.assertEqual(interior['query_coverage'], 0)
            self.assertIsNone(interior['answered_only_mae'])
        self.assertEqual(b['summary']['boundary']['query_count'], 2)
        self.assertEqual(b['summary']['boundary']['observed_query_count'], 1)
        self.assertEqual(b['summary']['boundary']['censored_query_count'], 1)

    def test_eof_observed_but_censored_later_deadline_unknown(self):
        result = self.evaluate([release(1200, 1600, cells=[cell(12, [('road_user', 16, 4)])])])
        eof = q(result, start=1200)
        self.assertTrue(eof['answered'])
        self.assertTrue(eof['deadline_at_eof'])
        self.assertEqual(eof['cohort'], 'boundary')
        later = q(result, start=1200, lag=400)
        self.assertFalse(later['deadline_observed'])
        self.assertFalse(later['answered'])
        self.assertIsNone(later['prediction'])

    def test_trailing_partial_query_is_not_fabricated(self):
        result = self.evaluate([], replay=source(1700), categories=['road_user'])
        for evaluation in result['evaluations_by_lag_ms'].values():
            self.assertEqual([r['start_ms'] for r in evaluation['queries']], [0, 400, 800, 1200])

    def test_nonzero_origin_is_supported(self):
        replay, public = source(), release()
        replay['coverage'].update(x=-10, y=25)
        for batch in replay['batches']:
            for observation in batch['observations']:
                observation['x'] -= 10
                observation['y'] += 25
        for row in (public['coordination_cell'], public['cells'][0]):
            row['x'] -= 10
            row['y'] += 25
        self.assertEqual(q(self.evaluate([public], replay=replay))['prediction'], 12)

    def test_deep_grid_root_query_does_not_require_leaf_materialization(self):
        for depth in (6, 14):
            with self.subTest(depth=depth):
                replay = source()
                replay['coverage']['leaf_depth'] = depth
                for batch in replay['batches']:
                    batch['observations'] = []
                public = release(cells=[cell(3, [('road_user', 12, 4)])], owner=3)
                row = q(self.evaluate([public], replay=replay,
                    target_cells=[{'cell_id': 3, 'depth': 0}]), identity=3)
                self.assertEqual(row['prediction'], 12)
                self.assertEqual(row['reference_observation_contributions'], 0)

    def test_canonical_leaf_alias_changes_are_supported(self):
        replay = source()
        replay['batches'][1]['observations'][0]['type'] = 'Cyclist Adult Alias'
        self.assertEqual(q(self.evaluate([release()], replay=replay))['absolute_error'], 0)

    def test_actual_canonical_type_changes_are_rejected(self):
        replay = source()
        replay['batches'][1]['observations'][0]['type'] = 'Child Cyclist'
        with self.assertRaises(ValueError):
            self.evaluate(replay=replay)

    def test_duplicate_public_support_is_rejected(self):
        public = release(identity='one')
        duplicate = release(identity='two')
        with self.assertRaises(ValueError):
            self.evaluate([public, duplicate])

    def test_parent_child_public_overlap_is_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate([release(cells=[cell(), cell(48, [('adult_cyclist', 3, 1)])])])

    def test_disjoint_spatial_cells_with_overlapping_time_are_legal(self):
        public = [release(cells=[cell(48, [('adult_cyclist', 3, 1)])], owner=48),
                  release(cells=[cell(49, [('child_cyclist', 3, 1)])], owner=49)]
        result = self.evaluate(public, target_cells=[{'cell_id': 48, 'depth': 2},
                                                     {'cell_id': 49, 'depth': 2}])
        self.assertEqual(q(result, identity=48)['prediction'], 3)
        self.assertEqual(q(result, identity=49)['prediction'], 3)

    def test_repeated_local_owner_with_disjoint_time_is_legal(self):
        result = self.evaluate([release(), release(400, 800,
            cells=[cell(12, [('road_user', 16, 4)])])], window_ms=800)
        self.assertEqual(q(result)['prediction'], 28)

    def test_malformed_scope_and_out_of_scope_selected_cell_are_rejected(self):
        for mutation in (
            lambda r: r['coordination_cell'].update(x=1),
            lambda r: r['coordination_cell'].update(depth=2),
            lambda r: r.update(coordination_cell=scope(48)),
            lambda r: r.update(cells=[cell(52, [('road_user', 3, 1)])]),
            lambda r: r.update(coordination_cell={}),
        ):
            public = release()
            mutation(public)
            with self.assertRaises(ValueError):
                self.evaluate([public])

    def test_mixed_common_and_local_streams_are_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate([release(owner=None), release(400, 800)])

    def test_invalid_interval_and_event_chronology_are_rejected(self):
        for mutation in (
            lambda r: r.update(start_ms=1), lambda r: r.update(end_ms=401),
            lambda r: r.update(end_ms=0), lambda r: r.update(sealed_at_ms=399),
            lambda r: r.update(sealed_at_ms=1601),
        ):
            public = release()
            mutation(public)
            with self.assertRaises(ValueError):
                self.evaluate([public])
        with self.assertRaises(ValueError):
            self.evaluate([release(400, 800), release()])

    def test_invalid_public_count_partitions_are_rejected(self):
        for mutation in (
            lambda c: c.update(distinct_road_users=5),
            lambda c: c.update(observation_contributions=13),
            lambda c: c['semantic']['categories'][0].update(distinct_contributors=4),
            lambda c: c['semantic'].update(semantic_mean_loss=.1),
            lambda c: c['semantic'].update(semantic_max_loss=1),
            lambda c: c['semantic'].update(min_category_distinct_contributors=2),
            lambda c: c['semantic'].update(taxonomy_id='other'),
            lambda c: c['semantic'].update(taxonomy_version='2'),
            lambda c: c['semantic']['categories'][0].update(category_id='absent'),
            lambda c: c['semantic']['categories'].append(deepcopy(c['semantic']['categories'][0])),
        ):
            public = release()
            mutation(public['cells'][0])
            with self.assertRaises(ValueError):
                self.evaluate([public])
        with self.assertRaises(ValueError):
            self.evaluate([release(cells=[cell(12, [('road_user', 9, 3), ('cyclist', 3, 1)])])])

    def test_invalid_source_identity_coordinate_and_t0_are_rejected(self):
        for mutation in (
            lambda r: r['batches'][0]['observations'][0].update(x=3),
            lambda r: r['batches'][0]['observations'][0].update(type='Car'),
            lambda r: r['batches'][0]['observations'].append(deepcopy(r['batches'][0]['observations'][0])),
            lambda r: r['batches'][0].update(observed_at_ms=0),
            lambda r: r['batches'][0].update(status='unavailable'),
        ):
            replay = source()
            mutation(replay)
            with self.assertRaises(ValueError):
                self.evaluate(replay=replay)

    def test_invalid_taxonomy_is_rejected(self):
        for mutation in (
            lambda c: c['semantic_taxonomy']['nodes'][1].update(parent='absent'),
            lambda c: c['semantic_taxonomy']['nodes'][0].update(parent='cyclist'),
            lambda c: c['semantic_taxonomy']['nodes'][4].update(input_types=['Impossible internal label']),
            lambda c: c['semantic_taxonomy']['nodes'][5].update(input_types=['Adult Pedestrian']),
        ):
            config = configuration()
            mutation(config)
            with self.assertRaises(ValueError):
                self.evaluate(config=config)

    def test_query_workload_limits_and_invalid_targets_are_rejected(self):
        for options in (
            {'max_queries': 1}, {'max_queries': False},
            {'target_cells': []}, {'target_cells': [{'cell_id': 12, 'depth': 2}]},
            {'target_cells': [{'cell_id': 12, 'depth': 1}, {'cell_id': 12, 'depth': 1}]},
            {'categories': []}, {'categories': ['road_user', 'road_user']},
            {'categories': ['unknown']}, {'window_ms': 0}, {'window_ms': 150},
            {'lags_ms': []}, {'lags_ms': [400, 0]}, {'lags_ms': [0, 0]},
            {'lags_ms': [False]},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.evaluate(**options)

    def test_inputs_are_not_mutated(self):
        replay, config, public = source(), configuration(), [release()]
        before = deepcopy((replay, config, public))
        self.evaluate(public, replay=replay, config=config)
        self.assertEqual((replay, config, public), before)

    def test_first_period_has_no_scheduled_sample_and_is_not_reported_as_zero(self):
        result = self.evaluate([], window_ms=100, categories=['road_user'])
        first = q(result)
        self.assertEqual(first['scheduled_sample_count'], 0)
        self.assertFalse(first['answered'])
        self.assertFalse(first['reference_available'])
        self.assertIsNone(first['prediction'])
        self.assertIsNone(first['reference_observation_contributions'])
        self.assertIn('no_scheduled_samples', first['unknown_reasons'])
        following = q(result, start=100)
        self.assertEqual(following['scheduled_sample_count'], 1)
        self.assertEqual(following['reference_observation_contributions'], 4)

    def test_receiver_and_reference_eligible_denominators_are_separate(self):
        replay = source()
        replay['batches'].pop(1)
        result = self.evaluate([release()], replay=replay, categories=['road_user'])
        summary = result['evaluations_by_lag_ms']['0']['summary']['interior']
        self.assertEqual(summary['query_count'], 2)
        self.assertEqual(summary['receiver_answered_query_count'], 1)
        self.assertEqual(summary['receiver_query_coverage'], .5)
        self.assertEqual(summary['reference_available_query_count'], 1)
        self.assertEqual(summary['reference_unavailable_query_count'], 1)
        self.assertEqual(summary['answered_query_count'], 0)
        self.assertEqual(summary['query_coverage'], 0)
        self.assertIsNone(summary['answered_only_mae'])

    def test_positive_known_zero_and_category_summary_partition(self):
        result = self.evaluate([release()], categories=['road_user', 'cyclist', 'scooter'])
        summary = result['evaluations_by_lag_ms']['0']['summary']['interior']
        self.assertEqual(summary['query_count'], 6)
        self.assertEqual(summary['answered_query_count'], 3)
        self.assertEqual(summary['query_coverage'], .5)
        self.assertEqual(summary['known_zero']['query_count'], 2)
        self.assertEqual(summary['known_zero']['answered_query_count'], 1)
        self.assertEqual(summary['positive']['query_count'], 4)
        self.assertEqual(summary['positive']['answered_query_count'], 2)
        self.assertEqual(sum(s['query_count'] for s in summary['by_category'].values()), 6)
        self.assertEqual(summary['absolute_error_sum'], 0)

    def test_query_budget_is_checked_before_visiting_observations(self):
        class UnreadableBatches(list):
            def __iter__(self):
                raise AssertionError('Budget preflight must precede source traversal')
        replay = source()
        replay['batches'] = UnreadableBatches(replay['batches'])
        with self.assertRaisesRegex(ValueError, '[Bb]udget'):
            self.evaluate(replay=replay, max_queries=1)

    def test_compact_keeps_definitions_and_summaries_without_query_rows(self):
        result = self.evaluate([release()])
        before = deepcopy(result)
        small = compact(result)
        self.assertEqual(small['schema'], result['schema'])
        self.assertEqual(small['query_definition'], result['query_definition'])
        for lag, item in small['evaluations_by_lag_ms'].items():
            self.assertNotIn('queries', item)
            self.assertEqual(item['summary'], result['evaluations_by_lag_ms'][lag]['summary'])
        small['query_definition']['categories'].append('changed-copy')
        self.assertEqual(result, before)

    def test_pairing_reports_common_answers_separately_from_individual_coverage(self):
        a = self.evaluate([release()], categories=['road_user'])
        b = self.evaluate([release(cells=[cell(12, [('road_user', 15, 4)])]),
            release(400, 800, cells=[cell(12, [('road_user', 16, 4)])])],
            categories=['road_user'])
        pair = paired_summary(a, b)
        self.assertEqual(pair['schema'], 'ump.scoped-semantic-queries-paired.v1')
        summary = pair['evaluations_by_lag_ms']['0']['summary']['interior']
        self.assertEqual(summary['query_count'], 2)
        self.assertEqual(summary['both_answered_query_count'], 1)
        self.assertEqual(summary['only_a_answered_query_count'], 0)
        self.assertEqual(summary['only_b_answered_query_count'], 1)
        self.assertEqual(summary['neither_answered_query_count'], 0)
        self.assertEqual(summary['intersection_a_mae'], 0)
        self.assertEqual(summary['intersection_b_mae'], 3)
        self.assertEqual(summary['a']['query_coverage'], .5)
        self.assertEqual(summary['b']['query_coverage'], 1)
        self.assertEqual(summary['b']['answered_only_mae'], 1.5)
        self.assertEqual(summary['by_category']['road_user']['both_answered_query_count'], 1)
        self.assertEqual(summary['known_zero']['query_count'], 0)
        self.assertEqual(summary['positive']['query_count'], 2)

    def test_pairing_rejects_different_definitions_reference_or_compact_inputs(self):
        a = self.evaluate([release()], categories=['road_user'])
        different_window = self.evaluate([release()], categories=['road_user'], window_ms=800)
        changed = source()
        for batch in changed['batches']:
            batch['observations'] = []
        different_reference = self.evaluate([release()], replay=changed, categories=['road_user'])
        for b in (different_window, different_reference, compact(a)):
            with self.assertRaises(ValueError):
                paired_summary(a, b)

    def test_pairing_without_common_answers_leaves_intersection_error_unknown(self):
        a = self.evaluate([release()], categories=['road_user'])
        b = self.evaluate([release(400, 800, cells=[cell(12, [('road_user', 16, 4)])])],
                          categories=['road_user'])
        summary = paired_summary(a, b)['evaluations_by_lag_ms']['0']['summary']['interior']
        self.assertEqual(summary['both_answered_query_count'], 0)
        self.assertEqual(summary['only_a_answered_query_count'], 1)
        self.assertEqual(summary['only_b_answered_query_count'], 1)
        self.assertIsNone(summary['intersection_a_mae'])
        self.assertIsNone(summary['intersection_b_mae'])

    def test_deadline_lag_need_not_align_with_sensor_cadence(self):
        exact = self.evaluate([release(sealed=450)], lags_ms=(0, 50))
        late = self.evaluate([release(sealed=451)], lags_ms=(0, 50))
        self.assertFalse(q(exact)['answered'])
        self.assertTrue(q(exact, lag=50)['answered'])
        self.assertEqual(q(exact, lag=50)['deadline_ms'], 450)
        self.assertFalse(q(late, lag=50)['answered'])

    def test_pairing_retains_recipient_answers_when_private_reference_is_unavailable(self):
        replay = source()
        replay['batches'].pop(1)
        a = self.evaluate([release()], replay=replay, categories=['road_user'])
        b = self.evaluate([release()], replay=replay, categories=['road_user'])
        summary = paired_summary(a, b)['evaluations_by_lag_ms']['0']['summary']['interior']
        self.assertEqual(summary['query_count'], 2)
        self.assertEqual(summary['reference_available_query_count'], 1)
        self.assertEqual(summary['both_answered_query_count'], 1)
        self.assertEqual(summary['neither_answered_query_count'], 1)
        self.assertEqual(summary['scored_intersection_query_count'], 0)
        self.assertIsNone(summary['intersection_a_mae'])
        self.assertIsNone(summary['intersection_b_mae'])
        empty = self.evaluate([], replay=replay, categories=['road_user'])
        exclusive = paired_summary(a, empty)['evaluations_by_lag_ms']['0']['summary']['interior']
        self.assertEqual(exclusive['only_a_answered_query_count'], 1)
        self.assertEqual(exclusive['neither_answered_query_count'], 1)

    def test_huge_origin_one_ulp_shift_is_rejected_when_large_relative_to_cell(self):
        replay = source()
        replay['coverage'].update(x=1e12, width=80, height=80, leaf_depth=14)
        for batch in replay['batches']:
            batch['observations'] = []
        identity = 3 << 28  # Northwest leaf, fourteen divisions from the root.
        geometry = {'cell_id': identity, 'depth': 14, 'x': 1e12, 'y': 0,
                    'width': 80 / 16384, 'height': 80 / 16384}
        public = release(cells=[cell(12, [('road_user', 12, 4)])])
        public['coordination_cell'] = deepcopy(geometry)
        public['cells'][0].update(geometry)
        options = {'target_cells': [{'cell_id': identity, 'depth': 14}]}
        valid = self.evaluate([public], replay=replay, **options)
        self.assertEqual(q(valid, identity=identity)['prediction'], 12)
        for where in ('scope', 'cell'):
            shifted = deepcopy(public)
            item = shifted['coordination_cell'] if where == 'scope' else shifted['cells'][0]
            item['x'] = math.nextafter(1e12, math.inf)
            with self.subTest(where=where), self.assertRaises(ValueError):
                self.evaluate([shifted], replay=replay, **options)

    def test_harmless_one_ulp_rounding_of_ordinary_geometry_is_accepted(self):
        replay, public = source(), release()
        replay['coverage'].update(x=.1, y=.1)
        for batch in replay['batches']:
            for observation in batch['observations']:
                observation['x'] += .1
                observation['y'] += .1
        for item in (public['coordination_cell'], public['cells'][0]):
            item['x'] = math.nextafter(.1, math.inf)
            item['y'] = .1
        self.assertEqual(q(self.evaluate([public], replay=replay))['prediction'], 12)

    def test_legacy_fixed_workload_predictions_are_preserved(self):
        from test_semantic_queries import configuration as legacy_config, source as legacy_source
        from test_semantic_queries import cell as legacy_cell, release as legacy_release
        from semantic_queries import CATEGORIES, evaluate_queries
        targets = [{'cell_id': i, 'depth': 2} for i in range(48, 52)] + [{'cell_id': 12, 'depth': 1}]
        cases = [([legacy_release()], 400),
                 ([legacy_release(cells=[legacy_cell(12, [('road_user', 9, 3)])])], 400),
                 ([legacy_release(end=800, sealed=800,
                    cells=[legacy_cell(12, [('road_user', 21, 3)])])], 400),
                 ([legacy_release(end=800, sealed=800,
                    cells=[legacy_cell(12, [('road_user', 21, 3)])])], 800)]
        fields = ('answered', 'prediction', 'reference_available',
                  'reference_observation_contributions', 'absolute_error',
                  'cohort', 'deadline_observed', 'deadline_at_eof')
        for public, window in cases:
            with self.subTest(window=window, release=public):
                replay, config = legacy_source(), legacy_config()
                previous = evaluate_queries(replay, config, public, window_ms=window)
                current = evaluate(replay, config, public, target_cells=targets,
                                   categories=list(CATEGORIES), window_ms=window)
                for lag in ('0', '400'):
                    expected = {(r['cell_id'], r['start_ms'], r['category_id']): r
                        for scale in previous['by_scale'].values()
                        for r in scale['by_lag_ms'][lag]['queries']}
                    actual = current['evaluations_by_lag_ms'][lag]['queries']
                    self.assertEqual(len(actual), len(expected))
                    for row in actual:
                        old = expected[(row['cell_id'], row['start_ms'], row['category_id'])]
                        self.assertEqual(tuple(row[f] for f in fields), tuple(old[f] for f in fields))


if __name__ == '__main__':
    unittest.main()
