"""Real-core Semantic First acceptance using independent raw-data references.

The old scalar oracle is given an explicit TF strategy-only projection after
semantic constraints are removed. It checks counts/geometry/coverage/retirement,
not the new adaptation priority. Separate hand-worked cases assert that priority.
Every actual cut is also matched against the independent complete tiny reference;
the fixed receiver query bank uses only recipient releases for its predictions.
These checks do not establish a globally optimal online schedule or privacy gain.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / 'tools/evaluation'))
from oracle import validate_result
from run_semantic_priority_study import audit_choices, scalar_projection
from semantic_queries import evaluate_queries

BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT / 'simulator/build/AggregationReplay'))
POSITIONS = {48: (1, 1), 49: (21, 1), 50: (1, 21), 51: (21, 21)}


def taxonomy():
    return {'id': 'semantic-priority', 'version': '1', 'nodes': [
        {'id': 'road_user', 'loss': 1},
        {'id': 'pedestrian', 'parent': 'road_user', 'loss': 0, 'input_types': ['pedestrian']},
        {'id': 'cyclist', 'parent': 'road_user', 'loss': .5},
        {'id': 'adult_cyclist', 'parent': 'cyclist', 'loss': 0, 'input_types': ['adult_cyclist']},
        {'id': 'child_cyclist', 'parent': 'cyclist', 'loss': 0, 'input_types': ['child_cyclist']}]}


def observation(identity, kind, cell=48):
    x, y = POSITIONS[cell]
    return {'id': identity, 'type': kind, 'cell_id': cell, 'x': x, 'y': y}


def density(multiplier):
    return [observation(f'{cell}/{kind}/{index}', kind, cell)
            for cell in POSITIONS
            for kind, count in [('pedestrian', 2 * multiplier), ('adult_cyclist', multiplier),
                                ('child_cyclist', multiplier)] for index in range(count)]


def replay(rows, *, end=1600):
    samples = []
    for time in range(100, end, 100):
        observations = rows(time) if callable(rows) else rows
        if observations == 'missing':
            continue
        samples.append({'sequence': time // 100, 'observed_at_ms': time,
                        'status': 'unavailable' if observations is None else 'measured',
                        'observations': [] if observations is None else deepcopy(observations)})
    return {'schema': 'ump.observation-replay.v1', 'run_id': 'semantic-first-acceptance',
            'sensor_id': 'agbs', 'coverage': {'x': 0, 'y': 0, 'width': 80, 'height': 80, 'leaf_depth': 2},
            'sampling_period_ms': 100, 'end_ms': end, 'batches': samples}


def policy(*, loss=1, side=40, minimum_depth=1, maximum=800):
    return {'application_id': 'semantic-first-acceptance', 'window_ms': 400,
            'max_observations_per_window': 1000000,
            'history': {'retention_ms': 2000, 'max_bins': 32, 'max_observations': 100000,
                        'max_identity_bytes': 16000000, 'max_buckets': 128},
            'spatial_selection': {'min_depth': minimum_depth, 'max_evaluations': 4096,
                                  'preserve_valid_descendants': True},
            'temporal_adaptation': {'extension_step_ms': 100, 'max_window_ms': maximum,
                                    'max_evaluations': 16, 'coordination': 'common_window'},
            'semantic_taxonomy': taxonomy(),
            'policy_tree': {'id': 'semantic-first-acceptance-policy', 'version': '1', 'max_nodes': 65536,
                            'execution': {'publication_model': 'private_final_snapshot', 'strategy': 'semantic_first',
                                          'release_trigger': 'priority_satisfied'},
                            'root': {'distinct_contributors': {'min': 1},
                                     'cell_side_m': {'min': 1.25, 'max': side},
                                     'window_duration_ms': {'max': maximum},
                                     'age_at_evaluation_ms': {'max': maximum},
                                     'min_category_distinct_contributors': {'min': 5},
                                     'semantic_max_loss': {'max': loss}}, 'regions': []},
            'policy_regions': []}


def projected_scalar(config, result):
    config, result = scalar_projection(config, result)
    # Explicit legacy validation projection only. No numeric bounds, selected
    # cells, source records, intervals or recipient data change here.
    if config['policy_tree']['execution']['strategy'] == 'semantic_first':
        config['policy_tree']['execution']['strategy'] = 'temporal_first'
    if result['mode'] == 'semantic_first':
        result['mode'] = 'temporal_first'
    for window in result['windows']:
        if window.get('strategy') == 'semantic_first':
            window['strategy'] = 'temporal_first'
    return config, result


def bins(cell):
    return {row['category_id']: row['distinct_contributors'] for row in cell['semantic']['categories']}


class SemanticFirstReplayTests(unittest.TestCase):
    maxDiff = None

    def run_core(self, data, config, mode='semantic_first', *, reject=False, audit=True):
        with tempfile.TemporaryDirectory(prefix='ump-semantic-first-') as temporary:
            directory = Path(temporary)
            inp, cfg, out = (directory / name for name in ('input.json', 'policy.json', 'result.json'))
            inp.write_text(json.dumps(data), encoding='utf-8')
            cfg.write_text(json.dumps(config), encoding='utf-8')
            completed = subprocess.run([str(BINARY), '--input', str(inp), '--config', str(cfg), '--mode', mode,
                                        '--output', str(out)], capture_output=True, text=True, timeout=30)
            if reject:
                self.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                self.assertFalse(out.exists(), 'Rejected replay wrote a result')
                self.assertEqual(sorted(p.name for p in directory.iterdir()), ['input.json', 'policy.json'])
                return completed
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = json.loads(out.read_text(encoding='utf-8'))
        if audit:
            self.audit(data, config, result)
        return result

    def audit(self, data, config, result):
        scalar_config, scalar_result = projected_scalar(config, result)
        validation = validate_result(data, scalar_config, scalar_result)
        self.assertTrue(validation['valid'], json.dumps(validation['violations'][:5], indent=2))
        # Independent reference reconstructs raw identities/classes and all legal
        # complete antichains. Matching includes counts, geometry and all losses.
        choices = audit_choices(data, config, result)
        self.assertEqual(len(choices), len(result['windows']))
        for choice in choices:
            self.assertGreater(choice['candidate_count'], 0)
        for release in result['releases']:
            self.assertNotIn('semantic_priority', release, 'Private preference diagnostics leaked to the recipient')
            for cell in release['cells']:
                self.assertNotIn('semantic_priority', cell)
        for window in result['windows']:
            if result['mode'] != 'semantic_first':
                self.assertNotIn('semantic_priority', window)
                continue
            metadata = window['semantic_priority']
            self.assertEqual(metadata['schema'], 'ump.semantic-priority.v1')
            self.assertEqual(metadata['secondary_strategy'], 'temporal_first')
            self.assertEqual(metadata['preferred_max_loss'], 0)
            self.assertGreaterEqual(metadata['attempted_ceilings'], 1)
            corresponding = [r for r in result['releases']
                             if r['start_ms'] == window['start_ms'] and r['end_ms'] == window['end_ms']]
            expected = max((c['semantic']['semantic_max_loss']
                            for release in corresponding for c in release['cells']), default=None)
            self.assertEqual(metadata['actual_max_loss'], expected)
            if expected is not None:
                self.assertGreaterEqual(metadata['selected_max_loss_ceiling'], expected)
        if data['end_ms'] % 800 == 0:
            for duration in (400, 800):
                evaluate_queries(data, config, result['releases'], window_ms=duration)
        return choices

    def test_medium_density_preserves_exact_categories_by_spatial_merge_at_first_probe(self):
        data, config = replay(density(2)), policy(loss=1)
        actual = self.run_core(data, config)
        self.assertEqual(actual['mode'], 'semantic_first')
        first = actual['releases'][0]
        self.assertEqual((first['start_ms'], first['end_ms'], first['sealed_at_ms']), (0, 400, 400))
        self.assertEqual([c['cell_id'] for c in first['cells']], [12])
        self.assertEqual(bins(first['cells'][0]), {'pedestrian': 16, 'adult_cyclist': 8, 'child_cyclist': 8})
        self.assertEqual(first['cells'][0]['semantic']['semantic_max_loss'], 0)
        self.assertEqual(actual['windows'][0]['semantic_priority']['attempted_ceilings'], 1)
        self.assertFalse(actual['windows'][0]['semantic_priority']['terminal_fallback'])
        for old_mode in ('temporal_first', 'spatial_first'):
            old = self.run_core(data, config, old_mode)
            self.assertEqual(old['releases'][0]['end_ms'], 400)
            self.assertEqual([c['cell_id'] for c in old['releases'][0]['cells']], [48, 49, 50, 51])
            self.assertTrue(all(bins(c) == {'road_user': 8} for c in old['releases'][0]['cells']))
        queries = evaluate_queries(data, config, actual['releases'], window_ms=400)
        self.assertEqual(queries['by_scale']['40']['by_lag_ms']['0']['summary']['interior']['query_coverage'], 1)
        self.assertEqual(queries['by_scale']['20']['by_lag_ms']['0']['summary']['interior']['query_coverage'], 0)

    def test_high_density_keeps_exact_fine_cells_without_waiting(self):
        data, config = replay(density(5)), policy()
        actual = self.run_core(data, config)
        self.assertEqual(actual['releases'][0]['end_ms'], 400)
        for release in actual['releases']:
            self.assertEqual([c['cell_id'] for c in release['cells']], [48, 49, 50, 51])
            for cell in release['cells']:
                self.assertEqual(bins(cell), {'pedestrian': 10, 'adult_cyclist': 5, 'child_cyclist': 5})
                self.assertEqual(cell['semantic']['semantic_max_loss'], 0)

    def test_low_static_density_waits_then_uses_smallest_legal_terminal_loss(self):
        data, config = replay(density(1)), policy()
        actual = self.run_core(data, config)
        self.assertEqual(actual['windows'][0]['end_ms'], 800)
        self.assertEqual(actual['releases'][0]['end_ms'], 800)
        self.assertEqual(actual['windows'][0]['semantic_priority']['selected_max_loss_ceiling'], .5)
        self.assertEqual(actual['windows'][0]['semantic_priority']['attempted_ceilings'], 2)
        self.assertTrue(actual['windows'][0]['semantic_priority']['terminal_fallback'])
        for release in actual['releases']:
            self.assertEqual([c['cell_id'] for c in release['cells']], [12])
            semantic = release['cells'][0]['semantic']
            self.assertEqual(bins(release['cells'][0]), {'pedestrian': 8, 'cyclist': 8})
            self.assertEqual((semantic['semantic_max_loss'], semantic['semantic_mean_loss']), (.5, .25))

    def test_temporal_arrivals_unlock_exact_detail_without_resetting_interval_start(self):
        initial = [observation(f'{kind}/{i}', kind)
                   for kind in ('pedestrian', 'adult_cyclist', 'child_cyclist') for i in range(4)]
        arrived = initial + [observation(f'{kind}/4', kind)
                             for kind in ('pedestrian', 'adult_cyclist', 'child_cyclist')]
        data, config = replay(lambda t: initial if t < 400 else arrived, end=800), policy()
        actual = self.run_core(data, config)
        first = actual['releases'][0]
        self.assertEqual((first['start_ms'], first['end_ms'], first['sealed_at_ms']), (0, 500, 500))
        self.assertEqual([c['cell_id'] for c in first['cells']], [48])
        self.assertEqual(bins(first['cells'][0]), {'pedestrian': 5, 'adult_cyclist': 5, 'child_cyclist': 5})
        self.assertEqual(first['cells'][0]['observation_contributions'], 51)
        self.assertEqual(first['cells'][0]['semantic']['semantic_max_loss'], 0)

    def test_hard_max_and_mean_loss_constraints_remain_mandatory(self):
        data = replay(density(1), end=800)
        for config in (policy(loss=0), policy(loss=.4)):
            with self.subTest(loss=config['policy_tree']['root']['semantic_max_loss']):
                self.assertEqual(self.run_core(data, config)['releases'], [])
        config = policy()
        config['policy_tree']['root']['semantic_mean_loss'] = {'max': .2}
        self.assertEqual(self.run_core(data, config)['releases'], [])

    def test_time_limit_stops_preference_waiting_without_relaxing_the_policy(self):
        data, config = replay(density(1)), policy()
        config['policy_tree']['root']['window_duration_ms'] = {'max': 400}
        config['policy_tree']['root']['age_at_evaluation_ms'] = {'max': 400}
        actual = self.run_core(data, config)
        self.assertEqual(actual['releases'][0]['end_ms'], 400)
        self.assertTrue(actual['windows'][0]['semantic_priority']['terminal_fallback'])
        self.assertTrue(all(r['end_ms'] - r['start_ms'] <= 400 for r in actual['releases']))
        self.assertEqual(bins(actual['releases'][0]['cells'][0]), {'pedestrian': 8, 'cyclist': 8})

    def test_partial_zero_loss_cut_waits_and_full_terminal_cut_retains_every_class(self):
        rows = [row for row in density(5) if row['cell_id'] == 48]
        rows += [observation(f'rare/{kind}/{i}', kind, 49)
                 for kind, count in [('pedestrian', 2), ('adult_cyclist', 2), ('child_cyclist', 1)]
                 for i in range(count)]
        data, config = replay(rows, end=800), policy(side=20)
        actual = self.run_core(data, config)
        self.assertEqual(len(actual['releases']), 1)
        first = actual['releases'][0]
        self.assertEqual((first['start_ms'], first['end_ms']), (0, 800))
        self.assertEqual([c['cell_id'] for c in first['cells']], [48, 49])
        self.assertEqual(bins(first['cells'][0]), {'pedestrian': 10, 'adult_cyclist': 5, 'child_cyclist': 5})
        self.assertEqual(bins(first['cells'][1]), {'road_user': 5})
        self.assertEqual(sum(c['observation_contributions'] for c in first['cells']), 175)
        self.assertEqual(actual['windows'][0]['semantic_priority']['attempted_ceilings'], 3)

    def test_intersected_region_enforces_hard_detail_for_the_entire_parent(self):
        data, config = replay(density(1), end=800), policy()
        config['policy_tree']['regions'] = ['strict-detail']
        config['policy_regions'] = [{'id': 'strict-detail', 'type': 'crossing', 'x': 0, 'y': 0,
                                    'width': 20, 'height': 20,
                                    'requirements': {'semantic_max_loss': {'max': 0}}}]
        self.assertEqual(self.run_core(data, config)['releases'], [])

    def test_spatial_region_and_depth_limits_cannot_be_relaxed_by_priority(self):
        data = replay(density(2), end=800)
        configs = [policy(side=20), policy(minimum_depth=2)]
        regional = policy()
        regional['policy_tree']['regions'] = ['small-cell']
        regional['policy_regions'] = [{'id': 'small-cell', 'type': 'crossing', 'x': 0, 'y': 0,
                                     'width': 20, 'height': 20,
                                     'requirements': {'cell_side_m': {'max': 20}}}]
        configs.append(regional)
        for config in configs:
            with self.subTest(config=config):
                actual = self.run_core(data, config)
                self.assertEqual(actual['releases'][0]['end_ms'], 800)
                self.assertTrue(all(c['width'] == 20 and bins(c) == {'road_user': 8}
                                    for r in actual['releases'] for c in r['cells']))

    def test_incomplete_measurements_never_trigger_positive_loss_fallback(self):
        for absent in ('missing', None):
            with self.subTest(absent=absent):
                data = replay(lambda time: absent if time == 200 else density(2), end=800)
                actual = self.run_core(data, policy())
                self.assertTrue(all(release['start_ms'] >= 400 for release in actual['releases']))
                self.assertEqual(actual['windows'][0]['end_ms'], 400)
                self.assertEqual(actual['windows'][0]['completion_reason'], 'coverage_unavailable')
                self.assertEqual(actual['windows'][0]['semantic_priority']['attempted_ceilings'], 1)
                self.assertFalse(actual['windows'][0]['semantic_priority']['terminal_fallback'])

    def test_eof_uses_actual_terminal_time_and_never_invents_future_samples(self):
        data, config = replay(density(1), end=600), policy()
        actual = self.run_core(data, config)
        self.assertEqual(len(actual['windows']), 1)
        self.assertEqual((actual['windows'][0]['start_ms'], actual['windows'][0]['end_ms']), (0, 600))
        self.assertEqual(actual['releases'][0]['sealed_at_ms'], 600)
        self.assertEqual(bins(actual['releases'][0]['cells'][0]), {'pedestrian': 8, 'cyclist': 8})
        exact = self.run_core(replay(density(2), end=300), config)
        self.assertEqual((exact['releases'][0]['end_ms'], exact['releases'][0]['sealed_at_ms']), (300, 300))
        self.assertEqual(exact['releases'][0]['cells'][0]['semantic']['semantic_max_loss'], 0)

    def test_complete_parent_cut_is_exclusive_and_never_reuses_retired_support(self):
        data, config = replay(density(2)), policy()
        actual = self.run_core(data, config)
        self.assertEqual([(r['start_ms'], r['end_ms']) for r in actual['releases']],
                         [(0, 400), (400, 800), (800, 1200), (1200, 1600)])
        expected = sum(len(b['observations']) for b in data['batches'])
        self.assertEqual(sum(c['observation_contributions'] for r in actual['releases'] for c in r['cells']), expected)
        for release in actual['releases']:
            self.assertEqual([c['cell_id'] for c in release['cells']], [12])
        damaged = deepcopy(actual)
        damaged['releases'][0]['cells'].append(deepcopy(damaged['releases'][0]['cells'][0]))
        projected_config, projected_result = projected_scalar(config, damaged)
        self.assertFalse(validate_result(data, projected_config, projected_result)['valid'])

    def test_missing_taxonomy_and_local_coordination_fail_before_output(self):
        data = replay(density(2), end=800)
        no_taxonomy = policy()
        no_taxonomy.pop('semantic_taxonomy')
        for metric in ('min_category_distinct_contributors', 'semantic_max_loss'):
            no_taxonomy['policy_tree']['root'].pop(metric)
        self.run_core(data, no_taxonomy, reject=True)
        # A CLI override cannot hide a malformed declared semantic strategy.
        self.run_core(data, no_taxonomy, 'temporal_first', reject=True)
        no_taxonomy['policy_tree']['execution']['strategy'] = 'temporal_first'
        self.run_core(data, no_taxonomy, reject=True)
        local = policy()
        local['temporal_adaptation']['coordination'] = 'cell_local'
        self.run_core(data, local, reject=True)
        no_temporal = policy()
        no_temporal.pop('temporal_adaptation')
        self.run_core(data, no_temporal, reject=True)

    def test_cli_override_and_omitted_common_coordination_are_explicit(self):
        data, config = replay(density(2), end=800), policy()
        config['policy_tree']['execution']['strategy'] = 'temporal_first'
        config['temporal_adaptation'].pop('coordination')
        actual = self.run_core(data, config)
        self.assertEqual(actual['parameters']['coordination'], 'common_window')
        self.assertEqual(actual['mode'], 'semantic_first')
        self.assertEqual(actual['releases'][0]['cells'][0]['semantic']['semantic_max_loss'], 0)
        self.assertIn('strategy: semantic_first', actual['configuration_yaml'])

    def test_invalid_late_input_is_rejected_before_any_complete_output(self):
        data = replay(density(5))
        for mutate in ('unknown-type', 'conflicting-class', 'invalid-position', 'duplicate-identity'):
            with self.subTest(mutation=mutate):
                damaged = deepcopy(data)
                last = damaged['batches'][-1]['observations']
                if mutate == 'unknown-type':
                    last[0]['type'] = 'unknown-class'
                elif mutate == 'conflicting-class':
                    last[0]['type'] = 'adult_cyclist'
                elif mutate == 'invalid-position':
                    last[0]['x'] = 81
                else:
                    last.append(deepcopy(last[0]))
                self.run_core(damaged, policy(), reject=True)

    def test_empty_measured_input_retires_without_creating_semantic_categories(self):
        actual = self.run_core(replay([], end=800), policy())
        self.assertEqual(actual['releases'], [])
        self.assertEqual(actual['input_observation_contributions'], 0)
        self.assertEqual(actual['accounted_observation_contributions'], 0)


if __name__ == '__main__':
    unittest.main()
