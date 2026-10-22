"""Real C++ replay acceptance for semantic release triggers and secondary priority.

Decision expectations below are hand-worked bounded fixtures. The numeric audit
rebuilds truthful category partitions, distinct identities and declared loss from
raw input, independently of production pass flags and controller decisions. The
existing scalar oracle checks geometry, coverage and support retirement after an
explicit semantic-only projection; no legacy waiting oracle is used.
"""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / 'tools/evaluation'))
from oracle import validate_result
from run_semantic_priority_study import scalar_projection

BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT / 'simulator/build/AggregationReplay'))
POSITIONS = {48: (1, 1), 49: (21, 1), 50: (1, 21), 51: (21, 21)}
FAMILIES = ('pedestrian', 'cyclist', 'scooter')


def taxonomy():
    nodes = [{'id': 'road_user', 'loss': 1}]
    for family in FAMILIES:
        nodes.append({'id': family, 'parent': 'road_user', 'loss': .5})
        for age in ('adult', 'child'):
            label = f'{age}_{family}'
            nodes.append({'id': label, 'parent': family, 'loss': 0, 'input_types': [label]})
    return {'id': 'semantic-release-contract', 'version': '1', 'nodes': nodes}


def row(identity, kind='adult_pedestrian', cell=48):
    x, y = POSITIONS[cell]
    return {'id': identity, 'type': kind, 'cell_id': cell, 'x': x, 'y': y}


def people(cell, counts):
    return [row(f'{cell}/{kind}/{index}', kind, cell)
            for kind, count in counts.items() for index in range(count)]


def source(rows, end=800, *, unavailable=(), missing=()):
    batches = []
    for time in range(100, end, 100):
        if time in missing:
            continue
        values = rows(time) if callable(rows) else rows
        batches.append({'sequence': time // 100, 'observed_at_ms': time,
                        'status': 'unavailable' if time in unavailable else 'measured',
                        'observations': [] if time in unavailable else deepcopy(values)})
    return {'schema': 'ump.observation-replay.v1', 'run_id': 'semantic-release-contract',
            'sensor_id': 'agbs', 'coverage': {'x': 0, 'y': 0, 'width': 80, 'height': 80, 'leaf_depth': 2},
            'sampling_period_ms': 100, 'end_ms': end, 'batches': batches}


def policy(*, secondary=None, trigger=None, loss=1, side=40, maximum=800):
    execution = {'publication_model': 'private_final_snapshot', 'strategy': 'semantic_first'}
    if secondary is not None:
        execution['semantic_secondary_strategy'] = secondary
    if trigger is not None:
        execution['release_trigger'] = trigger
    return {'application_id': 'semantic-release-contract', 'window_ms': 400,
            'max_observations_per_window': 1000000,
            'history': {'retention_ms': 2000, 'max_bins': 32, 'max_observations': 100000,
                        'max_identity_bytes': 16000000, 'max_buckets': 128},
            'spatial_selection': {'min_depth': 1, 'max_evaluations': 4096,
                                  'preserve_valid_descendants': True},
            'temporal_adaptation': {'extension_step_ms': 100, 'max_window_ms': maximum,
                                    'max_evaluations': 16, 'coordination': 'common_window'},
            'semantic_taxonomy': taxonomy(),
            'policy_tree': {'id': 'semantic-release-contract-policy', 'version': '1', 'max_nodes': 65536,
                            'execution': execution,
                            'root': {'distinct_contributors': {'min': 1},
                                     'cell_side_m': {'min': 1.25, 'max': side},
                                     'window_duration_ms': {'max': maximum},
                                     'age_at_evaluation_ms': {'max': maximum},
                                     'min_category_distinct_contributors': {'min': 5},
                                     'semantic_max_loss': {'max': loss}}, 'regions': []},
            'policy_regions': []}


def categories(cell):
    return {item['category_id']: item['distinct_contributors'] for item in cell['semantic']['categories']}


def generalized_people():
    return people(48, {f'adult_{family}': 2 for family in FAMILIES})


def intermediate_people():
    return people(48, {f'{age}_{family}': count
                       for family in FAMILIES for age, count in (('adult', 2), ('child', 3))})


class SemanticReleaseTests(unittest.TestCase):
    maxDiff = None

    def run_core(self, data, config, *, reject=False, mode='semantic_first'):
        with tempfile.TemporaryDirectory(prefix='ump-semantic-release-') as temporary:
            directory = Path(temporary)
            inp, cfg, out = (directory / name for name in ('input.json', 'policy.json', 'result.json'))
            inp.write_text(json.dumps(data), encoding='utf-8')
            cfg.write_text(json.dumps(config), encoding='utf-8')
            completed = subprocess.run([str(BINARY), '--input', str(inp), '--config', str(cfg),
                                        '--mode', mode, '--output', str(out)],
                                       capture_output=True, text=True, timeout=30)
            if reject:
                self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertFalse(out.exists(), 'Rejected replay wrote a result')
                self.assertEqual(sorted(p.name for p in directory.iterdir()), ['input.json', 'policy.json'])
                return completed
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            actual = json.loads(out.read_text(encoding='utf-8'))
        self.audit(data, config, actual)
        return actual

    def audit(self, data, config, actual):
        scalar_config, scalar_actual = scalar_projection(config, actual)
        scalar_config['policy_tree']['execution']['strategy'] = 'temporal_first'
        scalar_actual['mode'] = 'temporal_first'
        for window in scalar_actual['windows']:
            window['strategy'] = 'temporal_first'
        validated = validate_result(data, scalar_config, scalar_actual)
        self.assertTrue(validated['valid'], json.dumps(validated['violations'][:5], indent=2))

        catalog = config['semantic_taxonomy']
        nodes = {node['id']: node for node in catalog['nodes']}
        labels = {label: node['id'] for node in nodes.values() for label in node.get('input_types', [])}
        def ancestors(category):
            chain = []
            while category:
                chain.append(category)
                category = nodes[category].get('parent')
            return chain
        chains = {category: ancestors(category) for category in nodes}
        source_depth = data['coverage']['leaf_depth']
        root_bounds = config['policy_tree']['root']
        for release in actual['releases']:
            self.assertNotIn('semantic_priority', release)
            for cell in release['cells']:
                self.assertNotIn('semantic_priority', cell)
                observed = [observation for batch in data['batches']
                            if release['start_ms'] <= batch['observed_at_ms'] < release['end_ms']
                            for observation in batch['observations']
                            if observation['cell_id'] >> (2 * (source_depth - cell['depth'])) == cell['cell_id']]
                semantic = cell['semantic']
                self.assertEqual(semantic['schema'], 'ump.semantic-release.v1')
                self.assertEqual((semantic['taxonomy_id'], semantic['taxonomy_version']),
                                 (catalog['id'], catalog['version']))
                self.assertEqual(cell['observation_contributions'], len(observed))
                selected = [item['category_id'] for item in semantic['categories']]
                self.assertEqual(len(selected), len(set(selected)))
                self.assertTrue(all(category in nodes for category in selected))
                self.assertFalse(any(a != b and a in chains[b] for a in selected for b in selected))
                self.assertTrue(all(sum(category in chains[labels[item['type']]] for category in selected) == 1
                                    for item in observed), 'Observed type omitted or represented twice')
                weighted, support = 0, []
                for item in semantic['categories']:
                    category = item['category_id']
                    matching = [observation for observation in observed
                                if category in chains[labels[observation['type']]]]
                    distinct = len({observation['id'] for observation in matching})
                    self.assertEqual(item['observation_contributions'], len(matching))
                    self.assertEqual(item['distinct_contributors'], distinct)
                    self.assertGreater(distinct, 0)
                    support.append(distinct)
                    weighted += len(matching) * nodes[category]['loss']
                values = {'min_category_distinct_contributors': min(support),
                          'semantic_max_loss': max(nodes[category]['loss'] for category in selected),
                          'semantic_mean_loss': weighted / len(observed)}
                for metric, expected in values.items():
                    self.assertTrue(math.isclose(semantic[metric], expected, rel_tol=1e-12, abs_tol=1e-12))
                    bound = root_bounds.get(metric, {})
                    self.assertGreaterEqual(expected, bound.get('min', -math.inf))
                    self.assertLessEqual(expected, bound.get('max', math.inf))
        if actual['mode'] != 'semantic_first':
            self.assertTrue(all('semantic_priority' not in window for window in actual['windows']))
            return
        execution = config['policy_tree']['execution']
        for window in actual['windows']:
            metadata = window['semantic_priority']
            self.assertEqual(metadata['secondary_strategy'], execution.get('semantic_secondary_strategy', 'temporal_first'))
            self.assertEqual(metadata['release_trigger'], execution.get('release_trigger', 'policy_satisfied'))
            matching = [r for r in actual['releases']
                        if (r['start_ms'], r['end_ms']) == (window['start_ms'], window['end_ms'])]
            maximum = max((cell['semantic']['semantic_max_loss'] for release in matching for cell in release['cells']),
                          default=None)
            self.assertEqual(metadata['actual_max_loss'], maximum)
            self.assertIsInstance(metadata['policy_satisfied_release'], bool)
            if maximum is not None:
                self.assertGreaterEqual(metadata['selected_max_loss_ceiling'], maximum)

    def test_default_releases_generalized_full_cut_at_first_probe(self):
        data = source(generalized_people())
        for secondary in (None, 'temporal_first', 'spatial_first'):
            with self.subTest(secondary=secondary):
                actual = self.run_core(data, policy(secondary=secondary))
                first = actual['releases'][0]
                self.assertEqual((first['start_ms'], first['end_ms'], first['sealed_at_ms']), (0, 400, 400))
                self.assertEqual(categories(first['cells'][0]), {'road_user': 6})
                metadata = actual['windows'][0]['semantic_priority']
                self.assertEqual(metadata['selected_max_loss_ceiling'], 1)
                self.assertFalse(metadata['terminal_fallback'])
                self.assertTrue(metadata['policy_satisfied_release'])

    def test_semantic_primary_selects_exact_parent_before_generalized_fine(self):
        rows = [item for cell in POSITIONS for item in people(cell, {
            'adult_pedestrian': 4, 'adult_cyclist': 2, 'child_cyclist': 2})]
        for secondary in ('temporal_first', 'spatial_first'):
            with self.subTest(secondary=secondary):
                actual = self.run_core(source(rows), policy(secondary=secondary))
                first = actual['releases'][0]
                self.assertEqual(first['end_ms'], 400)
                self.assertEqual([cell['cell_id'] for cell in first['cells']], [12])
                self.assertEqual(categories(first['cells'][0]),
                                 {'adult_pedestrian': 16, 'adult_cyclist': 8, 'child_cyclist': 8})
                self.assertEqual(first['cells'][0]['semantic']['semantic_max_loss'], 0)

    def test_priority_secondaries_choose_parent_now_or_exact_fine_after_arrivals(self):
        initial = [item for cell in (48, 49) for item in people(cell, {f'adult_{family}': 4 for family in FAMILIES})]
        arrived = [item for cell in (48, 49) for item in people(cell, {f'adult_{family}': 5 for family in FAMILIES})]
        data = source(lambda time: initial if time < 600 else arrived)
        temporal = self.run_core(data, policy(secondary='temporal_first', trigger='priority_satisfied'))
        spatial = self.run_core(data, policy(secondary='spatial_first', trigger='priority_satisfied'))
        self.assertEqual(temporal['releases'][0]['end_ms'], 400)
        self.assertEqual([cell['cell_id'] for cell in temporal['releases'][0]['cells']], [12])
        self.assertEqual(spatial['releases'][0]['end_ms'], 700)
        self.assertEqual(spatial['releases'][0]['start_ms'], 0)
        self.assertEqual([cell['cell_id'] for cell in spatial['releases'][0]['cells']], [48, 49])
        self.assertTrue(all(cell['semantic']['semantic_max_loss'] == 0 for cell in spatial['releases'][0]['cells']))
        self.assertFalse(spatial['windows'][0]['semantic_priority']['policy_satisfied_release'])

    def test_default_overrides_spatial_preference_wait_when_exact_parent_already_passes(self):
        rows = [item for cell in (48, 49) for item in people(cell, {f'adult_{family}': 4 for family in FAMILIES})]
        actual = self.run_core(source(rows), policy(secondary='spatial_first'))
        self.assertEqual(actual['releases'][0]['end_ms'], 400)
        self.assertEqual([cell['cell_id'] for cell in actual['releases'][0]['cells']], [12])
        self.assertTrue(actual['windows'][0]['semantic_priority']['policy_satisfied_release'])

    def test_priority_satisfied_retains_explicit_waiting_baseline(self):
        for secondary in ('temporal_first', 'spatial_first'):
            with self.subTest(secondary=secondary):
                actual = self.run_core(source(generalized_people()),
                                       policy(secondary=secondary, trigger='priority_satisfied'))
                self.assertEqual([(release['start_ms'], release['end_ms']) for release in actual['releases']], [(0, 800)])
                self.assertTrue(actual['windows'][0]['semantic_priority']['terminal_fallback'])
                self.assertFalse(actual['windows'][0]['semantic_priority']['policy_satisfied_release'])

    def test_intermediate_pedestrian_cyclist_scooter_categories_precede_road_user(self):
        actual = self.run_core(source(intermediate_people()), policy())
        first = actual['releases'][0]
        self.assertEqual(first['end_ms'], 400)
        self.assertEqual(categories(first['cells'][0]), {family: 5 for family in FAMILIES})
        self.assertEqual(first['cells'][0]['semantic']['semantic_max_loss'], .5)
        self.assertEqual(first['cells'][0]['semantic']['semantic_mean_loss'], .5)
        metadata = actual['windows'][0]['semantic_priority']
        self.assertEqual(metadata['selected_max_loss_ceiling'], .5)
        self.assertEqual(metadata['attempted_ceilings'], 2)
        self.assertFalse(metadata['terminal_fallback'])

    def test_allowed_maximum_one_does_not_force_all_categories_to_road_user(self):
        rows = people(48, {'adult_pedestrian': 5})
        rows += people(49, {f'adult_{family}': 2 for family in FAMILIES})
        actual = self.run_core(source(rows), policy(side=20))
        first = actual['releases'][0]
        self.assertEqual([categories(cell) for cell in first['cells']], [{'adult_pedestrian': 5}, {'road_user': 6}])
        self.assertEqual(actual['windows'][0]['semantic_priority']['actual_max_loss'], 1)

    def test_partial_legal_cut_stays_private_until_terminal_endpoint(self):
        rows = people(48, {'adult_pedestrian': 5}) + people(49, {'adult_cyclist': 1})
        actual = self.run_core(source(rows), policy(side=20))
        self.assertEqual(len(actual['windows']), 1)
        self.assertEqual([(release['start_ms'], release['end_ms']) for release in actual['releases']], [(0, 800)])
        self.assertEqual([cell['cell_id'] for cell in actual['releases'][0]['cells']], [48])
        self.assertEqual(categories(actual['releases'][0]['cells'][0]), {'adult_pedestrian': 5})
        self.assertFalse(actual['windows'][0]['semantic_priority']['policy_satisfied_release'])

    def test_hard_semantic_spatial_mean_and_regional_bounds_remain_mandatory(self):
        for loss in (0, .4):
            with self.subTest(loss=loss):
                self.assertEqual(self.run_core(source(intermediate_people()), policy(loss=loss))['releases'], [])
        config = policy()
        config['policy_tree']['root']['semantic_mean_loss'] = {'max': .4}
        self.assertEqual(self.run_core(source(intermediate_people()), config)['releases'], [])
        rows = [item for cell in (48, 49) for item in people(cell, {'adult_pedestrian': 3})]
        self.assertEqual(self.run_core(source(rows), policy(loss=0, side=20))['releases'], [])
        config = policy()
        config['policy_tree']['regions'] = ['exact-region']
        config['policy_regions'] = [{'id': 'exact-region', 'type': 'crossing', 'x': 0, 'y': 0,
                                    'width': 20, 'height': 20,
                                    'requirements': {'semantic_max_loss': {'max': 0}}}]
        self.assertEqual(self.run_core(source(intermediate_people()), config)['releases'], [])

    def test_hard_age_or_duration_limit_stops_priority_waiting(self):
        for metric in ('age_at_evaluation_ms', 'window_duration_ms'):
            with self.subTest(metric=metric):
                config = policy(secondary='spatial_first', trigger='priority_satisfied')
                config['policy_tree']['root'][metric] = {'max': 400}
                actual = self.run_core(source(generalized_people()), config)
                self.assertEqual(actual['releases'][0]['end_ms'], 400)
                self.assertTrue(actual['windows'][0]['semantic_priority']['terminal_fallback'])

    def test_missing_or_unavailable_measurements_never_form_a_complete_release(self):
        for absent in ('missing', 'unavailable'):
            with self.subTest(absent=absent):
                data = source(generalized_people(), **{absent: (200,)})
                actual = self.run_core(data, policy())
                self.assertEqual(actual['windows'][0]['completion_reason'], 'coverage_unavailable')
                self.assertFalse(any(release['start_ms'] <= 200 < release['end_ms'] for release in actual['releases']))
                self.assertFalse(actual['windows'][0]['semantic_priority']['policy_satisfied_release'])
                self.assertFalse(actual['windows'][0]['semantic_priority']['terminal_fallback'])

    def test_eof_flushes_only_actual_observed_history(self):
        actual = self.run_core(source(generalized_people(), end=600),
                               policy(secondary='spatial_first', trigger='priority_satisfied'))
        self.assertEqual([(release['start_ms'], release['end_ms'], release['sealed_at_ms'])
                          for release in actual['releases']], [(0, 600, 600)])
        self.assertEqual(actual['windows'][0]['completion_reason'], 'end_of_stream')
        self.assertEqual(actual['input_observation_contributions'], 30)
        self.assertEqual(actual['releases'][0]['cells'][0]['observation_contributions'], 30)

    def test_same_input_repeats_and_retires_every_observation_once(self):
        data, config = source(generalized_people(), end=1600), policy(secondary='spatial_first')
        first, second = self.run_core(data, config), self.run_core(data, config)
        self.assertEqual({key: value for key, value in first.items() if key != 'runtime'},
                         {key: value for key, value in second.items() if key != 'runtime'})
        self.assertEqual([(release['start_ms'], release['end_ms']) for release in first['releases']],
                         [(0, 400), (400, 800), (800, 1200), (1200, 1600)])
        self.assertEqual(sum(cell['observation_contributions'] for release in first['releases'] for cell in release['cells']),
                         sum(len(batch['observations']) for batch in data['batches']))

    def test_invalid_settings_and_local_semantic_coordination_reject_before_output(self):
        data = source(generalized_people())
        for key, values in (('release_trigger', ('unknown', True, '')),
                            ('semantic_secondary_strategy', ('semantic_first', True, ''))):
            for value in values:
                with self.subTest(key=key, value=value):
                    config = policy()
                    config['policy_tree']['execution'][key] = value
                    self.run_core(data, config, reject=True)
        local = policy(secondary='spatial_first')
        local['temporal_adaptation']['coordination'] = 'cell_local'
        self.run_core(data, local, reject=True)

    def test_cli_tf_sf_override_removes_only_semantic_secondary_and_preserves_bounds(self):
        # Each fine cell has four people, below support five. Only the 40-m
        # parent can pass. TF should merge at 400 ms; SF should wait to 800 ms.
        data = source([row for cell in (48, 49)
                       for row in people(cell, {'adult_pedestrian': 4})], end=1600)
        for mode, first_end in (('temporal_first', 400), ('spatial_first', 800)):
            for secondary in ('temporal_first', 'spatial_first'):
                with self.subTest(mode=mode, secondary=secondary):
                    config = policy(secondary=secondary, loss=0, maximum=800)
                    original = deepcopy(config)
                    actual = self.run_core(data, config, mode=mode)
                    self.assertEqual(config, original)
                    self.assertEqual(actual['mode'], mode)
                    self.assertEqual(actual['releases'][0]['end_ms'], first_end)
                    parent = actual['releases'][0]['cells'][0]
                    self.assertEqual((parent['cell_id'], parent['width']), (12, 40))
                    self.assertEqual(categories(parent), {'adult_pedestrian': 8})
                    for window in actual['windows']:
                        for cell in window['cells']:
                            checks = {check['metric']: check for check in cell['checks']}
                            self.assertEqual(checks['min_category_distinct_contributors']['min'], 5)
                            self.assertEqual(checks['semantic_max_loss']['max'], 0)
                            self.assertEqual(checks['cell_side_m']['max'], 40)
                            self.assertEqual(checks['window_duration_ms']['max'], 800)
                            self.assertEqual(checks['age_at_evaluation_ms']['max'], 800)
            # A smaller hard cap must still prohibit the only passing parent.
            strict = policy(secondary='spatial_first', loss=0, side=20, maximum=800)
            rejected_cut = self.run_core(data, strict, mode=mode)
            self.assertEqual(rejected_cut['releases'], [])

    def test_cli_tf_sf_override_cannot_hide_invalid_original_semantic_settings(self):
        data = source(generalized_people())
        for mode in ('temporal_first', 'spatial_first'):
            for key in ('semantic_secondary_strategy', 'release_trigger'):
                with self.subTest(mode=mode, key=key):
                    malformed = policy(secondary='spatial_first')
                    malformed['policy_tree']['execution'][key] = 'unsupported'
                    failed = self.run_core(data, malformed, reject=True, mode=mode)
                    self.assertIn('Unsupported policy_tree.execution.' + key, failed.stderr)

    def test_independent_audit_detects_tampered_semantic_counts(self):
        data, config = source(intermediate_people()), policy()
        actual = self.run_core(data, config)
        damaged = deepcopy(actual)
        damaged['releases'][0]['cells'][0]['semantic']['categories'][0]['distinct_contributors'] += 1
        with self.assertRaises(AssertionError):
            self.audit(data, config, damaged)


if __name__ == '__main__':
    unittest.main()
