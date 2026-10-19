#!/usr/bin/env python3
"""Audit and compare two frozen coordination matrices without changing a controller.

This is a private research comparison. A complete frozen realization is the paired
unit. Conditional errors use each method's support plus an explicit old/new matched
support; neither zero-output policy compliance nor higher retention proves privacy.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

from occupancy import summarize_queries
from run_comparison import digest, scientific_result, write_json
from run_coordination_study import QUERY_PRESETS, STUDY_VARIANTS, matched_errors, query_subset

VARIANT_NAMES = tuple(variant[0] for variant in STUDY_VARIANTS)
REFERENCE_VARIANTS = VARIANT_NAMES[:7]
METRICS = ('retained_observation_fraction', 'answered_query_coverage', 'occupancy_mae',
           'mean_observation_age_ms', 'p95_observation_age_ms', 'core_processing_ms',
           'matched_occupancy_mae')


def read_json(path):
    return json.loads(Path(path).read_text())


def child(root, relative):
    """Manifest paths may name nested source files, but cannot escape a bundle."""
    root = Path(root).resolve()
    candidate = root / relative
    try:
        candidate.resolve().relative_to(root)
    except ValueError:
        raise ValueError('Manifest path escapes its bundle: ' + str(relative))
    if Path(relative).is_absolute() or not relative or str(relative) == '.':
        raise ValueError('Manifest path must be relative: ' + str(relative))
    return candidate


def verify_hash(path, expected):
    if not path.is_file() or digest(path) != expected:
        raise ValueError('Artifact hash mismatch: ' + str(path))


def load_bundle(directory):
    """Verify recorded provenance; stored independent audits are checked, not rerun."""
    directory = Path(directory).resolve(strict=True)
    manifest = read_json(directory / 'manifest.json')
    protocol = read_json(directory / 'protocol.json')
    summary = read_json(directory / 'summary.json')
    if manifest.get('schema') != 'ump.coordination-study-manifest.v1' \
            or protocol.get('schema') != 'ump.coordination-protocol.v1' \
            or summary.get('schema') != 'ump.coordination-study.v1':
        raise ValueError('Unsupported coordination study schema: ' + str(directory))
    verify_hash(directory / 'protocol.json', manifest['protocol_sha256'])
    verify_hash(directory / 'summary.json', manifest['summary_sha256'])
    verify_hash(directory / 'AggregationReplay', manifest['binary_sha256'])
    if summary['protocol_sha256'] != manifest['protocol_sha256'] \
            or protocol['binary_sha256'] != manifest['binary_sha256']:
        raise ValueError('Top-level protocol/binary hashes disagree')
    if not manifest.get('source_unchanged'):
        raise ValueError('Study did not record unchanged source during execution')
    for relative, expected in protocol['source_sha256'].items():
        verify_hash(child(directory / 'source', relative), expected)
    cases = protocol['case_order']
    if len(cases) != len(set(cases)) or set(cases) != set(summary['cases']) \
            or set(cases) != set(manifest['case_manifests']):
        raise ValueError('Top-level case sets differ or contain duplicate units')
    if [variant[0] for variant in protocol['variants']] != list(VARIANT_NAMES):
        raise ValueError('Study does not contain the nine declared configurations')
    if summary['completed_cases'] != len(cases) \
            or summary['audited_replays'] != len(cases) * len(VARIANT_NAMES) \
            or summary['deterministic_repeats'] != len(cases) * 4:
        raise ValueError('Recorded study execution counts are incomplete')
    files_verified = 3 + len(protocol['source_sha256'])
    case_manifests = {}
    for name in cases:
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('Unsafe case name: ' + str(name))
        case_dir = child(directory / 'cases', name)
        verify_hash(case_dir / 'manifest.json', manifest['case_manifests'][name])
        case_manifest = read_json(case_dir / 'manifest.json')
        if case_manifest.get('schema') != 'ump.coordination-case.v1':
            raise ValueError('Unsupported case schema: ' + name)
        artifacts = case_manifest['artifact_sha256']
        required = {'observations.json', 'policy.json', 'case.json', 'summary.json', 'pairs.json'}
        for variant in VARIANT_NAMES:
            required.update(variant + suffix for suffix in (
                '.json', '.policy.json', '.audit.json', '.metrics.json',
                '.primary.utility.json', '.fine.utility.json'))
        if not required.issubset(artifacts):
            raise ValueError('Case omits required artifact hashes: ' + name)
        for relative, expected in artifacts.items():
            verify_hash(child(case_dir, relative), expected)
        if case_manifest['input_sha256'] != artifacts['observations.json'] \
                or case_manifest['policy_sha256'] != artifacts['policy.json']:
            raise ValueError('Case input/policy hashes disagree: ' + name)
        records = case_manifest['variants']
        if len(records) != len(VARIANT_NAMES) or {v['name'] for v in records} != set(VARIANT_NAMES):
            raise ValueError('Case configuration set differs: ' + name)
        for record in records:
            variant = record['name']
            if record['config_sha256'] != artifacts[variant + '.policy.json'] \
                    or record['result_sha256'] != artifacts[variant + '.json']:
                raise ValueError('Case variant hashes disagree: ' + name + '/' + variant)
            audit = read_json(case_dir / (variant + '.audit.json'))
            if not record.get('independent_audit_valid') or not audit.get('valid'):
                raise ValueError('Case lacks a passing independent audit: ' + name + '/' + variant)
        if case_manifest.get('adaptive_deterministic_repeats') != 4:
            raise ValueError('Case lacks all four deterministic repeats: ' + name)
        case_summary = read_json(case_dir / 'summary.json')
        if case_summary != summary['cases'][name] or set(case_summary) != set(VARIANT_NAMES):
            raise ValueError('Top-level and case summaries disagree: ' + name)
        case_manifests[name] = case_manifest
        files_verified += 1 + len(artifacts)
    return dict(directory=directory, manifest=manifest, protocol=protocol, summary=summary,
                cases=case_manifests, files_verified=files_verified)


def paired_value(before, after):
    for value in (before, after):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value)):
            raise ValueError('Paired metrics must be finite numbers or undefined')
    return dict(before=before, after=after,
                delta_after_minus_before=after - before if before is not None and after is not None else None)


def query_comparison(before, after, coverage, end_ms):
    whole = [dict(id='all', **{key: coverage[key] for key in ('x', 'y', 'width', 'height')})]
    result = {}
    for horizon, start, end in [('full', 0, end_ms), ('interior', 1000, end_ms - 1000)]:
        first, second = query_subset(before, start, end), query_subset(after, start, end)
        shared = matched_errors(first, second)
        a = summarize_queries(first, whole)['regions'][0]
        b = summarize_queries(second, whole)['regions'][0]
        result[horizon] = dict(before=a, after=b,
            metrics={key: paired_value(a[key], b[key])
                     for key in ('answered_query_coverage', 'occupancy_mae')},
            matched=dict(scored_queries=shared['scored_queries'],
                **paired_value(shared['common_mae'], shared['local_mae'])))
    return result


def aggregate_pairs(pairs):
    groups = {}
    for pair in pairs:
        if pair['kind'] == 'replicate':
            groups.setdefault((pair['family'], pair['strategy']), []).append(pair)
    result = []
    for (family, strategy), group in sorted(groups.items()):
        metrics = {}
        for metric in METRICS:
            values = [pair['metrics'][metric]['delta_after_minus_before'] for pair in group
                      if pair['metrics'][metric]['delta_after_minus_before'] is not None]
            metrics[metric] = dict(n=len(values), mean=statistics.mean(values) if values else None,
                median=statistics.median(values) if values else None,
                min=min(values) if values else None, max=max(values) if values else None)
        result.append(dict(family=family, strategy=strategy, n=len(group), metrics=metrics))
    return result


def compare_studies(before_path, after_path, output):
    before, after = load_bundle(before_path), load_bundle(after_path)
    for key in ('case_order', 'seeds', 'variants', 'query_presets', 'horizons',
                'metrics', 'statistical_unit', 'reporting_regions', 'publication'):
        if before['protocol'][key] != after['protocol'][key]:
            raise ValueError('Study protocols differ in comparison definition: ' + key)
    pairs = []
    reference_checks = 0
    for name in before['protocol']['case_order']:
        a_dir, b_dir = before['directory'] / 'cases' / name, after['directory'] / 'cases' / name
        a_manifest, b_manifest = before['cases'][name], after['cases'][name]
        for relative in ['observations.json', 'policy.json', 'case.json'] \
                + [variant + '.policy.json' for variant in VARIANT_NAMES]:
            if a_manifest['artifact_sha256'][relative] != b_manifest['artifact_sha256'][relative]:
                raise ValueError('Frozen input or policy changed: ' + name + '/' + relative)
        for variant in REFERENCE_VARIANTS:
            if scientific_result(read_json(a_dir / (variant + '.json'))) \
                    != scientific_result(read_json(b_dir / (variant + '.json'))):
                raise ValueError('Unmodified reference scientific output changed: ' + name + '/' + variant)
            reference_checks += 1
        metadata, replay = read_json(a_dir / 'case.json'), read_json(a_dir / 'observations.json')
        a_summary, b_summary = before['summary']['cases'][name], after['summary']['cases'][name]
        for strategy in ('temporal_first', 'spatial_first'):
            variant = 'local_' + strategy
            metrics = {key: paired_value(a_summary[variant].get(key), b_summary[variant].get(key))
                       for key in METRICS if key != 'matched_occupancy_mae'}
            queries = {}
            for preset in QUERY_PRESETS:
                first = read_json(a_dir / (variant + '.' + preset + '.utility.json'))
                second = read_json(b_dir / (variant + '.' + preset + '.utility.json'))
                comparison = query_comparison(first, second, replay['coverage'], replay['end_ms'])
                queries.update({preset + '_' + horizon: values for horizon, values in comparison.items()})
            metrics['matched_occupancy_mae'] = queries['primary_full']['matched'].copy()
            metrics['matched_occupancy_mae'].pop('scored_queries')
            pairs.append(dict(case=name, kind=metadata['kind'], family=name.split('-seed-')[0],
                seed=metadata.get('seed'), strategy=strategy, metrics=metrics, queries=queries))
    report = dict(schema='ump.coordination-study-comparison.v1', classification='private_research_results',
        before=str(before['directory']), after=str(after['directory']),
        before_manifest_sha256=digest(before['directory'] / 'manifest.json'),
        after_manifest_sha256=digest(after['directory'] / 'manifest.json'),
        cases_verified=len(before['cases']), reference_outputs_identical=reference_checks,
        before_artifacts_hash_verified=before['files_verified'],
        after_artifacts_hash_verified=after['files_verified'],
        recorded_independent_audits_valid=True, pairs=pairs, aggregates=aggregate_pairs(pairs),
        definitions=dict(delta='after minus before', statistical_unit='complete frozen realization',
            occupancy='retrospective fixed-grid queries; unreported support remains unknown',
            matched_error='same old/new scored query intersection, separately for each preset/horizon',
            age='sealed_at_ms minus actual observed_at_ms, conditional on retained contributions',
            runtime='one descriptive core elapsed measurement; not a CPU or latency guarantee',
            privacy='policy support checks do not establish attack resistance or formal privacy'))
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    write_json(output / 'comparison.json', report)
    with (output / 'paired-results.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['case', 'kind', 'family', 'seed', 'strategy',
            'metric', 'before', 'after', 'delta_after_minus_before'])
        writer.writeheader()
        for pair in pairs:
            for metric, values in pair['metrics'].items():
                writer.writerow({key: pair[key] for key in ('case', 'kind', 'family', 'seed', 'strategy')}
                                | dict(metric=metric, **values))
    write_json(output / 'manifest.json', dict(schema='ump.coordination-comparison-manifest.v1',
        comparison_sha256=digest(output / 'comparison.json'),
        paired_results_sha256=digest(output / 'paired-results.csv'),
        before_manifest_sha256=report['before_manifest_sha256'],
        after_manifest_sha256=report['after_manifest_sha256']))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--after', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New private result directory')
    args = parser.parse_args()
    report = compare_studies(args.before, args.after, args.output)
    print(f'Compared {report["cases_verified"]} frozen cases; '
          f'{report["reference_outputs_identical"]} reference outputs identical: {args.output}', flush=True)


if __name__ == '__main__':
    main()
