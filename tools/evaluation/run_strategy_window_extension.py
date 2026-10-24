#!/usr/bin/env python3
"""Predeclare standalone Temporal First and matched long-window fixed controls.

Uses both complete frozen observation streams. Numeric policy constraints and
input observations remain unchanged. Longer fixed windows that violate local
hard limits are suppressed rather than granted a baseline-specific exemption.
"""
from __future__ import annotations
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
_spec=importlib.util.spec_from_file_location('ump_strategy_window_correction_helpers',
    ROOT/'tools/evaluation/run_spatial20_correction.py')
helper=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helper)
require,sha,read,write=helper.require,helper.sha,helper.read,helper.write
SOURCES=helper.SOURCES
CONTRACTS=helper.CONTRACTS
PILOT='mixed_spatial20_adaptive_temporal_first_off'


def matrix():
    rows=[]
    for source in SOURCES:
        for contract in CONTRACTS:
            rows.append(dict(id=f'{source}_{contract}_adaptive_temporal_first_off',source=source,
                contract=contract,method='adaptive_temporal_first',mode='temporal_first',enabled=False,
                role='standalone_temporal_priority'))
            for side,depth in ((5,4),(10,3),(20,2)):
                for window in (2000,4000):
                    method=f'fixed_{side}m_{window}ms'
                    rows.append(dict(id=f'{source}_{contract}_{method}_off',source=source,
                        contract=contract,method=method,mode='fixed',enabled=False,
                        fixed_depth=depth,fixed_window_ms=window,role='matched_long_fixed_window'))
    return rows


def selected_cases(names):
    planned=matrix();known={row['id'] for row in planned}
    if names is None or names==['all']:return planned
    require(isinstance(names,(list,tuple)) and names and len(set(names))==len(names)
        and all(name in known for name in names),'Choose unique predeclared extension cases or all')
    return [row for row in planned if row['id'] in names]


def hard_policy(config):
    """Strip only application/tree identity and execution-choice metadata."""
    value=copy.deepcopy(config)
    value.pop('application_id',None)
    value['policy_tree'].pop('id',None)
    value['policy_tree'].pop('execution',None)
    return value


def config_for(original,row):
    config=copy.deepcopy(original)
    cap=config['policy_tree']['root'].get('semantic_suppression_fraction',{}).get('max',0)
    require(cap==0,'The extension is OFF-only; source policy permits selective suppression')
    config['application_id']+='/strategy-window-extension/'+row['method']
    config['policy_tree']['id']+='/strategy-window-extension/'+row['method']
    if row['mode']=='temporal_first':
        execution=config['policy_tree']['execution']
        execution['strategy']='temporal_first'
        execution.pop('semantic_secondary_strategy',None)
    require(hard_policy(config)==hard_policy(original),'Numeric or regional policy changed')
    require(config['window_ms']==original['window_ms'],'Adaptive base window changed')
    return config


def checked_reference(case,label):
    checked=case.get('independent_audit',{})
    require(checked.get('status')=='verified' and checked.get('scalar_valid') is True
        and checked.get('published_policy_violations')==0,'Unverified reference: '+label)
    for key in ('config_sha256','result_sha256'):
        value=case.get(key)
        require(isinstance(value,str) and len(value)==64
            and all(c in '0123456789abcdef' for c in value),'Missing reference digest: '+label)
    return {key:copy.deepcopy(case[key]) for key in ('stats','independent_audit','config_sha256',
        'result_sha256','native_process_wall_seconds','native_runtime') if key in case}


def verify_corrected(path,sources,binary_sha):
    root=Path(path)
    require(not root.is_symlink(),'Corrected study cannot be a symbolic link')
    root=root.resolve(strict=True)
    summary=read(helper.safe_file(root,'summary.json'))
    require(summary.get('schema')=='ump.spatial20-correction.v1' and summary.get('status')=='verified'
        and summary.get('completion_scope')=='all_16_predeclared_cases'
        and summary.get('executed_case_count')==summary.get('planned_case_count')==16,
        'Require the complete verified corrected study')
    protocol=read(helper.safe_file(root,'protocol.json'))
    require(sha(root/'protocol.json')==summary.get('protocol_sha256') and protocol==summary.get('protocol'),
        'Corrected protocol receipt differs')
    require(protocol['native_binary_sha256']==binary_sha,'Use the same corrected binary as the adaptive references')
    refs={}
    for source in SOURCES:
        receipt=protocol['sources'][source]
        require(receipt['summary_sha256']==sources[source]['summary_sha256']
            and receipt['observations_sha256']==sources[source]['observations_sha256'],
            'Corrected reference source differs: '+source)
        for contract in CONTRACTS:
            for method in ('adaptive_immediate','adaptive_spatial_first'):
                identifier=f'{source}_{contract}_{method}_off';case=summary['cases'][identifier]
                require(case.get('off_policy_byte_identity_verified') is True,'Corrected OFF policy not identical')
                config=helper.safe_file(root,identifier+'-policy.json')
                require(sha(config)==case['config_sha256'],'Corrected reference config changed')
                require(case['config_sha256']==sources[source]['references'][contract+'_'+method]['config_sha256'],
                    'Corrected reference policy differs from original')
                refs[identifier]=dict(**checked_reference(case,identifier),source=source,contract=contract,
                    method=method,role='verified_corrected_adaptive_reference')
    return dict(root=root,summary_sha256=sha(root/'summary.json'),protocol_sha256=sha(root/'protocol.json'),
        references=refs)


def metric_row(case):
    stats=case['stats'];accounting=stats['source_accounting']
    return dict(source=case['source'],contract=case['contract'],method=case['method'],role=case['role'],
        input_observations=stats['input_observation_contributions'],
        retained_fraction=stats['retained_fraction'],full_input_semantic_distortion=stats['full_input_semantic_distortion'],
        retained_semantic_loss=stats['observation_weighted_semantic_loss'],
        retained_mean_cell_side_m=stats['observation_weighted_cell_side_m'],
        retained_mean_window_ms=stats['observation_weighted_interval_duration_ms'],
        retained_delay_ms=accounting['observation_to_release_delay_ms'],core_processing_ms=stats['core_processing_ms'],
        source_point_regions=accounting.get('by_source_point_region',accounting.get('by_region',{})),
        native_process_wall_seconds=case['native_process_wall_seconds'],
        config_sha256=case['config_sha256'],result_sha256=case['result_sha256'])


def fmt(value,scale=1):return 'n/a' if value is None else f'{value*scale:.3f}'


def markdown(summary):
    lines=['# Strategy and fixed-window extension','',
        'Full frozen streams; unchanged hard policies; selective suppression OFF. Temporal First preserves temporal accuracy by preferring spatial aggregation. Fixed windows remain subject to all local duration and age limits.','',
        'J penalizes every omitted input observation by one and adds retained taxonomy loss, divided by all inputs. Lower is better. Conditional metrics are undefined when nothing is retained. No attack-based privacy gain is claimed.','']
    rows=summary['comparison_rows']
    for source in SOURCES:
        for contract in CONTRACTS:
            lines.extend([f'## {source} / {contract}','',
                '| Method | Evidence | Retained (%) | J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |',
                '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |'])
            for row in rows:
                if row['source']!=source or row['contract']!=contract:continue
                delay=row['retained_delay_ms']
                lines.append('| '+' | '.join((row['method'],row['role'],fmt(row['retained_fraction'],100),
                    fmt(row['full_input_semantic_distortion'],100),fmt(row['retained_semantic_loss'],100),
                    fmt(row['retained_mean_cell_side_m']),fmt(row['retained_mean_window_ms']),
                    fmt(delay.get('mean'))+' / '+fmt(delay.get('p95')),fmt(row['core_processing_ms'])))+' |')
            lines.append('')
    lines.extend(['## Limits','',
        '- One realization per source; strategy and window sensitivity, not population-level inference.',
        '- Previous verified references are reused with summary/configuration/result digests. Their timings are separate recordings; no paired runtime claim.',
        '- A 2 s or 4 s fixed window is not exempt from a regional 1 s bound. Zero release is an admissibility result, not evidence of an implementation failure.',
        '- Core processing excludes motion generation, Python audit, rendering and final file I/O. Offline throughput does not establish deadline compliance.',
        '- Regional source-point cohorts may overlap and must not be summed as a partition.',
        '- Every current case passes the independent full-input accounting and public-policy audit with a declared one-million-cell audit bound.',''])
    return '\n'.join(lines)


def extension(mixed_portfolio,pedestrian_portfolio,corrected_study,output,binary,*,cases=None,wall_budget_s=240):
    require(type(wall_budget_s) is int and 1<=wall_budget_s<=240,'Native wall budget must be an integer from 1 to 240 seconds')
    chosen=selected_cases(cases);planned=matrix();output=Path(output)
    require(not output.exists() and not output.is_symlink(),'Choose a fresh extension directory')
    binary=Path(binary).resolve();require(binary.is_file(),'Build the corrected AggregationReplay binary first')
    sources={name:helper.verify_portfolio(path) for name,path in
        (('mixed',mixed_portfolio),('pedestrians',pedestrian_portfolio))}
    binary_sha=sha(binary);corrected=verify_corrected(corrected_study,sources,binary_sha)
    output=output.resolve()
    for source_root in [s['root'] for s in sources.values()]+[corrected['root']]:
        require(not output.is_relative_to(source_root) and not source_root.is_relative_to(output),
            'Extension must be separate from each frozen source study')
    output.parent.mkdir(parents=True,exist_ok=True);output.mkdir(mode=0o700)
    provenance=output/'provenance';provenance.mkdir()
    shutil.copy2(binary,provenance/'AggregationReplay')
    implementation_sources={'run_strategy_window_extension.py':Path(__file__).resolve(),
        'run_spatial20_correction.py':ROOT/'tools/evaluation/run_spatial20_correction.py',
        'CellLocalAggregation.cpp':ROOT/'simulator/src/CellLocalAggregation.cpp',
        'CellLocalAggregation.hpp':ROOT/'simulator/include/CellLocalAggregation.hpp'}
    for name,path in implementation_sources.items():shutil.copyfile(path,provenance/name)
    write(provenance/'implementation-receipt.json',dict(files_sha256={name:sha(provenance/name) for name in implementation_sources},
        scope='Copied orchestration and controller files at protocol freeze. Native binary digest is the execution identity; no clean-tree claim.'))
    references=copy.deepcopy(corrected['references']);source_receipts={}
    shutil.copyfile(corrected['root']/'summary.json',provenance/'corrected-summary.json')
    shutil.copyfile(corrected['root']/'protocol.json',provenance/'corrected-protocol.json')
    for name,source in sources.items():
        shutil.copyfile(source['observations'],output/(name+'-observations.json'))
        shutil.copyfile(source['root']/'summary.json',provenance/(name+'-original-summary.json'))
        shutil.copyfile(source['proof'],provenance/(name+'-capture-proof.json'))
        source_receipts[name]=dict(observations_sha256=source['observations_sha256'],
            original_summary_sha256=source['summary_sha256'],capture_proof_sha256=sha(source['proof']),
            **copy.deepcopy(source['summary']['source']))
        for contract in CONTRACTS:
            for side in (5,10,20):
                for window in (400,1000):
                    method=f'fixed_{side}m_{window}ms';old=f'{contract}_{method}'
                    references[f'{name}_{old}_off']=dict(**checked_reference(source['references'][old],old),
                        source=name,contract=contract,method=method,role='verified_historical_fixed_reference')
    commands={};configs={}
    for row in planned:
        identifier=row['id'];source=sources[row['source']]
        base=read(source['configs'][row['contract']+'_adaptive_immediate'])
        config=config_for(base,row);config_path=output/(identifier+'-policy.json');write(config_path,config)
        configs[identifier]=config_path;step=source['summary']['protocol']['progress_step_ms']
        require(type(step) is int and step>0,'Invalid frozen progress step')
        command=[str(provenance/'AggregationReplay'),'--input',str(output/(row['source']+'-observations.json')),
            '--config',str(config_path),'--mode',row['mode'],'--output',str(output/(identifier+'.json')),
            '--progress-step-ms',str(step)]
        if row['mode']=='fixed':command+=['--fixed-depth',str(row['fixed_depth']),'--fixed-window-ms',str(row['fixed_window_ms'])]
        commands[identifier]=command
    frozen={str(path.relative_to(output)):sha(path) for path in output.rglob('*') if path.is_file()}
    protocol=dict(schema='ump.strategy-window-extension-protocol.v1',matrix=planned,selected_cases=[r['id'] for r in chosen],
        commands=commands,native_binary_sha256=binary_sha,native_process_wall_budget_s=wall_budget_s,
        offline_audit_max_cells=1000000,pre_execution_artifacts_sha256=frozen,sources=source_receipts,
        corrected_reference_summary_sha256=corrected['summary_sha256'],corrected_reference_protocol_sha256=corrected['protocol_sha256'],
        numeric_policy_scope='Identical root/regional hard bounds, history and taxonomy; only application/tree IDs and adaptive execution strategy change. Fixed depth/window are CLI selection parameters, not policy exemptions.',
        filtering_scope='OFF for every method; no suppression-policy sensitivity in this extension.',
        fixed_scope='5m/depth4, 10m/depth3, 20m/depth2 over unchanged 80m domain; 2s/4s windows, subject to every existing regional limit.',
        runtime_scope='Native core and subprocess wall time exclude Python audit and motion generation; offline unpaced, no deadline guarantee.',
        scientific_scope='Predeclared matrix on two complete fixed streams; one realization each. Reused historical metrics retain separate timing provenance.',
        privacy_scope='Operational policy compliance and source-denominated utility only; no measured attack resistance.')
    write(output/'protocol.json',protocol);protocol_sha=sha(output/'protocol.json')
    summary=dict(schema='ump.strategy-window-extension.v1',status='running',protocol=protocol,protocol_sha256=protocol_sha,
        reference_cases=references,cases={},scientific_repetitions=0)
    current_source=None;data=None
    for row in chosen:
        identifier=row['id'];source=sources[row['source']]
        helper.check_frozen(output,frozen);require(sha(binary)==binary_sha,'Native binary changed after freeze')
        if current_source!=row['source']:
            data=read(output/(row['source']+'-observations.json'));current_source=row['source']
            helper.mapped.validate_completed_source(read(source['proof']),data)
            coverage=data['coverage']
            require(coverage.get('width')==80 and coverage.get('height')==80 and coverage.get('leaf_depth')==6,
                'This predeclared depth/side matrix requires the frozen 80m square D6 domain')
        config=read(configs[identifier]);command=commands[identifier];start=time.perf_counter()
        try:completed=subprocess.run(command,text=True,capture_output=True,timeout=wall_budget_s)
        except subprocess.TimeoutExpired as error:
            write(output/(identifier+'-execution.json'),dict(command=command,status='native_timeout',wall_budget_s=wall_budget_s))
            raise RuntimeError(identifier+': native wall budget exhausted') from error
        wall=time.perf_counter()-start
        (output/(identifier+'.log')).write_text(completed.stdout+completed.stderr)
        write(output/(identifier+'-execution.json'),dict(command=command,returncode=completed.returncode,
            native_process_wall_seconds=wall,timing_scope=protocol['runtime_scope']))
        require(completed.returncode==0,identifier+': native execution failed: '+completed.stderr[:2000])
        helper.check_frozen(output,frozen);result_path=output/(identifier+'.json');result=read(result_path)
        audited_config=copy.deepcopy(config);audited_config['temporal_adaptation']['coordination']=result['parameters']['coordination']
        checked=helper.audit(data,audited_config,result,max_cells=1000000)
        stats=helper.summarize(data,config,result,checked);write(output/(identifier+'-private-audit.json'),checked)
        base_name=row['contract']+'_adaptive_immediate'
        base_path=source['configs'][base_name]
        require(sha(base_path)==source['references'][base_name]['config_sha256'],
            'Original policy changed during extension')
        require(hard_policy(config)==hard_policy(read(base_path)),
            'Executed policy differs from the frozen hard policy')
        summary['cases'][identifier]=dict(**row,stats=stats,native_runtime=result.get('runtime',{}),
            independent_audit=dict(status=checked['status'],scalar_valid=checked['scalar']['valid'],
                semantic_published_cells=checked['semantic_published_cells'],published_policy_violations=0),
            native_process_wall_seconds=wall,result_sha256=sha(result_path),config_sha256=sha(configs[identifier]),
            hard_policy_identity_verified=True)
        print(json.dumps(dict(case=identifier,status='verified',retained_fraction=stats['retained_fraction'],
            full_input_semantic_distortion=stats['full_input_semantic_distortion'],native_process_wall_seconds=wall)),flush=True)
        del result,checked
    helper.check_frozen(output,frozen)
    require(sha(output/'protocol.json')==protocol_sha and sha(binary)==binary_sha,'Frozen protocol or binary changed')
    require(sha(corrected['root']/'summary.json')==corrected['summary_sha256']
        and sha(corrected['root']/'protocol.json')==corrected['protocol_sha256'],
        'Corrected reference summary or protocol changed')
    for source in sources.values():
        require(sha(source['root']/'summary.json')==source['summary_sha256']
            and sha(source['observations'])==source['observations_sha256'],'Original source changed during extension')
    summary.update(status='verified',completion_scope='all_28_predeclared_cases' if len(chosen)==28 else 'explicit_predeclared_subset',
        planned_case_count=len(planned),executed_case_count=len(chosen),
        comparison_rows=[metric_row(case) for case in (*references.values(),*summary['cases'].values())])
    write(output/'summary.json',summary)
    (output/'report.md').write_text(markdown(summary),encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mixed-portfolio',type=Path,required=True)
    parser.add_argument('--pedestrian-portfolio',type=Path,required=True)
    parser.add_argument('--corrected-study',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'simulator/build/AggregationReplay')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cases',nargs='+',default=['all'],help='all or unique predeclared case IDs; pilot: '+PILOT)
    parser.add_argument('--native-wall-budget-s',type=int,default=240)
    args=parser.parse_args();result=extension(args.mixed_portfolio,args.pedestrian_portfolio,args.corrected_study,
        args.output,args.binary,cases=args.cases,wall_budget_s=args.native_wall_budget_s)
    print(json.dumps(dict(status=result['status'],completion_scope=result['completion_scope'],executed_case_count=result['executed_case_count'])))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as error:raise SystemExit('Strategy/window extension failed: '+str(error))
