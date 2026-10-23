#!/usr/bin/env python3
"""Run one same-input diagnostic variant and retain compact timing evidence."""
import argparse, hashlib, json, os, subprocess, time
from collections import defaultdict
from pathlib import Path

INPUT_SHA='ab4fadf254bfb5432018ff4bd305cd16d82a7475ae3d934c14c4f9af67dd5cf1'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def percentile(values,p):
    values=sorted(values)
    return values[max(0,min(len(values)-1,int((len(values)-1)*p+.5)))] if values else None

def summarize(events):
    grouped=defaultdict(list)
    for row in events:grouped[row['stage']].append(row)
    return {name:{'calls':len(rows),'total_ms':sum(r['duration_ms'] for r in rows),
        'mean_ms':sum(r['duration_ms'] for r in rows)/len(rows),
        'p50_ms':percentile([r['duration_ms'] for r in rows],.5),
        'p95_ms':percentile([r['duration_ms'] for r in rows],.95),
        'maximum_ms':max(r['duration_ms'] for r in rows),
        'count_sum':sum(r['count'] for r in rows)} for name,rows in sorted(grouped.items())}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True,type=Path);p.add_argument('--binary',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--mode',required=True,choices=['full','off','disabled']);p.add_argument('--snapshots',action='store_true');p.add_argument('--protocol',required=True,type=Path)
    a=p.parse_args();root=a.repo.resolve();out=a.output.resolve();protocol=a.protocol.resolve()
    protocol_sha256=digest(protocol)
    if out.exists() or root==out or root in out.parents:raise ValueError('Fresh external output required')
    input_file=root/'results/moving-replay-2026-10-21/n500/capture/observations.json'
    policy=root/'tools/profiling/live/semantic_local_policy.json'
    if digest(input_file)!=INPUT_SHA:raise ValueError('Unexpected retained frozen input')
    out.mkdir(parents=True,mode=0o700);(out/'diagnostics').mkdir(mode=0o700)
    env=dict(os.environ,UMP_LIVE_TIMING_PATH=str(out/'events.jsonl'),UMP_DIAGNOSTIC_PROFILE_DIR=str(out/'diagnostics'),
        UMP_DIAGNOSTIC_PROFILE_MODE=a.mode,UMP_DIAGNOSTIC_PROFILE_SNAPSHOTS='1' if a.snapshots else '0')
    args=[str(a.binary.resolve()),'--input',str(input_file),'--config',str(policy),'--mode','semantic_first','--output',str(out/'result.json')]
    started=time.monotonic()
    with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
        subprocess.run(args,env=env,stdout=stdout,stderr=stderr,check=True,timeout=240)
    elapsed=time.monotonic()-started
    result=json.loads((out/'result.json').read_text());events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()]
    logical={k:v for k,v in result.items() if k!='runtime'}
    artifacts=[]
    for file in sorted(out.rglob('*')):
        if file.is_file():artifacts.append({'path':str(file.relative_to(out)),'bytes':file.stat().st_size,'sha256':digest(file)})
    summary={'schema':'ump.diagnostic-profile-run.v1','mode':a.mode,'renderer_progress_snapshots':a.snapshots,
        'adapter_scope':'Production diagnostic sinks and controller/publication core on retained 20-s input; advance(0), then advance every50ms before100ms ingest; no motion, MongoDB, SFML renderer draw or transport.',
        'binary_sha256':digest(a.binary),'input_sha256':INPUT_SHA,'policy_sha256':digest(policy),
        'process_wall_seconds':elapsed,'runtime':result['runtime'],
        'measured_processing_scope':'Core processing in production50msorder, enabled diagnostic construction/JSON/filewrite/flush, selection copy, optional renderer progress snapshots and in-memory replay serialization; excludes input parsing/validation, final result file I/O, motion, MongoDB and renderer draw.',
        'runtime_scope_note':'The explicitly stated measured_processing_scope governs this adapter, including for the first baseline whose inherited stock replay scope excluded file I/O.',
        'logical_result_sha256':hashlib.sha256(json.dumps(logical,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'protocol_sha256':protocol_sha256,'runner_sha256':digest(Path(__file__)),
        'input_contributions':result['input_observation_contributions'],'accounted_contributions':result['accounted_observation_contributions'],
        'windows':len(result['windows']),'releases':len(result['releases']),
        'stages':summarize(events),'step_classes':{label:{
            'calls':len(rows),'total_ms':sum(row['duration_ms'] for row in rows),
            'p95_ms':percentile([row['duration_ms'] for row in rows],.95),
            'maximum_ms':max((row['duration_ms'] for row in rows),default=0),
            'over_50_ms':sum(row['duration_ms']>50 for row in rows),
            'over_100_ms':sum(row['duration_ms']>100 for row in rows)}
            for label,rows in {
                'all_50ms_source_steps':[row for row in events if row['stage']=='profile_step'],
                '100ms_sample_steps':[row for row in events if row['stage']=='profile_step' and row['logical_ms']>0 and row['logical_ms']%100==0],
                'no_sample_steps':[row for row in events if row['stage']=='profile_step' and not (row['logical_ms']>0 and row['logical_ms']%100==0)],
                'finish':[row for row in events if row['stage']=='profile_finish']}.items()},'artifacts':artifacts}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
