#!/usr/bin/env python3
"""Execute the frozen P25.3 main source slots without retry or replacement.

TRAIN/CAL may be captured while the implementation supplement is being validated.
TEST additionally requires an authenticated P25.4 implementation and model lock.
Native source generation, physical audits and all source gates reuse the unchanged
P25.3 source helper. This wrapper never trains attacks or reads mechanism scores.
"""
from __future__ import annotations
import argparse
import fcntl
import os
from copy import deepcopy
from pathlib import Path
import shutil
import signal
import sys

import run_urban_privacy_sources as source
import urban_privacy_fixture as fixture
import urban_privacy_split as split

ROOT = source.ROOT
SCHEMA = 'ump.urban-primary-source-protocol.v1'
MIN_FREE_BYTES = 3 * 1024**3


def require(condition, message):
    fixture.insist(condition, message)


def prepare(freeze, output):
    freeze = fixture.safe_path(freeze, root=ROOT / 'results')
    checked = split.verify_freeze(freeze)
    manifest = source.load(freeze / 'manifest.json')
    design = manifest['design']
    reference = next(row for row in design['generator']['evidence_files']
                     if row['path'].endswith('/protocol.json'))
    pilot = source.load(ROOT / reference['path'])
    require(source.sha(ROOT / reference['path']) == reference['sha256'], 'DEV protocol changed')
    source.frozen_check(pilot)
    for row in design['generator']['evidence_files']:
        require(source.sha(ROOT / row['path']) == row['sha256'], 'Frozen implementation changed: ' + row['path'])
    output = fixture.new_output(output)
    cases = []
    for group in manifest['groups']:
        seed = group['seeds']['source_generation']
        name = 'seed' + str(seed)
        cases.append(dict(id=name, group_id=group['group_id'], split=group['split'], seed=seed,
                          scene_directory=str(output / name / 'scene'),
                          replay_directory=str(output / name / 'replay'),
                          command=source.command(output, seed), audit_command=source.audit_command(output, seed)))
    protocol = deepcopy(pilot)
    protocol.update(schema=SCHEMA, output_directory=str(output), prepared_at=source.now(), cases=cases,
                    freeze_directory=str(freeze), manifest_sha256=checked['manifest_sha256'],
                    frozen_manifest_files_sha256={str(path): source.sha(path) for path in freeze.iterdir()},
                    planned_group_counts=design['group_counts'], minimum_free_bytes=MIN_FREE_BYTES,
                    scope='72 frozen primary recording slots; failures retained, no retry/replacement, no attack assessment.',
                    test_gate='Authenticated implementation supplement plus locked TRAIN/CAL models before TEST source generation.')
    protocol['frozen_files_sha256'][str(Path(__file__).resolve())] = source.sha(Path(__file__).resolve())
    source.write(output / 'protocol.json', protocol)
    fixture.write_new(output / 'protocol.sha256', (source.sha(output / 'protocol.json') + '\n').encode())
    return output


def read_protocol(output):
    output = fixture.safe_path(output, root=ROOT / 'results')
    require(source.sha(output / 'protocol.json') == fixture.read_bytes(output / 'protocol.sha256').decode().strip(),
            'Primary source protocol changed')
    protocol = source.load(output / 'protocol.json')
    require(protocol['schema'] == SCHEMA and protocol['output_directory'] == str(output), 'Wrong primary source protocol')
    for path, digest in protocol['frozen_manifest_files_sha256'].items():
        require(source.sha(path) == digest, 'Frozen main design changed')
    manifest = source.load(Path(protocol['freeze_directory']) / 'manifest.json')
    require(source.sha(Path(protocol['freeze_directory']) / 'manifest.json') == protocol['manifest_sha256'], 'Manifest changed')
    expected = []
    for group in manifest['groups']:
        seed = group['seeds']['source_generation']; name = 'seed' + str(seed)
        expected.append(dict(id=name, group_id=group['group_id'], split=group['split'], seed=seed,
                             scene_directory=str(output / name / 'scene'), replay_directory=str(output / name / 'replay'),
                             command=source.command(output, seed), audit_command=source.audit_command(output, seed)))
    require(protocol['cases'] == expected, 'Primary source seed/split/path assignment changed')
    source.frozen_check(protocol)
    return output, protocol, manifest


def authenticate_supplement(path, manifest_sha):
    path = fixture.safe_path(path, root=ROOT / 'results')
    supplement = source.load(path)
    require(supplement.get('schema') == 'ump.urban-primary-implementation.v1'
            and supplement.get('status') == 'verified_before_test'
            and supplement.get('manifest_sha256') == manifest_sha, 'Unverified or wrong implementation supplement')
    required = {'tools/evaluation/' + name for name in (
        'run_urban_privacy_primary_sources.py', 'run_urban_privacy_primary.py',
        'urban_privacy_statistics.py', 'urban_privacy_queries.py', 'urban_privacy_analysis.py',
        'test_run_urban_privacy_primary_sources.py', 'test_run_urban_privacy_primary.py',
        'test_urban_privacy_statistics.py', 'test_urban_privacy_queries.py', 'test_urban_privacy_analysis.py')}
    require(required <= set(supplement.get('files_sha256', {})), 'Incomplete implementation code evidence')
    require(len(supplement.get('test_receipts', [])) >= 2, 'Require unit and DEV integration validation receipts')
    for name, digest in supplement['files_sha256'].items():
        require(source.sha(ROOT / name) == digest, 'Supplement implementation changed: ' + name)
    for receipt in supplement['test_receipts']:
        require(source.sha(path.parent / receipt['path']) == receipt['sha256'], 'Implementation validation receipt changed')
    return supplement


def authenticate_test_gate(implementation, lock, manifest_sha):
    require(implementation is not None and lock is not None, 'TEST needs implementation supplement and TRAIN/CAL model lock')
    supplement = authenticate_supplement(implementation, manifest_sha)
    lock = fixture.safe_path(lock, root=ROOT / 'results')
    models = source.load(lock)
    require(models.get('schema') == 'ump.urban-primary-model-lock.v1'
            and models.get('status') == 'locked_before_test'
            and models.get('manifest_sha256') == manifest_sha
            and models.get('implementation_sha256') == source.sha(implementation)
            and models.get('group_counts') == {'train': 24, 'calibration': 16}
            and models.get('test_rows_seen') == 0, 'TRAIN/CAL model lock is incomplete or belongs to another study')
    require(models.get('implementation_files_sha256') == supplement['files_sha256'], 'Model and supplement implementation differ')
    manifest_path = fixture.safe_path(Path(supplement['freeze_directory']) / 'manifest.json', root=ROOT / 'results')
    require(source.sha(manifest_path) == manifest_sha, 'Supplement refers to another frozen manifest')
    manifest = source.load(manifest_path)
    for key in ('models', 'data'):
        reference = models.get(key, {})
        path = split.relative_file(lock.parent, reference)
        require(source.sha(path) == reference['sha256'], 'Locked TRAIN/CAL evidence changed')
    fitted = source.load(split.relative_file(lock.parent, models['models']))
    expected = {role: sorted(row['group_id'] for row in manifest['groups'] if row['split'] == role)
                for role in ('train', 'calibration')}
    require(fitted.get('training_group_ids') == expected['train']
            and fitted.get('calibration_group_ids') == expected['calibration'], 'Actual model source groups differ')
    require(set(fitted.get('expected_method_ids', [])) == {row['id'] for row in manifest['design']['methods']}
            and len(fitted.get('models', [])) == 22, 'Actual model family is incomplete')
    rows = source.load(split.relative_file(lock.parent, models['data']))
    require(isinstance(rows, list) and len(rows) == 40 * 22
            and {row['group_id'] for row in rows} == set(expected['train'] + expected['calibration'])
            and all(row['split'] in expected and row['group_id'] in expected[row['split']] for row in rows),
            'Actual TRAIN/CAL data missing, misassigned or includes TEST')
    import urban_privacy_analysis as analysis
    analysis.validate_model_lock(fitted, rows)
    return models


def summarize(output, protocol, manifest, *, verify=True):
    cases, seen = [], {}
    exclusions = {row.get(key) for row in manifest['exclusions'] for key in
                  ('observations_sha256', 'normalized_source_fingerprint', 'normalized_source_fingerprint_v2')}
    excluded_routes = {row.get('planned_route_fingerprint') for row in manifest['exclusions']}
    for row in protocol['cases']:
        directory = output / row['id']; receipt = directory / 'private-source-summary.json'
        case = {key: row[key] for key in ('id', 'group_id', 'split', 'seed', 'scene_directory', 'replay_directory')}
        if not receipt.is_file():
            case['status'] = 'interrupted' if directory.exists() else 'not_attempted'
        else:
            saved = source.load(receipt)
            require(all(saved.get(key) == row[key] for key in ('id', 'group_id', 'seed', 'scene_directory', 'replay_directory')),
                    'Source receipt identity mismatch')
            require(saved.get('split', row['split']) == row['split'], 'Source receipt split mismatch')
            case.update(saved)
            case['split'] = row['split']
            if case['status'] == 'verified':
                try:
                    if verify:
                        actual = source.validate_capture(row, protocol)
                        require(all(case.get(key) == value for key, value in actual.items()), 'Accepted source receipt differs')
                    identity_path = directory / 'primary-identity.json'
                    if not verify and identity_path.is_file():
                        identity = source.load(identity_path)
                        require(identity['observations_sha256'] == case['observations_sha256'], 'Cached primary identity differs')
                        normalized = identity['normalized_source_fingerprint_v2']
                    else:
                        data = source.load(Path(row['replay_directory']) / 'observations.json')
                        normalized = split.normalized_fingerprint(data)
                        if not identity_path.exists():
                            source.write(identity_path, {'observations_sha256': case['observations_sha256'],
                                'normalized_source_fingerprint_v2': normalized})
                    require(not ({case['observations_sha256'], case['normalized_source_fingerprint'], normalized} & exclusions),
                            'Primary recording overlaps excluded DEV/historical source')
                    require(case['planned_route_fingerprint'] not in excluded_routes, 'Route plan overlaps excluded DEV source')
                    case['normalized_source_fingerprint_v2'] = normalized
                    for field in ('normalized_source_fingerprint_v2', 'planned_route_fingerprint'):
                        key = (field, case[field])
                        if key in seen:
                            case['status'] = 'invalid_duplicate'
                            seen[key]['status'] = 'invalid_duplicate'
                        else:
                            seen[key] = case
                except Exception as error:
                    case.update(status='invalid', error=str(error))
        cases.append(case)
    counts = {name: {state: sum(c['split'] == name and c['status'] == state for c in cases)
                     for state in sorted({c['status'] for c in cases})} for name in ('train', 'calibration', 'test')}
    return dict(schema='ump.urban-primary-source-summary.v1', status='verified' if all(c['status'] == 'verified' for c in cases) else 'incomplete',
                manifest_sha256=protocol['manifest_sha256'], planned_count=72,
                attempted_count=sum(c['status'] != 'not_attempted' for c in cases),
                verified_count=sum(c['status'] == 'verified' for c in cases), by_split=counts, cases=cases)


def snapshot(output, summary):
    name = 'source-summary-' + source.now().replace(':', '').replace('+', '_') + '.json'
    source.write(output / name, summary)
    print(f"source_snapshot={name} verified={summary['verified_count']}/72 attempted={summary['attempted_count']}", flush=True)


def _resume_locked(output, splits, *, limit=None, implementation=None, model_lock=None):
    output, protocol, manifest = read_protocol(output)
    if 'test' in splits:
        authenticate_test_gate(implementation, model_lock, protocol['manifest_sha256'])
    summary = summarize(output, protocol, manifest)
    snapshot(output, summary)
    attempts = 0
    for row in protocol['cases']:
        if row['split'] not in splits or (output / row['id']).exists():
            continue
        if limit is not None and attempts >= limit:
            break
        require(shutil.disk_usage(output).free >= protocol['minimum_free_bytes'], 'Less than 3 GiB free; stop before starting another capture')
        print(f"source_start group={row['group_id']} split={row['split']} seed={row['seed']}", flush=True)
        result = source.attempt(output, protocol, row)
        attempts += 1
        print(f"source_done group={row['group_id']} status={result['status']}", flush=True)
        # Save the just-completed case immediately; full reauthentication is done
        # on resume/verify rather than O(N squared) physical proof reads.
        summary = summarize(output, protocol, manifest, verify=False)
        snapshot(output, summary)
    snapshot(output, summarize(output, protocol, manifest))


def resume(output, splits, *, limit=None, implementation=None, model_lock=None):
    output = fixture.safe_path(output, root=ROOT / 'results')
    lock_path = output / '.running.lock'
    descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Another source runner owns this study') from error
        _resume_locked(output, splits, limit=limit, implementation=implementation, model_lock=model_lock)
    finally:
        os.close(descriptor)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare', type=Path); action.add_argument('--resume', type=Path); action.add_argument('--verify', type=Path)
    parser.add_argument('--freeze', type=Path); parser.add_argument('--split', action='append', choices=('train','calibration','test'))
    parser.add_argument('--limit', type=int); parser.add_argument('--implementation', type=Path); parser.add_argument('--model-lock', type=Path)
    args = parser.parse_args(argv)
    require(args.limit is None or args.limit > 0, 'Limit must be positive')
    if args.prepare:
        require(args.freeze is not None, '--prepare requires --freeze'); print(prepare(args.freeze, args.prepare))
    elif args.verify:
        out, protocol, manifest = read_protocol(args.verify); snapshot(out, summarize(out, protocol, manifest))
    else:
        require(args.split, 'Declare --split explicitly')
        resume(args.resume, args.split, limit=args.limit, implementation=args.implementation, model_lock=args.model_lock)


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, interrupted)
    main()
