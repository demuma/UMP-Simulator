"""Independent real-core regressions for the bounded four-second policy study.

These are deterministic contract fixtures, not moving-scenario evidence. They
separate repeated observations from distinct Road Users and demonstrate when
longer private history can actually improve support. Numeric audits reconstruct
counts from the input independently of the C++ release decisions.
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

BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT / 'simulator/build/AggregationReplay'))
MODES = ('temporal_first', 'spatial_first', 'semantic_first')


def row(identity, kind='Adult Pedestrian'):
    return {'id': identity, 'type': kind, 'x': .25, 'y': .25,
            'cell_id': cell_for(.25, .25)[0]}


def source(rows, end_ms=4000, unavailable=()):
    batches = []
    for time in range(100, end_ms, 100):
        values = rows(time) if callable(rows) else rows
        batches.append({'sequence': time // 100, 'observed_at_ms': time,
                        'status': 'unavailable' if time in unavailable else 'measured',
                        'observations': [] if time in unavailable else deepcopy(values)})
    return {'schema': 'ump.observation-replay.v1', 'run_id': 'four-second-window-contract',
            'sensor_id': 'temporal-aggregation-agbs',
            'coverage': {'x': 0, 'y': 0, 'width': 80, 'height': 80, 'leaf_depth': 6},
            'sampling_period_ms': 100, 'end_ms': end_ms, 'batches': batches}


class FourSecondWindowTests(unittest.TestCase):
    maxDiff = None

    def run_core(self, replay, config, mode, fixed_window=None):
        with tempfile.TemporaryDirectory(prefix='ump-window4s-contract-') as temporary:
            directory = Path(temporary)
            src, cfg, out = (directory / name for name in ('source.json', 'policy.json', 'result.json'))
            src.write_text(json.dumps(replay))
            cfg.write_text(json.dumps(config))
            command = [str(BINARY), '--input', str(src), '--config', str(cfg),
                       '--mode', mode, '--output', str(out)]
            if fixed_window is not None:
                command += ['--fixed-depth', '4', '--fixed-window-ms', str(fixed_window)]
            completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = json.loads(out.read_text())
        audit_config = deepcopy(config)
        if mode != 'fixed':
            audit_config['policy_tree']['execution']['strategy'] = mode
        if fixed_window is not None:
            audit_config['window_ms'] = fixed_window
        self.assertTrue(moving.scalar_audit(replay, audit_config, result)['valid'])
        self.assertEqual(moving.semantic_audit(replay, config, result)['status'], 'verified')
        self.assertEqual(result['input_observation_contributions'],
                         sum(len(batch['observations']) for batch in replay['batches']))
        self.assertEqual(result['accounted_observation_contributions'], result['input_observation_contributions'])
        for release in result['releases']:
            self.assertLessEqual(release['end_ms'], replay['end_ms'])
            self.assertLessEqual(release['end_ms'] - release['start_ms'],
                                 config['policy_tree']['root']['window_duration_ms']['max'])
            self.assertLessEqual(release['sealed_at_ms'] - release['start_ms'],
                                 config['policy_tree']['root']['age_at_evaluation_ms']['max'])
            self.assertNotIn('semantic_priority', release)
            self.assertTrue(all(cell['width'] <= 5 for cell in release['cells']))
        return result

    def test_default_one_second_policy_and_matrix_remain_byte_equivalent(self):
        default = moving.policy()
        self.assertEqual(default, moving.policy(max_window_ms=1000))
        self.assertEqual(moving.VARIANTS, moving.variants_for_cap(max_window_ms=1000))
        # The historical runner now explicitly opts into its old release behavior.
        self.assertEqual(default['policy_tree']['execution'].pop('release_trigger'), 'priority_satisfied')
        # Remaining canonical archived policy is unchanged.
        self.assertEqual(hashlib.sha256(json.dumps(default, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                         '2cf3be91142fb60b18b851ec59974161113b766319660f5c31e7a47067066578')

    def test_four_second_policy_changes_time_capacity_not_support_or_taxonomy(self):
        for cap in (5, 10, 40):
            with self.subTest(cap=cap):
                old, new = moving.policy(cap), moving.policy(cap, max_window_ms=4000)
                self.assertEqual(new['window_ms'], 400)
                self.assertEqual(new['temporal_adaptation']['extension_step_ms'], 100)
                self.assertEqual(new['temporal_adaptation']['max_window_ms'], 4000)
                self.assertGreaterEqual(new['temporal_adaptation']['max_evaluations'], 37)
                self.assertEqual(new['policy_tree']['root']['window_duration_ms'], {'max': 4000})
                self.assertEqual(new['policy_tree']['root']['age_at_evaluation_ms'], {'max': 4000})
                self.assertEqual(new['history']['retention_ms'], 5000)
                self.assertEqual(new['history']['max_bins'], 64)
                self.assertEqual(new['semantic_taxonomy'], old['semantic_taxonomy'])
                self.assertEqual(new['spatial_selection'], old['spatial_selection'])
                self.assertEqual(new['policy_tree']['root']['min_category_distinct_contributors'], {'min': 5})
                self.assertEqual(new['policy_tree']['root']['semantic_max_loss'], {'max': 1})
                self.assertNotEqual(new['policy_tree']['id'], old['policy_tree']['id'])
                variants = moving.variants_for_cap(cap, max_window_ms=4000)
                self.assertEqual(len(variants), 12)
                self.assertEqual({window for _, mode, _, window in variants if mode == 'fixed'}, {400, 1000, 4000})
                for _, mode, depth, _ in variants:
                    if mode == 'fixed':
                        self.assertLessEqual(80 / 2 ** depth, cap)

    def test_invalid_window_caps_are_rejected_before_running(self):
        for invalid in (True, False, None, '4000', 4000.0, 0, 400, 2000, 4100):
            with self.subTest(window=invalid):
                with self.assertRaises(ValueError):
                    moving.policy(max_window_ms=invalid)
                with self.assertRaises(ValueError):
                    moving.variants_for_cap(max_window_ms=invalid)

    def test_one_repeated_identity_never_becomes_five_distinct_road_users(self):
        replay, config = source([row('same-person')]), moving.policy(5, max_window_ms=4000)
        for mode in MODES + ('fixed',):
            with self.subTest(mode=mode):
                result = self.run_core(replay, config, mode, 4000 if mode == 'fixed' else None)
                self.assertEqual(result['input_observation_contributions'], 39)
                self.assertEqual(result['releases'], [])
                self.assertEqual([(item['start_ms'], item['end_ms']) for item in result['windows']], [(0, 4000)])

    def test_five_distinct_arrivals_unlock_the_same_cell_before_four_seconds(self):
        # The fifth identity is first observed at3300; intervals are half-open,
        # so the first candidate containing it ends at3400, never3300.
        arrivals = (100, 900, 1700, 2500, 3300)
        replay = source(lambda time: [row(f'person-{i}') for i, arrival in enumerate(arrivals) if arrival <= time])
        for mode in MODES:
            with self.subTest(mode=mode):
                long = self.run_core(replay, moving.policy(5, max_window_ms=4000), mode)
                first = long['releases'][0]
                self.assertEqual((first['start_ms'], first['end_ms'], first['sealed_at_ms']), (0, 3400, 3400))
                self.assertEqual(len(first['cells']), 1)
                semantic = first['cells'][0]['semantic']
                self.assertEqual(semantic['categories'], [{'category_id': 'adult_pedestrian',
                                  'observation_contributions': 85, 'distinct_contributors': 5}])
                self.assertEqual(semantic['semantic_max_loss'], 0)
                short = self.run_core(replay, moving.policy(5), mode)
                self.assertFalse(any(r['start_ms'] == 0 for r in short['releases']),
                                 'The one-second controller cannot recover its already retired first interval')
                long_retained = sum(c['observation_contributions'] for r in long['releases'] for c in r['cells'])
                short_retained = sum(c['observation_contributions'] for r in short['releases'] for c in r['cells'])
                self.assertGreater(long_retained, short_retained)

    def test_four_second_setting_does_not_override_a_one_second_hard_age_cap(self):
        replay = source([row('same-person')])
        for metric in ('window_duration_ms', 'age_at_evaluation_ms'):
            config = moving.policy(5, max_window_ms=4000)
            config['policy_tree']['root'][metric]['max'] = 1000
            for mode in MODES:
                with self.subTest(metric=metric, mode=mode):
                    result = self.run_core(replay, config, mode)
                    self.assertEqual(result['releases'], [])
                    self.assertEqual([(item['start_ms'], item['end_ms']) for item in result['windows']],
                                     [(0, 1000), (1000, 2000), (2000, 3000), (3000, 4000)])

    def test_seven_repeated_types_allow_truthful_generalization_but_no_new_exact_support(self):
        config = moving.policy(5, max_window_ms=4000)
        labels = [label for node in config['semantic_taxonomy']['nodes'] for label in node.get('input_types', [])]
        self.assertEqual(len(labels), 7)
        replay = source([row(f'person-{i}', kind) for i, kind in enumerate(labels)])
        for mode in MODES:
            with self.subTest(mode=mode):
                result = self.run_core(replay, config, mode)
                first = result['releases'][0]
                self.assertEqual(first['end_ms'], 4000 if mode == 'semantic_first' else 400)
                for release in result['releases']:
                    for cell in release['cells']:
                        self.assertEqual(cell['semantic']['semantic_max_loss'], 1)
                        self.assertEqual([item['category_id'] for item in cell['semantic']['categories']], ['road_user'])
                        self.assertEqual(cell['semantic']['categories'][0]['distinct_contributors'], 7)

    def test_eof_finalizes_a_shorter_window_without_waiting_for_unobserved_future(self):
        replay = source([row('same-person')], end_ms=3950)
        for mode in MODES:
            with self.subTest(mode=mode):
                result = self.run_core(replay, moving.policy(5, max_window_ms=4000), mode)
                self.assertEqual(result['releases'], [])
                self.assertEqual(result['input_observation_contributions'], 39)
                self.assertEqual([(item['start_ms'], item['end_ms']) for item in result['windows']], [(0, 3950)])
                self.assertEqual(result['windows'][0]['completion_reason'], 'end_of_stream')

    def test_missing_measurement_cannot_be_disguised_as_complete_four_second_evidence(self):
        config = moving.policy(5, max_window_ms=4000)
        labels = [label for node in config['semantic_taxonomy']['nodes'] for label in node.get('input_types', [])]
        replay = source([row(f'person-{i}', kind) for i, kind in enumerate(labels)], unavailable=(2000,))
        result = self.run_core(replay, config, 'semantic_first')
        self.assertFalse(any(r['start_ms'] <= 2000 < r['end_ms'] for r in result['releases']))
        self.assertTrue(any(w['completion_reason'] == 'coverage_unavailable' for w in result['windows']))


if __name__ == '__main__':
    unittest.main()
