#!/usr/bin/env python3
"""Exploratory selective-contribution ablation on immutable urban recordings.

Semantic generalization stays enabled. Seven cap-.10 methods are paired with
seven authenticated historical cap-zero methods. Whole recordings run in six
spawned workers; utility audits precede TRAIN/CAL fitting and locked TEST scoring.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
from collections import Counter
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/evaluation'))
import run_urban_semantic_ablation as legacy
import semantic_suppression_audit as filtered
import regional_selective_public_transcript as regional
import urban_selective_suppression_utility as utility_adapter
from parallel_recordings import execute_recordings, BatchFailure

primary, source, analysis = legacy.primary, legacy.source, legacy.analysis
SCHEMA = 'ump.urban-selective-suppression-execution.v1'
UTILITY_SCHEMA = 'ump.urban-selective-suppression-utility.v1'
REPORT_SCHEMA = 'ump.urban-selective-suppression-report.v1'
LOCK_SCHEMA = 'ump.urban-selective-suppression-model-lock.v1'
CAP, WORKERS = .10, 6
FIT_OUTPUTS = legacy.FIT_OUTPUTS
BASE_IDS = legacy.ON_IDS
NEW_IDS = tuple(name + '_selective' for name in BASE_IDS)


def _catalog():
    old = [dict(m, base_method_id=m['id'], suppression_enabled=False, suppression_cap=0,
                semantic_generalization='enabled') for m in legacy.ON_METHODS]
    new = [dict(m, id=m['id']+'_selective', base_method_id=m['id'], label=m['label']+' / selective cap .10',
                suppression_enabled=True, suppression_cap=CAP, origin='new_selective', semantic_generalization='enabled')
           for m in legacy.ON_METHODS]
    return tuple(old + new)


METHODS = _catalog()
OLD_METHODS, NEW_METHODS = METHODS[:7], METHODS[7:]
AUXILIARY_METHODS = tuple(dict(id=f'fixed20_{ms}ms_selective', base_method_id=f'fixed20_{ms}ms',
    label=f'Auxiliary fixed 20 m / {ms} ms / selective', kind='native_fixed', fixed_depth=2,
    grid_side_m=20, window_ms=ms, suppression_enabled=True, suppression_cap=CAP,
    semantic_generalization='enabled') for ms in (1000, 2000, 4000))
NATIVE_METHODS = tuple(m for m in NEW_METHODS if m['kind'] != 'regional_static') + AUXILIARY_METHODS
CONTRASTS = tuple((name+'_selective_vs_disabled', name+'_selective', name, 20261028501+i)
                  for i,name in enumerate(BASE_IDS)) + tuple(
    (m['base_method_id']+'_selective_vs_regional_selective',m['id'],'regional_static20_selective',20261028601+i)
    for i,m in enumerate(NEW_METHODS[2:]))
_WORKER_STATE = None


def require(condition, message): primary.require(condition, message)
def reference(path): return legacy.reference(path)
def authenticated(ref): return legacy.authenticated(ref)
def load_ref(ref): return source.load(authenticated(ref))
def write(path, value): primary.write(path, value)


def variant_config(base, method):
    require(method in METHODS + AUXILIARY_METHODS, 'Unknown selective-study method')
    original = next((m for m in legacy.ON_METHODS if m['id'] == method['base_method_id']), None)
    config = legacy.variant_config(base, original) if original is not None else deepcopy(base)
    config['policy_tree']['root']['semantic_suppression_fraction'] = {'max': CAP if method['suppression_enabled'] else 0}
    restored = deepcopy(config)
    if 'semantic_suppression_fraction' in base['policy_tree']['root']:
        restored['policy_tree']['root']['semantic_suppression_fraction'] = deepcopy(base['policy_tree']['root']['semantic_suppression_fraction'])
    else:
        restored['policy_tree']['root'].pop('semantic_suppression_fraction', None)
    require(legacy.previous.hard_policy(restored) == legacy.previous.hard_policy(base), 'Undeclared hard policy change')
    return config


def implementation_files():
    files = legacy.implementation_files()
    for path in (ROOT/'simulator/tools').glob('*.hpp'):
        files[str(path.relative_to(ROOT))] = source.sha(path)
    for path in (ROOT/'simulator/tools').glob('*.cpp'):
        files[str(path.relative_to(ROOT))] = source.sha(path)
    return dict(sorted(files.items()))


def prepare(output, contract, *, history=legacy.DEFAULT_HISTORY, binary=legacy.DEFAULT_BINARY):
    context = legacy.authenticate_history(history)
    base = load_ref(context['history']['bound_anchors']['original_config'])
    require(base['policy_tree']['root'].get('semantic_suppression_fraction', {}).get('max',0) == 0,
            'Historical reference must prohibit selective suppression')
    require(Path(contract).is_file() and Path(binary).is_file(), 'Missing contract or native binary')
    output = primary.fixture.new_output(output)
    for name in ('groups','configs','provenance'): (output/name).mkdir(mode=0o700)
    shutil.copy2(binary, output/'provenance/AggregationReplay')
    configs = {}
    for method in NATIVE_METHODS:
        path = output/'configs'/(method['id']+'.json'); write(path, variant_config(base,method)); configs[method['id']] = reference(path)
    parent = context['values']['supplement_protocol']
    p = dict(schema=SCHEMA, prepared_at=source.now(), output_directory=str(output), history=reference(history),
        contract=reference(contract), implementation_files_sha256=implementation_files(),
        native_binary=reference(output/'provenance/AggregationReplay'), original_native_binary=reference(binary),
        original_config=context['history']['bound_anchors']['original_config'], hard_policy_sha256=analysis.digest(legacy.previous.hard_policy(base)),
        method_catalog=deepcopy(METHODS), auxiliary_method_catalog=deepcopy(AUXILIARY_METHODS), variant_configs=configs,
        contrasts=[dict(id=n,left=l,right=r,seed=s,replicates=1000,confidence_level=.95) for n,l,r,s in CONTRASTS],
        workers=WORKERS, multiprocessing_start_method='spawn', suppression_cap=CAP, semantic_generalization='enabled',
        group_counts=dict(train=24,calibration=16,test=32), group_order=context['manifest']['groups'],
        expected_headline_rows=2016, expected_imported_rows=1008, expected_new_rows=1008,
        expected_auxiliary_rows=432, expected_native_cases=1296, expected_regional_compositions=144, expected_new_models=14,
        native_wall_budget_s=parent['native_wall_budget_s'], audit_max_cells=parent['audit_max_cells'],
        minimum_free_bytes=parent['minimum_free_bytes'], worker_disk_reserve_bytes=2*1024**3,
        availability=parent['availability'], model_parameters=deepcopy(analysis.MODEL_PARAMETERS),
        source_generation_allowed=False, old_artifact_changes_allowed=False, retries_allowed=False,
        test_sources_already_seen=True, scope='Exploratory reused-source cap-.10 versus cap-zero ablation; semantics enabled throughout. '
        'Operational support constraints, empirical MIA and utility remain separate claims. Concurrent times are batch diagnostics, not real-time evidence.')
    write(output/'protocol.json',p)
    primary.fixture.write_new(output/'protocol.sha256',(source.sha(output/'protocol.json')+'\n').encode())
    return output


def read_protocol(output, *, verify_archives=False, verify_raw=False):
    output = primary.fixture.safe_path(output,root=ROOT/'results')
    p = source.load(output/'protocol.json')
    require(p['schema']==SCHEMA and p['output_directory']==str(output)
        and source.sha(output/'protocol.json')==(output/'protocol.sha256').read_text().strip(),'Selective protocol changed')
    for key in ('history','contract','native_binary','original_native_binary','original_config'): authenticated(p[key])
    for name,digest in p['implementation_files_sha256'].items(): require(source.sha(ROOT/name)==digest,'Implementation changed: '+name)
    require(p['method_catalog']==list(METHODS) and p['auxiliary_method_catalog']==list(AUXILIARY_METHODS)
        and p['contrasts']==[dict(id=n,left=l,right=r,seed=s,replicates=1000,confidence_level=.95) for n,l,r,s in CONTRASTS], 'Selective catalog changed')
    require(p['workers']==WORKERS and type(p['workers']) is int and p['suppression_cap']==CAP
        and p['semantic_generalization']=='enabled' and p['multiprocessing_start_method']=='spawn', 'Execution action changed')
    require(all(p[k] is False for k in ('source_generation_allowed','old_artifact_changes_allowed','retries_allowed'))
        and p['test_sources_already_seen'] is True and p['model_parameters']==analysis.MODEL_PARAMETERS,'Study scope changed')
    require(tuple(p[k] for k in ('expected_headline_rows','expected_imported_rows','expected_new_rows','expected_auxiliary_rows',
        'expected_native_cases','expected_regional_compositions','expected_new_models'))==(2016,1008,1008,432,1296,144,14), 'Study counts changed')
    context = legacy.authenticate_history(authenticated(p['history']),verify_archives=verify_archives,verify_raw=verify_raw)
    require(p['group_order']==context['manifest']['groups'] and p['group_counts']==dict(train=24,calibration=16,test=32),'Source roles/order changed')
    parent=context['values']['supplement_protocol']
    require(all(p[k]==parent[k] for k in ('native_wall_budget_s','audit_max_cells','minimum_free_bytes','availability'))
        and p['worker_disk_reserve_bytes']==2*1024**3,'Budget/availability changed')
    require(p['original_config']==context['history']['bound_anchors']['original_config'],'Original policy changed')
    base=load_ref(p['original_config'])
    require(p['hard_policy_sha256']==analysis.digest(legacy.previous.hard_policy(base)),'Original hard policy digest changed')
    require(set(p['variant_configs'])=={m['id'] for m in NATIVE_METHODS},'Missing native configurations')
    for method in NATIVE_METHODS: require(load_ref(p['variant_configs'][method['id']])==variant_config(base,method),'Variant policy changed')
    return output,p,context


def validate_native(result,data,config,method):
    mode='fixed' if method['kind']=='native_fixed' else method['strategy']
    require(result.get('schema')=='ump.replay-result.v1' and result.get('mode')==mode,'Native mode differs')
    require(all(result['source'].get(k)==data[k] for k in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms'))
        and result['source'].get('application_id')==config['application_id'],'Native source differs')
    q=result['parameters']; require(q.get('semantic_generalization')=='enabled' and q.get('progress_step_ms')==50 and q.get('progress_origin_ms')==0,'Semantic/progress clock differs')
    if mode=='fixed': require(q.get('fixed_depth')==2 and q.get('window_ms')==method['window_ms'] and q.get('coordination')=='common_window','Fixed schedule differs')
    else:
        require(q.get('coordination')=='cell_local','Adaptive coordination differs')
        if mode=='semantic_first': require(q.get('semantic_secondary_strategy')==method['secondary_strategy'] and q.get('release_trigger')==method['release_trigger'],'Priority/release trigger differs')
        else: require('semantic_secondary_strategy' not in q and 'release_trigger' not in q,'Unexpected semantic-only parameters')
    total=primary.fixture.counts(data)['observations']
    require(result['input_observation_contributions']==result['accounted_observation_contributions']==total,'Native observation conservation differs')


def row_for(group,world,method,public,knowledge,data,audit,config,result=None,query_reference=None):
    features,checks=primary.pilot.feature_check(public,knowledge)
    scalar=primary.scalar.feature_vector(legacy.semantic._scalar_projection(public),knowledge,include_geometry=True)
    require(len(features['values'])==111 and len(scalar)==31,'Frozen feature dimensions differ')
    empty=deepcopy(public);empty['releases']=[]; no_output,_=primary.pilot.feature_check(empty,knowledge)
    return dict(group_id=group['group_id'],split=group['split'],world=world,label=int(world=='IN'),method_id=method['id'],
        features=features['values'],scalar_features=scalar,
        auxiliary_features=analysis.auxiliary_features(knowledge,data['coverage'],data['end_ms']),
        controls=dict(prior_only=.5,unprotected=primary.positive_control(data,knowledge),no_output_features=no_output['values']),
        utility=utility_adapter.utility(data,public,config,audit,result,query_reference=query_reference,include_queries=method not in AUXILIARY_METHODS),feature_checks=checks)


def run_case(directory,data_path,base,method,group,world,knowledge,protocol,*,data=None,query_reference=None):
    require(method in NATIVE_METHODS and world in ('IN','OUT'),'Unknown native case')
    directory=Path(directory);name=method['id']; config=variant_config(base,method)
    require(not any((directory/(name+s)).exists() for s in ('-attempt.json','-execution.json','.json','-receipt.json')),'No native retries/overwrite')
    if 'variant_configs' in protocol: require(config==load_ref(protocol['variant_configs'][name]),'Config differs from freeze')
    policy=directory/(name+'-policy.json');result_path=directory/(name+'.json');write(policy,config)
    binary=directory/'AggregationReplay'
    command=primary.native_command(binary,data_path,policy,result_path,method)+['--semantic-generalization','enabled','--decision-digest','sha256']
    frozen={str(q):source.sha(q) for q in (data_path,binary,policy)}
    require(frozen[str(binary)]==protocol['native_binary']['sha256'],'Native binary changed')
    write(directory/(name+'-attempt.json'),dict(command=command,started_at=source.now(),wall_cap_s=protocol['native_wall_budget_s']))
    start=time.perf_counter();execution=dict(status='failed',command=command)
    try:
        done=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=protocol['native_wall_budget_s'],umask=0o077)
        execution.update(status='complete' if done.returncode==0 else 'failed',returncode=done.returncode,stdout=done.stdout,stderr=done.stderr)
    except subprocess.TimeoutExpired: execution['status']='timeout'
    except BaseException as error: execution.update(status='interrupted',error=str(error));raise
    finally:
        execution['seconds']=time.perf_counter()-start;write(directory/(name+'-execution.json'),execution)
    require(execution['status']=='complete','Native case failed or exceeded wall cap')
    primary.pilot.unchanged(frozen);data=source.load(data_path) if data is None else data;result=source.load(result_path)
    validate_native(result,data,config,method)
    projected=deepcopy(config);projected['temporal_adaptation']['coordination']=result['parameters']['coordination']
    audit=primary.independent.audit(data,projected,result,max_cells=protocol['audit_max_cells'])
    require(audit.get('status')=='verified' and audit.get('scalar',{}).get('valid') is True,'Independent retained/source audit failed')
    public=legacy.semantic.export_public(result,config['semantic_taxonomy'],availability_model=protocol.get('availability',primary.pilot.AVAILABILITY))
    primary.pilot.public_contract(public,config,{data['run_id'],data['sensor_id']}|{r['id'] for b in data['batches'] for r in b['observations']})
    row=row_for(group,world,method,public,knowledge,data,audit,config,result,query_reference)
    for suffix,value in (('-audit.json',audit),('-public.json',public),('-row.json',row)): write(directory/(name+suffix),value)
    record=dict(method_id=name,world=world,status='verified',role='auxiliary' if method in AUXILIARY_METHODS else 'headline',
        native_seconds=execution['seconds'],independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0),
        decision_audit=result.get('runtime',{}).get('decision_audit'),
        artifacts={p.name:primary.artifact(directory,p) for p in (policy,result_path,directory/(name+'-audit.json'),directory/(name+'-public.json'),directory/(name+'-row.json'),directory/(name+'-execution.json'))})
    write(directory/(name+'-receipt.json'),record)
    print('selective_native_done group='+group['group_id']+' world='+world+' method='+name,flush=True)
    return record,row


def compose(directory,base,group,world,knowledge,records,data,query_reference):
    method=NEW_METHODS[1];config=variant_config(base,method);name=method['id'];write(directory/(name+'-policy.json'),config)
    cases={}
    for ms in (400,1000,2000,4000):
        identity=f'fixed20_{ms}ms_selective';require(records.get(identity,{}).get('status')=='verified','Missing regional dependency')
        cases[str(ms)]=dict(config=primary.artifact(directory,directory/(identity+'-policy.json')),
            result=primary.artifact(directory,directory/(identity+'.json')),private_audit=primary.artifact(directory,directory/(identity+'-audit.json')),
            independent_audit=records[identity]['independent_audit'])
    family=dict(schema=regional.FAMILY_SCHEMA,public_coverage=data['coverage'],sampling_period_ms=data['sampling_period_ms'],end_ms=data['end_ms'],side_m=20,
        public_policy_id=config['policy_tree']['id'],method_alias=name,source=primary.artifact(directory,directory/'input.json'),
        native_binary=primary.artifact(directory,directory/'AggregationReplay'),cases=cases)
    write(directory/(name+'-family.json'),family)
    composed=regional.compose_family(directory,family,availability_model=primary.pilot.AVAILABILITY)
    public,audit=composed['public_transcript'],composed['private_audit']
    primary.pilot.public_contract(public,config)
    row=row_for(group,world,method,public,knowledge,data,audit,config,query_reference=query_reference)
    for suffix,value in (('-public.json',public),('-audit.json',audit),('-row.json',row)):write(directory/(name+suffix),value)
    record=dict(method_id=name,world=world,status='verified',role='headline',native_seconds=None,
        independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0))
    write(directory/(name+'-receipt.json'),record);return record,row


def process_group(output,p,context,group):
    identity=group['group_id'];directory=output/'groups'/identity
    require(not directory.exists(),'No group retries/overwrite');directory.mkdir(mode=0o700)
    imported=context['history']['original_groups'][identity]
    write(directory/'attempt.json',dict(group_id=identity,split=group['split'],started_at=source.now(),original_pair=imported['files']['pair.json']))
    for name in ('in.json','out.json','auxiliary.json','pair.json'):os.link(authenticated(imported['files'][name]),directory/name)
    pair=legacy.previous.validate_pair_import(directory,imported);require(pair['group_id']==identity,'Wrong source pair')
    primary.split.verify_actual_sources(context['manifest'],[pair],ROOT)
    knowledge=source.load(directory/'auxiliary.json');base=load_ref(p['original_config']);rows=[];aux=[];cases=[];archives={}
    old={ (r['world'],r['method_id']):r for r in context['all_historical_rows'] if r['group_id']==identity }
    for world in ('IN','OUT'):
        work=directory/world;work.mkdir(mode=0o700)
        os.link(directory/('in.json' if world=='IN' else 'out.json'),work/'input.json');os.link(authenticated(p['native_binary']),work/'AggregationReplay')
        data=source.load(work/'input.json');bank=legacy.queries.prepare_reference(data,base)
        for method in OLD_METHODS:rows.append(deepcopy(old[world,method['id']]))
        records={}
        for method in NATIVE_METHODS:
            try:
                require(shutil.disk_usage(output).free>=p['minimum_free_bytes'],'Insufficient free disk')
                record,row=run_case(work,work/'input.json',base,method,group,world,knowledge,p,data=data,query_reference=bank)
                (aux if method in AUXILIARY_METHODS else rows).append(row)
            except Exception as error:
                record=dict(method_id=method['id'],world=world,status='failed',error=str(error));write(work/(method['id']+'-failed.json'),record)
            records[method['id']]=record;cases.append(record)
        try:
            record,row=compose(work,base,group,world,knowledge,records,data,bank);rows.append(row)
        except Exception as error:
            record=dict(method_id=NEW_METHODS[1]['id'],world=world,status='failed_dependency_or_audit',error=str(error))
            write(work/(NEW_METHODS[1]['id']+'-failed.json'),record)
        cases.append(record);archives[world]={}
        for path in sorted(work.glob('*.json')):
            if path.name=='input.json' or path.name.endswith(('-policy.json','-row.json','-execution.json','-receipt.json','-attempt.json','-failed.json')):continue
            archives[world][path.name]=primary.archive_file(path)
    write(directory/'rows.json',rows);write(directory/'auxiliary-rows.json',aux);write(directory/'archive-receipt.json',archives)
    summary=dict(group_id=identity,split=group['split'],status='verified' if len(rows)==28 and len(aux)==6 and len(cases)==20 and all(c['status']=='verified' for c in cases) else 'incomplete',
        pair=pair,cases=cases,rows=primary.artifact(directory,directory/'rows.json'),auxiliary_rows=primary.artifact(directory,directory/'auxiliary-rows.json'),
        archives=primary.artifact(directory,directory/'archive-receipt.json'))
    write(directory/'summary.json',summary)
    write(directory/'selective-receipt.json',dict(schema='ump.selective-recording-binding.v1',protocol_sha256=source.sha(output/'protocol.json'),
        original_pair=imported['files']['pair.json'],summary=reference(directory/'summary.json'),rows=summary['rows'],auxiliary_rows=summary['auxiliary_rows']))
    return summary


def _initialize(output,p,context):
    global _WORKER_STATE
    _WORKER_STATE=(Path(output),p,context)


def _run_group(group):
    output,p,context=_WORKER_STATE
    start=time.perf_counter();summary=process_group(output,p,context,group)
    require(summary['status']=='verified','Recording incomplete: '+group['group_id'])
    return dict(summary=summary,seconds=time.perf_counter()-start,pid=os.getpid())


def collect(output,p,context,*,verify_archives=False,require_complete=True):
    rows=[];aux=[];summaries=[]
    for group in context['manifest']['groups']:
        directory=output/'groups'/group['group_id']
        if not (directory/'summary.json').is_file():
            require(not require_complete,'Missing recording summary');continue
        summary=source.load(directory/'summary.json');require(summary['status']=='verified' and summary['group_id']==group['group_id'] and summary['split']==group['split'],'Incomplete or mismatched recording')
        require(len(summary['cases'])==20 and {(c['method_id'],c['world']) for c in summary['cases']}=={(m['id'],w) for m in NATIVE_METHODS+(NEW_METHODS[1],) for w in ('IN','OUT')}
            and all(c['status']=='verified' for c in summary['cases']),'Incomplete case family')
        for name in ('rows','auxiliary_rows','archives'):primary.split.relative_file(directory,summary[name])
        side=source.load(directory/'selective-receipt.json');imported=context['history']['original_groups'][group['group_id']]
        legacy.previous.validate_pair_import(directory,imported)
        require(side['schema']=='ump.selective-recording-binding.v1' and side['protocol_sha256']==source.sha(output/'protocol.json')
            and side['original_pair']==imported['files']['pair.json'] and side['summary']==reference(directory/'summary.json')
            and side['rows']==summary['rows'] and side['auxiliary_rows']==summary['auxiliary_rows'],'Recording binding changed')
        if verify_archives:primary.verify_group_artifacts(directory,summary)
        group_rows=source.load(directory/'rows.json');group_aux=source.load(directory/'auxiliary-rows.json')
        original={ (r['world'],r['method_id']):r for r in context['all_historical_rows'] if r['group_id']==group['group_id'] and r['method_id'] in BASE_IDS }
        require(all(r==original[r['world'],r['method_id']] for r in group_rows if r['method_id'] in BASE_IDS),'Historical row changed')
        rows.extend(group_rows);aux.extend(group_aux);summaries.append(summary)
    expected=legacy.window.expected_groups(context['manifest'])
    analysis._checked_rows(rows,expected,[m['id'] for m in METHODS],allow_test=True)
    analysis._checked_rows(aux,expected,[m['id'] for m in AUXILIARY_METHODS],allow_test=True)
    if require_complete:require(len(rows)==2016 and len(aux)==432 and len(summaries)==72,'Incomplete 72-recording study')
    return rows,summaries,aux


def run_utility(output):
    output,p,context=read_protocol(output)
    require(not any((output/n).exists() for n in FIT_OUTPUTS),'Utility cannot follow fitting')
    require(not any((output/n).exists() for n in ('execution-attempt.json','execution-receipt.json','execution-failed.json')) and not any((output/'groups').iterdir()),'No execution retry')
    def disk():
        free=shutil.disk_usage(output).free;need=p['minimum_free_bytes']+WORKERS*p['worker_disk_reserve_bytes']
        require(free>=need,'Insufficient centrally reserved worker disk headroom')
    disk();write(output/'execution-attempt.json',dict(started_at=source.now(),protocol=reference(output/'protocol.json'),workers=WORKERS,retries_allowed=False))
    began=time.perf_counter();completed={}
    def on_result(group,result):
        require(result['summary']['group_id']==group['group_id'] and result['summary']['status']=='verified','Wrong worker summary')
        completed[group['group_id']]=dict(seconds=result['seconds'],pid=result['pid'],summary=reference(output/'groups'/group['group_id']/'summary.json'))
        print('selective_group_done '+group['group_id']+' seconds='+str(round(result['seconds'],3)),flush=True)
    try:
        execute_recordings(context['manifest']['groups'],_run_group,workers=WORKERS,initializer=_initialize,
            initargs=(str(output),p,context),before_submit=lambda group:disk(),on_result=on_result)
        rows,summaries,aux=collect(output,p,context,verify_archives=True)
        receipt=dict(status='verified',workers=WORKERS,recordings=len(summaries),native_cases=1296,regional_compositions=144,
            seconds=time.perf_counter()-began,completed=completed,mia_status='not_started',timing_scope='Concurrent whole-recording throughput; no isolated/real-time claim')
        write(output/'execution-receipt.json',receipt);return receipt
    except BaseException as error:
        failure=dict(status='failed',error=str(error),completed=completed,seconds=time.perf_counter()-began,no_retry=True)
        if isinstance(error,BatchFailure):failure.update(errors={k:str(v) for k,v in error.errors.items()},cancelled=list(error.cancelled_group_ids))
        write(output/'execution-failed.json',failure);raise


def design():
    return dict(title='Selective contribution suppression with semantic generalization enabled',source_recordings=72,train=24,calibration=16,test=32,
        horizon_ms=300000,workers=WORKERS,suppression_cap=CAP,new_native_cases=1296,regional_compositions=144,
        imported_headline_rows=1008,new_headline_rows=1008,new_models=14,source_resimulations=0,old_model_refits=0,
        semantic_generalization='enabled',test_reused_exploratory=True,
        protected_unit='All observed contributions of one operational track within [0,300 s); not a person or all visits.',
        attack_scope='Frozen quarter-count target sightings; Full111 and Scalar31 L2 logistic classifiers. TRAIN24/CAL16/TEST32. Final snapshot.')


def lineage(output,p,context):
    anchors=context['history']['bound_anchors']
    return dict(protocol=reference(output/'protocol.json'),history_snapshot=p['history'],original_config=p['original_config'],native_binary=p['native_binary'],
        old_models=anchors['supplement_models'],old_model_lock=anchors['supplement_model_lock'],old_report=anchors['supplement_report'],
        parallel_execution_receipt=reference(output/'execution-receipt.json'))


def utility_contrasts(rows):
    index={(r['group_id'],r['world'],r['method_id']):r for r in rows if r['split']=='test'}
    groups=sorted({r['group_id'] for r in rows if r['split']=='test'})
    paths=('retained_fraction','full_input_J','retained_semantic_loss','mean_retained_cell_side_m','mean_retained_interval_ms','logical_seal_delay_ms.mean')
    def value(row,path):
        item=row['utility']
        for part in path.split('.'):
            if not isinstance(item,dict) or part not in item:return None
            item=item[part]
        return item if type(item) in (int,float) and math.isfinite(item) else None
    out={}
    for i,(name,left,right,_) in enumerate(CONTRASTS[:7]):
        metrics={}
        for path in paths:
            values=[(value(index[g,'IN',left],path),value(index[g,'IN',right],path)) for g in groups]
            diff=[a-b for a,b in values if a is not None and b is not None]
            rng=random.Random(20261028701+i);n=len(diff)
            samples=sorted(math.fsum(rng.choice(diff) for _ in range(n))/n for _ in range(1000)) if n>=2 else []
            metrics[path]=dict(mean_difference=math.fsum(diff)/n if n else None,
                ci95=[legacy.previous.percentile(samples,.025),legacy.previous.percentile(samples,.975)] if n>=2 else None,
                paired_recordings=n,replicates=1000,confidence_level=.95,seed=20261028701+i)
        out[name]=dict(left=left,right=right,world='IN',metrics=metrics,scope='Exploratory paired-source mean differences; fixed inputs; marginal intervals, available pairs only.')
    return out


def utility_report(output):
    output,p,context=read_protocol(output)
    require(not any((output/n).exists() for n in FIT_OUTPUTS) and not (output/'utility-report.json').exists(),'Utility report cannot follow fitting/overwrite')
    receipt=source.load(output/'execution-receipt.json');require(receipt['status']=='verified','Verified execution required')
    rows,summaries,aux=collect(output,p,context,verify_archives=True)
    expected=legacy.window.expected_groups(context['manifest'])
    report=dict(schema=UTILITY_SCHEMA,phase='utility',study_design=design(),method_catalog=deepcopy(METHODS),lineage=lineage(output,p,context),
        utility={m['id']:analysis._utility([r for r in rows if r['method_id']==m['id']],expected) for m in METHODS},
        paired_utility_contrasts=utility_contrasts(rows),mia_status='not_started',
        all_rows_sha256=analysis.digest(analysis._checked_rows(rows,expected,[m['id'] for m in METHODS],allow_test=True)),auxiliary_rows_sha256=analysis.digest(aux),
        scope=p['scope'])
    write(output/'utility-report.json',report);return report


def combine_models(original,attacks,training,expected):
    require(set(attacks)==set(NEW_IDS),'Seven new attack families required')
    ids=[m['id'] for m in METHODS];checked=analysis._checked_rows(training,expected,ids,allow_test=False)
    require(len(checked)==1120,'Complete TRAIN/CAL rows required')
    result=deepcopy(original);result.pop('prepared_sha256')
    result['attacks']={name:deepcopy(original['attacks'][name]) for name in BASE_IDS};result['attacks'].update(deepcopy(attacks))
    result.update(method_ids=ids,expected_method_ids=ids,expected_groups=deepcopy(expected),training_calibration_rows_sha256=analysis.digest(checked),
        training_calibration_rows=len(checked),training_group_ids=sorted({r['group_id'] for r in checked if r['split']=='train'}),
        calibration_group_ids=sorted({r['group_id'] for r in checked if r['split']=='calibration'}),test_rows_seen=0,
        models=[dict(method_id=name,representation=rep,**deepcopy(result['attacks'][name][rep])) for name in ids for rep in analysis.REPRESENTATIONS],
        scope='Fourteen new suppression-ON TRAIN fits/CAL locks; fourteen historical suppression-OFF objects and four controls reused exactly.')
    require(result['controls']==original['controls'],'Original controls changed')
    result['prepared_sha256']=analysis.digest(result);analysis.validate_model_lock(result,checked,require_complete=True)
    return result


def fit_mia(output):
    output,p,context=read_protocol(output)
    require(not any((output/n).exists() for n in FIT_OUTPUTS),'No fitting retry')
    gate=source.load(output/'utility-report.json');require(gate['schema']==UTILITY_SCHEMA and gate['mia_status']=='not_started'
        and gate['lineage']['protocol']==reference(output/'protocol.json'),'Completed utility gate required')
    rows,_,aux=collect(output,p,context);expected=legacy.window.expected_groups(context['manifest'])
    checked=analysis._checked_rows(rows,expected,[m['id'] for m in METHODS],allow_test=True)
    require(analysis.digest(checked)==gate['all_rows_sha256'] and analysis.digest(aux)==gate['auxiliary_rows_sha256'],'Utility rows changed')
    training=[r for r in checked if r['split']!='test'];require(len(training)==1120,'TRAIN/CAL completeness differs')
    write(output/'mia-fit-attempt.json',dict(status='attempted',protocol=reference(output/'protocol.json'),utility_gate=reference(output/'utility-report.json'),
        new_fit_count=14,test_rows_seen_by_fitter=0,training_rows_sha256=analysis.digest(training),model_parameters=deepcopy(analysis.MODEL_PARAMETERS),started_at=source.now()))
    attacks={};completed=0
    try:
        for method in NEW_METHODS:
            selected=[r for r in training if r['method_id']==method['id']];attacks[method['id']]={}
            for rep,(field,_) in analysis.REPRESENTATIONS.items():
                attacks[method['id']][rep]=analysis._fit(selected,lambda row,f=field:row[f],expected);completed+=1
        models=combine_models(context['models'],attacks,training,expected)
    except BaseException as error:
        write(output/'mia-fit-failed.json',dict(status='failed',error=str(error),completed_fits=completed,no_retry=True));raise
    write(output/'models.json',models);write(output/'train-cal-rows.json',training)
    lock=dict(schema=LOCK_SCHEMA,status='locked_before_new_TEST_scoring',created_at=source.now(),protocol=reference(output/'protocol.json'),
        utility_gate=reference(output/'utility-report.json'),fit_attempt=reference(output/'mia-fit-attempt.json'),models=reference(output/'models.json'),
        data=reference(output/'train-cal-rows.json'),old_models=context['history']['bound_anchors']['supplement_models'],
        old_model_lock=context['history']['bound_anchors']['supplement_model_lock'],new_fit_count=14,old_model_refits=0,test_rows_seen_by_fitter=0,
        test_sources_already_seen=True)
    write(output/'models-lock.json',lock);return lock


def authenticate_models(output,p,context,training):
    lock=source.load(output/'models-lock.json');require(lock['schema']==LOCK_SCHEMA and lock['status']=='locked_before_new_TEST_scoring'
        and lock['protocol']==reference(output/'protocol.json') and lock['utility_gate']==reference(output/'utility-report.json')
        and lock['old_models']==context['history']['bound_anchors']['supplement_models']
        and lock['old_model_lock']==context['history']['bound_anchors']['supplement_model_lock']
        and lock['new_fit_count']==14 and lock['old_model_refits']==lock['test_rows_seen_by_fitter']==0
        and lock['test_sources_already_seen'] is True,'Model lock changed')
    attempt=load_ref(lock['fit_attempt']);require(attempt['new_fit_count']==14 and attempt['test_rows_seen_by_fitter']==0
        and attempt['model_parameters']==analysis.MODEL_PARAMETERS and attempt['training_rows_sha256']==analysis.digest(training),'Fit evidence changed')
    models=load_ref(lock['models']);locked=load_ref(lock['data'])
    require(locked==training,'TRAIN/CAL locked data differs');analysis.validate_model_lock(models,training,require_complete=True)
    require(all(models['attacks'][name]==context['models']['attacks'][name] for name in BASE_IDS)
        and models['controls']==context['models']['controls'],'Historical attack/control replaced')
    return models


def assess_mia(output):
    output,p,context=read_protocol(output,verify_archives=True,verify_raw=True)
    require(not (output/'final-report.json').exists(),'No TEST assessment overwrite')
    rows,_,aux=collect(output,p,context,verify_archives=True);training=analysis._checked_rows([r for r in rows if r['split']!='test'],legacy.window.expected_groups(context['manifest']),[m['id'] for m in METHODS],allow_test=False)
    models=authenticate_models(output,p,context,training);assessed=analysis.evaluate_models(models,rows)
    old=context['original_report']['analysis'];require(all(assessed['attacks'][name]==old['attacks'][name] for name in BASE_IDS)
        and assessed['controls']==old['controls'] and assessed['primary_contrast']==context['original_primary'],'Historical assessment changed')
    contrasts={}
    for name,left,right,seed in CONTRASTS:
        reps={}
        for rep in analysis.REPRESENTATIONS:
            a,b=assessed['attacks'][left][rep],assessed['attacks'][right][rep]
            reps[rep]=analysis.paired_source_auc_difference(a['group_scores'],b['group_scores'],replicates=1000,seed=seed) if a['status']==b['status']=='evaluated' else dict(status='unavailable',left_status=a['status'],right_status=b['status'])
        contrasts[name]=dict(left=left,right=right,metric='ROC_AUC',seed=seed,replicates=1000,confidence_level=.95,representations=reps,
            scope='Exploratory reused TEST recording pairs; fixed TRAIN/CAL, marginal intervals, no equivalence claim.')
    gate=source.load(output/'utility-report.json')
    require(analysis.digest(analysis._checked_rows(rows,legacy.window.expected_groups(context['manifest']),[m['id'] for m in METHODS],allow_test=True))==gate['all_rows_sha256'],'Utility evidence changed')
    require(assessed['utility']==gate['utility'],'Utility summary changed at scoring')
    report=dict(schema=REPORT_SCHEMA,phase='assessed',study_design=design(),method_catalog=deepcopy(METHODS),lineage=lineage(output,p,context),
        utility=gate['utility'],paired_utility_contrasts=gate['paired_utility_contrasts'],analysis=assessed,exploratory_contrasts=contrasts,
        models_lock=reference(output/'models-lock.json'),mia_status='complete' if assessed['status']=='complete' else assessed['status'],
        original_primary_result_preserved=True,scope=p['scope'])
    write(output/'final-report.json',report);return report


@contextmanager
def locked(output):
    output=primary.fixture.safe_path(output,root=ROOT/'results')
    fd=os.open(output/'.selective-study.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);yield
    finally:os.close(fd)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);actions=parser.add_mutually_exclusive_group(required=True)
    for action in ('prepare','check','run-utility','utility-report','fit-mia','assess-mia'):actions.add_argument('--'+action,type=Path)
    parser.add_argument('--contract',type=Path);parser.add_argument('--history',type=Path,default=legacy.DEFAULT_HISTORY)
    parser.add_argument('--native-binary',type=Path,default=legacy.DEFAULT_BINARY)
    args=parser.parse_args(argv)
    if args.prepare:
        require(args.contract is not None,'Explicit new study contract required');print(prepare(args.prepare,args.contract,history=args.history,binary=args.native_binary));return
    output=args.check or args.run_utility or args.utility_report or args.fit_mia or args.assess_mia
    with locked(output):
        if args.check:read_protocol(output);print('verified: selective-study protocol')
        elif args.run_utility:print(json.dumps(run_utility(output),default=str))
        elif args.utility_report:utility_report(output);print('verified: utility report; MIA not started')
        elif args.fit_mia:fit_mia(output);print('verified:14 new fits locked; TEST not scored')
        else:assess_mia(output);print('completed: held-out scoring on reused TEST groups')


if __name__=='__main__':main()
