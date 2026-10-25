"""Prospective recording independence checks using miniature synthetic files only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import urban_privacy_split as split


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def design():
    methods = [{'id': f'fixed{side}_{window}', 'kind': 'native_fixed', 'grid_side_m': side,
                'window_ms': window, 'policy_audit_required': True}
               for side in (10, 20) for window in split.WINDOWS_MS]
    methods += [{'id': 'regional20', 'kind': 'regional_static', 'grid_side_m': 20,
                 'components': [f'fixed20_{window}' for window in split.WINDOWS_MS],
                 'selection': 'public_policy_only', 'policy_audit_required': True},
                {'id': 'adaptive_semantic', 'kind': 'native_adaptive', 'strategy': 'semantic_first',
                 'policy_audit_required': True}]
    return {'study_id': 'new-study', 'master_seed': 87192,
            'group_counts': {'train': 2, 'calibration': 2, 'test': 2}, 'targets_per_recording': 1,
            'generator': {'law_id': 'mapped-mixed-v1', 'scene_configuration_sha256': sha('scene'),
                          'map_geometry_sha256': sha('map'), 'end_ms': 300000, 'population': 128,
                          'sensor_period_ms': 100, 'gt_period_ms': 50},
            'conditions': [{'id': 'spatial20', 'policy': {'path': 'policy.json', 'sha256': sha('policy')},
                            'hard_requirements_sha256': sha('hard bounds')}], 'methods': methods,
            'attack_protocol': {'availability_model': 'final_snapshot_at_horizon',
                                'selection': 'TRAIN_fit_CAL_threshold_TEST_once'},
            'analysis_protocol': {'independence_unit': 'recording', 'uncertainty': 'recording_cluster_bootstrap'},
            'resource_limits': {'scene_wall_s': 90, 'capture_wall_s': 90, 'native_case_wall_s': 240}}


def pilot():
    return {'schema': 'ump.urban-privacy-sources.v1', 'status': 'verified',
            'cases': [{'group_id': 'pilot-' + str(i), 'seed': 2026102501 + i, 'status': 'verified',
                       'observations_sha256': sha('source' + str(i)),
                       'normalized_source_fingerprint': sha('normal' + str(i)),
                       'planned_route_fingerprint': sha('plan' + str(i))} for i in range(8)]}


def source(offset=0):
    return {'schema': 'ump.observation-replay.v1', 'run_id': 'private-run', 'sensor_id': 'private-sensor',
            'coverage': {'x': 0, 'y': 0, 'width': 80, 'height': 80, 'leaf_depth': 6},
            'sampling_period_ms': 100, 'end_ms': 300000,
            'batches': [{'sequence': i, 'observed_at_ms': 100 * i, 'status': 'measured',
                         'observations': ([{'id': 'target', 'type': 'pedestrian', 'cell_id': 1,
                                           'x': offset + i, 'y': 2},
                                          {'id': 'background', 'type': 'car', 'cell_id': 2,
                                           'x': offset + 40 + i, 'y': 40}] if i in (1, 2) else [])}
                        for i in range(1, 3000)]}


def history():
    # Pure-manifest tests use declared miniature evidence. Freeze tests patch the
    # pinned historical hash to these exact test bytes; no real capture is read.
    replay = source(11)
    return [{'group_id': 'historical-mixed', 'seed': 20261024,
             'source': {'path': 'historical-source.json', 'sha256': split.HISTORICAL_SOURCE_SHA256},
             'observations_sha256': split.HISTORICAL_SOURCE_SHA256,
             'normalized_source_fingerprint': split.normalized_fingerprint(replay, legacy=True),
             'normalized_source_fingerprint_v2': split.normalized_fingerprint(replay),
             'target_ids': [], 'background_fingerprints': [], 'normalized_trajectory_fingerprints': []}]


class ProspectiveTests(unittest.TestCase):
    def setUp(self):
        self.manifest = split.build_manifest(design(), pilot(), history())

    def test_deterministic_preassigned_group_and_seed_roles(self):
        self.assertEqual(self.manifest, split.build_manifest(design(), pilot(), history()))
        split.validate_manifest(self.manifest)
        groups = self.manifest['groups']
        self.assertEqual(len(groups), 6)
        self.assertEqual(len({r['group_id'] for r in groups}), 6)
        self.assertEqual(len({v for r in groups for v in r['seeds'].values()}), 18)
        self.assertTrue(all(r['source_state'] == 'planned_not_generated' for r in groups))
        self.assertEqual(self.manifest['actual_recordings'], 0)
        self.assertEqual(self.manifest['attack_runs'], 0)
        excluded = {r['seed'] for r in self.manifest['exclusions'] if 'seed' in r}
        self.assertFalse(excluded & {v for r in groups for v in r['seeds'].values()})

    def test_design_tamper_changes_commitment_or_is_rejected(self):
        for mutation in ('split', 'seed', 'role', 'count', 'pilot'):
            with self.subTest(mutation=mutation):
                changed = deepcopy(self.manifest)
                if mutation == 'split':
                    changed['groups'][0]['split'] = 'test'
                elif mutation == 'seed':
                    changed['groups'][0]['seeds']['source_generation'] = 20261024
                elif mutation == 'role':
                    changed['groups'][0]['seeds']['target_selection'] = changed['groups'][0]['seeds']['auxiliary_selection']
                elif mutation == 'count':
                    changed['design']['group_counts']['train'] += 1
                else:
                    changed['exclusions'][0]['group_id'] = changed['groups'][0]['group_id']
                with self.assertRaises(ValueError):
                    split.validate_manifest(changed)

    def test_pilot_never_becomes_primary_or_effective_sample(self):
        self.assertEqual(len(self.manifest['exclusions']), 10)
        self.assertEqual(self.manifest['budget_projection']['independent_recordings'], 6)
        self.assertEqual(self.manifest['pilot_role'], 'development_only_excluded_from_train_calibration_test')
        for change in ('short', 'failure', 'clone', 'numeric_clone', 'seed'):
            p = pilot()
            if change == 'short':
                p['cases'].pop()
            elif change == 'failure':
                p['cases'][0]['status'] = 'failed'
            elif change == 'clone':
                p['cases'][1]['normalized_source_fingerprint'] = p['cases'][0]['normalized_source_fingerprint']
            elif change == 'numeric_clone':
                p['cases'][0]['normalized_source_fingerprint_v2'] = sha('numeric disguise')
                p['cases'][1]['normalized_source_fingerprint_v2'] = sha('numeric disguise')
            else:
                p['cases'][1]['seed'] = p['cases'][0]['seed']
            with self.subTest(change=change), self.assertRaises(ValueError):
                split.build_manifest(design(), p, history())

    def test_pinned_historical_source_requires_normalized_clone_evidence(self):
        for records in ([], [{'seed': 20261024}], [{'observations_sha256': split.HISTORICAL_SOURCE_SHA256}]):
            with self.subTest(records=records), self.assertRaisesRegex(ValueError, 'historical mixed source fingerprints'):
                split.build_manifest(design(), pilot(), records)

    def test_resource_projection_counts_sources_not_target_rows(self):
        d = design()
        d['group_counts'] = {'train': 24, 'calibration': 16, 'test': 32}
        d['targets_per_recording'] = 4
        result = split.budget_projection(d)
        self.assertEqual(result['independent_recordings'], 72)
        self.assertEqual(result['episode_pairs'], 288)
        self.assertEqual(result['native_cases_without_reuse'], 5184)
        self.assertEqual(result['independent_out_unit_fpr_step']['calibration'], 1 / 16)
        self.assertEqual(result['independent_out_unit_fpr_step']['test'], 1 / 32)
        self.assertEqual(result['pooled_dependent_episode_out_fpr_step']['test'], 1 / 128)

    def test_bad_policy_and_comparator_declarations_fail(self):
        for change in ('window', 'grid', 'regional', 'selection', 'audit', 'independence', 'horizon', 'bool'):
            d = design()
            if change == 'window':
                d['methods'][0]['window_ms'] = 50
            elif change == 'grid':
                d['methods'][0]['grid_side_m'] = 5
            elif change == 'regional':
                d['methods'][-2]['components'].pop()
            elif change == 'selection':
                d['methods'][-2]['selection'] = 'test_best'
            elif change == 'audit':
                d['methods'][0]['policy_audit_required'] = False
            elif change == 'independence':
                d['analysis_protocol']['independence_unit'] = 'episode'
            elif change == 'horizon':
                d['generator']['end_ms'] = 4000
            else:
                d['group_counts']['test'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                split.build_manifest(d, pilot(), history())

    def derivative(self):
        group = self.manifest['groups'][0]
        return {'source_group_id': group['group_id'], 'group_id': group['group_id'], 'split': group['split'],
                'target_slot': 'target-00', 'world': 'IN', 'method_id': 'adaptive_semantic',
                'condition_id': 'spatial20', 'hard_requirements_sha256': sha('hard bounds'),
                'excerpt': {'start_ms': 100, 'end_ms': 500}}

    def test_all_world_policy_method_excerpt_derivatives_remain_grouped(self):
        record = self.derivative()
        split.validate_derivatives(self.manifest, [record, dict(record, world='OUT', method_id='fixed10_400')])
        for field, value in (('split', 'unseen'), ('group_id', 'different'), ('target_slot', 'target-10'),
                             ('source_group_id', 'pilot-0'), ('world', 'PRESENT'), ('method_id', 'unknown'),
                             ('hard_requirements_sha256', sha('different'))):
            with self.subTest(field=field), self.assertRaises(ValueError):
                split.validate_derivatives(self.manifest, [dict(record, **{field: value})])


class ActualAndFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        patched = patch.object(split, 'HISTORICAL_SOURCE_SHA256', hashlib.sha256(split.encoded(source(11))).hexdigest())
        patched.start()
        self.addCleanup(patched.stop)
        self.put('historical-source.json', source(11))
        self.manifest = split.build_manifest(design(), pilot(), history())
        self.pilot_evidence = pilot()
        for index, case in enumerate(self.pilot_evidence['cases']):
            directory = self.root / ('pilot' + str(index))
            directory.mkdir()
            replay = source(20 + 2 * index)
            (directory / 'observations.json').write_bytes(split.encoded(replay))
            case.update(replay_directory=str(directory), observations_sha256=split.file_sha(directory / 'observations.json'),
                        normalized_source_fingerprint=split.normalized_fingerprint(replay, legacy=True),
                        configuration_equivalence_sha256=sha('scene'))

    def put(self, name, value):
        path = self.root / name
        path.write_bytes(split.encoded(value))
        return {'path': name, 'sha256': split.file_sha(path)}

    def actual(self, index=0, replay=None):
        group = self.manifest['groups'][index]
        replay = source(index * 3) if replay is None else replay
        absent = deepcopy(replay)
        for batch in absent['batches']:
            batch['observations'] = [o for o in batch['observations'] if o['id'] != 'target']
        return {'group_id': group['group_id'], 'split': group['split'],
                'source_generation_seed': group['seeds']['source_generation'],
                'source': self.put(f'source-{index}.json', replay),
                'targets': [{'target_slot': 'target-00', 'target_id': 'target',
                             'out': self.put(f'out-{index}.json', absent)}]}

    def test_actual_source_checks_exact_out_and_keeps_empty_batch(self):
        actual = self.actual()
        checked = split.verify_actual_sources(self.manifest, [actual], self.root)
        self.assertEqual(checked['independent_recordings_checked'], 1)
        self.assertFalse(checked['primary_complete'])
        out = split.load(self.root / actual['targets'][0]['out']['path'])
        self.assertEqual(out['batches'][-1]['observations'], [])
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            split.verify_actual_sources(self.manifest, [actual], self.root, require_complete=True)

    def test_source_file_hash_and_seed_are_required(self):
        actual = self.actual()
        for change in ('hash', 'seed', 'split'):
            changed = deepcopy(actual)
            if change == 'hash':
                changed['source']['sha256'] = sha('forged')
            elif change == 'seed':
                changed['source_generation_seed'] += 1
            else:
                changed['split'] = 'development'
            with self.subTest(change=change), self.assertRaises(ValueError):
                split.verify_actual_sources(self.manifest, [changed], self.root)

    def test_coherent_out_background_tamper_fails_after_rehash(self):
        actual = self.actual()
        absent = split.load(self.root / actual['targets'][0]['out']['path'])
        absent['batches'][0]['observations'][0]['x'] += 1
        actual['targets'][0]['out'] = self.put('out-0.json', absent)
        with self.assertRaisesRegex(ValueError, 'remove only'):
            split.verify_actual_sources(self.manifest, [actual], self.root)

    def test_excerpt_cannot_masquerade_as_independent_full_recording(self):
        replay = source()
        replay['batches'].pop()
        actual = self.actual(replay=replay)
        with self.assertRaisesRegex(ValueError, 'excerpts cannot be separate groups'):
            split.verify_actual_sources(self.manifest, [actual], self.root)

    def test_renamed_id_source_clone_is_not_independent(self):
        first = self.actual()
        renamed = source()
        renamed['run_id'] = 'unrelated-private-run'
        for batch in renamed['batches']:
            batch['observations'].reverse()
            for observation in batch['observations']:
                observation['id'] = {'target': 'target', 'background': 'renamed-bg'}[observation['id']]
                observation['x'] = float(observation['x'])
        second = self.actual(1, renamed)
        with self.assertRaisesRegex(ValueError, 'Cloned source'):
            split.verify_actual_sources(self.manifest, [first, second], self.root)

    def test_header_numeric_reserialization_cannot_hide_renamed_clone(self):
        original = source()
        renamed = deepcopy(original)
        renamed['run_id'] = 'renamed-private-run'
        renamed['sensor_id'] = 'renamed-private-sensor'
        renamed['coverage'] = {key: float(value) for key, value in original['coverage'].items()}
        renamed['end_ms'] = float(original['end_ms'])
        renamed['sampling_period_ms'] = float(original['sampling_period_ms'])
        for batch in renamed['batches']:
            batch['sequence'] = float(batch['sequence'])
            for observation in batch['observations']:
                observation['id'] = {'target': 'target', 'background': 'renamed-bg'}[observation['id']]
                for key in ('x', 'y', 'cell_id'):
                    observation[key] = float(observation[key])
        self.assertNotEqual(split.normalized_fingerprint(original, legacy=True),
                            split.normalized_fingerprint(renamed, legacy=True))
        self.assertEqual(split.normalized_fingerprint(original), split.normalized_fingerprint(renamed))
        first, second = self.actual(), self.actual(1, renamed)
        with self.assertRaisesRegex(ValueError, 'Cloned source'):
            split.verify_actual_sources(self.manifest, [first, second], self.root)

    def test_background_and_trajectory_clones_across_sources_fail(self):
        for kind in ('background', 'trajectory'):
            first = self.actual()
            replay = source(3)
            for batch in replay['batches']:
                for o in batch['observations']:
                    if o['id'] == ('background' if kind == 'background' else 'target'):
                        o['x'] -= 3
            second = self.actual(1, replay)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'Cloned ' + kind):
                split.verify_actual_sources(self.manifest, [first, second], self.root)

    def test_pilot_and_historical_actual_clones_are_excluded(self):
        p = pilot()
        p['cases'][0]['normalized_source_fingerprint'] = split.normalized_fingerprint(source(), legacy=True)
        manifest = split.build_manifest(design(), p, history())
        with self.assertRaisesRegex(ValueError, 'overlaps DEV/historical'):
            split.verify_actual_sources(manifest, [self.actual()], self.root)
        manifest = split.build_manifest(design(), pilot(), history() + [{'normalized_trajectory_fingerprint':
                                        split.normalized_fingerprint(source(), target_id='target')}])
        with self.assertRaisesRegex(ValueError, 'overlaps excluded'):
            split.verify_actual_sources(manifest, [self.actual()], self.root)

    def test_legacy_fingerprint_matches_existing_private_dataset_algorithm(self):
        # Independent transcription of the legacy digest format, no capture data.
        replay = source()
        trajectories = []
        for identity in ('target', 'background'):
            trajectory = []
            for batch in replay['batches']:
                for o in batch['observations']:
                    if o['id'] == identity:
                        trajectory.append([batch['observed_at_ms'], o['type'], o['x'], o['y'], o['cell_id']])
            trajectories.append(trajectory)
        payload = {'coverage': replay['coverage'], 'end_ms': replay['end_ms'],
                   'sampling_period_ms': replay['sampling_period_ms'],
                   'opportunities': [[b['sequence'], b['observed_at_ms'], b['status']] for b in replay['batches']],
                   'trajectories': sorted(trajectories, key=lambda x: json.dumps(x, separators=(',', ':')))}
        expected = hashlib.sha256((json.dumps(payload, indent=2, sort_keys=True) + '\n').encode()).hexdigest()
        self.assertEqual(split.normalized_fingerprint(replay, legacy=True), expected)

    def test_path_escape_symlink_directory_and_nonfinite_are_rejected(self):
        actual = self.actual()
        bad_refs = [dict(actual['source'], path='../outside.json'),
                    dict(actual['source'], path=str(self.root / 'source-0.json')),
                    dict(actual['source'], path='.')]
        (self.root / 'link.json').symlink_to(self.root / 'source-0.json')
        bad_refs.append(dict(actual['source'], path='link.json'))
        for reference in bad_refs:
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                split.relative_file(self.root, reference)
        with self.assertRaises(ValueError):
            split.read_bytes(self.root)
        (self.root / 'nan.json').write_text('{"x": NaN}')
        with self.assertRaises(ValueError):
            split.load(self.root / 'nan.json')

    def test_private_fresh_freeze_reopens_and_detects_mutation(self):
        self.root.joinpath('policy.json').write_bytes(b'policy')
        self.put('input-design.json', design())
        self.put('input-pilot.json', self.pilot_evidence)
        self.put('input-history.json', history())
        output = self.root / 'freeze'
        args = (self.root / 'input-design.json', self.root / 'input-pilot.json', self.root / 'input-history.json', output)
        checked = split.freeze(*args, evidence_root=self.root)
        self.assertEqual(checked['actual_primary_recordings'], 0)
        self.assertEqual(checked['planned_group_counts'], design()['group_counts'])
        self.assertEqual(split.verify_freeze(output), checked)
        with self.assertRaises(ValueError):
            split.freeze(*args, evidence_root=self.root)
        (output / 'manifest.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Frozen file changed'):
            split.verify_freeze(output)

    def test_frozen_policy_is_copied_and_independent_of_original_file(self):
        self.root.joinpath('policy.json').write_bytes(b'policy')
        self.put('input-design.json', design())
        self.put('input-pilot.json', self.pilot_evidence)
        self.put('input-history.json', history())
        output = self.root / 'freeze'
        checked = split.freeze(self.root / 'input-design.json', self.root / 'input-pilot.json',
                               self.root / 'input-history.json', output, evidence_root=self.root)
        self.root.joinpath('policy.json').write_bytes(b'edited after freeze')
        self.assertEqual(split.verify_freeze(output), checked)
        copied = output / 'policy-spatial20.json'
        self.assertEqual(copied.read_bytes(), b'policy')
        copied.write_bytes(b'forged')
        with self.assertRaisesRegex(ValueError, 'Frozen file changed'):
            split.verify_freeze(output)

    def test_generator_evidence_bytes_are_frozen_and_verified(self):
        self.root.joinpath('policy.json').write_bytes(b'policy')
        declared = design()
        declared['generator']['evidence_files'] = [self.put('generator-proof.json', {'law': 'fixed'})]
        self.put('input-design.json', declared)
        self.put('input-pilot.json', self.pilot_evidence)
        self.put('input-history.json', history())
        output = self.root / 'freeze'
        checked = split.freeze(self.root / 'input-design.json', self.root / 'input-pilot.json',
                               self.root / 'input-history.json', output, evidence_root=self.root)
        self.put('generator-proof.json', {'law': 'edited'})
        self.assertEqual(split.verify_freeze(output), checked)
        (output / 'generator-evidence-00.bin').write_bytes(b'altered')
        with self.assertRaisesRegex(ValueError, 'Frozen file changed'):
            split.verify_freeze(output)

    def test_freeze_rejects_changed_policy_and_world_readable_artifacts(self):
        self.root.joinpath('policy.json').write_bytes(b'different policy')
        self.put('input-design.json', design())
        self.put('input-pilot.json', self.pilot_evidence)
        self.put('input-history.json', history())
        args = (self.root / 'input-design.json', self.root / 'input-pilot.json', self.root / 'input-history.json', self.root / 'freeze')
        with self.assertRaisesRegex(ValueError, 'provenance hash'):
            split.freeze(*args, evidence_root=self.root)
        self.root.joinpath('policy.json').write_bytes(b'policy')
        split.freeze(*args, evidence_root=self.root)
        (self.root / 'freeze' / 'manifest.json').chmod(0o644)
        with self.assertRaisesRegex(ValueError, '0600'):
            split.verify_freeze(self.root / 'freeze')

    def test_freeze_reauthenticates_historical_and_pilot_fingerprints_and_law(self):
        self.root.joinpath('policy.json').write_bytes(b'policy')
        self.put('input-design.json', design())
        for change, message in (('history', 'Historical source fingerprints'),
                                ('pilot', 'DEV pilot normalized fingerprint'),
                                ('law', 'same generator law')):
            historical = history()
            evidence = deepcopy(self.pilot_evidence)
            if change == 'history':
                historical[0]['normalized_source_fingerprint_v2'] = sha('coherently forged receipt')
            elif change == 'pilot':
                evidence['cases'][0]['normalized_source_fingerprint'] = sha('coherently forged receipt')
            else:
                evidence['cases'][0]['configuration_equivalence_sha256'] = sha('different law')
            self.put('input-history.json', historical)
            self.put('input-pilot.json', evidence)
            output = self.root / ('bad-' + change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                split.freeze(self.root / 'input-design.json', self.root / 'input-pilot.json',
                             self.root / 'input-history.json', output, evidence_root=self.root)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
