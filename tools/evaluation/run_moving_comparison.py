#!/usr/bin/env python3
"""Bounded moving-data pilot: identical observations, six fixed baselines, three strategies.

This is an engineering/mechanism pilot, not a statistical privacy study. The
recipient occupancy estimator is declared; suppression remains unknown, not zero.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from oracle import validate_result
from occupancy import evaluate as occupancy_evaluate
from online_occupancy import evaluate as online_evaluate
from run_semantic_priority_study import scalar_projection

SCHEMA = 'ump.moving-comparison.v1'
CELL_CAP_BASELINES = {
    40: ((10, 3), (20, 2), (40, 1)),
    10: ((2.5, 5), (5, 4), (10, 3)),
    5: ((1.25, 6), (2.5, 5), (5, 4)),
}


def variants_for_cap(max_cell_side_m=40, max_window_ms=1000):
    if type(max_cell_side_m) is not int or max_cell_side_m not in CELL_CAP_BASELINES:
        raise ValueError('max_cell_side_m must be one of 40, 10 or 5 metres')
    if type(max_window_ms) is not int or max_window_ms not in (1000, 4000):
        raise ValueError('max_window_ms must be 1000 or 4000 milliseconds')
    windows = (400, 1000) if max_window_ms == 1000 else (400, 1000, 4000)
    return [(f'fixed_{side:g}m_{window}ms'.replace('.', 'p'), 'fixed', depth, window)
            for side, depth in CELL_CAP_BASELINES[max_cell_side_m] for window in windows] + [
                (mode, mode, None, None) for mode in ('temporal_first', 'spatial_first', 'semantic_first')]


# Backward-compatible default matrix; archived 40-m experiments remain unchanged.
VARIANTS = variants_for_cap()
SEMANTIC = {'min_category_distinct_contributors', 'semantic_max_loss', 'semantic_mean_loss'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as out:
        json.dump(value, out, sort_keys=True, separators=(',', ':'), allow_nan=False)
        out.write('\n')
    Path(path).chmod(0o600)


def policy(max_cell_side_m=40, max_window_ms=1000):
    variants_for_cap(max_cell_side_m, max_window_ms)  # Validate before building a policy.
    minimum_depth = {40: 1, 10: 3, 5: 4}[max_cell_side_m]
    nodes = [{'id': 'road_user', 'loss': 1},
             {'id': 'pedestrian', 'parent': 'road_user', 'loss': .5},
             {'id': 'cyclist', 'parent': 'road_user', 'loss': .5},
             {'id': 'escooter', 'parent': 'road_user', 'loss': 0,
              'input_types': ['Adult E-Scooter Driver']}]
    for category, parent, label in (
        ('child_pedestrian', 'pedestrian', 'Child Pedestrian'),
        ('senior_pedestrian', 'pedestrian', 'Senior Pedestrian'),
        ('adult_pedestrian', 'pedestrian', 'Adult Pedestrian'),
        ('senior_cyclist', 'cyclist', 'Senior Cyclist'),
        ('adult_cyclist', 'cyclist', 'Adult Cyclist'),
        ('adult_cargo_cyclist', 'cyclist', 'Adult Cargo Cyclist')):
        nodes.append({'id': category, 'parent': parent, 'loss': 0, 'input_types': [label]})
    return {'application_id': 'moving-occupancy-pilot', 'window_ms': 400,
            'max_observations_per_window': 1000000,
            'history': {'retention_ms': 2000 if max_window_ms == 1000 else 5000, 'max_bins': 32 if max_window_ms == 1000 else 64, 'max_observations': 100000,
                        'max_identity_bytes': 16000000, 'max_buckets': 128},
            'spatial_selection': {'min_depth': minimum_depth, 'max_evaluations': 8192, 'preserve_valid_descendants': True},
            'temporal_adaptation': {'coordination': 'common_window', 'extension_step_ms': 100,
                                    'max_window_ms': max_window_ms, 'max_evaluations': 16 if max_window_ms == 1000 else 64},
            'semantic_taxonomy': {'id': 'ump-seven-profile-release', 'version': '1', 'nodes': nodes},
            'policy_tree': {'id': (f'moving-occupancy-pilot-cap-{max_cell_side_m}m-window-{max_window_ms}ms' if max_window_ms != 1000 else 'moving-occupancy-pilot' if max_cell_side_m == 40 else f'moving-occupancy-pilot-cap-{max_cell_side_m}m'), 'version': '1', 'max_nodes': 65536,
                            'execution': {'publication_model': 'private_final_snapshot', 'strategy': 'temporal_first',
                                          'release_trigger': 'priority_satisfied'},
                            'root': {'distinct_contributors': {'min': 1},
                                     'min_category_distinct_contributors': {'min': 5},
                                     'semantic_max_loss': {'max': 1},
                                     'cell_side_m': {'min': 1.25, 'max': max_cell_side_m},
                                     'window_duration_ms': {'max': max_window_ms},
                                     'age_at_evaluation_ms': {'max': max_window_ms}}, 'regions': []},
            'policy_regions': []}


def scalar_audit(replay, config, result):
    config, result = scalar_projection(config, result)
    if config['policy_tree']['execution']['strategy'] == 'semantic_first':
        config['policy_tree']['execution']['strategy'] = 'temporal_first'
    if result['mode'] == 'semantic_first':
        result['mode'] = 'temporal_first'
    for window in result['windows']:
        if window.get('strategy') == 'semantic_first':
            window['strategy'] = 'temporal_first'
    value = validate_result(replay, config, result, max_cells=500000)
    if not value['valid']:
        raise ValueError(f'Independent scalar audit failed: {value}')
    return value


def semantic_audit(replay, config, result):
    """Rebuild every published bin from raw identities; no C++ pass flags or bin selection reuse.

    This bounded pilot has a uniform root policy, a fixed checked taxonomy, and
    common windows. This check does not enumerate alternatives or prove optimality.
    """
    if config.get('policy_regions') or config['policy_tree'].get('regions'):
        raise ValueError('Pilot semantic audit only supports the declared uniform policy')
    catalog = config['semantic_taxonomy']
    if catalog != policy()['semantic_taxonomy']:
        raise ValueError('Pilot requires its predeclared seven-profile taxonomy')
    nodes = {node['id']: node for node in catalog['nodes']}
    labels = {label: node['id'] for node in catalog['nodes'] for label in node.get('input_types', [])}
    def ancestors(category):
        answer = []
        while category:
            answer.append(category)
            category = nodes[category].get('parent')
        return answer
    chains = {category: ancestors(category) for category in nodes}
    stable = {}
    for batch in replay['batches']:
        for row in batch['observations']:
            category = labels.get(row['type'])
            if category is None or stable.setdefault(row['id'], category) != category:
                raise ValueError('Unmapped or unstable source type')
    depth = replay['coverage']['leaf_depth']
    root = config['policy_tree']['root']
    audited_cells = audited_bins = 0
    for release in result['releases']:
        counts, people = Counter(), defaultdict(set)
        for batch in replay['batches']:
            if release['start_ms'] <= batch['observed_at_ms'] < release['end_ms']:
                for row in batch['observations']:
                    for d in range(1, depth + 1):
                        cid = row['cell_id'] >> (2 * (depth - d))
                        terminal = labels[row['type']]
                        counts[(cid, terminal)] += 1
                        people[(cid, terminal)].add(row['id'])
        for cell in release['cells']:
            value = cell['semantic']
            if value.get('schema') != 'ump.semantic-release.v1' or value.get('taxonomy_id') != catalog['id'] or value.get('taxonomy_version') != catalog['version']:
                raise ValueError('Semantic schema/catalog mismatch')
            bins = value['categories']
            categories = [b['category_id'] for b in bins]
            if len(set(categories)) != len(categories) or any(c not in nodes for c in categories):
                raise ValueError('Unknown or repeated category')
            if any(a != b and a in chains[b] for a in categories for b in categories):
                raise ValueError('Overlapping semantic antichain')
            cid = cell['cell_id']
            expected_total = sum(counts[cid, leaf] for leaf in labels.values())
            if expected_total != cell['observation_contributions'] or expected_total <= 0:
                raise ValueError('Published observations disagree with original support')
            for leaf in labels.values():
                if counts[cid, leaf] and sum(c in chains[leaf] for c in categories) != 1:
                    raise ValueError('Observed class omitted or represented twice')
            weighted = 0
            minimum = math.inf
            for item in bins:
                c = item['category_id']
                descendants = [leaf for leaf in labels.values() if c in chains[leaf]]
                expected = sum(counts[cid, leaf] for leaf in descendants)
                union = set().union(*(people[cid, leaf] for leaf in descendants))
                if any(type(item.get(key)) is not int or not 1 <= item[key] <= 2**53 - 1
                       for key in ('observation_contributions', 'distinct_contributors')):
                    raise ValueError('Semantic counts require positive exact integers')
                if expected <= 0 or item['observation_contributions'] != expected or item['distinct_contributors'] != len(union):
                    raise ValueError('Published bin count/identity union is incorrect')
                minimum = min(minimum, len(union))
                weighted += expected * nodes[c]['loss']
                audited_bins += 1
            maximum = max(nodes[c]['loss'] for c in categories)
            mean = weighted / expected_total
            for key, expected in (('min_category_distinct_contributors', minimum),
                                  ('semantic_max_loss', maximum), ('semantic_mean_loss', mean)):
                actual = value[key]
                if isinstance(actual, bool) or not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError('Semantic summary mismatch')
                bound = root.get(key, {})
                if actual < bound.get('min', -math.inf) or actual > bound.get('max', math.inf):
                    raise ValueError('Released semantic metric violates the policy')
            audited_cells += 1
    return {'status': 'verified', 'published_cells': audited_cells, 'published_bins': audited_bins,
            'scope': 'Original counts, identity unions, complete truthful antichain, declared losses and root bounds; no alternative-cut/optimality claim.'}


def population(replay):
    seen, moved, origins = set(), set(), {}
    for batch in replay['batches']:
        for row in batch['observations']:
            identity = row['id']
            seen.add(identity)
            point = row['x'], row['y']
            if origins.setdefault(identity, point) != point:
                moved.add(identity)
    sizes = [len(b['observations']) for b in replay['batches']]
    return {'sampled_frames': len(sizes), 'first_sample_road_users': sizes[0], 'last_sample_road_users': sizes[-1],
            'minimum_sample_road_users': min(sizes), 'maximum_sample_road_users': max(sizes),
            'unique_sampled_road_users': len(seen), 'road_users_with_observed_displacement': len(moved),
            'first_sample_types': dict(Counter(r['type'] for r in replay['batches'][0]['observations']))}


def summarize(replay, result, eventual, online):
    cells = [(release, cell) for release in result['releases'] for cell in release['cells']]
    retained = sum(c['observation_contributions'] for _, c in cells)
    def weighted(fn):
        return sum(c['observation_contributions'] * fn(r, c) for r, c in cells) / retained if retained else None
    return {'input_observations': result['input_observation_contributions'], 'released_observations': retained,
            'retained_fraction': retained / result['input_observation_contributions'] if result['input_observation_contributions'] else None,
            'released_cells': len(cells), 'released_windows': len(result['releases']),
            'mean_cell_side_m': weighted(lambda r, c: c['width']),
            'mean_semantic_loss': weighted(lambda r, c: c['semantic']['semantic_mean_loss']),
            'maximum_semantic_loss': max((c['semantic']['semantic_max_loss'] for _, c in cells), default=None),
            'mean_interval_start_age_ms': weighted(lambda r, c: r['sealed_at_ms'] - r['start_ms']),
            'occupancy_eventual': eventual['summary'],
            'occupancy_at_deadline': {lag: val['summary'] for lag, val in online['evaluations_by_lag_ms'].items()},
            'core_processing_ms': result['runtime']['processing_ms'],
            'timing_scope': 'Logical simulation-time interval-start age and deadlines; CPU reported separately, no live DB/network latency.'}


def run(capture, output, binary, timeout=180, *, max_cell_side_m=40, max_window_ms=1000):
    capture, output, binary = Path(capture).resolve(), Path(output).resolve(), Path(binary).resolve()
    source = capture / 'observations.json'
    proof = json.loads((capture / 'capture-proof.json').read_text())
    capture_manifest = json.loads((capture / 'capture-manifest.json').read_text())
    if proof.get('status') != 'verified' or capture_manifest.get('status') != 'verified':
        raise ValueError('Require independently verified capture')
    for name in ('observations.json', 'capture-proof.json'):
        expected = capture_manifest['artifacts_sha256'].get(name)
        if expected != digest(capture / name):
            raise ValueError(f'Capture {name} hash mismatch')
    replay = json.loads(source.read_text())
    if replay['coverage'] != dict(x=0, y=0, width=80, height=80, leaf_depth=6) or replay['sampling_period_ms'] != 100:
        raise ValueError('Pilot requires its declared 80m/D6/100ms source')
    if not 2000 <= replay['end_ms'] <= 120000:
        raise ValueError('Pilot source horizon must be between2 and120 simulated seconds')
    config = policy(max_cell_side_m, max_window_ms)
    variants_to_run = variants_for_cap(max_cell_side_m, max_window_ms)
    labels = {label for n in config['semantic_taxonomy']['nodes'] for label in n.get('input_types', [])}
    if any(row['type'] not in labels for batch in replay['batches'] for row in batch['observations']):
        raise ValueError('Source uses undeclared profile')
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    source_root = Path(__file__).resolve().parent
    frozen_sources = output / 'sources'
    frozen_sources.mkdir(mode=0o700)
    for name in ('run_moving_comparison.py', 'oracle.py', 'occupancy.py', 'online_occupancy.py',
                 'coordination_metrics.py', 'run_semantic_priority_study.py', 'semantic_tradeoffs.py',
                 'capture_simulator.py'):
        shutil.copyfile(source_root / name, frozen_sources / name)
    shutil.copyfile(source, output / 'observations.json')
    shutil.copyfile(capture / 'capture-proof.json', output / 'capture-proof.json')
    shutil.copyfile(capture / 'capture-manifest.json', output / 'capture-manifest.json')
    shutil.copyfile(binary, output / 'AggregationReplay.frozen')
    (output / 'AggregationReplay.frozen').chmod(0o700)
    write_json(output / 'policy.json', config)
    protocol_name = ('FOUR_SECOND_WINDOW_PROTOCOL_2026-10-21.md' if max_window_ms != 1000 else
                     'MOVING_REPLAY_PROTOCOL_2026-10-21.md' if max_cell_side_m == 40 else 'CELL_SIZE_CAP_PROTOCOL_2026-10-21.md')
    protocol = Path(__file__).resolve().parents[2] / 'docs' / protocol_name
    if not protocol.is_file():
        raise ValueError('Record the pilot protocol before running')
    shutil.copyfile(protocol, output / 'protocol.md')
    summaries, variants, commands = {}, [], []
    for identity, mode, depth, window in variants_to_run:
        directory = output / identity
        directory.mkdir(mode=0o700)
        command = [str(output / 'AggregationReplay.frozen'), '--input', str(output / 'observations.json'),
                   '--config', str(output / 'policy.json'), '--mode', mode, '--output', str(directory / 'result.json')]
        if depth is not None:
            command.extend(['--fixed-depth', str(depth), '--fixed-window-ms', str(window)])
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        (directory / 'stdout.log').write_text(completed.stdout)
        (directory / 'stderr.log').write_text(completed.stderr)
        if completed.returncode:
            raise RuntimeError(f'{identity} failed; output is incomplete: {completed.stderr}')
        result = json.loads((directory / 'result.json').read_text())
        audit_config = deepcopy(config)
        if mode != 'fixed':
            audit_config['policy_tree']['execution']['strategy'] = mode
        if window is not None:
            audit_config['window_ms'] = window
        scalar = scalar_audit(replay, audit_config, result)
        semantics = semantic_audit(replay, config, result)
        for collection in ('windows', 'releases'):
            for event in result[collection]:
                if any(cell['width'] > max_cell_side_m or cell['height'] > max_cell_side_m
                       or cell['depth'] < config['spatial_selection']['min_depth'] for cell in event['cells']):
                    raise ValueError('Final diagnostic/released footprint exceeds the declared cell-size cap')
        write_json(directory / 'audit.json', {'scalar': scalar, 'semantic': semantics})
        eventual = occupancy_evaluate(replay, result, reference_cell_m=10, reference_window_ms=1000)
        online = online_evaluate(replay, result, reference_cell_m=10, reference_window_ms=1000,
                                 deadline_lags_ms=(0, 200, 1000))
        write_json(directory / 'occupancy.json', eventual)
        write_json(directory / 'deadline-occupancy.json', online)
        summaries[identity] = summarize(replay, result, eventual, online)
        variants.append({'id': identity, 'label': identity.replace('_', ' '), 'result': f'{identity}/result.json'})
        commands.append(command)
        print(json.dumps({'variant': identity, 'retained': summaries[identity]['retained_fraction'],
                          'side_m': summaries[identity]['mean_cell_side_m'], 'semantic_loss': summaries[identity]['mean_semantic_loss']}), flush=True)
    first = variants[-1]
    again = output / 'determinism-repeat.json'
    command = commands[-1][:-1] + [str(again)]
    subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=True)
    previous = json.loads((output / first['result']).read_text())
    repeated = json.loads(again.read_text())
    previous.pop('runtime', None)
    repeated.pop('runtime', None)
    if previous != repeated:
        raise ValueError('Frozen source deterministic replay failed')
    write_json(output / 'summary.json', {'schema': SCHEMA, 'max_cell_side_m': max_cell_side_m, 'max_window_ms': max_window_ms, 'population': population(replay), 'variants': summaries,
                                        'scientific_repeats': 0, 'determinism_repeats': 1})
    with (output / 'summary.csv').open('x', newline='') as out:
        fields = ['variant', 'retained_fraction', 'mean_cell_side_m', 'mean_semantic_loss', 'mean_interval_start_age_ms']
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for identity, summary in summaries.items():
            writer.writerow({'variant': identity, **{k: summary[k] for k in fields[1:]}})
    write_json(output / 'bundle.json', {'schema': 'ump.replay-viewer.v1', 'title': ('Moving-data mechanism pilot' if max_cell_side_m == 40 and max_window_ms == 1000 else f'Moving-data pilot / cell cap {max_cell_side_m} m / maximum window {max_window_ms} ms'),
                                       'observations': 'observations.json', 'variants': variants})
    write_json(output / 'manifest.json', {'schema': SCHEMA, 'status': 'verified', 'max_cell_side_m': max_cell_side_m, 'max_window_ms': max_window_ms, 'commands': commands,
               'binary_sha256': digest(binary), 'runner_sha256': digest(frozen_sources / 'run_moving_comparison.py'),
               'capture': str(capture), 'protocol_sha256': digest(protocol),
               'artifacts_sha256': {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob('*')) if p.is_file()},
               'limitations': ['One stochastic realization per population; no statistical superiority or measured privacy-gain claim.',
                               'Uniform initial positions and random straight-line destinations; no map or replenishing flow.',
                               'All methods use identical observations, policy thresholds and semantic release selector.',
                               'Declared taxonomy loss0/.5/1 is a preference scale, not a calibrated privacy measure.',
                               'Fixed10m/1s all-road-user occupancy assumes spatial uniformity and temporal constancy within published support.',
                               'Semantic class-query utility is not measured by this all-road-user occupancy workload.',
                               'A limited predeclared fixed matrix; not an exhaustive best-fixed or global-optimality claim.']})
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--binary', type=Path, default=Path(__file__).resolve().parents[2] / 'simulator/build/AggregationReplay')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--max-cell-side-m', type=int, choices=(40, 10, 5), default=40,
                        help='Maximum published cell side; changes policy/search cap and legal fixed baseline sizes')
    parser.add_argument('--max-window-ms', type=int, choices=(1000, 4000), default=1000,
                        help='Maximum window and age; 4000 also increases history and endpoint-check limits')
    args = parser.parse_args()
    run(args.capture, args.output, args.binary, args.timeout, max_cell_side_m=args.max_cell_side_m, max_window_ms=args.max_window_ms)


if __name__ == '__main__':
    main()
