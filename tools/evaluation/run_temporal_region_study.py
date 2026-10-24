#!/usr/bin/env python3
"""Freeze a paired local-freshness study on completed, unchanged observations.

The control removes only the old west/east temporal caps. The treatment adds a
400-ms window/age ceiling in the existing central region. All spatial, support,
semantic and taxonomy settings remain identical. No motion is generated.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import time

import run_spatial20_correction as correction
import report_spatial20_correction as compact

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ('mixed', 'pedestrians')
POLICIES = ('control', 'local400')
WINDOWS_MS = (400, 1000, 2000, 4000)
SIDES_M = (10, 20)
ADAPTIVE = ('temporal_first', 'spatial_first', 'semantic_first')
REGIONS = ('entrance-vicinity', 'west-footway-control', 'central-through-footway', 'east-footway-control')
PILOT = 'mixed_control_adaptive_temporal_first'
require, read, write, sha = correction.require, correction.read, correction.write, correction.sha


def matrix():
    methods = [dict(method='adaptive_' + mode, mode=mode) for mode in ADAPTIVE]
    methods += [dict(method=f'fixed_{side}m_{window}ms', mode='fixed', side_m=side, window_ms=window)
                for side in SIDES_M for window in WINDOWS_MS]
    return [dict(method, id=f'{source}_{policy}_{method["method"]}', source=source, policy=policy)
            for source in SOURCES for policy in POLICIES for method in methods]


def selected_cases(names):
    planned = matrix()
    if names is None or names == ['all']:
        return planned
    identifiers = {row['id'] for row in planned}
    require(isinstance(names, (list, tuple)) and names and len(set(names)) == len(names)
            and all(name in identifiers for name in names),
            'Choose unique predeclared local-freshness cases or all')
    return [row for row in planned if row['id'] in names]


def differences(before, after, path=''):
    """Exact JSON-pointer differences, including removals and metadata changes."""
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(set(before) | set(after)):
            child = path + '/' + key.replace('~', '~0').replace('/', '~1')
            if key not in before:
                changes.append(dict(path=child, operation='add', after=copy.deepcopy(after[key])))
            elif key not in after:
                changes.append(dict(path=child, operation='remove', before=copy.deepcopy(before[key])))
            else:
                changes.extend(differences(before[key], after[key], child))
        return changes
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [change for index, (old, new) in enumerate(zip(before, after))
                for change in differences(old, new, path + '/' + str(index))]
    return [] if before == after else [dict(path=path, operation='replace', before=copy.deepcopy(before), after=copy.deepcopy(after))]


def hard_policy(config):
    """Execution preferences and labels do not change the shared hard contract."""
    tree = config['policy_tree']
    return dict(root=copy.deepcopy(tree['root']), region_references=copy.deepcopy(tree['regions']),
                policy_regions=copy.deepcopy(config['policy_regions']), taxonomy=copy.deepcopy(config['semantic_taxonomy']))


def policy_pair(original):
    root = original['policy_tree']['root']
    require(original['window_ms'] == 400 and root['window_duration_ms'] == {'min': 400, 'max': 4000}
            and root['age_at_evaluation_ms'] == {'max': 4000}, 'Require the original 400-ms/4-s temporal contract')
    require(root.get('semantic_suppression_fraction') == {'max': 0}, 'Selective suppression must be OFF')
    regions = original.get('policy_regions', [])
    require(tuple(region['id'] for region in regions) == REGIONS
            and original['policy_tree']['regions'] == list(REGIONS), 'Expected the four frozen named regions')
    require(root['cell_side_m']['max'] == 20, 'Require the shared Spatial20 contract')
    for region in regions:
        for scope in ('type_requirements', 'requirements'):
            requirements = region.get(scope, {})
            require('cell_side_m' not in requirements or requirements['cell_side_m'].get('max', 20) == 20,
                    'All existing spatial maxima must already be 20 m')
            require('semantic_suppression_fraction' not in requirements
                    or requirements['semantic_suppression_fraction'] == {'max': 0}, 'Regional selective suppression must be OFF')
    control = copy.deepcopy(original)
    control['application_id'] = 'mapped-illustrative-temporal-region/control'
    control['policy_tree']['id'] = 'mapped-illustrative-temporal-region/control'
    for region in control['policy_regions']:
        if region['id'] not in ('west-footway-control', 'east-footway-control'):
            continue
        requirements = region['type_requirements']
        for metric in ('window_duration_ms', 'age_at_evaluation_ms'):
            require(requirements.get(metric) == {'max': 1000}, 'Expected the original west/east 1-s cap')
            del requirements[metric]
    # Assert the temporal control has no hidden local temporal ceiling.
    for region in control['policy_regions']:
        for scope in ('type_requirements', 'requirements'):
            require(all(metric not in region.get(scope, {}) for metric in ('window_duration_ms', 'age_at_evaluation_ms')),
                    'Unexpected remaining local temporal bound')
    treatment = copy.deepcopy(control)
    treatment['application_id'] = 'mapped-illustrative-temporal-region/local400'
    treatment['policy_tree']['id'] = 'mapped-illustrative-temporal-region/local400'
    central = next(region for region in treatment['policy_regions'] if region['id'] == 'central-through-footway')
    central['type_requirements']['window_duration_ms'] = {'max': 400}
    central['type_requirements']['age_at_evaluation_ms'] = {'max': 400}
    return dict(control=control, local400=treatment)


def method_config(base, row):
    config = copy.deepcopy(base)
    config['application_id'] += '/' + row['method']
    config['policy_tree']['id'] += '/' + row['method']
    execution = config['policy_tree']['execution']
    execution['strategy'] = 'semantic_first' if row['mode'] == 'fixed' else row['mode']
    execution['release_trigger'] = 'policy_satisfied'
    if execution['strategy'] == 'semantic_first':
        execution['semantic_secondary_strategy'] = 'temporal_first'
    else:
        execution.pop('semantic_secondary_strategy', None)
    require(hard_policy(config) == hard_policy(base), 'Method changed the shared hard policy')
    return config


def verify_correction(path):
    root = Path(path)
    require(not root.is_symlink(), 'Correction root cannot be symbolic')
    root = root.resolve(strict=True)
    summary = read(correction.safe_file(root, 'summary.json'))
    protocol_path = correction.safe_file(root, 'protocol.json')
    require(summary.get('schema') == 'ump.spatial20-correction.v1' and summary.get('status') == 'verified',
            'Require a completed verified controller correction')
    protocol = read(protocol_path)
    require(summary.get('protocol') == protocol and sha(protocol_path) == summary.get('protocol_sha256'),
            'Correction protocol or embedded receipt changed')
    require(summary.get('completion_scope') == 'all_16_predeclared_cases'
            and summary.get('executed_case_count') == summary.get('planned_case_count') == 16
            and set(summary.get('cases', {})) == {row['id'] for row in correction.matrix()},
            'Require the complete sixteen-case correction')
    correction.check_frozen(root, protocol['pre_execution_artifacts_sha256'])
    binary = correction.safe_file(root, 'provenance/AggregationReplay')
    require(sha(binary) == protocol.get('native_binary_sha256'), 'Correction binary changed')
    sources = {}
    for source in SOURCES:
        observations = correction.safe_file(root, source + '-observations.json')
        proof = correction.safe_file(root, 'provenance/' + source + '-capture-proof.json')
        metadata = protocol['sources'][source]
        require(sha(observations) == metadata['observations_sha256']
                and sha(proof) == metadata['capture_proof_sha256'], 'Correction source or capture proof changed')
        correction.mapped.validate_completed_source(read(proof))
        name = source + '_spatial20_adaptive_immediate_off'
        config_path = correction.safe_file(root, name + '-policy.json')
        case = summary['cases'][name]
        checked = case.get('independent_audit', {})
        require(checked.get('status') == 'verified' and checked.get('scalar_valid') is True
                and checked.get('published_policy_violations') == 0, 'Unverified canonical source policy')
        require(sha(config_path) == case['config_sha256'], 'Canonical correction policy changed')
        original = read(config_path)
        pairs = policy_pair(original)
        sources[source] = dict(observations=observations, proof=proof, original_config=original, policies=pairs,
                               metadata=copy.deepcopy(metadata), original_config_sha256=sha(config_path))
    return dict(root=root, summary=summary, summary_sha256=sha(root / 'summary.json'), protocol_sha256=sha(protocol_path),
                binary_sha256=sha(binary), sources=sources)


def paired_report(summary):
    """Aggregate-only contrasts; point-region cohorts are separate from cell tests."""
    rows = []
    pairs = []
    for row in matrix():
        case = summary['cases'].get(row['id'])
        if case is None:
            continue
        metrics = compact.checked_case(case, row['id'])
        rows.append(dict(source=row['source'], policy=row['policy'], method=row['method'], metrics=metrics))
    by_key = {(row['source'], row['policy'], row['method']): row['metrics'] for row in rows}
    for row in matrix():
        if row['policy'] != 'control':
            continue
        before = by_key.get((row['source'], 'control', row['method']))
        after = by_key.get((row['source'], 'local400', row['method']))
        if before is not None and after is not None:
            pairs.append(dict(source=row['source'], method=row['method'], control=before, local400=after,
                              treatment_minus_control=compact.changes(before, after)))
    return dict(schema='ump.temporal-region-aggregate-report.v1', status='verified_aggregate_consistency',
                completion_scope=summary['completion_scope'], executed_case_count=summary['executed_case_count'],
                planned_case_count=summary['planned_case_count'], cases=rows, paired_policy_effects=pairs,
                interpretation='Local temporal constraints are illustrative application requirements, not calibrated privacy protection. '
                               'Native fixed methods use one global schedule, with identical policy rejection. '
                               'A separately derived static regional schedule has no native execution-time claim.',
                privacy_scope=summary['protocol']['privacy_scope'])


def markdown(report):
    lines = ['# Paired local-freshness study', '', report['interpretation'], '',
             'All results use unchanged observations and suppression OFF. Percentages use the full input stream. '
             'Conditional loss and delay are undefined when nothing is retained.', '',
             '| Source | Policy | Method | Retained % | Full-input loss % | Conditional loss % | Delay mean / p95 ms | Core ms |',
             '|---|---|---|---:|---:|---:|---:|---:|']
    def value(number, scale=1):
        return 'n/a' if number is None else f'{number * scale:.3f}'
    for row in report['cases']:
        item = row['metrics']
        lines.append('| ' + ' | '.join([row['source'], row['policy'], row['method'], value(item['retained_fraction'], 100),
                     value(item['full_input_semantic_distortion'], 100), value(item['retained_only_semantic_loss'], 100),
                     value(item['retained_delay_mean_ms']) + ' / ' + value(item['retained_delay_p95_ms']), value(item['core_processing_ms'])]) + ' |')
    lines += ['', '## Paired effect of the central 400-ms cap', '',
              '| Source | Method | Retention change pp | Full-input loss change pp | Central retained change |',
              '|---|---|---:|---:|---:|']
    for row in report['paired_policy_effects']:
        delta = row['treatment_minus_control']
        central = delta['source_point_regions'].get('central-through-footway', {})
        lines.append('| ' + ' | '.join([row['source'], row['method'], value(delta['retained_fraction'], 100),
                     value(delta['full_input_semantic_distortion'], 100), str(central.get('retained_observation_delta', 'n/a'))]) + ' |')
    lines += ['', 'The reported source-point regions describe observation cohorts. Policy compliance uses conservative '
              'positive-area intersections of complete cell footprints; neighboring observations may therefore be affected.',
              '', 'Operational support and hard-policy compliance are measured. No attack-based or formal privacy gain is claimed.', '']
    return '\n'.join(lines)


def study(correction_dir, output, binary, *, cases=None, wall_budget_s=240):
    require(type(wall_budget_s) is int and 1 <= wall_budget_s <= 240, 'Native wall budget must be an integer from 1 to 240 seconds')
    selected = selected_cases(cases)
    planned = matrix()
    output = Path(output)
    require(not output.exists() and not output.is_symlink(), 'Choose a fresh study directory')
    binary = Path(binary).resolve()
    require(binary.is_file(), 'Build AggregationReplay first')
    reference = verify_correction(correction_dir)
    output = output.resolve()
    require(not output.is_relative_to(reference['root']) and not reference['root'].is_relative_to(output),
            'Study output must be separate from the correction evidence')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    provenance = output / 'provenance'
    provenance.mkdir()
    shutil.copy2(binary, provenance / 'AggregationReplay')
    for name in ('run_temporal_region_study.py', 'run_spatial20_correction.py', 'report_spatial20_correction.py',
                 'run_local_policy_replay.py'):
        shutil.copyfile(ROOT / 'tools/evaluation' / name, provenance / name)
    shutil.copyfile(ROOT / 'tools/mapped_scene/run_comparison.py', provenance / 'mapped_run_comparison.py')
    for relative in ('simulator/src/CellLocalAggregation.cpp', 'simulator/include/CellLocalAggregation.hpp',
                     'simulator/src/PolicyTree.cpp', 'simulator/include/PolicyTree.hpp',
                     'simulator/src/CandidateMetrics.cpp', 'simulator/include/CandidateMetrics.hpp',
                     'simulator/tools/AggregationReplay.cpp'):
        shutil.copyfile(ROOT / relative, provenance / Path(relative).name)
    source_info = {}
    coverages = {}
    for source, details in reference['sources'].items():
        shutil.copyfile(details['observations'], output / (source + '-observations.json'))
        coverages[source] = read(output / (source + '-observations.json'))['coverage']
        shutil.copyfile(details['proof'], provenance / (source + '-capture-proof.json'))
        source_info[source] = dict(observations_sha256=sha(details['observations']),
                                  capture_proof_sha256=sha(details['proof']),
                                  original_config_sha256=details['original_config_sha256'],
                                  control_changes_from_correction=differences(details['original_config'], details['policies']['control']),
                                  treatment_changes_from_control=differences(details['policies']['control'], details['policies']['local400']),
                                  **{key: details['metadata'][key] for key in ('horizon_ms', 'sampling_period_ms',
                                     'input_observation_contributions', 'peak_observed_simultaneous_tracks')})
    # Correction commands are the explicit provenance when the wrapper did not
    # duplicate the common progress cadence as a top-level field.
    command_steps = {command[command.index('--progress-step-ms') + 1]
                     for command in reference['summary']['protocol']['commands']}
    require(len(command_steps) == 1, 'Correction native progress cadences differ')
    step = int(next(iter(command_steps)))
    require(step > 0, 'Invalid native progress cadence')
    configs = {}
    commands = {}
    for row in planned:
        source = row['source']
        config = method_config(reference['sources'][source]['policies'][row['policy']], row)
        path = output / (row['id'] + '-policy.json')
        write(path, config)
        configs[row['id']] = path
        command = [str(provenance / 'AggregationReplay'), '--input', str(output / (source + '-observations.json')),
                   '--config', str(path), '--mode', row['mode'], '--output', str(output / (row['id'] + '.json')),
                   '--progress-step-ms', str(step)]
        if row['mode'] == 'fixed':
            # Depth is computed from the exact frozen square geometry, never a
            # guessed side/depth conversion. This read occurs before execution.
            command += ['--fixed-depth', str(correction.mapped.fixed_depth(coverages[source], row['side_m'])),
                        '--fixed-window-ms', str(row['window_ms'])]
        commands[row['id']] = command
    frozen = {str(path.relative_to(output)): sha(path) for path in output.rglob('*') if path.is_file()}
    binary_sha = sha(binary)
    protocol = dict(schema='ump.temporal-region-protocol.v1', matrix=planned, selected_cases=[row['id'] for row in selected],
                    commands=commands, progress_step_ms=step, native_binary_sha256=binary_sha,
                    correction_binary_sha256=reference['binary_sha256'],
                    native_binary_matches_correction=binary_sha == reference['binary_sha256'],
                    correction_summary_sha256=reference['summary_sha256'], correction_protocol_sha256=reference['protocol_sha256'],
                    sources=source_info, pre_execution_artifacts_sha256=frozen, native_process_wall_budget_s=wall_budget_s,
                    offline_audit_max_cells=1000000,
                    predeclared_factor='Only local temporal freshness differs between control and local400; all spatial maxima are 20 m.',
                    policy_scope='Illustrative application policies, not empirical privacy calibration. Every method receives identical hard rules.',
                    fixed_scope='Global fixed 10/20-m schedules at 0.4/1/2/4 s; taxonomy generalization and policy rejection remain active. '
                                'Regional static schedules, if separately derived, must not claim native runtime.',
                    strategy_scope='Temporal First preserves temporal accuracy; Spatial First preserves spatial accuracy. '
                                   'Semantic First uses Temporal First secondary. Every adaptive method releases when its policy is satisfied.',
                    runtime_scope='Unpaced native subprocess wall time and native processing_ms, excluding movement generation, '
                                  'Python audits and report writing; not a real-time deadline guarantee.',
                    privacy_scope='Operational track/category support and hard-policy fulfillment only; no formal or empirical privacy-gain claim.',
                    source_scope='Two complete unchanged correction source streams; horizon recorded per source. Selective suppression OFF, no motion regeneration or source selection.')
    write(output / 'protocol.json', protocol)
    protocol_sha = sha(output / 'protocol.json')
    summary = dict(schema='ump.temporal-region-study.v1', status='running', protocol=protocol, protocol_sha256=protocol_sha,
                   planned_case_count=len(planned), executed_case_count=0, scientific_repetitions=0, cases={})
    current_source = None
    data = None
    for row in selected:
        identifier = row['id']
        correction.check_frozen(output, frozen)
        require(sha(binary) == binary_sha, 'Native binary changed after protocol freeze')
        if current_source != row['source']:
            data = read(output / (row['source'] + '-observations.json'))
            correction.mapped.validate_completed_source(read(provenance / (row['source'] + '-capture-proof.json')), data)
            current_source = row['source']
        config = read(configs[identifier])
        command = commands[identifier]
        start = time.perf_counter()
        try:
            completed = subprocess.run(command, text=True, capture_output=True, timeout=wall_budget_s)
            wall = time.perf_counter() - start
        except subprocess.TimeoutExpired as error:
            write(output / (identifier + '-execution.json'), dict(command=command, status='native_timeout', wall_budget_s=wall_budget_s))
            raise RuntimeError(identifier + ': native wall budget exhausted') from error
        (output / (identifier + '.log')).write_text(completed.stdout + completed.stderr)
        write(output / (identifier + '-execution.json'), dict(command=command, returncode=completed.returncode,
              native_process_wall_seconds=wall, timing_scope=protocol['runtime_scope']))
        require(completed.returncode == 0, identifier + ': native execution failed: ' + completed.stderr[:2000])
        correction.check_frozen(output, frozen)
        result_path = output / (identifier + '.json')
        result = read(result_path)
        audited_config = copy.deepcopy(config)
        audited_config['temporal_adaptation']['coordination'] = result['parameters']['coordination']
        checked = correction.audit(data, audited_config, result, max_cells=1000000)
        stats = correction.summarize(data, config, result, checked)
        # Explicit no-filtering assertion lets the point-matching accounting
        # independently recompute regional cohorts and release delay unchanged.
        require(stats['selectively_suppressed_observation_contributions'] == 0, 'Unexpected selective suppression')
        point_accounting = correction.mapped.source_accounting(data, config, result)
        for key in ('by_source_type', 'by_source_point_region', 'region_scope', 'observation_to_release_delay_ms'):
            stats['source_accounting'][key] = point_accounting[key]
        write(output / (identifier + '-private-audit.json'), checked)
        summary['cases'][identifier] = dict(row, stats=stats,
            independent_audit=dict(status=checked['status'], scalar_valid=checked['scalar']['valid'],
                                  semantic_published_cells=checked['semantic_published_cells'], published_policy_violations=0),
            native_process_wall_seconds=wall, native_runtime=result.get('runtime', {}),
            result_sha256=sha(result_path), config_sha256=sha(configs[identifier]))
        print(json.dumps(dict(case=identifier, status='verified', retained_fraction=stats['retained_fraction'],
                             full_input_semantic_distortion=stats['full_input_semantic_distortion'], native_process_wall_seconds=wall)), flush=True)
        del result, checked
    correction.check_frozen(output, frozen)
    require(sha(output / 'protocol.json') == protocol_sha and sha(binary) == binary_sha, 'Frozen protocol or binary changed')
    require(sha(reference['root'] / 'summary.json') == reference['summary_sha256']
            and sha(reference['root'] / 'protocol.json') == reference['protocol_sha256'], 'Correction reference changed during study')
    correction.check_frozen(reference['root'], reference['summary']['protocol']['pre_execution_artifacts_sha256'])
    for details in reference['sources'].values():
        require(sha(details['observations']) == details['metadata']['observations_sha256'], 'Correction observations changed during study')
    summary.update(status='verified', executed_case_count=len(selected),
                   completion_scope='all_44_predeclared_cases' if len(selected) == len(planned) else 'explicit_predeclared_subset')
    report = paired_report(summary)
    write(output / 'summary.json', summary)
    write(output / 'aggregate-report.json', report)
    (output / 'report.md').write_text(markdown(report), encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--correction', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--binary', type=Path, default=ROOT / 'simulator/build/AggregationReplay')
    parser.add_argument('--cases', nargs='+', default=['all'], help='all or unique predeclared IDs; pilot: ' + PILOT)
    parser.add_argument('--native-wall-budget-s', type=int, default=240)
    args = parser.parse_args()
    result = study(args.correction, args.output, args.binary, cases=args.cases, wall_budget_s=args.native_wall_budget_s)
    print(json.dumps(dict(status=result['status'], completion_scope=result['completion_scope'], executed_case_count=result['executed_case_count'])))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        raise SystemExit('Local-freshness study failed: ' + str(error))
