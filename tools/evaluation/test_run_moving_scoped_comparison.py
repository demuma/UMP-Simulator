"""Fairness, provenance, boundedness and failure-state tests for the moving pilot."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import run_moving_scoped_comparison as study


@contextmanager
def source_fixture():
    with tempfile.TemporaryDirectory(prefix='ump-moving-scoped-test-') as temporary:
        directory = Path(temporary)
        source = directory / 'capture'
        source.mkdir()
        replay = dict(schema='ump.observation-replay.v1', run_id='test-run', sensor_id='test-sensor',
            coverage=dict(x=0, y=0, width=80, height=80, leaf_depth=6),
            sampling_period_ms=100, end_ms=20000,
            batches=[dict(observed_at_ms=time, observations=[]) for time in range(100, 20000, 100)])
        study.write_json(source / 'observations.json', replay)
        study.write_json(source / 'capture-proof.json', dict(status='verified', private_token='never-copy'))
        rehash(source)
        implementation = directory / 'implementation'
        for name in study.DEPENDENCIES + (study.PROTOCOL,):
            target = implementation / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('Frozen test implementation: ' + name + '\n')
        binary = directory / 'core'
        binary.write_bytes(b'test binary')
        with patch.object(study, 'ROOT', implementation), patch.object(
                study, 'SOURCE_SHA256', study.digest(source / 'observations.json')):
            yield source, directory / 'output', binary, replay


def rehash(source):
    study.write_json(source / 'capture-manifest.json', dict(status='verified',
        private_database='never-copy', artifacts_sha256={
            name: study.digest(source / name) for name in study.SOURCE_FILES[:2]}),
        replace=(source / 'capture-manifest.json').exists())


def mock_execute(replay):
    def execute(command, directory, timeout, prefix=''):
        config = study.read_json(command[command.index('--config') + 1])
        mode = command[command.index('--mode') + 1]
        fixed_depth = int(command[command.index('--fixed-depth') + 1]) if '--fixed-depth' in command else None
        result = dict(schema='ump.replay-result.v1', mode=mode,
            source={**{key: deepcopy(replay[key]) for key in (
                'run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms')},
                'application_id': config['application_id']},
            parameters=dict(coordination=config['temporal_adaptation']['coordination'],
                window_ms=config['window_ms'], fixed_depth=fixed_depth,
                semantic_secondary_strategy=config['policy_tree']['execution']['semantic_secondary_strategy'],
                release_trigger='policy_satisfied'),
            runtime=dict(processing_ms=2 if prefix else 1), windows=[], releases=[])
        if mode == 'fixed':
            window = config['window_ms']
            result['windows'] = [dict(start_ms=start, end_ms=start + window,
                evaluated_at_ms=start + window, cells=[])
                for start in range(0, replay['end_ms'], window)]
        study.write_json(command[command.index('--output') + 1], result)
    return execute


def scalar_success():
    return dict(schema='test-oracle', valid=True, violations=[], released_cells=[{'private': 'do-not-copy'}],
                checked_windows=[{'private': 'do-not-copy'}], released_cell_count=0, no_release=True,
                released_observation_contributions=0, input_observation_contributions=0, scope={})


@contextmanager
def stub_core(replay):
    with patch.object(study, 'execute', side_effect=mock_execute(replay)), patch.object(
            study, 'scalar_audit', return_value=scalar_success()), patch.object(
            study, 'audit_result', return_value={'audit': {'status': 'verified'}, 'stats': {'released_observations': 0}}):
        yield


class MovingScopedRunnerTests(unittest.TestCase):
    def test_matrix_has_six_legal_fixed_and_four_adaptive_variants(self):
        matrix = study.variants()
        self.assertEqual(len(matrix), 10)
        self.assertEqual(len({row['id'] for row in matrix}), 10)
        self.assertEqual({(row['fixed_depth'], row['fixed_window_ms']) for row in matrix if row['mode'] == 'fixed'},
                         {(depth, window) for depth in (3, 4, 5) for window in (400, 1000)})
        self.assertEqual({(row['coordination'], row['secondary']) for row in matrix if row['mode'] != 'fixed'},
                         {(coord, second) for coord in ('common_window', 'cell_local') for second in study.SECONDARIES})

    def test_all_variants_share_hard_policy_and_taxonomy(self):
        configs = [study.config_for(row) for row in study.variants()]
        root = configs[0]['policy_tree']['root']
        self.assertEqual(root['window_duration_ms'], {'min': 400, 'max': 1000})
        self.assertEqual(root['cell_side_m'], {'min': 1.25, 'max': 10})
        self.assertEqual(root['min_category_distinct_contributors'], {'min': 5})
        for config, variant in zip(configs, study.variants()):
            self.assertEqual(config['policy_tree']['root'], root)
            self.assertEqual(config['semantic_taxonomy'], configs[0]['semantic_taxonomy'])
            self.assertEqual(config['policy_tree']['execution']['release_trigger'], 'policy_satisfied')
            self.assertEqual(config['policy_tree']['execution']['strategy'], 'semantic_first')
            self.assertEqual(config['temporal_adaptation']['max_active_cells'], 4096)
            self.assertEqual(config['spatial_selection']['preserve_valid_descendants'], variant['coordination'] == 'common_window')
            self.assertEqual(config['window_ms'], variant['fixed_window_ms'] or 400)
        with self.assertRaisesRegex(ValueError, 'matrix'):
            study.config_for({**study.variants()[0], 'fixed_depth': 2})

    def test_query_banks_and_fixed_matches_are_predeclared_and_bounded(self):
        banks = study.workloads(study.config_for(study.variants()[0]))
        self.assertEqual(len(banks), 4)
        expected = {'full_area_5m_w400ms': 384000, 'full_area_5m_w1000ms': 153600,
                    'full_area_10m_w400ms': 96000, 'full_area_10m_w1000ms': 38400}
        for name, bank in banks.items():
            count = 20000 // bank['window_ms'] * len(bank['target_cells']) * len(bank['categories']) * len(bank['lags_ms'])
            self.assertEqual(count, expected[name])
            self.assertLessEqual(count, study.MAX_QUERIES)
            self.assertEqual(bank['lags_ms'], [0, 200, 1000])
            self.assertIn(bank['matching_fixed_baseline'], {row['id'] for row in study.variants()})
        self.assertEqual(sum(expected.values()) * 10, 6720000)

    def test_verified_capture_provenance_contains_no_private_manifest_payload(self):
        with source_fixture() as (source, _, _, expected):
            replay, provenance = study.verify_capture(source)
            self.assertEqual(replay, expected)
            self.assertEqual(set(provenance['source_artifacts_sha256']), set(study.SOURCE_FILES))
            self.assertNotIn('never-copy', json.dumps(provenance))

    def test_hash_or_status_failure_precedes_output_creation(self):
        for action in ('bytes', 'manifest-status', 'proof-status'):
            with self.subTest(action=action), source_fixture() as (source, output, binary, _):
                if action == 'bytes':
                    with (source / 'observations.json').open('a') as target:
                        target.write(' ')
                else:
                    filename = 'capture-manifest.json' if action == 'manifest-status' else 'capture-proof.json'
                    value = study.read_json(source / filename)
                    value['status'] = 'unverified'
                    study.write_json(source / filename, value, replace=True)
                with self.assertRaises(ValueError):
                    study.run(source, output, binary)
                self.assertFalse(output.exists())

    def test_reauthenticated_different_capture_is_still_refused(self):
        with source_fixture() as (source, output, binary, _):
            with (source / 'observations.json').open('a') as target:
                target.write(' ')
            rehash(source)
            with self.assertRaisesRegex(ValueError, 'predeclared'):
                study.run(source, output, binary)
            self.assertFalse(output.exists())

    def test_missing_scheduled_frame_is_rejected_even_when_hash_matches(self):
        with source_fixture() as (source, _, _, replay):
            replay['batches'].pop()
            study.write_json(source / 'observations.json', replay, replace=True)
            rehash(source)
            with patch.object(study, 'SOURCE_SHA256', study.digest(source / 'observations.json')):
                with self.assertRaisesRegex(ValueError, '199 complete'):
                    study.verify_capture(source)

    def test_existing_and_nested_outputs_are_refused(self):
        with source_fixture() as (source, output, binary, _):
            output.mkdir()
            (output / 'keep').write_text('keep')
            with self.assertRaisesRegex(ValueError, 'existing'):
                study.run(source, output, binary)
            self.assertEqual((output / 'keep').read_text(), 'keep')
            with self.assertRaisesRegex(ValueError, 'frozen capture'):
                study.run(source, source / 'nested', binary)
            self.assertFalse((source / 'nested').exists())

    def test_repeat_ignores_only_runtime(self):
        first = dict(runtime={'processing_ms': 1}, releases=[{'count': 1}], windows=[])
        second = dict(runtime={'processing_ms': 2}, releases=[{'count': 1}], windows=[])
        self.assertEqual(study.normalized_result(first), study.normalized_result(second))
        second['releases'][0]['count'] = 2
        self.assertNotEqual(study.normalized_result(first), study.normalized_result(second))
        self.assertIn('runtime', first)

    def test_candidate_preflight_counts_crossing_parent_support(self):
        replay = {'end_ms': 20000, 'sampling_period_ms': 100}
        bank = study.workloads(study.config_for(study.variants()[0]))['full_area_5m_w400ms']
        releases = [dict(start_ms=0, end_ms=1000, cells=[dict(cell_id=192, depth=3)])]
        budget = study.budget_preflight(replay, releases, bank)
        # One10m parent intersects four5m targets and three400ms intervals.
        self.assertEqual(budget['indexed_candidate_checks'], 4 * 3 * 10 * 3)
        self.assertEqual(budget['expanded_queries'], 384000)
        with patch.object(study, 'MAX_CANDIDATE_CHECKS', 359):
            with self.assertRaisesRegex(ValueError, 'comparison budget'):
                study.budget_preflight(replay, releases, bank)
        with patch.object(study, 'MAX_QUERIES', 383999):
            with self.assertRaisesRegex(ValueError, 'query budget'):
                study.budget_preflight(replay, releases, bank)
        with patch.object(study, 'MAX_RECORDS', 0):
            with self.assertRaisesRegex(ValueError, 'record budget'):
                study.budget_preflight(replay, releases, bank)

    def test_scalar_compaction_excludes_private_rows(self):
        compacted = study.compact_scalar_audit(scalar_success())
        self.assertEqual(compacted['violation_count'], 0)
        self.assertEqual(compacted['checked_window_count'], 1)
        self.assertNotIn('released_cells', compacted)
        self.assertNotIn('do-not-copy', json.dumps(compacted))

    def test_metadata_mismatch_is_rejected(self):
        with source_fixture() as (_, output, _, replay):
            output.mkdir()
            variant = study.variants()[-1]
            config = study.config_for(variant)
            config_path, result_path = output / 'policy.json', output / 'result.json'
            study.write_json(config_path, config)
            command = study.command_for(Path('binary'), Path('source'), config_path, result_path, variant)
            mock_execute(replay)(command, output, 300)
            result = study.read_json(result_path)
            study.validate_result_metadata(replay, config, result, variant)
            result['parameters']['release_trigger'] = 'priority_satisfied'
            with self.assertRaisesRegex(ValueError, 'release trigger'):
                study.validate_result_metadata(replay, config, result, variant)

    def test_fixed_baseline_cannot_masquerade_as_adaptive_intervals_or_grid(self):
        with source_fixture() as (_, output, _, replay):
            output.mkdir()
            variant = study.variants()[0]
            config = study.config_for(variant)
            config_path, result_path = output / 'policy.json', output / 'result.json'
            study.write_json(config_path, config)
            command = study.command_for(Path('binary'), Path('source'), config_path, result_path, variant)
            mock_execute(replay)(command, output, 300)
            original = study.read_json(result_path)
            study.validate_result_metadata(replay, config, original, variant)
            mutations = (
                lambda value: value['windows'][0].update(end_ms=500),
                lambda value: value['windows'][0].update(cells=[{'depth': 6}]),
                lambda value: value.update(releases=[dict(start_ms=100, end_ms=400, sealed_at_ms=400, cells=[])]),
                lambda value: value.update(releases=[dict(start_ms=0, end_ms=400, sealed_at_ms=500, cells=[])]),
                lambda value: value.update(releases=[dict(start_ms=0, end_ms=400, sealed_at_ms=400, cells=[{'depth': 6}])]),
            )
            for mutation in mutations:
                value = deepcopy(original)
                mutation(value)
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Fixed baseline'):
                    study.validate_result_metadata(replay, config, value, variant)

    def test_core_failure_keeps_unverified_terminal_manifest(self):
        with source_fixture() as (source, output, binary, _), patch.object(
                study, 'execute', side_effect=RuntimeError('test core failure')):
            with self.assertRaisesRegex(RuntimeError, 'test core'):
                study.run(source, output, binary)
            terminal = study.read_json(output / 'study-manifest.json')
            self.assertEqual(terminal['status'], 'unverified')
            self.assertEqual(terminal['failure']['type'], 'RuntimeError')
            self.assertFalse((output / 'summary.json').exists())
            self.assertFalse((output / 'observations.json').exists())
            self.assertFalse((output / 'capture-manifest.json').exists())
            self.assertEqual(study.digest(output / 'AggregationReplay.frozen'), study.digest(binary))

    def test_evaluation_failure_cannot_mark_audited_core_study_verified(self):
        with source_fixture() as (source, output, binary, replay), stub_core(replay), patch.object(
                study, 'evaluate_workloads', side_effect=ValueError('test query failure')):
            with self.assertRaisesRegex(ValueError, 'test query'):
                study.run(source, output, binary)
            terminal = study.read_json(output / 'study-manifest.json')
            self.assertEqual(terminal['status'], 'unverified')
            self.assertEqual(len(terminal['commands']), 10)
            self.assertFalse((output / 'summary.json').exists())

    def test_complete_mock_core_run_freezes_sources_and_four_repeats(self):
        with source_fixture() as (source, output, binary, replay), stub_core(replay), patch.object(
                study, 'evaluate_workloads', return_value=({}, {}, {})), patch.object(
                study, 'population', return_value={'sampled_frames': 199}):
            original = study.tree_hashes(source)
            self.assertEqual(study.run(source, output, binary), output.resolve())
            terminal = study.read_json(output / 'study-manifest.json')
            summary = study.read_json(output / 'summary.json')
            self.assertEqual(terminal['status'], 'verified')
            self.assertEqual(len(terminal['determinism_repeats']), 4)
            self.assertEqual(summary['scientific_repeats'], 0)
            self.assertEqual(study.tree_hashes(source), original)
            self.assertEqual(len(summary['variants']), 10)
            self.assertNotIn('do-not-copy', json.dumps(summary))
            for filename, digest in terminal['artifacts_sha256'].items():
                self.assertEqual(study.digest(output / filename), digest)

    def test_changed_source_is_detected_after_core_and_evaluation(self):
        with source_fixture() as (source, output, binary, replay), stub_core(replay):
            def change(*args):
                (source / 'new-file').write_text('mutation')
                return {}, {}, {}
            with patch.object(study, 'evaluate_workloads', side_effect=change):
                with self.assertRaisesRegex(ValueError, 'source capture changed'):
                    study.run(source, output, binary)
            self.assertEqual(study.read_json(output / 'study-manifest.json')['status'], 'unverified')

    def test_workload_orchestration_runs_forty_banks_and_twentyfour_named_pairs(self):
        with source_fixture() as (_, output, _, replay):
            output.mkdir()
            (output / 'queries').mkdir()
            for variant in study.variants():
                directory = output / variant['id']
                directory.mkdir()
                config_path, result_path = directory / 'policy.json', directory / 'result.json'
                study.write_json(config_path, study.config_for(variant))
                mock_execute(replay)(study.command_for(Path('binary'), Path('source'), config_path,
                                                       result_path, variant), directory, 300)
            def empty_bank(replay, config, releases, **definition):
                return dict(schema='ump.scoped-semantic-queries.v1', query_definition=definition,
                    evaluations_by_lag_ms={str(lag): {'queries': [], 'summary': {}}
                                           for lag in definition['lags_ms']})
            banks = study.workloads(study.config_for(study.variants()[0]))
            with patch.object(study, 'evaluate', side_effect=empty_bank) as evaluator:
                evaluations, pairs, budgets = study.evaluate_workloads(replay, output, banks, study.variants())
            self.assertEqual(evaluator.call_count, 40)
            self.assertEqual(sum(map(len, evaluations.values())), 40)
            self.assertEqual(sum(map(len, budgets.values())), 40)
            self.assertEqual(len(pairs), 24)
            self.assertEqual(len(list((output / 'queries').glob('*.json'))), 64)
            for workload, bank in banks.items():
                selected = [key for key in pairs if key.endswith('--' + workload)]
                self.assertEqual(len(selected), 6)
                self.assertEqual(sum(key.startswith(bank['matching_fixed_baseline'] + '--') for key in selected), 4)
            for path in (output / 'queries').glob('*.json'):
                self.assertNotIn('"queries":', path.read_text())

    def test_repeat_semantic_difference_leaves_study_unverified(self):
        with source_fixture() as (source, output, binary, replay), stub_core(replay):
            def changed(command, directory, timeout, prefix=''):
                mock_execute(replay)(command, directory, timeout, prefix)
                if prefix:
                    path = Path(command[command.index('--output') + 1])
                    value = study.read_json(path)
                    value['unexpected_semantic_change'] = True
                    study.write_json(path, value, replace=True)
            with patch.object(study, 'execute', side_effect=changed):
                with self.assertRaisesRegex(ValueError, 'differs beyond runtime'):
                    study.run(source, output, binary)
            self.assertEqual(study.read_json(output / 'study-manifest.json')['status'], 'unverified')
            self.assertFalse((output / 'summary.json').exists())

    def test_timeout_preserves_partial_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            error = subprocess.TimeoutExpired(['test'], 1, output=b'partial stdout', stderr=b'partial stderr')
            with patch.object(study.subprocess, 'run', side_effect=error):
                with self.assertRaises(subprocess.TimeoutExpired):
                    study.execute(['test'], path, 1)
            self.assertEqual((path / 'stdout.log').read_text(), 'partial stdout')
            self.assertEqual((path / 'stderr.log').read_text(), 'partial stderr')


if __name__ == '__main__':
    unittest.main()
