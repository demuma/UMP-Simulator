"""Provenance, unchanged exact scores, bounded orchestration and failure tests."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import recipient_support
import run_recipient_contract_study as study


def full_fixture(definition):
    """Small orchestration stand-in; algorithm correctness has separate tests."""
    return dict(schema=recipient_support.SCHEMA,
        query_definition={key: deepcopy(definition[key]) for key in study.QUERY_KEYS},
        recipient_contract={'uniform_estimate_enabled': True},
        evaluations_by_lag_ms={str(lag): dict(
            queries=[{'private_row': 'must-not-be-written'}],
            summary={'interior': {'answered_query_count': 0}, 'boundary': {}},
            recipient_support_summary={'interior': {'fixture': True}, 'boundary': {}})
            for lag in definition['lags_ms']})


def result_fixture(replay, variant):
    config = study.parent.config_for(variant)
    result = dict(schema='ump.replay-result.v1', mode=variant['mode'],
        source={**{key: deepcopy(replay[key]) for key in (
            'run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms')},
            'application_id': config['application_id']},
        parameters=dict(coordination=variant['coordination'], window_ms=config['window_ms'],
            fixed_depth=variant['fixed_depth'], semantic_secondary_strategy=variant['secondary'],
            release_trigger='policy_satisfied'), releases=[], windows=[])
    if variant['mode'] == 'fixed':
        window = variant['fixed_window_ms']
        result['windows'] = [dict(start_ms=start, end_ms=start + window,
            evaluated_at_ms=start + window, cells=[])
            for start in range(0, replay['end_ms'], window)]
    return result


def update_parent_hash(directory, relative):
    manifest = study.read_json(directory / 'study-manifest.json')
    manifest['artifacts_sha256'][relative] = study.digest(directory / relative)
    study.write_json(directory / 'study-manifest.json', manifest, replace=True)
    return study.digest(directory / 'study-manifest.json')


@contextmanager
def frozen_fixture():
    with tempfile.TemporaryDirectory(prefix='ump-recipient-runner-test-') as temporary:
        root = Path(temporary).resolve()
        comparison, capture, implementation = (root / name for name in ('parent', 'capture', 'implementation'))
        comparison.mkdir()
        capture.mkdir()
        (comparison / 'queries').mkdir()
        replay = dict(schema='ump.observation-replay.v1', run_id='fixture-source', sensor_id='fixture-sensor',
            coverage=dict(x=0, y=0, width=80, height=80, leaf_depth=6),
            sampling_period_ms=100, end_ms=20000,
            batches=[dict(observed_at_ms=time, status='measured', observations=[])
                     for time in range(100, 20000, 100)])
        study.write_json(capture / 'observations.json', replay)
        study.write_json(capture / 'capture-proof.json', dict(status='verified', private_token='never-copy'))
        study.write_json(capture / 'capture-manifest.json', dict(status='verified', private_database='never-copy',
            artifacts_sha256={name: study.digest(capture / name) for name in study.parent.SOURCE_FILES[:2]}))
        matrix = study.parent.variants()
        workloads = study.parent.workloads(study.parent.config_for(matrix[0]))
        evaluations = {}
        for variant in matrix:
            directory = comparison / variant['id']
            directory.mkdir()
            study.write_json(directory / 'policy.json', study.parent.config_for(variant))
            study.write_json(directory / 'result.json', result_fixture(replay, variant))
            evaluations[variant['id']] = {}
            for workload, definition in workloads.items():
                filename = f"queries/{variant['id']}--{workload}.json"
                study.write_json(comparison / filename, study.exact_projection(full_fixture(definition)))
                evaluations[variant['id']][workload] = filename
        study.write_json(comparison / 'summary.json', dict(schema=study.parent.SCHEMA, status='verified',
            evaluation_count=40, paired_comparison_count=24, source_capture_unchanged=True,
            evaluations=evaluations))
        study.write_json(comparison / 'study-manifest.json', dict(schema=study.parent.SCHEMA,
            status='verified', evaluation_count=40, paired_comparison_count=24,
            source_capture_unchanged=True, variants=matrix, workloads=workloads,
            source_capture=str(capture), source_artifacts_sha256={
                name: study.digest(capture / name) for name in study.parent.SOURCE_FILES},
            artifacts_sha256=study.parent.tree_hashes(comparison)))
        for name in study.DEPENDENCIES + (study.PROTOCOL,):
            target = implementation / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('Frozen implementation fixture: ' + name + '\n')
        source_hash = study.digest(capture / 'observations.json')
        with patch.object(study, 'ROOT', implementation), patch.object(
                study, 'PARENT_MANIFEST_SHA256', study.digest(comparison / 'study-manifest.json')), \
                patch.object(study, 'SOURCE_SHA256', source_hash), patch.object(
                study.parent, 'SOURCE_SHA256', source_hash):
            yield comparison, root / 'output', capture


@contextmanager
def mocked_evaluation():
    def evaluate(replay, config, releases, **kwargs):
        if kwargs.pop('uniform_estimate') is not True:
            raise AssertionError('The explicit estimator must be enabled for this declared study')
        return full_fixture(kwargs)

    def pair(a, b):
        if a['query_definition'] != b['query_definition']:
            raise AssertionError('Pairing changed fixed workload identities')
        return dict(schema='fixture-paired', summary={'same_queries': True})

    with patch.object(study.recipient, 'evaluate', side_effect=evaluate) as evaluator, \
            patch.object(study.recipient, 'paired_summary', side_effect=pair) as pairing, \
            patch.object(study.parent, 'execute') as core:
        yield evaluator, pairing, core


class RecipientRunnerTests(unittest.TestCase):
    def test_accepts_only_pinned_verified_parent_and_source(self):
        with frozen_fixture() as (comparison, _, capture):
            frozen = study.verify_parent(comparison)
            self.assertEqual(frozen['capture'], capture)
            self.assertEqual(len(frozen['matrix']), 10)
            self.assertEqual(len(frozen['workloads']), 4)
            self.assertEqual(len(frozen['parent_hashes']), 61)
            self.assertNotIn('private_token', str(frozen['safe_source']))
            self.assertNotIn('private_database', str(frozen['safe_source']))

    def test_refuses_unpinned_parent_manifest_before_creating_output(self):
        with frozen_fixture() as (comparison, output, _):
            with (comparison / 'study-manifest.json').open('a') as file:
                file.write(' ')
            with self.assertRaisesRegex(ValueError, 'Parent manifest differs'):
                study.run(comparison, output)
            self.assertFalse(output.exists())

    def test_refuses_unverified_parent_even_with_matching_digest(self):
        with frozen_fixture() as (comparison, _, _):
            path = comparison / 'study-manifest.json'
            manifest = study.read_json(path)
            manifest['status'] = 'unverified'
            study.write_json(path, manifest, replace=True)
            with patch.object(study, 'PARENT_MANIFEST_SHA256', study.digest(path)):
                with self.assertRaisesRegex(ValueError, 'verified complete'):
                    study.verify_parent(comparison)

    def test_refuses_missing_or_modified_result_and_policy(self):
        for relative, remove in (('fixed_10m_400ms/result.json', True),
                                 ('cell_local_temporal_first/policy.json', False)):
            with self.subTest(relative=relative), frozen_fixture() as (comparison, _, _):
                path = comparison / relative
                if remove:
                    path.unlink()
                else:
                    with path.open('a') as file:
                        file.write(' ')
                with self.assertRaisesRegex(ValueError, 'artifact'):
                    study.verify_parent(comparison)

    def test_refuses_missing_parent_artifact_digest(self):
        with frozen_fixture() as (comparison, _, _):
            path = comparison / 'study-manifest.json'
            manifest = study.read_json(path)
            manifest['artifacts_sha256'].pop('fixed_10m_400ms/policy.json')
            study.write_json(path, manifest, replace=True)
            with patch.object(study, 'PARENT_MANIFEST_SHA256', study.digest(path)):
                with self.assertRaisesRegex(ValueError, 'digest'):
                    study.verify_parent(comparison)

    def test_refuses_query_compact_tampering(self):
        with frozen_fixture() as (comparison, _, _):
            file = comparison / 'queries/fixed_10m_400ms--full_area_5m_w400ms.json'
            file.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'digest'):
                study.verify_parent(comparison)

    def test_refuses_changed_source_after_valid_parent(self):
        with frozen_fixture() as (comparison, _, capture):
            path = capture / 'observations.json'
            value = study.read_json(path)
            value['run_id'] = 'different-source'
            study.write_json(path, value, replace=True)
            with self.assertRaisesRegex(ValueError, 'capture digest'):
                study.verify_parent(comparison)

    def test_refuses_changed_policy_even_when_artifact_hash_is_updated(self):
        with frozen_fixture() as (comparison, _, _):
            relative = 'cell_local_temporal_first/policy.json'
            value = study.read_json(comparison / relative)
            value['policy_tree']['root']['window_duration_ms']['min'] = 100
            study.write_json(comparison / relative, value, replace=True)
            with patch.object(study, 'PARENT_MANIFEST_SHA256', update_parent_hash(comparison, relative)):
                with self.assertRaisesRegex(ValueError, 'matched requirements'):
                    study.verify_parent(comparison)

    def test_refuses_changed_result_execution_metadata(self):
        with frozen_fixture() as (comparison, _, _):
            relative = 'fixed_10m_400ms/result.json'
            value = study.read_json(comparison / relative)
            value['parameters']['fixed_depth'] = 4
            study.write_json(comparison / relative, value, replace=True)
            with patch.object(study, 'PARENT_MANIFEST_SHA256', update_parent_hash(comparison, relative)):
                with self.assertRaisesRegex(ValueError, 'execution parameters'):
                    study.verify_parent(comparison)

    def test_refuses_changed_workload_or_query_index(self):
        with frozen_fixture() as (comparison, _, _):
            relative = 'summary.json'
            value = study.read_json(comparison / relative)
            value['evaluations']['fixed_10m_400ms']['full_area_5m_w400ms'] = '../outside.json'
            study.write_json(comparison / relative, value, replace=True)
            with patch.object(study, 'PARENT_MANIFEST_SHA256', update_parent_hash(comparison, relative)):
                with self.assertRaisesRegex(ValueError, 'forty banks'):
                    study.verify_parent(comparison)

    def test_refuses_escaping_artifact_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('../outside.json', '/tmp/absolute.json', ''):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    study._file(root, name)

    def test_refuses_existing_output_without_modifying_it(self):
        with frozen_fixture() as (comparison, output, _):
            output.mkdir()
            marker = output / 'keep.txt'
            marker.write_text('keep')
            with self.assertRaisesRegex(ValueError, 'replace'):
                study.run(comparison, output)
            self.assertEqual(marker.read_text(), 'keep')

    def test_refuses_output_inside_comparison_or_source(self):
        with frozen_fixture() as (comparison, _, capture):
            for destination in (comparison / 'new-output', capture / 'new-output'):
                with self.subTest(destination=destination), self.assertRaisesRegex(ValueError, 'inside'):
                    study.run(comparison, destination)
                self.assertFalse(destination.exists())

    def test_exact_projection_discards_only_additive_fields(self):
        definition = study.parent.workloads(study.parent.config_for(study.parent.variants()[0]))
        full = full_fixture(next(iter(definition.values())))
        projected = study.exact_projection(full)
        self.assertEqual(projected['schema'], study.exact.SCHEMA)
        self.assertEqual(projected['query_definition'], full['query_definition'])
        self.assertNotIn('recipient_contract', projected)
        self.assertNotIn('must-not-be-written', str(projected))
        for lag in projected['evaluations_by_lag_ms']:
            self.assertEqual(projected['evaluations_by_lag_ms'][lag],
                             {'summary': full['evaluations_by_lag_ms'][lag]['summary']})

    def test_complete_matrix_and_pairs_keep_exact_scores_and_write_only_compacts(self):
        with frozen_fixture() as (comparison, output, capture), mocked_evaluation() as (evaluate, pair, core):
            before_parent = study.parent.tree_hashes(comparison)
            before_capture = study.parent.tree_hashes(capture)
            self.assertEqual(study.run(comparison, output), output)
            self.assertEqual(evaluate.call_count, 40)
            self.assertEqual(pair.call_count, 24)
            core.assert_not_called()
            summary = study.read_json(output / 'summary.json')
            self.assertEqual(summary['legacy_exact_compact_match_count'], 40)
            self.assertEqual(len(summary['pairs']), 24)
            self.assertEqual(sum(map(len, summary['evaluations'].values())), 40)
            self.assertEqual(sum(1 for _ in (output / 'queries').glob('*.json')), 64)
            for path in output.rglob('*.json'):
                text = path.read_text()
                self.assertNotIn('must-not-be-written', text)
                self.assertNotIn('never-copy', text)
            manifest = study.read_json(output / 'study-manifest.json')
            self.assertEqual(manifest['status'], 'verified')
            self.assertFalse(manifest['source_observations_copied'])
            self.assertFalse(manifest['raw_releases_copied'])
            self.assertEqual(manifest['new_producer_executions'], 0)
            for name, expected in manifest['artifacts_sha256'].items():
                self.assertEqual(study.digest(output / name), expected)
            self.assertEqual(study.parent.tree_hashes(comparison), before_parent)
            self.assertEqual(study.parent.tree_hashes(capture), before_capture)

    def test_legacy_exact_drift_fails_and_never_marks_study_verified(self):
        with frozen_fixture() as (comparison, output, _), mocked_evaluation() as (evaluate, _, _):
            def drift(replay, config, releases, **kwargs):
                full = full_fixture(kwargs)
                full['evaluations_by_lag_ms']['0']['summary']['interior']['answered_query_count'] = 1
                return full
            evaluate.side_effect = drift
            with self.assertRaisesRegex(ValueError, 'Legacy exact evaluation changed'):
                study.run(comparison, output)
            manifest = study.read_json(output / 'study-manifest.json')
            self.assertEqual(manifest['status'], 'unverified')
            self.assertIn('Legacy exact', manifest['failure']['message'])
            self.assertFalse((output / 'summary.json').exists())

    def test_evaluator_budget_failure_is_not_silently_skipped(self):
        with frozen_fixture() as (comparison, output, _), mocked_evaluation() as (evaluate, _, _):
            evaluate.side_effect = ValueError('Public tile/query comparison budget exceeded')
            with self.assertRaisesRegex(ValueError, 'budget exceeded'):
                study.run(comparison, output)
            self.assertEqual(study.read_json(output / 'study-manifest.json')['status'], 'unverified')

    def test_source_or_parent_mutation_during_study_fails(self):
        for target in ('source', 'parent'):
            with self.subTest(target=target), frozen_fixture() as (comparison, output, capture), mocked_evaluation() as (evaluate, _, _):
                original = evaluate.side_effect
                changed = False
                def mutate(replay, config, releases, **kwargs):
                    nonlocal changed
                    if not changed:
                        path = capture / 'capture-proof.json' if target == 'source' else comparison / 'summary.json'
                        with path.open('a') as file:
                            file.write(' ')
                        changed = True
                    return original(replay, config, releases, **kwargs)
                evaluate.side_effect = mutate
                with self.assertRaisesRegex(ValueError, 'changed during'):
                    study.run(comparison, output)
                self.assertEqual(study.read_json(output / 'study-manifest.json')['status'], 'unverified')

    def test_implementation_mutation_during_study_fails(self):
        with frozen_fixture() as (comparison, output, _), mocked_evaluation() as (evaluate, _, _):
            original = evaluate.side_effect
            def mutate(replay, config, releases, **kwargs):
                with (study.ROOT / study.DEPENDENCIES[0]).open('a') as file:
                    file.write(' ')
                return original(replay, config, releases, **kwargs)
            evaluate.side_effect = mutate
            with self.assertRaisesRegex(ValueError, 'implementation changed'):
                study.run(comparison, output)
            self.assertEqual(study.read_json(output / 'study-manifest.json')['status'], 'unverified')


if __name__ == '__main__':
    unittest.main()
