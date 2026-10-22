"""Hand-computed tests for the private-truth moving pilot audit."""
from copy import deepcopy
import unittest

from moving_scoped_audit import audit_result


def fixture():
    # Ten identities, three samples each: 30 contributions. The deliberately
    # off-cadence seal proves delay is derived from source timestamps, not T/2.
    nodes = [dict(id='road_user', loss=1), dict(id='pedestrian', parent='road_user', loss=.5),
             dict(id='cyclist', parent='road_user', loss=.5),
             dict(id='escooter', parent='road_user', loss=0, input_types=['Adult E-Scooter Driver'])]
    for category, parent, label in (
            ('child_pedestrian', 'pedestrian', 'Child Pedestrian'),
            ('senior_pedestrian', 'pedestrian', 'Senior Pedestrian'),
            ('adult_pedestrian', 'pedestrian', 'Adult Pedestrian'),
            ('senior_cyclist', 'cyclist', 'Senior Cyclist'),
            ('adult_cyclist', 'cyclist', 'Adult Cyclist'),
            ('adult_cargo_cyclist', 'cyclist', 'Adult Cargo Cyclist')):
        nodes.append(dict(id=category, parent=parent, loss=0, input_types=[label]))
    config = {'semantic_taxonomy': {'id': 'ump-seven-profile-release', 'version': '1', 'nodes': nodes},
              'policy_regions': [], 'policy_tree': {'regions': [], 'root': {
                  'window_duration_ms': {'min': 400, 'max': 1000},
                  'age_at_evaluation_ms': {'max': 1000},
                  'cell_side_m': {'min': 1.25, 'max': 10},
                  'distinct_contributors': {'min': 1},
                  'min_category_distinct_contributors': {'min': 5},
                  'semantic_max_loss': {'max': 1}}}}
    rows = [dict(id=f'{kind}-{n}', type=label, cell_id=12288, x=.5, y=.5)
            for kind, label in (('adult', 'Adult Pedestrian'), ('child', 'Child Pedestrian'))
            for n in range(5)]
    replay = {'schema': 'ump.observation-replay.v1',
              'coverage': dict(x=0, y=0, width=80, height=80, leaf_depth=6),
              'sampling_period_ms': 100, 'end_ms': 800,
              'batches': [dict(sequence=t // 100, observed_at_ms=t, status='measured',
                               observations=deepcopy(rows) if t < 400 else [])
                          for t in range(100, 800, 100)]}
    semantic = {'schema': 'ump.semantic-release.v1', 'taxonomy_id': 'ump-seven-profile-release',
                'taxonomy_version': '1', 'min_category_distinct_contributors': 5,
                'semantic_max_loss': 0, 'semantic_mean_loss': 0,
                'categories': [dict(category_id=f'{kind}_pedestrian', observation_contributions=15,
                                    distinct_contributors=5) for kind in ('adult', 'child')]}
    cell = dict(cell_id=12288, depth=6, x=0, y=0, width=1.25, height=1.25,
                observation_contributions=30, distinct_road_users=10, semantic=semantic)
    result = {'input_observation_contributions': 30, 'accounted_observation_contributions': 30,
              'runtime': {'processing_ms': 1.5}, 'windows': [{}, {}],
              'releases': [dict(start_ms=0, end_ms=400, sealed_at_ms=450, cells=[cell])]}
    return replay, config, result


class MovingScopedAuditTests(unittest.TestCase):
    def setUp(self):
        self.replay, self.config, self.result = fixture()

    @property
    def cell(self):
        return self.result['releases'][0]['cells'][0]

    @property
    def semantic(self):
        return self.cell['semantic']

    def audit(self):
        return audit_result(self.replay, self.config, self.result)

    def test_exact_counts_delay_and_safe_summary(self):
        value = self.audit()
        self.assertEqual(value['audit']['status'], 'verified')
        stats = value['stats']
        self.assertEqual(stats['released_observations'], 30)
        self.assertEqual(stats['retained_fraction'], 1)
        self.assertEqual(stats['mean_semantic_loss'], 0)
        self.assertEqual(stats['mean_cell_side_m'], 1.25)
        self.assertEqual(stats['mean_interval_start_age_ms'], 450)
        self.assertEqual(stats['mean_observation_to_release_delay_ms'], 250)
        self.assertEqual(stats['observation_to_release_delay_ms'], {'min': 150, 'max': 350})
        self.assertEqual(stats['window_duration_ms'], {'min': 400, 'max': 400})
        self.assertEqual(stats['per_input_type']['adult_pedestrian']['released_observations'], 15)
        self.assertEqual(stats['released_category_observations']['child_pedestrian'], 15)
        self.assertNotIn('adult-0', str(value))
        self.assertNotIn('child-0', str(value))

    def test_generalized_truthful_parent_counts_identities_and_loss(self):
        self.semantic.update(categories=[dict(category_id='pedestrian', observation_contributions=30,
                                              distinct_contributors=10)],
                             min_category_distinct_contributors=10,
                             semantic_max_loss=.5, semantic_mean_loss=.5)
        stats = self.audit()['stats']
        self.assertEqual(stats['mean_semantic_loss'], .5)
        self.assertEqual(stats['released_category_observations']['pedestrian'], 30)

    def test_spatial_ancestor_collects_exact_descendant_rows(self):
        for batch in self.replay['batches']:
            for row in batch['observations']:
                if row['type'] == 'Child Pedestrian':
                    row.update(cell_id=12289, x=1.5)
        self.cell.update(cell_id=3072, depth=5, width=2.5, height=2.5)
        self.assertEqual(self.audit()['stats']['mean_cell_side_m'], 2.5)

    def test_adjacent_disjoint_windows_do_not_reuse_source_rows(self):
        rows = deepcopy(self.replay['batches'][0]['observations'])
        for batch in self.replay['batches']:
            if batch['observed_at_ms'] >= 400:
                batch['observations'] = deepcopy(rows)
        release = deepcopy(self.result['releases'][0])
        release.update(start_ms=400, end_ms=800, sealed_at_ms=800)
        cell = release['cells'][0]
        cell['observation_contributions'] = 40
        for item in cell['semantic']['categories']:
            item['observation_contributions'] = 20
        self.result['releases'].append(release)
        self.result['input_observation_contributions'] = 70
        self.result['accounted_observation_contributions'] = 70
        self.assertEqual(self.audit()['stats']['released_observations'], 70)

    def test_empty_release_stream_reports_unknown_means(self):
        self.result['releases'] = []
        stats = self.audit()['stats']
        self.assertEqual(stats['retained_fraction'], 0)
        self.assertEqual(stats['unreleased_observations'], 30)
        for key in ('mean_semantic_loss', 'mean_cell_side_m', 'mean_interval_start_age_ms',
                    'mean_observation_to_release_delay_ms', 'mean_window_duration_ms'):
            self.assertIsNone(stats[key])

    def test_rejects_cell_contribution_count_mutation(self):
        self.cell['observation_contributions'] += 1
        with self.assertRaisesRegex(ValueError, 'cell observation count'):
            self.audit()

    def test_rejects_cell_identity_count_mutation(self):
        self.cell['distinct_road_users'] += 1
        with self.assertRaisesRegex(ValueError, 'cell identity union'):
            self.audit()

    def test_rejects_bin_contribution_and_identity_mutations(self):
        for field in ('observation_contributions', 'distinct_contributors'):
            with self.subTest(field=field):
                self.setUp()
                self.semantic['categories'][0][field] += 1
                with self.assertRaisesRegex(ValueError, 'bin count/identity union'):
                    self.audit()

    def test_rejects_boolean_counts_and_losses(self):
        for field in ('observation_contributions', 'distinct_contributors'):
            with self.subTest(field=field):
                self.setUp()
                self.semantic['categories'][0][field] = True
                with self.assertRaisesRegex(ValueError, 'exact integer'):
                    self.audit()
        self.setUp()
        self.semantic['semantic_mean_loss'] = False
        with self.assertRaisesRegex(ValueError, 'finite numeric'):
            self.audit()

    def test_rejects_omitted_observed_class(self):
        self.semantic['categories'].pop()
        with self.assertRaisesRegex(ValueError, 'omits or repeats'):
            self.audit()

    def test_rejects_untruthful_relabeling(self):
        self.semantic['categories'][0]['category_id'] = 'adult_cyclist'
        with self.assertRaisesRegex(ValueError, 'omits or repeats'):
            self.audit()

    def test_rejects_overlapping_antichain(self):
        self.semantic['categories'][0]['category_id'] = 'pedestrian'
        with self.assertRaisesRegex(ValueError, 'antichain'):
            self.audit()

    def test_rejects_empty_or_unknown_or_repeated_bins(self):
        for categories in ([], [dict(category_id='unknown')],
                           [self.semantic['categories'][0], self.semantic['categories'][0]]):
            with self.subTest(categories=categories):
                self.setUp()
                self.semantic['categories'] = deepcopy(categories)
                with self.assertRaisesRegex(ValueError, 'Unknown, empty or repeated'):
                    self.audit()

    def test_rejects_unobserved_added_category(self):
        self.semantic['categories'].append(dict(category_id='cyclist', observation_contributions=1,
                                                distinct_contributors=1))
        with self.assertRaisesRegex(ValueError, 'bin count/identity union'):
            self.audit()

    def test_rejects_semantic_summary_mutations(self):
        for key in ('min_category_distinct_contributors', 'semantic_max_loss', 'semantic_mean_loss'):
            with self.subTest(key=key):
                self.setUp()
                self.semantic[key] += 1
                with self.assertRaisesRegex(ValueError, 'disagrees'):
                    self.audit()

    def test_rejects_semantic_hard_support_violation(self):
        self.config['policy_tree']['root']['min_category_distinct_contributors']['min'] = 6
        with self.assertRaisesRegex(ValueError, 'hard policy min'):
            self.audit()

    def test_rejects_true_generalization_above_semantic_loss_limit(self):
        self.test_generalized_truthful_parent_counts_identities_and_loss()
        self.config['policy_tree']['root']['semantic_max_loss']['max'] = .4
        with self.assertRaisesRegex(ValueError, 'hard policy max'):
            self.audit()

    def test_rejects_public_source_reuse(self):
        self.result['releases'].append(deepcopy(self.result['releases'][0]))
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.audit()

    def test_rejects_ancestor_descendant_reuse(self):
        parent = deepcopy(self.cell)
        parent.update(cell_id=3072, depth=5, width=2.5, height=2.5)
        self.result['releases'][0]['cells'].append(parent)
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.audit()

    def test_rejects_accounting_mutations(self):
        for key in ('input_observation_contributions', 'accounted_observation_contributions'):
            with self.subTest(key=key):
                self.setUp()
                self.result[key] += 1
                with self.assertRaisesRegex(ValueError, 'accounting total'):
                    self.audit()

    def test_rejects_intervals_outside_hard_duration_bounds(self):
        for bound, value in (('min', 500), ('max', 300)):
            with self.subTest(bound=bound):
                self.setUp()
                self.config['policy_tree']['root']['window_duration_ms'][bound] = value
                with self.assertRaisesRegex(ValueError, 'window_duration_ms violates'):
                    self.audit()

    def test_rejects_hard_age_and_size_violations(self):
        for metric, value in (('age_at_evaluation_ms', 400), ('cell_side_m', 1)):
            with self.subTest(metric=metric):
                self.setUp()
                self.config['policy_tree']['root'][metric]['max'] = value
                with self.assertRaisesRegex(ValueError, f'{metric} violates'):
                    self.audit()

    def test_rejects_schema_and_catalog_mismatch(self):
        for key in ('schema', 'taxonomy_id', 'taxonomy_version'):
            with self.subTest(key=key):
                self.setUp()
                self.semantic[key] = 'wrong'
                with self.assertRaisesRegex(ValueError, 'schema or taxonomy'):
                    self.audit()

    def test_rejects_wrong_taxonomy_structure_loss_and_repeated_nodes(self):
        for change in ('loss', 'parent', 'repeated'):
            with self.subTest(change=change):
                self.setUp()
                nodes = self.config['semantic_taxonomy']['nodes']
                if change == 'loss':
                    nodes[0]['loss'] = .9
                elif change == 'parent':
                    nodes[1]['parent'] = 'cyclist'
                else:
                    nodes[-1] = deepcopy(nodes[-2])
                with self.assertRaises(ValueError):
                    self.audit()

    def test_rejects_regions_explicitly(self):
        self.config['policy_regions'] = [{'id': 'regional'}]
        with self.assertRaisesRegex(ValueError, 'uniform root policy'):
            self.audit()

    def test_rejects_unstable_identity_class(self):
        self.replay['batches'][1]['observations'][0]['type'] = 'Child Pedestrian'
        with self.assertRaisesRegex(ValueError, 'unstable terminal type'):
            self.audit()

    def test_rejects_unmapped_type_and_duplicate_identity(self):
        self.replay['batches'][0]['observations'][0]['type'] = 'Car'
        with self.assertRaisesRegex(ValueError, 'Unmapped source type'):
            self.audit()
        self.setUp()
        self.replay['batches'][0]['observations'][1]['id'] = self.replay['batches'][0]['observations'][0]['id']
        with self.assertRaisesRegex(ValueError, 'Repeated identity'):
            self.audit()

    def test_rejects_incomplete_or_unavailable_source(self):
        self.replay['batches'].pop()
        with self.assertRaisesRegex(ValueError, 'complete measured source cadence'):
            self.audit()
        self.setUp()
        self.replay['batches'][0]['status'] = 'unavailable'
        with self.assertRaisesRegex(ValueError, 'complete measured source cadence'):
            self.audit()

    def test_rejects_noncanonical_cell_geometry(self):
        self.cell['width'] = 2
        with self.assertRaisesRegex(ValueError, 'cell width'):
            self.audit()
        self.setUp()
        self.cell['depth'] = 5
        with self.assertRaisesRegex(ValueError, 'Cell ID'):
            self.audit()

    def test_does_not_modify_inputs(self):
        before = deepcopy((self.replay, self.config, self.result))
        self.audit()
        self.assertEqual((self.replay, self.config, self.result), before)


if __name__ == '__main__':
    unittest.main()
