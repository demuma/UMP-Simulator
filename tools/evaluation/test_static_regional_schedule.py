"""Independent static-schedule composition and adversarial receipt checks."""
from collections import defaultdict
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

import static_regional_schedule as subject

_spec=importlib.util.spec_from_file_location('ump_static_schedule_mapped_test_helper',
    Path(__file__).resolve().parents[1]/'mapped_scene/run_comparison.py')
mapped=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(mapped)


def fixture(local=False):
    data=dict(schema='ump.observation-replay.v1',run_id='static-test',sensor_id='sensor',
        coverage=copy.deepcopy(subject.PUBLIC_COVERAGE),sampling_period_ms=100,end_ms=8000,batches=[])
    for time in range(100,8000,100):
        rows=[]
        for cell,x in ((12288,1),(12544,21)):
            for person in range(3):
                rows.append(dict(id=f'{cell}-{person}',type='Adult' if person<2 else 'Child',
                    x=x+person*.02,y=1,cell_id=cell))
        data['batches'].append(dict(observed_at_ms=time,sequence=time//100,status='measured',observations=rows))
    root=dict(distinct_contributors={'min':2},min_category_distinct_contributors={'min':2},
        cell_side_m={'min':1.25,'max':20},window_duration_ms={'min':400,'max':4000},
        age_at_evaluation_ms={'max':4000},semantic_max_loss={'max':1},semantic_suppression_fraction={'max':0})
    config=dict(application_id='fixture',window_ms=400,policy_tree=dict(id='fixture',version='1',root=root,
        regions=['central'],execution=dict(strategy='semantic_first',semantic_secondary_strategy='temporal_first',
        release_trigger='policy_satisfied',publication_model='private_final_snapshot')),
        policy_regions=[dict(id='central',type='fresh',x=0,y=0,width=10,height=10,
            type_requirements={'window_duration_ms':{'max':400},'age_at_evaluation_ms':{'max':400}} if local else {},requirements={})],
        semantic_taxonomy=dict(id='fixture',version='1',nodes=[dict(id='root',loss=1),
            dict(id='pedestrian',parent='root',loss=.5),
            dict(id='adult',parent='pedestrian',loss=0,input_types=['Adult']),
            dict(id='child',parent='pedestrian',loss=0,input_types=['Child'])]))
    return data,config


def native(data,config,side,window):
    depth={10:3,20:2}[side];shift=2*(6-depth);groups=defaultdict(list)
    for batch in data['batches']:
        t=batch['observed_at_ms'];start=(t//window)*window;end=min(start+window,data['end_ms'])
        for row in batch['observations']:groups[(start,end,row['cell_id']>>shift)].append((t,row))
    windows=[];releases=[]
    for start in range(0,data['end_ms'],window):
        end=min(start+window,data['end_ms']);cells=[];public=[]
        for (group_start,group_end,cid),rows in sorted(groups.items()):
            if (group_start,group_end)!=(start,end):continue
            geometry=subject.decode_cell(data['coverage'],cid,depth)
            samples=sum(start<=b['observed_at_ms']<end for b in data['batches']);n=len(rows)
            # Three known fixture tracks per occupied fixed cell; one child
            # requires the family cut because child support is one (< two).
            values=dict(observation_contributions=n,distinct_contributors=3,mean_sample_occupancy=n/samples,
                cell_side_m=side,cell_area_m2=side*side,window_duration_ms=end-start,
                age_at_evaluation_ms=end-start,post_window_delay_ms=0,measured_sample_fraction=1,
                min_category_distinct_contributors=3,semantic_max_loss=.5,semantic_mean_loss=.5,
                semantic_suppression_fraction=0,occupancy_mae=None)
            bounds=copy.deepcopy(config['policy_tree']['root'])
            if geometry['x']==0 and local_bound(config):
                bounds['window_duration_ms']['max']=400;bounds['age_at_evaluation_ms']['max']=400
            checks=[dict(metric=metric,min=limits.get('min'),max=limits.get('max'),observed=values[metric],
                status='pass' if limits.get('min',float('-inf'))<=values[metric]<=limits.get('max',float('inf')) else 'fail')
                for metric,limits in bounds.items()]
            passing=all(check['status']=='pass' for check in checks)
            semantic=dict(schema='ump.semantic-release.v1',taxonomy_id='fixture',taxonomy_version='1',
                min_category_distinct_contributors=3,semantic_max_loss=.5,semantic_mean_loss=.5,
                categories=[dict(category_id='pedestrian',observation_contributions=n,distinct_contributors=3)])
            cell=dict(geometry,observation_contributions=n,distinct_road_users=3,mean_sample_occupancy=n/samples,
                selected=passing,assessment_status='pass' if passing else 'fail',semantic=semantic,metrics=values,checks=checks)
            cells.append(cell)
            if passing:public.append({key:copy.deepcopy(value) for key,value in cell.items()
                if key not in ('selected','assessment_status','metrics','checks')})
        windows.append(dict(start_ms=start,end_ms=end,evaluated_at_ms=end,cells=cells))
        if public:releases.append(dict(start_ms=start,end_ms=end,sealed_at_ms=end,cells=public))
    return dict(schema='ump.replay-result.v1',source={key:copy.deepcopy(data[key]) for key in
        ('run_id','sensor_id','coverage','sampling_period_ms','end_ms')},
        parameters=dict(coordination='common_window',fixed_depth=depth,window_ms=window),
        windows=windows,releases=releases,runtime=dict(processing_ms=12345))


def local_bound(config):return bool(config['policy_regions'][0]['type_requirements'])


def all_native(data,config,side):return {window:native(data,config,side,window) for window in subject.WINDOWS}


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')


def study_fixture(root):
    root.mkdir();cases={};sources={}
    for source in subject.SOURCES:
        data,_=fixture();write(root/(source+'-observations.json'),data)
        sources[source]=dict(observations_sha256=subject.sha(root/(source+'-observations.json')))
        for policy in subject.POLICIES:
            data,config=fixture(policy=='local400')
            for mode in ('temporal_first','spatial_first','semantic_first'):
                cases[f'{source}_{policy}_adaptive_{mode}']={}
            for side in subject.SIDES:
                for window in subject.WINDOWS:
                    identifier=f'{source}_{policy}_fixed_{side}m_{window}ms';result=native(data,config,side,window)
                    write(root/(identifier+'-policy.json'),config);write(root/(identifier+'.json'),result)
                    stats=mapped.summarize(data,config,result)
                    stats['source_accounting']=mapped.source_accounting(data,config,result)
                    cases[identifier]=dict(stats=stats,independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0),
                        config_sha256=subject.sha(root/(identifier+'-policy.json')),result_sha256=subject.sha(root/(identifier+'.json')))
    (root/'provenance').mkdir();(root/'provenance/AggregationReplay').write_bytes(b'verified fixture native binary')
    protocol=dict(sources=sources,native_binary_sha256=subject.sha(root/'provenance/AggregationReplay'))
    write(root/'protocol.json',protocol)
    summary=dict(schema='ump.temporal-region-study.v1',status='verified',completion_scope='all_44_predeclared_cases',
        executed_case_count=44,planned_case_count=44,cases=cases,protocol=protocol,protocol_sha256=subject.sha(root/'protocol.json'))
    write(root/'summary.json',summary)


class StaticRegionalScheduleTests(unittest.TestCase):
    def test_policy_only_schedule_uses_full_cell_intersection_and_strict_overlap(self):
        data,config=fixture(True)
        plan=subject.plan_schedule(data['coverage'],config,20)
        self.assertEqual(plan['cell_window_ms']['48'],400);self.assertEqual(plan['cell_window_ms']['49'],4000)
        self.assertEqual(CounterValues(plan),{400:1,4000:15})
        control=subject.plan_schedule(data['coverage'],fixture(False)[1],10)
        self.assertEqual(set(control['cell_window_ms'].values()),{4000})
        config['policy_regions'].append(dict(id='stricter',x=9,y=0,width=2,height=10,type_requirements={},
            requirements={'window_duration_ms':{'max':1000},'age_at_evaluation_ms':{'max':1000}}))
        config['policy_tree']['regions'].append('stricter')
        plan=subject.plan_schedule(data['coverage'],config,10)
        self.assertEqual(plan['cell_window_ms']['192'],400)
        self.assertEqual(plan['cell_window_ms']['193'],1000)

    def test_control_composition_exactly_equals_native_4s_all_source_metrics(self):
        for side in subject.SIDES:
            data,config=fixture();results=all_native(data,config,side)
            stats=subject.compose(data,config,subject.plan_schedule(data['coverage'],config,side),results)
            self.assertEqual(stats['input_observation_contributions'],474)
            self.assertEqual(stats['retained_fraction'],1);self.assertEqual(stats['full_input_semantic_distortion'],.5)
            self.assertEqual(stats['observation_weighted_semantic_loss'],.5)
            self.assertIsNone(stats['core_processing_ms'])
            reference=mapped.summarize(data,config,results[4000])
            reference['source_accounting']=mapped.source_accounting(data,config,results[4000])
            subject.verify_control(stats,reference)
            partition=stats['partition_audit']
            self.assertEqual(partition['scheduled_cell_intervals'],(64 if side==10 else 16)*2)
            self.assertEqual(partition['nonempty_cell_intervals'],4)

    def test_local_schedule_recovers_fresh_region_without_claiming_native_runtime(self):
        data,config=fixture(True);results=all_native(data,config,20)
        stats=subject.compose(data,config,subject.plan_schedule(data['coverage'],config,20),results)
        self.assertEqual(stats['retained_observation_contributions'],474)
        self.assertEqual(sum(c['observation_contributions'] for r in results[4000]['releases'] for c in r['cells']),237)
        self.assertEqual(stats['source_accounting']['by_source_type']['Child']['retained_observation_contributions'],158)
        self.assertEqual(stats['source_accounting']['by_source_point_region']['central']['retained_fraction'],1)
        self.assertEqual(stats['observation_weighted_interval_duration_ms'],2200)
        self.assertEqual(stats['published_policy_violations'],0)

    def test_missing_failed_private_group_or_selected_release_is_rejected(self):
        for alteration in ('private','release'):
            data,config=fixture(True);results=all_native(data,config,20)
            if alteration=='private':results[400]['windows'][0]['cells'].pop(0)
            else:results[400]['releases'][0]['cells'].pop(0)
            with self.subTest(alteration=alteration),self.assertRaises(ValueError):
                subject.compose(data,config,subject.plan_schedule(data['coverage'],config,20),results)

    def test_counts_semantics_selected_flags_and_duplicate_release_tampering_rejected(self):
        def count(r):r[400]['windows'][0]['cells'][0]['distinct_road_users']=4
        def loss(r):r[400]['windows'][0]['cells'][0]['semantic']['semantic_mean_loss']=0
        def flag(r):r[400]['windows'][0]['cells'][0]['selected']=False
        def duplicate(r):r[400]['releases'][0]['cells'].append(copy.deepcopy(r[400]['releases'][0]['cells'][0]))
        for mutation in (count,loss,flag,duplicate):
            data,config=fixture(True);results=all_native(data,config,20);mutation(results)
            with self.subTest(mutation=mutation.__name__),self.assertRaises(ValueError):
                subject.compose(data,config,subject.plan_schedule(data['coverage'],config,20),results)

    def test_source_position_identity_and_schedule_changes_are_rejected(self):
        data,config=fixture(True);plan=subject.plan_schedule(data['coverage'],config,20);results=all_native(data,config,20)
        corrupted=copy.deepcopy(data);corrupted['batches'][0]['observations'][0]['x']=30
        with self.assertRaisesRegex(ValueError,'position'):subject.compose(corrupted,config,plan,results)
        corrupted=copy.deepcopy(data);corrupted['batches'][0]['observations'].append(copy.deepcopy(corrupted['batches'][0]['observations'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):subject.compose(corrupted,config,plan,results)
        plan['cells'][48]['window_ms']=4000
        with self.assertRaisesRegex(ValueError,'solely'):subject.compose(data,config,plan,results)

    def test_semantic_antichain_and_complete_coverage_are_independently_checked(self):
        data,config=fixture(True);results=all_native(data,config,20)
        for container in (results[400]['windows'][0]['cells'][0],results[400]['releases'][0]['cells'][0]):
            container['semantic']['categories'].append(dict(category_id='adult',observation_contributions=6,distinct_contributors=2))
        with self.assertRaisesRegex(ValueError,'cut overlaps'):
            subject.compose(data,config,subject.plan_schedule(data['coverage'],config,20),results)
        data,config=fixture(True);results=all_native(data,config,20)
        data['batches'][1]['status']='unavailable';data['batches'][1]['observations']=[]
        with self.assertRaises(ValueError):subject.compose(data,config,subject.plan_schedule(data['coverage'],config,20),results)

    def test_off_only_unsatisfiable_schedule_and_incomplete_native_partitions_rejected(self):
        data,config=fixture();config['policy_tree']['root']['semantic_suppression_fraction']['max']=.1
        with self.assertRaisesRegex(ValueError,'OFF'):subject.plan_schedule(data['coverage'],config,20)
        data,config=fixture();config['policy_tree']['root']['window_duration_ms']['max']=300
        with self.assertRaisesRegex(ValueError,'No admissible'):subject.plan_schedule(data['coverage'],config,20)
        data,config=fixture();results=all_native(data,config,20);results[4000]['windows'].pop()
        with self.assertRaisesRegex(ValueError,'omits'):subject.compose(data,config,subject.plan_schedule(data['coverage'],config,20),results)

    def test_failed_nonempty_groups_are_accounted_and_cannot_disappear(self):
        data,config=fixture();config['policy_tree']['root']['semantic_max_loss']={'max':.4}
        results=all_native(data,config,20);plan=subject.plan_schedule(data['coverage'],config,20)
        stats=subject.compose(data,config,plan,results)
        self.assertEqual(stats['retained_observation_contributions'],0)
        self.assertEqual(stats['unpublished_observation_contributions'],474)
        self.assertEqual(stats['full_input_semantic_distortion'],1)
        self.assertIsNone(stats['observation_weighted_semantic_loss'])
        self.assertIsNone(stats['source_accounting']['observation_to_release_delay_ms']['p95'])
        results[4000]['windows'][0]['cells'].pop(0)
        with self.assertRaisesRegex(ValueError,'lacks its chosen'):
            subject.compose(data,config,plan,results)

    def test_end_to_end_eight_derived_cases_and_compact_motion_free_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);study_fixture(root/'study')
            with contextlib.redirect_stdout(io.StringIO()):result=subject.derive(root/'study',root/'out')
            self.assertEqual(result['status'],'verified');self.assertEqual(result['executed_case_count'],8)
            self.assertEqual(result['protocol']['source_native_binary_sha256'],
                subject.sha(root/'study/provenance/AggregationReplay'))
            self.assertEqual(set(p.name for p in (root/'out').iterdir()),{'protocol.json','summary.json','report.md'})
            for key,case in result['cases'].items():
                self.assertIsNone(case['native_runtime']);self.assertIsNone(case['native_process_wall_seconds'])
                if case['policy']=='control':self.assertTrue(case['independent_composition_audit']['positive_control_equal_native_4s'])
            text=(root/'out'/'summary.json').read_text()
            self.assertNotIn('12288-0',text);self.assertNotIn('batches',text);self.assertNotIn('observations": [',text)
            with self.assertRaisesRegex(ValueError,'fresh'):subject.derive(root/'study',root/'out')

    def test_source_binary_tampering_or_self_consistent_forged_receipt_rejected(self):
        for alteration in ('binary','receipt'):
            with self.subTest(alteration=alteration),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);study_fixture(root/'study')
                if alteration=='binary':
                    binary=root/'study/provenance/AggregationReplay';binary.write_bytes(binary.read_bytes()+b' changed')
                else:
                    protocol=subject.read(root/'study/protocol.json');protocol['native_binary_sha256']='0'*64
                    write(root/'study/protocol.json',protocol)
                    summary=subject.read(root/'study/summary.json');summary['protocol']=protocol
                    summary['protocol_sha256']=subject.sha(root/'study/protocol.json')
                    write(root/'study/summary.json',summary)
                with self.assertRaisesRegex(ValueError,'native binary receipt'):
                    subject.derive(root/'study',root/'out')
                self.assertFalse((root/'out').exists())

    def test_forged_receipts_wrong_policy_and_positive_control_metrics_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);study_fixture(root/'study')
            path=root/'study/mixed_control_fixed_10m_400ms.json';path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaisesRegex(ValueError,'receipt'):subject.derive(root/'study',root/'out')
            self.assertFalse((root/'out').exists())
        data,config=fixture();results=all_native(data,config,20)
        stats=subject.compose(data,config,subject.plan_schedule(data['coverage'],config,20),results)
        reference=mapped.summarize(data,config,results[4000]);reference['source_accounting']=mapped.source_accounting(data,config,results[4000])
        reference['source_accounting']['by_source_type']['Child']['retained_observation_contributions']-=1
        with self.assertRaisesRegex(ValueError,'Positive control'):subject.verify_control(stats,reference)


def CounterValues(plan):
    return {value:list(plan['cell_window_ms'].values()).count(value) for value in set(plan['cell_window_ms'].values())}


if __name__=='__main__':unittest.main()
