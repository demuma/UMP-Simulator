#!/usr/bin/env python3
"""Evaluate fixed semantic queries on a verified, unchanged local-window study."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from scoped_semantic_queries import compact, evaluate, paired_summary


ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
PROTOCOL = 'docs/SCOPED_SEMANTIC_UTILITY_PROTOCOL_2026-10-22.md'
SCHEMA = 'ump.scoped-semantic-utility-study.v1'
VARIANTS = tuple((f'{coord}_{scope}_{secondary}', coord, scope, secondary)
                 for coord in ('common_window', 'cell_local')
                 for scope in ('uniform', 'regional')
                 for secondary in ('temporal_first', 'spatial_first'))
REQUIRED = ('observations.json',) + tuple(name + suffix for name, _, _, _ in VARIANTS
                                         for suffix in ('.json', '-policy.json'))
ROI_ORIGINS = ((2.5, 2.5), (10, 10), (20, 10), (30, 10), (40, 10), (50, 10))


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def read_json(payload):
    return json.loads(payload, parse_constant=lambda value: (_ for _ in ()).throw(
        ValueError('Non-finite JSON number: ' + value)))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def tree_hashes(directory):
    return {str(path.relative_to(directory)): digest(path.read_bytes())
            for path in sorted(directory.rglob('*')) if path.is_file()}


def cell_at(x, y, depth):
    """Encode the declared 80 m origin-zero square without inspecting releases."""
    side, identity = 80, 3
    for _ in range(depth):
        side /= 2
        east, south = int(x >= side), int(y >= side)
        identity = identity * 4 + east + 2 * south
        x -= east * side
        y -= south * side
    return {'cell_id': identity, 'depth': depth}


def workloads(config):
    nodes = config['semantic_taxonomy']['nodes']
    categories = sorted(node['id'] for node in nodes)
    if len(categories) != 10 or len(set(categories)) != 10:
        raise ValueError('The declared workload requires the ten-node study taxonomy')
    patches = sorted((cell_at(x, y, 5) for x, y in ROI_ORIGINS), key=lambda row: row['cell_id'])
    banks = {
        'full_area_5m': [{'cell_id': identity, 'depth': 4} for identity in range(3 * 4**4, 4 * 4**4)],
        'six_rois_2p5m': patches,
        'six_rois_1p25m': [{'cell_id': parent['cell_id'] * 4 + child, 'depth': 6}
                          for parent in patches for child in range(4)],
    }
    return {f'{bank}_w{window}ms': {
        'bank': bank, 'target_cells': cells, 'categories': categories,
        'window_ms': window, 'lags_ms': [0, 200, 400],
        'footprint_selection': 'Declared geometry before evaluating recipient output',
    } for bank, cells in banks.items() for window in (400, 1000)}


def verify_study(study):
    manifest_bytes = (study / 'study-manifest.json').read_bytes()
    manifest = read_json(manifest_bytes)
    if manifest.get('schema') != 'ump.semantic-cell-local-study.v1' or manifest.get('status') != 'verified':
        raise ValueError('Expected a verified semantic cell-local study')
    hashes, verified = manifest.get('artifacts_sha256', {}), {}
    if not isinstance(hashes, dict):
        raise ValueError('Study manifest has no artifact digest map')
    # Only this literal allowlist chooses input paths; evaluate the verified bytes.
    for name in REQUIRED:
        payload = (study / name).read_bytes()
        if digest(payload) != hashes.get(name):
            raise ValueError('Missing or mismatched frozen input digest: ' + name)
        verified[name] = payload
    parsed = {name: read_json(payload) for name, payload in verified.items()}
    replay = parsed['observations.json']
    if (replay.get('coverage') != dict(x=0, y=0, width=80, height=80, leaf_depth=6)
            or replay.get('sampling_period_ms') != 100 or replay.get('end_ms') != 2000):
        raise ValueError('This protocol requires its 80 m, depth-six, 100 ms, 2000 ms fixture')
    taxonomy, cohort_policies = None, {}
    for name, coordination, scope, secondary in VARIANTS:
        config, result = parsed[name + '-policy.json'], parsed[name + '.json']
        if result.get('schema') != 'ump.replay-result.v1' or result.get('mode') != 'semantic_first':
            raise ValueError('Unexpected result schema or preservation strategy: ' + name)
        source, parameters = result.get('source', {}), result.get('parameters', {})
        for field in ('run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms'):
            if source.get(field) != replay.get(field):
                raise ValueError('Result source metadata disagrees with observations: ' + name + '/' + field)
        if (parameters.get('coordination') != coordination
                or parameters.get('semantic_secondary_strategy') != secondary
                or config.get('temporal_adaptation', {}).get('coordination') != coordination):
            raise ValueError('Unexpected coordination or secondary strategy: ' + name)
        execution = config.get('policy_tree', {}).get('execution', {})
        if (execution.get('strategy') != 'semantic_first'
                or execution.get('semantic_secondary_strategy') != secondary):
            raise ValueError('Unexpected policy preservation strategy: ' + name)
        if (source.get('application_id') != config.get('application_id')
                or bool(config.get('policy_regions')) != (scope == 'regional')):
            raise ValueError('Result application or regional cohort disagrees: ' + name)
        for release in result.get('releases', []):
            if ('coordination_cell' in release) != (coordination == 'cell_local'):
                raise ValueError('Public release coordination scope disagrees: ' + name)
        catalog = config.get('semantic_taxonomy')
        if taxonomy is not None and taxonomy != catalog:
            raise ValueError('All variants require the same taxonomy')
        taxonomy = catalog
        normalized = deepcopy(config)
        normalized['temporal_adaptation'].pop('coordination')
        normalized['policy_tree']['execution'].pop('semantic_secondary_strategy')
        normalized['spatial_selection'].pop('preserve_valid_descendants', None)
        if scope in cohort_policies and cohort_policies[scope] != normalized:
            raise ValueError('Hard policy changed inside a paired cohort: ' + name)
        cohort_policies[scope] = normalized
    return parsed, {'study_manifest_sha256': digest(manifest_bytes),
                    'input_artifacts_sha256': {name: digest(verified[name]) for name in REQUIRED}}


def audit_released_counts(replay, config, result):
    """Independent private truth check; its observations never supply predictions."""
    observations = [(batch['observed_at_ms'], row) for batch in replay['batches']
                    for row in batch['observations']]
    total = len(observations)
    if result.get('input_observation_contributions') != total or result.get('accounted_observation_contributions') != total:
        raise ValueError('Result input/accounting total disagrees with the frozen observations')
    nodes = {node['id']: node for node in config['semantic_taxonomy']['nodes']}
    labels = {label: node['id'] for node in nodes.values() for label in node.get('input_types', [])}
    def category_of(category, node):
        if category not in nodes:
            raise ValueError('Unknown published semantic category')
        seen = set()
        while node:
            if node not in nodes or node in seen:
                raise ValueError('Unknown parent or cycle in semantic taxonomy')
            seen.add(node)
            if node == category:
                return True
            node = nodes[node].get('parent')
        return False
    consumed, selected_cells, semantic_bins = set(), 0, 0
    for release in result['releases']:
        for cell in release['cells']:
            shift = 2 * (replay['coverage']['leaf_depth'] - cell['depth'])
            matching = [(time, row) for time, row in observations
                        if release['start_ms'] <= time < release['end_ms']
                        and row['cell_id'] >> shift == cell['cell_id']]
            identities = {row['id'] for _, row in matching}
            if (len(matching) != cell['observation_contributions']
                    or len(identities) != cell['distinct_road_users']):
                raise ValueError('Published cell count disagrees with raw frozen support')
            keys = {(time, row['id']) for time, row in matching}
            if keys & consumed:
                raise ValueError('A source contribution occurs in multiple published cells')
            consumed.update(keys)
            bins = cell['semantic']['categories']
            for bin_ in bins:
                members = [row for _, row in matching if category_of(bin_['category_id'], labels[row['type']])]
                if (len(members) != bin_['observation_contributions']
                        or len({row['id'] for row in members}) != bin_['distinct_contributors']):
                    raise ValueError('Published semantic bin disagrees with raw frozen support')
            if any(sum(category_of(bin_['category_id'], labels[row['type']]) for bin_ in bins) != 1
                   for _, row in matching):
                raise ValueError('Published semantic bins do not partition their observations')
            selected_cells += 1
            semantic_bins += len(bins)
    return {'status': 'verified', 'input_observations': total,
            'released_observations': len(consumed), 'unreleased_observations': total - len(consumed),
            'public_releases': len(result['releases']), 'public_cells': selected_cells,
            'semantic_bins': semantic_bins,
            'purpose': 'Private truth audit only; query predictions use recipient releases'}


def run(study, output):
    study, output = Path(study).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Refusing to replace an existing evaluation directory')
    if output.is_relative_to(study):
        raise ValueError('Evaluation output cannot be placed inside the frozen source study')
    parsed, provenance = verify_study(study)
    replay = parsed['observations.json']
    declared = workloads(parsed[VARIANTS[0][0] + '-policy.json'])
    code_paths = ('tools/evaluation/run_scoped_semantic_utility.py',
                  'tools/evaluation/scoped_semantic_queries.py', PROTOCOL)
    code_hashes = {name: digest((ROOT / name).read_bytes()) for name in code_paths}
    original_hashes = tree_hashes(study)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    preflight = {'schema': SCHEMA, 'status': 'unverified', 'protocol': PROTOCOL,
        'source_study': str(study), **provenance, 'implementation_sha256': code_hashes,
        'workloads': declared, 'variant_names': [row[0] for row in VARIANTS],
        'count': 'Observation contributions; never summed distinct people',
        'scope': 'Fixed analytical mechanism fixture; no new traffic or privacy-effectiveness claim'}
    write_json(output / 'preflight-manifest.json', preflight)
    write_json(output / 'study-manifest.json', preflight)
    audits, evaluations, pairs = {}, {}, {}
    try:
        for name, _, _, _ in VARIANTS:
            audits[name] = audit_released_counts(replay, parsed[name + '-policy.json'], parsed[name + '.json'])
        for scope in ('uniform', 'regional'):
            for secondary in ('temporal_first', 'spatial_first'):
                common = f'common_window_{scope}_{secondary}'
                local = f'cell_local_{scope}_{secondary}'
                for workload, definition in declared.items():
                    full = []
                    for name in (common, local):
                        evaluated = evaluate(replay, parsed[name + '-policy.json'], parsed[name + '.json']['releases'],
                            **{key: definition[key] for key in ('target_cells', 'categories', 'window_ms', 'lags_ms')})
                        compacted = compact(evaluated)
                        filename = f'{name}--{workload}.json'
                        write_json(output / filename, compacted)
                        evaluations.setdefault(name, {})[workload] = filename
                        full.append(evaluated)
                    paired = paired_summary(*full)
                    pair_key = f'{scope}_{secondary}--{workload}'
                    filename = 'paired--' + pair_key + '.json'
                    write_json(output / filename, {'a': common, 'b': local, **paired})
                    pairs[pair_key] = filename
        if original_hashes != tree_hashes(study):
            raise ValueError('Frozen source study changed during evaluation')
        if code_hashes != {name: digest((ROOT / name).read_bytes()) for name in code_paths}:
            raise ValueError('Protocol or implementation changed during evaluation')
        summary = {'schema': SCHEMA, 'status': 'verified', 'evaluations': evaluations,
                   'pairs': pairs, 'released_count_audits': audits,
                   'evaluation_count': sum(len(rows) for rows in evaluations.values()),
                   'paired_comparison_count': len(pairs), 'source_study_unchanged': True}
        write_json(output / 'summary.json', summary)
        manifest = {**preflight, 'status': 'verified', 'evaluation_count': summary['evaluation_count'],
                    'paired_comparison_count': len(pairs), 'source_study_unchanged': True,
                    'artifacts_sha256': {name: value for name, value in tree_hashes(output).items()
                                         if name != 'study-manifest.json'}}
        write_json(output / 'study-manifest.json', manifest)
    except Exception as error:
        write_json(output / 'study-manifest.json', {**preflight, 'status': 'unverified',
            'failure': {'type': type(error).__name__, 'message': str(error)}})
        raise
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print('Verified scoped semantic utility study:', run(args.study, args.output))


if __name__ == '__main__':
    main()
