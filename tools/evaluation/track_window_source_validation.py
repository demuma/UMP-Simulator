#!/usr/bin/env python3
"""Opt-in validation of recorded visible-track contributions in a fixed window.

This module does not replace or call the legacy completed-cohort validator.
The full native clock, raw GT/lifecycle/sensor/publication agreement, exact map,
configuration law, source executable and independent physical audit remain hard
requirements. Destination coverage, pending/active episodes and reported stalls
are movement-quality observations, never reasons to delete or repair input.

Only the explicit protocol schema/profile below selects these semantics. Raw
tracks with one sensor sample remain input; only membership-target eligibility
requires at least two samples. No source simulation, database read, attack,
model fitting, output mutation or synthetic EOF lifecycle event occurs here.
"""
from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path
import re

import run_urban_privacy_sources as source

ROOT = Path(__file__).resolve().parents[2]
PROFILE = 'observed_track_window_v1'
PROTOCOL_SCHEMA = 'ump.observed-track-window-source-protocol.v1'
LEGACY_PROFILE = 'legacy_completed_v1'
AUDITOR = ROOT / 'tools/mapped_scene/audit_building_access.py'
EXPORTER = ROOT / 'tools/mapped_scene/export_replay.py'


def require(value, message):
    if not value:
        raise ValueError(message)


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reference(value):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'Invalid authenticated artifact reference')
    path = source.fixture.safe_path(Path(value['path']))
    require(source.sha(path) == value['sha256'], 'Referenced artifact hash mismatch')
    return path


def _audit_command(command, scene, replay, output, profile):
    require(isinstance(command, list) and len(command) >= 2 and isinstance(command[0], str), 'Invalid physical audit command')
    expected = [str(AUDITOR), '--scene', str(scene), '--replay', str(replay), '--output', str(output)]
    require(command[1:] == expected + (['--profile', PROFILE] if profile == PROFILE else [])
            or profile == LEGACY_PROFILE and command[1:] == expected + ['--profile', LEGACY_PROFILE],
            'Physical audit command/profile/path mismatch')


def _physical_audit(row, protocol, proof, config, config_sha, replay):
    """Authenticate independently executed checker evidence, without rerunning it.

    A historical successful default-strict audit is reusable only through an
    explicit frozen provenance entry, including the ORIGINAL auditor bytes and
    producer protocol. A failed/absent old audit needs a fresh windowed audit;
    it is never caught and reclassified as a physical pass.
    """
    scene = Path(row['scene_directory'])
    proof_sha = source.sha(replay / 'capture-proof.json')
    legacy = protocol.get('legacy_physical_audits', {}).get(proof_sha)
    windowed = protocol.get('windowed_physical_audits', {}).get(proof_sha)
    require(not (legacy is not None and windowed is not None), 'Ambiguous physical audit provenance')
    if legacy is not None:
        require(set(legacy) == {'report', 'execution', 'producer_protocol', 'archived_auditor'}, 'Incomplete legacy audit provenance')
        audit_path, execution_path, producer_path, archived_auditor = (
            _reference(legacy[name]) for name in ('report', 'execution', 'producer_protocol', 'archived_auditor'))
        producer = source.load(producer_path)
        require(source.sha(archived_auditor) == producer['frozen_files_sha256'][str(AUDITOR)], 'Original physical auditor bytes not authenticated')
        require(producer.get('configuration_equivalence_sha256') == protocol['configuration_equivalence_sha256']
                and producer.get('geometry_sha256') == protocol['geometry_sha256']
                and producer.get('simulator_sha256') == proof['native_execution']['binary_sha256'],
                'Legacy physical producer used another law/map/source binary')
        cases = [case for case in producer['cases'] if case.get('seed') == row['seed']
                 and case.get('scene_directory') == str(scene) and case.get('replay_directory') == str(replay)]
        require(len(cases) == 1, 'Original physical producer does not uniquely bind this capture')
        command, profile = cases[0]['audit_command'], LEGACY_PROFILE
    elif windowed is not None:
        require(set(windowed) == {'report', 'execution', 'command'}, 'Incomplete windowed audit provenance')
        audit_path, execution_path = _reference(windowed['report']), _reference(windowed['execution'])
        command, profile = windowed['command'], PROFILE
    else:
        audit_path = source.fixture.safe_path(scene.parent / 'motion-audit.json')
        execution_path = source.fixture.safe_path(scene.parent / 'audit-execution.json')
        command, profile = row['audit_command'], PROFILE
    _audit_command(command, scene, replay, audit_path, profile)
    audit, execution = source.load(audit_path), source.load(execution_path)
    require(execution.get('status') == 'complete' and type(execution.get('returncode')) is int
            and execution['returncode'] == 0 and execution.get('command') == command, 'Independent physical audit execution failed')
    require(audit.get('status') == 'pass' and audit.get('source_access_validation', {}).get('status') == 'pass'
            and audit.get('config_sha256') == config_sha
            and audit.get('native_source_sha256') == proof['files_sha256']['private/native_source.json'],
            'Independent physical/source-access audit failed or source binding differs')
    require(set(audit.get('portals', {})) == {p['id'] for p in config['mapped_scene']['portals']},
            'Physical audit portal registry differs from configuration')
    if profile == PROFILE:
        require(audit.get('validation_profile') == PROFILE and isinstance(audit.get('movement_coverage_quality'), dict),
                'Physical report lacks explicit windowed profile/coverage quality')
    else:
        require(audit.get('validation_profile', LEGACY_PROFILE) == LEGACY_PROFILE, 'Legacy report was relabeled')
        # Old successful strict reports must actually retain their stronger
        # coverage evidence; no all-planned completion gate is added here.
        coverage = sum(value.get('completed_entries', 0) > 0 and value.get('realized_exits', 0) > 0
                       for value in audit.get('portals', {}).values())
        require(len(config['mapped_scene']['portals']) >= 2 and coverage >= 2, 'Legacy physical coverage evidence missing')
    for key in ('navigation_static_body_checks', 'navigation_motion_segments_checked', 'navigation_velocity_checks',
                'independent_gt_body_pair_checks', 'independent_gt_swept_body_pair_checks', 'boundary_endpoint_checks'):
        require(type(audit.get(key)) is int and audit[key] >= 0, 'Missing/invalid physical check counter: ' + key)
    # A count may truthfully be zero in a sparse window (e.g. no simultaneous
    # pair). Static checks must still cover every retained GT body. The checker
    # unconditionally enforces geometry/speed/sweep rules whenever applicable.
    require(audit['navigation_static_body_checks'] == proof['gt_rows'] > 0, 'Physical audit did not inspect every GT body')
    for key in ('minimum_body_clearance_margin_m', 'minimum_swept_body_clearance_margin_m'):
        require(key in audit, 'Missing physical clearance evidence')
        value = audit[key]
        counter = 'independent_gt_swept_body_pair_checks' if 'swept' in key else 'independent_gt_body_pair_checks'
        require((value is None and audit[counter] == 0) or type(value) in (int, float) and value >= -1e-4,
                'Physical clearance violation')
    return audit, dict(profile=profile, report_sha256=source.sha(audit_path), execution_sha256=source.sha(execution_path),
                       reused_successful_legacy_audit=profile == LEGACY_PROFILE)


def validate_capture(row, protocol):
    """Return hard validity plus separate quality; reject all unsupported profiles.

    Protocol authentication/freezing by the caller remains mandatory, as with
    source.validate_capture. This function additionally rechecks its declared
    frozen code/binary/environment and all retained capture artifact bytes.
    A legacy physical import must be predeclared in legacy_physical_audits.
    """
    require(protocol.get('schema') == PROTOCOL_SCHEMA and protocol.get('source_validation_profile') == PROFILE,
            'Explicit observed-track-window protocol schema/profile required')
    require(protocol.get('source_horizon_ms') == 300000, 'Require fixed full 300-second window')
    frozen = protocol.get('frozen_files_sha256', {})
    # Freeze the entire maintained dependency set, not merely the direct
    # imports. This includes map readers, transit/access helpers, replay tools,
    # source code and the historical law/geometry inputs used by the producer.
    require(isinstance(protocol.get('historical_scene'), str), 'Windowed protocol needs its frozen historical scene')
    historical = source.fixture.safe_path(Path(protocol['historical_scene']))
    required_code = set(source.source_paths(historical)) | {Path(__file__).resolve()}
    require(all(str(path) in frozen for path in required_code), 'Windowed protocol must freeze all validation helpers')
    require(frozen.get(protocol.get('simulator_path')) == protocol.get('simulator_sha256'), 'Source binary is not frozen')
    source.frozen_check(protocol)
    scene = source.fixture.safe_path(Path(row['scene_directory']))
    replay = source.fixture.safe_path(Path(row['replay_directory']))
    require(scene.parent == replay.parent and scene != replay, 'Capture scene/replay must share their own case directory')
    proof = source.load(replay / 'capture-proof.json')
    require(proof.get('schema') == 'ump.mapped-recording-proof.v1' and proof.get('status') == 'verified'
            and proof.get('source_horizon_completed') is True, 'Require verified complete source horizon')
    hashes = proof.get('files_sha256', {})
    require(source.REQUIRED_FILES <= set(hashes), 'Capture proof must bind every required source/private artifact')
    for name, expected in hashes.items():
        require(isinstance(expected, str) and re.fullmatch(r'[a-f0-9]{64}', expected)
                and source.sha(source.safe_file(replay, name)) == expected, 'Capture proof artifact hash mismatch: ' + name)
    config = source.config_read(scene / 'config.yaml')
    config_sha = source.sha(scene / 'config.yaml')
    require(config_sha == hashes['private/config.yaml'], 'Scene and captured configuration differ')
    law = source.configuration_law(config)
    require(source.digest(law) == protocol['configuration_equivalence_sha256'], 'Source configuration law changed')
    if 'configuration_law' in protocol:
        require(law == protocol['configuration_law'], 'Source configuration law literal differs')
    require(set(protocol['geometry_sha256']) == {'building_access.json', 'map_background.png'}, 'Exact fixed map files required')
    for name, expected in protocol['geometry_sha256'].items():
        require(source.sha(scene / name) == expected == hashes[name], 'Fixed mapped geometry/background changed')
    manifest = source.load(scene / 'scene_manifest.json')
    require(manifest.get('status') == 'pass' and manifest.get('seed') == row['seed']
            and manifest.get('configuration_sha256') == config_sha
            and manifest.get('generator_sha256') == frozen[str(ROOT / 'tools/mapped_scene/build_mapped_scene.py')],
            'Generated scene manifest/config/seed/builder mismatch')
    demand = manifest['building_access']['demand']
    require(demand.get('arrival_interval_ms') == 150 and demand.get('road_user_fraction') == .2
            and demand.get('distributed_crossing_fraction_of_through_pedestrian_trips') == .2,
            'Mixed traffic demand configuration changed')
    require(manifest.get('source_options') == dict(expanded_shop_access=True, pedestrians_only=False,
            subway_access=True, rider_priority=True), 'Mapped source options changed')
    execution = source.load(replay / 'private/execution.json')
    require(execution == source.load(scene / 'execution.json') == proof.get('native_execution')
            and execution.get('schema') == 'ump.mapped-execution.v1' and execution.get('state') == 'complete'
            and type(execution.get('exit_code')) is int and execution['exit_code'] == 0
            and execution.get('binary_sha256') == protocol['simulator_sha256']
            and execution.get('config_sha256') == config_sha, 'Native execution/config/frozen binary mismatch')
    budget = proof.get('capture_budget', {})
    require(budget.get('max_capture_mib') == source.CAPTURE_MIB
            and budget.get('max_capture_bytes') == source.CAPTURE_MIB * 1024**2
            and budget.get('source_configuration_sha256') == config_sha
            and budget.get('native_source_json_bytes') == (replay / 'private/native_source.json').stat().st_size,
            'Capture byte budget/config binding changed')
    exporter = _module(EXPORTER, 'ump_windowed_recording_exporter')
    raw = source.load(replay / 'private/native_source.json')
    metadata = [item for item in raw['agents'] if item.get('data_type') == 'metadata']
    require(len(metadata) == 1 and metadata[0].get('frame_rate') == 1 / config['simulation']['time_step']
            and metadata[0].get('simulation_area') == dict(width=80, height=80)
            and metadata[0].get('observation_identity_unit') == 'visible_episode_track'
            and metadata[0].get('ground_truth_identity_unit') == 'synthetic_person',
            'Native metadata source clock/area/identity unit mismatch')
    # The historical exporter rounds ISO timestamps. Reject sub-millisecond
    # raw times first, using the maintained exact parser, so rounding cannot
    # manufacture a source/sensor/lifecycle point on the numerical clock.
    for item in raw['agents']:
        kind = item.get('data_type')
        if kind in ('metadata', 'agent data') or kind == 'mapped lifecycle event' and 'timestamp' in item:
            source.fixture.epoch(item.get('timestamp'))
    for item in raw['sensor']:
        if item.get('data_type') == 'adaptive grid data':
            source.fixture.epoch(item.get('timestamp'))
    rebuilt_data, rebuilt_result, rebuilt_proof = exporter.build_recording(config, raw)
    data = source.load(replay / 'observations.json')
    require(data == rebuilt_data, 'Stored observations differ from actual GT/sensor recording')
    require(source.load(replay / 'native_result.json') == rebuilt_result, 'Stored native result differs from actual publication/journal recording')
    require(all(proof.get(key) == value for key, value in rebuilt_proof.items()), 'Stored capture proof differs from rebuilt raw recording')
    access = exporter.validate_scene_building_access(scene, config, scene / 'building_access.json')
    require(proof.get('building_access') == access, 'Stored physical access proof differs from actual scene')
    types = {profile['type'] for profile in config['agents']['road_user_taxonomy']}
    traces = source.fixture.validate_replay(data, types)
    people = config['mapped_scene']['people']
    registry = {episode['track_id']: person['type'] for person in people for episode in person['episodes']}
    require(len(registry) == sum(len(person['episodes']) for person in people), 'Duplicate configured track identity')
    require(set(traces) <= set(registry), 'Observed track is absent from configured registry')
    require(all(item['type'] == registry[item['id']] for batch in data['batches'] for item in batch['observations']),
            'Observed type differs from configured track')
    origin = rebuilt_proof['source_origin_epoch_ms']
    observed_registry = {item['agent_id'] for item in raw['agents'] if item.get('data_type') == 'agent data'
        and 0 < source.fixture.epoch(item['timestamp']) - origin < 300000
        and (source.fixture.epoch(item['timestamp']) - origin) % 100 == 0
        and exporter.inside(item['position'], data['coverage'])}
    require(set(traces) == observed_registry, 'Observation track count differs from actual measured GT registry')
    eligible = sum(len(trace) >= 2 for trace in traces.values())
    require(eligible > 0, 'No observed track has at least two samples for target eligibility')
    diagnostics = rebuilt_proof['motion_quality']['reported_diagnostics']
    require(type(diagnostics.get('body_overlap_violations')) is int and diagnostics['body_overlap_violations'] == 0,
            'Missing/nonzero reported body overlaps')
    require(type(diagnostics.get('active_stalled_tracks')) is int, 'Missing recorded stalled-track quality')
    populations = Counter(person['type'] for person in people)
    require(dict(populations) == manifest['scene_contract']['population_by_observed_profile'], 'Scene realized type counts differ')
    audit, audit_provenance = _physical_audit(row, protocol, proof, config, config_sha, replay)
    contributions = Counter(item['type'] for batch in data['batches'] for item in batch['observations'])
    files = {str(path.relative_to(scene.parent)): source.sha(path) for path in
             (scene / 'config.yaml', scene / 'scene_manifest.json', scene / 'execution.json', replay / 'capture-proof.json')}
    files.update({'replay/' + name: value for name, value in hashes.items()})
    return dict(status='verified', validation_profile=PROFILE,
        observations_sha256=hashes['observations.json'], capture_proof_sha256=source.sha(replay / 'capture-proof.json'),
        configuration_equivalence_sha256=protocol['configuration_equivalence_sha256'],
        normalized_source_fingerprint=source.privacy_dataset.normalized_fingerprint(data),
        planned_route_fingerprint=source.planned_route_fingerprint(config), files_sha256=files,
        owned_databases=[config['database']['db_name'] + suffix for suffix in ('', '_Releases', '_Private')],
        realized=dict(scheduled_people=len(people), scheduled_episodes=len(registry), observed_episode_count=len(traces),
            observation_contributions=sum(contributions.values()), population_by_type=dict(populations),
            observed_contributions_by_type=dict(contributions), peak_observed_tracks=max(len(b['observations']) for b in data['batches']),
            measured_samples=len(data['batches']), measured_empty_samples=sum(not b['observations'] for b in data['batches']),
            source_horizon_ms=data['end_ms'], sampling_period_ms=data['sampling_period_ms'],
            eligible_target_tracks=eligible, single_sample_observed_tracks=sum(len(t) == 1 for t in traces.values()),
            configured_tracks_without_sensor_samples=len(registry) - len(traces)),
        movement_quality=dict(lifecycle_quality=rebuilt_proof['lifecycle_quality'], motion_quality=rebuilt_proof['motion_quality'],
            all_scheduled_episodes_completed=rebuilt_proof['all_scheduled_episodes_completed'],
            scheduled_episode_sensor_observability=rebuilt_proof.get('sensor_observability'),
            all_planned_entries_completed=audit.get('all_planned_entries_completed'),
            targets_with_completed_entries=audit.get('targets_with_completed_entries'),
            buildings_with_completed_entries=audit.get('buildings_with_completed_entries'),
            buildings_with_realized_exits=audit.get('buildings_with_realized_exits'),
            movement_coverage_quality=audit.get('movement_coverage_quality'), physical_audit=audit_provenance,
            scope='Quality is reported without filtering, dropping stalls, completing visits or reconnecting private person identities.'),
        checks=dict(full_horizon=True, source_hashes_verified=True, same_configuration_law=True, fixed_geometry=True,
            raw_recording_rebuilt=True, recorded_gt_visible_intervals=True, observed_registry='pass',
            source_observability='observed_registry_pass', independent_physical_audit='pass',
            at_least_one_eligible_target=True),
        source_unit='One observed visible-episode track contribution within the fixed 300-second window; not a whole person or completed visit.')
