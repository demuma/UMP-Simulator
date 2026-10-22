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

from coordination_metrics import weighted_distribution
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


def _load_reference(study):
    """Validate only the completed reference mechanism evidence, never its models."""
    study = Path(study).expanduser().resolve(strict=True)
    manifest_path, protocol_path = study/'manifest.json', study/'protocol.json'
    manifest, protocol = read_json(manifest_path), read_json(protocol_path)
    if (manifest.get('status') != 'complete' or protocol.get('status') != 'predeclared'
            or protocol.get('schema') != 'ump.privacy-robustness-protocol.v1'):
        raise ValueError('Reference study must be a completed robustness study')
    if manifest.get('schema') != 'ump.privacy-robustness-manifest.v1':
        raise ValueError('Invalid reference study manifest schema')
    report = read_json(study/'report.json')
    if report.get('schema') != 'ump.privacy-robustness-report.v1' or report.get('status') != 'complete':
        raise ValueError('Reference study report must be complete')
    artifacts = manifest.get('artifact_sha256', {})
    if (report.get('protocol_sha256') != manifest.get('protocol_sha256')
            or digest(protocol_path) != manifest.get('protocol_sha256')
            or artifacts.get('protocol.json') != manifest.get('protocol_sha256')
            or digest(study/'report.json') != manifest.get('report_sha256')
            or artifacts.get('report.json') != manifest.get('report_sha256')):
        raise ValueError('Reference study protocol/report provenance mismatch')
    binary = relative_file(study, 'AggregationReplay.frozen')
    if (digest(binary) != protocol.get('binary_sha256')
            or digest(binary) != manifest.get('binary_sha256')
            or artifacts.get('AggregationReplay.frozen') != protocol.get('binary_sha256')):
        raise ValueError('Reference study binary provenance mismatch')
    sources = protocol.get('source_sha256', {})
    required = {'simulator/src/CellLocalAggregation.cpp', 'simulator/tools/AggregationReplay.cpp',
                'simulator/CMakeLists.txt'}
    if not isinstance(sources, dict) or not required.issubset(sources):
        raise ValueError('Reference study must contain its declared mechanism source snapshot')
    for relative, expected in sources.items():
        if not isinstance(relative,str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Reference source paths must be relative without traversal')
        source = relative_file(study, 'source/'+relative)
        if digest(source) != expected or artifacts.get('source/'+relative) != expected:
            raise ValueError('Reference source provenance mismatch: '+relative)
    return dict(study=study, binary=binary, protocol=protocol,
        manifest_sha256=digest(manifest_path), protocol_sha256=digest(protocol_path),
        report_sha256=digest(study/'report.json'))


def _source_point_ages(replay, result):
    """Exact evaluator-only source age on public spatial/time support."""
    period, depth = replay['sampling_period_ms'], replay['coverage']['leaf_depth']
    active = defaultdict(dict)
    for release in result['releases']:
        for cell in release['cells']:
            first = max(period, ((release['start_ms']+period-1)//period)*period)
            for timestamp in range(first, release['end_ms'], period):
                key = cell['depth'], cell['cell_id']
                if key in active[timestamp]:
                    raise ValueError('Duplicate public support in source-age evaluation')
                active[timestamp][key] = release['sealed_at_ms']
    values = {}
    for batch in replay['batches']:
        timestamp = batch['observed_at_ms']
        support = active.get(timestamp, {})
        for observation in batch['observations']:
            matches = [support[(d, observation['cell_id'] >> (2*(depth-d)))]
                       for d in range(1, depth+1)
                       if (d, observation['cell_id'] >> (2*(depth-d))) in support]
            if len(matches) > 1:
                raise ValueError('Overlapping public support in source-age evaluation')
            if matches:
                key = timestamp, observation['id']
                if key in values or matches[0] < timestamp:
                    raise ValueError('Invalid repeated source point or negative source age')
                values[key] = matches[0]-timestamp
    expected = sum(c['observation_contributions'] for r in result['releases'] for c in r['cells'])
    if len(values) != expected:
        raise ValueError('Public contribution count differs from exact source-age support')
    return values


def _repair_row(replay, reference, repaired, reference_utility, repaired_utility):
    old, new = _source_point_ages(replay, reference), _source_point_ages(replay, repaired)
    shared = old.keys() & new.keys()
    matched = matched_errors(reference_utility, repaired_utility)
    return dict(input_contributions=sum(len(b['observations']) for b in replay['batches']),
        reference_released=len(old), repaired_released=len(new),
        gained=len(new.keys()-old.keys()), lost=len(old.keys()-new.keys()), shared_count=len(shared),
        reference_queries=reference_utility['summary']['reference_queries'],
        reference_answered=reference_utility['summary']['answered_queries'],
        repaired_answered=repaired_utility['summary']['answered_queries'],
        matched_queries=matched['scored_queries'], reference_matched_mae=matched['common_mae'],
        repaired_matched_mae=matched['local_mae'],
        age_histograms={
            'reference_retained_age_ms':dict(Counter(old.values())),
            'repaired_retained_age_ms':dict(Counter(new.values())),
            'reference_shared_age_ms':dict(Counter(old[k] for k in shared)),
            'repaired_shared_age_ms':dict(Counter(new[k] for k in shared))})


def _repair_rollup(rows):
    inputs = sum(r['input_contributions'] for r in rows)
    old, new = (sum(r[key] for r in rows) for key in ('reference_released','repaired_released'))
    queries = sum(r['reference_queries'] for r in rows)
    matched = sum(r['matched_queries'] for r in rows)
    histograms = defaultdict(Counter)
    for row in rows:
        for name, histogram in row['age_histograms'].items():
            histograms[name].update({int(age):count for age,count in histogram.items()})
    ages = {name:weighted_distribution(hist.items()) for name,hist in histograms.items()}
    for distribution in ages.values():
        distribution['distinct_age_values'] = distribution['count']
        distribution['count'] = distribution['total_weight']
    shared_count = sum(r['shared_count'] for r in rows)
    return dict(case_worlds=len(rows), input_contributions=inputs,
        reference_released=old, repaired_released=new,
        reference_retention=old/inputs if inputs else None,
        repaired_retention=new/inputs if inputs else None,
        delta_retention_pp=100*(new-old)/inputs if inputs else None,
        gained=sum(r['gained'] for r in rows),lost=sum(r['lost'] for r in rows),
        shared_count=shared_count,reference_queries=queries,
        reference_coverage=sum(r['reference_answered'] for r in rows)/queries if queries else None,
        repaired_coverage=sum(r['repaired_answered'] for r in rows)/queries if queries else None,
        matched_queries=matched,
        reference_matched_mae=sum((r['reference_matched_mae'] or 0)*r['matched_queries'] for r in rows)/matched if matched else None,
        repaired_matched_mae=sum((r['repaired_matched_mae'] or 0)*r['matched_queries'] for r in rows)/matched if matched else None,
        **ages,shared_mean_age_delta_ms=(ages['repaired_shared_age_ms']['mean']-ages['reference_shared_age_ms']['mean']
                                       if shared_count else None),
        age_scope='Exact retained source observations; same-point intersection for shared ages; logical sealing, not recipient latency')


def run_study(dataset, output, binary, *, bootstrap_repeats=400, attack_families=FAMILIES,
              reference_study=None):
    if isinstance(bootstrap_repeats, bool) or not isinstance(bootstrap_repeats, int) or bootstrap_repeats < 0:
        raise ValueError('bootstrap_repeats must be a nonnegative integer')
    families = tuple(attack_families)
    if not families or len(set(families)) != len(families) or set(families) - set(FAMILIES):
        raise ValueError('Select unique known attack families')
    if 'hist_gradient_boosting' in families:
        _optional_libraries()  # Dependency/version failure precedes output creation.
    dataset, manifest = _load(dataset)
    reference = _load_reference(reference_study) if reference_study is not None else None
    variant_specs = list(ROBUST_VARIANTS)
    if reference:
        variant_specs += [('reference_'+name, mode, depth, window, coordination)
                          for name,mode,depth,window,coordination in ROBUST_VARIANTS if name.startswith('local_')]
    binary = Path(binary).resolve(strict=True)
    raw_output = Path(output).expanduser()
    if raw_output.exists() or raw_output.is_symlink():
        raise FileExistsError('Study output already exists')
    output = raw_output.resolve()
    if reference and (output == reference['study'] or reference['study'] in output.parents or output in reference['study'].parents):
        raise ValueError('Reference study and output must be separate non-nested directories')
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
    reference_frozen = None
    if reference:
        reference_frozen = output/'AggregationReplay.reference.frozen'
        shutil.copy2(reference['binary'], reference_frozen)
        reference_frozen.chmod(0o500)
        for name in ('manifest.json','protocol.json','report.json'):
            shutil.copyfile(reference['study']/name, output/('reference-'+name))
        for relative, expected in reference['protocol']['source_sha256'].items():
            destination = output/'reference-source'/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(relative_file(reference['study'],'source/'+relative),destination)
            if digest(destination) != expected:
                raise ValueError('Reference source changed while freezing')
        if digest(reference_frozen) != reference['protocol']['binary_sha256']:
            raise ValueError('Reference executable changed while freezing')
    policies = {}
    for variant in variant_specs:
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
        source_sha256=source_hashes, variants=variant_specs,
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
    if reference:
        protocol['reference_study'] = dict(path=str(reference['study']),
            manifest_sha256=reference['manifest_sha256'],protocol_sha256=reference['protocol_sha256'],
            report_sha256=reference['report_sha256'],binary_sha256=reference['protocol']['binary_sha256'],
            source_sha256=reference['protocol']['source_sha256'],
            controls='First IN source: old/new fixed20m1000ms and both common priorities must match scientifically',
            primary_contrast='Repaired local minus frozen reference local AUC within cohort, priority, family and knowledge profile',
            fitting='A separate adaptive attack fitted and calibrated for every mechanism; no old model deserialization')
        protocol['utility'] += '; reference/repaired matched query support and exact same-source-point sealing ages'
    write_json(output/'dataset-manifest.json', manifest)
    write_json(output/'protocol.json', protocol)
    running = dict(schema='ump.privacy-robustness-manifest.v1', status='running',
        protocol_sha256=digest(output/'protocol.json'), dataset_manifest_sha256=protocol['dataset_manifest_sha256'],
        binary_sha256=protocol['binary_sha256'])
    write_json(output/'manifest.json', running)
    feature_rows, utility_rows = defaultdict(list), defaultdict(list)
    commands, audit_records, repeats, auxiliary_records = [], [], [], []
    reference_controls, repair_rows = [], []
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
                for name, mode, depth, window, coordination in variant_specs:
                    artifact = hashlib.sha256(f'{case["case_id"]}:{world}:{name}'.encode()).hexdigest()[:24]
                    destination = output/'raw'/(artifact+'.json')
                    policy_path = output/'policies'/(name+'.json')
                    mechanism_binary = reference_frozen if name.startswith('reference_') else frozen
                    result, command = run_variant(mechanism_binary,source,policy_path,destination,mode,depth,window)
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
                        repeated,_ = run_variant(mechanism_binary,source,policy_path,repeat_path,mode,depth,window)
                        if scientific_result(repeated) != scientific_result(result):
                            raise ValueError('Scientific replay is nondeterministic')
                        repeat_path.unlink(); repeats.append(name)
                if reference and case_number == 1 and world == 'present':
                    for name,mode,depth,window,_ in ROBUST_VARIANTS:
                        if name.startswith('local_'): continue
                        path = output/'raw'/('reference-control-'+name+'.json')
                        control,command = run_variant(reference_frozen,source,output/'policies'/(name+'.json'),path,mode,depth,window)
                        if scientific_result(control) != scientific_result(results[name]):
                            raise ValueError('Reference/new shared mechanism differs scientifically: '+name)
                        audit = validate_result(replay,policies[name],control)
                        if not audit['valid']: raise ValueError('Reference control audit failed')
                        reference_controls.append(dict(variant=name,identical=True,audit_valid=True,command=command,result_sha256=digest(path)))
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
                if reference:
                    for priority in ('temporal_first','spatial_first'):
                        old,new = 'reference_local_'+priority,'local_'+priority
                        repair_rows.append(dict(group_id=case['group_id'],split=case['split'],
                            distribution=case['distribution'],scenario=case['scenario'],world=world,priority=priority,
                            **_repair_row(replay,results[old],results[new],utilities[old],utilities[new])))
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
        if reference:
            for record in attacks:
                if not record['variant'].startswith('local_'): continue
                for distribution,assessment in record['test_by_distribution'].items():
                    key = (record['variant'],record['knowledge_profile'],record['attack_family'],distribution)
                    baseline = ('reference_'+key[0],*key[1:])
                    assessment['paired_vs_reference_local'] = paired_auc_difference(
                        predictions[key],predictions[baseline],bootstrap_repeats,
                        stable_seed('paired-repair',*key[1:]))
            if digest(reference_frozen) != protocol['reference_study']['binary_sha256']:
                raise ValueError('Frozen reference executable changed')
            if any(digest(output/'reference-source'/relative)!=expected
                   for relative,expected in reference['protocol']['source_sha256'].items()):
                raise ValueError('Frozen reference source changed')
            for name,expected in [('manifest.json',reference['manifest_sha256']),
                                  ('protocol.json',reference['protocol_sha256']),('report.json',reference['report_sha256'])]:
                if digest(output/('reference-'+name)) != expected:
                    raise ValueError('Frozen reference metadata changed')
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
        if reference:
            report['reference_study'] = protocol['reference_study']
            report['independent_validation']['shared_mechanism_reference_controls'] = reference_controls
            report['repair_comparison_by_distribution'] = {
                distribution:{priority:_repair_rollup([r for r in repair_rows if r['split']=='test'
                    and r['distribution']==distribution and r['priority']==priority])
                    for priority in ('temporal_first','spatial_first')} for distribution in DISTRIBUTIONS}
            write_json(output/'repair-pairs-private.json',repair_rows)
            write_json(output/'reference-controls.json',reference_controls)
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
    parser.add_argument('--reference-study',type=Path,help='Completed robustness bundle supplying the frozen old local mechanism and source provenance')
    parser.add_argument('--bootstrap-repeats',type=int,default=400)
    parser.add_argument('--attack-families',nargs='+',choices=FAMILIES,default=list(FAMILIES))
    args = parser.parse_args()
    run_study(args.dataset,args.output,args.binary,bootstrap_repeats=args.bootstrap_repeats,
              attack_families=tuple(args.attack_families),reference_study=args.reference_study)


if __name__=='__main__': main()
