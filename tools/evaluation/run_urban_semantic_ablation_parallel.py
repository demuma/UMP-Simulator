#!/usr/bin/env python3
"""Freeze and execute a fresh semantic-ablation utility study by recording.

This adapter adds process scheduling only. The frozen serial producer owns each
whole recording, including IN/OUT and method dependencies. It never fits or
scores MIA models; concurrent runtime observations measure batch throughput.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import math
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/evaluation'))
import run_urban_semantic_ablation as s
from parallel_recordings import BatchFailure, execute_recordings

SCHEMA = 'ump.urban-semantic-ablation-parallel-plan.v1'
ATTEMPT_SCHEMA = 'ump.urban-semantic-ablation-parallel-attempt.v1'
RECEIPT_SCHEMA = 'ump.urban-semantic-ablation-parallel-receipt.v1'
PLAN = 'parallel-execution-plan.json'
PLAN_SHA = 'parallel-execution-plan.sha256'
ATTEMPT = 'parallel-execution-attempt.json'
RECEIPT = 'parallel-execution-receipt.json'
FAILED = 'parallel-execution-failed.json'
GROUP_RECEIPTS = 'parallel-execution-groups'
DEFAULT_WORKERS = 6
DEFAULT_WORKER_DISK_RESERVE_GIB = 2
TIMING_SCOPE = ('Concurrent recording execution: wall times and native processing times '
                'describe this batch and are not isolated runtime benchmarks.')
_WORKER_CONTEXT = None


def require(condition, message):
    s.require(condition, message)


def validate_workers(workers):
    require(type(workers) is int and 1 <= workers <= DEFAULT_WORKERS,
            'Workers must be an integer from 1 through 6')
    return workers


def _reserve_bytes(gib):
    require(type(gib) in (int, float) and math.isfinite(gib) and gib > 0,
            'Worker disk reserve GiB must be positive and finite')
    value = math.ceil(gib * 1024 ** 3)
    require(value > 0, 'Worker disk reserve must be positive')
    return value


def _write_new(path, value):
    """Publish complete JSON exclusively; never replace an existing artifact."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp-' + str(os.getpid()) + '-' + uuid.uuid4().hex)
    try:
        s.primary.fixture.write_new(temporary, s.primary.fixture.encoded(value))
        os.link(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def study_lock(output):
    output = s.primary.fixture.safe_path(output, root=s.ROOT / 'results')
    descriptor = os.open(output / '.semantic-ablation.lock',
                         os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield output
    finally:
        os.close(descriptor)


def _implementation_files():
    directory = Path(__file__).resolve().parent
    names = (Path(__file__).name, 'test_' + Path(__file__).name,
             'parallel_recordings.py', 'test_parallel_recordings.py')
    return [s.reference(directory / name) for name in names]


def _pristine(output, *, preparing=False):
    groups = output / 'groups'
    require(groups.is_dir() and not any(groups.iterdir()),
            'Parallel execution requires a fresh study: no completed or attempted groups; no retries')
    forbidden = set(s.FIT_OUTPUTS) | {'utility-report.json', ATTEMPT, RECEIPT, FAILED, GROUP_RECEIPTS}
    if preparing:
        forbidden.update((PLAN, PLAN_SHA))
    require(not any(os.path.lexists(output / name) for name in forbidden),
            'Existing execution, utility or MIA artifacts forbid prepare/run or retry')


def prepare_execution(output, *, workers=DEFAULT_WORKERS,
                      worker_disk_reserve_gib=DEFAULT_WORKER_DISK_RESERVE_GIB):
    workers = validate_workers(workers)
    reserve = _reserve_bytes(worker_disk_reserve_gib)
    _pristine(Path(output), preparing=True)
    with study_lock(output):
        output, protocol, context = s.read_protocol(output)
        _pristine(output, preparing=True)
        groups = context['manifest']['groups']
        plan = dict(schema=SCHEMA, status='prepared', prepared_at=s.source.now(),
                    output_directory=str(output), base_protocol=s.reference(output / 'protocol.json'),
                    base_protocol_schema=protocol['schema'], original_config=protocol['original_config'],
                    variant_configs=protocol['variant_configs'], native_binary=protocol['native_binary'],
                    implementation_files=_implementation_files(), workers=workers, group_order=groups,
                    scheduling_unit='whole_recording_including_IN_OUT_and_method_dependencies',
                    multiprocessing_start_method='spawn', retries_allowed=False, mia_allowed=False,
                    source_generation_allowed=False, minimum_free_bytes=protocol['minimum_free_bytes'],
                    worker_disk_reserve_bytes=reserve,
                    worker_disk_reserve_gib=worker_disk_reserve_gib,
                    disk_reserve_scope='Explicit per-active-worker allowance, not an estimated artifact size or hard cap',
                    timing_scope=TIMING_SCOPE, isolated_runtime_benchmark=False)
        _write_new(output / PLAN, plan)
        _write_new(output / PLAN_SHA, {'sha256': s.source.sha(output / PLAN)})
        return plan


def _read_plan(output, protocol, context):
    plan = s.source.load(output / PLAN)
    require(s.source.load(output / PLAN_SHA) == {'sha256': s.source.sha(output / PLAN)},
            'Parallel execution plan digest differs')
    require(plan['schema'] == SCHEMA and plan['status'] == 'prepared'
            and plan['output_directory'] == str(output), 'Parallel execution plan identity differs')
    require(plan['base_protocol'] == s.reference(output / 'protocol.json')
            and plan['base_protocol_schema'] == protocol['schema'] == s.SCHEMA,
            'Parallel plan base protocol differs')
    require(all(plan[key] == protocol[key] for key in
                ('original_config', 'variant_configs', 'native_binary', 'minimum_free_bytes')),
            'Parallel plan configuration/budgets differ')
    require(plan['implementation_files'] == _implementation_files(),
            'Parallel wrapper/helper/test bytes changed')
    for item in plan['implementation_files']:
        s.authenticated(item)
    validate_workers(plan['workers'])
    require(plan['group_order'] == context['manifest']['groups'], 'Parallel recording order differs')
    require(plan['worker_disk_reserve_bytes'] == _reserve_bytes(plan['worker_disk_reserve_gib']),
            'Parallel worker disk reserve differs')
    require(plan['scheduling_unit'] == 'whole_recording_including_IN_OUT_and_method_dependencies'
            and plan['multiprocessing_start_method'] == 'spawn'
            and all(plan[key] is False for key in ('retries_allowed', 'mia_allowed', 'source_generation_allowed',
                                                    'isolated_runtime_benchmark'))
            and plan['timing_scope'] == TIMING_SCOPE, 'Parallel execution scope differs')
    return plan


def _check_disk(output, protocol, plan):
    active = min(plan['workers'], len(plan['group_order']))
    required = protocol['minimum_free_bytes'] + active * plan['worker_disk_reserve_bytes']
    free = shutil.disk_usage(output).free
    require(free >= required,
            f'Insufficient aggregate free disk: {free} bytes available; {required} required '
            f'(base floor plus allowance for {active} workers)')
    return dict(free_bytes=free, required_free_bytes=required, active_worker_allowances=active)


def _initialize_worker(output, protocol, context):
    global _WORKER_CONTEXT
    _WORKER_CONTEXT = (Path(output), protocol, context)


def _run_group(group):
    require(_WORKER_CONTEXT is not None, 'Parallel worker context is missing')
    output, protocol, context = _WORKER_CONTEXT
    started = time.perf_counter()
    summary = s.process_group(output, protocol, context, group)
    _verified_summary(group, summary)
    return dict(summary=summary, seconds=time.perf_counter() - started, worker_pid=os.getpid())


def _verified_summary(group, summary):
    require(isinstance(summary, dict) and summary.get('status') == 'verified'
            and summary.get('group_id') == group['group_id']
            and summary.get('split') == group['split'],
            'Recording returned an incomplete, failed or mismatched summary: ' + group['group_id'])


def run_utility(output):
    _pristine(Path(output))
    with study_lock(output):
        # Authenticate historical context once in the parent, then initialize each
        # spawned process once. Each recording retains the frozen serial checks.
        output, protocol, context = s.read_protocol(output)
        _pristine(output)
        plan = _read_plan(output, protocol, context)
        disk = _check_disk(output, protocol, plan)
        groups = context['manifest']['groups']
        require(groups, 'No recordings declared')
        attempt = dict(schema=ATTEMPT_SCHEMA, status='attempted', started_at=s.source.now(),
                       execution_plan=s.reference(output / PLAN), workers=plan['workers'],
                       ordered_group_ids=[group['group_id'] for group in groups], disk_preflight=disk,
                       retries_allowed=False, mia_allowed=False, timing_scope=TIMING_SCOPE)
        _write_new(output / ATTEMPT, attempt)
        receipts = output / GROUP_RECEIPTS
        completed = {}
        started = time.perf_counter()

        def before_submit(group):
            _check_disk(output, protocol, plan)

        def on_result(group, result):
            summary = result['summary']
            _verified_summary(group, summary)
            path = output / 'groups' / group['group_id'] / 'summary.json'
            require(s.source.load(path) == summary, 'Worker summary differs from stored result')
            require(group['group_id'] not in completed, 'Duplicate recording result')
            receipt = dict(group_id=group['group_id'], split=group['split'], status='verified',
                           summary=s.reference(path), worker_pid=result['worker_pid'],
                           concurrent_recording_seconds=result['seconds'])
            _write_new(receipts / (group['group_id'] + '.json'), receipt)
            completed[group['group_id']] = receipt

        try:
            receipts.mkdir(mode=0o700)
            results = execute_recordings(groups, _run_group, workers=plan['workers'],
                                         initializer=_initialize_worker,
                                         initargs=(str(output), protocol, context),
                                         before_submit=before_submit, on_result=on_result)
            require(len(results) == len(groups) and len(completed) == len(groups),
                    'Parallel execution did not verify every recording')
            for group, result in zip(groups, results):
                _verified_summary(group, result['summary'])
            rows, summaries, auxiliary = s.collect(output, protocol, context,
                                                   verify_archives=True, require_complete=True)
            elapsed = time.perf_counter() - started
            receipt = dict(schema=RECEIPT_SCHEMA, status='verified', completed_at=s.source.now(),
                           execution_plan=s.reference(output / PLAN), attempt=s.reference(output / ATTEMPT),
                           workers=plan['workers'], ordered_group_ids=[g['group_id'] for g in groups],
                           group_receipts=[s.reference(receipts / (g['group_id'] + '.json')) for g in groups],
                           headline_rows=len(rows), auxiliary_rows=len(auxiliary), recordings=len(summaries),
                           concurrent_batch_seconds=elapsed,
                           recordings_per_second=len(groups) / elapsed if elapsed else None,
                           mia_status='not_started', timing_scope=TIMING_SCOPE,
                           isolated_runtime_benchmark=False)
            _write_new(output / RECEIPT, receipt)
            return receipt
        except BaseException as error:
            failure = dict(schema=RECEIPT_SCHEMA, status='failed', failed_at=s.source.now(),
                           execution_plan=s.reference(output / PLAN), attempt=s.reference(output / ATTEMPT),
                           error_type=type(error).__name__, error=str(error),
                           completed_group_ids=[g['group_id'] for g in groups if g['group_id'] in completed],
                           workers=plan['workers'], concurrent_batch_seconds=time.perf_counter() - started,
                           retries_allowed=False, mia_status='not_started', timing_scope=TIMING_SCOPE)
            if isinstance(error, BatchFailure):
                failure.update(errors={key: str(value) for key, value in error.errors.items()},
                               cancelled_group_ids=error.cancelled_group_ids,
                               unsubmitted_group_ids=error.unsubmitted_group_ids)
            _write_new(output / FAILED, failure)
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare-execution', type=Path, metavar='STUDY')
    action.add_argument('--run-utility', type=Path, metavar='STUDY')
    parser.add_argument('--workers', type=int, default=None)
    parser.add_argument('--worker-disk-reserve-gib', type=float, default=None)
    args = parser.parse_args(argv)
    if args.prepare_execution:
        result = prepare_execution(args.prepare_execution,
                                   workers=DEFAULT_WORKERS if args.workers is None else args.workers,
                                   worker_disk_reserve_gib=(DEFAULT_WORKER_DISK_RESERVE_GIB
                                       if args.worker_disk_reserve_gib is None else args.worker_disk_reserve_gib))
        print('Prepared parallel utility execution with', result['workers'], 'workers')
    else:
        require(args.workers is None and args.worker_disk_reserve_gib is None,
                'Concurrency and disk allowance must be frozen with --prepare-execution')
        result = run_utility(args.run_utility)
        print('Verified', result['recordings'], 'recordings; MIA not started')


if __name__ == '__main__':
    main()
