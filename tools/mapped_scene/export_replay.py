#!/usr/bin/env python3
"""Persist a verified native mapped run as a private local browser replay.

Reads only the three UUID-owned namespaces declared by the scene configuration.
Never reruns aggregation or infers failed candidate checks. Generated data belong
under ignored results/, not in Git. Stable GT identities remain in a private
sidecar that the replay HTTP server does not serve.
"""
from __future__ import annotations
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import yaml

MAX_BYTES = 256 * 1024 * 1024
GEOMETRY_KEYS = ('cell_id','depth','x','y','width','height')


def insist(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    data = (json.dumps(value, allow_nan=False, separators=(',',':'), ensure_ascii=False)+'\n').encode()
    insist(len(data) <= MAX_BYTES, 'Replay artifact exceeds 256 MiB')
    with path.open('xb') as stream:
        stream.write(data)


def epoch_ms(text):
    value = datetime.fromisoformat(text.replace('Z','+00:00'))
    insist(value.tzinfo is not None, 'GT timestamp needs a UTC offset')
    return round(value.timestamp()*1000)


def cell_id(x, y, coverage):
    n = 1 << coverage['leaf_depth']
    gx = math.floor((x-coverage['x'])/coverage['width']*n)
    gy = math.floor((y-coverage['y'])/coverage['height']*n)
    value = 3
    for bit in range(coverage['leaf_depth']-1,-1,-1):
        value = (value << 2) | ((gx >> bit)&1) | (((gy >> bit)&1)<<1)
    return value


def inside(item, geometry):
    return (geometry['x'] <= item['x'] < geometry['x']+geometry['width']
            and geometry['y'] <= item['y'] < geometry['y']+geometry['height'])


def tighten(*sets):
    result = {}
    for requirements in sets:
        for metric, bounds in requirements.items():
            target = result.setdefault(metric,{})
            if 'min' in bounds: target['min'] = max(target.get('min',-math.inf),bounds['min'])
            if 'max' in bounds: target['max'] = min(target.get('max',math.inf),bounds['max'])
    return result


def regional_metadata(cfg, aggregation):
    types = {item['type']:item for item in cfg.get('region_taxonomy',[])}
    selected = set(aggregation['policy_tree']['regions'])
    rows=[]
    for region in cfg.get('regions',[]):
        if region['id'] not in selected: continue
        requirements=tighten(types[region['type']].get('metric_requirements',{}),region.get('metric_requirements',{}))
        rows.append({'id':region['id'],'type':region['type'],**region['area'],
                     'requirements':[{'metric':metric,**bounds} for metric,bounds in sorted(requirements.items())]})
    return rows


def audit_lifecycle(cfg, raw, frames, person_by_track, origin, step, end, summary):
    """Audit recorded visibility, without replaying motion or reconnecting IDs.

    A completed source clock does not imply drained queues or completed visits.
    The private event stream independently specifies which tracks must have a
    GT state on every source step, including between sensor observations. This
    detects lost GT rows that would otherwise look like measured-empty data.
    It validates the *recorded* lifecycle; it does not prove route realism or
    collision avoidance between source steps.
    """
    def count(value, name):
        insist(type(value) is int and value >= 0, 'Invalid source diagnostic: '+name)
        return value

    scheduled=count(summary.get('scheduled_tracks'), 'scheduled_tracks')
    scheduled_people=count(summary.get('scheduled_people'), 'scheduled_people')
    insist(scheduled > 0 and scheduled_people > 0, 'Empty mapped source schedule')
    planned={}
    people=cfg.get('mapped_scene',{}).get('people')
    if people is not None:
        insist(isinstance(people,list) and len(people)==scheduled_people,
               'Configured people differ from source summary')
        person_ids=set()
        for person in people:
            private_id=person['person_id']
            insist(isinstance(private_id,str) and private_id and private_id not in person_ids,
                   'Invalid configured private person identity')
            person_ids.add(private_id)
            for episode in person['episodes']:
                track=episode['track_id']
                insist(isinstance(track,str) and track and track not in planned,
                       'Duplicate/invalid configured episode track')
                planned[track]=(private_id,episode['route_id'])
        insist(len(planned)==scheduled, 'Configured episodes differ from source summary')

    episodes={}
    names={'visible_start':'start','episode_start':'start',
           'visible_end':'end','episode_end':'end'}
    for row in raw['agents']:
        if row.get('data_type')!='mapped lifecycle event': continue
        kind=names.get(row.get('event'))
        insist(kind is not None, 'Unknown mapped lifecycle event')
        track=row.get('observation_track_id'); person=row.get('private_person_id')
        route=row.get('route_id')
        insist(all(isinstance(value,str) and value for value in (track,person,route)),
               'Missing lifecycle identity/route boundary')
        if 'timestamp' in row:
            at=epoch_ms(row['timestamp'])-origin
            if 'at_ms' in row:
                insist(type(row['at_ms']) is int and row['at_ms']==at,
                       'Lifecycle timestamp differs from relative event time')
        else:
            at=row.get('at_ms')
        insist(type(at) is int and 0<=at<=end, 'Invalid lifecycle event time')
        if 'processed_at_ms' in row:
            processed=row['processed_at_ms']
            insist(type(processed) is int and at<=processed<=end and processed%step==0,
                   'Invalid lifecycle event processing time')
        if people is not None:
            insist(planned.get(track)==(person,route), 'Lifecycle event differs from configured episode')
        episode=episodes.setdefault(track,{'person':person,'route':route})
        insist(episode['person']==person and episode['route']==route,
               'Lifecycle episode changes private person/route')
        insist(kind not in episode, 'Duplicate lifecycle start/end event')
        episode[kind]=at

    insist(episodes, 'Mapped lifecycle events required for GT coverage audit')
    insist(len(episodes)<=scheduled, 'More realized episodes than scheduled tracks')
    insist(len({episode['person'] for episode in episodes.values()})<=scheduled_people,
           'More realized private people than scheduled')
    starts=ends=expected_rows=0
    intervals_by_person=defaultdict(list)
    for track,episode in episodes.items():
        insist('start' in episode, 'Lifecycle end lacks a start event')
        begin=episode['start']; finish=episode.get('end',end)
        insist(begin<finish or (begin==finish==end and 'end' not in episode),
               'Lifecycle end does not follow start')
        starts+=1; ends+='end' in episode
        intervals_by_person[episode['person']].append((begin,finish))
        if track in person_by_track:
            insist(person_by_track[track]==episode['person'], 'GT/lifecycle private person mismatch')
        for at in range(((begin+step-1)//step)*step,finish,step):
            insist(track in frames.get(at,{}), 'Missing GT state inside recorded visible episode')
            expected_rows+=1
    for intervals in intervals_by_person.values():
        intervals.sort()
        insist(all(previous[1]<=current[0] for previous,current in zip(intervals,intervals[1:])),
               'One private person has overlapping visible episodes')
    for at,frame in frames.items():
        for track in frame:
            episode=episodes.get(track)
            insist(episode is not None and episode['start']<=at<episode.get('end',end),
                   'GT state outside recorded visible episode')
    insist(expected_rows==sum(len(frame) for frame in frames.values()),
           'GT row coverage differs from recorded lifecycle')
    pending=scheduled-starts; active=starts-ends
    derived={'realized_track_starts':starts,'realized_track_ends':ends,
             'pending_tracks':pending,'active_tracks':active}
    for name,value in derived.items():
        if name in summary:
            insist(count(summary[name],name)==value, 'Source/lifecycle diagnostic mismatch: '+name)
    diagnostic_names=('blocked_motion_steps','admission_wait_steps','merge_admission_wait_steps',
                      'max_consecutive_stop_ms','active_stalled_tracks','body_overlap_violations')
    # Historical integration captures did not record these diagnostics. Null is
    # intentional: absence of a counter is not evidence of zero violations.
    diagnostics={name:count(summary[name],name) if name in summary else None
                 for name in diagnostic_names}
    stalled=diagnostics['active_stalled_tracks']
    insist(stalled is None or stalled<=active, 'More stalled than active source tracks')
    all_completed=ends==scheduled
    if diagnostics['body_overlap_violations']:
        motion_status='reported_body_overlap_violations'
    elif stalled:
        motion_status='reported_stalls_at_horizon'
    elif not all_completed:
        motion_status='unfinished_episodes_at_horizon'
    elif all(value is None for value in diagnostics.values()):
        motion_status='diagnostics_not_recorded'
    else:
        motion_status='scheduled_episodes_completed'
    return {
        'all_scheduled_episodes_completed':all_completed,
        'lifecycle_quality':{
            'status':'all_scheduled_episodes_completed' if all_completed else 'censored_at_source_horizon',
            'gt_coverage_status':'verified_against_recorded_visible_intervals',
            'event_rows':starts+ends,'expected_gt_rows':expected_rows,
            'source_steps_checked':end//step,'scheduled_people':scheduled_people,
            'scheduled_episodes':scheduled,'realized_starts':starts,'realized_ends':ends,
            'pending_episodes_at_horizon':pending,'active_episodes_at_horizon':active},
        'motion_quality':{
            'status':motion_status,
            'source_model':summary.get('motion_model','not_recorded'),
            'reported_diagnostics':diagnostics,
            'scope':'Recorded source counters and event/GT consistency only. Completion does not establish '
                    'realistic motion, general queue liveness, swept collision avoidance or privacy.'}}


def build_recording(cfg, raw):
    """Independent source/raw/journal consistency checks; no source simulation."""
    sensors=[s for s in cfg['sensors'] if s['type']=='adaptive-grid-based']
    insist(len(sensors)==1,'Recording requires exactly one AGBS sensor')
    sensor=sensors[0]; aggregation=sensor['aggregation']
    period=round(1000/sensor['frame_rate']); step=round(1000*cfg['simulation']['time_step'])
    end=round(cfg['simulation']['duration_seconds']*1000)
    insist(period>0 and step>0 and period%step==0 and end%step==0,'Unsupported source/sample clock')
    coverage={k:sensor['detection_area'][k] for k in ('x','y','width','height')}
    coverage['leaf_depth']=sensor['grid']['max_depth']
    summaries=[r for r in raw['agents'] if r.get('data_type')=='mapped source summary']
    metadata=[r for r in raw['agents'] if r.get('data_type')=='metadata']
    insist(len(summaries)==len(metadata)==1,'One completed source summary and GT metadata required')
    summary=summaries[0]
    insist(summary['completed_steps']==end//step and summary['source_elapsed_ms']==end
           and summary['planned_duration_ms']==end,'Refusing an incomplete/cancelled mapped run')
    origin=epoch_ms(metadata[0]['timestamp'])
    frames=defaultdict(dict); person_by_track={}; gt_rows=0
    for row in raw['agents']:
        if row.get('data_type')!='agent data': continue
        time=epoch_ms(row['timestamp'])-origin; track=row['agent_id']
        insist(isinstance(track,str) and track and 0<=time<end and time%step==0,'Invalid GT track/time')
        insist(row.get('observation_track_id')==track and row.get('private_person_id'),'Missing private identity boundary')
        insist(track not in frames[time],'Duplicate GT track in one frame')
        person=row['private_person_id']
        insist(person_by_track.setdefault(track,person)==person,'One track maps to multiple GT people')
        point={'id':track,'type':row['type'],'x':row['position']['x'],'y':row['position']['y']}
        insist(all(isinstance(point[k],(int,float)) and math.isfinite(point[k]) for k in ('x','y')),'Nonfinite GT position')
        frames[time][track]=point; gt_rows+=1
    insist(gt_rows>0,'No observed GT states')
    quality=audit_lifecycle(cfg,raw,frames,person_by_track,origin,step,end,summary)
    # Completed source + event-audited GT establish execution of empty frames;
    # raw AGBS records alone cannot establish a measured-empty opportunity.
    expected={}; batches=[]
    for time in range(period,end,period):
        observations=[]
        for point in frames.get(time,{}).values():
            if not inside(point,coverage): continue
            observation={**point,'cell_id':cell_id(point['x'],point['y'],coverage)}
            observations.append(observation)
            counts=expected.setdefault((time,observation['cell_id']),Counter())
            counts[point['type']]+=1
        batches.append({'sequence':time//period,'observed_at_ms':time,'status':'measured',
                        'observations':sorted(observations,key=lambda o:o['id'])})
    actual={}
    for row in raw['sensor']:
        if row.get('data_type')!='adaptive grid data': continue
        insist(row.get('sensor_id')==sensor['id'],'Unexpected raw sensor ID')
        key=(epoch_ms(row['timestamp'])-origin,row['cell_id'])
        insist(key not in actual and key in expected,'Duplicate/off-cadence/unexpected AGBS cell')
        groups={}
        for group in row['agent_type_count']:
            insist(group['type'] not in groups and type(group['count']) is int and group['count']>0,'Invalid raw type counts')
            groups[group['type']]=group['count']
        insist(groups==dict(expected[key]) and row['total_agents']==sum(groups.values()),'GT/raw count or type mismatch')
        n=1<<coverage['leaf_depth']; side=coverage['width']/n
        insist(coverage['width']==coverage['height'] and abs(row['cell_size']-side)<1e-6,'Raw leaf size mismatch')
        representative=next(o for o in frames[key[0]].values() if inside(o,coverage) and cell_id(o['x'],o['y'],coverage)==key[1])
        insist(abs(row['cell_position']['x']-(coverage['x']+math.floor((representative['x']-coverage['x'])/side)*side))<1e-6
               and abs(row['cell_position']['y']-(coverage['y']+math.floor((representative['y']-coverage['y'])/side)*side))<1e-6,'Raw leaf geometry mismatch')
        actual[key]=groups
    insist(actual.keys()==expected.keys(),'Missing occupied raw AGBS cells')
    journals=raw['journals']; recipients=raw['releases']
    insist(journals and all(j.get('state')=='committed' for j in journals),'A fully committed private journal is required')
    insist(all(j.get('schema')=='ump.publication-journal.v1' and j.get('data_role')=='private_publication_journal' for j in journals),'Invalid private journal schema')
    insist(len({j['_id'] for j in journals})==len(journals),'Duplicate private journal identity')
    run_ids={j['run_id'] for j in journals}
    insist(len(run_ids)==1,'Multiple aggregation runs in one recording')
    run_id=next(iter(run_ids))
    insist(isinstance(run_id,str) and bool(run_id),'Missing native run identity')
    for j in journals:
        insist(j.get('sensor_id')==sensor['id'] and j.get('application_id')==aggregation['application_id']
               and j.get('start_ms')==j['release'].get('start_ms') and j.get('end_ms')==j['release'].get('end_ms'),'Journal context differs from scene/payload')
    for payload in recipients+[j['release'] for j in journals]:
        insist(payload.get('schema')=='ump.release.v2' and payload.get('data_role')=='recipient_release','Invalid native scoped release schema')
        key=''.join(str(len(payload[name].encode('utf-8')))+':'+payload[name] for name in ('run_id','sensor_id','application_id'))
        expected_id='ump-release-v2/'+key+'/'+str(payload['start_ms'])+'/'+str(payload['end_ms'])+'/'+str(payload['coordination_cell']['cell_id'])+'/'+str(payload['coordination_cell']['depth'])
        insist(payload.get('_id')==expected_id,'Native release identity is not canonical')
        insist(payload.get('run_id')==run_id and payload.get('sensor_id')==sensor['id']
               and payload.get('application_id')==aggregation['application_id']
               and payload.get('policy_id')==aggregation['policy_tree']['id']
               and payload.get('policy_version')==aggregation['policy_tree']['version']
               and payload.get('model')==aggregation['policy_tree']['execution'].get('publication_model','private_final_snapshot'),'Native release belongs to another scene/policy')
    by_id={r['_id']:r for r in recipients}
    insist(len(by_id)==len(recipients),'Duplicate recipient release ID')
    nonempty={j['release']['_id']:j['release'] for j in journals if j['release']['cells']}
    insist(nonempty==by_id,'Recipient records differ from committed nonempty journal payloads')
    insist(all(j['release']['_id']==j['_id'] and j['release']['run_id']==run_id for j in journals),'Invalid journal identity')
    replay={'schema':'ump.observation-replay.v1','run_id':run_id,'sensor_id':sensor['id'],
            'coverage':coverage,'sampling_period_ms':period,'end_ms':end,'batches':batches}
    source={k:replay[k] for k in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms')}
    def flattened(cell, selected=False):
        value={k:cell[k] for k in GEOMETRY_KEYS}
        value.update(observation_contributions=cell['counts']['observation_contributions'],
                     distinct_road_users=cell['counts']['distinct_contributors'],
                     mean_sample_occupancy=cell['counts'].get('mean_sample_occupancy'),
                     effective_policy_id=cell['effective_policy_id'])
        if 'semantic' in cell: value['semantic']=copy.deepcopy(cell['semantic'])
        if selected: value.update(selected=True,checks=[],diagnostics_status='not_recorded_in_publication_journal')
        return value
    def converted(payload, private=False):
        row={k:payload[k] for k in ('start_ms','end_ms','policy_id','policy_version','coordination_cell')}
        row['evaluated_at_ms' if private else 'sealed_at_ms']=payload['sealed_at_ms']
        row['cells']=[flattened(c,private) for c in payload['cells']]
        if private:
            row['diagnostics_status']='committed_retirement_only; rejected_candidates_unavailable'
        return row
    order=lambda p:(p['sealed_at_ms'],p['start_ms'],p['coordination_cell']['cell_id'],p['end_ms'],p['_id'])
    releases=[converted(p) for p in sorted(recipients,key=order)]
    windows=[converted(j['release'],True) for j in sorted(journals,key=lambda j:order(j['release']))]
    result={'schema':'ump.replay-result.v1','source':source,'mode':'native_recorded',
            'parameters':{'coordination':'cell_local','strategy':aggregation['policy_tree']['execution']['strategy'],
                          'release_trigger':aggregation['policy_tree']['execution'].get('release_trigger','policy_satisfied')},
            'input_observation_contributions':sum(len(b['observations']) for b in batches),
            'windows':windows,'releases':releases}
    # Reconstruct every public count/category and policy using private source.
    times=[b['observed_at_ms'] for b in batches]
    taxonomy=aggregation['semantic_taxonomy']; nodes={n['id']:n for n in taxonomy['nodes']}
    leaf_by_type={label:n['id'] for n in nodes.values() for label in n.get('input_types',[])}
    def descendant(ancestor,leaf):
        while leaf is not None:
            if leaf==ancestor: return True
            leaf=nodes[leaf].get('parent')
        return False
    regions=regional_metadata(cfg,aggregation); checked=0; inflation=0
    for release in releases:
        section=batches[bisect_left(times,release['start_ms']):bisect_left(times,release['end_ms'])]
        insist(section,'Published interval has no measured sample')
        for cell in release['cells']:
            observed=[o for b in section for o in b['observations'] if inside(o,cell)]
            tracks={o['id'] for o in observed}; people={person_by_track[t] for t in tracks}
            insist(len(observed)==cell['observation_contributions'] and len(tracks)==cell['distinct_road_users']
                   and abs(len(observed)/len(section)-cell['mean_sample_occupancy'])<1e-8,'Published scalar count mismatch')
            inflation += len(tracks)!=len(people)
            semantic=cell.get('semantic'); insist(semantic,'Semantic metadata missing from mapped output')
            assigned=set(); supports=[]; loss=0; weighted=0
            for category in semantic['categories']:
                members=[o for o in observed if descendant(category['category_id'],leaf_by_type[o['type']])]
                support=len({o['id'] for o in members})
                insist(members and len(members)==category['observation_contributions'] and support==category['distinct_contributors'],'Published category count mismatch')
                # Observations occur at distinct sample indices; index preserves repeated IDs.
                indices={i for i,o in enumerate(observed) if descendant(category['category_id'],leaf_by_type[o['type']])}
                insist(not assigned.intersection(indices),'Overlapping semantic categories'); assigned.update(indices)
                supports.append(support); cost=nodes[category['category_id']]['loss']; loss=max(loss,cost); weighted+=len(members)*cost
            insist(len(assigned)==len(observed) and semantic['min_category_distinct_contributors']==min(supports)
                   and semantic['semantic_max_loss']==loss and abs(semantic['semantic_mean_loss']-weighted/len(observed))<1e-8,'Semantic partition/loss mismatch')
            requirements=copy.deepcopy(aggregation['policy_tree']['root'])
            for region in regions:
                if (cell['x']<region['x']+region['width'] and region['x']<cell['x']+cell['width']
                    and cell['y']<region['y']+region['height'] and region['y']<cell['y']+cell['height']):
                    requirements=tighten(requirements,{r['metric']:{k:v for k,v in r.items() if k!='metric'} for r in region['requirements']})
            metrics={'distinct_contributors':len(tracks),'observation_contributions':len(observed),
                     'mean_sample_occupancy':len(observed)/len(section),'cell_side_m':cell['width'],
                     'cell_area_m2':cell['width']*cell['height'],'window_duration_ms':release['end_ms']-release['start_ms'],
                     'age_at_evaluation_ms':release['sealed_at_ms']-release['start_ms'],
                     'post_window_delay_ms':release['sealed_at_ms']-release['end_ms'],'measured_sample_fraction':1,
                     'min_category_distinct_contributors':min(supports),'semantic_max_loss':loss,'semantic_mean_loss':weighted/len(observed)}
            for metric,bounds in requirements.items():
                insist(metric in metrics and metrics[metric]>=bounds.get('min',-math.inf)-1e-8
                       and metrics[metric]<=bounds.get('max',math.inf)+1e-8,'Published effective policy violation: '+metric)
            checked+=1
    spec=importlib.util.spec_from_file_location('ump_replay_validation',Path(__file__).resolve().parents[2]/'tools/replay_viewer/serve.py')
    validator=importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
    validator.validate_result_events(result,coverage,end,'native')
    proof={'schema':'ump.mapped-recording-proof.v1','status':'verified','source_completed':True,
           'source_horizon_completed':True,
           'source_completion_semantics':'source_completed is a compatibility alias for source_horizon_completed; it does not mean all episodes completed.',
           **quality,
           'source_origin_epoch_ms':origin,'gt_rows':gt_rows,'measured_samples':len(batches),
           'measured_empty_samples':sum(not b['observations'] for b in batches),'raw_cell_rows':len(actual),
           'input_observation_contributions':result['input_observation_contributions'],
           'recipient_release_documents':len(releases),'published_cell_windows':checked,
           'unique_published_cell_ids':len({c['cell_id'] for r in releases for c in r['cells']}),
           'private_retirements':len(windows),'private_empty_retirements':sum(not w['cells'] for w in windows),
           'track_person_inflated_published_cells':inflation,
           'scope':'Exact recorded source/lifecycle/count/category/policy and committed journal agreement. No general motion liveness, empirical privacy or baseline superiority claim.',
           'empty_measurement_evidence':'Completed source horizon, event-audited GT coverage, fail-fast GT writes and configured sensor clock; raw rows alone do not prove empty measurement.'}
    return replay,result,proof


def load_native(cfg):
    base=cfg['database']['db_name']
    insist(re.fullmatch(r'UMP_Mapped_[0-9a-f]{32}',base),'Only UUID-owned mapped namespaces are accepted')
    sensor=next(s for s in cfg['sensors'] if s['type']=='adaptive-grid-based'); publication=sensor['aggregation']['publication']
    insist(sensor['database']['db_name']==base and publication['database']==base+'_Releases'
           and publication['journal_database']==base+'_Private','Scene databases do not share an owned namespace')
    shell=shutil.which('mongosh'); insist(shell,'mongosh is required')
    # JavaScript is a structured subprocess argument, never interpolated into a shell.
    script='const cfg='+json.dumps(cfg)+';\n'+r'''
const sensor=cfg.sensors.find(s=>s.type==='adaptive-grid-based'),p=sensor.aggregation.publication;
function plain(v){if(v instanceof Date)return v.toISOString();if(v&&typeof v==='object'&&['Long','Int32','Double','Decimal128'].includes(v._bsontype))return Number(v.toString());if(v&&v._bsontype==='ObjectId')return v.toString();if(Array.isArray(v))return v.map(plain);if(v&&typeof v==='object')return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,plain(x)]));return v;}
function rows(database,collection){const count=db.getSiblingDB(database).getCollection(collection).countDocuments({});if(count>1000000)throw Error('Collection exceeds bounded capture');return db.getSiblingDB(database).getCollection(collection).find({}).toArray();}
const value=plain({agents:rows(cfg.database.db_name,cfg.database.collection_name||'Agents'),sensor:rows(sensor.database.db_name,sensor.database.collection_name),releases:rows(p.database,p.collection),journals:rows(p.journal_database,p.journal_collection)});
const text=JSON.stringify(value);if(Buffer.byteLength(text)>268435456)throw Error('Capture exceeds 256 MiB');print(text);
'''
    completed=subprocess.run([shell,'mongodb://localhost:27017/?serverSelectionTimeoutMS=5000','--quiet','--eval',script],capture_output=True,text=True,timeout=120)
    insist(completed.returncode==0,'Native read failed: '+completed.stderr.strip()[:2000])
    insist(len(completed.stdout.encode())<=MAX_BYTES,'Capture exceeds 256 MiB')
    return json.loads(completed.stdout)


def map_metadata(scene, cfg, repo):
    manifest=json.loads((scene/'scene_manifest.json').read_text())
    labels=manifest.get('map_labels',[])
    if not labels:
        from shapely.geometry import box
        spec=importlib.util.spec_from_file_location('ump_mapped_generator',repo/'tools/mapped_scene/build_mapped_scene.py')
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        _,local,_,_,_=module.load_source(repo)
        chosen={}
        for props,geometry in local:
            name=props.get('tags',{}).get('name'); kind='street' if props['kind']=='transport_line' else 'building'
            if not name or props['kind'] not in ('transport_line','building'): continue
            clipped=geometry.intersection(box(0,0,80,80))
            if clipped.is_empty: continue
            key=(kind,name)
            if key not in chosen or clipped.length>chosen[key].length: chosen[key]=clipped
        for (kind,name),geometry in sorted(chosen.items()):
            point=geometry.interpolate(.5,normalized=True) if kind=='street' else geometry.representative_point()
            labels.append({'text':name,'x':point.x,'y':point.y,'kind':kind})
    poi_path=repo/'tools/osm_regions/data/moenckeberg/close/poi_labels.json'
    if poi_path.is_file():
        pois=json.loads(poi_path.read_text())
        insist(pois.get('schema')=='ump.osm-label-snapshot.v1' and pois.get('coordinate_transform')==manifest.get('coordinate_transform'), 'POI snapshot belongs to a different map transform')
        labels += [{key:row[key] for key in ('text','x','y','kind')} for row in pois['labels']]
    result = {'image':'map_background.png','bounds':{'x':0,'y':0,'width':80,'height':80},
            'attribution':cfg['renderer']['map_attribution'],'labels':labels,
            'legend':[{'label':label,'color':color} for label,color in
                      [('Buildings','#CBD1D9'),('Walking geometry','#B8DDD5'),('Carriageway','#E4B66B'),
                       ('Cycling geometry','#B9CAE4'),('Crossing geometry','#D5BFDF'),('Entrance context','#E4B295')]]}
    access=scene/'building_access.json'
    if access.exists():
        insist(access.resolve().is_relative_to(scene.resolve()) and access.is_file(), 'Escaping public building access artifact')
        result['building_access']='building_access.json'
        result['legend']=[entry for entry in result['legend'] if entry['label']!='Entrance context']
    return result


def validate_scene_building_access(scene, cfg, access_path):
    """Tie public map targets to the exact native source configuration.

    Structural public-schema validation alone cannot establish that a drawing
    represents the doors actually used by the recorded source. Keep this check
    explicit, ID keyed and independent of portal ordering in either artifact.
    """
    access=json.loads(access_path.read_text())
    bounds=access['bounds']; simulation=cfg['simulation']
    insist(bounds=={'x':0,'y':0,'width':simulation.get('width'),'height':simulation.get('height')},
           'Public building access bounds differ from native scene dimensions')
    declared=cfg.get('mapped_scene',{}).get('portals')
    insist(isinstance(declared,list) and all(isinstance(portal,dict) and isinstance(portal.get('id'),str) for portal in declared),
           'Public building access requires declared native scene portals')
    by_id={portal['id']:portal for portal in declared}
    insist(len(by_id)==len(declared) and by_id=={portal['id']:portal for portal in access['portals']},
           'Public building access portals differ from native scene configuration')
    manifest_path=scene/'scene_manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    if 'building_access_sha256' in manifest:
        insist(manifest['building_access_sha256']==digest(access_path),
               'Public building access differs from generated scene manifest digest')
    generated=manifest.get('motion_mode')=='buildings'
    if generated:
        insist(manifest.get('configuration_sha256')==digest(scene/'config.yaml'),
               'Native building configuration differs from generated scene manifest digest')
        insist(manifest.get('background_sha256')==digest(scene/'map_background.png'),
               'Building map background differs from generated scene manifest digest')
        insist('building_access_sha256' in manifest,
               'Generated building scene is missing its public geometry digest')
    return {'status':'verified_native_portal_agreement','building_footprints':len(access['buildings']),
            'routable_portals':len(access['portals']),
            'generated_manifest_geometry_digest_verified':'building_access_sha256' in manifest,
            'generated_manifest_config_and_background_verified':generated}


def export_scene(scene, output):
    scene=Path(scene).resolve(); output=Path(output).resolve(); repo=Path(__file__).resolve().parents[2]
    insist(not output.exists(),'Choose a new recording directory')
    cfg=yaml.safe_load((scene/'config.yaml').read_text())
    raw=load_native(cfg); observations,result,proof=build_recording(cfg,raw)
    map_info=map_metadata(scene,cfg,repo)
    if 'building_access' in map_info:
        spec=importlib.util.spec_from_file_location('ump_access_validation',repo/'tools/replay_viewer/serve.py')
        validator=importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)
        access_path=validator.validate_building_access(scene,map_info,observations['coverage'])
        proof['building_access']=validate_scene_building_access(scene,cfg,access_path)
    sensor=next(s for s in cfg['sensors'] if s['type']=='adaptive-grid-based'); agg=sensor['aggregation']
    output.mkdir(parents=True,mode=0o700); (output/'private').mkdir(mode=0o700)
    write_json(output/'observations.json',observations); write_json(output/'native_result.json',result)
    write_json(output/'private/native_source.json',raw)
    shutil.copyfile(scene/'config.yaml',output/'private/config.yaml')
    shutil.copyfile(scene/'map_background.png',output/'map_background.png')
    public_files=['observations.json','native_result.json','map_background.png']
    if 'building_access' in map_info:
        shutil.copyfile(scene/'building_access.json',output/'building_access.json')
        public_files.append('building_access.json')
    bundle={'schema':'ump.replay-viewer.v1','title':'Mönckebergstraße · native mapped observations and actual releases',
            'observations':'observations.json','identity_unit':'visible_episode_track',
            'input_provenance':'Maintained C++ Simulator, mapped '+cfg['mapped_scene'].get('motion',{}).get('mode','integration')
                +' source. Recorded GT positions at the AGBS cadence, independently matched to actual raw AGBS cells. Stable person mapping is private and never supplied to aggregation.',
            'map':map_info,'variants':[{'id':'native','label':'Actual native aggregation',
                 'result':'native_result.json','policy_tree_id':agg['policy_tree']['id'],'policy_regions':regional_metadata(cfg,agg),
                 'policy_root_requirements':[{'metric':m,**b} for m,b in sorted(agg['policy_tree']['root'].items())]}]}
    bundle['sha256']={name:digest(output/name) for name in public_files}
    write_json(output/'bundle.json',bundle)
    execution_path=scene/'execution.json'
    if execution_path.is_file():
        execution=json.loads(execution_path.read_text())
        insist(execution.get('schema')=='ump.mapped-execution.v1' and execution.get('state')=='complete'
               and execution.get('exit_code')==0 and execution.get('config_sha256')==digest(scene/'config.yaml')
               and re.fullmatch(r'[0-9a-f]{64}',execution.get('binary_sha256','')), 'Invalid native execution provenance')
        shutil.copyfile(execution_path,output/'private/execution.json')
        proof['native_execution']=execution
    else:
        proof['native_execution']={'status':'not_recorded_by_earlier_launcher'}
    proof['files_sha256']={name:digest(output/name) for name in public_files+['private/native_source.json','private/config.yaml','bundle.json']}
    if (output/'private/execution.json').is_file():proof['files_sha256']['private/execution.json']=digest(output/'private/execution.json')
    # Shared validator checks ID-derived geometry, scopes, event order and no reuse.
    spec=importlib.util.spec_from_file_location('ump_replay_server',repo/'tools/replay_viewer/serve.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.validate_bundle(output)
    # A failed map/bundle validation must never leave a verified-looking proof.
    write_json(output/'capture-proof.json',proof)
    return proof


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    proof=export_scene(args.scene,args.output)
    print(json.dumps({'status':'verified','output':str(args.output.resolve()),
                      'published_cell_windows':proof['published_cell_windows'],
                      'unique_published_cell_ids':proof['unique_published_cell_ids']}))


if __name__=='__main__':
    main()
