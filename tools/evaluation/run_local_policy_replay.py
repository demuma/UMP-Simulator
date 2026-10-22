#!/usr/bin/env python3
"""Four bounded local-leaf policy replays; scripted mechanism fixture, no MongoDB."""
from collections import Counter
from copy import deepcopy
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / 'tools/evaluation'))
from make_fixture import cell_id
from oracle import decode_cell, validate_result
from run_moving_comparison import policy as moving_policy
from run_semantic_priority_study import scalar_projection

PROTOCOL = 'docs/LOCAL_LEAF_POLICY_PROTOCOL_2026-10-22.md'
VARIANTS = (('uniform_temporal', False, 'temporal_first'),
            ('local_temporal', True, 'temporal_first'),
            ('uniform_spatial', False, 'spatial_first'),
            ('local_spatial', True, 'spatial_first'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')


def fixture():
    grid = {'x': 0, 'y': 0, 'width': 80, 'height': 80, 'leaf_depth': 6}
    groups = (
        ('control-west', 'Adult Pedestrian', 4, 2.8, 2.8),
        ('semantic-adult', 'Adult Pedestrian', 2, 10.3, 10.3),
        ('semantic-child', 'Child Pedestrian', 2, 10.3, 10.3),
        ('spatial-adult', 'Adult Cyclist', 2, 20.3, 10.3),
        ('spatial-senior', 'Senior Cyclist', 2, 21.6, 10.3),
        ('infeasible-scooter', 'Adult E-Scooter Driver', 3, 30.3, 10.3),
        ('guard-east', 'Adult Cyclist', 1, 42.8, 10.3),
        ('guard-south', 'Adult Cyclist', 1, 40.3, 12.8),
        ('control-east', 'Adult Pedestrian', 3, 50.3, 10.3))
    batches = []
    for time in range(100, 2000, 100):
        rows = []
        for name, kind, count, cx, cy in groups:
            for index in range(count):
                # Bounded offsets preserve the declared leaf and vary coordinates.
                x = cx + index * .055 + .025 * math.sin(time / 500 + index)
                y = cy + index * .04 + .025 * math.cos(time / 500 + index)
                rows.append({'id': f'{name}-{index}', 'type': kind, 'x': x, 'y': y,
                             'cell_id': cell_id(x, y, grid)})
        batches.append({'sequence': time // 100, 'observed_at_ms': time,
                        'status': 'measured', 'observations': rows})
    return {'schema': 'ump.observation-replay.v1', 'run_id': 'local-leaf-policy-contract-v1',
            'sensor_id': 'scripted-ideal-agbs', 'coverage': grid,
            'sampling_period_ms': 100, 'end_ms': 2000, 'batches': batches}


def regions():
    definitions = (
        ('semantic-patch', 10, {'min_category_distinct_contributors': {'min': 3},
                              'semantic_max_loss': {'max': .5}}),
        ('spatial-patch', 20, {'min_category_distinct_contributors': {'min': 4},
                             'semantic_max_loss': {'max': .5}}),
        ('infeasible-patch', 30, {'min_category_distinct_contributors': {'min': 4},
                                'semantic_max_loss': {'max': .5}}),
        ('empty-guard-patch', 40, {'min_category_distinct_contributors': {'min': 5},
                                 'cell_side_m': {'max': 1.25},
                                 'window_duration_ms': {'max': 600},
                                 'age_at_evaluation_ms': {'max': 600}}))
    return [{'id': name, 'type': name, 'x': x, 'y': 10, 'width': 2.5, 'height': 2.5,
             'requirements': bounds} for name, x, bounds in definitions]


def policy(local, secondary):
    if type(local) is not bool or secondary not in ('temporal_first', 'spatial_first'):
        raise ValueError('Expected boolean local flag and declared secondary strategy')
    config = moving_policy(5, 1000)
    config['application_id'] = 'local-leaf-policy-contract'
    config['policy_tree']['id'] = 'local-leaf-policy' if local else 'uniform-leaf-policy'
    config['policy_tree']['root']['min_category_distinct_contributors']['min'] = 2
    config['policy_tree']['execution'] = {
        'publication_model': 'private_final_snapshot', 'strategy': 'semantic_first',
        'semantic_secondary_strategy': secondary, 'release_trigger': 'policy_satisfied'}
    config['policy_regions'] = regions() if local else []
    config['policy_tree']['regions'] = [r['id'] for r in config['policy_regions']]
    return config


def intersects(a, b):
    """Strict positive-area overlap; boundary contact cannot import a policy."""
    return (a['x'] < b['x'] + b['width'] and b['x'] < a['x'] + a['width']
            and a['y'] < b['y'] + b['height'] and b['y'] < a['y'] + a['height'])


def effective(config, cell):
    """Independent geometry-based strongest-bound resolver, never C++ policy IDs."""
    bounds = deepcopy(config['policy_tree']['root'])
    touched = []
    for region in config['policy_regions']:
        if not intersects(cell, region):
            continue
        touched.append(region['id'])
        for requirements in (region.get('type_requirements', {}), region.get('requirements', {})):
            for metric, additions in requirements.items():
                target = bounds.setdefault(metric, {})
                if 'min' in additions:
                    target['min'] = max(target.get('min', -math.inf), additions['min'])
                if 'max' in additions:
                    target['max'] = min(target.get('max', math.inf), additions['max'])
    return bounds, touched


def audit(data, config, actual):
    scalar_config, scalar_result = scalar_projection(config, actual)
    scalar_config['policy_tree']['execution']['strategy'] = 'temporal_first'
    scalar_result['mode'] = 'temporal_first'
    for window in scalar_result['windows']:
        window['strategy'] = 'temporal_first'
    scalar = validate_result(data, scalar_config, scalar_result, max_cells=100000)
    if not scalar['valid']:
        raise ValueError('Independent scalar/retirement audit failed: ' + repr(scalar['violations'][:4]))
    nodes = {node['id']: node for node in config['semantic_taxonomy']['nodes']}
    labels = {label: node['id'] for node in nodes.values() for label in node.get('input_types', [])}
    def chain(category):
        result = []
        while category:
            result.append(category)
            category = nodes[category].get('parent')
        return result
    chains = {category: chain(category) for category in nodes}
    bins_count = cells_count = 0
    groups = Counter()
    records = []
    for release in actual['releases']:
        for cell in release['cells']:
            geometry = decode_cell(data['coverage'], cell['cell_id'], cell['depth'])
            if any(not math.isclose(cell[k], v, abs_tol=1e-12) for k, v in geometry.items()):
                raise ValueError('Geometry disagrees with cell ID')
            source = [r for batch in data['batches']
                      if release['start_ms'] <= batch['observed_at_ms'] < release['end_ms']
                      for r in batch['observations']
                      if r['cell_id'] >> (2 * (data['coverage']['leaf_depth'] - cell['depth'])) == cell['cell_id']]
            semantic = cell['semantic']
            if semantic.get('schema') != 'ump.semantic-release.v1':
                raise ValueError('Wrong semantic release schema')
            if (semantic['taxonomy_id'], semantic['taxonomy_version']) != (
                    config['semantic_taxonomy']['id'], config['semantic_taxonomy']['version']):
                raise ValueError('Wrong semantic catalog')
            selected = [item['category_id'] for item in semantic['categories']]
            if not selected or len(selected) != len(set(selected)) or any(c not in nodes for c in selected):
                raise ValueError('Invalid selected semantic categories')
            if any(a != b and a in chains[b] for a in selected for b in selected):
                raise ValueError('Semantic antichain overlaps')
            if any(sum(c in chains[labels[r['type']]] for c in selected) != 1 for r in source):
                raise ValueError('Source class omitted or represented twice')
            support, weighted = [], 0
            for item in semantic['categories']:
                category = item['category_id']
                matching = [r for r in source if category in chains[labels[r['type']]]]
                distinct = len({r['id'] for r in matching})
                if item['observation_contributions'] != len(matching) or item['distinct_contributors'] != distinct or distinct == 0:
                    raise ValueError('Semantic original observation/identity count mismatch')
                support.append(distinct)
                weighted += len(matching) * nodes[category]['loss']
                bins_count += 1
            values = {'min_category_distinct_contributors': min(support),
                      'semantic_max_loss': max(nodes[c]['loss'] for c in selected),
                      'semantic_mean_loss': weighted / len(source),
                      'distinct_contributors': len({r['id'] for r in source}),
                      'cell_side_m': cell['width'],
                      'window_duration_ms': release['end_ms'] - release['start_ms'],
                      'age_at_evaluation_ms': release['sealed_at_ms'] - release['start_ms']}
            if len(source) != cell['observation_contributions']:
                raise ValueError('Cell contribution count disagrees with source')
            for metric in ('min_category_distinct_contributors', 'semantic_max_loss', 'semantic_mean_loss'):
                if not math.isclose(semantic[metric], values[metric], abs_tol=1e-12, rel_tol=1e-12):
                    raise ValueError('Incorrect semantic summary')
            bounds, touched = effective(config, geometry)
            for metric, limits in bounds.items():
                if values[metric] < limits.get('min', -math.inf) or values[metric] > limits.get('max', math.inf):
                    raise ValueError('Published cell violates geometry-resolved regional bound: ' + metric)
            for row in source:
                groups[row['id'].rsplit('-', 1)[0]] += 1
            records.append({'start_ms': release['start_ms'], 'end_ms': release['end_ms'],
                            'cell_id': cell['cell_id'], 'depth': cell['depth'],
                            'intersected_regions': touched, 'effective_requirements': bounds,
                            'recomputed_metrics': values})
            cells_count += 1
    return {'status': 'verified', 'scalar': scalar, 'semantic_published_cells': cells_count,
            'semantic_published_bins': bins_count, 'retained_by_source_group': dict(groups),
            'regional_recomputations': records,
            'scope': 'Raw counts/identity unions, truthful antichains, declared losses, positive-area regional bounds, scalar geometry/coverage/retirement; no optimality or attack-resistance claim.'}


def normalized(actual):
    return {key: value for key, value in actual.items() if key != 'runtime'}


def summarize(actual, checked):
    cells = [(r, c) for r in actual['releases'] for c in r['cells']]
    retained = sum(c['observation_contributions'] for _, c in cells)
    return {'input_observations': actual['input_observation_contributions'],
            'released_observations': retained,
            'retained_fraction': retained / actual['input_observation_contributions'],
            'release_intervals_ms': [[r['start_ms'], r['end_ms']] for r in actual['releases']],
            'mean_interval_start_age_ms': sum(c['observation_contributions'] * (r['sealed_at_ms'] - r['start_ms'])
                                              for r, c in cells) / retained,
            'mean_semantic_loss': sum(c['observation_contributions'] * c['semantic']['semantic_mean_loss']
                                      for _, c in cells) / retained,
            'released_cells': len(cells),
            'retained_by_source_group': checked['retained_by_source_group']}


def run(output, binary):
    output, binary = Path(output).resolve(), Path(binary).resolve()
    if output.exists():
        raise ValueError('Refusing an existing study directory')
    output.mkdir(parents=True, mode=0o700)
    provenance = output / 'provenance'
    provenance.mkdir()
    shutil.copy2(binary, provenance / 'AggregationReplay')
    shutil.copy2(ROOT / PROTOCOL, provenance / Path(PROTOCOL).name)
    shutil.copy2(Path(__file__), provenance / Path(__file__).name)
    for name in ('make_fixture.py', 'oracle.py', 'run_moving_comparison.py', 'run_semantic_priority_study.py',
                 'occupancy.py', 'online_occupancy.py', 'semantic_queries.py', 'semantic_tradeoffs.py'):
        shutil.copy2(ROOT / 'tools/evaluation' / name, provenance / name)
    implementation = {str(p.relative_to(ROOT)): digest(p) for folder, suffix in
                      (('simulator/src', '*.cpp'), ('simulator/include', '*.hpp'), ('simulator/include', '*.tpp'),
                       ('simulator/tools', '*.cpp')) for p in (ROOT / folder).glob(suffix)}
    write_json(provenance / 'implementation-sha256.json', implementation)
    data = fixture()
    write_json(output / 'observations.json', data)
    commands = []
    for name, local, secondary in VARIANTS:
        write_json(output / (name + '-policy.json'), policy(local, secondary))
        commands.append([str(provenance / 'AggregationReplay'), '--input', str(output / 'observations.json'),
                         '--config', str(output / (name + '-policy.json')), '--mode', 'semantic_first',
                         '--output', str(output / (name + '.json'))])
    frozen = {str(p.relative_to(output)): digest(p) for p in output.rglob('*') if p.is_file()}
    write_json(output / 'pre-execution-manifest.json', {'schema': 'ump.local-leaf-policy-preflight.v1',
               'status': 'inputs_frozen', 'artifacts_sha256': frozen, 'commands': commands,
               'expected_input_observations': 380, 'expected_region_leaves': 16})
    summary = {}
    for (name, local, secondary), command in zip(VARIANTS, commands):
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        write_json(output / (name + '-execution.json'), {'command': command, 'returncode': completed.returncode,
                    'stdout': completed.stdout, 'stderr': completed.stderr})
        if completed.returncode:
            raise RuntimeError(completed.stdout + completed.stderr)
        actual = json.loads((output / (name + '.json')).read_text())
        checked = audit(data, policy(local, secondary), actual)
        write_json(output / (name + '-audit.json'), checked)
        summary[name] = summarize(actual, checked)
    repeat = commands[1][:-1] + [str(output / 'local_temporal-repeat.json')]
    completed = subprocess.run(repeat, capture_output=True, text=True, timeout=60)
    write_json(output / 'repeat-execution.json', {'command': repeat, 'returncode': completed.returncode,
               'stdout': completed.stdout, 'stderr': completed.stderr})
    if completed.returncode:
        raise RuntimeError('Determinism repeat failed')
    repeated = json.loads((output / 'local_temporal-repeat.json').read_text())
    audit(data, policy(True, 'temporal_first'), repeated)
    if normalized(repeated) != normalized(json.loads((output / 'local_temporal.json').read_text())):
        raise ValueError('Determinism repeat changed scientific output')
    variants = []
    for name, local, secondary in VARIANTS:
        metadata = [{**{key: region[key] for key in ('id', 'type', 'x', 'y', 'width', 'height')},
                     'requirements': [{'metric': metric, **bounds} for metric, bounds in region['requirements'].items()]}
                    for region in policy(local, secondary)['policy_regions']]
        variants.append({'id': name, 'label': ('Local patches' if local else 'Uniform root') +
                         (' · Semantic → Temporal' if secondary == 'temporal_first' else ' · Semantic → Spatial'),
                         'result': name + '.json', 'policy_regions': metadata})
    bundle_files = ['observations.json'] + [v['result'] for v in variants]
    write_json(output / 'bundle.json', {'schema': 'ump.replay-viewer.v1',
               'title': 'Local policy on 16 of 4096 finest leaves · scripted mechanism test',
               'observations': 'observations.json', 'variants': variants,
               'sha256': {name: digest(output / name) for name in bundle_files}})
    write_json(output / 'summary.json', summary)
    artifacts = {str(p.relative_to(output)): digest(p) for p in output.rglob('*') if p.is_file()}
    write_json(output / 'study-manifest.json', {'schema': 'ump.local-leaf-policy-study.v1', 'status': 'verified',
               'protocol': PROTOCOL, 'artifacts_sha256': artifacts, 'determinism_repeat': 'verified',
               'source': 'Deterministic scripted analytical fixture; not a full simulator capture or real traffic.',
               'variant_count': 4, 'production_calls': 5})
    print(json.dumps(summary, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--binary', type=Path, default=ROOT / 'simulator/build/AggregationReplay')
    args = parser.parse_args()
    run(args.output, args.binary)


if __name__ == '__main__':
    main()
