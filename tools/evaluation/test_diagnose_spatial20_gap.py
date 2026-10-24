"""Small independent membership, parent-policy and phase-diagnosis checks."""
from copy import deepcopy
from collections import Counter
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import diagnose_spatial20_gap as diagnosis
from oracle import decode_cell


def config():
    return dict(application_id='gap-fixture',policy_tree=dict(id='gap-policy',version='1',regions=[],
        root=dict(distinct_contributors={'min':2},min_category_distinct_contributors={'min':2},
            cell_side_m={'min':1.25,'max':20},window_duration_ms={'min':400,'max':1000},
            age_at_evaluation_ms={'max':1000},semantic_max_loss={'max':1},semantic_suppression_fraction={'max':0})),
        policy_regions=[],semantic_taxonomy=dict(id='gap-taxonomy',version='1',nodes=[
            dict(id='road_user',loss=1),dict(id='pedestrian',parent='road_user',loss=.5),
            dict(id='adult',parent='pedestrian',loss=0,input_types=['Adult Pedestrian'])]))


def source():
    return dict(schema='ump.observation-replay.v1',run_id='gap-source',sensor_id='agbs',
        coverage=dict(x=0,y=0,width=80,height=80,leaf_depth=3),sampling_period_ms=100,end_ms=800,
        batches=[dict(observed_at_ms=t,status='measured',sequence=t//100,observations=[
            dict(id='private-a',type='Adult Pedestrian',cell_id=192,x=1,y=1),
            dict(id='private-c',type='Adult Pedestrian',cell_id=192,x=2,y=1),
            dict(id='private-b',type='Adult Pedestrian',cell_id=193,x=11,y=1)]) for t in range(100,800,100)])


def window(data,identity,depth,start,end,n,selected,reason):
    geometry=decode_cell(data['coverage'],identity,depth)
    cell=dict(geometry,observation_contributions=n,distinct_road_users=2 if selected else 1,
        mean_sample_occupancy=2 if selected else 1,selected=selected,reason=reason,metrics={},checks=[])
    return dict(start_ms=start,end_ms=end,evaluated_at_ms=end,coordination_cell=geometry,
        input_observation_contributions=n,completion_reason=reason,temporal_extensions=0,
        cells=[cell] if n else [],temporal_decisions=[dict(action='finalize',start_ms=start,end_ms=end,evaluated_at_ms=end,status='pass' if selected else 'fail')])


def results(data):
    raw=[window(data,192,3,0,400,6,True,'requirements_met'),window(data,192,3,400,800,8,True,'requirements_met'),
         window(data,193,3,0,800,7,False,'coordination_handoff')]+[
         window(data,cid,3,0,800,0,False,'measured_empty') for cid in (194,195)]
    def release(identity,depth,start,end,n):
        return dict(start_ms=start,end_ms=end,sealed_at_ms=end,cells=[dict(decode_cell(data['coverage'],identity,depth),observation_contributions=n)])
    adaptive=dict(schema='ump.replay-result.v1',windows=raw,releases=[release(192,3,0,400,6),release(192,3,400,800,8)])
    fixed=dict(schema='ump.replay-result.v1',windows=[],releases=[release(48,2,0,400,9),release(48,2,400,800,12)])
    return adaptive,fixed


class SpatialGapDiagnosisTests(unittest.TestCase):
    def test_stream_parser_preserves_large_header_numeric_boundary_and_both_arrays(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'native.json'
            # Put the number across a64-KiB read boundary.
            prefix='{"padding":"';middle='","number":'
            padding='x'*(65536-len(prefix)-len(middle)-3)
            raw=prefix+padding+middle+'123456789,"windows":[{"a":1},{"a":2}],"releases":[{"b":3}]}'
            path.write_text(raw)
            rows=list(diagnosis.native_records(path))
            self.assertEqual(dict((key,value) for key,value in rows if key not in ('windows','releases'))['number'],123456789)
            self.assertEqual([value for key,value in rows if key=='windows'],[{'a':1},{'a':2}])
            self.assertEqual([value for key,value in rows if key=='releases'],[{'b':3}])

    def test_exact_membership_parent_check_and_phase_difference_are_conserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=source();cfg=config();adaptive,fixed=results(data)
            for name,value in [('observations',data),('adaptive',adaptive),('fixed',fixed),('adaptive-policy',cfg)]:
                (root/(name+'.json')).write_text(json.dumps(value))
            summary=dict(status='verified',protocol=dict(observations_sha256=diagnosis.sha(root/'observations.json')),
                cases={name:dict(result_sha256=diagnosis.sha(root/(name+'.json')),stats=dict(retained_observation_contributions=n)) for name,n in [('adaptive',14),('fixed',21)]})
            (root/'summary.json').write_text(json.dumps(summary))
            with contextlib.redirect_stdout(io.StringIO()):report=diagnosis.diagnose(root,'adaptive','fixed',root/'diagnosis')
            self.assertEqual(report['membership'],{'both_retained':14,'fixed_only':7})
            self.assertEqual(report['source_observations'],21);self.assertEqual(report['net_fixed_advantage'],7)
            self.assertEqual(report['fixed_only_counterfactual_classification'],{'parent_passes_same_interval_but_owner_starts_differ':7})
            example=report['examples'][0]
            self.assertTrue(example['same_interval_parent']['passing'])
            self.assertEqual(example['parent_clock_evidence']['starts_leaf_units'],{'0':3,'400':1})
            self.assertFalse(example['parent_clock_evidence']['all_starts_match'])
            self.assertNotIn('private-a',json.dumps(report));self.assertNotIn('private-b',json.dumps(report))
            self.assertNotIn('"x":',json.dumps(report))
            with self.assertRaisesRegex(ValueError,'fresh'):diagnosis.diagnose(root,'adaptive','fixed',root/'diagnosis')

    def test_parent_inherits_stricter_region_even_when_source_points_are_outside_it(self):
        data=source();cfg=config()
        cfg['policy_tree']['regions']=['lower-half'];cfg['policy_regions']=[dict(id='lower-half',type='fresh',x=0,y=10,width=10,height=10,
            requirements=dict(window_duration_ms={'max':500},age_at_evaluation_ms={'max':500}))]
        evidence=diagnosis.ParentEvidence(data,cfg,{})
        parent=evidence.assess(48,0,800,800)
        self.assertEqual(parent['intersected_regions'],['lower-half'])
        self.assertFalse(parent['passing']);self.assertEqual(set(parent['failed_metrics']),{'window_duration_ms','age_at_evaluation_ms'})
        self.assertTrue(evidence.assess(48,0,400,400)['passing'])

    def test_membership_never_double_counts_published_parent_and_child(self):
        index=diagnosis.IntervalIndex();index.add(48,0,400,'parent');index.add(192,0,400,'child');index.finish()
        with self.assertRaisesRegex(ValueError,'Overlapping ancestor'):index.match(192,100,3)
        index=diagnosis.IntervalIndex();index.add(48,0,400,'old');index.add(48,400,800,'new');index.finish()
        self.assertEqual(index.match(192,399,3),'old');self.assertEqual(index.match(192,400,3),'new')
        self.assertIsNone(index.match(192,800,3))


if __name__=='__main__':unittest.main()
