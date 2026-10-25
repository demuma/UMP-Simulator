#!/usr/bin/env python3
"""Build/independently verify one private P25.1 development membership fixture.

Only existing completed source observations are filtered. No native executable,
movement generation, aggregation replay, or attack is invoked. Raw agent evidence
is streamed without decoding the recipient releases or private journal channels.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'ump.urban-membership-dev-fixture.v1'
PROTOCOL_SCHEMA = 'ump.urban-membership-fixture-protocol.v1'
SEED, END_MS, PERIOD_MS = 20261025, 300000, 100
MAX_FILE_BYTES = 2 * 1024**3
COVERAGE = dict(x=0, y=0, width=80, height=80, leaf_depth=6)
POLICY_NAME = 'mixed_spatial20_adaptive_immediate_off-policy.json'
EXPECTED_SOURCE_SHA256 = 'c24134c724acf2df38a85b2906a2e80f8de7b420529a4b8cda3f9e5f98a3eff5'
EXPECTED_POLICY_SHA256 = 'eff7a65e08c3f352a0c984d956917e7312da8815021f256e68db6b2189016bda'
EXPECTED_CAPTURE_PROOF_SHA256 = 'eba903f5cf22ad97083cee0735b2397e78fece8dda4f8b7e45274840b5265640'
ARTIFACTS = ('in.json', 'out.json', 'target-trace.json', 'auxiliary-in.json', 'auxiliary-out.json')
POINT_FIELDS = {'observed_at_ms', 'x', 'y', 'cell_id'}
PUBLIC_KNOWLEDGE = {
    'candidate': 'Exact retrospective 25% (ceil, at least one) seeded subset of the complete episode sensor trace; coordinate/time/cell only, identical under both labels.',
    'prior': {'IN': 0.5, 'OUT': 0.5},
    'public_context': ['map/coverage geometry', 'taxonomy/policy definitions', 'sampling cadence',
                       'full 300-second horizon', 'contract logical availability and EOF rules'],
    'secret': 'Inclusion of one visible episode source contribution, not physical presence, person identity, visits, or every episode of a person.',
    'clock': 'Offline logical sealing; full-horizon retrospective auxiliary knowledge; no causal-prefix or wall-clock delivery assessment.',
    'recipient': 'Only the versioned contract recipient channel; no raw fixture, labels, traces, source groups or private manifest.',
}


def insist(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical(value: Any) -> bytes:
    """Rank keys: sorted keys, compact ASCII JSON, finite numbers, no newline."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def encoded(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(path: Path, *, root: Path | None = None, exists: bool = True) -> Path:
    path = Path(path).expanduser()
    insist('..' not in path.parts, 'Parent traversal is forbidden')
    if not path.is_absolute():
        path = Path.cwd() / path
    for part in (path, *path.parents):
        insist(not part.is_symlink(), f'Symlink paths are forbidden: {part}')
    path = path.resolve(strict=exists)
    if root is not None:
        insist(path.is_relative_to(root.resolve()), 'Path escapes its declared root')
    return path


def _open_read(path: Path, binary: bool = True):
    path = safe_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
        os.close(descriptor)
        raise ValueError('Input must be a regular file of at most 2 GiB')
    return os.fdopen(descriptor, 'rb' if binary else 'r', **({} if binary else {'encoding': 'utf-8'}))


def read_bytes(path: Path) -> bytes:
    with _open_read(path) as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    insist(len(data) <= MAX_FILE_BYTES, 'Input exceeds 2 GiB')
    return data


def sha(path: Path) -> str:
    value, total = hashlib.sha256(), 0
    with _open_read(path) as stream:
        while chunk := stream.read(1024 * 1024):
            total += len(chunk)
            insist(total <= MAX_FILE_BYTES, 'Input exceeds 2 GiB')
            value.update(chunk)
    return value.hexdigest()


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        insist(key not in result, 'Duplicate JSON object key')
        result[key] = value
    return result


def _nonfinite(token: str):
    raise ValueError(f'Nonfinite JSON value: {token}')


def load(path: Path) -> Any:
    return json.loads(read_bytes(path), object_pairs_hook=_pairs, parse_constant=_nonfinite)


def write_new(path: Path, data: bytes) -> None:
    insist(len(data) <= MAX_FILE_BYTES, 'Output exceeds 2 GiB')
    path = safe_path(path, exists=False)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def new_output(output: Path) -> Path:
    output = safe_path(output, root=PROJECT_ROOT / 'results', exists=False)
    insist(output != (PROJECT_ROOT / 'results').resolve(), 'Output must be a new results subdirectory')
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    result = subprocess.run(['git', '-C', str(PROJECT_ROOT), 'check-ignore', '--quiet', '--no-index',
                             str(output.relative_to(PROJECT_ROOT))], capture_output=True, check=False)
    insist(result.returncode == 0, 'Private output must be ignored by Git under results/')
    insist(output.parent.is_dir(), 'Output parent must already exist')
    output.mkdir(mode=0o700)
    return output


def private_bundle(directory: Path, *, initial: bool) -> Path:
    directory = safe_path(directory, root=PROJECT_ROOT / 'results')
    info = directory.stat()
    insist(directory.is_dir() and info.st_uid == os.getuid() and not info.st_mode & 0o077,
           'Fixture directory must be owner-only')
    expected = set(ARTIFACTS) | {'protocol.json', 'private-manifest.json'}
    if not initial:
        expected.add('verification.json')
    insist({p.name for p in directory.iterdir()} == expected, 'Unexpected or missing fixture artifacts')
    for path in directory.iterdir():
        safe_path(path, root=directory)
        info = path.stat()
        insist(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077,
               'Fixture artifacts must be owner-only regular files')
    return directory


def number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def cell_id(x: float, y: float, coverage: dict) -> int:
    insist(coverage['x'] <= x < coverage['x'] + coverage['width']
           and coverage['y'] <= y < coverage['y'] + coverage['height'], 'Position outside coverage')
    left, top, width, height = (coverage[k] for k in ('x', 'y', 'width', 'height'))
    value = 3
    for _ in range(coverage['leaf_depth']):
        width /= 2
        height /= 2
        right, bottom = x >= left + width, y >= top + height
        value = value * 4 + int(right) + 2 * int(bottom)
        left += width if right else 0
        top += height if bottom else 0
    return value


def validate_replay(replay: dict, allowed_types: set[str]) -> dict[str, list[dict]]:
    insist(isinstance(replay, dict) and replay.get('schema') == 'ump.observation-replay.v1', 'Expected observation replay v1')
    insist(set(replay) == {'schema', 'run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms', 'batches'},
           'Unexpected replay metadata')
    insist(all(isinstance(replay[k], str) and replay[k] for k in ('run_id', 'sensor_id')), 'Missing run/sensor identity')
    coverage = replay['coverage']
    insist(isinstance(coverage, dict) and set(coverage) == set(COVERAGE)
           and all(number(coverage[k]) for k in ('x', 'y', 'width', 'height'))
           and type(coverage['leaf_depth']) is int and coverage == COVERAGE, 'Unexpected coverage geometry/leaf depth')
    insist(type(replay['end_ms']) is int and replay['end_ms'] == END_MS
           and type(replay['sampling_period_ms']) is int and replay['sampling_period_ms'] == PERIOD_MS,
           'Full frozen 300-second horizon and 100-ms cadence required')
    insist(isinstance(replay['batches'], list) and len(replay['batches']) == END_MS // PERIOD_MS - 1,
           'Every sampling opportunity must be present')
    traces, types = defaultdict(list), {}
    for sequence, batch in enumerate(replay['batches'], 1):
        insist(isinstance(batch, dict) and set(batch) == {'sequence', 'observed_at_ms', 'status', 'observations'},
               'Unexpected batch metadata')
        insist(type(batch['sequence']) is int and batch['sequence'] == sequence
               and type(batch['observed_at_ms']) is int and batch['observed_at_ms'] == sequence * PERIOD_MS
               and batch['status'] == 'measured', 'Invalid batch metadata/cadence; measured-empty must remain measured')
        insist(isinstance(batch['observations'], list), 'Observations must be a list')
        seen = set()
        for observation in batch['observations']:
            insist(isinstance(observation, dict) and set(observation) == {'id', 'type', 'x', 'y', 'cell_id'},
                   'Unexpected observation fields')
            identity, kind = observation['id'], observation['type']
            insist(isinstance(identity, str) and identity and identity not in seen, 'Duplicate or invalid (time,id) observation')
            seen.add(identity)
            insist(isinstance(kind, str) and kind in allowed_types, 'Observation type absent from frozen taxonomy')
            insist(types.setdefault(identity, kind) == kind, 'One episode changes type')
            insist(all(number(observation[k]) for k in ('x', 'y')), 'Coordinates must be finite numbers')
            insist(type(observation['cell_id']) is int
                   and observation['cell_id'] == cell_id(observation['x'], observation['y'], coverage), 'Position/leaf cell mismatch')
            traces[identity].append(dict(observed_at_ms=batch['observed_at_ms'],
                                         **{k: observation[k] for k in ('x', 'y', 'cell_id')}))
    insist(bool(traces), 'Source has no observed episodes')
    return dict(traces)


def epoch(value: Any) -> int:
    insist(isinstance(value, str), 'Missing timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    insist(parsed.tzinfo is not None, 'Timestamp requires timezone')
    insist(parsed.microsecond % 1000 == 0, 'Timestamp requires integer milliseconds')
    elapsed = parsed - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return elapsed.days * 86400000 + elapsed.seconds * 1000 + elapsed.microseconds // 1000


def agent_rows(path: Path) -> Iterator[dict]:
    """Decode only the first agents array; release/journal values remain unread."""
    decoder = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_nonfinite)
    with _open_read(path, binary=False) as stream:
        buffer = ''
        def whitespace() -> None:
            nonlocal buffer
            buffer = buffer.lstrip()
            while not buffer:
                buffer = stream.read(65536)
                insist(bool(buffer), 'Truncated capture agents array')
                buffer = buffer.lstrip()
        def token(expected: str) -> None:
            nonlocal buffer
            whitespace()
            insist(buffer.startswith(expected), 'Capture must begin with agents array')
            buffer = buffer[len(expected):]
        def value() -> Any:
            nonlocal buffer
            whitespace()
            while True:
                try:
                    row, end = decoder.raw_decode(buffer)
                    buffer = buffer[end:]
                    return row
                except json.JSONDecodeError:
                    chunk = stream.read(65536)
                    insist(bool(chunk), 'Truncated capture agent JSON')
                    buffer += chunk
                    insist(len(buffer) <= 8 * 1024 * 1024, 'Capture agent row exceeds parser bound')
        token('{')
        insist(value() == 'agents', 'Capture first member must be agents')
        token(':')
        token('[')
        whitespace()
        if buffer.startswith(']'):
            return
        while True:
            row = value()
            insist(isinstance(row, dict), 'Capture agent row must be object')
            yield row
            whitespace()
            if buffer.startswith(']'):
                return
            token(',')


def lifecycle(path: Path, replay: dict, proof: dict, traces: dict) -> dict:
    metadata, summaries, events, tracks = [], [], {}, defaultdict(dict)
    origin = proof.get('source_origin_epoch_ms')
    insist(type(origin) is int, 'Capture proof requires source origin')
    for row in agent_rows(path):
        kind = row.get('data_type')
        if kind == 'metadata':
            metadata.append(row)
        elif kind == 'mapped source summary':
            summaries.append(row)
        elif kind == 'mapped lifecycle event':
            identity, person, route = (row.get(k) for k in ('observation_track_id', 'private_person_id', 'route_id'))
            insist(all(isinstance(v, str) and v for v in (identity, person, route)), 'Missing lifecycle identity boundary')
            event = row.get('event')
            insist(event in ('visible_start', 'visible_end'), 'Unknown lifecycle event')
            at = epoch(row.get('timestamp')) - origin
            insist(0 <= at <= END_MS, 'Lifecycle event outside horizon')
            if 'at_ms' in row:
                insist(type(row['at_ms']) is int and row['at_ms'] == at, 'Lifecycle relative time/timestamp mismatch')
            processed = row.get('processed_at_ms')
            insist(type(processed) is int and at <= processed <= END_MS and processed % 50 == 0, 'Invalid lifecycle processing clock')
            episode = events.setdefault(identity, {'person': person, 'route': route})
            insist(episode['person'] == person and episode['route'] == route and event not in episode,
                   'Duplicate lifecycle event or changed person/route')
            episode[event] = at
        elif kind == 'agent data':
            identity, person = row.get('agent_id'), row.get('private_person_id')
            insist(isinstance(identity, str) and identity and row.get('observation_track_id') == identity
                   and isinstance(person, str) and person, 'Invalid raw GT identity boundary')
            at = epoch(row.get('timestamp')) - origin
            insist(0 <= at < END_MS and at % 50 == 0 and at not in tracks[identity], 'Duplicate/invalid raw GT (time,id)')
            position = row.get('position')
            insist(isinstance(position, dict) and all(number(position.get(k)) for k in ('x', 'y')), 'Invalid raw GT position')
            tracks[identity][at] = (person, row.get('type'), position['x'], position['y'])
        else:
            raise ValueError('Unexpected raw agent evidence type')
    insist(len(metadata) == len(summaries) == 1, 'One GT metadata and completed source summary required')
    meta, summary = metadata[0], summaries[0]
    insist(meta.get('observation_identity_unit') == 'visible_episode_track'
           and meta.get('ground_truth_identity_unit') == 'synthetic_person'
           and meta.get('support_contract') == 'one_episode_per_retained_history'
           and meta.get('frame_rate') == 20 and epoch(meta.get('timestamp')) == origin,
           'Raw metadata does not establish visible-episode identity/clock')
    expected = dict(completed_steps=6000, source_elapsed_ms=END_MS, planned_duration_ms=END_MS,
                    scheduled_tracks=len(events), realized_track_starts=len(events),
                    realized_track_ends=len(events), pending_tracks=0, active_tracks=0)
    insist(all(type(summary.get(k)) is int and summary[k] == v for k, v in expected.items()),
           'Raw source did not complete all scheduled episodes')
    insist(set(traces) == set(tracks) == set(events)
           and len(events) == proof['lifecycle_quality']['scheduled_episodes'], 'Observation/lifecycle/GT token sets disagree')
    people = {episode['person'] for episode in events.values()}
    insist(type(summary.get('scheduled_people')) is int and summary['scheduled_people'] == len(people)
           and proof['lifecycle_quality'].get('scheduled_people') == len(people), 'Scheduled private person counts disagree')
    insist(proof.get('gt_rows') == sum(map(len, tracks.values())), 'Raw GT count differs from capture proof')
    sensor, intervals = defaultdict(list), defaultdict(list)
    for identity, episode in events.items():
        insist('visible_start' in episode and 'visible_end' in episode
               and episode['visible_start'] < episode['visible_end'], 'Episode lacks completed visible interval')
        begin, end = episode['visible_start'], episode['visible_end']
        intervals[episode['person']].append((begin, end))
        insist(set(tracks[identity]) == set(range(((begin + 49) // 50) * 50, end, 50)),
               'Raw GT does not cover complete visible episode')
        kinds = set()
        for at, (person, kind, x, y) in tracks[identity].items():
            insist(person == episode['person'], 'Raw GT/lifecycle person mismatch')
            kinds.add(kind)
            if 0 < at < END_MS and at % PERIOD_MS == 0 and 0 <= x < 80 and 0 <= y < 80:
                sensor[at].append(dict(id=identity, type=kind, x=x, y=y, cell_id=cell_id(x, y, replay['coverage'])))
        insist(len(kinds) == 1, 'Raw GT episode changes type')
    for entries in intervals.values():
        entries.sort()
        insist(all(a[1] <= b[0] for a, b in zip(entries, entries[1:])), 'Private person has overlapping visible episodes')
    for batch in replay['batches']:
        insist(batch['observations'] == sorted(sensor[batch['observed_at_ms']], key=lambda o: o['id']),
               'Frozen observations differ from complete raw GT sensor projection')
    return events


def reference(path: Path, expected: str | None = None) -> dict:
    path = safe_path(path, root=PROJECT_ROOT)
    value = sha(path)
    insist(expected is None or value == expected, f'Frozen source hash mismatch: {path.name}')
    return {'path': str(path.relative_to(PROJECT_ROOT)), 'sha256': value}


def recheck(references: dict) -> None:
    for record in references.values():
        reference(PROJECT_ROOT / record['path'], record['sha256'])


def inspect_source(study: Path, capture: Path, contract: Path) -> dict:
    study, capture = (safe_path(p, root=PROJECT_ROOT / 'results') for p in (study, capture))
    contract = safe_path(contract, root=PROJECT_ROOT)
    summary, protocol = load(study / 'summary.json'), load(study / 'protocol.json')
    insist(summary.get('schema') == 'ump.spatial20-correction.v1' and summary.get('status') == 'verified'
           and protocol.get('schema') == 'ump.spatial20-correction-protocol.v1'
           and canonical(summary.get('protocol')) == canonical(protocol),
           'Verified corrected v2 source summary/protocol required')
    source_receipt, frozen = protocol['sources']['mixed'], protocol['pre_execution_artifacts_sha256']
    source_sha, proof_sha = source_receipt['observations_sha256'], source_receipt['capture_proof_sha256']
    insist(source_sha == EXPECTED_SOURCE_SHA256, 'Source differs from the frozen one-source development contract')
    insist(proof_sha == EXPECTED_CAPTURE_PROOF_SHA256, 'Capture proof differs from the frozen development contract')
    insist(frozen.get(POLICY_NAME) == EXPECTED_POLICY_SHA256, 'Policy differs from the frozen development contract')
    insist(frozen.get('mixed-observations.json') == source_sha
           and frozen.get('provenance/mixed-capture-proof.json') == proof_sha, 'Source/proof not frozen in protocol')
    refs = {'observations': reference(study / 'mixed-observations.json', source_sha),
            'capture_proof': reference(study / 'provenance/mixed-capture-proof.json', proof_sha),
            'source_summary': reference(study / 'summary.json'),
            'source_protocol': reference(study / 'protocol.json', summary.get('protocol_sha256')),
            'contract': reference(contract), 'tool': reference(Path(__file__))}
    for name, key in [('mixed-original-summary.json', 'summary_sha256'), ('mixed-original-bundle.json', 'bundle_sha256')]:
        refs[name] = reference(study / 'provenance' / name, source_receipt[key])
    insist(POLICY_NAME in frozen, 'Canonical frozen policy reference missing')
    refs['policy'] = reference(study / POLICY_NAME, frozen[POLICY_NAME])
    taxonomy = load(study / POLICY_NAME).get('semantic_taxonomy', {})
    allowed = {kind for node in taxonomy.get('nodes', []) for kind in node.get('input_types', [])}
    insist(bool(allowed) and all(isinstance(kind, str) and kind for kind in allowed), 'Frozen input taxonomy missing')
    proof = load(study / 'provenance/mixed-capture-proof.json')
    insist(proof.get('schema') == 'ump.mapped-recording-proof.v1' and proof.get('status') == 'verified'
           and proof.get('source_horizon_completed') is True and proof.get('all_scheduled_episodes_completed') is True,
           'Verified complete capture lifecycle proof required')
    quality, visible = proof.get('lifecycle_quality', {}), proof.get('sensor_observability', {})
    count = quality.get('scheduled_episodes')
    insist(type(count) is int and count > 0 and quality.get('status') == 'all_scheduled_episodes_completed'
           and quality.get('gt_coverage_status') == 'verified_against_recorded_visible_intervals'
           and quality.get('realized_starts') == count and quality.get('realized_ends') == count
           and quality.get('pending_episodes_at_horizon') == 0 and quality.get('active_episodes_at_horizon') == 0,
           'All scheduled episodes must complete with verified GT coverage')
    insist(visible.get('schema') == 'ump.source-sensor-episode-observability.v1' and visible.get('status') == 'pass'
           and visible.get('scheduled_tracks') == count and visible.get('sensor_observed_tracks') == count
           and visible.get('missing_track_count') == 0 and visible.get('unexpected_track_count') == 0,
           'Complete sensor episode observability required')
    refs['original_capture_proof'] = reference(capture / 'capture-proof.json', proof_sha)
    bound = proof.get('files_sha256', {})
    for name in ('observations.json', 'private/native_source.json', 'private/config.yaml', 'private/execution.json',
                 'bundle.json', 'map_background.png', 'building_access.json'):
        insist(isinstance(bound.get(name), str), 'Capture proof must bind all source/geometry evidence')
        refs['capture:' + name] = reference(capture / name, bound[name])
    bundle = load(capture / 'bundle.json')
    insist(bundle.get('identity_unit') == 'visible_episode_track' and bundle.get('observations') == 'observations.json'
           and bundle.get('sha256', {}).get('observations.json') == source_sha, 'Capture bundle episode/source identity mismatch')
    insist(bound['observations.json'] == source_sha, 'Capture/study source identity mismatch')
    source_bytes = read_bytes(study / 'mixed-observations.json')
    insist(digest(source_bytes) == source_sha and source_bytes == read_bytes(capture / 'observations.json'),
           'Study/capture observations differ or changed during read')
    replay = load(study / 'mixed-observations.json')
    traces = validate_replay(replay, allowed)
    total = sum(map(len, traces.values()))
    insist(len(traces) == count and source_receipt.get('horizon_ms') == END_MS
           and source_receipt.get('sampling_period_ms') == PERIOD_MS
           and source_receipt.get('input_observation_contributions') == total
           and proof.get('input_observation_contributions') == total
           and proof.get('measured_samples') == len(replay['batches'])
           and proof.get('measured_empty_samples') == sum(not b['observations'] for b in replay['batches']),
           'Source counts/horizon disagree with verified receipts')
    events = lifecycle(capture / 'private/native_source.json', replay, proof, traces)
    recheck(refs)
    return dict(study=study, capture=capture, references=refs, replay=replay, source_bytes=source_bytes,
                traces=traces, events=events, allowed_types=allowed, source_sha256=source_sha)


def select_target(traces: dict[str, list[dict]], source_sha: str) -> tuple[str, list[str]]:
    eligible = sorted(identity for identity, trace in traces.items() if len(trace) >= 2)
    insist(bool(eligible), 'No completed episode has at least two observations')
    target = min(eligible, key=lambda identity: (digest(canonical(['target-v1', SEED, source_sha, identity])), identity))
    return target, eligible


def auxiliary(trace: list[dict], source_sha: str, target: str) -> list[dict]:
    insist(bool(trace) and all(isinstance(point, dict) and set(point) == POINT_FIELDS for point in trace),
           'Auxiliary source points must contain coordinate/time/cell only')
    ranked = sorted(trace, key=lambda point: (digest(canonical(['aux-v1', SEED, source_sha, target, point])), canonical(point)))
    return sorted(deepcopy(ranked[:max(1, (len(trace) + 3) // 4)]), key=lambda point: point['observed_at_ms'])


def fingerprint(replay: dict) -> str:
    """ID-independent group fingerprint; renamed IDs cannot create independence."""
    paths = defaultdict(list)
    for batch in replay['batches']:
        for o in batch['observations']:
            paths[o['id']].append([batch['observed_at_ms'], o['type'], o['x'], o['y'], o['cell_id']])
    return digest(canonical(dict(coverage=replay['coverage'], sampling_period_ms=replay['sampling_period_ms'], end_ms=replay['end_ms'],
        opportunities=[{k: v for k, v in b.items() if k != 'observations'} for b in replay['batches']],
        trajectories=sorted(paths.values(), key=canonical))))


def counts(replay: dict) -> dict:
    by_type = Counter(o['type'] for b in replay['batches'] for o in b['observations'])
    return dict(observations=sum(by_type.values()), by_type=dict(sorted(by_type.items())), batches=len(replay['batches']),
                measured_empty_batches=sum(not b['observations'] for b in replay['batches']))


def make_protocol(source: dict) -> dict:
    return dict(schema=PROTOCOL_SCHEMA, purpose='P25.1 development-only matched fixture', split='development_only',
        not_train_cal_test=True, not_p25_3_independent_source_pilot=True, seed=SEED, horizon_ms=END_MS,
        sampling_period_ms=PERIOD_MS, executable_used=None, native_replay_executed=False, attack_executed=False,
        sources=source['references'], source_study=str(source['study'].relative_to(PROJECT_ROOT)),
        capture=str(source['capture'].relative_to(PROJECT_ROOT)),
        selection=dict(namespace='target-v1', key=['target-v1', SEED, '<source_observations_sha256>', '<episode_id>'],
            ordering='Sort eligible IDs; ascending SHA256(key), tie break by ID; choose first.',
            eligibility='Complete raw per-track visible_start/end and GT interval, complete global lifecycle/sensor proof, at least two sensor observations.',
            release_outcomes_used=False),
        auxiliary=dict(namespace='aux-v1', key=['aux-v1', SEED, '<source_observations_sha256>', '<episode_id>', '<point>'],
            fraction={'numerator': 1, 'denominator': 4}, rounding='ceil; minimum one',
            ordering='Ascending SHA256(key), tie break canonical point bytes; retain first ceil(n/4), then sort by time.',
            fields=sorted(POINT_FIELDS), same_for_both_labels=True, scope='full-horizon retrospective'),
        canonical_json='Python json.dumps(sort_keys=True,separators=(comma,colon),ensure_ascii=True,allow_nan=False); ASCII bytes, no newline.',
        neighbour_rule='IN original source bytes; OUT deepcopy removing exactly the selected episode ID across all 300 seconds; every other field and ordering retained.',
        public_knowledge=PUBLIC_KNOWLEDGE,
        group_rule='Every episode/label/policy variant/excerpt/ID rename of this source stays in one private development group.',
        private_scope='All fixture files, IDs, labels, full traces, groups and fingerprints remain local; never attack features.')


def make_manifest(source: dict, target: str, eligible: list[str], absent: dict, files: dict) -> dict:
    present = source['replay']
    target_types = Counter(o['type'] for b in present['batches'] for o in b['observations'] if o['id'] == target)
    return dict(schema=SCHEMA, split='development_only', labels={'in.json': 'IN', 'out.json': 'OUT'}, target_id=target,
        eligible_episode_count=len(eligible), eligible_ids_sha256=digest(canonical(eligible)),
        target_observation_count=len(source['traces'][target]), target_by_type=dict(sorted(target_types.items())),
        target_interval={k: source['events'][target][k] for k in ('visible_start', 'visible_end')},
        counts={'IN': counts(present), 'OUT': counts(absent)},
        private_source_group=dict(group_id='development-source-' + source['source_sha256'], source_sha256=source['source_sha256'],
            source_fingerprint=fingerprint(present), background_fingerprint=fingerprint(absent),
            dependency_scope='Every target/label/policy variant/excerpt/ID rename from this source shares this development group.'),
        files_sha256={name: digest(data) for name, data in files.items()})


def build_fixture(study: Path, capture: Path, contract: Path, output: Path) -> dict:
    source = inspect_source(study, capture, contract)
    protocol = make_protocol(source)
    output = new_output(output)
    write_new(output / 'protocol.json', encoded(protocol))
    # Selection/fixture serialization follows the committed protocol. Outcome
    # channels are never decoded and do not enter either seeded ranking.
    recheck(source['references'])
    target, eligible = select_target(source['traces'], source['source_sha256'])
    absent = deepcopy(source['replay'])
    for batch in absent['batches']:
        batch['observations'] = [o for o in batch['observations'] if o['id'] != target]
    trace, knowledge = source['traces'][target], auxiliary(source['traces'][target], source['source_sha256'], target)
    files = {'in.json': source['source_bytes'], 'out.json': encoded(absent), 'target-trace.json': encoded(trace),
             'auxiliary-in.json': encoded(knowledge), 'auxiliary-out.json': encoded(knowledge)}
    manifest = make_manifest(source, target, eligible, absent, files)
    manifest['protocol_sha256'] = sha(output / 'protocol.json')
    for name, data in files.items():
        write_new(output / name, data)
    write_new(output / 'private-manifest.json', encoded(manifest))
    recheck(source['references'])
    receipt = verify_fixture(output, initial=True)
    write_new(output / 'verification.json', encoded(receipt))
    return receipt


def verify_fixture(directory: Path, *, initial: bool = False) -> dict:
    directory = private_bundle(directory, initial=initial)
    protocol, manifest = load(directory / 'protocol.json'), load(directory / 'private-manifest.json')
    insist(protocol.get('schema') == PROTOCOL_SCHEMA and manifest.get('schema') == SCHEMA, 'Unexpected fixture/protocol schema')
    refs = protocol.get('sources')
    insist(isinstance(refs, dict) and 'contract' in refs, 'Missing frozen provenance references')
    recheck(refs)
    source = inspect_source(PROJECT_ROOT / protocol['source_study'], PROJECT_ROOT / protocol['capture'],
                            PROJECT_ROOT / refs['contract']['path'])
    insist(canonical(protocol) == canonical(make_protocol(source)), 'Protocol differs from frozen development contract')
    insist(sha(directory / 'protocol.json') == manifest.get('protocol_sha256'), 'Fixture protocol hash mismatch')
    present, absent = load(directory / 'in.json'), load(directory / 'out.json')
    insist(read_bytes(directory / 'in.json') == source['source_bytes'] and present == source['replay'], 'IN must preserve original source bytes/values')
    validate_replay(present, source['allowed_types'])
    validate_replay(absent, source['allowed_types'])
    target, eligible = select_target(source['traces'], source['source_sha256'])
    insist(manifest.get('target_id') == target, 'Target differs from independently reconstructed selection')
    insist(canonical({k: v for k, v in present.items() if k != 'batches'})
           == canonical({k: v for k, v in absent.items() if k != 'batches'}),
           'Pair run/sensor/geometry/cadence metadata differ')
    removed = []
    for left, right in zip(present['batches'], absent['batches']):
        insist(canonical({k: v for k, v in left.items() if k != 'observations'})
               == canonical({k: v for k, v in right.items() if k != 'observations'}),
               'Pair batch metadata/order/status differ')
        background = []
        for observation in left['observations']:
            if observation['id'] == target:
                removed.append(dict(observed_at_ms=left['observed_at_ms'], **{k: observation[k] for k in ('x', 'y', 'cell_id')}))
            else:
                background.append(observation)
        insist(right['observations'] == background and canonical(right['observations']) == canonical(background),
               'OUT changes background bytes/values/order or does not remove exactly target')
    insist(canonical(removed) == canonical(source['traces'][target])
           and canonical(load(directory / 'target-trace.json')) == canonical(removed), 'Removed trace is not complete selected episode')
    left_aux, right_aux = load(directory / 'auxiliary-in.json'), load(directory / 'auxiliary-out.json')
    insist(isinstance(left_aux, list) and all(isinstance(p, dict) and set(p) == POINT_FIELDS for p in left_aux),
           'Auxiliary points contain private/unexpected fields')
    insist(read_bytes(directory / 'auxiliary-in.json') == read_bytes(directory / 'auxiliary-out.json')
           and canonical(left_aux) == canonical(right_aux) == canonical(auxiliary(removed, source['source_sha256'], target)),
           'Auxiliary label/ranking/count/point mismatch')
    inside, outside = counts(present), counts(absent)
    target_types = Counter(o['type'] for b in present['batches'] for o in b['observations'] if o['id'] == target)
    insist(inside['observations'] == outside['observations'] + len(removed)
           and all(inside['by_type'].get(k, 0) == outside['by_type'].get(k, 0) + target_types.get(k, 0)
                   for k in set(inside['by_type']) | set(outside['by_type']) | set(target_types)), 'Count/type conservation failed')
    files = {name: read_bytes(directory / name) for name in ARTIFACTS}
    expected = make_manifest(source, target, eligible, absent, files)
    expected['protocol_sha256'] = sha(directory / 'protocol.json')
    insist(canonical(manifest) == canonical(expected), 'Private manifest/hash/group/count metadata disagree')
    recheck(refs)
    receipt = dict(schema='ump.urban-membership-fixture-verification.v1', status='verified', development_only=True,
        independent_sources=1, fixture_pairs=1, horizon_ms=END_MS, sampling_period_ms=PERIOD_MS,
        counts=manifest['counts'], removed_observations=len(removed), auxiliary_points=len(left_aux), eligible_episodes=len(eligible),
        checks=['source hashes before/after', 'complete lifecycle/sensor token proof', 'complete raw per-episode GT intervals',
                'IN source byte identity', 'exact target-only filter over every batch', 'background canonical bytes/values/order',
                'duplicate time/id and stable types', 'coordinate/leaf geometry and full cadence', 'count/type conservation',
                'outcome-independent target/aux reconstruction', 'identical coordinate/time/cell auxiliary for both labels',
                'one private dependent development source group'],
        protocol_sha256=sha(directory / 'protocol.json'), manifest_sha256=sha(directory / 'private-manifest.json'),
        native_replay_executed=False, attack_executed=False,
        scope='One private P25.1 development fixture; no TRAIN/CAL/TEST, P25.3 independent recording, empirical privacy, attack, utility or runtime result.')
    if not initial:
        insist(canonical(load(directory / 'verification.json')) == canonical(receipt), 'Stored verification receipt differs from recomputation')
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('source-study', 'capture', 'contract', 'output', 'verify'):
        parser.add_argument('--' + flag, type=Path)
    args = parser.parse_args()
    if args.verify:
        if any((args.source_study, args.capture, args.contract, args.output)):
            parser.error('--verify cannot be combined with construction arguments')
        receipt = verify_fixture(args.verify)
    else:
        if not all((args.source_study, args.capture, args.contract, args.output)):
            parser.error('construction requires --source-study, --capture, --contract and --output')
        receipt = build_fixture(args.source_study, args.capture, args.contract, args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
