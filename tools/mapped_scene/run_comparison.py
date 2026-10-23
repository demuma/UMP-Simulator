#!/usr/bin/env python3
"""Compare fixed grid/windows and semantic triggers on one recorded mapped source.

The matrix and recipient query bank are fixed before opening any result. Full
inputs/results stay local under ignored results/. Only aggregate summaries are
suitable for the repository. No policy weakening or source regeneration occurs.
"""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import yaml

QUERY_BUDGET=200000
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/evaluation'))
import recipient_support
import run_local_policy_replay


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def write(path,value):
    with Path(path).open('x') as stream: json.dump(value,stream,indent=2,allow_nan=False); stream.write('\n')


def variants():
    return [dict(id='adaptive_immediate',mode='semantic_first',trigger='policy_satisfied'),
            dict(id='adaptive_semantic_wait',mode='semantic_first',trigger='priority_satisfied')]+[
        dict(id=f'fixed_{side}m_{window}ms',mode='fixed',depth=depth,window=window)
        for side,depth in [(5,4),(10,3)] for window in [400,1000]]


def native_config(cfg):
    # The adapter preserves the normal Region type/instance distinction.
    module_path=Path(__file__).with_name('analyze_tracks.py')
    spec=importlib.util.spec_from_file_location('mapped_tracks',module_path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.replay_config(cfg)


def settings_for(base,variant):
    config=copy.deepcopy(base)
    config['policy_tree']['execution']['release_trigger']=variant.get('trigger','policy_satisfied')
    return config


def summarize(data,config,result):
    nodes={node['id']:node for node in config['semantic_taxonomy']['nodes']}
    total=sum(len(b['observations']) for b in data['batches'])
    retained=0; loss=0.; exact=0; side=0.; age=0.; duration=0.; categories=Counter(); sizes=Counter()
    for release in result['releases']:
        for cell in release['cells']:
            n=cell['observation_contributions'];retained+=n
            side+=n*cell['width']; age+=n*(release['sealed_at_ms']-release['start_ms']); duration+=n*(release['end_ms']-release['start_ms'])
            sizes[str(cell['width'])]+=1
            for category in cell['semantic']['categories']:
                count=category['observation_contributions']; cost=nodes[category['category_id']]['loss']
                categories[category['category_id']]+=count;loss+=count*cost
                if cost==0: exact+=count
    return {'input_observation_contributions':total,'retained_observation_contributions':retained,
            'retained_fraction':retained/total if total else None,'unpublished_observation_contributions':total-retained,
            'exact_subtype_observation_contributions':exact,'exact_subtype_fraction_of_input':exact/total if total else None,
            'exact_subtype_fraction_of_retained':exact/retained if retained else None,
            'observation_weighted_semantic_loss':loss/retained if retained else None,
            'observation_weighted_cell_side_m':side/retained if retained else None,
            'observation_weighted_interval_duration_ms':duration/retained if retained else None,
            'observation_weighted_age_at_release_ms':age/retained if retained else None,
            'published_category_observations':dict(sorted(categories.items())),
            'published_cell_sizes':dict(sorted(sizes.items())),
            'published_cell_windows':sum(len(r['cells']) for r in result['releases']),
            'unique_published_spatial_ids':len({c['cell_id'] for r in result['releases'] for c in r['cells']}),
            'core_processing_ms':result.get('runtime',{}).get('processing_ms')}


def compare(recording,output,binary):
    recording=Path(recording).resolve();output=Path(output).resolve();binary=Path(binary).resolve()
    if output.exists(): raise ValueError('Choose a new comparison directory')
    proof=read(recording/'capture-proof.json')
    if proof.get('schema')!='ump.mapped-recording-proof.v1' or proof.get('status')!='verified' or proof.get('source_completed') is not True:
        raise ValueError('Require a completed verified mapped recording')
    hashes=proof.get('files_sha256',{})
    required={'observations.json','native_result.json','private/native_source.json','private/config.yaml','map_background.png','bundle.json'}
    if not isinstance(hashes,dict) or not required.issubset(hashes):raise ValueError('Incomplete recording digest set')
    for name,digest in hashes.items():
        if not isinstance(name,str) or not name or '\\' in name or Path(name).is_absolute() or any(part in ('','.','..') for part in name.split('/')):
            raise ValueError('Recording artifact path must be canonical and relative')
        path=(recording/name).resolve()
        if not path.is_relative_to(recording) or not path.is_file() or not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest) or sha(path)!=digest:
            raise ValueError('Changed or escaping recording artifact: '+name)
    spec=importlib.util.spec_from_file_location('source_viewer_validation',ROOT/'tools/replay_viewer/serve.py');validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator);validator.validate_bundle(recording)
    data=read(recording/'observations.json');native_cfg=yaml.safe_load((recording/'private/config.yaml').read_text());base=native_config(native_cfg)
    progress_step=round(native_cfg['simulation']['time_step']*1000)
    if progress_step<=0 or data['sampling_period_ms']%progress_step or abs(native_cfg['simulation']['time_step']*1000-progress_step)>1e-9:
        raise ValueError('Native progress step must be whole milliseconds dividing sensor cadence')
    matrix=variants()
    query={'target_cells':[{'cell_id':identity,'depth':3} for identity in range(3<<6,4<<6)],
           'categories':sorted(node['id'] for node in base['semantic_taxonomy']['nodes']),
           'window_ms':1000,'lags_ms':[0,1000]}
    query_count=(data['end_ms']//query['window_ms'])*len(query['target_cells'])*len(query['categories'])*len(query['lags_ms'])
    if query_count>QUERY_BUDGET:
        raise ValueError('Declared mapped comparison exceeds query budget; shorten the source horizon')
    output.mkdir(parents=True,mode=0o700)
    binary_sha=sha(binary);source_sha=sha(recording/'observations.json')
    protocol={'schema':'ump.mapped-comparison-protocol.v1','matrix':matrix,'queries':query,
              'binary_sha256':binary_sha,'observations_sha256':source_sha,'progress_step_ms':progress_step,'query_count':query_count,'query_budget':QUERY_BUDGET,
              'policy_scope':'Every hard root/region constraint and taxonomy is unchanged across methods. Fixed settings still perform permitted semantic generalization.',
              'recipient_scope':'Conservative exact answers plus separately evaluated uniform spatial/temporal occupancy estimates. Missing support never becomes zero.',
              'replication':'One deterministic source; no population-level statistical generalization or privacy-improvement claim.'}
    write(output/'protocol.json',protocol)
    summary={'schema':'ump.mapped-comparison.v1','status':'verified','protocol':protocol,'cases':{},'scientific_repetitions':0}
    viewer=copy.deepcopy(read(recording/'bundle.json'))
    viewer['title']='Mönckebergstraße · same-source fixed and adaptive comparison'
    viewer['variants']=[]; viewer['sha256']={}
    # Local copies allow a self-contained persistent comparison; original remains frozen.
    for name in ('observations.json','map_background.png'): shutil.copyfile(recording/name,output/name)
    for variant in matrix:
        name=variant['id'];config=settings_for(base,variant)
        config_path=output/(name+'-policy.json');result_path=output/(name+'.json');write(config_path,config)
        command=[str(binary),'--input',str(recording/'observations.json'),'--config',str(config_path),
                 '--mode',variant['mode'],'--output',str(result_path),'--progress-step-ms',str(progress_step)]
        if variant['mode']=='fixed':command+=['--fixed-depth',str(variant['depth']),'--fixed-window-ms',str(variant['window'])]
        start=time.perf_counter(); completed=subprocess.run(command,text=True,capture_output=True,timeout=240)
        (output/(name+'.log')).write_text(completed.stdout+completed.stderr)
        if completed.returncode: raise RuntimeError(name+': '+completed.stderr[:2000])
        result=read(result_path)
        audit_config=copy.deepcopy(config)
        # Fixed modes use common publication intervals even when the source's
        # adaptive configuration selects local ownership. This changes only
        # independent retirement validation, never a hard policy or execution.
        audit_config.setdefault('temporal_adaptation',{})['coordination']=result['parameters']['coordination']
        audit=run_local_policy_replay.audit(data,audit_config,result)
        stats=summarize(data,config,result)
        evaluation=recipient_support.evaluate(data,config,result['releases'],**query,max_queries=QUERY_BUDGET,uniform_estimate=True)
        compact=recipient_support.compact(evaluation)
        write(output/(name+'-queries.json'),compact)
        write(output/(name+'-private-audit.json'),audit)
        audit_summary={'status':audit['status'],'scalar_valid':audit['scalar']['valid'],
                       'semantic_published_cells':audit['semantic_published_cells'],
                       'semantic_published_bins':audit['semantic_published_bins'],
                       'regional_recomputed_cells':len(audit['regional_recomputations'])}
        summary['cases'][name]={'stats':stats,'independent_audit':audit_summary,
                                 'recipient_query_summaries':compact,'wall_seconds':time.perf_counter()-start,
                                 'result_sha256':sha(result_path),'config_sha256':sha(config_path)}
        # The actual native output is independent evidence, not silently replaced.
        # The comparison viewer explicitly identifies all six as offline reruns.
        metadata=copy.deepcopy(read(recording/'bundle.json')['variants'][0])
        metadata.update(id=name,label=name.replace('_',' '),result=result_path.name)
        viewer['variants'].append(metadata)
        if sha(binary)!=binary_sha or sha(recording/'observations.json')!=source_sha:
            raise ValueError('Frozen binary/source changed during comparison')
        print(json.dumps({'variant':name,'status':'verified','retained_fraction':stats['retained_fraction'],
                          'exact_subtype_fraction':stats['exact_subtype_fraction_of_input']}),flush=True)
    for name in ['observations.json','map_background.png']+[v['result'] for v in viewer['variants']]:viewer['sha256'][name]=sha(output/name)
    viewer['input_provenance']+=' Comparison panels are actual offline AggregationReplay executions on these identical observations, not the native sink stream.'
    write(output/'bundle.json',viewer)
    spec=importlib.util.spec_from_file_location('viewer_validation',ROOT/'tools/replay_viewer/serve.py');validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator);validator.validate_bundle(output)
    write(output/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'simulator/build/AggregationReplay')
    args=parser.parse_args(); compare(args.recording,args.output,args.binary)


if __name__=='__main__':main()
