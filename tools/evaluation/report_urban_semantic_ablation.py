#!/usr/bin/env python3
"""Aggregate-only report for the paired semantic-generalization action ablation.

This layer projects authenticated runner summaries through explicit allowlists.
It opens no referenced artifact, fits no model and changes no estimate. Historical
ON results remain immutable; added OFF comparisons reuse already exposed sources.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path

import report_urban_privacy_primary as strict
import report_urban_track_window_primary as window
import report_urban_strategy_supplement as previous
import urban_semantic_ablation_queries as queries

INPUT_SCHEMA='ump.urban-semantic-ablation-report.v1'
UTILITY_INPUT_SCHEMA='ump.urban-semantic-ablation-utility.v1'
SCHEMA='ump.urban-semantic-ablation-public-report.v1'
ARTIFACT_SCHEMA='ump.urban-semantic-ablation-public-artifacts.v1'
PROFILE=window.PROFILE
GROUP_COUNTS=dict(strict.GROUP_COUNTS)
REPRESENTATIONS=tuple(strict.REPRESENTATIONS)
CONTROLS=tuple(strict.CONTROLS)
BASE_METHODS=(
    ('fixed20_400ms','Fixed 20 m / 0.4 s'),
    ('regional_static20','Regional static 20 m'),
    ('adaptive_temporal_first','Temporal First'),
    ('adaptive_spatial_first','Spatial First'),
    ('adaptive_semantic_first','Semantic First / immediate'),
    ('adaptive_semantic_wait_temporal','Semantic First → Temporal First / wait'),
    ('adaptive_semantic_wait_spatial','Semantic First → Spatial First / wait'),
)
ON_IDS=tuple(name for name,_ in BASE_METHODS)
OFF_IDS=tuple(name+'_exact_only' for name in ON_IDS)
METHOD_IDS=ON_IDS+OFF_IDS
AUXILIARY_IDS=tuple('fixed20_'+str(ms)+'ms_exact_only' for ms in (1000,2000,4000))
ALL_IDS=METHOD_IDS+AUXILIARY_IDS
CATEGORIES=('road_user','pedestrian','adult_pedestrian','child_pedestrian','senior_pedestrian',
    'pedestrian_with_stroller','pedestrian_with_mobility_aid','cyclist','e_scooter_rider',
    'adult_cyclist','senior_cyclist','adult_e_scooter_rider')
SOURCE_CLASSES=('Adult Pedestrian','Child Pedestrian','Senior Pedestrian','Pedestrian With Stroller',
    'Pedestrian With Mobility Aid','Adult Cyclist','Senior Cyclist','Adult E-Scooter Driver')
REGIONS=('entrance-vicinity','west-footway-control','central-through-footway','east-footway-control','outside_policy_regions')
CONTRASTS=tuple((name+'_exact_only_vs_enabled',name+'_exact_only',name,20261027401+i) for i,name in enumerate(ON_IDS))
DUPLICATE_PAIRS=tuple(itertools.combinations(OFF_IDS[2:],2))
HASH_FIELDS=('hard_policy_sha256','original_config_sha256','ablation_protocol_sha256','historical_snapshot_sha256',
    'original_report_sha256','original_models_sha256','original_model_lock_sha256','original_rows_sha256')
COHORT_FIELDS=('input_observation_contributions','retained_observation_contributions','unpublished_observation_contributions','retained_fraction')
SCOPE=(
    'Exploratory semantic-action ablation on already exposed recordings; the original primary study and strategy supplement remain unchanged.',
    'Same source observations, target/auxiliary pairs, taxonomy and hard regional policies. ON allows truthful taxonomy generalization; OFF permits input-leaf categories only. Whole failed candidates may be suppressed; selective contribution suppression remains OFF.',
    'Seven ON/OFF pairs are headline comparisons. Three additional OFF fixed-window methods are dependencies of regional composition, not extra headline strategies.',
    'Regional cohort attribution uses source-point membership; hard policies apply to the whole candidate footprint and may intersect several regions. Overlapping cohort summaries are not new independent populations.',
    'Exact-only zero semantic loss is conditional on surviving input. Always read retention, full-input J and per-source-class/region omission alongside it.',
    'J=(1-retained fraction)+retained fraction times retained taxonomy loss. It includes omission and semantic distortion, excludes spatial/temporal distortion, and is not a privacy metric.',
    'Aligned 20 m / 400 ms taxonomy queries count observation contributions. Ancestor/descendant workloads overlap and must not be summed as distinct traffic. Missing public support and semantic ambiguity remain unknown, not zero.',
    'Exact and estimated query answers are separate. Estimates allocate identifiable category counts uniformly in sampled space/time only; they never distribute coarse labels among semantic descendants or use private cohort frequencies.',
    'Each world uses its own sampled reference. Utility uses equal-recording TEST macro means with metric-specific available Ns; conditional error must be read with answered coverage.',
    'MIA protects inclusion of all observed contributions of one operational track within [0,300 s), not identity, a complete journey or every visit. TRAIN fits/scaling and CAL thresholds stay separate from TEST.',
    'Full111 versus Scalar31 is a joint representation ablation, not a semantic-action ablation or an isolated semantic-leakage measure.',
    'OFF-minus-ON AUC intervals use 1000 paired-source bootstrap replicates conditional on fixed fits/CAL; intervals are exploratory, non-simultaneous, and establish no equivalence margin.',
    'A duplicate recipient transcript is an observation under these inputs, not universal equivalence of the algorithms. Every declared strategy remains in the execution/model family.',
    'One final recipient snapshot at H=300 s; logical sealing delay and offline native/core times do not establish live delivery or per-step real-time guarantees. Movement quality remains separate from privacy.',
)
require=strict.require


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _lineage(report,phase):
    value=strict._object(strict._object(report.get('semantic_ablation'),'semantic ablation').get('public_lineage'),'public lineage')
    require(value.get('hard_policy_unchanged') is True,'Hard regional policy changed')
    result={field:strict._hash(value.get(field)) for field in HASH_FIELDS}
    require(all(result.values()),'Mandatory ablation provenance hash missing')
    counts=dict(imported_groups=72,imported_headline_rows=1008,new_headline_rows=1008,auxiliary_rows=432,
        new_native_executions=1296,regional_compositions=144,ONmodel_refits=0,imported_attack_variants=14,
        new_attack_variants=0 if phase=='utility' else 14,source_resimulations=0,source_replacements=0)
    result.update(previous._counts(value,counts,'ablation lineage'))
    repair=strict._object(value.get('diagnostic_repair'),'original diagnostic repair')
    require(repair.get('source_validation_profile')==PROFILE,'Original diagnostic profile differs')
    projected={key:strict._hash(repair.get(key)) for key in previous.REPAIR_HASH_FIELDS}
    require(all(projected.values()),'Missing original diagnostic repair provenance')
    projected.update(previous._counts(repair,previous.REPAIR_COUNTS,'diagnostic repair'))
    require(repair.get('original_test_source_status_counts')=={'invalid':32},'Original diagnostic failures must remain visible')
    projected.update(source_validation_profile=PROFILE,original_test_source_status_counts={'invalid':32})
    result.update(hard_policy_unchanged=True,diagnostic_repair=projected)
    return result


def _definition(value):
    value=strict._object(value,'aligned query definition')
    require(value.get('schema')==queries.SCHEMA and value.get('cell_side_m')==20 and value.get('window_ms')==400,
            'Aligned query dimensions/schema differ')
    require(value.get('count_unit')=='observation_contributions' and value.get('all_road_user_category')=='road_user',
            'Aligned query count/category contract differs')
    require(isinstance(value.get('categories'),list) and len(value['categories'])==len(CATEGORIES)
            and set(value['categories'])==set(CATEGORIES),'Aligned taxonomy workload changed')
    require(value.get('source_horizon_ms')==300000 and value.get('full_window_count')==750
            and value.get('spatial_cell_count')==16 and value.get('query_count')==144000,'Aligned query denominator changed')
    require(value.get('initial_sample_excluded') is True,'t0 must remain unsampled')
    result={key:value[key] for key in ('schema','cell_side_m','window_ms','count_unit','all_road_user_category',
        'source_horizon_ms','full_window_count','spatial_cell_count','query_count','initial_sample_excluded')}
    result.update(categories=sorted(CATEGORIES),taxonomy_sha256=strict._hash(value.get('taxonomy_sha256')),
                  sampling_period_ms=strict._integer(value.get('sampling_period_ms'),'sensor period',nullable=False))
    require(result['taxonomy_sha256'] is not None and result['sampling_period_ms']==100,'Aligned source cadence/taxonomy missing')
    return result


def _catalog(value,auxiliary):
    require(isinstance(value,list) and len(value)==14,'Exactly fourteen headline methods required')
    ids=[strict._object(item,'catalog method').get('id') for item in value]
    require(len(set(ids))==14 and set(ids)==set(METHOD_IDS),'Headline catalog missing/duplicate/unregistered')
    for item in value:
        base=item['id'].removesuffix('_exact_only')
        mode='exact_only' if item['id'] in OFF_IDS else 'enabled'
        kind='regional_static' if base=='regional_static20' else 'native_fixed' if base=='fixed20_400ms' else 'native_adaptive'
        require(item.get('on_method_id')==base and item.get('semantic_generalization')==mode and item.get('kind')==kind,
                'Catalog semantic action or method kind changed')
        if base=='fixed20_400ms':
            require(item.get('fixed_depth')==2 and item.get('window_ms')==400 and item.get('grid_side_m')==20,'Headline fixed schedule changed')
        if base=='regional_static20':require(item.get('grid_side_m')==20,'Regional fixed geometry changed')
        if base in previous.EXECUTION_CATALOG:
            require(tuple(item.get(key) for key in ('strategy','secondary_strategy','release_trigger'))==previous.EXECUTION_CATALOG[base],
                    'Catalog execution preferences differ')
    require(isinstance(auxiliary,list) and len(auxiliary)==3
            and {strict._object(item,'auxiliary method').get('id') for item in auxiliary}==set(AUXILIARY_IDS),
            'Exactly three registered composition dependencies required')
    for item in auxiliary:
        ms=int(item['id'].split('_')[1].removesuffix('ms'))
        require(item.get('kind')=='native_fixed' and item.get('fixed_depth')==2 and item.get('grid_side_m')==20
            and item.get('window_ms')==ms and item.get('semantic_generalization')=='exact_only','Auxiliary schedule/capability changed')


def _outcomes(groups):
    require(isinstance(groups,list),'Recording outcomes must be a list')
    splits={split:Counter() for split in GROUP_COUNTS};methods={method:Counter() for method in ALL_IDS};seen=set()
    for group in groups:
        group=strict._object(group,'recording outcome');identity=group.get('group_id');split=group.get('split')
        require(isinstance(identity,str) and identity and identity not in seen and split in GROUP_COUNTS,'Invalid/repeated recording or split')
        seen.add(identity);splits[split][strict._state(group.get('status'))]+=1
        keys=set();cases=group.get('cases',[]);imports=group.get('imported_on_cases',[])
        require(isinstance(cases,list) and isinstance(imports,list),'Cases and imported cases must be lists')
        require(all(strict._object(item,'imported case').get('method_id') in ON_IDS and item.get('role')=='authenticated_historical_on' for item in imports),'Imported case role/method differs')
        require(all(strict._object(item,'new case').get('method_id') not in ON_IDS for item in cases),'Historical ON must be explicit authenticated imports')
        cases=cases+imports
        for case in cases:
            case=strict._object(case,'case');method,world=case.get('method_id'),case.get('world')
            require(method in methods and world in ('IN','OUT') and (method,world) not in keys,'Repeated/unregistered method/world')
            keys.add((method,world));methods[method][strict._state(case.get('status'))]+=1
    for split,planned in GROUP_COUNTS.items():
        n=sum(splits[split].values());require(n<=planned,'Too many recording slots');splits[split]['not_reported']+=planned-n
    return dict(planned_recordings=72,planned_by_split=dict(GROUP_COUNTS),
        recording_status_by_split={split:dict(sorted(counts.items())) for split,counts in splits.items()},
        planned_headline_rows=2016,imported_headline_rows=1008,new_headline_rows=1008,auxiliary_rows=432,
        new_native_executions=1296,new_regional_compositions=144,
        method_world_status={method:dict(planned=144,observed=sum(counts.values()),unreported=144-sum(counts.values()),
            statuses=dict(sorted(counts.items())),role='auxiliary_dependency' if method in AUXILIARY_IDS else 'headline') for method,counts in methods.items()})


def _extra_utility_keys():
    keys=set()
    for mode in ('exact','estimate'):
        for stem in (f'aligned_semantic_queries.{mode}.summary',*(f'aligned_semantic_queries.{mode}.by_category.{category}' for category in CATEGORIES)):
            keys.update(stem+'.'+field for field in queries.SUMMARY_FIELDS)
            keys.update(stem+'.unknown_reasons.'+reason for reason in queries.REASONS)
    for family,cohorts in (('by_source_type',SOURCE_CLASSES),('by_source_point_region',REGIONS)):
        keys.update('source_accounting.'+family+'.'+cohort+'.'+field for cohort in cohorts for field in COHORT_FIELDS)
    return frozenset(keys)


EXTRA_UTILITY_KEYS=_extra_utility_keys()


def _utility(value):
    result=previous._utility(value)
    raw=strict._object(value.get('macro_means',{}),'macro means') if isinstance(value,dict) else {}
    for field in ('source_accounting.selectively_suppressed_observations','source_accounting.selectively_suppressed_fraction'):
        if field in raw:
            require(raw[field].get('mean') in (None,0),'Selective contribution suppression must remain OFF')
    def project(key,entry):
        entry=strict._object(entry,'utility mean')
        mean=strict._number(entry.get('mean'),'utility value',0)
        n=strict._integer(entry.get('recordings'),'metric available recordings',nullable=False)
        require(n<=result['observed_recordings'] and ((mean is None)==(n==0)),'Utility mean/N mismatch')
        if key.endswith(('.query_coverage','.scored_query_coverage','.retained_fraction')):
            require(mean is None or mean<=1,'Fractional utility exceeds one')
        return dict(mean=mean,recordings=n)
    for key in sorted(EXTRA_UTILITY_KEYS & raw.keys()):
        result['macro_means'][key]=project(key,raw[key])
    # Native source accounting and regional composition use different historical
    # field names. Normalize their approved aggregate aliases in this derived
    # presentation only; original row bytes remain unchanged. No absent outside-
    # region cohort is manufactured from overlapping regional counts.
    for family,cohorts in (('by_source_type',SOURCE_CLASSES),('by_source_point_region',REGIONS)):
        for cohort in cohorts:
            stem='source_accounting.'+family+'.'+cohort+'.'
            old_stem='source_accounting.'+('by_region' if family=='by_source_point_region' else family)+'.'+cohort+'.'
            for field in ('selectively_suppressed_observations','selectively_suppressed_fraction'):
                if old_stem+field in raw:require(raw[old_stem+field].get('mean') in (None,0),'Selective cohort suppression must remain OFF')
            for old,new in (('input_observations','input_observation_contributions'),('retained_observations','retained_observation_contributions'),('retained_fraction','retained_fraction')):
                if old_stem+old not in raw:continue
                item=project(stem+new,raw[old_stem+old])
                if stem+new in result['macro_means']:
                    require(result['macro_means'][stem+new]==item,'Conflicting source-accounting aliases')
                result['macro_means'][stem+new]=item
            incoming=result['macro_means'].get(stem+'input_observation_contributions',{})
            retained=result['macro_means'].get(stem+'retained_observation_contributions',{})
            if incoming.get('mean') is not None and retained.get('mean') is not None and incoming['recordings']==retained['recordings']:
                require(incoming['mean']>=retained['mean'],'Retained cohort exceeds input')
                derived=dict(mean=incoming['mean']-retained['mean'],recordings=incoming['recordings'])
                old=result['macro_means'].get(stem+'unpublished_observation_contributions')
                require(old is None or (old['recordings']==derived['recordings'] and math.isclose(old['mean'],derived['mean'],rel_tol=1e-12,abs_tol=1e-9)),
                        'Cohort omission contradicts input-retained accounting')
                result['macro_means'][stem+'unpublished_observation_contributions']=derived
    return result


def _exact_only_consistency(utility):
    for world in ('IN','OUT'):
        means=utility[world]['macro_means']
        loss=means.get('retained_semantic_loss',{})
        require(loss.get('mean') is None or loss['mean']==0,'Exact-only retained semantic loss must be zero')
        retained=means.get('retained_fraction',{});j=means.get('full_input_J',{})
        if retained.get('mean') is not None and j.get('mean') is not None and retained.get('recordings')==j.get('recordings'):
            require(math.isclose(j['mean'],1-retained['mean'],rel_tol=1e-12,abs_tol=1e-12),
                    'Exact-only J must equal omitted input fraction with the same available N')
        if retained.get('mean')==0:
            require(loss.get('mean') is None and loss.get('recordings',0)==0,
                    'Empty exact-only output has undefined conditional semantic loss, not zero')


def _runtime(value):
    value={} if value is None else strict._object(value,'native execution summary')
    result={'scope':'Offline native subprocess wall diagnostics; core and logical delay have different boundaries. Historical ON and new OFF run at different times; regional composition native runtime unavailable; no per-step/live guarantee.'}
    allowed=set(ALL_IDS)-{'regional_static20','regional_static20_exact_only'}
    for key,n in (('by_method',144),('by_method_test',64)):
        raw=strict._object(value.get(key,{}),'runtime family');require(set(raw)<=allowed,'Unknown or nonnative runtime method')
        result[key]={}
        for method,row in raw.items():
            row=strict._object(row,'runtime');count=strict._integer(row.get('runs'),'runtime runs')
            require(count in (None,n),'Native runtime denominator differs')
            result[key][method]=dict(runs=count,**{field:strict._number(row.get(field),field,0) for field in
                ('wall_seconds_mean','wall_seconds_p50','wall_seconds_p95','wall_seconds_maximum','core_ms_mean')})
    return result


def _duplicates(value):
    value={} if value is None else strict._object(value,'duplicate check')
    require(value.get('scope','recipient_payload_ignoring_release_ids')=='recipient_payload_ignoring_release_ids','Unknown duplicate scope')
    require(value.get('expected_streams_per_pair',144)==144,'Duplicate denominator differs')
    raw=strict._object(value.get('by_pair',{}),'duplicate pair family')
    known={left+'__vs__'+right:(left,right) for left,right in DUPLICATE_PAIRS}
    require(set(raw)<=set(known),'Unregistered duplicate pair')
    projected={}
    for key,(left,right) in known.items():
        item=strict._object(raw.get(key,{}),'duplicate pair')
        require(item.get('left',left)==left and item.get('right',right)==right,'Duplicate pair identities differ')
        compared=strict._integer(item.get('compared_streams',0),'compared streams',nullable=False)
        equal=strict._integer(item.get('equal_streams',0),'equal streams',nullable=False)
        require(equal<=compared<=144,'Invalid duplicate count')
        all_equal=item.get('all_equal')
        require(all_equal is None or type(all_equal) is bool,'Duplicate all_equal must be boolean')
        require(all_equal is None or all_equal==(compared==144 and equal==144),'Duplicate equality claim differs from counts')
        projected[key]=dict(left=left,right=right,compared_streams=compared,equal_streams=equal,
                           all_equal=all_equal if compared==144 else None)
    status=strict._state(value.get('status','unavailable'))
    complete=status=='verified' and all(item['compared_streams']==144 for item in projected.values())
    return dict(status='verified' if complete else 'incomplete',scope='recipient_payload_ignoring_release_ids',
                expected_streams_per_pair=144,by_pair=projected)


def _contrasts(value,phase):
    value={} if value is None else strict._object(value,'paired contrasts')
    require(set(value)<={key for key,*_ in CONTRASTS},'Unregistered paired ablation contrast')
    require(phase!='utility' or not value,'Utility phase contains MIA contrasts')
    result={}
    for key,left,right,seed in CONTRASTS:
        raw=strict._object(value.get(key,{}),'paired contrast')
        require(raw.get('left',left)==left and raw.get('right',right)==right and raw.get('metric','ROC_AUC')=='ROC_AUC','OFF-minus-ON comparator changed')
        reps=strict._object(raw.get('representations',{}),'contrast representations');require(set(reps)<=set(REPRESENTATIONS),'Unknown representation')
        projected={}
        for representation in REPRESENTATIONS:
            entry=strict._object(reps.get(representation,{}),'paired estimate')
            if 'auc_difference' not in entry:
                projected[representation]=dict(status='not_evaluated' if phase=='utility' else 'unavailable');continue
            require(entry.get('confidence_level')==.95 and entry.get('seed')==seed and entry.get('replicates')==1000,'Paired bootstrap contract differs')
            n=strict._integer(entry.get('independent_groups'),'paired groups',nullable=False);require(2<=n<=32,'Invalid paired denominator')
            interval=entry.get('interval');require(isinstance(interval,(list,tuple)) and len(interval)==2,'Expected paired interval')
            bounds=[strict._number(item,'AUC bound',-1,1,nullable=False) for item in interval];require(bounds[0]<=bounds[1],'Reversed interval')
            projected[representation]=dict(status='evaluated',auc_difference=strict._number(entry['auc_difference'],'AUC difference',-1,1,nullable=False),
                interval=bounds,confidence_level=.95,independent_groups=n,replicates=1000)
        result[key]=dict(left=left,right=right,metric='ROC_AUC',direction='OFF minus ON',representations=projected)
    return result


def _complete_attack(value,feature_count=None):
    if not previous._complete_attack(value):return False
    calibration=value.get('calibration') or {};metrics=value.get('metrics') or {};cal=calibration.get('metrics') or {}
    if not (calibration.get('target_fpr')==.1 and calibration.get('negative_case_fpr_resolution')==1/16
            and calibration.get('threshold') is not None and calibration.get('threshold')==metrics.get('threshold')
            and cal.get('threshold')==calibration.get('threshold') and cal.get('positive_cases')==cal.get('negative_cases')==16
            and cal.get('fpr') is not None and cal['fpr']<=.1):return False
    if feature_count is None:return value.get('fit_diagnostics') is None
    fit=value.get('fit_diagnostics') or {}
    return (fit.get('converged') is True and fit.get('training_rows')==48 and fit.get('feature_count')==feature_count
            and type(fit.get('iterations')) is int and 1<=fit['iterations']<=500 and fit.get('training_objective') is not None)


def compact_report(report,*,input_sha256=None):
    report=strict._object(report,'private ablation report');schema=report.get('schema')
    require(schema in (INPUT_SCHEMA,UTILITY_INPUT_SCHEMA),'Unexpected ablation report schema')
    phase='utility' if schema==UTILITY_INPUT_SCHEMA else 'mia'
    require(report.get('source_validation_profile')==PROFILE,'Protected-unit profile differs')
    identity=report.get('ablation_id',report.get('evaluation_id'));require(isinstance(identity,str) and 0<len(identity)<=256,'Expected bounded study identity')
    _catalog(report.get('method_catalog'),report.get('auxiliary_method_catalog'))
    lineage=_lineage(report,phase);definition=_definition(report.get('aligned_query_definition'))
    assessment={} if phase=='utility' else strict._object(report.get('analysis'),'MIA analysis')
    if phase=='utility':
        require(report.get('mia_status')=='not_started' and not report.get('analysis') and not report.get('exploratory_contrasts'),'MIA must remain not started at utility stage')
    else:
        require(assessment.get('schema')=='ump.urban-privacy-analysis.v1' and report.get('original_primary_result_preserved') is True,'Original result preservation/schema missing')
    attacks=strict._object(assessment.get('attacks',{}),'attack family')
    utilities=strict._object(report.get('utility',{}) if phase=='utility' else assessment.get('utility',{}),'utility family')
    require(set(attacks)<=set(METHOD_IDS) and set(utilities)<=set(METHOD_IDS),'Auxiliary/unregistered method in headline estimates')
    methods=[]
    for base,label in BASE_METHODS:
        for mode,method in (('enabled',base),('exact_only',base+'_exact_only')):
            family=strict._object(attacks.get(method,{}),'attack representations');require(set(family)<=set(REPRESENTATIONS),'Unknown attack representation')
            worlds=strict._object(utilities.get(method,{}),'utility worlds');require(set(worlds)<={'IN','OUT'},'Unknown world')
            methods.append(dict(id=method,on_method_id=base,label=label,semantic_generalization=mode,
                origin='authenticated_historical_on' if mode=='enabled' else 'new_exact_only',
                utility={world:_utility(worlds.get(world,{})) for world in ('IN','OUT')},
                attacks={rep:strict._attack(family.get(rep)) if phase=='mia' else strict._attack({'status':'not_evaluated'}) for rep in REPRESENTATIONS}))
            if mode=='exact_only':_exact_only_consistency(methods[-1]['utility'])
    outcomes=_outcomes(report.get('group_outcomes',[]));audit=strict._object(report.get('source_split_audit',{}),'source split audit')
    duplicate=_duplicates(report.get('duplicate_check'))
    complete=(audit.get('status')=='verified' and duplicate['status']=='verified'
        and all(outcomes['recording_status_by_split'][split].get('verified',0)==n for split,n in GROUP_COUNTS.items())
        and all(row['statuses']=={'verified':144} for row in outcomes['method_world_status'].values())
        and all(m['utility'][world]['observed_recordings']==32 for m in methods for world in ('IN','OUT')))
    # Incomplete newly added query calculations must not masquerade as a complete
    # utility study even if the historical scalar metrics are already present.
    for method in methods:
        for world in ('IN','OUT'):
            means=method['utility'][world]['macro_means']
            for key in ('retained_fraction','full_input_J','published_policy_violations',
                        'aligned_semantic_queries.exact.summary.query_count','aligned_semantic_queries.estimate.summary.query_count'):
                complete=complete and means.get(key,{}).get('recordings')==32
            if means.get('published_policy_violations',{}).get('mean') not in (None,0):complete=False
    controls=strict._object(assessment.get('controls',{}),'controls');require(set(controls)<=set(CONTROLS),'Unknown control')
    projected_controls={name:strict._attack(controls.get(name)) for name in CONTROLS}
    checks=strict._object(assessment.get('negative_control_checks',{}),'control checks')
    positive=strict._object(assessment.get('positive_control_check',{}),'positive control')
    gate=assessment.get('interpretation_gate','not_evaluated');require(gate in ('controls_pass','diagnose_controls_before_interpreting_lower_attack_success','not_evaluated'),'Unknown interpretation gate')
    contrasts=_contrasts(report.get('exploratory_contrasts'),phase)
    original=strict._contrast(assessment.get('primary_contrast'))
    status='not_evaluated' if phase=='utility' else strict._state(assessment.get('status','missing'))
    mia_complete=(complete and all(_complete_attack(m['attacks'][rep],111 if rep=='semantic111' else 31) for m in methods for rep in REPRESENTATIONS)
        and all(_complete_attack(control,8 if name=='auxiliary_only' else 111 if name=='no_output' else None) for name,control in projected_controls.items())
        and previous._complete_contrasts(contrasts) and previous._complete_contrasts({'original':original})
        and gate=='controls_pass' and positive.get('status')=='pass'
        and all(strict._object(checks.get(name,{}),'negative control').get('status')=='pass' for name in ('prior_only','auxiliary_only','no_output')))
    if status=='complete' and not mia_complete:status='incomplete_or_diagnostic'
    return dict(schema=SCHEMA,phase=phase,study_design='exploratory_paired_semantic_action_ablation_reused_recordings',
        source_validation_profile=PROFILE,protected_unit='all_observed_contributions_of_one_operational_track_within_fixed_300s',
        horizon_ms=300000,utility_status='complete' if complete else 'incomplete',mia_status='not_started' if phase=='utility' else status,
        analysis_status=status,interpretation_gate=gate,methods=methods,
        auxiliary_methods=[dict(id=name,role='regional_composition_dependency_only') for name in AUXILIARY_IDS],
        source_and_execution=outcomes,source_quality=window._quality(report.get('source_quality')),
        source_split_audit_status=strict._state(audit.get('status','unavailable')),aligned_query_definition=definition,
        duplicate_check=duplicate,controls=projected_controls,exploratory_contrasts=contrasts,
        original_primary_contrast=original,negative_control_checks={name:strict._state(strict._object(checks.get(name,{}),'control').get('status','unavailable')) for name in ('prior_only','auxiliary_only','no_output')},
        positive_control_status=strict._state(positive.get('status','unavailable')),
        native_runtime=_runtime(report.get('native_execution_summary')),ablation_lineage=lineage,
        provenance=dict(private_report_sha256=strict._hash(input_sha256),ablation_id_sha256=hashlib.sha256(identity.encode()).hexdigest(),
            dataset_manifest_sha256=strict._hash(report.get('dataset_manifest_sha256')),source_split_audit_sha256=hashlib.sha256(canonical(audit)).hexdigest()),
        scope=list(SCOPE))


def _public(value):
    require(isinstance(value,dict) and value.get('schema')==SCHEMA,'Expected public ablation report');return value


def _fmt(value,scale=1):return strict._fmt(value,scale)


def _mean(method,world,key):return strict._mean(method['utility'][world],key)


def _metric(method,world,key,scale=1):
    item=method['utility'][world]['macro_means'].get(key,{})
    return _fmt(item.get('mean'),scale)+' (n='+str(item.get('recordings',0))+')'


def markdown(public):
    public=_public(public)
    lines=['# Paired semantic-generalization action ablation','',
        '**Exploratory reuse of the same recordings. Historical ON evidence remains unchanged.**','',
        f"Phase: **{public['phase']}**. Utility: **{public['utility_status']}**. MIA: **{public['mia_status']}**. Gate: **{public['interpretation_gate']}**.",'',
        'Seven headline ON/OFF pairs use identical observations and hard policies: 72 recordings (24 TRAIN / 16 CAL / 32 TEST), 2016 headline method/world rows. Three OFF fixed-window dependencies add 432 rows; they are not extra headline methods.', '',
        '## TEST utility (IN world; every metric retains its available N)','',
        '| Method | Generalization | Retained (%) | J (%) | Retained semantic loss (%) | Logical delay (ms) | Aligned exact coverage (%) | Aligned exact count MAE | Aligned estimate coverage (%) |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for m in public['methods']:
        vals=[_metric(m,'IN',key,scale) for key,scale in (('retained_fraction',100),('full_input_J',100),('retained_semantic_loss',100),
            ('logical_seal_delay_ms.mean',1),('aligned_semantic_queries.exact.summary.query_coverage',100),
            ('aligned_semantic_queries.exact.summary.answered_only_mae',1),('aligned_semantic_queries.estimate.summary.query_coverage',100))]
        lines.append('| '+' | '.join([m['label'],'ON' if m['semantic_generalization']=='enabled' else 'OFF (exact only)',*vals])+' |')
    lines+=['','OFF zero retained semantic loss does not mean zero full-input loss. J includes omission plus taxonomy loss; lower is better. Aligned errors count observation contributions, not instantaneous occupancy. Unknown is not zero. Full IN/OUT, per-class, per-region and per-taxonomy-node values with available Ns are in summary.json. Existing 10 m / 1 s occupancy queries remain separate.','',
        '## Source-class and regional omission (Fixed 20 m / 0.4 s, IN world)','',
        '| Input cohort | ON retained (%) | OFF retained (%) | ON omitted contributions | OFF omitted contributions |','|---|---:|---:|---:|---:|']
    selected={m['id']:m for m in public['methods']}
    for family,cohorts in (('by_source_type',SOURCE_CLASSES),('by_source_point_region',REGIONS)):
        for cohort in cohorts:
            stem='source_accounting.'+family+'.'+cohort+'.'
            lines.append('| '+' | '.join([cohort,_metric(selected['fixed20_400ms'],'IN',stem+'retained_fraction',100),
                _metric(selected['fixed20_400ms_exact_only'],'IN',stem+'retained_fraction',100),
                _metric(selected['fixed20_400ms'],'IN',stem+'unpublished_observation_contributions'),
                _metric(selected['fixed20_400ms_exact_only'],'IN',stem+'unpublished_observation_contributions')])+' |')
    lines+=['','## Native runtime boundaries','', '| Method | Generalization | TEST native runs | Mean wall (s) | p95 wall (s) | Core processing (s) |','|---|---|---:|---:|---:|---:|']
    for m in public['methods']:
        r=public['native_runtime']['by_method_test'].get(m['id'],{})
        lines.append('| '+' | '.join([m['label'],'ON' if m['semantic_generalization']=='enabled' else 'OFF',
            str(r.get('runs')) if r.get('runs') is not None else 'NA',_fmt(r.get('wall_seconds_mean')),
            _fmt(r.get('wall_seconds_p95')),_fmt(_mean(m,'IN','core_processing_ms'),.001)])+' |')
    lines+=['',public['native_runtime']['scope'],'','## Measured OFF adaptive transcript duplicates','',
        'Only release IDs are excluded from comparison; all remaining recipient content/order is preserved. Equality here is not a universal algorithm-equivalence claim.','',
        '| Left | Right | Compared streams | Equal streams | All 144 equal? |','|---|---|---:|---:|---|']
    for item in public['duplicate_check']['by_pair'].values():
        lines.append('| '+' | '.join([item['left'],item['right'],str(item['compared_streams']),str(item['equal_streams']),
            'unknown' if item['all_equal'] is None else str(item['all_equal']).lower()])+' |')
    if public['phase']=='utility':
        lines+=['','## MIA pending','','MIA has not started for the OFF methods. Historical ON attack scores are omitted from this utility-stage report. Utility and support compliance do not establish a privacy gain.']
    else:
        lines+=['','## MIA: fixed models, CAL thresholds, 32 TEST pairs per method','',
            '| Method | Generalization | Full111 AUC | Scalar31 AUC | Full111 TPR [95% CI] | Full111 FPR [95% CI] | Status |','|---|---|---:|---:|---:|---:|---|']
        for m in public['methods']:
            full=m['attacks']['semantic111'];scalar=m['attacks']['scalar31']
            lines.append('| '+' | '.join([m['label'],'ON' if m['semantic_generalization']=='enabled' else 'OFF',
                _fmt((full['metrics'] or {}).get('roc_auc')),_fmt((scalar['metrics'] or {}).get('roc_auc')),
                strict._rate(full['metrics'],'tpr'),strict._rate(full['metrics'],'fpr'),full['status']])+' |')
        lines+=['','### Paired AUC changes: OFF minus ON','',
            '| Pair | Representation | Difference | Paired 95% interval | Independent groups |','|---|---|---:|---|---:|']
        for key,label in BASE_METHODS:
            for rep,item in public['exploratory_contrasts'][key+'_exact_only_vs_enabled']['representations'].items():
                interval=item.get('interval');bounds='NA' if interval is None else '['+', '.join(_fmt(v) for v in interval)+']'
                lines.append('| '+' | '.join([label,rep,_fmt(item.get('auc_difference')),bounds,str(item.get('independent_groups','NA'))])+' |')
        lines+=['','Lower AUC is favorable for this attack; a change may reflect omitted information. Every interval is exploratory and non-simultaneous. An interval crossing zero establishes neither superiority nor equivalence. The CAL 10% FPR cap is not a TEST guarantee. Full111/Scalar31 is not the ON/OFF action comparison.']
    lines+=['','## Interpretation scope','',*('- '+line for line in public['scope']),'','## Provenance','',
        'Original diagnostic-repair history and immutable historical bindings are retained in summary.json and ablation-lineage-public.json. No source IDs, seeds, model parameters, features or individual scores are exported.']
    return '\n'.join(lines)+'\n'


def figures(public,output,*,synthetic=False):
    public=_public(public);output=Path(output);require(output.is_dir(),'Figure directory must exist')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    generated=[];labels=[label for _,label in BASE_METHODS];ys=list(range(7));by_id={m['id']:m for m in public['methods']}
    caption=('SYNTHETIC layout fixture; not experimental evidence.\n' if synthetic else '')+(
        'Exploratory reused-source ablation; TEST N=32 recordings, each metric has its own N. Identical hard policies.\n'
        'Conditional detail/error requires coverage; logical/offline timing is not a live-delivery or per-step guarantee.')
    legend=[Line2D([],[],ls='',marker='o',color='#2869a1',label='ON: generalization allowed'),
            Line2D([],[],ls='',marker='x',color='#c66a16',label='OFF: exact input categories only')]
    def save(fig,stem,bottom=.16):
        fig.text(.01,.01,caption,fontsize=8);fig.tight_layout(rect=(0,bottom,1,.94))
        for extension in ('png','svg'):
            p=output/(stem+'.'+extension);require(not p.exists(),'Refuse figure overwrite');fig.savefig(p,dpi=160);generated.append(p.name)
        plt.close(fig)
    def axis(ax):
        ax.set_yticks(ys,labels);ax.set_ylim(6.6,-.6);ax.grid(axis='x',alpha=.18)
    def compare(axes,descriptors):
        for ax,(key,scale,title) in zip(axes,descriptors):
            for i,(base,_) in enumerate(BASE_METHODS):
                for suffix,offset,color,marker in (('',-.1,'#2869a1','o'),('_exact_only',.1,'#c66a16','x')):
                    value=_mean(by_id[base+suffix],'IN',key)
                    if value is None:ax.text(.01,i+offset,'NA',transform=ax.get_yaxis_transform(),fontsize=7)
                    else:ax.scatter(value*scale,i+offset,c=color,marker=marker,s=32,clip_on=False)
            axis(ax);ax.set(title=title);ax.set_xlim(left=0)
        axes[0].legend(handles=legend,loc='upper left',bbox_to_anchor=(0,-.12),fontsize=8)
    fig,axes=plt.subplots(1,4,figsize=(18,6.2),sharey=True)
    compare(axes,(('retained_fraction',100,'Retained input (%)'),('full_input_J',100,'Full-input J (%)'),
        ('retained_semantic_loss',100,'Retained taxonomy loss (%)'),('logical_seal_delay_ms.mean',1,'Logical delay (ms)')))
    fig.suptitle('Semantic-action ablation: TEST utility, IN world');save(fig,'urban-semantic-ablation-utility')
    fig,axes=plt.subplots(1,3,figsize=(16,6.2),sharey=True)
    compare(axes,(('aligned_semantic_queries.exact.summary.query_coverage',100,'Aligned exact query coverage (%)'),
        ('aligned_semantic_queries.exact.summary.answered_only_mae',1,'Conditional exact count MAE'),
        ('aligned_semantic_queries.estimate.summary.query_coverage',100,'Aligned estimated coverage (%)')))
    fig.suptitle('20 m / 400 ms category queries: observation contributions');save(fig,'urban-semantic-ablation-queries')
    if public['phase']=='utility':return generated
    fig,axes=plt.subplots(1,2,figsize=(14,6.2),sharey=True)
    for ax,rep in zip(axes,REPRESENTATIONS):
        for i,(base,_) in enumerate(BASE_METHODS):
            for suffix,offset,color,marker in (('',-.1,'#2869a1','o'),('_exact_only',.1,'#c66a16','x')):
                metric=by_id[base+suffix]['attacks'][rep]['metrics']
                if metric is not None:ax.scatter(metric['roc_auc'],i+offset,c=color,marker=marker,s=32)
        axis(ax);ax.axvline(.5,color='#777',ls='--',lw=.8);ax.set(title=('Full111' if rep=='semantic111' else 'Scalar31')+' AUC',xlabel='ROC-AUC; lower favors privacy for this attack',xlim=(0,1))
    axes[0].legend(handles=legend,loc='upper left',bbox_to_anchor=(0,-.14),fontsize=8)
    fig.suptitle('MIA point estimates: fixed TRAIN/CAL models');save(fig,'urban-semantic-ablation-attack')
    fig,ax=plt.subplots(figsize=(12,6.4))
    for i,(base,_) in enumerate(BASE_METHODS):
        for rep,offset,color,marker in (('semantic111',-.1,'#2869a1','o'),('scalar31',.1,'#c66a16','x')):
            item=public['exploratory_contrasts'][base+'_exact_only_vs_enabled']['representations'][rep]
            if item['status']=='evaluated':
                lo,hi=item['interval'];ax.plot([lo,hi],[i+offset,i+offset],color=color);ax.scatter(item['auc_difference'],i+offset,c=color,marker=marker,s=32)
    axis(ax);ax.axvline(0,color='#777',ls='--',lw=.8);ax.set(xlabel='OFF minus ON ROC-AUC; exploratory paired 95% interval')
    ax.legend(handles=[Line2D([],[],marker='o',color='#2869a1',label='Full111'),Line2D([],[],marker='x',color='#c66a16',label='Scalar31')],
        loc='upper center',bbox_to_anchor=(.5,-.16),ncol=2,fontsize=8)
    fig.suptitle('Paired semantic-action AUC contrasts');save(fig,'urban-semantic-ablation-contrasts',bottom=.22)
    return generated


def export(report_path,output,*,make_figures=True):
    report_path=Path(report_path);output=Path(output)
    require(report_path.is_file() and report_path.stat().st_size<=2*1024**3,'Expected bounded private report')
    require(not output.exists(),'Refuse artifact directory overwrite');output.mkdir(parents=True)
    public=compact_report(json.loads(report_path.read_text()),input_sha256=sha(report_path))
    for name,value in (('summary.json',public),('ablation-lineage-public.json',public['ablation_lineage'])):
        with (output/name).open('x') as stream:json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    with (output/'report.md').open('x') as stream:stream.write(markdown(public))
    names=figures(public,output) if make_figures else []
    paths=[output/name for name in ('summary.json','ablation-lineage-public.json','report.md',*names)]
    with (output/'artifact-receipt.json').open('x') as stream:
        json.dump(dict(schema=ARTIFACT_SCHEMA,phase=public['phase'],source_sha256=sha(report_path),
            reporter_code_sha256=sha(__file__),query_helper_code_sha256=sha(queries.__file__),
            files={path.name:dict(sha256=sha(path),bytes=path.stat().st_size) for path in paths}),stream,sort_keys=True,indent=2);stream.write('\n')
    return public


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--no-figures',action='store_true');args=parser.parse_args(argv)
    public=export(args.report,args.output,make_figures=not args.no_figures)
    print(json.dumps({key:public[key] for key in ('schema','phase','utility_status','mia_status')}))


if __name__=='__main__':main()
