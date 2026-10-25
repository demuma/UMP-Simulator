"""Authenticated small source fixtures and mocked processes; no Mongo/native jobs."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import yaml
import run_urban_privacy_sources as runner


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def source_config(seed=2026102501, namespace='a'):
    database = 'UMP_Mapped_' + namespace * 32
    people = [dict(person_id='private-' + str(i), type='Adult Pedestrian', speed_mps=1.3, radius_m=.25,
                   episodes=[dict(track_id=f'track-{i}', route_id='route-' + str(i), start_ms=i * 150)])
              for i in range(128)]
    routes = [dict(id='route-' + str(i), points=[[1 + seed % 100 / 1000, 1], [2, 2]], start_portal='west', end_portal='east')
              for i in range(128)]
    return dict(database=dict(db_name=database, clear_database=False),
                agents=dict(num_agents=128, road_user_taxonomy=[dict(type='Adult Pedestrian', probability=1.)]),
                simulation=dict(duration_seconds=300, time_step=.05),
                mapped_scene=dict(routes=routes, people=people, motion=dict(mode='local_navigation'), portals=[]),
                sensors=[dict(database=dict(db_name=database), aggregation=dict(
                    publication=dict(database=database + '_Releases', journal_database=database + '_Private'),
                    semantic_taxonomy=dict(nodes=[dict(id='pedestrian', input_types=['Adult Pedestrian'])])))])


def capture(output, protocol, row, *, incomplete=False, clone_seed=None, with_audit=True):
    """Only 128 observations; all 2999 measured sampling opportunities are kept."""
    scene, replay = Path(row['scene_directory']), Path(row['replay_directory'])
    scene.mkdir(parents=True)
    (replay / 'private').mkdir(parents=True)
    config = source_config(clone_seed or row['seed'])
    content = yaml.safe_dump(config).encode()
    (scene / 'config.yaml').write_bytes(content)
    (replay / 'private/config.yaml').write_bytes(content)
    for name in ('building_access.json', 'map_background.png'):
        (scene / name).write_bytes((Path(protocol['historical_scene']) / name).read_bytes())
        (replay / name).write_bytes((scene / name).read_bytes())
    data = dict(schema='ump.observation-replay.v1', run_id='private-run-' + str(row['seed']), sensor_id='sensor',
                coverage=runner.fixture.COVERAGE, end_ms=300000, sampling_period_ms=100,
                batches=[dict(sequence=i, observed_at_ms=i * 100, status='measured', observations=[])
                         for i in range(1, 3000)])
    data['batches'][200]['observations'] = [dict(id='track-' + str(i), type='Adult Pedestrian',
        x=1 + (clone_seed or row['seed']) % 100 / 1000, y=1, cell_id=runner.fixture.cell_id(1, 1, runner.fixture.COVERAGE))
        for i in range(128)]
    dump(replay / 'observations.json', data)
    execution = dict(state='complete', exit_code=0, binary_sha256=protocol['simulator_sha256'], config_sha256=runner.sha(scene / 'config.yaml'))
    dump(replay / 'private/execution.json', execution)
    for name in ('bundle.json', 'native_result.json', 'private/native_source.json'):
        dump(replay / name, dict(authenticated_small_fixture=True))
    manifest = dict(status='pass', seed=row['seed'], configuration_sha256=runner.sha(scene / 'config.yaml'),
                    generator_sha256=protocol['frozen_files_sha256'][str(runner.ROOT / 'tools/mapped_scene/build_mapped_scene.py')],
                    source_options=dict(expanded_shop_access=True, pedestrians_only=False, subway_access=True, rider_priority=True),
                    scene_contract=dict(population_by_observed_profile={'Adult Pedestrian': 128}),
                    building_access=dict(demand=dict(arrival_interval_ms=150, road_user_fraction=.2,
                        distributed_crossing_fraction_of_through_pedestrian_trips=.2)))
    dump(scene / 'scene_manifest.json', manifest)
    proof = dict(schema='ump.mapped-recording-proof.v1', status='verified', source_horizon_completed=True,
                 all_scheduled_episodes_completed=not incomplete,
                 motion_quality=dict(reported_diagnostics=dict(active_stalled_tracks=0, body_overlap_violations=0)),
                 lifecycle_quality=dict(status='all_scheduled_episodes_completed', scheduled_people=128,
                    scheduled_episodes=128, realized_starts=128, realized_ends=128, pending_episodes_at_horizon=0,
                    active_episodes_at_horizon=0),
                 sensor_observability=dict(schema='ump.source-sensor-episode-observability.v1', status='pass',
                    scheduled_tracks=128, sensor_observed_tracks=128, missing_track_count=0, unexpected_track_count=0),
                 native_execution=execution, capture_budget=dict(max_capture_mib=2048, max_capture_bytes=2147483648,
                    source_configuration_sha256=runner.sha(scene / 'config.yaml')),
                 files_sha256={name: runner.sha(replay / name) for name in runner.REQUIRED_FILES})
    dump(replay / 'capture-proof.json', proof)
    if with_audit:
        physical_audit_fixture(output, row)
        dump(scene.parent / 'audit-execution.json', dict(status='complete', returncode=0, command=row['audit_command']))
    return data, config


def physical_audit_fixture(output, row):
    directory = output / row['id']
    dump(directory / 'motion-audit.json', dict(status='pass', all_planned_entries_completed=True,
        source_access_validation=dict(status='pass'), config_sha256=runner.sha(directory / 'scene/config.yaml'),
        native_source_sha256=runner.sha(directory / 'replay/private/native_source.json'),
        navigation_static_body_checks=128, navigation_motion_segments_checked=128, navigation_velocity_checks=128,
        independent_gt_swept_body_pair_checks=128, boundary_endpoint_checks=128))


class UrbanSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.original_root = runner.ROOT
        self.root_patch = mock.patch.object(runner, 'ROOT', self.root)
        self.root_patch.start()
        self.historical = self.root / runner.HISTORICAL
        self.historical.mkdir(parents=True)
        (self.historical / 'config.yaml').write_text(yaml.safe_dump(source_config(20261024)))
        dump(self.historical / 'scene_manifest.json', dict(status='pass', seed=20261024,
            configuration_sha256=runner.sha(self.historical / 'config.yaml')))
        dump(self.historical / 'building_access.json', {'static_geometry': 'fixture'})
        (self.historical / 'map_background.png').write_bytes(b'fixture image')
        self.binary = self.root / 'simulator/build/Simulator'
        self.binary.parent.mkdir(parents=True)
        self.binary.write_bytes(b'never executed native fixture')
        self.generator = self.root / 'tools/mapped_scene/build_mapped_scene.py'
        self.generator.parent.mkdir(parents=True)
        self.generator.write_bytes(b'frozen fixture generator')
        self.env = dict(python_executable='fixture-python', packages=dict(PyYAML='fixture'))
        self.env_patch = mock.patch.object(runner, 'environment', return_value=self.env)
        self.env_patch.start()
        self.paths_patch = mock.patch.object(runner, 'source_paths', return_value=[self.generator, self.historical / 'config.yaml'])
        self.paths_patch.start()
        self.output = self.root / 'results/pilot'
        def new_output(path):
            path.mkdir(mode=0o700)
            return path
        self.output_patch = mock.patch.object(runner.fixture, 'new_output', side_effect=new_output)
        self.output_patch.start()
        spec = runner.importlib.util.spec_from_file_location('fixture_real_mapped', self.original_root / 'tools/mapped_scene/run_comparison.py')
        self.mapped = runner.importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mapped)
        self.validator_patch = mock.patch.object(runner, 'completed_validator', return_value=self.mapped.validate_completed_source)
        self.validator_patch.start()
        def run_audit(command, **kwargs):
            self.assertEqual(kwargs['timeout'], 420)
            row = next(row for row in runner.load(self.output / 'protocol.json')['cases'] if row['audit_command'] == command)
            physical_audit_fixture(self.output, row)
            return subprocess.CompletedProcess(command, 0)
        self.audit_patch = mock.patch.object(runner.subprocess, 'run', side_effect=run_audit)
        self.audit_patch.start()

    def tearDown(self):
        mock.patch.stopall()
        self.temp.cleanup()

    def prepared(self):
        return runner.prepare(self.output)[1]

    def test_freezes_all_seeds_flags_hashes_and_caps_before_processes(self):
        with mock.patch.object(runner.subprocess, 'Popen') as native:
            protocol = self.prepared()
        native.assert_not_called()
        self.assertEqual([r['seed'] for r in protocol['cases']], list(range(2026102501, 2026102509)))
        self.assertEqual(len({r['group_id'] for r in protocol['cases']}), 8)
        self.assertEqual(protocol['process_wall_budget_s'], 420)
        self.assertEqual(protocol['max_capture_bytes'], 2147483648)
        for row in protocol['cases']:
            command = row['command']
            self.assertEqual(command[1], str(self.root / 'tools/mapped_scene/run_scene.py'))
            for flag, value in (('--duration-s', '300'), ('--population', '128'), ('--arrival-interval-ms', '150'), ('--max-capture-mib', '2048')):
                self.assertEqual(command[command.index(flag) + 1], value)
            for flag in ('--urban-traffic', '--subway-access', '--expanded-shop-access', '--rider-priority'):
                self.assertIn(flag, command)
            self.assertFalse({'--cleanup', '--no-record', '--render', '--replay', '--pedestrians-only'} & set(command))
            self.assertEqual(Path(row['scene_directory']).parent.name, row['id'])
        self.assertEqual(runner.read_protocol(self.output)[1], protocol)

    def test_configuration_law_allows_seeded_mix_and_routes_only(self):
        left = source_config()
        right = source_config(2026102502, 'b')
        self.assertEqual(runner.configuration_law(left), runner.configuration_law(right))
        right['mapped_scene']['motion']['mode'] = 'unbounded'
        self.assertNotEqual(runner.configuration_law(left), runner.configuration_law(right))
        right = source_config()
        right['agents']['road_user_taxonomy'][0]['probability'] = .5
        with self.assertRaisesRegex(ValueError, 'probability'):
            runner.configuration_law(right)
        right = source_config()
        right['database']['db_name'] = 'Simulation'
        with self.assertRaisesRegex(ValueError, 'UUID'):
            runner.configuration_law(right)

    def test_authenticates_completed_capture_using_real_maintained_validators(self):
        protocol = self.prepared()
        row = protocol['cases'][0]
        capture(self.output, protocol, row)
        result = runner.validate_capture(row, protocol)
        self.assertEqual(result['realized']['scheduled_people'], 128)
        self.assertEqual(result['realized']['observed_episode_count'], 128)
        self.assertEqual(result['realized']['measured_samples'], 2999)
        self.assertEqual(result['checks']['source_observability'], 'pass')
        (Path(row['replay_directory']) / 'observations.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            runner.validate_capture(row, protocol)

    def test_censored_or_missing_observability_cannot_be_accepted(self):
        protocol = self.prepared()
        row = protocol['cases'][0]
        capture(self.output, protocol, row, incomplete=True)
        with self.assertRaisesRegex(ValueError, 'all scheduled'):
            runner.validate_capture(row, protocol)
        path = Path(row['replay_directory']) / 'capture-proof.json'
        proof = runner.load(path)
        proof['all_scheduled_episodes_completed'] = True
        proof.pop('sensor_observability')
        dump(path, proof)
        with self.assertRaisesRegex(ValueError, 'observability'):
            runner.validate_capture(row, protocol)

    def test_hashes_and_full_horizon_are_fail_closed(self):
        protocol = self.prepared()
        row = protocol['cases'][0]
        capture(self.output, protocol, row)
        proof_path = Path(row['replay_directory']) / 'capture-proof.json'
        proof = runner.load(proof_path)
        data = runner.load(Path(row['replay_directory']) / 'observations.json')
        data['end_ms'] = 1000
        dump(Path(row['replay_directory']) / 'observations.json', data)
        proof['files_sha256']['observations.json'] = runner.sha(Path(row['replay_directory']) / 'observations.json')
        dump(proof_path, proof)
        with self.assertRaisesRegex(ValueError, '300-second'):
            runner.validate_capture(row, protocol)
        self.generator.write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError, 'Frozen source'):
            runner.read_protocol(self.output)

    def fake_process(self, protocol, row, code=0, clone_seed=None):
        parent = self
        class Process:
            pid = 987654
            returncode = code
            def wait(self, timeout):
                parent.assertEqual(timeout, 420)
                return code
        def launch(command, **kwargs):
            self.assertEqual(command, row['command'])
            self.assertTrue((self.output / 'protocol.json').is_file())
            self.assertTrue((self.output / row['id'] / 'attempt.json').is_file())
            self.assertTrue(kwargs['start_new_session'])
            self.assertEqual(kwargs['umask'], 0o077)
            self.assertNotIn('shell', kwargs)
            if code == 0:
                capture(self.output, protocol, row, clone_seed=clone_seed, with_audit=False)
            return Process()
        return launch

    def test_resume_is_serial_and_never_retries_failed_seed(self):
        protocol = self.prepared()
        rows = protocol['cases']
        with mock.patch.object(runner.subprocess, 'Popen', side_effect=self.fake_process(protocol, rows[0], code=9)) as native:
            summary = runner.resume(self.output, limit=1)
        self.assertEqual(summary['cases'][0]['status'], 'failed')
        self.assertEqual(native.call_count, 1)
        with mock.patch.object(runner.subprocess, 'Popen', side_effect=self.fake_process(protocol, rows[1])) as native:
            summary = runner.resume(self.output, limit=1)
        self.assertEqual(native.call_count, 1)
        self.assertEqual(summary['attempted_case_count'], 2)
        self.assertEqual(summary['verified_case_count'], 1)
        self.assertEqual(summary['pilot_excluded_seeds'], list(runner.SEEDS))
        self.assertFalse((self.output / 'source-summary.json').exists())
        self.assertEqual(len(list((self.output / 'reports').glob('summary-*.json'))), 2)
        with self.assertRaisesRegex(ValueError, 'retry/overwrite'):
            runner.attempt(self.output, protocol, rows[0])

    def test_timeout_and_interruption_are_recorded_and_kill_only_owned_group(self):
        protocol = self.prepared()
        row = protocol['cases'][0]
        process = mock.Mock(pid=987654, returncode=-9)
        process.wait.side_effect = [subprocess.TimeoutExpired(row['command'], 420), -9]
        with mock.patch.object(runner.subprocess, 'Popen', return_value=process), mock.patch.object(runner.os, 'killpg') as kill:
            result = runner.attempt(self.output, protocol, row)
        self.assertEqual(result['status'], 'timeout')
        kill.assert_called_once_with(987654, runner.signal.SIGKILL)
        second = protocol['cases'][1]
        process.wait.side_effect = [KeyboardInterrupt(), -9]
        with mock.patch.object(runner.subprocess, 'Popen', return_value=process), mock.patch.object(runner.os, 'killpg'):
            with self.assertRaises(KeyboardInterrupt):
                runner.attempt(self.output, protocol, second)
        self.assertEqual(runner.load(self.output / second['id'] / 'execution.json')['status'], 'interrupted')
        summary = runner.summarize(self.output, protocol)
        self.assertEqual(summary['cases'][1]['status'], 'interrupted')

    def test_id_renaming_does_not_hide_duplicate_routes_or_trajectories(self):
        left = source_config()
        renamed = deepcopy(left)
        for person, route in zip(renamed['mapped_scene']['people'], renamed['mapped_scene']['routes']):
            route['id'] += '-renamed'
            person['person_id'] += '-renamed'
            person['episodes'][0]['track_id'] += '-renamed'
            person['episodes'][0]['route_id'] += '-renamed'
        self.assertEqual(runner.planned_route_fingerprint(left), runner.planned_route_fingerprint(renamed))
        protocol = self.prepared()
        for row in protocol['cases'][:2]:
            with mock.patch.object(runner.subprocess, 'Popen', side_effect=self.fake_process(protocol, row, clone_seed=2026102501)):
                runner.attempt(self.output, protocol, row)
        summary = runner.summarize(self.output, protocol)
        self.assertEqual(summary['verified_case_count'], 0)
        self.assertEqual(summary['capture_verified_case_count'], 2)
        self.assertEqual({r['status'] for r in summary['cases'][:2]}, {'invalid_duplicate'})
        self.assertEqual(summary['status'], 'incomplete')
        self.assertIsNone(summary['independent_source_count'])
        for field in ('planned_route_fingerprint', 'normalized_source_fingerprint'):
            self.assertEqual(summary['duplicate_fingerprint_groups'][field], [[r['id'] for r in protocol['cases'][:2]]])

    def test_all_eight_valid_cases_finalize_without_running_again(self):
        protocol = self.prepared()
        calls = []
        def launch(command, **kwargs):
            row = next(row for row in protocol['cases'] if row['command'] == command)
            calls.append(row['seed'])
            return self.fake_process(protocol, row)(command, **kwargs)
        with mock.patch.object(runner.subprocess, 'Popen', side_effect=launch):
            summary = runner.resume(self.output)
        self.assertEqual(calls, list(runner.SEEDS))
        self.assertEqual(summary['status'], 'verified')
        self.assertEqual(summary['verified_case_count'], 8)
        frozen_final = (self.output / 'source-summary.json').read_bytes()
        with mock.patch.object(runner.subprocess, 'Popen') as native:
            again = runner.resume(self.output)
        native.assert_not_called()
        self.assertEqual(again, summary)
        self.assertEqual((self.output / 'source-summary.json').read_bytes(), frozen_final)

    def test_physical_audit_and_exact_episode_set_are_required(self):
        protocol = self.prepared()
        row = protocol['cases'][0]
        capture(self.output, protocol, row)
        audit_path = self.output / row['id'] / 'motion-audit.json'
        audit = runner.load(audit_path)
        audit['all_planned_entries_completed'] = False
        dump(audit_path, audit)
        with self.assertRaisesRegex(ValueError, 'physical/source-access'):
            runner.validate_capture(row, protocol)
        audit['all_planned_entries_completed'] = True
        audit['navigation_velocity_checks'] = 0
        dump(audit_path, audit)
        with self.assertRaisesRegex(ValueError, 'actual sweeps'):
            runner.validate_capture(row, protocol)
        data_path = Path(row['replay_directory']) / 'observations.json'
        data = runner.load(data_path)
        data['batches'][200]['observations'][0]['id'] = 'renamed-foreign-track'
        dump(data_path, data)
        proof_path = Path(row['replay_directory']) / 'capture-proof.json'
        proof = runner.load(proof_path)
        proof['files_sha256']['observations.json'] = runner.sha(data_path)
        dump(proof_path, proof)
        with self.assertRaisesRegex(ValueError, 'missing observed episodes'):
            runner.validate_capture(row, protocol)

    def test_protocol_tampering_and_existing_directories_do_not_start_native(self):
        protocol = self.prepared()
        (self.output / protocol['cases'][0]['id']).mkdir()
        with mock.patch.object(runner.subprocess, 'Popen', side_effect=self.fake_process(protocol, protocol['cases'][1])):
            summary = runner.resume(self.output, limit=1)
        self.assertEqual(summary['cases'][0]['status'], 'interrupted')
        protocol['cases'][2]['seed'] = 20261024
        dump(self.output / 'protocol.json', protocol)
        with mock.patch.object(runner.subprocess, 'Popen') as native:
            with self.assertRaisesRegex(ValueError, 'protocol changed'):
                runner.resume(self.output)
        native.assert_not_called()


if __name__ == '__main__':
    unittest.main()
