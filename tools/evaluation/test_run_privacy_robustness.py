"""Independent pipeline checks for the predeclared long-horizon privacy study.

These tests use tiny independent cohorts and the real replay executable. They do
not reuse the completed four-second held-out evaluation or assert a desired AUC
ordering between the adaptive coordination mechanisms.
"""
import hashlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest

from empirical_privacy import attack_metrics, calibrate_threshold, feature_vector
from privacy_dataset import build_dataset, build_robustness_dataset
from robustness_attacks import SKLEARN_VERSION, fit_attack, predict_attack
from run_privacy_robustness import run_study

ROOT = Path(__file__).resolve().parents[2]
BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', str(ROOT / 'simulator/build/AggregationReplay')))
DISTRIBUTIONS = ('base', 'background_density_shift')
VARIANTS = {
    'fixed_20m_1000ms', 'common_temporal_first', 'local_temporal_first',
    'common_spatial_first', 'local_spatial_first',
}
CONTROLS = {'control_exact_count', 'control_no_output'}


def read_json(path):
    return json.loads(Path(path).read_text())


def make_dataset(path):
    return build_robustness_dataset(path, seed=20261021, train_groups=2,
        calibration_groups=2, test_groups=2, shifted_test_groups=2, end_ms=1000)


@unittest.skipUnless(BINARY.is_file(), 'Build AggregationReplay for the real robustness pipeline')
class RobustnessInputBoundaryTests(unittest.TestCase):
    def test_legacy_dataset_is_rejected_without_creating_study_output(self):
        with tempfile.TemporaryDirectory(prefix='ump-robustness-input-') as temporary:
            directory = Path(temporary)
            build_dataset(directory / 'legacy', 41, 2, 2, 2, 1000)
            output = directory / 'study'
            with self.assertRaises(ValueError):
                run_study(directory / 'legacy', output, BINARY,
                          bootstrap_repeats=0, attack_families=('logistic',))
            self.assertFalse(output.exists())

    def test_tampered_source_is_rejected_before_study_output(self):
        with tempfile.TemporaryDirectory(prefix='ump-robustness-tamper-') as temporary:
            directory = Path(temporary)
            manifest = make_dataset(directory / 'dataset')
            path = directory / 'dataset' / manifest['cases'][0]['present_input']
            path.write_text(path.read_text() + '\n')
            output = directory / 'study'
            with self.assertRaises(ValueError):
                run_study(directory / 'dataset', output, BINARY,
                          bootstrap_repeats=0, attack_families=('logistic',))
            self.assertFalse(output.exists())

    def test_invalid_attack_protocols_are_rejected_without_output(self):
        with tempfile.TemporaryDirectory(prefix='ump-robustness-invalid-') as temporary:
            directory = Path(temporary)
            make_dataset(directory / 'dataset')
            for index, families in enumerate(((), ('logistic', 'logistic'), ('unknown',))):
                output = directory / f'study-{index}'
                with self.subTest(families=families), self.assertRaises(ValueError):
                    run_study(directory / 'dataset', output, BINARY,
                              bootstrap_repeats=0, attack_families=families)
                self.assertFalse(output.exists())


@unittest.skipUnless(BINARY.is_file(), 'Build AggregationReplay for the real robustness pipeline')
class RobustnessPipelineTests(unittest.TestCase):
    def test_frozen_models_are_evaluated_separately_on_independent_base_and_shift_cohorts(self):
        with tempfile.TemporaryDirectory(prefix='ump-privacy-robustness-') as temporary:
            directory = Path(temporary)
            dataset, output = directory / 'dataset', directory / 'study'
            dataset_manifest = make_dataset(dataset)
            dataset_before = (dataset / 'manifest.json').read_bytes()
            report = run_study(dataset, output, BINARY,
                               bootstrap_repeats=10, attack_families=('logistic',))
            self.assertEqual(report['schema'], 'ump.privacy-robustness-report.v1')
            self.assertEqual(report['status'], 'complete')
            self.assertNotIn('test', report)
            self.assertEqual(report['independent_validation']['checks'], 8 * 2 * 5)
            self.assertTrue(report['independent_validation']['all_valid'])
            self.assertEqual(set(report['independent_validation']['deterministic_repeats']),
                             VARIANTS - {'fixed_20m_1000ms'})
            self.assertEqual((dataset / 'manifest.json').read_bytes(), dataset_before)
            protocol = read_json(output / 'protocol.json')
            saved = read_json(output / 'manifest.json')
            self.assertEqual(protocol['status'], 'predeclared')
            self.assertEqual(saved['status'], 'complete')
            self.assertEqual(hashlib.sha256((output / 'AggregationReplay.frozen').read_bytes()).hexdigest(),
                             protocol['binary_sha256'])
            self.assertEqual(hashlib.sha256((output / 'protocol.json').read_bytes()).hexdigest(),
                             saved['protocol_sha256'])
            self.assertEqual(hashlib.sha256((output / 'report.json').read_bytes()).hexdigest(),
                             saved['report_sha256'])
            attacks = report['attacks']
            self.assertEqual(len(attacks), 7 * 2)
            self.assertEqual({row['variant'] for row in attacks}, VARIANTS | CONTROLS)
            self.assertEqual({row['attack_family'] for row in attacks}, {'logistic'})
            self.assertEqual(len({row['knowledge_profile'] for row in attacks}), 2)
            for attack in attacks:
                model = attack['model_metadata']
                self.assertEqual(model['training_rows'], 4)
                self.assertEqual(model['fit_partition'], 'training_only')
                self.assertEqual(model['feature_count'], 31)
                self.assertEqual(set(attack['test_by_distribution']), set(DISTRIBUTIONS))
                for distribution in DISTRIBUTIONS:
                    assessment = attack['test_by_distribution'][distribution]
                    self.assertEqual(assessment['uncertainty']['groups'], 2)
                    self.assertEqual(assessment['test']['positive_cases'], 2)
                    self.assertEqual(assessment['test']['negative_cases'], 2)
                    if attack['variant'].startswith('local_'):
                        pair = assessment['paired_vs_common']
                        self.assertEqual(pair['independent_groups'], 2)
                        self.assertLessEqual(abs(pair['auc_difference']), 1)
                    if attack['variant'] == 'control_no_output':
                        self.assertEqual(assessment['test']['roc_auc'], .5)
            features = {tuple(record['key']): record['rows']
                        for record in read_json(output / 'features-private.json')}
            predictions = {tuple(record['key']): record['rows']
                           for record in read_json(output / 'test-predictions-private.json')}
            for attack in attacks:
                key = attack['variant'], attack['knowledge_profile']
                rows = features[key]
                training = [row for row in rows if row['split'] == 'train']
                calibration = [row for row in rows if row['split'] == 'calibration']
                self.assertTrue(all(row['distribution'] == 'base' for row in training + calibration))
                # An independently repeated fit must match exactly; adding CAL or
                # shifted/test rows to training changes this complete artifact.
                fitted = fit_attack([row['features'] for row in training],
                                    [row['label'] for row in training], 'logistic')
                self.assertEqual(attack['model_metadata'], fitted)
                calibrated = calibrate_threshold(predict_attack(fitted,
                    [row['features'] for row in calibration]),
                    [row['label'] for row in calibration], target_fpr=.1)
                self.assertEqual(attack['calibration'], calibrated)
                test_group_sets = []
                for distribution in DISTRIBUTIONS:
                    test_rows = [row for row in rows if row['split'] == 'test'
                                 and row['distribution'] == distribution]
                    scores = predict_attack(fitted, [row['features'] for row in test_rows])
                    expected = attack_metrics(scores, [row['label'] for row in test_rows],
                                              calibrated['threshold'])
                    self.assertEqual(attack['test_by_distribution'][distribution]['test'], expected)
                    persisted = predictions[(*key, 'logistic', distribution)]
                    self.assertEqual([row['score'] for row in persisted], scores)
                    test_group_sets.append({row['group_id'] for row in persisted})
                self.assertFalse(test_group_sets[0] & test_group_sets[1])
                for row in rows:
                    world = 'present' if row['label'] else 'absent'
                    artifact = hashlib.sha256(
                        f"{row['case_id']}:{world}:{attack['variant']}".encode()).hexdigest()[:24]
                    public = read_json(output / 'public' / (artifact + '.json'))
                    known = read_json(output / 'auxiliary' / (row['case_id'] + '.json'))
                    self.assertEqual(row['features'], feature_vector(public,
                        known['profiles'][attack['knowledge_profile']], include_geometry=True))
            for distribution in DISTRIBUTIONS:
                utility = report['utility_by_distribution'][distribution]
                self.assertEqual(set(utility), VARIANTS | CONTROLS)
                self.assertEqual(utility['control_exact_count']['answered_query_coverage'], 1)
                self.assertAlmostEqual(utility['control_exact_count']['occupancy_mae'], 0)
                self.assertEqual(utility['control_no_output']['answered_query_coverage'], 0)
                self.assertIsNone(utility['control_no_output']['occupancy_mae'])
                for name in ('common_temporal_first', 'local_temporal_first',
                             'common_spatial_first', 'local_spatial_first'):
                    self.assertIn('paired_scored_queries', utility[name])
                    self.assertIn('paired_support_mae', utility[name])
            configurations = {p.stem: read_json(p) for p in (output / 'policies').glob('*.json')}
            self.assertEqual(set(configurations), VARIANTS)
            original = read_json(dataset / 'policy.json')
            for name, config in configurations.items():
                self.assertEqual(config['temporal_adaptation']['coordination'],
                                 'cell_local' if name.startswith('local_') else 'common_window')
                self.assertEqual(config['policy_tree']['root'], original['policy_tree']['root'])
                self.assertEqual(config['policy_regions'], original['policy_regions'])
            commands = read_json(output / 'commands.json')
            self.assertEqual(len(commands), 80)
            for row in commands:
                command = row['command']
                self.assertEqual(Path(command[0]), output.resolve() / 'AggregationReplay.frozen')
                self.assertEqual(Path(command[command.index('--config') + 1]).name,
                                 row['variant'] + '.json')
            public_paths = list((output / 'public').glob('*.json'))
            self.assertEqual(len(public_paths), 8 * 2 * 7)
            for path in public_paths:
                public = read_json(path)
                self.assertEqual(set(public), {'schema', 'coverage', 'sampling_period_ms', 'end_ms', 'releases'})
            before = (output / 'manifest.json').read_bytes()
            with self.assertRaises(FileExistsError):
                run_study(dataset, output, BINARY,
                          bootstrap_repeats=10, attack_families=('logistic',))
            self.assertEqual((output / 'manifest.json').read_bytes(), before)
            dangling, missing = directory / 'dangling', directory / 'missing'
            dangling.symlink_to(missing)
            with self.assertRaises(FileExistsError):
                run_study(dataset, dangling, BINARY,
                          bootstrap_repeats=0, attack_families=('logistic',))
            self.assertFalse(missing.exists())
            self.assertEqual(dataset_manifest['test_cohort_group_counts'],
                             {'base': 2, 'background_density_shift': 2})


def histogram_available():
    try:
        return sys.version_info >= (3, 11) and importlib.metadata.version('scikit-learn') == SKLEARN_VERSION
    except importlib.metadata.PackageNotFoundError:
        return False


@unittest.skipUnless(BINARY.is_file() and histogram_available(),
                     'Optional pinned Python/scikit-learn robustness environment required')
class NonlinearRobustnessPipelineTests(unittest.TestCase):
    def test_default_families_share_inputs_and_keep_independent_frozen_models(self):
        with tempfile.TemporaryDirectory(prefix='ump-nonlinear-robustness-') as temporary:
            directory = Path(temporary).resolve()
            dataset, output = directory / 'dataset', directory / 'study'
            make_dataset(dataset)
            report = run_study(dataset, output, BINARY, bootstrap_repeats=2)
            attacks = report['attacks']
            self.assertEqual(len(attacks), 28)
            self.assertEqual({row['attack_family'] for row in attacks},
                             {'logistic', 'hist_gradient_boosting'})
            self.assertEqual(report['independent_validation']['checks'], 80)
            self.assertEqual(len(list((output / 'models').glob('*.joblib'))), 14)
            metadata_paths = set()
            for attack in attacks:
                model = attack['model_metadata']
                self.assertEqual(model['training_rows'], 4)
                self.assertEqual(model['fit_partition'], 'training_only')
                for distribution in DISTRIBUTIONS:
                    self.assertEqual(attack['test_by_distribution'][distribution]['test']['threshold'],
                                     attack['calibration']['threshold'])
                if attack['attack_family'] == 'hist_gradient_boosting':
                    model_path = Path(model['model_path'])
                    metadata_paths.add(model_path)
                    self.assertEqual(model_path.parent, output / 'models')
                    self.assertEqual(model_path.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(hashlib.sha256(model_path.read_bytes()).hexdigest(), model['model_sha256'])
                    self.assertEqual(model['versions']['scikit-learn'], SKLEARN_VERSION)
                    self.assertEqual(model['threads'], 1)
                    self.assertEqual(model['iterations'], 64)
            self.assertEqual(len(metadata_paths), 14)


if __name__ == '__main__':
    unittest.main()
