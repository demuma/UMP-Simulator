#!/usr/bin/env python3
"""Compare fixed grid/windows and semantic triggers on one recorded mapped source.

Each selected matrix and recipient query bank is written before its own cases
execute. The maximum-window mode is explicitly post-hoc after the main study.
Full inputs/results stay local under ignored results/. Only aggregate summaries are
suitable for the repository. The default method matrix preserves every hard
requirement. The explicit support-policy comparison lowers only declared support
floors. The opt-in spatial portfolio adds fixed20 m controls under an original
and an explicitly relaxed spatial20 contract, applied equally to every method.
No mode regenerates source motion or measures empirical privacy.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import math
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


def policy_variants():
    """Predeclare the same controller/fixed portfolio under two support contracts."""
    methods=[dict(id='adaptive_immediate',mode='semantic_first',trigger='policy_satisfied')]+[
        dict(id=f'fixed_{side}m_{window}ms',mode='fixed',depth=depth,window=window)
        for side,depth in [(5,4),(10,3)] for window in [400,1000]]
    return [dict(method,id=profile+'_'+method['id'],policy_profile=profile,method_id=method['id'])
            for profile in ('original','support60') for method in methods]


def max_window_variants():
    """Post-hoc check of the permitted maximum window, separate from the main study."""
    return [dict(id=f'{profile}_fixed_{side}m_4000ms',mode='fixed',depth=depth,window=4000,
                 policy_profile=profile,method_id=f'fixed_{side}m_4000ms')
            for profile in ('original','support60') for side,depth in ((5,4),(10,3))]



SPATIAL_PROFILES=('original','spatial20')


def fixed_depth(coverage,side):
    """Resolve an exact grid side from the frozen square quadtree geometry."""
    width,height,leaf_depth=(coverage.get(key) for key in ('width','height','leaf_depth'))
    if (type(width) not in (int,float) or not math.isfinite(width) or width<=0 or
        type(height) not in (int,float) or height!=width or type(leaf_depth) is not int or not 1<=leaf_depth<=14):
        raise ValueError('Spatial portfolio requires finite square quadtree coverage')
    ratio=width/side
    depth=round(math.log2(ratio))
    if not 1<=depth<=leaf_depth or not math.isclose(width/(2**depth),side,rel_tol=0,abs_tol=1e-9):
        raise ValueError(f'Fixed {side:g} m is not an exact representable quadtree depth')
    return depth


def spatial_portfolio_variants(coverage,profiles=SPATIAL_PROFILES):
    """Two adaptive strategies plus six declared uniform schedules per contract."""
    if (not isinstance(profiles,(tuple,list)) or not profiles or len(set(profiles))!=len(profiles)
        or any(profile not in SPATIAL_PROFILES for profile in profiles)):
        raise ValueError('Spatial profiles must be a nonempty distinct subset of original/spatial20')
    methods=[dict(id='adaptive_immediate',mode='semantic_first',trigger='policy_satisfied'),
             dict(id='adaptive_spatial_first',mode='spatial_first',trigger='policy_satisfied')]+[
        dict(id=f'fixed_{side}m_{window}ms',mode='fixed',depth=fixed_depth(coverage,side),window=window,side_m=side)
        for side in (5,10,20) for window in (400,1000)]
    return [dict(method,id=profile+'_'+method['id'],policy_profile=profile,method_id=method['id'],
                 spatial_portfolio=True,suppression_cap=0,minimum_candidate_depth=fixed_depth(coverage,20))
            for profile in profiles for method in methods]



def spatial_variant_label(variant):
    contract='Original' if variant['policy_profile']=='original' else 'Spatial20'
    if variant['mode']=='fixed':
        label=f"{contract} · Fixed {variant['side_m']:g} m · {variant['window']/1000:g} s"
        if contract=='Original' and variant['side_m']==20: label+=' · rejection control'
        return label
    strategy='Semantic First' if variant['mode']=='semantic_first' else 'Spatial First'
    return contract+' · Adaptive '+strategy

def relaxed_spatial20(base):
    """Declare one common spatial contract; preserve every nonspatial bound.

    Existing root/region cell-side maxima become 20 m. Absent regional maxima
    inherit the root. This relaxation applies to adaptive and fixed methods;
    it is never a method-specific exemption from the strict original contract.
    """
    config=copy.deepcopy(base)
    config['policy_tree']['id']+='-spatial20'
    scopes=[('root',config['policy_tree']['root'])]
    for region in config.get('policy_regions',[]):
        for kind in ('type_requirements','requirements'):
            scopes.append(('region:'+region['id']+':'+kind,region.get(kind,{})))
    changes=[]
    if 'max' not in config['policy_tree']['root'].get('cell_side_m',{}):
        raise ValueError('Spatial portfolio requires a declared original root cell-side maximum')
    for scope,requirements in scopes:
        bounds=requirements.get('cell_side_m',{})
        if 'max' not in bounds: continue
        before=bounds['max']
        if type(before) not in (int,float) or not math.isfinite(before) or not 0<before<=20:
            raise ValueError('Spatial20 may only relax finite positive cell-side maxima up to 20 m')
        if 'min' in bounds and bounds['min']>20:
            raise ValueError('Spatial20 conflicts with an existing minimum cell side')
        bounds['max']=20
        if before!=20:changes.append(dict(scope=scope,metric='cell_side_m',before=before,after=20))
    return config,changes


def validate_completed_source(proof,data=None):
    """New spatial studies reject censored cohorts; old studies stay compatible."""
    if proof.get('all_scheduled_episodes_completed') is not True:
        raise ValueError('Spatial portfolio requires all scheduled episodes completed')
    lifecycle=proof.get('lifecycle_quality',{})
    for field in ('pending_episodes_at_horizon','active_episodes_at_horizon'):
        if field in lifecycle and (type(lifecycle[field]) is not int or lifecycle[field]!=0):
            raise ValueError('Spatial portfolio rejects pending or active episodes at the horizon')
    observation=proof.get('sensor_observability')
    if not isinstance(observation,dict):
        raise ValueError('Spatial portfolio requires a complete sensor-observability proof')
    if observation is not None:
        counts=[observation.get(key) for key in ('scheduled_tracks','sensor_observed_tracks','missing_track_count','unexpected_track_count')]
        if (observation.get('schema')!='ump.source-sensor-episode-observability.v1' or
            observation.get('status')!='pass' or any(type(value) is not int or value<0 for value in counts) or
            counts[0]!=counts[1] or counts[2:]!=[0,0]):
            raise ValueError('Spatial portfolio requires a passing sensor-observability proof')
        if 'scheduled_episodes' in lifecycle and lifecycle['scheduled_episodes']!=counts[0]:
            raise ValueError('Sensor-observability and lifecycle scheduled counts disagree')
        if data is not None:
            observed={item['id'] for batch in data['batches'] for item in batch['observations']}
            if len(observed)!=counts[1]:
                raise ValueError('Sensor-observability count disagrees with the frozen observation stream')
            if 'sensor_period_ms' in observation and observation['sensor_period_ms']!=data['sampling_period_ms']:
                raise ValueError('Sensor-observability cadence disagrees with the frozen source')
            if 'observations' in observation and observation['observations']!=sum(len(batch['observations']) for batch in data['batches']):
                raise ValueError('Sensor-observability contribution count disagrees with the frozen source')


def check_frozen_artifacts(output,digests):
    for name,digest in digests.items():
        if not (Path(output)/name).is_file() or sha(Path(output)/name)!=digest:
            raise ValueError('Frozen portfolio artifact changed: '+name)

def relaxed_support(base):
    """Relax support minima only, including both Region type and instance bounds.

    Integer arithmetic defines ceil(3*n/5) exactly. A positive floor stays at
    least one; 5 becomes 3 and 10 becomes 6. Geometry, execution preferences,
    temporal bounds, semantic ceilings and the catalog remain unchanged.
    """
    config=copy.deepcopy(base)
    config['policy_tree']['id']+='-support60'
    changes=[]
    scopes=[('root',config['policy_tree']['root'])]
    for region in config.get('policy_regions',[]):
        for kind in ('type_requirements','requirements'):
            scopes.append(('region:'+region['id']+':'+kind,region.get(kind,{})))
    for scope,requirements in scopes:
        for metric in ('distinct_contributors','min_category_distinct_contributors'):
            bounds=requirements.get(metric,{})
            if 'min' not in bounds: continue
            before=bounds['min']
            if type(before) not in (int,float) or not math.isfinite(before) or before<0 or before!=int(before):
                raise ValueError('Support-policy comparison requires nonnegative integer floors')
            after=(3*int(before)+4)//5
            bounds['min']=after
            if after!=before: changes.append(dict(scope=scope,metric=metric,before=before,after=after))
    if not changes: raise ValueError('Support-policy comparison requires at least one relaxable support floor')
    return config,changes


def policy_metadata(config):
    """Build viewer overlays from the actual executed policy, never native labels."""
    regions=[]
    for region in config.get('policy_regions',[]):
        effective={}
        for requirements in (region.get('type_requirements',{}),region.get('requirements',{})):
            for metric,bounds in requirements.items():
                target=effective.setdefault(metric,{})
                if 'min' in bounds: target['min']=max(target.get('min',-math.inf),bounds['min'])
                if 'max' in bounds: target['max']=min(target.get('max',math.inf),bounds['max'])
        regions.append({key:region[key] for key in ('id','type','x','y','width','height')})
        regions[-1]['requirements']=[dict(metric=metric,**bounds) for metric,bounds in sorted(effective.items())]
    tree=config['policy_tree']
    return dict(policy_tree_id=tree['id'],policy_tree_version=tree['version'],policy_regions=regions,
                policy_root_requirements=[dict(metric=metric,**bounds) for metric,bounds in sorted(tree['root'].items())])


def source_accounting(data,config,result):
    """Account for actual retained source observations without semantic imputation.

    Each observation is matched to at most one published ancestor/interval.
    Regional rows use its actual point, with half-open boundaries; overlapping
    regions are explicitly nonexclusive. This is separate from the conservative
    whole-cell intersection used by the independent policy audit.
    """
    intervals={}
    for release in result['releases']:
        for cell in release['cells']:
            intervals.setdefault(cell['cell_id'],[]).append((release['start_ms'],release['end_ms'],release['sealed_at_ms']))
    starts={}
    for identity,rows in intervals.items():
        rows.sort(); starts[identity]=[row[0] for row in rows]
        if any(left[1]>right[0] for left,right in zip(rows,rows[1:])):
            raise ValueError('Published intervals overlap within one spatial cell')
    by_type={}; by_region={r['id']:[0,0] for r in config.get('policy_regions',[])}
    by_region['outside_policy_regions']=[0,0]
    delays=Counter(); retained=0
    for batch in data['batches']:
        timestamp=batch['observed_at_ms']
        for observation in batch['observations']:
            matches=[]
            for depth in range(1,data['coverage']['leaf_depth']+1):
                identity=observation['cell_id']>>(2*(data['coverage']['leaf_depth']-depth))
                index=bisect_right(starts.get(identity,()),timestamp)-1
                if index>=0 and timestamp<intervals[identity][index][1]: matches.append(intervals[identity][index])
            if len(matches)>1: raise ValueError('One source contribution appears in overlapping published ancestors')
            released=bool(matches); retained+=released
            counts=by_type.setdefault(observation['type'],[0,0]);counts[0]+=1;counts[1]+=released
            touched=[r['id'] for r in config.get('policy_regions',[])
                     if r['x']<=observation['x']<r['x']+r['width'] and r['y']<=observation['y']<r['y']+r['height']]
            for identity in touched or ['outside_policy_regions']:
                by_region[identity][0]+=1;by_region[identity][1]+=released
            if released:
                delay=matches[0][2]-timestamp
                if delay<0: raise ValueError('Published contribution is sealed before observation')
                delays[delay]+=1
    expected=sum(c['observation_contributions'] for r in result['releases'] for c in r['cells'])
    if retained!=expected: raise ValueError('Released contribution total disagrees with independently matched source')
    def rows(groups):
        return {name:dict(input_observation_contributions=counts[0],retained_observation_contributions=counts[1],
                          unpublished_observation_contributions=counts[0]-counts[1],
                          retained_fraction=counts[1]/counts[0] if counts[0] else None)
                for name,counts in sorted(groups.items())}
    def quantile(fraction):
        target=math.ceil(retained*fraction); cumulative=0
        for delay,count in sorted(delays.items()):
            cumulative+=count
            if cumulative>=target: return delay
        return None
    return dict(by_source_type=rows(by_type),by_source_point_region=rows(by_region),
                region_scope='Nonexclusive half-open source-point memberships; policy tests use whole-cell positive-area intersections.',
                observation_to_release_delay_ms=dict(mean=sum(d*n for d,n in delays.items())/retained if retained else None,
                    p50=quantile(.5),p95=quantile(.95),p99=quantile(.99),maximum=max(delays) if delays else None))


def native_config(cfg):
    # The adapter preserves the normal Region type/instance distinction.
    module_path=Path(__file__).with_name('analyze_tracks.py')
    spec=importlib.util.spec_from_file_location('mapped_tracks',module_path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.replay_config(cfg)


def settings_for(base,variant):
    config=relaxed_support(base)[0] if variant.get('policy_profile')=='support60' else (
        relaxed_spatial20(base)[0] if variant.get('policy_profile')=='spatial20' else copy.deepcopy(base))
    config['policy_tree']['execution']['release_trigger']=variant.get('trigger','policy_satisfied')
    if variant.get('spatial_portfolio'):
        # This controlled portfolio separates strategy from selective filtering.
        config['policy_tree']['root']['semantic_suppression_fraction']={'max':0}
        selection=config.setdefault('spatial_selection',{})
        selection['min_depth']=variant['minimum_candidate_depth']
        execution=config['policy_tree']['execution']
        execution['strategy']='semantic_first' if variant['mode']=='fixed' else variant['mode']
        if execution['strategy']!='semantic_first': execution.pop('semantic_secondary_strategy',None)
        else: execution.setdefault('semantic_secondary_strategy','temporal_first')
        config['policy_tree']['id']+='/'+variant['method_id']
        config['application_id']+='/'+variant['id']
    return config


def support_statistics(rows,weighted_key):
    """Published-record support; p50 is unweighted nearest rank, mean is weighted."""
    if not rows: return dict(min=None,p50=None,**{weighted_key:None})
    ordered=sorted(value for value,_ in rows)
    weight=sum(n for _,n in rows)
    return dict(min=ordered[0],p50=ordered[math.ceil(len(ordered)/2)-1],
                **{weighted_key:sum(value*n for value,n in rows)/weight if weight else None})


def summarize(data,config,result):
    nodes={node['id']:node for node in config['semantic_taxonomy']['nodes']}
    total=sum(len(b['observations']) for b in data['batches'])
    retained=0; loss=0.; exact=0; side=0.; age=0.; duration=0.; categories=Counter(); sizes=Counter()
    cell_support=[]; category_support=[]
    for release in result['releases']:
        for cell in release['cells']:
            n=cell['observation_contributions'];retained+=n
            cell_support.append((cell['distinct_road_users'],n))
            side+=n*cell['width']; age+=n*(release['sealed_at_ms']-release['start_ms']); duration+=n*(release['end_ms']-release['start_ms'])
            sizes[str(cell['width'])]+=1
            for category in cell['semantic']['categories']:
                count=category['observation_contributions']; cost=nodes[category['category_id']]['loss']
                categories[category['category_id']]+=count;loss+=count*cost
                category_support.append((category['distinct_contributors'],count))
                if cost==0: exact+=count
    return {'input_observation_contributions':total,'retained_observation_contributions':retained,
            'retained_fraction':retained/total if total else None,'unpublished_observation_contributions':total-retained,
            'exact_subtype_observation_contributions':exact,'exact_subtype_fraction_of_input':exact/total if total else None,
            'exact_subtype_fraction_of_retained':exact/retained if retained else None,
            'observation_weighted_semantic_loss':loss/retained if retained else None,
            'full_input_semantic_distortion':(total-retained+loss)/total if total else None,
            'observation_weighted_cell_side_m':side/retained if retained else None,
            'observation_weighted_interval_duration_ms':duration/retained if retained else None,
            'observation_weighted_age_at_release_ms':age/retained if retained else None,
            'published_cell_distinct_road_users':support_statistics(cell_support,'observation_weighted_mean'),
            'published_category_distinct_contributors':support_statistics(category_support,'category_observation_weighted_mean'),
            'support_statistics_scope':'Operational observed-track support in published cell-windows/category bins; p50 is unweighted nearest rank. Not measured privacy gain or trajectory k-anonymity.',
            'published_category_observations':dict(sorted(categories.items())),
            'published_cell_sizes':dict(sorted(sizes.items())),
            'published_cell_windows':sum(len(r['cells']) for r in result['releases']),
            'unique_published_spatial_ids':len({c['cell_id'] for r in result['releases'] for c in r['cells']}),
            'core_processing_ms':result.get('runtime',{}).get('processing_ms')}



def report_markdown(summary):
    """Human-readable aggregate evidence; no source IDs, coordinates or releases."""
    def number(value,places=2): return 'n/a' if value is None else f'{value:.{places}f}'
    def percent(value): return 'n/a' if value is None else f'{100*value:.2f}%'
    source=summary['source']
    lines=['# Same-source mapped comparison', '',
           f"Status: {summary['status']}. Observations SHA-256: `{summary['protocol']['observations_sha256']}`.", '',
           summary['protocol']['policy_scope'], '',
           f"Source horizon: {source['horizon_ms']/1000:g} s; sensor period: {source['sampling_period_ms']} ms; "
           f"input observation contributions: {source['input_observation_contributions']}; "
           f"peak observed simultaneous tracks: {source['peak_observed_simultaneous_tracks']}.", '',
           'A completed source horizon does not imply a drained finite cohort. The lifecycle counts below describe the recorded horizon.', '',
           f"Recorded lifecycle counts: `{json.dumps(source['recorded_lifecycle_counts'],sort_keys=True)}`.", '',
           '## Policy and retained detail', '',
           '| Case | Retained input | Exact subtype / input | Mean semantic loss | Mean cell side (m) | Mean interval (ms) | Mean observation delay (ms) | p95 delay (ms) | Core (ms) | Policy violations |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,case in summary['cases'].items():
        stats=case['stats'];delay=stats['source_accounting']['observation_to_release_delay_ms']
        lines.append('| '+' | '.join([name,percent(stats['retained_fraction']),percent(stats['exact_subtype_fraction_of_input']),
            number(stats['observation_weighted_semantic_loss']),number(stats['observation_weighted_cell_side_m']),
            number(stats['observation_weighted_interval_duration_ms']),number(delay['mean']),number(delay['p95']),
            number(stats['core_processing_ms']),str(case['independent_audit']['published_policy_violations'])])+' |')
    lines += ['', 'Zero violations with no releases is vacuous compliance; read it together with retention. Semantic, side and interval means condition on retained observations. Exact subtype / input and retention use the full input denominator.', '',
              '## Operational observed-track support', '',
              'Cell statistics use distinct observed tracks per published cell-window. Category statistics use distinct tracks per published semantic bin. Both p50 values are unweighted nearest-rank medians; means are weighted by cell or category observation contributions respectively. Empty output is n/a. These are operational support statistics, not measured attack risk, privacy gain or a trajectory k-anonymity guarantee.', '',
              '| Case | Cell min | Cell p50 | Cell observation-weighted mean | Category min | Category p50 | Category observation-weighted mean |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name,case in summary['cases'].items():
        cells=case['stats']['published_cell_distinct_road_users'];categories=case['stats']['published_category_distinct_contributors']
        lines.append('| '+' | '.join([name,number(cells['min'],0),number(cells['p50'],0),
            number(cells['observation_weighted_mean']),number(categories['min'],0),number(categories['p50'],0),
            number(categories['category_observation_weighted_mean'])])+' |')
    lines += ['', 'Core timing excludes input validation and file I/O. The complete comparison pipeline also includes independent Python audits and query evaluation. Neither timing is a per-step live deadline guarantee.', '',
              '## Recipient queries', '',
              summary['protocol']['query_category_scope'], '',
              'The table separates positive-reference queries from known-zero queries, and interior windows from source-boundary windows. Estimates use public uniform spatial/time allocation and keep their own error; missing output never becomes zero.', '',
              '| Case | Lag (ms) | Cohort | Positive reference queries | Exact coverage | Estimated coverage | Estimated occupancy MAE |',
              '| --- | ---: | --- | ---: | ---: | ---: | ---: |']
    for name,case in summary['cases'].items():
        for lag,evaluation in case['recipient_query_summaries'].get('evaluations_by_lag_ms',{}).items():
            for cohort,exact in evaluation.get('summary',{}).items():
                positive=exact.get('positive',{})
                support=evaluation.get('recipient_support_summary',{}).get(cohort,{})
                estimate=support.get('positive',{}).get('uniform_estimate',{})
                lines.append('| '+' | '.join([name,str(lag),cohort,str(positive.get('reference_available_query_count',0)),
                    percent(positive.get('query_coverage')),percent(estimate.get('query_coverage')),
                    number(estimate.get('answered_only_mean_sample_occupancy_mae'),4)])+' |')
    lines += ['', '## Source type and local region costs', '',
              'Each row keeps the full input denominator for that type or source-point region. Region memberships can overlap and do not sum to a global partition. Effective policy audit instead intersects the entire released footprint with every selected region.', '',
              '| Case | Group kind | Group | Input contributions | Retained contributions | Retained fraction |',
              '| --- | --- | --- | ---: | ---: | ---: |']
    for name,case in summary['cases'].items():
        for kind in ('by_source_type','by_source_point_region'):
            for group,values in case['stats']['source_accounting'][kind].items():
                lines.append('| '+' | '.join([name,kind,group,str(values['input_observation_contributions']),
                    str(values['retained_observation_contributions']),percent(values['retained_fraction'])])+' |')
    lines += ['', '## Interpretation limits', '',
              summary['protocol'].get('portfolio_scope','The tested fixed portfolio covers 5/10 m crossed with 400/1000 ms; adaptive windows may extend to 4000 ms, so this alone cannot isolate adaptation from longer permitted windows.')+(' Compare controller choices within one policy. Changing spatial utility bounds changes the output contract; between-policy utility differences do not establish a privacy gain.' if summary['protocol'].get('comparison_kind')=='spatial_resolution_portfolio' else ' Compare controller choices within one policy. Relaxing support changes the protection contract, so improved utility across policies does not establish a privacy gain.'), '',
              summary['protocol']['replication'], '',
              'Distinct observed-track support is an operational release condition. It is not automatically classical trajectory k-anonymity, and this comparison contains no membership, linkage or re-identification attack.', '']
    return '\n'.join(lines)


def compare(recording,output,binary,*,policy_comparison=False,max_window_sensitivity=False,
            spatial_portfolio=False,spatial_profiles=SPATIAL_PROFILES,native_wall_budget_s=240,audit_max_cells=None):
    if type(native_wall_budget_s) is not int or not 1<=native_wall_budget_s<=3600:
        raise ValueError('Native wall budget must be an integer from 1 to 3600 seconds')
    if sum(bool(value) for value in (policy_comparison,max_window_sensitivity,spatial_portfolio))>1:
        raise ValueError('Choose either one comparison mode or one sensitivity portfolio')
    if not spatial_portfolio and tuple(spatial_profiles)!=SPATIAL_PROFILES:
        raise ValueError('Spatial profiles are only valid with the spatial portfolio')
    from semantic_suppression_audit import audit_budget
    effective_audit_budget=audit_budget(audit_max_cells,1000000) if spatial_portfolio or audit_max_cells is not None else None
    support_study=policy_comparison or max_window_sensitivity
    recording=Path(recording).resolve();output=Path(output).resolve();binary=Path(binary).resolve()
    if output.exists(): raise ValueError('Choose a new comparison directory')
    proof=read(recording/'capture-proof.json')
    if proof.get('schema')!='ump.mapped-recording-proof.v1' or proof.get('status')!='verified' or proof.get('source_completed') is not True:
        raise ValueError('Require a completed verified mapped recording')
    if spatial_portfolio: validate_completed_source(proof)
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
    shared_files=['observations.json','map_background.png']
    if read(recording/'bundle.json').get('map',{}).get('building_access'):
        if 'building_access.json' not in hashes: raise ValueError('Missing building access recording digest')
        shared_files.append('building_access.json')
    data=read(recording/'observations.json');native_cfg=yaml.safe_load((recording/'private/config.yaml').read_text());base=native_config(native_cfg)
    if spatial_portfolio: validate_completed_source(proof,data)
    progress_step=round(native_cfg['simulation']['time_step']*1000)
    if progress_step<=0 or data['sampling_period_ms']%progress_step or abs(native_cfg['simulation']['time_step']*1000-progress_step)>1e-9:
        raise ValueError('Native progress step must be whole milliseconds dividing sensor cadence')
    matrix=(spatial_portfolio_variants(data['coverage'],spatial_profiles) if spatial_portfolio else
            max_window_variants() if max_window_sensitivity else policy_variants() if policy_comparison else variants())
    changes=relaxed_support(base)[1] if support_study else relaxed_spatial20(base)[1] if spatial_portfolio else []
    if spatial_portfolio:
        original_max=base['policy_tree']['root']['cell_side_m']['max']
        if not original_max<20: raise ValueError('Original spatial contract must prohibit 20 m for its declared negative control')
    query_depth=fixed_depth(data['coverage'],10) if spatial_portfolio else 3
    query={'target_cells':[{'cell_id':identity,'depth':query_depth} for identity in range(3<<(2*query_depth),4<<(2*query_depth))],
           'categories':sorted(node['id'] for node in base['semantic_taxonomy']['nodes']
                               if not (support_study or spatial_portfolio) or 'parent' not in node or
                               any(parent['id']==node.get('parent') and 'parent' not in parent for parent in base['semantic_taxonomy']['nodes'])),
           'window_ms':1000,'lags_ms':[0,1000]}
    query_count=(data['end_ms']//query['window_ms'])*len(query['target_cells'])*len(query['categories'])*len(query['lags_ms'])
    if query_count>QUERY_BUDGET:
        raise ValueError('Declared mapped comparison exceeds query budget; shorten the source horizon')
    output.mkdir(parents=True,mode=0o700)
    binary_sha=sha(binary);source_sha=sha(recording/'observations.json')
    frozen={}
    if spatial_portfolio:
        provenance=output/'provenance';provenance.mkdir(mode=0o700)
        shutil.copy2(binary,provenance/'AggregationReplay')
        shutil.copyfile(recording/'capture-proof.json',provenance/'capture-proof.json')
        shutil.copyfile(recording/'observations.json',output/'observations.json')
        if sha(provenance/'AggregationReplay')!=binary_sha or sha(output/'observations.json')!=source_sha:
            raise ValueError('Source or binary changed while preparing the frozen portfolio')
        write(output/'query-bank.json',query)
        for variant in matrix: write(output/(variant['id']+'-policy.json'),settings_for(base,variant))
        frozen={str(path.relative_to(output)):sha(path) for path in output.rglob('*') if path.is_file()}
    protocol={'schema':'ump.mapped-comparison-protocol.v1','matrix':matrix,'queries':query,
              'binary_sha256':binary_sha,'observations_sha256':source_sha,'progress_step_ms':progress_step,'query_count':query_count,'query_budget':QUERY_BUDGET,
              'native_process_wall_budget_s':native_wall_budget_s,
              'policy_scope':('Support-only sensitivity: support60 lowers each root/region type/instance support floor to ceil(0.6*n). All other hard constraints, taxonomy and release triggers match. Compare methods within a policy; policy changes alter the protection contract.' if support_study else
                              'Every hard root/region constraint and taxonomy is unchanged across methods. Fixed settings still perform permitted semantic generalization.'),
              'comparison_kind':'post_hoc_fixed_max_window_sensitivity' if max_window_sensitivity else 'support_policy_sensitivity' if policy_comparison else 'methods',
              'analysis_status':'post_hoc_sensitivity_after_ten_case_results' if max_window_sensitivity else 'predeclared_matrix',
              'portfolio_scope':('Post-hoc fixed maximum-window sensitivity: 5/10 m crossed with 4000 ms, selected after the original ten-case results; the original study remains unchanged.' if max_window_sensitivity else
                                 'The fixed portfolio is a declared subset (5/10 m crossed with 400/1000 ms), not a claim of the best possible uniform schedule. Adaptive windows may extend to 4000 ms, so this portfolio alone cannot isolate adaptation from access to longer windows.'),
              'policy_changes':changes,
              'query_category_scope':'Total and immediate taxonomy families; fine-label preservation is reported separately.' if support_study else 'Every declared taxonomy node.',
              'recipient_scope':'Conservative exact answers plus separately evaluated uniform spatial/temporal occupancy estimates. Missing support never becomes zero.',
              'replication':'One deterministic source; no population-level statistical generalization or privacy-improvement claim.'}
    if spatial_portfolio:
        protocol.update(comparison_kind='spatial_resolution_portfolio',analysis_status='predeclared_matrix',
            policy_scope='Original: all original hard root/region constraints remain. Spatial20: every existing root/region cell_side_m.max becomes20 m, equally for every method. All support, temporal and semantic bounds, regions and taxonomy remain. Selective contribution suppression is disabled in every case. Compare methods within one contract.',
            portfolio_scope='Two adaptive strategies and fixed 5/10/20 m crossed with 400/1000 ms under each selected contract. Original 20 m is a deliberate negative control. Adaptive windows may reach 4000 ms. Connected fixed-grid measurements are empirical guides only: no fitted regression, statistical significance or claim for intermediate cell sizes.',
            spatial_profiles=list(spatial_profiles),source_completion_gate='All scheduled episodes complete; zero pending/active if reported; required complete sensor-observability proof.',
            shared_execution_changes=[dict(setting='spatial_selection.min_depth',before=base.get('spatial_selection',{}).get('min_depth'),after=fixed_depth(data['coverage'],20),scope='Every method under both contracts; candidate search permits20 m while strict original numeric policy rejects20 m'),
                dict(setting='semantic_suppression_fraction.max',before=base['policy_tree']['root'].get('semantic_suppression_fraction',{}).get('max',0),after=0,scope='Every method under both contracts; contribution filtering disabled')],
            source_proof_sha256=sha(recording/'capture-proof.json'),pre_execution_artifacts_sha256=frozen,
            query_category_scope='Total and immediate taxonomy families, identical across both contracts. Exact subtype preservation is separately source-denominated.',
            binary_execution='Frozen local provenance/AggregationReplay copy; all configurations and query-bank written and hashed before first execution.')
    if effective_audit_budget is not None:
        protocol['offline_audit_max_cells']=effective_audit_budget
        protocol['offline_audit_capacity_scope']='Explicit bound for independently checked private windows/releases and cells; every geometry/count/coverage/policy/retirement check is retained. This is offline validator capacity, not an aggregation-policy change.'
    write(output/'protocol.json',protocol)
    summary={'schema':'ump.mapped-comparison.v1','status':'running' if spatial_portfolio else 'verified','protocol':protocol,'cases':{},'scientific_repetitions':0,
             'source':dict(horizon_ms=data['end_ms'],sampling_period_ms=data['sampling_period_ms'],
                 input_observation_contributions=sum(len(batch['observations']) for batch in data['batches']),
                 peak_observed_simultaneous_tracks=max((len(batch['observations']) for batch in data['batches']),default=0),
                 recorded_lifecycle_counts={key:proof.get('lifecycle_quality',{}).get(key) for key in
                     ('scheduled_people','scheduled_episodes','realized_starts','realized_ends','pending_episodes_at_horizon','active_episodes_at_horizon')})}
    viewer=copy.deepcopy(read(recording/'bundle.json'))
    viewer['title']=('Mönckebergstraße · original and spatial20 contracts · same-source resolution portfolio' if spatial_portfolio else
                     'Mönckebergstraße · post-hoc maximum-window sensitivity on one source' if max_window_sensitivity else
                     'Mönckebergstraße · original and relaxed support policies on one source' if policy_comparison else
                     'Mönckebergstraße · same-source fixed and adaptive comparison')
    viewer['variants']=[]; viewer['sha256']={}
    # Local copies allow a self-contained persistent comparison; original remains frozen.
    for name in shared_files:
        if spatial_portfolio and name=='observations.json': continue
        shutil.copyfile(recording/name,output/name)
    for variant in matrix:
        name=variant['id'];config=settings_for(base,variant)
        config_path=output/(name+'-policy.json');result_path=output/(name+'.json')
        if not spatial_portfolio: write(config_path,config)
        if spatial_portfolio: check_frozen_artifacts(output,frozen)
        execution_binary=output/'provenance/AggregationReplay' if spatial_portfolio else binary
        execution_input=output/'observations.json' if spatial_portfolio else recording/'observations.json'
        command=[str(execution_binary),'--input',str(execution_input),'--config',str(config_path),
                 '--mode',variant['mode'],'--output',str(result_path),'--progress-step-ms',str(progress_step)]
        if variant['mode']=='fixed':command+=['--fixed-depth',str(variant['depth']),'--fixed-window-ms',str(variant['window'])]
        start=time.perf_counter(); completed=subprocess.run(command,text=True,capture_output=True,timeout=native_wall_budget_s)
        process_wall=time.perf_counter()-start
        (output/(name+'.log')).write_text(completed.stdout+completed.stderr)
        if completed.returncode: raise RuntimeError(name+': '+completed.stderr[:2000])
        result=read(result_path)
        audit_config=copy.deepcopy(config)
        # Fixed modes use common publication intervals even when the source's
        # adaptive configuration selects local ownership. This changes only
        # independent retirement validation, never a hard policy or execution.
        audit_config.setdefault('temporal_adaptation',{})['coordination']=result['parameters']['coordination']
        audit=run_local_policy_replay.audit(data,audit_config,result,**({'max_cells':effective_audit_budget} if effective_audit_budget is not None else {}))
        stats=summarize(data,config,result)
        stats['source_accounting']=source_accounting(data,config,result)
        evaluation=recipient_support.evaluate(data,config,result['releases'],**query,max_queries=QUERY_BUDGET,uniform_estimate=True)
        compact=recipient_support.compact(evaluation)
        write(output/(name+'-queries.json'),compact)
        write(output/(name+'-private-audit.json'),audit)
        audit_summary={'status':audit['status'],'scalar_valid':audit['scalar']['valid'],
                       'semantic_published_cells':audit['semantic_published_cells'],
                       'semantic_published_bins':audit['semantic_published_bins'],
                       'regional_recomputed_cells':len(audit['regional_recomputations']),
                       'published_policy_violations':0,
                       'zero_violation_scope':'Every published cell is independently audited; zero releases is vacuous compliance, not successful coverage.'}
        pipeline_wall=time.perf_counter()-start
        summary['cases'][name]={'policy_profile':variant.get('policy_profile','original'),
                                 'policy_tree_id':config['policy_tree']['id'],'stats':stats,'independent_audit':audit_summary,
                                 'recipient_query_summaries':compact,'native_process_wall_seconds':process_wall,
                                 'comparison_pipeline_wall_seconds':pipeline_wall,
                                 'wall_seconds':pipeline_wall,
                                 'timing_scope':'wall_seconds is a legacy alias for comparison_pipeline_wall_seconds, including Python audits/queries/writes.',
                                 'result_sha256':sha(result_path),'config_sha256':sha(config_path)}
        # The actual native output is independent evidence, not silently replaced.
        # The comparison viewer explicitly identifies every panel as an offline rerun.
        metadata=copy.deepcopy(read(recording/'bundle.json')['variants'][0])
        metadata.update(id=name,label=name.replace('_',' '),result=result_path.name,**policy_metadata(config))
        if spatial_portfolio:
            metadata['contribution_selection']='all_contributions'
            metadata['label']=spatial_variant_label(variant)
        viewer['variants'].append(metadata)
        if spatial_portfolio: check_frozen_artifacts(output,frozen)
        if sha(binary)!=binary_sha or sha(recording/'observations.json')!=source_sha:
            raise ValueError('Frozen binary/source changed during comparison')
        print(json.dumps({'variant':name,'status':'verified','retained_fraction':stats['retained_fraction'],
                          'exact_subtype_fraction':stats['exact_subtype_fraction_of_input']}),flush=True)
    if policy_comparison:
        # The initial panes compare the same controller under the two policies.
        # Presentation order does not change the predeclared execution matrix.
        initial=('original_adaptive_immediate','support60_adaptive_immediate')
        indexed={variant['id']:variant for variant in viewer['variants']}
        viewer['variants']=[indexed[name] for name in initial]+[variant for variant in viewer['variants'] if variant['id'] not in initial]
    for name in shared_files+[v['result'] for v in viewer['variants']]:viewer['sha256'][name]=sha(output/name)
    viewer['input_provenance']+=' Comparison panels are actual offline AggregationReplay executions on these identical observations, not the native sink stream.'
    write(output/'bundle.json',viewer)
    spec=importlib.util.spec_from_file_location('viewer_validation',ROOT/'tools/replay_viewer/serve.py');validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator);validator.validate_bundle(output)
    summary['status']='verified'
    with (output/'report.md').open('x') as stream: stream.write(report_markdown(summary))
    write(output/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'simulator/build/AggregationReplay')
    study=parser.add_mutually_exclusive_group()
    study.add_argument('--policy-comparison',action='store_true',
                        help='Predeclare original versus support60 policies on the identical recorded source; other hard bounds stay fixed')
    study.add_argument('--max-window-sensitivity',action='store_true',
                       help='Separate post-hoc original/support60 fixed5m/10m 4000-ms sensitivity; never replaces the ten-case study')
    study.add_argument('--spatial-portfolio',action='store_true',
                       help='Predeclare original/spatial20 same-source adaptive and fixed 5/10/20 m ×400/1000 ms contracts')
    parser.add_argument('--spatial-profiles',nargs='+',choices=SPATIAL_PROFILES,default=list(SPATIAL_PROFILES),
                        help='Spatial portfolio contracts (default: original spatial20); compare methods within each contract')
    parser.add_argument('--audit-max-cells',type=int,default=None,
                        help='Explicit offline audit bound1..1000000; spatial portfolio defaults1000000, legacy modes keep previous defaults')
    parser.add_argument('--native-wall-budget-s',type=int,default=240,
                        help='Per-case native process wall budget, 1..3600 seconds (default: 240); execution limit only')
    args=parser.parse_args(); compare(args.recording,args.output,args.binary,policy_comparison=args.policy_comparison,
                                     max_window_sensitivity=args.max_window_sensitivity,spatial_portfolio=args.spatial_portfolio,
                                     spatial_profiles=args.spatial_profiles,native_wall_budget_s=args.native_wall_budget_s,audit_max_cells=args.audit_max_cells)


if __name__=='__main__':main()
