#!/usr/bin/env python3
"""Bounded runner orchestration tests; no native replay or build is executed."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import run_current_paced_study as study
from test_summarize_paced_replay import add_audit, failed_prefix, pair


def dump(path, value):
    Path(path).write_text(json.dumps(value))


def full_control():
    _, value = pair()
    value['parameters'].update(progress_step_ms=50, progress_origin_ms=0)
    add_audit(value)
    return value


def paced_result(reference):
    value = copy.deepcopy(reference)
    paced, _ = pair()
    value['runtime']['pacing'] = paced['runtime']['pacing']
    telemetry = value['runtime']['pacing']
    telemetry['queue_capacity'] = 8
    rows = []
    for logical in (50, 100, 150, 200, 250):
        rows.append(dict(logical_time_ms=logical, kind='finish' if logical == 250 else 'cadence',
                         scheduled_arrival_ms=logical, enqueue_attempt_ms=logical + .05,
                         enqueued_ms=logical + .1, service_start_ms=logical + .2,
                         service_finish_ms=logical + 10, queue_depth_after_enqueue=1))
    telemetry['events'] = rows
    value['runtime']['diagnostics'] = 'minimal'
    value['windows'] = []
    return value


def historical_evidence_fixture(source, policy):
    return dict(protocol=dict(artifacts_before=dict(source=study.audit.fingerprint(source),
                policy=study.audit.fingerprint(policy), binary=dict(sha256='c' * 64, bytes=123))),
                paced_incomplete_result=dict(result='bounded_queue_overflow',
                    source=dict(end_ms=240000, progress_step_ms=50, sampling_period_ms=100),
                    offered_load=dict(rate=1, queue_capacity=8),
                    events=dict(completed=528, rejected_logical_time_ms=26850),
                    completed_prefix_cadence_response_misses=170,
                    completed_sensor_period_response_misses=42))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.folder = self.root / 'mixed'
        self.folder.mkdir()
        self.reference = self.root / 'historical.json'
        dump(self.reference, full_control())
        self.protocol = dict(schema=study.SCHEMA, study_directory=str(self.root), repo=str(self.root), original_artifacts={}, frozen_artifacts={}, source_files={},
                             max_case_wall_seconds=420,
                             expected_sources=dict(mixed=dict(duration_ms=250, sensor_sampling_ms=100)),
                             offered_load=dict(rate=1, queue_capacity=8, progress_step_ms=50))
        self.freeze_test_protocol()

    def freeze_test_protocol(self):
        # Unit fixtures may declare different bounded synthetic horizons. Each
        # fixture declaration gets its own matching prepare-time receipt before
        # the runner is invoked; production never rewrites either artifact.
        dump(self.root / 'protocol.json', self.protocol)
        dump(self.root / 'protocol-receipt.json', dict(schema='ump.current-paced-protocol-receipt.v1',
            protocol_fingerprint=study.audit.fingerprint(self.root / 'protocol.json')))

    def tearDown(self):
        self.temporary.cleanup()

    def item(self, case):
        return dict(id='mixed/' + case, source='mixed', case=case,
                    output=str(self.folder / (case + '.json')),
                    failure=str(self.folder / (case + '-failure.json')),
                    execution=str(self.folder / (case + '-execution.json')),
                    summary=str(self.folder / (case + '-summary.json')),
                    historical_full=str(self.reference), command=['frozen-native', case])

    def fake_success(self, command, **kwargs):
        self.assertEqual(kwargs['timeout'], 420)
        self.assertTrue(kwargs['capture_output'])
        self.assertFalse(kwargs['check'])
        case = command[1] if len(command) == 2 else 'full_unpaced'
        value = full_control()
        if case != 'full_unpaced':
            value['runtime']['diagnostics'] = 'minimal'
            value['windows'] = []
        if case == 'minimal_paced_1x':
            value = paced_result(full_control())
        dump(self.item(case)['output'], value)
        return subprocess.CompletedProcess(command, 0, 'completed', '')

    def controls(self):
        for case in study.CASES[:2]:
            self.assertEqual(study.run_case(self.protocol, self.item(case))['status'], 'validated')

    @patch.object(study.subprocess, 'run')
    def test_complete_audited_control_chain_and_paced_success(self, native):
        native.side_effect = self.fake_success
        self.controls()
        result = study.run_case(self.protocol, self.item('minimal_paced_1x'))
        self.assertEqual(result['status'], 'validated')
        self.assertEqual(native.call_count, 3)
        report = json.loads(Path(self.item('minimal_paced_1x')['summary']).read_text())
        self.assertTrue(report['logical_output_equal_excluding_runtime'])
        self.assertEqual(report['offered_load']['queue_capacity'], 8)
        self.assertEqual(report['cadence']['service']['count'], 4)
        self.assertNotIn('never-copy', json.dumps(report))

    @patch.object(study.subprocess, 'run')
    def test_protocol_command_and_offered_load_tampering_rejected_before_native(self, native):
        self.protocol['cases'] = [self.item('full_unpaced')]
        self.freeze_test_protocol()
        original = (self.root / 'protocol.json').read_bytes()
        mutations = (lambda p: p['cases'][0]['command'].append('--changed'),
                     lambda p: p['offered_load'].update(rate=.5),
                     lambda p: p.update(deadline_contract=dict(cadence_response_ms=100)))
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                changed = json.loads(original)
                mutation(changed)
                dump(self.root / 'protocol.json', changed)
                with self.assertRaisesRegex(ValueError, 'prepare-time SHA-256 receipt'):
                    study.verify_protocol(changed, self.root)
                with self.assertRaisesRegex(ValueError, 'prepare-time SHA-256 receipt'):
                    study.run_case(changed, changed['cases'][0])
                with self.assertRaisesRegex(ValueError, 'prepare-time SHA-256 receipt'):
                    study.compact_report(changed)
        (self.root / 'protocol.json').write_bytes(original)
        study.verify_protocol(self.protocol, self.root)
        native.assert_not_called()

    @patch.object(study.subprocess, 'run')
    def test_successful_pacing_cannot_change_rate_or_queue(self, native):
        native.side_effect = self.fake_success
        self.controls()
        for field, replacement in (('rate', 2), ('queue_capacity', 4)):
            with self.subTest(field=field):
                item = self.item('minimal_paced_1x')
                def changed(command, **kwargs):
                    result = self.fake_success(command, **kwargs)
                    value = json.loads(Path(item['output']).read_text())
                    pacing = value['runtime']['pacing']
                    pacing[field] = replacement
                    if field == 'rate':
                        for event in pacing['events']:
                            for key in ('scheduled_arrival_ms', 'enqueue_attempt_ms', 'enqueued_ms', 'service_start_ms', 'service_finish_ms'):
                                event[key] /= 2
                        for sample in pacing['memory_samples']:
                            sample['wall_ms'] /= 2
                        for acknowledgement in pacing['release_acknowledgements']:
                            acknowledgement['in_memory_ack_ms'] /= 2
                    dump(item['output'], value)
                    return result
                native.side_effect = changed
                record = study.run_case(self.protocol, item)
                self.assertEqual(record['status'], 'verification_failed')
                self.assertIn('frozen offered-load', record['verification_error'])
                # Separate mock case paths permit both adversarial scenarios;
                # production deliberately never removes or retries a case.
                for name in ('output', 'failure', 'execution', 'summary'):
                    Path(item[name]).unlink(missing_ok=True)

    @patch.object(study.subprocess, 'run')
    def test_mutated_control_payloads_block_later_native_execution(self, native):
        native.side_effect = self.fake_success
        self.controls()
        for case in ('full_unpaced', 'minimal_unpaced'):
            with self.subTest(case=case):
                path = Path(self.item(case)['output'])
                original = path.read_bytes()
                value = json.loads(original)
                if case == 'full_unpaced':
                    value['windows'][0]['secret_identity'] = 'changed-private-value'
                else:
                    value['releases'][0]['end_ms'] = 201
                dump(path, value)
                with self.assertRaisesRegex(ValueError, 'control changed since its execution receipt'):
                    study.run_case(self.protocol, self.item('minimal_paced_1x'))
                path.write_bytes(original)
        self.assertEqual(native.call_count, 2)

    def configure_compact_protocol(self):
        binary = self.root / 'AggregationReplay'
        binary.write_text('frozen-native')
        self.protocol.update(cases=[self.item(case) for case in study.CASES],
            frozen_artifacts={str(binary): study.audit.fingerprint(binary)},
            deadline_contract=dict(cadence_response_ms=50, secondary_sensor_response_ms=100),
            limitation='Synthetic mocked study')
        self.freeze_test_protocol()

    @patch.object(study.subprocess, 'run')
    def test_compact_report_rejects_changed_native_output_and_compact_summary(self, native):
        self.configure_compact_protocol()
        native.side_effect = self.fake_success
        for case in study.CASES:
            record = study.run_case(self.protocol, self.item(case))
            self.assertEqual(record['status'], 'validated')
            self.assertIn('summary_fingerprint', record)
        self.assertTrue(study.compact_report(self.protocol)['all_native_cases_completed'])
        for field in ('output', 'summary'):
            with self.subTest(field=field):
                path = Path(self.item('minimal_paced_1x')[field])
                original = path.read_bytes()
                value = json.loads(original)
                value['changed_after_validation'] = True
                dump(path, value)
                with self.assertRaisesRegex(ValueError, 'changed before compact reporting'):
                    study.compact_report(self.protocol)
                path.write_bytes(original)
        self.assertTrue(study.compact_report(self.protocol)['all_native_cases_completed'])

    def test_compact_report_rejects_changed_failure_telemetry(self):
        self.configure_compact_protocol()
        item = self.item('minimal_paced_1x')
        failure = Path(item['failure'])
        compact = Path(item['summary'])
        dump(failure, failed_prefix())
        dump(compact, dict(successful_replay_result=False))
        dump(item['execution'], dict(id=item['id'], status='bounded_queue_overflow', return_code=1,
            failure_fingerprint=study.audit.fingerprint(failure), summary_fingerprint=study.audit.fingerprint(compact)))
        self.assertFalse(study.compact_report(self.protocol)['all_native_cases_completed'])
        dump(failure, dict(changed_after_validation=True))
        with self.assertRaisesRegex(ValueError, 'Failure telemetry changed'):
            study.compact_report(self.protocol)

    @patch.object(study.subprocess, 'run')
    def test_changed_private_decision_blocks_full_equivalence(self, native):
        def changed(command, **kwargs):
            result = self.fake_success(command, **kwargs)
            path = Path(self.item('full_unpaced')['output'])
            value = json.loads(path.read_text())
            value['windows'][0]['secret_identity'] = 'different'
            dump(path, value)
            return result
        native.side_effect = changed
        record = study.run_case(self.protocol, self.item('full_unpaced'))
        self.assertEqual(record['status'], 'verification_failed')
        self.assertIn('differs outside', record['verification_error'])
        with self.assertRaisesRegex(ValueError, 'validated prior control'):
            study.run_case(self.protocol, self.item('minimal_unpaced'))
        self.assertEqual(native.call_count, 1)

    @patch.object(study.subprocess, 'run')
    def test_overflow_is_a_failed_gate_without_successful_output(self, native):
        native.side_effect = self.fake_success
        self.controls()
        failure = failed_prefix()
        self.protocol['expected_sources']['mixed']['duration_ms'] = 500
        self.protocol['offered_load'].update(progress_step_ms=100, queue_capacity=1)
        self.freeze_test_protocol()
        def overflow(command, **kwargs):
            dump(self.item('minimal_paced_1x')['failure'], failure)
            return subprocess.CompletedProcess(command, 1, '', 'bounded overflow')
        native.side_effect = overflow
        record = study.run_case(self.protocol, self.item('minimal_paced_1x'))
        self.assertEqual(record['status'], 'bounded_queue_overflow')
        self.assertFalse(record['output_exists'])
        report = json.loads(Path(self.item('minimal_paced_1x')['summary']).read_text())
        self.assertFalse(report['successful_replay_result'])
        self.assertIsNone(report['logical_output_equal_excluding_runtime'])
        self.assertEqual(report['events']['completed'], 2)

    @patch.object(study.subprocess, 'run')
    def test_failure_contract_cannot_silently_change_queue(self, native):
        native.side_effect = self.fake_success
        self.controls()
        def overflow(command, **kwargs):
            dump(self.item('minimal_paced_1x')['failure'], failed_prefix())
            return subprocess.CompletedProcess(command, 1, '', 'overflow')
        native.side_effect = overflow
        result = study.run_case(self.protocol, self.item('minimal_paced_1x'))
        self.assertEqual(result['status'], 'verification_failed')
        self.assertIn('frozen offered-load', result['verification_error'])

    @patch.object(study.subprocess, 'run')
    def test_timeout_and_native_failure_have_receipts_and_no_retry(self, native):
        native.side_effect = subprocess.TimeoutExpired(['native'], 420)
        result = study.run_case(self.protocol, self.item('full_unpaced'))
        self.assertEqual(result['status'], 'timeout')
        self.assertIsNone(result['return_code'])
        with self.assertRaisesRegex(ValueError, 'never overwritten or retried'):
            study.run_case(self.protocol, self.item('full_unpaced'))
        self.assertEqual(native.call_count, 1)

    @patch.object(study.subprocess, 'run')
    def test_existing_output_or_changed_artifact_prevents_native_execution(self, native):
        item = self.item('full_unpaced')
        Path(item['output']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'already exist'):
            study.run_case(self.protocol, item)
        Path(item['output']).unlink()
        watched = self.root / 'source.cpp'
        watched.write_text('before')
        self.protocol['source_files'] = study.fingerprints([watched])
        self.freeze_test_protocol()
        watched.write_text('after')
        with self.assertRaisesRegex(ValueError, 'artifacts changed'):
            study.run_case(self.protocol, item)
        native.assert_not_called()

    @patch.object(study.subprocess, 'run')
    def test_missing_sidecar_is_native_failure_not_overflow(self, native):
        native.return_value = subprocess.CompletedProcess(['native'], 1, '', 'other failure')
        result = study.run_case(self.protocol, self.item('full_unpaced'))
        self.assertEqual(result['status'], 'native_failure')
        self.assertFalse(Path(self.item('full_unpaced')['summary']).exists())

    def test_command_freezes_queue_cadence_digests_and_separate_failure_output(self):
        for case in study.CASES:
            command = study.command('native', 'source', 'policy', 'result', case, 'failure')
            options = dict(zip(command[1::2], command[2::2]))
            self.assertEqual(options['--progress-step-ms'], '50')
            self.assertEqual(options['--decision-digest'], 'sha256')
            if case == 'minimal_paced_1x':
                self.assertEqual(options['--queue-capacity'], '8')
                self.assertEqual(options['--pace-rate'], '1')
                self.assertEqual(options['--failure-output'], 'failure')
            else:
                self.assertNotIn('--pace-rate', options)
                self.assertNotIn('--failure-output', options)

    @patch.object(study, 'independent_policy_audit')
    @patch.object(study.subprocess, 'run')
    def test_historical_dense_uses_current_independent_audit_without_old_output_equality(self, native, independent):
        native.side_effect = self.fake_success
        independent.return_value = dict(status='verified', scalar_valid=True, policy_violation_count=0)
        item = self.item('full_unpaced')
        item.update(full_validation='independent_policy_audit', historical_full=None,
                    command=['frozen-native', '--input', str(self.reference),
                             '--config', str(self.reference)])
        self.protocol['historical_failed_gate'] = dict(old_result='bounded_queue_overflow')
        self.freeze_test_protocol()
        result = study.run_case(self.protocol, item)
        self.assertEqual(result['status'], 'validated')
        independent.assert_called_once()
        checked = json.loads(Path(item['summary']).read_text())
        self.assertFalse(checked['old_binary_logical_equality_required'])
        self.assertEqual(checked['independent_policy_audit']['status'], 'verified')
        self.assertNotIn('historical_corrected_output_equal', checked)

    @patch.object(study, 'independent_policy_audit', side_effect=ValueError('Independent audit rejected'))
    @patch.object(study.subprocess, 'run')
    def test_historical_dense_audit_failure_fails_closed(self, native, independent):
        native.side_effect = self.fake_success
        item = self.item('full_unpaced')
        item.update(full_validation='independent_policy_audit', historical_full=None,
                    command=['frozen-native', '--input', str(self.reference),
                             '--config', str(self.reference)])
        self.protocol['historical_failed_gate'] = dict(old_result='bounded_queue_overflow')
        self.freeze_test_protocol()
        record = study.run_case(self.protocol, item)
        self.assertEqual(record['status'], 'verification_failed')
        self.assertIn('Independent audit rejected', record['verification_error'])
        self.assertFalse(Path(item['summary']).exists())

    def test_historical_identity_rejects_changed_source(self):
        source = self.root / 'old-source.json'
        policy = self.root / 'old-policy.json'
        evidence = self.root / 'old-evidence.json'
        dump(source, dict(observations=[]))
        dump(policy, dict(policy=True))
        dump(evidence, historical_evidence_fixture(source, policy))
        values = dict(observations=source, policy=policy, historical_evidence=evidence)
        identity = study.historical_identity(values)
        self.assertEqual(identity['old_completed_events'], 528)
        dump(source, dict(observations=['changed']))
        with self.assertRaisesRegex(ValueError, 'differs from the recorded failed gate'):
            study.historical_identity(values)

    @patch.object(study.platform, 'platform', new=lambda: 'mock-platform')
    @patch.object(study.subprocess, 'check_output', return_value='revision\n')
    def test_prepare_freezes_all_commands_before_any_execution(self, git):
        binary = self.root / 'simulator/build/AggregationReplay'
        binary.parent.mkdir(parents=True)
        binary.write_text('fake native executable')
        binary.chmod(0o755)
        base = self.root / study.CORRECTION
        base.mkdir(parents=True)
        policy = dict(policy_tree=dict(execution=dict(strategy='semantic_first',
                    release_trigger='policy_satisfied', semantic_secondary_strategy='temporal_first'),
                    root=dict(semantic_suppression_fraction=dict(max=0))))
        for source in ('mixed', 'pedestrians'):
            dump(base / (source + '-observations.json'), dict(private_observations=[]))
            dump(base / (source + '_spatial20_adaptive_immediate_off-policy.json'), policy)
            dump(base / (source + '_spatial20_adaptive_immediate_off.json'), full_control())
        legacy_source = self.root / study.HISTORICAL_SOURCE
        legacy_source.parent.mkdir(parents=True)
        dump(legacy_source, dict(private_observations=['old-dense-source']))
        legacy_policy = self.root / study.HISTORICAL_POLICY
        legacy_policy.parent.mkdir(parents=True)
        legacy_configuration = copy.deepcopy(policy)
        legacy_configuration['policy_tree']['root'].pop('semantic_suppression_fraction')
        dump(legacy_policy, legacy_configuration)
        historical_evidence = self.root / study.HISTORICAL_EVIDENCE
        historical_evidence.parent.mkdir(parents=True)
        dump(historical_evidence, historical_evidence_fixture(legacy_source, legacy_policy))
        target = self.root / 'new-study'
        protocol = study.prepare(self.root, target, binary, study.SOURCES)
        self.assertEqual(len(protocol['cases']), 9)
        self.assertEqual(protocol['expected_sources']['old_dense']['duration_ms'], 240000)
        self.assertEqual(protocol['historical_failed_gate']['old_rejected_logical_time_ms'], 26850)
        legacy_cases = [case for case in protocol['cases'] if case['source'] == 'old_dense']
        self.assertTrue(all(case['historical_full'] is None for case in legacy_cases))
        self.assertTrue(all(case['full_validation'] == 'independent_policy_audit' for case in legacy_cases))
        self.assertTrue((target / 'protocol.json').is_file())
        self.assertTrue((target / 'provenance/AggregationReplay').stat().st_mode & 0o100)
        self.assertFalse(any(target.glob('*/*-execution.json')))
        study.require_unchanged(study.invariant_artifacts(protocol))
        self.assertEqual(protocol['offered_load']['queue_capacity'], 8)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            study.prepare(self.root, target, binary, study.SOURCES)
        policy['policy_tree']['root']['semantic_suppression_fraction']['max'] = .1
        dump(base / 'mixed_spatial20_adaptive_immediate_off-policy.json', policy)
        with self.assertRaisesRegex(ValueError, 'suppression-OFF'):
            study.prepare(self.root, self.root / 'bad-policy', binary, ('mixed',))
        self.assertFalse((self.root / 'bad-policy').exists())


if __name__ == '__main__':
    unittest.main()
