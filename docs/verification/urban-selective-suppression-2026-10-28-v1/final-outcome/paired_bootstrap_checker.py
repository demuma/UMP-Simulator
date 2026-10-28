#!/usr/bin/env python3
"""Independent paired-CI arithmetic on an already successful assessment.

Standard library only. No producer helper, model fit, prediction or threshold
choice is called. Actual assessment payloads are opened only after an explicit
confirmation flag AND a verified zero-return-code assessment receipt.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import time

REPRESENTATIONS = ('semantic111', 'scalar31')
UTILITY_PATHS = ('retained_fraction', 'full_input_J', 'retained_semantic_loss',
                 'mean_retained_cell_side_m', 'mean_retained_interval_ms', 'logical_seal_delay_ms.mean')
SCHEMA = 'ump.urban-selective-independent-paired-bootstrap.v1'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024*1024), b''):
            value.update(part)
    return value.hexdigest()


def load(path):
    with Path(path).open() as stream:
        return json.load(stream)


def save_new(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    descriptor = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(descriptor,'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def numeric(value):
    return type(value) in (int,float) and math.isfinite(value)


def compare(actual, expected, name):
    if expected is None:
        require(actual is None, name+' unavailable-value mismatch')
        return 0.
    require(numeric(actual) and numeric(expected) and math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12),
            name+' arithmetic mismatch')
    return abs(actual-expected)


def quantile(ordered, probability):
    require(ordered, 'No bootstrap samples')
    rank = (len(ordered)-1)*probability
    lower, upper = math.floor(rank), math.ceil(rank)
    return ordered[lower] + (ordered[upper]-ordered[lower])*(rank-lower)


def paired_scores(rows):
    result = {}
    for row in rows:
        group, label, value = row['group_id'], row['label'], row['score']
        require(isinstance(group,str) and group and type(label) is int and label in (0,1)
                and numeric(value) and 0<=value<=1, 'Invalid assessed source score')
        pair = result.setdefault(group,{})
        require(label not in pair, 'Duplicate assessed source/world score')
        pair[label] = value
    require(result and all(set(pair)=={0,1} for pair in result.values()),'Incomplete assessed source pairs')
    return result


def paired_auc(left_rows, right_rows, *, seed, replicates=1000, confidence=.95):
    """Integer concordance differences, weighted by sampled source multiplicity.

    Every sampled source supplies BOTH its IN and OUT scores to BOTH methods.
    AUC is independently defined by all IN-vs-OUT comparisons, ties worth1/2.
    The precomputed two-times-concordance kernel avoids producer rank/metric code.
    """
    left, right = paired_scores(left_rows), paired_scores(right_rows)
    require(set(left)==set(right),'Assessed methods have different source sets')
    groups = sorted(left); n = len(groups)
    def twice(a,b):
        return 2 if a>b else 1 if a==b else 0
    kernel = [[twice(left[a][1],left[b][0])-twice(right[a][1],right[b][0]) for b in groups] for a in groups]
    point = sum(sum(row) for row in kernel)/(2*n*n)
    if n<2:
        return dict(auc_difference=point,interval=None,independent_groups=n,replicates=0)
    rng = random.Random(seed); samples = []
    for _ in range(replicates):
        multiplicity = Counter(rng.randrange(n) for _ in range(n))
        numerator = sum(ca*cb*kernel[a][b] for a,ca in multiplicity.items() for b,cb in multiplicity.items())
        samples.append(numerator/(2*n*n))
    samples.sort(); tail = (1-confidence)/2
    return dict(auc_difference=point,interval=[quantile(samples,tail),quantile(samples,1-tail)],
                independent_groups=n,replicates=replicates)


def value_at(row, path):
    value = row['utility']
    for part in path.split('.'):
        if not isinstance(value,dict) or part not in value:
            return None
        value=value[part]
    return value if numeric(value) else None


def paired_mean(differences, *, seed, replicates=1000):
    n=len(differences); point=math.fsum(differences)/n if n else None
    if n<2:
        return dict(mean_difference=point,ci95=None,paired_recordings=n)
    rng=random.Random(seed)
    samples=sorted(math.fsum(differences[rng.randrange(n)] for _ in range(n))/n for _ in range(replicates))
    return dict(mean_difference=point,ci95=[quantile(samples,.025),quantile(samples,.975)],paired_recordings=n)


def _self_test():
    rows=lambda scores:[dict(group_id=str(i),label=label,score=value) for i,pair in enumerate(scores) for label,value in enumerate(pair)]
    perfect=rows([(.1,.9),(.2,.8),(.3,.7)])
    reversed_scores=rows([(.9,.1),(.8,.2),(.7,.3)])
    tied=rows([(.5,.5)]*3)
    require(paired_auc(perfect,perfect,seed=11)['interval']==[0,0],'Identity contrast regression')
    require(paired_auc(perfect,reversed_scores,seed=11)['interval']==[1,1],'Pairwise AUC orientation regression')
    require(paired_auc(perfect,tied,seed=11)['auc_difference']==.5,'AUC ties regression')
    require(paired_auc(list(reversed(perfect)),tied,seed=11)==paired_auc(perfect,tied,seed=11),'Input-order regression')
    require(paired_mean([1,1,1],seed=11)['ci95']==[1,1],'Paired-mean regression')
    require(paired_mean([1],seed=11)['ci95'] is None,'Singleton interval regression')
    require(paired_mean([],seed=11)['mean_difference'] is None,'Missing-value regression')
    try:
        paired_auc(perfect[:-1],tied,seed=11)
    except ValueError:
        pass
    else:
        raise AssertionError('Incomplete score pairs were accepted')
    # Independent direct enumeration checks the multiplicity-kernel bootstrap.
    rng=random.Random(991); sources=sorted({r['group_id'] for r in perfect})
    varied_left=rows([(.3,.7),(.8,.2),(.5,.5)])
    varied_right=rows([(.6,.7),(.8,.9),(.2,.4)])
    left=paired_scores(varied_left);right=paired_scores(varied_right);direct=[]
    for _ in range(31):
        chosen=[sources[rng.randrange(len(sources))] for _ in sources]
        def auc(table):
            return math.fsum(1 if table[a][1]>table[b][0] else .5 if table[a][1]==table[b][0] else 0
                             for a in chosen for b in chosen)/(len(chosen)**2)
        direct.append(auc(left)-auc(right))
    direct.sort();expected=[quantile(direct,(1-.95)/2),quantile(direct,1-(1-.95)/2)]
    computed=paired_auc(varied_left,varied_right,seed=991,replicates=31)['interval']
    require(all(math.isclose(a,b,abs_tol=1e-14,rel_tol=1e-14) for a,b in zip(computed,expected)), 'Direct paired-bootstrap regression')
    return dict(status='verified',synthetic_regressions=9,actual_assessment_payloads_read=False)


def synthetic_benchmark():
    rng=random.Random(123)
    left=[dict(group_id='synthetic-'+str(i),label=label,score=rng.random()) for i in range(32) for label in (0,1)]
    right=[dict(row,score=rng.random()) for row in left]
    start=time.perf_counter()
    for index in range(24):
        paired_auc(left,right,seed=20261028501+index)
    for index in range(42):
        paired_mean([rng.random() for _ in range(32)],seed=20261028701+index)
    return dict(synthetic_only=True,auc_intervals=24,utility_intervals=42,replicates=1000,
                arithmetic_seconds=time.perf_counter()-start,performance_claim_about_study=False)


def verify(study, assessment_receipt, output, *, confirmed=False):
    require(confirmed,'Root must confirm successful assessment before existing TEST payloads are read')
    gate=load(assessment_receipt)
    require(gate.get('status')=='verified' and gate.get('returncode')==0,'Successful zero-return-code assessment receipt required')
    study=Path(study).resolve();output=Path(output)
    require(not output.exists(),'Choose a fresh immutable bootstrap verification directory')
    output.mkdir(mode=0o700)
    inputs={str(Path(assessment_receipt).resolve()):sha(assessment_receipt),str(Path(__file__).resolve()):sha(__file__)}
    def bound(path):
        path=Path(path).resolve();before=sha(path);data=load(path)
        require(sha(path)==before,'Input changed during read: '+str(path))
        inputs[str(path)]=before
        return data
    started=time.perf_counter()
    save_new(output/'attempt.json',dict(schema=SCHEMA,status='attempted',started_at=datetime.now(timezone.utc).isoformat(),
        assessment_receipt=dict(path=str(Path(assessment_receipt).resolve()),sha256=sha(assessment_receipt)),
        existing_assessment_only=True,models_refitted=0,new_predictions_computed=False))
    try:
        protocol=bound(study/'protocol.json')
        require(sha(study/'protocol.json')==(study/'protocol.sha256').read_text().strip(),'Protocol digest differs')
        report=bound(study/'final-report.json');utility=bound(study/'utility-report.json')
        require(report.get('phase')=='assessed' and report.get('mia_status')=='complete'
                and report['analysis']['status']=='complete','Complete assessed report required')
        require(report['lineage']['protocol']==dict(path=str(study/'protocol.json'),sha256=sha(study/'protocol.json')),
                'Assessed report protocol binding differs')
        require(report['paired_utility_contrasts']==utility['paired_utility_contrasts'],'Utility contrast gate changed')
        groups=protocol['group_order'];roles={g['group_id']:g['split'] for g in groups}
        require(len(roles)==72 and Counter(roles.values())==dict(train=24,calibration=16,test=32),'Role metadata differs')
        test_groups=sorted(g for g,role in roles.items() if role=='test')
        contrasts=protocol['contrasts'];require(len(contrasts)==12,'Expected12 declared contrasts')
        require([c['seed'] for c in contrasts]==list(range(20261028501,20261028508))+list(range(20261028601,20261028606)),
                'Declared AUC seeds differ')
        require(set(report['exploratory_contrasts'])=={c['id'] for c in contrasts},'Assessed contrast catalog differs')
        auc_checks=[];maximum_error=0.
        for declared in contrasts:
            name=declared['id'];actual=report['exploratory_contrasts'][name]
            require(all(actual[k]==declared[k] for k in ('left','right','seed','replicates','confidence_level')),
                    'Assessed contrast declaration differs: '+name)
            require(declared['replicates']==1000 and declared['confidence_level']==.95,'Bootstrap declaration differs')
            require(set(actual['representations'])==set(REPRESENTATIONS),'AUC representations differ')
            for representation in REPRESENTATIONS:
                sides=[report['analysis']['attacks'][declared[side]][representation] for side in ('left','right')]
                require(all(side['status']=='evaluated' for side in sides),'Unevaluated assessed attack')
                require(all(set(paired_scores(side['group_scores']))==set(test_groups) for side in sides),'Assessed TEST source set differs')
                recomputed=paired_auc(sides[0]['group_scores'],sides[1]['group_scores'],seed=declared['seed'])
                saved=actual['representations'][representation]
                require(saved['independent_groups']==32 and saved['replicates']==saved['requested_replicates']==1000
                        and saved['seed']==declared['seed'] and saved['confidence_level']==.95
                        and saved['resampling_unit']=='recording_with_both_worlds_and_both_methods', 'AUC resampling metadata differs')
                maximum_error=max(maximum_error,compare(saved['auc_difference'],recomputed['auc_difference'],name+'/'+representation+'/point'))
                require(isinstance(saved['interval'],list) and len(saved['interval'])==2,'AUC interval missing')
                for a,b in zip(saved['interval'],recomputed['interval']):maximum_error=max(maximum_error,compare(a,b,name+'/'+representation+'/CI'))
                auc_checks.append(dict(contrast=name,representation=representation,seed=declared['seed'],**recomputed))
        rows=[]
        for group in test_groups:
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',group),'Unsafe source ID')
            directory=study/'groups'/group
            summary=bound(directory/'summary.json');side=bound(directory/'selective-receipt.json')
            path=directory/summary['rows']['path']
            require(path.resolve().is_relative_to(directory.resolve()) and sha(path)==summary['rows']['sha256'], 'Stored utility-row provenance differs')
            require(side['protocol_sha256']==sha(study/'protocol.json')
                    and side['summary']==dict(path=str((directory/'summary.json').resolve()),sha256=sha(directory/'summary.json')),
                    'Recording binding differs')
            group_rows=bound(path)
            require(summary['status']=='verified' and all(r['group_id']==group and r['split']=='test' for r in group_rows),'Utility source role differs')
            rows.extend(group_rows)
        index={(r['group_id'],r['world'],r['method_id']):r for r in rows}
        require(len(index)==len(rows)==32*14*2,'Assessed TEST utility matrix differs')
        require(set(report['paired_utility_contrasts'])=={c['id'] for c in contrasts[:7]},'Utility contrast catalog differs')
        utility_checks=[]
        for number,declared in enumerate(contrasts[:7]):
            name=declared['id'];saved=report['paired_utility_contrasts'][name]
            require(saved['left']==declared['left'] and saved['right']==declared['right'] and saved['world']=='IN'
                    and set(saved['metrics'])==set(UTILITY_PATHS),'Utility contrast declaration differs')
            seed=20261028701+number
            for path in UTILITY_PATHS:
                pairs=[(value_at(index[g,'IN',declared['left']],path),value_at(index[g,'IN',declared['right']],path)) for g in test_groups]
                differences=[a-b for a,b in pairs if a is not None and b is not None]
                recomputed=paired_mean(differences,seed=seed);claimed=saved['metrics'][path]
                require(claimed['paired_recordings']==len(differences) and claimed['seed']==seed
                        and claimed['replicates']==1000 and claimed['confidence_level']==.95,'Utility resampling metadata differs')
                maximum_error=max(maximum_error,compare(claimed['mean_difference'],recomputed['mean_difference'],name+'/'+path+'/point'))
                if recomputed['ci95'] is None:
                    require(claimed['ci95'] is None,'Insufficient-source utility interval fabricated')
                else:
                    require(isinstance(claimed['ci95'],list) and len(claimed['ci95'])==2,'Utility interval missing')
                    for a,b in zip(claimed['ci95'],recomputed['ci95']):maximum_error=max(maximum_error,compare(a,b,name+'/'+path+'/CI'))
                utility_checks.append(dict(contrast=name,metric=path,seed=seed,**recomputed))
        require(len(auc_checks)==24 and len(utility_checks)==42,'Incomplete paired-bootstrap verification')
        require(all(sha(path)==value for path,value in inputs.items()),'Verification input changed')
        receipt=dict(schema=SCHEMA,status='verified',completed_at=datetime.now(timezone.utc).isoformat(),
            input_sha256=inputs,auc_intervals_verified=24,utility_intervals_verified=42,replicates_per_interval=1000,
            maximum_absolute_arithmetic_difference=maximum_error,source_resampling_unit='one matched TEST recording with both worlds and both methods',
            interval_rule='linear interpolation at (B-1)*q; marginal95% intervals conditional on fixed TRAIN models and CAL thresholds',
            auc_implementation='Independent integer pairwise concordance-difference kernel weighted by sampled source multiplicities; no producer rank/bootstrap helpers.',
            utility_implementation='Independent available-pair IN differences with source-resampled means; one RNG reset per contrast/metric.',
            auc_checks=auc_checks,utility_checks=utility_checks,models_refitted=0,new_predictions_computed=False,
            thresholds_retuned=False,producer_bootstrap_helpers_called=False,seconds=time.perf_counter()-started,
            scope='Recompute declared intervals from existing assessed TEST scores and stored utility only; no rescore, refit, data replacement or additional physical/source audit. No simultaneous-family or equivalence claim.')
        save_new(output/'receipt.json',receipt)
        return receipt
    except BaseException as error:
        save_new(output/'failed.json',dict(schema=SCHEMA,status='failed',error_type=type(error).__name__,error=str(error),
                                         input_sha256=inputs,seconds=time.perf_counter()-started,models_refitted=0,new_predictions_computed=False))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--benchmark-synthetic',action='store_true')
    parser.add_argument('--study',type=Path)
    parser.add_argument('--assessment-receipt',type=Path)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--confirmed-assessment-success',action='store_true')
    args=parser.parse_args()
    if args.self_test or args.benchmark_synthetic:
        require(args.study is None and args.assessment_receipt is None and args.output_dir is None,'Synthetic mode cannot read study files')
        result=_self_test()
        if args.benchmark_synthetic:result['synthetic_benchmark']=synthetic_benchmark()
    else:
        require(args.study is not None and args.assessment_receipt is not None and args.output_dir is not None,'Explicit study, successful-assessment receipt and fresh output are required')
        result=verify(args.study,args.assessment_receipt,args.output_dir,confirmed=args.confirmed_assessment_success)
        result={k:result[k] for k in ('status','auc_intervals_verified','utility_intervals_verified','maximum_absolute_arithmetic_difference','seconds')}
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
