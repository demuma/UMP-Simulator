#!/usr/bin/env python3
"""Exploratory semantic-generalization ON/OFF ablation on immutable urban pairs.

Historical source code is authenticated in an explicit archived producer view;
it is never asserted to equal newly modified native code. Utility/audits precede
14 new TRAIN-only fits/CAL locks, and TEST scoring is a separate final action.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import fcntl
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/evaluation'))
import run_urban_strategy_supplement as previous
import urban_semantic_ablation_queries as queries

primary, source, analysis = previous.primary, previous.source, previous.analysis
repair, window, semantic = previous.repair, previous.window, previous.semantic
SCHEMA = 'ump.urban-semantic-ablation-execution.v1'
HISTORY_SCHEMA = 'ump.urban-semantic-ablation-historical-import.v1'
UTILITY_SCHEMA = 'ump.urban-semantic-ablation-utility.v1'
REPORT_SCHEMA = 'ump.urban-semantic-ablation-report.v1'
LOCK_SCHEMA = 'ump.urban-semantic-ablation-model-lock.v1'
SIDECAR_SCHEMA = 'ump.urban-semantic-ablation-group.v1'
EXPECTED_HISTORY_SHA256 = '5937daf128dc3877e11ff5f551caaf7bc2077339f1b0838f7281631207c537d3'
DEFAULT_BINARY = ROOT/'simulator/build-semantic-ablation/AggregationReplay'
DEFAULT_HISTORY = ROOT/'results/urban-semantic-ablation-implementation-2026-10-27/historical-import/history-import.json'
FIT_OUTPUTS = previous.FIT_OUTPUTS
ON_IDS = ('fixed20_400ms','regional_static20','adaptive_temporal_first','adaptive_spatial_first',
          'adaptive_semantic_first','adaptive_semantic_wait_temporal','adaptive_semantic_wait_spatial')


def require(value, message): primary.require(value, message)
def reference(path): return previous.reference(path)
def authenticated(ref): return previous.authenticated(ref)
def load_ref(ref): return source.load(authenticated(ref))
def off_id(name): return name+'_exact_only'


def _catalog():
    definitions = [
        dict(id='fixed20_400ms',label='Fixed 20 m / 0.4 s',kind='native_fixed',fixed_depth=2,grid_side_m=20,window_ms=400),
        dict(id='regional_static20',label='Regional static 20 m',kind='regional_static',grid_side_m=20),
        *[dict(m) for m in previous.VARIANTS[:2]],
        dict(id='adaptive_semantic_first',label='Semantic First / immediate',kind='native_adaptive',strategy='semantic_first',secondary_strategy='temporal_first',release_trigger='policy_satisfied'),
        *[dict(m) for m in previous.VARIANTS[2:]],
    ]
    require(tuple(m['id'] for m in definitions)==ON_IDS,'Internal ON catalog differs')
    on=[dict(m,on_method_id=m['id'],semantic_generalization='enabled',origin='imported_enabled') for m in definitions]
    off=[dict(m,id=off_id(m['id']),on_method_id=m['id'],semantic_generalization='exact_only',origin='new_exact_only') for m in definitions]
    return tuple(on+off)


METHODS = _catalog()
ON_METHODS, OFF_METHODS = METHODS[:7], METHODS[7:]
AUXILIARY_METHODS = tuple(dict(id=off_id('fixed20_'+str(ms)+'ms'),on_method_id='fixed20_'+str(ms)+'ms',
    label='Auxiliary fixed 20 m / '+str(ms)+' ms / exact only',kind='native_fixed',fixed_depth=2,grid_side_m=20,
    window_ms=ms,semantic_generalization='exact_only',origin='new_exact_only_dependency') for ms in (1000,2000,4000))
NATIVE_METHODS = tuple(m for m in OFF_METHODS if m['kind']!='regional_static')+AUXILIARY_METHODS
CONTRASTS = tuple((name+'_exact_only_vs_enabled',off_id(name),name,20261027401+i) for i,name in enumerate(ON_IDS))


def variant_config(base, method):
    require(method in METHODS+AUXILIARY_METHODS,'Unknown/altered ablation method')
    if method['kind']!='native_adaptive': return deepcopy(base)
    choices = previous.VARIANTS+(dict(id='adaptive_semantic_first',label='Semantic First / immediate',kind='native_adaptive',
        strategy='semantic_first',secondary_strategy='temporal_first',release_trigger='policy_satisfied'),)
    equivalent=next(v for v in choices if v['id']==method['on_method_id'])
    # Use the frozen primitive without changing its global catalog or invoking it
    # for the imported immediate method which was never in that catalog.
    result=deepcopy(base); execution=result['policy_tree']['execution']
    for key in previous.EXECUTION_KEYS: execution.pop(key,None)
    execution.update(strategy=equivalent['strategy'],release_trigger=equivalent['release_trigger'])
    if equivalent['secondary_strategy'] is not None: execution['semantic_secondary_strategy']=equivalent['secondary_strategy']
    require(previous.hard_policy(result)==previous.hard_policy(base),'Hard policy changed')
    return result


def _historical_version(history, name, expected):
    path=Path(name) if Path(name).is_absolute() else ROOT/name
    versions=history['historical_expected_versions'].get(str(path),{})
    entry=versions.get(expected)
    if entry is None:
        entry=history['files'].get(str(path))
    require(entry is not None and entry['sha256']==expected,'Missing exact historical producer version: '+str(path))
    archive=Path(entry['archived_path'])
    require(archive.is_relative_to(Path(history['_directory'])) and archive.is_file()
            and archive.stat().st_size==entry['bytes'] and source.sha(archive)==expected,'Historical archive changed')
    return archive


def validate_historical_code(h):
    # Recheck every archived version, including the explicitly retained old and
    # corrected auditor bytes. New native C++ is authenticated separately.
    for name,versions in h['historical_expected_versions'].items():
        for digest in versions: _historical_version(h,name,digest)
    for name,entry in h['files'].items():
        archive=Path(entry['archived_path'])
        require(source.sha(archive)==entry['sha256'] and archive.stat().st_size==entry['bytes'],'Historical snapshot bytes differ')
        if Path(name).suffix=='.py': require(source.sha(Path(name))==entry['sha256'],'Imported Python primitive changed: '+name)


def authenticate_history(history_path, *, verify_archives=False, verify_raw=False):
    """Explicit archived-producer bridge; never invoke old current-code gates."""
    history_path=Path(history_path).resolve()
    require(source.sha(history_path)==EXPECTED_HISTORY_SHA256,'Historical bridge differs from trusted prechange snapshot')
    h=source.load(history_path); h['_directory']=str(history_path.parent)
    require(h.get('schema')==HISTORY_SCHEMA and h.get('status')=='verified'
            and h['historical_code_is_archived_not_asserted_current'] is True
            and h['new_native_edits_present'] is False,'Historical capture scope differs')
    receipt=load_ref(h['authentication_receipt'])
    require(receipt['status']=='verified' and receipt['source_groups']==72 and receipt['combined_recipient_rows']==2160
            and receipt['method_representation_models']==30 and receipt['old_primary_preserved'] is True
            and receipt['source_generation_or_model_fitting'] is False,'Historical prechange authentication incomplete')
    require(source.environment()==receipt['environment'],'Historical/current Python environment differs')
    validate_historical_code(h)
    anchors=h['bound_anchors']; values={name:load_ref(ref) for name,ref in anchors.items()}
    sp,rp,pp=values['original_source_protocol'],values['original_repair_protocol'],values['supplement_protocol']
    original=values['original_execution_protocol']; manifest=values['dataset_manifest']
    for mapping in (sp['frozen_files_sha256'],original['implementation_files_sha256'],pp['implementation_files_sha256']):
        for name,digest in mapping.items(): _historical_version(h,name,digest)
    primary.split.validate_manifest(manifest)
    require(Counter(g['split'] for g in manifest['groups'])==Counter(train=24,calibration=16,test=32),'Historical roles differ')
    require(pp['imported_groups']==h['original_groups'] and pp['parent_references']==h['old_parent_references'],'Historical parent/group declarations differ')
    require(anchors['supplement_protocol']['sha256']==h['old_supplement_protocol_sha256']
            and anchors['supplement_report']['sha256']==h['old_supplement_report_sha256'],'Historical final bindings differ')
    for publication in h['publication'].values():
        for relative,ref in publication['files'].items():
            actual=authenticated(ref).read_bytes()
            committed=subprocess.check_output(['git','show',publication['commit']+':'+relative],cwd=ROOT)
            require(actual==committed,'Historical public Git bytes changed')
    original_rows=[]; old_summaries=[]
    group_ids={g['group_id'] for g in manifest['groups']}
    require(set(h['original_groups'])==set(h['supplementary_groups'])==group_ids,'Historical72 group matrix differs')
    for group in manifest['groups']:
        identity=group['group_id']; imported=h['original_groups'][identity]; fs=imported['files']
        require(imported['split']==group['split'],'Historical role changed')
        for name,ref in fs.items(): authenticated(ref)
        summary=load_ref(fs['summary.json']); rows=load_ref(fs['rows.json'])
        require(summary['status']=='verified' and len(rows)==22 and len(summary['cases'])==22
                and all(c['status']=='verified' for c in summary['cases']),'Historical original group incomplete')
        if verify_archives: primary.verify_group_artifacts(Path(imported['directory']),summary)
        original_rows.extend(rows); old_summaries.append(summary)
    context=dict(manifest=manifest,main=original,source=sp,models=values['supplement_models'],
        original_rows=original_rows,original_summaries=old_summaries,parent_output=Path(pp['parent_output']))
    supplement_output=Path(pp['output_directory'])
    extra_rows,extra_summaries=previous.collect_new(supplement_output,pp,context,verify_archives=verify_archives,require_complete=True)
    for summary in extra_summaries:
        fs=h['supplementary_groups'][summary['group_id']]['files']
        for ref in fs.values():authenticated(ref)
        require(source.load(authenticated(fs['summary.json']))==summary,'Historical supplementary summary differs')
    all_old=analysis._checked_rows(original_rows+extra_rows,window.expected_groups(manifest),[m['id'] for m in pp['original_methods']+pp['variants']],allow_test=True)
    oldreport=values['supplement_report']; original_report=values['original_report']
    require(len(all_old)==2160 and analysis.digest(all_old)==oldreport['analysis']['all_rows_sha256']
            and oldreport['analysis']['primary_contrast']==original_report['analysis']['primary_contrast'],'Historical final assessment changed')
    locked=values['supplement_train_cal_rows']; analysis.validate_model_lock(values['supplement_models'],locked,require_complete=True)
    lock=values['supplement_model_lock']
    require(lock['models']==anchors['supplement_models'] and lock['data']==anchors['supplement_train_cal_rows']
            and lock['new_fit_count']==8 and lock['test_rows_seen_by_fitter']==0,'Historical model lock differs')
    require(all(oldreport['analysis']['attacks'][m]==original_report['analysis']['attacks'][m] for m in original_report['analysis']['attacks'])
            and oldreport['analysis']['controls']==original_report['analysis']['controls'],'Historical old attacks/controls changed')
    if verify_raw: verify_historical_sources(h,values)
    context.update(history=h,history_reference=reference(history_path),values=values,all_historical_rows=all_old,
        original_report=oldreport,original_primary=original_report['analysis']['primary_contrast'],supplementary_summaries=extra_summaries)
    return context


def authenticated_historical_capture(row,saved,frozen):
    """Pin the actual proof before trusting its artifact map or reconstruction."""
    replay,scene=Path(row['replay_directory']),Path(row['scene_directory'])
    require(saved['group_id']==row['group_id'] and saved['split']==row['split']
        and saved['replay_directory']==str(replay) and saved['scene_directory']==str(scene),'Historical source receipt paths/identity differ')
    proof_ref=frozen['capture_proof'];config_ref=frozen['config']
    require(Path(proof_ref['path'])==replay/'capture-proof.json'
        and proof_ref['sha256']==saved['capture_proof_sha256']
        and proof_ref['sha256']==saved['files_sha256']['replay/capture-proof.json'],'Frozen capture-proof binding differs')
    require(Path(config_ref['path'])==scene/'config.yaml'
        and config_ref['sha256']==frozen['capture_files_sha256']['private/config.yaml']
        and config_ref['sha256']==saved['files_sha256']['scene/config.yaml'],'Frozen configuration binding differs')
    observations_ref=dict(path=str(replay/'observations.json'),sha256=frozen['capture_files_sha256']['observations.json'])
    require(observations_ref['sha256']==saved['observations_sha256']
        and observations_ref['sha256']==saved['files_sha256']['replay/observations.json'],'Frozen observations binding differs')
    proof=load_ref(proof_ref)
    authenticated(config_ref);authenticated(observations_ref)
    require(proof['files_sha256']==frozen['capture_files_sha256'],'Frozen capture artifact map differs')
    return proof


def verify_historical_sources(history,values):
    """Full payload hashes and GT/sensor reconstruction under archived producer.

    The historical current-code frozen_check gate is deliberately NOT called.
    Prior physical/source qualification remains bound; this is a new bridge.
    """
    view=values['source_validation_producer_view']; ledger=values['original_validation_ledger']
    require(ledger['status']=='verified' and ledger['full_raw_validations']==72
            and ledger['producer_view']==history['bound_anchors']['source_validation_producer_view'],'Historical source ledger differs')
    by={entry['group_id']:entry for entry in ledger['cases']}
    for row in view['cases']:
        saved=load_ref(by[row['group_id']]['receipt']); require(saved['status']=='verified' and saved['split']==row['split'],'Historical source invalid')
        frozen=values['original_repair_protocol']['original_source_inputs'][row['group_id']]
        proof=authenticated_historical_capture(row,saved,frozen)
        repair.physical_proof(view,saved)
        replay,scene=Path(row['replay_directory']),Path(row['scene_directory'])
        require(proof['status']=='verified' and proof['source_horizon_completed'] is True,'Historical capture incomplete')
        require(source.REQUIRED_FILES<=set(proof['files_sha256']),'Capture proof omits required artifacts')
        for name,digest in proof['files_sha256'].items():require(source.sha(source.safe_file(replay,name))==digest,'Historical raw/capture bytes changed')
        config=source.config_read(scene/'config.yaml'); raw=source.load(replay/'private/native_source.json')
        exporter=repair.validation._module(repair.validation.EXPORTER,'ump_semantic_ablation_historical_exporter')
        data,result,rebuilt=exporter.build_recording(config,raw)
        require(data==source.load(replay/'observations.json') and result==source.load(replay/'native_result.json')
                and all(proof.get(k)==v for k,v in rebuilt.items()),'Historical GT/sensor reconstruction differs')
        require(source.sha(scene/'config.yaml')==proof['files_sha256']['private/config.yaml'],'Historical source config differs')


def implementation_files():
    paths=set((ROOT/'tools/evaluation').glob('*.py'))|set((ROOT/'tools/mapped_scene').glob('*.py'))
    for base in (ROOT/'simulator/src',ROOT/'simulator/include',ROOT/'simulator/tests'):
        paths.update(p for p in base.rglob('*') if p.is_file() and p.suffix in ('.cpp','.hpp','.h','.tpp','.mm'))
    paths.add(ROOT/'simulator/CMakeLists.txt')
    return {str(p.relative_to(ROOT)):source.sha(p) for p in sorted(paths)}


def prepare(output, *, history=DEFAULT_HISTORY, binary=DEFAULT_BINARY, contract):
    context=authenticate_history(history); base=load_ref(context['history']['bound_anchors']['original_config'])
    require(Path(binary).resolve()==DEFAULT_BINARY.resolve(),'A separate declared ablation binary is required')
    output=primary.fixture.new_output(output);(output/'groups').mkdir(mode=0o700);(output/'configs').mkdir(mode=0o700)
    configs={}
    for method in NATIVE_METHODS:
        path=output/'configs'/(method['id']+'.json');primary.write(path,variant_config(base,method));configs[method['id']]=reference(path)
    pp=context['values']['supplement_protocol']
    p=dict(schema=SCHEMA,status='prepared_exploratory_semantic_ablation',prepared_at=source.now(),output_directory=str(output),
        history=reference(history),contract=reference(contract),adapter=reference(Path(__file__)),tests=reference(Path(__file__).with_name('test_'+Path(__file__).name)),
        implementation_files_sha256=implementation_files(),native_binary=reference(binary),original_config=context['history']['bound_anchors']['original_config'],
        hard_policy_sha256=analysis.digest(previous.hard_policy(base)),variant_configs=configs,method_catalog=deepcopy(METHODS),
        auxiliary_method_catalog=deepcopy(AUXILIARY_METHODS),contrasts=[dict(id=n,left=l,right=r,seed=s,replicates=1000,confidence_level=.95) for n,l,r,s in CONTRASTS],
        source_generation_allowed=False,old_artifact_changes_allowed=False,group_counts=dict(train=24,calibration=16,test=32),
        expected_headline_rows=2016,expected_new_headline_rows=1008,expected_imported_headline_rows=1008,expected_auxiliary_rows=432,
        expected_new_native_cases=1296,expected_new_regional_cases=144,expected_new_models=14,
        native_wall_budget_s=pp['native_wall_budget_s'],audit_max_cells=pp['audit_max_cells'],minimum_free_bytes=pp['minimum_free_bytes'],
        availability=pp['availability'],scope='Exploratory semantic exact-only versus enabled on reused sources. Hard policy unchanged; utility first;14 new TRAIN-only fits/CAL locks; TEST scoring last. Historical producer bytes archived separately from modified native code.')
    primary.write(output/'protocol.json',p);primary.fixture.write_new(output/'protocol.sha256',(source.sha(output/'protocol.json')+'\n').encode())
    return output


def read_protocol(output, *, verify_archives=False, verify_raw=False):
    output=primary.fixture.safe_path(output,root=ROOT/'results');p=source.load(output/'protocol.json')
    require(p['schema']==SCHEMA and p['output_directory']==str(output)
            and source.sha(output/'protocol.json')==(output/'protocol.sha256').read_text().strip(),'Ablation protocol differs')
    for name in ('history','contract','adapter','tests','native_binary','original_config'):authenticated(p[name])
    require(p['adapter']==reference(Path(__file__)) and p['tests']==reference(Path(__file__).with_name('test_'+Path(__file__).name)),'Ablation runner/test bytes differ')
    require(p['method_catalog']==list(METHODS) and p['auxiliary_method_catalog']==list(AUXILIARY_METHODS)
            and p['contrasts']==[dict(id=n,left=l,right=r,seed=s,replicates=1000,confidence_level=.95) for n,l,r,s in CONTRASTS],'Ablation catalog/contrasts differ')
    for name,digest in p['implementation_files_sha256'].items():require(source.sha(ROOT/name)==digest,'Ablation implementation changed: '+name)
    require(p['source_generation_allowed'] is p['old_artifact_changes_allowed'] is False
            and p['group_counts']==dict(train=24,calibration=16,test=32)
            and tuple(p[k] for k in ('expected_headline_rows','expected_new_headline_rows','expected_imported_headline_rows','expected_auxiliary_rows','expected_new_native_cases','expected_new_regional_cases','expected_new_models'))==(2016,1008,1008,432,1296,144,14),'Ablation scope/counts differ')
    context=authenticate_history(authenticated(p['history']),verify_archives=verify_archives,verify_raw=verify_raw)
    require(p['original_config']==context['history']['bound_anchors']['original_config'],'Base policy differs from historical declaration')
    base=load_ref(p['original_config']);require(p['hard_policy_sha256']==analysis.digest(previous.hard_policy(base)),'Hard policy digest differs')
    require(set(p['variant_configs'])=={m['id'] for m in NATIVE_METHODS},'Native configuration family differs')
    for method in NATIVE_METHODS:require(load_ref(p['variant_configs'][method['id']])==variant_config(base,method),'Only declared execution configuration deltas allowed')
    require(Path(p['native_binary']['path']).resolve()==DEFAULT_BINARY.resolve(),'Unexpected native executable path')
    parent=context['values']['supplement_protocol']
    require(all(p[k]==parent[k] for k in ('native_wall_budget_s','audit_max_cells','minimum_free_bytes','availability')),'Inherited budget/availability differs')
    return output,p,context


def validate_native(result,data,config,method):
    require(method in NATIVE_METHODS,'Unknown native method')
    mode='fixed' if method['kind']=='native_fixed' else method['strategy'];q=result.get('parameters',{})
    require(result.get('schema')=='ump.replay-result.v1' and result.get('mode')==mode
            and q.get('semantic_generalization')=='exact_only','Native mode/generalization mismatch')
    require(all(result.get('source',{}).get(k)==data[k] for k in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms'))
            and result['source'].get('application_id')==config['application_id'],'Native source header differs')
    require(q.get('progress_step_ms')==50 and q.get('progress_origin_ms')==0,'Native clock differs')
    if mode=='fixed':
        require(q.get('coordination')=='common_window' and q.get('fixed_depth')==method['fixed_depth']
                and q.get('window_ms')==method['window_ms'],'Fixed schedule differs')
    else:
        require(q.get('coordination')=='cell_local' and q.get('window_ms')==config['window_ms']
                and q.get('max_window_ms')==config['temporal_adaptation']['max_window_ms']
                and q.get('extension_step_ms')==config['temporal_adaptation']['extension_step_ms']
                and q.get('min_depth')==config['spatial_selection']['min_depth'],'Adaptive bounds differ')
        if mode=='semantic_first':require(q.get('semantic_secondary_strategy')==method['secondary_strategy'] and q.get('release_trigger')==method['release_trigger'],'Semantic strategy metadata differs')
        else:require('semantic_secondary_strategy' not in q and 'release_trigger' not in q,'Plain strategy claimed semantic-only metadata')
    total=primary.fixture.counts(data)['observations']
    require(result['input_observation_contributions']==result['accounted_observation_contributions']==total,'Native contribution conservation differs')


def audit_native(data,config,result,*,max_cells):
    # As in frozen primary.run_native: the fixed replay schedule is audited as
    # common_window, without changing the published/frozen policy configuration.
    audited=deepcopy(config)
    audited['temporal_adaptation']['coordination']=result['parameters']['coordination']
    return primary.independent.audit(data,audited,result,max_cells=max_cells)


def exact_only_evidence(public,config):
    catalog=primary.regional.Catalog(config);cells=[c for r in public['releases'] for c in r['cells']]
    bins=[b for c in cells for b in c['semantic']['categories']]
    require(all(b['category_id'] in catalog.leaves for b in bins),'Exact-only output generalized a category')
    require(all(c['semantic']['semantic_mean_loss']==c['semantic']['semantic_max_loss']==0 for c in cells),'Exact-only output has semantic loss')
    return dict(status='verified',published_cells=len(cells),terminal_bins=len(bins),all_categories_terminal=True,
        semantic_loss_zero=True,source_contributions_independently_audited=True)


def recipient_digest(public):
    value=deepcopy(public)
    for release in value['releases']:release.pop('release_id',None)
    return analysis.digest(value)


def attach_queries(row,data,public,config,query_reference):
    evaluated=queries.evaluate(data,public,config,reference=query_reference)
    row['utility']['aligned_semantic_queries']={mode:evaluated[mode] for mode in ('exact','estimate')}
    row['recipient_digest_no_release_ids']=recipient_digest(public)
    return row


def attach_case_queries(row,data,public,config,query_reference,method):
    require(method in METHODS+AUXILIARY_METHODS,'Unknown query diagnostic role')
    if method in AUXILIARY_METHODS:
        return row
    return attach_queries(row,data,public,config,query_reference)


def run_case(directory,data_path,base,method,group,world,knowledge,protocol,*,data=None,query_reference=None):
    """Fresh excluded-DEV or study native case; never fit or alter old evidence."""
    directory,data_path=Path(directory),Path(data_path);config=variant_config(base,method);name=method['id']
    require(method in NATIVE_METHODS and world in ('IN','OUT'),'Invalid native case')
    if 'variant_configs' in protocol:require(config==load_ref(protocol['variant_configs'][name]),'Native config differs from freeze')
    require(not any((directory/(name+suffix)).exists() for suffix in ('-attempt.json','-execution.json','.json','-receipt.json')),'No native retry/overwrite')
    policy_path=directory/(name+'-policy.json');result_path=directory/(name+'.json');primary.write(policy_path,config)
    command=primary.native_command(directory/'AggregationReplay',data_path,policy_path,result_path,method)+['--semantic-generalization','exact_only']
    frozen={str(q):source.sha(q) for q in (data_path,directory/'AggregationReplay',policy_path)}
    if 'native_binary' in protocol:require(frozen[str(directory/'AggregationReplay')]==protocol['native_binary']['sha256'],'Native executable changed')
    primary.write(directory/(name+'-attempt.json'),dict(started_at=source.now(),command=command,wall_cap_s=protocol['native_wall_budget_s']))
    started=time.perf_counter();execution=dict(status='failed',command=command)
    try:
        done=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=protocol['native_wall_budget_s'],umask=0o077)
        execution.update(status='complete' if done.returncode==0 else 'failed',returncode=done.returncode,stdout=done.stdout,stderr=done.stderr)
    except subprocess.TimeoutExpired:execution['status']='timeout'
    except BaseException as error:execution.update(status='interrupted',error=str(error));raise
    finally:execution['seconds']=time.perf_counter()-started;primary.write(directory/(name+'-execution.json'),execution)
    require(execution['status']=='complete','Native failed or exceeded cap')
    primary.pilot.unchanged(frozen);data=source.load(data_path) if data is None else data;result=source.load(result_path)
    validate_native(result,data,config,method)
    audit=audit_native(data,config,result,max_cells=protocol['audit_max_cells'])
    require(audit.get('status')=='verified' and audit.get('scalar',{}).get('valid') is True,'Independent native audit failed')
    public=semantic.export_public(result,config['semantic_taxonomy'],availability_model=primary.pilot.AVAILABILITY)
    primary.pilot.public_contract(public,config,{data['run_id'],data['sensor_id']}|{r['id'] for b in data['batches'] for r in b['observations']})
    evidence=exact_only_evidence(public,config)
    row=primary.row_for(group,world,method,public,knowledge,data,audit,result)
    attach_case_queries(row,data,public,config,query_reference,method)
    for suffix,value in (('-audit.json',audit),('-public.json',public),('-row.json',row)):primary.write(directory/(name+suffix),value)
    record=dict(method_id=name,world=world,status='verified',role='auxiliary' if method in AUXILIARY_METHODS else 'headline',
        independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0),exact_only=evidence,native_seconds=execution['seconds'],
        artifacts={q.name:primary.artifact(directory,q) for q in (result_path,directory/(name+'-audit.json'),directory/(name+'-public.json'),directory/(name+'-row.json'),directory/(name+'-execution.json'),policy_path)})
    primary.write(directory/(name+'-receipt.json'),record);primary.pilot.unchanged(frozen)
    print('semantic_ablation_native_done group='+group['group_id']+' world='+world+' method='+name,flush=True)
    return record,row


def compose(directory,base,group,world,knowledge,records,data,query_reference):
    method=next(m for m in OFF_METHODS if m['kind']=='regional_static');name=method['id'];cases={}
    config_path=directory/(name+'-policy.json');primary.write(config_path,base)
    for ms in (400,1000,2000,4000):
        identity=off_id('fixed20_'+str(ms)+'ms');require(records.get(identity,{}).get('status')=='verified','Missing regional dependency')
        cases[str(ms)]=dict(config=primary.artifact(directory,directory/(identity+'-policy.json')),result=primary.artifact(directory,directory/(identity+'.json')),
            private_audit=primary.artifact(directory,directory/(identity+'-audit.json')),independent_audit=records[identity]['independent_audit'])
    family=dict(schema=primary.regional.FAMILY_SCHEMA,public_coverage=data['coverage'],sampling_period_ms=data['sampling_period_ms'],end_ms=data['end_ms'],
        side_m=20,public_policy_id=base['policy_tree']['id'],method_alias=name,source=primary.artifact(directory,directory/'input.json'),
        native_binary=primary.artifact(directory,directory/'AggregationReplay'),cases=cases)
    primary.write(directory/(name+'-family.json'),family)
    composed=primary.regional.compose_family(directory,family,availability_model=primary.pilot.AVAILABILITY)
    public,audit=composed['public_transcript'],composed['private_audit'];primary.pilot.public_contract(public,base)
    evidence=exact_only_evidence(public,base);row=primary.row_for(group,world,method,public,knowledge,data,audit,None)
    attach_case_queries(row,data,public,base,query_reference,method)
    for suffix,value in (('-public.json',public),('-audit.json',audit),('-row.json',row)):primary.write(directory/(name+suffix),value)
    record=dict(method_id=name,world=world,status='verified',role='headline',native_runtime=None,exact_only=evidence)
    return record,row


def historical_public(context,identity,world,method):
    h=context['history'];entry=(h['supplementary_groups'] if method in {m['id'] for m in previous.VARIANTS} else h['original_groups'])[identity]
    archive=load_ref(entry['files']['archive-receipt.json']);name=method+'-public.json';receipt=archive[world][name]
    path=primary.split.relative_file(Path(entry['directory'])/world,dict(path=receipt['path'],sha256=receipt['sha256']))
    digest=hashlib.sha256();chunks=[];size=0
    with gzip.open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            size+=len(chunk);require(size<=primary.fixture.MAX_FILE_BYTES,'Historical public artifact exceeds bound');digest.update(chunk);chunks.append(chunk)
    require(size==receipt['uncompressed_bytes'] and digest.hexdigest()==receipt['uncompressed_sha256'],'Historical public payload differs')
    return json.loads(b''.join(chunks))


def imported_row(context,group,world,method,data,knowledge,base,query_reference):
    candidates=[r for r in context['all_historical_rows'] if r['group_id']==group['group_id'] and r['world']==world and r['method_id']==method['id']]
    require(len(candidates)==1,'Missing/duplicate ON row');original=candidates[0];row=deepcopy(original)
    public=historical_public(context,group['group_id'],world,method['id'])
    features,_=primary.pilot.feature_check(public,knowledge)
    scalar=primary.scalar.feature_vector(semantic._scalar_projection(public),knowledge,include_geometry=True)
    require(features['values']==row['features'] and scalar==row['scalar_features'],'Imported recipient/features differ')
    attach_case_queries(row,data,public,base,query_reference,method)
    row['imported_row_sha256']=analysis.digest(original)
    return row


def process_group(output,p,context,group):
    identity=group['group_id'];directory=output/'groups'/identity;require(not directory.exists(),'No group retry/overwrite');directory.mkdir(mode=0o700)
    imported=context['history']['original_groups'][identity];primary.write(directory/'attempt.json',dict(group_id=identity,split=group['split'],started_at=source.now(),original_pair=imported['files']['pair.json']))
    for name in ('in.json','out.json','auxiliary.json','pair.json'):os.link(authenticated(imported['files'][name]),directory/name)
    pair=previous.validate_pair_import(directory,imported);require(pair['group_id']==identity,'Wrong pair identity')
    primary.split.verify_actual_sources(context['manifest'],[pair],ROOT)
    knowledge=source.load(directory/'auxiliary.json');base=load_ref(p['original_config']);rows=[];auxiliary=[];cases=[];imported_on_cases=[];archives={};definition=None
    for world in ('IN','OUT'):
        work=directory/world;work.mkdir(mode=0o700);os.link(directory/('in.json' if world=='IN' else 'out.json'),work/'input.json');os.link(authenticated(p['native_binary']),work/'AggregationReplay')
        data=source.load(work/'input.json');bank=queries.prepare_reference(data,base)
        require(definition is None or definition==bank['definition'],'Query world definitions differ');definition=bank['definition']
        for method in ON_METHODS:
            rows.append(imported_row(context,group,world,method,data,knowledge,base,bank))
            imported_on_cases.append(dict(method_id=method['id'],world=world,status='verified',role='authenticated_historical_on'))
        records={}
        for method in NATIVE_METHODS:
            require(shutil.disk_usage(output).free>=p['minimum_free_bytes'],'Insufficient free disk')
            try:
                record,row=run_case(work,work/'input.json',base,method,group,world,knowledge,p,data=data,query_reference=bank)
                (auxiliary if method in AUXILIARY_METHODS else rows).append(row)
            except Exception as error:
                record=dict(method_id=method['id'],world=world,status='failed',role='auxiliary' if method in AUXILIARY_METHODS else 'headline',error=str(error));primary.write(work/(method['id']+'-failed.json'),record)
            records[method['id']]=record;cases.append(record)
        regional=next(m for m in OFF_METHODS if m['kind']=='regional_static')
        try:record,row=compose(work,base,group,world,knowledge,records,data,bank);rows.append(row)
        except Exception as error:record=dict(method_id=regional['id'],world=world,status='failed_dependency_or_audit',role='headline',error=str(error))
        cases.append(record);primary.write(work/(regional['id']+'-receipt.json'),record)
        archives[world]={}
        for path in sorted(work.glob('*.json')):
            if path.name=='input.json' or path.name.endswith(('-policy.json','-row.json','-execution.json','-receipt.json','-attempt.json','-failed.json')):continue
            archives[world][path.name]=primary.archive_file(path)
    primary.write(directory/'rows.json',rows);primary.write(directory/'auxiliary-rows.json',auxiliary);primary.write(directory/'archive-receipt.json',archives)
    summary=dict(group_id=identity,split=group['split'],status='verified' if len(rows)==28 and len(auxiliary)==6 and len(cases)==20 and all(c['status']=='verified' for c in cases) else 'incomplete',
        pair=pair,cases=cases,imported_on_cases=imported_on_cases,rows=primary.artifact(directory,directory/'rows.json'),auxiliary_rows=primary.artifact(directory,directory/'auxiliary-rows.json'),
        archives=primary.artifact(directory,directory/'archive-receipt.json'),aligned_query_definition=definition)
    primary.write(directory/'summary.json',summary);primary.write(directory/'ablation-receipt.json',dict(schema=SIDECAR_SCHEMA,protocol_sha256=source.sha(output/'protocol.json'),original_pair=imported['files']['pair.json'],summary_sha256=source.sha(directory/'summary.json'),rows_sha256=summary['rows']['sha256'],auxiliary_rows_sha256=summary['auxiliary_rows']['sha256']))
    return summary


def validate_imported_cases(cases):
    expected={(m['id'],world) for m in ON_METHODS for world in ('IN','OUT')}
    require(isinstance(cases,list) and len(cases)==14
        and {(c.get('method_id'),c.get('world')) for c in cases}==expected
        and all(c.get('status')=='verified' and c.get('role')=='authenticated_historical_on' for c in cases),'Incomplete authenticated ON case matrix')


def validate_imported_row(row,context):
    source_row=next((r for r in context['all_historical_rows'] if (r['group_id'],r['method_id'],r['world'])==(row['group_id'],row['method_id'],row['world'])),None)
    require(source_row is not None and row['imported_row_sha256']==analysis.digest(source_row),'ON row provenance differs')
    reconstructed=deepcopy(row);reconstructed.pop('imported_row_sha256');reconstructed.pop('recipient_digest_no_release_ids');reconstructed['utility'].pop('aligned_semantic_queries')
    require(reconstructed==source_row,'Imported ON fields changed beyond new query diagnostics')


def collect(output,p,context,*,verify_archives=False,require_complete=False):
    rows,summaries=primary.collect(output,context['manifest'],verify_archives=verify_archives);aux=[]
    expected_cases={(m['id'],w) for m in NATIVE_METHODS+(next(m for m in OFF_METHODS if m['kind']=='regional_static'),) for w in ('IN','OUT')}
    for summary in summaries:
        if summary['status'] in ('not_attempted','interrupted'):continue
        directory=output/'groups'/summary['group_id'];side=source.load(directory/'ablation-receipt.json');imported=context['history']['original_groups'][summary['group_id']]
        previous.validate_pair_import(directory,imported)
        require(side['schema']==SIDECAR_SCHEMA and side['protocol_sha256']==source.sha(output/'protocol.json') and side['original_pair']==imported['files']['pair.json']
                and side['summary_sha256']==source.sha(directory/'summary.json') and side['rows_sha256']==summary['rows']['sha256']
                and side['auxiliary_rows_sha256']==summary['auxiliary_rows']['sha256'],'Ablation group binding differs')
        validate_imported_cases(summary.get('imported_on_cases'))
        require(len(summary['cases'])==20 and {(c['method_id'],c['world']) for c in summary['cases']}==expected_cases,'Ablation case matrix differs')
        group_rows=source.load(primary.split.relative_file(directory,summary['rows']));group_aux=source.load(primary.split.relative_file(directory,summary['auxiliary_rows']));aux.extend(group_aux)
        for row in group_rows:
            if row['method_id'] in ON_IDS:validate_imported_row(row,context)
        if summary['status']=='verified':
            require(len(group_rows)==28 and len(group_aux)==6 and all(c['status']=='verified' for c in summary['cases']),'Forged verified group')
            for case in summary['cases']:
                evidence=case.get('exact_only',{})
                require(evidence.get('status')=='verified' and evidence.get('all_categories_terminal') is True
                    and evidence.get('semantic_loss_zero') is True and evidence.get('source_contributions_independently_audited') is True,'Missing exact-terminal source evidence')
                if case['method_id'] in {m['id'] for m in NATIVE_METHODS}:
                    require(case.get('independent_audit')==dict(status='verified',scalar_valid=True,published_policy_violations=0),'Missing independent native policy evidence')
    expected=window.expected_groups(context['manifest']);analysis._checked_rows(rows,expected,[m['id'] for m in METHODS],allow_test=True);analysis._checked_rows(aux,expected,[m['id'] for m in AUXILIARY_METHODS],allow_test=True)
    if require_complete:require(len(rows)==2016 and len(aux)==432 and len(summaries)==72 and all(s['status']=='verified' for s in summaries),'Complete72x14x2 headline and auxiliary matrix required')
    return rows,summaries,aux


def run_utility(output,*,limit=None):
    output,p,context=read_protocol(output);require(not any((output/n).exists() for n in FIT_OUTPUTS),'Utility cannot follow fitting attempt')
    require(limit is None or type(limit) is int and limit>0,'Invalid development limit');completed=0
    for group in context['manifest']['groups']:
        directory=output/'groups'/group['group_id']
        if directory.exists():require((directory/'summary.json').is_file(),'Interrupted group cannot be retried');continue
        if limit is not None and completed>=limit:break
        process_group(output,p,context,group);completed+=1
    return collect(output,p,context,require_complete=limit is None)


def duplicate_check(rows):
    by={(r['group_id'],r['world'],r['method_id']):r['recipient_digest_no_release_ids'] for r in rows};groups={(r['group_id'],r['world']) for r in rows}
    require(len(groups)==144,'Complete source/world comparison required');pairs={}
    adaptive=[m['id'] for m in OFF_METHODS if m['kind']=='native_adaptive']
    for a,b in itertools.combinations(adaptive,2):
        equal=sum(by[g,w,a]==by[g,w,b] for g,w in groups)
        pairs[a+'__vs__'+b]=dict(left=a,right=b,compared_streams=144,equal_streams=equal,all_equal=equal==144)
    return dict(status='verified',scope='recipient_payload_ignoring_release_ids',expected_streams_per_pair=144,by_pair=pairs,
        interpretation='Observed equality on shared recordings, not global algorithm equivalence or extra independent evidence.')


def native_execution_summary(context,rows,summaries):
    values=defaultdict(list);test=defaultdict(list)
    old=context['original_report']['native_execution_summary']
    for summary in summaries:
        for case in summary['cases']:
            if 'native_seconds' not in case:continue
            values[case['method_id']].append(case['native_seconds'])
            if summary['split']=='test':test[case['method_id']].append(case['native_seconds'])
    def agg(mapping):return {k:dict(runs=len(v),wall_seconds_mean=sum(v)/len(v),wall_seconds_p50=previous.percentile(v,.5),wall_seconds_p95=previous.percentile(v,.95),wall_seconds_maximum=max(v)) for k,v in mapping.items()}
    all_stats={k:v for k,v in old['by_method'].items() if k in ON_IDS};all_stats.update(agg(values))
    test_stats={k:v for k,v in old['by_method_test'].items() if k in ON_IDS};test_stats.update(agg(test))
    return dict(by_method=all_stats,by_method_test=test_stats,new_native_executions=1296,imported_native_executions=864,total_native_executions=2160,
        regional_compositions=144,imported_regional_streams=144,scope='Offline native subprocess diagnostics; imported ON and new OFF at different times; derived regional runtime unavailable. No per-step or live-delivery guarantee.')


def public_lineage(output,p,context,*,mia=False):
    a=context['history']['bound_anchors'];old=context['original_report']['strategy_supplement']['public_lineage']
    return dict(hard_policy_sha256=p['hard_policy_sha256'],original_config_sha256=p['original_config']['sha256'],ablation_protocol_sha256=source.sha(output/'protocol.json'),historical_snapshot_sha256=p['history']['sha256'],
        original_report_sha256=a['supplement_report']['sha256'],original_models_sha256=a['supplement_models']['sha256'],original_model_lock_sha256=a['supplement_model_lock']['sha256'],original_rows_sha256=context['original_report']['analysis']['all_rows_sha256'],
        historical_original_report_sha256=a['original_report']['sha256'],hard_policy_unchanged=True,source_resimulations=0,source_replacements=0,ONmodel_refits=0,
        imported_groups=72,imported_headline_rows=1008,new_headline_rows=1008,auxiliary_rows=432,new_native_executions=1296,regional_compositions=144,
        imported_attack_variants=14,new_attack_variants=14 if mia else 0,diagnostic_repair=deepcopy(old['diagnostic_repair']))


def report_base(output,p,context,rows,summaries):
    pairs=[s['pair'] for s in summaries];audit=primary.split.verify_actual_sources(context['manifest'],pairs,ROOT,require_complete=True);audit['status']='verified'
    definitions=[s['aligned_query_definition'] for s in summaries];require(all(d==definitions[0] for d in definitions),'Query definitions differ across recordings')
    ledger=context['values']['original_validation_ledger'];cases=[load_ref(v['receipt']) for v in ledger['cases']]
    return dict(**window._bindings(context['main']),method_catalog=deepcopy(METHODS),auxiliary_method_catalog=deepcopy(AUXILIARY_METHODS),
        group_outcomes=summaries,source_split_audit=audit,source_quality=window.source_quality(cases,context['manifest']),
        native_execution_summary=native_execution_summary(context,rows,summaries),aligned_query_definition=definitions[0],duplicate_check=duplicate_check(rows),
        semantic_ablation=dict(protocol=reference(output/'protocol.json'),historical_snapshot=p['history'],public_lineage=public_lineage(output,p,context),scope=p['scope']))


def utility_report(output):
    output,p,context=read_protocol(output);require(not any((output/n).exists() for n in FIT_OUTPUTS),'Utility gate precedes fitting attempt');require(not (output/'utility-report.json').exists(),'No utility overwrite')
    rows,summaries,aux=collect(output,p,context,verify_archives=True,require_complete=True)
    report=dict(schema=UTILITY_SCHEMA,**report_base(output,p,context,rows,summaries),utility={m['id']:analysis._utility([r for r in rows if r['method_id']==m['id']],window.expected_groups(context['manifest'])) for m in METHODS},
        mia_status='not_started',all_rows_sha256=analysis.digest(analysis._checked_rows(rows,window.expected_groups(context['manifest']),[m['id'] for m in METHODS],allow_test=True)),auxiliary_rows_sha256=analysis.digest(aux))
    primary.write(output/'utility-report.json',report);return report


def combine_models(original,new_attacks,rows,expected):
    require(set(new_attacks)=={m['id'] for m in OFF_METHODS},'All seven OFF attack families required')
    ids=[m['id'] for m in METHODS];checked=analysis._checked_rows(rows,expected,ids,allow_test=False)
    require(len(checked)==1120,'Complete40x14x2 TRAIN/CAL rows required')
    result=deepcopy(original);result.pop('prepared_sha256')
    result['attacks']={m:deepcopy(original['attacks'][m]) for m in ON_IDS};result['attacks'].update(deepcopy(new_attacks))
    require(result['controls']==original['controls'],'Control refit/replacement forbidden')
    result.update(method_ids=ids,expected_method_ids=ids,expected_groups=deepcopy(expected),training_calibration_rows_sha256=analysis.digest(checked),training_calibration_rows=len(checked),
        training_group_ids=sorted({r['group_id'] for r in checked if r['split']=='train'}),calibration_group_ids=sorted({r['group_id'] for r in checked if r['split']=='calibration'}),test_rows_seen=0,
        models=[dict(method_id=m,representation=r,**deepcopy(result['attacks'][m][r])) for m in ids for r in analysis.REPRESENTATIONS],
        scope='Derived14-method model view:14 enabled fitted objects and controls reused exactly;14 exact-only TRAIN fits/CAL locks. Reused-source exploratory ablation.')
    result['prepared_sha256']=analysis.digest(result);analysis.validate_model_lock(result,checked,require_complete=True);return result


def fit_mia(output):
    output,p,context=read_protocol(output);require(not any((output/n).exists() for n in FIT_OUTPUTS),'No fitting retry or post-score fitting')
    gate=source.load(output/'utility-report.json');require(gate['schema']==UTILITY_SCHEMA and gate['mia_status']=='not_started'
        and gate['semantic_ablation']['protocol']==reference(output/'protocol.json'),'Completed utility gate required')
    rows,summaries,aux=collect(output,p,context,require_complete=True);expected=window.expected_groups(context['manifest']);ids=[m['id'] for m in METHODS]
    checked=analysis._checked_rows(rows,expected,ids,allow_test=True);require(analysis.digest(checked)==gate['all_rows_sha256'] and analysis.digest(aux)==gate['auxiliary_rows_sha256'],'Utility-gate rows changed')
    training=[r for r in checked if r['split']!='test'];require(len(training)==1120,'Complete TRAIN/CAL family required')
    primary.write(output/'mia-fit-attempt.json',dict(schema='ump.urban-semantic-ablation-fit-attempt.v1',status='attempted',started_at=source.now(),protocol=reference(output/'protocol.json'),utility_gate=reference(output/'utility-report.json'),training_rows_sha256=analysis.digest(training),new_fit_count=14,test_rows_seen_by_fitter=0,model_parameters=deepcopy(analysis.MODEL_PARAMETERS)))
    attacks={};completed=0
    try:
        for method in OFF_METHODS:
            selected=[r for r in training if r['method_id']==method['id']];attacks[method['id']]={}
            for rep,(field,_) in analysis.REPRESENTATIONS.items():
                attacks[method['id']][rep]=analysis._fit(selected,lambda row,f=field:row[f],expected);completed+=1
        models=combine_models(context['models'],attacks,training,expected)
    except BaseException as error:
        primary.write(output/'mia-fit-failed.json',dict(status='failed',error=str(error),completed_fit_invocations=completed,no_retry=True));raise
    primary.write(output/'train-cal-rows.json',training);primary.write(output/'models.json',models)
    lock=dict(schema=LOCK_SCHEMA,status='locked_before_ablation_TEST_scoring',created_at=source.now(),protocol=reference(output/'protocol.json'),utility_gate=reference(output/'utility-report.json'),models=reference(output/'models.json'),data=reference(output/'train-cal-rows.json'),fit_attempt=reference(output/'mia-fit-attempt.json'),
        original_models=context['history']['bound_anchors']['supplement_models'],original_model_lock=context['history']['bound_anchors']['supplement_model_lock'],new_fit_count=14,ONmodel_refits=0,original_threshold_retunes=0,training_groups=24,calibration_groups=16,test_rows_seen_by_fitter=0,test_sources_already_seen=True,scope=p['scope'])
    primary.write(output/'models-lock.json',lock);return lock


def authenticate_model_lock(output,p,context,training):
    lock=source.load(output/'models-lock.json');a=context['history']['bound_anchors']
    require(lock['schema']==LOCK_SCHEMA and lock['status']=='locked_before_ablation_TEST_scoring'
        and lock['protocol']==reference(output/'protocol.json') and lock['utility_gate']==reference(output/'utility-report.json')
        and lock['fit_attempt']==reference(output/'mia-fit-attempt.json') and lock['new_fit_count']==14
        and lock['ONmodel_refits']==lock['original_threshold_retunes']==lock['test_rows_seen_by_fitter']==0
        and lock['training_groups']==24 and lock['calibration_groups']==16 and lock['test_sources_already_seen'] is True
        and lock['original_models']==a['supplement_models'] and lock['original_model_lock']==a['supplement_model_lock'],'Model-lock scope differs')
    attempt=load_ref(lock['fit_attempt']);require(attempt['schema']=='ump.urban-semantic-ablation-fit-attempt.v1' and attempt['status']=='attempted'
        and attempt['protocol']==reference(output/'protocol.json') and attempt['utility_gate']==reference(output/'utility-report.json')
        and attempt['new_fit_count']==14 and attempt['test_rows_seen_by_fitter']==0 and attempt['model_parameters']==analysis.MODEL_PARAMETERS,'Fit attempt differs')
    models=load_ref(lock['models']);locked=load_ref(lock['data']);expected=window.expected_groups(context['manifest']);ids=[m['id'] for m in METHODS]
    checked=analysis._checked_rows(training,expected,ids,allow_test=False)
    require(len(checked)==1120 and analysis.digest(checked)==attempt['training_rows_sha256']==analysis.digest(analysis._checked_rows(locked,expected,ids,allow_test=False)),'Locked TRAIN/CAL evidence differs')
    require(all(models['attacks'][m]==context['models']['attacks'][m] for m in ON_IDS) and models['controls']==context['models']['controls'],'Imported ON/control object changed')
    analysis.validate_model_lock(models,locked,require_complete=True);return models


def exploratory_contrasts(assessed):
    result={}
    for name,left,right,seed in CONTRASTS:
        reps={}
        for rep in analysis.REPRESENTATIONS:
            a,b=assessed['attacks'][left][rep],assessed['attacks'][right][rep]
            reps[rep]=analysis.paired_source_auc_difference(a['group_scores'],b['group_scores'],replicates=1000,seed=seed) if a['status']==b['status']=='evaluated' else dict(status='unavailable',left_status=a['status'],right_status=b['status'])
        result[name]=dict(left=left,right=right,metric='ROC_AUC',representations=reps,scope='OFF minus enabled, exploratory paired-source comparison; fixed fits/CAL, marginal intervals, no equivalence claim.')
    return result


def assess_mia(output):
    output,p,context=read_protocol(output,verify_archives=True,verify_raw=True)
    require(not (output/'final-report.json').exists(),'No final-report overwrite')
    rows,summaries,aux=collect(output,p,context,verify_archives=True,require_complete=True);training=[r for r in rows if r['split']!='test'];models=authenticate_model_lock(output,p,context,training)
    assessed=analysis.evaluate_models(models,rows);old=context['original_report']['analysis']
    require(all(assessed['attacks'][m]==old['attacks'][m] for m in ON_IDS) and assessed['controls']==old['controls']
        and assessed['primary_contrast']==context['original_primary'],'Historical ON assessment/control/primary changed')
    base=report_base(output,p,context,rows,summaries);base['semantic_ablation']['public_lineage']=public_lineage(output,p,context,mia=True)
    report=dict(schema=REPORT_SCHEMA,**base,analysis=assessed,exploratory_contrasts=exploratory_contrasts(assessed),original_primary_result_preserved=True,
        models_lock=reference(output/'models-lock.json'),final_verification=dict(historical_source_groups=72,original_archive_groups=72,supplement_archive_groups=72,new_archive_groups=72,
            historical_source_code_archive=p['history'],new_native_binary=p['native_binary'],physical_audit_reexecutions=0,source_simulations=0,
            scope='Full original capture payload hashes and unchanged GT/sensor exporter reconstruction against historical producer/proof chains; old/new archives decompressed. Historical current-code frozen_check is not claimed after native changes. No source/physical audit reexecution.'))
    primary.write(output/'final-report.json',report);return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);action=parser.add_mutually_exclusive_group(required=True)
    for name in ('prepare','check','run-utility','utility-report','fit-mia','assess-mia'):action.add_argument('--'+name,type=Path)
    parser.add_argument('--history',type=Path,default=DEFAULT_HISTORY);parser.add_argument('--native-binary',type=Path,default=DEFAULT_BINARY);parser.add_argument('--contract',type=Path);parser.add_argument('--limit',type=int)
    args=parser.parse_args(argv)
    if args.prepare:
        require(args.contract is not None,'Explicit ablation contract required');require(args.limit is None,'No limited prepare');print(prepare(args.prepare,history=args.history,binary=args.native_binary,contract=args.contract));return
    output=args.check or args.run_utility or args.utility_report or args.fit_mia or args.assess_mia
    require(args.limit is None or args.run_utility,'Limit applies only to explicit DEV utility calls')
    descriptor=os.open(output/'.semantic-ablation.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.check:read_protocol(output);print('verified: historical archive bridge and unchanged ablation policy')
        elif args.run_utility:run_utility(output,limit=args.limit)
        elif args.utility_report:utility_report(output)
        elif args.fit_mia:fit_mia(output)
        else:assess_mia(output)
    finally:os.close(descriptor)


if __name__=='__main__':main()
