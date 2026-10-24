#!/usr/bin/env python3
"""Build compact aggregate-only tables from a completed correction study.

This reads bounded summary/configuration JSON only, never movement or native
private-window arrays. Native audit/provenance assertions remain those of the
verified correction runner; this report checks their compact consistency.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

SOURCES=('mixed','pedestrians')
CONTRACTS=('original','spatial20')
ADAPTIVE=('adaptive_immediate','adaptive_spatial_first')
BASELINES=('fixed_10m_1000ms','fixed_20m_400ms','fixed_20m_1000ms')
MAX_JSON_BYTES=16*1024*1024


def require(value,message):
    if not value:raise ValueError(message)


def digest(raw):return hashlib.sha256(raw).hexdigest()


def read(path):
    path=Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=MAX_JSON_BYTES,
            'Require a bounded regular aggregate/configuration file: '+str(path))
    raw=path.read_bytes()
    return json.loads(raw),digest(raw)


def number(value,label,*,minimum=None,maximum=None):
    require(type(value) in (int,float) and math.isfinite(value),'Nonfinite/non-numeric '+label)
    require(minimum is None or value>=minimum,'Below range '+label)
    require(maximum is None or value<=maximum,'Above range '+label)
    return value


def checked_case(case,label):
    audit=case.get('independent_audit',{})
    require(audit.get('status')=='verified' and audit.get('scalar_valid') is True
            and audit.get('published_policy_violations')==0,'Unverified audit: '+label)
    for key in ('config_sha256','result_sha256'):
        value=case.get(key)
        require(isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value),
                'Missing artifact digest: '+label+' '+key)
    stats=case['stats'];total=number(stats['input_observation_contributions'],label+' input',minimum=1)
    retained=number(stats['retained_observation_contributions'],label+' retained',minimum=0,maximum=total)
    fraction=number(stats['retained_fraction'],label+' retention',minimum=0,maximum=1)
    require(math.isclose(fraction,retained/total,abs_tol=1e-12),'Retention denominator differs: '+label)
    loss=stats['observation_weighted_semantic_loss']
    if retained:
        number(loss,label+' conditional semantic loss',minimum=0,maximum=1)
        expected=(total-retained+retained*loss)/total
    else:
        require(loss is None,'No retained support must have undefined conditional loss: '+label)
        expected=1
    distortion=number(stats['full_input_semantic_distortion'],label+' full-input distortion',minimum=0,maximum=1)
    require(math.isclose(distortion,expected,abs_tol=1e-12),'Full-input objective differs: '+label)
    accounting=stats['source_accounting'];delay=accounting['observation_to_release_delay_ms']
    regions={};outside=None
    if 'by_source_point_region' in accounting:
        regional=accounting['by_source_point_region'];n_key='input_observation_contributions';r_key='retained_observation_contributions'
    else:
        regional=accounting['by_region'];n_key='input_observations';r_key='retained_observations'
    for name,row in regional.items():
        n=number(row[n_key],label+' regional input',minimum=0)
        r=number(row[r_key],label+' regional retained',minimum=0,maximum=n)
        require(n<=total,'Regional input exceeds source: '+label)
        cohort={'input_observations':n,'retained_observations':r,'retained_fraction':r/n if n else None}
        if name=='outside_policy_regions':outside=cohort
        else:regions[name]=cohort
    selective=number(stats.get('selectively_suppressed_observation_contributions',0),label+' selective omission',minimum=0)
    whole=number(stats.get('whole_footprint_suppressed_observation_contributions',total-retained),label+' whole omission',minimum=0)
    require(retained+selective+whole==total,'Source conservation differs: '+label)
    return dict(input_observations=total,retained_observations=retained,retained_fraction=fraction,
        full_input_semantic_distortion=distortion,retained_only_semantic_loss=loss,
        retained_mean_cell_side_m=stats['observation_weighted_cell_side_m'],
        retained_mean_window_ms=stats['observation_weighted_interval_duration_ms'],
        retained_delay_mean_ms=delay['mean'],retained_delay_p95_ms=delay['p95'],
        core_processing_ms=number(stats['core_processing_ms'],label+' core',minimum=0),
        native_process_wall_seconds=number(case['native_process_wall_seconds'],label+' wall',minimum=0),
        selectively_suppressed_observations=selective,whole_footprint_suppressed_observations=whole,
        config_sha256=case['config_sha256'],result_sha256=case['result_sha256'],
        source_point_regions=regions,outside_named_regions=outside)


def changes(before,after):
    require(before['input_observations']==after['input_observations'],'Compared source denominators differ')
    result={key:None if before[key] is None or after[key] is None else after[key]-before[key]
            for key in ('retained_observations','retained_fraction','full_input_semantic_distortion',
                'retained_only_semantic_loss','retained_mean_cell_side_m','retained_mean_window_ms',
                'retained_delay_mean_ms','retained_delay_p95_ms','core_processing_ms')}
    result['core_processing_ratio_after_over_before']=after['core_processing_ms']/before['core_processing_ms'] if before['core_processing_ms'] else None
    require(set(before['source_point_regions'])==set(after['source_point_regions']),'Compared regional cohorts differ')
    regions={}
    for name,old in before['source_point_regions'].items():
        new=after['source_point_regions'][name]
        require(old['input_observations']==new['input_observations'],'Regional source denominator differs: '+name)
        regions[name]=dict(input_observations=old['input_observations'],
            retained_before=old['retained_observations'],retained_after=new['retained_observations'],
            retained_observation_delta=new['retained_observations']-old['retained_observations'],
            retained_fraction_delta=None if old['retained_fraction'] is None else new['retained_fraction']-old['retained_fraction'])
    result['source_point_regions']=regions
    return result


def build_report(summary,originals,summary_sha256=None):
    require(summary.get('schema')=='ump.spatial20-correction.v1' and summary.get('status')=='verified',
            'Require the verified correction summary')
    require(summary.get('completion_scope')=='all_16_predeclared_cases'
            and summary.get('executed_case_count')==summary.get('planned_case_count')==16,
            'Require all sixteen predeclared cases')
    protocol=summary['protocol'];cases=summary['cases'];expected=set()
    for source in SOURCES:
        for contract in CONTRACTS:
            for method in ADAPTIVE:expected.add(f'{source}_{contract}_{method}_off')
        for method in (*ADAPTIVE,'fixed_20m_1000ms'):
            expected.add(f'{source}_spatial20_{method}_on')
        expected.add(f'{source}_spatial20_fixed_20m_1000ms_off')
    require(set(cases)==expected,'Correction case matrix differs')
    require(set(protocol.get('selected_cases',[]))==expected,'Declared case matrix differs')
    report=dict(schema='ump.spatial20-correction-aggregate-report.v1',status='verified_aggregate_consistency',
        correction_summary_sha256=summary_sha256,correction_protocol_sha256=summary['protocol_sha256'],
        corrected_binary_sha256=protocol['native_binary_sha256'],sources={},primary_tables=[],
        correction_changes=[],baseline_comparisons=[],filtering_sensitivity=[],
        scope=dict(objective='J=(N_input-N_retained+sum_retained taxonomy_loss)/N_input; unit omission cost. Lower is better; experimental utility, not privacy risk.',
            conditional_metrics='Semantic loss, cell side, interval length and observation-to-release delay condition on retained observations.',
            regional_cohorts='Compare the four named nonexclusive source-point cohorts; regional privacy/utility checks use full-cell intersections. Historical outside-policy-region counts remain as optional provenance, but the corrected audit does not provide this cohort. It is not reconstructed by subtracting overlapping named cohorts. Regional counts must not be summed as a partition.',
            timing='Historical and corrected core/process timings are separate recordings, not paired statistical estimates. Core excludes simulation, Python audit, rendering and report writing.',
            baselines='Historical fixed10m/1s and fixed20m/.4s,1s are unchanged-policy references. The corrected fixed20m/1s OFF identity control checks exact public/private logical equality; other fixed cases are not rerun.',
            filtering='ON is a separate root maximum selective-suppression fraction of 0.1; OFF policies retain byte identity. Compare ON/OFF within the same method and contract.',
            study='Two frozen sources, one realization each; post hoc implementation repair, no statistical population inference. Different source motion prevents an isolated taxonomy-causality claim.',
            privacy='Zero audited violations refers to selected operational constraints; neither attack resistance nor a privacy gain is measured.',
            provenance='Reported source/native result digests are execution receipts from the verified runner; this lightweight report does not reread movement or private arrays.'))
    for source in SOURCES:
        old,old_sha=originals[source]
        require(old.get('schema')=='ump.mapped-comparison.v1' and old.get('status')=='verified','Unverified original summary')
        receipt=protocol['sources'][source]
        require(receipt['summary_sha256']==old_sha,'Original summary digest differs')
        require(receipt['observations_sha256']==old['protocol']['observations_sha256'],'Original source digest differs')
        require(receipt['original_binary_sha256']==old['protocol']['binary_sha256'],'Original binary digest differs')
        report['sources'][source]={key:receipt[key] for key in
            ('summary_sha256','bundle_sha256','observations_sha256','capture_proof_sha256','original_binary_sha256',
             'horizon_ms','sampling_period_ms','input_observation_contributions')}
        for contract in CONTRACTS:
            rows=[]
            for method in ADAPTIVE:
                name=f'{source}_{contract}_{method}_off';new=cases[name];prior=old['cases'][f'{contract}_{method}']
                require(new.get('off_policy_byte_identity_verified') is True
                        and new['config_sha256']==prior['config_sha256'],'OFF policy differs: '+name)
                before=checked_case(prior,'historical '+name);after=checked_case(new,'corrected '+name)
                require(before['input_observations']==receipt['input_observation_contributions'],'Historical source input differs')
                rows.extend([dict(method=method,implementation='historical',metrics=before),
                             dict(method=method,implementation='corrected',metrics=after)])
                report['correction_changes'].append(dict(source=source,contract=contract,method=method,delta=changes(before,after)))
                for baseline in BASELINES:
                    reference=checked_case(old['cases'][f'{contract}_{baseline}'],'historical '+baseline)
                    for epoch,metrics in (('historical',before),('corrected',after)):
                        report['baseline_comparisons'].append(dict(source=source,contract=contract,method=method,
                            implementation=epoch,baseline=baseline,adaptive_minus_fixed=changes(reference,metrics)))
            for baseline in BASELINES:
                rows.append(dict(method=baseline,implementation='historical_fixed_reference',
                    metrics=checked_case(old['cases'][f'{contract}_{baseline}'],'historical '+baseline)))
            report['primary_tables'].append(dict(source=source,contract=contract,rows=rows))
        identity=cases[f'{source}_spatial20_fixed_20m_1000ms_off']
        require(identity.get('fixed_release_identity_verified') is True
                and identity.get('fixed_private_window_identity_verified') is True
                and identity.get('off_policy_byte_identity_verified') is True,'Fixed identity control failed')
        for method in (*ADAPTIVE,'fixed_20m_1000ms'):
            off=cases[f'{source}_spatial20_{method}_off'];on=cases[f'{source}_spatial20_{method}_on']
            require(off['enabled'] is False and on['enabled'] is True,'Filtering case label differs')
            before=checked_case(off,'corrected filtering OFF');after=checked_case(on,'corrected filtering ON')
            report['filtering_sensitivity'].append(dict(source=source,contract='spatial20',method=method,
                off=before,on=after,on_minus_off=changes(before,after)))
    return report


def fmt(value,scale=1):return 'n/a' if value is None else f'{value*scale:.3f}'


def markdown(report):
    lines=['# Same-input controller correction: aggregate results','',
        'All 16 predeclared corrected cases passed independent audits. The main OFF policies and frozen observation streams are unchanged. Results are a post hoc implementation correction, with one realization per source.','',
        'Retention and full-input distortion use every input observation. J assigns unit cost to omitted observations plus retained taxonomy loss; lower is better. Semantic loss, spatial detail and delay are conditional on retained data.','']
    for table in report['primary_tables']:
        lines.extend([f"## {table['source']} / {table['contract']}",'',
            '| Method | Implementation | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell (m) | Mean window (ms) | Mean / p95 delay (ms) | Core (ms) |',
            '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |'])
        for row in table['rows']:
            m=row['metrics'];lines.append('| '+' | '.join([row['method'],row['implementation'],fmt(m['retained_fraction'],100),
                fmt(m['full_input_semantic_distortion'],100),fmt(m['retained_only_semantic_loss'],100),
                fmt(m['retained_mean_cell_side_m']),fmt(m['retained_mean_window_ms']),
                fmt(m['retained_delay_mean_ms'])+' / '+fmt(m['retained_delay_p95_ms']),fmt(m['core_processing_ms'])])+' |')
        lines.append('')
    lines.extend(['## Regional correction deltas','',
        'Nonexclusive source-point cohorts; this is not a disjoint regional partition. Deltas are corrected minus historical OFF.','',
        '| Source / contract / method | Region | Input | Retained before → after | Retention delta (pp) |',
        '| --- | --- | ---: | ---: | ---: |'])
    for row in report['correction_changes']:
        for region,m in row['delta']['source_point_regions'].items():
            lines.append(f"| {row['source']} / {row['contract']} / {row['method']} | {region} | {m['input_observations']} | {m['retained_before']} → {m['retained_after']} | {fmt(m['retained_fraction_delta'],100)} |")
    lines.extend(['','## Separate filtering sensitivity','',
        'ON changes the root maximum selective-suppression fraction from 0 to 0.1. It is a separate policy sensitivity, not part of the unchanged-policy correction.','',
        '| Source / method | OFF → ON retention (%) | OFF → ON full-input J (%) | Selectively omitted / input (%) | Mean delay OFF → ON (ms) |',
        '| --- | ---: | ---: | ---: | ---: |'])
    for row in report['filtering_sensitivity']:
        a,b=row['off'],row['on']
        lines.append(f"| {row['source']} / {row['method']} | {fmt(a['retained_fraction'],100)} → {fmt(b['retained_fraction'],100)} | {fmt(a['full_input_semantic_distortion'],100)} → {fmt(b['full_input_semantic_distortion'],100)} | {fmt(b['selectively_suppressed_observations']/b['input_observations'],100)} | {fmt(a['retained_delay_mean_ms'])} → {fmt(b['retained_delay_mean_ms'])} |")
    lines.extend(['','## Limits and provenance',''])
    lines.extend('- '+value for value in report['scope'].values())
    lines.extend(['',f"Correction summary SHA-256: `{report['correction_summary_sha256']}`.",
        f"Corrected binary SHA-256: `{report['corrected_binary_sha256']}`.",'',
        'The accompanying aggregate JSON contains source/configuration/result hashes and numerical baseline/region deltas. It contains no individual identities, positions or movement records.',''])
    return '\n'.join(lines)


def report(study,output):
    study,output=Path(study).resolve(),Path(output)
    require(not output.exists(),'Choose a fresh report output directory')
    summary,summary_sha=read(study/'summary.json');protocol,protocol_sha=read(study/'protocol.json')
    require(protocol_sha==summary.get('protocol_sha256') and protocol==summary.get('protocol'),'Protocol receipt differs')
    originals={source:read(study/'provenance'/(source+'-original-summary.json')) for source in SOURCES}
    result=build_report(summary,originals,summary_sha)
    for name,case in summary['cases'].items():
        _,config_sha=read(study/(name+'-policy.json'))
        require(config_sha==case['config_sha256'],'Corrected configuration digest differs: '+name)
    output.mkdir(parents=True)
    (output/'aggregate-report.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    (output/'report.md').write_text(markdown(result))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=report(args.study,args.output)
    print(json.dumps(dict(status=result['status'],primary_tables=len(result['primary_tables']),
        correction_changes=len(result['correction_changes']),filtering_sensitivity=len(result['filtering_sensitivity']))))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,TypeError) as error:raise SystemExit('Correction aggregate report failed: '+str(error))
