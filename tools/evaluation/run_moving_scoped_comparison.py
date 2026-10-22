#!/usr/bin/env python3
"""Frozen same-input moving pilot: fixed grids/windows versus semantic coordination.

This is a bounded mechanism comparison, not a privacy-gain or statistical study.
Private audits and recipient query predictions are deliberately separate.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from moving_scoped_audit import audit_result
from run_moving_comparison import policy, population, scalar_audit
from scoped_semantic_queries import (MAX_CANDIDATE_CHECKS, MAX_QUERIES, MAX_RECORDS,
                                     compact, evaluate, paired_summary)

ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
PROTOCOL = 'docs/MOVING_SCOPED_COMPARISON_PROTOCOL_2026-10-22.md'
SCHEMA = 'ump.moving-scoped-comparison.v1'
SOURCE_SHA256 = 'ab4fadf254bfb5432018ff4bd305cd16d82a7475ae3d934c14c4f9af67dd5cf1'
SOURCE_FILES = ('observations.json', 'capture-proof.json', 'capture-manifest.json')
DEPENDENCIES = tuple('tools/evaluation/' + name for name in (
    'run_moving_scoped_comparison.py', 'moving_scoped_audit.py',
    'run_moving_comparison.py', 'scoped_semantic_queries.py', 'oracle.py',
    'occupancy.py', 'online_occupancy.py', 'coordination_metrics.py',
    'run_semantic_priority_study.py', 'semantic_queries.py', 'semantic_tradeoffs.py'))
SECONDARIES = ('temporal_first', 'spatial_first')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      parse_constant=lambda value: (_ for _ in ()).throw(
                          ValueError('Non-finite JSON number: ' + value)))


def write_json(path, value, *, replace=False):
    path = Path(path)
    with path.open('w' if replace else 'x', encoding='utf-8') as output:
        json.dump(value, output, sort_keys=True, separators=(',', ':'), allow_nan=False)
        output.write('\n')
    path.chmod(0o600)


def tree_hashes(directory):
    return {str(path.relative_to(directory)): digest(path)
            for path in sorted(Path(directory).rglob('*')) if path.is_file()}


def variants():
    fixed = [dict(id=f'fixed_{side:g}m_{window}ms'.replace('.', 'p'), mode='fixed',
                  coordination='common_window', secondary='temporal_first',
                  fixed_depth=depth, fixed_window_ms=window)
             for side, depth in ((2.5, 5), (5, 4), (10, 3)) for window in (400, 1000)]
    adaptive = [dict(id=f'{coord}_{secondary}', mode='semantic_first',
                     coordination=coord, secondary=secondary, fixed_depth=None,
                     fixed_window_ms=None)
                for coord in ('common_window', 'cell_local') for secondary in SECONDARIES]
    return fixed + adaptive


def config_for(variant):
    if variant not in variants():
        raise ValueError('Variant is outside the predeclared matrix')
    config = policy(10, 1000)
    config['application_id'] = 'moving-scoped-comparison'
    config['policy_tree']['id'] = 'moving-scoped-cap10m-duration400to1000ms'
    config['policy_tree']['root']['window_duration_ms']['min'] = 400
    config['policy_tree']['execution'].update(
        strategy='semantic_first', semantic_secondary_strategy=variant['secondary'],
        release_trigger='policy_satisfied')
    config['temporal_adaptation'].update(coordination=variant['coordination'], max_active_cells=4096)
    config['spatial_selection']['preserve_valid_descendants'] = variant['coordination'] == 'common_window'
    # A fixed override is also recorded in the exact config audited afterwards.
    if variant['fixed_window_ms'] is not None:
        config['window_ms'] = variant['fixed_window_ms']
    return config


def workloads(config):
    categories = sorted(node['id'] for node in config['semantic_taxonomy']['nodes'])
    if len(categories) != 10 or len(set(categories)) != 10:
        raise ValueError('Expected the declared ten-node taxonomy')
    return {f'full_area_{side}m_w{window}ms': dict(
        target_cells=[dict(cell_id=identity, depth=depth)
                      for identity in range(3 * 4**depth, 4 * 4**depth)],
        categories=categories, window_ms=window, lags_ms=[0, 200, 1000],
        matching_fixed_baseline=f'fixed_{side}m_{window}ms',
        footprint_selection='Entire declared coverage; fixed before reading any release')
        for side, depth in ((5, 4), (10, 3)) for window in (400, 1000)}


def verify_capture(capture):
    capture = Path(capture)
    manifest, proof = read_json(capture / 'capture-manifest.json'), read_json(capture / 'capture-proof.json')
    if manifest.get('status') != 'verified' or proof.get('status') != 'verified':
        raise ValueError('Require independently verified capture and proof')
    hashes = {name: digest(capture / name) for name in SOURCE_FILES}
    for name in SOURCE_FILES[:2]:
        if hashes[name] != manifest.get('artifacts_sha256', {}).get(name):
            raise ValueError('Missing or mismatched capture digest: ' + name)
    if hashes['observations.json'] != SOURCE_SHA256:
        raise ValueError('Capture differs from the predeclared n500 moving source')
    replay = read_json(capture / 'observations.json')
    if (replay.get('schema') != 'ump.observation-replay.v1'
            or replay.get('coverage') != dict(x=0, y=0, width=80, height=80, leaf_depth=6)
            or replay.get('sampling_period_ms') != 100 or replay.get('end_ms') != 20000):
        raise ValueError('Expected the declared 80m/D6/100ms/20000ms source')
    if [batch.get('observed_at_ms') for batch in replay.get('batches', [])] != list(range(100, 20000, 100)):
        raise ValueError('Expected 199 complete scheduled source frames; t0 is unsampled')
    # No source manifest/proof payload is copied: it contains local database metadata.
    return replay, dict(source_artifacts_sha256=hashes,
                        source_run_id=replay['run_id'], source_sensor_id=replay['sensor_id'])


def compact_scalar_audit(value):
    """Keep verification totals; detailed private oracle rows stay in memory."""
    return {**{key: value[key] for key in (
        'schema', 'valid', 'released_cell_count', 'no_release',
        'released_observation_contributions', 'input_observation_contributions', 'scope')},
        'violation_count': len(value['violations']),
        'checked_window_count': len(value['checked_windows'])}


def normalized_result(result):
    result = deepcopy(result)
    result.pop('runtime', None)
    return result


def validate_result_metadata(replay, config, result, variant):
    if result.get('schema') != 'ump.replay-result.v1' or result.get('mode') != variant['mode']:
        raise ValueError('Unexpected result schema/mode: ' + variant['id'])
    source, parameters = result.get('source', {}), result.get('parameters', {})
    for key in ('run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms'):
        if source.get(key) != replay.get(key):
            raise ValueError('Result source metadata mismatch: ' + key)
    if source.get('application_id') != config['application_id']:
        raise ValueError('Result application mismatch')
    if (parameters.get('coordination') != variant['coordination']
            or parameters.get('window_ms') != config['window_ms']
            or parameters.get('fixed_depth') != variant['fixed_depth']):
        raise ValueError('Result execution parameters mismatch')
    if variant['mode'] == 'semantic_first' and (
            parameters.get('semantic_secondary_strategy') != variant['secondary']
            or parameters.get('release_trigger') != 'policy_satisfied'):
        raise ValueError('Result semantic priority/release trigger mismatch')
    if variant['mode'] == 'fixed':
        window, horizon = variant['fixed_window_ms'], replay['end_ms']
        expected = [(start, min(start + window, horizon)) for start in range(0, horizon, window)]
        actual = [(row.get('start_ms'), row.get('end_ms')) for row in result.get('windows', [])]
        if actual != expected:
            raise ValueError('Fixed baseline changed its predetermined interval partition')
        for collection in ('windows', 'releases'):
            for event in result[collection]:
                interval = (event.get('start_ms'), event.get('end_ms'))
                endpoint = 'evaluated_at_ms' if collection == 'windows' else 'sealed_at_ms'
                if interval not in expected or event.get(endpoint) != interval[1]:
                    raise ValueError('Fixed baseline changed its interval or release endpoint')
                if any(cell.get('depth') != variant['fixed_depth'] for cell in event['cells']):
                    raise ValueError('Fixed baseline changed its predetermined grid depth')


def budget_preflight(replay, releases, definition):
    """Count the evaluator's indexed candidate work without generating query rows.

    These checks do not validate release truth; the independent audits do that.
    Spatial overlaps are quadtree ancestor relations, with each scheduled source
    tile counted for every intersected fixed query interval, category and lag.
    """
    window, period = definition['window_ms'], replay['sampling_period_ms']
    count = replay['end_ms'] // window
    multiplier = len(definition['categories']) * len(definition['lags_ms'])
    queries = len(definition['target_cells']) * count * multiplier
    if queries > MAX_QUERIES:
        raise ValueError('Expanded query budget exceeded in preflight')
    records = sum(len(release['cells']) for release in releases)
    if len(releases) > MAX_RECORDS or records > MAX_RECORDS:
        raise ValueError('Public record budget exceeded in preflight')
    targets = definition['target_cells']
    checks = 0
    for release in releases:
        tlo = max(1, release['start_ms'] // period)
        thi = release['end_ms'] // period
        first = tlo * period // window
        last = min(count - 1, (thi - 1) * period // window)
        occurrences = max(0, last - first + 1)
        for cell in release['cells']:
            overlaps = sum((cell['cell_id'] >> (2 * (cell['depth'] - target['depth'])) == target['cell_id'])
                           if cell['depth'] >= target['depth'] else
                           (target['cell_id'] >> (2 * (target['depth'] - cell['depth'])) == cell['cell_id'])
                           for target in targets)
            checks += overlaps * occurrences * multiplier
            if checks > MAX_CANDIDATE_CHECKS:
                raise ValueError('Public tile/query comparison budget exceeded in preflight')
    return dict(expanded_queries=queries, public_cell_records=records,
                indexed_candidate_checks=checks, query_limit=MAX_QUERIES,
                record_limit=MAX_RECORDS, candidate_check_limit=MAX_CANDIDATE_CHECKS)


def execute(command, directory, timeout, prefix=''):
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        for name, value in (('stdout', error.stdout), ('stderr', error.stderr)):
            if isinstance(value, bytes):
                value = value.decode('utf-8', errors='replace')
            (directory / (prefix + name + '.log')).write_text(value or '', encoding='utf-8')
        raise
    (directory / (prefix + 'stdout.log')).write_text(completed.stdout, encoding='utf-8')
    (directory / (prefix + 'stderr.log')).write_text(completed.stderr, encoding='utf-8')
    if completed.returncode:
        raise RuntimeError(f'Core replay failed with exit code {completed.returncode}; inspect {directory.name} logs')


def command_for(binary, source, config, result, variant):
    command = [str(binary), '--input', str(source), '--config', str(config),
               '--mode', variant['mode'], '--output', str(result)]
    if variant['fixed_depth'] is not None:
        command += ['--fixed-depth', str(variant['fixed_depth']),
                    '--fixed-window-ms', str(variant['fixed_window_ms'])]
    return command


def evaluate_workloads(replay, output, declared, matrix):
    evaluations, pairs, budgets = {}, {}, {}
    by_id = {variant['id']: variant for variant in matrix}
    for workload, definition in declared.items():
        print(json.dumps({'stage': 'queries', 'workload': workload}), flush=True)
        baseline = definition['matching_fixed_baseline']
        def one(identity):
            result = read_json(output / identity / 'result.json')
            config = config_for(by_id[identity])
            budget = budget_preflight(replay, result['releases'], definition)
            full = evaluate(replay, config, result['releases'], **{
                key: definition[key] for key in ('target_cells', 'categories', 'window_ms', 'lags_ms')})
            filename = f'queries/{identity}--{workload}.json'
            write_json(output / filename, compact(full))
            evaluations.setdefault(identity, {})[workload] = filename
            budgets.setdefault(identity, {})[workload] = budget
            return full
        def pair(a, b, left, right):
            filename = f'queries/paired--{a}--{b}--{workload}.json'
            write_json(output / filename, dict(a=a, b=b, **paired_summary(left, right)))
            pairs[f'{a}--{b}--{workload}'] = filename
        # Maximum live query banks: the matching baseline plus one common/local
        # pair. No full query rows are saved, and all other fixed banks are freed.
        matched = one(baseline)
        for variant in matrix:
            if variant['mode'] == 'fixed' and variant['id'] != baseline:
                full = one(variant['id'])
                del full
        for secondary in SECONDARIES:
            common, local = (f'{coord}_{secondary}' for coord in ('common_window', 'cell_local'))
            common_full = one(common)
            pair(baseline, common, matched, common_full)
            local_full = one(local)
            pair(baseline, local, matched, local_full)
            pair(common, local, common_full, local_full)
            del common_full, local_full
        del matched
    return evaluations, pairs, budgets


def run(capture, output, binary, timeout=300):
    capture, output, binary = (Path(value).resolve() for value in (capture, output, binary))
    if output.exists():
        raise ValueError('Refusing to replace an existing comparison directory')
    if output.is_relative_to(capture):
        raise ValueError('Output cannot be inside the frozen capture')
    if type(timeout) is not int or not 1 <= timeout <= 300:
        raise ValueError('Core timeout must be in [1,300] seconds')
    replay, provenance = verify_capture(capture)
    source_hashes = tree_hashes(capture)
    code_paths = DEPENDENCIES + (PROTOCOL,)
    code_hashes = {name: digest(ROOT / name) for name in code_paths}
    binary_hash = digest(binary)
    matrix = variants()
    declared = workloads(config_for(matrix[0]))
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    (output / 'sources').mkdir(mode=0o700)
    (output / 'queries').mkdir(mode=0o700)
    for name in DEPENDENCIES:
        shutil.copyfile(ROOT / name, output / 'sources' / Path(name).name)
    shutil.copyfile(ROOT / PROTOCOL, output / 'protocol.md')
    frozen = output / 'AggregationReplay.frozen'
    shutil.copyfile(binary, frozen)
    frozen.chmod(0o700)
    if digest(frozen) != binary_hash:
        raise ValueError('Frozen binary copy changed')
    preflight = dict(schema=SCHEMA, status='unverified', protocol=PROTOCOL,
        source_capture=str(capture), **provenance, implementation_sha256=code_hashes,
        binary_sha256=binary_hash, variants=matrix, workloads=declared,
        core_timeout_seconds=timeout, scientific_repeats=0, planned_determinism_repeats=4,
        scope='One frozen moving realization; policy compliance and exact recipient query utility only',
        private_source_manifest_copied=False, source_observations_copied=False)
    write_json(output / 'preflight-manifest.json', preflight)
    write_json(output / 'study-manifest.json', preflight)
    commands, stats, audits, repeats = {}, {}, {}, {}
    try:
        for variant in matrix:
            identity = variant['id']
            directory = output / identity
            directory.mkdir(mode=0o700)
            config = config_for(variant)
            write_json(directory / 'policy.json', config)
            command = command_for(frozen, capture / 'observations.json', directory / 'policy.json',
                                  directory / 'result.json', variant)
            commands[identity] = command
            print(json.dumps({'stage': 'core', 'variant': identity}), flush=True)
            execute(command, directory, timeout)
            result = read_json(directory / 'result.json')
            validate_result_metadata(replay, config, result, variant)
            scalar = scalar_audit(replay, config, result)
            checked = audit_result(replay, config, result)
            audits[identity] = dict(scalar=compact_scalar_audit(scalar), semantic=checked['audit'])
            del scalar
            stats[identity] = checked['stats']
            stats[identity]['core_processing_ms'] = result['runtime']['processing_ms']
            write_json(directory / 'audit.json', audits[identity])
            write_json(directory / 'stats.json', stats[identity])
            if variant['mode'] == 'semantic_first':
                repeat_command = command_for(frozen, capture / 'observations.json', directory / 'policy.json',
                                             directory / 'determinism-repeat.json', variant)
                print(json.dumps({'stage': 'determinism', 'variant': identity}), flush=True)
                execute(repeat_command, directory, timeout, 'repeat-')
                repeated = read_json(directory / 'determinism-repeat.json')
                if normalized_result(result) != normalized_result(repeated):
                    raise ValueError('Frozen replay differs beyond runtime: ' + identity)
                repeats[identity] = dict(status='verified', excluded_fields=['runtime'])
            del result
        evaluations, pairs, budgets = evaluate_workloads(replay, output, declared, matrix)
        if source_hashes != tree_hashes(capture):
            raise ValueError('Frozen source capture changed during comparison')
        if code_hashes != {name: digest(ROOT / name) for name in code_paths}:
            raise ValueError('Protocol or implementation changed during comparison')
        if digest(frozen) != binary_hash:
            raise ValueError('Frozen core binary changed during comparison')
        summary = dict(schema=SCHEMA, status='verified', population=population(replay),
            variants=stats, audits=audits, evaluations=evaluations, pairs=pairs,
            query_budget_preflight=budgets, determinism_repeats=repeats, scientific_repeats=0,
            evaluation_count=sum(len(value) for value in evaluations.values()),
            paired_comparison_count=len(pairs), source_capture_unchanged=True,
            limitations=[
                'One stochastic realization; no statistical superiority or measured privacy-gain claim.',
                'Uniform initial positions and random straight-line destinations; no map or replenishing flow.',
                'Same hard thresholds do not establish equal measured privacy.',
                'Fixed baselines use the same semantic release selector; these are not unmodified GBS outputs.',
                'Finite predeclared fixed matrix; no exhaustive best-fixed or global-optimality claim.',
                'Exact query answers require complete public support; unpublished empty space remains unknown.',
                'Semantic loss0/.5/1 is a preference scale, not a calibrated privacy measure.',
                'Logical simulation deadlines and CPU processing are distinct from live DB/network latency.',
                'Interior query cohort excludes EOF influence; boundary and censored deadlines are separate.'])
        write_json(output / 'summary.json', summary)
        manifest = dict(preflight, status='verified', commands=commands,
            determinism_repeats=repeats, evaluation_count=summary['evaluation_count'],
            paired_comparison_count=len(pairs), source_capture_unchanged=True,
            artifacts_sha256={name: value for name, value in tree_hashes(output).items()
                              if name != 'study-manifest.json'})
        write_json(output / 'study-manifest.json', manifest, replace=True)
    except Exception as error:
        write_json(output / 'study-manifest.json', dict(preflight, status='unverified',
            failure=dict(type=type(error).__name__, message=str(error)), commands=commands), replace=True)
        raise
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--binary', type=Path, default=ROOT / 'simulator/build/AggregationReplay')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    print('Verified moving scoped comparison:', run(args.capture, args.output, args.binary, args.timeout))


if __name__ == '__main__':
    main()
