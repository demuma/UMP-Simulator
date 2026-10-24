#!/usr/bin/env python3
"""Explain a frozen fixed/adaptive retention gap without rerunning either method.

Observation membership is joined exactly on the private source time/identity.
Only compact counts and bounded aggregate counterexamples are exported. Parent
checks are counterfactual assessments on the actual failed interval; they are
not a claim that a different online schedule can recover every listed loss.
"""
from __future__ import annotations
import argparse
from array import array
from bisect import bisect_right,bisect_left
from collections import Counter,defaultdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import time

from oracle import decode_cell
from semantic_suppression_audit import Catalog,effective

MAX_RECORD=4*1024*1024


def require(condition,message):
    if not condition:raise ValueError(message)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


class Reader:
    def __init__(self,handle):
        self.handle=handle;self.buffer='';self.at=0;self.eof=False;self.decoder=json.JSONDecoder()
    def more(self):
        self.buffer=self.buffer[self.at:];self.at=0
        chunk=self.handle.read(65536)
        self.buffer+=chunk;self.eof=not chunk
    def peek(self):
        while True:
            while self.at<len(self.buffer) and self.buffer[self.at].isspace():self.at+=1
            if self.at<len(self.buffer):return self.buffer[self.at]
            if self.eof:raise ValueError('Unexpected JSON end')
            self.more()
    def expect(self,char):
        require(self.peek()==char,'Expected JSON token '+char);self.at+=1
    def value(self):
        self.peek()
        while True:
            try:value,end=self.decoder.raw_decode(self.buffer,self.at)
            except json.JSONDecodeError:
                require(not self.eof and len(self.buffer)-self.at<MAX_RECORD,'Malformed or oversized native JSON record')
                self.more();continue
            # raw_decode may accept a numeric prefix at a chunk boundary.
            # Require its following separator before committing the value.
            separator=end
            while separator<len(self.buffer) and self.buffer[separator].isspace():separator+=1
            if separator==len(self.buffer) and not self.eof:
                self.more();continue
            require(separator<len(self.buffer) and self.buffer[separator] in ',]}:',
                    'Invalid JSON value separator')
            self.at=end
            return value


def native_records(path):
    """Stream the two large top-level arrays; never materialize empty history."""
    with Path(path).open(encoding='utf-8') as handle:
        reader=Reader(handle);reader.expect('{')
        while reader.peek()!='}':
            key=reader.value();require(isinstance(key,str),'Native top-level key must be text');reader.expect(':')
            if key in ('windows','releases'):
                reader.expect('[')
                while reader.peek()!=']':
                    yield key,reader.value()
                    if reader.peek()==',':reader.at+=1
                    else:break
                reader.expect(']')
            else:yield key,reader.value()
            if reader.peek()==',':reader.at+=1
            else:break
        reader.expect('}')


class IntervalIndex:
    def __init__(self):self.rows=defaultdict(list);self.starts={}
    def add(self,cell,start,end,payload):self.rows[cell].append((start,end,payload))
    def finish(self):
        for identity,rows in self.rows.items():
            rows.sort(key=lambda row:row[0]);self.starts[identity]=[r[0] for r in rows]
            require(all(a[1]<=b[0] for a,b in zip(rows,rows[1:])),'Overlapping same-cell intervals')
    def match(self,leaf,time,leaf_depth):
        matches=[]
        for depth in range(1,leaf_depth+1):
            identity=leaf>>(2*(leaf_depth-depth));position=bisect_right(self.starts.get(identity,()),time)-1
            if position>=0:
                row=self.rows[identity][position]
                if time<row[1]:matches.append(row[2])
        require(len(matches)<=1,'Overlapping ancestor ownership/release')
        return matches[0] if matches else None


def load_case(path,private=False):
    releases=IntervalIndex();suppressed=IntervalIndex();windows=[];owners={};headers={};ordinal=0
    for key,row in native_records(path):
        if key=='windows':
            if private:
                scope=row['coordination_cell'];identity=scope['cell_id']
                if identity not in owners:owners[identity]=(scope['depth'],array('q'),array('q'),array('q'))
                owner=owners[identity];owner[1].append(row['start_ms']);owner[2].append(row['end_ms']);owner[3].append(ordinal)
                if row['input_observation_contributions']:
                    item={name:row.get(name) for name in ('start_ms','end_ms','evaluated_at_ms','completion_reason','temporal_extensions','coordination_cell','temporal_decisions')}
                    item['ordinal']=ordinal;item['cells']=row['cells'];windows.append(item)
                    for cell in item['cells']:
                        if not cell['selected']:
                            record={'window':item,'cell':cell}
                            suppressed.add(cell['cell_id'],item['start_ms'],item['end_ms'],record)
            ordinal+=1
        elif key=='releases':
            for cell in row['cells']:
                record={name:row[name] for name in ('start_ms','end_ms','sealed_at_ms')};record['cell']=cell
                releases.add(cell['cell_id'],row['start_ms'],row['end_ms'],record)
        else:headers[key]=row
    releases.finish();suppressed.finish()
    # Final retirement order is usually endpoint order. Index by start without
    # retaining the original half-gigabyte diagnostic objects.
    for identity,(depth,starts,ends,ordinals) in list(owners.items()):
        order=sorted(range(len(starts)),key=starts.__getitem__)
        owners[identity]=(depth,array('q',(starts[i] for i in order)),array('q',(ends[i] for i in order)),array('q',(ordinals[i] for i in order)))
    return dict(headers=headers,releases=releases,suppressed=suppressed,windows=windows,owners=owners)


def intersect(a,b):
    return a['x']<b['x']+b['width'] and b['x']<a['x']+a['width'] and a['y']<b['y']+b['height'] and b['y']<a['y']+a['height']


class ParentEvidence:
    def __init__(self,data,config,owners):
        self.data=data;self.config=config;self.catalog=Catalog(config);self.owners=owners
        self.depth=data['coverage']['leaf_depth'];self.period=data['sampling_period_ms']
        self.rows=defaultdict(list);self.times={};self.batch_times=[b['observed_at_ms'] for b in data['batches']]
        for batch in data['batches']:
            for row in batch['observations']:
                identity=row['cell_id']>>(2*(self.depth-2));self.rows[identity].append((batch['observed_at_ms'],row))
        for identity,rows in self.rows.items():self.times[identity]=[r[0] for r in rows]
    @lru_cache(maxsize=None)
    def assess(self,identity,start,end,now):
        geometry=decode_cell(self.data['coverage'],identity,2);bounds,regions=effective(self.config,geometry)
        rows=self.rows.get(identity,());times=self.times.get(identity,())
        selected=rows[bisect_left(times,start):bisect_left(times,end)]
        by_leaf=defaultdict(list)
        for _,row in selected:by_leaf[self.catalog.labels[row['type']]].append(row)
        support=bounds['min_category_distinct_contributors']['min']
        def visit(node):
            relevant=[row for leaf,items in by_leaf.items() if node in self.catalog.chains[leaf] for row in items]
            if not relevant:return []
            children=self.catalog.children[node]
            if children:
                cuts=[visit(child) for child in children]
                if all(cut is not None for cut in cuts):return [entry for cut in cuts for entry in cut]
            distinct=len({row['id'] for row in relevant})
            if distinct>=support:return [(node,len(relevant),distinct)]
            return None
        cut=visit(self.catalog.root)
        first=max(self.period,((start+self.period-1)//self.period)*self.period)
        expected=len(range(first,end,self.period))
        batches=self.data['batches'][bisect_left(self.batch_times,start):bisect_left(self.batch_times,end)]
        measured=sum(batch['status']=='measured' for batch in batches)
        total=len(selected);distinct=len({row['id'] for _,row in selected})
        values=dict(observation_contributions=total,distinct_contributors=distinct,
            mean_sample_occupancy=total/measured if measured else None,cell_side_m=geometry['width'],cell_area_m2=geometry['width']*geometry['height'],
            window_duration_ms=end-start,age_at_evaluation_ms=now-start,post_window_delay_ms=now-end,
            measured_sample_fraction=measured/expected if expected else None,
            min_category_distinct_contributors=min((n for _,_,n in cut),default=None) if cut else None,
            semantic_max_loss=max((self.catalog.nodes[c]['loss'] for c,_,_ in cut),default=None) if cut else None,
            semantic_mean_loss=sum(n*self.catalog.nodes[c]['loss'] for c,n,_ in cut)/total if cut and total else None,
            semantic_suppression_fraction=0)
        failures=[]
        if not expected or measured!=expected:failures.append('complete_coverage')
        for metric,limits in bounds.items():
            value=values.get(metric)
            if value is None or value<limits.get('min',-math.inf) or value>limits.get('max',math.inf):failures.append(metric)
        return dict(cell_id=identity,depth=2,start_ms=start,end_ms=end,evaluated_at_ms=now,
            metrics=values,effective_requirements=bounds,intersected_regions=regions,passing=not failures,failed_metrics=failures,
            semantic_categories=[] if cut is None else [dict(category_id=c,observations=n,distinct_tracks=k) for c,n,k in cut],
            source_type_counts=dict(Counter(row['type'] for _,row in selected)))
    @lru_cache(maxsize=None)
    def phases(self,parent,end,failed_start,ordinal):
        target_depth=2;leaf_depth=self.depth;units=4**(leaf_depth-target_depth);covered=0;starts=Counter();same_endpoint_prior=0;examples=[]
        t=end-1
        for identity,(depth,begins,ends,ordinals) in self.owners.items():
            if depth>=target_depth:
                if identity>>(2*(depth-target_depth))!=parent:continue
                weight=4**(leaf_depth-depth)
            else:
                if parent>>(2*(target_depth-depth))!=identity:continue
                weight=units
            at=bisect_right(begins,t)-1
            if at<0 or not t<ends[at]:continue
            covered+=weight;starts[begins[at]]+=weight
            prior=ends[at]==end and ordinals[at]<ordinal
            same_endpoint_prior+=bool(prior)
            if begins[at]!=failed_start and len(examples)<8:
                examples.append(dict(cell_id=identity,depth=depth,start_ms=begins[at],end_ms=ends[at],earlier_same_endpoint=bool(prior)))
        return dict(covered_leaf_units=covered,expected_leaf_units=units,starts_leaf_units={str(k):v for k,v in sorted(starts.items())},
                    full_coverage=covered==units,all_starts_match=covered==units and set(starts)=={failed_start},
                    earlier_same_endpoint_retirements=same_endpoint_prior,other_clock_examples=examples,
                    scope='Retirement ownership immediately before the endpoint; later refinements can make archived scopes finer than the live frontier. Different starts are exact; live handoff intent is not reconstructed.')


def public_failure(record):
    window,cell=record['window'],record['cell']
    return dict(start_ms=window['start_ms'],end_ms=window['end_ms'],evaluated_at_ms=window['evaluated_at_ms'],
        cell_id=cell['cell_id'],depth=cell['depth'],observation_contributions=cell['observation_contributions'],
        completion_reason=window['completion_reason'],reason=cell['reason'],metrics=cell['metrics'],
        failed_checks=[check for check in cell['checks'] if check['status']!='pass'],
        temporal_actions=dict(Counter(row['action'] for row in window['temporal_decisions'])))


def diagnose(directory,adaptive_name,fixed_name,output,*,example_limit=8):
    directory=Path(directory).resolve();output=Path(output).resolve();require(not output.exists(),'Choose a fresh diagnosis output')
    summary=json.loads((directory/'summary.json').read_text());require(summary['status']=='verified','Require verified complete source comparison')
    paths={name:directory/(name+'.json') for name in (adaptive_name,fixed_name)}
    for name,path in paths.items():require(sha(path)==summary['cases'][name]['result_sha256'],'Changed frozen native result '+name)
    config=json.loads((directory/(adaptive_name+'-policy.json')).read_text())
    require(config['policy_tree']['root'].get('semantic_suppression_fraction',{}).get('max',0)==0,'This diagnostic requires filtering disabled')
    data=json.loads((directory/'observations.json').read_text());require(sha(directory/'observations.json')==summary['protocol']['observations_sha256'],'Changed frozen observations')
    print(json.dumps(dict(stage='load_adaptive',case=adaptive_name)),flush=True)
    adaptive=load_case(paths[adaptive_name],True)
    print(json.dumps(dict(stage='load_fixed',case=fixed_name)),flush=True)
    fixed=load_case(paths[fixed_name]);depth=data['coverage']['leaf_depth']
    evidence=ParentEvidence(data,config,adaptive['owners'])
    counts=Counter();types=defaultdict(Counter);regions=defaultdict(Counter);loss_reasons=Counter();failed_combinations=Counter();durations=Counter();actions=Counter();parent_failures=Counter();mechanisms=Counter();by_parent=Counter()
    examples={};fixed_validated=set();lost_windows=Counter()
    for batch in data['batches']:
        t=batch['observed_at_ms']
        for row in batch['observations']:
            a=adaptive['releases'].match(row['cell_id'],t,depth);f=fixed['releases'].match(row['cell_id'],t,depth)
            group='both_retained' if a and f else 'adaptive_only' if a else 'fixed_only' if f else 'neither'
            counts[group]+=1;types[row['type']][group]+=1
            point_regions=[r['id'] for r in config.get('policy_regions',[]) if r['x']<=row['x']<r['x']+r['width'] and r['y']<=row['y']<r['y']+r['height']]
            for region in point_regions or ['outside_policy_regions']:regions[region][group]+=1
            if group!='fixed_only':continue
            failure=adaptive['suppressed'].match(row['cell_id'],t,depth);require(failure is not None,'Fixed-only source row lacks actual adaptive suppression')
            w,c=failure['window'],failure['cell'];parent=row['cell_id']>>(2*(depth-2))
            lost_windows[(w['ordinal'],c['cell_id'])]+=1
            loss_reasons[w['completion_reason']]+=1;durations[str(w['end_ms']-w['start_ms'])]+=1;by_parent[str(parent)]+=1
            failed=tuple(sorted(check['metric'] for check in c['checks'] if check['status']!='pass'));failed_combinations[' + '.join(failed)]+=1
            for action in {d['action'] for d in w['temporal_decisions']}:actions[action]+=1
            assessment=evidence.assess(parent,w['start_ms'],w['end_ms'],w['evaluated_at_ms'])
            for metric in assessment['failed_metrics']:parent_failures[metric]+=1
            phase=evidence.phases(parent,w['end_ms'],w['start_ms'],w['ordinal'])
            if assessment['passing']:
                mechanism='parent_passes_same_interval_but_owner_starts_differ' if not phase['all_starts_match'] else 'parent_passes_same_interval_with_aligned_archived_starts'
            elif 'window_duration_ms' in assessment['failed_metrics'] or 'age_at_evaluation_ms' in assessment['failed_metrics']:
                mechanism='parent_same_interval_exceeds_regional_time_or_age_limit'
            else:mechanism='parent_same_interval_fails_other_constraints'
            mechanisms[mechanism]+=1
            fixed_key=(f['cell']['cell_id'],f['start_ms'],f['end_ms'],f['sealed_at_ms'])
            if fixed_key not in fixed_validated:
                verified=evidence.assess(*fixed_key);require(verified['passing'],'Actual fixed release fails independent same-policy parent assessment');fixed_validated.add(fixed_key)
            if mechanism not in examples and len(examples)<example_limit:
                examples[mechanism]=dict(first_source_time_ms=t,source_type=row['type'],source_point_regions=point_regions,
                    adaptive_failure=public_failure(failure),same_interval_parent=assessment,parent_clock_evidence=phase,
                    fixed_actual_release=evidence.assess(*fixed_key))
    total=sum(counts.values());expected=sum(len(b['observations']) for b in data['batches'])
    require(total==expected,'Join does not conserve source observations')
    for name,case,observed in ((adaptive_name,adaptive,counts['both_retained']+counts['adaptive_only']),
                              (fixed_name,fixed,counts['both_retained']+counts['fixed_only'])):
        require(observed==summary['cases'][name]['stats']['retained_observation_contributions'],'Exact join disagrees with verified retained total')
    report=dict(schema='ump.spatial-gap-diagnosis.v1',status='verified_exact_membership_join',
        adaptive=adaptive_name,fixed=fixed_name,source_observations=total,observations_sha256=summary['protocol']['observations_sha256'],
        result_sha256={name:summary['cases'][name]['result_sha256'] for name in paths},
        membership=dict(counts),net_fixed_advantage=counts['fixed_only']-counts['adaptive_only'],
        by_source_type={k:dict(v) for k,v in sorted(types.items())},by_source_point_region={k:dict(v) for k,v in sorted(regions.items())},
        fixed_only_adaptive_completion_reasons=dict(loss_reasons),fixed_only_adaptive_failed_metric_combinations=dict(failed_combinations),
        fixed_only_adaptive_duration_ms=dict(sorted(durations.items(),key=lambda item:int(item[0]))),
        fixed_only_adaptive_action_presence=dict(actions),fixed_only_by_parent20=dict(by_parent),
        fixed_only_counterfactual_parent_failed_metrics=dict(parent_failures),fixed_only_counterfactual_classification=dict(mechanisms),
        contributing_suppressed_cell_windows=len(lost_windows),fixed_releases_recomputed=len(fixed_validated),examples=list(examples.values()),
        limitations=['Membership is exact for the recorded outputs; counterfactual parent checks do not prove a different online schedule can recover every loss.',
            'Counterfactual classification is noncausal: changing earlier releases also changes available sibling support, windows and other outcomes.',
            'Archived interval starts establish phase differences, but live handoff intentions and exact intermediate refinement order are not reconstructed.',
            'Regional source-point memberships are nonexclusive and differ from conservative whole-cell policy intersections.',
            'No raw identities, individual positions or generated movement stream are exported.'])
    output.mkdir(parents=True,mode=0o700)
    (output/'diagnosis.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ('adaptive','fixed','membership','net_fixed_advantage','fixed_only_counterfactual_classification')}),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--comparison',type=Path,required=True)
    parser.add_argument('--adaptive',required=True);parser.add_argument('--fixed',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();diagnose(args.comparison,args.adaptive,args.fixed,args.output)

if __name__=='__main__':main()
