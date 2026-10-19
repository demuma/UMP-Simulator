#!/usr/bin/env python3
"""Run a private, grouped, held-out membership benchmark on the real replay core.

This evaluates source-contribution membership on a synthetic population, not physical
presence. All IN/OUT pairs and aggregation variants share one split. Only exported
recipient transcripts and declared target knowledge enter the classifier. Raw replay
results, labels, models and diagnostics remain in a private research bundle.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
from datetime import datetime, timezone

from empirical_privacy import (attack_metrics, calibrate_threshold, export_public,
    feature_names, feature_vector, fit_classifier, predict_scores)
from occupancy import evaluate
from oracle import validate_result
from privacy_dataset import target_knowledge, validate_dataset
from run_comparison import VARIANTS, digest, git_state, run_variant, scientific_result, write_json

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = ('control_exact_count', 'control_no_output')


def integer(value, name, minimum=1):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return value


def probability(value, name, include_zero=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not (0 <= value <= 1)
            or (not include_zero and value == 0)):
        raise ValueError(f'{name} must be a finite probability in the permitted range')
    return value


def read_json(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 256 * 1024 * 1024:
        raise ValueError('JSON input must be a regular file of at most 256 MiB')
    def reject(value):
        raise ValueError(f'Non-finite JSON constant: {value}')
    return json.loads(path.read_text(), parse_constant=reject)


def relative_file(directory, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('Dataset paths must be nonempty relative paths')
    path = (directory / relative).resolve(strict=True)
    if directory not in path.parents:
        raise ValueError('Dataset path escapes its root')
    return path


def load_dataset(directory):
    """Validate all pair/split/hash contracts before creating a study output."""
    directory = Path(directory).resolve(strict=True)
    manifest = read_json(directory / 'manifest.json')
    # Validate paths before the generator's loader reads their contents.
    for case in manifest.get('cases', []):
        for key in ('present_input', 'absent_input', 'target_trace'):
            relative_file(directory, case.get(key))
    policy = relative_file(directory, manifest.get('policy', 'policy.json'))
    validate_dataset(manifest, directory)
    splits = Counter(case['split'] for case in manifest['cases'])
    if set(splits) != {'train', 'calibration', 'test'} or any(n < 2 for n in splits.values()):
        raise ValueError('Each independent split needs at least two paired groups')
    return manifest, policy


def source_result(replay, releases, name):
    total = sum(len(batch['observations']) for batch in replay['batches'])
    return dict(schema='ump.replay-result.v1', mode=name,
        source=dict(run_id=replay['run_id'], sensor_id=replay['sensor_id'],
            application_id='source-occupancy', coverage=deepcopy(replay['coverage']),
            sampling_period_ms=replay['sampling_period_ms'], end_ms=replay['end_ms']),
        parameters={}, configuration_yaml='', input_observation_contributions=total,
        accounted_observation_contributions=total, windows=[], releases=releases,
        runtime={'processing_ms': 0})


def control_result(replay, name):
    """Explicit unprotected 10-m/100-ms full-count grid, or a constant no-output view.

    Zero certificates belong ONLY to this unprotected control. Actual mechanisms
    retain their sparse-publication contract, where absent output is unknown.
    """
    if name == 'control_no_output':
        return source_result(replay, [], name)
    if name != 'control_exact_count':
        raise ValueError('Unknown control')
    grid, period = replay['coverage'], replay['sampling_period_ms']
    if grid['width'] != 80 or grid['height'] != 80:
        raise ValueError('Exact-count control requires the declared 80-m preset')
    releases = []
    for batch in replay['batches']:
        if batch['status'] != 'measured':
            continue
        buckets = defaultdict(set)
        for observation in batch['observations']:
            column = int((observation['x'] - grid['x']) // 10)
            row = int((observation['y'] - grid['y']) // 10)
            buckets[(column, row)].add(observation['id'])
        cells = []
        for row in range(8):
            for column in range(8):
                cell_id = 3
                for bit in (2, 1, 0):
                    cell_id = cell_id * 4 + ((column >> bit) & 1) + 2 * ((row >> bit) & 1)
                count = len(buckets[(column, row)])
                cells.append(dict(cell_id=cell_id, depth=3, x=grid['x']+column*10,
                    y=grid['y']+row*10, width=10, height=10,
                    observation_contributions=count, distinct_road_users=count,
                    mean_sample_occupancy=float(count), effective_policy_id='unprotected-control'))
        start = batch['observed_at_ms']
        releases.append(dict(release_id=f'control-{start}', start_ms=start,
            end_ms=min(start+period, replay['end_ms']), sealed_at_ms=min(start+period,replay['end_ms']),
            model='unprotected_control', policy_id='unprotected-control', policy_version='1', cells=cells))
    return source_result(replay, releases, name)


def quantile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered)-1)*fraction
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high]-ordered[low])*(position-low)


def clustered_intervals(rows, threshold, repeats=200, seed=1):
    """Percentile bootstrap of paired cases, never of individual windows/frames.

    The fitted classifier and calibrated threshold remain frozen. Intervals describe
    conditional test-group sampling variation, not model-training uncertainty or a
    population privacy guarantee. Each group must contain both membership labels.
    """
    integer(repeats, 'bootstrap repeats', 0)
    groups = defaultdict(list)
    for row in rows:
        groups[row['group_id']].append(row)
    if any(sorted(r['label'] for r in group) != [0, 1] for group in groups.values()):
        raise ValueError('Bootstrap groups must contain exactly one IN and one OUT case')
    if len(groups) < 2 or repeats == 0:
        return dict(method='disabled_or_insufficient_groups', groups=len(groups), repeats=0)
    rng = random.Random(seed)
    keys = sorted(groups)
    strata = defaultdict(list)
    for group in keys:
        scenarios={r.get('scenario','pooled') for r in groups[group]}
        if len(scenarios)!=1:
            raise ValueError('A source group cannot cross scenario strata')
        strata[next(iter(scenarios))].append(group)
    samples = defaultdict(list)
    for _ in range(repeats):
        selected = [r for stratum in sorted(strata) for _ in strata[stratum]
                    for r in groups[rng.choice(strata[stratum])]]
        metrics = attack_metrics([r['score'] for r in selected],
                                 [r['label'] for r in selected], threshold)
        for key in ('roc_auc', 'tpr', 'fpr', 'advantage', 'balanced_accuracy'):
            if metrics.get(key) is not None:
                samples[key].append(metrics[key])
    return dict(method='scenario_stratified_paired_source_group_percentile_bootstrap', confidence=.95,
        groups=len(groups), repeats=repeats,
        intervals={key: [quantile(values,.025),quantile(values,.975)] for key,values in samples.items()},
        scope='Frozen model/threshold; synthetic independent test groups; no training uncertainty')


def paired_auc_difference(rows, baseline, repeats=200, seed=1):
    """Paired AUC difference using the same resampled groups for both mechanisms."""
    left = {(r['group_id'],r['label']): r['score'] for r in rows}
    right = {(r['group_id'],r['label']): r['score'] for r in baseline}
    if set(left) != set(right):
        raise ValueError('Paired mechanism comparisons require identical test cases')
    if len(left)!=len(rows) or len(right)!=len(baseline):
        raise ValueError('Duplicate paired test cases')
    groups = sorted({key[0] for key in left})
    strata=defaultdict(list)
    for group in groups:
        scenarios={r.get('scenario','pooled') for r in rows if r['group_id']==group}
        if len(scenarios)!=1 or sorted(r['label'] for r in rows if r['group_id']==group)!=[0,1]:
            raise ValueError('Each paired source group needs one scenario and both labels')
        strata[next(iter(scenarios))].append(group)
    def difference(selected):
        keys = [(group,label) for group in selected for label in (0,1)]
        labels = [key[1] for key in keys]
        return (attack_metrics([left[key] for key in keys],labels,.5)['roc_auc']
              - attack_metrics([right[key] for key in keys],labels,.5)['roc_auc'])
    point = difference(groups)
    if repeats == 0 or len(groups) < 2:
        return dict(auc_difference=point, interval=None, independent_groups=len(groups))
    rng = random.Random(seed)
    samples = [difference([rng.choice(strata[stratum]) for stratum in sorted(strata)
                           for _ in strata[stratum]]) for _ in range(repeats)]
    return dict(auc_difference=point, interval=[quantile(samples,.025),quantile(samples,.975)],
        independent_groups=len(groups), repeats=repeats,
        method='scenario_stratified_paired_source_group_percentile_bootstrap')


def utility_rollup(rows):
    """Pool fixed-query numerators/denominators; report absence as undefined error."""
    reference = sum(r['reference_queries'] for r in rows)
    answered = sum(r['answered_queries'] for r in rows)
    scored = sum(r['scored_queries'] for r in rows)
    error = math.fsum((r['occupancy_mae'] or 0)*r['scored_queries'] for r in rows)
    common = sum(r.get('common_scored_queries',0) for r in rows)
    common_error = math.fsum((r.get('common_support_mae') or 0)*r.get('common_scored_queries',0) for r in rows)
    inputs = sum(r['input_contributions'] for r in rows)
    released = sum(r['released_contributions'] for r in rows)
    ages = [age for r in rows for age in r['release_ages_ms']]
    return dict(case_worlds=len(rows), reference_queries=reference, answered_queries=answered,
        scored_queries=scored, occupancy_mae=error/scored if scored else None,
        answered_query_coverage=answered/reference if reference else None,
        contribution_retention=released/inputs if inputs else None,
        input_contributions=inputs, released_contributions=released,
        common_scored_queries=common, common_support_mae=common_error/common if common else None,
        mean_release_age_ms=math.fsum(ages)/len(ages) if ages else None,
        p95_release_age_ms=quantile(ages,.95), release_count=len(ages),
        weighting='Pooled equal-weight fixed queries/contributions; one age weight per release',
        reference_population='Included source contributors, not all physically present road users')


def stable_seed(*parts):
    return int.from_bytes(hashlib.sha256(':'.join(map(str,parts)).encode()).digest()[:8],'big') % (2**63)


def run_study(dataset, output, binary, *, knowledge_fractions=(.25,1.0), target_fpr=.1,
              bootstrap_repeats=200):
    """Run real replay, independent checks, public features and held-out attacks."""
    manifest, policy_path = load_dataset(dataset)
    config = read_json(policy_path)
    fractions = tuple(knowledge_fractions)
    if not fractions or len(set(fractions)) != len(fractions):
        raise ValueError('Knowledge fractions must be nonempty and unique')
    for fraction in fractions:
        probability(fraction,'knowledge fraction')
    probability(target_fpr,'target FPR',include_zero=True)
    integer(bootstrap_repeats,'bootstrap repeats',0)
    binary = Path(binary).resolve(strict=True)
    if not binary.is_file():
        raise ValueError('Replay binary must be a file')
    raw_output = Path(output).expanduser()
    if raw_output.exists() or raw_output.is_symlink():
        raise FileExistsError(f'Output path already exists: {raw_output}')
    dataset, output = Path(dataset).resolve(), raw_output.resolve()
    if output == dataset or dataset in output.parents or output in dataset.parents:
        raise ValueError('Study output and source dataset must be separate directories')
    # Exclusive creation: evidence is never overwritten.
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    for subdirectory in ('raw','public','models'):
        (output/subdirectory).mkdir(mode=0o700)
    provenance = dict(schema='ump.privacy-study-manifest.v1', status='running',
        classification='private_research_bundle', created_utc=datetime.now(timezone.utc).isoformat(),
        dataset=str(dataset), dataset_manifest_sha256=digest(dataset/'manifest.json'),
        policy_sha256=digest(policy_path), binary_sha256=digest(binary), git=git_state(ROOT),
        python=sys.version, knowledge_fractions=fractions, calibration_target_fpr=target_fpr,
        bootstrap_repeats=bootstrap_repeats, split_groups=dict(Counter(c['split'] for c in manifest['cases'])),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in sorted((ROOT/'tools/evaluation').glob('*.py'))},
        observer='One immutable application stream; public fields and candidate partial trace only',
        secret='Source-contribution membership; not physical presence',
        utility_population='Included source contributors',
        guarantees='Empirical scoped synthetic study; no k-anonymity, differential privacy or universal guarantee')
    write_json(output/'manifest.json',provenance)
    feature_rows = defaultdict(list)
    utility_rows = defaultdict(list)
    oracle_records = []
    command_records = []
    variant_specs = [(name,mode,depth,window) for name,mode,depth,window in VARIANTS]
    for case_number, case in enumerate(manifest['cases'],1):
        trace = read_json(relative_file(dataset,case['target_trace']))
        knowledge = {fraction:target_knowledge(trace,fraction,stable_seed(manifest['seed'],case['group_id'],fraction))
                     for fraction in fractions}
        for world,label in (('present',1),('absent',0)):
            source_path = relative_file(dataset,case[world+'_input'])
            replay = read_json(source_path)
            results, utilities = {}, {}
            for name,mode,depth,window in variant_specs:
                artifact = hashlib.sha256(f"{case['case_id']}:{world}:{name}".encode()).hexdigest()[:24]
                destination = output/'raw'/(artifact+'.json')
                result,command = run_variant(binary,source_path,policy_path,destination,mode,depth,window)
                audit = validate_result(replay,config,result)
                oracle_records.append(dict(case_id=case['case_id'],world=world,variant=name,**audit))
                if not audit['valid']:
                    write_json(output/'oracle-failure.json',oracle_records[-1])
                    raise ValueError(f'Independent oracle rejected {case["case_id"]}/{world}/{name}')
                command_records.append(dict(case_id=case['case_id'],world=world,variant=name,
                    command=command,input_sha256=digest(source_path),result_sha256=digest(destination)))
                results[name]=result
                # Repeat one actual execution to check deterministic scientific output.
                if case_number==1 and world=='present' and name=='spatial_first':
                    repeated_path=output/'raw'/'determinism-repeat.json'
                    repeated,_=run_variant(binary,source_path,policy_path,repeated_path,mode,depth,window)
                    if scientific_result(repeated)!=scientific_result(result):
                        raise ValueError('Scientific replay is not deterministic')
                    repeated_path.unlink()
            for name in CONTROLS:
                results[name]=control_result(replay,name)
            for name,result in results.items():
                public=export_public(result)
                artifact=hashlib.sha256(f"{case['case_id']}:{world}:{name}".encode()).hexdigest()[:24]
                write_json(output/'public'/(artifact+'.json'),public)
                utilities[name]=evaluate(replay,result)
                for fraction,known in knowledge.items():
                    for include_geometry in (False,True):
                        key=(name,fraction,'counts_geometry_time' if include_geometry else 'counts_availability')
                        feature_rows[key].append(dict(group_id=case['group_id'],case_id=case['case_id'],
                            split=case['split'],scenario=case['scenario'],label=label,
                            features=feature_vector(public,known,include_geometry=include_geometry)))
            common=[i for i in range(len(next(iter(utilities.values()))['queries']))
                    if all(utilities[name]['queries'][i]['absolute_error'] is not None
                           for name,*_ in variant_specs)]
            for name,utility in utilities.items():
                result=results[name]
                row=dict(case_id=case['case_id'],group_id=case['group_id'],split=case['split'],
                    world=world,scenario=case['scenario'],**utility['summary'],
                    input_contributions=sum(len(b['observations']) for b in replay['batches']),
                    released_contributions=sum(c['observation_contributions'] for r in result['releases'] for c in r['cells']),
                    release_ages_ms=[r['sealed_at_ms']-r['start_ms'] for r in result['releases']],
                    common_scored_queries=len(common),
                    common_support_mae=(math.fsum(utility['queries'][i]['absolute_error'] for i in common)/len(common)
                                        if common and name not in CONTROLS else None))
                # Controls are not part of the seven-policy-method common-support comparison.
                if name in CONTROLS:
                    row['common_scored_queries']=0
                utility_rows[name].append(row)
        print(f'Validated paired group {case_number}/{len(manifest["cases"])} ({case["split"]}, {case["scenario"]})',flush=True)
    attacks=[]
    predictions={}
    for key,rows in sorted(feature_rows.items()):
        name,fraction,feature_set=key
        splits={split:[r for r in rows if r['split']==split] for split in ('train','calibration','test')}
        model=fit_classifier([r['features'] for r in splits['train']],[r['label'] for r in splits['train']])
        calibration_scores=predict_scores(model,[r['features'] for r in splits['calibration']])
        calibration=calibrate_threshold(calibration_scores,[r['label'] for r in splits['calibration']],target_fpr=target_fpr)
        threshold=calibration['threshold']
        test_scores=predict_scores(model,[r['features'] for r in splits['test']])
        test_rows=[dict(group_id=r['group_id'],scenario=r['scenario'],label=r['label'],score=score)
                   for r,score in zip(splits['test'],test_scores)]
        predictions[key]=test_rows
        record=dict(variant=name,knowledge_fraction=fraction,feature_set=feature_set,
            feature_count=len(rows[0]['features']),features=feature_names(include_geometry=feature_set=='counts_geometry_time'),
            training_groups=len(splits['train'])//2,calibration_groups=len(splits['calibration'])//2,
            test_groups=len(splits['test'])//2,calibration=calibration,
            test=attack_metrics(test_scores,[r['label'] for r in splits['test']],threshold),
            test_uncertainty=clustered_intervals(test_rows,threshold,bootstrap_repeats,stable_seed(*key)))
        record['test_by_scenario']={scenario:attack_metrics(
            [r['score'] for r in test_rows if r['scenario']==scenario],
            [r['label'] for r in test_rows if r['scenario']==scenario],threshold)
            for scenario in sorted({r['scenario'] for r in test_rows})}
        attacks.append(record)
        model_id=hashlib.sha256(repr(key).encode()).hexdigest()[:24]
        write_json(output/'models'/(model_id+'.json'),dict(key=list(key),model=model,threshold=threshold))
    for record in attacks:
        key=(record['variant'],record['knowledge_fraction'],record['feature_set'])
        baseline=('fixed_10m_400ms',record['knowledge_fraction'],record['feature_set'])
        record['paired_vs_fixed_10m_400ms']=paired_auc_difference(predictions[key],predictions[baseline],
            bootstrap_repeats,stable_seed('paired',record['knowledge_fraction'],record['feature_set']))
    test_groups=[c['group_id'] for c in manifest['cases'] if c['split']=='test']
    prior_labels=[label for _ in test_groups for label in (0,1)]
    prior_calibration_labels=[label for c in manifest['cases'] if c['split']=='calibration' for label in (0,1)]
    prior_calibration=calibrate_threshold([.5]*len(prior_calibration_labels),prior_calibration_labels,target_fpr=target_fpr)
    prior_baseline=attack_metrics([.5]*len(prior_labels),prior_labels,prior_calibration['threshold'])
    report=dict(schema='ump.empirical-privacy-report.v1',classification='private_research_bundle',
        status='complete',threat_model=provenance['observer'],secret=provenance['secret'],
        limitations=[provenance['guarantees'],'Synthetic prescribed routes; no city-map realism claim',
            'Classifier failure is not a bound on every possible attacker',
            'Bootstrap conditions on the fitted model and calibrated threshold',
            'Common-window algorithm baseline; no independent local windows or A07 rescue',
            'Logical release timing only; transport/runtime channels excluded'],
        prior_only=prior_baseline,attacks=attacks,
        utility={name:utility_rollup([r for r in rows if r['split']=='test']) for name,rows in utility_rows.items()},
        utility_by_scenario={name:{scenario:utility_rollup([r for r in rows if r['split']=='test' and r['scenario']==scenario])
            for scenario in sorted({r['scenario'] for r in rows if r['split']=='test'})}
            for name,rows in utility_rows.items()},
        independent_validation=dict(checks=len(oracle_records),all_valid=True,
            released_cell_count=sum(r.get('released_cell_count',len(r.get('released_cells',[]))) for r in oracle_records),
            no_release_cases=sum(bool(r.get('no_release')) for r in oracle_records)),
        scope=dict(membership_prior=.5,reference_grid_m=10,reference_window_ms=1000,
            exact_control='Unprotected complete 10-m/100-ms grid with explicit zeros; outside policy',
            missing_public_support='Unknown for policy-controlled streams; no GT filling'))
    write_json(output/'report.json',report)
    write_json(output/'oracle-validation.json',oracle_records)
    write_json(output/'commands.json',command_records)
    write_json(output/'features-private.json',[dict(key=list(key),rows=rows) for key,rows in sorted(feature_rows.items())])
    write_json(output/'test-predictions-private.json',[dict(key=list(key),rows=rows) for key,rows in sorted(predictions.items())])
    write_json(output/'utility-private.json',utility_rows)
    with (output/'attack-summary.csv').open('x',newline='') as stream:
        columns=['variant','knowledge_fraction','feature_set','roc_auc','tpr','fpr','advantage','balanced_accuracy','test_groups']
        writer=csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader()
        for r in attacks:
            writer.writerow({**{k:r[k] for k in ('variant','knowledge_fraction','feature_set','test_groups')},
                             **{k:r['test'].get(k) for k in ('roc_auc','tpr','fpr','advantage','balanced_accuracy')}})
    # Replace only our own running manifest after every final artifact exists.
    provenance['status']='complete'
    provenance['report_sha256']=digest(output/'report.json')
    (output/'manifest.json').write_text(json.dumps(provenance,indent=2,allow_nan=False)+'\n')
    print(f'Completed {len(attacks)} held-out attack comparisons; report: {output / "report.json"}',flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--binary',type=Path,default=ROOT/'simulator/build/AggregationReplay')
    parser.add_argument('--knowledge-fractions',type=float,nargs='+',default=[.25,1.0])
    parser.add_argument('--target-fpr',type=float,default=.1)
    parser.add_argument('--bootstrap-repeats',type=int,default=200)
    args=parser.parse_args()
    try:
        run_study(args.dataset,args.output,args.binary,knowledge_fractions=args.knowledge_fractions,
                  target_fpr=args.target_fpr,bootstrap_repeats=args.bootstrap_repeats)
    except (ValueError,OSError,RuntimeError,KeyError) as error:
        parser.exit(1,f'Privacy study failed: {error}\n')


if __name__=='__main__':
    main()
