#!/usr/bin/env python3
"""Validate prefix-owner optimization against the frozen 10-variant study.

Requires macOS, the private frozen study/capture and native build dependencies.
All raw outputs and copied instrumented sources stay outside the repository.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

SOURCES = ('AggregationManager', 'AggregationHistory', 'CandidateMetrics', 'PolicyTree',
           'SpatialSelection', 'AdaptiveAggregation', 'CellLocalAggregation',
           'PublicationCoordinator', 'AggregationConfiguration', 'PolicyConfiguration',
           'SemanticTaxonomy')
CONTROLS = ('fixed_10m_400ms', 'common_window_temporal_first', 'cell_local_temporal_first')
STUDY_MANIFEST_SHA256 = 'e81b724b673ac5f8e77ddd483b41b4ec2756206fbd32ccf2455e14bd234dc83f'
OBSERVATIONS_SHA256 = 'ab4fadf254bfb5432018ff4bd305cd16d82a7475ae3d934c14c4f9af67dd5cf1'


def variants():
    fixed = [dict(id=f'fixed_{side}m_{window}ms', mode='fixed', depth=depth, window=window)
             for side, depth in (('2p5', 5), ('5', 4), ('10', 3)) for window in (400, 1000)]
    return fixed + [dict(id=f'{coord}_{secondary}', mode='semantic_first', depth=None, window=None)
                    for coord in ('common_window', 'cell_local')
                    for secondary in ('temporal_first', 'spatial_first')]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    Path(path).chmod(0o600)


def verify_frozen_artifacts(study):
    manifest_path = Path(study) / 'study-manifest.json'
    if digest(manifest_path) != STUDY_MANIFEST_SHA256:
        raise ValueError('Study manifest differs from the pinned verified study')
    manifest = read(manifest_path)
    expected = manifest.get('artifacts_sha256', {})
    names = ['AggregationReplay.frozen']
    names += [variant['id'] + '/' + filename for variant in variants()
              for filename in ('policy.json', 'result.json')]
    verified = {}
    for name in names:
        observed = digest(Path(study) / name)
        if observed != expected.get(name):
            raise ValueError('Frozen study artifact differs from its pinned manifest: ' + name)
        verified[name] = observed
    if verified['AggregationReplay.frozen'] != manifest.get('binary_sha256'):
        raise ValueError('Pinned study binary declarations disagree')
    if manifest.get('source_artifacts_sha256', {}).get('observations.json') != OBSERVATIONS_SHA256:
        raise ValueError('Pinned study source differs from the required capture')
    return verified


def summarize_profile(profile):
    if profile.get('schema') != 'ump.scoped-runtime-instrumentation.v1':
        raise ValueError('Unexpected instrumentation schema')
    ticks = profile.pop('ticks')
    inputs = [item for item in ticks if not item['eof']]
    eof = [item for item in ticks if item['eof']]
    if [item['logical_ms'] for item in inputs] != list(range(100, 20000, 100)):
        raise ValueError('Instrumentation did not observe the 199 scheduled inputs')
    if len(eof) != 1 or eof[0]['logical_ms'] != 20000:
        raise ValueError('Instrumentation did not observe the expected EOF')
    ordered = sorted(item['service_ms'] for item in inputs)
    if any(not math.isfinite(value) or value < 0 for value in ordered):
        raise ValueError('Invalid input service duration')
    quantile = lambda q: ordered[max(0, math.ceil(q * len(ordered)) - 1)]
    complete, max_wait, delays = 0.0, 0.0, []
    for item in inputs:
        arrival = float(item['logical_ms'])
        max_wait = max(max_wait, complete - arrival)
        complete = max(arrival, complete) + item['service_ms']
        delays.append(complete - arrival)
    return dict(profile, input_tick_service=dict(count=len(inputs), mean_ms=sum(ordered)/len(ordered),
        p50_ms=quantile(.5), p95_ms=quantile(.95), p99_ms=quantile(.99), max_ms=ordered[-1],
        quantile_definition='nearest rank, ceil(p*n)',
        service_above_100ms_count=sum(value > 100 for value in ordered), eof_service_ms=eof[0]['service_ms']),
        hypothetical_fifo_100ms_arrivals=dict(initial_queue_empty=True, live_paced_measurement=False,
            max_wait_before_service_ms=max_wait, max_input_completion_delay_ms=max(delays),
            last_input_completion_delay_ms=delays[-1],
            completion_delay_above_100ms_count=sum(value > 100 for value in delays)))


def execute(binary, source, study, variant, destination, kind):
    destination.mkdir(mode=0o700)
    name = variant['id']
    command = [str(binary), '--input', str(source), '--config', str(study / name / 'policy.json'),
               '--mode', variant['mode'], '--output', str(destination / 'result.json')]
    if variant['depth'] is not None:
        command += ['--fixed-depth', str(variant['depth']), '--fixed-window-ms', str(variant['window'])]
    with (destination / 'stdout.log').open('wb') as stdout, (destination / 'stderr.log').open('wb') as stderr:
        started = time.perf_counter()
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        _, status, usage = os.wait4(child.pid, 0)
        wall = time.perf_counter() - started
        child.returncode = os.waitstatus_to_exitcode(status)
    if child.returncode:
        raise RuntimeError(f'{name} exited {child.returncode}; inspect private stderr.log')
    result, reference = read(destination / 'result.json'), read(study / name / 'result.json')
    runtime = result.pop('runtime')
    reference.pop('runtime')
    if result != reference:
        raise RuntimeError(f'Full logical output differs: {name}')
    row = dict(variant=name, build_kind=kind, logical_output_equal_excluding_runtime=True,
               core_processing_ms=runtime['processing_ms'], process_wall_s=wall,
               process_user_s=usage.ru_utime, process_system_s=usage.ru_stime,
               process_maxrss_bytes=usage.ru_maxrss, maxrss_unit='Darwin wait4 bytes',
               output_sha256=digest(destination / 'result.json'))
    if kind == 'optimized_instrumented':
        row['instrumentation'] = summarize_profile(read(destination / 'stderr.log'))
    write(destination / 'metrics.json', row)
    print(f'{kind} {name}: {runtime["processing_ms"]:.3f} ms core; full logical output equal', flush=True)
    return row


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Fresh directory outside the repository')
    parser.add_argument('--study', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--binary', type=Path, help='Optimized Release AggregationReplay; copied before runs')
    parser.add_argument('--patch', type=Path, default=here / 'prefix_runtime_instrumentation.patch')
    parser.add_argument('--source-hashes', type=Path, default=here / 'prefix_runtime_source_hashes.json')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--wait-for-start', type=Path, help='Optional external signal file after native build; avoids test contention')
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    if platform.system() != 'Darwin':
        raise ValueError('This timing/RSS reproduction is specified for macOS')
    if output == root or root in output.parents:
        raise ValueError('Output must be outside the repository')
    if output.exists():
        raise ValueError('Output directory must be fresh')
    study = (args.study or root / 'results/moving-scoped-comparison-2026-10-22').resolve()
    source = (args.source or root / 'results/moving-replay-2026-10-21/n500/capture/observations.json').resolve()
    binary = (args.binary or root / 'simulator/build/AggregationReplay').resolve()
    expected = read(args.source_hashes)
    for relative, wanted in expected.items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or path.parts[0] != 'simulator':
            raise ValueError('Unsafe source manifest path')
        original = root / path
        if wanted is None:
            if original.exists():
                raise ValueError(f'Diagnostic file already exists in production: {relative}')
        elif digest(original) != wanted:
            raise ValueError(f'Production source changed; review instrumentation first: {relative}')
    authenticated = verify_frozen_artifacts(study)
    artifacts = {'optimized_binary': binary, 'source': source, 'study_manifest': study / 'study-manifest.json',
                 'optimization_protocol': root / 'docs/PREFIX_OWNER_LOOKUP_PROTOCOL_2026-10-23.md'}
    artifacts.update({name: study / name for name in authenticated})
    before = {key: digest(value) for key, value in artifacts.items()}
    if before['source'] != OBSERVATIONS_SHA256:
        raise ValueError('Unexpected frozen observation capture')
    output.mkdir(mode=0o700)
    isolated = output / 'isolated'
    for relative, wanted in expected.items():
        if wanted is None:
            continue
        target = isolated / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
    patch = args.patch.resolve()
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=isolated, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=isolated, check=True)
    optimized = output / 'AggregationReplay.optimized'
    shutil.copy2(binary, optimized)
    write(output / 'preflight.json', dict(schema='ump.prefix-runtime-preflight.v1',
        input_sha256=before, pinned_study_manifest_sha256=STUDY_MANIFEST_SHA256,
        authenticated_study_artifacts_sha256=authenticated, patch_sha256=digest(patch),
        source_manifest_sha256=digest(args.source_hashes), optimized_source_sha256=expected,
        native_matrix=[v['id'] for v in variants()], production_modified=False, database_access=False,
        prepared_sources_sha256={str(path.relative_to(isolated)): digest(path)
            for path in sorted(isolated.rglob('*')) if path.is_file()}))
    if args.prepare_only:
        print('Verified inputs and prepared isolated instrumentation; no compilation or execution.')
        return
    project = isolated / 'simulator'
    cmake = '''cmake_minimum_required(VERSION 3.12)
project(UMPPrefixRuntimeDiagnostic LANGUAGES CXX)
find_package(SFML 3.0.0 COMPONENTS Graphics Window System REQUIRED)
find_package(yaml-cpp REQUIRED)
add_executable(AggregationReplayInstrumented tools/AggregationReplay.cpp
'''+ ''.join('src/' + name + '.cpp\n' for name in SOURCES) + ''')
target_compile_features(AggregationReplayInstrumented PRIVATE cxx_std_17)
target_compile_options(AggregationReplayInstrumented PRIVATE -O3)
target_include_directories(AggregationReplayInstrumented PRIVATE include)
target_link_libraries(AggregationReplayInstrumented PRIVATE SFML::Graphics yaml-cpp::yaml-cpp)
'''
    (project / 'CMakeLists.txt').write_text(cmake)
    build = output / 'build'
    subprocess.run(['cmake', '-S', str(project), '-B', str(build), '-DCMAKE_BUILD_TYPE=Release',
                    '-DCMAKE_OSX_ARCHITECTURES=' + platform.machine()], check=True)
    subprocess.run(['cmake', '--build', str(build), '--parallel', '4'], check=True)
    if args.wait_for_start:
        print('Instrumentation built; waiting for start signal: ' + str(args.wait_for_start), flush=True)
        while not args.wait_for_start.exists():
            time.sleep(.25)
    rows = []
    specs = {v['id']: v for v in variants()}
    # Fresh controls bracket the matrix/profile for the changed local coordinator.
    rows.append(execute(study / 'AggregationReplay.frozen', source, study,
        specs['cell_local_temporal_first'], output / 'old_local_control', 'frozen_control'))
    for variant in variants():
        rows.append(execute(optimized, source, study, variant, output / variant['id'], 'optimized'))
    for name in CONTROLS:
        rows.append(execute(build / 'AggregationReplayInstrumented', source, study, specs[name],
            output / (name + '_instrumented'), 'optimized_instrumented'))
    rows.append(execute(optimized, source, study, specs['cell_local_temporal_first'],
        output / 'optimized_local_repeat', 'optimized_repeat'))
    after = {key: digest(value) for key, value in artifacts.items()}
    if before != after:
        raise RuntimeError('Frozen input or optimized build changed during measurement')
    for relative, wanted in expected.items():
        if wanted is not None and digest(root / relative) != wanted:
            raise RuntimeError('Production source changed during reproduction')
    write(output / 'summary.json', dict(schema='ump.prefix-runtime-results.v1', rows=rows,
        verified_complete=True, logical_output_equality_count=len(rows),
        original_inputs_unchanged=True, optimized_sources_unchanged=True, input_sha256=before,
        pinned_study_manifest_sha256=STUDY_MANIFEST_SHA256,
        authenticated_study_artifacts_sha256=authenticated,
        optimized_binary_sha256=digest(optimized),
        instrumented_binary_sha256=digest(build / 'AggregationReplayInstrumented'),
        source_manifest_sha256=digest(args.source_hashes), patch_sha256=digest(patch),
        notes=['Inclusive scopes overlap and must not be summed.',
               'Map lookup probes count find calls, not internal map key comparisons.',
               'Timing differences include instrumentation perturbation and uncontrolled run-to-run variation.',
               'Tick timing is unpaced replay service time; FIFO calculations are a model, not a live benchmark.',
               'Peak RSS includes whole-input parsing and private output retention, not only online history.',
               'One movement realization; native repetitions do not create scientific replicates.']))


if __name__ == '__main__':
    main()
