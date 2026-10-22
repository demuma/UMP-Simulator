#!/usr/bin/env python3
"""Diagnose the frozen moving pilot under an explicit recipient query contract.

No producer is rerun and no source, policy, release, or legacy exact score changes.
Public support certificates and a separately declared uniform estimator are
evaluated on the original fixed query cohorts. Only compact summaries are saved.
"""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import shutil

import recipient_support as recipient
import run_moving_scoped_comparison as parent
import scoped_semantic_queries as exact


ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
PROTOCOL = 'docs/RECIPIENT_CONTRACT_PROTOCOL_2026-10-23.md'
SCHEMA = 'ump.recipient-contract-study.v1'
PARENT_MANIFEST_SHA256 = 'e81b724b673ac5f8e77ddd483b41b4ec2756206fbd32ccf2455e14bd234dc83f'
SOURCE_SHA256 = parent.SOURCE_SHA256
DEPENDENCIES = tuple(dict.fromkeys((
    'tools/evaluation/run_recipient_contract_study.py',
    'tools/evaluation/recipient_support.py',
) + parent.DEPENDENCIES))
QUERY_KEYS = ('target_cells', 'categories', 'window_ms', 'lags_ms')
digest, read_json, write_json = parent.digest, parent.read_json, parent.write_json


def _file(root, name):
    """Only canonical relative artifact paths inside their frozen directory."""
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError('Artifact path must be a nonempty relative path')
    candidate = Path(root) / name
    if '..' in Path(name).parts or not candidate.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Artifact path escapes the frozen directory')
    if not candidate.is_file():
        raise ValueError('Required frozen artifact is missing: ' + name)
    return candidate


def _artifact_hashes(directory, manifest, names):
    declared = manifest.get('artifacts_sha256')
    if not isinstance(declared, dict):
        raise ValueError('Parent manifest has no artifact digests')
    verified = {}
    for name in sorted(set(names)):
        expected = declared.get(name)
        if not isinstance(expected, str) or digest(_file(directory, name)) != expected:
            raise ValueError('Parent artifact digest is missing or mismatched: ' + name)
        verified[name] = expected
    return verified


def verify_parent(directory, capture=None):
    directory = Path(directory).resolve()
    manifest_path = _file(directory, 'study-manifest.json')
    if digest(manifest_path) != PARENT_MANIFEST_SHA256:
        raise ValueError('Parent manifest differs from the frozen comparison')
    manifest = read_json(manifest_path)
    if (manifest.get('schema') != parent.SCHEMA or manifest.get('status') != 'verified'
            or manifest.get('evaluation_count') != 40 or manifest.get('paired_comparison_count') != 24
            or manifest.get('source_capture_unchanged') is not True):
        raise ValueError('Require the verified complete moving comparison')
    matrix = parent.variants()
    declared = parent.workloads(parent.config_for(matrix[0]))
    if manifest.get('variants') != matrix or manifest.get('workloads') != declared:
        raise ValueError('Parent matrix or fixed query workloads changed')
    source_hashes = manifest.get('source_artifacts_sha256', {})
    if source_hashes.get('observations.json') != SOURCE_SHA256:
        raise ValueError('Parent observation hash differs from the frozen n500 recording')
    # Read this index only after verifying it against the pinned parent manifest.
    required = ['summary.json']
    _artifact_hashes(directory, manifest, required)
    summary = read_json(directory / 'summary.json')
    if (summary.get('schema') != parent.SCHEMA or summary.get('status') != 'verified'
            or summary.get('evaluation_count') != 40 or summary.get('paired_comparison_count') != 24
            or summary.get('source_capture_unchanged') is not True):
        raise ValueError('Parent summary is not a verified complete comparison')
    evaluations = summary.get('evaluations')
    expected_evaluations = {
        variant['id']: {workload: f"queries/{variant['id']}--{workload}.json"
                        for workload in declared}
        for variant in matrix}
    if evaluations != expected_evaluations:
        raise ValueError('Parent exact evaluation index differs from the declared forty banks')
    for variant in matrix:
        identity = variant['id']
        required.extend((f'{identity}/policy.json', f'{identity}/result.json'))
        required.extend(evaluations[identity].values())
    parent_hashes = _artifact_hashes(directory, manifest, required)
    capture = Path(capture if capture is not None else manifest['source_capture']).resolve()
    replay, provenance = parent.verify_capture(capture)
    if provenance['source_artifacts_sha256'] != source_hashes:
        raise ValueError('Capture provenance differs from the pinned comparison')
    for variant in matrix:
        identity = variant['id']
        config = read_json(directory / identity / 'policy.json')
        if config != parent.config_for(variant):
            raise ValueError('Frozen policy differs from the matched requirements: ' + identity)
        parent.validate_result_metadata(replay, config,
            read_json(directory / identity / 'result.json'), variant)
    return dict(directory=directory, capture=capture, replay=replay, matrix=matrix,
                workloads=declared, exact_files=evaluations,
                parent_hashes=parent_hashes, source_hashes=source_hashes,
                parent_tree_hashes=parent.tree_hashes(directory),
                source_tree_hashes=parent.tree_hashes(capture),
                safe_source=dict(observations_sha256=SOURCE_SHA256,
                                 source_run_id=provenance['source_run_id'],
                                 source_sensor_id=provenance['source_sensor_id']))


def assert_unchanged(frozen):
    directory = frozen['directory']
    if digest(directory / 'study-manifest.json') != PARENT_MANIFEST_SHA256:
        raise ValueError('Frozen parent manifest changed during recipient evaluation')
    for name, expected in frozen['parent_hashes'].items():
        if digest(_file(directory, name)) != expected:
            raise ValueError('Frozen parent artifact changed during recipient evaluation: ' + name)
    if parent.tree_hashes(directory) != frozen['parent_tree_hashes']:
        raise ValueError('Frozen parent directory changed during recipient evaluation')
    if parent.tree_hashes(frozen['capture']) != frozen['source_tree_hashes']:
        raise ValueError('Frozen source capture changed during recipient evaluation')


def exact_projection(value):
    """The legacy compact public contract, without new diagnoses or estimates."""
    return exact.compact({**value, 'schema': exact.SCHEMA})


def evaluate_workloads(frozen, output):
    evaluations, pairs, budgets = {}, {}, {}
    directory, replay = frozen['directory'], frozen['replay']
    matrix = frozen['matrix']
    for workload, definition in frozen['workloads'].items():
        print('Recipient workload: ' + workload, flush=True)
        baseline = definition['matching_fixed_baseline']

        def one(identity):
            result = read_json(directory / identity / 'result.json')
            config = read_json(directory / identity / 'policy.json')
            budget = parent.budget_preflight(replay, result['releases'], definition)
            full = recipient.evaluate(replay, config, result['releases'],
                **{key: definition[key] for key in QUERY_KEYS}, uniform_estimate=True)
            expected = read_json(directory / frozen['exact_files'][identity][workload])
            if exact_projection(full) != expected:
                raise ValueError('Legacy exact evaluation changed: ' + identity + '/' + workload)
            filename = f'queries/{identity}--{workload}.json'
            write_json(output / filename, recipient.compact(full))
            evaluations.setdefault(identity, {})[workload] = filename
            budgets.setdefault(identity, {})[workload] = budget
            return full

        def pair(a, b, left, right):
            filename = f'queries/paired--{a}--{b}--{workload}.json'
            write_json(output / filename, dict(a=a, b=b, **recipient.paired_summary(left, right)))
            pairs[f'{a}--{b}--{workload}'] = filename

        # At most three full banks coexist. Raw per-query rows are never saved.
        matched = one(baseline)
        for variant in matrix:
            if variant['mode'] == 'fixed' and variant['id'] != baseline:
                full = one(variant['id'])
                del full
        for secondary in parent.SECONDARIES:
            common, local = (f'{coord}_{secondary}' for coord in ('common_window', 'cell_local'))
            common_full = one(common)
            pair(baseline, common, matched, common_full)
            local_full = one(local)
            pair(baseline, local, matched, local_full)
            pair(common, local, common_full, local_full)
            del common_full, local_full
        del matched
    return evaluations, pairs, budgets


def run(comparison, output, capture=None):
    comparison, output = (Path(value).resolve() for value in (comparison, output))
    if output.exists():
        raise ValueError('Refusing to replace an existing recipient study directory')
    if output.is_relative_to(comparison):
        raise ValueError('Output cannot be inside the frozen comparison')
    frozen = verify_parent(comparison, capture)
    if output.is_relative_to(frozen['capture']):
        raise ValueError('Output cannot be inside the frozen capture')
    code_paths = DEPENDENCIES + (PROTOCOL,)
    code_hashes = {name: digest(ROOT / name) for name in code_paths}
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    preflight = dict(schema=SCHEMA, status='unverified', protocol=PROTOCOL,
        parent_manifest_sha256=PARENT_MANIFEST_SHA256,
        parent_artifacts_sha256=frozen['parent_hashes'],
        source_artifacts_sha256=frozen['source_hashes'], **frozen['safe_source'],
        implementation_sha256=code_hashes,
        variants=deepcopy(frozen['matrix']), workloads=deepcopy(frozen['workloads']),
        uniform_estimate=True, new_producer_executions=0, scientific_repeats=0,
        private_source_manifest_copied=False, source_observations_copied=False,
        raw_releases_copied=False, per_query_rows_saved=False,
        scope='Same frozen releases and fixed recipient cohorts; conditional support and utility only')
    write_json(output / 'preflight-manifest.json', preflight)
    write_json(output / 'study-manifest.json', preflight)
    try:
        (output / 'sources').mkdir(mode=0o700)
        (output / 'queries').mkdir(mode=0o700)
        for name in DEPENDENCIES:
            target = output / 'sources' / Path(name).name
            shutil.copyfile(ROOT / name, target)
            if digest(target) != code_hashes[name]:
                raise ValueError('Frozen dependency copy changed: ' + name)
        shutil.copyfile(ROOT / PROTOCOL, output / 'protocol.md')
        if digest(output / 'protocol.md') != code_hashes[PROTOCOL]:
            raise ValueError('Frozen protocol copy changed')
        evaluations, pairs, budgets = evaluate_workloads(frozen, output)
        if sum(map(len, evaluations.values())) != 40 or len(pairs) != 24:
            raise ValueError('Recipient study did not complete its forty banks and twenty-four pairs')
        assert_unchanged(frozen)
        if code_hashes != {name: digest(ROOT / name) for name in code_paths}:
            raise ValueError('Protocol or implementation changed during recipient evaluation')
        summary = dict(schema=SCHEMA, status='verified', evaluations=evaluations,
            pairs=pairs, query_budget_preflight=budgets, evaluation_count=40,
            paired_comparison_count=24, legacy_exact_compact_match_count=40,
            source_capture_unchanged=True, parent_used_artifacts_unchanged=True,
            parent_directory_unchanged=True,
            uniform_estimate=True, new_producer_executions=0, scientific_repeats=0,
            limitations=[
                'The original exact recipient decoder and fixed query cohorts remain unchanged.',
                'Support masks diagnose certificate restrictions, not causal controller effects.',
                'Ignoring a certificate restriction does not reconstruct missing counts.',
                'Uniform spatial and discrete-sample temporal allocation is a conditional estimator.',
                'Unpublished support and ambiguous semantic classes remain unknown.',
                'Missing publication is not evidence of zero; private source never fills public support.',
                'One recording and deterministic re-evaluation do not establish statistical superiority.',
                'No additional release, policy change, measured privacy gain, or real-time claim.'])
        write_json(output / 'summary.json', summary)
        write_json(output / 'study-manifest.json', dict(preflight, status='verified',
            evaluation_count=40, paired_comparison_count=24,
            legacy_exact_compact_match_count=40, source_capture_unchanged=True,
            parent_used_artifacts_unchanged=True, parent_directory_unchanged=True,
            artifacts_sha256={name: value for name, value in parent.tree_hashes(output).items()
                              if name != 'study-manifest.json'}), replace=True)
    except Exception as error:
        write_json(output / 'study-manifest.json', dict(preflight, status='unverified',
            failure=dict(type=type(error).__name__, message=str(error))), replace=True)
        raise
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--capture', type=Path,
                        help='Optional relocated identical capture; all original hashes must match')
    args = parser.parse_args()
    print('Verified recipient contract study:', run(args.comparison, args.output, args.capture))


if __name__ == '__main__':
    main()
