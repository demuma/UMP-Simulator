#!/usr/bin/env python3
"""Run a fresh mapped visit scene using the maintained Simulator binary.

Keeps the owned MongoDB data by default for inspection. --cleanup removes only
the three fresh UUID namespaces created by this invocation, after the run.
"""
import argparse
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import uuid


def mongo(shell, script):
    result = subprocess.run([shell, 'mongodb://localhost:27017/?serverSelectionTimeoutMS=3000',
                             '--quiet', '--eval', script], text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'MongoDB command failed')
    return json.loads(result.stdout.strip().splitlines()[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--duration-s', type=int, default=90)
    parser.add_argument('--seed', type=int, default=20261023)
    parser.add_argument('--output', type=pathlib.Path)
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    repo = pathlib.Path(__file__).resolve().parents[2]
    binary = repo/'simulator/build/Simulator'
    shell = shutil.which('mongosh')
    if not binary.is_file() or not shell:
        parser.error('Build simulator/build/Simulator and make mongosh available first')
    missing = [m for m in ['yaml','shapely','matplotlib','numpy','pyproj'] if importlib.util.find_spec(m) is None]
    if missing:
        parser.error('Use a Python environment with tools/mapped_scene/requirements.txt; missing: '+', '.join(missing))
    database = 'UMP_Mapped_'+uuid.uuid4().hex
    names = [database,database+'_Releases',database+'_Private']
    existing = mongo(shell, 'const names='+json.dumps(names)+'; print(JSON.stringify(names.filter(n => '
        'db.getSiblingDB(n).getCollectionNames().length>0)));')
    if existing:
        raise RuntimeError('Fresh namespace collision; refusing to reuse data')
    output = args.output or pathlib.Path(tempfile.mkdtemp(prefix='ump-mapped-visits-'))/'scene'
    command = [sys.executable,str(pathlib.Path(__file__).with_name('build_mapped_scene.py')),
               '--repo',str(repo),'--output',str(output),'--database',database,
               '--duration-s',str(args.duration_s),'--seed',str(args.seed)]
    if args.render:
        command.append('--render')
    subprocess.run(command,check=True)
    print('Scene: '+str(output.resolve()),flush=True)
    print('Owned MongoDB databases: '+', '.join(names),flush=True)
    print('Private GT identity is separate from visible observation tracks.',flush=True)
    try:
        return subprocess.run([str(binary)],cwd=output).returncode
    finally:
        if args.cleanup:
            result = mongo(shell,'const names='+json.dumps(names)+'; for(const n of names) db.getSiblingDB(n).dropDatabase(); '
                'print(JSON.stringify({remaining:names.filter(n=>db.getSiblingDB(n).getCollectionNames().length>0)}));')
            if result['remaining']:
                raise RuntimeError('Owned database cleanup failed: '+str(result['remaining']))
            print('Removed the three owned test databases.',flush=True)


if __name__=='__main__':
    raise SystemExit(main())
