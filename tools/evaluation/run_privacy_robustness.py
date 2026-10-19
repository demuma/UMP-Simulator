#!/usr/bin/env python3
"""New-data privacy stress test: longer paths, uncertain knowledge and density shift.

Base training/calibration groups fit every model and threshold once. Independent
base and shifted test cohorts remain separate; private scenario/distribution labels
are evaluation metadata, never prediction features. All outputs stay private.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import shutil
import sys
from datetime import datetime, timezone

from empirical_privacy import attack_metrics, calibrate_threshold, export_public, feature_names, feature_vector
from occupancy import evaluate
from oracle import validate_result
from privacy_dataset import validate_dataset, target_knowledge, noisy_target_knowledge
from robustness_attacks import FAMILIES, HGB_PARAMETERS, LOGISTIC_PARAMETERS, fit_attack, predict_attack, _optional_libraries
from run_comparison import digest, git_state, run_variant, scientific_result, write_json
from run_coordination_study import STUDY_VARIANTS, effective_policy, matched_errors, source_files
from run_privacy_study import (CONTROLS, control_result, read_json, relative_file, stable_seed,
                               clustered_intervals, paired_auc_difference, utility_rollup)

ROOT = Path(__file__).resolve().parents[2]
ROBUST_VARIANTS = [STUDY_VARIANTS[3]] + STUDY_VARIANTS[5:]
PROFILES = ('exact_25', 'noisy_25')
DISTRIBUTIONS = ('base', 'background_density_shift')


def _load(dataset):
    dataset = Path(dataset).resolve(strict=True)
    manifest = read_json(dataset / 'manifest.json')
    if manifest.get('schema') != 'ump.privacy-dataset.v2' or manifest.get('generator') != 'long_corridors_v2':
        raise ValueError('This study requires a new v2 long-corridor robustness dataset')
    validate_dataset(manifest, dataset)
    for split in ('train', 'calibration'):
        cases = [c for c in manifest['cases'] if c['split'] == split]
        if len(cases) < 2 or any(c['distribution'] != 'base' for c in cases):
            raise ValueError('Training and calibration need independent base-only groups')
    for distribution in DISTRIBUTIONS:
        if sum(c['split'] == 'test' and c['distribution'] == distribution for c in manifest['cases']) < 2:
            raise ValueError('Each independent test distribution needs at least two groups')
    return dataset, manifest


def _pooled_utility(rows):
    summary = utility_rollup(rows)
    for key in ('mean_release_age_ms', 'p95_release_age_ms', 'release_count'):
        summary.pop(key)
    summary['weighting'] = 'Pooled fixed queries and source contributions; no release-batching age comparison'
    return summary


def run_study(dataset, output, binary, *, bootstrap_repeats=400, attack_families=FAMILIES):
    if isinstance(bootstrap_repeats, bool) or not isinstance(bootstrap_repeats, int) or bootstrap_repeats < 0:
        raise ValueError('bootstrap_repeats must be a nonnegative integer')
    families = tuple(attack_families)
    if not families or len(set(families)) != len(families) or set(families) - set(FAMILIES):
        raise ValueError('Select unique known attack families')
    if 'hist_gradient_boosting' in families:
        _optional_libraries()  # Dependency/version failure precedes output creation.
    dataset, manifest = _load(dataset)
    binary = Path(binary).resolve(strict=True)
    raw_output = Path(output).expanduser()
    if raw_output.exists() or raw_output.is_symlink():
        raise FileExistsError('Study output already exists')
    output = raw_output.resolve()
    if output == dataset or dataset in output.parents or output in dataset.parents:
        raise ValueError('Dataset and output must be separate non-nested directories')
    config = read_json(relative_file(dataset, manifest['policy']))
    paths = source_files(ROOT) + sorted((ROOT / 'tools/evaluation').glob('requirements-robustness*.txt'))
    source_hashes = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for directory in ('raw', 'public', 'models', 'policies', 'auxiliary', 'source'):
        (output / directory).mkdir(mode=0o700)
    frozen = output / 'AggregationReplay.frozen'
    shutil.copy2(binary, frozen)
    frozen.chmod(0o500)
    if digest(frozen) != digest(binary):
        raise ValueError('Replay executable changed while freezing it')
    for relative, expected in source_hashes.items():
        destination = output / 'source' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
        if digest(destination) != expected:
            raise ValueError('Source changed while freezing: ' + relative)
    policies = {}
    for variant in ROBUST_VARIANTS:
        policies[variant[0]] = effective_policy(config, variant)
        write_json(output / 'policies' / (variant[0] + '.json'), policies[variant[0]])
    environment = {}
    for package in ('scikit-learn', 'numpy', 'scipy', 'joblib', 'threadpoolctl'):
        try: environment[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: environment[package] = None
    protocol = dict(schema='ump.privacy-robustness-protocol.v1', status='predeclared', classification='private_predeclared_protocol',
        created_utc=datetime.now(timezone.utc).isoformat(), git=git_state(ROOT), python=sys.version,
        platform=platform.platform(), packages=environment,
        dataset_manifest_sha256=digest(dataset / 'manifest.json'), binary_sha256=digest(frozen),
        source_sha256=source_hashes, variants=ROBUST_VARIANTS,
        effective_policy_sha256={name: digest(output/'policies'/(name+'.json')) for name in policies},
        independent_groups=dict(Counter(c['split'] for c in manifest['cases'])),
        test_distributions=dict(Counter(c['distribution'] for c in manifest['cases'] if c['split']=='test')),
        source_horizon_ms=manifest['end_ms'], protected_unit='whole recorded candidate contribution in this declared horizon',
        secret='source contribution inclusion; physical candidate exists in both worlds',
        profiles=dict(exact_25=dict(fraction=.25, spatial_sigma_m=0, temporal_jitter_ms=0),
                      noisy_25=dict(fraction=.25, spatial_sigma_m=2, temporal_jitter_ms=200)),
        knowledge='Same sampled indices; noisy coordinates/times generated once per group and reused for both labels/all mechanisms',
        knowledge_boundary_rule='Clamp coordinates to half-open public coverage and time to [1,end_ms-1]; recompute cell IDs, remove exact duplicate time/x/y triples, retain off-cadence observations',
        feature_set='counts_geometry_time', feature_names=feature_names(True),
        attack_families=families, attack_parameters=dict(logistic=LOGISTIC_PARAMETERS, hist_gradient_boosting=HGB_PARAMETERS),
        fitting='Only base training groups; no test-driven model/feature/score-direction selection',
        calibration='Base calibration groups only; maximize TPR with empirical FPR<=0.1; one frozen threshold per model/profile/mechanism',
        shifted_test='Background density x1.5; independent test groups; candidate distribution unchanged; no refitting or recalibration',
        bootstrap_repeats=bootstrap_repeats,
        uncertainty='Scenario-stratified paired source-group bootstrap separately in each test distribution, frozen models/thresholds',
        utility='Public-only retrospective 10-m/1000-ms query with unknown absent support, exact source retention, common/local matched support',
        controls=CONTROLS, execution='Serial mechanisms; offline immediate sink ACK; no online latency claim',
        interpretation=['A different longer protected unit, not a causal comparison with the old four-second test',
            'Density-shift and base test cohorts are independent; no cross-cohort pairing',
            'Coordinate/time noise is auxiliary-knowledge uncertainty, not a noisy privacy mechanism',
            'HGB tests nonlinear interactions within the same fixed31features, not every possible attack',
            'No sensitive-attribute, formal anonymity or differential-privacy guarantee'])
    write_json(output/'dataset-manifest.json', manifest)
    write_json(output/'protocol.json', protocol)
    running = dict(schema='ump.privacy-robustness-manifest.v1', status='running',
        protocol_sha256=digest(output/'protocol.json'), dataset_manifest_sha256=protocol['dataset_manifest_sha256'],
        binary_sha256=protocol['binary_sha256'])
    write_json(output/'manifest.json', running)
    feature_rows, utility_rows = defaultdict(list), defaultdict(list)
    commands, audit_records, repeats, auxiliary_records = [], [], [], []
    try:
        for case_number, case in enumerate(manifest['cases'], 1):
            trace_path = relative_file(dataset, case['target_trace'])
            if digest(trace_path) != case['sha256']['target_trace']:
                raise ValueError('Frozen auxiliary trace changed')
            trace = read_json(trace_path)
            knowledge_seed = stable_seed(manifest['seed'], case['group_id'], 'knowledge25')
            exact = target_knowledge(trace, .25, knowledge_seed)
            noisy = noisy_target_knowledge(trace, .25, knowledge_seed, spatial_sigma_m=2,
                                           temporal_jitter_ms=200, end_ms=manifest['end_ms'])
            knowledge = dict(exact_25=exact, noisy_25=noisy)
            auxiliary = dict(group_id=case['group_id'], split=case['split'], distribution=case['distribution'],
                profiles=knowledge, noise_note='Off-cadence uncertain timestamps and clamping are intentional; private points never filled from GT')
            auxiliary_path = output/'auxiliary'/(case['case_id']+'.json')
            write_json(auxiliary_path, auxiliary)
            auxiliary_records.append(dict(group_id=case['group_id'], sha256=digest(auxiliary_path),
                exact_points=len(exact), noisy_points=len(noisy), deduplicated_points=len(exact)-len(noisy),
                final_boundary_points=sum(point['observed_at_ms'] in (1, manifest['end_ms']-1)
                    or point['x'] in (manifest['coverage']['x'], math.nextafter(manifest['coverage']['x']+manifest['coverage']['width'], -math.inf))
                    or point['y'] in (manifest['coverage']['y'], math.nextafter(manifest['coverage']['y']+manifest['coverage']['height'], -math.inf))
                    for point in noisy), boundary_count_note='Final boundary incidence, not an inferred number of clamping operations'))
            for world, label in (('present',1), ('absent',0)):
                source = relative_file(dataset, case[world+'_input'])
                if digest(source) != case['sha256'][world+'_input']:
                    raise ValueError('Frozen input changed')
                replay, results, utilities = read_json(source), {}, {}
                for name, mode, depth, window, coordination in ROBUST_VARIANTS:
                    artifact = hashlib.sha256(f'{case["case_id"]}:{world}:{name}'.encode()).hexdigest()[:24]
                    destination = output/'raw'/(artifact+'.json')
                    policy_path = output/'policies'/(name+'.json')
                    result, command = run_variant(frozen,source,policy_path,destination,mode,depth,window)
                    audit = validate_result(replay, policies[name], result)
                    audit_records.append(dict(case_id=case['case_id'], world=world, variant=name, **audit))
                    if not audit['valid']:
                        write_json(output/'oracle-failure.json',audit_records[-1])
                        raise ValueError('Independent policy/ownership audit failed')
                    commands.append(dict(case_id=case['case_id'],world=world,variant=name,command=command,
                        input_sha256=digest(source),policy_sha256=digest(policy_path),result_sha256=digest(destination)))
                    results[name] = result
                    if case_number == 1 and world == 'present' and mode in ('temporal_first','spatial_first'):
                        repeat_path = output/'raw'/'repeat.json'
                        repeated,_ = run_variant(frozen,source,policy_path,repeat_path,mode,depth,window)
                        if scientific_result(repeated) != scientific_result(result):
                            raise ValueError('Scientific replay is nondeterministic')
                        repeat_path.unlink(); repeats.append(name)
                if digest(source) != case['sha256'][world+'_input']:
                    raise ValueError('Frozen input changed during replay')
                for name in CONTROLS: results[name] = control_result(replay,name)
                for name,result in results.items():
                    public = export_public(result)
                    artifact = hashlib.sha256(f'{case["case_id"]}:{world}:{name}'.encode()).hexdigest()[:24]
                    write_json(output/'public'/(artifact+'.json'),public)
                    utilities[name] = evaluate(replay,result)
                    for profile,known in knowledge.items():
                        feature_rows[(name,profile)].append(dict(group_id=case['group_id'],case_id=case['case_id'],
                            split=case['split'],distribution=case['distribution'],scenario=case['scenario'],label=label,
                            features=feature_vector(public,known,include_geometry=True)))
                paired_support = {}
                for priority in ('temporal_first','spatial_first'):
                    a,b = 'common_'+priority,'local_'+priority
                    shared = matched_errors(utilities[a],utilities[b])
                    paired_support[a] = shared['scored_queries'],shared['common_mae']
                    paired_support[b] = shared['scored_queries'],shared['local_mae']
                for name,utility in utilities.items():
                    result = results[name]
                    count,mae = paired_support.get(name,(0,None))
                    utility_rows[name].append(dict(group_id=case['group_id'],split=case['split'],
                        distribution=case['distribution'],scenario=case['scenario'],world=world,**utility['summary'],
                        input_contributions=sum(len(batch['observations']) for batch in replay['batches']),
                        released_contributions=sum(cell['observation_contributions'] for release in result['releases'] for cell in release['cells']),
                        release_ages_ms=[],paired_scored_queries=count,paired_support_mae=mae))
            print(f'Validated group {case_number}/{len(manifest["cases"])} ({case["split"]}, {case["distribution"]}, {case["scenario"]})',flush=True)
        attacks, predictions = [], {}
        for (name,profile), rows in sorted(feature_rows.items()):
            train = [row for row in rows if row['split']=='train' and row['distribution']=='base']
            calibration = [row for row in rows if row['split']=='calibration' and row['distribution']=='base']
            for family in families:
                model_id = hashlib.sha256(f'{name}:{profile}:{family}'.encode()).hexdigest()[:24]
                fitted = fit_attack([r['features'] for r in train],[r['label'] for r in train],family,
                                    model_path=output/'models'/(model_id+'.joblib') if family=='hist_gradient_boosting' else None)
                cal_scores = predict_attack(fitted,[r['features'] for r in calibration])
                calibrated = calibrate_threshold(cal_scores,[r['label'] for r in calibration],target_fpr=.1)
                write_json(output/'models'/(model_id+'.json'),dict(metadata=fitted,calibration=calibrated))
                record = dict(variant=name,knowledge_profile=profile,attack_family=family,feature_count=31,
                    training_groups=len(train)//2,calibration_groups=len(calibration)//2,
                    model_metadata=fitted,calibration=calibrated,test_by_distribution={})
                for distribution in DISTRIBUTIONS:
                    test = [r for r in rows if r['split']=='test' and r['distribution']==distribution]
                    scores = predict_attack(fitted,[r['features'] for r in test])
                    test_rows = [dict(group_id=row['group_id'],scenario=row['scenario'],distribution=distribution,label=row['label'],score=score)
                                 for row,score in zip(test,scores)]
                    predictions[(name,profile,family,distribution)] = test_rows
                    record['test_by_distribution'][distribution] = dict(test_groups=len(test)//2,
                        test=attack_metrics(scores,[r['label'] for r in test],calibrated['threshold']),
                        uncertainty=clustered_intervals(test_rows,calibrated['threshold'],bootstrap_repeats,
                            stable_seed('robust',name,profile,family,distribution)),
                        by_scenario={scenario:attack_metrics([r['score'] for r in test_rows if r['scenario']==scenario],
                            [r['label'] for r in test_rows if r['scenario']==scenario],calibrated['threshold'])
                            for scenario in sorted({r['scenario'] for r in test_rows})})
                attacks.append(record)
                print(f'Fitted {name}/{profile}/{family}; evaluated both frozen test cohorts',flush=True)
        for record in attacks:
            if not record['variant'].startswith('local_'): continue
            for distribution,assessment in record['test_by_distribution'].items():
                key = (record['variant'],record['knowledge_profile'],record['attack_family'],distribution)
                baseline = ('common_'+record['variant'][len('local_'):],*key[1:])
                assessment['paired_vs_common'] = paired_auc_difference(predictions[key],predictions[baseline],
                    bootstrap_repeats,stable_seed('paired-robust',*key[1:]))
        if digest(frozen)!=protocol['binary_sha256'] or digest(dataset/'manifest.json')!=protocol['dataset_manifest_sha256'] \
                or digest(output/'protocol.json')!=running['protocol_sha256']:
            raise ValueError('Frozen protocol/data/executable changed')
        if any(digest(ROOT/relative)!=expected for relative,expected in source_hashes.items()):
            raise ValueError('Source changed during the fixed study')
        validate_dataset(manifest, dataset)
        if any(digest(output/'policies'/(name+'.json')) != expected
               for name, expected in protocol['effective_policy_sha256'].items()):
            raise ValueError('Frozen effective policy changed')
        report = dict(schema='ump.privacy-robustness-report.v1',status='complete',classification='private_research_bundle',
            protocol_sha256=running['protocol_sha256'],attacks=attacks,
            utility_by_distribution={distribution:{name:_pooled_utility([r for r in rows if r['split']=='test' and r['distribution']==distribution])
                for name,rows in utility_rows.items()} for distribution in DISTRIBUTIONS},
            independent_validation=dict(checks=len(audit_records),all_valid=True,deterministic_repeats=repeats,
                released_cell_count=sum(a['released_cell_count'] for a in audit_records)),
            interpretation=protocol['interpretation'],membership_prior=.5,
            test_cohorts_independent=True,calibration_target_fpr=.1,auxiliary_world_invariance_verified=True)
        for filename,value in [('report.json',report),('commands.json',commands),('oracle-validation.json',audit_records),
            ('auxiliary-manifest.json',auxiliary_records),('features-private.json',[dict(key=list(k),rows=v) for k,v in sorted(feature_rows.items())]),
            ('test-predictions-private.json',[dict(key=list(k),rows=v) for k,v in sorted(predictions.items())]),('utility-private.json',utility_rows)]:
            write_json(output/filename,value)
        running.update(status='complete',completed_utc=datetime.now(timezone.utc).isoformat(),report_sha256=digest(output/'report.json'),
            artifact_sha256={str(p.relative_to(output)):digest(p) for p in output.rglob('*') if p.is_file() and p!=output/'manifest.json'})
        (output/'manifest.json').write_text(json.dumps(running,indent=2,allow_nan=False)+'\n')
    except Exception as error:
        write_json(output/'failure.json',dict(error_type=type(error).__name__,message=str(error)))
        raise
    print(f'Completed {len(audit_records)} audited replays and {len(attacks)} frozen attacks: {output}',flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'simulator/build/AggregationReplay')
    parser.add_argument('--bootstrap-repeats',type=int,default=400)
    parser.add_argument('--attack-families',nargs='+',choices=FAMILIES,default=list(FAMILIES))
    args = parser.parse_args()
    run_study(args.dataset,args.output,args.binary,bootstrap_repeats=args.bootstrap_repeats,
              attack_families=tuple(args.attack_families))


if __name__=='__main__': main()
