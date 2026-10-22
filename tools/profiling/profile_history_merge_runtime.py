#!/usr/bin/env python3
"""Authenticate sequential history/merge performance gates against frozen outputs.

macOS only. All native outputs and instrumented copied sources stay outside Git.
"""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import profile_prefix_runtime as shared


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--study', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--patch', type=Path)
    parser.add_argument('--source-hashes', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--stage', choices=('baseline','history','merge'), required=True)
    parser.add_argument('--source-root', type=Path, help='Frozen production source snapshot; root remains the study/protocol location')
    parser.add_argument('--protocol', type=Path)
    parser.add_argument('--profile-repeats', type=int, help='Default: one for baseline/history, three for merge')
    parser.add_argument('--local-repeat', action='store_true')
    parser.add_argument('--wait-for-start', type=Path)
    args = parser.parse_args()
    args.patch = args.patch or here / ('history_merge_' + args.stage + '_instrumentation.patch')
    args.source_hashes = args.source_hashes or here / ('history_merge_' + args.stage + '_source_hashes.json')
    if args.profile_repeats is None:
        args.profile_repeats = 3 if args.stage == 'merge' else 1
    root, output = args.root.resolve(), args.output.resolve()
    source_root = (args.source_root or root).resolve()
    if args.profile_repeats < 1 or args.profile_repeats > 10:
        raise ValueError('Detailed profile repeat count must be 1..10')
    if platform.system() != 'Darwin':
        raise ValueError('The native CPU/RSS method is specified for macOS')
    if output.exists() or output == root or root in output.parents:
        raise ValueError('Output must be a fresh directory outside the repository')
    study = (args.study or root / 'results/moving-scoped-comparison-2026-10-22').resolve()
    source = (args.source or root / 'results/moving-replay-2026-10-21/n500/capture/observations.json').resolve()
    binary = (args.binary or root / 'simulator/build/AggregationReplay').resolve()
    expected = shared.read(args.source_hashes)
    for relative, wanted in expected.items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or path.parts[0] != 'simulator':
            raise ValueError('Unsafe source manifest path')
        original = source_root / path
        if wanted is None:
            if original.exists():
                raise ValueError('Diagnostic-only header exists in production: ' + relative)
        elif shared.digest(original) != wanted:
            raise ValueError('Production source changed; review instrumentation: ' + relative)
    verified = shared.verify_frozen_artifacts(study)
    artifacts = {'optimized_binary': binary, 'source': source,
                 'protocol': (args.protocol or root / 'docs/HISTORY_MERGE_OPTIMIZATION_PROTOCOL_2026-10-23.md').resolve(),
                 'study_manifest': study / 'study-manifest.json'}
    artifacts.update({name: study / name for name in verified})
    before = {name: shared.digest(path) for name, path in artifacts.items()}
    if before['source'] != shared.OBSERVATIONS_SHA256:
        raise ValueError('Unexpected frozen source capture')
    output.mkdir(mode=0o700)
    isolated = output / 'isolated'
    for relative, wanted in expected.items():
        if wanted is None:
            continue
        target = isolated / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative, target)
    patch = args.patch.resolve()
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=isolated, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=isolated, check=True)
    optimized = output / 'AggregationReplay.optimized'
    shutil.copy2(binary, optimized)
    shared.write(output / 'preflight.json', dict(schema='ump.history-merge-runtime-preflight.v1',
        input_sha256=before, authenticated_artifacts_sha256=verified,
        source_sha256=expected, source_manifest_sha256=shared.digest(args.source_hashes),
        patch_sha256=shared.digest(patch), harness_sha256=shared.digest(__file__),
        helper_sha256=shared.digest(shared.__file__), production_modified=False,
        native_variants=[v['id'] for v in shared.variants() if args.stage != 'baseline' or v['id'] == 'cell_local_temporal_first'], detailed_repeats=args.profile_repeats, stage=args.stage, local_native_repeat=args.local_repeat,
        prepared_sources_sha256={str(p.relative_to(isolated)): shared.digest(p)
            for p in sorted(isolated.rglob('*')) if p.is_file()}))
    if args.prepare_only:
        print('Authenticated source/study and prepared isolated instrumentation; no native execution.')
        return
    project = isolated / 'simulator'
    cmake = '''cmake_minimum_required(VERSION 3.12)
project(UMPOccupiedRuntimeDiagnostic LANGUAGES CXX)
find_package(SFML 3.0.0 COMPONENTS Graphics Window System REQUIRED)
find_package(yaml-cpp REQUIRED)
add_executable(AggregationReplayInstrumented tools/AggregationReplay.cpp
''' + ''.join('src/' + name + '.cpp\n' for name in shared.SOURCES) + ''')
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
        print('Built; waiting for start signal: ' + str(args.wait_for_start), flush=True)
        while not args.wait_for_start.exists():
            time.sleep(.25)
    rows = []
    variants = [v for v in shared.variants() if args.stage != 'baseline' or v['id'] == 'cell_local_temporal_first']
    local = next(v for v in variants if v['id'] == 'cell_local_temporal_first')
    for variant in variants:
        rows.append(shared.execute(optimized, source, study, variant,
            output / variant['id'], args.stage + '_native'))
    for repeat in range(1, args.profile_repeats + 1):
        destination = output / f'local_instrumented_{repeat}'
        row = shared.execute(build / 'AggregationReplayInstrumented', source, study,
            local, destination, args.stage + '_detailed')
        profile = shared.read(destination / 'stderr.log')
        if any(not math.isfinite(t['thread_cpu_ms']) or t['thread_cpu_ms'] < 0 for t in profile['ticks']):
            raise ValueError('Invalid thread CPU duration')
        row['instrumentation'] = shared.summarize_profile(dict(profile))
        row['top_ticks'] = sorted([t for t in profile['ticks'] if not t['eof']],
            key=lambda t: t['service_ms'], reverse=True)[:10]
        row['previous_max_tick'] = next(t for t in profile['ticks'] if t['logical_ms'] == 15200)
        shared.write(destination / 'detailed_metrics.json', row)
        rows.append(row)
    if args.local_repeat:
        rows.append(shared.execute(optimized, source, study, local,
            output / 'local_optimized_repeat', args.stage + '_native_repeat'))
    after = {name: shared.digest(path) for name, path in artifacts.items()}
    if before != after:
        raise RuntimeError('Source, executable, protocol or frozen artifact changed during measurement')
    for relative, wanted in expected.items():
        if wanted is not None and shared.digest(source_root / relative) != wanted:
            raise RuntimeError('Production source changed during measurement')
    shared.write(output / 'summary.json', dict(schema='ump.history-merge-runtime-results.v1',
        verified_complete=True, full_logical_equality_count=len(rows), rows=rows, stage=args.stage,
        original_inputs_unchanged=True, production_sources_unchanged=True,
        input_sha256=before, instrumented_binary_sha256=shared.digest(build / 'AggregationReplayInstrumented'),
        instrumentation_inclusive_nonadditive=True,
        input_service_excludes_initial_read_and_final_write=True,
        thread_cpu_clock='CLOCK_THREAD_CPUTIME_ID at tick start/end'))
    print(f'Verified complete: all {len(rows)} native outputs equal their frozen reference.', flush=True)


if __name__ == '__main__':
    main()
