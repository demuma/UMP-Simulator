#!/usr/bin/env python3
"""P25.2 private DEV plumbing pilot: audited native output -> semantic recipient.

No motion is generated and no attack is trained. All methods use the P25.1 IN/OUT
pair, one unchanged policy and one frozen executable. Runtime receipts are
operational diagnostics, not isolated performance benchmarks or privacy results.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

import urban_privacy_fixture as fixture
import semantic_privacy as semantic
import regional_public_transcript as regional
import run_local_policy_replay as independent
import static_regional_schedule as static

ROOT = Path(__file__).resolve().parents[2]
WORLDS = ('IN', 'OUT')
WINDOWS = (400, 1000, 2000, 4000)
AVAILABILITY = 'final_snapshot_at_horizon'
MATRIX = ({'method': 'adaptive_semantic_first', 'mode': 'semantic_first'},) + tuple(
    {'method': f'fixed20_{window}ms', 'mode': 'fixed', 'window_ms': window} for window in WINDOWS)


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    return fixture.load(Path(path))


def write(path, value):
    fixture.write_new(Path(path), fixture.encoded(value))


def sha(path):
    return fixture.sha(Path(path))


def canonical(value):
    return fixture.canonical(value)


def matrix():
    return [dict(row, world=world, id=world + '_' + row['method']) for world in WORLDS for row in MATRIX]


def public_policy(config):
    tree = config['policy_tree']
    return {'policy_id': tree['id'], 'policy_version': tree['version'],
            'root_requirements': deepcopy(tree['root']),
            'regional_requirements': deepcopy(config.get('policy_regions', [])),
            'execution': deepcopy(tree['execution'])}


def public_contract(public, config, forbidden_tokens=()):
    """Check declared constants and prevent source/run/episode aliases leaking."""
    semantic.validate_public(public)
    expected = config['policy_tree']
    taxonomy = semantic.public_taxonomy(config['semantic_taxonomy'])
    require(canonical(public['taxonomy']) == canonical(taxonomy), 'Public taxonomy changed')
    require(public['availability_model'] == AVAILABILITY, 'Pilot availability model changed')
    prefix = expected['id'] + '/' + expected['version'] + '/'
    suffixes = {depth: regional._policy_suffixes(public['coverage'], config, depth)
                for depth in {cell['depth'] for release in public['releases'] for cell in release['cells']}}
    for release in public['releases']:
        require(release['policy_id'] == expected['id'] and release['policy_version'] == expected['version']
                and release['model'] == expected['execution']['publication_model'],
                'Public policy/model identity differs from frozen policy')
        for cell in release['cells']:
            identifier = cell['effective_policy_id']
            require(identifier == prefix + suffixes[cell['depth']][cell['cell_id']],
                    'Effective public policy identity differs from compiled policy')
    text = canonical(public).decode('ascii')
    require(not any(token and token in text for token in forbidden_tokens), 'Private source/episode identity in recipient stream')


def constants(public):
    return {key: value for key, value in public.items() if key != 'releases'}


def feature_check(public, knowledge):
    names = semantic.feature_names(public, include_geometry=True)
    values = semantic.feature_vector(public, knowledge, include_geometry=True)
    require(len(names) == len(values) and len(set(names)) == len(names), 'Feature schema/dimension mismatch')
    require(all(type(value) in (int, float) and math.isfinite(value) for value in values), 'Nonfinite public feature')
    end = public['end_ms']
    before = semantic.public_view(public, end - 1)
    final = semantic.public_view(public, end)
    require(not before['releases'], 'A final snapshot became visible before its availability')
    require(canonical(final) == canonical(public), 'Final recipient view changed records')
    empty = deepcopy(public)
    empty['releases'] = []
    empty_values = semantic.feature_vector(empty, knowledge, include_geometry=True)
    require(semantic.feature_names(empty, include_geometry=True) == names and len(empty_values) == len(values)
            and all(value == 0 for value in empty_values), 'No-output changes feature space or leaks label-dependent information')
    return {'schema': 'ump.urban-semantic-feature-vector.v1', 'feature_names': names, 'values': values}, {
        'features': len(names), 'finite': True, 'full_horizon_view_equal': True,
        'before_horizon_no_snapshot': True, 'no_output_same_dimension': True}


def source_paths():
    # Freeze all evaluation helpers, including transitive raw-audit projections.
    return sorted((ROOT / 'tools/evaluation').glob('*.py')) + [ROOT / 'simulator/CMakeLists.txt']


def unchanged(receipt):
    for name, expected in receipt.items():
        require(sha(Path(name)) == expected, 'Frozen source or artifact changed: ' + str(name))


def remember(output, names, frozen):
    unchanged(frozen)
    for name in names:
        path = Path(output) / name
        require(path.is_file(), 'Missing completed pilot artifact: ' + str(path))
        frozen[str(path)] = sha(path)


def command(binary, input_path, policy_path, output_path, row):
    result = [str(binary), '--input', str(input_path), '--config', str(policy_path),
              '--mode', row['mode'], '--output', str(output_path), '--progress-step-ms', '50']
    if row['mode'] == 'fixed':
        result += ['--fixed-depth', '2', '--fixed-window-ms', str(row['window_ms'])]
    return result


def prepare(fixture_dir, output, binary, wall_budget_s):
    require(type(wall_budget_s) is int and 1 <= wall_budget_s <= 240, 'Native wall cap must be 1..240 seconds')
    fixture_dir = fixture.safe_path(Path(fixture_dir), root=ROOT / 'results')
    checked = fixture.verify_fixture(fixture_dir)
    old_manifest = load(fixture_dir / 'private-manifest.json')
    require(sha(fixture_dir / 'private-manifest.json') == checked['manifest_sha256']
            and sha(fixture_dir / 'protocol.json') == checked['protocol_sha256'], 'Verified fixture receipt changed')
    require(checked['development_only'] and checked['independent_sources'] == 1, 'Expected the P25.1 DEV source')
    old_protocol = load(fixture_dir / 'protocol.json')
    policy_path = ROOT / old_protocol['sources']['policy']['path']
    config = load(policy_path)
    require(config['policy_tree']['root']['semantic_suppression_fraction']['max'] == 0, 'Pilot is suppression OFF')
    require(config['policy_tree']['execution']['strategy'] == 'semantic_first', 'Expected frozen Semantic First policy')
    binary = fixture.safe_path(Path(binary), root=ROOT)
    study_protocol = load(ROOT / old_protocol['sources']['source_protocol']['path'])
    require(sha(binary) == study_protocol['native_binary_sha256'], 'Use the unchanged corrected native executable')
    # Schedule is selected from public geometry/policy, never publication outcomes.
    schedule = static.plan_schedule(fixture.COVERAGE, config, 20)
    output = fixture.new_output(Path(output))
    provenance = output / 'provenance'
    provenance.mkdir(mode=0o700)
    copied_binary = provenance / 'AggregationReplay'
    shutil.copyfile(binary, copied_binary)
    copied_binary.chmod(0o700)
    require(sha(copied_binary) == study_protocol['native_binary_sha256'], 'Binary changed while copying')
    fixture.write_new(provenance / 'policy.json', fixture.read_bytes(policy_path))
    require(sha(provenance / 'policy.json') == old_protocol['sources']['policy']['sha256'], 'Policy changed while copying')
    for world, name in (('IN', 'in.json'), ('OUT', 'out.json')):
        fixture.write_new(provenance / (world + '.json'), fixture.read_bytes(fixture_dir / name))
        require(sha(provenance / (world + '.json')) == old_manifest['files_sha256'][name], 'Verified source changed while copying')
        aux_name = 'auxiliary-' + world.lower() + '.json'
        fixture.write_new(provenance / (world + '-auxiliary.json'), fixture.read_bytes(fixture_dir / aux_name))
        require(sha(provenance / (world + '-auxiliary.json')) == old_manifest['files_sha256'][aux_name], 'Verified auxiliary changed while copying')
    write(provenance / 'regional-schedule.json', {key: value for key, value in schedule.items() if key != 'cells'})
    # Fixed public side information is not the raw simulator configuration.
    capture = ROOT / old_protocol['capture']
    for name in ('map_background.png', 'building_access.json'):
        fixture.write_new(provenance / name, fixture.read_bytes(capture / name))
        require(sha(provenance / name) == old_protocol['sources']['capture:' + name]['sha256'], 'Public map changed while copying')
    methods = [dict(row, grid_side_m=20) if row['mode'] == 'fixed' else dict(row) for row in MATRIX]
    methods.append({'method': 'regional_static20', 'mode': 'derived_policy_only_schedule', 'grid_side_m': 20,
                    'cell_window_ms': schedule['cell_window_ms'], 'native_runtime': None})
    context = {'schema': 'ump.urban-public-context.v1', 'policy': public_policy(config), 'methods': methods,
               'execution_scope': 'Policy execution is reference provenance; declared fixed modes override selection and regional static is derived.',
               'taxonomy': semantic.public_taxonomy(config['semantic_taxonomy']),
               'map_geometry': 'building_access.json', 'map_background': 'map_background.png',
               'scope': 'Fixed public context, identical for both labels; no source identities, seeds, visits or raw simulator configuration.'}
    write(provenance / 'public-context.json', context)
    cases = matrix()
    for row in cases:
        row['command'] = command(copied_binary, provenance / (row['world'] + '.json'), provenance / 'policy.json', output / (row['id'] + '.json'), row)
    frozen = {str(path): sha(path) for path in provenance.iterdir()}
    frozen.update({str(path): sha(path) for path in source_paths()})
    frozen.update({str(path): sha(path) for path in fixture_dir.iterdir()})
    protocol = {'schema': 'ump.urban-privacy-channel-pilot-protocol.v1',
                'cases': cases, 'native_binary_sha256': sha(copied_binary), 'frozen_files_sha256': dict(frozen),
                'fixture_directory': str(fixture_dir), 'availability_model': AVAILABILITY,
                'worlds': list(WORLDS), 'regional_windows_ms': list(WINDOWS), 'regional_side_m': 20,
                'native_wall_budget_s': wall_budget_s, 'audit_max_cells': 1000000,
                'public_policy': public_policy(config), 'public_context': context,
                'feature_names': semantic.feature_names(semantic.public_taxonomy(config['semantic_taxonomy']), include_geometry=True),
                'scope': 'One DEV pair and ten native plumbing replays; no fitting, held-out risk estimate, privacy benefit or isolated runtime claim.',
                'timing_scope': 'Elapsed times are operational run receipts only; they include startup/final file writing and do not certify live delivery.',
                'availability_scope': 'Retrospective final snapshot assumed available at H for evaluation; no actual delivery/receipt time is measured.'}
    write(output / 'protocol.json', protocol)
    frozen[str(output / 'protocol.json')] = sha(output / 'protocol.json')
    return output, config, protocol, frozen


def native_header(result, source, config, row):
    parameters = result.get('parameters', {})
    actual_source = result.get('source', {})
    require(result.get('schema') == 'ump.replay-result.v1' and result.get('mode') == row['mode'],
            'Native replay method differs from its predeclared command')
    require(parameters.get('progress_step_ms') == 50 and parameters.get('progress_origin_ms') == 0,
            'Native progress cadence changed')
    require(all(actual_source.get(key) == source[key] for key in
                ('run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms')),
            'Native result source identity/horizon differs')
    require(actual_source.get('application_id') == config['application_id'], 'Native application differs')
    if row['mode'] == 'fixed':
        require(parameters.get('fixed_depth') == 2 and parameters.get('window_ms') == row['window_ms']
                and parameters.get('coordination') == 'common_window', 'Native fixed schedule changed')
    else:
        require(parameters.get('coordination') == 'cell_local', 'Native adaptive coordination changed')
    total = sum(len(batch['observations']) for batch in source['batches'])
    require(result.get('input_observation_contributions') == total
            and result.get('accounted_observation_contributions') == total, 'Native input accounting differs')


def run_native(output, config, protocol, frozen, row):
    unchanged(frozen)
    started = time.perf_counter()
    try:
        completed = subprocess.run(row['command'], cwd=ROOT, text=True, capture_output=True,
                                   timeout=protocol['native_wall_budget_s'], umask=0o077)
    except subprocess.TimeoutExpired as error:
        write(output / (row['id'] + '-execution.json'), {'status': 'timeout', 'seconds': time.perf_counter() - started})
        raise RuntimeError(row['id'] + ' exceeded the native wall budget') from error
    write(output / (row['id'] + '-execution.json'), {'returncode': completed.returncode,
          'seconds': time.perf_counter() - started, 'stdout': completed.stdout, 'stderr': completed.stderr})
    require(completed.returncode == 0, row['id'] + ' native replay failed')
    unchanged(frozen)
    source = load(output / 'provenance' / (row['world'] + '.json'))
    result_path = output / (row['id'] + '.json')
    result_digest = sha(result_path)
    result = load(result_path)
    native_header(result, source, config, row)
    audited = deepcopy(config)
    audited['temporal_adaptation']['coordination'] = result['parameters']['coordination']
    audit = independent.audit(source, audited, result, max_cells=protocol['audit_max_cells'])
    require(audit.get('status') == 'verified' and audit.get('scalar', {}).get('valid') is True,
            row['id'] + ' independent raw audit failed')
    write(output / (row['id'] + '-audit.json'), audit)
    public = semantic.export_public(result, config['semantic_taxonomy'], availability_model=AVAILABILITY)
    forbidden = {source['run_id'], source['sensor_id']} | {o['id'] for batch in source['batches'] for o in batch['observations']}
    public_contract(public, config, forbidden)
    knowledge = load(output / 'provenance' / (row['world'] + '-auxiliary.json'))
    features, checks = feature_check(public, knowledge)
    require(features['feature_names'] == protocol['feature_names'], 'Feature schema changed after predeclaration')
    write(output / (row['id'] + '-public.json'), public)
    write(output / (row['id'] + '-features.json'), features)
    unchanged(frozen)
    require(sha(result_path) == result_digest, 'Native result changed during verification')
    remember(output, [row['id'] + suffix for suffix in ('.json', '-execution.json', '-audit.json', '-public.json', '-features.json')], frozen)
    record = dict(row, status='verified', result_sha256=result_digest,
                  public_sha256=sha(output / (row['id'] + '-public.json')),
                  private_audit_sha256=sha(output / (row['id'] + '-audit.json')),
                  independent_audit={'status': 'verified', 'scalar_valid': True, 'published_policy_violations': 0},
                  published_releases=len(public['releases']),
                  published_cells=sum(len(r['cells']) for r in public['releases']),
                  input_observations=result['input_observation_contributions'],
                  accounted_observations=result['accounted_observation_contributions'], feature_checks=checks)
    print(json.dumps({'case': row['id'], 'status': 'verified', 'public_cells': record['published_cells'], 'features': checks['features']}), flush=True)
    return record, public


def family_manifest(output, config, world, records):
    cases = {}
    for window in WINDOWS:
        key = world + '_fixed20_' + str(window) + 'ms'
        record = records[key]
        entry = {}
        for label, name in [('config', 'provenance/policy.json'), ('result', key + '.json'), ('private_audit', key + '-audit.json')]:
            entry[label] = {'path': name, 'sha256': sha(output / name)}
        entry['independent_audit'] = record['independent_audit']
        cases[str(window)] = entry
    return {'schema': 'ump.regional-public-family.v1', 'public_coverage': fixture.COVERAGE,
            'sampling_period_ms': 100, 'end_ms': 300000, 'side_m': 20,
            'public_policy_id': config['policy_tree']['id'], 'method_alias': 'regional-static-20m',
            'source': {'path': 'provenance/' + world + '.json', 'sha256': sha(output / 'provenance' / (world + '.json'))},
            'native_binary': {'path': 'provenance/AggregationReplay', 'sha256': sha(output / 'provenance/AggregationReplay')},
            'cases': cases}


def pilot(fixture_dir, output, binary, *, wall_budget_s=180):
    output, config, protocol, frozen = prepare(fixture_dir, output, binary, wall_budget_s)
    records, publics, regional_cases = {}, {}, {}
    try:
        for row in protocol['cases']:
            record, public = run_native(output, config, protocol, frozen, row)
            records[row['id']], publics[row['id']] = record, public
        for world in WORLDS:
            unchanged(frozen)
            manifest = family_manifest(output, config, world, records)
            write(output / (world + '-regional-family.json'), manifest)
            remember(output, [world + '-regional-family.json'], frozen)
            composed = regional.compose_family(output, manifest, availability_model=AVAILABILITY)
            public = composed['public_transcript']
            public_contract(public, config)
            features, checked = feature_check(public, load(output / 'provenance' / (world + '-auxiliary.json')))
            require(features['feature_names'] == protocol['feature_names'], 'Regional feature schema changed after freeze')
            key = world + '_regional_static20'
            write(output / (key + '-public.json'), public)
            write(output / (key + '-features.json'), features)
            write(output / (key + '-audit.json'), composed['private_audit'])
            remember(output, [key + suffix for suffix in ('-public.json', '-features.json', '-audit.json')], frozen)
            publics[key] = public
            regional_cases[key] = {'status': 'verified', 'native_runtime': None,
                                   'public_sha256': sha(output / (key + '-public.json')), 'feature_checks': checked}
        headers = [canonical(constants(value)) for value in publics.values()]
        require(all(value == headers[0] for value in headers), 'Public fixed context differs by world or method')
        require(all(record['feature_checks']['features'] == next(iter(records.values()))['feature_checks']['features']
                    for record in records.values()), 'Method-specific feature dimensions')
        schedule_in = load(output / 'IN_regional_static20-audit.json')
        schedule_out = load(output / 'OUT_regional_static20-audit.json')
        # The public-only policy schedule is independently declared before results.
        declared = load(output / 'provenance/regional-schedule.json')['cell_window_ms']
        for row in (schedule_in, schedule_out):
            actual = row.get('cell_window_ms', row.get('schedule', {}).get('cell_window_ms'))
            require(actual == declared, 'Regional schedule changed with membership or outcomes')
        unchanged(frozen)
        summary = {'schema': 'ump.urban-privacy-channel-pilot.v1', 'status': 'verified',
                   'development_only': True, 'independent_sources': 1, 'fixture_pairs': 1,
                   'protocol_sha256': sha(output / 'protocol.json'), 'native_cases': records,
                   'regional_cases': regional_cases, 'recipient_streams': len(publics),
                   'availability_model': AVAILABILITY, 'public_context_equal': True,
                   'regional_schedule_equal_IN_OUT': True, 'attack_fitted': False, 'privacy_result': None,
                   'final_artifacts_sha256': dict(frozen),
                   'scope': protocol['scope']}
        write(output / 'summary.json', summary)
        return summary
    except Exception as error:
        write(output / 'failed-summary.json', {'schema': 'ump.urban-privacy-channel-pilot.v1', 'status': 'failed',
              'completed_native_cases': list(records), 'completed_regional_cases': list(regional_cases),
              'error': str(error), 'scope': protocol['scope']})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--binary', type=Path, default=ROOT / 'simulator/build/AggregationReplay')
    parser.add_argument('--native-wall-budget-s', type=int, default=180)
    args = parser.parse_args()
    result = pilot(args.fixture, args.output, args.binary, wall_budget_s=args.native_wall_budget_s)
    print(json.dumps({'status': result['status'], 'native_cases': len(result['native_cases']), 'recipient_streams': result['recipient_streams']}))


if __name__ == '__main__':
    main()
