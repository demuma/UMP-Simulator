#!/usr/bin/env python3
"""Isolated live-path measurement. Prepare by default; --execute explicitly runs it.

Only freshly-owned UUID databases can be created/audited/removed. Raw state stays
local. Renderer and headless runs are independent stochastic realizations.
"""
import argparse, importlib.util, json, math, os, re, shutil, subprocess, time, uuid
from pathlib import Path
from live_measurement import summaries, validate_trace, validate_mongo_audit

REPO=None
POLICY=None
cap=None

def write(path,value):
 path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');path.chmod(0o600)
def mongo(script): return cap.mongo(shutil.which('mongosh'),script,timeout=120)

def configuration(token,render,duration):
 raw='UMP_Live_'+token+'_raw';public='UMP_Live_'+token+'_release';journal='UMP_Live_'+token+'_journal'
 text=cap.capture_config((REPO/'simulator/examples/temporal-aggregation/config.yaml').read_text(),'UMP_Capture_'+token,num_agents=500,duration_seconds=duration,mixed_taxonomy=cap.behavior_taxonomy((REPO/'simulator/config.yaml').read_text()))
 text=text.replace('UMP_Capture_'+token,raw)
 text=cap.replace_once(text,'  buffer_capacity: 128\n','  buffer_capacity: 8\n')
 text=cap.replace_once(text,'  playback_speed: 0.5\n','  playback_speed: 1.0\n')
 text=cap.replace_once(text,'  show_renderer: false\n',f'  show_renderer: {str(render).lower()}\n  log_playback_timing: true\n')
 policy=json.loads(POLICY.read_text());policy.pop('policy_regions')
 policy.update(enabled=True,diagnostics_directory='diagnostics',publication={'database':public,'collection':'releases','journal_database':journal,'journal_collection':'publication_journal','max_document_bytes':8388608,'max_attempts':3,'journal_empty_retirements':False})
 text=cap.replace_once(text,'    aggregation:\n      enabled: false\n','    aggregation: '+json.dumps(policy,separators=(',',':'))+'\n')
 text=text.split('# Legacy fields remain')[0]+'region_taxonomy: []\nregions: []\n'
 if 'Simulation' in text or 'clear_database: true' in text or text.count(raw)!=2:raise ValueError('Unsafe live config')
 return text,[raw,public,journal],policy

def main():
 global REPO,POLICY,cap
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--policy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--simulator',type=Path,required=True);p.add_argument('--renderer',action='store_true');p.add_argument('--duration',type=int,default=120);p.add_argument('--timeout',type=int,default=600);p.add_argument('--execute',action='store_true');p.add_argument('--export-capture',action='store_true');p.add_argument('--capture-seconds',type=int,default=60);p.add_argument('--keep-databases',action='store_true');a=p.parse_args()
 REPO=a.repo.resolve();POLICY=a.policy.resolve();spec=importlib.util.spec_from_file_location('capture_simulator',REPO/'tools/evaluation/capture_simulator.py');cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
 if not 1<=a.capture_seconds<=a.duration or not 1<=a.duration<=300 or a.timeout<1:raise ValueError('Bounded duration/timeout required')
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);out.chmod(0o700)
 token=uuid.uuid4().hex;config,databases,policy=configuration(token,a.renderer,a.duration)
 (out/'config.yaml').write_text(config);(out/'config.yaml').chmod(0o600)
 manifest={'schema':'ump.live-path-measurement.v1','phase':'prepared','token':token,'databases':databases,'duration_seconds':a.duration,'renderer':a.renderer,'buffer_capacity':8,'production_default_buffer_capacity':128,'capture_seconds':a.capture_seconds if a.export_capture else None,'harness_sha256':cap.digest(Path(__file__)),'capture_helper_sha256':cap.digest(REPO/'tools/evaluation/capture_simulator.py'),'simulator':str(a.simulator.resolve()),'simulator_sha256':cap.digest(a.simulator),'config_sha256':cap.digest(out/'config.yaml'),'semantic_policy':policy,'source_policy_sha256':cap.digest(POLICY),'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'limitations':['Real stochastic simulation, not matched headless/renderer trajectories.','Motion noise depends on real elapsed time.','Renderer is sole pacing owner; headless is unpaced.','Queue write duration includes locking/copying plus waiting.','Instrumentation buffers events privately and adds measurement overhead.','Publication store spans include serialization, journal and acknowledged recipient operations; not network-only latency.','Source-to-display starts at producer state processing; not sensor external arrival time.']}
 write(out/'manifest.json',manifest)
 if not a.execute:print(json.dumps({'status':'prepared','output':str(out),'databases':databases}));return
 script=f'''const names={json.dumps(databases)}, token={json.dumps(token)};
const existing=db.getSiblingDB('admin').runCommand({{listDatabases:1,nameOnly:true}}).databases.map(x=>x.name);
if(names.some(n=>!/^UMP_Live_[0-9a-f]{{32}}_(raw|release|journal)$/.test(n)||existing.includes(n))) throw new Error('Unsafe or existing live namespace');
for(const name of names) db.getSiblingDB(name).getCollection('_live_owner').insertOne({{token,purpose:'live-path-measurement',created_at:new Date()}});
print(JSON.stringify({{owned:names}}));'''
 owned=mongo(script)
 if owned!={'owned':databases}:raise ValueError('Ownership creation mismatch')
 manifest['phase']='running';write(out/'manifest.json',manifest)
 env=os.environ.copy();env['UMP_LIVE_TIMING_PATH']=str(out/'timing.jsonl');started=time.monotonic();rss=[]
 with (out/'stdout.log').open('x') as stdout,(out/'stderr.log').open('x') as stderr:
  process=subprocess.Popen([str(a.simulator.resolve())],cwd=out,stdout=stdout,stderr=stderr,env=env)
  while process.poll() is None:
   if time.monotonic()-started>a.timeout:process.kill();process.wait();raise TimeoutError('Bounded live run timed out; owned databases retained')
   try:
    n=subprocess.check_output(['/bin/ps','-o','rss=','-p',str(process.pid)],text=True).strip()
    if n:rss.append({'wall_s':time.monotonic()-started,'rss_kib':int(n)})
   except subprocess.CalledProcessError:pass
   time.sleep(.5)
  elapsed=time.monotonic()-started
 if process.returncode:raise RuntimeError(f'Simulator failed{process.returncode}; DBs retained')
 logs=(out/'stdout.log').read_text()+(out/'stderr.log').read_text()
 if re.search(r'\b(error|failed|exception|fatal)\b',logs,re.I):raise RuntimeError('Simulator log error; DBs retained')
 events=[json.loads(s) for s in (out/'timing.jsonl').read_text().splitlines()]
 trace_verification=validate_trace(events,a.duration*1000,a.renderer,capacity=8)
 source=[x for x in events if x['stage']=='source_state'];receipts=[x for x in events if x['stage']=='renderer_receipt']
 if len(source)!=a.duration*20 or (a.renderer and len(receipts)!=len(source)):raise ValueError(f'Incomplete source/render cadence{len(source)}/{len(receipts)}')
 audit=mongo(f'''const raw=db.getSiblingDB({json.dumps(databases[0])}),pub=db.getSiblingDB({json.dumps(databases[1])}),journal=db.getSiblingDB({json.dumps(databases[2])});
const origin=raw.Agents.findOne({{data_type:'metadata'}}).timestamp;
const gt_inside=raw.Agents.aggregate([{{$match:{{data_type:'agent data','position.x':{{$gte:0,$lt:80}},'position.y':{{$gte:0,$lt:80}}}}}},{{$group:{{_id:'$timestamp',count:{{$sum:1}}}}}},{{$sort:{{_id:1}}}}]).toArray();
const gt=raw.Agents.aggregate([{{$match:{{data_type:'agent data'}}}},{{$group:{{_id:'$timestamp',count:{{$sum:1}}}}}},{{$sort:{{_id:1}}}}]).toArray();
const sensor=raw.AGB_Sensor_Data_V3.aggregate([{{$match:{{data_type:'adaptive grid data'}}}},{{$group:{{_id:'$timestamp',count:{{$sum:1}},road_users:{{$sum:'$total_agents'}}}}}},{{$sort:{{_id:1}}}}]).toArray();
let reconciled=0;for(const release of pub.releases.find()){{const j=journal.publication_journal.findOne({{_id:release._id,state:'committed'}});if(!j||EJSON.stringify(j.release)!==EJSON.stringify(release))throw new Error('Recipient/journal payload mismatch');++reconciled;}}
print(JSON.stringify({{origin_timestamp:origin,gt_inside_frames:gt_inside,reconciled_release_count:reconciled,gt_frames:gt,sensor_frames:sensor,release_count:pub.releases.countDocuments(),journal_count:journal.publication_journal.countDocuments(),journal_states:journal.publication_journal.aggregate([{{$group:{{_id:'$state',count:{{$sum:1}}}}}}]).toArray(),collections:{json.dumps(databases)}.map(n=>({{database:n,collections:db.getSiblingDB(n).getCollectionNames().sort()}}))}}));''')
 write(out/'mongo-audit.json',audit)
 mongo_verification=validate_mongo_audit(events,audit)
 write(out/'verification.json',{'trace':trace_verification,'mongo':mongo_verification})
 expected_counts=[x['count'] for x in sorted(source,key=lambda x:x['logical_ms']) if x['count']]
 if [x['count'] for x in audit['gt_frames']]!=expected_counts:raise ValueError('Mongo GT populations differ from every nonempty source frame')
 if any(x['_id']!='committed' for x in audit['journal_states']):raise ValueError('Publication journal left pending states')
 acknowledgements=sum(x['stage']=='publication_ack' and x['count']==1 for x in events)
 if audit['release_count']!=audit['journal_count'] or audit['reconciled_release_count']!=audit['release_count']:raise ValueError('Recipient/journal coverage differs')
 if audit['release_count']!=acknowledgements:raise ValueError('Recipient release count differs from acknowledged publication calls')
 # A full replay export is optional and uses the same verified GT/AGBS conversion.
 if a.export_capture:
  # Export only a declared nonempty prefix; every raw file and replay remain <=256MiB.
  rawdir=out/'capture';rawdir.mkdir(mode=0o700)
  exports={}
  # Only this known owned raw DB is exported; helper originally names capture namespaces.
  for collection,name in [('Agents','raw-agents.json'),('AGB_Sensor_Data_V3','raw-agbs.json')]:
   projection={'_id':0,'timestamp':1,'data_type':1,'agent_id':1,'type':1,'position':1,'frame_rate':1,'simulation_area':1,'cell_size':1} if collection=='Agents' else {'_id':0,'timestamp':1,'data_type':1,'sensor_id':1,'cell_id':1,'cell_position':1,'cell_size':1,'agent_type_count':1,'total_agents':1,'max_depth':1,'frame_rate':1,'position':1,'detection_area':1}
   script=f'''const raw=db.getSiblingDB({json.dumps(databases[0])});const origin=raw.Agents.findOne({{data_type:'metadata'}}).timestamp;const c=raw.getCollection({json.dumps(collection)}).find({{timestamp:{{$lt:new Date(origin.getTime()+{a.capture_seconds*1000})}}}},{json.dumps(projection)}).sort({{timestamp:1}});let bytes=4,first=true;print('[');while(c.hasNext()){{const line=(first?'':',')+JSON.stringify(c.next());bytes+=Buffer.byteLength(line)+1;if(bytes>268435456)throw new Error('Raw export budget exceeded');print(line);first=false;}}print(']');'''
   with (rawdir/name).open('x') as f:
    proc=subprocess.run([shutil.which('mongosh'),'mongodb://localhost:27017/?serverSelectionTimeoutMS=5000','--quiet','--eval',script],stdout=f,stderr=subprocess.PIPE,text=True,timeout=a.timeout)
   if proc.returncode:raise RuntimeError('Raw export failed: '+proc.stderr)
   exports[collection]=json.loads((rawdir/name).read_text())
  replay,proof=cap.verify_and_replay(exports['Agents'],exports['AGB_Sensor_Data_V3'],'simulator-live-'+token,a.capture_seconds*1000)
  cap.write_json(rawdir/'observations.json',replay);cap.write_json(rawdir/'capture-proof.json',proof)
  manifest['capture']={'observations_sha256':cap.digest(rawdir/'observations.json'),'proof_sha256':cap.digest(rawdir/'capture-proof.json'),'path':str(rawdir),'prefix_end_ms':a.capture_seconds*1000}
 summary={'wall_seconds':elapsed,'requested_logical_seconds':a.duration,'source_steps':len(source),'renderer_frames':len(receipts),'max_rss_kib':max((x['rss_kib'] for x in rss),default=0),'stages':summaries(events),'mongo_release_count':audit['release_count'],'mongo_journal_count':audit['journal_count']}
 write(out/'rss.json',rss);write(out/'summary.json',summary)
 if cap.digest(a.simulator)!=manifest['simulator_sha256']:raise ValueError('Simulator binary changed during measurement')
 if not a.keep_databases:
  dropped=mongo(f'''const names={json.dumps(databases)},token={json.dumps(token)};for(const n of names){{if(!/^UMP_Live_[0-9a-f]{{32}}_(raw|release|journal)$/.test(n))throw new Error('Unsafe cleanup name');const owners=db.getSiblingDB(n).getCollection('_live_owner').find().toArray();if(owners.length!==1||owners[0].token!==token)throw new Error('Ownership mismatch');}}for(const n of names){{if(db.getSiblingDB(n).dropDatabase().ok!==1)throw new Error('Cleanup failed');}}print(JSON.stringify({{dropped:names}}));''')
  if dropped!={'dropped':databases}:raise ValueError('Cleanup result mismatch')
 manifest['phase']='verified';manifest['databases_dropped']=not a.keep_databases;write(out/'manifest.json',manifest)
 print(json.dumps({'status':'verified','output':str(out),'wall_seconds':elapsed,'max_rss_kib':summary['max_rss_kib'],'databases_dropped':manifest['databases_dropped']}))
if __name__=='__main__':main()
