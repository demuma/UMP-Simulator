"""Small authenticated capture mocks; no movement/native replay/attack jobs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

_SPEC = importlib.util.spec_from_file_location('ump_p25_1_urban_fixture_tool',
                                               Path(__file__).with_name('urban_privacy_fixture.py'))
fixture = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fixture)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fixture.encoded(value))


class UrbanFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / 'results').mkdir()
        (self.root / '.gitignore').write_text('results/\n')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, capture_output=True)
        self.tool = self.root / 'tools/evaluation/urban_privacy_fixture.py'
        self.tool.parent.mkdir(parents=True)
        self.tool.write_bytes(Path(fixture.__file__).read_bytes())
        self.patch_root = mock.patch.object(fixture, 'PROJECT_ROOT', self.root)
        self.patch_file = mock.patch.object(fixture, '__file__', str(self.tool))
        self.patch_root.start()
        self.patch_file.start()
        self.study = self.root / 'results/spatial20-controller-correction-2026-10-24-v2'
        self.capture = self.root / 'results/original-capture/replay'
        self.output = self.root / 'results/private-dev-fixture'
        self.contract = self.root / 'docs/contract.md'
        self.contract.parent.mkdir()
        self.contract.write_text('Frozen mock P25.1 membership contract; no attack.\n')
        origin = datetime(2026, 10, 24, tzinfo=timezone.utc)
        stamp = lambda t: (origin + timedelta(milliseconds=t)).isoformat().replace('+00:00', 'Z')
        episodes = [('episode-a', 0, 600, 'Adult', 12), ('episode-b', 150, 1000, 'Child', 25),
                    ('episode-c', 0, 1000, 'Adult', 36), ('episode-d', 150, 250, 'Child', 40)]
        self.raw = {'agents': [dict(data_type='metadata', timestamp=stamp(0), frame_rate=20,
            observation_identity_unit='visible_episode_track', ground_truth_identity_unit='synthetic_person',
            support_contract='one_episode_per_retained_history')],
            'releases': [{'private_or_outcome': 'not decoded'}], 'journals': [{'private_or_outcome': 'not decoded'}]}
        sensor = {}
        for index, (identity, begin, end, kind, x) in enumerate(episodes):
            person = 'person-' + str(index)
            for event, at in [('visible_start', begin), ('visible_end', end)]:
                self.raw['agents'].append(dict(data_type='mapped lifecycle event', observation_track_id=identity,
                    private_person_id=person, route_id='route-' + str(index), event=event,
                    timestamp=stamp(at), processed_at_ms=at))
            for at in range(begin, end, 50):
                point = dict(x=x + at / 10000, y=20)
                self.raw['agents'].append(dict(data_type='agent data', timestamp=stamp(at), agent_id=identity,
                    observation_track_id=identity, private_person_id=person, type=kind, position=point))
                if at and at % 100 == 0:
                    sensor.setdefault(at, []).append(dict(id=identity, type=kind, **point,
                        cell_id=fixture.cell_id(point['x'], point['y'], fixture.COVERAGE)))
        self.raw['agents'].append(dict(data_type='mapped source summary', completed_steps=6000,
            source_elapsed_ms=300000, planned_duration_ms=300000, scheduled_tracks=4,
            realized_track_starts=4, realized_track_ends=4, pending_tracks=0, active_tracks=0, scheduled_people=4))
        self.replay = dict(schema='ump.observation-replay.v1', run_id='original-run', sensor_id='original-sensor',
            coverage={k: v if k == 'leaf_depth' else float(v) for k, v in fixture.COVERAGE.items()}, sampling_period_ms=100, end_ms=300000,
            batches=[dict(sequence=t // 100, observed_at_ms=t, status='measured',
                          observations=sorted(sensor.get(t, []), key=lambda o: o['id'])) for t in range(100, 300000, 100)])
        write(self.capture / 'observations.json', self.replay)
        # Intentionally noncanonical whitespace: IN must retain the original bytes.
        source = (json.dumps(self.replay, separators=(', ', ': ')) + '\n').encode()
        (self.capture / 'observations.json').write_bytes(source)
        self.study.mkdir(parents=True)
        (self.study / 'mixed-observations.json').write_bytes(source)
        write(self.capture / 'private/config.yaml', {'mock_config': 'source fixed before fixture'})
        write(self.capture / 'private/execution.json', {'state': 'complete'})
        (self.capture / 'map_background.png').write_bytes(b'mock-map')
        write(self.capture / 'building_access.json', {'mock_geometry': True})
        write(self.study / fixture.POLICY_NAME, {'semantic_taxonomy': {'id': 'mock', 'version': '1',
            'nodes': [{'id': 'adult', 'input_types': ['Adult']}, {'id': 'child', 'input_types': ['Child']}]}})
        self.proof = dict(schema='ump.mapped-recording-proof.v1', status='verified', source_horizon_completed=True,
            all_scheduled_episodes_completed=True, source_origin_epoch_ms=int(origin.timestamp() * 1000),
            lifecycle_quality=dict(status='all_scheduled_episodes_completed',
                gt_coverage_status='verified_against_recorded_visible_intervals', scheduled_episodes=4,
                realized_starts=4, realized_ends=4, pending_episodes_at_horizon=0, active_episodes_at_horizon=0, scheduled_people=4),
            sensor_observability=dict(schema='ump.source-sensor-episode-observability.v1', status='pass',
                scheduled_tracks=4, sensor_observed_tracks=4, missing_track_count=0, unexpected_track_count=0),
            input_observation_contributions=23, measured_samples=2999, measured_empty_samples=2990,
            gt_rows=sum(r.get('data_type') == 'agent data' for r in self.raw['agents']))
        self.freeze()
        self.patch_source = mock.patch.object(fixture, 'EXPECTED_SOURCE_SHA256', fixture.sha(self.capture / 'observations.json'))
        self.patch_policy = mock.patch.object(fixture, 'EXPECTED_POLICY_SHA256', fixture.sha(self.study / fixture.POLICY_NAME))
        self.patch_source.start()
        self.patch_policy.start()
        self.patch_proof = mock.patch.object(fixture, 'EXPECTED_CAPTURE_PROOF_SHA256', fixture.sha(self.capture / 'capture-proof.json'))
        self.patch_proof.start()

    def tearDown(self):
        self.patch_source.stop()
        self.patch_policy.stop()
        self.patch_proof.stop()
        self.patch_file.stop()
        self.patch_root.stop()
        self.temp.cleanup()

    def freeze(self):
        # Keep agents first, as the native capture stream does. The tool never
        # decodes either following outcome channel.
        raw_path = self.capture / 'private/native_source.json'
        raw_path.write_text(json.dumps(self.raw))
        source_sha = fixture.sha(self.capture / 'observations.json')
        write(self.capture / 'bundle.json', dict(schema='ump.replay-viewer.v1', observations='observations.json',
            identity_unit='visible_episode_track', sha256={'observations.json': source_sha}))
        bound = {name: fixture.sha(self.capture / name) for name in ('observations.json', 'private/native_source.json',
            'private/config.yaml', 'private/execution.json', 'bundle.json', 'map_background.png', 'building_access.json')}
        self.proof['files_sha256'] = bound
        write(self.capture / 'capture-proof.json', self.proof)
        write(self.study / 'provenance/mixed-capture-proof.json', self.proof)
        write(self.study / 'provenance/mixed-original-summary.json', {'schema': 'mock-summary', 'status': 'verified'})
        write(self.study / 'provenance/mixed-original-bundle.json', {'schema': 'mock-bundle'})
        frozen = {name: fixture.sha(self.study / name) for name in ('mixed-observations.json', fixture.POLICY_NAME,
            'provenance/mixed-capture-proof.json', 'provenance/mixed-original-summary.json', 'provenance/mixed-original-bundle.json')}
        source = dict(observations_sha256=source_sha, capture_proof_sha256=fixture.sha(self.capture / 'capture-proof.json'),
            summary_sha256=frozen['provenance/mixed-original-summary.json'], bundle_sha256=frozen['provenance/mixed-original-bundle.json'],
            horizon_ms=300000, sampling_period_ms=100, input_observation_contributions=23)
        protocol = dict(schema='ump.spatial20-correction-protocol.v1', sources={'mixed': source}, pre_execution_artifacts_sha256=frozen)
        write(self.study / 'protocol.json', protocol)
        write(self.study / 'summary.json', dict(schema='ump.spatial20-correction.v1', status='verified', protocol=protocol,
                                               protocol_sha256=fixture.sha(self.study / 'protocol.json')))

    def build(self):
        return fixture.build_fixture(self.study, self.capture, self.contract, self.output)

    def mutate(self, name, change):
        value = fixture.load(self.output / name)
        change(value)
        (self.output / name).write_bytes(fixture.encoded(value))

    def test_verified_pair_protocol_first_exact_bytes_and_owner_permissions(self):
        original = fixture.write_new
        calls = []
        def observed(path, data):
            if path.name != 'protocol.json':
                self.assertTrue((self.output / 'protocol.json').is_file())
            calls.append(path.name)
            original(path, data)
        with mock.patch.object(fixture, 'write_new', side_effect=observed):
            receipt = self.build()
        self.assertEqual(calls[0], 'protocol.json')
        self.assertEqual(fixture.verify_fixture(self.output), receipt)
        self.assertEqual((self.output / 'in.json').read_bytes(), (self.capture / 'observations.json').read_bytes())
        self.assertEqual((self.output / 'auxiliary-in.json').read_bytes(), (self.output / 'auxiliary-out.json').read_bytes())
        manifest = fixture.load(self.output / 'private-manifest.json')
        self.assertEqual(manifest['eligible_episode_count'], 3)
        self.assertEqual(manifest['split'], 'development_only')
        self.assertFalse(self.output.stat().st_mode & 0o077)
        self.assertTrue(all(not p.stat().st_mode & 0o077 for p in self.output.iterdir()))
        self.assertFalse(receipt['native_replay_executed'])
        self.assertFalse(receipt['attack_executed'])
        self.assertEqual(receipt['counts']['IN']['observations'], 23)
        self.assertEqual(receipt['auxiliary_points'], (receipt['removed_observations'] + 3) // 4)
        absent = fixture.load(self.output / 'out.json')
        for left, right in zip(self.replay['batches'], absent['batches']):
            self.assertEqual({k: v for k, v in left.items() if k != 'observations'},
                             {k: v for k, v in right.items() if k != 'observations'})

    def test_target_hash_order_and_aux_independent_namespaces(self):
        source = fixture.inspect_source(self.study, self.capture, self.contract)
        target, eligible = fixture.select_target(source['traces'], source['source_sha256'])
        expected = sorted(eligible, key=lambda identity: (fixture.digest(fixture.canonical(
            ['target-v1', 20261025, source['source_sha256'], identity])), identity))[0]
        self.assertEqual(target, expected)
        self.assertNotIn('episode-d', eligible)
        trace = source['traces'][target]
        auxiliary = fixture.auxiliary(trace, source['source_sha256'], target)
        ranked = sorted(trace, key=lambda point: (fixture.digest(fixture.canonical(
            ['aux-v1', 20261025, source['source_sha256'], target, point])), fixture.canonical(point)))
        self.assertEqual(auxiliary, sorted(ranked[:(len(trace) + 3) // 4], key=lambda p: p['observed_at_ms']))
        self.assertTrue(all(set(point) == fixture.POINT_FIELDS for point in auxiliary))

    def test_fixed_hash_oracles_and_quarter_rounding(self):
        # Frozen independently computed SHA256 examples, not a second call to
        # the constructor's ranking implementation.
        self.assertEqual(fixture.select_target({'a': [{}, {}], 'b': [{}, {}], 'c': [{}], 'd': [{}, {}]}, '0' * 64),
                         ('a', ['a', 'b', 'd']))
        for n, expected_times in [(2, [100]), (4, [400]), (5, [300, 400]), (8, [400, 800])]:
            trace = [dict(observed_at_ms=i * 100, x=1.0, y=2.0, cell_id=3) for i in range(1, n + 1)]
            selected = fixture.auxiliary(trace, '0' * 64, 'known-a')
            self.assertEqual([p['observed_at_ms'] for p in selected], expected_times)

    def test_canonical_source_policy_and_capture_proof_pins(self):
        for name in ('EXPECTED_SOURCE_SHA256', 'EXPECTED_POLICY_SHA256', 'EXPECTED_CAPTURE_PROOF_SHA256'):
            with self.subTest(name=name), mock.patch.object(fixture, name, 'f' * 64), self.assertRaises(ValueError):
                fixture.inspect_source(self.study, self.capture, self.contract)

    def test_outcome_channels_are_never_decoded(self):
        path = self.root / 'agents-only.json'
        path.write_text('{"agents":[{"data_type":"metadata"}],"releases":THIS IS NOT JSON}')
        self.assertEqual(list(fixture.agent_rows(path)), [{'data_type': 'metadata'}])

    def test_independent_verifier_rejects_target_change_background_metadata_geometry_and_duplicates(self):
        self.build()
        originals = {p.name: p.read_bytes() for p in self.output.iterdir()}
        target = fixture.load(self.output / 'private-manifest.json')['target_id']
        def background(value):
            item = next(o for b in value['batches'] for o in b['observations'])
            item['x'] += .0001
        def reverse_background(value):
            next(b['observations'] for b in value['batches'] if len(b['observations']) > 1).reverse()
        def duplicate(value):
            batch = next(b for b in value['batches'] if b['observations'])
            batch['observations'].append(deepcopy(batch['observations'][0]))
        mutations = [('private-manifest.json', lambda v: v.update(target_id='renamed-target')),
            ('out.json', background), ('out.json', reverse_background),
            ('out.json', lambda v: v['batches'][-1].update(status='missing')),
            ('out.json', lambda v: v['batches'][0].update(sequence=2)),
            ('out.json', lambda v: v['coverage'].update(width=81)),
            ('out.json', duplicate),
            ('in.json', lambda v: next(o for b in v['batches'] for o in b['observations'] if o['id'] == target).update(id='renamed'))]
        for name, change in mutations:
            with self.subTest(name=name, mutation=change):
                self.mutate(name, change)
                with self.assertRaises(ValueError):
                    fixture.verify_fixture(self.output)
                for filename, data in originals.items():
                    (self.output / filename).write_bytes(data)

    def test_coherently_rehashed_numeric_metadata_and_manifest_tampering_rejected(self):
        self.build()
        originals = {p.name: p.read_bytes() for p in self.output.iterdir()}
        def repair_hashes():
            manifest = fixture.load(self.output / 'private-manifest.json')
            manifest['files_sha256'] = {name: fixture.sha(self.output / name) for name in fixture.ARTIFACTS}
            manifest['private_source_group']['background_fingerprint'] = fixture.fingerprint(fixture.load(self.output / 'out.json'))
            manifest['protocol_sha256'] = fixture.sha(self.output / 'protocol.json')
            (self.output / 'private-manifest.json').write_bytes(fixture.encoded(manifest))
            receipt = fixture.load(self.output / 'verification.json')
            receipt['protocol_sha256'] = fixture.sha(self.output / 'protocol.json')
            receipt['manifest_sha256'] = fixture.sha(self.output / 'private-manifest.json')
            (self.output / 'verification.json').write_bytes(fixture.encoded(receipt))
        for name, change in [('out.json', lambda v: v['coverage'].update(x=0)),
                             ('out.json', lambda v: v['batches'][-1].update(sequence=2999.0)),
                             ('protocol.json', lambda v: v.update(not_train_cal_test=1)),
                             ('private-manifest.json', lambda v: v.update(eligible_episode_count=3.0))]:
            with self.subTest(name=name, change=change):
                self.mutate(name, change)
                repair_hashes()
                with self.assertRaises(ValueError):
                    fixture.verify_fixture(self.output)
                for filename, data in originals.items():
                    (self.output / filename).write_bytes(data)

    def test_auxiliary_private_fields_wrong_count_wrong_point_and_label_mismatch_rejected(self):
        self.build()
        original = (self.output / 'auxiliary-in.json').read_bytes()
        for change in (lambda v: v[0].update(id='private-id'), lambda v: v[0].update(type='Adult'),
                       lambda v: v.append(deepcopy(v[0])), lambda v: v[0].update(x=13), lambda v: v.reverse()):
            with self.subTest(change=change):
                self.mutate('auxiliary-in.json', change)
                with self.assertRaises(ValueError):
                    fixture.verify_fixture(self.output)
                (self.output / 'auxiliary-in.json').write_bytes(original)
        # A matched malicious change must still fail deterministic reconstruction.
        self.mutate('auxiliary-in.json', lambda v: v[0].update(x=13))
        (self.output / 'auxiliary-out.json').write_bytes((self.output / 'auxiliary-in.json').read_bytes())
        with self.assertRaises(ValueError):
            fixture.verify_fixture(self.output)

    def test_source_hash_mutation_and_source_change_during_build_rejected(self):
        self.build()
        path = self.capture / 'private/config.yaml'
        original = path.read_bytes()
        path.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            fixture.verify_fixture(self.output)
        path.write_bytes(original)
        shutil.rmtree(self.output)
        real_write = fixture.write_new
        def changed(path, data):
            real_write(path, data)
            if path.name == 'in.json':
                (self.capture / 'private/config.yaml').write_bytes(original + b' ')
        with mock.patch.object(fixture, 'write_new', side_effect=changed), self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.build()
        self.assertFalse((self.output / 'verification.json').exists())

    def test_authenticated_raw_lifecycle_gt_and_episode_metadata_tampering_rejected(self):
        original = deepcopy(self.raw)
        mutations = [lambda rows: rows.__setitem__(slice(None), [r for r in rows if r.get('event') != 'visible_end']),
            lambda rows: rows[0].update(observation_identity_unit='person'),
            lambda rows: next(r for r in rows if r.get('event') == 'visible_start').update(at_ms=1),
            lambda rows: next(r for r in rows if r.get('data_type') == 'mapped source summary').update(scheduled_people=1),
            lambda rows: next(r for r in rows if r.get('data_type') == 'agent data').update(private_person_id='other'),
            lambda rows: next(r for r in rows if r.get('data_type') == 'agent data' and '.100000' in r['timestamp'])['position'].update(x=50),
            lambda rows: rows.append(deepcopy(next(r for r in rows if r.get('data_type') == 'agent data')))]
        for change in mutations:
            with self.subTest(mutation_index=mutations.index(change)):
                self.raw = deepcopy(original)
                change(self.raw['agents'])
                self.freeze()  # Bind tampered mock bytes: independent semantic checks must reject them.
                fixture.EXPECTED_CAPTURE_PROOF_SHA256 = fixture.sha(self.capture / 'capture-proof.json')
                with self.assertRaises(ValueError):
                    fixture.inspect_source(self.study, self.capture, self.contract)

    def test_missing_complete_capture_or_sensor_proof_rejected(self):
        for field, value in [('all_scheduled_episodes_completed', False), ('source_horizon_completed', False)]:
            with self.subTest(field=field):
                self.proof[field] = value
                self.freeze()
                fixture.EXPECTED_CAPTURE_PROOF_SHA256 = fixture.sha(self.capture / 'capture-proof.json')
                with self.assertRaises(ValueError):
                    fixture.inspect_source(self.study, self.capture, self.contract)
                self.proof[field] = True
        self.proof['sensor_observability']['missing_track_count'] = 1
        self.freeze()
        fixture.EXPECTED_CAPTURE_PROOF_SHA256 = fixture.sha(self.capture / 'capture-proof.json')
        with self.assertRaises(ValueError):
            fixture.inspect_source(self.study, self.capture, self.contract)

    def test_position_leaf_type_stability_duplicates_and_horizon_rejected(self):
        for change in (lambda v: v['coverage'].update(leaf_depth=True), lambda v: v.update(end_ms=1000),
                       lambda v: v['batches'][0]['observations'][0].update(cell_id=3),
                       lambda v: v['batches'][0]['observations'][0].update(x=float('nan')),
                       lambda v: v['batches'][1]['observations'][0].update(type='Child'),
                       lambda v: v['batches'][0]['observations'].append(deepcopy(v['batches'][0]['observations'][0]))):
            value = deepcopy(self.replay)
            change(value)
            with self.assertRaises(ValueError):
                fixture.validate_replay(value, {'Adult', 'Child'})

    def test_no_overwrite_no_symlinks_no_escape_and_file_budget(self):
        self.build()
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})
        link = self.root / 'results/symlink'
        link.symlink_to(self.output, target_is_directory=True)
        for path in (link, link / 'child', self.root / 'outside', self.root / 'results/../escaped'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                fixture.new_output(path)
        source_link = self.capture / 'linked.json'
        source_link.symlink_to(self.capture / 'observations.json')
        with self.assertRaises(ValueError):
            fixture.read_bytes(source_link)
        with mock.patch.object(fixture, 'MAX_FILE_BYTES', 2):
            with self.assertRaises(ValueError):
                fixture.read_bytes(self.contract)
            with self.assertRaises(ValueError):
                fixture.write_new(self.root / 'large', b'123')

    def test_id_renamed_group_fingerprint_unchanged(self):
        renamed = deepcopy(self.replay)
        for batch in renamed['batches']:
            for observation in batch['observations']:
                observation['id'] = 'renamed-' + observation['id']
        self.assertEqual(fixture.fingerprint(self.replay), fixture.fingerprint(renamed))


if __name__ == '__main__':
    unittest.main()
