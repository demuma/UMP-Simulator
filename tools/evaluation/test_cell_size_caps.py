"""Independent cell-cap regression, using the actual C++ replay binary.

Fixtures are synthetic contract tests, never real moving-data evidence. Two
stationary four-person groups can satisfy support5 only if they may merge.
The groups straddle a requested spatial boundary, so changing the cap changes
feasibility without changing inputs, privacy support, semantics or time limits.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / 'tools/evaluation'))
import run_moving_comparison as moving
from capture_simulator import cell_for
from occupancy import evaluate as eventual_evaluate
from online_occupancy import evaluate as deadline_evaluate
from test_moving_comparison import tiny_d6_source

BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT / 'simulator/build/AggregationReplay'))


def boundary_source(second_x):
    batches = []
    for time in range(100, 2000, 100):
        rows = []
        for group, x in enumerate((.25, second_x)):
            for person in range(4):
                rows.append({'id': f'group{group}/person{person}',
                             'type': 'Adult Pedestrian', 'x': x, 'y': .25,
                             'cell_id': cell_for(x, .25)[0]})
        batches.append({'sequence': time // 100, 'observed_at_ms': time,
                        'status': 'measured', 'observations': rows})
    return {'schema': 'ump.observation-replay.v1', 'run_id': f'cell-cap-contract-{second_x}',
            'sensor_id': 'temporal-aggregation-agbs',
            'coverage': {'x': 0, 'y': 0, 'width': 80, 'height': 80, 'leaf_depth': 6},
            'sampling_period_ms': 100, 'end_ms': 2000, 'batches': batches}


class IndependentCellCapTests(unittest.TestCase):
    def test_old_default_policy_and_matrix_are_scientifically_unchanged(self):
        # Canonical SHA256 of the old, independently archived n500 policy.
        # Metadata on new capped policies may differ; cap40's contract must not.
        legacy_policy_sha256 = '2cf3be91142fb60b18b851ec59974161113b766319660f5c31e7a47067066578'
        # Explicit opt-in preserves this historical experiment's waiting rule.
        config = moving.policy()
        self.assertEqual(config['policy_tree']['execution'].pop('release_trigger'), 'priority_satisfied')
        actual = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(actual, legacy_policy_sha256)
        archived = ROOT / 'results/moving-replay-2026-10-21/n500/comparison/policy.json'
        if archived.is_file():
            self.assertEqual(config, json.loads(archived.read_text()))
        expected = [('fixed_10m_400ms', 'fixed', 3, 400), ('fixed_10m_1000ms', 'fixed', 3, 1000),
                    ('fixed_20m_400ms', 'fixed', 2, 400), ('fixed_20m_1000ms', 'fixed', 2, 1000),
                    ('fixed_40m_400ms', 'fixed', 1, 400), ('fixed_40m_1000ms', 'fixed', 1, 1000),
                    ('temporal_first', 'temporal_first', None, None),
                    ('spatial_first', 'spatial_first', None, None),
                    ('semantic_first', 'semantic_first', None, None)]
        self.assertEqual(moving.VARIANTS, expected)

    def test_invalid_caps_are_rejected_by_python_api(self):
        for invalid in (True, False, 5.0, 10.0, '10', 0, 2.5, 20, 80, None):
            with self.subTest(cap=invalid):
                with self.assertRaises(ValueError):
                    moving.policy(max_cell_side_m=invalid)
                with self.assertRaises(ValueError):
                    moving.variants_for_cap(invalid)

    def test_declared_variants_keep_nine_methods_and_only_legal_fixed_grids(self):
        expected = {40: ((10, 3), (20, 2), (40, 1)),
                    10: ((2.5, 5), (5, 4), (10, 3)),
                    5: ((1.25, 6), (2.5, 5), (5, 4))}
        self.assertEqual(moving.policy(), moving.policy(max_cell_side_m=40))
        self.assertEqual(moving.VARIANTS, moving.variants_for_cap(40))
        self.assertEqual(len({moving.policy(max_cell_side_m=cap)['policy_tree']['id'] for cap in expected}), 3,
                         'Different hard policies must have distinct identities')
        for cap, pairs in expected.items():
            with self.subTest(cap=cap):
                config = moving.policy(max_cell_side_m=cap)
                variants = moving.variants_for_cap(cap)
                self.assertEqual(len(variants), 9)
                self.assertEqual(config['spatial_selection']['min_depth'], {40: 1, 10: 3, 5: 4}[cap])
                self.assertEqual(config['policy_tree']['root']['cell_side_m'], {'min': 1.25, 'max': cap})
                self.assertEqual({(depth, duration) for _, mode, depth, duration in variants if mode == 'fixed'},
                                 {(depth, duration) for _, depth in pairs for duration in (400, 1000)})
                self.assertEqual([mode for _, mode, _, _ in variants if mode != 'fixed'],
                                 ['temporal_first', 'spatial_first', 'semantic_first'])
                old = moving.policy()
                for key in ('semantic_taxonomy', 'temporal_adaptation', 'history'):
                    self.assertEqual(config[key], old[key], f'{key} must not change to make the tighter cap pass')
                for key, bound in old['policy_tree']['root'].items():
                    if key != 'cell_side_m':
                        self.assertEqual(config['policy_tree']['root'][key], bound)

    def test_actual_tiny_d6_source_all_nine_methods_at_each_cap(self):
        with tempfile.TemporaryDirectory(prefix='ump-cell-cap-tiny-d6-') as temporary:
            directory = Path(temporary)
            replay = tiny_d6_source()
            source = directory / 'source.json'
            source.write_text(json.dumps(replay))
            for cap in (40, 10, 5):
                config = moving.policy(max_cell_side_m=cap)
                policy = directory / f'policy{cap}.json'
                policy.write_text(json.dumps(config))
                for identity, mode, depth, window in moving.variants_for_cap(cap):
                    with self.subTest(cap=cap, mode=identity):
                        destination = directory / f'cap{cap}-{identity}.json'
                        command = [str(BINARY), '--input', str(source), '--config', str(policy),
                                   '--mode', mode, '--output', str(destination)]
                        if depth is not None:
                            command += ['--fixed-depth', str(depth), '--fixed-window-ms', str(window)]
                        completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
                        self.assertEqual(completed.returncode, 0, completed.stderr)
                        result = json.loads(destination.read_text())
                        audit_config = deepcopy(config)
                        if mode != 'fixed':
                            audit_config['policy_tree']['execution']['strategy'] = mode
                        if window is not None:
                            audit_config['window_ms'] = window
                        self.assertTrue(moving.scalar_audit(replay, audit_config, result)['valid'])
                        self.assertEqual(moving.semantic_audit(replay, config, result)['status'], 'verified')
                        self.assertEqual(sum(c['observation_contributions'] for r in result['releases'] for c in r['cells']), 56 * 19)
                        self.assertTrue(all(c['width'] <= cap for r in result['releases'] for c in r['cells']))

    def test_actual_binary_prevents_both_10m_and_20m_rescue_above_cap(self):
        with tempfile.TemporaryDirectory(prefix='ump-cell-cap-independent-') as temporary:
            directory = Path(temporary)
            # The first pair can merge at10m, the second needs20m.
            for scenario, second_x, required_side in (('needs10', 5.25, 10), ('needs20', 10.25, 20)):
                replay = boundary_source(second_x)
                source = directory / f'{scenario}-source.json'
                source.write_text(json.dumps(replay))
                for cap in (40, 10, 5):
                    config = moving.policy(max_cell_side_m=cap)
                    policy = directory / f'{scenario}-cap{cap}-policy.json'
                    policy.write_text(json.dumps(config))
                    for identity, mode, depth, window in moving.variants_for_cap(cap):
                        with self.subTest(scenario=scenario, cap=cap, mode=identity):
                            destination = directory / f'{scenario}-cap{cap}-{identity}.json'
                            command = [str(BINARY), '--input', str(source), '--config', str(policy),
                                       '--mode', mode, '--output', str(destination)]
                            if depth is not None:
                                command += ['--fixed-depth', str(depth), '--fixed-window-ms', str(window)]
                            completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
                            self.assertEqual(completed.returncode, 0, completed.stderr)
                            result = json.loads(destination.read_text())
                            audit_config = deepcopy(config)
                            if mode != 'fixed':
                                audit_config['policy_tree']['execution']['strategy'] = mode
                            if window is not None:
                                audit_config['window_ms'] = window
                            self.assertTrue(moving.scalar_audit(replay, audit_config, result)['valid'])
                            self.assertEqual(moving.semantic_audit(replay, config, result)['status'], 'verified')
                            public = [cell for release in result['releases'] for cell in release['cells']]
                            diagnostics = [cell for interval in result['windows'] for cell in interval['cells']]
                            for cell in public + diagnostics:
                                # Geometry is derived separately from declared depth,
                                # while the scalar oracle recomputes it from cell ID.
                                self.assertLessEqual(80 / 2 ** cell['depth'], cap)
                                self.assertLessEqual(cell['width'], cap)
                            feasible = cap >= required_side and (mode != 'fixed' or 80 / 2 ** depth >= required_side)
                            self.assertEqual(bool(public), feasible)
                            retained = sum(cell['observation_contributions'] for cell in public)
                            self.assertEqual(retained, 152 if feasible else 0)
                            self.assertEqual(result['input_observation_contributions'], 152)
                            self.assertEqual(result['accounted_observation_contributions'], 152)
                            if not feasible:
                                eventual = eventual_evaluate(replay, result, reference_cell_m=10, reference_window_ms=1000)
                                deadlines = deadline_evaluate(replay, result, reference_cell_m=10,
                                                              reference_window_ms=1000, deadline_lags_ms=(0, 200, 1000))
                                summary = moving.summarize(replay, result, eventual, deadlines)
                                self.assertEqual(summary['retained_fraction'], 0)
                                self.assertEqual(summary['released_observations'], 0)
                                for name in ('mean_cell_side_m', 'mean_semantic_loss', 'maximum_semantic_loss',
                                             'mean_interval_start_age_ms'):
                                    self.assertIsNone(summary[name], name)
                                self.assertEqual(summary['occupancy_eventual']['answered_queries'], 0)


if __name__ == '__main__':
    unittest.main()
