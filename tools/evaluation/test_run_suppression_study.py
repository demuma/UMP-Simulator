"""Bounded post-hoc protocol, exact prefix lineage and six real-core cases."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest

from make_fixture import cell_id
from run_suppression_study import MATRIX, case_config, prefix, run
from test_semantic_suppression_audit import source, settings, BINARY


class SuppressionProtocolTests(unittest.TestCase):
    def test_prefix_preserves_rows_and_rejects_misaligned_horizon(self):
        original=source();original['coverage']['leaf_depth']=6
        for batch in original['batches']:
            for row in batch['observations']:row['cell_id']=cell_id(row['x'],row['y'],original['coverage'])
        actual=prefix(original,400)
        self.assertEqual(actual['end_ms'],400)
        self.assertEqual(actual['batches'],original['batches'][:3])
        self.assertEqual(original['end_ms'],800)
        for bad in (0,True,401,-100):
            with self.assertRaises(ValueError):prefix(original,bad)

    def test_six_fair_policy_cases_change_only_option_identity_execution(self):
        base=settings()
        for name,mode,on in MATRIX:
            cfg=case_config(base,name,mode,on,.1)
            self.assertEqual(cfg['policy_tree']['root']['semantic_suppression_fraction']['max'],.1 if on else 0)
            expected=deepcopy(base['policy_tree']['root']);expected['semantic_suppression_fraction']={'max':.1 if on else 0}
            self.assertEqual(cfg['policy_tree']['root'],expected)
            self.assertEqual(cfg['policy_regions'],base['policy_regions'])
            self.assertEqual(cfg['semantic_taxonomy'],base['semantic_taxonomy'])
            if mode=='spatial_first':self.assertNotIn('semantic_secondary_strategy',cfg['policy_tree']['execution'])
        self.assertEqual(len({case_config(base,n,m,on,.1)['policy_tree']['id'] for n,m,on in MATRIX}),6)

    @unittest.skipUnless(BINARY.is_file(),'Build native AggregationReplay')
    def test_actual_six_case_run_freezes_source_and_reports_full_input_loss(self):
        data=source();data['coverage']['leaf_depth']=6
        for batch in data['batches']:
            for row in batch['observations']:row['cell_id']=cell_id(row['x'],row['y'],data['coverage'])
        cfg=settings();cfg['spatial_selection']['min_depth']=3
        cfg['temporal_adaptation']['max_active_cells']=4096
        cfg['history']['max_buckets']=16384
        cfg['policy_tree']['root']['cell_side_m']['max']=10
        cfg['policy_tree']['root']['window_duration_ms']['max']=1000
        cfg['policy_tree']['root']['age_at_evaluation_ms']['max']=1000
        with tempfile.TemporaryDirectory(prefix='ump-suppression-study-') as temporary:
            parent=Path(temporary);inp=parent/'observations.json';conf=parent/'config.json'
            inp.write_text(json.dumps(data));conf.write_text(json.dumps(cfg))
            out=parent/'study'
            result=run(inp,conf,out,BINARY,duration_ms=800,wall_budget_s=15)
            self.assertEqual(result['status'],'verified')
            self.assertEqual(set(result['cases']),{row[0] for row in MATRIX})
            self.assertEqual(len(result['protocol']['derived_input_sha256']),64)
            self.assertEqual(result['protocol']['derived_horizon_ms'],800)
            self.assertEqual(result['protocol']['analysis_status'],'post_hoc_sensitivity')
            for name,mode,on in MATRIX:
                case=result['cases'][name]
                self.assertEqual(case['input_observations'],140)
                self.assertEqual(case['contribution_selection'],'policy_filtered' if on else 'all_contributions')
                self.assertEqual(case['independent_audit']['published_policy_violations'],0)
                self.assertEqual(case['source_accounting']['input_observations'],140)
                self.assertNotIn('retained_by_source_group',repr(case))
            with self.assertRaises(ValueError):run(inp,conf,out,BINARY)


if __name__=='__main__':unittest.main()
