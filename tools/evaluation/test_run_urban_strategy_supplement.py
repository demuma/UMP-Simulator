"""Synthetic boundary checks; no actual recordings, native jobs or original models."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_urban_strategy_supplement as s
import test_urban_privacy_analysis as fixtures


def config():
    return dict(application_id='app',window_ms=400,
        temporal_adaptation=dict(coordination='cell_local',max_window_ms=4000,extension_step_ms=100),
        spatial_selection=dict(min_depth=2,max_evaluations=8192),
        policy_tree=dict(id='policy',version='v1',execution=dict(publication_model='private_final_snapshot',
            strategy='semantic_first',semantic_secondary_strategy='temporal_first',release_trigger='policy_satisfied'),
            root={'requirements':[{'metric':'support','min':5}]}),
        policy_regions=[{'id':'region','bounds':[0,0,5,5],'requirements':[{'metric':'window_duration_ms','max':400}]}],
        semantic_taxonomy={'id':'taxonomy'})


def data():
    return dict(run_id='run',sensor_id='sensor',application_id='app',coverage={'leaf_depth':6},sampling_period_ms=100,end_ms=300000,
                batches=[dict(observed_at_ms=100,observations=[{'id':'private','type':'Adult Pedestrian','x':1,'y':2,'cell_id':4096}])])


def native(method):
    d=data();c=config()
    parameters=dict(coordination='cell_local',progress_step_ms=50,progress_origin_ms=0,window_ms=400,
                    max_window_ms=4000,extension_step_ms=100,min_depth=2)
    if method['strategy']=='semantic_first':
        parameters.update(semantic_secondary_strategy=method['secondary_strategy'],release_trigger=method['release_trigger'])
    return dict(schema='ump.replay-result.v1',mode=method['strategy'],source={k:d[k] for k in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms','application_id')},
                parameters=parameters,input_observation_contributions=1,accounted_observation_contributions=1)


def ref(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
def auth(v):
    p=Path(v['path']);s.require(ref(p)==v,'Reference changed');return p


def all_rows():
    result=fixtures.rows()
    for method in s.VARIANTS:
        for row in fixtures.rows():
            if row['method_id']=='adaptive_semantic_first':
                row['method_id']=method['id'];result.append(row)
    return result


class ConfigurationTests(unittest.TestCase):
    def test_four_distinct_explicit_methods_no_duplicate_immediate_semantic_variant(self):
        self.assertEqual(len(s.VARIANTS),4)
        self.assertEqual(len({m['id'] for m in s.VARIANTS}),4)
        self.assertEqual([m['strategy'] for m in s.VARIANTS],['temporal_first','spatial_first','semantic_first','semantic_first'])
        self.assertEqual([m['release_trigger'] for m in s.VARIANTS],['policy_satisfied','policy_satisfied','priority_satisfied','priority_satisfied'])
        self.assertNotIn('adaptive_semantic_first',{m['id'] for m in s.VARIANTS})

    def test_variant_changes_only_execution_preferences_not_hard_policy(self):
        base=config();before=deepcopy(base)
        for method in s.VARIANTS:
            with self.subTest(method=method['id']):
                variant=s.variant_config(base,method)
                self.assertEqual(s.hard_policy(base),s.hard_policy(variant))
                s.validate_variant_config(base,variant,method)
                self.assertEqual(variant['policy_tree']['id'],base['policy_tree']['id'])
                self.assertEqual(variant['policy_tree']['execution']['publication_model'],'private_final_snapshot')
                self.assertEqual(s.variant_config(variant,method),variant)
        self.assertEqual(base,before)

    def test_wrong_or_extra_execution_setting_rejected(self):
        base=config()
        for method in s.VARIANTS:
            wrong=s.variant_config(base,method);wrong['policy_tree']['execution']['release_trigger']='unregistered'
            with self.assertRaises(ValueError):s.validate_variant_config(base,wrong,method)
            wrong=s.variant_config(base,method);wrong['policy_tree']['execution']['new_setting']='hidden'
            with self.assertRaises(ValueError):s.validate_variant_config(base,wrong,method)

    def test_regional_semantic_spatial_and_window_hard_deltas_rejected(self):
        base=config();m=s.VARIANTS[0]
        changes=[lambda c:c['policy_tree']['root']['requirements'][0].update(min=4),
                 lambda c:c['policy_regions'][0]['requirements'][0].update(max=4000),
                 lambda c:c['temporal_adaptation'].update(max_window_ms=8000),
                 lambda c:c['spatial_selection'].update(min_depth=1),
                 lambda c:c['semantic_taxonomy'].update(id='different'),
                 lambda c:c['policy_tree'].update(version='v2')]
        for change in changes:
            bad=s.variant_config(base,m);change(bad)
            with self.assertRaises(ValueError):s.validate_variant_config(base,bad,m)

    def test_unknown_or_tweaked_method_rejected(self):
        bad=deepcopy(s.VARIANTS[0]);bad['release_trigger']='priority_satisfied'
        with self.assertRaises(ValueError):s.variant_config(config(),bad)

    def test_plain_tf_sf_do_not_carry_semantic_secondary(self):
        for method in s.VARIANTS[:2]:
            value=s.variant_config(config(),method)
            self.assertNotIn('semantic_secondary_strategy',value['policy_tree']['execution'])

    def test_exploratory_contrast_seeds_fixed_and_unambiguous(self):
        self.assertEqual([c[3] for c in s.CONTRASTS],list(range(20261026311,20261026319)))
        self.assertEqual(s.CONTRASTS[-1][1:3],('adaptive_semantic_wait_temporal','adaptive_semantic_wait_spatial'))


class PublishedOriginalBoundaryTests(unittest.TestCase):
    def publication(self, root):
        parent=root/'parent';parent.mkdir()
        (parent/'final-report.json').write_text('{"fixed":"original"}')
        (parent/'repair-lineage-public.json').write_text('{"fixed":"lineage"}')
        summary=dict(provenance={'private_report_sha256':s.source.sha(parent/'final-report.json')})
        (root/'summary.json').write_text(json.dumps(summary))
        (root/'lineage.json').write_bytes((parent/'repair-lineage-public.json').read_bytes())
        (root/'bundle.json').write_text('{"scope":"original"}')
        frozen={n:(root/n).read_bytes() for n in ('summary.json','lineage.json','bundle.json')}
        return parent,frozen

    def check(self,root,parent,frozen):
        with patch.object(s,'ROOT',root),patch.object(s,'PUBLIC_SUMMARY',Path('summary.json')),patch.object(s,'PUBLIC_LINEAGE',Path('lineage.json')),patch.object(s,'PUBLIC_BUNDLE',Path('bundle.json')),patch.object(s,'reference',side_effect=ref),patch.object(s.subprocess,'check_output',side_effect=lambda cmd,**kw:frozen[cmd[2].split(':',1)[1]]):
            return s.authenticate_publication(parent)

    def test_original_report_bound_to_already_committed_public_summary(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve();parent,frozen=self.publication(root)
            self.assertEqual(set(self.check(root,parent,frozen)),{'summary.json','lineage.json','bundle.json'})
            (parent/'final-report.json').write_text('{"fixed":"changed"}')
            with self.assertRaisesRegex(ValueError,'published result'):self.check(root,parent,frozen)

    def test_modified_working_public_summary_cannot_rebind_changed_original(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve();parent,frozen=self.publication(root)
            (parent/'final-report.json').write_text('{"fixed":"changed"}')
            (root/'summary.json').write_text(json.dumps({'provenance':{'private_report_sha256':s.source.sha(parent/'final-report.json')}}))
            with self.assertRaisesRegex(ValueError,'committed bytes'):self.check(root,parent,frozen)

    def test_changed_original_repair_lineage_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve();parent,frozen=self.publication(root)
            (parent/'repair-lineage-public.json').write_text('{"fixed":"modified"}')
            with self.assertRaisesRegex(ValueError,'lineage differs'):self.check(root,parent,frozen)


class NativeMetadataTests(unittest.TestCase):
    def test_all_four_header_families_are_validated(self):
        for m in s.VARIANTS:
            with self.subTest(method=m['id']):s.validate_native(native(m),data(),s.variant_config(config(),m),m)

    def test_plain_tf_sf_cannot_claim_semantic_controller_fields(self):
        for m in s.VARIANTS[:2]:
            for field,value in [('semantic_secondary_strategy','temporal_first'),('release_trigger','policy_satisfied')]:
                result=native(m);result['parameters'][field]=value
                with self.assertRaises(ValueError):s.validate_native(result,data(),config(),m)

    def test_waiting_semantic_controller_cannot_silently_run_immediate_or_wrong_secondary(self):
        for m in s.VARIANTS[2:]:
            for field,value in [('release_trigger','policy_satisfied'),('semantic_secondary_strategy','unknown')]:
                result=native(m);result['parameters'][field]=value
                with self.assertRaises(ValueError):s.validate_native(result,data(),config(),m)

    def test_source_clock_bounds_strategy_and_conservation_mutations_rejected(self):
        m=s.VARIANTS[0]
        changes=[lambda r:r.update(mode='spatial_first'),lambda r:r['source'].update(sensor_id='other'),
                 lambda r:r['parameters'].update(progress_step_ms=100),lambda r:r['parameters'].update(coordination='common_window'),
                 lambda r:r['parameters'].update(max_window_ms=8000),lambda r:r['parameters'].update(min_depth=1),
                 lambda r:r.update(accounted_observation_contributions=0)]
        for change in changes:
            value=native(m);change(value)
            with self.assertRaises(ValueError):s.validate_native(value,data(),config(),m)

    def test_native_command_uses_registered_mode(self):
        for m in s.VARIANTS:
            command=s.primary.native_command(Path('binary'),Path('input'),Path('policy'),Path('output'),m)
            self.assertEqual(command[command.index('--mode')+1],m['strategy'])
            self.assertNotIn('--fixed-depth',command)

    def test_existing_native_attempt_cannot_be_retried(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();m=s.VARIANTS[0];(directory/(m['id']+'-attempt.json')).write_text('{}')
            with patch.object(s.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'no retry'):
                s.run_case(directory,directory/'input',config(),m,{'group_id':'g'},'IN',[],{})
            run.assert_not_called()

    def test_native_nonzero_exit_preserved_and_no_public_export(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();(directory/'AggregationReplay').write_bytes(b'binary');path=directory/'input.json';path.write_text('{}');m=s.VARIANTS[0]
            with patch.object(s.subprocess,'run',return_value=SimpleNamespace(returncode=7,stdout='',stderr='failed')),patch.object(s.semantic,'export_public') as export:
                with self.assertRaisesRegex(ValueError,'Native failed'):
                    s.run_case(directory,path,config(),m,{'group_id':'g'},'IN',[],{'native_wall_budget_s':1,'audit_max_cells':5})
                value=json.loads((directory/(m['id']+'-execution.json')).read_text())
                self.assertEqual(value['returncode'],7);export.assert_not_called()

    def test_native_timeout_preserved_and_not_given_public_success(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();(directory/'AggregationReplay').write_bytes(b'binary');path=directory/'input.json';path.write_text('{}');m=s.VARIANTS[0]
            with patch.object(s.subprocess,'run',side_effect=s.subprocess.TimeoutExpired('native',1)),patch.object(s.semantic,'export_public') as export:
                with self.assertRaisesRegex(ValueError,'Native failed'):
                    s.run_case(directory,path,config(),m,{'group_id':'g'},'IN',[],{'native_wall_budget_s':1,'audit_max_cells':5})
                self.assertEqual(json.loads((directory/(m['id']+'-execution.json')).read_text())['status'],'timeout');export.assert_not_called()


class PairAndStageBoundaryTests(unittest.TestCase):
    def pair(self,directory):
        for name in ('in.json','out.json','auxiliary.json'):(directory/name).write_text('{}')
        value=dict(group_id='g',split='train',auxiliary_sha256=s.source.sha(directory/'auxiliary.json'))
        (directory/'pair.json').write_text(json.dumps(value))
        return dict(split='train',files={n:ref(directory/n) for n in ('in.json','out.json','auxiliary.json','pair.json')})

    def test_pair_import_preserves_exact_inputs_target_auxiliary_and_role(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();imp=self.pair(directory)
            with patch.object(s,'authenticated',side_effect=auth):self.assertEqual(s.validate_pair_import(directory,imp)['split'],'train')
            (directory/'auxiliary.json').write_text('{"changed":true}')
            with patch.object(s,'authenticated',side_effect=auth),self.assertRaises(ValueError):s.validate_pair_import(directory,imp)

    def test_role_change_even_with_rehashed_pair_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();imp=self.pair(directory)
            value=json.loads((directory/'pair.json').read_text());value['split']='test';(directory/'pair.json').write_text(json.dumps(value));imp['files']['pair.json']=ref(directory/'pair.json')
            with patch.object(s,'authenticated',side_effect=auth),self.assertRaisesRegex(ValueError,'role'):
                s.validate_pair_import(directory,imp)

    def test_utility_run_cannot_follow_model_lock(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();(output/'models-lock.json').write_text('{}')
            with patch.object(s,'read_protocol',return_value=(output,{},{})),patch.object(s,'process_group') as process:
                with self.assertRaisesRegex(ValueError,'cannot follow'):s.run_utility(output)
                process.assert_not_called()

    def test_any_prior_fit_output_blocks_fitter_before_an_optimizer_call(self):
        for filename in s.FIT_OUTPUTS:
            with tempfile.TemporaryDirectory() as name:
                output=Path(name).resolve();(output/filename).write_text('{}')
                with patch.object(s,'read_protocol',return_value=(output,{},{})),patch.object(s.analysis,'_fit') as fit:
                    with self.assertRaisesRegex(ValueError,'No fitting retry'):s.fit_mia(output)
                    fit.assert_not_called()

    def test_fit_attempt_blocks_further_utility_generation(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();(output/'mia-fit-attempt.json').write_text('{}')
            with patch.object(s,'read_protocol',return_value=(output,{},{})),patch.object(s,'process_group') as process:
                with self.assertRaisesRegex(ValueError,'fitting attempt'):s.run_utility(output)
                process.assert_not_called()

    def test_fit_attempt_is_persisted_before_optimizer_and_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();(output/'protocol.json').write_text('{}')
            oldmethods=[{'id':m} for m in fixtures.METHODS];p={'original_methods':oldmethods}
            rows=all_rows();new=[r for r in rows if r['method_id'] in {m['id'] for m in s.VARIANTS}]
            utility=dict(schema=s.UTILITY_SCHEMA,mia_status='not_started',strategy_supplement={'protocol':ref(output/'protocol.json')},new_rows_sha256=s.analysis.digest(new))
            (output/'utility-report.json').write_text(json.dumps(utility))
            context={'manifest':{'groups':[{'group_id':g,'split':role} for role,groups in fixtures.GROUPS.items() for g in groups]}}
            def fail_optimizer(*args,**kwargs):
                attempt=json.loads((output/'mia-fit-attempt.json').read_text())
                self.assertEqual(attempt['new_fit_count'],8)
                self.assertEqual(attempt['test_rows_seen_by_fitter'],0)
                self.assertTrue(all(r['split']!='test' for r in args[0]))
                raise RuntimeError('synthetic optimizer interruption')
            with patch.object(s,'read_protocol',return_value=(output,p,context)),patch.object(s,'combined_rows_and_summaries',return_value=(rows,[])),patch.object(s,'reference',side_effect=ref),patch.object(s.analysis,'_fit',side_effect=fail_optimizer) as fit:
                with self.assertRaisesRegex(RuntimeError,'optimizer interruption'):s.fit_mia(output)
                self.assertTrue((output/'mia-fit-failed.json').is_file())
                self.assertEqual(fit.call_count,1)
                with self.assertRaisesRegex(ValueError,'No fitting retry'):s.fit_mia(output)
                self.assertEqual(fit.call_count,1)

    def test_incomplete_utility_stage_cannot_open_mia(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name)
            with patch.object(s,'read_protocol',return_value=(output,{},{})),patch.object(s.analysis,'_fit') as fit:
                with self.assertRaises((ValueError,OSError)):s.fit_mia(output)
                fit.assert_not_called()

    def test_interrupted_group_not_retried_or_silently_skipped(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();(output/'groups'/'g').mkdir(parents=True)
            ctx={'manifest':{'groups':[{'group_id':'g','split':'train'}]}}
            with patch.object(s,'read_protocol',return_value=(output,{},ctx)),patch.object(s,'process_group') as process:
                with self.assertRaisesRegex(ValueError,'Interrupted'):s.run_utility(output)
                process.assert_not_called()

    def test_utility_report_cannot_run_after_mia_lock(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();(output/'models-lock.json').write_text('{}')
            with patch.object(s,'read_protocol',return_value=(output,{},{})),self.assertRaisesRegex(ValueError,'precede MIA'):
                s.utility_report(output)


class CompleteCaseGateTests(unittest.TestCase):
    def family(self):
        groups=[];summaries=[];rows=[];imported={}
        prototype=fixtures.rows()[0]
        for index in range(72):
            role='train' if index<24 else 'calibration' if index<40 else 'test';gid='g'+str(index)
            groups.append(dict(group_id=gid,split=role));cases=[]
            imported[gid]=dict(split=role,files={'pair.json':{'path':'original','sha256':'sha'}})
            for m in s.VARIANTS:
                for label,world in ((1,'IN'),(0,'OUT')):
                    row=deepcopy(prototype);row.update(group_id=gid,split=role,world=world,label=label,method_id=m['id']);row['controls']['unprotected']=label;rows.append(row)
                    cases.append(dict(method_id=m['id'],world=world,status='verified',independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0)))
            summaries.append(dict(group_id=gid,split=role,status='verified',cases=cases,pair=dict(group_id=gid,split=role),rows={'sha256':'sha'}))
        return rows,summaries,dict(imported_groups=imported),dict(manifest={'groups':groups})

    def call(self,rows,summaries,p,context):
        def load_side(path):
            gid=path.parent.name
            return dict(schema=s.SIDECAR_SCHEMA,protocol_sha256='sha',original_pair=p['imported_groups'][gid]['files']['pair.json'],
                source_pair_hashes={n:'sha' for n in ('in.json','out.json','auxiliary.json','pair.json')},summary_sha256='sha',rows_sha256='sha')
        def pair(directory,imported):return dict(group_id=directory.name,split=imported['split'])
        with patch.object(s.primary,'collect',return_value=(rows,summaries)),patch.object(s.source,'load',side_effect=load_side),patch.object(s.source,'sha',return_value='sha'),patch.object(s,'validate_pair_import',side_effect=pair):
            return s.collect_new(Path('/synthetic'),p,context,require_complete=True)

    def test_full72_by4_by2_case_and_row_matrix_accepted(self):
        values=self.family();self.assertEqual(len(self.call(*values)[0]),576)

    def test_verified_summary_cannot_hide_failed_native_case(self):
        values=self.family();values[1][0]['cases'][0]['status']='failed'
        with self.assertRaisesRegex(ValueError,'All72'):self.call(*values)

    def test_missing_world_or_duplicate_case_cannot_preserve_nominal_count(self):
        values=self.family();values[1][0]['cases'][1]=deepcopy(values[1][0]['cases'][0])
        with self.assertRaisesRegex(ValueError,'matrix'):self.call(*values)

    def test_missing_row_cannot_hide_behind_complete_summary(self):
        values=self.family();values[0].pop()
        with self.assertRaisesRegex(ValueError,'All72'):self.call(*values)


class ModelPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=all_rows();cls.training=[r for r in cls.rows if r['split']!='test']
        cls.old=s.analysis.prepare_models([r for r in cls.training if r['method_id'] in fixtures.METHODS],expected_groups=fixtures.GROUPS,method_ids=fixtures.METHODS)
        cls.new={m['id']:{rep:s.analysis._fit([r for r in cls.training if r['method_id']==m['id']],lambda row,f=field:row[f],fixtures.GROUPS)
                              for rep,(field,_) in s.analysis.REPRESENTATIONS.items()} for m in s.VARIANTS}
        cls.methods=fixtures.METHODS+[m['id'] for m in s.VARIANTS]

    def test_derived_model_view_preserves_original_fits_controls_and_inputs(self):
        original=deepcopy(self.old);rows=deepcopy(self.training)
        result=s.combine_models(self.old,self.new,self.training,fixtures.GROUPS,self.methods)
        self.assertEqual(self.old,original);self.assertEqual(self.training,rows)
        self.assertEqual(result['controls'],original['controls'])
        for method in fixtures.METHODS:self.assertEqual(result['attacks'][method],original['attacks'][method])
        self.assertEqual(len(result['models']),12)
        self.assertEqual(result['training_calibration_rows'],48)
        self.assertEqual(s.analysis.validate_model_lock(result,self.training)['status'],'verified')

    def test_test_rows_forbidden_in_combined_fitting_view(self):
        with self.assertRaisesRegex(ValueError,'TEST rows'):
            s.combine_models(self.old,self.new,self.rows,fixtures.GROUPS,self.methods)

    def test_missing_or_replacement_new_model_family_rejected(self):
        missing=deepcopy(self.new);missing.pop(s.VARIANTS[0]['id'])
        with self.assertRaises(ValueError):s.combine_models(self.old,missing,self.training,fixtures.GROUPS,self.methods)
        replacement=deepcopy(self.new);replacement['adaptive_semantic_first']=replacement.pop(s.VARIANTS[0]['id'])
        with self.assertRaises(ValueError):s.combine_models(self.old,replacement,self.training,fixtures.GROUPS,self.methods)

    def test_changed_duplicate_controls_cannot_enter_derived_view(self):
        bad=deepcopy(self.training);next(r for r in bad if r['method_id']==s.VARIANTS[0]['id'])['auxiliary_features'][0]+=.1
        with self.assertRaisesRegex(ValueError,'Method-dependent'):
            s.combine_models(self.old,self.new,bad,fixtures.GROUPS,self.methods)

    def test_original_primary_and_controls_reproduce_in_synthetic_extension(self):
        combined=s.combine_models(self.old,self.new,self.training,fixtures.GROUPS,self.methods)
        old_report=s.analysis.evaluate_models(self.old,[r for r in self.rows if r['method_id'] in fixtures.METHODS])
        report=s.analysis.evaluate_models(combined,self.rows)
        self.assertEqual(report['controls'],old_report['controls'])
        self.assertEqual(report['primary_contrast'],old_report['primary_contrast'])
        for m in fixtures.METHODS:self.assertEqual(report['attacks'][m],old_report['attacks'][m])
        self.assertEqual(report['interpretation_gate'],'controls_pass')
        extra=s.exploratory_contrasts(report)
        self.assertEqual(len(extra),8)
        self.assertTrue(all(v['representations']['semantic111']['independent_groups']==2 for v in extra.values()))

    def test_model_lock_role_metadata_is_enforced(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();model=s.combine_models(self.old,self.new,self.training,fixtures.GROUPS,self.methods)
            files={'protocol.json':{},'utility-report.json':{},'mia-fit-attempt.json':{},'models.json':model,'train-cal-rows.json':self.training}
            for n,v in files.items():(output/n).write_text(json.dumps(v))
            attempt=dict(schema='ump.urban-strategy-supplement-fit-attempt.v1',status='attempted',protocol=ref(output/'protocol.json'),
                utility_gate=ref(output/'utility-report.json'),new_fit_count=8,test_rows_seen_by_fitter=0,model_parameters=deepcopy(s.analysis.MODEL_PARAMETERS),
                training_rows_sha256=s.analysis.digest(s.analysis._checked_rows(self.training,fixtures.GROUPS,self.methods,allow_test=False)))
            (output/'mia-fit-attempt.json').write_text(json.dumps(attempt))
            parent_refs={'models':{'sha256':'old-models'},'models_lock':{'sha256':'old-lock'}}
            lock=dict(schema=s.LOCK_SCHEMA,status='locked_before_supplement_TEST_scoring',protocol=ref(output/'protocol.json'),utility_gate=ref(output/'utility-report.json'),
                new_fit_count=8,test_rows_seen_by_fitter=0,training_groups=24,calibration_groups=16,test_sources_already_seen=True,
                fit_attempt=ref(output/'mia-fit-attempt.json'),original_models=parent_refs['models'],original_model_lock=parent_refs['models_lock'],
                original_model_refits=0,original_threshold_retunes=0,models=ref(output/'models.json'),data=ref(output/'train-cal-rows.json'))
            def write(v):(output/'models-lock.json').write_text(json.dumps(v))
            write(lock)
            with patch.object(s,'reference',side_effect=ref),patch.object(s,'authenticated',side_effect=auth):
                self.assertEqual(s.authenticate_model_lock(output,{'parent_references':parent_refs},{'models':self.old},self.training)['controls'],self.old['controls'])
                for key,value in [('training_groups',23),('calibration_groups',15),('test_sources_already_seen',False)]:
                    bad=deepcopy(lock);bad[key]=value;write(bad)
                    with self.assertRaisesRegex(ValueError,'scope differs'):s.authenticate_model_lock(output,{'parent_references':parent_refs},{'models':self.old},self.training)

    def test_only_eight_new_fits_are_called_after_utility_and_old_controls_reused(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();(output/'protocol.json').write_text('{}')
            oldmethods=[{'id':m} for m in fixtures.METHODS]
            parents={'models':{'sha256':'old-models'},'models_lock':{'sha256':'old-lock'}}
            p=dict(original_methods=oldmethods,parent_references=parents,scope='synthetic exploratory fixture')
            context={'manifest':{'groups':[{'group_id':g,'split':role} for role,groups in fixtures.GROUPS.items() for g in groups]},'models':self.old}
            new=[r for r in self.rows if r['method_id'] in {m['id'] for m in s.VARIANTS}]
            utility=dict(schema=s.UTILITY_SCHEMA,mia_status='not_started',strategy_supplement={'protocol':ref(output/'protocol.json')},new_rows_sha256=s.analysis.digest(new))
            (output/'utility-report.json').write_text(json.dumps(utility))
            original_fit=s.analysis._fit
            def fit_only_new(rows,*args,**kwargs):
                self.assertTrue(all(r['split'] in ('train','calibration') and r['method_id'] in {m['id'] for m in s.VARIANTS} for r in rows))
                self.assertTrue((output/'mia-fit-attempt.json').is_file())
                return original_fit(rows,*args,**kwargs)
            with patch.object(s,'read_protocol',return_value=(output,p,context)),patch.object(s,'combined_rows_and_summaries',return_value=(self.rows,[])),patch.object(s,'reference',side_effect=ref),patch.object(s.analysis,'_fit',side_effect=fit_only_new) as fit:
                lock=s.fit_mia(output)
            self.assertEqual(fit.call_count,8)
            self.assertEqual(lock['new_fit_count'],8)
            self.assertEqual(json.loads((output/'models.json').read_text())['controls'],self.old['controls'])

    def test_modified_old_threshold_detected_by_frozen_model_validation(self):
        combined=s.combine_models(self.old,self.new,self.training,fixtures.GROUPS,self.methods)
        combined['attacks']['adaptive_semantic_first']['semantic111']['calibration']['threshold']+=.01
        with self.assertRaisesRegex(ValueError,'bundle changed'):s.analysis.evaluate_models(combined,self.rows)


class FinalParentValidationTests(unittest.TestCase):
    def test_final_stage_revalidates_all_raw_and_original_archives_before_assessment(self):
        context={'verified':'full'};p=dict(parent_output='/synthetic-parent',parent_references={'x':'pinned'},imported_groups={'x':'same'})
        with patch.object(s,'parent_context',return_value=context) as verify,patch.object(s,'parent_refs',return_value={'x':'pinned'}),patch.object(s,'import_groups',return_value={'x':'same'}):
            self.assertIs(s.fully_verified_parent(p),context)
            verify.assert_called_once_with(Path('/synthetic-parent'),verify_archives=True,verify_raw=True)

    def test_final_full_validation_cannot_rebind_different_original_imports(self):
        p=dict(parent_output='/synthetic-parent',parent_references={'x':'pinned'},imported_groups={'x':'same'})
        with patch.object(s,'parent_context',return_value={}),patch.object(s,'parent_refs',return_value={'x':'changed'}),patch.object(s,'import_groups',return_value={'x':'same'}):
            with self.assertRaisesRegex(ValueError,'differs from frozen imports'):s.fully_verified_parent(p)


class RuntimeSummaryTests(unittest.TestCase):
    def test_percentiles_are_linear_interpolated_without_missing_zero_fill(self):
        self.assertEqual(s.percentile([10,20],.5),15)
        self.assertAlmostEqual(s.percentile([10,20],.95),19.5)
        with self.assertRaises(ValueError):s.percentile([],.5)


if __name__=='__main__':unittest.main()
