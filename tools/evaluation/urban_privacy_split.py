#!/usr/bin/env python3
"""Prospective recording-group split freeze for the new P25 urban study.

This tool generates neither movement nor attack results. Eight completed source
pilot recordings are DEV evidence, excluded from every prospective primary slot.
Actual recordings and derivatives may later be checked against the frozen slots;
four episodes from one recording still count as one independent source group.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

SCHEMA = 'ump.urban-privacy-prospective-split.v1'
SPLITS = ('train', 'calibration', 'test')
WINDOWS_MS = (400, 1000, 2000, 4000)
COVERAGE = {'x': 0, 'y': 0, 'width': 80, 'height': 80, 'leaf_depth': 6}
MAX_BYTES = 2 * 1024**3
HISTORICAL_SEED = 20261024
HISTORICAL_SOURCE_SHA256 = 'c24134c724acf2df38a85b2906a2e80f8de7b420529a4b8cda3f9e5f98a3eff5'
ROLES = ('source_generation', 'target_selection', 'auxiliary_selection')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def integer(value, label, low=1, high=2**63 - 1):
    require(type(value) is int and low <= value <= high, label + ' is out of range')
    return value


def identifier(value, label='identifier'):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}', value),
            'Invalid ' + label)
    return value


def sha256(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'Expected SHA-256')
    return value


def safe_path(path, *, root=None, exists=True):
    path = Path(path).expanduser()
    require('..' not in path.parts, 'Parent traversal is forbidden')
    if not path.is_absolute():
        path = Path.cwd() / path
    require(not any(part.is_symlink() for part in (path, *path.parents)), 'Symlink path is forbidden')
    path = path.resolve(strict=exists)
    if root is not None:
        require(path.is_relative_to(safe_path(root)), 'File escapes declared root')
    return path


def read_bytes(path):
    path = safe_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
        os.close(descriptor)
        raise ValueError('Expected a bounded regular file')
    with os.fdopen(descriptor, 'rb') as stream:
        return stream.read()


def load(path):
    return json.loads(read_bytes(path), parse_constant=lambda value: (_ for _ in ()).throw(
        ValueError('Nonfinite JSON number: ' + value)))


def file_sha(path):
    return hashlib.sha256(read_bytes(path)).hexdigest()


def relative_file(root, reference):
    require(isinstance(reference, dict) and set(reference) == {'path', 'sha256'}, 'Invalid file reference')
    name = reference['path']
    require(isinstance(name, str) and name and not Path(name).is_absolute() and Path(name) != Path('.'),
            'File reference must be relative')
    sha256(reference['sha256'])
    path = safe_path(Path(root) / name, root=root)
    require(file_sha(path) == reference['sha256'], 'File provenance hash mismatch')
    return path


def _seed(study_id, master_seed, group_id, role):
    # Separate roles prevent target/auxiliary selection from reusing the motion RNG.
    return int(digest(['urban-primary-seed-v1', study_id, master_seed, group_id, role])[:15], 16) + 1


def validate_design(design):
    require(isinstance(design, dict), 'Expected a design object')
    identifier(design.get('study_id'), 'study ID')
    integer(design.get('master_seed'), 'master seed', 0)
    counts = design.get('group_counts')
    require(isinstance(counts, dict) and set(counts) == set(SPLITS), 'Declare all three grouped split counts')
    for split in SPLITS:
        integer(counts[split], split + ' groups', 1, 10000)
    require(sum(counts.values()) <= 10000, 'Too many recording groups')
    integer(design.get('targets_per_recording'), 'targets per recording', 1, 64)
    generator = design.get('generator', {})
    require(isinstance(generator, dict), 'Expected generator declaration')
    identifier(generator.get('law_id'), 'generator law ID')
    for field in ('scene_configuration_sha256', 'map_geometry_sha256'):
        sha256(generator.get(field))
    evidence_files = generator.get('evidence_files', [])
    require(isinstance(evidence_files, list), 'Generator evidence must be a list')
    for reference in evidence_files:
        require(isinstance(reference, dict) and set(reference) == {'path', 'sha256'}, 'Invalid generator evidence reference')
        require(isinstance(reference['path'], str) and reference['path'] and not Path(reference['path']).is_absolute()
                and '..' not in Path(reference['path']).parts, 'Generator evidence path must be relative')
        sha256(reference['sha256'])
    require(generator.get('end_ms') == 300000 and generator.get('population') == 128
            and generator.get('sensor_period_ms') == 100 and generator.get('gt_period_ms') == 50,
            'P25 primary uses the same 300-s, 128-person, 20-Hz GT/10-Hz sensor law')
    conditions = design.get('conditions')
    require(isinstance(conditions, list) and conditions, 'Declare policy conditions')
    names = set()
    for condition in conditions:
        identifier(condition.get('id'), 'condition ID')
        require(condition['id'] not in names, 'Duplicate condition')
        names.add(condition['id'])
        sha256(condition.get('hard_requirements_sha256'))
        ref = condition.get('policy')
        require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'Declare a frozen policy file')
        require(isinstance(ref['path'], str) and ref['path'] and not Path(ref['path']).is_absolute()
                and '..' not in Path(ref['path']).parts, 'Policy path must be relative')
        sha256(ref['sha256'])
    methods = design.get('methods')
    require(isinstance(methods, list) and methods, 'Declare the comparator family')
    names = set()
    for method in methods:
        identifier(method.get('id'), 'method ID')
        require(method['id'] not in names, 'Duplicate method')
        names.add(method['id'])
        kind = method.get('kind')
        require(kind in ('native_fixed', 'native_adaptive', 'regional_static'), 'Unknown method kind')
        if kind in ('native_fixed', 'regional_static'):
            require(method.get('grid_side_m') in (10, 20), 'Fixed grids must be predeclared 10/20 m')
        if kind == 'native_fixed':
            require(method.get('window_ms') in WINDOWS_MS, 'Unknown fixed-window baseline')
        if kind == 'native_adaptive':
            require(method.get('strategy') in ('semantic_first', 'spatial_first'), 'Unknown adaptive strategy')
        require(method.get('policy_audit_required') is True, 'Every method requires the same-condition hard-policy audit')
    for method in methods:
        if method['kind'] == 'regional_static':
            expected = {m['id'] for m in methods if m['kind'] == 'native_fixed'
                        and m['grid_side_m'] == method['grid_side_m']}
            require(len(expected) == 4 and set(method.get('components', [])) == expected,
                    'Regional static requires all four same-grid audited fixed components')
            require(method.get('selection') == 'public_policy_only', 'Regional selection must be policy-only')
    for field in ('attack_protocol', 'analysis_protocol'):
        require(isinstance(design.get(field), dict) and design[field], 'Declare ' + field)
    require(design['analysis_protocol'].get('independence_unit') == 'recording', 'Inference must respect recording dependence')
    require(design['attack_protocol'].get('availability_model') == 'final_snapshot_at_horizon', 'Declare full-horizon snapshot clock')
    limits = design.get('resource_limits', {})
    require(isinstance(limits, dict), 'Declare resource limits')
    for name in ('capture_wall_s', 'native_case_wall_s'):
        integer(limits.get(name), name, 1, 3600)
    for name in ('scene_wall_s', 'source_audit_wall_s'):
        if name in limits:
            integer(limits[name], name, 1, 3600)


def pilot_exclusions(summary):
    require(isinstance(summary, dict) and summary.get('schema') == 'ump.urban-privacy-sources.v1'
            and summary.get('status') == 'verified', 'A completed verified eight-source DEV pilot is required')
    cases = summary.get('cases')
    require(isinstance(cases, list) and len(cases) == 8, 'Expected exactly eight DEV pilot sources')
    result = []
    groups, seeds, sources, sources_v2, plans = set(), set(), set(), set(), set()
    for case in cases:
        require(case.get('status') == 'verified', 'Every DEV source must be verified')
        identifier(case.get('group_id'), 'pilot group ID')
        integer(case.get('seed'), 'pilot seed', 0)
        for field in ('observations_sha256', 'normalized_source_fingerprint', 'planned_route_fingerprint'):
            sha256(case.get(field))
        for field, seen in (('group_id', groups), ('seed', seeds), ('normalized_source_fingerprint', sources),
                            ('planned_route_fingerprint', plans)):
            require(case[field] not in seen, 'Duplicate DEV pilot ' + field)
            seen.add(case[field])
        record = {key: case[key] for key in ('group_id', 'seed', 'observations_sha256',
                                            'normalized_source_fingerprint', 'planned_route_fingerprint')}
        if 'normalized_source_fingerprint_v2' in case:
            record['normalized_source_fingerprint_v2'] = sha256(case['normalized_source_fingerprint_v2'])
            require(record['normalized_source_fingerprint_v2'] not in sources_v2,
                    'Duplicate DEV pilot numerically normalized source fingerprint')
            sources_v2.add(record['normalized_source_fingerprint_v2'])
        result.append(record)
    return result


def historical_exclusions(records):
    require(isinstance(records, list), 'Historical exclusions must be a list')
    result = [{'group_id': 'historical-20261024', 'seed': HISTORICAL_SEED,
               'observations_sha256': HISTORICAL_SOURCE_SHA256}]
    for record in records:
        require(isinstance(record, dict) and record, 'Invalid historical exclusion')
        require(set(record) <= {'group_id', 'seed', 'source', 'target_ids', 'observations_sha256',
                                'normalized_source_fingerprint', 'normalized_source_fingerprint_v2',
                                'normalized_trajectory_fingerprint', 'background_fingerprint',
                                'normalized_trajectory_fingerprints', 'background_fingerprints', 'planned_route_fingerprint'},
                'Unknown historical exclusion field')
        for key, value in record.items():
            if key == 'group_id':
                identifier(value)
            elif key == 'seed':
                integer(value, 'historical seed', 0)
            elif key == 'source':
                require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'Invalid historical source reference')
                require(isinstance(value['path'], str) and value['path'] and not Path(value['path']).is_absolute()
                        and '..' not in Path(value['path']).parts, 'Historical source path must be relative')
                sha256(value['sha256'])
            elif key == 'target_ids':
                require(isinstance(value, list) and all(isinstance(v, str) and v for v in value)
                        and len(value) == len(set(value)), 'Invalid excluded target IDs')
            elif key.endswith('_fingerprints'):
                require(isinstance(value, list), 'Expected historical fingerprint list')
                for item in value:
                    sha256(item)
            else:
                sha256(value)
        result.append(deepcopy(record))
    require(any(record.get('observations_sha256') == HISTORICAL_SOURCE_SHA256
                and record.get('source', {}).get('sha256') == HISTORICAL_SOURCE_SHA256
                and record.get('normalized_source_fingerprint')
                and record.get('normalized_source_fingerprint_v2') for record in records),
            'Authenticated historical mixed source fingerprints are required, including ID-normalized clones')
    return result


def historical_source_record(source_reference, root, *, group_id, seed, target_ids=()):
    """Compute exclusions from actual hashed historical bytes (never capture anew)."""
    source = load(relative_file(root, source_reference))
    result = {'group_id': identifier(group_id), 'seed': integer(seed, 'historical seed', 0),
              'source': deepcopy(source_reference), 'observations_sha256': source_reference['sha256'],
              'normalized_source_fingerprint': normalized_fingerprint(source, legacy=True),
              'normalized_source_fingerprint_v2': normalized_fingerprint(source),
              'target_ids': list(target_ids), 'background_fingerprints': [],
              'normalized_trajectory_fingerprints': []}
    for identity in target_ids:
        require(sum(o['id'] == identity for b in source['batches'] for o in b['observations']) >= 2,
                'Historical target must have at least two observations')
        result['background_fingerprints'].append(normalized_fingerprint(source, target_id=identity, remove_target=True))
        result['normalized_trajectory_fingerprints'].append(normalized_fingerprint(source, target_id=identity))
    return result


def budget_projection(design):
    counts = design['group_counts']
    groups = sum(counts.values())
    targets = groups * design['targets_per_recording']
    native_methods = sum(m['kind'] != 'regional_static' for m in design['methods'])
    native_cases = targets * 2 * len(design['conditions']) * native_methods
    return {'independent_recordings': groups, 'episode_pairs': targets,
            'native_cases_without_reuse': native_cases,
            'source_wall_cap_s': groups * sum(design['resource_limits'].get(name, 0)
                                             for name in ('scene_wall_s', 'capture_wall_s', 'source_audit_wall_s')),
            'native_wall_cap_s_without_reuse': native_cases * design['resource_limits']['native_case_wall_s'],
            'independent_out_unit_fpr_step': {split: 1 / counts[split] for split in ('calibration', 'test')},
            'pooled_dependent_episode_out_fpr_step': {split: 1 / (counts[split] * design['targets_per_recording'])
                                                     for split in ('calibration', 'test')},
            'interpretation': 'Exploratory bounded design; pooled episodes are dependent. No statistical-power claim. Native bound assumes no shared-IN reuse.'}


def build_manifest(design, pilot_summary, historical=()):
    validate_design(design)
    pilot = pilot_exclusions(pilot_summary)
    excluded = pilot + historical_exclusions(list(historical))
    excluded_ids = {r.get('group_id') for r in excluded}
    excluded_seeds = {r.get('seed') for r in excluded}
    count = sum(design['group_counts'].values())
    ids = [f"{design['study_id']}-g{index:05d}" for index in range(count)]
    # Assignment is committed before generation and independent of all outcomes.
    ranked = sorted(ids, key=lambda name: digest(['urban-primary-split-v1', design['master_seed'], name]))
    groups, used_seeds = [], set()
    offset = 0
    for split in SPLITS:
        for group_id in ranked[offset:offset + design['group_counts'][split]]:
            require(group_id not in excluded_ids, 'Primary source overlaps DEV/historical group')
            seeds = {role: _seed(design['study_id'], design['master_seed'], group_id, role) for role in ROLES}
            for value in seeds.values():
                require(value not in used_seeds and value not in excluded_seeds, 'Seed role or exclusion collision')
                used_seeds.add(value)
            groups.append({'group_id': group_id, 'split': split, 'seeds': seeds,
                           'source_state': 'planned_not_generated',
                           'target_slots': [f'target-{index:02d}' for index in range(design['targets_per_recording'])]})
        offset += design['group_counts'][split]
    return {'schema': SCHEMA, 'status': 'prospectively_frozen_not_generated',
            'design': deepcopy(design), 'design_sha256': digest(design),
            'pilot_role': 'development_only_excluded_from_train_calibration_test',
            'exclusions': excluded, 'groups': groups, 'budget_projection': budget_projection(design),
            'split_unit': 'complete_recording_all_targets_worlds_conditions_methods_and_excerpts',
            'test_rule': 'Do not generate or inspect TEST until this manifest and analysis protocol are frozen.',
            'actual_recordings': 0, 'attack_runs': 0}


def validate_manifest(manifest):
    require(isinstance(manifest, dict) and manifest.get('schema') == SCHEMA, 'Unknown prospective manifest')
    # Reconstruct through the same deterministic assignment while retaining only
    # exclusions not already supplied as the first eight pilot entries.
    exclusions = manifest.get('exclusions', [])
    pilot = {'schema': 'ump.urban-privacy-sources.v1', 'status': 'verified',
             'cases': [dict(record, status='verified') for record in exclusions[:8]]}
    historical = exclusions[9:]
    expected = build_manifest(manifest.get('design'), pilot, historical)
    require(canonical(manifest) == canonical(expected), 'Prospective manifest differs from its committed design/seed assignment')


def validate_derivatives(manifest, records):
    """Reject any target/world/method/policy/excerpt assigned away from its source."""
    validate_manifest(manifest)
    groups = {row['group_id']: row for row in manifest['groups']}
    conditions = {row['id']: row for row in manifest['design']['conditions']}
    methods = {row['id'] for row in manifest['design']['methods']}
    require(isinstance(records, list), 'Derivative records must be a list')
    for record in records:
        require(isinstance(record, dict), 'Invalid derivative')
        group = groups.get(record.get('source_group_id'))
        require(group is not None, 'Unknown derivative source group')
        require(record.get('group_id') == group['group_id'] and record.get('split') == group['split'],
                'All recording derivatives must remain in the recording split')
        require(record.get('target_slot') in group['target_slots'], 'Unknown target slot')
        require(record.get('world') in ('IN', 'OUT'), 'Unknown membership world')
        require(record.get('method_id') in methods, 'Unknown method')
        condition = conditions.get(record.get('condition_id'))
        require(condition is not None and record.get('hard_requirements_sha256') == condition['hard_requirements_sha256'],
                'Hard requirements must be identical within a condition')


def _normalized_number(value):
    require(type(value) in (int, float) and math.isfinite(value), 'Coordinates must be finite numbers')
    return 0 if value == 0 else int(value) if value == int(value) else value


def normalized_fingerprint(replay, *, target_id=None, remove_target=False, legacy=False):
    """ID-independent identity-linked trajectories, with numeric normalization.

    The legacy option matches privacy_dataset.normalized_fingerprint for pilot
    receipt comparison. The default also catches 1 versus 1.0 JSON disguises.
    """
    require(isinstance(replay, dict) and isinstance(replay.get('batches'), list), 'Expected observation replay')
    traces = {}
    opportunities = []
    for batch in replay['batches']:
        require(isinstance(batch, dict) and isinstance(batch.get('observations'), list), 'Invalid observation batch')
        time = integer(batch.get('observed_at_ms'), 'measurement time', 0)
        opportunities.append([batch['sequence'], time, batch['status']])
        ids = set()
        for observation in batch['observations']:
            identity = observation.get('id')
            require(isinstance(identity, str) and identity and identity not in ids, 'Invalid or duplicate observation ID')
            ids.add(identity)
            if target_id is not None and ((identity == target_id) == remove_target):
                continue
            point = [time, observation['type'], observation['x'], observation['y'], observation['cell_id']]
            if not legacy:
                point[2:4] = [_normalized_number(value) for value in point[2:4]]
                point[4] = _normalized_number(point[4])
            traces.setdefault(identity, []).append(point)
    trajectories = sorted(traces.values(), key=lambda value: json.dumps(value, separators=(',', ':')))
    if not legacy:
        opportunities = [[_normalized_number(v) if type(v) in (int, float) else v for v in row]
                         for row in opportunities]
    value = dict(coverage=replay['coverage'] if legacy else {k: _normalized_number(v) for k, v in replay['coverage'].items()},
                 end_ms=replay['end_ms'] if legacy else _normalized_number(replay['end_ms']),
                 sampling_period_ms=replay['sampling_period_ms'] if legacy else _normalized_number(replay['sampling_period_ms']),
                 opportunities=opportunities,
                 trajectories=trajectories)
    return hashlib.sha256((json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()).hexdigest() if legacy else digest(value)


def verify_actual_sources(manifest, records, root, *, require_complete=False):
    """Check later source receipts and exact OUTs without modifying the freeze.

    Records contain group_id/split/source_generation_seed, a hashed source file,
    and targets [{target_slot,target_id,out:{path,sha256}}]. This is a split and
    clone audit, not a substitute for independent lifecycle/source authentication.
    """
    validate_manifest(manifest)
    require(isinstance(records, list), 'Actual records must be a list')
    groups = {r['group_id']: r for r in manifest['groups']}
    exclusions = manifest['exclusions']
    known_sources = {r[field] for r in exclusions for field in ('observations_sha256', 'normalized_source_fingerprint',
                                                              'normalized_source_fingerprint_v2') if field in r}
    seen_groups, seen_sources, seen_backgrounds, seen_trajectories = set(), set(), set(), set()
    checked = []
    for record in records:
        group = groups.get(record.get('group_id'))
        require(group is not None and group['group_id'] not in seen_groups, 'Unknown or repeated actual recording group')
        seen_groups.add(group['group_id'])
        require(record.get('split') == group['split'] and record.get('source_generation_seed') == group['seeds']['source_generation'],
                'Actual recording differs from frozen split/source seed')
        source_path = relative_file(root, record.get('source'))
        source = load(source_path)
        generator = manifest['design']['generator']
        require(source.get('end_ms') == generator['end_ms'] and source.get('sampling_period_ms') == generator['sensor_period_ms']
                and source.get('coverage') == COVERAGE, 'Actual source map/horizon/cadence differs')
        require([batch.get('observed_at_ms') for batch in source.get('batches', [])]
                == list(range(generator['sensor_period_ms'], generator['end_ms'], generator['sensor_period_ms'])),
                'Every full-recording measurement opportunity is required; excerpts cannot be separate groups')
        require(all(batch.get('sequence') == index and batch.get('status') == 'measured'
                    for index, batch in enumerate(source['batches'], 1)), 'Measurement sequence/status differs')
        fingerprint = normalized_fingerprint(source)
        legacy = normalized_fingerprint(source, legacy=True)
        require(not ({record['source']['sha256'], fingerprint, legacy} & known_sources), 'Source overlaps DEV/historical recording')
        require(fingerprint not in seen_sources, 'Cloned source recording across groups')
        seen_sources.add(fingerprint)
        targets = record.get('targets')
        require(isinstance(targets, list) and len(targets) == len(group['target_slots']), 'Actual target count differs')
        target_slots, target_ids = set(), set()
        target_checks = []
        for target in targets:
            slot, identity = target.get('target_slot'), target.get('target_id')
            require(slot in group['target_slots'] and slot not in target_slots, 'Unknown or repeated target slot')
            require(isinstance(identity, str) and identity and identity not in target_ids, 'Invalid or repeated target ID')
            target_slots.add(slot)
            target_ids.add(identity)
            absent = load(relative_file(root, target.get('out')))
            expected = deepcopy(source)
            count = 0
            for batch in expected['batches']:
                count += sum(o['id'] == identity for o in batch['observations'])
                batch['observations'] = [o for o in batch['observations'] if o['id'] != identity]
            require(count >= 2 and canonical(expected) == canonical(absent), 'OUT must remove only the complete target contribution')
            background = normalized_fingerprint(absent)
            trajectory = normalized_fingerprint(source, target_id=identity)
            for kind, value, seen in (('background', background, seen_backgrounds), ('trajectory', trajectory, seen_trajectories)):
                # Multiple targets of this same recording may share a fingerprint;
                # only cross-recording reuse is an independence violation.
                require((value, group['group_id']) in seen or not any(v == value for v, _ in seen),
                        'Cloned ' + kind + ' across source groups')
                field = 'normalized_trajectory_fingerprint' if kind == 'trajectory' else 'background_fingerprint'
                excluded_values = {r.get(field) for r in exclusions}
                excluded_values.update(v for r in exclusions for v in r.get(field + 's', []))
                require(value not in excluded_values, 'Target/background overlaps excluded data')
                seen.add((value, group['group_id']))
            target_checks.append({'target_slot': slot, 'background_fingerprint': background,
                                  'normalized_trajectory_fingerprint': trajectory})
        checked.append({'group_id': group['group_id'], 'split': group['split'],
                        'normalized_source_fingerprint': fingerprint, 'targets': target_checks})
    if require_complete:
        require(seen_groups == set(groups), 'Actual primary sources are incomplete')
    return {'schema': 'ump.urban-privacy-split-audit.v1', 'independent_recordings_checked': len(checked),
            'primary_complete': seen_groups == set(groups), 'records': checked,
            'scope': 'split/seed/file-provenance/normalized-clone checks; lifecycle and generator-law authentication required separately'}


def write_new(path, value):
    write_bytes_new(path, encoded(value))


def write_bytes_new(path, data):
    path = safe_path(path, exists=False)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def freeze(design_path, pilot_summary_path, historical_path, output, *, evidence_root):
    design, pilot, historical = load(design_path), load(pilot_summary_path), load(historical_path)
    # Reopen all pilot source bytes. The runner remains responsible for its
    # stronger lifecycle/configuration/route audit; a verified label alone cannot
    # supply the numerical clone fingerprint used by this split freeze.
    pilot_exclusions(pilot)
    for case in pilot['cases']:
        directory = safe_path(case.get('replay_directory', ''), root=evidence_root)
        path = safe_path(directory / 'observations.json', root=evidence_root)
        require(file_sha(path) == case['observations_sha256'], 'DEV pilot observation bytes changed')
        source = load(path)
        require(normalized_fingerprint(source, legacy=True) == case['normalized_source_fingerprint'],
                'DEV pilot normalized fingerprint differs from authenticated bytes')
        case['normalized_source_fingerprint_v2'] = normalized_fingerprint(source)
        require(case.get('configuration_equivalence_sha256') == design.get('generator', {}).get('scene_configuration_sha256'),
                'Primary and DEV sources must use the same generator law')
    manifest = build_manifest(design, pilot, historical)
    for record in historical:
        require('source' in record, 'Every historical exclusion must retain its authenticated source file reference')
        expected = historical_source_record(record['source'], evidence_root, group_id=record['group_id'],
                                            seed=record['seed'], target_ids=record.get('target_ids', []))
        require(canonical(record) == canonical(expected), 'Historical source fingerprints differ from authenticated bytes')
    # Retain policy bytes locally so future verification is independent of edits
    # to the original evidence directory.
    policies = {condition['id']: read_bytes(relative_file(evidence_root, condition['policy']))
                for condition in design['conditions']}
    generator_evidence = [read_bytes(relative_file(evidence_root, reference))
                          for reference in design['generator'].get('evidence_files', [])]
    output = safe_path(output, exists=False)
    require(not output.exists(), 'Refuse to overwrite a completed or failed freeze')
    output.mkdir(mode=0o700)
    for condition_id, data in policies.items():
        write_bytes_new(output / ('policy-' + condition_id + '.json'), data)
    for index, data in enumerate(generator_evidence):
        write_bytes_new(output / f'generator-evidence-{index:02d}.bin', data)
    for name, value in (('design.json', design), ('pilot-summary.json', pilot),
                        ('historical-exclusions.json', historical), ('manifest.json', manifest)):
        write_new(output / name, value)
    names = ('design.json', 'pilot-summary.json', 'historical-exclusions.json', 'manifest.json')
    names += tuple('policy-' + condition_id + '.json' for condition_id in policies)
    names += tuple(f'generator-evidence-{index:02d}.bin' for index in range(len(generator_evidence)))
    write_new(output / 'freeze-receipt.json', {'schema': 'ump.urban-privacy-split-freeze-receipt.v1',
              'files_sha256': {name: file_sha(output / name) for name in names}})
    return verify_freeze(output)


def verify_freeze(directory):
    directory = safe_path(directory)
    require(stat.S_IMODE(directory.stat().st_mode) == 0o700, 'Freeze directory must be private 0700')
    receipt = load(directory / 'freeze-receipt.json')
    require(receipt.get('schema') == 'ump.urban-privacy-split-freeze-receipt.v1', 'Invalid freeze receipt')
    design = load(directory / 'design.json')
    validate_design(design)
    names = ('design.json', 'pilot-summary.json', 'historical-exclusions.json', 'manifest.json')
    names += tuple('policy-' + condition['id'] + '.json' for condition in design['conditions'])
    names += tuple(f'generator-evidence-{index:02d}.bin'
                   for index in range(len(design['generator'].get('evidence_files', []))))
    require(set(receipt.get('files_sha256', {})) == set(names), 'Incomplete freeze receipt')
    for name in (*names, 'freeze-receipt.json'):
        require(stat.S_IMODE(safe_path(directory / name).stat().st_mode) == 0o600, 'Freeze files must be private 0600')
        if name in names:
            require(file_sha(directory / name) == receipt['files_sha256'][name], 'Frozen file changed: ' + name)
    manifest = load(directory / 'manifest.json')
    for condition in design['conditions']:
        require(file_sha(directory / ('policy-' + condition['id'] + '.json')) == condition['policy']['sha256'],
                'Frozen policy differs from design')
    for index, reference in enumerate(design['generator'].get('evidence_files', [])):
        require(file_sha(directory / f'generator-evidence-{index:02d}.bin') == reference['sha256'],
                'Frozen generator evidence differs from design')
    expected = build_manifest(design, load(directory / 'pilot-summary.json'),
                              load(directory / 'historical-exclusions.json'))
    require(canonical(manifest) == canonical(expected), 'Frozen manifest differs from evidence/design')
    validate_manifest(manifest)
    return {'schema': 'ump.urban-privacy-split-freeze-verification.v1', 'status': 'verified',
            'manifest_sha256': file_sha(directory / 'manifest.json'),
            'planned_group_counts': manifest['design']['group_counts'],
            'actual_primary_recordings': 0, 'attack_runs': 0,
            'budget_projection': manifest['budget_projection']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--design', type=Path)
    parser.add_argument('--pilot-summary', type=Path)
    parser.add_argument('--historical-exclusions', type=Path)
    parser.add_argument('--evidence-root', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.verify:
        require(not any((args.design, args.pilot_summary, args.historical_exclusions, args.evidence_root, args.output)),
                'Verification cannot be combined with creation')
        result = verify_freeze(args.verify)
    else:
        require(all((args.design, args.pilot_summary, args.historical_exclusions, args.evidence_root, args.output)),
                'Creation requires design, pilot summary, historical exclusions, evidence root and fresh output')
        result = freeze(args.design, args.pilot_summary, args.historical_exclusions, args.output,
                        evidence_root=args.evidence_root)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
