#!/usr/bin/env python3
"""Derive a policy-only static regional schedule from verified fixed-grid runs.

This is an aggregate utility composition, not a native replay result or an
implemented online scheduler. Each fixed cell receives its longest admissible
predeclared window using public footprint constraints before observations are
inspected. Only matching, previously audited native cell records are composed.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
import math
from pathlib import Path

from oracle import decode_cell
from semantic_suppression_audit import Catalog, SourceIndex, close, effective

WINDOWS=(400,1000,2000,4000)
SOURCES=('mixed','pedestrians')
POLICIES=('control','local400')
SIDES=(10,20)
PUBLIC_COVERAGE=dict(x=0,y=0,width=80,height=80,leaf_depth=6)
MAX_BYTES=2*1024**3


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def read(path):
    path=Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=MAX_BYTES,
        'Require a bounded regular artifact: '+str(path))
    with path.open(encoding='utf-8') as stream:return json.load(stream)


def artifact(root,name):
    require(isinstance(name,str) and name and not Path(name).is_absolute()
        and all(part not in ('','.','..') for part in name.split('/')) and '\\' not in name,
        'Artifact name must be canonical and relative')
    current=root
    for part in name.split('/'):
        current=current/part;require(not current.is_symlink(),'Symbolic artifacts are unsupported')
    require(current.is_file() and current.resolve().is_relative_to(root),'Missing or escaping artifact: '+name)
    return current


def hard_policy(config):
    value=copy.deepcopy(config)
    value.pop('application_id',None)
    value['policy_tree'].pop('id',None)
    value['policy_tree'].pop('execution',None)
    return value


def off_only(config):
    groups=[config['policy_tree']['root']]
    for region in config.get('policy_regions',[]):
        groups.extend((region.get('type_requirements',{}),region.get('requirements',{})))
    require(all(group.get('semantic_suppression_fraction',{}).get('max',0)==0 for group in groups),
        'Static composition requires selective suppression OFF')


def admissible(value,bounds):
    return bounds.get('min',-math.inf)<=value<=bounds.get('max',math.inf)


def plan_schedule(coverage,config,side):
    """Use only public geometry and hard policy; no input counts or motion."""
    require(type(side) is int and side in SIDES,'Choose the predeclared 10 m or 20 m grid')
    ratio=coverage['width']/side
    require(coverage['width']==coverage['height'] and ratio>=2 and math.log2(ratio).is_integer(),
        'Fixed side does not match the square quadtree')
    depth=int(math.log2(ratio));require(depth<=coverage['leaf_depth'],'Fixed grid exceeds source depth')
    off_only(config);cells={}
    for identity in range(3*4**depth,4*4**depth):
        geometry=decode_cell(coverage,identity,depth);bounds,touched=effective(config,geometry)
        choices=[]
        for window in WINDOWS:
            values={'cell_side_m':geometry['width'],'cell_area_m2':geometry['width']*geometry['height'],
                'window_duration_ms':window,'age_at_evaluation_ms':window,'post_window_delay_ms':0}
            if all(metric not in bounds or admissible(value,bounds[metric]) for metric,value in values.items()):
                choices.append(window)
        require(choices,'No admissible predeclared static schedule for cell '+str(identity))
        cells[identity]=dict(geometry=geometry,window_ms=max(choices),intersected_regions=touched,
            effective_requirements=bounds)
    return dict(depth=depth,side_m=side,cells=cells,
        cell_window_ms={str(identity):row['window_ms'] for identity,row in cells.items()},
        selection_scope='Longest admissible predeclared window from footprint size, duration, age and post-window delay bounds; fixed before reading observations.')


def groups_for(data,plan):
    """Assign each source contribution to one static cell/half-open interval."""
    groups=defaultdict(list);seen=set();end=data['end_ms'];coverage=data['coverage']
    require(type(end) is int and end>0,'Invalid source horizon')
    shift=2*(coverage['leaf_depth']-plan['depth']);previous=0
    period=data['sampling_period_ms']
    require(type(period) is int and period>0,'Invalid source sampling period')
    for batch in data['batches']:
        timestamp=batch['observed_at_ms']
        require(type(timestamp) is int and previous<timestamp<end and timestamp%period==0,
            'Source timestamps must increase on the sensor cadence')
        previous=timestamp
        require(batch['status'] in ('measured','unavailable')
            and (batch['status']=='measured' or not batch['observations']),'Invalid source coverage status')
        for row in batch['observations']:
            require(isinstance(row['id'],str) and row['id'] and isinstance(row['type'],str),'Invalid source identity/type')
            key=(timestamp,row['id']);require(key not in seen,'Duplicate source contribution');seen.add(key)
            leaf=decode_cell(coverage,row['cell_id'],coverage['leaf_depth'])
            require(all(type(row[k]) in (int,float) and math.isfinite(row[k]) for k in ('x','y'))
                and leaf['x']<=row['x']<leaf['x']+leaf['width']
                and leaf['y']<=row['y']<leaf['y']+leaf['height'],'Source position disagrees with encoded leaf')
            identity=row['cell_id']>>shift;require(identity in plan['cells'],'Source lies outside static grid')
            window=plan['cells'][identity]['window_ms'];start=(timestamp//window)*window
            groups[(identity,start,min(start+window,end))].append((timestamp,row))
    scheduled=sum((end+row['window_ms']-1)//row['window_ms'] for row in plan['cells'].values())
    require(len(groups)<=scheduled,'More nonempty groups than the mathematical static partition')
    return dict(groups),len(seen),scheduled


def _equal_payload(private,public):
    keys=('cell_id','depth','x','y','width','height','observation_contributions',
        'distinct_road_users','mean_sample_occupancy','semantic')
    return all(private.get(key)==public.get(key) for key in keys)


def native_records(data,plan,result,window):
    """Match actual private/public cells before selecting schedule-owned records."""
    params=result.get('parameters',{})
    require(params.get('fixed_depth')==plan['depth'] and params.get('window_ms')==window
        and params.get('coordination')=='common_window','Native fixed schedule parameters differ')
    source=result.get('source',{})
    require(all(source.get(key)==data[key] for key in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms')),
        'Native source identity/geometry/horizon differs')
    public={}
    for release in result['releases']:
        for cell in release['cells']:
            key=(cell['cell_id'],release['start_ms'],release['end_ms'])
            require(key not in public,'Duplicate native public cell interval')
            public[key]=(cell,release['sealed_at_ms'])
    private=set();selected=set();composed={};seen_intervals=set()
    horizon=data['end_ms']
    expected_intervals={(start,min(start+window,horizon)) for start in range(0,horizon,window)}
    for diagnostic in result['windows']:
        start,end=diagnostic['start_ms'],diagnostic['end_ms'];interval=(start,end)
        require(interval in expected_intervals and interval not in seen_intervals,'Native global intervals are not an exact fixed partition')
        seen_intervals.add(interval)
        for cell in diagnostic['cells']:
            identity=cell['cell_id'];key=(identity,start,end)
            require(identity in plan['cells'] and cell['depth']==plan['depth'] and key not in private,
                'Duplicate, out-of-grid or wrong-depth private cell')
            private.add(key);require(type(cell.get('selected')) is bool,'Private selected flag is not Boolean')
            if cell['selected']:
                selected.add(key);require(key in public,'Selected private cell has no native public cell')
                released,sealed=public[key]
                require(_equal_payload(cell,released) and sealed==diagnostic['evaluated_at_ms'],
                    'Private and immutable native public payload/evaluation time differ')
            else:require(key not in public,'Failed private cell was published')
            if plan['cells'][identity]['window_ms']==window:
                composed[key]=dict(cell=cell,evaluated_at_ms=diagnostic['evaluated_at_ms'],
                    sealed_at_ms=public[key][1] if key in public else None)
    require(seen_intervals==expected_intervals,'Native fixed schedule omits a global interval')
    require(selected==set(public),'Native public cell has no selected private record')
    return composed


def check_group(data,config,catalog,index,plan,key,rows,record):
    identity,start,end=key;cell=record['cell'];geometry=plan['cells'][identity]['geometry']
    require(all(close(cell.get(k),v) for k,v in geometry.items()),'Composed cell geometry disagrees with ID')
    require(not cell.get('semantic_suppression') and not cell.get('retained_counts'),'OFF record contains selective suppression')
    identities=catalog.source(rows);expected,measured=index.samples(start,end)
    require(len(rows)==cell['observation_contributions'] and len(identities)==cell['distinct_road_users'],
        'Composed observation/identity support differs from original source')
    occupancy=len(rows)/measured if measured else None
    require(close(cell['mean_sample_occupancy'],occupancy),'Composed occupancy differs from measured samples')
    semantic=cell['semantic']
    require(semantic.get('schema')=='ump.semantic-release.v1'
        and semantic.get('taxonomy_id')==catalog.taxonomy['id']
        and semantic.get('taxonomy_version')==catalog.taxonomy['version'],'Composed semantic catalog differs')
    bins=semantic['categories'];categories=[item['category_id'] for item in bins]
    require(categories and len(categories)==len(set(categories)) and all(c in catalog.nodes for c in categories),
        'Invalid composed semantic categories')
    require(not any(a!=b and a in catalog.chains[b] for a in categories for b in categories),'Composed semantic cut overlaps')
    require(all(sum(category in catalog.chains[catalog.labels[row['type']]] for category in categories)==1
        for _,row in rows),'Composed semantic cut omits or double-represents source')
    supports=[];weighted=0;row_losses={}
    for item in bins:
        category=item['category_id'];matching=[(t,row) for t,row in rows if category in catalog.chains[catalog.labels[row['type']]]]
        support=len({row['id'] for _,row in matching})
        require(support>0 and item['observation_contributions']==len(matching) and item['distinct_contributors']==support,
            'Composed semantic bin support differs from original source')
        supports.append(support);loss=catalog.nodes[category]['loss'];weighted+=len(matching)*loss
        for timestamp,row in matching:row_losses[(timestamp,row['id'])]=loss
    evaluated=record['evaluated_at_ms']
    require(type(evaluated) is int and evaluated>=end,'Invalid composed evaluation time')
    values=dict(observation_contributions=len(rows),distinct_contributors=len(identities),mean_sample_occupancy=occupancy,
        cell_side_m=geometry['width'],cell_area_m2=geometry['width']*geometry['height'],
        window_duration_ms=end-start,age_at_evaluation_ms=evaluated-start,post_window_delay_ms=evaluated-end,
        measured_sample_fraction=measured/expected if expected else None,
        min_category_distinct_contributors=min(supports),semantic_max_loss=max(catalog.nodes[c]['loss'] for c in categories),
        semantic_mean_loss=weighted/len(rows),semantic_suppression_fraction=0,occupancy_mae=None)
    for metric in ('min_category_distinct_contributors','semantic_max_loss','semantic_mean_loss'):
        require(close(semantic.get(metric),values[metric]),'Composed semantic summary differs')
    bounds,_=effective(config,geometry)
    require(bounds==plan['cells'][identity]['effective_requirements'],'Policy changed after schedule declaration')
    checks=[]
    for metric,limits in bounds.items():
        require(metric in values,'Unsupported composed hard metric: '+metric)
        value=values[metric];checks.append(value is not None and admissible(value,limits))
    coverage_complete=expected>0 and measured==expected
    passes=coverage_complete and all(checks)
    require(cell['selected']==passes,'Composed selection differs from independently recomputed policy/coverage')
    require(cell.get('assessment_status')==('pass' if all(checks) else 'fail')
        or not passes and cell.get('assessment_status')=='unavailable','Composed assessment status differs')
    for metric,value in cell.get('metrics',{}).items():
        require(metric in values and (value is None and values[metric] is None or close(value,values[metric])),
            'Composed diagnostic metric differs: '+metric)
    diagnostics=cell.get('checks',[])
    require(len(diagnostics)==len(bounds) and len({check['metric'] for check in diagnostics})==len(bounds),
        'Composed diagnostic omits/duplicates policy checks')
    for check in diagnostics:
        metric=check['metric'];require(metric in bounds and all(check.get(k)==bounds[metric].get(k) for k in ('min','max')),
            'Composed diagnostic bound differs')
        observed=values[metric]
        require(observed is None and check.get('observed') is None or close(check.get('observed'),observed),
            'Composed diagnostic observation differs')
        expected_status='unavailable' if observed is None else 'pass' if admissible(observed,bounds[metric]) else 'fail'
        require(check.get('status')==expected_status,'Composed diagnostic check status differs')
    return passes,weighted,row_losses


def delay_stats(delays):
    count=sum(delays.values())
    def quantile(fraction):
        target=math.ceil(count*fraction);seen=0
        for value,n in sorted(delays.items()):
            seen+=n
            if seen>=target:return value
        return None
    return dict(mean=sum(value*n for value,n in delays.items())/count if count else None,
        p50=quantile(.5),p95=quantile(.95),p99=quantile(.99),maximum=max(delays) if delays else None)


def cohort_rows(groups):
    return {name:dict(input_observation_contributions=count[0],retained_observation_contributions=count[1],
        unpublished_observation_contributions=count[0]-count[1],retained_fraction=count[1]/count[0] if count[0] else None)
        for name,count in sorted(groups.items())}


def compose(data,config,plan,results):
    """Independently reconstruct every scheduled nonempty source group once."""
    require(set(results)==set(WINDOWS),'All four predeclared native fixed schedules are required')
    require(plan==plan_schedule(data['coverage'],config,plan['side_m']),'Schedule was not derived solely from the policy')
    groups,total,scheduled=groups_for(data,plan);records={}
    for window in WINDOWS:
        selected=native_records(data,plan,results[window],window)
        require(not set(selected)&set(records),'Composed private scope overlaps');records.update(selected)
    require(set(records)==set(groups),'A nonempty source group lacks its chosen native private record, or a record has no source')
    catalog=Catalog(config);index=SourceIndex(data);retained=0;loss=0.;side_sum=0.;window_sum=0.;age_sum=0.
    exact=0;delays=Counter();by_type={};by_region={identity:[0,0] for identity in config['policy_tree']['regions']}
    by_region['outside_policy_regions']=[0,0]
    regions={r['id']:r for r in config.get('policy_regions',[])};published=0;category_counts=Counter();cell_sizes=Counter();spatial_ids=set()
    for key,rows in groups.items():
        passing,weighted,row_losses=check_group(data,config,catalog,index,plan,key,rows,records[key])
        identity,start,end=key;geometry=plan['cells'][identity]['geometry']
        if passing:
            retained+=len(rows);loss+=weighted;published+=1;spatial_ids.add(identity)
            side_sum+=len(rows)*geometry['width'];window_sum+=len(rows)*(end-start)
            age_sum+=len(rows)*(records[key]['sealed_at_ms']-start);cell_sizes[str(geometry['width'])]+=1
            for item in records[key]['cell']['semantic']['categories']:
                category_counts[item['category_id']]+=item['observation_contributions']
        for timestamp,row in rows:
            kind=by_type.setdefault(row['type'],[0,0]);kind[0]+=1;kind[1]+=passing
            touched=[identity for identity in config['policy_tree']['regions']
                if regions[identity]['x']<=row['x']<regions[identity]['x']+regions[identity]['width']
                and regions[identity]['y']<=row['y']<regions[identity]['y']+regions[identity]['height']]
            for identity in touched or ['outside_policy_regions']:
                by_region[identity][0]+=1;by_region[identity][1]+=passing
            if passing:
                delay=records[key]['sealed_at_ms']-timestamp;require(delay>=0,'Composed publication predates source')
                delays[delay]+=1;exact+=row_losses[(timestamp,row['id'])]==0
    require(retained==sum(delays.values()) and total==sum(len(rows) for rows in groups.values()),'Composed input conservation differs')
    return dict(input_observation_contributions=total,retained_observation_contributions=retained,
        unpublished_observation_contributions=total-retained,retained_fraction=retained/total if total else None,
        full_input_semantic_distortion=(total-retained+loss)/total if total else None,
        observation_weighted_semantic_loss=loss/retained if retained else None,
        observation_weighted_cell_side_m=side_sum/retained if retained else None,
        observation_weighted_interval_duration_ms=window_sum/retained if retained else None,
        observation_weighted_age_at_release_ms=age_sum/retained if retained else None,
        exact_subtype_observation_contributions=exact,exact_subtype_fraction_of_input=exact/total if total else None,
        exact_subtype_fraction_of_retained=exact/retained if retained else None,
        published_category_observations=dict(sorted(category_counts.items())),published_cell_sizes=dict(sorted(cell_sizes.items())),
        published_cell_windows=published,unique_published_spatial_ids=len(spatial_ids),core_processing_ms=None,
        source_accounting=dict(input_observations=total,retained_observations=retained,
            selectively_suppressed_observations=0,whole_footprint_suppressed_observations=total-retained,
            by_source_type=cohort_rows(by_type),by_source_point_region=cohort_rows(by_region),
            observation_to_release_delay_ms=delay_stats(delays),
            region_scope='Nonexclusive half-open source-point cohorts; hard constraints use whole-cell positive-area intersections.'),
        partition_audit=dict(status='verified',scheduled_cell_intervals=scheduled,nonempty_cell_intervals=len(groups),
            empty_cell_intervals=scheduled-len(groups),input_assigned_once=total,
            empty_scope='Every fixed cell is partitioned by [k*w,min((k+1)*w,horizon)); empty groups have zero source and require no native cell record.'),
        published_policy_violations=0)


def recursively_equal(before,after,path=''):
    if isinstance(before,dict) and isinstance(after,dict):
        require(set(before)==set(after),'Positive control keys differ: '+path)
        for key in before:recursively_equal(before[key],after[key],path+'/'+str(key))
    elif type(before) in (int,float) and type(after) in (int,float):
        require(close(before,after),'Positive control numerical value differs: '+path)
    else:require(before==after,'Positive control differs: '+path)


def verify_control(stats,native_stats):
    keys=('input_observation_contributions','retained_observation_contributions','retained_fraction',
        'full_input_semantic_distortion','observation_weighted_semantic_loss','observation_weighted_cell_side_m',
        'observation_weighted_interval_duration_ms','observation_weighted_age_at_release_ms',
        'exact_subtype_observation_contributions','published_category_observations','published_cell_windows')
    for key in keys:recursively_equal(stats[key],native_stats[key],key)
    for key in ('by_source_type','by_source_point_region','observation_to_release_delay_ms'):
        recursively_equal(stats['source_accounting'][key],native_stats['source_accounting'][key],key)


def derive(study,output):
    root=Path(study);require(not root.is_symlink(),'Study root cannot be symbolic');root=root.resolve(strict=True)
    output=Path(output);require(not output.exists() and not output.is_symlink(),'Choose a fresh static schedule output')
    output=output.resolve();require(not output.is_relative_to(root) and not root.is_relative_to(output),'Output must be separate from source study')
    summary_path=artifact(root,'summary.json');protocol_path=artifact(root,'protocol.json')
    summary=read(summary_path);protocol=read(protocol_path);summary_sha=sha(summary_path);protocol_sha=sha(protocol_path)
    require(summary.get('schema')=='ump.temporal-region-study.v1' and summary.get('status')=='verified'
        and summary.get('completion_scope')=='all_44_predeclared_cases'
        and summary.get('executed_case_count')==summary.get('planned_case_count')==44,
        'Require the full verified 44-case temporal-region study')
    require(summary.get('protocol')==protocol and summary.get('protocol_sha256')==protocol_sha,'Study protocol receipt differs')
    binary_path=artifact(root,'provenance/AggregationReplay')
    binary_sha=sha(binary_path)
    require(binary_sha==protocol.get('native_binary_sha256'),'Source native binary receipt differs')
    expected_cases={f'{source}_{policy}_{method}' for source in SOURCES for policy in POLICIES
        for method in [*(f'adaptive_{mode}' for mode in ('temporal_first','spatial_first','semantic_first')),
            *(f'fixed_{side}m_{window}ms' for side in SIDES for window in WINDOWS)]}
    require(set(summary.get('cases',{}))==expected_cases,'Study does not contain the complete declared case matrix')
    receipts={};configs={};plans={};cohort_policies={}
    # Freeze the entire policy-only schedule before loading any observation file.
    for source in SOURCES:
        for policy in POLICIES:
            for side in SIDES:
                key=f'{source}_{policy}_static_{side}m';cases={};canonical=None
                for window in WINDOWS:
                    identifier=f'{source}_{policy}_fixed_{side}m_{window}ms';case=summary['cases'][identifier]
                    checked=case.get('independent_audit',{})
                    require(checked.get('status')=='verified' and checked.get('scalar_valid') is True
                        and checked.get('published_policy_violations')==0,'Native source case is not independently verified: '+identifier)
                    config_path=artifact(root,identifier+'-policy.json');result_path=artifact(root,identifier+'.json')
                    require(sha(config_path)==case['config_sha256'] and sha(result_path)==case['result_sha256'],
                        'Native configuration/result receipt differs: '+identifier)
                    config=read(config_path);off_only(config)
                    require(canonical is None or hard_policy(config)==hard_policy(canonical),'Fixed native cases differ in hard policy')
                    canonical=config
                    cohort=(source,policy)
                    require(cohort not in cohort_policies or hard_policy(config)==cohort_policies[cohort],
                        'Fixed grids differ in hard policy')
                    cohort_policies[cohort]=hard_policy(config)
                    cases[window]=dict(id=identifier,result_path=result_path,config_sha256=case['config_sha256'],
                        result_sha256=case['result_sha256'])
                # Public geometry is fixed by this experiment, independently
                # of any motion/outcome file; verified against every input later.
                plans[key]=plan_schedule(PUBLIC_COVERAGE,canonical,side);configs[key]=canonical;receipts[key]=cases
    output.parent.mkdir(parents=True,exist_ok=True);output.mkdir(mode=0o700)
    declaration=dict(schema='ump.static-regional-schedule-protocol.v1',source_summary_sha256=summary_sha,
        source_protocol_sha256=protocol_sha,source_native_binary_sha256=binary_sha,
        windows_ms=list(WINDOWS),public_coverage=PUBLIC_COVERAGE,
        implementation_sha256={name:sha(Path(__file__).with_name(name))
            for name in ('static_regional_schedule.py','oracle.py','semantic_suppression_audit.py')},
        schedules={key:{name:copy.deepcopy(value) for name,value in plan.items() if name!='cells'} for key,plan in plans.items()},
        source_native_cases={key:{str(window):{name:value for name,value in receipt.items() if name!='result_path'}
            for window,receipt in cases.items()} for key,cases in receipts.items()},
        runtime_scope='Derived utility composition only. No online scheduler was implemented or timed; runtime is null.',
        selection_scope='Grid fixed at 10m or 20m; per-cell longest admissible window uses only public whole-footprint constraints, before reading observations.',
        source_scope='All unchanged source observations; no generated motion, individual IDs or movement positions are exported.')
    (output/'protocol.json').write_text(json.dumps(declaration,indent=2,sort_keys=True,allow_nan=False)+'\n')
    result=dict(schema='ump.static-regional-schedule.v1',status='running',protocol=declaration,
        protocol_sha256=sha(output/'protocol.json'),cases={})
    for source in SOURCES:
        observations_path=artifact(root,source+'-observations.json');observation_sha=sha(observations_path)
        require(observation_sha==protocol['sources'][source]['observations_sha256'],'Source observation receipt differs')
        data=read(observations_path)
        require(data['coverage']==PUBLIC_COVERAGE,'Source geometry differs from the predeclared public domain')
        for policy in POLICIES:
            for side in SIDES:
                key=f'{source}_{policy}_static_{side}m';native={}
                for window,receipt in receipts[key].items():
                    require(sha(receipt['result_path'])==receipt['result_sha256'],'Native result changed during composition')
                    native[window]=read(receipt['result_path'])
                stats=compose(data,configs[key],plans[key],native)
                control_verified=False
                if policy=='control':
                    require(set(plans[key]['cell_window_ms'].values())=={4000},'Control is not a uniform 4s schedule')
                    verify_control(stats,summary['cases'][f'{source}_{policy}_fixed_{side}m_4000ms']['stats']);control_verified=True
                result['cases'][key]=dict(source=source,policy=policy,side_m=side,method=f'static_regional_{side}m',
                    stats=stats,native_runtime=None,native_process_wall_seconds=None,
                    observations_sha256=observation_sha,cell_window_ms=plans[key]['cell_window_ms'],
                    independent_composition_audit=dict(status='verified',published_policy_violations=0,
                        source_assigned_once=True,positive_control_equal_native_4s=control_verified if policy=='control' else None),
                    source_native_cases=declaration['source_native_cases'][key])
                print(json.dumps(dict(case=key,status='verified',retained_fraction=stats['retained_fraction'],
                    full_input_semantic_distortion=stats['full_input_semantic_distortion'])),flush=True)
                del native
        require(sha(observations_path)==observation_sha,'Source observations changed during composition')
    require(sha(summary_path)==summary_sha and sha(protocol_path)==protocol_sha,'Source study receipts changed')
    require(sha(binary_path)==binary_sha,'Source native binary changed during composition')
    require(sha(output/'protocol.json')==result['protocol_sha256'],'Static schedule declaration changed')
    result.update(status='verified',executed_case_count=8)
    (output/'summary.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    (output/'report.md').write_text(markdown(result),encoding='utf-8')
    return result


def markdown(result):
    lines=['# Static regional fixed-grid schedule: derived utility','',
        'The grid is fixed in advance. Each cell receives the longest 0.4/1/2/4-s window permitted by whole-footprint temporal and spatial constraints, before any movement data are inspected.','',
        '**This composition is not an implemented or timed online scheduler.** It reuses only independently verified native cell records and independently reconstructs original support, semantic bins, coverage, source partition and all retained-cell requirements. Runtime is undefined.','',
        '| Source | Policy | Grid (m) | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean window (ms) | Mean / p95 delay (ms) |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    def fmt(value,scale=1):return 'n/a' if value is None else f'{value*scale:.3f}'
    for case in result['cases'].values():
        s=case['stats'];delay=s['source_accounting']['observation_to_release_delay_ms']
        lines.append('| '+' | '.join((case['source'],case['policy'],str(case['side_m']),fmt(s['retained_fraction'],100),
            fmt(s['full_input_semantic_distortion'],100),fmt(s['observation_weighted_semantic_loss'],100),
            fmt(s['observation_weighted_interval_duration_ms']),fmt(delay['mean'])+' / '+fmt(delay['p95'])))+' |')
    lines.extend(['','The uniform-temporal control must exactly reproduce the corresponding native global 4-s utility, source-type/region accounting and release-delay distributions. Empty cell intervals are covered by the explicit mathematical partition; every nonempty interval requires its own chosen native private record.','',
        'J assigns unit loss to omitted input plus retained taxonomy loss. Regional point cohorts may overlap; policy checks use full-cell intersections. No attack-based or formal privacy improvement is measured.',''])
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=derive(args.study,args.output)
    print(json.dumps(dict(status=result['status'],executed_case_count=result['executed_case_count'])))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,TypeError) as error:raise SystemExit('Static regional composition failed: '+str(error))
