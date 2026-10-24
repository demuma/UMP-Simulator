#!/usr/bin/env python3
"""Scientific contract checks for the bounded, same-recording method comparison."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import zlib

import run_comparison as comparison


def config_fixture():
    taxonomy={'id':'fixture-pedestrians','version':'1','nodes':[
        {'id':'road_user','loss':1}, {'id':'pedestrian','parent':'road_user','loss':.5},
        {'id':'adult','parent':'pedestrian','loss':0,'input_types':['Adult Pedestrian']},
        {'id':'child','parent':'pedestrian','loss':0,'input_types':['Child Pedestrian']}]}
    return {'simulation':{'time_step':.05,'duration_seconds':2},
      'region_taxonomy':[{'type':'local','metric_requirements':{'window_duration_ms':{'max':1000}}}],
      'regions':[{'id':'small-local-patch','type':'local','area':dict(x=10,y=10,width=2.5,height=2.5),
                  'metric_requirements':{'semantic_max_loss':{'max':.5}}}],
      'sensors':[{'id':'fixture-agbs','type':'adaptive-grid-based','aggregation':{
        'application_id':'fixture-occupancy','window_ms':400,
        'history':{'retention_ms':6000},
        'publication':{'database':'private-db'},'diagnostics':{'mode':'off'},
        'policy_tree':{'id':'fixture-policy','version':'1','regions':['small-local-patch'],
          'root':{'distinct_contributors':{'min':5},'min_category_distinct_contributors':{'min':5},
                  'cell_side_m':{'min':1.25,'max':10},'window_duration_ms':{'min':400,'max':4000},
                  'age_at_evaluation_ms':{'max':4000},'semantic_max_loss':{'max':1}},
          'execution':{'strategy':'semantic_first','semantic_secondary_strategy':'temporal_first',
                       'release_trigger':'policy_satisfied','publication_model':'private_final_snapshot'}},
        'semantic_taxonomy':taxonomy}}]}


def source_fixture():
    coverage=dict(x=0,y=0,width=80,height=80,leaf_depth=6)
    observations={'schema':'ump.observation-replay.v1','run_id':'frozen-native-run','sensor_id':'fixture-agbs',
        'coverage':coverage,'sampling_period_ms':100,'end_ms':2000,
        'batches':[{'observed_at_ms':time,'sequence':time//100,'status':'measured',
                    'observations':[dict(id='episode-'+str(index),type='Adult Pedestrian',x=1+index*.02,y=1,cell_id=12288)
                                    for index in range(5)]} for time in range(100,2000,100)]}
    source={key:observations[key] for key in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms')}
    scope=dict(cell_id=192,depth=3,x=0,y=0,width=10,height=10)
    cells=[]
    windows=[];releases=[]
    for start,end,samples in [(0,1000,9),(1000,2000,10)]:
        cell={**scope,'observation_contributions':5*samples,'distinct_road_users':5,'mean_sample_occupancy':5,
          'semantic':{'schema':'ump.semantic-release.v1','taxonomy_id':'fixture-pedestrians','taxonomy_version':'1',
             'min_category_distinct_contributors':5,'semantic_max_loss':0,'semantic_mean_loss':0,
             'categories':[{'category_id':'adult','observation_contributions':5*samples,'distinct_contributors':5}]}}
        releases.append(dict(start_ms=start,end_ms=end,sealed_at_ms=end,coordination_cell=copy.deepcopy(scope),cells=[copy.deepcopy(cell)]))
        windows.append(dict(start_ms=start,end_ms=end,evaluated_at_ms=end,coordination_cell=copy.deepcopy(scope),cells=[dict(cell,selected=True)]))
    result={'schema':'ump.replay-result.v1','source':source,'parameters':{'coordination':'cell_local'},
            'input_observation_contributions':95,'runtime':{'processing_ms':12.5},'releases':releases,'windows':windows}
    return observations,result


def png():
    def chunk(kind,payload):
        return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))
            +chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\xff\xff'))+chunk(b'IEND',b''))


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.recording=self.root/'recording';self.recording.mkdir();(self.recording/'private').mkdir()
        self.binary=self.root/'AggregationReplay';self.binary.write_bytes(b'frozen mocked compiled binary\n')
        self.cfg=config_fixture();self.data,self.result=source_fixture()
        self.base=comparison.native_config(self.cfg)
        self.manifest={'schema':'ump.replay-viewer.v1','title':'Native fixture','observations':'observations.json',
            'identity_unit':'visible_episode_track','input_provenance':'Native recorded observations matched to raw source.',
            'map':{'image':'map_background.png','bounds':dict(x=0,y=0,width=80,height=80),
                   'attribution':'© OpenStreetMap contributors','labels':[],'legend':[]},
            'variants':[{'id':'native','label':'Actual native aggregation','result':'native_result.json',
                         'policy_root_requirements':[{'metric':key,**bounds} for key,bounds in self.base['policy_tree']['root'].items()],
                         'policy_regions':[]}]}
        self.write_json(self.recording/'observations.json',self.data)
        self.write_json(self.recording/'native_result.json',self.result)
        self.write_json(self.recording/'private/native_source.json',{'private_person_id':'private-oracle-not-browser-data'})
        (self.recording/'private/config.yaml').write_text(comparison.yaml.safe_dump(self.cfg),encoding='utf-8')
        (self.recording/'map_background.png').write_bytes(png())
        self.manifest['sha256']={name:comparison.sha(self.recording/name) for name in ('observations.json','native_result.json','map_background.png')}
        self.write_json(self.recording/'bundle.json',self.manifest)
        self.proof={'schema':'ump.mapped-recording-proof.v1','status':'verified','source_completed':True,
                    'files_sha256':{name:comparison.sha(self.recording/name) for name in
                        ('observations.json','native_result.json','private/native_source.json','private/config.yaml','map_background.png','bundle.json')}}
        self.write_proof()

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def write_json(path,value):
        path.write_text(json.dumps(value),encoding='utf-8')

    def write_proof(self):
        self.write_json(self.recording/'capture-proof.json',self.proof)

    def run_mocked(self,output,*,empty=False,after_run=None,policy_comparison=False,max_window_sensitivity=False,native_wall_budget_s=240):
        calls=[];queries=[];policies=[]
        audit={'status':'verified','scalar':{'valid':True},'semantic_published_cells':2,'semantic_published_bins':2,
               'regional_recomputations':[{}],'retained_by_source_group':{'private-oracle-not-browser-data':95}}
        def binary_run(command,**kwargs):
            protocol=comparison.read(output/'protocol.json')
            self.assertEqual(protocol['matrix'],comparison.max_window_variants() if max_window_sensitivity else comparison.policy_variants() if policy_comparison else comparison.variants())
            self.assertFalse((output/'summary.json').exists(),'Summary may only claim verified after every case passes')
            self.assertEqual(protocol['observations_sha256'],comparison.sha(self.recording/'observations.json'))
            if not calls:
                self.assertFalse(any(output.glob('adaptive_immediate.json')))
            self.assertEqual(Path(command[command.index('--input')+1]),self.recording.resolve()/'observations.json')
            self.assertEqual(comparison.sha(command[command.index('--input')+1]),protocol['observations_sha256'])
            policy=comparison.read(command[command.index('--config')+1]);policies.append(policy)
            result=copy.deepcopy(self.result)
            if empty:result['releases']=[];result['windows']=[]
            result['mode']=command[command.index('--mode')+1]
            self.write_json(Path(command[command.index('--output')+1]),result)
            calls.append(command)
            if after_run:after_run(len(calls))
            self.assertEqual(kwargs['timeout'],native_wall_budget_s)
            self.assertEqual(protocol['native_process_wall_budget_s'],native_wall_budget_s)
            self.assertNotIn('shell',kwargs)
            return subprocess.CompletedProcess(command,0,'bounded replay finished\n','')
        def evaluate(data,config,releases,**kwargs):
            self.assertEqual(data,self.data);queries.append(copy.deepcopy(kwargs))
            return {'fixture_evaluation':'separate exact and estimate results'}
        with mock.patch.object(comparison.subprocess,'run',side_effect=binary_run),\
             mock.patch.object(comparison.run_local_policy_replay,'audit',return_value=audit),\
             mock.patch.object(comparison.recipient_support,'evaluate',side_effect=evaluate),\
             mock.patch.object(comparison.recipient_support,'compact',return_value={'exact':{'count':1},'uniform_estimate':{'count':1}}),\
             contextlib.redirect_stdout(io.StringIO()):
            summary=comparison.compare(self.recording,output,self.binary,policy_comparison=policy_comparison,
                                       max_window_sensitivity=max_window_sensitivity,native_wall_budget_s=native_wall_budget_s)
        return summary,calls,queries,policies

    def test_matrix_predeclares_fixed_and_adaptive_methods_without_outcome_selection(self):
        matrix=comparison.variants()
        self.assertEqual(len(matrix),6)
        self.assertEqual({row['trigger'] for row in matrix if row['mode']=='semantic_first'},
                         {'policy_satisfied','priority_satisfied'})
        fixed={(row['depth'],row['window']) for row in matrix if row['mode']=='fixed'}
        self.assertEqual(fixed,{(3,400),(3,1000),(4,400),(4,1000)})
        # Canonical 80-m geometry: these depths are exactly 10-m and 5-m cells.
        self.assertEqual({80/(2**depth) for depth,_ in fixed},{5,10})
        matrix[0]['trigger']='changed-test-copy'
        self.assertNotEqual(comparison.variants()[0]['trigger'],'changed-test-copy')

    def test_every_method_keeps_all_hard_local_root_and_taxonomy_constraints(self):
        before=copy.deepcopy(self.base)
        for variant in comparison.variants():
            config=comparison.settings_for(self.base,variant)
            self.assertEqual(config['policy_tree']['root'],before['policy_tree']['root'])
            self.assertEqual(config['policy_regions'],before['policy_regions'])
            self.assertEqual(config['semantic_taxonomy'],before['semantic_taxonomy'])
            self.assertEqual(config['history'],before['history'])
            self.assertEqual(config['policy_tree']['execution']['semantic_secondary_strategy'],'temporal_first')
            self.assertEqual(config['policy_tree']['execution']['release_trigger'],variant.get('trigger','policy_satisfied'))
            config['policy_tree']['root']['distinct_contributors']['min']=999
            config['policy_regions'][0]['type_requirements']['window_duration_ms']['max']=1
            config['semantic_taxonomy']['nodes'][0]['loss']=99
            self.assertEqual(self.base,before)
        self.assertNotIn('publication',self.base)
        self.assertNotIn('diagnostics',self.base)

    def test_summary_uses_observation_weights_and_reports_suppression_against_full_input(self):
        data={'batches':[{'observations':[{}]*120}]}
        def cell(identity,n,width,category):
            return {'cell_id':identity,'width':width,'observation_contributions':n,'distinct_road_users':5,
                    'semantic':{'categories':[{'category_id':category,'observation_contributions':n,'distinct_contributors':5}]}}
        result={'releases':[dict(start_ms=0,end_ms=1000,sealed_at_ms=1100,cells=[cell(192,90,10,'pedestrian')]),
                            dict(start_ms=1000,end_ms=1400,sealed_at_ms=1500,cells=[cell(768,10,5,'adult')])]}
        stats=comparison.summarize(data,self.base,result)
        self.assertEqual(stats['retained_observation_contributions'],100)
        self.assertAlmostEqual(stats['retained_fraction'],5/6)
        self.assertEqual(stats['unpublished_observation_contributions'],20)
        self.assertAlmostEqual(stats['exact_subtype_fraction_of_input'],1/12)
        self.assertAlmostEqual(stats['exact_subtype_fraction_of_retained'],.1)
        self.assertAlmostEqual(stats['observation_weighted_semantic_loss'],.45)
        self.assertAlmostEqual(stats['observation_weighted_cell_side_m'],9.5)
        self.assertAlmostEqual(stats['observation_weighted_interval_duration_ms'],940)
        self.assertAlmostEqual(stats['observation_weighted_age_at_release_ms'],1040)
        self.assertEqual(stats['published_category_observations'],{'adult':10,'pedestrian':90})
        self.assertEqual(stats['published_cell_windows'],2)
        self.assertEqual(stats['unique_published_spatial_ids'],2)
        self.assertIsNone(stats['core_processing_ms'])

    def test_zero_denominators_are_unknown_instead_of_perfect_utility(self):
        stats=comparison.summarize({'batches':[]},self.base,{'releases':[]})
        for key in ('retained_fraction','exact_subtype_fraction_of_input','exact_subtype_fraction_of_retained',
                    'observation_weighted_semantic_loss','observation_weighted_cell_side_m',
                    'observation_weighted_interval_duration_ms','observation_weighted_age_at_release_ms'):
            self.assertIsNone(stats[key],key)
        nonempty=comparison.summarize({'batches':[{'observations':[{},{}]}]},self.base,{'releases':[]})
        self.assertEqual(nonempty['retained_fraction'],0)
        self.assertEqual(nonempty['exact_subtype_fraction_of_input'],0)
        self.assertEqual(nonempty['unpublished_observation_contributions'],2)
        self.assertIsNone(nonempty['exact_subtype_fraction_of_retained'])
        self.assertIsNone(nonempty['observation_weighted_semantic_loss'])

    def test_operational_support_distinguishes_cell_union_bins_median_and_weights(self):
        data={'batches':[{'observations':[{}]*120}]}
        def category(name,n,support):
            return dict(category_id=name,observation_contributions=n,distinct_contributors=support)
        def cell(identity,n,distinct,categories):
            return dict(cell_id=identity,width=5,observation_contributions=n,distinct_road_users=distinct,
                        semantic=dict(categories=categories))
        result={'releases':[dict(start_ms=0,end_ms=1000,sealed_at_ms=1000,cells=[
            cell(768,90,10,[category('adult',45,5),category('child',45,5)]),
            cell(769,10,4,[category('adult',10,4)])])]}
        stats=comparison.summarize(data,self.base,result)
        self.assertEqual(stats['published_cell_distinct_road_users'],dict(min=4,p50=4,observation_weighted_mean=9.4))
        self.assertEqual(stats['published_category_distinct_contributors'],
                         dict(min=4,p50=5,category_observation_weighted_mean=4.9))
        self.assertAlmostEqual(stats['retained_fraction'],100/120)
        empty=comparison.summarize(data,self.base,{'releases':[]})
        self.assertEqual(empty['retained_fraction'],0)
        self.assertTrue(all(v is None for v in empty['published_cell_distinct_road_users'].values()))
        self.assertTrue(all(v is None for v in empty['published_category_distinct_contributors'].values()))
        self.assertIn('Not measured privacy gain',stats['support_statistics_scope'])

    def test_repeated_spatial_cell_counts_as_multiple_windows_but_one_spatial_id(self):
        result=copy.deepcopy(self.result)
        stats=comparison.summarize(self.data,self.base,result)
        self.assertEqual(stats['published_cell_windows'],2)
        self.assertEqual(stats['unique_published_spatial_ids'],1)
        self.assertEqual(stats['core_processing_ms'],12.5)

    def test_full_orchestration_uses_identical_frozen_input_and_explicit_offline_viewer(self):
        before={str(path.relative_to(self.recording)):path.read_bytes() for path in self.recording.rglob('*') if path.is_file()}
        output=self.root/'comparison'
        summary,calls,queries,policies=self.run_mocked(output)
        self.assertEqual(len(calls),6)
        self.assertEqual(len(summary['cases']),6)
        for case in summary['cases'].values():
            self.assertGreaterEqual(case['native_process_wall_seconds'],0)
            self.assertGreaterEqual(case['comparison_pipeline_wall_seconds'],case['native_process_wall_seconds'])
            self.assertEqual(case['wall_seconds'],case['comparison_pipeline_wall_seconds'])
            self.assertIn('legacy alias',case['timing_scope'])
        self.assertEqual(summary['scientific_repetitions'],0)
        self.assertEqual({tuple((command[command.index('--fixed-depth')+1],command[command.index('--fixed-window-ms')+1]))
                          for command in calls if '--fixed-depth' in command},{('3','400'),('3','1000'),('4','400'),('4','1000')})
        self.assertTrue(all(policy['policy_tree']['root']==self.base['policy_tree']['root'] for policy in policies))
        self.assertTrue(all(policy['policy_regions']==self.base['policy_regions'] for policy in policies))
        for query in queries:
            self.assertEqual(query['window_ms'],1000)
            self.assertEqual(query['lags_ms'],[0,1000])
            self.assertEqual(query['categories'],['adult','child','pedestrian','road_user'])
            self.assertEqual(len(query['target_cells']),64)
            self.assertEqual({row['cell_id'] for row in query['target_cells']},set(range(192,256)))
            self.assertTrue(query['uniform_estimate'])
            self.assertEqual(query['max_queries'],comparison.QUERY_BUDGET)
        viewer=comparison.read(output/'bundle.json')
        self.assertEqual(len(viewer['variants']),6)
        self.assertIn('offline AggregationReplay',viewer['input_provenance'])
        self.assertIn('not the native sink stream',viewer['input_provenance'])
        self.assertEqual((output/'observations.json').read_bytes(),(self.recording/'observations.json').read_bytes())
        self.assertNotIn('private-oracle-not-browser-data',json.dumps(summary))
        report=(output/'report.md').read_text()
        self.assertNotIn('private-oracle-not-browser-data',report)
        self.assertNotIn('episode-0',report)
        self.assertIn('vacuous compliance',report)
        self.assertIn('mean',report.lower())
        self.assertIn('private-oracle-not-browser-data',(output/'adaptive_immediate-private-audit.json').read_text())
        self.assertEqual({str(path.relative_to(self.recording)):path.read_bytes() for path in self.recording.rglob('*') if path.is_file()},before)

    def test_support_relaxation_changes_only_two_support_floors_at_every_scope(self):
        base=copy.deepcopy(self.base)
        base['policy_tree']['root']['distinct_contributors']['max']=20
        region=base['policy_regions'][0]
        region['type_requirements']['distinct_contributors']={'min':10}
        region['requirements']['min_category_distinct_contributors']={'min':7}
        before=copy.deepcopy(base)
        relaxed,changes=comparison.relaxed_support(base)
        self.assertEqual(base,before)
        self.assertEqual(relaxed['policy_tree']['id'],base['policy_tree']['id']+'-support60')
        self.assertEqual(relaxed['policy_tree']['root']['distinct_contributors'],{'min':3,'max':20})
        self.assertEqual(relaxed['policy_tree']['root']['min_category_distinct_contributors'],{'min':3})
        self.assertEqual(relaxed['policy_regions'][0]['type_requirements']['distinct_contributors'],{'min':6})
        self.assertEqual(relaxed['policy_regions'][0]['requirements']['min_category_distinct_contributors'],{'min':5})
        self.assertEqual(len(changes),4)
        # Restore each declared change and the ID: every other byte of config is equal.
        restored=copy.deepcopy(relaxed);restored['policy_tree']['id']=base['policy_tree']['id']
        for change in changes:
            target=restored['policy_tree']['root'] if change['scope']=='root' else next(
                row for row in restored['policy_regions'] if row['id']==region['id'])[change['scope'].split(':')[-1]]
            target[change['metric']]['min']=change['before']
        self.assertEqual(restored,base)
        for floor in (True,-1,2.5,float('nan')):
            invalid=copy.deepcopy(base);invalid['policy_tree']['root']['distinct_contributors']['min']=floor
            with self.assertRaisesRegex(ValueError,'nonnegative integer'):comparison.relaxed_support(invalid)

    def test_support_policy_matrix_preserves_captured_mixed_taxonomy_and_updates_viewer_bounds(self):
        # A captured cyclist family is consumed without a hardcoded pedestrian-only catalog.
        self.cfg['sensors'][0]['aggregation']['semantic_taxonomy']['nodes'] += [
            {'id':'cyclist','parent':'road_user','loss':.5},
            {'id':'adult_cyclist','parent':'cyclist','loss':0,'input_types':['Adult Cyclist']}]
        (self.recording/'private/config.yaml').write_text(comparison.yaml.safe_dump(self.cfg))
        self.proof['files_sha256']['private/config.yaml']=comparison.sha(self.recording/'private/config.yaml');self.write_proof()
        output=self.root/'support-policies'
        summary,calls,queries,policies=self.run_mocked(output,policy_comparison=True)
        self.assertEqual(len(calls),10)
        self.assertEqual(summary['protocol']['comparison_kind'],'support_policy_sensitivity')
        self.assertEqual({row['policy_profile'] for row in summary['protocol']['matrix']},{'original','support60'})
        self.assertEqual({tuple(query['categories']) for query in queries},{('cyclist','pedestrian','road_user')})
        self.assertEqual({policy['semantic_taxonomy']['nodes'][-1]['id'] for policy in policies},{'adult_cyclist'})
        viewer=comparison.read(output/'bundle.json')
        self.assertEqual([variant['id'] for variant in viewer['variants'][:2]],
                         ['original_adaptive_immediate','support60_adaptive_immediate'])
        self.assertNotEqual(viewer['variants'][0]['policy_tree_id'],viewer['variants'][1]['policy_tree_id'])
        self.assertEqual([row['id'] for row in summary['protocol']['matrix']],
                         [row['id'] for row in comparison.policy_variants()])
        self.assertEqual([Path(command[command.index('--output')+1]).stem for command in calls],
                         [row['id'] for row in comparison.policy_variants()])
        for variant in viewer['variants']:
            relaxed=variant['id'].startswith('support60_')
            self.assertEqual(variant['policy_tree_id'],'fixture-policy'+('-support60' if relaxed else ''))
            self.assertEqual(variant['policy_tree_version'],'1')
            bounds={r['metric']:r for r in variant['policy_root_requirements']}
            self.assertEqual(bounds['distinct_contributors']['min'],3 if relaxed else 5)
            self.assertEqual(variant['policy_regions'][0]['requirements'],[
                {'metric':'semantic_max_loss','max':.5},{'metric':'window_duration_ms','max':1000}])
        self.assertTrue(all(case['independent_audit']['published_policy_violations']==0 for case in summary['cases'].values()))
        empty=self.run_mocked(self.root/'support-empty',empty=True,policy_comparison=True)[0]
        self.assertEqual(summary['protocol'],empty['protocol'])

    def test_source_type_region_accounting_and_actual_observation_delays(self):
        data,result=source_fixture();config=copy.deepcopy(self.base)
        config['policy_regions']=[dict(id='observed-patch',type='local',x=0,y=0,width=2,height=2),
                                  dict(id='overlap-patch',type='local',x=0,y=0,width=2,height=2)]
        result['releases']=result['releases'][:1]
        result['releases'][0]['sealed_at_ms']=1100
        stats=comparison.source_accounting(data,config,result)
        self.assertEqual(stats['by_source_type']['Adult Pedestrian'],dict(input_observation_contributions=95,
            retained_observation_contributions=45,unpublished_observation_contributions=50,retained_fraction=45/95))
        for name in ('observed-patch','overlap-patch'):
            self.assertEqual(stats['by_source_point_region'][name]['retained_observation_contributions'],45)
        self.assertIsNone(stats['by_source_point_region']['outside_policy_regions']['retained_fraction'])
        self.assertEqual(stats['observation_to_release_delay_ms'],dict(mean=600,p50=600,p95=1000,p99=1000,maximum=1000))
        # Counting the same ancestor twice is rejected, as is a bad declared sum.
        duplicate=copy.deepcopy(result);duplicate['releases']*=2
        with self.assertRaisesRegex(ValueError,'overlap'):comparison.source_accounting(data,config,duplicate)
        duplicate=copy.deepcopy(result);duplicate['releases'][0]['cells'][0]['observation_contributions']+=1
        with self.assertRaisesRegex(ValueError,'contribution total'):comparison.source_accounting(data,config,duplicate)
        stats=comparison.source_accounting(data,config,{'releases':[]})
        self.assertEqual(stats['by_source_type']['Adult Pedestrian']['retained_fraction'],0)
        self.assertTrue(all(value is None for value in stats['observation_to_release_delay_ms'].values()))

    def test_source_accounting_rejects_overlapping_ancestor_descendant_ownership(self):
        data,result=source_fixture()
        child=copy.deepcopy(result['releases'][0]['cells'][0]);child['cell_id']=768;child['depth']=4
        result['releases'][0]['cells'].append(child)
        with self.assertRaisesRegex(ValueError,'overlapping published ancestors'):
            comparison.source_accounting(data,self.base,result)

    @unittest.skipUnless(os.environ.get('UMP_REPLAY_BINARY'),'Set UMP_REPLAY_BINARY for actual C++ comparison integration')
    def test_actual_native_support_comparison_releases_three_users_only_under_relaxed_policy(self):
        cfg=copy.deepcopy(self.cfg);aggregation=cfg['sensors'][0]['aggregation']
        aggregation['history'].update(max_bins=64,max_observations=10000,max_identity_bytes=1000000,max_buckets=512)
        aggregation['spatial_selection']={'min_depth':3,'max_evaluations':8192,'preserve_valid_descendants':False}
        aggregation['temporal_adaptation']={'coordination':'cell_local','extension_step_ms':100,
                                           'max_window_ms':4000,'max_evaluations':64,'max_active_cells':4096}
        data=copy.deepcopy(self.data)
        for batch in data['batches']:batch['observations']=batch['observations'][:3]
        self.write_json(self.recording/'observations.json',data)
        (self.recording/'private/config.yaml').write_text(comparison.yaml.safe_dump(cfg))
        for name in ('observations.json','private/config.yaml'):
            self.proof['files_sha256'][name]=comparison.sha(self.recording/name)
        # The viewer manifest digest must follow the changed observation fixture.
        self.manifest['sha256']['observations.json']=comparison.sha(self.recording/'observations.json')
        self.write_json(self.recording/'bundle.json',self.manifest)
        self.proof['files_sha256']['bundle.json']=comparison.sha(self.recording/'bundle.json');self.write_proof()
        with contextlib.redirect_stdout(io.StringIO()):
            summary=comparison.compare(self.recording,self.root/'native-support-policies',
                os.environ['UMP_REPLAY_BINARY'],policy_comparison=True)
        for name,case in summary['cases'].items():
            self.assertEqual(case['independent_audit']['status'],'verified')
            self.assertEqual(case['independent_audit']['published_policy_violations'],0)
            if name.startswith('original_'):self.assertEqual(case['stats']['retained_fraction'],0)
            else:self.assertGreater(case['stats']['retained_fraction'],0)
        self.assertEqual(summary['cases']['support60_adaptive_immediate']['stats']['source_accounting']
                         ['by_source_type']['Adult Pedestrian']['input_observation_contributions'],57)
        self.assertEqual(summary['source']['peak_observed_simultaneous_tracks'],3)
        report=(self.root/'native-support-policies/report.md').read_text()
        self.assertIn('support60_adaptive_immediate | 0 | interior |',report)
        self.assertIn('Estimated occupancy MAE',report)
        self.assertIn('original_adaptive_immediate | 0.00%',report)
        self.assertNotIn('episode-0',report)

    def add_building_access(self):
        access={'schema':'ump.building-access.v1','bounds':dict(x=0,y=0,width=80,height=80),
                'buildings':[{'id':'way1','name':'Shop building','polygons':[[[10,10],[30,10],[30,30],[10,30],[10,10]]]}],
                'portals':[{'id':'entry1','building_id':'way1','point':[20,10],
                            'facade':[[10,10],[30,10]],'width_m':1.2,'provenance':'synthetic'}]}
        self.write_json(self.recording/'building_access.json',access)
        self.manifest['map']['building_access']='building_access.json'
        self.manifest['sha256']['building_access.json']=comparison.sha(self.recording/'building_access.json')
        self.write_json(self.recording/'bundle.json',self.manifest)
        self.proof['files_sha256']['building_access.json']=comparison.sha(self.recording/'building_access.json')
        self.proof['files_sha256']['bundle.json']=comparison.sha(self.recording/'bundle.json');self.write_proof()

    def test_public_building_geometry_survives_same_source_comparison_without_private_sidecars(self):
        self.add_building_access();output=self.root/'building-comparison'
        self.run_mocked(output)
        viewer=comparison.read(output/'bundle.json')
        self.assertEqual(viewer['map']['building_access'],'building_access.json')
        self.assertEqual((output/'building_access.json').read_bytes(),(self.recording/'building_access.json').read_bytes())
        self.assertEqual(viewer['sha256']['building_access.json'],comparison.sha(output/'building_access.json'))
        self.assertFalse((output/'private/native_source.json').exists())

    def test_storefront_v2_geometry_is_retained_without_native_navigation_or_schedules(self):
        self.add_building_access();path=self.recording/'building_access.json';access=comparison.read(path)
        access['schema']='ump.building-access.v2';access.update(
            store_fronts=[{'id':'front1','destination_id':'shop1','building_id':'way1','portal_id':'entry1',
                'poi':{'osm_type':'node','osm_id':2,'name':'Fixture shop','point':[20,15]},
                'frontage':[[10,10],[30,10]],'provenance':'synthetic_poi_projection',
                'projection_method':'orthogonal_to_reachable_original_facade'}],facade_separators=[],
            boundary_intervals=[{'id':'west1','mode':'walking','side':'west','points':[[0,20],[0,40]],
                'length_m':20,'spawn_supported':True,'provenance':'derived_frozen_functional_zone_boundary'}],
            navigation={'body_clearance_m':.55,'allowed_center_polygons_sha256':'a'*64,'scope':'Public geometry digest only.'})
        self.write_json(path,access);self.manifest['sha256'][path.name]=comparison.sha(path)
        self.write_json(self.recording/'bundle.json',self.manifest)
        self.proof['files_sha256'][path.name]=comparison.sha(path)
        self.proof['files_sha256']['bundle.json']=comparison.sha(self.recording/'bundle.json');self.write_proof()
        output=self.root/'storefront-comparison';self.run_mocked(output)
        self.assertEqual((output/path.name).read_bytes(),path.read_bytes())
        public=comparison.read(output/path.name)
        self.assertEqual(public['store_fronts'][0]['poi']['name'],'Fixture shop')
        self.assertNotIn('allowed_center_polygons',public['navigation'])
        self.assertFalse((output/'private/config.yaml').exists())

    def test_public_building_recording_digest_cannot_be_missing_or_changed(self):
        self.add_building_access()
        original=(self.recording/'building_access.json').read_bytes()
        (self.recording/'building_access.json').write_bytes(original+b' ')
        self.assert_preflight_rejects()
        (self.recording/'building_access.json').write_bytes(original)
        self.proof['files_sha256'].pop('building_access.json');self.write_proof()
        self.assert_preflight_rejects()

    def test_protocol_and_query_bank_do_not_change_when_every_variant_suppresses_output(self):
        populated,_,_,_=self.run_mocked(self.root/'populated')
        empty,_,_,_=self.run_mocked(self.root/'empty',empty=True)
        self.assertEqual(populated['protocol'],empty['protocol'])
        self.assertNotEqual(populated['cases']['adaptive_immediate']['stats']['retained_fraction'],
                            empty['cases']['adaptive_immediate']['stats']['retained_fraction'])

    def assert_preflight_rejects(self):
        with mock.patch.object(comparison.subprocess,'run') as run:
            with self.assertRaises((ValueError,OSError,KeyError)):comparison.compare(self.recording,self.root/'rejected',self.binary)
            run.assert_not_called()
        self.assertFalse((self.root/'rejected').exists())

    def test_posthoc_maximum_window_study_is_separate_and_retains_both_policy_contracts(self):
        output=self.root/'posthoc-max-window'
        summary,calls,queries,policies=self.run_mocked(output,max_window_sensitivity=True)
        self.assertEqual(len(calls),4)
        self.assertEqual(summary['protocol']['comparison_kind'],'post_hoc_fixed_max_window_sensitivity')
        self.assertEqual(summary['protocol']['analysis_status'],'post_hoc_sensitivity_after_ten_case_results')
        self.assertEqual({command[command.index('--fixed-window-ms')+1] for command in calls},{'4000'})
        self.assertEqual({command[command.index('--fixed-depth')+1] for command in calls},{'3','4'})
        self.assertEqual({policy['policy_tree']['root']['distinct_contributors']['min'] for policy in policies},{3,5})
        self.assertTrue(all(policy['policy_regions']==self.base['policy_regions'] for policy in policies))
        self.assertTrue(all(query['categories']==['pedestrian','road_user'] for query in queries))
        self.assertEqual(summary['protocol']['policy_changes'],comparison.relaxed_support(self.base)[1])
        self.assertIn('Post-hoc',summary['protocol']['portfolio_scope'])
        self.assertIn('post-hoc',comparison.read(output/'bundle.json')['title'])
        self.assertEqual(len(comparison.policy_variants()),10)
        self.assertIn('Post-hoc fixed maximum-window', (output/'report.md').read_text())
        with mock.patch.object(comparison.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'either'):
                comparison.compare(self.recording,self.root/'mixed-study',self.binary,
                                   policy_comparison=True,max_window_sensitivity=True)
            run.assert_not_called()
        self.assertFalse((self.root/'mixed-study').exists())

    def test_native_wall_budget_is_predeclared_and_does_not_change_experiment_matrix(self):
        default,_,_,_=self.run_mocked(self.root/'default-budget',policy_comparison=True)
        longer,_,_,_=self.run_mocked(self.root/'longer-budget',policy_comparison=True,native_wall_budget_s=900)
        self.assertEqual(default['protocol']['native_process_wall_budget_s'],240)
        self.assertEqual(longer['protocol']['native_process_wall_budget_s'],900)
        unchanged=copy.deepcopy(longer['protocol']);unchanged['native_process_wall_budget_s']=240
        self.assertEqual(default['protocol'],unchanged)
        self.assertEqual(default['cases'].keys(),longer['cases'].keys())

    def test_invalid_native_wall_budget_rejected_before_output_or_process(self):
        for budget in (0,-1,3601,True,240.5,'900'):
            output=self.root/('invalid-budget-'+str(budget))
            with self.subTest(budget=budget),mock.patch.object(comparison.subprocess,'run') as run:
                with self.assertRaisesRegex(ValueError,'1 to 3600'):
                    comparison.compare(self.recording,output,self.binary,native_wall_budget_s=budget)
                run.assert_not_called()
                self.assertFalse(output.exists())

    def test_query_budget_is_predeclared_and_checked_before_binary_execution(self):
        # Same verified input, smaller test-only resource cap; no adaptive
        # truncation of the query bank after observing an outcome.
        with mock.patch.object(comparison,'QUERY_BUDGET',1):
            self.assert_preflight_rejects()

    def test_changed_source_policy_native_result_and_private_ground_truth_rejected(self):
        for relative in ('observations.json','native_result.json','private/native_source.json','private/config.yaml','map_background.png','bundle.json'):
            with self.subTest(relative=relative):
                path=self.recording/relative;original=path.read_bytes();path.write_bytes(original+b'\nchanged artifact\n')
                self.assert_preflight_rejects();path.write_bytes(original)

    def test_incomplete_or_unverified_recording_proof_rejected(self):
        original=copy.deepcopy(self.proof)
        for mutation in ('schema','status','source','hashes','missing_required_hash','bad_digest'):
            with self.subTest(mutation=mutation):
                self.proof=copy.deepcopy(original)
                if mutation=='schema':self.proof['schema']='unknown'
                if mutation=='status':self.proof['status']='pending'
                if mutation=='source':self.proof['source_completed']=False
                if mutation=='hashes':self.proof['files_sha256']={}
                if mutation=='missing_required_hash':self.proof['files_sha256'].pop('private/config.yaml')
                if mutation=='bad_digest':self.proof['files_sha256']['private/config.yaml']='not-a-digest'
                self.write_proof();self.assert_preflight_rejects()
        self.proof=original;self.write_proof()

    def test_proof_paths_cannot_escape_or_alias_recording(self):
        original=copy.deepcopy(self.proof)
        external=self.root/'outside.json';external.write_text('{}')
        link=self.recording/'linked.json';link.symlink_to(external)
        for relative in ('../outside.json',str(external),'private//config.yaml','private/./config.yaml','private\\config.yaml','linked.json'):
            with self.subTest(relative=relative):
                self.proof=copy.deepcopy(original);self.proof['files_sha256'][relative]=comparison.sha(external)
                self.write_proof();self.assert_preflight_rejects()
        self.proof=original;self.write_proof()

    def test_source_bundle_validation_precedes_any_comparison_execution(self):
        self.manifest['variants'][0]['result']='../outside.json'
        self.write_json(self.recording/'bundle.json',self.manifest)
        self.proof['files_sha256']['bundle.json']=comparison.sha(self.recording/'bundle.json');self.write_proof()
        self.assert_preflight_rejects()

    def test_existing_comparison_directory_is_preserved(self):
        output=self.root/'existing';output.mkdir();sentinel=output/'preserve.txt';sentinel.write_text('keep')
        with mock.patch.object(comparison.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'new comparison directory'):comparison.compare(self.recording,output,self.binary)
            run.assert_not_called()
        self.assertEqual(sentinel.read_text(),'keep')

    def test_binary_or_source_change_during_run_aborts_verified_summary(self):
        for mutation in ('binary','source'):
            with self.subTest(mutation=mutation):
                target=self.binary if mutation=='binary' else self.recording/'observations.json';original=target.read_bytes()
                output=self.root/('changed-'+mutation)
                def change(count):
                    if count==1:target.write_bytes(original+b' ')
                with self.assertRaisesRegex(ValueError,'Frozen binary/source changed'):
                    self.run_mocked(output,after_run=change)
                self.assertFalse((output/'summary.json').exists())
                target.write_bytes(original)

    def test_failed_binary_cannot_produce_a_verified_summary(self):
        output=self.root/'failed'
        failed=subprocess.CompletedProcess([],1,'','deliberate binary failure')
        with mock.patch.object(comparison.subprocess,'run',return_value=failed):
            with self.assertRaisesRegex(RuntimeError,'deliberate binary failure'):comparison.compare(self.recording,output,self.binary)
        self.assertTrue((output/'protocol.json').exists())
        self.assertFalse((output/'summary.json').exists())
        self.assertFalse((output/'bundle.json').exists())


if __name__=='__main__':
    unittest.main()
