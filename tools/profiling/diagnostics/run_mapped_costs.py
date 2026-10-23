#!/usr/bin/env python3
"""Profile a copied native mapped configuration in fresh retained UUID databases.

Requires PyYAML and the mapped replay export dependencies. Full movement and traces
stay local. Does not delete databases, alter the source scene or weaken journaling.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

import yaml

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'tools/profiling/live'))
from live_measurement import summaries, validate_trace


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-scene', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, binary, out = (p.resolve() for p in
                           (args.source_scene, args.binary, args.output))
    if out.exists() or out == source or source in out.parents:
        parser.error('Choose a fresh output outside the frozen source scene')
    if REPO in out.parents and REPO / 'results' not in out.parents:
        parser.error('Generated repository-local data must stay under ignored results/')
    cfg = yaml.safe_load((source / 'config.yaml').read_text())
    source_hash = digest(source / 'config.yaml')
    duration = cfg['simulation']['duration_seconds']
    if (cfg['simulation'].get('scenario') != 'mapped_visits'
            or cfg['simulation']['time_step'] != .05 or not 1 <= duration <= 300
            or cfg['database'].get('clear_database') is not False
            or len(cfg['sensors']) != 1):
        parser.error('Requires bounded mapped source, 50-ms steps, one AGBS and no database clearing')
    sensor = cfg['sensors'][0]
    if (sensor['type'] != 'adaptive-grid-based'
            or sensor['aggregation']['publication'].get('journal_empty_retirements', True) is not True):
        parser.error('Full private retirement journal is required')
    shell = shutil.which('mongosh')
    if not shell or not binary.is_file():
        parser.error('mongosh and an existing instrumented binary are required')
    names = ['UMP_Mapped_' + uuid.uuid4().hex]
    names += [names[0] + '_Releases', names[0] + '_Private']
    script = ('const names=' + json.dumps(names) + '; print(JSON.stringify(names.filter(n=>'
              'db.getSiblingDB(n).getCollectionNames().length)));')
    existing = subprocess.check_output([shell,
        'mongodb://localhost:27017/?serverSelectionTimeoutMS=3000',
        '--quiet', '--eval', script], text=True, timeout=20)
    if json.loads(existing) != []:
        raise RuntimeError('Refusing existing mapped namespace')
    out.mkdir(parents=True, mode=0o700)
    scene = out / 'scene'
    scene.mkdir(mode=0o700)
    cfg['renderer']['show_renderer'] = False
    # Equal absolute origin is necessary for exact independent source comparisons.
    cfg['simulation']['datetime'] = '2026-10-23T12:00:00Z'
    cfg['database']['db_name'] = names[0]
    sensor['database']['db_name'] = names[0]
    sensor['aggregation']['publication'].update(database=names[1], journal_database=names[2])
    (scene / 'config.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    for name in ['map_background.png', 'scene_manifest.json']:
        shutil.copyfile(source / name, scene / name)
    binary_hash = digest(binary)
    env = os.environ.copy()
    env['UMP_LIVE_TIMING_PATH'] = str(out / 'timing.jsonl')
    started = time.perf_counter()
    with (out / 'stdout.log').open('x') as stdout, (out / 'stderr.log').open('x') as stderr:
        subprocess.run([str(binary)], cwd=scene, env=env, stdout=stdout,
                       stderr=stderr, check=True, timeout=300)
    elapsed = time.perf_counter() - started
    if digest(binary) != binary_hash or digest(source / 'config.yaml') != source_hash:
        raise RuntimeError('Input or executable changed during measurement')
    execution = {'schema': 'ump.mapped-execution.v1', 'state': 'complete', 'exit_code': 0,
                 'config_sha256': digest(scene / 'config.yaml'),
                 'binary_sha256': binary_hash, 'binary_wall_seconds': elapsed}
    (scene / 'execution.json').write_text(json.dumps(execution, indent=2) + '\n')
    events = [json.loads(line) for line in (out / 'timing.jsonl').read_text().splitlines()]
    result = {'schema': 'ump.mapped-mongo-cost.v1', 'execution': execution,
              'source_config_sha256': source_hash, 'runner_sha256': digest(Path(__file__)),
              'databases': names,
              'trace': validate_trace(events, round(duration * 1000), False),
              'stages': summaries(events)}
    (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    with (out / 'export.log').open('x') as log:
        subprocess.run([sys.executable, str(REPO / 'tools/mapped_scene/export_replay.py'),
                        '--scene', str(scene), '--output', str(out / 'replay')],
                       check=True, stdout=log, timeout=300)
    print(json.dumps({'output': str(out), 'wall_seconds': elapsed,
                      'steps': result['trace']['source_steps'], 'databases_retained': names}))


if __name__ == '__main__':
    main()
