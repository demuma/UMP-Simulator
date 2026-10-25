#!/usr/bin/env python3
"""Predeclare eight private same-site DEV source captures through run_scene.py.

No attack, effectiveness estimate or model-selection split is produced. Every seed
gets at most one serial attempt, including failures/timeouts/interruption. Owned
UUID databases and ignored local artifacts are retained. --prepare-only freezes
the complete protocol; --resume continues only seeds that were never attempted.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import time

import yaml
import privacy_dataset
import urban_privacy_fixture as fixture

ROOT = Path(__file__).resolve().parents[2]
SEEDS = tuple(range(2026102501, 2026102509))
HISTORICAL = Path('results/expanded-access-mixed-2026-10-24-v1/scene')
SCHEMA = 'ump.urban-privacy-sources.v1'
PROTOCOL_SCHEMA = 'ump.urban-privacy-sources-protocol.v1'
CAPTURE_MIB = 2048
REQUIRED_FILES = {'observations.json', 'native_result.json', 'map_background.png',
                  'building_access.json', 'private/native_source.json',
                  'private/config.yaml', 'bundle.json', 'private/execution.json'}
SCOPE = ('Eight independently seeded same-site source-generation attempts for DEV pipeline validation only; '
         'no training, held-out privacy estimate, calibrated mobility, source representativeness or population independence claim.')


def require(value, message):
    if not value:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return fixture.sha(Path(path))


def load(path):
    return fixture.load(Path(path))


def write(path, value):
    fixture.write_new(Path(path), fixture.encoded(value))


def digest(value):
    return hashlib.sha256(fixture.canonical(value)).hexdigest()


def safe_file(directory, name):
    require(isinstance(name, str) and name and '\\' not in name and not Path(name).is_absolute()
            and all(part not in ('', '.', '..') for part in name.split('/')), 'Unsafe artifact path')
    return fixture.safe_path(Path(directory) / name, root=Path(directory))


def config_read(path):
    value = yaml.safe_load(fixture.read_bytes(Path(path)))
    require(isinstance(value, dict), 'Expected mapped YAML configuration')
    return value


def configuration_law(config):
    """Only seeded plans, identities, DB namespace and realized type mix may vary."""
    value = deepcopy(config)
    database = value['database']['db_name']
    require(re.fullmatch(r'UMP_Mapped_[0-9a-f]{32}', database) is not None, 'Expected fresh UUID database namespace')
    require(value['database']['clear_database'] is False, 'Database clearing is forbidden')
    sensor = value['sensors'][0]
    require(sensor['database']['db_name'] == database
            and sensor['aggregation']['publication']['database'] == database + '_Releases'
            and sensor['aggregation']['publication']['journal_database'] == database + '_Private',
            'Source must use only its three owned databases')
    def replace(item):
        if isinstance(item, dict):
            return {key: replace(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [replace(val) for val in item]
        return item.replace(database, '<OWNED_DB>') if isinstance(item, str) else item
    value = replace(value)
    value['mapped_scene'].pop('routes')
    people = value['mapped_scene'].pop('people')
    counts = Counter(person['type'] for person in people)
    require(len(people) == 128 and value['agents']['num_agents'] == 128, 'Expected 128 configured private people')
    for profile in value['agents']['road_user_taxonomy']:
        require(profile['probability'] == counts[profile['type']] / 128, 'Taxonomy probability must describe the realized configured cohort')
        profile.pop('probability')
    require(value['simulation']['duration_seconds'] == 300, 'Expected full 300-second source horizon')
    return value


def planned_route_fingerprint(config):
    """Discard route/track/person identifiers, retain geometric plans and schedules."""
    routes = {row['id']: {key: value for key, value in row.items() if key != 'id'}
              for row in config['mapped_scene']['routes']}
    require(len(routes) == len(config['mapped_scene']['routes']), 'Duplicate planned route identity')
    people = []
    for person in config['mapped_scene']['people']:
        episodes = []
        for episode in person['episodes']:
            episodes.append(dict({key: value for key, value in episode.items() if key not in ('track_id', 'route_id')},
                                 route=routes[episode['route_id']]))
        people.append(episodes)
    return digest(sorted(people, key=lambda row: fixture.canonical(row)))


def source_paths(historical):
    paths = [Path(__file__).resolve(), ROOT / 'tools/evaluation/privacy_dataset.py',
             ROOT / 'tools/evaluation/urban_privacy_fixture.py', ROOT / 'tools/evaluation/make_fixture.py',
             ROOT / 'tools/evaluation/run_local_policy_replay.py', ROOT / 'tools/evaluation/recipient_support.py',
             ROOT / 'simulator/examples/temporal-aggregation/config.yaml', ROOT / 'simulator/config.yaml',
             ROOT / 'simulator/CMakeLists.txt', ROOT / 'tools/replay_viewer/serve.py']
    for directory in ('simulator/src', 'simulator/include'):
        paths += [path for path in (ROOT / directory).rglob('*') if path.is_file()]
    for directory in ('tools/mapped_scene', 'tools/osm_regions'):
        paths += list((ROOT / directory).glob('*.py')) + list((ROOT / directory).glob('requirements.txt'))
    paths += [path for path in (ROOT / 'tools/osm_regions/data/moenckeberg').rglob('*') if path.is_file()]
    paths += [historical / name for name in ('config.yaml', 'scene_manifest.json', 'building_access.json', 'map_background.png')]
    return sorted(set(paths))


def environment():
    packages = {name: importlib.metadata.version(name) for name in
                ('PyYAML', 'Shapely', 'matplotlib', 'numpy', 'pyproj', 'Pillow')}
    shell = shutil.which('mongosh')
    require(shell is not None, 'mongosh must be available')
    result = subprocess.run([shell, '--version'], text=True, capture_output=True, timeout=10, check=True)
    return dict(python_executable=sys.executable, python_resolved=str(Path(sys.executable).resolve()),
                python_version=platform.python_version(), platform=platform.platform(), packages=packages,
                mongosh_path=shell, mongosh_version=result.stdout.strip(), mongosh_sha256=sha(Path(shell).resolve()))


def command(output, seed):
    return [sys.executable, str(ROOT / 'tools/mapped_scene/run_scene.py'),
            '--duration-s', '300', '--seed', str(seed), '--motion-mode', 'storefronts',
            '--population', '128', '--arrival-interval-ms', '150', '--urban-traffic',
            '--subway-access', '--expanded-shop-access', '--rider-priority',
            '--road-user-fraction', '0.2', '--distributed-crossing-fraction', '0.2',
            '--pedestrian-clearance-m', '0.05', '--max-capture-mib', str(CAPTURE_MIB),
            '--output', str(output / ('seed' + str(seed)) / 'scene')]


def audit_command(output, seed):
    directory = output / ('seed' + str(seed))
    return [sys.executable, str(ROOT / 'tools/mapped_scene/audit_building_access.py'),
            '--scene', str(directory / 'scene'), '--replay', str(directory / 'replay'),
            '--output', str(directory / 'motion-audit.json')]


def prepare(output, *, historical_scene=None, wall_budget_s=420):
    require(type(wall_budget_s) is int and 1 <= wall_budget_s <= 420, 'Process wall cap must be 1..420 seconds')
    historical = fixture.safe_path(historical_scene or ROOT / HISTORICAL, root=ROOT / 'results')
    baseline = config_read(historical / 'config.yaml')
    manifest = load(historical / 'scene_manifest.json')
    require(manifest.get('seed') == 20261024 and manifest.get('status') == 'pass', 'Expected declared historical mixed scene')
    require(manifest['configuration_sha256'] == sha(historical / 'config.yaml'), 'Historical configuration changed')
    law = configuration_law(baseline)
    binary = fixture.safe_path(ROOT / 'simulator/build/Simulator', root=ROOT)
    frozen = {str(path): sha(path) for path in source_paths(historical)}
    frozen[str(binary)] = sha(binary)
    env = environment()
    output = fixture.new_output(Path(output))
    cases = [dict(id='seed' + str(seed), group_id='source-seed' + str(seed), seed=seed,
                  scene_directory=str(output / ('seed' + str(seed)) / 'scene'),
                  replay_directory=str(output / ('seed' + str(seed)) / 'replay'), command=command(output, seed),
                  audit_command=audit_command(output, seed))
             for seed in SEEDS]
    protocol = dict(schema=PROTOCOL_SCHEMA, prepared_at=now(), output_directory=str(output), cases=cases,
                    simulator_path=str(binary), simulator_sha256=sha(binary), environment=env,
                    frozen_files_sha256=frozen, historical_scene=str(historical),
                    configuration_equivalence_sha256=digest(law), configuration_law=law,
                    configuration_exclusions=['mapped_scene.people', 'mapped_scene.routes',
                        'agents.road_user_taxonomy[*].probability (must equal realized person proportions)',
                        'fresh UUID database namespace'],
                    geometry_sha256={name: sha(historical / name) for name in ('building_access.json', 'map_background.png')},
                    max_capture_mib=CAPTURE_MIB, max_capture_bytes=CAPTURE_MIB * 1024**2,
                    process_wall_budget_s=wall_budget_s, physical_audit_wall_budget_s=420, source_horizon_ms=300000,
                    budget_scope='Each complete run_scene process group: generation, native source and export. Capture byte budget is per bounded local artifact, not an RSS limit.',
                    database_lifecycle='run_scene creates fresh UUID databases; retain all three by default; cleanup is never requested.',
                    failure_rule='At most one attempt per predeclared seed. Failures, incomplete captures, timeouts and interruptions stay in the denominator; no replacement seed or retry.',
                    seed_independence_gate='Both normalized source trajectories and ID-independent planned route fingerprints must be unique across all accepted source captures.',
                    scope=SCOPE)
    write(output / 'protocol.json', protocol)
    fixture.write_new(output / 'protocol.sha256', (sha(output / 'protocol.json') + '\n').encode())
    return output, protocol


def frozen_check(protocol):
    for name, expected in protocol['frozen_files_sha256'].items():
        require(sha(name) == expected, 'Frozen source/binary/map changed: ' + name)
    require(environment() == protocol['environment'], 'Frozen Python/package/mongosh environment changed')


def read_protocol(output):
    output = fixture.safe_path(Path(output), root=ROOT / 'results')
    expected = fixture.read_bytes(output / 'protocol.sha256').decode().strip()
    require(sha(output / 'protocol.json') == expected, 'Predeclared protocol changed')
    protocol = load(output / 'protocol.json')
    require(protocol.get('schema') == PROTOCOL_SCHEMA and protocol['output_directory'] == str(output), 'Wrong source protocol/output')
    require([row['seed'] for row in protocol['cases']] == list(SEEDS), 'Predeclared seed matrix changed')
    require(all(row['command'] == command(output, row['seed'])
                and row['audit_command'] == audit_command(output, row['seed']) for row in protocol['cases']),
            'Predeclared capture/audit command changed')
    frozen_check(protocol)
    return output, protocol


def completed_validator():
    spec = importlib.util.spec_from_file_location('ump_urban_sources_mapped', ROOT / 'tools/mapped_scene/run_comparison.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_completed_source


def validate_capture(row, protocol):
    scene, replay = Path(row['scene_directory']), Path(row['replay_directory'])
    proof = load(replay / 'capture-proof.json')
    require(proof.get('schema') == 'ump.mapped-recording-proof.v1' and proof.get('status') == 'verified'
            and proof.get('source_horizon_completed') is True, 'Require verified complete source horizon')
    hashes = proof.get('files_sha256', {})
    require(REQUIRED_FILES <= set(hashes), 'Capture proof must bind every required private/source artifact')
    for name, expected in hashes.items():
        require(re.fullmatch(r'[a-f0-9]{64}', expected or '') and sha(safe_file(replay, name)) == expected,
                'Capture proof artifact hash mismatch: ' + name)
    data = load(replay / 'observations.json')
    config = config_read(scene / 'config.yaml')
    config_sha = sha(scene / 'config.yaml')
    require(config_sha == hashes['private/config.yaml'], 'Scene and captured configuration differ')
    require(digest(configuration_law(config)) == protocol['configuration_equivalence_sha256'], 'Source law differs from historical mixed configuration')
    for name, expected in protocol['geometry_sha256'].items():
        require(sha(scene / name) == expected and hashes[name] == expected, 'Fixed mapped geometry/background changed')
    manifest = load(scene / 'scene_manifest.json')
    require(manifest.get('status') == 'pass' and manifest.get('seed') == row['seed']
            and manifest.get('configuration_sha256') == config_sha, 'Generated scene manifest/config/seed mismatch')
    require(manifest.get('generator_sha256') == protocol['frozen_files_sha256'][str(ROOT / 'tools/mapped_scene/build_mapped_scene.py')], 'Generated scene builder differs from frozen generator')
    demand = manifest['building_access']['demand']
    require(demand['arrival_interval_ms'] == 150 and demand['road_user_fraction'] == .2
            and demand['distributed_crossing_fraction_of_through_pedestrian_trips'] == .2,
            'Mixed traffic demand configuration changed')
    require(manifest.get('source_options') == dict(expanded_shop_access=True, pedestrians_only=False,
            subway_access=True, rider_priority=True), 'Mapped source options changed')
    types = {profile['type'] for profile in config['agents']['road_user_taxonomy']}
    traces = fixture.validate_replay(data, types)
    completed_validator()(proof, data)
    quality = proof['lifecycle_quality']
    people = config['mapped_scene']['people']
    episode_count = sum(len(person['episodes']) for person in people)
    require(quality.get('scheduled_people') == 128 and quality.get('scheduled_episodes') == episode_count > 0
            and quality.get('status') == 'all_scheduled_episodes_completed'
            and quality.get('realized_starts') == quality.get('realized_ends') == episode_count
            and len(traces) == episode_count
            and set(traces) == {episode['track_id'] for person in people for episode in person['episodes']},
            'Incomplete scheduled cohort or missing observed episodes')
    diagnostics = proof.get('motion_quality', {}).get('reported_diagnostics', {})
    require(all(type(diagnostics.get(key)) is int and diagnostics[key] == 0
                for key in ('active_stalled_tracks', 'body_overlap_violations')),
            'Source reports missing/nonzero stalls or body overlaps')
    execution = load(replay / 'private/execution.json')
    require(execution == proof.get('native_execution') and execution.get('state') == 'complete'
            and execution.get('exit_code') == 0 and execution.get('binary_sha256') == protocol['simulator_sha256']
            and execution.get('config_sha256') == config_sha, 'Native execution receipt does not match frozen successful source')
    budget = proof.get('capture_budget', {})
    require(budget.get('max_capture_mib') == CAPTURE_MIB and budget.get('max_capture_bytes') == CAPTURE_MIB * 1024**2
            and budget.get('source_configuration_sha256') == config_sha, 'Capture budget/config binding changed')
    contributions = Counter(item['type'] for batch in data['batches'] for item in batch['observations'])
    populations = Counter(person['type'] for person in people)
    require(dict(populations) == manifest['scene_contract']['population_by_observed_profile'], 'Scene manifest realized type counts differ')
    files = {str(path.relative_to(scene.parent)): sha(path) for path in (scene / 'config.yaml', scene / 'scene_manifest.json', replay / 'capture-proof.json')}
    files.update({'replay/' + name: expected for name, expected in hashes.items()})
    audit_path = scene.parent / 'motion-audit.json'
    audit = load(audit_path)
    require(audit.get('status') == 'pass' and audit.get('all_planned_entries_completed') is True
            and audit.get('source_access_validation', {}).get('status') == 'pass'
            and audit.get('config_sha256') == config_sha
            and audit.get('native_source_sha256') == hashes['private/native_source.json'],
            'Independent physical/source-access audit failed or source binding differs')
    require(all(type(audit.get(key)) is int and audit[key] > 0 for key in
            ('navigation_static_body_checks', 'navigation_motion_segments_checked', 'navigation_velocity_checks',
             'independent_gt_swept_body_pair_checks', 'boundary_endpoint_checks')),
            'Physical audit must check actual sweeps, surfaces, speed and boundary endpoints')
    for portal in config['mapped_scene']['portals']:
        if portal.get('kind') != 'surface_access':
            counts = audit.get('portals', {}).get(portal['id'], {})
            require(counts.get('completed_entries', 0) > 0 and counts.get('realized_exits', 0) > 0,
                    'A declared shop destination lacks completed visits/returns')
    audit_execution = load(scene.parent / 'audit-execution.json')
    require(audit_execution.get('status') == 'complete' and audit_execution.get('returncode') == 0
            and audit_execution.get('command') == row['audit_command'], 'Independent physical audit execution failed')
    files.update({'motion-audit.json': sha(audit_path), 'audit-execution.json': sha(scene.parent / 'audit-execution.json')})
    return dict(status='verified', observations_sha256=hashes['observations.json'], capture_proof_sha256=sha(replay / 'capture-proof.json'),
                configuration_equivalence_sha256=protocol['configuration_equivalence_sha256'],
                normalized_source_fingerprint=privacy_dataset.normalized_fingerprint(data),
                planned_route_fingerprint=planned_route_fingerprint(config), files_sha256=files,
                owned_databases=[config['database']['db_name'] + suffix for suffix in ('', '_Releases', '_Private')],
                realized=dict(scheduled_people=len(people), scheduled_episodes=episode_count,
                    observed_episode_count=len(traces), observation_contributions=sum(contributions.values()),
                    population_by_type=dict(populations), observed_contributions_by_type=dict(contributions),
                    peak_observed_tracks=max(len(batch['observations']) for batch in data['batches']),
                    measured_samples=len(data['batches']), measured_empty_samples=sum(not batch['observations'] for batch in data['batches']),
                    source_horizon_ms=data['end_ms'], sampling_period_ms=data['sampling_period_ms']),
                checks=dict(all_scheduled_episodes_completed=True, source_observability='pass', full_horizon=True,
                    source_hashes_verified=True, same_configuration_law=True, fixed_geometry=True, independent_physical_audit='pass'))


def stop_owned_group(process):
    """Only the new session created for this capture is signaled; DBs survive."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=10)


def run_physical_audit(output, protocol, row):
    directory = output / row['id']
    receipt = dict(command=row['audit_command'], started_at=now(), status='failed')
    started = time.perf_counter()
    try:
        with (directory / 'audit-stdout.log').open('x') as stdout, (directory / 'audit-stderr.log').open('x') as stderr:
            result = subprocess.run(row['audit_command'], cwd=ROOT, stdout=stdout, stderr=stderr,
                                    timeout=protocol['physical_audit_wall_budget_s'], umask=0o077)
        receipt.update(status='complete' if result.returncode == 0 else 'failed', returncode=result.returncode)
    except subprocess.TimeoutExpired:
        receipt.update(status='timeout')
    except BaseException as error:
        receipt.update(status='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'failed', error=str(error))
        raise
    finally:
        receipt.update(elapsed_seconds=time.perf_counter() - started, finished_at=now())
        write(directory / 'audit-execution.json', receipt)
    require(receipt['status'] == 'complete', 'Independent physical audit failed or exceeded its finite wall cap')


def attempt(output, protocol, row):
    frozen_check(protocol)
    directory = output / row['id']
    require(not directory.exists(), 'A seed directory already exists; retry/overwrite forbidden: ' + row['id'])
    directory.mkdir(mode=0o700)
    write(directory / 'attempt.json', dict(schema='ump.urban-source-attempt.v1', started_at=now(),
          protocol_sha256=sha(output / 'protocol.json'), command=row['command'],
          process_wall_budget_s=protocol['process_wall_budget_s'], seed=row['seed']))
    started = time.perf_counter()
    receipt = dict(schema='ump.urban-source-execution.v1', status='failed', started_at=now())
    try:
        with (directory / 'stdout.log').open('x') as stdout, (directory / 'stderr.log').open('x') as stderr:
            process = subprocess.Popen(row['command'], cwd=ROOT, stdout=stdout, stderr=stderr,
                                       start_new_session=True, umask=0o077)
            try:
                code = process.wait(timeout=protocol['process_wall_budget_s'])
                receipt.update(status='complete' if code == 0 else 'failed', returncode=code)
            except subprocess.TimeoutExpired:
                stop_owned_group(process)
                receipt.update(status='timeout', returncode=process.returncode, owned_process_group_killed=True)
            except BaseException:
                stop_owned_group(process)
                receipt.update(status='interrupted', returncode=process.returncode, owned_process_group_killed=True)
                raise
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        receipt.update(status='failed', error=str(error))
    finally:
        receipt.update(elapsed_seconds=time.perf_counter() - started, finished_at=now())
        write(directory / 'execution.json', receipt)
    result = dict(id=row['id'], group_id=row['group_id'], seed=row['seed'],
                  scene_directory=row['scene_directory'], replay_directory=row['replay_directory'],
                  status=receipt['status'], execution=receipt)
    if receipt['status'] == 'complete':
        try:
            frozen_check(protocol)
            run_physical_audit(output, protocol, row)
            result.update(validate_capture(row, protocol))
        except Exception as error:
            result.update(status='invalid', error=str(error))
    write(directory / 'private-source-summary.json', result)
    return result


def summarize(output, protocol):
    cases = []
    for row in protocol['cases']:
        directory = output / row['id']
        summary = directory / 'private-source-summary.json'
        if summary.is_file():
            case = load(summary)
            require(all(case.get(key) == row[key] for key in
                    ('id', 'group_id', 'seed', 'scene_directory', 'replay_directory')),
                    'Source receipt group/seed/path differs from predeclared identity')
            # Reauthenticate accepted source receipts on every resume/summary.
            if case['status'] == 'verified':
                try:
                    require(validate_capture(row, protocol) == {key: value for key, value in case.items()
                            if key not in ('id', 'group_id', 'seed', 'scene_directory', 'replay_directory', 'execution')},
                            'Accepted source summary changed')
                except Exception as error:
                    case.update(status='invalid', error=str(error))
        else:
            case = {key: row[key] for key in ('id', 'group_id', 'seed', 'scene_directory', 'replay_directory')}
            case['status'] = 'interrupted' if directory.exists() else 'not_attempted'
            if directory.exists():
                case['error'] = 'Seed directory exists without a completed source receipt; it will never be retried.'
        cases.append(case)
    duplicate_groups = {}
    for field in ('normalized_source_fingerprint', 'planned_route_fingerprint'):
        by_hash = {}
        for case in cases:
            if case['status'] == 'verified':
                by_hash.setdefault(case[field], []).append(case['id'])
        duplicate_groups[field] = [ids for ids in by_hash.values() if len(ids) > 1]
    capture_verified = sum(case['status'] == 'verified' for case in cases)
    for field, groups in duplicate_groups.items():
        for group in groups:
            for case in cases:
                if case['id'] in group:
                    case['status'] = 'invalid_duplicate'
                    case.setdefault('duplicate_fingerprint_fields', []).append(field)
    accepted = sum(case['status'] == 'verified' for case in cases)
    attempted = sum(case['status'] != 'not_attempted' for case in cases)
    distinct = not any(duplicate_groups.values())
    return dict(schema=SCHEMA, protocol_sha256=sha(output / 'protocol.json'), status='verified' if accepted == 8 and distinct else 'incomplete',
                planned_case_count=8, attempted_case_count=attempted, verified_case_count=accepted,
                capture_verified_case_count=capture_verified,
                independent_source_count=accepted if distinct else None, all_sources_configuration_equivalent=accepted == 8,
                duplicate_fingerprint_groups=duplicate_groups, pilot_excluded_seeds=list(SEEDS),
                pilot_excluded_groups=[row['group_id'] for row in protocol['cases']], cases=cases, scope=SCOPE,
                independence_scope='Unique seed-conditioned plans/realizations at one fixed site; this is not independence of real-world people, sites or demand processes.')


def save_report(output, summary):
    reports = output / 'reports'
    reports.mkdir(mode=0o700, exist_ok=True)
    index = 1
    while (reports / f'summary-{index:03d}.json').exists():
        index += 1
    write(reports / f'summary-{index:03d}.json', summary)
    lines = ['# Private urban source-generation pilot', '', SCOPE, '',
             f"Attempted {summary['attempted_case_count']}/8; verified captures {summary['verified_case_count']}/8; overall {summary['status']}.", '',
             '| Seed | Status | People | Episodes | Observations | Peak tracks |', '|---|---|---:|---:|---:|---:|']
    for row in summary['cases']:
        realized = row.get('realized', {})
        lines.append('| ' + ' | '.join(str(value) for value in (row['seed'], row['status'],
            realized.get('scheduled_people', ''), realized.get('scheduled_episodes', ''),
            realized.get('observation_contributions', ''), realized.get('peak_observed_tracks', ''))) + ' |')
    lines += ['', 'Every planned seed remains in the denominator. Database namespaces, raw observations and person/episode identities remain private under ignored results/.',
              'Configuration equivalence permits seeded routes, identities and realized type proportions; realized density and per-type counts are reported separately in the private JSON.',
              'These receipts reuse maintained capture/lifecycle/observability validation; they make no effectiveness or empirical privacy claim.', '']
    fixture.write_new(reports / f'report-{index:03d}.md', '\n'.join(lines).encode())
    if summary['attempted_case_count'] == 8 and not (output / 'source-summary.json').exists():
        write(output / 'source-summary.json', summary)
    return summary


def resume(output, *, limit=None):
    require(limit is None or type(limit) is int and 1 <= limit <= 8, 'Limit must be 1..8 new attempts')
    output, protocol = read_protocol(output)
    require(not (output / '.running').exists(), 'Another run or interrupted lock exists; concurrent source capture is forbidden')
    lock = output / '.running'
    fixture.write_new(lock, fixture.encoded(dict(pid=os.getpid(), started_at=now())))
    try:
        count = 0
        for row in protocol['cases']:
            if (output / row['id']).exists():
                continue
            if limit is not None and count >= limit:
                break
            attempt(output, protocol, row)
            count += 1
        frozen_check(protocol)
        return save_report(output, summarize(output, protocol))
    except BaseException:
        save_report(output, summarize(output, protocol))
        raise
    finally:
        lock.unlink()


def terminate_requested(signum, _frame):
    raise KeyboardInterrupt('Termination signal ' + str(signum) + '; record interruption and retain all databases')


def main():
    signal.signal(signal.SIGTERM, terminate_requested)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--historical-scene', type=Path)
    parser.add_argument('--wall-budget-s', type=int, default=420)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--limit', type=int, help='At most this many previously unattempted seeds; the full matrix stays frozen')
    parser.add_argument('--verify', type=Path, help='Reauthenticate and write a new private summary snapshot; never runs native jobs')
    args = parser.parse_args()
    if args.verify:
        require(not any((args.output, args.resume, args.prepare_only, args.limit, args.historical_scene)), '--verify cannot be combined with capture flags')
        output, protocol = read_protocol(args.verify)
        summary = save_report(output, summarize(output, protocol))
    elif args.resume:
        require(not any((args.output, args.prepare_only, args.historical_scene)), '--resume uses the unchanged predeclared protocol')
        summary = resume(args.resume, limit=args.limit)
    else:
        require(args.output is not None, '--output is required for preparation')
        output, _ = prepare(args.output, historical_scene=args.historical_scene, wall_budget_s=args.wall_budget_s)
        if args.prepare_only:
            print(json.dumps(dict(status='prepared', output=str(output), cases=8, protocol_sha256=sha(output / 'protocol.json'))))
            return 0
        summary = resume(output, limit=args.limit)
    print(json.dumps({key: summary[key] for key in ('status', 'planned_case_count', 'attempted_case_count', 'verified_case_count')}))
    return 0 if summary['status'] == 'verified' else 2


if __name__ == '__main__':
    raise SystemExit(main())
