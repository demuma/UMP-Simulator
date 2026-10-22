#!/usr/bin/env python3
"""Paired semantic common/local coordination checks on a fixed analytical fixture."""
from collections import defaultdict
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / 'tools/evaluation'))
from run_local_policy_replay import audit, digest, fixture, normalized, policy, summarize, write_json

PROTOCOL = 'docs/SEMANTIC_CELL_LOCAL_PROTOCOL_2026-10-22.md'
VARIANTS = tuple((f'{coord}_{scope}_{secondary}', coord, scope == 'regional', secondary)
                 for coord in ('common_window', 'cell_local')
                 for scope in ('uniform', 'regional')
                 for secondary in ('temporal_first', 'spatial_first'))


def configuration(coordination, regional, secondary):
    if coordination not in ('common_window', 'cell_local'):
        raise ValueError('Unsupported coordination mode')
    config = policy(regional, secondary)
    config['temporal_adaptation']['coordination'] = coordination
    if coordination == 'cell_local':
        # Independent owners already preserve valid descendants; the common-cut
        # selector option is deliberately incompatible with local coordination.
        config['spatial_selection']['preserve_valid_descendants'] = False
    return config


def checked_summary(data, config, result):
    checked = audit(data, config, result)
    summary = summarize(result, checked)
    # A local release list is not a single timeline. Preserve explicit scopes
    # in the full result, and report weighted ages and per-source group intervals.
    summary.pop('release_intervals_ms')
    groups = defaultdict(lambda: {'input_observations': 0, 'released_observations': 0, 'age_sum': 0,
                                 'sample_delay_sum': 0, 'intervals': set()})
    for batch in data['batches']:
        for row in batch['observations']:
            groups[row['id'].rsplit('-', 1)[0]]['input_observations'] += 1
    total_delay = width_sum = 0
    depth = data['coverage']['leaf_depth']
    for release in result['releases']:
        for cell in release['cells']:
            rows = [(batch['observed_at_ms'], row) for batch in data['batches']
                    if release['start_ms'] <= batch['observed_at_ms'] < release['end_ms']
                    for row in batch['observations']
                    if row['cell_id'] >> (2 * (depth - cell['depth'])) == cell['cell_id']]
            width_sum += len(rows) * cell['width']
            for observed, row in rows:
                delay = release['sealed_at_ms'] - observed
                total_delay += delay
                group = groups[row['id'].rsplit('-', 1)[0]]
                group['released_observations'] += 1
                group['age_sum'] += release['sealed_at_ms'] - release['start_ms']
                group['sample_delay_sum'] += delay
                group['intervals'].add((release['start_ms'], release['end_ms']))
    for group in groups.values():
        n = group['released_observations']
        group['unreleased_observations'] = group['input_observations'] - n
        age, delay = group.pop('age_sum'), group.pop('sample_delay_sum')
        group['mean_interval_start_age_ms'] = age / n if n else None
        group['mean_observation_to_release_delay_ms'] = delay / n if n else None
        group['intervals'] = sorted(map(list, group['intervals']))
    n = summary['released_observations']
    summary.update({'coordination': config['temporal_adaptation']['coordination'],
                    'unreleased_observations': summary['input_observations'] - n,
                    'mean_observation_to_release_delay_ms': total_delay / n if n else None,
                    'mean_output_cell_side_m': width_sum / n if n else None,
                    'per_source_group': dict(groups),
                    'retired_domains': len(result['windows']),
                    'independent_audit': 'verified'})
    return summary, checked


def execute(command):
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    record = {'command': command, 'returncode': completed.returncode,
              'stdout': completed.stdout, 'stderr': completed.stderr}
    if completed.returncode:
        raise RuntimeError(json.dumps(record))
    return record


def run(output, binary):
    output, binary = Path(output).resolve(), Path(binary).resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    provenance = output / 'provenance'
    provenance.mkdir()
    shutil.copy2(binary, provenance / 'AggregationReplay')
    shutil.copy2(ROOT / PROTOCOL, provenance / Path(PROTOCOL).name)
    for name in ('run_semantic_local_policy.py', 'run_local_policy_replay.py', 'make_fixture.py',
                 'run_moving_comparison.py', 'run_semantic_priority_study.py', 'oracle.py',
                 'occupancy.py', 'online_occupancy.py', 'semantic_queries.py', 'semantic_tradeoffs.py'):
        shutil.copy2(ROOT / 'tools/evaluation' / name, provenance / name)
    sources = {str(p.relative_to(ROOT)): digest(p) for directory, suffix in
               (('simulator/src', '*.cpp'), ('simulator/include', '*.hpp'),
                ('simulator/include', '*.tpp'), ('simulator/tools', '*.cpp'))
               for p in (ROOT / directory).glob(suffix)}
    write_json(provenance / 'implementation-sha256.json', sources)
    data = fixture()
    write_json(output / 'observations.json', data)
    commands = []
    for name, coord, regional, secondary in VARIANTS:
        write_json(output / f'{name}-policy.json', configuration(coord, regional, secondary))
        commands.append([str(provenance / 'AggregationReplay'), '--input', str(output / 'observations.json'),
                         '--config', str(output / f'{name}-policy.json'), '--mode', 'semantic_first',
                         '--output', str(output / f'{name}.json')])
    write_json(output / 'pre-execution-manifest.json', {
        'schema': 'ump.semantic-cell-local-preflight.v1', 'protocol': PROTOCOL,
        'artifacts_sha256': {str(p.relative_to(output)): digest(p)
                             for p in output.rglob('*') if p.is_file()}, 'commands': commands})
    summary, repeats = {}, []
    for (name, coord, regional, secondary), command in zip(VARIANTS, commands):
        write_json(output / f'{name}-execution.json', execute(command))
        result = json.loads((output / f'{name}.json').read_text())
        config = configuration(coord, regional, secondary)
        summary[name], checked = checked_summary(data, config, result)
        write_json(output / f'{name}-audit.json', checked)
        if coord == 'cell_local':
            repeat_command = command[:-1] + [str(output / f'{name}-repeat.json')]
            write_json(output / f'{name}-repeat-execution.json', execute(repeat_command))
            repeated = json.loads((output / f'{name}-repeat.json').read_text())
            checked_summary(data, config, repeated)
            if normalized(result) != normalized(repeated):
                raise ValueError('Deterministic scientific output changed: ' + name)
            repeats.append(name)
    write_json(output / 'summary.json', summary)
    write_json(output / 'study-manifest.json', {
        'schema': 'ump.semantic-cell-local-study.v1', 'status': 'verified', 'protocol': PROTOCOL,
        'source': 'Stationary analytical fixture; no realistic traffic or privacy-effectiveness claim.',
        'variant_count': len(VARIANTS), 'production_calls': len(VARIANTS) + len(repeats),
        'scientifically_equal_repeats': repeats,
        'artifacts_sha256': {str(p.relative_to(output)): digest(p)
                             for p in output.rglob('*') if p.is_file()}})
    print(json.dumps({name: {k: v for k, v in value.items() if k not in
          ('per_source_group', 'retained_by_source_group')} for name, value in summary.items()}, indent=2))
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--binary', type=Path, default=ROOT / 'simulator/build/AggregationReplay')
    args = parser.parse_args()
    run(args.output, args.binary)
