#!/usr/bin/env python3
"""Freeze and run an isolated, bounded current-build replay study.

The two 300-second Spatial20 streams come from the controller-correction study.
The third source exactly repeats the earlier failed 240-second dense-stream gate
with the corrected binary and unchanged original policy. Native processes run serially. The runner
never builds, regenerates motion, changes queue bounds, retries failed cases, or
changes a source clock. Raw outputs remain in the requested local results folder.
A compact study-summary.json contains no individual observations or release IDs.
"""
import argparse
from datetime import datetime, timezone
import gc
import json
import importlib.util
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

import summarize_paced_replay as audit


SCHEMA = 'ump.current-paced-study-protocol.v2'
CASES = ('full_unpaced', 'minimal_unpaced', 'minimal_paced_1x')
SOURCES = ('mixed', 'pedestrians', 'old_dense')
CORRECTION = Path('results/spatial20-controller-correction-2026-10-24-v2')
HISTORICAL_SOURCE = Path('results/urban-traffic-2026-10-24-256/replay/observations.json')
HISTORICAL_POLICY = Path('results/urban-traffic-2026-10-24-256-policy-comparison/original_adaptive_immediate-policy.json')
HISTORICAL_EVIDENCE = Path('docs/verification/urban-minimal-paced-2026-10-24.json')
MAX_WALL_SECONDS = 420
# Include implementation, headers, native build configuration and analysis code.
# This fingerprints the working source tree, including uncommitted corrections.
SOURCE_GLOBS = ('simulator/src/*.cpp', 'simulator/include/*.hpp',
                'simulator/include/*.tpp', 'simulator/tools/*.cpp',
                'simulator/tools/*.hpp', 'simulator/CMakeLists.txt',
                'tools/evaluation/*.py')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def fingerprints(paths):
    return {str(path): audit.fingerprint(path) for path in paths}


def require_unchanged(expected):
    changed = [path for path, fingerprint in expected.items()
               if not Path(path).is_file() or audit.fingerprint(path) != fingerprint]
    if changed:
        raise ValueError('Frozen/source artifacts changed: ' + ', '.join(changed))


def command(binary, source, policy, output, case, failure):
    result = [str(binary), '--input', str(source), '--config', str(policy),
              '--mode', 'semantic_first', '--progress-step-ms', '50',
              '--decision-digest', 'sha256', '--diagnostics',
              'full' if case == 'full_unpaced' else 'minimal', '--output', str(output)]
    if case == 'minimal_paced_1x':
        result += ['--pace-rate', '1', '--queue-capacity', '8', '--failure-output', str(failure)]
    return result



def historical_identity(values):
    evidence = audit.load(values['historical_evidence'])
    before = evidence['protocol']['artifacts_before']
    for current, previous in (('observations', 'source'), ('policy', 'policy')):
        actual = audit.fingerprint(values[current])
        expected = {name: before[previous][name] for name in ('sha256', 'bytes')}
        if actual != expected:
            raise ValueError('Historical dense ' + previous + ' differs from the recorded failed gate')
    failed = evidence['paced_incomplete_result']
    if (failed['result'] != 'bounded_queue_overflow'
            or failed['source'] != dict(end_ms=240000, progress_step_ms=50, sampling_period_ms=100)
            or failed['offered_load']['rate'] != 1 or failed['offered_load']['queue_capacity'] != 8):
        raise ValueError('Historical evidence does not describe the required unchanged failed gate')
    return dict(source={name: before['source'][name] for name in ('sha256', 'bytes')},
                policy={name: before['policy'][name] for name in ('sha256', 'bytes')},
                old_binary={name: before['binary'][name] for name in ('sha256', 'bytes')},
                old_result='bounded_queue_overflow', old_completed_events=failed['events']['completed'],
                old_rejected_logical_time_ms=failed['events']['rejected_logical_time_ms'],
                old_cadence_response_misses=failed['completed_prefix_cadence_response_misses'],
                old_sensor_response_misses=failed['completed_sensor_period_response_misses'],
                contrast='Identical input and policy, corrected current binary; old/current logical decisions may differ.')


def independent_policy_audit(repo, observations, policy, result):
    directory = repo / 'tools/evaluation'
    sys.path.insert(0, str(directory))
    specification = importlib.util.spec_from_file_location(
        'ump_current_paced_independent_policy_audit', directory / 'run_local_policy_replay.py')
    helper = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(helper)
    checked = helper.audit(observations, policy, result, max_cells=1000000)
    if checked.get('status') != 'verified' or checked.get('scalar', {}).get('valid') is not True:
        raise ValueError('Independent current dense-stream policy/retirement audit failed')
    scalar = checked['scalar']
    # Explicit allowlist: do not copy private cell details or per-track groups.
    return dict(status='verified', scalar_valid=True, policy_violation_count=0,
                released_cell_count=scalar['released_cell_count'],
                input_observation_contributions=scalar['input_observation_contributions'],
                released_observation_contributions=scalar['released_observation_contributions'],
                semantic_published_cells=checked['semantic_published_cells'],
                semantic_published_bins=checked['semantic_published_bins'],
                max_cells=1000000,
                scope='Independent raw-observation, geometry, retirement, truthful semantic antichain and regional-policy recomputation; no attack-resistance claim.')


def prepare(repo, output, binary, sources):
    repo, output, binary = repo.resolve(), output.resolve(), binary.resolve()
    if output.exists():
        raise ValueError('Study output already exists; use --resume for its frozen protocol')
    inputs = {}
    for source in sources:
        base = repo / CORRECTION
        if source == 'old_dense':
            inputs[source] = dict(observations=repo / HISTORICAL_SOURCE,
                                  policy=repo / HISTORICAL_POLICY,
                                  historical_evidence=repo / HISTORICAL_EVIDENCE)
        else:
            inputs[source] = dict(observations=base / (source + '-observations.json'),
                                  policy=base / (source + '_spatial20_adaptive_immediate_off-policy.json'),
                                  historical_full=base / (source + '_spatial20_adaptive_immediate_off.json'))
    # Check every intended source before creating any provenance directory.
    original_paths = [binary] + [path for values in inputs.values() for path in values.values()]
    original_fingerprints = fingerprints(original_paths)
    for values in inputs.values():
        policy = audit.load(values['policy'])
        execution = policy['policy_tree']['execution']
        if (execution['strategy'] != 'semantic_first'
                or execution['release_trigger'] != 'policy_satisfied'
                or execution['semantic_secondary_strategy'] != 'temporal_first'
                or policy['policy_tree']['root'].get('semantic_suppression_fraction', {'max': 0})['max'] != 0):
            raise ValueError('Expected unchanged Spatial20 Semantic First, policy-satisfied, suppression-OFF policy')
    historical = None
    if 'old_dense' in inputs:
        historical = historical_identity(inputs['old_dense'])
    output.mkdir(parents=True)
    provenance = output / 'provenance'
    provenance.mkdir()
    frozen_binary = provenance / 'AggregationReplay'
    shutil.copy2(binary, frozen_binary)
    cases = []
    frozen_paths = [frozen_binary]
    for source, values in inputs.items():
        observations = provenance / (source + '-observations.json')
        policy = provenance / (source + '-policy.json')
        shutil.copy2(values['observations'], observations)
        shutil.copy2(values['policy'], policy)
        frozen_paths.extend((observations, policy))
        folder = output / source
        folder.mkdir()
        for case in CASES:
            result = folder / (case + '.json')
            failure = folder / (case + '-failure.json')
            cases.append(dict(id=source + '/' + case, source=source, case=case,
                              command=command(frozen_binary, observations, policy, result, case, failure),
                              output=str(result), failure=str(failure),
                              historical_full=str(values['historical_full']) if 'historical_full' in values else None,
                              full_validation='independent_policy_audit' if source == 'old_dense' else 'historical_corrected_equality',
                              execution=str(folder / (case + '-execution.json')),
                              summary=str(folder / (case + '-summary.json'))))
    source_paths = sorted({path.resolve() for pattern in SOURCE_GLOBS for path in repo.glob(pattern)})
    source_paths += [Path(__file__).resolve(), Path(audit.__file__).resolve()]
    protocol = dict(schema=SCHEMA, created_utc=utc_now(), repo=str(repo), study_directory=str(output),
                    git_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
                    platform=platform.platform(), original_artifacts=original_fingerprints,
                    frozen_artifacts=fingerprints(frozen_paths), source_files=fingerprints(source_paths),
                    sources=list(sources), cases=cases, max_case_wall_seconds=MAX_WALL_SECONDS,
                    expected_sources={source: dict(duration_ms=240000 if source == 'old_dense' else 300000,
                                                   sensor_sampling_ms=100) for source in sources},
                    historical_failed_gate=historical,
                    offered_load=dict(rate=1, queue_capacity=8, progress_step_ms=50),
                    deadline_contract=dict(cadence_response_ms=50, secondary_sensor_response_ms=100,
                                           fixed_schedule=True),
                    isolation='Operator must exclude builds, simulations, captures, renderers, other native measurements and intentionally scheduled heavy jobs for the whole serial execution. Postprocessing occurs between native processes.',
                    equality_gate='Mixed/pedestrian full output equals historical corrected control outside runtime. Dense historical source full output passes independent policy/retirement audit; old-binary output equality is not required. New audited full/minimal controls have exact common/public fields and complete typed SHA-256 retirement/release audits. Paced success must equal the new unpaced control.',
                    overload_policy='Keep bounded-queue failure; no retry, larger queue, slower clock, shifted deadlines or successful-output claim.',
                    limitation='One isolated paced run per source; observed deadlines are empirical, not a hard realtime guarantee.')
    require_unchanged(original_fingerprints)
    write_new(output / 'protocol.json', protocol)
    write_new(output / 'protocol-receipt.json', dict(schema='ump.current-paced-protocol-receipt.v1',
              protocol_fingerprint=audit.fingerprint(output / 'protocol.json')))
    return protocol



def verify_protocol(protocol, expected_directory=None):
    directory = Path(protocol['study_directory'])
    if expected_directory is not None and directory != Path(expected_directory).resolve():
        raise ValueError('Frozen protocol study directory differs from the requested study')
    receipt = audit.load(directory / 'protocol-receipt.json')
    fingerprint = audit.fingerprint(directory / 'protocol.json')
    if (receipt.get('schema') != 'ump.current-paced-protocol-receipt.v1'
            or receipt.get('protocol_fingerprint') != fingerprint
            or audit.load(directory / 'protocol.json') != protocol):
        raise ValueError('Frozen protocol differs from its independent prepare-time SHA-256 receipt')
    return fingerprint


def invariant_artifacts(protocol):
    # Current build may change after preparation; execute its frozen copy only.
    # The original input/control files and working implementation must not change.
    original = {path: value for path, value in protocol['original_artifacts'].items()
                if path != str(Path(protocol['repo']) / 'simulator/build/AggregationReplay')}
    return dict(original, **protocol['frozen_artifacts'], **protocol['source_files'])


def verify_source(value, protocol, item):
    expected = protocol['expected_sources'][item['source']]
    if (value.get('schema') != 'ump.replay-result.v1'
            or value['source']['end_ms'] != expected['duration_ms']
            or value['source']['sampling_period_ms'] != expected['sensor_sampling_ms']
            or value['parameters'].get('progress_step_ms') != 50
            or value['parameters'].get('progress_origin_ms') != 0
            or value['input_observation_contributions'] != value['accounted_observation_contributions']):
        raise ValueError('Unexpected source/cadence/accounting contract')
    audit.validate_decision_audit(value)


def summarize_case(protocol, item):
    result = audit.load(item['output'])
    verify_source(result, protocol, item)
    folder = Path(item['output']).parent
    if item['case'] == 'full_unpaced':
        checked = dict(schema='ump.current-paced-control-summary.v1',
                       decision_audit=result['runtime']['decision_audit'],
                       processing_ms=result['runtime']['processing_ms'], phases=result['runtime'].get('phases'),
                       input_observation_contributions=result['input_observation_contributions'],
                       release_count=len(result['releases']))
        if item.get('full_validation') == 'independent_policy_audit':
            options = dict(zip(item['command'][1::2], item['command'][2::2]))
            checked.update(independent_policy_audit=independent_policy_audit(
                Path(protocol['repo']), audit.load(options['--input']), audit.load(options['--config']), result),
                old_binary_logical_equality_required=False,
                historical_failed_gate=protocol['historical_failed_gate'])
        else:
            reference = audit.load(item['historical_full'])
            checked.update(historical_corrected_output_equal=True,
                           equivalence=audit.logical_equivalence(result, reference))
        return checked
    reference = audit.load(folder / 'full_unpaced.json')
    verify_source(reference, protocol, item)
    if item['case'] == 'minimal_unpaced':
        return dict(schema='ump.current-paced-control-summary.v1',
                    full_minimal_logical_equivalence=audit.logical_equivalence(result, reference),
                    decision_audit=result['runtime']['decision_audit'],
                    processing_ms=result['runtime']['processing_ms'], phases=result['runtime'].get('phases'),
                    input_observation_contributions=result['input_observation_contributions'],
                    release_count=len(result['releases']))
    minimal = audit.load(folder / 'minimal_unpaced.json')
    audit.logical_equivalence(minimal, reference)
    pacing = result['runtime']['pacing']
    load = protocol['offered_load']
    if pacing['rate'] != load['rate'] or pacing['queue_capacity'] != load['queue_capacity']:
        raise ValueError('Successful pacing differs from the frozen offered-load contract')
    return audit.summarize(result, minimal)


def dependencies_ready(item):
    folder = Path(item['output']).parent
    required = () if item['case'] == 'full_unpaced' else ('full_unpaced',)
    if item['case'] == 'minimal_paced_1x':
        required += ('minimal_unpaced',)
    for case in required:
        record_path = folder / (case + '-execution.json')
        if not record_path.is_file():
            raise ValueError('A validated prior control is required: ' + str(record_path))
        record = audit.load(record_path)
        if record.get('status') != 'validated':
            raise ValueError('A validated prior control is required: ' + str(record_path))
        control_path = folder / (case + '.json')
        if (not control_path.is_file() or record.get('output_fingerprint') != audit.fingerprint(control_path)):
            raise ValueError('Validated prior control changed since its execution receipt: ' + str(control_path))


def run_case(protocol, item):
    verify_protocol(protocol)
    paths = [Path(item[name]) for name in ('output', 'failure', 'execution', 'summary')]
    if any(path.exists() for path in paths):
        raise ValueError('Case artifacts already exist; failed/completed cases are never overwritten or retried: ' + item['id'])
    dependencies_ready(item)
    invariants = invariant_artifacts(protocol)
    require_unchanged(invariants)
    record = dict(id=item['id'], command=item['command'], started_utc=utc_now())
    start = time.perf_counter()
    try:
        child = subprocess.run(item['command'], cwd=protocol['repo'], capture_output=True, text=True,
                               timeout=protocol['max_case_wall_seconds'], check=False)
        record.update(return_code=child.returncode, stdout=child.stdout, stderr=child.stderr)
    except subprocess.TimeoutExpired as error:
        record.update(return_code=None, status='timeout',
                      stderr='Native process exceeded the frozen wall-time cap; no retry.',
                      timeout_seconds=error.timeout)
    record.update(wall_seconds=time.perf_counter() - start, completed_utc=utc_now(),
                  output_exists=paths[0].exists(), failure_exists=paths[1].exists())
    # Always preserve the native execution receipt even when verification fails.
    try:
        verify_protocol(protocol)
        require_unchanged(invariants)
        record['artifacts_unchanged'] = True
        dependencies_ready(item)
        if record.get('status') == 'timeout':
            pass
        elif record['return_code'] == 0:
            if not paths[0].is_file() or paths[1].exists():
                raise ValueError('Successful native run lacks output or also wrote failure telemetry')
            result = summarize_case(protocol, item)
            dependencies_ready(item)
            verify_protocol(protocol)
            record['status'] = 'validated'
            record['output_fingerprint'] = audit.fingerprint(paths[0])
            write_new(paths[3], result)
            record['summary_fingerprint'] = audit.fingerprint(paths[3])
        elif item['case'] == 'minimal_paced_1x' and paths[1].is_file() and not paths[0].exists():
            failure = audit.load(paths[1])
            load = protocol['offered_load']
            if (failure['rate'] != load['rate'] or failure['queue_capacity'] != load['queue_capacity']
                    or failure['progress_step_ms'] != load['progress_step_ms']
                    or failure['source_end_ms'] != protocol['expected_sources'][item['source']]['duration_ms']
                    or failure['sampling_period_ms'] != protocol['expected_sources'][item['source']]['sensor_sampling_ms']):
                raise ValueError('Failure sidecar differs from the frozen offered-load contract')
            write_new(paths[3], audit.summarize_failure(failure))
            record['summary_fingerprint'] = audit.fingerprint(paths[3])
            record.update(status='bounded_queue_overflow', failure_fingerprint=audit.fingerprint(paths[1]))
        else:
            record['status'] = 'native_failure'
    except Exception as error:
        record.update(status='verification_failed', verification_error=str(error))
    write_new(paths[2], record)
    gc.collect()
    print(item['id'] + ': ' + record['status'], flush=True)
    return record


def compact_report(protocol):
    protocol_fingerprint = verify_protocol(protocol)
    report = dict(schema='ump.current-paced-study-summary.v1',
                  protocol_sha256=protocol_fingerprint['sha256'],
                  frozen_binary=next(value for path, value in protocol['frozen_artifacts'].items()
                                     if Path(path).name == 'AggregationReplay'),
                  offered_load=protocol['offered_load'], deadline_contract=protocol['deadline_contract'],
                  expected_sources=protocol['expected_sources'], historical_failed_gate=protocol.get('historical_failed_gate'),
                  cases=[], limitation=protocol['limitation'])
    for item in protocol['cases']:
        if not Path(item['execution']).exists():
            report['cases'].append(dict(id=item['id'], status='not_run'))
            continue
        record = audit.load(item['execution'])
        if record.get('id') != item['id']:
            raise ValueError('Execution receipt case identity differs from the frozen protocol')
        if record.get('status') == 'validated':
            result_path = Path(item['output'])
            if (not result_path.is_file() or record.get('output_fingerprint') != audit.fingerprint(result_path)):
                raise ValueError('Validated output changed before compact reporting: ' + item['id'])
        if record.get('status') == 'bounded_queue_overflow':
            failure_path = Path(item['failure'])
            if (not failure_path.is_file() or record.get('failure_fingerprint') != audit.fingerprint(failure_path)):
                raise ValueError('Failure telemetry changed before compact reporting: ' + item['id'])
        summary_path = Path(item['summary'])
        if record.get('status') in ('validated', 'bounded_queue_overflow') or summary_path.exists():
            if (not summary_path.is_file() or record.get('summary_fingerprint') != audit.fingerprint(summary_path)):
                raise ValueError('Validated summary changed before compact reporting: ' + item['id'])
        compact = {name: record[name] for name in ('id', 'status', 'return_code', 'wall_seconds', 'artifacts_unchanged') if name in record}
        if summary_path.is_file():
            compact['measurements'] = audit.load(summary_path)
        if 'verification_error' in record:
            compact['verification_error'] = 'Verification failed; detailed local execution receipt retained.'
        report['cases'].append(compact)
    report['all_native_cases_completed'] = all(case['status'] == 'validated' for case in report['cases'])
    verify_protocol(protocol)
    return report


def execute(protocol, sources, cases):
    verify_protocol(protocol)
    for item in protocol['cases']:
        if item['source'] not in sources or item['case'] not in cases:
            continue
        record = run_case(protocol, item)
        # A scientific equivalence/setup/native error blocks subsequent cases.
        # A valid bounded-overflow result is a measured failed gate; continue
        # with the other source without changing any frozen experiment setting.
        if record['status'] not in ('validated', 'bounded_queue_overflow'):
            raise RuntimeError(item['id'] + ' did not validate; inspect its execution receipt')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--binary', type=Path, help='Current AggregationReplay; defaults to REPO/simulator/build/AggregationReplay')
    parser.add_argument('--output', required=True, type=Path, help='New local study directory, or an existing frozen study with --resume')
    parser.add_argument('--sources', nargs='+', choices=SOURCES)
    parser.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if args.resume:
        if args.binary or args.prepare_only:
            parser.error('--resume uses the frozen binary and cannot be combined with --prepare-only')
        protocol = audit.load(output / 'protocol.json')
        if protocol.get('schema') != SCHEMA:
            raise ValueError('Unexpected frozen protocol schema')
        verify_protocol(protocol, output)
        require_unchanged(invariant_artifacts(protocol))
    else:
        protocol = prepare(args.repo, output, args.binary or args.repo / 'simulator/build/AggregationReplay', args.sources or SOURCES)
    sources = args.sources or protocol['sources']
    if not set(sources).issubset(protocol['sources']):
        raise ValueError('Requested source was not in the frozen protocol')
    if args.prepare_only:
        print('Frozen protocol (no native execution): ' + str(output / 'protocol.json'))
        return
    if (output / 'study-summary.json').exists():
        raise ValueError('Final study summary already exists; cases are never retried or overwritten')
    try:
        execute(protocol, sources, args.cases)
    finally:
        report = compact_report(protocol)
        # Partial selected-case runs have immutable receipts; write the single
        # final compact summary only after every planned case has a receipt.
        if all(case['status'] != 'not_run' for case in report['cases']):
            write_new(output / 'study-summary.json', report)
    print('Selected native cases finished; raw outputs remain local: ' + str(output))


if __name__ == '__main__':
    main()
