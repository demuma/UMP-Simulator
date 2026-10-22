"""Protocol/provenance tests for the fixed asynchronous semantic query study."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_scoped_semantic_utility as study
from run_semantic_local_policy import configuration
from run_local_policy_replay import fixture


@contextmanager
def input_study():
    with tempfile.TemporaryDirectory(prefix='ump-scoped-study-') as temporary:
        root = Path(temporary)
        source = root / 'source'
        source.mkdir()
        data = fixture()
        study.write_json(source / 'observations.json', data)
        total = sum(len(batch['observations']) for batch in data['batches'])
        for name, coord, region, secondary in study.VARIANTS:
            config = configuration(coord, region == 'regional', secondary)
            result = {'schema': 'ump.replay-result.v1', 'mode': 'semantic_first',
                'source': {**{key: deepcopy(data[key]) for key in
                    ('run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms')},
                    'application_id': config['application_id']},
                'parameters': {'coordination': coord, 'semantic_secondary_strategy': secondary},
                'input_observation_contributions': total, 'accounted_observation_contributions': total,
                'releases': []}
            study.write_json(source / (name + '-policy.json'), config)
            study.write_json(source / (name + '.json'), result)
        rehash(source)
        # Separate provenance fixture: production protocol must already exist for
        # an actual study, whereas these tests must not depend on its prose.
        provenance = root / 'implementation'
        for name in ('tools/evaluation/run_scoped_semantic_utility.py',
                     'tools/evaluation/scoped_semantic_queries.py', study.PROTOCOL):
            target = provenance / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('Frozen test provenance: ' + name + '\n')
        with patch.object(study, 'ROOT', provenance):
            yield source, root / 'output'


def rehash(source):
    study.write_json(source / 'study-manifest.json', {
        'schema': 'ump.semantic-cell-local-study.v1', 'status': 'verified',
        'artifacts_sha256': {name: study.digest((source / name).read_bytes()) for name in study.REQUIRED}})


def change(source, name, mutation):
    content = study.read_json((source / name).read_bytes())
    mutation(content)
    study.write_json(source / name, content)
    rehash(source)


def contains_key(value, key):
    if isinstance(value, dict):
        return key in value or any(contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, key) for item in value)
    return False


class ScopedSemanticStudyTests(unittest.TestCase):
    def test_workload_is_fixed_independent_of_outputs(self):
        value = study.workloads(configuration('common_window', True, 'temporal_first'))
        self.assertEqual(len(value), 6)
        self.assertEqual([cell['cell_id'] for cell in value['six_rois_2p5m_w400ms']['target_cells']],
                         [3075, 3120, 3168, 3184, 3360, 3376])
        self.assertEqual(len(value['full_area_5m_w400ms']['target_cells']), 256)
        fine = value['six_rois_1p25m_w400ms']['target_cells']
        self.assertEqual(len(fine), 24)
        self.assertEqual({cell['cell_id'] // 4 for cell in fine}, {3075, 3120, 3168, 3184, 3360, 3376})
        self.assertEqual(len(value['full_area_5m_w400ms']['categories']), 10)
        self.assertTrue(all(item['lags_ms'] == [0, 200, 400] for item in value.values()))
        self.assertEqual({item['window_ms'] for item in value.values()}, {400, 1000})

    def test_all_seventeen_hashes_are_verified_before_creating_output(self):
        self.assertEqual(len(study.REQUIRED), 17)
        with input_study() as (source, output):
            last = source / study.REQUIRED[-1]
            last.write_bytes(last.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'digest'):
                study.run(source, output)
            self.assertFalse(output.exists())

    def test_existing_output_and_nested_source_output_are_refused(self):
        with input_study() as (source, output):
            output.mkdir()
            sentinel = output / 'keep.txt'
            sentinel.write_text('keep')
            with self.assertRaisesRegex(ValueError, 'existing'):
                study.run(source, output)
            self.assertEqual(sentinel.read_text(), 'keep')
            with self.assertRaisesRegex(ValueError, 'frozen source'):
                study.run(source, source / 'new-output')
            self.assertFalse((source / 'new-output').exists())

    def test_unverified_source_study_is_refused(self):
        with input_study() as (source, output):
            manifest = source / 'study-manifest.json'
            record = study.read_json(manifest.read_bytes())
            record['status'] = 'unverified'
            study.write_json(manifest, record)
            with self.assertRaisesRegex(ValueError, 'verified'):
                study.run(source, output)
            self.assertFalse(output.exists())

    def test_authenticated_metadata_mismatch_is_refused_before_output(self):
        mutations = (
            ('.json', lambda d: d['source'].update(run_id='other')),
            ('.json', lambda d: d['parameters'].update(coordination='cell_local')),
            ('-policy.json', lambda d: d['semantic_taxonomy'].update(id='different')),
            ('-policy.json', lambda d: d['policy_tree']['root']['distinct_contributors'].update(min=99)),
        )
        for suffix, mutation in mutations:
            with self.subTest(suffix=suffix), input_study() as (source, output):
                change(source, study.VARIANTS[0][0] + suffix, mutation)
                with self.assertRaises(ValueError):
                    study.run(source, output)
                self.assertFalse(output.exists())

    def test_truth_audit_failure_preserves_unverified_manifest(self):
        with input_study() as (source, output):
            change(source, study.VARIANTS[0][0] + '.json',
                   lambda d: d.update(accounted_observation_contributions=0))
            with self.assertRaisesRegex(ValueError, 'accounting'):
                study.run(source, output)
            manifest = study.read_json((output / 'study-manifest.json').read_bytes())
            self.assertEqual(manifest['status'], 'unverified')
            self.assertEqual(manifest['failure']['type'], 'ValueError')
            self.assertFalse((output / 'summary.json').exists())
            self.assertEqual(len(manifest['input_artifacts_sha256']), 17)

    def test_evaluation_failure_never_marks_study_verified(self):
        with input_study() as (source, output), patch.object(study, 'evaluate', side_effect=ValueError('test failure')):
            before = study.tree_hashes(source)
            with self.assertRaisesRegex(ValueError, 'test failure'):
                study.run(source, output)
            self.assertEqual(study.tree_hashes(source), before)
            record = study.read_json((output / 'study-manifest.json').read_bytes())
            self.assertEqual(record['status'], 'unverified')
            self.assertEqual(record['failure']['message'], 'test failure')
            self.assertFalse((output / 'summary.json').exists())

    def test_private_truth_audit_rejects_unknown_or_cyclic_taxonomy_parents(self):
        data = fixture()
        for parent in ('adult_pedestrian', 'missing'):
            config = configuration('common_window', True, 'temporal_first')
            nodes = {node['id']: node for node in config['semantic_taxonomy']['nodes']}
            nodes['pedestrian']['parent'] = parent
            matching = [row for batch in data['batches'] for row in batch['observations']
                        if row['cell_id'] == 12300]
            count, distinct = len(matching), len({row['id'] for row in matching})
            self.assertEqual((count, distinct), (76, 4))
            result = {'input_observation_contributions': 380, 'accounted_observation_contributions': 380,
                'releases': [{'start_ms': 0, 'end_ms': 2000, 'cells': [{
                    'cell_id': 12300, 'depth': 6, 'observation_contributions': count,
                    'distinct_road_users': distinct, 'semantic': {'categories': [{
                        'category_id': 'road_user', 'observation_contributions': count,
                        'distinct_contributors': distinct}]}}]}]}
            with self.subTest(parent=parent), self.assertRaisesRegex(ValueError, 'parent or cycle'):
                study.audit_released_counts(data, config, result)

    def test_complete_empty_public_study_uses_all_fixed_queries_without_copying_inputs(self):
        with input_study() as (source, output):
            before = study.tree_hashes(source)
            self.assertEqual(study.run(source, output), output.resolve())
            self.assertEqual(study.tree_hashes(source), before)
            manifest = study.read_json((output / 'study-manifest.json').read_bytes())
            summary = study.read_json((output / 'summary.json').read_bytes())
            self.assertEqual((manifest['status'], manifest['evaluation_count'], manifest['paired_comparison_count']),
                             ('verified', 48, 24))
            self.assertTrue(manifest['source_study_unchanged'])
            self.assertEqual(len(summary['evaluations']), 8)
            self.assertFalse((output / 'observations.json').exists())
            self.assertTrue(all(audit['released_observations'] == 0 for audit in summary['released_count_audits'].values()))
            for filename, expected in manifest['artifacts_sha256'].items():
                self.assertEqual(study.digest((output / filename).read_bytes()), expected)
            for variants in summary['evaluations'].values():
                self.assertEqual(len(variants), 6)
                for filename in variants.values():
                    result = study.read_json((output / filename).read_bytes())
                    self.assertFalse(contains_key(result, 'queries'))
                    for projection in result['evaluations_by_lag_ms'].values():
                        self.assertEqual(projection['summary']['interior']['answered_query_count'], 0)


if __name__ == '__main__':
    unittest.main()
