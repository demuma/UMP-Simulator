"""Bounded P25.2 orchestration tests; no urban/native benchmark or fitting."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import run_urban_privacy_channel_pilot as pilot
import semantic_privacy as semantic
from test_semantic_privacy import private_result, taxonomy, point


def config():
    return {'policy_tree': {'id': 'public-policy', 'version': '1', 'regions': [], 'root': {},
            'execution': {'strategy': 'semantic_first', 'publication_model': 'private_final_snapshot'}},
            'policy_regions': [], 'semantic_taxonomy': taxonomy(), 'history': {'private_count': 999}}


def public():
    result = private_result()
    result['releases'][0]['cells'][0]['effective_policy_id'] = 'public-policy/1/p0'
    return semantic.export_public(result, taxonomy())


class UrbanPrivacyChannelPilotTests(unittest.TestCase):
    def test_ten_predeclared_native_cases_and_fixed_schedule(self):
        rows = pilot.matrix()
        self.assertEqual(len(rows), 10)
        self.assertEqual(len({row['id'] for row in rows}), 10)
        self.assertEqual({row['world'] for row in rows}, {'IN', 'OUT'})
        for world in pilot.WORLDS:
            selected = [r for r in rows if r['world'] == world]
            self.assertEqual(sum(r['mode'] == 'semantic_first' for r in selected), 1)
            self.assertEqual({r['window_ms'] for r in selected if r['mode'] == 'fixed'}, {400, 1000, 2000, 4000})

    def test_commands_keep_policy_input_and_progress_boundary(self):
        for row in pilot.matrix():
            args = pilot.command(Path('binary'), Path('source'), Path('policy'), Path('output'), row)
            self.assertEqual(args[args.index('--config') + 1], 'policy')
            self.assertEqual(args[args.index('--input') + 1], 'source')
            self.assertEqual(args[args.index('--progress-step-ms') + 1], '50')
            if row['mode'] == 'fixed':
                self.assertEqual(args[args.index('--fixed-depth') + 1], '2')
                self.assertEqual(int(args[args.index('--fixed-window-ms') + 1]), row['window_ms'])
            self.assertNotIn('--pace-rate', args)

    def test_public_side_information_excludes_raw_configuration(self):
        context = pilot.public_policy(config())
        self.assertEqual(set(context), {'policy_id', 'policy_version', 'root_requirements', 'regional_requirements', 'execution'})
        self.assertNotIn('history', context)
        self.assertNotIn('semantic_taxonomy', context)

    def test_declared_public_ids_model_and_compiled_effective_policy(self):
        original = public()
        pilot.public_contract(original, config())
        for mutate in (
            lambda p: p['releases'][0].__setitem__('policy_id', 'label-OUT'),
            lambda p: p['releases'][0].__setitem__('policy_version', '2'),
            lambda p: p['releases'][0].__setitem__('model', 'another-model'),
            lambda p: p['releases'][0]['cells'][0].__setitem__('effective_policy_id', 'public-policy/1/p999'),
        ):
            changed = deepcopy(original)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                pilot.public_contract(changed, config())
        with self.assertRaises(ValueError):
            pilot.public_contract(original, config(), ['public-policy'])

    def test_complete_feature_vector_snapshot_and_no_output_controls(self):
        values, receipt = pilot.feature_check(public(), [point()])
        self.assertEqual(len(values['feature_names']), len(values['values']))
        self.assertTrue(receipt['before_horizon_no_snapshot'])
        self.assertTrue(receipt['full_horizon_view_equal'])
        self.assertTrue(receipt['no_output_same_dimension'])
        with mock.patch.object(semantic, 'feature_vector', return_value=[float('nan')]):
            with self.assertRaises(ValueError):
                pilot.feature_check(public(), [point()])

    def test_logical_sealing_is_not_silently_accepted_as_snapshot(self):
        result = private_result()
        value = semantic.export_public(result, taxonomy(), availability_model='logical_sealing')
        with self.assertRaises(ValueError):
            pilot.feature_check(value, [point()])
        with self.assertRaises(ValueError):
            pilot.public_contract(value, config())

    def test_immutable_artifact_checks_reject_changes_after_verification(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            path = Path(directory) / 'case.json'
            path.write_text('original')
            frozen = {}
            pilot.remember(directory, [path.name], frozen)
            pilot.unchanged(frozen)
            path.write_text('changed')
            with self.assertRaises(ValueError):
                pilot.unchanged(frozen)
            with self.assertRaises(ValueError):
                pilot.remember(directory, ['later.json'], frozen)

    def test_missing_and_changed_frozen_sources_fail_closed(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            path = Path(directory) / 'file'
            path.write_text('fixed')
            frozen = {str(path): pilot.sha(path)}
            path.unlink()
            with self.assertRaises((ValueError, OSError)):
                pilot.unchanged(frozen)

    def test_invalid_wall_budget_rejected_before_fixture_access(self):
        for budget in (0, 241, True, 1.5):
            with self.subTest(budget=budget), mock.patch.object(pilot.fixture, 'verify_fixture') as verify:
                with self.assertRaises(ValueError):
                    pilot.prepare(Path('absent'), Path('output'), Path('binary'), budget)
                verify.assert_not_called()

    def test_native_header_keeps_method_source_cadence_and_accounting(self):
        source = {'run_id': 'r', 'sensor_id': 's', 'coverage': {}, 'sampling_period_ms': 100,
                  'end_ms': 1000, 'batches': [{'observations': [1, 2]}]}
        cfg = {'application_id': 'app'}
        result = {'schema': 'ump.replay-result.v1', 'mode': 'fixed',
                  'source': {k: v for k, v in source.items() if k != 'batches'},
                  'parameters': {'progress_step_ms': 50, 'progress_origin_ms': 0,
                      'fixed_depth': 2, 'window_ms': 400, 'coordination': 'common_window'},
                  'input_observation_contributions': 2, 'accounted_observation_contributions': 2}
        result['source']['application_id'] = 'app'
        row = {'mode': 'fixed', 'window_ms': 400}
        pilot.native_header(result, source, cfg, row)
        for section, key, changed in [('parameters', 'fixed_depth', 3),
            ('parameters', 'window_ms', 1000), ('parameters', 'progress_step_ms', 100),
            ('source', 'end_ms', 2000), ('source', 'application_id', 'other')]:
            value = deepcopy(result); value[section][key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                pilot.native_header(value, source, cfg, row)
        for key, changed in [('mode', 'semantic_first'), ('accounted_observation_contributions', 1)]:
            value = deepcopy(result); value[key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                pilot.native_header(value, source, cfg, row)

    def test_timeout_is_preserved_without_retry_or_auditing(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            row = {'id': 'IN_demo', 'command': ['unused']}
            protocol = {'native_wall_budget_s': 1}
            import subprocess
            with mock.patch.object(pilot.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['unused'], 1)) as native:
                with self.assertRaises(RuntimeError):
                    pilot.run_native(Path(directory), config(), protocol, {}, row)
            self.assertEqual(native.call_count, 1)
            self.assertEqual(pilot.load(Path(directory) / 'IN_demo-execution.json')['status'], 'timeout')


if __name__ == '__main__':
    unittest.main()
