"""Synthetic fixed-window integrity and unchanged physical-checker regressions.

No simulator, MongoDB, recorded primary trajectory, attack or fitted model is
used. The compact exporter fixture is authored by its maintained test helper;
we extend only its public synthetic clock/schedule. Physical geometry tests run
actual checker code, including the unapplied reviewed copy during development.
"""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import yaml
import track_window_source_validation as window

ROOT = Path(__file__).resolve().parents[2]
MAPPED = ROOT / 'tools/mapped_scene'
if str(MAPPED) not in sys.path:
    sys.path.insert(0, str(MAPPED))
import export_replay as export
import test_export_replay as export_fixtures
import test_audit_building_access as physical_fixtures


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(*, censored=True, short_track=False):
    cfg, raw = export_fixtures.native_fixture()
    cfg['simulation'].update(duration_seconds=300, width=80, height=80)
    cfg['database']['clear_database'] = False
    cfg['agents'] = dict(num_agents=128, road_user_taxonomy=[dict(type='Adult Pedestrian', probability=1.)])
    cfg['mapped_scene'] = dict(portals=[], routes=[dict(id='fixture-route', points=[[1, 1], [2, 1]])],
        motion=dict(mode='local_navigation'), people=[dict(person_id=f'private-person-{i:03d}',
            type='Adult Pedestrian', speed_mps=1., radius_m=.2,
            episodes=[dict(track_id=f'track-{i:03d}', route_id='fixture-route', start_ms=0)]) for i in range(1, 129)])
    summary = next(row for row in raw['agents'] if row.get('data_type') == 'mapped source summary')
    summary.update(completed_steps=6000, source_elapsed_ms=300000, planned_duration_ms=300000,
                   scheduled_people=128, scheduled_tracks=128, body_overlap_violations=0,
                   active_stalled_tracks=int(censored))
    if censored:
        raw['agents'] = [row for row in raw['agents'] if not
            (row.get('event') == 'episode_end' and row.get('observation_track_id') == 'track-001')]
        for at in range(500, 300000, 50):
            raw['agents'].append(dict(data_type='agent data', timestamp=export_fixtures.stamp(at),
                agent_id='track-001', observation_track_id='track-001', private_person_id='private-person-001',
                type='Adult Pedestrian', position=dict(x=1, y=1), velocity=dict(x=0, y=0)))
        for at in range(500, 300000, 100):
            raw['sensor'].append(dict(data_type='adaptive grid data', sensor_id=export_fixtures.SENSOR,
                timestamp=export_fixtures.stamp(at), cell_id=12288, cell_size=1.25, cell_position=dict(x=0, y=0),
                total_agents=1, agent_type_count=[dict(type='Adult Pedestrian', count=1)]))
        summary.update(realized_track_starts=5, realized_track_ends=4, active_tracks=1, pending_tracks=123)
    else:
        # Full lifecycle completion does not mean all configured episodes must
        # appear on the sensor clock. These genuine 50-ms tracks are preserved
        # in GT/lifecycle but correctly have no 100-ms sensor observation.
        for i in range(6, 129):
            raw['agents'].append(dict(data_type='agent data', timestamp=export_fixtures.stamp(0),
                agent_id=f'track-{i:03d}', observation_track_id=f'track-{i:03d}',
                private_person_id=f'private-person-{i:03d}', type='Adult Pedestrian',
                position=dict(x=2, y=2), velocity=dict(x=0, y=0)))
            for event, at in [('episode_start', 0), ('episode_end', 50)]:
                raw['agents'].append(dict(data_type='mapped lifecycle event', event=event, at_ms=at,
                    private_person_id=f'private-person-{i:03d}', observation_track_id=f'track-{i:03d}',
                    route_id='fixture-route', portal_id='fixture-portal'))
        summary.update(realized_track_starts=128, realized_track_ends=128, active_tracks=0, pending_tracks=0)
    if short_track:
        # An actually measured one-sample track must remain in input, even
        # though it cannot be selected as a membership target.
        i = 6
        raw['agents'].append(dict(data_type='agent data', timestamp=export_fixtures.stamp(100),
            agent_id=f'track-{i:03d}', observation_track_id=f'track-{i:03d}',
            private_person_id=f'private-person-{i:03d}', type='Adult Pedestrian',
            position=dict(x=14, y=14), velocity=dict(x=0, y=0)))
        for event, at in [('episode_start', 100), ('episode_end', 150)]:
            raw['agents'].append(dict(data_type='mapped lifecycle event', event=event, at_ms=at,
                private_person_id=f'private-person-{i:03d}', observation_track_id=f'track-{i:03d}',
                route_id='fixture-route', portal_id='fixture-portal'))
        raw['sensor'].append(dict(data_type='adaptive grid data', sensor_id=export_fixtures.SENSOR,
            timestamp=export_fixtures.stamp(100), cell_id=export.cell_id(14, 14, window.source.fixture.COVERAGE),
            cell_size=1.25, cell_position=dict(x=13.75, y=13.75), total_agents=1,
            agent_type_count=[dict(type='Adult Pedestrian', count=1)]))
        summary.update(realized_track_starts=6, realized_track_ends=5, pending_tracks=122)
    return cfg, raw


class WindowCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name).resolve()
        self.scene, self.replay = self.directory / 'scene', self.directory / 'replay'
        self.scene.mkdir(); (self.replay / 'private').mkdir(parents=True)
        self.binary = self.directory / 'Simulator'
        self.binary.write_bytes(b'never executed synthetic native fixture')
        self.row = dict(seed=71, scene_directory=str(self.scene), replay_directory=str(self.replay),
            audit_command=[sys.executable, str(window.AUDITOR), '--scene', str(self.scene), '--replay', str(self.replay),
                           '--output', str(self.directory / 'motion-audit.json'), '--profile', window.PROFILE])
        self.cfg, self.raw = fixture()
        self.environment = dict(test_environment='no native or database processes')
        self.env_patch = mock.patch.object(window.source, 'environment', return_value=self.environment)
        self.env_patch.start()
        self.write_capture()

    def tearDown(self):
        self.env_patch.stop(); self.tmp.cleanup()

    def write_capture(self):
        (self.scene / 'config.yaml').write_text(yaml.safe_dump(self.cfg))
        (self.replay / 'private/config.yaml').write_bytes((self.scene / 'config.yaml').read_bytes())
        data, result, proof = export.build_recording(self.cfg, self.raw)
        access = dict(schema='ump.building-access.v1', bounds=dict(x=0, y=0, width=80, height=80), buildings=[], portals=deepcopy(self.cfg['mapped_scene']['portals']))
        for place in (self.scene, self.replay):
            dump(place / 'building_access.json', access)
            (place / 'map_background.png').write_bytes(b'hash-bound synthetic map, not rendered')
        self.protocol = dict(schema=window.PROTOCOL_SCHEMA, source_validation_profile=window.PROFILE,
            source_horizon_ms=300000, simulator_path=str(self.binary), simulator_sha256=window.source.sha(self.binary),
            environment=self.environment, historical_scene=str(self.scene), configuration_equivalence_sha256=window.source.digest(window.source.configuration_law(self.cfg)),
            geometry_sha256={name: window.source.sha(self.scene / name) for name in ('building_access.json', 'map_background.png')})
        manifest = dict(status='pass', seed=self.row['seed'], configuration_sha256=window.source.sha(self.scene / 'config.yaml'),
            generator_sha256=window.source.sha(ROOT / 'tools/mapped_scene/build_mapped_scene.py'),
            source_options=dict(expanded_shop_access=True, pedestrians_only=False, subway_access=True, rider_priority=True),
            scene_contract=dict(population_by_observed_profile={'Adult Pedestrian': 128}),
            building_access=dict(demand=dict(arrival_interval_ms=150, road_user_fraction=.2,
                distributed_crossing_fraction_of_through_pedestrian_trips=.2)))
        dump(self.scene / 'scene_manifest.json', manifest)
        helpers = set(window.source.source_paths(self.scene)) | {Path(window.__file__), self.binary}
        self.protocol['frozen_files_sha256'] = {str(path): window.source.sha(path) for path in helpers}
        execution = dict(schema='ump.mapped-execution.v1', state='complete', exit_code=0,
            binary_sha256=self.protocol['simulator_sha256'], config_sha256=window.source.sha(self.scene / 'config.yaml'))
        dump(self.scene / 'execution.json', execution); dump(self.replay / 'private/execution.json', execution)
        dump(self.replay / 'observations.json', data); dump(self.replay / 'native_result.json', result)
        dump(self.replay / 'private/native_source.json', self.raw); dump(self.replay / 'bundle.json', dict(schema='synthetic-test-bundle'))
        proof.update(native_execution=execution,
            building_access=export.validate_scene_building_access(self.scene, self.cfg, self.scene / 'building_access.json'),
            capture_budget=dict(max_capture_mib=2048, max_capture_bytes=2147483648,
                source_configuration_sha256=window.source.sha(self.scene / 'config.yaml'),
                native_source_json_bytes=(self.replay / 'private/native_source.json').stat().st_size),
            files_sha256={name: window.source.sha(self.replay / name) for name in window.source.REQUIRED_FILES})
        dump(self.replay / 'capture-proof.json', proof)
        self.audit = dict(status='pass', validation_profile=window.PROFILE,
            movement_coverage_quality=dict(declared_destination_count=0, declared_building_count=0,
                realized_two_destination_coverage=False), source_access_validation=dict(status='pass'),
            config_sha256=execution['config_sha256'], native_source_sha256=proof['files_sha256']['private/native_source.json'],
            navigation_static_body_checks=proof['gt_rows'], navigation_motion_segments_checked=5989,
            navigation_velocity_checks=5989, independent_gt_body_pair_checks=0,
            independent_gt_swept_body_pair_checks=0, boundary_endpoint_checks=0,
            minimum_body_clearance_margin_m=None, minimum_swept_body_clearance_margin_m=None,
            portals={p['id']: dict(planned_entries=0, completed_entries=0, realized_exits=0) for p in self.cfg['mapped_scene']['portals']},
            all_planned_entries_completed=False, targets_with_completed_entries=0,
            buildings_with_completed_entries=0, buildings_with_realized_exits=0)
        dump(self.directory / 'motion-audit.json', self.audit)
        dump(self.directory / 'audit-execution.json', dict(status='complete', returncode=0, command=self.row['audit_command']))

    def rehash_artifact(self, name):
        proof = window.source.load(self.replay / 'capture-proof.json')
        proof['files_sha256'][name] = window.source.sha(self.replay / name)
        if name == 'private/native_source.json':
            proof['capture_budget']['native_source_json_bytes'] = (self.replay / name).stat().st_size
        dump(self.replay / 'capture-proof.json', proof)

    def validate(self):
        return window.validate_capture(self.row, self.protocol)

    def test_censored_300s_with_pending_active_stalled_is_valid_and_truthfully_reported(self):
        result = self.validate()
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['realized']['observed_episode_count'], 5)
        self.assertEqual(result['realized']['configured_tracks_without_sensor_samples'], 123)
        self.assertEqual(result['realized']['measured_samples'], 2999)
        self.assertEqual(result['realized']['eligible_target_tracks'], 5)
        quality = result['movement_quality']
        self.assertFalse(quality['all_scheduled_episodes_completed'])
        self.assertFalse(quality['all_planned_entries_completed'])
        self.assertEqual(quality['lifecycle_quality']['active_episodes_at_horizon'], 1)
        self.assertEqual(quality['lifecycle_quality']['pending_episodes_at_horizon'], 123)
        self.assertEqual(quality['motion_quality']['reported_diagnostics']['active_stalled_tracks'], 1)
        self.assertEqual(quality['scheduled_episode_sensor_observability']['status'], 'fail')
        # The measured registry passes; the scheduled-cohort diagnostic remains
        # fail and is never rewritten to claim all scheduled tracks were seen.
        self.assertEqual(result['checks']['observed_registry'], 'pass')

    def test_completed_source_also_passes_without_promoting_unmeasured_50ms_tracks(self):
        self.cfg, self.raw = fixture(censored=False); self.write_capture()
        result = self.validate()
        self.assertTrue(result['movement_quality']['all_scheduled_episodes_completed'])
        self.assertEqual(result['realized']['observed_episode_count'], 5)
        self.assertEqual(result['realized']['configured_tracks_without_sensor_samples'], 123)
        self.assertEqual(result['movement_quality']['lifecycle_quality']['realized_ends'], 128)

    def test_one_sample_track_is_kept_but_ineligible_as_target(self):
        self.cfg, self.raw = fixture(short_track=True); self.write_capture()
        result = self.validate()
        self.assertEqual(result['realized']['observed_episode_count'], 6)
        self.assertEqual(result['realized']['eligible_target_tracks'], 5)
        self.assertEqual(result['realized']['single_sample_observed_tracks'], 1)
        self.assertEqual(result['realized']['observation_contributions'], 3016)

    def test_missing_or_unsupported_profile_and_legacy_schema_cannot_select_this_path(self):
        for key, value in [('source_validation_profile', None), ('source_validation_profile', 'legacy_completed_v1'),
                           ('source_validation_profile', 'unknown'), ('schema', window.source.PROTOCOL_SCHEMA)]:
            with self.subTest(key=key, value=value):
                protocol = deepcopy(self.protocol); protocol[key] = value
                with self.assertRaisesRegex(ValueError, 'Explicit observed-track-window'):
                    window.validate_capture(self.row, protocol)

    def test_omitted_live_dependency_cannot_pass_protocol_freeze(self):
        for relative in ('tools/evaluation/privacy_dataset.py', 'tools/evaluation/make_fixture.py',
                         'tools/mapped_scene/transit_access.py', 'tools/osm_regions/build_map.py'):
            with self.subTest(dependency=relative):
                protocol = deepcopy(self.protocol)
                protocol['frozen_files_sha256'].pop(str(ROOT / relative))
                with self.assertRaisesRegex(ValueError, 'freeze all validation helpers'):
                    window.validate_capture(self.row, protocol)

    def test_clock_and_stored_observation_mutation_rejected_even_after_rehash(self):
        for mutation in ('omit_batch', 'drop_track', 'duplicate_track'):
            with self.subTest(mutation=mutation):
                data = window.source.load(self.replay / 'observations.json')
                old = deepcopy(data)
                if mutation == 'omit_batch': data['batches'].pop()
                elif mutation == 'drop_track': data['batches'][0]['observations'].pop()
                else: data['batches'][0]['observations'].append(deepcopy(data['batches'][0]['observations'][0]))
                dump(self.replay / 'observations.json', data); self.rehash_artifact('observations.json')
                with self.assertRaisesRegex(ValueError, 'Stored observations differ'):
                    self.validate()
                dump(self.replay / 'observations.json', old); self.rehash_artifact('observations.json')

    def test_submillisecond_raw_clocks_are_never_rounded_into_valid_measurements(self):
        for channel in ('metadata', 'GT', 'sensor', 'lifecycle'):
            with self.subTest(channel=channel):
                raw = window.source.load(self.replay / 'private/native_source.json')
                old = deepcopy(raw)
                if channel == 'metadata':
                    row = next(row for row in raw['agents'] if row.get('data_type') == 'metadata')
                elif channel == 'GT':
                    row = next(row for row in raw['agents'] if row.get('agent_id') == 'track-001')
                elif channel == 'sensor': row = raw['sensor'][0]
                else:
                    row = next(row for row in raw['agents'] if row.get('event') == 'episode_start')
                    row['timestamp'] = export_fixtures.stamp(row['at_ms'])
                # 0.4 ms would be silently rounded by the older export helper.
                row['timestamp'] = row['timestamp'].replace('Z', '400Z')
                dump(self.replay / 'private/native_source.json', raw); self.rehash_artifact('private/native_source.json')
                with self.assertRaisesRegex(ValueError, 'integer milliseconds'):
                    self.validate()
                dump(self.replay / 'private/native_source.json', old); self.rehash_artifact('private/native_source.json')

    def test_hash_and_frozen_binary_changes_rejected(self):
        (self.replay / 'map_background.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'artifact hash mismatch'):
            self.validate()
        self.write_capture(); self.binary.write_bytes(b'changed binary')
        with self.assertRaisesRegex(ValueError, 'Frozen source/binary/map changed'):
            self.validate()

    def test_raw_gt_gap_and_raw_sensor_missing_cell_rejected_after_rehash(self):
        for mutation, expected in [('gt_gap', 'Missing GT state'), ('sensor_gap', 'Missing occupied raw')]:
            with self.subTest(mutation=mutation):
                raw = window.source.load(self.replay / 'private/native_source.json')
                old = deepcopy(raw)
                if mutation == 'gt_gap':
                    row = next(row for row in raw['agents'] if row.get('agent_id') == 'track-001'
                               and row.get('timestamp') == export_fixtures.stamp(550))
                    raw['agents'].remove(row)
                else: raw['sensor'].pop()
                dump(self.replay / 'private/native_source.json', raw); self.rehash_artifact('private/native_source.json')
                with self.assertRaisesRegex(ValueError, expected): self.validate()
                dump(self.replay / 'private/native_source.json', old); self.rehash_artifact('private/native_source.json')

    def test_cancelled_source_clock_and_fabricated_eof_exit_are_rejected(self):
        raw = window.source.load(self.replay / 'private/native_source.json')
        next(row for row in raw['agents'] if row.get('data_type') == 'mapped source summary')['completed_steps'] -= 1
        dump(self.replay / 'private/native_source.json', raw); self.rehash_artifact('private/native_source.json')
        with self.assertRaisesRegex(ValueError, 'incomplete/cancelled'): self.validate()
        self.write_capture()
        raw = window.source.load(self.replay / 'private/native_source.json')
        raw['agents'].append(dict(data_type='mapped lifecycle event', event='episode_end', at_ms=300000,
            observation_track_id='track-001', private_person_id='private-person-001', route_id='fixture-route', portal_id='fixture-portal'))
        dump(self.replay / 'private/native_source.json', raw); self.rehash_artifact('private/native_source.json')
        with self.assertRaisesRegex(ValueError, 'diagnostic mismatch'): self.validate()

    def test_stored_proof_and_result_not_trusted_over_actual_raw(self):
        proof = window.source.load(self.replay / 'capture-proof.json'); proof['lifecycle_quality']['realized_ends'] += 1
        dump(self.replay / 'capture-proof.json', proof)
        with self.assertRaisesRegex(ValueError, 'proof differs'): self.validate()
        self.write_capture()
        result = window.source.load(self.replay / 'native_result.json'); result['input_observation_contributions'] += 1
        dump(self.replay / 'native_result.json', result); self.rehash_artifact('native_result.json')
        with self.assertRaisesRegex(ValueError, 'native result differs'): self.validate()

    def test_physical_failure_profile_provenance_overlap_and_body_coverage_rejected(self):
        for key, value, expected in [('status', 'fail', 'physical/source-access'),
                ('validation_profile', 'legacy_completed_v1', 'explicit windowed'),
                ('native_source_sha256', '0' * 64, 'source binding'),
                ('minimum_swept_body_clearance_margin_m', -.1, 'clearance violation'),
                ('navigation_static_body_checks', 1, 'every GT body')]:
            with self.subTest(key=key):
                audit = deepcopy(self.audit); audit[key] = value; dump(self.directory / 'motion-audit.json', audit)
                with self.assertRaisesRegex(ValueError, expected): self.validate()
        dump(self.directory / 'motion-audit.json', self.audit)
        self.raw['agents'][1]['body_overlap_violations'] = 1; self.write_capture()
        with self.assertRaisesRegex(ValueError, 'body overlaps'): self.validate()

    def test_configuration_law_native_exit_and_map_guards_stay_hard(self):
        self.protocol['configuration_equivalence_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'configuration law changed'): self.validate()
        self.write_capture()
        execution = window.source.load(self.replay / 'private/execution.json'); execution['exit_code'] = 1
        dump(self.replay / 'private/execution.json', execution); self.rehash_artifact('private/execution.json')
        with self.assertRaisesRegex(ValueError, 'Native execution'): self.validate()
        self.write_capture(); self.protocol['geometry_sha256']['building_access.json'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Fixed mapped geometry'): self.validate()


    def test_no_track_with_two_samples_cannot_supply_a_target(self):
        self.cfg, self.raw = fixture(censored=False)
        # Keep only the first actual 100-ms sample for the first five tracks;
        # update their true lifecycle interval rather than dropping input rows.
        self.raw['agents'] = [row for row in self.raw['agents'] if not
            (row.get('data_type') == 'agent data' and row.get('agent_id') in
             {f'track-{i:03d}' for i in range(1, 6)} and
             export.epoch_ms(row['timestamp']) - export.epoch_ms(export_fixtures.stamp(0)) >= 150)]
        for row in self.raw['agents']:
            if row.get('event') == 'episode_end' and row.get('observation_track_id') in {f'track-{i:03d}' for i in range(1, 6)}:
                row['at_ms'] = 150
        self.raw['sensor'] = self.raw['sensor'][:1]
        # No recipient release is invented. The already committed public cell
        # now truly has five contributions over one sample, within its policy.
        for payload in self.raw['releases'] + [j['release'] for j in self.raw['journals'] if j['release']['cells']]:
            cell = payload['cells'][0]
            cell['counts']['observation_contributions'] = 5
            cell['counts']['mean_sample_occupancy'] = 1.25
            cell['semantic']['categories'][0]['observation_contributions'] = 5
        self.write_capture()
        with self.assertRaisesRegex(ValueError, 'at least two samples'):
            self.validate()

    def test_new_windowed_audit_can_live_outside_original_capture_without_overwrite(self):
        extra = self.directory / 'new-evaluation'; extra.mkdir()
        report = extra / 'windowed-audit.json'
        receipt = extra / 'windowed-execution.json'
        command = deepcopy(self.row['audit_command'])
        command[command.index('--output') + 1] = str(report)
        dump(report, self.audit)
        dump(receipt, dict(status='complete', returncode=0, command=command))
        def ref(path): return dict(path=str(path), sha256=window.source.sha(path))
        proof_sha = window.source.sha(self.replay / 'capture-proof.json')
        self.protocol['windowed_physical_audits'] = {proof_sha: dict(report=ref(report), execution=ref(receipt), command=command)}
        # A failed old audit remains untouched. The new proof is an explicitly
        # bound execution of the current checker, rather than a renamed failure.
        dump(self.directory / 'motion-audit.json', dict(status='fail', error='historical coverage gate'))
        self.assertEqual(self.validate()['status'], 'verified')
        self.assertEqual(window.source.load(self.directory / 'motion-audit.json')['status'], 'fail')
        report.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'artifact hash mismatch'):
            self.validate()

    def test_successful_original_strict_audit_requires_full_authenticated_provenance(self):
        legacy_audit = deepcopy(self.audit)
        legacy_audit.pop('validation_profile'); legacy_audit.pop('movement_coverage_quality')
        legacy_audit['portals'] = {f'p{i}': dict(completed_entries=1, realized_exits=1) for i in range(2)}
        # Keep the genuine capture's configuration unchanged. The stronger
        # report's declared coverage must match the original configured portals.
        self.cfg['mapped_scene']['portals'] = [dict(id=f'p{i}', building_id=f'b{i}', point=[i, 1]) for i in range(2)]
        self.write_capture()
        legacy_audit.update(config_sha256=self.audit['config_sha256'], native_source_sha256=self.audit['native_source_sha256'])
        dump(self.directory / 'motion-audit.json', legacy_audit)
        legacy_command = self.row['audit_command'][:-2]
        dump(self.directory / 'audit-execution.json', dict(status='complete', returncode=0, command=legacy_command))
        archived = self.directory / 'original-auditor.py'; archived.write_bytes(window.AUDITOR.read_bytes())
        producer = deepcopy(self.protocol)
        producer['schema'] = window.source.PROTOCOL_SCHEMA
        producer['cases'] = [dict(self.row, audit_command=legacy_command)]
        original_protocol = self.directory / 'original-protocol.json'; dump(original_protocol, producer)
        def ref(path): return dict(path=str(path), sha256=window.source.sha(path))
        entry = dict(report=ref(self.directory / 'motion-audit.json'), execution=ref(self.directory / 'audit-execution.json'),
                     producer_protocol=ref(original_protocol), archived_auditor=ref(archived))
        proof_sha = window.source.sha(self.replay / 'capture-proof.json')
        self.protocol['legacy_physical_audits'] = {proof_sha: entry}
        result = self.validate()
        provenance = result['movement_quality']['physical_audit']
        self.assertEqual(provenance['profile'], window.LEGACY_PROFILE)
        self.assertTrue(provenance['reused_successful_legacy_audit'])
        self.assertFalse(result['movement_quality']['all_scheduled_episodes_completed'])
        archived.write_bytes(b'unrelated original checker')
        with self.assertRaisesRegex(ValueError, 'artifact hash mismatch'):
            self.validate()
        archived.write_bytes(window.AUDITOR.read_bytes())
        # A fresh reference to replacement bytes still fails the original
        # producer's frozen auditor hash; self-consistent relabeling is barred.
        archived.write_bytes(b'unrelated replacement checker'); entry['archived_auditor'] = ref(archived)
        with self.assertRaisesRegex(ValueError, 'Original physical auditor'):
            self.validate()


class SharedAuditorProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # During the live frozen batch only, use the exact isolated patch copy.
        # Production defaults to the maintained shared checker after root applies
        # that patch safely. No guard function is monkeypatched or reimplemented.
        path = Path(os.environ.get('UMP_WINDOW_AUDITOR_TEST_COPY', str(window.AUDITOR)))
        cls.auditor = load_module(path, 'ump_explicit_windowed_physical_checker')

    def test_legacy_default_keeps_original_coverage_requirement_and_result(self):
        cfg, raw = physical_fixtures.navigation_fixture()[:2]
        legacy = physical_fixtures.audit(cfg, raw)
        self.assertEqual(self.auditor.audit(cfg, raw), legacy)
        cfg, raw, _, _ = physical_fixtures.navigation_fixture()
        raw['agents'] = [row for row in raw['agents'] if not str(row.get('agent_id', row.get('observation_track_id', ''))).startswith('8')]
        with self.assertRaisesRegex(ValueError, 'two distinct destinations'):
            self.auditor.audit(cfg, raw)
        result = self.auditor.audit(cfg, raw, profile=window.PROFILE)
        self.assertFalse(result['movement_coverage_quality']['realized_two_destination_coverage'])
        self.assertEqual(result['validation_profile'], window.PROFILE)

    def test_censored_track_is_physically_checked_without_inventing_a_door_end(self):
        cfg, raw, context, layers = physical_fixtures.navigation_fixture()
        # Preserve the complete actually recorded body motion, remove only its
        # authored terminal/return evidence to model an unfinished synthetic case.
        raw['agents'] = [row for row in raw['agents'] if not
            (row.get('observation_track_id') == '8a' and row.get('event') == 'visible_end')
            and row.get('observation_track_id') != '8b' and row.get('agent_id') != '8b']
        with self.assertRaisesRegex(ValueError, 'two distinct destinations'):
            self.auditor.audit(cfg, raw, public_context=context, map_layers=layers)
        result = self.auditor.audit(cfg, raw, public_context=context, map_layers=layers, profile=window.PROFILE)
        self.assertFalse(result['all_planned_entries_completed'])
        self.assertEqual(result['portals']['door-8']['completed_entries'], 0)
        self.assertEqual(result['navigation_static_body_checks'], 41)
        self.assertGreater(result['navigation_motion_segments_checked'], 0)

    def test_windowed_profile_retains_geometry_speed_velocity_gap_sweep_and_body_guards(self):
        for mutation, expected in [('outside', 'position leaves navigation'), ('gap', 'missing source frames'),
                ('speed', 'preferred speed'), ('velocity', 'velocity differs'), ('hole', 'sweep leaves navigation')]:
            with self.subTest(mutation=mutation):
                cfg, raw, _, _ = physical_fixtures.navigation_fixture()
                rows = [row for row in raw['agents'] if row.get('agent_id') == '1a']
                if mutation == 'outside': rows[0]['position']['x'] = -.2
                elif mutation == 'gap': raw['agents'].remove(rows[5])
                elif mutation == 'speed': rows[5]['position']['x'] += 1
                elif mutation == 'velocity': rows[5]['velocity']['x'] += .1
                else:
                    cfg['mapped_scene']['motion']['navigation']['allowed_center_polygons'][0]['holes'] = [
                        [[1.002, .07], [1.009, .07], [1.009, .08], [1.002, .08]]]
                with self.assertRaisesRegex(ValueError, expected):
                    self.auditor.audit(cfg, raw, profile=window.PROFILE)
        cfg, raw = physical_fixtures.fixture()
        next(row for row in raw['agents'] if row.get('agent_id') == '1a')['position']['x'] += .1
        with self.assertRaisesRegex(ValueError, 'declared route'):
            self.auditor.audit(cfg, raw, profile=window.PROFILE)

    def test_unknown_profile_cannot_disable_physical_or_legacy_checks(self):
        cfg, raw = physical_fixtures.fixture()
        with self.assertRaisesRegex(ValueError, 'Unsupported physical audit profile'):
            self.auditor.audit(cfg, raw, profile='skip_physics')


if __name__ == '__main__':
    unittest.main()
