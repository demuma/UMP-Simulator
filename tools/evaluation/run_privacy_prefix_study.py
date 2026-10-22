#!/usr/bin/env python3
"""Causal recipient-prefix membership probes over an immutable completed study.

No mechanism replay or old model loading occurs. Every checkpoint classifier is
fitted on TRAIN only. One CAL threshold is chosen for the maximum score over all
predeclared looks, then frozen across independent test cohorts. Logical sealing is
an availability proxy, not measured network latency or a formal privacy guarantee.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import math
from pathlib import Path
import platform
import shutil
import sys

from causal_privacy import CHECKPOINTS, PROFILES, RECENT_WINDOW_MS, feature_names, feature_views_many, knowledge_events
from empirical_privacy import attack_metrics, calibrate_threshold
from privacy_dataset import validate_dataset
from robustness_attacks import FAMILIES, HGB_PARAMETERS, LOGISTIC_PARAMETERS, _optional_libraries, fit_attack, predict_attack
from run_comparison import digest, git_state, write_json
from run_coordination_study import source_files
from run_privacy_study import CONTROLS, clustered_intervals, paired_auc_difference, read_json, relative_file, stable_seed

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = ('fixed_20m_1000ms', 'common_temporal_first', 'common_spatial_first',
            'local_temporal_first', 'local_spatial_first') + tuple(CONTROLS)
DISTRIBUTIONS = ('base', 'background_density_shift')
AUXILIARY_STREAM = 'control_auxiliary_only'
VIEWS = ('recent', 'history')


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(name+' must be an integer >= '+str(minimum))
    return value


def _hash_checked(root, relative, expected, consumed):
    path = relative_file(root, relative)
    actual = digest(path)
    if actual != expected:
        raise ValueError('Consumed artifact provenance mismatch: '+relative)
    consumed[str(path)] = actual
    return path


def load_source(study, dataset):
    """Validate the exact public/data provenance consumed by this analysis."""
    study, dataset = Path(study).resolve(strict=True), Path(dataset).resolve(strict=True)
    manifest, protocol, report = (read_json(study/name) for name in ('manifest.json','protocol.json','report.json'))
    if (manifest.get('schema') != 'ump.privacy-robustness-manifest.v1' or manifest.get('status') != 'complete'
            or protocol.get('schema') != 'ump.privacy-robustness-protocol.v1' or protocol.get('status') != 'predeclared'
            or report.get('schema') != 'ump.privacy-robustness-report.v1' or report.get('status') != 'complete'):
        raise ValueError('Source must be a completed immutable robustness study')
    artifacts, consumed = manifest.get('artifact_sha256', {}), {}
    for name, expected in (('protocol.json',manifest.get('protocol_sha256')),('report.json',manifest.get('report_sha256'))):
        if artifacts.get(name) != expected:
            raise ValueError('Source metadata is not linked by the artifact manifest')
        _hash_checked(study,name,expected,consumed)
    if report.get('protocol_sha256') != manifest.get('protocol_sha256'):
        raise ValueError('Source report/protocol linkage mismatch')
    consumed[str(study/'manifest.json')] = digest(study/'manifest.json')
    expected_data = protocol.get('dataset_manifest_sha256')
    _hash_checked(dataset,'manifest.json',expected_data,consumed)
    copied = _hash_checked(study,'dataset-manifest.json',artifacts.get('dataset-manifest.json'),consumed)
    data = read_json(dataset/'manifest.json')
    if read_json(copied) != data or data.get('schema') != 'ump.privacy-dataset.v2':
        raise ValueError('Source study and supplied v2 dataset differ')
    for case in data.get('cases',[]):
        for key in ('present_input','absent_input','target_trace'):
            _hash_checked(dataset,case[key],case['sha256'][key],consumed)
    for key, hash_key in (('policy','policy_sha256'),('generation_protocol','generation_protocol_sha256')):
        _hash_checked(dataset,data[key],data[hash_key],consumed)
    validate_dataset(data,dataset)
    for split in ('train','calibration'):
        selected = [c for c in data['cases'] if c['split']==split]
        if len(selected)<2 or any(c['distribution']!='base' for c in selected):
            raise ValueError('TRAIN and CAL require independent base-only source groups')
    for distribution in DISTRIBUTIONS:
        if sum(c['split']=='test' and c['distribution']==distribution for c in data['cases'])<2:
            raise ValueError('Both independent test cohorts need at least two groups')
    available = {v[0] for v in protocol.get('variants',[])} | set(protocol.get('controls',[]))
    if not set(VARIANTS).issubset(available):
        raise ValueError('Source does not contain all five mechanisms and both controls')
    validation = report.get('independent_validation',{})
    if not validation.get('all_valid'):
        raise ValueError('Source mechanism audits are not all valid')
    expected_binary = protocol.get('binary_sha256')
    if manifest.get('binary_sha256') != expected_binary or artifacts.get('AggregationReplay.frozen') != expected_binary:
        raise ValueError('Source mechanism executable provenance mismatch')
    _hash_checked(study,'AggregationReplay.frozen',expected_binary,consumed)
    source_hashes = protocol.get('source_sha256',{})
    required = {'simulator/CMakeLists.txt','simulator/tools/AggregationReplay.cpp','simulator/src/CellLocalAggregation.cpp'}
    if not isinstance(source_hashes,dict) or not required.issubset(source_hashes):
        raise ValueError('Source study lacks its mechanism source snapshot')
    for relative,expected in source_hashes.items():
        if not isinstance(relative,str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Unsafe source snapshot path')
        name = 'source/'+relative
        if artifacts.get(name)!=expected:
            raise ValueError('Source snapshot hash is not linked by its artifact manifest')
        _hash_checked(study,name,expected,consumed)
    for variant in VARIANTS:
        if variant not in CONTROLS:
            name = 'policies/'+variant+'.json';expected=protocol.get('effective_policy_sha256',{}).get(variant)
            if artifacts.get(name)!=expected: raise ValueError('Source effective policy linkage mismatch')
            _hash_checked(study,name,expected,consumed)
        for case in data['cases']:
            for world in ('present','absent'):
                name = public_relative(case,world,variant)
                _hash_checked(study,name,artifacts.get(name),consumed)
    return dict(study=study,dataset=dataset,manifest=manifest,protocol=protocol,report=report,data=data,consumed=consumed)


def public_relative(case, world, variant):
    token = hashlib.sha256(f'{case["case_id"]}:{world}:{variant}'.encode()).hexdigest()[:24]
    return 'public/'+token+'.json'


def _path_rows(paths, checkpoints, *, at=None):
    """One paired source/world row per trajectory, never one row per look."""
    output=[];seen=set();labels=defaultdict(list)
    if at is not None and (type(at) is not int or not 0<=at<len(checkpoints)):
        raise ValueError('Checkpoint index is outside the declared schedule')
    for row in paths:
        identity=row['group_id'],row['label']
        if identity in seen or type(row['label']) is not int or row['label'] not in (0,1):
            raise ValueError('Score paths contain duplicate or invalid source/world identities')
        seen.add(identity);labels[row['group_id']].append(row['label'])
        values=row['scores']
        if (not isinstance(values,list) or len(values)!=len(checkpoints)
                or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in values)):
            raise ValueError('Score trajectory has invalid or incomplete checkpoint values')
        limit=len(checkpoints) if at is None else at+1
        output.append({key:row[key] for key in ('group_id','scenario','distribution','label')}
                      | dict(score=max(values[:limit])))
    if not labels or any(sorted(values)!=[0,1] for values in labels.values()):
        raise ValueError('Every score-path group must contain both membership worlds')
    return output


def _raw_rows(paths, index):
    return [{key:row[key] for key in ('group_id','scenario','distribution','label')}
            | dict(score=row['scores'][index]) for row in paths]


def calibrate_paths(paths, checkpoints):
    """Choose one empirical operating point for the complete fixed look schedule."""
    rows=_path_rows(paths,checkpoints)
    return calibrate_threshold([r['score'] for r in rows],[r['label'] for r in rows],target_fpr=.1)


def _first_crossings(paths, checkpoints, threshold):
    output={}
    for label,name in ((1,'positive'),(0,'negative')):
        selected=[r for r in paths if r['label']==label];counts=Counter()
        for row in selected:
            first=next((t for t,score in zip(checkpoints,row['scores']) if score>=threshold),None)
            counts[first]+=1
        accumulated=0;curve=[]
        for t in checkpoints:
            accumulated+=counts[t]
            curve.append(dict(checkpoint_ms=t,first_crossings=counts[t],cumulative_count=accumulated,
                              cdf=accumulated/len(selected)))
        output[name]=dict(cases=len(selected),never_alarm=counts[None],curve=curve)
    return output


def assess_paths(paths, checkpoints, threshold, repeats, seed_parts):
    maximum=_path_rows(paths,checkpoints)
    output=dict(test_groups=len(maximum)//2,max_score=attack_metrics([r['score'] for r in maximum],
        [r['label'] for r in maximum],threshold),max_score_uncertainty=clustered_intervals(maximum,threshold,repeats,
        stable_seed('prefix-max',*seed_parts)),checkpoints=[],first_crossing_cdf=_first_crossings(paths,checkpoints,threshold))
    for index,t in enumerate(checkpoints):
        raw,cumulative=_raw_rows(paths,index),_path_rows(paths,checkpoints,at=index)
        raw_metrics=attack_metrics([r['score'] for r in raw],[r['label'] for r in raw],threshold)
        raw_uncertainty=clustered_intervals(raw,threshold,repeats,stable_seed('prefix-score',*seed_parts,t))
        output['checkpoints'].append(dict(checkpoint_ms=t,eof_checkpoint=t==checkpoints[-1],
            score_auc=raw_metrics['roc_auc'],score_auc_uncertainty=raw_uncertainty.get('intervals',{}).get('roc_auc'),
            cumulative_alarm=attack_metrics([r['score'] for r in cumulative],[r['label'] for r in cumulative],threshold),
            cumulative_alarm_uncertainty=clustered_intervals(cumulative,threshold,repeats,
                stable_seed('prefix-alarm',*seed_parts,t))))
    return output


def _same_pair_features(rows):
    grouped=defaultdict(dict)
    for row in rows:grouped[row['group_id']][row['label']]=row['features']
    if any(set(labels)!={0,1} or labels[0]!=labels[1] for labels in grouped.values()):
        raise ValueError('Auxiliary-only features differ between the two membership worlds')


def _replace_json(path, value):
    """Atomically advance our own new manifest/report; never overwrite inputs."""
    temporary=path.with_name('.'+path.name+'.update')
    try:
        write_json(temporary,value)
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        if temporary.exists():temporary.unlink()


def _mark_failure(output, manifest, error):
    write_json(output/'failure.json',dict(error_type=type(error).__name__,message=str(error)))
    manifest.update(status='failed',failure_sha256=digest(output/'failure.json'))
    _replace_json(output/'manifest.json',manifest)


def run_study(source_study,dataset,output,*,checkpoints=CHECKPOINTS,recent_window_ms=RECENT_WINDOW_MS,
              bootstrap_repeats=400,attack_families=FAMILIES):
    _integer(bootstrap_repeats,'bootstrap repeats')
    checkpoints=tuple(checkpoints)
    if not checkpoints or any(isinstance(t,bool) or not isinstance(t,int) or t<=0 for t in checkpoints):
        raise ValueError('Checkpoints must be positive integer times')
    if tuple(sorted(set(checkpoints)))!=checkpoints:
        raise ValueError('Checkpoints must be strictly increasing and unique')
    if type(recent_window_ms) is not int or recent_window_ms!=RECENT_WINDOW_MS:
        raise ValueError('This protocol fixes the recent arrival window at 1000 ms')
    families=tuple(attack_families)
    if not families or len(set(families))!=len(families) or set(families)-set(FAMILIES):
        raise ValueError('Select unique predeclared attack families')
    if 'hist_gradient_boosting' in families:_optional_libraries()
    source=load_source(source_study,dataset);data=source['data'];horizon=data['end_ms']
    if checkpoints[-1]!=horizon:
        raise ValueError('Final checkpoint must equal the fixed source horizon; earlier checkpoints are interior')
    output=Path(output).expanduser()
    if output.exists() or output.is_symlink():raise FileExistsError('Prefix-study output already exists')
    output=output.resolve()
    for protected in (source['study'],source['dataset']):
        if output==protected or protected in output.parents or output in protected.parents:
            raise ValueError('Output and immutable source/data must be separate non-nested directories')
    paths=source_files(ROOT)+sorted((ROOT/'tools/evaluation').glob('requirements-robustness*.txt'))
    analysis_hashes={str(p.relative_to(ROOT)):digest(p) for p in paths}
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    manifest=dict(schema='ump.privacy-prefix-manifest.v1',status='running',phase='freezing_analysis')
    write_json(output/'manifest.json',manifest)
    try:
        for name in ('models','knowledge','source'):(output/name).mkdir(mode=0o700)
        for relative,expected in analysis_hashes.items():
            destination=output/'source'/relative;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/relative,destination)
            if digest(destination)!=expected:raise ValueError('Analysis source changed while freezing')
        for name in ('manifest.json','protocol.json','report.json','dataset-manifest.json'):
            shutil.copyfile(source['study']/name,output/('source-study-'+name))
        versions={}
        for package in ('scikit-learn','numpy','scipy','joblib','threadpoolctl'):
            try:versions[package]=importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:versions[package]=None
        protocol=dict(schema='ump.privacy-prefix-protocol.v1',status='predeclared',classification='private_predeclared_protocol',
            created_utc=datetime.now(timezone.utc).isoformat(),git=git_state(ROOT),python=sys.version,platform=platform.platform(),packages=versions,
            source_study=str(source['study']),dataset=str(source['dataset']),source_manifest_sha256=digest(source['study']/'manifest.json'),
            source_protocol_sha256=digest(source['study']/'protocol.json'),source_report_sha256=digest(source['study']/'report.json'),
            dataset_manifest_sha256=digest(source['dataset']/'manifest.json'),consumed_sha256=source['consumed'],analysis_source_sha256=analysis_hashes,
            checkpoints_ms=list(checkpoints),interior_checkpoints_ms=list(checkpoints[:-1]),eof_checkpoint_ms=horizon,recent_window_ms=recent_window_ms,
            protected_unit='Whole recorded candidate source contribution over the fixed source horizon; unchanged at every look',
            secret='Source-contribution inclusion; physical candidate exists in both worlds',source_horizon_ms=horizon,
            variants=list(VARIANTS),profiles=list(PROFILES),views=list(VIEWS),auxiliary_control=AUXILIARY_STREAM,
            feature_names={view:feature_names(view) for view in ('auxiliary','recent','history')},
            knowledge='Timestamp-wise independent Bernoulli p=.25; same selected acquisitions in both profiles and all worlds/mechanisms',
            knowledge_seed='stable_seed(dataset.seed,group_id,causal-knowledge25)',
            knowledge_availability='max(true acquisition, reported time)<=checkpoint; future acquisitions never become visible under negative timestamp jitter',
            noisy_knowledge='Independent Gaussian x/y sigma2m and integer time jitter[-200,200]ms; clipped to public coverage/horizon; causal deduplication',
            public_availability='Whole immutable releases with logical sealed_at_ms<=checkpoint; recent arrival block (checkpoint-1000,checkpoint]; no partial support clipping',
            fitting='Separate checkpoint models; base TRAIN groups only; no test selection/refitting/recalibration',
            calibration='One threshold per stream/view/profile/family, maximize CAL TPR subject to empirical ever-positive CAL FPR<=.1 on max checkpoint score',
            attack_families=list(families),attack_parameters=dict(logistic=LOGISTIC_PARAMETERS,hist_gradient_boosting=HGB_PARAMETERS),
            independent_groups=dict(Counter(c['split'] for c in data['cases'])),test_cohorts=dict(Counter(c['distribution'] for c in data['cases'] if c['split']=='test')),
            bootstrap_repeats=bootstrap_repeats,uncertainty='Scenario-stratified paired source-group bootstrap conditional on fitted models and one frozen threshold',
            paired_contrasts='History minus recent, and each view minus auxiliary-only: max-over-checkpoints score AUC on the same held-out source groups',
            deadline_utility='Held-out TEST worlds only; fixed10m/1000ms queries; lags0/200/500/1000ms; primary query_end+maxlag<horizon; EOF boundary/censoring separate; common/local matched-query errors on identical support',
            interpretation=['The six fixed looks are one predeclared attack, not six independent chances at FPR .1',
                'Global threshold is calibrated separately per family/profile; no TEST-best family/checkpoint selection',
                'Empirical CAL FPR is not a confidence-bound or deployment guarantee',
                'Cumulative alarm TPR/FPR are monotone; restricted learned-score AUC need not be',
                'Fixed full horizon metadata/normalization is known; the final checkpoint includes EOF behavior',
                'Logical sealing is an availability proxy; no measured transport/online-speed claim',
                'No sensitive-attribute, optimal-attack, formal anonymity or differential-privacy guarantee'])
        write_json(output/'protocol.json',protocol)
        manifest=dict(schema='ump.privacy-prefix-manifest.v1',status='running',protocol_sha256=digest(output/'protocol.json'))
        _replace_json(output/'manifest.json',manifest)
    except Exception as error:
        _mark_failure(output,manifest,error)
        raise
    features=defaultdict(list);online_rows=defaultdict(list);online_pairs=defaultdict(list);event_manifest=[];generated_hashes={}
    try:
        from online_occupancy import (compact, evaluate as evaluate_online, rollup as rollup_online,
                                      paired_rollup, pool_paired_rollups)
        for number,case in enumerate(data['cases'],1):
            trace=read_json(relative_file(source['dataset'],case['target_trace']))
            seed=stable_seed(data['seed'],case['group_id'],'causal-knowledge25')
            events={profile:knowledge_events(trace,data['coverage'],horizon,seed,profile) for profile in PROFILES}
            event_path=output/'knowledge'/(case['case_id']+'.json')
            write_json(event_path,dict(group_id=case['group_id'],profiles=events))
            event_manifest.append(dict(group_id=case['group_id'],sha256=digest(event_path)))
            generated_hashes[str(event_path)]=digest(event_path)
            auxiliary_reference={}
            for world,label in (('present',1),('absent',0)):
                replay=read_json(relative_file(source['dataset'],case[world+'_input']))
                metadata=dict(group_id=case['group_id'],scenario=case['scenario'],distribution=case['distribution'],split=case['split'],label=label)
                world_online={}
                for variant in VARIANTS:
                    public=read_json(relative_file(source['study'],public_relative(case,world,variant)))
                    if (public.get('coverage')!=data['coverage'] or public.get('end_ms')!=horizon
                            or public.get('sampling_period_ms')!=data['sampling_period_ms']):
                        raise ValueError('Public transcript differs from declared fixed source context')
                    if case['split']=='test':
                        world_online[variant]=evaluate_online(replay,public)
                        online_rows[variant].append(dict(world=world,**metadata,evaluation=compact(world_online[variant])))
                    feature_grid=feature_views_many(public,events,checkpoints)
                    for profile in PROFILES:
                        for t in checkpoints:
                            views=feature_grid[profile][t]
                            auxiliary=views['auxiliary'];key=profile,t
                            if key in auxiliary_reference and auxiliary_reference[key]!=auxiliary:
                                raise ValueError('Auxiliary-only features depend on stream or membership label')
                            auxiliary_reference[key]=auxiliary
                            if variant==VARIANTS[0]:features[(AUXILIARY_STREAM,'auxiliary',profile,t)].append(dict(**metadata,features=auxiliary))
                            for view in VIEWS:features[(variant,view,profile,t)].append(dict(**metadata,features=views[view]))
                if world_online:
                    for priority in ('temporal_first','spatial_first'):
                        common,local='common_'+priority,'local_'+priority
                        online_pairs[priority].append(dict(world=world,**metadata,
                            evaluation=paired_rollup([(world_online[common],world_online[local])])))
                del world_online
            print(f'Featurized causal group {number}/{len(data["cases"])} ({case["split"]}, {case["distribution"]})',flush=True)
        for (stream,view,profile,t),rows in features.items():
            if stream==AUXILIARY_STREAM:_same_pair_features(rows)
        series_keys=sorted({key[:3] for key in features})
        attacks=[];score_paths={};calibration_paths={};model_count=0
        for stream,view,profile in series_keys:
            for family in families:
                key=stream,view,profile,family
                paths_by_split=defaultdict(dict);models=[]
                for index,t in enumerate(checkpoints):
                    rows=features[(stream,view,profile,t)]
                    train=[r for r in rows if r['split']=='train' and r['distribution']=='base']
                    calibration=[r for r in rows if r['split']=='calibration' and r['distribution']=='base']
                    model_id=hashlib.sha256(f'{stream}:{view}:{profile}:{family}:{t}'.encode()).hexdigest()[:24]
                    fitted=fit_attack([r['features'] for r in train],[r['label'] for r in train],family,
                        model_path=output/'models'/(model_id+'.joblib') if family=='hist_gradient_boosting' else None)
                    cal_rows=[]
                    for partition,selected in [('calibration',calibration)]+[(d,[r for r in rows if r['split']=='test' and r['distribution']==d]) for d in DISTRIBUTIONS]:
                        scores=predict_attack(fitted,[r['features'] for r in selected])
                        for row,score in zip(selected,scores):
                            identity=row['group_id'],row['label']
                            if identity not in paths_by_split[partition]:
                                paths_by_split[partition][identity]={k:row[k] for k in ('group_id','scenario','distribution','label')} | dict(scores=[])
                            paths_by_split[partition][identity]['scores'].append(score)
                            if partition=='calibration':cal_rows.append({k:row[k] for k in ('group_id','scenario','distribution','label')} | dict(score=score))
                    model_json=output/'models'/(model_id+'.json')
                    write_json(model_json,dict(metadata=fitted,checkpoint_ms=t,calibration_scores=cal_rows))
                    generated_hashes[str(model_json)]=digest(model_json)
                    if family=='hist_gradient_boosting':generated_hashes[fitted['model_path']]=fitted['model_sha256']
                    models.append(dict(checkpoint_ms=t,model_id=model_id,metadata=fitted));model_count+=1
                calibration=list(paths_by_split['calibration'].values())
                calibrated=calibrate_paths(calibration,checkpoints)
                calibration_paths[key]=calibration
                record=dict(stream=stream,view=view,knowledge_profile=profile,attack_family=family,
                    feature_count=len(feature_names(view)),training_groups=len(train)//2,calibration_groups=len(calibration)//2,
                    checkpoint_models=models,calibration=calibrated,test_by_distribution={})
                for distribution in DISTRIBUTIONS:
                    paths=list(paths_by_split[distribution].values());score_paths[(*key,distribution)]=paths
                    record['test_by_distribution'][distribution]=assess_paths(paths,checkpoints,calibrated['threshold'],bootstrap_repeats,(*key,distribution))
                attacks.append(record)
                print(f'Fitted causal path {stream}/{view}/{profile}/{family}',flush=True)
        for attack in attacks:
            stream,view,profile,family=(attack[k] for k in ('stream','view','knowledge_profile','attack_family'))
            if stream==AUXILIARY_STREAM:continue
            for distribution,assessment in attack['test_by_distribution'].items():
                rows=_path_rows(score_paths[(stream,view,profile,family,distribution)],checkpoints)
                auxiliary=_path_rows(score_paths[(AUXILIARY_STREAM,'auxiliary',profile,family,distribution)],checkpoints)
                assessment['paired_vs_auxiliary']=paired_auc_difference(rows,auxiliary,bootstrap_repeats,
                    stable_seed('prefix-paired-aux',stream,view,profile,family,distribution))
                if view=='history':
                    recent=_path_rows(score_paths[(stream,'recent',profile,family,distribution)],checkpoints)
                    assessment['paired_history_minus_recent']=paired_auc_difference(rows,recent,bootstrap_repeats,
                        stable_seed('prefix-paired-history',stream,profile,family,distribution))
        report=dict(schema='ump.privacy-prefix-report.v1',status='pending_validation',classification='private_research_bundle',
            protocol_sha256=manifest['protocol_sha256'],checkpoints_ms=list(checkpoints),interior_checkpoints_ms=list(checkpoints[:-1]),eof_checkpoint_ms=horizon,
            attacks=attacks,independent_source_groups=len(data['cases']),model_count=model_count,auxiliary_world_invariance_verified=True,
            calibration_target_ever_positive_fpr=.1,membership_prior=.5,test_cohorts_independent=True,
            online_utility={distribution:{variant:rollup_online([r['evaluation'] for r in rows if r['split']=='test' and r['distribution']==distribution])
                for variant,rows in online_rows.items()} for distribution in DISTRIBUTIONS},
            online_matched_utility={distribution:{priority:dict(common_mechanism='common_'+priority,local_mechanism='local_'+priority,
                **pool_paired_rollups([r['evaluation'] for r in rows if r['distribution']==distribution]))
                for priority,rows in online_pairs.items()} for distribution in DISTRIBUTIONS},interpretation=protocol['interpretation'])
        for name,value in [('report.json',report),('features-private.json',[dict(key=list(k),rows=v) for k,v in sorted(features.items())]),
            ('score-paths-private.json',[dict(key=list(k),calibration_rows=calibration_paths[k],test_by_distribution={d:score_paths[(*k,d)] for d in DISTRIBUTIONS}) for k in sorted(calibration_paths)]),
            ('knowledge-manifest.json',event_manifest),('online-utility-private.json',dict(compact_by_variant=online_rows,paired_by_priority=online_pairs))]:write_json(output/name,value)
        for absolute,expected in source['consumed'].items():
            if digest(Path(absolute))!=expected:raise ValueError('Consumed source artifact changed during analysis: '+absolute)
        for relative,expected in analysis_hashes.items():
            if digest(ROOT/relative)!=expected or digest(output/'source'/relative)!=expected:
                raise ValueError('Analysis source changed during the fixed study: '+relative)
        if digest(output/'protocol.json')!=manifest['protocol_sha256']:raise ValueError('Frozen protocol changed')
        for absolute,expected in generated_hashes.items():
            if digest(Path(absolute))!=expected:raise ValueError('Generated model/knowledge artifact changed: '+absolute)
        for name in ('manifest.json','protocol.json','report.json','dataset-manifest.json'):
            if digest(output/('source-study-'+name))!=source['consumed'][str(source['study']/name)]:
                raise ValueError('Frozen source-study metadata changed: '+name)

        report['status']='complete'
        _replace_json(output/'report.json',report)
        manifest.update(status='complete',completed_utc=datetime.now(timezone.utc).isoformat(),report_sha256=digest(output/'report.json'),
            artifact_sha256={str(p.relative_to(output)):digest(p) for p in output.rglob('*') if p.is_file() and p!=output/'manifest.json'})
        _replace_json(output/'manifest.json',manifest)
    except Exception as error:
        _mark_failure(output,manifest,error)
        raise
    print(f'Completed {model_count} causal checkpoint fits in {len(attacks)} score trajectories: {output}',flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-study',type=Path,required=True)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--checkpoints',type=int,nargs='+',default=list(CHECKPOINTS))
    parser.add_argument('--bootstrap-repeats',type=int,default=400)
    parser.add_argument('--attack-families',nargs='+',choices=FAMILIES,default=list(FAMILIES))
    args=parser.parse_args()
    run_study(args.source_study,args.dataset,args.output,checkpoints=tuple(args.checkpoints),
              bootstrap_repeats=args.bootstrap_repeats,attack_families=tuple(args.attack_families))


if __name__=='__main__':main()
