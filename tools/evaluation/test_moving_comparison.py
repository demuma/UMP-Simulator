"""Independent bounded moving-pilot audits with actual C++ replay executions.

The D6 source below is a hand-built test fixture, not captured movement evidence.
It deliberately separates policy support, truthful category unions and adaptation
preference, then tampers serialized outputs to exercise audit failures.
"""
from copy import deepcopy
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', '/Users/maxdemu/Developer/UMP-Simulator'))
sys.path.insert(0, str(ROOT / 'tools/evaluation'))
import run_moving_comparison as moving
from capture_simulator import cell_for
from occupancy import evaluate as eventual_evaluate
from online_occupancy import evaluate as deadline_evaluate

BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT / 'simulator/build/AggregationReplay'))
LABELS = ('Child Pedestrian', 'Senior Pedestrian', 'Adult Pedestrian',
          'Senior Cyclist', 'Adult Cyclist', 'Adult E-Scooter Driver', 'Adult Cargo Cyclist')


def tiny_d6_source():
    batches = []
    for time in range(100, 2000, 100):
        rows = []
        for corner, (x, y) in enumerate(((.25, .25), (1.5, .25), (.25, 1.5), (1.5, 1.5))):
            for label in LABELS:
                for person in range(2):
                    # Displacement stays within the original finest cell.
                    xx = x + time / 100000
                    rows.append({'id': f'{corner}/{label}/{person}', 'type': label,
                                 'x': xx, 'y': y, 'cell_id': cell_for(xx, y)[0]})
        batches.append({'sequence': time // 100, 'observed_at_ms': time,
                        'status': 'measured', 'observations': rows})
    return {'schema': 'ump.observation-replay.v1', 'run_id': 'moving-audit-unit-fixture',
            'sensor_id': 'temporal-aggregation-agbs',
            'coverage': {'x': 0, 'y': 0, 'width': 80, 'height': 80, 'leaf_depth': 6},
            'sampling_period_ms': 100, 'end_ms': 2000, 'batches': batches}


def effective_config(config, mode, window):
    value = deepcopy(config)
    if mode != 'fixed':
        value['policy_tree']['execution']['strategy'] = mode
    if window is not None:
        value['window_ms'] = window
    return value


class MovingComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BINARY.is_file():
            raise RuntimeError(f'Build the actual AggregationReplay binary before this suite: {BINARY}')
        cls.temporary = tempfile.TemporaryDirectory(prefix='ump-moving-audit-')
        cls.directory = Path(cls.temporary.name)
        cls.replay = tiny_d6_source()
        cls.config = moving.policy()
        source, config = cls.directory / 'observations.json', cls.directory / 'policy.json'
        source.write_text(json.dumps(cls.replay), encoding='utf-8')
        config.write_text(json.dumps(cls.config), encoding='utf-8')
        cls.results = {}
        for identity, mode, depth, window in moving.VARIANTS:
            destination = cls.directory / f'{identity}.json'
            command = [str(BINARY), '--input', str(source), '--config', str(config),
                       '--mode', mode, '--output', str(destination)]
            if depth is not None:
                command.extend(['--fixed-depth', str(depth), '--fixed-window-ms', str(window)])
            completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
            if completed.returncode:
                raise AssertionError(f'{identity}: {completed.stdout}\n{completed.stderr}')
            cls.results[identity] = json.loads(destination.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_predeclared_variants_are_six_fixed_settings_and_three_priorities(self):
        self.assertEqual(len(moving.VARIANTS), 9)
        self.assertEqual({(depth, duration) for _, mode, depth, duration in moving.VARIANTS if mode == 'fixed'},
                         {(depth, duration) for depth in (1, 2, 3) for duration in (400, 1000)})
        self.assertEqual([mode for _, mode, _, _ in moving.VARIANTS if mode != 'fixed'],
                         ['temporal_first', 'spatial_first', 'semantic_first'])
        catalog = self.config['semantic_taxonomy']
        observed = [label for node in catalog['nodes'] for label in node.get('input_types', [])]
        self.assertEqual(set(observed), set(LABELS))
        self.assertEqual(len(observed), 7)
        self.assertEqual(self.config['policy_tree']['root']['min_category_distinct_contributors'], {'min': 5})
        self.assertEqual(self.config['temporal_adaptation']['max_window_ms'], 1000)

    def test_actual_binary_all_variants_pass_independent_scalar_and_semantic_audits(self):
        original = deepcopy(self.config)
        for identity, mode, _, window in moving.VARIANTS:
            result = self.results[identity]
            config = effective_config(self.config, mode, window)
            with self.subTest(identity=identity):
                scalar = moving.scalar_audit(self.replay, config, result)
                semantics = moving.semantic_audit(self.replay, self.config, result)
                self.assertTrue(scalar['valid'])
                self.assertEqual(semantics['status'], 'verified')
                self.assertGreater(semantics['published_cells'], 0)
                retained = sum(cell['observation_contributions'] for release in result['releases'] for cell in release['cells'])
                self.assertEqual(retained, 56 * 19)
                for release in result['releases']:
                    for cell in release['cells']:
                        self.assertIn('semantic', cell, 'Fixed baselines must also use the same semantic selector')
                        self.assertNotIn('semantic_priority', cell)
                        if mode == 'fixed':
                            self.assertEqual(cell['width'], {1: 40, 2: 20, 3: 10}[next(d for i, _, d, _ in moving.VARIANTS if i == identity)])
                    if mode == 'fixed':
                        self.assertEqual(release['end_ms'] - release['start_ms'], window)
        self.assertEqual(self.config, original, 'Independent audits must not mutate shared policy settings')

    def test_semantic_preference_changes_resolution_without_changing_hard_bounds(self):
        temporal = self.results['temporal_first']['releases'][0]
        semantic = self.results['semantic_first']['releases'][0]
        self.assertEqual((temporal['end_ms'], semantic['end_ms']), (400, 400))
        self.assertTrue(all(c['width'] == 1.25 and c['semantic']['semantic_max_loss'] == 1 for c in temporal['cells']))
        self.assertEqual(len(semantic['cells']), 1)
        self.assertEqual(semantic['cells'][0]['width'], 2.5)
        self.assertEqual(semantic['cells'][0]['semantic']['semantic_max_loss'], 0)
        self.assertEqual({b['category_id']: b['distinct_contributors'] for b in semantic['cells'][0]['semantic']['categories']},
                         {'child_pedestrian': 8, 'senior_pedestrian': 8, 'adult_pedestrian': 8,
                          'senior_cyclist': 8, 'adult_cyclist': 8, 'escooter': 8, 'adult_cargo_cyclist': 8})

    def test_raw_bin_counts_and_distinct_identity_union_tampering_are_detected(self):
        for key in ('observation_contributions', 'distinct_contributors'):
            changed = deepcopy(self.results['semantic_first'])
            changed['releases'][0]['cells'][0]['semantic']['categories'][0][key] += 1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'bin count/identity union'):
                moving.semantic_audit(self.replay, self.config, changed)

    def test_class_omission_overlap_unknown_and_repetition_are_detected(self):
        changes = {
            'omission': lambda bins: bins.pop(),
            'overlap': lambda bins: bins.append({'category_id': 'road_user', 'observation_contributions': 168, 'distinct_contributors': 56}),
            'unknown': lambda bins: bins[0].update(category_id='car'),
            'repetition': lambda bins: bins.append(deepcopy(bins[0])),
        }
        for name, mutate in changes.items():
            changed = deepcopy(self.results['semantic_first'])
            mutate(changed['releases'][0]['cells'][0]['semantic']['categories'])
            with self.subTest(name=name), self.assertRaises(ValueError):
                moving.semantic_audit(self.replay, self.config, changed)

    def test_summary_and_original_source_contribution_tampering_are_detected(self):
        for key in ('min_category_distinct_contributors', 'semantic_max_loss', 'semantic_mean_loss'):
            changed = deepcopy(self.results['semantic_first'])
            changed['releases'][0]['cells'][0]['semantic'][key] += .25
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'summary mismatch'):
                moving.semantic_audit(self.replay, self.config, changed)
        changed = deepcopy(self.results['semantic_first'])
        changed['releases'][0]['cells'][0]['observation_contributions'] += 1
        with self.assertRaisesRegex(ValueError, 'original support'):
            moving.semantic_audit(self.replay, self.config, changed)

    def test_semantic_schema_requires_string_version_and_exact_integer_bin_counts(self):
        for key in ('observation_contributions', 'distinct_contributors'):
            for wrong in (8.0, True, 0, -1, 2**53):
                changed = deepcopy(self.results['semantic_first'])
                changed['releases'][0]['cells'][0]['semantic']['categories'][0][key] = wrong
                with self.subTest(key=key, wrong=wrong), self.assertRaisesRegex(ValueError, 'positive exact integers'):
                    moving.semantic_audit(self.replay, self.config, changed)
        changed = deepcopy(self.results['semantic_first'])
        changed['releases'][0]['cells'][0]['semantic']['taxonomy_version'] = 1
        with self.assertRaisesRegex(ValueError, 'schema/catalog mismatch'):
            moving.semantic_audit(self.replay, self.config, changed)

    def test_hard_support_and_semantic_loss_bounds_remain_exclusion_conditions(self):
        higher_support = deepcopy(self.config)
        higher_support['policy_tree']['root']['min_category_distinct_contributors'] = {'min': 9}
        with self.assertRaisesRegex(ValueError, 'violates the policy'):
            moving.semantic_audit(self.replay, higher_support, self.results['semantic_first'])
        exact_only = deepcopy(self.config)
        exact_only['policy_tree']['root']['semantic_max_loss'] = {'max': 0}
        with self.assertRaisesRegex(ValueError, 'violates the policy'):
            moving.semantic_audit(self.replay, exact_only, self.results['temporal_first'])

    def test_catalog_source_label_and_identity_stability_tampering_are_detected(self):
        for key, wrong in (('schema', 'other'), ('taxonomy_id', 'other'), ('taxonomy_version', '2')):
            changed = deepcopy(self.results['semantic_first'])
            changed['releases'][0]['cells'][0]['semantic'][key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError):
                moving.semantic_audit(self.replay, self.config, changed)
        for wrong in ('Car', 'Adult Cyclist'):
            changed = deepcopy(self.replay)
            changed['batches'][1]['observations'][0]['type'] = wrong
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, 'Unmapped or unstable'):
                moving.semantic_audit(changed, self.config, self.results['semantic_first'])

    def test_scalar_geometry_and_count_tampering_are_detected(self):
        for key, value in (('x', 40), ('observation_contributions', 999)):
            changed = deepcopy(self.results['semantic_first'])
            changed['releases'][0]['cells'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                moving.scalar_audit(self.replay, effective_config(self.config, 'semantic_first', None), changed)

    def test_population_and_utility_summary_keep_missing_public_support_unknown(self):
        stats = moving.population(self.replay)
        self.assertEqual(stats['unique_sampled_road_users'], 56)
        self.assertEqual(stats['road_users_with_observed_displacement'], 56)
        self.assertEqual(stats['first_sample_types'], {label: 8 for label in LABELS})
        result = self.results['semantic_first']
        eventual = eventual_evaluate(self.replay, result, reference_cell_m=10, reference_window_ms=1000)
        deadlines = deadline_evaluate(self.replay, result, reference_cell_m=10, reference_window_ms=1000,
                                     deadline_lags_ms=(0, 200, 1000))
        summary = moving.summarize(self.replay, result, eventual, deadlines)
        self.assertEqual(summary['retained_fraction'], 1)
        self.assertEqual(summary['mean_cell_side_m'], 2.5)
        self.assertEqual(summary['mean_semantic_loss'], 0)
        # Only a tiny2.5m area is published; absent neighboring area does not
        # become an observed zero just because all source observations fit it.
        self.assertEqual(eventual['summary']['answered_queries'], 0)
        self.assertEqual(set(summary['occupancy_at_deadline']), {'0', '200', '1000'})


    def fixture_capture(self, directory, replay=None):
        """Minimal manifest fixture for orchestration, never real capture evidence."""
        directory.mkdir()
        moving.write_json(directory / 'observations.json', replay or self.replay)
        moving.write_json(directory / 'capture-proof.json', {
            'status': 'verified', 'classification': 'synthetic_unit_test_fixture',
            'end_ms': 2000, 'not_real_capture_evidence': True})
        moving.write_json(directory / 'capture-manifest.json', {
            'status': 'verified', 'classification': 'synthetic_unit_test_fixture',
            'artifacts_sha256': {name: moving.digest(directory / name)
                                for name in ('observations.json', 'capture-proof.json')}})
        return directory

    def test_complete_runner_archives_identical_source_policy_results_and_repeat(self):
        with tempfile.TemporaryDirectory(prefix='ump-moving-runner-fixture-') as temporary:
            directory = Path(temporary)
            capture = self.fixture_capture(directory / 'capture')
            output = directory / 'comparison'
            with contextlib.redirect_stdout(io.StringIO()):
                summaries = moving.run(capture, output, BINARY, timeout=30)
            self.assertEqual(set(summaries), {row[0] for row in moving.VARIANTS})
            self.assertEqual((output / 'observations.json').read_bytes(), (capture / 'observations.json').read_bytes())
            self.assertEqual(json.loads((output / 'policy.json').read_text()), self.config)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'verified')
            self.assertEqual(manifest['binary_sha256'], moving.digest(output / 'AggregationReplay.frozen'))
            self.assertEqual(len(manifest['commands']), 9)
            for relative, expected in manifest['artifacts_sha256'].items():
                self.assertEqual(moving.digest(output / relative), expected, relative)
            bundle = json.loads((output / 'bundle.json').read_text())
            self.assertEqual(bundle['observations'], 'observations.json')
            self.assertEqual(len(bundle['variants']), 9)
            for variant in bundle['variants']:
                self.assertTrue((output / variant['result']).is_file())
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(summary['scientific_repeats'], 0)
            self.assertEqual(summary['determinism_repeats'], 1)
            first = json.loads((output / 'semantic_first/result.json').read_text())
            second = json.loads((output / 'determinism-repeat.json').read_text())
            first.pop('runtime')
            second.pop('runtime')
            self.assertEqual(first, second)
            with self.assertRaises(FileExistsError):
                moving.run(capture, output, BINARY, timeout=30)

    def test_runner_rejects_tampered_capture_artifacts_before_creating_output(self):
        with tempfile.TemporaryDirectory(prefix='ump-moving-bad-source-') as temporary:
            directory = Path(temporary)
            for index, name in enumerate(('observations.json', 'capture-proof.json')):
                capture = self.fixture_capture(directory / f'capture{index}')
                with (capture / name).open('a') as file:
                    file.write(' ')
                output = directory / f'comparison{index}'
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    moving.run(capture, output, BINARY, timeout=30)
                self.assertFalse(output.exists())

    def test_runner_requires_declared_source_cadence_footprint_and_horizon(self):
        mutations = [lambda source: source.update(sampling_period_ms=50),
                     lambda source: source['coverage'].update(leaf_depth=5),
                     lambda source: source.update(end_ms=1000),
                     lambda source: source['batches'][0]['observations'][0].update(type='Car')]
        with tempfile.TemporaryDirectory(prefix='ump-moving-bad-geometry-') as temporary:
            directory = Path(temporary)
            for index, mutation in enumerate(mutations):
                source = deepcopy(self.replay)
                mutation(source)
                capture = self.fixture_capture(directory / f'capture{index}', source)
                output = directory / f'comparison{index}'
                with self.subTest(index=index), self.assertRaises(ValueError):
                    moving.run(capture, output, BINARY, timeout=30)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
