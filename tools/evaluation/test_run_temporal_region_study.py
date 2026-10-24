"""Bounded scientific-contract checks; no native timing or motion generation."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import run_temporal_region_study as runner
from test_run_spatial20_correction import config_fixture, source_fixture


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def base_config():
    config = copy.deepcopy(config_fixture()['sensors'][0]['aggregation'])
    config.pop('publication', None)
    config.pop('diagnostics', None)
    config['policy_tree']['root']['cell_side_m']['max'] = 20
    config['policy_tree']['root']['semantic_suppression_fraction'] = {'max': 0}
    config['policy_tree']['regions'] = list(runner.REGIONS)
    config['policy_regions'] = [
        dict(id='entrance-vicinity', type='mapped_entrance', x=20, y=65, width=10, height=10,
             type_requirements={'distinct_contributors': {'min': 10}}, requirements={}),
        dict(id='west-footway-control', type='mapped_fresh_footway', x=0, y=62.5, width=15, height=12.5,
             type_requirements={'cell_side_m': {'max': 20}, 'window_duration_ms': {'max': 1000},
                                'age_at_evaluation_ms': {'max': 1000}, 'semantic_max_loss': {'max': .5}}, requirements={}),
        dict(id='central-through-footway', type='mapped_through', x=40, y=50, width=20, height=12.5,
             type_requirements={'semantic_max_loss': {'max': .5}}, requirements={}),
        dict(id='east-footway-control', type='mapped_fresh_footway', x=65, y=40, width=15, height=12.5,
             type_requirements={'cell_side_m': {'max': 20}, 'window_duration_ms': {'max': 1000},
                                'age_at_evaluation_ms': {'max': 1000}, 'semantic_max_loss': {'max': .5}}, requirements={})]
    config['spatial_selection'] = {'min_depth': 2, 'max_evaluations': 8192}
    config['temporal_adaptation'] = {'coordination': 'cell_local', 'max_window_ms': 4000, 'extension_step_ms': 100}
    return config


def correction_fixture(root):
    root.mkdir()
    provenance = root / 'provenance'
    provenance.mkdir()
    data, result = source_fixture()
    binary = provenance / 'AggregationReplay'
    binary.write_bytes(b'corrected native fixture\n')
    configs = {}
    sources = {}
    for source in runner.SOURCES:
        write(root / (source + '-observations.json'), data)
        proof = {'schema': 'ump.mapped-recording-proof.v1', 'status': 'verified',
                 'all_scheduled_episodes_completed': True,
                 'lifecycle_quality': {'scheduled_episodes': 5, 'pending_episodes_at_horizon': 0, 'active_episodes_at_horizon': 0},
                 'sensor_observability': {'schema': 'ump.source-sensor-episode-observability.v1', 'status': 'pass',
                                         'scheduled_tracks': 5, 'sensor_observed_tracks': 5,
                                         'missing_track_count': 0, 'unexpected_track_count': 0}}
        write(provenance / (source + '-capture-proof.json'), proof)
        sources[source] = dict(observations_sha256=runner.sha(root / (source + '-observations.json')),
                               capture_proof_sha256=runner.sha(provenance / (source + '-capture-proof.json')),
                               horizon_ms=2000, sampling_period_ms=100, input_observation_contributions=95,
                               peak_observed_simultaneous_tracks=5)
    for row in runner.correction.matrix():
        name = row['id']
        config = base_config()
        path = root / (name + '-policy.json')
        write(path, config)
        configs[name] = dict(config_sha256=runner.sha(path), independent_audit={
            'status': 'verified', 'scalar_valid': True, 'published_policy_violations': 0})
    frozen = {str(path.relative_to(root)): runner.sha(path) for path in root.rglob('*') if path.is_file()}
    protocol = dict(pre_execution_artifacts_sha256=frozen, sources=sources,
                    native_binary_sha256=runner.sha(binary), commands=[['native', '--progress-step-ms', '50']])
    write(root / 'protocol.json', protocol)
    summary = dict(schema='ump.spatial20-correction.v1', status='verified',
                   completion_scope='all_16_predeclared_cases', executed_case_count=16, planned_case_count=16,
                   protocol=protocol, protocol_sha256=runner.sha(root / 'protocol.json'), cases=configs)
    write(root / 'summary.json', summary)
    return data, result


class TemporalRegionStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.correction = self.root / 'correction'
        self.data, self.native = correction_fixture(self.correction)
        self.binary = self.correction / 'provenance/AggregationReplay'
        self.output = self.root / 'study'

    def tearDown(self):
        self.temp.cleanup()

    def checked(self, *args, **kwargs):
        self.assertEqual(kwargs, {'max_cells': 1000000})
        return dict(status='verified', scalar={'valid': True}, semantic_published_cells=2,
                    contribution_selection='all_contributions', source_accounting={
                        'input_observations': 95, 'retained_observations': 95,
                        'selectively_suppressed_observations': 0, 'whole_footprint_suppressed_observations': 0,
                        'by_source_type': {}, 'by_region': {},
                        'observation_to_release_delay_ms': {'mean': 500, 'p95': 900}})

    def mocked(self, cases=None, *, mutate=None, fail=False, checked=None):
        calls = []
        def native(command, **kwargs):
            protocol = runner.read(self.output / 'protocol.json')
            self.assertEqual(len(protocol['matrix']), 44)
            self.assertEqual(len(list(self.output.glob('*-policy.json'))), 44)
            self.assertFalse((self.output / 'summary.json').exists())
            runner.correction.check_frozen(self.output, protocol['pre_execution_artifacts_sha256'])
            self.assertEqual(kwargs['timeout'], 240)
            self.assertNotIn('shell', kwargs)
            self.assertEqual(Path(command[0]), self.output / 'provenance/AggregationReplay')
            write(Path(command[command.index('--output') + 1]), self.native)
            calls.append(command)
            if mutate:
                mutate(command)
            return subprocess.CompletedProcess(command, int(fail), 'fixture output\n', 'failure' if fail else '')
        with mock.patch.object(runner.subprocess, 'run', side_effect=native), \
             mock.patch.object(runner.correction, 'audit', side_effect=checked or self.checked) as audit, \
             contextlib.redirect_stdout(io.StringIO()):
            result = runner.study(self.correction, self.output, self.binary, cases=cases)
        return result, calls, audit

    def test_matrix_is_complete_paired_and_has_matched_four_second_fixed_schedules(self):
        rows = runner.matrix()
        self.assertEqual(len(rows), 44)
        self.assertEqual(len({row['id'] for row in rows}), 44)
        for source in runner.SOURCES:
            for policy in runner.POLICIES:
                cases = [row for row in rows if row['source'] == source and row['policy'] == policy]
                self.assertEqual(len(cases), 11)
                self.assertEqual({row['mode'] for row in cases if row['mode'] != 'fixed'}, set(runner.ADAPTIVE))
                self.assertEqual({(row['side_m'], row['window_ms']) for row in cases if row['mode'] == 'fixed'},
                                 {(side, window) for side in (10, 20) for window in (400, 1000, 2000, 4000)})
        self.assertEqual(runner.selected_cases([runner.PILOT])[0]['id'], runner.PILOT)
        for names in ([], ['unknown'], [runner.PILOT, runner.PILOT], ['all', runner.PILOT]):
            with self.assertRaises(ValueError):
                runner.selected_cases(names)

    def test_policy_pair_changes_only_declared_time_caps_and_labels(self):
        original = base_config()
        untouched = copy.deepcopy(original)
        pair = runner.policy_pair(original)
        self.assertEqual(original, untouched)
        control = copy.deepcopy(pair['control'])
        for name in ('application_id',):
            control[name] = original[name]
        control['policy_tree']['id'] = original['policy_tree']['id']
        removed = runner.differences(original, control)
        self.assertEqual(len(removed), 4)
        self.assertTrue(all(change['operation'] == 'remove' and change['before'] == {'max': 1000} for change in removed))
        self.assertEqual({change['path'] for change in removed}, {
            f'/policy_regions/{index}/type_requirements/{metric}' for index in (1, 3)
            for metric in ('window_duration_ms', 'age_at_evaluation_ms')})
        treatment = copy.deepcopy(pair['local400'])
        treatment['application_id'] = pair['control']['application_id']
        treatment['policy_tree']['id'] = pair['control']['policy_tree']['id']
        added = runner.differences(pair['control'], treatment)
        self.assertEqual(len(added), 2)
        self.assertTrue(all(change['operation'] == 'add' and change['after'] == {'max': 400} for change in added))
        self.assertEqual({change['path'] for change in added}, {
            '/policy_regions/2/type_requirements/window_duration_ms', '/policy_regions/2/type_requirements/age_at_evaluation_ms'})

    def test_methods_never_change_hard_rules_and_release_on_policy_satisfaction(self):
        pair = runner.policy_pair(base_config())
        for row in runner.matrix():
            base = pair[row['policy']]
            config = runner.method_config(base, row)
            self.assertEqual(runner.hard_policy(config), runner.hard_policy(base))
            execution = config['policy_tree']['execution']
            self.assertEqual(execution['release_trigger'], 'policy_satisfied')
            self.assertEqual(config['window_ms'], 400)
            if row['mode'] in ('temporal_first', 'spatial_first'):
                self.assertNotIn('semantic_secondary_strategy', execution)
            else:
                self.assertEqual(execution['semantic_secondary_strategy'], 'temporal_first')

    def test_hidden_temporal_or_suppression_or_spatial_changes_are_rejected(self):
        mutations = [lambda config: config['policy_tree']['root'].update(semantic_suppression_fraction={'max': .1}),
                     lambda config: config['policy_regions'][2]['requirements'].update(window_duration_ms={'max': 3000}),
                     lambda config: config['policy_regions'][1]['type_requirements'].update(cell_side_m={'max': 10}),
                     lambda config: config['policy_regions'][1]['type_requirements'].update(window_duration_ms={'max': 900})]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                config = base_config()
                mutation(config)
                with self.assertRaises(ValueError):
                    runner.policy_pair(config)

    def test_verified_correction_and_exact_frozen_inputs_are_required(self):
        verified = runner.verify_correction(self.correction)
        self.assertEqual(set(verified['sources']), set(runner.SOURCES))
        for relative in ('mixed-observations.json', 'provenance/pedestrians-capture-proof.json',
                         'mixed_spatial20_adaptive_immediate_off-policy.json', 'provenance/AggregationReplay', 'protocol.json'):
            path = self.correction / relative
            before = path.read_bytes()
            path.write_bytes(before + b' ')
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                runner.verify_correction(self.correction)
            path.write_bytes(before)

    def test_partial_or_missing_or_unverified_correction_is_rejected(self):
        path = self.correction / 'summary.json'
        original = runner.read(path)
        for change in ('status', 'count', 'case', 'audit'):
            summary = copy.deepcopy(original)
            if change == 'status':
                summary['status'] = 'running'
            elif change == 'count':
                summary['executed_case_count'] = 15
            elif change == 'case':
                summary['cases'].pop(next(iter(summary['cases'])))
            else:
                summary['cases']['mixed_spatial20_adaptive_immediate_off']['independent_audit']['scalar_valid'] = False
            write(path, summary)
            with self.subTest(change=change), self.assertRaises(ValueError):
                runner.verify_correction(self.correction)
        write(path, original)

    def test_pilot_freezes_all_cases_and_exact_diffs_before_execution(self):
        before = {str(path.relative_to(self.correction)): path.read_bytes() for path in self.correction.rglob('*') if path.is_file()}
        result, calls, audit = self.mocked([runner.PILOT])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['completion_scope'], 'explicit_predeclared_subset')
        self.assertEqual(result['executed_case_count'], 1)
        self.assertEqual(result['planned_case_count'], 44)
        self.assertEqual(len(calls), 1)
        self.assertEqual(audit.call_count, 1)
        protocol = result['protocol']
        self.assertTrue(protocol['native_binary_matches_correction'])
        for source in runner.SOURCES:
            self.assertEqual(len(protocol['sources'][source]['control_changes_from_correction']), 6)
            self.assertEqual(len(protocol['sources'][source]['treatment_changes_from_control']), 4)
        self.assertEqual(result['cases'][runner.PILOT]['stats']['source_accounting']['by_source_point_region']['outside_policy_regions']['retained_observation_contributions'], 95)
        report = runner.read(self.output / 'aggregate-report.json')
        self.assertEqual(len(report['cases']), 1)
        self.assertEqual(report['paired_policy_effects'], [])
        self.assertEqual(before, {str(path.relative_to(self.correction)): path.read_bytes() for path in self.correction.rglob('*') if path.is_file()})

    def test_all_native_cases_are_audited_and_paired_without_cheating_on_fixed_windows(self):
        result, calls, audit = self.mocked()
        self.assertEqual(result['completion_scope'], 'all_44_predeclared_cases')
        self.assertEqual(len(calls), 44)
        self.assertEqual(audit.call_count, 44)
        fixed = [command for command in calls if '--fixed-depth' in command]
        self.assertEqual(len(fixed), 32)
        self.assertEqual({command[command.index('--fixed-depth') + 1] for command in fixed}, {'2', '3'})
        self.assertEqual({command[command.index('--fixed-window-ms') + 1] for command in fixed}, {'400', '1000', '2000', '4000'})
        report = runner.read(self.output / 'aggregate-report.json')
        self.assertEqual(len(report['paired_policy_effects']), 22)
        self.assertTrue(all(row['treatment_minus_control']['retained_fraction'] == 0 for row in report['paired_policy_effects']))
        self.assertNotIn('episode-0', (self.output / 'report.md').read_text())
        self.assertNotIn('frozen-native-run', (self.output / 'aggregate-report.json').read_text())

    def test_midrun_configuration_change_aborts_without_verified_summary(self):
        def mutate(command):
            path = Path(command[command.index('--config') + 1])
            path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'Frozen correction artifact changed'):
            self.mocked([runner.PILOT], mutate=mutate)
        self.assertFalse((self.output / 'summary.json').exists())

    def test_failed_native_or_independent_audit_never_gets_verified_summary(self):
        with self.assertRaisesRegex(ValueError, 'native execution failed'):
            self.mocked([runner.PILOT], fail=True)
        self.assertTrue((self.output / (runner.PILOT + '-execution.json')).exists())
        self.assertFalse((self.output / 'summary.json').exists())
        self.output = self.root / 'audit-failure'
        def invalid(*args, **kwargs):
            checked = self.checked(*args, **kwargs)
            checked['status'] = 'failed'
            return checked
        with self.assertRaisesRegex(ValueError, 'audit did not pass'):
            self.mocked([runner.PILOT], checked=invalid)
        self.assertFalse((self.output / 'summary.json').exists())

    def test_suppression_or_nonconserved_output_is_rejected(self):
        for failure in ('filtering', 'conservation'):
            self.output = self.root / failure
            def bad(*args, **kwargs):
                checked = self.checked(*args, **kwargs)
                if failure == 'filtering':
                    checked['source_accounting'].update(selectively_suppressed_observations=1,
                                                        whole_footprint_suppressed_observations=-1)
                else:
                    checked['source_accounting']['whole_footprint_suppressed_observations'] = 1
                return checked
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                self.mocked([runner.PILOT], checked=bad)
            self.assertFalse((self.output / 'summary.json').exists())

    def test_existing_outputs_and_invalid_budget_are_rejected_before_execution(self):
        self.output.mkdir()
        (self.output / 'keep').write_text('keep')
        with mock.patch.object(runner.subprocess, 'run') as native:
            with self.assertRaisesRegex(ValueError, 'fresh'):
                runner.study(self.correction, self.output, self.binary)
            native.assert_not_called()
        self.assertEqual((self.output / 'keep').read_text(), 'keep')
        for budget in (0, 241, True, .5):
            with self.assertRaisesRegex(ValueError, 'wall budget'):
                runner.study(self.correction, self.root / 'other', self.binary, wall_budget_s=budget)


if __name__ == '__main__':
    unittest.main()
