"""Actual native outputs and adversarial independent filtered-release audits."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from run_local_policy_replay import audit
from run_semantic_priority_study import fixture, policy
from semantic_suppression_audit import effective, may_filter, audit_budget, _raw_projection, SourceIndex
from oracle import decode_cell

ROOT = Path(__file__).resolve().parents[2]
BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT/'simulator/build/AggregationReplay'))


def source():
    data = fixture('rare_local')
    data['end_ms'] = 800
    data['batches'] = [b for b in data['batches'] if b['observed_at_ms'] < 800]
    for batch in data['batches']:
        batch['observations'] = [r for r in batch['observations'] if r['cell_id'] == 48]
    return data


def settings(cap=.1):
    config = policy('rare_local',5,1,20,800,'temporal_first')
    config['policy_tree']['execution'] = {'publication_model':'private_final_snapshot',
        'strategy':'semantic_first', 'semantic_secondary_strategy':'temporal_first', 'release_trigger':'policy_satisfied'}
    config['policy_tree']['root']['distinct_contributors'] = {'min':5}
    config['policy_tree']['root']['semantic_suppression_fraction'] = {'max':cap}
    return config


def core(data, config, mode='semantic_first'):
    with tempfile.TemporaryDirectory(prefix='ump-semantic-filter-audit-') as temporary:
        directory = Path(temporary)
        files = [directory/name for name in ('input.json','config.json','output.json')]
        for path, value in zip(files,(data,config)):
            path.write_text(json.dumps(value))
        completed = subprocess.run([str(BINARY),'--input',str(files[0]),'--config',str(files[1]),
            '--mode',mode,'--output',str(files[2])], capture_output=True,text=True,timeout=15)
        if completed.returncode:
            raise AssertionError(completed.stdout+completed.stderr)
        return json.loads(files[2].read_text())


@unittest.skipUnless(BINARY.is_file(),'Build native AggregationReplay')
class SemanticSuppressionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.config = source(), settings()
        cls.actual = core(cls.data,cls.config)

    def test_source_reconstructed_filter_and_full_retirement(self):
        checked = audit(self.data,self.config,self.actual)
        accounting = checked['source_accounting']
        self.assertEqual(checked['status'],'verified')
        self.assertTrue(checked['scalar']['valid'])
        self.assertEqual(accounting['input_observations'],140)
        self.assertEqual(accounting['retained_observations'],133)
        self.assertEqual(accounting['selectively_suppressed_observations'],7)
        self.assertEqual(accounting['whole_footprint_suppressed_observations'],0)
        self.assertEqual(accounting['by_source_type']['adult_cyclist']['retained_fraction'],0)
        self.assertEqual(accounting['by_source_type']['pedestrian']['retained_fraction'],1)
        self.assertEqual(checked['contribution_selection'],'policy_filtered')
        self.assertLessEqual(checked['suppression_candidates'],2*len(self.config['semantic_taxonomy']['nodes']))
        self.assertEqual(self.actual['input_observation_contributions'],self.actual['accounted_observation_contributions'])
        self.assertNotIn('evaluation_nanoseconds',repr(self.actual['windows']))

    def test_explicit_capacity_reaches_actual_independent_oracle(self):
        checked=audit(self.data,self.config,self.actual,max_cells=1000)
        self.assertEqual(checked['scalar']['scope']['max_cells'],1000)
        with self.assertRaisesRegex(ValueError,'budget'):
            audit(self.data,self.config,self.actual,max_cells=1)

    def test_cap_zero_keeps_old_complete_population(self):
        cfg=settings(0); actual=core(self.data,cfg)
        checked=audit(self.data,cfg,actual)
        self.assertEqual(checked['source_accounting']['retained_observations'],140)
        self.assertEqual(checked['source_accounting']['selectively_suppressed_observations'],0)
        self.assertEqual(checked['contribution_selection'],'all_contributions')
        self.assertTrue(all(c['semantic']['semantic_mean_loss']==1 for r in actual['releases'] for c in r['cells']))

    def test_rejects_counts_private_masks_loss_and_retirement_tampering(self):
        def mutate_counts(a): a['releases'][0]['cells'][0]['observation_contributions']+=1
        def mutate_mask(a): a['windows'][0]['cells'][0]['semantic_suppression']['suppressed_terminal_categories']=[]
        def mutate_map(a): a['windows'][0]['cells'][0]['semantic_suppression']['suppressed_type_observation_contributions']={'pedestrian':3}
        def mutate_loss(a): a['windows'][0]['cells'][0]['semantic_suppression']['full_input_semantic_loss']=0
        def mutate_retirement(a): a['windows'][0]['input_observation_contributions']-=1
        def mutate_metric(a): a['windows'][0]['cells'][0]['metrics']['distinct_contributors']=20
        for mutation in (mutate_counts,mutate_mask,mutate_map,mutate_loss,mutate_retirement,mutate_metric):
            with self.subTest(mutation=mutation.__name__):
                damaged=deepcopy(self.actual); mutation(damaged)
                with self.assertRaises(ValueError): audit(self.data,self.config,damaged)

    def test_strict_region_prohibits_previously_valid_filter(self):
        cfg=deepcopy(self.config)
        cfg['policy_regions']=[dict(id='strict',type='strict',x=0,y=0,width=20,height=20,
            requirements={'semantic_suppression_fraction':{'max':0}})]
        cfg['policy_tree']['regions']=['strict']
        with self.assertRaisesRegex(ValueError,'permission|cap'):
            audit(self.data,cfg,self.actual)
        actual=core(self.data,cfg)
        checked=audit(self.data,cfg,actual)
        self.assertEqual(checked['source_accounting']['selectively_suppressed_observations'],0)
        # Global capability label remains policy_filtered even if this region forbids it.
        self.assertTrue(may_filter(cfg))
        self.assertEqual(checked['contribution_selection'],'policy_filtered')

    def test_spatial_first_same_input_gets_its_own_valid_retained_audit(self):
        cfg=settings();cfg['policy_tree']['id']='spatial-first-filter-policy'
        cfg['policy_tree']['execution'].pop('semantic_secondary_strategy')
        cfg['policy_tree']['execution']['strategy']='spatial_first'
        actual=core(self.data,cfg,'spatial_first')
        checked=audit(self.data,cfg,actual)
        self.assertEqual(checked['source_accounting']['retained_observations'],133)


class OfflineAuditCapacityTests(unittest.TestCase):
    def test_explicit_capacity_above_old_limit_preserves_full_retirement_checks(self):
        # Four distinct depth-one scopes retire every1-ms interval. This creates
        #200004 legitimate empty retirements, rather than padding duplicate rows.
        end=50001;grid=dict(x=0,y=0,width=80,height=80,leaf_depth=1)
        data=dict(schema='ump.observation-replay.v1',run_id='large-empty-retirement',sensor_id='agbs',
            coverage=grid,sampling_period_ms=1,end_ms=end,
            batches=[dict(sequence=t,observed_at_ms=t,status='measured',observations=[]) for t in range(1,end)])
        cfg=settings(0);cfg['temporal_adaptation']['coordination']='cell_local'
        scopes=[decode_cell(grid,cid,1) for cid in range(12,16)]
        windows=[dict(start_ms=start,end_ms=start+1,evaluated_at_ms=start+1,
            expected_samples=int(start>0),measured_samples=int(start>0),unavailable_samples=0,missing_samples=0,
            coverage='complete' if start else 'no_scheduled_samples',input_observation_contributions=0,
            selected_cells=0,suppressed_cells=0,cells=[],coordination_cell=scope)
            for start in range(end) for scope in scopes]
        actual=dict(schema='ump.replay-result.v1',mode='semantic_first',
            source=dict(run_id=data['run_id'],sensor_id='agbs',application_id=cfg['application_id'],
                coverage=grid,sampling_period_ms=1,end_ms=end),parameters=dict(coordination='cell_local'),
            input_observation_contributions=0,accounted_observation_contributions=0,windows=windows,releases=[])
        index=SourceIndex(data)
        with self.assertRaisesRegex(ValueError,'window/release budget'):
            _raw_projection(data,cfg,actual,index)
        checked=_raw_projection(data,cfg,actual,index,max_cells=200004)
        self.assertTrue(checked['valid']);self.assertEqual(len(checked['checked_windows']),200004)
        self.assertEqual(checked['scope']['max_cells'],200004)
        del checked
        # A defect after the old200000 boundary must still be detected.
        actual['windows'][-1]['suppressed_cells']=1
        with self.assertRaisesRegex(ValueError,'Independent raw ownership/retirement audit failed'):
            _raw_projection(data,cfg,actual,index,max_cells=200004)

    def test_explicit_capacity_is_bounded_exact_integer_and_defaults_stay_distinct(self):
        self.assertEqual(audit_budget(None),200000)
        self.assertEqual(audit_budget(None,100000),100000)
        self.assertEqual(audit_budget(1000000),1000000)
        for value in (0,-1,True,200000.0,1000001,float('inf'),'1000000'):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'1 to 1000000'):
                audit_budget(value)


class StrictPermissionTests(unittest.TestCase):
    def test_region_cannot_enable_without_root_permission(self):
        cfg=settings();cfg['policy_tree']['root'].pop('semantic_suppression_fraction')
        cfg['policy_regions']=[dict(id='local',type='local',x=0,y=0,width=20,height=20,
            requirements={'semantic_suppression_fraction':{'max':.3}})]
        cfg['policy_tree']['regions']=['local']
        bounds,_=effective(cfg,dict(x=0,y=0,width=20,height=20))
        self.assertEqual(bounds['semantic_suppression_fraction'],{'max':0})
        self.assertFalse(may_filter(cfg))


if __name__=='__main__': unittest.main()
