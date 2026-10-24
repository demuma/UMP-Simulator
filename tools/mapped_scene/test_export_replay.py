#!/usr/bin/env python3
"""Independent native-publication fixtures for the private mapped replay boundary."""
from __future__ import annotations

import copy
import contextlib
import io
import sys
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


def streamed_response(payload, returncode=0, stderr=''):
    """Mock the descriptor-based subprocess boundary, not a giant stdout string."""
    def invoke(*args, **kwargs):
        data=payload.encode('utf-8') if isinstance(payload,str) else payload
        kwargs['stdout'].write(data)
        return subprocess.CompletedProcess(args[0],returncode,None,stderr)
    return invoke


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

    def test_interval_exit_positions_are_recorded_and_final_step_bounded(self):
        self.cfg['mapped_scene']={'routes':[{'id':'fixture-route','points':[[0,1],[2,1]],'end_boundary':[[0,1],[2,1]]}],
            'people':[{'person_id':f'private-person-{i+1:03d}','speed_mps':1,
                'episodes':[{'track_id':f'track-{i+1:03d}','route_id':'fixture-route'}]} for i in range(5)]}
        ends=[r for r in self.raw['agents'] if r.get('event')=='episode_end']
        for i,event in enumerate(ends):event['position']={'x':1+i*.02,'y':1}
        self.assertEqual(self.build()[2]['lifecycle_quality']['interval_terminal_positions_checked'],5)
        for mutation in ('missing','off_interval','too_far'):
            with self.subTest(mutation=mutation):
                old=copy.deepcopy(ends[0])
                if mutation=='missing':ends[0].pop('position');expected='explicit finite terminal position'
                if mutation=='off_interval':ends[0]['position']['y']=1.1;expected='declared exit interval'
                if mutation=='too_far':ends[0]['position']['x']=1.5;expected='terminal displacement'
                with self.assertRaisesRegex(ValueError,expected):self.build()
                ends[0].clear();ends[0].update(old)

    def test_filtered_product_cannot_receive_a_complete_source_footprint_capture_proof(self):
        self.cfg['sensors'][0]['aggregation']['policy_tree']['root']['semantic_suppression_fraction']={'max':.1}
        with self.assertRaisesRegex(ValueError,'retained-population accounting'):
            self.build()

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

    def test_local_navigation_counters_are_retained_without_inferring_motion_guarantees(self):
        summary=next(r for r in self.raw['agents'] if r['data_type']=='mapped source summary')
        counts={'navigation_steering_steps':12,'navigation_replans':3,'navigation_replan_failures':1,
                'navigation_candidate_checks':50,'navigation_max_search_nodes':20}
        summary.update(counts,motion_model='local_navigation')
        proof=self.build()[2]
        self.assertEqual(proof['motion_quality']['source_model'],'local_navigation')
        for name,value in counts.items():
            self.assertEqual(proof['motion_quality']['reported_diagnostics'][name],value)
            summary[name]=-1
            with self.assertRaisesRegex(ValueError,'Invalid source diagnostic'):self.build()
            summary[name]=value
        self.assertIn('collision safety beyond recorded checks',proof['motion_quality']['scope'])

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

    def test_capture_budget_choices_are_bounded_and_rejected_before_database_work(self):
        for value in (256,512,1024,2048):self.assertEqual(export.capture_limit_bytes(value),value*1024*1024)
        for value in (None,True,256.,'512',0,257,4096):
            with self.subTest(value=value),mock.patch.object(export.subprocess,'run',side_effect=AssertionError('Unexpected database read')):
                with self.assertRaisesRegex(ValueError,'one of 256, 512, 1024 or 2048'):
                    export.load_native(self.cfg,max_capture_mib=value)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'replay'
            with mock.patch.object(export,'load_native',side_effect=AssertionError('Unexpected database read')):
                with self.assertRaisesRegex(ValueError,'one of 256, 512, 1024 or 2048'):
                    export.export_scene(Path(directory),output,max_capture_mib=4096)
            self.assertFalse(output.exists())
        with mock.patch.object(sys,'argv',['export','--scene','/not-read','--output','/not-created','--max-capture-mib','4096']), \
             mock.patch.object(export,'load_native',side_effect=AssertionError('Unexpected database read')), \
             contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as raised:
            export.main()
        self.assertEqual(raised.exception.code,2)

    def test_capture_budget_applies_same_limit_in_mongosh_and_python_without_large_allocations(self):
        for mib in (256,512,1024,2048):
            payload={'text':'{"safe":1}'}
            streams=[]
            def invoke(args,**kwargs):
                streams.append(kwargs['stdout'])
                kwargs['stdout'].write(payload['text'].encode('utf-8'))
                return subprocess.CompletedProcess(args,0,None,'')
            with self.subTest(mib=mib),mock.patch.object(export.shutil,'which',return_value='/mock/mongosh'), \
                 mock.patch.object(export,'capture_limit_bytes',return_value=16), \
                 mock.patch.object(export.subprocess,'run',side_effect=invoke) as run:
                self.assertEqual(export.load_native(self.cfg,max_capture_mib=mib),{'safe':1})
                script=run.call_args.args[0][-1]
                self.assertIn('const maxCaptureBytes=16;',script)
                self.assertIn("Buffer.byteLength(chunk,'utf8')",script)
                self.assertNotIn('capture_output',run.call_args.kwargs)
                self.assertIsNotNone(run.call_args.kwargs['stdout'])
                payload['text']=json.dumps({'too_large':'x'*32})
                with self.assertRaisesRegex(ValueError,f'Capture exceeds {mib} MiB'):
                    export.load_native(self.cfg,max_capture_mib=mib)
            self.assertTrue(all(stream.closed for stream in streams))
        with tempfile.TemporaryDirectory() as directory,mock.patch.object(export,'MAX_BYTES',8):
            with self.assertRaisesRegex(ValueError,'2048 MiB'):
                export.write_json(Path(directory)/'public.json',{'value':'larger'})
            export.write_json(Path(directory)/'private.json',{'value':'larger'},max_bytes=32)
            with self.assertRaisesRegex(ValueError,'bounded capture budget'):
                export.write_json(Path(directory)/'rejected-private.json',{'value':'larger'},max_bytes=8)

    def test_streamed_capture_rejects_utf8_overflow_truncation_and_command_failure_and_closes_files(self):
        payload=json.dumps({'value':'ééé'},ensure_ascii=False)
        self.assertGreater(len(payload.encode('utf-8')),len(payload))
        cases=[(payload,0,'',len(payload),'Capture exceeds'),
               ('{"unfinished":[',0,'',1024,'malformed or truncated JSON'),
               (b'{"invalid":"\xff"}',0,'',1024,'malformed or truncated JSON'),
               ('{"unfinished":[',1,'connection lost',1024,'Native read failed')]
        for text,code,error,limit,expected in cases:
            with self.subTest(expected=expected),mock.patch.object(export.shutil,'which',return_value='/mock/mongosh'), \
                 mock.patch.object(export,'capture_limit_bytes',return_value=limit), \
                 mock.patch.object(export.subprocess,'run',side_effect=streamed_response(text,code,error)) as run:
                with self.assertRaisesRegex(ValueError,expected):export.load_native(self.cfg)
                self.assertTrue(run.call_args.kwargs['stdout'].closed)

    def test_actual_javascript_record_stream_keeps_unicode_and_enforces_total_byte_budget(self):
        # Execute the production serialization script against an independent
        # tiny cursor double. This exercises real JSON punctuation, UTF-8 byte
        # counting and asynchronous cursor iteration without MongoDB writes.
        sample={'agents':[{'value':'Grüße 🌍','nested':[1,2]}],'sensor':[],'releases':[],'journals':[]}
        for limit,success,declared_count in [(1024,True,None),(2147483648,True,1000001),(32,False,None)]:
            with mock.patch.object(export.shutil,'which',return_value='/mock/mongosh'), \
                 mock.patch.object(export,'capture_limit_bytes',return_value=limit), \
                 mock.patch.object(export.subprocess,'run',side_effect=streamed_response('{}')) as run:
                export.load_native(self.cfg)
            script=run.call_args.args[0][-1]
            wrapper="""const source=SAMPLE;
const keys=['agents','sensor','releases','journals'];let next=0;
global.db={getSiblingDB(){return {getCollection(){const key=keys[next++],rows=source[key];return {async countDocuments(){return key==='agents'&&DECLARED_COUNT!==null?DECLARED_COUNT:rows.length;},find(){return {async forEach(visit){for(const row of rows)visit(row);}};}};}};}};
global.print=text=>process.stdout.write(text+'\\n');
(async()=>{await eval(SCRIPT);})().catch(error=>{console.error(error.message);process.exitCode=1;});
""".replace('SAMPLE',json.dumps(sample)).replace('SCRIPT',json.dumps(script)).replace('DECLARED_COUNT',json.dumps(declared_count))
            result=subprocess.run(['node','-e',wrapper],capture_output=True,text=True,timeout=10)
            if success:
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(result.stdout),sample)
                self.assertLessEqual(len(result.stdout.encode('utf-8')),limit)
            else:
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Capture exceeds 32 bytes',result.stderr)
                self.assertLessEqual(len(result.stdout.encode('utf-8')),limit)

    def test_streamed_json_write_rejects_sparse_oversized_chunk_and_removes_only_its_partial_file(self):
        class EncodedTooLarge:
            def __len__(self):return 2048*1024*1024+1
        class SparseChunk:
            def encode(self,encoding):return EncodedTooLarge()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'too-large.json'
            with mock.patch.object(export.json.JSONEncoder,'iterencode',return_value=iter([SparseChunk()])):
                with self.assertRaisesRegex(ValueError,'2048 MiB'):export.write_json(path,{})
            self.assertFalse(path.exists())
            invalid=Path(directory)/'partial.json'
            with self.assertRaises(ValueError):export.write_json(invalid,{'good':1,'bad':float('nan')})
            self.assertFalse(invalid.exists())
            existing=Path(directory)/'existing.json';existing.write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):export.write_json(existing,{'replace':True})
            self.assertEqual(existing.read_bytes(),b'preserve')

    def test_loaded_rows_use_read_only_bounded_uuid_owned_namespaces(self):
        with mock.patch.object(export.shutil,'which',return_value='/mock/mongosh'),mock.patch.object(export.subprocess,'run',side_effect=streamed_response(json.dumps(self.raw))) as run:
            self.assertEqual(export.load_native(self.cfg),self.raw)
        args=run.call_args.args[0]
        self.assertEqual(args[0],'/mock/mongosh')
        self.assertIn('mongodb://localhost:27017/',args[1])
        script=args[-1]
        self.assertIn('countDocuments({})',script)
        self.assertIn('find({}).forEach(document',script)
        self.assertNotIn('.toArray()',script)
        self.assertNotIn('JSON.stringify(value)',script)
        for mutation in ('dropDatabase','deleteMany','insertOne','updateOne','remove('):self.assertNotIn(mutation,script)
        self.assertEqual(run.call_args.kwargs['timeout'],360)
        self.assertNotIn('shell',run.call_args.kwargs)

    def test_mongosh_argument_contains_only_collection_metadata_for_large_scenes(self):
        cfg=copy.deepcopy(self.cfg)
        cfg['mapped_scene']={'people':[{'person_id':'unused-private-person','episodes':[]}]*16384,
                             'routes':[{'id':'unused-route','points':[[0,0],[80,80]]}]*16384,
                             'motion':{'navigation':{'allowed_center_polygons':
                                 [{'outer':[[0,0],[80,0],[80,80],[0,80]]}]*16384}}}
        self.assertGreater(len(json.dumps(cfg)),1024*1024)
        scripts=[]
        for source in (self.cfg,cfg):
            with mock.patch.object(export.shutil,'which',return_value='/mock/mongosh'), \
                 mock.patch.object(export.subprocess,'run',side_effect=streamed_response('{}')) as run:
                self.assertEqual(export.load_native(source),{})
            scripts.append(run.call_args.args[0][-1])
        self.assertEqual(scripts[0],scripts[1])
        self.assertLess(len(scripts[1].encode('utf-8')),16384)
        self.assertNotIn('unused-private-person',scripts[1])
        self.assertNotIn('unused-route',scripts[1])
        prefix=scripts[1].split(';',1)[0]
        self.assertTrue(prefix.startswith('const collections='))
        self.assertEqual(json.loads(prefix.removeprefix('const collections=')),
            [['agents',BASE,'Agents'],['sensor',BASE,'AGB_Sensor_Data_V3'],
             ['releases',BASE+'_Releases','Published'],['journals',BASE+'_Private','Journal']])

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
            budget=proof['capture_budget']
            self.assertEqual(budget['max_capture_mib'],2048)
            self.assertEqual(budget['max_capture_bytes'],2048*1024*1024)
            self.assertEqual(budget['public_artifact_max_bytes'],2048*1024*1024)
            self.assertEqual(budget['native_source_json_bytes'],(output/'private/native_source.json').stat().st_size)
            self.assertEqual(budget['source_configuration_sha256'],export.digest(scene/'config.yaml'))
            expanded=Path(directory)/'replay-512'
            with mock.patch.object(export,'load_native',return_value=self.raw) as load, mock.patch.object(export,'map_metadata',return_value=mapping):
                expanded_proof=export.export_scene(scene,expanded,max_capture_mib=512)
            load.assert_called_once_with(self.cfg,max_capture_mib=512)
            self.assertEqual(expanded_proof['capture_budget']['max_capture_bytes'],512*1024*1024)
            for name in ('observations.json','native_result.json','bundle.json','private/config.yaml','private/native_source.json'):
                self.assertEqual((output/name).read_bytes(),(expanded/name).read_bytes())
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

    def test_export_public_building_geometry_is_validated_hashed_and_keeps_private_data_separate(self):
        self.cfg['mapped_scene']={'motion':{'mode':'buildings'}}
        def chunk(kind,payload):
            return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
        png=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))
             +chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\xff\xff'))+chunk(b'IEND',b''))
        access={'schema':'ump.building-access.v1','bounds':dict(x=0,y=0,width=80,height=80),
                'buildings':[{'id':'way1','name':'Shop building','polygons':[[[10,10],[30,10],[30,30],[10,30],[10,10]]]}],
                'portals':[{'id':'entry1','building_id':'way1','point':[20,10],
                            'facade':[[10,10],[30,10]],'width_m':1.2,'provenance':'synthetic'}]}
        mapping={'image':'map_background.png','bounds':dict(x=0,y=0,width=80,height=80),
                 'attribution':'© OpenStreetMap contributors','labels':[],'legend':[],
                 'building_access':'building_access.json'}
        self.cfg['simulation'].update(width=80,height=80)
        self.cfg['mapped_scene']['portals']=copy.deepcopy(access['portals'])
        with tempfile.TemporaryDirectory() as directory:
            scene=Path(directory)/'scene';scene.mkdir();output=Path(directory)/'replay'
            (scene/'config.yaml').write_text(export.yaml.safe_dump(self.cfg),encoding='utf-8')
            (scene/'map_background.png').write_bytes(png)
            (scene/'building_access.json').write_text(json.dumps(access))
            with mock.patch.object(export,'load_native',return_value=self.raw),mock.patch.object(export,'map_metadata',return_value=mapping):
                proof=export.export_scene(scene,output)
            manifest=json.loads((output/'bundle.json').read_text())
            self.assertEqual(manifest['map']['building_access'],'building_access.json')
            self.assertEqual(proof['files_sha256']['building_access.json'],export.digest(scene/'building_access.json'))
            self.assertEqual(manifest['sha256']['building_access.json'],proof['files_sha256']['building_access.json'])
            self.assertEqual((output/'building_access.json').read_bytes(),(scene/'building_access.json').read_bytes())
            self.assertNotIn('private-person-',(output/'building_access.json').read_text())
            access['private_person_id']='forbidden'
            (scene/'building_access.json').write_text(json.dumps(access))
            rejected=Path(directory)/'rejected'
            with mock.patch.object(export,'load_native',return_value=self.raw),mock.patch.object(export,'map_metadata',return_value=mapping):
                with self.assertRaisesRegex(ValueError,'public building access schema'):export.export_scene(scene,rejected)
            self.assertFalse(rejected.exists(),'Invalid public geometry must fail before creating a recording')

    def test_public_building_artifact_must_match_native_portals_dimensions_and_generated_digests(self):
        access={'schema':'ump.building-access.v1','bounds':dict(x=0,y=0,width=80,height=80),
                'buildings':[], 'portals':[{'id':'door-b','building_id':'building-b','point':[2,0],
                    'facade':[[0,0],[4,0]],'width_m':1.2,'provenance':'synthetic'},
                    {'id':'door-a','building_id':'building-a','point':[8,0],
                    'facade':[[6,0],[10,0]],'width_m':1.2,'provenance':'synthetic'}]}
        with tempfile.TemporaryDirectory() as directory:
            scene=Path(directory);path=scene/'building_access.json'
            path.write_text(json.dumps(access));(scene/'map_background.png').write_bytes(b'fixture map bytes')
            cfg={'simulation':{'width':80,'height':80},'mapped_scene':{'portals':list(reversed(copy.deepcopy(access['portals'])))}}
            (scene/'config.yaml').write_text(export.yaml.safe_dump(cfg))
            proof=export.validate_scene_building_access(scene,cfg,path)
            self.assertEqual(proof['status'],'verified_native_portal_agreement')
            self.assertFalse(proof['generated_manifest_config_and_background_verified'])
            for mutation in ('point','facade','width_m','building_id','provenance','missing','duplicate','width','height'):
                with self.subTest(mutation=mutation):
                    changed=copy.deepcopy(cfg)
                    portal=changed['mapped_scene']['portals'][0]
                    if mutation=='point':portal['point'][0]+=.1
                    if mutation=='facade':portal['facade'][0][0]+=.1
                    if mutation=='width_m':portal['width_m']=1.1
                    if mutation=='building_id':portal['building_id']='another-building'
                    if mutation=='provenance':portal['provenance']='osm'
                    if mutation=='missing':changed['mapped_scene']['portals'].pop()
                    if mutation=='duplicate':changed['mapped_scene']['portals'].append(copy.deepcopy(portal))
                    if mutation in ('width','height'):changed['simulation'][mutation]=81
                    with self.assertRaisesRegex(ValueError,'differ from native'):export.validate_scene_building_access(scene,changed,path)
            manifest={'motion_mode':'buildings','building_access_sha256':export.digest(path),
                      'configuration_sha256':export.digest(scene/'config.yaml'),
                      'background_sha256':export.digest(scene/'map_background.png')}
            (scene/'scene_manifest.json').write_text(json.dumps(manifest))
            proof=export.validate_scene_building_access(scene,cfg,path)
            self.assertTrue(proof['generated_manifest_config_and_background_verified'])
            for mutation in ('geometry','configuration','background','missing_geometry'):
                with self.subTest(mutation=mutation):
                    changed=copy.deepcopy(manifest)
                    if mutation=='geometry':changed['building_access_sha256']='0'*64
                    if mutation=='configuration':changed['configuration_sha256']='0'*64
                    if mutation=='background':changed['background_sha256']='0'*64
                    if mutation=='missing_geometry':changed.pop('building_access_sha256')
                    (scene/'scene_manifest.json').write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError,'digest'):export.validate_scene_building_access(scene,cfg,path)

    def test_storefront_navigation_and_boundary_metadata_must_match_native_configuration(self):
        polygons=[{'outer':[[0,0],[80,0],[80,80],[0,80],[0,0]],'holes':[]}]
        boundary={'id':'west-walk','mode':'walking','side':'west','points':[[0,10],[0,20]],
                  'length_m':10,'spawn_supported':True,'provenance':'derived_frozen_functional_zone_boundary'}
        nav_digest=export.hashlib.sha256(json.dumps(polygons,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        access={'schema':'ump.building-access.v2','bounds':dict(x=0,y=0,width=80,height=80),
            'buildings':[],'portals':[],'store_fronts':[],'facade_separators':[],
            'boundary_intervals':[boundary],'navigation':{'body_clearance_m':.55,
                'allowed_center_polygons_sha256':nav_digest,'scope':'Fixture geometry.'}}
        cfg={'simulation':dict(width=80,height=80),'mapped_scene':{'portals':[],
            'routes':[{'id':'r','points':[[0,10],[0,20]],'start_portal':'west-walk','end_portal':'west-walk'}],
            'motion':{'mode':'local_navigation','navigation':{'allowed_center_polygons':polygons,
                'center_clearance_m':.55}}}}
        with tempfile.TemporaryDirectory() as directory:
            scene=Path(directory);path=scene/'building_access.json';path.write_text(json.dumps(access))
            proof=export.validate_scene_building_access(scene,cfg,path)
            self.assertTrue(proof['native_navigation_geometry_and_boundaries_verified'])
            self.assertEqual(proof['boundary_intervals'],1)
            for mutation in ('geometry','clearance','boundary','missing_boundary','missing_geometry'):
                with self.subTest(mutation=mutation):
                    changed=copy.deepcopy(cfg);nav=changed['mapped_scene']['motion']['navigation']
                    if mutation=='geometry':nav['allowed_center_polygons'][0]['outer'][1][0]=79
                    if mutation=='clearance':nav['center_clearance_m']=.4
                    if mutation=='boundary':changed['mapped_scene']['routes'][0]['points'][0]=[0,9]
                    if mutation=='missing_boundary':changed['mapped_scene']['routes'][0]['start_portal']='missing'
                    if mutation=='missing_geometry':nav.pop('allowed_center_polygons')
                    with self.assertRaisesRegex(ValueError,'native|Native'):export.validate_scene_building_access(scene,changed,path)
            (scene/'config.yaml').write_text(export.yaml.safe_dump(cfg));(scene/'map_background.png').write_bytes(b'map')
            manifest={'motion_mode':'storefronts','configuration_sha256':export.digest(scene/'config.yaml'),
                'background_sha256':export.digest(scene/'map_background.png'),'building_access_sha256':export.digest(path)}
            (scene/'scene_manifest.json').write_text(json.dumps(manifest))
            self.assertTrue(export.validate_scene_building_access(scene,cfg,path)['generated_manifest_config_and_background_verified'])
            manifest['configuration_sha256']='a'*64;(scene/'scene_manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'digest'):export.validate_scene_building_access(scene,cfg,path)

    def test_public_mode_specific_geometry_digest_and_road_boundaries_are_verified(self):
        polygons=[{'outer':[[0,0],[80,0],[80,80],[0,80],[0,0]],'holes':[]}]
        road=[{'outer':[[0,30],[80,30],[80,40],[0,40],[0,30]],'holes':[]}]
        def geometry_digest(rows):
            return export.hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        access={'schema':'ump.building-access.v2','bounds':dict(x=0,y=0,width=80,height=80),
            'buildings':[],'portals':[],'store_fronts':[],'facade_separators':[],
            'boundary_intervals':[{'id':'road-west','mode':'road','spawn_supported':True,'points':[[0,31],[0,39]]}],
            'navigation':{'body_clearance_m':.5,'allowed_center_polygons_sha256':geometry_digest(polygons),
                'spaces':[{'id':'carriageway','body_clearance_m':1.05,'allowed_center_polygons_sha256':geometry_digest(road)}]}}
        cfg={'simulation':dict(width=80,height=80),'mapped_scene':{'portals':[],
            'routes':[{'id':'r','points':[[0,33],[0,37]],'start_portal':'road-west','end_portal':'road-west','navigation_space':'carriageway','end_boundary':[[0,31],[0,39]]}],
            'motion':{'mode':'local_navigation','navigation':{'allowed_center_polygons':polygons,'center_clearance_m':.5,
                'spaces':[{'id':'carriageway','allowed_center_polygons':road,'center_clearance_m':1.05}]}}}}
        with tempfile.TemporaryDirectory() as directory:
            scene=Path(directory);path=scene/'building_access.json';path.write_text(json.dumps(access))
            self.assertTrue(export.validate_scene_building_access(scene,cfg,path)['native_navigation_geometry_and_boundaries_verified'])
            directional=copy.deepcopy(cfg);directional_access=copy.deepcopy(access)
            directional['mapped_scene']['motion']['navigation']['spaces'][0]['id']='carriageway-east'
            directional['mapped_scene']['routes'][0]['navigation_space']='carriageway-east'
            directional_access['navigation']['spaces'][0].update(id='carriageway-east',mode='road')
            path.write_text(json.dumps(directional_access))
            self.assertTrue(export.validate_scene_building_access(scene,directional,path)['native_navigation_geometry_and_boundaries_verified'])
            for mutation in ('geometry','clearance','missing_space','wrong_route_space','walking_boundary','exit_interval','mode'):
                with self.subTest(mutation=mutation):
                    changed=copy.deepcopy(cfg);context=copy.deepcopy(access)
                    nav=changed['mapped_scene']['motion']['navigation']
                    if mutation=='geometry':nav['spaces'][0]['allowed_center_polygons'][0]['outer'][0][1]=29
                    if mutation=='clearance':nav['spaces'][0]['center_clearance_m']=.55
                    if mutation=='missing_space':nav['spaces']=[]
                    if mutation=='wrong_route_space':changed['mapped_scene']['routes'][0].pop('navigation_space')
                    if mutation=='walking_boundary':context['boundary_intervals'][0]['mode']='walking'
                    if mutation=='exit_interval':changed['mapped_scene']['routes'][0]['end_boundary'][0][1]=32
                    if mutation=='mode':context['navigation']['spaces'][0]['mode']='walking'
                    path.write_text(json.dumps(context))
                    with self.assertRaisesRegex(ValueError,'native|Native'):
                        export.validate_scene_building_access(scene,changed,path)

    def test_map_metadata_only_references_optional_local_public_building_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            scene=Path(directory)/'scene';scene.mkdir();repo=Path(directory)/'repo';repo.mkdir()
            (scene/'scene_manifest.json').write_text(json.dumps({'map_labels':[{'text':'Building','x':20,'y':20,'kind':'building'}]}))
            cfg={'renderer':{'map_attribution':'© OpenStreetMap contributors'}}
            self.assertNotIn('building_access',export.map_metadata(scene,cfg,repo))
            (scene/'building_access.json').write_text('{}')
            self.assertEqual(export.map_metadata(scene,cfg,repo)['building_access'],'building_access.json')
            (scene/'building_access.json').unlink()
            external=Path(directory)/'outside.json';external.write_text('{}')
            (scene/'building_access.json').symlink_to(external)
            with self.assertRaisesRegex(ValueError,'Escaping public building access'):export.map_metadata(scene,cfg,repo)

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
                with self.assertRaisesRegex(ValueError,'2048 MiB'):export.write_json(Path(directory)/'too-large.json',{'larger':'than bound'})


class RetainedBackgroundRefreshTests(unittest.TestCase):
    """Presentation changes preserve the original capture and reject stale proof."""

    @classmethod
    def setUpClass(cls):
        import refresh_background
        cls.refresh = refresh_background
        cls.repo = Path(__file__).resolve().parents[2]
        cls.builder = cls.refresh.module_at('ump_refresh_test_builder', cls.repo / 'tools/mapped_scene/build_mapped_scene.py')
        _, _, cls.layers, _, cls.provenance = cls.builder.load_source(cls.repo)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ump-refresh-test-')
        self.addCleanup(self.temporary.cleanup)
        self.scene, self.replay = Path(self.temporary.name) / 'scene', Path(self.temporary.name) / 'replay'
        self.scene.mkdir()
        cfg, raw = native_fixture()
        access = {'schema':'ump.building-access.v1','bounds':dict(x=0,y=0,width=80,height=80),
                  'buildings':[{'id':'way1','name':'Shop building','polygons':[[[10,10],[30,10],[30,30],[10,30],[10,10]]]}],
                  'portals':[{'id':'entry1','building_id':'way1','point':[20,10],
                              'facade':[[10,10],[30,10]],'width_m':1.2,'provenance':'synthetic'}]}
        cfg['simulation'].update(width=80, height=80)
        cfg['mapped_scene'] = {'epoch_utc':'2026-10-23T10:30:00.000Z', 'portals':copy.deepcopy(access['portals'])}
        (self.scene / 'config.yaml').write_text(export.yaml.safe_dump(cfg))
        (self.scene / 'building_access.json').write_text(json.dumps(access))
        def chunk(kind, body):
            return struct.pack('!I',len(body))+kind+body+struct.pack('!I',zlib.crc32(kind+body)&0xffffffff)
        png = (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',1,1,8,6,0,0,0))
               +chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\xff\xff'))+chunk(b'IEND',b''))
        (self.scene / 'map_background.png').write_bytes(png)
        manifest = {**self.provenance, 'motion_mode':'buildings', 'generator_sha256':'original-generator',
                    'configuration_sha256':export.digest(self.scene/'config.yaml'),
                    'building_access_sha256':export.digest(self.scene/'building_access.json'),
                    'background_sha256':export.digest(self.scene/'map_background.png')}
        (self.scene / 'scene_manifest.json').write_text(json.dumps(manifest))
        mapping = {'image':'map_background.png','bounds':dict(x=0,y=0,width=80,height=80),
                   'attribution':'© OpenStreetMap contributors; ODbL 1.0',
                   'labels':[{'text':'Readable shop name','kind':'shop','x':20,'y':20}], 'legend':[],
                   'building_access':'building_access.json'}
        with mock.patch.object(export,'load_native',return_value=raw), mock.patch.object(export,'map_metadata',return_value=mapping):
            export.export_scene(self.scene, self.replay)

    def test_refresh_archives_original_evidence_and_preserves_all_nonpresentation_bytes(self):
        before = {root: {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
                  for root in (self.scene, self.replay)}
        result = self.refresh.refresh_background(self.scene, self.replay, self.repo)
        self.assertEqual(result['status'], 'refreshed')
        changed = {self.scene: {'map_background.png', 'scene_manifest.json'},
                   self.replay: {'map_background.png', 'bundle.json', 'capture-proof.json'}}
        for root, files in before.items():
            for name, contents in files.items():
                if name not in changed[root]:
                    self.assertEqual((root / name).read_bytes(), contents, name)
        manifest = json.loads((self.scene/'scene_manifest.json').read_text())
        proof = json.loads((self.replay/'capture-proof.json').read_text())
        self.assertEqual(manifest['generator_sha256'], 'original-generator')
        self.assertEqual(manifest['background_rendering'], self.builder.background_rendering())
        record = proof['presentation_refreshes'][0]
        for name in changed[self.scene]:
            self.assertEqual((self.scene/record['scene_archive']/name).read_bytes(), before[self.scene][name])
        for name in changed[self.replay]:
            self.assertEqual((self.replay/record['replay_archive']/name).read_bytes(), before[self.replay][name])
        bundle = json.loads((self.replay/'bundle.json').read_text())
        old_bundle = json.loads(before[self.replay]['bundle.json'])
        self.assertEqual(bundle['map'], old_bundle['map'])  # Attribution and toggleable names survive.
        for name, expected in proof['files_sha256'].items():
            self.assertEqual(export.digest(self.replay/name), expected)
        again = self.refresh.refresh_background(self.scene, self.replay, self.repo)
        self.assertEqual(again['status'], 'unchanged')
        self.assertEqual(len(json.loads((self.replay/'capture-proof.json').read_text())['presentation_refreshes']), 1)

    def test_overlapping_and_repository_directories_are_rejected_without_writes(self):
        temporary = Path(self.temporary.name)
        before = {str(path.relative_to(temporary)): path.read_bytes()
                  for path in temporary.rglob('*') if path.is_file()}
        cases = [(self.scene, self.scene), (temporary, self.replay),
                 (self.scene, temporary), (self.repo, self.replay),
                 (self.scene, self.repo), (self.repo.parent, self.replay),
                 (self.scene, self.repo.parent)]
        with mock.patch.object(self.refresh.tempfile, 'TemporaryDirectory', side_effect=AssertionError('Guard must run before staging')):
            for scene, replay in cases:
                with self.subTest(scene=scene, replay=replay):
                    with self.assertRaisesRegex(ValueError, 'non-overlapping|contain the repository'):
                        self.refresh.refresh_background(scene, replay, self.repo)
                    after = {str(path.relative_to(temporary)): path.read_bytes()
                             for path in temporary.rglob('*') if path.is_file()}
                    self.assertEqual(before, after)

    def test_corrupt_capture_hash_is_rejected_without_changes(self):
        path = self.replay/'capture-proof.json'
        proof = json.loads(path.read_text())
        proof['files_sha256']['private/config.yaml'] = '0'*64
        path.write_text(json.dumps(proof))
        image = (self.replay/'map_background.png').read_bytes()
        with self.assertRaisesRegex(ValueError, 'Original capture digest mismatch'):
            self.refresh.refresh_background(self.scene, self.replay, self.repo)
        self.assertEqual((self.replay/'map_background.png').read_bytes(), image)
        self.assertFalse((self.scene/'presentation_history').exists())

    def test_incomplete_original_proof_is_rejected(self):
        path = self.replay/'capture-proof.json'
        proof = json.loads(path.read_text())
        del proof['files_sha256']['private/native_source.json']
        path.write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError, 'missing required artifact digests'):
            self.refresh.refresh_background(self.scene, self.replay, self.repo)
        self.assertFalse((self.scene/'presentation_history').exists())

    def test_changed_scene_and_frozen_source_are_rejected(self):
        path = self.scene/'scene_manifest.json'
        original = json.loads(path.read_text())
        for field in ('source_geometry_sha256', 'compressed_source_sha256', 'coordinate_transform', 'map_builder_sha256', 'background_sha256'):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed[field] = {} if field == 'coordinate_transform' else '0'*64
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    self.refresh.refresh_background(self.scene, self.replay, self.repo)
        path.write_text(json.dumps(original))
        self.assertFalse((self.scene/'presentation_history').exists())

    def test_existing_history_is_never_overwritten(self):
        output = Path(self.temporary.name)/'clean.png'
        access = json.loads((self.scene/'building_access.json').read_text())
        self.builder.draw_background(self.layers, output, access)
        refresh_id = 'geometry-only-'+export.digest(self.scene/'map_background.png')[:12]+'-'+export.digest(output)[:12]
        archive = self.scene/'presentation_history'/refresh_id
        archive.mkdir(parents=True)
        sentinel = archive/'keep.txt'
        sentinel.write_text('prior evidence')
        with self.assertRaisesRegex(ValueError, 'Refusing to replace prior presentation history'):
            self.refresh.refresh_background(self.scene, self.replay, self.repo)
        self.assertEqual(sentinel.read_text(), 'prior evidence')
        self.assertFalse((self.replay/'private/presentation_history').exists())


if __name__=='__main__':
    unittest.main()
