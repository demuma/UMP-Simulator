#!/usr/bin/env python3
"""Post-hoc bounded same-source semantic filtering and strategy sensitivity.

Six predeclared cases share one exact recorded prefix: Semantic First, Spatial
First and fixed 10 m/1 s, each with suppression off/on. No motion is regenerated.
Source/derived/config/binary hashes are frozen before native execution. Results
remain local; compact totals contain no observation IDs or raw movements.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import time

from run_local_policy_replay import audit
from semantic_suppression_audit import may_filter

ROOT=Path(__file__).resolve().parents[2]
MAX_BYTES=2*1024**3
MATRIX=(('semantic_first_off','semantic_first',0),('semantic_first_on','semantic_first',1),
        ('spatial_first_off','spatial_first',0),('spatial_first_on','spatial_first',1),
        ('fixed_10m_1000ms_off','fixed',0),('fixed_10m_1000ms_on','fixed',1))


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def read(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>MAX_BYTES: raise ValueError('Input must be a regular file of at most 2 GiB')
    return json.loads(path.read_text())


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:
        json.dump(value,handle,sort_keys=True,indent=2,allow_nan=False);handle.write('\n')


def prefix(data,duration_ms):
    if type(duration_ms) is not int or duration_ms<=0 or duration_ms%data['sampling_period_ms']:
        raise ValueError('Prefix duration must be a positive sampling-aligned integer')
    end=min(data['end_ms'],duration_ms)
    result={key:deepcopy(value) for key,value in data.items() if key!='batches'}
    result['end_ms']=end
    result['batches']=[deepcopy(batch) for batch in data['batches'] if batch['observed_at_ms']<end]
    return result


def case_config(base,name,mode,enabled,cap):
    result=deepcopy(base)
    result['application_id']=base['application_id']+'/'+name
    result['policy_tree']['id']=base['policy_tree']['id']+'/'+name
    result['policy_tree']['version']=str(base['policy_tree']['version'])+'/selective-study-v1'
    result['policy_tree']['root']['semantic_suppression_fraction']={'max':cap if enabled else 0}
    execution=result['policy_tree'].setdefault('execution',{})
    execution['release_trigger']='policy_satisfied'
    execution['strategy']='semantic_first' if mode=='fixed' else mode
    if execution['strategy']=='semantic_first': execution.setdefault('semantic_secondary_strategy','temporal_first')
    else: execution.pop('semantic_secondary_strategy',None)
    return result


def summary(data,config,result,checked):
    cells=[(r,c) for r in result['releases'] for c in r['cells']]
    n=sum(c['observation_contributions'] for _,c in cells)
    weighted_loss=sum(c['observation_contributions']*c['semantic']['semantic_mean_loss'] for _,c in cells)
    exact=sum(b['observation_contributions'] for _,c in cells for b in c['semantic']['categories']
              if next(node['loss'] for node in config['semantic_taxonomy']['nodes'] if node['id']==b['category_id'])==0)
    total=result['input_observation_contributions'];lost=total-n
    accounting=checked['source_accounting']
    selective=accounting['selectively_suppressed_observations']
    return {'input_observations':total,'retained_observations':n,'retained_fraction':n/total if total else None,
        'whole_footprint_suppressed_observations':lost-selective,'selectively_suppressed_observations':selective,
        'selectively_suppressed_fraction_of_input':selective/total if total else None,
        'conditional_semantic_loss':weighted_loss/n if n else None,
        'full_input_semantic_distortion':(lost+weighted_loss)/total if total else None,
        'full_input_distortion_scope':'Unit penalty for any omitted contribution plus taxonomy cost for retained contributions; experimental utility score, not a privacy guarantee.',
        'exact_subtype_fraction_of_input':exact/total if total else None,
        'mean_cell_side_m':sum(c['observation_contributions']*c['width'] for _,c in cells)/n if n else None,
        'mean_window_duration_ms':sum(c['observation_contributions']*(r['end_ms']-r['start_ms']) for r,c in cells)/n if n else None,
        'published_cell_windows':len(cells),'suppression_candidates_in_published_cells':checked['suppression_candidates'],
        'source_accounting':accounting,'runtime':result.get('runtime',{}),
        'contribution_selection':'policy_filtered' if may_filter(config) else 'all_contributions',
        'original_gt_exact_queries':'not_evaluated; filtered counts are retained-population counts, never original-source exact answers',
        'independent_audit':{'status':checked['status'],'raw_ownership_valid':checked['scalar']['valid'],'published_policy_violations':0}}


def viewer_bundle(source_path, output, configs):
    original=Path(source_path).parent/'bundle.json'
    if not original.is_file(): return None
    bundle=read(original)
    bundle['title']='Mönckebergstraße · same recorded prefix · selective contribution suppression'
    bundle['input_provenance']='Offline replay of one frozen recorded prefix; no regenerated motion. Policy-filtered variants report retained-population counts, not exact original-source counts.'
    expected_hashes=bundle.get('sha256',{})
    bundle['observations']='observations.json';bundle['variants']=[];bundle['sha256']={}
    names=['observations.json']
    for key in ('image','building_access'):
        name=bundle.get('map',{}).get(key)
        if name:
            if not isinstance(name,str) or Path(name).name!=name: raise ValueError('Map artifacts must be local flat filenames')
            source=original.parent/name
            if not source.is_file(): raise ValueError('Missing original map artifact: '+name)
            if expected_hashes.get(name) not in (None,digest(source)): raise ValueError('Map artifact hash mismatch')
            shutil.copy2(source,output/name);names.append(name)
    for name,mode,enabled in MATRIX:
        config=configs[name]
        regions=[]
        for region in config.get('policy_regions',[]):
            bounds=deepcopy(region.get('type_requirements',{}))
            for metric,extra in region.get('requirements',{}).items():
                target=bounds.setdefault(metric,{})
                if 'min' in extra: target['min']=max(target.get('min',-math.inf),extra['min'])
                if 'max' in extra: target['max']=min(target.get('max',math.inf),extra['max'])
            regions.append({**{key:region[key] for key in ('id','type','x','y','width','height')},
                'requirements':[{'metric':metric,**limits} for metric,limits in bounds.items()]})
        filename=name+'.json';names.append(filename)
        bundle['variants'].append(dict(id=name,label=name.replace('_',' '),result=filename,
            policy_tree_id=config['policy_tree']['id'],policy_regions=regions,
            policy_root_requirements=[{'metric':metric,**limits} for metric,limits in config['policy_tree']['root'].items()],
            contribution_selection='policy_filtered' if enabled else 'all_contributions'))
    bundle['sha256']={name:digest(output/name) for name in names}
    write(output/'bundle.json',bundle)
    return 'bundle.json'


def run(source_path,config_path,output,binary,*,duration_ms=60000,cap=.1,progress_step_ms=50,wall_budget_s=900):
    source_path,config_path,output,binary=map(lambda p:Path(p).resolve(),(source_path,config_path,output,binary))
    if output.exists(): raise ValueError('Choose a fresh output directory')
    if not binary.is_file(): raise ValueError('Build AggregationReplay first')
    if type(cap) not in (int,float) or not math.isfinite(cap) or not 0<cap<=1: raise ValueError('Cap must be finite in (0,1]')
    if type(wall_budget_s) is not int or not 1<=wall_budget_s<=3600: raise ValueError('Wall budget must be integer1..3600 s')
    if type(progress_step_ms) is not int or progress_step_ms<1: raise ValueError('Progress step must be positive')
    data=prefix(read(source_path),duration_ms);base=read(config_path)
    if data['coverage']['width']!=80 or data['coverage']['height']!=80 or data['coverage']['leaf_depth']<3:
        raise ValueError('This predeclared fixed10m comparison requires 80m square coverage and depth>=3')
    if not base.get('policy_tree') or not base.get('semantic_taxonomy'): raise ValueError('Require native replay Policy Tree and taxonomy configuration')
    if any(batch['observed_at_ms']%progress_step_ms for batch in data['batches']) or data['end_ms']%progress_step_ms:
        raise ValueError('Progress step must align all source samples and final horizon')
    output.mkdir(parents=True,mode=0o700)
    write(output/'observations.json',data)
    provenance=output/'provenance';provenance.mkdir()
    shutil.copy2(binary,provenance/'AggregationReplay')
    commands=[];configs={}
    for name,mode,enabled in MATRIX:
        cfg=case_config(base,name,mode,enabled,cap);configs[name]=cfg
        write(output/(name+'-policy.json'),cfg)
        command=[str(provenance/'AggregationReplay'),'--input',str(output/'observations.json'),
            '--config',str(output/(name+'-policy.json')),'--mode',mode,'--output',str(output/(name+'.json')),
            '--progress-step-ms',str(progress_step_ms)]
        if mode=='fixed': command+=['--fixed-depth','3','--fixed-window-ms','1000']
        commands.append(command)
    protocol={'schema':'ump.selective-semantic-study-protocol.v1','analysis_status':'post_hoc_sensitivity',
        'matrix':[dict(id=n,mode=m,suppression_cap=cap if on else 0,
            contribution_selection='policy_filtered' if on else 'all_contributions') for n,m,on in MATRIX],
        'full_source_sha256':digest(source_path),'original_config_sha256':digest(config_path),
        'derived_input_sha256':digest(output/'observations.json'),'derived_horizon_ms':data['end_ms'],
        'binary_sha256':digest(provenance/'AggregationReplay'),'progress_step_ms':progress_step_ms,
        'native_process_wall_budget_s':wall_budget_s,'commands':commands,
        'source_derivation':'Exact [0,end_ms) prefix of the original frozen observations; timestamps/identities/types/positions unchanged. No new motion.',
        'comparison_scope':'Equal source and hard regional requirements; strategy and explicit suppression permission differ. Fixed baseline receives the same on/off action permission.',
        'recipient_query_scope':'No original-GT exact query evaluation for filtered products; report retained detail, source-denominated omissions and full-input semantic distortion.',
        'privacy_scope':'Operational policy/support compliance only; no attack evaluation or formal anonymity claim.'}
    protocol['pre_execution_artifacts_sha256']={str(p.relative_to(output)):digest(p) for p in output.rglob('*') if p.is_file()}
    write(output/'protocol.json',protocol)
    result_summary={'schema':'ump.selective-semantic-study.v1','status':'running','protocol':protocol,'cases':{}}
    for (name,mode,enabled),command in zip(MATRIX,commands):
        started=time.perf_counter();completed=subprocess.run(command,text=True,capture_output=True,timeout=wall_budget_s)
        wall=time.perf_counter()-started
        write(output/(name+'-execution.json'),dict(command=command,returncode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr,wall_seconds=wall))
        if completed.returncode: raise RuntimeError(name+': '+completed.stderr[:2000])
        result=read(output/(name+'.json'));cfg=configs[name]
        cfg['temporal_adaptation']['coordination']=result['parameters']['coordination']
        checked=audit(data,cfg,result);stats=summary(data,cfg,result,checked)
        stats['native_process_wall_seconds']=wall
        stats['result_sha256']=digest(output/(name+'.json'))
        result_summary['cases'][name]=stats
        write(output/(name+'-audit.json'),checked)
        print(json.dumps(dict(case=name,**{k:stats[k] for k in ('retained_fraction','conditional_semantic_loss','full_input_semantic_distortion','selectively_suppressed_observations')})),flush=True)
    require_same=digest(source_path)==protocol['full_source_sha256'] and digest(output/'observations.json')==protocol['derived_input_sha256']
    if not require_same: raise ValueError('Frozen source mutated during study')
    result_summary['status']='verified'
    result_summary['viewer_bundle']=viewer_bundle(source_path,output,configs)
    write(output/'summary.json',result_summary)
    write(output/'study-manifest.json',dict(schema='ump.selective-semantic-study-manifest.v1',status='verified',
        contribution_selection='mixed_explicit_per_variant',protocol_sha256=digest(output/'protocol.json'),
        artifacts_sha256={str(p.relative_to(output)):digest(p) for p in output.rglob('*') if p.is_file()}))
    return result_summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--binary',type=Path,default=ROOT/'simulator/build/AggregationReplay')
    parser.add_argument('--duration-ms',type=int,default=60000);parser.add_argument('--cap',type=float,default=.1)
    parser.add_argument('--progress-step-ms',type=int,default=50);parser.add_argument('--native-wall-budget-s',type=int,default=900)
    args=parser.parse_args();run(args.input,args.config,args.output,args.binary,duration_ms=args.duration_ms,cap=args.cap,
        progress_step_ms=args.progress_step_ms,wall_budget_s=args.native_wall_budget_s)


if __name__=='__main__': main()
