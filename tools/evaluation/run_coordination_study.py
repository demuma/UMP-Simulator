#!/usr/bin/env python3
"""Frozen, paired common-window versus cell-local aggregation experiments.

All outputs are private research artifacts. This runner changes configurations and
measurement only; it does not alter aggregation decisions or establish privacy.
"""
import argparse
from copy import deepcopy
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import statistics
import sys

from coordination_metrics import summarize as coordination_summary
from coordination_scenarios import (PREDECLARED_SEEDS, make_case, scenarios,
                                    replicate_scenarios, validate_case)
from occupancy import evaluate, summarize_queries, summarize_region_retention
from oracle import validate_result
from run_comparison import VARIANTS, digest, git_state, run_variant, scientific_result, summarize, write_json

ROOT = Path(__file__).resolve().parents[2]
STUDY_VARIANTS = [(name, mode, depth, window, 'common_window')
                  for name, mode, depth, window in VARIANTS[:5]] + [
    (coord + '_' + strategy, strategy, None, None, coordination)
    for coord, coordination in [('common', 'common_window'), ('local', 'cell_local')]
    for strategy in ('temporal_first', 'spatial_first')]
QUERY_PRESETS = {'primary': (10, 1000), 'fine': (5, 200)}
METRICS = ('retained_observation_fraction', 'answered_query_coverage', 'occupancy_mae',
           'mean_observation_age_ms', 'p95_observation_age_ms', 'core_processing_ms',
           'matched_occupancy_mae')


def effective_policy(policy, variant):
    """Explicit reference coordination avoids an ambiguous oracle configuration."""
    _, mode, _, _, coordination = variant
    result = deepcopy(policy)
    result['temporal_adaptation']['coordination'] = coordination
    if mode in ('temporal_first', 'spatial_first'):
        result['policy_tree']['execution']['strategy'] = mode
    return result


def matched_errors(common, local):
    """Compare identical scored queries, while preserving full-domain denominators."""
    if common['reference'] != local['reference']:
        raise ValueError('Paired utility queries have different reference definitions')
    if len(common['queries']) != len(local['queries']):
        raise ValueError('Paired query counts differ')
    rows = []
    identity = ('column', 'row', 'start_ms', 'end_ms')
    for first, second in zip(common['queries'], local['queries']):
        if any(first[key] != second[key] for key in identity):
            raise ValueError('Paired queries are not aligned')
        if first['absolute_error'] is not None and second['absolute_error'] is not None:
            rows.append((first['absolute_error'], second['absolute_error']))
    return dict(scored_queries=len(rows),
                common_mae=statistics.mean(row[0] for row in rows) if rows else None,
                local_mae=statistics.mean(row[1] for row in rows) if rows else None)


def paired_value(common, local):
    return dict(common=common, local=local,
                delta_local_minus_common=local - common if common is not None and local is not None else None)


def query_subset(evaluation, start, end):
    result = dict(evaluation)
    result['queries'] = [query for query in evaluation['queries']
                         if query['start_ms'] >= start and query['end_ms'] <= end]
    return result


def case_pairs(case_name, case, summaries, utilities):
    pairs = []
    coverage = case['observations']['coverage']
    whole = [dict(id='all', **{k: coverage[k] for k in ('x', 'y', 'width', 'height')})]
    for strategy in ('temporal_first', 'spatial_first'):
        first, second = 'common_' + strategy, 'local_' + strategy
        metrics = {key: paired_value(summaries[first].get(key), summaries[second].get(key))
                   for key in METRICS if key != 'matched_occupancy_mae'}
        query_comparisons = {}
        for preset in QUERY_PRESETS:
            common, local = utilities[first][preset], utilities[second][preset]
            for horizon, start, end in [('full', 0, case['observations']['end_ms']),
                                        ('interior', 1000, case['observations']['end_ms'] - 1000)]:
                a, b = query_subset(common, start, end), query_subset(local, start, end)
                shared = matched_errors(a, b)
                query_comparisons[preset + '_' + horizon] = dict(
                    common=summarize_queries(a, whole)['regions'][0],
                    local=summarize_queries(b, whole)['regions'][0], matched=shared)
        matched = query_comparisons['primary_full']['matched']
        metrics['matched_occupancy_mae'] = paired_value(matched['common_mae'], matched['local_mae'])
        pairs.append(dict(case=case_name, kind=case['kind'],
                          family=case_name.split('-seed-')[0], seed=case.get('seed'),
                          strategy=strategy, metrics=metrics, queries=query_comparisons))
    return pairs


def run_case(binary, output, name, case, rotation=0):
    """One frozen source and numerical policy, nine configurations, four repeats."""
    validate_case(case)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    replay, policy = case['observations'], case['policy']
    write_json(output / 'observations.json', replay)
    write_json(output / 'policy.json', policy)
    write_json(output / 'case.json', {key: value for key, value in case.items()
                                      if key not in ('observations', 'policy')})
    coverage = replay['coverage']
    regions = case['regions'] + [dict(id='all', **{key: coverage[key]
                                  for key in ('x', 'y', 'width', 'height')})]
    summaries, utilities, results, variants = {}, {}, {}, []
    ordered = STUDY_VARIANTS[rotation:] + STUDY_VARIANTS[:rotation]
    for variant in ordered:
        variant_name, mode, depth, window, _ = variant
        config = effective_policy(policy, variant)
        config_path = output / (variant_name + '.policy.json')
        write_json(config_path, config)
        destination = output / (variant_name + '.json')
        result, command = run_variant(binary, output / 'observations.json', config_path,
                                      destination, mode, depth, window)
        audit = validate_result(replay, config, result)
        write_json(output / (variant_name + '.audit.json'), audit)
        if not audit['valid']:
            raise ValueError(f'{name}/{variant_name}: independent audit failed: {audit["violations"][:3]}')
        utilities[variant_name] = {}
        for preset, (side, duration) in QUERY_PRESETS.items():
            utility = evaluate(replay, result, side, duration)
            utilities[variant_name][preset] = utility
            write_json(output / (variant_name + '.' + preset + '.utility.json'), utility)
        primary = utilities[variant_name]['primary']
        timing = coordination_summary(result)
        retention = summarize_region_retention(replay, result, regions)
        global_retention = next(region for region in retention['regions'] if region['id'] == 'all')
        exact_age = global_retention['simulated_observation_age_ms']
        summary = summarize(result, primary)
        summary.update(mean_observation_age_ms=exact_age['mean'], p95_observation_age_ms=exact_age['p95'],
                       public_result_bytes=destination.stat().st_size,
                       independently_audited=True)
        # The result contains private terminal diagnostics as well as public releases.
        summary['private_replay_result_bytes'] = summary.pop('public_result_bytes')
        details = dict(timing=timing, private_source_retention=retention,
                       regional_queries={preset: summarize_queries(utility, case['regions'])
                                         for preset, utility in utilities[variant_name].items()})
        write_json(output / (variant_name + '.metrics.json'), details)
        summaries[variant_name], results[variant_name] = summary, result
        variants.append(dict(name=variant_name, command=command, config_sha256=digest(config_path),
                             result_sha256=digest(destination), independent_audit_valid=True))
    # Repeat both priorities under both coordination models, excluding runtime only.
    for variant in STUDY_VARIANTS[5:]:
        variant_name, mode, depth, window, _ = variant
        repeated_path = output / (variant_name + '.repeat.json')
        repeated, _ = run_variant(binary, output / 'observations.json',
            output / (variant_name + '.policy.json'), repeated_path, mode, depth, window)
        if scientific_result(repeated) != scientific_result(results[variant_name]):
            raise ValueError(f'{name}/{variant_name}: scientific output is nondeterministic')
        repeated_path.unlink()
    pairs = case_pairs(name, case, summaries, utilities)
    write_json(output / 'summary.json', summaries)
    write_json(output / 'pairs.json', pairs)
    write_json(output / 'manifest.json', dict(schema='ump.coordination-case.v1',
        classification='private_research_bundle', input_sha256=digest(output / 'observations.json'),
        policy_sha256=digest(output / 'policy.json'), variants=variants,
        adaptive_deterministic_repeats=4,
        artifact_sha256={p.name: digest(p) for p in sorted(output.iterdir()) if p.is_file()}))
    return pairs, summaries


def aggregate_pairs(pairs):
    """The independent realization is the unit, never windows or road users."""
    groups = {}
    for pair in pairs:
        if pair['kind'] == 'replicate':
            groups.setdefault((pair['family'], pair['strategy']), []).append(pair)
    output = []
    for (family, strategy), group in sorted(groups.items()):
        metrics = {}
        for metric in METRICS:
            values = [pair['metrics'][metric]['delta_local_minus_common'] for pair in group
                      if pair['metrics'][metric]['delta_local_minus_common'] is not None]
            metrics[metric] = dict(n=len(values), mean=statistics.mean(values) if values else None,
                                  median=statistics.median(values) if values else None,
                                  min=min(values) if values else None, max=max(values) if values else None)
        output.append(dict(family=family, strategy=strategy, n=len(group), metrics=metrics))
    return output


def source_files(root):
    files = [root / 'simulator/CMakeLists.txt', root / 'simulator/tools/AggregationReplay.cpp']
    files += sorted((root / 'simulator/src').glob('*.cpp'))
    files += sorted((root / 'simulator/include').glob('*.*'))
    files += sorted((root / 'tools/evaluation').glob('*.py'))
    return [path for path in files if path.is_file()]


def run_study(output, binary, names, seeds):
    if len(set(names)) != len(names) or len(set(seeds)) != len(seeds):
        raise ValueError('Duplicate scenario names or seeds are not independent replications')
    if not names or not seeds:
        raise ValueError('Select at least one scenario and one seed')
    cases = []
    for name in names:
        if name in scenarios():
            cases.append((name, make_case(name)))
        elif name in replicate_scenarios():
            cases += [(f'{name}-seed-{seed}', make_case(name, seed)) for seed in seeds]
        else:
            raise ValueError('Unknown scenario: ' + name)
    for _, case in cases:
        validate_case(case)
    binary = binary.resolve(strict=True)
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in source_files(ROOT)}
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    frozen_binary = output / 'AggregationReplay'
    shutil.copy2(binary, frozen_binary)
    snapshot = output / 'source'
    for relative in hashes:
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
        if digest(destination) != hashes[relative]:
            raise ValueError('Source changed during freezing: ' + relative)
    protocol = dict(schema='ump.coordination-protocol.v1', classification='private_research_protocol',
        created_utc=datetime.now(timezone.utc).isoformat(), git=git_state(ROOT),
        platform=platform.platform(), python=sys.version,
        binary_sha256=digest(frozen_binary), source_sha256=hashes,
        case_order=[name for name, _ in cases], seeds=seeds, variants=STUDY_VARIANTS,
        execution='serial cyclic rotation by case index; four adaptive scientific repeats per case',
        query_presets=QUERY_PRESETS, horizons=dict(primary='full recorded horizon including EOF finalization',
            supplementary='query intervals contained in [1000,end_ms-1000)'),
        metrics=list(METRICS), statistical_unit='independent complete frozen realization, paired across methods',
        reporting_regions='four fixed disjoint 40m quadrants; query footprints must be fully contained',
        publication='private_final_snapshot, immediate offline acknowledgement; no sink/network delay',
        interpretation=['retrospective occupancy; no online availability guarantee',
            'undefined and unreported support is unknown, never zero',
            'age is simulated sealed_at minus actual observed_at, conditional on retained observations',
            'support thresholds are policy requirements, not empirical or formal privacy',
            'mechanism cases explain conditions; seeded synthetic families are exploratory',
            'MAE on full conditional support and paired common support are both reported',
            'no asynchronous optimality oracle or publication-opportunity regret is computed',
            'runtime is a single descriptive elapsed core measurement, not a CPU benchmark'])
    # This immutable protocol precedes every replay execution.
    write_json(output / 'protocol.json', protocol)
    pairs, case_summaries = [], {}
    try:
        for index, (name, case) in enumerate(cases):
            print(f'[{index + 1}/{len(cases)}] {name}', flush=True)
            case_pairs_result, summaries = run_case(frozen_binary, output / 'cases' / name,
                                                    name, case, index % len(STUDY_VARIANTS))
            pairs.extend(case_pairs_result)
            case_summaries[name] = summaries
        changed = [relative for relative, value in hashes.items() if digest(ROOT / relative) != value]
        if changed:
            raise ValueError('Source changed during study: ' + ', '.join(changed))
        summary = dict(schema='ump.coordination-study.v1', classification='private_research_results',
            protocol_sha256=digest(output / 'protocol.json'), cases=case_summaries,
            pairs=pairs, aggregates=aggregate_pairs(pairs), completed_cases=len(cases),
            audited_replays=len(cases) * len(STUDY_VARIANTS), deterministic_repeats=len(cases) * 4)
        write_json(output / 'summary.json', summary)
        with (output / 'paired-results.csv').open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['case', 'kind', 'family', 'seed', 'strategy',
                                                       'metric', 'common', 'local', 'delta_local_minus_common'])
            writer.writeheader()
            for pair in pairs:
                for metric, values in pair['metrics'].items():
                    writer.writerow({key: pair[key] for key in ('case', 'kind', 'family', 'seed', 'strategy')}
                                    | dict(metric=metric, **values))
        write_json(output / 'manifest.json', dict(schema='ump.coordination-study-manifest.v1',
            completed_utc=datetime.now(timezone.utc).isoformat(), source_unchanged=True,
            binary_sha256=digest(frozen_binary), protocol_sha256=digest(output / 'protocol.json'),
            summary_sha256=digest(output / 'summary.json'),
            case_manifests={name: digest(output / 'cases' / name / 'manifest.json') for name, _ in cases}))
    except Exception as error:
        write_json(output / 'failure.json', dict(error_type=type(error).__name__, message=str(error),
                   completed_cases=list(case_summaries)))
        raise
    print(f'Completed {len(cases)} cases, {summary["audited_replays"]} audited replays, '
          f'{summary["deterministic_repeats"]} deterministic repeats: {output}', flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New private result directory')
    parser.add_argument('--binary', type=Path, default=ROOT / 'simulator/build/AggregationReplay')
    parser.add_argument('--scenarios', nargs='+', default=scenarios() + replicate_scenarios())
    parser.add_argument('--seeds', nargs='+', type=int, default=list(PREDECLARED_SEEDS))
    args = parser.parse_args()
    run_study(args.output.resolve(), args.binary, args.scenarios, args.seeds)


if __name__ == '__main__':
    main()
