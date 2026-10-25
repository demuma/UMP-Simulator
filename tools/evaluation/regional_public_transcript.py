#!/usr/bin/env python3
"""Materialize recipient releases from four frozen, audited fixed native cases.

The schedule uses public policy/geometry only. Output is a derived recipient
transcript, never a native replay result, incremental runtime or timed scheduler.
The family manifest and the returned private audit are not attacker inputs.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import copy
import hashlib
import json
import os
from pathlib import Path
import re

import semantic_privacy
import static_regional_schedule as static
from semantic_suppression_audit import Catalog, SourceIndex, effective

FAMILY_SCHEMA = 'ump.regional-public-family.v1'
AUDIT_SCHEMA = 'ump.regional-public-composition-audit.v1'
require, read, sha, artifact = static.require, static.read, static.sha, static.artifact


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _keys(value, expected, label):
    require(isinstance(value, dict) and set(value) == set(expected), 'Unexpected ' + label + ' fields')


def _receipt(root, receipt, label, frozen):
    _keys(receipt, ('path', 'sha256'), label + ' receipt')
    digest = receipt['sha256']
    require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'Invalid ' + label + ' digest')
    path = artifact(root, receipt['path'])
    require(sha(path) == digest, label + ' receipt differs')
    require(path not in frozen or frozen[path] == digest, 'Conflicting artifact receipt')
    frozen[path] = digest
    return path


def _alias(value, label):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,127}', value),
            'Require a bounded declared public ' + label)
    require(not {'in', 'out', 'present', 'absent'} & set(re.split(r'[/_.-]', value.lower())),
            'Public aliases must be independent of membership/world labels')
    return value


def _policy_suffixes(coverage, config, depth):
    """Reconstruct native immutable preorder interning, including policy sources.

    Native pN identifies compiled bounds AND root/region/type sources. It is not
    a digest of bounds alone. IDs below validate native labels; output retains
    the actual native suffix and changes only its declared policy namespace.
    """
    regions = {r['id']: r for r in config.get('policy_regions', [])}
    selected = config['policy_tree']['regions']
    signatures = {}; nodes = {}; node_count = 0

    def visit(cid, level, geometry):
        nonlocal node_count
        node_count += 1
        require(node_count <= config['policy_tree'].get('max_nodes', 1000000), 'Policy compilation exceeds node budget')
        bounds, touched = effective(config, geometry)
        sources = ['root:' + config['policy_tree']['id']]
        for identity in touched:
            sources += ['region:' + identity, 'region_type:' + regions[identity]['type']]
        signature = canonical_sha(dict(bounds=bounds, sources=sorted(set(sources))))
        suffix = signatures.setdefault(signature, 'p' + str(len(signatures)))
        nodes[(cid, level)] = suffix
        homogeneous = all(regions[i]['x'] <= geometry['x'] and regions[i]['y'] <= geometry['y']
            and geometry['x'] + geometry['width'] <= regions[i]['x'] + regions[i]['width']
            and geometry['y'] + geometry['height'] <= regions[i]['y'] + regions[i]['height'] for i in touched)
        if homogeneous:
            return
        require(level < coverage['leaf_depth'], 'Policy boundary is not aligned with source leaves')
        for quadrant in range(4):
            child = dict(x=geometry['x'] + (quadrant & 1) * geometry['width'] / 2,
                         y=geometry['y'] + (quadrant >> 1) * geometry['height'] / 2,
                         width=geometry['width'] / 2, height=geometry['height'] / 2)
            visit((cid << 2) | quadrant, level + 1, child)

    require(len(selected) == len(set(selected)), 'Duplicate selected policy region')
    visit(3, 0, {key: coverage[key] for key in ('x', 'y', 'width', 'height')})
    result = {}
    for cid in range(3 * 4 ** depth, 4 * 4 ** depth):
        for level in range(depth, -1, -1):
            ancestor = cid >> (2 * (depth - level))
            if (ancestor, level) in nodes:
                result[cid] = nodes[(ancestor, level)]; break
    return result


def _native_public(result, config, plan, public_policy_id, availability_model):
    """Validate every native recipient field before selecting schedule cells."""
    semantic_privacy.export_public(result, config['semantic_taxonomy'], availability_model=availability_model)
    suffixes = _policy_suffixes(result['source']['coverage'], config, plan['depth'])
    native_id = config['policy_tree']['id']; version = config['policy_tree']['version']
    expected_prefix = native_id + '/' + version + '/'
    public = {}
    for release in result['releases']:
        require(release['policy_id'] == native_id and release['policy_version'] == version
                and release['model'] == 'private_final_snapshot', 'Native public policy/model metadata differs')
        require('coordination_cell' not in release, 'Fixed global sources cannot contain local coordination releases')
        for cell in release['cells']:
            cid = cell['cell_id']; identity = cell['effective_policy_id']
            require(cid in suffixes and identity == expected_prefix + suffixes[cid], 'Native effective policy identity differs')
            key = (cid, release['start_ms'], release['end_ms'])
            require(key not in public, 'Duplicate native public cell interval')
            normalized = copy.deepcopy(cell)
            normalized['effective_policy_id'] = public_policy_id + identity[len(native_id):]
            public[key] = (normalized, release)
    return public


def _verify_private_audit(data, config, plan, result, window, audit):
    """Recompute all four native partitions, including failed nonempty groups."""
    uniform = copy.deepcopy(plan)
    for row in uniform['cells'].values(): row['window_ms'] = window
    groups, total, _ = static.groups_for(data, uniform)
    records = static.native_records(data, uniform, result, window)
    require(set(records) == set(groups), 'Native private source partition differs')
    catalog, index = Catalog(config), SourceIndex(data)
    published = {}; bins = 0; retained = 0
    for key, rows in groups.items():
        passing, _, _ = static.check_group(data, config, catalog, index, uniform, key, rows, records[key])
        if passing:
            published[key] = records[key]['cell']; retained += len(rows)
            bins += len(records[key]['cell']['semantic']['categories'])
    scalar = audit.get('scalar', {})
    require(audit.get('status') == 'verified' and scalar.get('valid') is True
            and scalar.get('violations') == [] and audit.get('contribution_selection') == 'all_contributions'
            and audit.get('selectively_suppressed_observations') == 0, 'Native private audit is not verified OFF')
    require(audit.get('semantic_published_cells') == len(published)
            and audit.get('semantic_published_bins') == bins
            and scalar.get('input_observation_contributions') == total
            and scalar.get('released_observation_contributions') == retained
            and scalar.get('released_cell_count') == len(published), 'Native private audit count receipt differs')
    accounting = audit.get('source_accounting', {})
    require(accounting.get('input_observations') == total and accounting.get('retained_observations') == retained
            and accounting.get('selectively_suppressed_observations') == 0
            and accounting.get('whole_footprint_suppressed_observations') == total - retained,
            'Native private audit source accounting differs')
    recomputed = {}
    for row in audit.get('regional_recomputations', []):
        key = (row['cell_id'], row['start_ms'], row['end_ms'])
        require(key not in recomputed and key in published, 'Native private regional audit scope differs')
        recomputed[key] = row
        geometry = plan['cells'][key[0]]['geometry']; bounds, touched = effective(config, geometry)
        require(row.get('depth') == plan['depth'] and row.get('effective_requirements') == bounds
                and row.get('intersected_regions') == touched, 'Native private regional policy receipt differs')
        metrics = {k: v for k, v in published[key]['metrics'].items() if k != 'occupancy_mae'}
        static.recursively_equal(metrics, row.get('recomputed_metrics'), 'private_audit/recomputed_metrics')
    require(set(recomputed) == set(published), 'Native private regional audit is incomplete')


def compose_family(root, manifest, *, availability_model='final_snapshot_at_horizon', logical_sealing_evidence=None):
    """Compose one source/policy/grid family; return public channel + private audit.

    Manifest artifact paths are canonical relative to root. Public coverage,
    sampling period, horizon, grid, public policy ID and method alias must be
    declared independently of observations and shared across matched worlds.
    Logical sealing requires an explicit nonempty assumption/evidence statement.
    """
    root = Path(root); require(not root.is_symlink(), 'Family root cannot be symbolic'); root = root.resolve(strict=True)
    manifest = copy.deepcopy(manifest)
    _keys(manifest, ('schema', 'public_coverage', 'sampling_period_ms', 'end_ms', 'side_m',
        'public_policy_id', 'method_alias', 'source', 'native_binary', 'cases'), 'family manifest')
    require(manifest['schema'] == FAMILY_SCHEMA, 'Unsupported regional family manifest')
    require(availability_model in ('final_snapshot_at_horizon', 'logical_sealing'), 'Unsupported availability model')
    require(availability_model != 'logical_sealing' or isinstance(logical_sealing_evidence, str)
            and logical_sealing_evidence.strip(), 'Logical sealing requires declared assumption/evidence')
    public_id = _alias(manifest['public_policy_id'], 'policy ID'); _alias(manifest['method_alias'], 'method alias')
    require(type(manifest['end_ms']) is int and manifest['end_ms'] > 0
            and type(manifest['sampling_period_ms']) is int and manifest['sampling_period_ms'] > 0,
            'Invalid declared public cadence/horizon')
    require(isinstance(manifest['cases'], dict) and set(manifest['cases']) == {str(w) for w in static.WINDOWS},
            'Require exactly the four predeclared fixed native cases')
    frozen = {}; source_path = _receipt(root, manifest['source'], 'Source observations', frozen)
    _receipt(root, manifest['native_binary'], 'Source native binary', frozen)
    configs = {}; paths = {}; canonical = None
    # Plan is frozen before loading observations or native/public outcomes.
    for window in static.WINDOWS:
        case = manifest['cases'][str(window)]
        _keys(case, ('config', 'result', 'private_audit', 'independent_audit'), 'native case')
        checked = case['independent_audit']
        require(checked.get('status') == 'verified' and checked.get('scalar_valid') is True
                and checked.get('published_policy_violations') == 0, 'Native case lacks verified independent receipt')
        config_path = _receipt(root, case['config'], 'Native configuration', frozen)
        result_path = _receipt(root, case['result'], 'Native result', frozen)
        audit_path = _receipt(root, case['private_audit'], 'Native private audit', frozen)
        config = read(config_path); static.off_only(config)
        require(canonical is None or static.hard_policy(config) == static.hard_policy(canonical),
                'Fixed native cases differ in hard policy/configuration')
        canonical = config; configs[window] = config; paths[window] = (result_path, audit_path)
    plan = static.plan_schedule(manifest['public_coverage'], canonical, manifest['side_m'])
    plan_sha = canonical_sha(plan)
    data = read(source_path)
    require(data.get('schema') == 'ump.observation-replay.v1', 'Require an observation replay source')
    require(all(data.get(k) == manifest[k] for k in ('sampling_period_ms', 'end_ms'))
            and data.get('coverage') == manifest['public_coverage'], 'Source differs from declared public header')
    for value in (data.get('run_id'), data.get('sensor_id')):
        require(not value or value not in public_id and value not in manifest['method_alias'],
                'Public alias contains a private source identity')
    results = {}; native_public = {}
    for window in static.WINDOWS:
        result_path, audit_path = paths[window]; result = read(result_path)
        require(result.get('schema') == 'ump.replay-result.v1', 'Require an actual native replay result')
        native_public[window] = _native_public(result, configs[window], plan, public_id, availability_model)
        _verify_private_audit(data, configs[window], plan, result, window, read(audit_path))
        results[window] = result
    stats = static.compose(data, canonical, plan, results)
    grouped = defaultdict(list); selected_keys = set()
    for window in static.WINDOWS:
        for key, (cell, release) in native_public[window].items():
            if plan['cells'][key[0]]['window_ms'] != window: continue
            require(key not in selected_keys, 'Composed recipient support is duplicated'); selected_keys.add(key)
            group = (release['start_ms'], release['end_ms'], release['sealed_at_ms'],
                     release['model'], public_id, release['policy_version'])
            grouped[group].append(cell)
    releases = []
    for group, cells in sorted(grouped.items(), key=lambda item: (item[0][2], item[0][0], item[0][1], item[0][3:])):
        start, end, sealed, model, policy_id, version = group
        releases.append(dict(release_id='recipient-' + str(len(releases)), start_ms=start, end_ms=end,
            sealed_at_ms=sealed, model=model, policy_id=policy_id, policy_version=version,
            cells=sorted(cells, key=lambda c: (c['cell_id'], c['depth']))))
    public = semantic_privacy.export_releases(coverage=manifest['public_coverage'],
        sampling_period_ms=manifest['sampling_period_ms'], end_ms=manifest['end_ms'], releases=releases,
        taxonomy=canonical['semantic_taxonomy'], availability_model=availability_model)
    require(sum(c['observation_contributions'] for r in public['releases'] for c in r['cells'])
            == stats['retained_observation_contributions'] and len(selected_keys) == stats['published_cell_windows'],
            'Composed recipient payload and source accounting differ')
    for path, digest in frozen.items(): require(sha(path) == digest, 'Frozen source artifact changed during composition')
    require(canonical_sha(plan) == plan_sha, 'Declared policy-only schedule changed')
    positive_control = set(plan['cell_window_ms'].values()) == {4000}
    if positive_control:
        reference = []
        for release in results[4000]['releases']:
            row = copy.deepcopy(release); row['policy_id'] = public_id
            row['cells'] = [copy.deepcopy(native_public[4000][(c['cell_id'], row['start_ms'], row['end_ms'])][0]) for c in row['cells']]
            reference.append(row)
        expected = semantic_privacy.export_releases(coverage=manifest['public_coverage'],
            sampling_period_ms=manifest['sampling_period_ms'], end_ms=manifest['end_ms'], releases=reference,
            taxonomy=canonical['semantic_taxonomy'], availability_model=availability_model)
        require(public == expected, 'Uniform 4s positive control differs from native recipient transcript')
    audit = dict(schema=AUDIT_SCHEMA, status='verified', family_manifest_sha256=canonical_sha(manifest),
        source_artifacts=copy.deepcopy(manifest), policy_only_schedule_sha256=plan_sha,
        cell_window_ms=plan['cell_window_ms'], method_alias=manifest['method_alias'], stats=stats,
        positive_control_equal_native_4s=positive_control, native_runtime=None, native_process_wall_seconds=None,
        availability_model=availability_model, logical_sealing_assumption_evidence=logical_sealing_evidence,
        utility_timing_scope='Source-accounting delay/age metrics use native logical sealing, independently of recipient availability; snapshot receipt occurs at the declared horizon.',
        public_transcript_sha256=canonical_sha(public),
        policy_identity_remapping='Validated native immutable policy-tree pN; replace only native tree ID with the declared public policy ID. Preserve version and actual native pN.',
        grouping='Group identical (start,end,sealed,model,public policy ID,version); sort by sealed,start,end,public metadata, then cell ID.',
        scope='Derived recipient materialization from exact audited native public cells. No native execution, online scheduler, delivery measurement or privacy benefit is established.')
    return dict(public_transcript=public, private_audit=audit)


def study_family(study, source, policy, side, *, public_policy_id=None, method_alias=None):
    """Build one explicit family from the complete historical 44-case study."""
    root = Path(study); require(not root.is_symlink(), 'Study root cannot be symbolic'); root = root.resolve(strict=True)
    summary_path = artifact(root, 'summary.json'); protocol_path = artifact(root, 'protocol.json')
    summary, protocol = read(summary_path), read(protocol_path)
    require(summary.get('schema') == 'ump.temporal-region-study.v1' and summary.get('status') == 'verified'
        and summary.get('completion_scope') == 'all_44_predeclared_cases'
        and summary.get('executed_case_count') == summary.get('planned_case_count') == 44,
        'Require the full verified 44-case temporal-region study')
    require(summary.get('protocol') == protocol and summary.get('protocol_sha256') == sha(protocol_path), 'Study protocol receipt differs')
    require(source in static.SOURCES and policy in static.POLICIES and side in static.SIDES, 'Choose a declared study family')
    expected = {f'{s}_{p}_{method}' for s in static.SOURCES for p in static.POLICIES for method in
        [*(f'adaptive_{mode}' for mode in ('temporal_first', 'spatial_first', 'semantic_first')),
         *(f'fixed_{d}m_{w}ms' for d in static.SIDES for w in static.WINDOWS)]}
    require(set(summary.get('cases', {})) == expected, 'Study case matrix differs')
    def receipt(name, digest=None):
        path = artifact(root, name)
        return dict(path=name, sha256=sha(path) if digest is None else digest)
    # Historical public geometry/cadence/horizon are experiment declarations,
    # not schedule choices inferred from a realized observation stream.
    cases = {}
    for window in static.WINDOWS:
        identifier = f'{source}_{policy}_fixed_{side}m_{window}ms'; case = summary['cases'][identifier]
        cases[str(window)] = dict(config=receipt(identifier + '-policy.json', case['config_sha256']),
            result=receipt(identifier + '.json', case['result_sha256']),
            private_audit=receipt(identifier + '-private-audit.json'), independent_audit=copy.deepcopy(case['independent_audit']))
    return dict(schema=FAMILY_SCHEMA, public_coverage=copy.deepcopy(static.PUBLIC_COVERAGE),
        sampling_period_ms=100, end_ms=300000, side_m=side,
        public_policy_id=public_policy_id or 'temporal-region/' + policy,
        method_alias=method_alias or f'regional-static-{side}m',
        source=receipt(source + '-observations.json', protocol['sources'][source]['observations_sha256']),
        native_binary=receipt('provenance/AggregationReplay', protocol['native_binary_sha256']), cases=cases)



def compose_study(study, source='mixed', policy='control', side=20, *, public_policy_id=None,
                  method_alias=None, availability_model='final_snapshot_at_horizon', logical_sealing_evidence=None):
    """Compose a historical family while freezing its completed-study receipts."""
    root = Path(study).resolve(strict=True)
    study_receipts = {name: sha(artifact(root, name)) for name in ('summary.json', 'protocol.json')}
    manifest = study_family(study, source, policy, side, public_policy_id=public_policy_id, method_alias=method_alias)
    result = compose_family(study, manifest, availability_model=availability_model,
                            logical_sealing_evidence=logical_sealing_evidence)
    for name, digest in study_receipts.items():
        require(sha(artifact(root, name)) == digest, 'Frozen completed-study receipt changed')
    result['private_audit']['source_study_receipts_sha256'] = study_receipts
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--study', type=Path); source.add_argument('--family-manifest', type=Path)
    parser.add_argument('--source', choices=static.SOURCES, default='mixed')
    parser.add_argument('--policy', choices=static.POLICIES, default='control')
    parser.add_argument('--side', type=int, choices=static.SIDES, default=20)
    parser.add_argument('--public-policy-id'); parser.add_argument('--method-alias')
    parser.add_argument('--availability-model', choices=('final_snapshot_at_horizon', 'logical_sealing'), default='final_snapshot_at_horizon')
    parser.add_argument('--logical-sealing-evidence'); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    require(not output.exists() and not output.is_symlink(), 'Choose a fresh recipient output directory')
    if args.study:
        result = compose_study(args.study, args.source, args.policy, args.side,
            public_policy_id=args.public_policy_id, method_alias=args.method_alias,
            availability_model=args.availability_model, logical_sealing_evidence=args.logical_sealing_evidence)
    else:
        require(not args.family_manifest.is_symlink(), 'Manifest cannot be symbolic')
        root = args.family_manifest.resolve(strict=True).parent
        manifest_sha = sha(args.family_manifest); manifest = read(args.family_manifest)
        require(args.public_policy_id is None and args.method_alias is None, 'Family aliases must come from the frozen manifest')
        result = compose_family(root, manifest, availability_model=args.availability_model,
                                logical_sealing_evidence=args.logical_sealing_evidence)
        require(sha(args.family_manifest) == manifest_sha, 'Frozen family manifest changed')
    output.mkdir(parents=True, mode=0o700)
    for name, value in (('public.json', result['public_transcript']), ('private-audit.json', result['private_audit'])):
        descriptor = os.open(output / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps(dict(status='verified', releases=len(result['public_transcript']['releases']),
                         published_cell_windows=result['private_audit']['stats']['published_cell_windows'])))


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit('Regional recipient composition failed: ' + str(error))
