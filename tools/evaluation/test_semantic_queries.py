"""Independent expected-count tests for the bounded recipient query contract."""
from copy import deepcopy
import unittest

from semantic_queries import evaluate_queries


def configuration():
    return dict(semantic_taxonomy=dict(id='semantic-priority', version='1', nodes=[
        dict(id='road_user', loss=1), dict(id='pedestrian', parent='road_user', loss=0, input_types=['Pedestrian']),
        dict(id='cyclist', parent='road_user', loss=.5),
        dict(id='adult_cyclist', parent='cyclist', loss=0, input_types=['Adult Cyclist']),
        dict(id='child_cyclist', parent='cyclist', loss=0, input_types=['Child Cyclist'])]))


def source(horizon=2400):
    # Three distinct people at every sample: adult in leaf48, child in leaf49,
    # pedestrian in leaf50. Leaf51 is measured empty, not publicly certified.
    observations = [dict(id='a', type='Adult Cyclist', cell_id=48, x=1, y=1),
        dict(id='c', type='Child Cyclist', cell_id=49, x=21, y=1),
        dict(id='p', type='Pedestrian', cell_id=50, x=1, y=21)]
    return dict(schema='ump.observation-replay.v1', run_id='queries', sensor_id='agbs',
        coverage=dict(x=0, y=0, width=80, height=80, leaf_depth=2), sampling_period_ms=100,
        end_ms=horizon, batches=[dict(sequence=n, observed_at_ms=time, status='measured',
            observations=deepcopy(observations)) for n, time in enumerate(range(100, horizon, 100), 1)])


LOSS = {'road_user': 1, 'pedestrian': 0, 'cyclist': .5, 'adult_cyclist': 0, 'child_cyclist': 0}


def cell(identity, bins):
    depth = 1 if identity == 12 else 2
    x, y, side = (0, 0, 40) if identity == 12 else ((identity % 4 & 1) * 20, (identity % 4 >> 1) * 20, 20)
    categories = [dict(category_id=category, observation_contributions=observations, distinct_contributors=distinct)
        for category, observations, distinct in bins]
    total = sum(row[1] for row in bins)
    return dict(cell_id=identity, depth=depth, x=x, y=y, width=side, height=side,
        observation_contributions=total, distinct_road_users=sum(row[2] for row in bins),
        mean_sample_occupancy=1, effective_policy_id='policy/effective',
        semantic=dict(schema='ump.semantic-release.v1', taxonomy_id='semantic-priority', taxonomy_version='1',
            min_category_distinct_contributors=min(row[2] for row in bins),
            semantic_max_loss=max(LOSS[row[0]] for row in bins),
            semantic_mean_loss=sum(LOSS[row[0]] * row[1] for row in bins) / total, categories=categories))


def release(start=0, end=400, sealed=400, cells=None, identity=None):
    return dict(release_id=identity or f'release-{start}-{end}', start_ms=start, end_ms=end, sealed_at_ms=sealed,
        model='private_final_snapshot', policy_id='policy', policy_version='1', cells=cells or [cell(12,
            [('adult_cyclist', 3, 1), ('child_cyclist', 3, 1), ('pedestrian', 3, 1)])])


def query(result, *, scale='40', lag='0', start=0, category='road_user', identity=None):
    rows = result['by_scale'][scale]['by_lag_ms'][lag]['queries']
    return next(q for q in rows if q['start_ms'] == start and q['category_id'] == category
        and (identity is None or q['cell_id'] == identity))


class SemanticQueryTests(unittest.TestCase):
    def evaluate(self, releases=(), replay=None, config=None, **kwargs):
        return evaluate_queries(replay or source(), config or configuration(), list(releases), **kwargs)

    def test_exact_parent_sums_observations_not_people(self):
        result = self.evaluate([release()])
        root = query(result)
        self.assertTrue(root['answered'])
        self.assertEqual((root['prediction'], root['reference_observation_contributions'], root['absolute_error']), (9, 9, 0))
        self.assertEqual(query(result, category='cyclist')['prediction'], 6)
        self.assertEqual(query(result, category='adult_cyclist')['prediction'], 3)
        self.assertEqual(query(result, category='child_cyclist')['prediction'], 3)
        self.assertEqual(root['cohort'], 'interior')

    def test_parent_release_cannot_be_spatially_clipped_for_child(self):
        result = self.evaluate([release()])
        child = query(result, scale='20', identity=48)
        self.assertFalse(child['answered'])
        self.assertIsNone(child['prediction'])
        self.assertIn('crossing_public_support', child['unknown_reasons'])
        self.assertEqual(child['reference_observation_contributions'], 3)

    def test_child_tiles_can_answer_parent_only_with_all_four_spatial_parts(self):
        three = [cell(48, [('adult_cyclist', 3, 1)]), cell(49, [('child_cyclist', 3, 1)]),
                 cell(50, [('pedestrian', 3, 1)])]
        result = self.evaluate([release(cells=three)])
        self.assertTrue(query(result, scale='20', identity=48)['answered'])
        self.assertFalse(query(result)['answered'])
        # GT says leaf51 is empty. That private fact must not fill the fourth public hole.
        empty = query(result, scale='20', identity=51)
        self.assertEqual(empty['reference_observation_contributions'], 0)
        self.assertFalse(empty['answered'])
        self.assertIsNone(empty['prediction'])

    def test_full_spatial_tiles_satisfy_parent_independently_of_reference_errors(self):
        # A deliberately different public count proves predictions do not consult GT.
        tiles = [cell(identity, [('adult_cyclist', 3, 1)]) for identity in range(48, 52)]
        result = self.evaluate([release(cells=tiles)])
        q = query(result)
        self.assertTrue(q['answered'])
        self.assertEqual((q['prediction'], q['reference_observation_contributions'], q['absolute_error']), (12, 9, 3))

    def test_semantic_ancestor_straddling_query_is_unknown(self):
        result = self.evaluate([release(cells=[cell(12, [('road_user', 9, 3)])])])
        self.assertEqual(query(result)['prediction'], 9)
        for category in ('cyclist', 'adult_cyclist', 'child_cyclist'):
            self.assertFalse(query(result, category=category)['answered'])
            self.assertIn('semantic_generalization', query(result, category=category)['unknown_reasons'])
        intermediate = self.evaluate([release(cells=[cell(12, [('cyclist', 6, 2), ('pedestrian', 3, 1)])])])
        self.assertEqual(query(intermediate, category='cyclist')['prediction'], 6)
        self.assertFalse(query(intermediate, category='adult_cyclist')['answered'])

    def test_disjoint_complete_category_partition_certifies_zero(self):
        result = self.evaluate([release(cells=[cell(48, [('pedestrian', 3, 1)])])])
        q = query(result, scale='20', identity=48, category='cyclist')
        self.assertTrue(q['answered'])
        self.assertEqual(q['prediction'], 0)
        # Incorrect public/reference discrepancy must stay visible, never be repaired.
        self.assertEqual((q['reference_observation_contributions'], q['absolute_error']), (3, 3))

    def test_delayed_release_becomes_visible_at_exact_deadline(self):
        result = self.evaluate([release(sealed=800)])
        self.assertFalse(query(result, lag='0')['answered'])
        self.assertTrue(query(result, lag='400')['answered'])
        # Boundary equality is included; one millisecond later is excluded.
        later = self.evaluate([release(sealed=801)])
        self.assertFalse(query(later, lag='400')['answered'])

    def test_crossing_time_aggregate_is_not_clipped(self):
        large = release(end=800, sealed=800, cells=[cell(12,
            [('adult_cyclist', 7, 1), ('child_cyclist', 7, 1), ('pedestrian', 7, 1)])])
        result = self.evaluate([large])
        self.assertFalse(query(result, lag='400')['answered'])
        self.assertFalse(query(result, start=400)['answered'])
        coarse = self.evaluate([large], window_ms=800)
        self.assertEqual(query(coarse)['prediction'], 21)
        self.assertEqual(query(coarse)['absolute_error'], 0)

    def test_time_tiles_cover_a_coarser_query_without_doublecount(self):
        first = release()
        second = release(start=400, end=800, sealed=800, cells=[cell(12,
            [('adult_cyclist', 4, 1), ('child_cyclist', 4, 1), ('pedestrian', 4, 1)])])
        result = self.evaluate([first, second], window_ms=800)
        self.assertEqual(query(result)['prediction'], 21)
        self.assertEqual(query(result)['reference_observation_contributions'], 21)
        self.assertEqual(query(result)['absolute_error'], 0)

    def test_missing_time_tile_stays_unknown(self):
        result = self.evaluate([release()], window_ms=800)
        self.assertFalse(query(result)['answered'])

    def test_missing_and_unavailable_reference_are_not_fabricated(self):
        for mode in ('missing', 'unavailable'):
            replay = source()
            if mode == 'missing':
                replay['batches'].pop(1)
            else:
                replay['batches'][1].update(status='unavailable', observations=[])
            result = self.evaluate([release()], replay=replay)
            q = query(result)
            self.assertTrue(q['answered'])
            self.assertEqual(q['prediction'], 9)
            self.assertFalse(q['reference_available'])
            self.assertIsNone(q['reference_observation_contributions'])
            self.assertIsNone(q['absolute_error'])
            summary = result['by_scale']['40']['by_lag_ms']['0']['summary']['interior']
            self.assertEqual(summary['reference_unavailable_query_count'], 4)

    def test_censored_deadline_and_eof_are_separate_from_interior(self):
        last = release(start=2000, end=2400, sealed=2400, cells=[cell(12,
            [('adult_cyclist', 4, 1), ('child_cyclist', 4, 1), ('pedestrian', 4, 1)])])
        result = self.evaluate([last])
        eof = query(result, start=2000)
        self.assertTrue(eof['answered'])
        self.assertTrue(eof['deadline_at_eof'])
        self.assertEqual(eof['cohort'], 'boundary')
        censored = query(result, lag='400', start=2000)
        self.assertFalse(censored['deadline_observed'])
        self.assertFalse(censored['answered'])
        self.assertIsNone(censored['prediction'])
        at_eof = query(result, lag='400', start=1600)
        self.assertTrue(at_eof['deadline_observed'])
        self.assertTrue(at_eof['deadline_at_eof'])
        self.assertEqual(at_eof['cohort'], 'boundary')

    def test_summary_denominators_are_fixed_and_unknown_errors_remain_null(self):
        result = self.evaluate([])
        for lag in ('0', '400'):
            interior = result['by_scale']['40']['by_lag_ms'][lag]['summary']['interior']
            self.assertEqual(interior['query_count'], 16)  # four 400ms intervals times four tasks
            self.assertEqual(interior['reference_available_query_count'], 16)
            self.assertEqual(interior['answered_query_count'], 0)
            self.assertEqual(interior['query_coverage'], 0)
            self.assertIsNone(interior['answered_only_mae'])
            self.assertEqual(sum(v['query_count'] for v in interior['by_category'].values()), 16)
            self.assertEqual(interior['known_zero']['query_count'] + interior['positive']['query_count'], 16)
        boundary = result['by_scale']['40']['by_lag_ms']['400']['summary']['boundary']
        self.assertEqual((boundary['query_count'], boundary['observed_query_count'], boundary['censored_query_count']), (8, 4, 4))

    def test_changing_private_reference_does_not_change_predictions(self):
        reference = source()
        for batch in reference['batches']:
            batch['observations'] = []
        actual = self.evaluate([release()])
        empty = self.evaluate([release()], replay=reference)
        for scale in ('20', '40'):
            for lag in ('0', '400'):
                a = actual['by_scale'][scale]['by_lag_ms'][lag]['queries']
                b = empty['by_scale'][scale]['by_lag_ms'][lag]['queries']
                self.assertEqual([(q['answered'], q['prediction']) for q in a], [(q['answered'], q['prediction']) for q in b])

    def test_unknown_raw_class_and_invalid_source_are_rejected(self):
        replay = source()
        replay['batches'][0]['observations'][0]['type'] = 'Car'
        with self.assertRaises(ValueError):
            self.evaluate(replay=replay)
        replay = source()
        replay['batches'][0]['observations'][0]['x'] = 21
        with self.assertRaises(ValueError):
            self.evaluate(replay=replay)
        replay = source()
        replay['batches'][0]['observations'].append(deepcopy(replay['batches'][0]['observations'][0]))
        with self.assertRaises(ValueError):
            self.evaluate(replay=replay)

    def test_source_and_recipient_support_outside_parent12_are_rejected(self):
        replay = source()
        replay['batches'][0]['observations'][0].update(cell_id=52, x=41, y=1)
        with self.assertRaises(ValueError):
            self.evaluate(replay=replay)
        for identity, depth, side in ((13, 1, 40), (52, 2, 20)):
            outside = cell(12, [('road_user', 9, 3)])
            outside.update(cell_id=identity, depth=depth, x=40, y=0, width=side, height=side)
            with self.assertRaises(ValueError):
                self.evaluate([release(cells=[outside])])

    def test_release_metadata_geometry_and_overlap_are_validated(self):
        for mutate in (lambda r: r.update(sealed_at_ms=399), lambda r: r.update(end_ms=0),
                       lambda r: r['cells'][0].update(x=1), lambda r: r['cells'][0].update(depth=2),
                       lambda r: r.update(coordination_cell={})):
            row = release()
            mutate(row)
            with self.assertRaises(ValueError):
                self.evaluate([row])
        with self.assertRaises(ValueError):
            self.evaluate([release(), release(identity='duplicate-support')])
        with self.assertRaises(ValueError):
            self.evaluate([release(cells=[cell(12, [('road_user', 9, 3)]), cell(48, [('adult_cyclist', 3, 1)])])])
        with self.assertRaises(ValueError):
            self.evaluate([release(), release(start=400, end=800, sealed=800, identity='release-0-400')])

    def test_category_partition_and_metric_summaries_are_validated(self):
        mutations = [lambda s: s.update(taxonomy_version='2'), lambda s: s.update(taxonomy_id='other'),
            lambda s: s.update(schema='unknown'), lambda s: s.update(semantic_mean_loss=float('nan')),
            lambda s: s.update(semantic_max_loss=.5), lambda s: s.update(min_category_distinct_contributors=2),
            lambda s: s['categories'][0].update(category_id='unknown'),
            lambda s: s['categories'][0].update(observation_contributions=4),
            lambda s: s['categories'][0].update(distinct_contributors=2),
            lambda s: s['categories'].append(deepcopy(s['categories'][0]))]
        for mutate in mutations:
            row = release()
            mutate(row['cells'][0]['semantic'])
            with self.assertRaises(ValueError):
                self.evaluate([row])
        overlapping = cell(12, [('road_user', 6, 2), ('cyclist', 3, 1)])
        with self.assertRaises(ValueError):
            self.evaluate([release(cells=[overlapping])])

    def test_unsupported_workload_is_rejected_without_mutating_inputs(self):
        replay, config, public = source(), configuration(), [release()]
        before = deepcopy((replay, config, public))
        evaluate_queries(replay, config, public)
        self.assertEqual((replay, config, public), before)
        for kwargs in (dict(window_ms=200), dict(lags_ms=()), dict(lags_ms=(400, 0)),
                       dict(lags_ms=(0, 0)), dict(lags_ms=(0, 200)), dict(lags_ms=(False,))):
            with self.assertRaises(ValueError):
                evaluate_queries(replay, config, public, **kwargs)
        for key, value in (('leaf_depth', 6), ('width', 160)):
            wrong = deepcopy(replay)
            wrong['coverage'][key] = value
            with self.assertRaises(ValueError):
                evaluate_queries(wrong, config, public)


if __name__ == '__main__':
    unittest.main()
