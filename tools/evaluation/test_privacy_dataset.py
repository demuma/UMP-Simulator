"""Independent contract checks for controlled contribution-membership datasets."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from make_fixture import cell_id
from privacy_dataset import (GRID, SCENARIOS, build_dataset, generate_case,
                             normalized_fingerprint, target_knowledge,
                             validate_case, validate_dataset)


class ControlledCaseTests(unittest.TestCase):
    def test_seed_and_case_names_are_reproducible_but_independent(self):
        first = generate_case(42, 'heterogeneous', 'first')
        self.assertEqual(first, generate_case(42, 'heterogeneous', 'first'))
        changed_seed = generate_case(43, 'heterogeneous', 'first')
        changed_case = generate_case(42, 'heterogeneous', 'second')
        self.assertNotEqual(normalized_fingerprint(first['present']), normalized_fingerprint(changed_seed['present']))
        self.assertNotEqual(normalized_fingerprint(first['present']), normalized_fingerprint(changed_case['present']))

    def test_every_scenario_has_exact_frozen_neighbours_and_valid_geometry(self):
        for scenario in SCENARIOS:
            for horizon in (4000, 8000):
                with self.subTest(scenario=scenario, horizon=horizon):
                    case = generate_case(731, scenario, 'case', horizon)
                    validate_case(case)
                    present, absent = case['present'], case['absent']
                    self.assertEqual(present['run_id'], absent['run_id'])
                    self.assertEqual(present['coverage'], GRID)
                    self.assertEqual(len(present['batches']), horizon // 100 - 1)
                    self.assertEqual([b['observed_at_ms'] for b in present['batches']], list(range(100, horizon, 100)))
                    self.assertTrue(case['target_trace'])
                    for left, right in zip(present['batches'], absent['batches']):
                        self.assertEqual({k: v for k, v in left.items() if k != 'observations'},
                                         {k: v for k, v in right.items() if k != 'observations'})
                        self.assertEqual(right['observations'], [o for o in left['observations'] if o['id'] != case['target_id']])
                        for observation in left['observations']:
                            self.assertEqual(observation['cell_id'], cell_id(observation['x'], observation['y'], GRID))

    def test_prescribed_modes_stay_in_their_corridors(self):
        found_modes = set()
        for seed in range(8):
            case = generate_case(seed, 'heterogeneous', f'case-{seed}')
            for batch in case['present']['batches']:
                for observation in batch['observations']:
                    mode, y = observation['type'], observation['y']
                    found_modes.add(mode)
                    bounds = {'pedestrian': (10, 23), 'bicycle': (29, 31), 'car': (48, 52)}[mode]
                    self.assertGreaterEqual(y, bounds[0])
                    self.assertLessEqual(y, bounds[1])
        self.assertEqual(found_modes, {'pedestrian', 'bicycle', 'car'})

    def test_motion_variation_density_and_turnover_are_realized(self):
        sparse_counts, dense_counts, trajectory_hashes = set(), set(), set()
        for seed in range(12):
            sparse = generate_case(seed, 'sparse', f'sparse-{seed}')
            dense = generate_case(seed, 'dense', f'dense-{seed}')
            sparse_counts.add(len(sparse['absent']['batches'][10]['observations']))
            dense_counts.add(len(dense['absent']['batches'][10]['observations']))
            trajectory_hashes.add(json.dumps(sparse['target_trace'], sort_keys=True))
        self.assertGreater(len(sparse_counts), 1)
        self.assertGreater(len(dense_counts), 1)
        self.assertGreater(min(dense_counts), max(sparse_counts))
        self.assertEqual(len(trajectory_hashes), 12)
        handover = generate_case(3, 'handover', 'turnover')
        observations = handover['absent']['batches']
        first = {o['id'] for batch in observations[:10] for o in batch['observations']}
        last = {o['id'] for batch in observations[-10:] for o in batch['observations']}
        self.assertTrue(first)
        self.assertTrue(last)
        self.assertFalse(first & last)

    def test_empty_sampling_opportunities_survive_target_removal(self):
        case = generate_case(22, 'sparse', 'single')
        # An analytical source with only the candidate checks the measured-empty
        # contract without depending on a particular random population draw.
        for batch in case['present']['batches']:
            batch['observations'] = [o for o in batch['observations'] if o['id'] == case['target_id']]
        for batch in case['absent']['batches']:
            batch['observations'] = []
        validate_case(case)
        self.assertTrue(all(b['status'] == 'measured' and not b['observations'] for b in case['absent']['batches']))

    def test_background_and_target_corruption_are_rejected(self):
        original = generate_case(7, 'dense', 'original')
        changes = [lambda c: c['absent']['batches'][0].update(status='unavailable'),
                   lambda c: c['absent']['batches'].pop(),
                   lambda c: c['absent']['batches'][10]['observations'][0].update(x=0),
                   lambda c: c['target_trace'][0].update(x=0),
                   lambda c: c['absent'].update(run_id='other'),
                   lambda c: [c[key].update(schema='unsupported') for key in ('present', 'absent')],
                   lambda c: c['present']['batches'][10]['observations'][0].update(type='unknown'),
                   lambda c: c['present']['batches'][10]['observations'][0].update(x=True)]
        for change in changes:
            case = deepcopy(original)
            change(case)
            with self.assertRaises(ValueError):
                validate_case(case)

    def test_invalid_generator_arguments_fail(self):
        for args in [(-1, 'sparse', 'case', 4000), (True, 'sparse', 'case', 4000),
                     (1, 'unknown', 'case', 4000), (1, 'sparse', '../escape', 4000),
                     (1, 'sparse', '', 4000), (1, 'sparse', 'case', 1050),
                     (1, 'sparse', 'case', 0), (1, 'sparse', 'case', 60001)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                generate_case(*args)

    def test_knowledge_is_reproducible_partial_chronological_and_id_free(self):
        trace = generate_case(17, 'dense', 'candidate')['target_trace']
        before = deepcopy(trace)
        knowledge = target_knowledge(trace, .25, 8)
        self.assertEqual(knowledge, target_knowledge(trace, .25, 8))
        self.assertNotEqual(knowledge, target_knowledge(trace, .25, 9))
        self.assertEqual(len(knowledge), 10)
        self.assertEqual(trace, before)
        self.assertEqual(target_knowledge(trace, 1, 8), trace)
        self.assertEqual([p['observed_at_ms'] for p in knowledge], sorted(p['observed_at_ms'] for p in knowledge))
        self.assertTrue(all(set(point) == {'observed_at_ms', 'x', 'y', 'cell_id'} for point in knowledge))
        knowledge[0]['x'] = -1
        self.assertEqual(trace, before)

    def test_invalid_or_private_knowledge_is_rejected(self):
        trace = generate_case(17, 'dense', 'candidate')['target_trace']
        for fraction in (0, -1, 1.1, True, float('nan'), float('inf'), '0.25'):
            with self.assertRaises(ValueError):
                target_knowledge(trace, fraction, 8)
        for bad in ([], [dict(trace[0], id='private')], [dict(trace[0], cell_id=12)], [dict(trace[0], x=float('nan'))], list(reversed(trace))):
            with self.assertRaises(ValueError):
                target_knowledge(bad, .25, 8)

    def test_fingerprint_ignores_identity_names_but_preserves_trajectories(self):
        case = generate_case(42, 'dense', 'sample')
        renamed = deepcopy(case['present'])
        renamed['run_id'] = 'different'
        for batch in renamed['batches']:
            for observation in batch['observations']:
                observation['id'] = 'renamed-' + observation['id']
        self.assertEqual(normalized_fingerprint(case['present']), normalized_fingerprint(renamed))
        renamed['batches'][0]['observations'][0]['x'] += .001
        self.assertNotEqual(normalized_fingerprint(case['present']), normalized_fingerprint(renamed))


class DatasetBundleTests(unittest.TestCase):
    def build(self, path, **kwargs):
        return build_dataset(path, 114, train_groups=4, calibration_groups=4, test_groups=4, **kwargs)

    def test_private_manifest_hashes_splits_and_deterministic_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / 'first', root / 'second'
            manifest = self.build(first)
            self.assertEqual(manifest, self.build(second))
            validate_dataset(manifest, first)
            self.assertEqual(len(manifest['cases']), 12)
            groups = {split: {c['group_id'] for c in manifest['cases'] if c['split'] == split}
                      for split in ('train', 'calibration', 'test')}
            self.assertFalse(groups['train'] & groups['test'])
            self.assertFalse(groups['train'] & groups['calibration'])
            self.assertFalse(groups['calibration'] & groups['test'])
            for split in groups:
                self.assertEqual({c['scenario'] for c in manifest['cases'] if c['split'] == split}, set(SCENARIOS))
            for source in first.rglob('*.json'):
                self.assertEqual(source.read_bytes(), (second / source.relative_to(first)).read_bytes())
            policy = json.loads((first / 'policy.json').read_text())
            self.assertEqual(policy['policy_tree']['root']['distinct_contributors']['min'], 3)
            self.assertEqual(manifest['classification'], 'private_research_bundle')
            self.assertIn('not_full_physical', manifest['utility_reference'])

    def test_overwrite_and_invalid_counts_create_no_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'dataset'
            self.build(output)
            before = (output / 'manifest.json').read_bytes()
            with self.assertRaises(FileExistsError):
                self.build(output)
            self.assertEqual(before, (output / 'manifest.json').read_bytes())
            for key, value in [('train_groups', 0), ('calibration_groups', -1), ('test_groups', True),
                               ('end_ms', 1501), ('support_threshold', 0), ('seed', -1)]:
                args = dict(seed=114, train_groups=1, calibration_groups=1, test_groups=1)
                args[key] = value
                destination = root / f'invalid-{key}'
                with self.subTest(key=key), self.assertRaises(ValueError):
                    build_dataset(destination, **args)
                self.assertFalse(destination.exists())

    def test_symlink_output_and_escaping_manifest_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            link = root / 'output'
            link.symlink_to(root / 'not-yet-existing', target_is_directory=True)
            with self.assertRaises(FileExistsError):
                self.build(link)
            manifest = self.build(root / 'valid')
            for path in ('../outside.json', '/private/tmp/outside.json'):
                corrupted = deepcopy(manifest)
                corrupted['cases'][0]['present_input'] = path
                with self.assertRaises(ValueError):
                    validate_dataset(corrupted, root / 'valid')

    def test_hash_split_and_clone_leakage_checks_detect_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'dataset'
            manifest = self.build(root)
            duplicate = deepcopy(manifest)
            duplicate['cases'][1]['group_id'] = duplicate['cases'][0]['group_id']
            with self.assertRaisesRegex(ValueError, 'reused'):
                validate_dataset(duplicate, root)
            clone = deepcopy(manifest)
            clone['cases'][4] = dict(clone['cases'][0], case_id='copy', group_id='copy', split='calibration')
            with self.assertRaisesRegex(ValueError, 'Cloned'):
                validate_dataset(clone, root)
            changed = root / manifest['cases'][0]['present_input']
            changed.write_bytes(changed.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                validate_dataset(manifest, root)

    def test_cli_and_help(self):
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(__file__).with_name('privacy_dataset.py')
            output = Path(temporary) / 'cli'
            completed = subprocess.run([sys.executable, str(script), '--output', str(output), '--seed', '31',
                                        '--train-groups', '1', '--calibration-groups', '1', '--test-groups', '1'],
                                       text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('3 independent paired cases', completed.stdout)
            self.assertTrue((output / 'manifest.json').is_file())
            help_result = subprocess.run([sys.executable, str(script), '--help'], text=True, capture_output=True)
            self.assertEqual(help_result.returncode, 0)
            self.assertIn('--support-threshold', help_result.stdout)


if __name__ == '__main__':
    unittest.main()
