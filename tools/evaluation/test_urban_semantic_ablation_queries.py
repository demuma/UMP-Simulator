"""Hand-calculated checks; private reference data never repairs public answers."""
from copy import deepcopy
import unittest

import urban_semantic_ablation_queries as queries


def taxonomy():
    return {'id':'tiny','version':'1','nodes':[
        {'id':'road_user','loss':1},
        {'id':'adult','parent':'road_user','loss':0,'input_types':['Adult']},
        {'id':'child','parent':'road_user','loss':0,'input_types':['Child']} ]}


def source(end=400):
    return dict(schema='ump.observation-replay.v1',run_id='private-source',sensor_id='agbs',
        coverage=dict(x=0,y=0,width=40,height=40,leaf_depth=1),sampling_period_ms=100,end_ms=end,
        batches=[dict(observed_at_ms=t,status='measured',observations=[
            dict(id='private-a',type='Adult',cell_id=12,x=1,y=1),
            dict(id='private-b',type='Child',cell_id=12,x=2,y=1)]) for t in range(100,end,100)])


def cell(identity=12, bins=None):
    bins=bins or [('adult',3,1),('child',3,1)]
    depth=0 if identity==3 else 1
    side=40 if depth==0 else 20
    x=0 if identity==3 else (identity&1)*20
    y=0 if identity==3 else ((identity>>1)&1)*20
    total=sum(n for _,n,_ in bins)
    return dict(cell_id=identity,depth=depth,x=x,y=y,width=side,height=side,
        observation_contributions=total,distinct_road_users=sum(n for _,_,n in bins),
        semantic=dict(schema='ump.semantic-release.v1',taxonomy_id='tiny',taxonomy_version='1',
            min_category_distinct_contributors=min(n for _,_,n in bins),
            semantic_max_loss=max(1 if c=='road_user' else 0 for c,_,_ in bins),
            semantic_mean_loss=sum((1 if c=='road_user' else 0)*n for c,n,_ in bins)/total,
            categories=[dict(category_id=c,observation_contributions=n,distinct_contributors=d) for c,n,d in bins]))


def release(cells=None,start=0,end=400,name='r',sealed=None):
    return dict(release_id=name,start_ms=start,end_ms=end,sealed_at_ms=end if sealed is None else sealed,
                cells=cells or [cell()])


def evaluate(data=None,releases=None,**kwargs):
    data=source() if data is None else data
    return queries.evaluate(data,{'releases':[release()] if releases is None else releases},taxonomy(),include_queries=True,**kwargs)


class AlignedSemanticQueryTests(unittest.TestCase):
    def test_exact_leaf_counts_and_full_denominator(self):
        value=evaluate()
        self.assertEqual(value['query_definition']['query_count'],12)
        self.assertEqual(value['exact']['summary']['answered_query_count'],3)
        self.assertEqual(value['exact']['summary']['query_coverage'],.25)
        self.assertEqual(value['exact']['summary']['answered_only_mae'],0)
        self.assertEqual(value['exact']['by_category']['adult']['query_count'],4)
        self.assertEqual(value['exact']['by_category']['adult']['answered_query_count'],1)
        self.assertEqual(value['estimate']['summary']['answered_only_mae'],0)

    def test_parent_generalization_is_unknown_even_for_estimate(self):
        value=evaluate(releases=[release([cell(bins=[('road_user',6,2)])])])
        for mode in ('exact','estimate'):
            self.assertEqual(value[mode]['by_category']['road_user']['answered_query_count'],1)
            self.assertEqual(value[mode]['by_category']['adult']['answered_query_count'],0)
            self.assertIsNone(value[mode]['by_category']['adult']['answered_only_mae'])
            self.assertEqual(value[mode]['by_category']['adult']['unknown_reasons']['semantic_generalization'],1)

    def test_missing_support_unknown_not_ground_truth_zero(self):
        value=evaluate(releases=[])
        self.assertEqual(value['exact']['summary']['reference_available_query_count'],12)
        self.assertEqual(value['exact']['summary']['known_zero_reference_query_count'],9)
        self.assertEqual(value['exact']['summary']['answered_query_count'],0)
        self.assertIsNone(value['exact']['summary']['answered_only_mae'])
        self.assertTrue(all(q['prediction'] is None for q in value['estimate']['queries']))

    def test_public_count_discrepancy_is_not_repaired_by_reference(self):
        value=evaluate(releases=[release([cell(bins=[('adult',6,1)])])])
        self.assertEqual(value['exact']['by_category']['adult']['answered_only_mae'],3)
        self.assertEqual(value['exact']['by_category']['child']['answered_only_mae'],3)
        child=next(q for q in value['exact']['queries'] if q['cell_id']==12 and q['category_id']=='child')
        self.assertEqual(child['prediction'],0)

    def test_spatial_estimate_allocates_count_but_does_not_invent_exact_answer(self):
        value=evaluate(releases=[release([cell(3,bins=[('adult',12,1)])])])
        self.assertEqual(value['exact']['summary']['answered_query_count'],0)
        self.assertEqual(value['estimate']['summary']['answered_query_count'],12)
        adults=[q['prediction'] for q in value['estimate']['queries'] if q['category_id']=='adult']
        self.assertEqual(adults,[3,3,3,3])
        self.assertEqual(value['estimate']['by_category']['adult']['answered_only_mae'],2.25)

    def test_temporal_estimate_uses_sample_counts_and_excludes_t0(self):
        value=evaluate(source(800),[release([cell(bins=[('adult',14,1)])],end=800)])
        self.assertEqual(value['exact']['summary']['answered_query_count'],0)
        adult=[q for q in value['estimate']['queries'] if q['cell_id']==12 and q['category_id']=='adult']
        self.assertEqual([q['prediction'] for q in adult],[6,8])
        self.assertEqual([q['reference'] for q in adult],[3,4])

    def test_fine_and_asynchronous_tiles_can_form_exact_answer(self):
        data=source(800)
        rows=[release([cell(bins=[('adult',1,1),('child',1,1)])],end=200,name='early'),
              release([cell(bins=[('adult',2,1),('child',2,1)])],start=200,end=400,name='late')]
        value=evaluate(data,rows)
        self.assertEqual(value['exact']['by_category']['adult']['answered_query_count'],1)
        self.assertEqual(value['exact']['by_category']['adult']['answered_only_mae'],0)

    def test_reference_unavailable_is_not_zero_and_cannot_repair_public(self):
        data=source();data['batches'][1].update(status='unavailable',observations=[])
        value=evaluate(data)
        self.assertEqual(value['exact']['summary']['answered_query_count'],3)
        self.assertEqual(value['exact']['summary']['scored_query_count'],0)
        self.assertEqual(value['exact']['summary']['reference_unavailable_query_count'],12)
        self.assertIsNone(value['exact']['summary']['answered_only_mae'])

    def test_cached_reference_cannot_be_used_for_another_world(self):
        data=source();reference=queries.prepare_reference(data,taxonomy())
        value=queries.evaluate(data,{'releases':[release()]},taxonomy(),reference=reference)
        self.assertEqual(value['exact']['summary']['answered_query_count'],3)
        with self.assertRaises(ValueError):
            queries.evaluate(deepcopy(data),{'releases':[release()]},taxonomy(),reference=reference)

    def test_cached_taxonomy_change_rejected(self):
        data=source();reference=queries.prepare_reference(data,taxonomy());changed=taxonomy()
        changed['nodes'][0]['loss']=.5
        with self.assertRaises(ValueError):
            queries.evaluate(data,{'releases':[release()]},changed,reference=reference)

    def test_invalid_overlap_unknown_type_and_bad_time_rejected(self):
        with self.assertRaises(ValueError):evaluate(releases=[release(),release(name='duplicate-support')])
        data=source();data['batches'][0]['observations'][0]['type']='unknown'
        with self.assertRaises(ValueError):evaluate(data)
        data=source();data['batches'][0]['observed_at_ms']=0
        with self.assertRaises(ValueError):evaluate(data)

    def test_unaligned_size_window_and_budget_rejected(self):
        for kwargs in ({'cell_side_m':15},{'window_ms':450},{'cell_side_m':0}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):evaluate(**kwargs)
        with self.assertRaises(ValueError):queries.prepare_reference(source(),taxonomy(),cell_side_m=.001)

    def test_final_snapshot_uses_actual_sealing_not_live_deadlines(self):
        value=evaluate(source(800),[release(end=400,sealed=800)])
        self.assertEqual(value['exact']['by_category']['road_user']['answered_query_count'],1)
        with self.assertRaises(ValueError):evaluate(releases=[release(sealed=500)])

    def test_no_queries_or_private_fields_in_default_output(self):
        data=source();before=deepcopy(data)
        value=queries.evaluate(data,{'releases':[release()]},taxonomy())
        import json
        encoded=json.dumps(value)
        for text in ('private-source','private-a','private-b','"queries"','source_object_identity'):
            self.assertNotIn(text,encoded)
        self.assertEqual(data,before)
        self.assertEqual(set(value['exact']['summary'])-{'unknown_reasons'},set(queries.SUMMARY_FIELDS))

    def test_each_world_has_its_own_truth(self):
        data=source();data['batches'][0]['observations'].pop()
        value=evaluate(data)
        self.assertEqual(value['exact']['by_category']['child']['answered_only_mae'],1)


if __name__=='__main__':unittest.main()
