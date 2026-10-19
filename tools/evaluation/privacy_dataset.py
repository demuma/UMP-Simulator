#!/usr/bin/env python3
"""Seeded controlled contribution-membership cases, not a realistic traffic model.

The physical candidate exists in both worlds. IN includes its sampled source
contribution and OUT omits exactly that contribution. Every background observation
and sampling opportunity is frozen. Occupancy utility therefore targets the sampled
source population, not all physical people. IDs, labels, traces and this manifest are
private research data and must never be supplied as classifier features.

Prescribed horizontal modal corridors and one pedestrian corner/dwell path expose
controlled density, motion and turnover effects. There is no map importer, obstacle
model, stochastic route choice or collision-avoidance claim. Handover schedules are
analytical capture intervals, not a claim about physically entering a street.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import random
import re
from typing import Any

from make_fixture import cell_id, make_policy

SCENARIOS = ('sparse', 'dense', 'handover', 'heterogeneous')
SCHEMA = 'ump.privacy-dataset.v1'
ROBUSTNESS_SCHEMA = 'ump.privacy-dataset.v2'
DISTRIBUTIONS = ('base', 'background_density_shift')
PERIOD_MS = 100
GRID = dict(x=0, y=0, width=80, height=80, leaf_depth=6)


def _integer(value: Any, name: str, minimum: int = 0, maximum: int = 1_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer in [{minimum},{maximum}]')
    return value


def _horizon(end_ms: int) -> int:
    _integer(end_ms, 'end_ms', 1000, 60000)
    if end_ms % PERIOD_MS:
        raise ValueError('end_ms must be a multiple of 100 ms')
    return end_ms


def _seed(seed: int, *parts: str) -> int:
    _integer(seed, 'seed', 0, 2**63 - 1)
    encoded = json.dumps([seed, *parts], separators=(',', ':')).encode()
    return int.from_bytes(hashlib.sha256(encoded).digest()[:16], 'big')


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _case_name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', value):
        raise ValueError('case_id must be a safe, nonempty ASCII identifier')
    return value


def _position(path: list[tuple[float, float]], distance: float,
              dwell_distance: float, dwell_seconds: float, speed: float) -> tuple[float, float] | None:
    """Traverse a polyline with one optional pause; stop observations after its end."""
    if distance > dwell_distance:
        distance = max(dwell_distance, distance - dwell_seconds * speed)
    for first, second in zip(path, path[1:]):
        length = math.hypot(second[0] - first[0], second[1] - first[1])
        if distance <= length:
            ratio = distance / length
            return (first[0] + ratio * (second[0] - first[0]),
                    first[1] + ratio * (second[1] - first[1]))
        distance -= length
    return None


def _actor(rng: random.Random, identity: str, scenario: str, end_ms: int,
           target: bool = False, generation: int = 0, turnover_ms: int = 0) -> dict:
    # Target selection precedes all mechanism outcomes. Each scenario has uncertain
    # background population size; no constant total population is given to attackers.
    mode = rng.choices(['pedestrian', 'bicycle', 'car'], [6, 2, 2])[0] if scenario == 'heterogeneous' else 'pedestrian'
    lane = {'pedestrian': (10, 18), 'bicycle': (29, 31), 'car': (48, 52)}[mode]
    y = rng.uniform(*lane)
    speed = rng.uniform(*{'pedestrian': (0.9, 1.9), 'bicycle': (3.5, 6.0), 'car': (6.0, 10.0)}[mode])
    x = rng.uniform(4, 38)
    path = [(x, y), (76, y)]
    if mode == 'pedestrian' and scenario == 'heterogeneous' and rng.random() < 0.55:
        path = [(x, y), (45, y), (45, 23)]
    starts = 0 if target else rng.choice([0, 0, 100, 200, 300, 400])
    ends = end_ms
    if scenario == 'handover' and not target:
        starts = generation * turnover_ms + rng.choice([0, 0, 100])
        ends = min(end_ms, (generation + 1) * turnover_ms)
    # The target is present long enough to provide partial auxiliary trace knowledge.
    # Dwell and speed are realization variables, never membership-dependent draws.
    return dict(id=identity, type=mode, path=path, speed=speed, starts=starts, ends=ends,
                dwell_distance=rng.uniform(0.5, 3.0), dwell_seconds=rng.uniform(0, 0.8))


def generate_case(seed: int, scenario: str, case_id: str, end_ms: int = 4000) -> dict:
    """Return one independent frozen IN/OUT case and its private target trace."""
    _integer(seed, 'seed', 0, 2**63 - 1)
    _horizon(end_ms)
    _case_name(case_id)
    if scenario not in SCENARIOS:
        raise ValueError(f'scenario must be one of {SCENARIOS}')
    rng = random.Random(_seed(seed, scenario, case_id))
    target_id = f'{case_id}-target'
    target = _actor(rng, target_id, scenario, end_ms, target=True)
    bounds = {'sparse': (1, 6), 'dense': (25, 55), 'handover': (2, 7), 'heterogeneous': (8, 30)}
    count = rng.randint(*bounds[scenario])
    turnover_ms = rng.choice([500, 700, 900, 1100])
    generations = range(math.ceil(end_ms / turnover_ms)) if scenario == 'handover' else range(1)
    actors = []
    for generation in generations:
        generation_count = max(1, count + rng.choice([-1, 0, 1])) if scenario == 'handover' else count
        for index in range(generation_count):
            actors.append(_actor(rng, f'{case_id}-background-{generation:03d}-{index:03d}',
                                 scenario, end_ms, generation=generation, turnover_ms=turnover_ms))
    batches, trace = [], []
    for sequence, time in enumerate(range(PERIOD_MS, end_ms, PERIOD_MS), 1):
        observations = []
        for actor in [*actors, target]:
            if not actor['starts'] <= time < actor['ends']:
                continue
            position = _position(actor['path'], actor['speed'] * (time - actor['starts']) / 1000,
                                 actor['dwell_distance'], actor['dwell_seconds'], actor['speed'])
            if position is None:
                continue
            x, y = (round(coordinate, 8) for coordinate in position)
            observation = dict(id=actor['id'], type=actor['type'], cell_id=cell_id(x, y, GRID), x=x, y=y)
            observations.append(observation)
            if actor['id'] == target_id:
                trace.append(dict(observed_at_ms=time, x=x, y=y, cell_id=observation['cell_id']))
        batches.append(dict(sequence=sequence, observed_at_ms=time, status='measured', observations=observations))
    present = dict(schema='ump.observation-replay.v1', run_id=f'controlled-{case_id}',
                   sensor_id='ideal-agbs', coverage=deepcopy(GRID), sampling_period_ms=PERIOD_MS,
                   end_ms=end_ms, batches=batches)
    absent = deepcopy(present)
    for batch in absent['batches']:
        batch['observations'] = [o for o in batch['observations'] if o['id'] != target_id]
    case = dict(present=present, absent=absent, target_id=target_id,
                target_trace=trace, group_id=case_id, scenario=scenario)
    validate_case(case)
    return case



def _extend_continuous_path(actor: dict, end_ms: int) -> None:
    """Reflect along the prescribed polyline until it covers the full horizon.

    Reversing direction at the end of a leg is deliberate controlled motion. It is
    continuous in position, but has neither realistic turning dynamics nor a map,
    obstacle or collision-avoidance interpretation. The optional pause is retained.
    """
    original = list(actor['path'])
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                 for a, b in zip(original, original[1:]))
    if length <= 0:
        raise ValueError('A prescribed path must have positive length')
    required = actor['speed'] * end_ms / 1000 + 1
    path = list(original)
    covered = length
    reverse = True
    while covered < required:
        leg = list(reversed(original)) if reverse else original
        path.extend(leg[1:])
        covered += length
        reverse = not reverse
    actor['path'] = path


def generate_robustness_case(seed: int, scenario: str, case_id: str, end_ms: int = 16000,
                             distribution: str = 'base') -> dict:
    """Generate v2 long-path neighbours with an optional background-density shift.

    Candidate, population and each background actor use separate RNG streams. For
    the same seed/case, increasing the background count cannot alter the candidate
    or any existing background actor. The shift adds ceil(1.5*n) rather than n
    actors per generation; it does not change their speed, mode or route law.
    """
    _integer(seed, 'seed', 0, 2**63 - 1)
    _horizon(end_ms)
    _case_name(case_id)
    if scenario not in SCENARIOS:
        raise ValueError(f'scenario must be one of {SCENARIOS}')
    if distribution not in DISTRIBUTIONS:
        raise ValueError(f'distribution must be one of {DISTRIBUTIONS}')
    prefix = ('long-corridors-v2', scenario, case_id)
    target_id = f'{case_id}-target'
    target_rng = random.Random(_seed(seed, *prefix, 'candidate'))
    target = _actor(target_rng, target_id, scenario, end_ms, target=True)
    _extend_continuous_path(target, end_ms)
    population_rng = random.Random(_seed(seed, *prefix, 'population'))
    bounds = {'sparse': (1, 6), 'dense': (25, 55), 'handover': (2, 7), 'heterogeneous': (8, 30)}
    count = population_rng.randint(*bounds[scenario])
    turnover_ms = population_rng.choice([500, 700, 900, 1100])
    generations = range(math.ceil(end_ms / turnover_ms)) if scenario == 'handover' else range(1)
    multiplier = 1.5 if distribution == 'background_density_shift' else 1.0
    actors = []
    for generation in generations:
        base_count = max(1, count + population_rng.choice([-1, 0, 1])) if scenario == 'handover' else count
        for index in range(math.ceil(base_count * multiplier)):
            actor_rng = random.Random(_seed(seed, *prefix, 'background', str(generation), str(index)))
            actor = _actor(actor_rng, f'{case_id}-background-{generation:03d}-{index:03d}',
                           scenario, end_ms, generation=generation, turnover_ms=turnover_ms)
            _extend_continuous_path(actor, end_ms)
            actors.append(actor)
    batches, trace = [], []
    for sequence, time in enumerate(range(PERIOD_MS, end_ms, PERIOD_MS), 1):
        observations = []
        for actor in [*actors, target]:
            if not actor['starts'] <= time < actor['ends']:
                continue
            position = _position(actor['path'], actor['speed'] * (time - actor['starts']) / 1000,
                                 actor['dwell_distance'], actor['dwell_seconds'], actor['speed'])
            if position is None:
                raise ValueError('Extended path ended before its declared capture interval')
            x, y = (round(coordinate, 8) for coordinate in position)
            observation = dict(id=actor['id'], type=actor['type'], cell_id=cell_id(x, y, GRID), x=x, y=y)
            observations.append(observation)
            if actor['id'] == target_id:
                trace.append(dict(observed_at_ms=time, x=x, y=y, cell_id=observation['cell_id']))
        batches.append(dict(sequence=sequence, observed_at_ms=time, status='measured', observations=observations))
    present = dict(schema='ump.observation-replay.v1', run_id=f'controlled-v2-{case_id}',
                   sensor_id='ideal-agbs', coverage=deepcopy(GRID), sampling_period_ms=PERIOD_MS,
                   end_ms=end_ms, batches=batches)
    absent = deepcopy(present)
    for batch in absent['batches']:
        batch['observations'] = [o for o in batch['observations'] if o['id'] != target_id]
    case = dict(present=present, absent=absent, target_id=target_id, target_trace=trace,
                group_id=case_id, scenario=scenario, distribution=distribution,
                background_count_multiplier=multiplier)
    validate_case(case)
    if len(trace) != end_ms // PERIOD_MS - 1:
        raise ValueError('V2 candidates must be observed for the entire horizon')
    return case


def target_knowledge(trace: list[dict], fraction: float, seed: int) -> list[dict]:
    """Sample exact candidate positions independently of IN/OUT, without private IDs.

    Fraction is in (0,1]; ceil ensures at least one point. No zero-knowledge claim or
    coordinate-noise model is implicit. Cell ID is a public geometric derivative.
    """
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not math.isfinite(fraction) or not 0 < fraction <= 1:
        raise ValueError('fraction must be finite and in (0,1]')
    _integer(seed, 'seed', 0, 2**63 - 1)
    if not isinstance(trace, list) or not trace:
        raise ValueError('trace must contain at least one candidate observation')
    previous = 0
    for point in trace:
        if not isinstance(point, dict) or set(point) != {'observed_at_ms', 'x', 'y', 'cell_id'}:
            raise ValueError('trace points must contain only public time, position and cell_id')
        time = _integer(point['observed_at_ms'], 'observed_at_ms', 1)
        if time <= previous or time % PERIOD_MS:
            raise ValueError('trace points must be chronological on the 100-ms cadence')
        previous = time
        if any(isinstance(point[axis], bool) or not isinstance(point[axis], (int, float))
               or not math.isfinite(point[axis]) for axis in ('x', 'y')):
            raise ValueError('trace coordinates must be finite numbers')
        if point['cell_id'] != cell_id(point['x'], point['y'], GRID):
            raise ValueError('trace cell_id does not match coordinates')
    indices = sorted(random.Random(_seed(seed, 'target-knowledge')).sample(range(len(trace)), math.ceil(len(trace) * fraction)))
    return [deepcopy(trace[index]) for index in indices]



def noisy_target_knowledge(trace: list[dict], fraction: float, seed: int, *,
                           spatial_sigma_m: float = 2.0, temporal_jitter_ms: int = 200,
                           end_ms: int) -> list[dict]:
    """Perturb exactly the same sampled points used by ``target_knowledge``.

    Noise is independently seeded and label/mechanism-independent. Coordinates use
    independent zero-mean Gaussian errors; timestamp errors are integer-uniform in
    [-jitter,+jitter]. Clip to the public half-open coverage and horizon, recompute
    cell IDs, remove exact duplicate triples and sort. No sensor-cadence snapping
    occurs: auxiliary observations may have off-cadence timestamps. Clipping and
    deduplication are declared parts of this bounded synthetic knowledge model.
    """
    _horizon(end_ms)
    if (isinstance(spatial_sigma_m, bool) or not isinstance(spatial_sigma_m, (int, float))
            or not math.isfinite(spatial_sigma_m) or spatial_sigma_m < 0):
        raise ValueError('spatial_sigma_m must be finite and nonnegative')
    _integer(temporal_jitter_ms, 'temporal_jitter_ms', 0, 60000)
    selected = target_knowledge(trace, fraction, seed)
    if any(point['observed_at_ms'] >= end_ms for point in trace):
        raise ValueError('Candidate trace must lie inside the public horizon')
    rng = random.Random(_seed(seed, 'candidate-knowledge-noise-v1'))
    upper_x = math.nextafter(GRID['x'] + GRID['width'], -math.inf)
    upper_y = math.nextafter(GRID['y'] + GRID['height'], -math.inf)
    result, seen = [], set()
    for point in selected:
        x = min(upper_x, max(GRID['x'], point['x'] + rng.gauss(0, spatial_sigma_m)))
        y = min(upper_y, max(GRID['y'], point['y'] + rng.gauss(0, spatial_sigma_m)))
        time = min(end_ms - 1, max(1, point['observed_at_ms'] + rng.randint(-temporal_jitter_ms, temporal_jitter_ms)))
        triple = (time, x, y)
        if triple in seen:
            continue
        seen.add(triple)
        result.append(dict(observed_at_ms=time, x=x, y=y, cell_id=cell_id(x, y, GRID)))
    return sorted(result, key=lambda point: (point['observed_at_ms'], point['x'], point['y']))


def validate_case(case: dict) -> None:
    """Check exact add/remove neighbours and their coordinate/cadence contract."""
    present, absent, target = case['present'], case['absent'], case['target_id']
    if present.get('schema') != 'ump.observation-replay.v1':
        raise ValueError('Expected the observation replay schema')
    if not isinstance(target, str) or not target:
        raise ValueError('Target identity must be a nonempty string')
    if {k: v for k, v in present.items() if k != 'batches'} != {k: v for k, v in absent.items() if k != 'batches'}:
        raise ValueError('Pair metadata differ')
    if present['coverage'] != GRID or present['sampling_period_ms'] != PERIOD_MS:
        raise ValueError('Unexpected controlled coverage or cadence')
    _horizon(present['end_ms'])
    expected_times = list(range(PERIOD_MS, present['end_ms'], PERIOD_MS))
    if len(present['batches']) != len(expected_times) or len(absent['batches']) != len(expected_times):
        raise ValueError('Every sampling opportunity must be preserved')
    trace = []
    for sequence, (time, left, right) in enumerate(zip(expected_times, present['batches'], absent['batches']), 1):
        metadata = dict(sequence=sequence, observed_at_ms=time, status='measured')
        if {k: v for k, v in left.items() if k != 'observations'} != metadata or {k: v for k, v in right.items() if k != 'observations'} != metadata:
            raise ValueError('Pair batch metadata or cadence differ')
        ids = set()
        for observation in left['observations']:
            if set(observation) != {'id', 'type', 'cell_id', 'x', 'y'}:
                raise ValueError('Unexpected observation fields')
            if not isinstance(observation['id'], str) or not observation['id']:
                raise ValueError('Road-user identity must be a nonempty string')
            if observation['type'] not in ('pedestrian', 'bicycle', 'car'):
                raise ValueError('Unexpected prescribed movement mode')
            _integer(observation['cell_id'], 'cell_id', 1)
            if any(isinstance(observation[axis], bool) or not isinstance(observation[axis], (int, float))
                   or not math.isfinite(observation[axis]) for axis in ('x', 'y')):
                raise ValueError('Observation coordinates must be finite numbers')
            if observation['id'] in ids:
                raise ValueError('Duplicate road-user identity within a sample')
            ids.add(observation['id'])
            if observation['cell_id'] != cell_id(observation['x'], observation['y'], GRID):
                raise ValueError('Observation cell ID does not match coordinates')
            if observation['id'] == target:
                trace.append(dict(observed_at_ms=time, x=observation['x'], y=observation['y'], cell_id=observation['cell_id']))
        if right['observations'] != [o for o in left['observations'] if o['id'] != target]:
            raise ValueError('OUT must remove only the target and preserve background ordering')
    if not trace or trace != case['target_trace']:
        raise ValueError('Target trace differs or is empty')
    target_knowledge(trace, 1.0, 0)


def normalized_fingerprint(replay: dict) -> str:
    """Detect ID-renamed/cloned realizations, retaining identity-linked trajectories."""
    traces = {}
    for batch in replay['batches']:
        for o in batch['observations']:
            traces.setdefault(o['id'], []).append([batch['observed_at_ms'], o['type'], o['x'], o['y'], o['cell_id']])
    trajectories = sorted(traces.values(), key=lambda value: json.dumps(value, separators=(',', ':')))
    return _digest(dict(coverage=replay['coverage'], end_ms=replay['end_ms'],
                        sampling_period_ms=replay['sampling_period_ms'],
                        opportunities=[[b['sequence'], b['observed_at_ms'], b['status']] for b in replay['batches']],
                        trajectories=trajectories))


def _safe_relative(directory: Path, name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or path == Path('.'):
        raise ValueError('Manifest file paths must be relative and stay inside the dataset')
    destination = directory / path
    if not destination.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Manifest file path escapes the dataset')
    return destination


def validate_dataset(manifest: dict, directory: Path) -> None:
    """Verify provenance, exact pairs, disjoint groups and normalized clone leakage."""
    if manifest.get('schema') not in (SCHEMA, ROBUSTNESS_SCHEMA) or not isinstance(manifest.get('cases'), list) or not manifest['cases']:
        raise ValueError('Expected a nonempty controlled dataset manifest')
    directory = Path(directory)
    counts = manifest.get('group_counts')
    if not isinstance(counts, dict) or set(counts) != {'train', 'calibration', 'test'}:
        raise ValueError('Manifest must declare all grouped split counts')
    for split, count in counts.items():
        _integer(count, f'{split}_groups', 1, 10000)
        if sum(record.get('split') == split for record in manifest['cases']) != count:
            raise ValueError('Manifest grouped split counts do not match cases')
    robustness = manifest['schema'] == ROBUSTNESS_SCHEMA
    if robustness:
        if manifest.get('generator') != 'long_corridors_v2':
            raise ValueError('V2 requires the declared long-corridor generator')
        _horizon(manifest.get('end_ms'))
        cohorts = manifest.get('test_cohort_group_counts')
        if not isinstance(cohorts, dict) or set(cohorts) != set(DISTRIBUTIONS):
            raise ValueError('V2 must declare base and shifted test cohort counts')
        for distribution, count in cohorts.items():
            _integer(count, f'{distribution}_test_groups', 1, 10000)
            if sum(r.get('split') == 'test' and r.get('distribution') == distribution
                   for r in manifest['cases']) != count:
                raise ValueError('V2 test cohort counts do not match cases')
        if sum(cohorts.values()) != counts['test']:
            raise ValueError('V2 test cohorts must partition the test split')
    seen_groups, seen_cases, fingerprints = set(), set(), set()
    for record in manifest['cases']:
        if robustness:
            distribution = record.get('distribution')
            if distribution not in DISTRIBUTIONS:
                raise ValueError('Unknown v2 distribution')
            if record.get('split') != 'test' and distribution != 'base':
                raise ValueError('Shifted groups are allowed only in the held-out test split')
            expected_multiplier = 1.5 if distribution == 'background_density_shift' else 1.0
            if record.get('background_count_multiplier') != expected_multiplier:
                raise ValueError('V2 background-density intervention does not match its cohort')
        if record['scenario'] not in SCENARIOS:
            raise ValueError('Unknown controlled scenario')
        _case_name(record['case_id'])
        _case_name(record['group_id'])
        if record['split'] not in ('train', 'calibration', 'test'):
            raise ValueError('Unknown split')
        if record['group_id'] in seen_groups or record['case_id'] in seen_cases:
            raise ValueError('A source realization/group is reused across cases or splits')
        seen_groups.add(record['group_id'])
        seen_cases.add(record['case_id'])
        loaded = {}
        for field in ('present_input', 'absent_input', 'target_trace'):
            data = _safe_relative(directory, record[field]).read_bytes()
            if hashlib.sha256(data).hexdigest() != record['sha256'][field]:
                raise ValueError(f'Input provenance hash mismatch: {field}')
            loaded[field] = json.loads(data)
        case = dict(present=loaded['present_input'], absent=loaded['absent_input'], target_trace=loaded['target_trace'],
                    target_id=record['target_id'], group_id=record['group_id'], scenario=record['scenario'])
        validate_case(case)
        if robustness and (case['present']['end_ms'] != manifest['end_ms']
                           or len(case['target_trace']) != manifest['end_ms'] // PERIOD_MS - 1):
            raise ValueError('V2 candidate trace must cover every declared sampling opportunity')
        background = normalized_fingerprint(case['absent'])
        pair = _digest([normalized_fingerprint(case['present']), background])
        if background != record['background_fingerprint'] or pair != record['pair_fingerprint']:
            raise ValueError('Normalized provenance fingerprint mismatch')
        # Empty backgrounds are also rejected if cloned; random IDs cannot make
        # identical empty or nonempty data independent experimental realizations.
        for kind, value in [('background', background), ('pair', pair)]:
            if (kind, value) in fingerprints:
                raise ValueError(f'Cloned {kind} realization detected across groups')
            fingerprints.add((kind, value))
    policy = _safe_relative(directory, manifest['policy']).read_bytes()
    if hashlib.sha256(policy).hexdigest() != manifest['policy_sha256']:
        raise ValueError('Policy provenance hash mismatch')
    if robustness:
        if manifest.get('coverage') != GRID or manifest.get('sampling_period_ms') != PERIOD_MS:
            raise ValueError('V2 metadata must describe the controlled grid and cadence')
        protocol_data = _safe_relative(directory, manifest['generation_protocol']).read_bytes()
        if hashlib.sha256(protocol_data).hexdigest() != manifest['generation_protocol_sha256']:
            raise ValueError('Generation protocol provenance hash mismatch')
        protocol = json.loads(protocol_data)
        expected_phases = [dict(split='train', distribution='base', groups=counts['train']),
                           dict(split='calibration', distribution='base', groups=counts['calibration']),
                           dict(split='test', distribution='base', groups=cohorts['base']),
                           dict(split='test', distribution='background_density_shift',
                                groups=cohorts['background_density_shift'])]
        if (protocol.get('schema') != 'ump.privacy-generation-protocol.v2'
                or protocol.get('generator') != manifest['generator']
                or protocol.get('seed') != manifest.get('seed')
                or protocol.get('end_ms') != manifest['end_ms']
                or protocol.get('sampling_period_ms') != PERIOD_MS
                or protocol.get('phases') != expected_phases):
            raise ValueError('Generation protocol does not match the v2 manifest')


def build_dataset(output: Path, seed: int, train_groups: int = 12, calibration_groups: int = 8,
                  test_groups: int = 12, end_ms: int = 4000, support_threshold: int = 3) -> dict:
    """Write a new private bundle after validating parameters and generated pairs.

    Groups are independent realizations, each with one candidate and both labels.
    Cases cycle four predeclared scenarios inside each split. The deterministic seed
    is for reproducibility, not a claim that pseudorandom realizations are real data.
    Existing paths are never reused. The returned manifest is also manifest.json.
    """
    _integer(seed, 'seed', 0, 2**63 - 1)
    _horizon(end_ms)
    counts = dict(train=train_groups, calibration=calibration_groups, test=test_groups)
    for split, count in counts.items():
        _integer(count, f'{split}_groups', 1, 10000)
    if sum(counts.values()) > 10000:
        raise ValueError('At most 10000 independent groups are supported')
    _integer(support_threshold, 'support_threshold', 1, 1000)
    output = Path(output).expanduser()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Output path already exists: {output}')
    output = output.resolve()
    # Validate all generated data and clone checks before creating output files.
    generated, records, seen_background, seen_pair = [], [], set(), set()
    for split, count in counts.items():
        for index in range(count):
            case_id = f'{split}-{index:05d}'
            scenario = SCENARIOS[index % len(SCENARIOS)]
            case = generate_case(_seed(seed, 'group', split, str(index)) % 2**63, scenario, case_id, end_ms)
            background = normalized_fingerprint(case['absent'])
            pair = _digest([normalized_fingerprint(case['present']), background])
            if background in seen_background or pair in seen_pair:
                raise ValueError('Generated cloned realization; choose a different dataset seed')
            seen_background.add(background)
            seen_pair.add(pair)
            generated.append(case)
            records.append(dict(case_id=case_id, group_id=case['group_id'], split=split, scenario=scenario,
                target_id=case['target_id'], present_input=f'cases/{case_id}/present.json',
                absent_input=f'cases/{case_id}/absent.json', target_trace=f'cases/{case_id}/target-trace.json',
                background_fingerprint=background, pair_fingerprint=pair,
                sha256={field: _digest(case[source]) for field, source in
                        [('present_input', 'present'), ('absent_input', 'absent'), ('target_trace', 'target_trace')]}))
    policy = make_policy()
    policy['policy_tree']['id'] = 'controlled-membership-policy'
    policy['policy_tree']['root']['distinct_contributors']['min'] = support_threshold
    policy['policy_regions'][0]['type_requirements']['distinct_contributors']['min'] = support_threshold
    policy['policy_regions'][0]['requirements']['distinct_contributors']['min'] = support_threshold
    manifest = dict(schema=SCHEMA, classification='private_research_bundle', generator='prescribed_corridors_v1',
        seed=seed, end_ms=end_ms, sampling_period_ms=PERIOD_MS, coverage=deepcopy(GRID), group_counts=counts,
        support_threshold=support_threshold, policy='policy.json', policy_sha256=_digest(policy),
        membership_secret='whole_horizon_source_contribution_inclusion',
        utility_reference='sampled_source_population_not_full_physical_population',
        target_selection='one candidate generated before observing any mechanism output',
        split_unit='independent_source_realization_with_both_labels_and_all_mechanisms',
        background_population='uncertain_and_not_supplied_as_an_attacker_feature',
        target_knowledge='exact sampled time/coordinates; fraction is separately predeclared by benchmark',
        scenario_scope='controlled prescribed paths and capture schedules; no real-world mobility claim', cases=records)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for case, record in zip(generated, records):
        case_directory = output / 'cases' / record['case_id']
        case_directory.mkdir(parents=True, mode=0o700)
        for field, source in [('present_input', 'present'), ('absent_input', 'absent'), ('target_trace', 'target_trace')]:
            with _safe_relative(output, record[field]).open('xb') as stream:
                stream.write(_json_bytes(case[source]))
    for name, value in [('policy.json', policy), ('manifest.json', manifest)]:
        with (output / name).open('xb') as stream:
            stream.write(_json_bytes(value))
    validate_dataset(manifest, output)
    return manifest



def build_robustness_dataset(output: Path, seed: int = 20261021, train_groups: int = 48,
                             calibration_groups: int = 32, test_groups: int = 64,
                             shifted_test_groups: int = 64, end_ms: int = 16000,
                             support_threshold: int = 3) -> dict:
    """Create a new v2 private bundle; shifted groups are held out from fitting.

    Only one generated IN/OUT pair is retained in memory at a time. Parameters are
    checked before exclusive directory creation. A generation protocol precedes
    samples; manifest.json is written only after every pair has been generated and
    hash/clone checked. Unexpected failure preserves incomplete evidence rather
    than overwriting or presenting a partial directory as a complete dataset.
    """
    _integer(seed, 'seed', 0, 2**63 - 1)
    _horizon(end_ms)
    phases = [('train', 'base', train_groups), ('calibration', 'base', calibration_groups),
              ('test', 'base', test_groups), ('test', 'background_density_shift', shifted_test_groups)]
    for split, distribution, count in phases:
        _integer(count, f'{split}_{distribution}_groups', 1, 10000)
    if sum(count for _, _, count in phases) > 10000:
        raise ValueError('At most 10000 independent groups are supported')
    _integer(support_threshold, 'support_threshold', 1, 1000)
    output = Path(output).expanduser()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Output path already exists: {output}')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    protocol = dict(schema='ump.privacy-generation-protocol.v2', generator='long_corridors_v2',
        seed=seed, end_ms=end_ms, sampling_period_ms=PERIOD_MS, phases=[dict(split=s, distribution=d, groups=n)
            for s, d, n in phases],
        background_shift='ceil(1.5 * base generation population); all other actor laws unchanged',
        candidate='Separate RNG; full-horizon continuous prescribed path in both physical worlds',
        paths='Continuous reversing legs, without realistic turning dynamics, maps or collision avoidance',
        split_unit='Independent realization with both membership worlds and all mechanisms')
    (output / 'generation-protocol.json').write_bytes(_json_bytes(protocol))
    records, seen_background, seen_pair = [], set(), set()
    for split, distribution, count in phases:
        for index in range(count):
            case_id = f'test-shift-{index:05d}' if distribution != 'base' else f'{split}-{index:05d}'
            scenario = SCENARIOS[index % len(SCENARIOS)]
            generation_seed = _seed(seed, 'v2-group', split, distribution, str(index)) % 2**63
            case = generate_robustness_case(generation_seed, scenario, case_id, end_ms, distribution)
            background = normalized_fingerprint(case['absent'])
            pair = _digest([normalized_fingerprint(case['present']), background])
            if background in seen_background or pair in seen_pair:
                raise ValueError('Generated cloned realization; choose a different dataset seed')
            seen_background.add(background)
            seen_pair.add(pair)
            record = dict(case_id=case_id, group_id=case['group_id'], split=split, scenario=scenario,
                distribution=distribution, background_count_multiplier=case['background_count_multiplier'],
                generation_seed=generation_seed, target_id=case['target_id'],
                present_input=f'cases/{case_id}/present.json', absent_input=f'cases/{case_id}/absent.json',
                target_trace=f'cases/{case_id}/target-trace.json', background_fingerprint=background,
                pair_fingerprint=pair, sha256={field: _digest(case[source]) for field, source in
                    [('present_input', 'present'), ('absent_input', 'absent'), ('target_trace', 'target_trace')]})
            (output / 'cases' / case_id).mkdir(parents=True, mode=0o700)
            for field, source in [('present_input', 'present'), ('absent_input', 'absent'), ('target_trace', 'target_trace')]:
                with _safe_relative(output, record[field]).open('xb') as stream:
                    stream.write(_json_bytes(case[source]))
            records.append(record)
    policy = make_policy()
    policy['policy_tree']['id'] = 'controlled-long-membership-policy'
    policy['policy_tree']['root']['distinct_contributors']['min'] = support_threshold
    policy['policy_regions'][0]['type_requirements']['distinct_contributors']['min'] = support_threshold
    policy['policy_regions'][0]['requirements']['distinct_contributors']['min'] = support_threshold
    manifest = dict(schema=ROBUSTNESS_SCHEMA, classification='private_research_bundle',
        generator='long_corridors_v2', seed=seed, end_ms=end_ms, sampling_period_ms=PERIOD_MS,
        coverage=deepcopy(GRID), group_counts=dict(train=train_groups, calibration=calibration_groups,
            test=test_groups + shifted_test_groups),
        test_cohort_group_counts=dict(base=test_groups, background_density_shift=shifted_test_groups),
        support_threshold=support_threshold, policy='policy.json', policy_sha256=_digest(policy),
        generation_protocol='generation-protocol.json', generation_protocol_sha256=_digest(protocol),
        membership_secret='whole_horizon_source_contribution_inclusion',
        utility_reference='sampled_source_population_not_full_physical_population',
        target_selection='Separate pre-output candidate RNG; no membership-dependent actor draws',
        split_unit='independent_source_realization_with_both_labels_and_all_mechanisms',
        background_population='uncertain_and_not_supplied_as_an_attacker_feature',
        target_knowledge='Exact/noisy sampled coordinates/times separately predeclared by benchmark',
        scenario_scope='Controlled long paths with ideal reversing legs; no maps or realistic turn dynamics',
        cases=records)
    (output / 'policy.json').write_bytes(_json_bytes(policy))
    validate_dataset(manifest, output)
    (output / 'manifest.json').write_bytes(_json_bytes(manifest))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New private dataset directory')
    parser.add_argument('--seed', required=True, type=int)
    parser.add_argument('--train-groups', default=None, type=int)
    parser.add_argument('--calibration-groups', default=None, type=int)
    parser.add_argument('--test-groups', default=None, type=int)
    parser.add_argument('--end-ms', default=None, type=int)
    parser.add_argument('--support-threshold', default=3, type=int)
    parser.add_argument('--robustness', action='store_true', help='V2 long paths and a separate held-out density-shift cohort')
    parser.add_argument('--shifted-test-groups', type=int, default=None, help='V2-only shifted test groups (default: 64)')
    args = parser.parse_args()
    try:
        if args.robustness:
            manifest = build_robustness_dataset(args.output, args.seed,
                48 if args.train_groups is None else args.train_groups,
                32 if args.calibration_groups is None else args.calibration_groups,
                64 if args.test_groups is None else args.test_groups,
                64 if args.shifted_test_groups is None else args.shifted_test_groups,
                16000 if args.end_ms is None else args.end_ms, args.support_threshold)
        else:
            if args.shifted_test_groups is not None:
                raise ValueError('--shifted-test-groups requires --robustness')
            manifest = build_dataset(args.output, args.seed,
                12 if args.train_groups is None else args.train_groups,
                8 if args.calibration_groups is None else args.calibration_groups,
                12 if args.test_groups is None else args.test_groups,
                4000 if args.end_ms is None else args.end_ms, args.support_threshold)
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(f"Created {len(manifest['cases'])} independent paired cases: {args.output}")


if __name__ == '__main__':
    main()
