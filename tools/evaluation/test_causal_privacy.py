"""Causal boundaries, auxiliary provenance and nested-representation regressions."""
from copy import deepcopy
import math
import random
import unittest
from unittest.mock import patch

from causal_privacy import (CHECKPOINTS, PROFILES, auxiliary_features, feature_names,
    feature_grid, feature_views, feature_views_many, knowledge_at, knowledge_events, public_view)
from empirical_privacy import _validated_public, export_public, feature_vector
from make_fixture import cell_id
from run_privacy_study import stable_seed

GRID = dict(x=0,y=0,width=80,height=80,leaf_depth=2)


def point(time,x=1,y=1):
    return dict(observed_at_ms=time,x=x,y=y,cell_id=cell_id(x,y,GRID))


def public_fixture():
    releases=[]
    for start,end,sealed,identity,x in [(0,400,500,12,0),(400,800,1000,13,40),
                                      (800,1200,1500,12,0),(400,800,2000,12,0)]:
        releases.append(dict(release_id=str(len(releases)),start_ms=start,end_ms=end,sealed_at_ms=sealed,
            policy_id='policy',policy_version='1',model='private_final_snapshot',cells=[
                dict(cell_id=identity,depth=1,x=x,y=0,width=40,height=40,
                     observation_contributions=6,distinct_road_users=2,
                     mean_sample_occupancy=2,effective_policy_id='root')]))
    return export_public(dict(schema='ump.replay-result.v1',releases=releases,
        source=dict(coverage=GRID,sampling_period_ms=100,end_ms=16000)))


class CausalKnowledgeTests(unittest.TestCase):
    def test_bernoulli_selection_is_independent_per_timestamp_and_shared_across_profiles(self):
        trace=[point(time) for time in range(100,16000,100)]
        exact=knowledge_events(trace,GRID,16000,42,'exact_25')
        noisy=knowledge_events(trace,GRID,16000,42,'noisy_25')
        expected=[p['observed_at_ms'] for p in trace
                  if random.Random(stable_seed(42,p['observed_at_ms'],'select')).random()<.25]
        self.assertEqual([e['acquired_at_ms'] for e in exact],expected)
        self.assertEqual([e['acquired_at_ms'] for e in noisy],expected)
        self.assertEqual(exact,knowledge_events(trace,GRID,16000,42,'exact_25'))
        self.assertNotEqual(exact,knowledge_events(trace,GRID,16000,43,'exact_25'))
        self.assertTrue(all(e['reported']==point(e['acquired_at_ms']) for e in exact))
        # This is Bernoulli acquisition, not a forced fixed-size whole-trace sample.
        counts={len(knowledge_events(trace,GRID,16000,seed,'exact_25')) for seed in range(5)}
        self.assertGreater(len(counts),1)

    def test_appending_future_trace_points_cannot_change_earlier_events(self):
        prefix=[point(time) for time in range(100,2000,100)]
        future=[point(time,x=45,y=5) for time in range(2000,16000,100)]
        for profile in PROFILES:
            old=knowledge_events(prefix,GRID,16000,12,profile)
            new=knowledge_events(prefix+future,GRID,16000,12,profile)
            self.assertEqual(old,[event for event in new if event['acquired_at_ms']<2000])
            self.assertEqual(knowledge_at(old,1900),knowledge_at(new,1900))

    def test_negative_noisy_timestamp_never_exposes_future_acquisition(self):
        event=dict(acquired_at_ms=2100,available_at_ms=2100,reported=point(1900))
        self.assertEqual(knowledge_at([event],2000),[])
        self.assertEqual(knowledge_at([event],2100),[point(1900)])
        positive=dict(acquired_at_ms=1900,available_at_ms=2100,reported=point(2100))
        self.assertEqual(knowledge_at([positive],2000),[])
        self.assertEqual(knowledge_at([positive],2100),[point(2100)])

    def test_causal_deduplication_occurs_after_gating_and_strips_metadata(self):
        a=dict(acquired_at_ms=100,available_at_ms=200,reported=point(200))
        b=dict(acquired_at_ms=300,available_at_ms=300,reported=point(200))
        before=deepcopy([a,b])
        self.assertEqual(knowledge_at([b,a],199),[])
        self.assertEqual(knowledge_at([b,a],200),[point(200)])
        self.assertEqual(knowledge_at([b,a],400),[point(200)])
        self.assertEqual([a,b],before)
        self.assertEqual(set(knowledge_at([a,b],400)[0]),{'observed_at_ms','x','y','cell_id'})

    def test_noise_clips_to_public_bounds_and_preserves_independent_per_point_draws(self):
        trace=[point(time,x=0,y=math.nextafter(80,-math.inf)) for time in range(1,1000)]
        events=knowledge_events(trace,GRID,1000,8,'noisy_25')
        self.assertTrue(events)
        self.assertTrue(any(e['reported']['x']==0 for e in events))
        self.assertTrue(any(e['reported']['y']==math.nextafter(80,-math.inf) for e in events))
        self.assertTrue(any(e['reported']['observed_at_ms'] in (1,999) for e in events))
        for event in events:
            p=event['reported']
            self.assertTrue(0<=p['x']<80 and 0<=p['y']<80 and 1<=p['observed_at_ms']<1000)
            self.assertEqual(p['cell_id'],cell_id(p['x'],p['y'],GRID))
            self.assertEqual(event['available_at_ms'],max(event['acquired_at_ms'],p['observed_at_ms']))
        self.assertTrue(any(e['reported']['observed_at_ms']%100 for e in events))

    def test_pair_invariance_and_inputs_remain_untouched(self):
        trace=[point(time) for time in range(100,16000,100)]
        before=deepcopy(trace)
        for profile in PROFILES:
            events=knowledge_events(trace,GRID,16000,831,profile)
            for checkpoint in CHECKPOINTS:
                self.assertEqual(knowledge_at(events,checkpoint),knowledge_at(deepcopy(events),checkpoint))
                self.assertEqual(auxiliary_features(knowledge_at(events,checkpoint)),
                                 auxiliary_features(knowledge_at(deepcopy(events),checkpoint)))
        self.assertEqual(trace,before)
        self.assertEqual(knowledge_events([],GRID,16000,1,'exact_25'),[])

    def test_unknown_private_fields_and_invalid_provenance_are_rejected(self):
        trace=[point(100)]
        for bad in ([dict(trace[0],id='private')],[dict(point(100),x=100)],list(reversed([point(100),point(200)])),
                    [point(16000)],[dict(trace[0],cell_id=1)]):
            with self.subTest(trace=bad),self.assertRaises(ValueError):
                knowledge_events(bad,GRID,16000,1,'exact_25')
        event=dict(acquired_at_ms=100,available_at_ms=100,reported=point(100))
        for bad in (dict(event,label=1),dict(event,available_at_ms=99),
                    dict(event,reported=dict(point(100),target_id='secret'))):
            with self.subTest(event=bad),self.assertRaises(ValueError):knowledge_at([bad],1000)
        for options in [(True,'exact_25'),(-1,'exact_25'),(2**63,'exact_25'),(1,'unknown')]:
            with self.assertRaises(ValueError):knowledge_events(trace,GRID,16000,*options)
        with self.assertRaises(ValueError):knowledge_at([event],True)


class CausalPublicViewsTests(unittest.TestCase):
    def test_prefix_gates_seal_not_interval_and_reindexes_aliases(self):
        public=public_fixture()
        prefix=public_view(public,1000)
        self.assertEqual(len(prefix['releases']),2)
        self.assertEqual([r['release_id'] for r in prefix['releases']],['release-000000','release-000001'])
        self.assertEqual(prefix['releases'][1]['cells'][0]['cell_id'],13)
        self.assertTrue(all(r['sealed_at_ms']<=1000 for r in prefix['releases']))
        self.assertEqual(prefix['end_ms'],16000)
        self.assertEqual(feature_vector(prefix,[]),feature_vector(deepcopy(prefix),[]))

    def test_recent_is_a_half_open_arrival_block_of_whole_records(self):
        public=public_fixture()
        recent=public_view(public,1500,recent_window_ms=1000)
        self.assertEqual([r['sealed_at_ms'] for r in recent['releases']],[1000,1500])
        self.assertNotIn(500,[r['sealed_at_ms'] for r in recent['releases']])
        # The record arriving at 1000 starts at 400, before the arrival-window
        # lower bound 500; its support must remain immutable.
        self.assertEqual(recent['releases'][0]['start_ms'],400)
        self.assertEqual(recent['releases'][0]['end_ms'],800)
        self.assertEqual(recent['end_ms'],16000)

    def test_future_record_insertion_cannot_change_prefix_aliases_or_features(self):
        first=public_fixture()
        base=deepcopy(first)
        base['releases']=[r for r in base['releases'] if r['sealed_at_ms']<=1000]
        for i,r in enumerate(base['releases']):r['release_id']=f'release-{i:06d}'
        self.assertEqual(public_view(first,1000),public_view(base,1000))
        self.assertEqual(feature_views(first,[],1000),feature_views(base,[],1000))

    def test_future_public_payload_values_never_enter_prefix_features(self):
        original=public_fixture()
        changed=deepcopy(original)
        for release in changed['releases']:
            if release['sealed_at_ms']>1000:
                for cell in release['cells']:
                    cell['observation_contributions']=10000
                    cell['distinct_road_users']=500
                    cell['mean_sample_occupancy']=1000
        self.assertEqual(feature_views(original,[],1000),feature_views(changed,[],1000))
        self.assertNotEqual(feature_views(original,[],16000)['history'],
                            feature_views(changed,[],16000)['history'])

    def test_full_horizon_restores_legacy_cumulative_features_with_known_points(self):
        public=public_fixture()
        events=[dict(acquired_at_ms=100,available_at_ms=100,reported=point(100)),
                dict(acquired_at_ms=700,available_at_ms=700,reported=point(700,x=45))]
        known=knowledge_at(events,16000)
        final=feature_views(public,events,16000)
        self.assertEqual(final['history'][-31:],feature_vector(public,known,True))
        self.assertEqual(final['auxiliary'][0],2)

    def test_no_mutation_and_final_cumulative_legacy_block_equality(self):
        public=public_fixture();before=deepcopy(public)
        features=feature_views(public,[],16000)
        self.assertEqual(features['history'][-31:],feature_vector(public,[],True))
        changed=public_view(public,1000)
        changed['releases'][0]['cells'][0]['mean_sample_occupancy']=999
        self.assertEqual(public,before)
        self.assertEqual(public_view(public,0)['releases'],[])

    def test_feature_dimensions_names_and_exact_nesting(self):
        public=public_fixture()
        events=[dict(acquired_at_ms=100,available_at_ms=100,reported=point(100)),
                dict(acquired_at_ms=3000,available_at_ms=3000,reported=point(3000,x=45))]
        views=feature_views(public,events,1000)
        self.assertEqual({k:len(v) for k,v in views.items()},dict(auxiliary=9,recent=40,history=71))
        self.assertEqual(views['recent'][:9],views['auxiliary'])
        self.assertEqual(views['history'][:40],views['recent'])
        for name,values in views.items():self.assertEqual(len(feature_names(name)),len(values))
        self.assertEqual(views['auxiliary'][0],1)
        self.assertEqual(len(set(feature_names('history'))),71)

    def test_auxiliary_hand_calculation_uses_reported_time_order(self):
        values=auxiliary_features([point(300,x=4,y=5),point(100,x=1,y=1)])
        expected=[2,2.5,3,1.5,2,100,300,200,5]
        self.assertEqual(values,expected)
        self.assertEqual(auxiliary_features([]),[0.0]*9)
        self.assertEqual(auxiliary_features([point(100)])[3:5],[0,0])
        self.assertEqual(auxiliary_features([point(100)])[8],0)

    def test_unknown_public_channels_and_invalid_checkpoints_rejected(self):
        public=public_fixture()
        for field in ('label','runtime','private_suppression'):
            with self.assertRaises(ValueError):public_view(dict(public,**{field:1}),1000)
        for checkpoint in (-1,True,16001):
            with self.assertRaises(ValueError):public_view(public,checkpoint)
        for window in (0,-1,True,1.5):
            with self.assertRaises(ValueError):public_view(public,1000,recent_window_ms=window)
        with self.assertRaises(ValueError):feature_names('unknown')
        with self.assertRaises(ValueError):auxiliary_features([dict(point(100),label=1)])


class CausalBatchFeatureTests(unittest.TestCase):
    def events(self):
        trace = [point(time, x=(time // 100) % 79 + .25, y=3)
                 for time in range(100, 16000, 100)]
        return {profile: knowledge_events(trace, GRID, 16000, 13, profile)
                for profile in PROFILES}

    def test_batch_exactly_matches_strict_views_for_empty_partial_full_and_noisy(self):
        populated = public_fixture()
        empty = dict(deepcopy(populated), releases=[])
        checkpoints = (0, 400, 500, 1000, 1500, 2000, 16000)
        for public in (empty, populated):
            for events in ({profile: [] for profile in PROFILES}, self.events()):
                batch = feature_views_many(public, events, checkpoints)
                self.assertEqual(set(batch), set(PROFILES))
                for profile in PROFILES:
                    self.assertEqual(list(batch[profile]), list(checkpoints))
                    for checkpoint in checkpoints:
                        self.assertEqual(batch[profile][checkpoint],
                            feature_views(public, events[profile], checkpoint))
        self.assertIs(feature_grid, feature_views_many)

    def test_full_public_validation_occurs_once_and_rejects_invalid_future_records(self):
        public = public_fixture()
        with patch('causal_privacy._validated_public', wraps=_validated_public) as validate:
            feature_views_many(public, self.events(), CHECKPOINTS)
            self.assertEqual(validate.call_count, 1)
        for change in ('unknown_cell', 'bad_geometry', 'nonfinite_count', 'unknown_release'):
            bad = deepcopy(public)
            release = bad['releases'][-1]
            cell = release['cells'][0]
            if change == 'unknown_cell': cell['private_road_user_id'] = 'secret'
            elif change == 'bad_geometry': cell['x'] += 1
            elif change == 'nonfinite_count': cell['mean_sample_occupancy'] = math.inf
            else: release['private_window_status'] = 'secret'
            with self.subTest(change=change), self.assertRaises(ValueError):
                feature_views_many(bad, self.events(), (0, 1000))
            # The established single-view public boundary remains equally strict.
            with self.assertRaises(ValueError): feature_views(bad, [], 0)

    def test_batch_does_not_mutate_or_return_aliases_to_inputs_or_other_views(self):
        public, events = public_fixture(), self.events()
        before = deepcopy((public, events))
        batch = feature_views_many(public, events, (1000, 16000))
        untouched = deepcopy(batch['noisy_25'])
        original_history = list(batch['exact_25'][1000]['history'])
        batch['exact_25'][1000]['recent'][0] = -999
        batch['exact_25'][1000]['auxiliary'][0] = -888
        self.assertEqual(batch['exact_25'][1000]['history'], original_history)
        self.assertEqual(batch['noisy_25'], untouched)
        self.assertEqual((public, events), before)
        self.assertEqual(feature_views_many(public, events, (1000, 16000))['noisy_25'], untouched)

    def test_batch_rejects_unknown_profiles_schedules_and_private_future_knowledge(self):
        public = public_fixture()
        for events in ({}, [], {'unknown': []}):
            with self.subTest(events=events), self.assertRaises(ValueError):
                feature_views_many(public, events, (1000,))
        for checkpoints in ((), [], (1000, 1000), (2000, 1000), (True,), (-1,), (16001,), (1.5,)):
            with self.subTest(checkpoints=checkpoints), self.assertRaises(ValueError):
                feature_views_many(public, {'exact_25': []}, checkpoints)
        future = dict(acquired_at_ms=5000, available_at_ms=5000,
                      reported=dict(point(5000), source_id='secret'))
        with self.assertRaises(ValueError):
            feature_views_many(public, {'exact_25': [future]}, (0, 1000))
        for knowledge in (None, [dict(point(100), source_id='secret')]):
            from empirical_privacy import _feature_vector_validated
            with self.assertRaises(ValueError):
                _feature_vector_validated(public, knowledge, True)


if __name__=='__main__':unittest.main()
