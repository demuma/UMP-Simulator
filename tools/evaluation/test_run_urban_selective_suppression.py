"""Synthetic boundaries for the new study; no actual sources or study jobs."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run_urban_selective_suppression as s
import test_run_urban_semantic_ablation as old


def rows(include_test=True):
    out=[]
    for split,groups in old.expected().items():
        if split=='test' and not include_test:continue
        for group in groups:
            for m in s.METHODS:
                for label,world in ((1,'IN'),(0,'OUT')):
                    out.append(dict(group_id=group,split=split,world=world,label=label,method_id=m['id'],
                        features=[0.]*111,scalar_features=[0.]*31,auxiliary_features=[0.]*8,
                        controls=dict(prior_only=.5,unprotected=label,no_output_features=[0.]*111),utility={}))
    return out


class CatalogTests(unittest.TestCase):
    def test_seven_pairs_and_three_dependencies(self):
        self.assertEqual(len(s.METHODS),14);self.assertEqual(len(s.NATIVE_METHODS),9)
        self.assertEqual([m['window_ms'] for m in s.AUXILIARY_METHODS],[1000,2000,4000])
        self.assertTrue(all(m['semantic_generalization']=='enabled' for m in s.METHODS+s.AUXILIARY_METHODS))
        self.assertEqual([m['suppression_cap'] for m in s.OLD_METHODS],[0]*7)
        self.assertTrue(all(m['suppression_cap']==.1 for m in s.NEW_METHODS+s.AUXILIARY_METHODS))
    def test_only_declared_cap_execution_change_and_base_unchanged(self):
        base=old.config();before=deepcopy(base)
        for m in s.METHODS+s.AUXILIARY_METHODS:
            cfg=s.variant_config(base,m);self.assertEqual(cfg['policy_tree']['root']['semantic_suppression_fraction']['max'],m['suppression_cap'])
            cfg['policy_tree']['root'].pop('semantic_suppression_fraction')
            self.assertEqual(s.legacy.previous.hard_policy(cfg),s.legacy.previous.hard_policy(base))
        self.assertEqual(base,before)
    def test_explicit_zero_and_regional_prohibition_unchanged(self):
        base=old.config();base['policy_tree']['root']['semantic_suppression_fraction']={'max':0}
        base['policy_regions']=[{'id':'restricted','requirements':{'semantic_suppression_fraction':{'max':0}}}]
        for m in s.NEW_METHODS:
            cfg=s.variant_config(base,m);self.assertEqual(cfg['policy_regions'],base['policy_regions'])
            self.assertEqual(cfg['policy_tree']['root']['semantic_suppression_fraction']['max'],.1)
    def test_unregistered_policy_candidate_rejected(self):
        m=deepcopy(s.NEW_METHODS[0]);m['window_ms']=999
        with self.assertRaisesRegex(ValueError,'Unknown'):s.variant_config(old.config(),m)
    def test_predeclared_contrast_direction_and_seeds(self):
        self.assertEqual(len(s.CONTRASTS),12)
        self.assertEqual([c[3] for c in s.CONTRASTS[:7]],list(range(20261028501,20261028508)))
        self.assertEqual([c[3] for c in s.CONTRASTS[7:]],list(range(20261028601,20261028606)))
        self.assertTrue(all(left==right+'_selective' for _,left,right,_ in s.CONTRASTS[:7]))
        self.assertTrue(all(c[2]=='regional_static20_selective' for c in s.CONTRASTS[7:]))


class NativeTests(unittest.TestCase):
    def result(self,m):
        r=old.native(m);r['parameters']['semantic_generalization']='enabled';return r
    def test_all_native_headers(self):
        for m in s.NATIVE_METHODS:s.validate_native(self.result(m),old.data(),old.config(),m)
    def test_exact_only_wrong_clock_or_source_rejected(self):
        m=s.NATIVE_METHODS[0]
        for key,value in (('semantic_generalization','exact_only'),('progress_step_ms',100),('progress_origin_ms',50)):
            r=self.result(m);r['parameters'][key]=value
            with self.assertRaises(ValueError):s.validate_native(r,old.data(),old.config(),m)
        r=self.result(m);r['source']['sensor_id']='other'
        with self.assertRaises(ValueError):s.validate_native(r,old.data(),old.config(),m)
    def test_conservation_or_fixed_window_mismatch_rejected(self):
        m=s.NATIVE_METHODS[0]
        for change in (lambda r:r.update(accounted_observation_contributions=0),lambda r:r['parameters'].update(window_ms=123)):
            r=self.result(m);change(r)
            with self.assertRaises(ValueError):s.validate_native(r,old.data(),old.config(),m)
    def test_waiting_and_plain_strategy_metadata(self):
        m=s.NEW_METHODS[-1];r=self.result(m);r['parameters']['release_trigger']='policy_satisfied'
        with self.assertRaisesRegex(ValueError,'trigger'):s.validate_native(r,old.data(),old.config(),m)
        for m in s.NEW_METHODS[2:4]:
            r=self.result(m);r['parameters']['release_trigger']='policy_satisfied'
            with self.assertRaisesRegex(ValueError,'semantic-only'):s.validate_native(r,old.data(),old.config(),m)
    def test_existing_native_attempt_never_retried(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);m=s.NATIVE_METHODS[0];(p/(m['id']+'-attempt.json')).write_text('{}')
            with patch.object(s.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'retries'):
                s.run_case(p,p/'input.json',old.config(),m,{'group_id':'g'},'IN',[],{})
            run.assert_not_called();self.assertEqual(len(list(p.iterdir())),1)
    def test_auxiliary_queries_excluded_and_features_stay_frozen(self):
        with patch.object(s.primary.pilot,'feature_check',return_value=({'values':[0.]*111},{})), \
             patch.object(s.primary.scalar,'feature_vector',return_value=[0.]*31), \
             patch.object(s.legacy.semantic,'_scalar_projection',return_value={}), \
             patch.object(s.analysis,'auxiliary_features',return_value=[0.]*8), \
             patch.object(s.primary,'positive_control',return_value=1), \
             patch.object(s.utility_adapter,'utility',return_value={}) as measure:
            for m in (s.NATIVE_METHODS[0],s.AUXILIARY_METHODS[0]):
                r=s.row_for(dict(group_id='g',split='train'),'IN',m,{'releases':[]},[],dict(coverage={},end_ms=800),{},old.config())
                self.assertEqual(len(r['features']),111);self.assertEqual(len(r['scalar_features']),31)
                self.assertEqual(measure.call_args.kwargs['include_queries'],m not in s.AUXILIARY_METHODS)


class ModelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training=rows(False);cls.expected=old.expected()
        cls.original=s.analysis.prepare_models([r for r in cls.training if r['method_id'] in s.BASE_IDS],expected_groups=cls.expected,method_ids=list(s.BASE_IDS))
        cls.attacks={name+'_selective':deepcopy(cls.original['attacks'][name]) for name in s.BASE_IDS}
    def test_28_objects_original_controls_and_models_preserved(self):
        before=deepcopy(self.original);r=s.combine_models(self.original,self.attacks,self.training,self.expected)
        self.assertEqual(len(r['models']),28);self.assertEqual(r['test_rows_seen'],0);self.assertEqual(r['training_calibration_rows'],1120)
        self.assertEqual(r['controls'],before['controls']);self.assertEqual(self.original,before)
        for name in s.BASE_IDS:self.assertEqual(r['attacks'][name],before['attacks'][name])
    def test_test_data_cannot_enter_models(self):
        with self.assertRaisesRegex(ValueError,'TEST'):s.combine_models(self.original,self.attacks,rows(),self.expected)
    def test_missing_attack_family_rejected(self):
        new=deepcopy(self.attacks);new.pop(s.NEW_IDS[0])
        with self.assertRaisesRegex(ValueError,'Seven'):s.combine_models(self.original,new,self.training,self.expected)
    def test_fit_attempt_blocks_before_collection(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);(p/'mia-fit-attempt.json').write_text('{}')
            with patch.object(s,'read_protocol',return_value=(p,{},{})),patch.object(s,'collect') as collect,self.assertRaisesRegex(ValueError,'retry'):
                s.fit_mia(p)
            collect.assert_not_called()
    def test_utility_cannot_follow_fitting(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);(p/'mia-fit-attempt.json').write_text('{}')
            with patch.object(s,'read_protocol',return_value=(p,{},{})),self.assertRaisesRegex(ValueError,'fitting'):s.run_utility(p)


class ContrastTests(unittest.TestCase):
    def fixture(self,n=3):
        return [dict(group_id=str(i),world='IN',split='test',method_id=m['id'],utility={'retained_fraction':.8 if m['suppression_enabled'] else .5}) for i in range(n) for m in s.METHODS]
    def test_paired_mean_difference_and_deterministic_interval(self):
        a=s.utility_contrasts(self.fixture());self.assertEqual(a,s.utility_contrasts(self.fixture()))
        for v in a.values():
            x=v['metrics']['retained_fraction'];self.assertAlmostEqual(x['mean_difference'],.3);self.assertEqual(x['paired_recordings'],3);self.assertEqual(len(x['ci95']),2)
    def test_missing_and_singleton_no_fake_interval(self):
        for n in (1,3):
            for entry in s.utility_contrasts(self.fixture(n)).values():
                x=entry['metrics']['retained_semantic_loss'];self.assertIsNone(x['mean_difference']);self.assertIsNone(x['ci95']);self.assertEqual(x['paired_recordings'],0)
                if n==1:self.assertIsNone(entry['metrics']['retained_fraction']['ci95'])


if __name__=='__main__':unittest.main()
