#!/usr/bin/env python3
"""Predeclare bounded same-input controller-correction and filtering checks.

No motion is generated. Main OFF configurations are byte-for-byte copies from
completed verified portfolios. ON cases are separately declared sensitivity
checks. Frozen historical fixed baselines are references, not rerun timings.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
_mapped_spec=importlib.util.spec_from_file_location(
    'ump_spatial20_correction_mapped_comparison',ROOT/'tools/mapped_scene/run_comparison.py')
mapped=importlib.util.module_from_spec(_mapped_spec)
_mapped_spec.loader.exec_module(mapped)
from run_local_policy_replay import audit

MAX_BYTES=2*1024**3
SOURCES=('mixed','pedestrians')
CONTRACTS=('original','spatial20')
ADAPTIVE=(('adaptive_immediate','semantic_first'),('adaptive_spatial_first','spatial_first'))
PILOT='mixed_spatial20_adaptive_immediate_off'


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def read(path):
    path=Path(path)
    require(path.is_file() and path.stat().st_size<=MAX_BYTES,'Require a regular JSON artifact of at most 2 GiB')
    with path.open(encoding='utf-8') as stream:return json.load(stream)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')


def safe_file(root,name):
    require(isinstance(name,str) and bool(name) and not Path(name).is_absolute()
            and '\\' not in name and all(part not in ('','.','..') for part in name.split('/')),
            'Artifact paths must be canonical and relative')
    current=root
    for part in name.split('/'):
        current=current/part
        require(not current.is_symlink(),'Symbolic input artifacts are not supported')
    require(current.is_file() and current.resolve().is_relative_to(root),'Missing or escaping source artifact: '+name)
    return current


def matrix():
    cases=[]
    for source in SOURCES:
        for contract in CONTRACTS:
            for method,mode in ADAPTIVE:
                cases.append(dict(id=f'{source}_{contract}_{method}_off',source=source,contract=contract,
                    method=method,mode=mode,enabled=False,original_case=f'{contract}_{method}',role='primary_correction'))
        for method,mode in (*ADAPTIVE,('fixed_20m_1000ms','fixed')):
            cases.append(dict(id=f'{source}_spatial20_{method}_on',source=source,contract='spatial20',
                method=method,mode=mode,enabled=True,original_case=f'spatial20_{method}',role='separate_filtering_sensitivity'))
        cases.append(dict(id=f'{source}_spatial20_fixed_20m_1000ms_off',source=source,contract='spatial20',
            method='fixed_20m_1000ms',mode='fixed',enabled=False,
            original_case='spatial20_fixed_20m_1000ms',role='fixed_identity_control'))
    return cases


def selected_cases(names):
    planned=matrix();by_id={row['id']:row for row in planned}
    if names is None or names==['all']:return planned
    require(isinstance(names,(list,tuple)) and names and len(set(names))==len(names)
            and all(name in by_id for name in names),'Choose unique predeclared correction cases or all')
    return [row for row in planned if row['id'] in names]


def on_config(original):
    config=copy.deepcopy(original)
    config['policy_tree']['root']['semantic_suppression_fraction']={'max':.1}
    config['policy_tree']['id']+='/correction-suppression-on'
    config['application_id']+='/correction-suppression-on'
    return config


def verify_portfolio(path):
    root=Path(path)
    require(not root.is_symlink(),'Portfolio root cannot be a symbolic link')
    root=root.resolve(strict=True);summary=read(safe_file(root,'summary.json'));bundle=read(safe_file(root,'bundle.json'))
    require(summary.get('schema')=='ump.mapped-comparison.v1' and summary.get('status')=='verified',
            'Require a completed independently verified original portfolio')
    require(summary.get('protocol',{}).get('comparison_kind')=='spatial_resolution_portfolio',
            'Expected the original/spatial20 comparison contract')
    require(bundle.get('schema')=='ump.replay-viewer.v1','Missing original viewer manifest')
    entries={row['id']:row for row in bundle.get('variants',[])}
    require(len(entries)==len(bundle.get('variants',[])) and set(entries)==set(summary.get('cases',{})),
            'Original summary and manifest cases differ')
    for name,digest in bundle.get('sha256',{}).items():
        require(re.fullmatch(r'[a-f0-9]{64}',digest or '') and sha(safe_file(root,name))==digest,
                'Original manifest artifact changed: '+name)
    observations=safe_file(root,bundle.get('observations'));observations_sha=sha(observations)
    require(observations_sha==summary['protocol'].get('observations_sha256'),'Original observation digest differs')
    configs={};references={}
    for name,case in summary['cases'].items():
        require(name in entries,'Missing original case manifest')
        result=safe_file(root,entries[name]['result']);policy=safe_file(root,name+'-policy.json')
        require(sha(result)==case.get('result_sha256') and sha(policy)==case.get('config_sha256'),
                'Original native result or configuration changed: '+name)
        checked=case.get('independent_audit',{})
        require(checked.get('status')=='verified' and checked.get('scalar_valid') is True
                and checked.get('published_policy_violations')==0,'Original independent audit failed: '+name)
        configs[name]=policy
        references[name]={key:copy.deepcopy(case[key]) for key in
            ('policy_profile','policy_tree_id','stats','independent_audit','result_sha256','config_sha256','native_process_wall_seconds') if key in case}
    proof=safe_file(root,'provenance/capture-proof.json')
    require(sha(proof)==summary['protocol'].get('source_proof_sha256'),'Original capture proof changed')
    mapped.validate_completed_source(read(proof))
    old_binary=safe_file(root,'provenance/AggregationReplay')
    require(sha(old_binary)==summary['protocol'].get('binary_sha256'),'Original frozen native binary changed')
    for name,digest in summary['protocol'].get('pre_execution_artifacts_sha256',{}).items():
        require(sha(safe_file(root,name))==digest,'Original pre-execution artifact changed: '+name)
    return dict(root=root,summary=summary,bundle=bundle,observations=observations,
        observations_sha256=observations_sha,configs=configs,references=references,proof=proof,old_binary=old_binary,
        summary_sha256=sha(root/'summary.json'),bundle_sha256=sha(root/'bundle.json'))


def check_frozen(output,hashes):
    for name,digest in hashes.items():
        require(sha(safe_file(output,name))==digest,'Frozen correction artifact changed: '+name)


def summarize(data,config,result,checked):
    require(checked.get('status')=='verified' and checked.get('scalar',{}).get('valid') is True,
            'Independent corrected-result audit did not pass')
    stats=mapped.summarize(data,config,result)
    accounting=checked['source_accounting']
    require(accounting['input_observations']==stats['input_observation_contributions']
            and accounting['retained_observations']==stats['retained_observation_contributions'],
            'Independent retained-source accounting differs from public totals')
    require(accounting['retained_observations']+accounting['selectively_suppressed_observations']
            +accounting['whole_footprint_suppressed_observations']==accounting['input_observations'],
            'Corrected source conservation failed')
    stats.update(source_accounting=accounting,
        selectively_suppressed_observation_contributions=accounting['selectively_suppressed_observations'],
        whole_footprint_suppressed_observation_contributions=accounting['whole_footprint_suppressed_observations'],
        suppression_candidates=checked.get('suppression_candidates',0),
        contribution_selection=checked['contribution_selection'],
        full_input_distortion_scope='Unit penalty for every omitted observation plus retained taxonomy loss; experimental utility score, not privacy risk.',
        original_gt_exact_query_scope='Not evaluated; filtered products contain retained-population counts.')
    return stats


def correction(mixed_portfolio,pedestrian_portfolio,output,binary,*,cases=None,wall_budget_s=240):
    require(type(wall_budget_s) is int and 1<=wall_budget_s<=240,'Native wall budget must be an integer from 1 to 240 seconds')
    selected=selected_cases(cases);planned=matrix();output=Path(output)
    require(not output.exists() and not output.is_symlink(),'Choose a fresh correction directory')
    binary=Path(binary).resolve();require(binary.is_file(),'Build the corrected AggregationReplay binary first')
    source_paths=dict(mixed=mixed_portfolio,pedestrians=pedestrian_portfolio)
    sources={name:verify_portfolio(source_paths[name]) for name in SOURCES}
    output=output.resolve()
    require(all(not output.is_relative_to(s['root']) and not s['root'].is_relative_to(output) for s in sources.values()),
            'Correction output must be separate from each frozen original portfolio')
    binary_sha=sha(binary);output.parent.mkdir(parents=True,exist_ok=True);output.mkdir(mode=0o700)
    provenance=output/'provenance';provenance.mkdir()
    shutil.copy2(binary,provenance/'AggregationReplay')
    implementation_sources={
        'run_spatial20_correction.py':Path(__file__).resolve(),
        'CellLocalAggregation.cpp':ROOT/'simulator/src/CellLocalAggregation.cpp',
        'CellLocalAggregation.hpp':ROOT/'simulator/include/CellLocalAggregation.hpp'}
    for name,path in implementation_sources.items():shutil.copyfile(path,provenance/name)
    git_head=None
    git_dir=ROOT/'.git'
    if git_dir.is_dir() and (git_dir/'HEAD').is_file():
        text=(git_dir/'HEAD').read_text().strip()
        if text.startswith('ref: '):
            ref=text[5:]
            if not Path(ref).is_absolute() and '..' not in Path(ref).parts and (git_dir/ref).is_file():git_head=(git_dir/ref).read_text().strip()
        else:git_head=text
    write(provenance/'implementation-receipt.json',dict(
        repository_head=git_head,files_sha256={name:sha(provenance/name) for name in implementation_sources},
        scope='Copied runner and controller implementation files at protocol freeze; no clean-working-tree claim. Native binary SHA is the execution identity.'))
    commands=[];configs={};historical={};source_info={}
    for name,source in sources.items():
        shutil.copyfile(source['observations'],output/(name+'-observations.json'))
        shutil.copyfile(source['root']/'summary.json',provenance/(name+'-original-summary.json'))
        shutil.copyfile(source['root']/'bundle.json',provenance/(name+'-original-bundle.json'))
        shutil.copyfile(source['proof'],provenance/(name+'-capture-proof.json'))
        source_info[name]=dict(summary_sha256=source['summary_sha256'],bundle_sha256=source['bundle_sha256'],
            observations_sha256=source['observations_sha256'],capture_proof_sha256=sha(source['proof']),
            original_binary_sha256=sha(source['old_binary']),**copy.deepcopy(source['summary']['source']))
        for contract in CONTRACTS:
            for method in ('fixed_20m_400ms','fixed_20m_1000ms','fixed_10m_1000ms'):
                old=contract+'_'+method;historical[name+'_'+old]=copy.deepcopy(source['references'][old])
    for row in planned:
        identifier=row['id'];source=sources[row['source']];original=source['configs'].get(row['original_case'])
        require(original is not None,'Missing required frozen controller policy')
        config_path=output/(identifier+'-policy.json')
        if row['enabled']:write(config_path,on_config(read(original)))
        else:shutil.copyfile(original,config_path)
        configs[identifier]=config_path
        step=source['summary']['protocol']['progress_step_ms']
        require(type(step) is int and step>0,'Invalid original progress step')
        command=[str(provenance/'AggregationReplay'),'--input',str(output/(row['source']+'-observations.json')),
            '--config',str(config_path),'--mode',row['mode'],'--output',str(output/(identifier+'.json')),
            '--progress-step-ms',str(step)]
        if row['mode']=='fixed':command+=['--fixed-depth','2','--fixed-window-ms','1000']
        commands.append(command)
    frozen={str(path.relative_to(output)):sha(path) for path in output.rglob('*') if path.is_file()}
    protocol=dict(schema='ump.spatial20-correction-protocol.v1',analysis_status='post_hoc_controller_correction_and_separate_filtering_sensitivity',
        matrix=planned,selected_cases=[row['id'] for row in selected],commands=commands,
        native_binary_sha256=binary_sha,native_process_wall_budget_s=wall_budget_s,offline_audit_max_cells=1000000,
        pre_execution_artifacts_sha256=frozen,sources=source_info,
        off_policy_scope='Exact original policy bytes and IDs; controller implementation only is changed.',
        on_policy_changes=[dict(path='policy_tree.root.semantic_suppression_fraction.max',before=0,after=.1),
            dict(path='policy_tree.id',change='append /correction-suppression-on'),dict(path='application_id',change='append /correction-suppression-on')],
        historical_baseline_scope='Previously verified fixed20m/.4s, fixed20m/1s and fixed10m/1s aggregate evidence under each unchanged contract; no rerun timing claim.',
        runtime_scope='Native subprocess wall time and native runtime.processing_ms exclude Python parsing, independent audit and report writing. No concurrent heavy task is scheduled by this runner.',
        privacy_scope='Operational policy/support compliance and source-denominated utility only; no empirical privacy-gain claim.',
        source_scope='Full identical frozen observation streams, unchanged timestamp/ID/type/position; no motion regeneration or prefix selection.')
    write(output/'protocol.json',protocol);protocol_sha=sha(output/'protocol.json')
    summary=dict(schema='ump.spatial20-correction.v1',status='running',protocol=protocol,protocol_sha256=protocol_sha,
        historical_fixed_baselines=historical,cases={},scientific_repetitions=0)
    by_id={row['id']:command for row,command in zip(planned,commands)}
    current_source=None;data=None
    for row in selected:
        identifier=row['id'];source=sources[row['source']]
        check_frozen(output,frozen)
        require(sha(binary)==binary_sha,'Corrected binary changed after protocol freeze')
        if row['source']!=current_source:
            data=read(output/(row['source']+'-observations.json'));current_source=row['source']
            mapped.validate_completed_source(read(source['proof']),data)
        config=read(configs[identifier]);command=by_id[identifier]
        start=time.perf_counter()
        try:
            completed=subprocess.run(command,text=True,capture_output=True,timeout=wall_budget_s)
            wall=time.perf_counter()-start
        except subprocess.TimeoutExpired as error:
            write(output/(identifier+'-execution.json'),dict(command=command,status='native_timeout',wall_budget_s=wall_budget_s))
            raise RuntimeError(identifier+': native wall budget exhausted') from error
        (output/(identifier+'.log')).write_text(completed.stdout+completed.stderr)
        write(output/(identifier+'-execution.json'),dict(command=command,returncode=completed.returncode,
            native_process_wall_seconds=wall,timing_scope=protocol['runtime_scope']))
        require(completed.returncode==0,identifier+': native execution failed: '+completed.stderr[:2000])
        check_frozen(output,frozen)
        result_path=output/(identifier+'.json');result=read(result_path)
        audited_config=copy.deepcopy(config)
        audited_config['temporal_adaptation']['coordination']=result['parameters']['coordination']
        checked=audit(data,audited_config,result,max_cells=1000000)
        stats=summarize(data,config,result,checked)
        write(output/(identifier+'-private-audit.json'),checked)
        original=source['references'][row['original_case']]
        case=dict(**row,stats=stats,independent_audit=dict(status=checked['status'],scalar_valid=checked['scalar']['valid'],
            semantic_published_cells=checked['semantic_published_cells'],published_policy_violations=0),
            native_process_wall_seconds=wall,native_runtime=result.get('runtime',{}),
            result_sha256=sha(result_path),config_sha256=sha(configs[identifier]),
            old_reference=copy.deepcopy(original),
            timing_scope=protocol['runtime_scope'])
        if row['role']=='fixed_identity_control':
            old_path=next(item['result'] for item in source['bundle']['variants'] if item['id']==row['original_case'])
            old_result=read(safe_file(source['root'],old_path))
            case['fixed_release_identity_verified']=result['releases']==old_result['releases']
            case['fixed_private_window_identity_verified']=result['windows']==old_result['windows']
            require(case['fixed_release_identity_verified'] and case['fixed_private_window_identity_verified'],
                    'Fixed identity control changed logical private decisions or public releases')
            del old_result
        if not row['enabled']:
            case['off_policy_byte_identity_verified']=case['config_sha256']==original['config_sha256']
            require(case['off_policy_byte_identity_verified'],'OFF policy bytes differ from original')
            case['retained_fraction_change_from_original']=stats['retained_fraction']-original['stats']['retained_fraction']
        summary['cases'][identifier]=case
        print(json.dumps(dict(case=identifier,status='verified',retained_fraction=stats['retained_fraction'],
            full_input_semantic_distortion=stats['full_input_semantic_distortion'],native_process_wall_seconds=wall)),flush=True)
        del result,checked
    check_frozen(output,frozen)
    require(sha(output/'protocol.json')==protocol_sha and sha(binary)==binary_sha,'Frozen protocol or binary changed')
    for source in sources.values():
        require(sha(source['root']/'summary.json')==source['summary_sha256'] and sha(source['root']/'bundle.json')==source['bundle_sha256']
                and sha(source['observations'])==source['observations_sha256'],'Original source changed during correction study')
    summary.update(status='verified',completion_scope='all_16_predeclared_cases' if len(selected)==16 else 'explicit_predeclared_subset',
        planned_case_count=len(planned),executed_case_count=len(selected))
    write(output/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mixed-portfolio',type=Path,required=True)
    parser.add_argument('--pedestrian-portfolio',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'simulator/build/AggregationReplay')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cases',nargs='+',default=['all'],help='all or unique predeclared case IDs; pilot: '+PILOT)
    parser.add_argument('--native-wall-budget-s',type=int,default=240)
    args=parser.parse_args()
    result=correction(args.mixed_portfolio,args.pedestrian_portfolio,args.output,args.binary,
        cases=args.cases,wall_budget_s=args.native_wall_budget_s)
    print(json.dumps(dict(status=result['status'],completion_scope=result['completion_scope'],executed_case_count=result['executed_case_count'])))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:raise SystemExit('Correction study failed: '+str(error))
