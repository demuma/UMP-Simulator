#!/usr/bin/env python3
"""Independent native-publication fixtures for the private mapped replay boundary."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import struct
import zlib
from unittest import mock

import export_replay as export


ORIGIN = datetime(2026,10,23,10,30,tzinfo=timezone.utc)
BASE = 'UMP_Mapped_'+'a'*32
RUN = 'native-fixture-run'
SENSOR = 'mapped-fixture-agbs'
APPLICATION = 'mapped-fixture-occupancy'
POLICY = 'fixture-policy'
SCOPE = dict(cell_id=192,depth=3,x=0,y=0,width=10,height=10)


def stamp(milliseconds):
    return (ORIGIN+timedelta(milliseconds=milliseconds)).isoformat(timespec='milliseconds').replace('+00:00','Z')


def native_id(start,end):
    parts=''.join(str(len(text))+':'+text for text in (RUN,SENSOR,APPLICATION))
    return f'ump-release-v2/{parts}/{start}/{end}/192/3'


def native_fixture():
    """Hand-calculated 80-m/D6 source: 5 tracks, 4 measured occupied frames.

    GT has 50-ms states and lifecycle rows; raw AGBS contains only occupied
    100-ms leaf records. A committed empty retirement is private-only. Counts
    are authored here, not obtained by calling exporter helpers under test.
    """
    root={'distinct_contributors':{'min':5},'min_category_distinct_contributors':{'min':5},
          'cell_side_m':{'min':1.25,'max':10},'window_duration_ms':{'min':400,'max':4000},
          'age_at_evaluation_ms':{'max':4000},'semantic_max_loss':{'max':.5}}
    cfg={'simulation':{'scenario':'mapped_visits','time_step':.05,'duration_seconds':1},
         'database':{'db_name':BASE,'collection_name':'Agents'},
         'region_taxonomy':[],'regions':[],
         'sensors':[{'id':SENSOR,'type':'adaptive-grid-based','frame_rate':10,
           'detection_area':{'x':0,'y':0,'width':80,'height':80},'grid':{'max_depth':6},
           'database':{'db_name':BASE,'collection_name':'AGB_Sensor_Data_V3'},
           'aggregation':{'application_id':APPLICATION,
             'policy_tree':{'id':POLICY,'version':'1','root':root,'regions':[],
                            'execution':{'strategy':'semantic_first','semantic_secondary_strategy':'temporal_first','release_trigger':'policy_satisfied'}},
             'publication':{'database':BASE+'_Releases','collection':'Published',
                            'journal_database':BASE+'_Private','journal_collection':'Journal'},
             'semantic_taxonomy':{'id':'fixture-taxonomy','version':'1','nodes':[
               {'id':'road_user','loss':1}, {'id':'pedestrian','parent':'road_user','loss':.5},
               {'id':'adult_pedestrian','parent':'pedestrian','loss':0,'input_types':['Adult Pedestrian']},
               {'id':'child_pedestrian','parent':'pedestrian','loss':0,'input_types':['Child Pedestrian']}]
             }}}]}
    agents=[{'data_type':'metadata','timestamp':stamp(0),'source_model':'mapped_visits',
             'observation_identity_unit':'visible_episode_track','ground_truth_identity_unit':'synthetic_person',
             'simulation_area':{'width':80,'height':80},'frame_rate':20},
            {'data_type':'mapped source summary','completed_steps':20,'source_elapsed_ms':1000,
             'planned_duration_ms':1000,'scheduled_people':5,'scheduled_tracks':5}]
    for index in range(5):
        track=f'track-{index+1:03d}'; person=f'private-person-{index+1:03d}'
        for at in range(0,500,50):
            agents.append({'data_type':'agent data','timestamp':stamp(at),'agent_id':track,
                           'observation_track_id':track,'private_person_id':person,'type':'Adult Pedestrian',
                           'position':{'x':1+index*.02,'y':1},'velocity':{'x':0,'y':0}})
        for event,at in [('episode_start',0),('episode_end',500)]:
            agents.append({'data_type':'mapped lifecycle event','event':event,'at_ms':at,
                           'private_person_id':person,'observation_track_id':track,'route_id':'fixture-route',
                           'portal_id':'fixture-portal'})
    raw_sensor=[{'data_type':'adaptive grid data','sensor_id':SENSOR,'timestamp':stamp(at),
                 'cell_id':12288,'cell_size':1.25,'cell_position':{'x':0,'y':0},'total_agents':5,
                 'agent_type_count':[{'type':'Adult Pedestrian','count':5}]} for at in (100,200,300,400)]
    semantic={'schema':'ump.semantic-release.v1','taxonomy_id':'fixture-taxonomy','taxonomy_version':'1',
              'min_category_distinct_contributors':5,'semantic_max_loss':.5,'semantic_mean_loss':.5,
              'categories':[{'category_id':'pedestrian','observation_contributions':20,'distinct_contributors':5}]}
    cell={**SCOPE,'counts':{'observation_contributions':20,'distinct_contributors':5,'mean_sample_occupancy':5},
          'effective_policy_id':'fixture-effective-0','semantic':semantic}
    def payload(start,end,cells):
        return {'_id':native_id(start,end),'schema':'ump.release.v2','data_role':'recipient_release',
                'run_id':RUN,'sensor_id':SENSOR,'application_id':APPLICATION,'model':'private_final_snapshot',
                'policy_id':POLICY,'policy_version':'1','start_ms':start,'end_ms':end,'sealed_at_ms':end,
                'coordination_cell':copy.deepcopy(SCOPE),'cells':cells}
    release=payload(0,500,[cell]); empty=payload(500,1000,[])
    def journal(release):
        return {'_id':release['_id'],'schema':'ump.publication-journal.v1','data_role':'private_publication_journal',
                'state':'committed','run_id':RUN,'sensor_id':SENSOR,'application_id':APPLICATION,
                'start_ms':release['start_ms'],'end_ms':release['end_ms'],'release':copy.deepcopy(release)}
    return cfg,{'agents':agents,'sensor':raw_sensor,'releases':[release],'journals':[journal(release),journal(empty)]}


class NativeRecordingTests(unittest.TestCase):
    def setUp(self):
        self.cfg,self.raw=native_fixture()

    def build(self):
        return export.build_recording(self.cfg,self.raw)

    def replace_public(self):
        """Keep native journal payload identical when testing source-independent defects."""
        self.raw['journals'][0]['release']=copy.deepcopy(self.raw['releases'][0])

    def test_complete_native_recording_includes_verified_measured_empty_opportunities(self):
        replay,result,proof=self.build()
        self.assertEqual([b['observed_at_ms'] for b in replay['batches']],list(range(100,1000,100)))
        self.assertEqual([len(b['observations']) for b in replay['batches']],[5,5,5,5,0,0,0,0,0])
        self.assertTrue(all(b['status']=='measured' for b in replay['batches']))
        self.assertEqual(replay['coverage'],dict(x=0,y=0,width=80,height=80,leaf_depth=6))
        self.assertEqual(replay['batches'][0]['observations'][0]['cell_id'],12288)
        self.assertEqual(result['input_observation_contributions'],20)
        self.assertEqual(proof['status'],'verified')
        self.assertEqual(proof['gt_rows'],50)
        self.assertEqual(proof['measured_samples'],9)
        self.assertEqual(proof['measured_empty_samples'],5)
        self.assertEqual(proof['raw_cell_rows'],4)
        self.assertEqual(proof['published_cell_windows'],1)
        self.assertEqual(proof['track_person_inflated_published_cells'],0)
        self.assertTrue(proof['source_horizon_completed'])
        self.assertTrue(proof['all_scheduled_episodes_completed'])
        self.assertEqual(proof['lifecycle_quality']['expected_gt_rows'],50)
        self.assertEqual(proof['lifecycle_quality']['active_episodes_at_horizon'],0)
        self.assertEqual(proof['motion_quality']['status'],'diagnostics_not_recorded')
        self.assertTrue(all(v is None for v in proof['motion_quality']['reported_diagnostics'].values()))

    def test_native_timestamp_events_and_processing_clock_are_audited(self):
        for row in self.raw['agents']:
            if row.get('data_type')=='mapped lifecycle event':
                row['event']={'episode_start':'visible_start','episode_end':'visible_end'}[row['event']]
                row['timestamp']=stamp(row.pop('at_ms'))
                row['processed_at_ms']=export.epoch_ms(row['timestamp'])-export.epoch_ms(stamp(0))
        self.assertEqual(self.build()[2]['lifecycle_quality']['event_rows'],10)

    def test_unsampled_missing_gt_state_does_not_become_measured_empty_evidence(self):
        for mode in ('one_state','whole_episode'):
            with self.subTest(mode=mode):
                self.setUp()
                self.raw['agents']=[r for r in self.raw['agents'] if not
                    (r.get('data_type')=='agent data' and r['agent_id']=='track-001'
                     and (mode=='whole_episode' or r['timestamp']==stamp(50)))]
                with self.assertRaisesRegex(ValueError,'Missing GT state inside'):
                    self.build()

    def test_gt_state_during_hidden_gap_or_at_exclusive_end_is_rejected(self):
        for at in (500,550):
            with self.subTest(at=at):
                self.setUp()
                row=copy.deepcopy(next(r for r in self.raw['agents'] if r.get('data_type')=='agent data'))
                row['timestamp']=stamp(at);self.raw['agents'].append(row)
                with self.assertRaisesRegex(ValueError,'outside recorded visible episode'):
                    self.build()

    def test_lifecycle_identity_duplicate_clock_and_missing_event_failures(self):
        for mode in ('missing_start','missing_end','missing_pair','duplicate','person','route',
                     'backwards','unknown','negative','fractional','timestamp_conflict','processing'):
            with self.subTest(mode=mode):
                self.setUp()
                events=[r for r in self.raw['agents'] if r.get('data_type')=='mapped lifecycle event']
                begin,finish=events[:2]
                if mode=='missing_start':self.raw['agents'].remove(begin)
                if mode=='missing_end':self.raw['agents'].remove(finish)
                if mode=='missing_pair':
                    self.raw['agents'].remove(begin);self.raw['agents'].remove(finish)
                if mode=='duplicate':self.raw['agents'].append(copy.deepcopy(begin))
                if mode=='person':finish['private_person_id']='wrong-private-person'
                if mode=='route':finish['route_id']='wrong-route'
                if mode=='backwards':finish['at_ms']=0
                if mode=='unknown':begin['event']='random_event'
                if mode=='negative':begin['at_ms']=-1
                if mode=='fractional':begin['at_ms']=.5
                if mode=='timestamp_conflict':begin['timestamp']=stamp(50)
                if mode=='processing':finish['processed_at_ms']=450
                with self.assertRaises(ValueError):self.build()

    def test_complete_horizon_accepts_and_labels_censored_stalled_and_pending_episodes(self):
        summary=next(r for r in self.raw['agents'] if r['data_type']=='mapped source summary')
        summary.update(scheduled_people=7,scheduled_tracks=7,motion_model='bounded_swept_body_corridor_following',
                       realized_track_starts=6,realized_track_ends=5,pending_tracks=1,active_tracks=1,
                       blocked_motion_steps=23,admission_wait_steps=4,merge_admission_wait_steps=3,
                       max_consecutive_stop_ms=50,active_stalled_tracks=1,body_overlap_violations=0)
        self.raw['agents'] += [
            {'data_type':'mapped lifecycle event','event':'visible_start','timestamp':stamp(950),
             'processed_at_ms':950,'observation_track_id':'last-active-track','private_person_id':'private-active-person',
             'route_id':'fixture-route','portal_id':'fixture-portal'},
            {'data_type':'agent data','timestamp':stamp(950),'agent_id':'last-active-track',
             'observation_track_id':'last-active-track','private_person_id':'private-active-person',
             'type':'Adult Pedestrian','position':{'x':1,'y':1},'velocity':{'x':0,'y':0}}]
        _,_,proof=self.build()
        self.assertTrue(proof['source_completed'])  # Explicit compatibility meaning: clock only.
        self.assertTrue(proof['source_horizon_completed'])
        self.assertFalse(proof['all_scheduled_episodes_completed'])
        self.assertEqual(proof['lifecycle_quality']['status'],'censored_at_source_horizon')
        self.assertEqual(proof['lifecycle_quality']['active_episodes_at_horizon'],1)
        self.assertEqual(proof['lifecycle_quality']['pending_episodes_at_horizon'],1)
        self.assertEqual(proof['motion_quality']['status'],'reported_stalls_at_horizon')
        self.assertEqual(proof['motion_quality']['reported_diagnostics']['merge_admission_wait_steps'],3)
        self.assertNotIn('private-active-person',json.dumps(proof))
        self.assertIn('general queue liveness',proof['motion_quality']['scope'])

    def test_reported_overlap_counter_is_labelled_without_inventing_a_safety_proof(self):
        summary=next(r for r in self.raw['agents'] if r['data_type']=='mapped source summary')
        summary['body_overlap_violations']=2
        proof=self.build()[2]
        self.assertEqual(proof['motion_quality']['status'],'reported_body_overlap_violations')
        self.assertTrue(proof['all_scheduled_episodes_completed'])

    def test_source_diagnostics_must_match_actual_lifecycle_and_be_nonnegative(self):
        for name,value in (('realized_track_starts',4),('realized_track_ends',4),
                           ('active_tracks',1),('pending_tracks',1),('active_stalled_tracks',1),
                           ('blocked_motion_steps',-1),('admission_wait_steps',False),
                           ('merge_admission_wait_steps',1.5),('max_consecutive_stop_ms',-50)):
            with self.subTest(name=name):
                self.setUp()
                next(r for r in self.raw['agents'] if r['data_type']=='mapped source summary')[name]=value
                with self.assertRaises(ValueError):self.build()

    def test_configured_episode_registry_is_independently_checked(self):
        self.cfg['mapped_scene']={'people':[{'person_id':f'private-person-{i:03d}',
            'episodes':[{'track_id':f'track-{i:03d}','route_id':'fixture-route','start_ms':0}]}
            for i in range(1,6)]}
        self.assertTrue(self.build()[2]['all_scheduled_episodes_completed'])
        for mode in ('person','route','tracks','people'):
            with self.subTest(mode=mode):
                cfg=copy.deepcopy(self.cfg)
                if mode=='person':cfg['mapped_scene']['people'][0]['person_id']='wrong-person'
                if mode=='route':cfg['mapped_scene']['people'][0]['episodes'][0]['route_id']='wrong-route'
                if mode=='tracks':cfg['mapped_scene']['people'][0]['episodes']=[]
                if mode=='people':cfg['mapped_scene']['people'].pop()
                with self.assertRaises(ValueError):export.build_recording(cfg,self.raw)

    def test_event_visibility_half_open_rounding_with_non_clock_boundaries(self):
        # Event times may fall between source steps in stateless integration.
        # Only source states 50 and100 belong to [1,101); 0 and150 do not.
        summary={'scheduled_tracks':1,'scheduled_people':1}
        raw={'agents':[{'data_type':'mapped lifecycle event','event':event,'at_ms':at,
                        'private_person_id':'private','observation_track_id':'track','route_id':'r'}
                       for event,at in [('episode_start',1),('episode_end',101)]]}
        frames={50:{'track':{}},100:{'track':{}}}
        quality=export.audit_lifecycle({},raw,frames,{'track':'private'},0,50,200,summary)
        self.assertEqual(quality['lifecycle_quality']['expected_gt_rows'],2)
        self.assertTrue(quality['all_scheduled_episodes_completed'])
        frames[0]={'track':{}}
        with self.assertRaisesRegex(ValueError,'outside recorded visible episode'):
            export.audit_lifecycle({},raw,frames,{'track':'private'},0,50,200,summary)

    def test_horizon_start_is_realized_but_not_visible_in_an_earlier_gt_frame(self):
        raw={'agents':[{'data_type':'mapped lifecycle event','event':'visible_start','at_ms':200,
                       'private_person_id':'private','observation_track_id':'track','route_id':'r'}]}
        quality=export.audit_lifecycle({},raw,{}, {},0,50,200,
                                       {'scheduled_tracks':1,'scheduled_people':1})
        self.assertFalse(quality['all_scheduled_episodes_completed'])
        self.assertEqual(quality['lifecycle_quality']['expected_gt_rows'],0)
        self.assertEqual(quality['lifecycle_quality']['active_episodes_at_horizon'],1)

    def test_one_person_cannot_have_overlapping_visible_tracks(self):
        for row in self.raw['agents']:
            if row.get('observation_track_id')=='track-002':
                row['private_person_id']='private-person-001'
        with self.assertRaisesRegex(ValueError,'overlapping visible episodes'):
            self.build()

    def test_native_nested_counts_and_semantics_are_preserved_without_reaggregation(self):
        _,result,_=self.build()
        self.assertEqual(result['mode'],'native_recorded')
        cell=result['releases'][0]['cells'][0]
        self.assertEqual(cell['observation_contributions'],20)
        self.assertEqual(cell['distinct_road_users'],5)
        self.assertEqual(cell['mean_sample_occupancy'],5)
        self.assertEqual(cell['semantic'],self.raw['releases'][0]['cells'][0]['semantic'])
        self.assertEqual(cell['effective_policy_id'],'fixture-effective-0')
        self.assertNotIn('checks',cell)
        self.assertNotIn('counts',cell)
        self.assertEqual(result['releases'][0]['sealed_at_ms'],500)

    def test_private_journal_retirements_do_not_fabricate_rejected_candidate_checks(self):
        _,result,proof=self.build()
        self.assertEqual(len(result['releases']),1)
        self.assertEqual(len(result['windows']),2)
        self.assertEqual(result['windows'][1]['cells'],[])
        selected=result['windows'][0]['cells'][0]
        self.assertTrue(selected['selected'])
        self.assertEqual(selected['checks'],[])
        self.assertIn('not_recorded',selected['diagnostics_status'])
        self.assertIn('rejected_candidates_unavailable',result['windows'][0]['diagnostics_status'])
        self.assertEqual(proof['private_retirements'],2)
        self.assertEqual(proof['private_empty_retirements'],1)

    def test_private_person_mapping_never_enters_browser_input(self):
        replay,result,proof=self.build()
        browser=json.dumps([replay,result,proof])
        self.assertNotIn('private-person-',browser)
        self.assertNotIn('private_person_id',browser)
        self.assertNotIn('observation_track_id',browser)
        self.assertIn('track-001',json.dumps(replay))
        self.assertNotIn('track-001',json.dumps(result))

    def test_fragmented_person_remains_multiple_tracks_and_inflation_is_reported(self):
        for row in self.raw['agents']:
            if row.get('data_type')=='agent data' and row['agent_id']=='track-001' and export.epoch_ms(row['timestamp'])-export.epoch_ms(stamp(0))>=250:
                row['agent_id']=row['observation_track_id']='track-006'
            elif row.get('data_type')=='mapped source summary':
                row['scheduled_tracks']=6
            elif row.get('data_type')=='mapped lifecycle event' and row['observation_track_id']=='track-001' and row['event']=='episode_end':
                row['at_ms']=250
        for event,at in [('episode_start',250),('episode_end',500)]:
            self.raw['agents'].append({'data_type':'mapped lifecycle event','event':event,'at_ms':at,
                    'private_person_id':'private-person-001','observation_track_id':'track-006',
                    'route_id':'fixture-route','portal_id':'fixture-portal'})
        cell=self.raw['releases'][0]['cells'][0]
        cell['counts']['distinct_contributors']=6
        cell['semantic']['categories'][0]['distinct_contributors']=6
        cell['semantic']['min_category_distinct_contributors']=6
        self.replace_public()
        replay,result,proof=self.build()
        identities={o['id'] for b in replay['batches'] for o in b['observations']}
        self.assertEqual(len(identities),6)
        self.assertEqual(result['releases'][0]['cells'][0]['distinct_road_users'],6)
        self.assertEqual(proof['track_person_inflated_published_cells'],1)
        self.assertEqual(result['input_observation_contributions'],20)

    def test_export_does_not_mutate_native_input_or_policy(self):
        before=json.dumps([self.cfg,self.raw],sort_keys=True)
        replay,result,_=self.build()
        result['releases'][0]['cells'][0]['semantic']['categories'][0]['category_id']='changed-browser-copy'
        replay['batches'][0]['observations'][0]['type']='changed-browser-copy'
        self.assertEqual(json.dumps([self.cfg,self.raw],sort_keys=True),before)

    def test_incomplete_or_missing_source_completion_rejected(self):
        for mutation in ('steps','elapsed','duration','missing','duplicate'):
            with self.subTest(mutation=mutation):
                self.setUp()
                summary=next(r for r in self.raw['agents'] if r['data_type']=='mapped source summary')
                if mutation=='steps':summary['completed_steps']-=1
                if mutation=='elapsed':summary['source_elapsed_ms']-=50
                if mutation=='duration':summary['planned_duration_ms']+=50
                if mutation=='missing':self.raw['agents'].remove(summary)
                if mutation=='duplicate':self.raw['agents'].append(copy.deepcopy(summary))
                with self.assertRaises(ValueError):self.build()

    def test_gt_duplicate_identity_and_reassigned_person_rejected(self):
        for mutation in ('duplicate','person','missing_boundary','offclock','nonfinite'):
            with self.subTest(mutation=mutation):
                self.setUp()
                rows=[r for r in self.raw['agents'] if r['data_type']=='agent data']
                if mutation=='duplicate':self.raw['agents'].append(copy.deepcopy(rows[0]))
                if mutation=='person':rows[1]['private_person_id']='different-private-person'
                if mutation=='missing_boundary':rows[0].pop('observation_track_id')
                if mutation=='offclock':rows[0]['timestamp']=stamp(1)
                if mutation=='nonfinite':rows[0]['position']['x']=float('nan')
                with self.assertRaises(ValueError):self.build()

    def test_raw_missing_duplicate_counts_types_geometry_and_sensor_mismatch_rejected(self):
        for mutation in ('missing','duplicate','count','type','position','size','sensor','unexpected_empty_time'):
            with self.subTest(mutation=mutation):
                self.setUp();row=self.raw['sensor'][0]
                if mutation=='missing':self.raw['sensor'].pop()
                if mutation=='duplicate':self.raw['sensor'].append(copy.deepcopy(row))
                if mutation=='count':row['total_agents']=4
                if mutation=='type':row['agent_type_count'][0]['type']='Child Pedestrian'
                if mutation=='position':row['cell_position']['x']=1.25
                if mutation=='size':row['cell_size']=2.5
                if mutation=='sensor':row['sensor_id']='different-sensor'
                if mutation=='unexpected_empty_time':row['timestamp']=stamp(500)
                with self.assertRaises(ValueError):self.build()

    def test_journal_must_be_committed_and_bijective_with_actual_publication(self):
        for mutation in ('missing','prepared','payload','identity','run','extra_public','empty_disclosed','duplicate'):
            with self.subTest(mutation=mutation):
                self.setUp()
                if mutation=='missing':self.raw['journals']=[]
                if mutation=='prepared':self.raw['journals'][0]['state']='prepared'
                if mutation=='payload':self.raw['journals'][0]['release']['cells'][0]['counts']['observation_contributions']-=1
                if mutation=='identity':self.raw['journals'][0]['_id']='different-id'
                if mutation=='run':self.raw['journals'][1]['run_id']='different-run'
                if mutation=='extra_public':self.raw['releases'].append(copy.deepcopy(self.raw['releases'][0]))
                if mutation=='empty_disclosed':self.raw['releases'].append(copy.deepcopy(self.raw['journals'][1]['release']))
                if mutation=='duplicate':self.raw['journals'].append(copy.deepcopy(self.raw['journals'][0]))
                with self.assertRaises(ValueError):self.build()

    def test_public_scalar_and_semantic_counts_partition_and_loss_are_checked(self):
        for mutation in ('scalar','occupancy','category_count','category_support','minimum_support','max_loss','mean_loss','overlap','missing_semantic'):
            with self.subTest(mutation=mutation):
                self.setUp();cell=self.raw['releases'][0]['cells'][0];semantic=cell['semantic']
                if mutation=='scalar':cell['counts']['observation_contributions']+=1
                if mutation=='occupancy':cell['counts']['mean_sample_occupancy']=4
                if mutation=='category_count':semantic['categories'][0]['observation_contributions']+=1
                if mutation=='category_support':semantic['categories'][0]['distinct_contributors']+=1
                if mutation=='minimum_support':semantic['min_category_distinct_contributors']+=1
                if mutation=='max_loss':semantic['semantic_max_loss']=1
                if mutation=='mean_loss':semantic['semantic_mean_loss']=1
                if mutation=='overlap':semantic['categories'].append(copy.deepcopy(semantic['categories'][0]))
                if mutation=='missing_semantic':cell.pop('semantic')
                self.replace_public()
                with self.assertRaises(ValueError):self.build()

    def test_native_schemas_and_stream_policy_identity_checked_before_conversion(self):
        for mutation in ('release_schema','journal_schema','sensor','application','policy','release_id'):
            with self.subTest(mutation=mutation):
                self.setUp();release=self.raw['releases'][0]
                if mutation=='release_schema':release['schema']='not-native-release'
                if mutation=='journal_schema':self.raw['journals'][0]['schema']='not-native-journal'
                if mutation=='sensor':release['sensor_id']='different-sensor'
                if mutation=='application':release['application_id']='different-application'
                if mutation=='policy':release['policy_id']='different-policy'
                if mutation=='release_id':
                    release['_id']='invented-id'
                    self.raw['journals'][0]['_id']='invented-id'
                self.replace_public()
                with self.assertRaises(ValueError):self.build()

    def test_root_and_overlapping_region_requirements_apply_jointly(self):
        self.cfg['region_taxonomy']=[{'type':'strict','metric_requirements':{'distinct_contributors':{'min':6}}},
                                     {'type':'fast','metric_requirements':{'window_duration_ms':{'max':400}}}]
        self.cfg['regions']=[{'id':'strict','type':'strict','area':dict(x=0,y=0,width=2.5,height=2.5)},
                             {'id':'fast','type':'fast','area':dict(x=1.25,y=1.25,width=2.5,height=2.5)}]
        self.cfg['sensors'][0]['aggregation']['policy_tree']['regions']=['strict','fast']
        with self.assertRaisesRegex(ValueError,'effective policy violation'):self.build()
        # Remove one restriction at a time: the remaining overlapping region
        # independently prevents this publication. No single region wins.
        self.cfg['region_taxonomy'][0]['metric_requirements']={}
        with self.assertRaisesRegex(ValueError,'effective policy violation'):self.build()
        self.cfg['region_taxonomy'][1]['metric_requirements']={}
        self.assertEqual(self.build()[2]['status'],'verified')

    def test_root_policy_violation_is_not_silently_accepted(self):
        self.cfg['sensors'][0]['aggregation']['policy_tree']['root']['semantic_max_loss']['max']=0
        with self.assertRaisesRegex(ValueError,'effective policy violation: semantic_max_loss'):self.build()

    def test_empty_measurement_claim_needs_source_summary_not_just_absent_raw_rows(self):
        self.raw['agents']=[row for row in self.raw['agents'] if row.get('data_type')!='mapped source summary']
        with self.assertRaisesRegex(ValueError,'completed source summary'):self.build()

    def test_loaded_rows_use_read_only_bounded_uuid_owned_namespaces(self):
        completed=subprocess.CompletedProcess([],0,json.dumps(self.raw),'')
        with mock.patch.object(export.shutil,'which',return_value='/mock/mongosh'),mock.patch.object(export.subprocess,'run',return_value=completed) as run:
            self.assertEqual(export.load_native(self.cfg),self.raw)
        args=run.call_args.args[0]
        self.assertEqual(args[0],'/mock/mongosh')
        self.assertIn('mongodb://localhost:27017/',args[1])
        script=args[-1]
        self.assertIn('countDocuments({})',script)
        self.assertIn('find({}).toArray()',script)
        for mutation in ('dropDatabase','deleteMany','insertOne','updateOne','remove('):self.assertNotIn(mutation,script)
        self.assertEqual(run.call_args.kwargs['timeout'],120)
        self.assertNotIn('shell',run.call_args.kwargs)

    def test_namespace_rejection_occurs_before_starting_mongosh(self):
        for mutation in ('raw','sensor','public','private'):
            with self.subTest(mutation=mutation):
                self.setUp()
                if mutation=='raw':self.cfg['database']['db_name']='Simulation'
                if mutation=='sensor':self.cfg['sensors'][0]['database']['db_name']='Simulation'
                if mutation=='public':self.cfg['sensors'][0]['aggregation']['publication']['database']='Simulation'
                if mutation=='private':self.cfg['sensors'][0]['aggregation']['publication']['journal_database']='Simulation'
                with mock.patch.object(export.subprocess,'run') as run:
                    with self.assertRaises(ValueError):export.load_native(self.cfg)
                    run.assert_not_called()

    def test_result_event_geometry_scope_and_interval_failures_are_checked_by_helper(self):
        for mutation in ('geometry','scope','future','before_end','duplicate_cell'):
            with self.subTest(mutation=mutation):
                self.setUp();release=self.raw['releases'][0]
                if mutation=='geometry':release['cells'][0]['width']=5
                if mutation=='scope':release['coordination_cell']['x']=10
                if mutation=='future':release['sealed_at_ms']=1100
                if mutation=='before_end':release['sealed_at_ms']=499
                if mutation=='duplicate_cell':release['cells'].append(copy.deepcopy(release['cells'][0]))
                self.replace_public()
                with self.assertRaises(ValueError):self.build()

    def test_export_persists_private_sidecar_outside_http_allowlist(self):
        self.cfg['mapped_scene']={'motion':{'mode':'integration'}}
        def chunk(kind,payload):
            return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
        png=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))
             +chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\xff\xff'))+chunk(b'IEND',b''))
        mapping={'image':'map_background.png','bounds':dict(x=0,y=0,width=80,height=80),
                 'attribution':'© OpenStreetMap contributors','labels':[],'legend':[]}
        with tempfile.TemporaryDirectory() as directory:
            scene=Path(directory)/'scene';scene.mkdir();output=Path(directory)/'replay'
            (scene/'config.yaml').write_text(export.yaml.safe_dump(self.cfg),encoding='utf-8')
            (scene/'map_background.png').write_bytes(png)
            with mock.patch.object(export,'load_native',return_value=self.raw),mock.patch.object(export,'map_metadata',return_value=mapping):
                proof=export.export_scene(scene,output)
            self.assertEqual(proof['status'],'verified')
            browser=json.dumps(json.loads((output/'observations.json').read_text()))
            self.assertNotIn('private-person-',browser)
            self.assertIn('private-person-',(output/'private/native_source.json').read_text())
            manifest=json.loads((output/'bundle.json').read_text())
            self.assertEqual(manifest['identity_unit'],'visible_episode_track')
            self.assertEqual(manifest['variants'][0]['policy_root_requirements'],
                [{'metric':metric,**bound} for metric,bound in sorted(self.cfg['sensors'][0]['aggregation']['policy_tree']['root'].items())])
            spec=export.importlib.util.spec_from_file_location('ump_export_test_server',Path(export.__file__).parents[1]/'replay_viewer/serve.py')
            server=export.importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
            _,files=server.validate_bundle(output)
            self.assertEqual(set(files),{'bundle.json','observations.json','native_result.json','map_background.png'})
            self.assertNotIn('private/native_source.json',files)
            self.assertNotIn('private/config.yaml',files)
            before={str(path.relative_to(output)):path.read_bytes() for path in output.rglob('*') if path.is_file()}
            with mock.patch.object(export,'load_native') as load:
                with self.assertRaisesRegex(ValueError,'new recording directory'):export.export_scene(scene,output)
                load.assert_not_called()
            self.assertEqual({str(path.relative_to(output)):path.read_bytes() for path in output.rglob('*') if path.is_file()},before)

    def test_native_read_failure_and_bounded_write_helpers(self):
        with mock.patch.object(export.shutil,'which',return_value='/mock/mongosh'),mock.patch.object(export.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','connection refused')):
            with self.assertRaisesRegex(ValueError,'Native read failed'):export.load_native(self.cfg)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'new.json'
            export.write_json(path,{'safe':'value'})
            self.assertEqual(json.loads(path.read_text()),{'safe':'value'})
            with self.assertRaises(FileExistsError):export.write_json(path,{'replace':'forbidden'})
            with self.assertRaises(ValueError):export.write_json(Path(directory)/'nonfinite.json',{'value':float('nan')})
            with mock.patch.object(export,'MAX_BYTES',8):
                with self.assertRaisesRegex(ValueError,'256 MiB'):export.write_json(Path(directory)/'too-large.json',{'larger':'than bound'})


if __name__=='__main__':
    unittest.main()
