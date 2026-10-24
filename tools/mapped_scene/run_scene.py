#!/usr/bin/env python3
"""Run and locally record a fresh mapped scene with the maintained Simulator.

Generated movement and replay artifacts are retained under ignored results/ by
 default. --replay serves the verified recording on localhost after completion.
Only explicitly requested --cleanup removes this invocation's three owned DBs.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time
import uuid
import webbrowser


def mongo(shell, script):
    result = subprocess.run([shell, 'mongodb://localhost:27017/?serverSelectionTimeoutMS=3000',
                             '--quiet', '--eval', script], text=True, capture_output=True, timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'MongoDB command failed')
    return json.loads(result.stdout.strip().splitlines()[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true', help='Show the native live window during simulation')
    parser.add_argument('--replay', action='store_true', help='Serve the recorded browser replay after simulation')
    parser.add_argument('--open', action='store_true', help='Open the browser when --replay starts')
    parser.add_argument('--port', type=int, default=8780)
    parser.add_argument('--duration-s', type=int, default=90)
    parser.add_argument('--seed', type=int, default=20261023)
    parser.add_argument('--motion-mode', choices=['integration','corridor','buildings','storefronts'], default='storefronts')
    parser.add_argument('--population', type=int, default=64)
    parser.add_argument('--urban-traffic', action='store_true', help='Opt-in mixed road riders and explicit synthetic crossing corridors')
    parser.add_argument('--subway-access', action='store_true', help='Opt-in A1/A2 surface sources/sinks; requires urban traffic')
    parser.add_argument('--rider-priority', action='store_true', help='Opt-in bounded pedestrian yielding; requires urban traffic')
    parser.add_argument('--road-user-fraction', type=float, default=.2)
    parser.add_argument('--distributed-crossing-fraction', type=float, default=.2)
    parser.add_argument('--pedestrian-clearance-m', type=float, default=.05)
    parser.add_argument('--shop-overrides', type=pathlib.Path, help='Source-bound synthetic shop entrance overrides (storefronts mode only)')
    parser.add_argument('--arrival-interval-ms',type=int)
    parser.add_argument('--experimental-narrow-passages',action='store_true',
        help='EXPERIMENTAL storefront routing and passage coordination; larger-cohort acceptance remains open')
    parser.add_argument('--output', type=pathlib.Path, help='Fresh scene folder; replay becomes its sibling')
    parser.add_argument('--no-record',action='store_true',help='Skip the persistent local recording')
    parser.add_argument('--max-capture-mib',type=int,choices=(256,512,1024,2048),default=2048,
        help='Bounded local source capture file budget (default 2048 MiB); JSON artifacts support up to 2 GiB')
    parser.add_argument('--cleanup', action='store_true', help='Remove only owned DBs after a verified recording/run')
    args = parser.parse_args()
    if args.open and not args.replay: parser.error('--open requires --replay')
    if args.no_record and args.replay: parser.error('--replay requires recording')
    if args.shop_overrides is not None and args.motion_mode != 'storefronts':
        parser.error('--shop-overrides requires --motion-mode storefronts')
    if args.experimental_narrow_passages and args.motion_mode != 'storefronts':
        parser.error('--experimental-narrow-passages requires --motion-mode storefronts')
    if not 1<=args.port<=65535: parser.error('Port must be 1..65535')
    if (args.subway_access or args.rider_priority) and not args.urban_traffic:
        parser.error('--subway-access and --rider-priority require --urban-traffic')
    if args.urban_traffic and args.motion_mode != 'storefronts':
        parser.error('--urban-traffic requires --motion-mode storefronts')
    if args.urban_traffic and args.experimental_narrow_passages:
        parser.error('--urban-traffic and --experimental-narrow-passages are mutually exclusive')
    repo = pathlib.Path(__file__).resolve().parents[2]
    binary = repo/'simulator/build/Simulator'
    shell = shutil.which('mongosh')
    if not binary.is_file() or not shell:
        parser.error('Build simulator/build/Simulator and make mongosh available first')
    missing = [m for m in ['yaml','shapely','matplotlib','numpy','pyproj'] if importlib.util.find_spec(m) is None]
    if missing:
        parser.error('Use a Python environment with tools/mapped_scene/requirements.txt; missing: '+', '.join(missing))
    token=uuid.uuid4().hex
    database = 'UMP_Mapped_'+token
    names = [database,database+'_Releases',database+'_Private']
    existing = mongo(shell, 'const names='+json.dumps(names)+'; print(JSON.stringify(names.filter(n => '
        'db.getSiblingDB(n).getCollectionNames().length>0)));')
    if existing:
        raise RuntimeError('Fresh namespace collision; refusing to reuse data')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = (args.output or repo/'results'/'mapped-visits'/(stamp+'-'+token[:8])/'scene').resolve()
    recording=output.parent/'replay'
    if output.exists() or (not args.no_record and recording.exists()):
        parser.error('Scene/recording folder already exists; choose a fresh --output parent')
    command = [sys.executable,str(pathlib.Path(__file__).with_name('build_mapped_scene.py')),
               '--repo',str(repo),'--output',str(output),'--database',database,
               '--duration-s',str(args.duration_s),'--seed',str(args.seed),
               '--motion-mode',args.motion_mode,'--population',str(args.population)]
    if args.arrival_interval_ms is not None: command += ['--arrival-interval-ms',str(args.arrival_interval_ms)]
    if args.shop_overrides is not None: command += ['--shop-overrides', str(args.shop_overrides.resolve())]
    if args.render: command.append('--render')
    if args.experimental_narrow_passages: command.append('--experimental-narrow-passages')
    if args.subway_access: command.append('--subway-access')
    if args.rider_priority: command.append('--rider-priority')
    if args.urban_traffic:
        command += ['--urban-traffic','--road-user-fraction',str(args.road_user_fraction),
                    '--distributed-crossing-fraction',str(args.distributed_crossing_fraction),
                    '--pedestrian-clearance-m',str(args.pedestrian_clearance_m)]
    subprocess.run(command,check=True)
    print('Scene: '+str(output),flush=True)
    print('Owned MongoDB databases: '+', '.join(names),flush=True)
    print('Private GT identity is separate from visible observation tracks.',flush=True)
    binary_sha=hashlib.sha256(binary.read_bytes()).hexdigest()
    config_sha=hashlib.sha256((output/'config.yaml').read_bytes()).hexdigest()
    started=time.perf_counter()
    result=subprocess.run([str(binary)],cwd=output)
    elapsed=time.perf_counter()-started
    execution={'schema':'ump.mapped-execution.v1','state':'complete' if result.returncode==0 else 'failed',
               'binary_sha256':binary_sha,'config_sha256':config_sha,'exit_code':result.returncode,
               'binary_wall_seconds':elapsed,
               'capture_budget':{'max_capture_mib':args.max_capture_mib,'max_capture_bytes':args.max_capture_mib*1024*1024,
                   'scope':'Local private source export only; generated movement stays outside Git.'},'scope':'Includes native startup, source, aggregation and DB I/O; not a per-step deadline.'}
    if hashlib.sha256(binary.read_bytes()).hexdigest()!=binary_sha:
        execution['state']='binary_changed'
    (output/'execution.json').write_text(json.dumps(execution,indent=2)+'\n')
    if execution['state']=='binary_changed':raise RuntimeError('Native binary changed during the source run; refusing a verified capture')
    if result.returncode:
        print('Simulator failed/cancelled: source databases retained for inspection; no verified replay claimed.',file=sys.stderr)
        return result.returncode
    if not args.no_record:
        subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('export_replay.py')),
                        '--scene',str(output),'--output',str(recording),'--max-capture-mib',str(args.max_capture_mib)],check=True)
        print('Persistent local replay: '+str(recording),flush=True)
    if args.cleanup:
        result = mongo(shell,'const names='+json.dumps(names)+'; for(const n of names) db.getSiblingDB(n).dropDatabase(); '
            'print(JSON.stringify({remaining:names.filter(n=>db.getSiblingDB(n).getCollectionNames().length>0)}));')
        if result['remaining']:
            raise RuntimeError('Owned database cleanup failed: '+str(result['remaining']))
        print('Removed only the three owned test databases; local recording is retained.',flush=True)
    if args.replay:
        if args.open:
            # Opening is user-selected. The server starts next; the tab can reload
            # if its first request races startup. No remote URL or service is used.
            webbrowser.open('http://127.0.0.1:'+str(args.port)+'/')
        return subprocess.run([sys.executable,str(repo/'tools/replay_viewer/serve.py'),
                               '--bundle',str(recording),'--port',str(args.port)]).returncode
    if not args.no_record:
        print('View again: '+sys.executable+' '+str(repo/'tools/replay_viewer/serve.py')
              +' --bundle '+str(recording)+' --port '+str(args.port),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
