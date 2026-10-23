#!/usr/bin/env python3
"""Compile the actual PolicyTree core and validate one bounded raster export.

No MongoDB, movement generation or rendering window is used. Requires an existing
semantic static library and pkg-config packages sfml-graphics and yaml-cpp.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument('--source', type=pathlib.Path,
                        default=pathlib.Path(__file__).with_name('check_policy.cpp'))
    parser.add_argument('--input', type=pathlib.Path, required=True)
    parser.add_argument('--out', type=pathlib.Path, required=True)
    parser.add_argument('--semantic-library', type=pathlib.Path)
    args = parser.parse_args()
    repo, source, input_path = args.repo.resolve(), args.source.resolve(), args.input.resolve()
    out = args.out.resolve()
    if out == input_path or out == source:
        parser.error('--out must not overwrite an input or the probe source')
    sources = [repo/'simulator/src'/name for name in
               ['PolicyTree.cpp', 'CandidateMetrics.cpp', 'PolicyConfiguration.cpp',
                'AggregationConfiguration.cpp', 'Region.cpp']]
    semantic = (args.semantic_library or repo/'simulator/build/libump_semantic.a').resolve()
    for path in [source, input_path, semantic, *sources]:
        if not path.is_file():
            parser.error(f'Required file missing: {path}; build the simulator first if needed')
    pkg_config = shutil.which('pkg-config')
    if not pkg_config:
        parser.error('pkg-config is required; install the SFML and yaml-cpp development packages')
    metadata = subprocess.run([pkg_config, '--cflags', '--libs', 'sfml-graphics', 'yaml-cpp'],
                              text=True, capture_output=True, check=True)
    flags = shlex.split(metadata.stdout)
    rpaths = [f'-Wl,-rpath,{item[2:]}' for item in flags if item.startswith('-L')]
    compiler = shlex.split(os.environ.get('CXX', 'c++'))
    recorded = {str(p.relative_to(repo)):digest(p) for p in sources}
    for header in sorted((repo/'simulator/include').glob('*')):
        if header.suffix in {'.hpp', '.h', '.tpp'}:
            recorded[str(header.relative_to(repo))] = digest(header)
    before = input_path.read_bytes()
    with tempfile.TemporaryDirectory(prefix='ump-osm-policy-probe-') as temp:
        binary = pathlib.Path(temp)/'check_policy'
        command = [*compiler, '-O3', '-DNDEBUG', '-std=c++17', '-I', str(repo/'simulator/include'),
                   str(source), *map(str,sources), str(semantic), *flags, *rpaths, '-o', str(binary)]
        subprocess.run(command, check=True)
        result = subprocess.run([str(binary), str(input_path)], text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'Production probe failed without an error message')
        report = json.loads(result.stdout)
        if report.get('status') != 'pass':
            raise RuntimeError('Production probe did not report success')
        if input_path.read_bytes() != before:
            raise RuntimeError('Input changed while validation was running')
        for relative, sha in recorded.items():
            if digest(repo/relative) != sha:
                raise RuntimeError(f'Production source changed during compilation: {relative}')
        report.update({'policy_sha256':hashlib.sha256(before).hexdigest(),
                       'probe_source_sha256':digest(source),
                       'build':{'compiler_command':command,
                                'production_source_sha256':recorded,
                                'semantic_library_sha256':digest(semantic),
                                'binary_sha256':digest(binary),
                                'pkg_config_packages':['sfml-graphics','yaml-cpp']}})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'build'}))


if __name__ == '__main__':
    main()
