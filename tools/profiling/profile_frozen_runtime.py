#!/usr/bin/env python3
"""Reproduce scoped timing without editing the production tree or opening MongoDB.

Requires the frozen local capture/study and macOS native dependencies. Raw result
files stay in the requested fresh output directory; only summary.json is compact.
"""
import argparse
import hashlib
import json
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
VARIANTS = ('fixed_10m_400ms', 'common_window_temporal_first', 'cell_local_temporal_first')
STUDY_MANIFEST_SHA256 = 'e81b724b673ac5f8e77ddd483b41b4ec2756206fbd32ccf2455e14bd234dc83f'
OBSERVATIONS_SHA256 = 'ab4fadf254bfb5432018ff4bd305cd16d82a7475ae3d934c14c4f9af67dd5cf1'


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
    """Authenticate the frozen study before launching any native executable."""
    manifest_path = Path(study) / 'study-manifest.json'
    if digest(manifest_path) != STUDY_MANIFEST_SHA256:
        raise ValueError('Study manifest differs from the pinned verified study')
    manifest = read(manifest_path)
    expected = manifest.get('artifacts_sha256', {})
    names = ['AggregationReplay.frozen']
    names += [variant + '/' + filename for variant in VARIANTS
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


def execute(binary, source, study, variant, destination, instrumented):
    destination.mkdir(mode=0o700)
    command = [str(binary), '--input', str(source), '--config', str(study / variant / 'policy.json'),
               '--mode', 'fixed' if variant.startswith('fixed') else 'semantic_first',
               '--output', str(destination / 'result.json')]
    if variant.startswith('fixed'):
        command += ['--fixed-depth', '3', '--fixed-window-ms', '400']
    with (destination / 'stdout.log').open('wb') as stdout, (destination / 'stderr.log').open('wb') as stderr:
        started = time.perf_counter()
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        _, status, usage = os.wait4(child.pid, 0)
        wall = time.perf_counter() - started
        child.returncode = os.waitstatus_to_exitcode(status)
    if child.returncode:
        raise RuntimeError(f'{variant} exited {child.returncode}; inspect private stderr.log')
    result, reference = read(destination / 'result.json'), read(study / variant / 'result.json')
    runtime = result.pop('runtime')
    reference.pop('runtime')
    if result != reference:
        raise RuntimeError(f'Full logical output differs: {variant}')
    row = dict(variant=variant, instrumented=instrumented, logical_output_equal_excluding_runtime=True,
               core_processing_ms=runtime['processing_ms'], process_wall_s=wall,
               process_user_s=usage.ru_utime, process_system_s=usage.ru_stime,
               process_maxrss_bytes=usage.ru_maxrss, maxrss_unit='Darwin wait4 bytes',
               output_sha256=digest(destination / 'result.json'))
    if instrumented:
        profile = read(destination / 'stderr.log')
        if profile.get('schema') != 'ump.scoped-runtime-instrumentation.v1':
            raise RuntimeError('Unexpected instrumentation schema')
        row['instrumentation'] = profile  # Only counters and timing, never source rows/identities.
    write(destination / 'metrics.json', row)
    print(f'{variant}: {runtime["processing_ms"]:.3f} ms core; full logical output equal', flush=True)
    return row


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Unmodified UMP-Simulator repository')
    parser.add_argument('--output', type=Path, required=True, help='Fresh directory outside the repository')
    parser.add_argument('--study', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--patch', type=Path, default=here / 'runtime_instrumentation.patch')
    parser.add_argument('--source-hashes', type=Path, default=here / 'runtime_profile_source_hashes.json')
    parser.add_argument('--prepare-only', action='store_true', help='Verify source and apply isolated patch; do not build/run')
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    if platform.system() != 'Darwin':
        raise ValueError('This timing/RSS reproduction is specified for macOS')
    if output == root or root in output.parents:
        raise ValueError('Use an output directory outside the repository to keep raw local results out of Git')
    if output.exists():
        raise ValueError('Output directory must be fresh')
    study = (args.study or root / 'results/moving-scoped-comparison-2026-10-22').resolve()
    source = (args.source or root / 'results/moving-replay-2026-10-21/n500/capture/observations.json').resolve()
    expected = read(args.source_hashes)
    for relative, wanted in expected.items():
        relative_path = Path(relative)
        if relative_path.is_absolute() or '..' in relative_path.parts or relative_path.parts[0] != 'simulator':
            raise ValueError('Unsafe source manifest path')
        original = root / relative_path
        if wanted is None:
            if original.exists():
                raise ValueError(f'Diagnostic file already exists in production: {relative}')
        elif digest(original) != wanted:
            raise ValueError(f'Production source changed; review instrumentation first: {relative}')
    authenticated_artifacts = verify_frozen_artifacts(study)
    binary = study / 'AggregationReplay.frozen'
    artifacts = {'binary': binary, 'source': source, 'study_manifest': study / 'study-manifest.json'}
    for variant in VARIANTS:
        artifacts[variant + '_policy'] = study / variant / 'policy.json'
        artifacts[variant + '_reference'] = study / variant / 'result.json'
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
    write(output / 'preflight.json', dict(schema='ump.runtime-diagnostic-reproduction.v1',
        input_sha256=before, pinned_study_manifest_sha256=STUDY_MANIFEST_SHA256,
        authenticated_study_artifacts_sha256=authenticated_artifacts,
        patch_sha256=digest(patch), source_manifest_sha256=digest(args.source_hashes),
        native_matrix=list(VARIANTS), production_modified=False, database_access=False,
        prepared_sources_sha256={str(path.relative_to(isolated)): digest(path)
            for path in sorted(isolated.rglob('*')) if path.is_file()}))
    if args.prepare_only:
        print('Verified source and prepared isolated instrumentation; no compilation or execution.')
        return
    project = isolated / 'simulator'
    cmake = '''cmake_minimum_required(VERSION 3.12)
project(UMPRuntimeDiagnostic LANGUAGES CXX)
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
    rows = []
    for instrumented, executable in ((False, binary), (True, build / 'AggregationReplayInstrumented')):
        for variant in VARIANTS:
            suffix = '_instrumented' if instrumented else '_control'
            rows.append(execute(executable, source, study, variant, output / (variant + suffix), instrumented))
    after = {key: digest(value) for key, value in artifacts.items()}
    if before != after:
        raise RuntimeError('Frozen input changed')
    for relative, wanted in expected.items():
        if wanted is not None and digest(root / relative) != wanted:
            raise RuntimeError('Production source changed during reproduction')
    write(output / 'summary.json', dict(schema='ump.runtime-diagnostic-reproduction-results.v1', rows=rows,
        original_inputs_unchanged=True, original_sources_unchanged=True, input_sha256=before,
        pinned_study_manifest_sha256=STUDY_MANIFEST_SHA256,
        authenticated_study_artifacts_sha256=authenticated_artifacts,
        instrumented_binary_sha256=digest(build / 'AggregationReplayInstrumented'),
        notes=['Inclusive scopes overlap and must not be summed.',
               'Timing differences include instrumentation perturbation and uncontrolled run-to-run variation.',
               'Tick timing is unpaced replay service time; FIFO calculations are a model, not a live benchmark.',
               'Peak RSS includes whole-input parsing and private output retention, not only online history.']))


if __name__ == '__main__':
    main()
