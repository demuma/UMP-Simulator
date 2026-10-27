"""Synthetic semantic-ablation boundaries; never study/native execution."""
from copy import deepcopy
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_urban_semantic_ablation as s
import test_run_urban_strategy_supplement as prior_fixtures


def config():return prior_fixtures.config()
def data():return prior_fixtures.data()
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
def auth(value):
    p=Path(value['path']);s.require(ref(p)==value,'Synthetic reference changed');return p


def native(method):
    q=dict(progress_step_ms=50,progress_origin_ms=0,semantic_generalization='exact_only')
    if method['kind']=='native_fixed':q.update(coordination='common_window',fixed_depth=2,window_ms=method['window_ms']);mode='fixed'
    else:
        q.update(coordination='cell_local',window_ms=400,max_window_ms=4000,extension_step_ms=100,min_depth=2);mode=method['strategy']
        if mode=='semantic_first':q.update(semantic_secondary_strategy=method['secondary_strategy'],release_trigger=method['release_trigger'])
    return dict(schema='ump.replay-result.v1',mode=mode,parameters=q,source={k:data()[k] for k in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms','application_id')},input_observation_contributions=1,accounted_observation_contributions=1)


def expected():return {split:[split+'-'+str(i) for i in range(count)] for split,count in (('train',24),('calibration',16),('test',32))}
def rows(include_test=True):
    result=[]
    for split,groups in expected().items():
        if not include_test and split=='test':continue
        for group in groups:
            for m in s.METHODS:
                for label,world in ((1,'IN'),(0,'OUT')):
                    result.append(dict(group_id=group,split=split,method_id=m['id'],world=world,label=label,features=[0.]*111,scalar_features=[0.]*31,auxiliary_features=[0.]*8,
                        controls=dict(prior_only=.5,unprotected=label,no_output_features=[0.]*111),utility={}))
    return result


class ConfigurationTests(unittest.TestCase):
    def test_seven_pairs_and_three_dependencies_are_explicit(self):
        self.assertEqual(len(s.METHODS),14);self.assertEqual(len(s.NATIVE_METHODS),9);self.assertEqual(len(s.AUXILIARY_METHODS),3)
        self.assertEqual([m['window_ms'] for m in s.AUXILIARY_METHODS],[1000,2000,4000])
        self.assertEqual(tuple(m['on_method_id'] for m in s.OFF_METHODS),s.ON_IDS)
        self.assertTrue(all(m['id']==s.off_id(m['on_method_id']) for m in s.OFF_METHODS))
        self.assertTrue(all(m['grid_side_m']==20 for m in s.AUXILIARY_METHODS))
    def test_only_registered_execution_preferences_change(self):
        base=config();copy=deepcopy(base)
        for m in s.METHODS+s.AUXILIARY_METHODS:
            variant=s.variant_config(base,m);self.assertEqual(s.previous.hard_policy(variant),s.previous.hard_policy(base))
            self.assertNotIn('semantic_generalization',variant)
            if m['kind']!='native_adaptive':self.assertEqual(variant,base)
        self.assertEqual(base,copy)
    def test_tampered_catalog_is_rejected(self):
        m=deepcopy(s.OFF_METHODS[2]);m['strategy']='unknown'
        with self.assertRaises(ValueError):s.variant_config(config(),m)
    def test_no_semantic_secondary_fields_for_plain_strategies(self):
        for m in s.OFF_METHODS[2:4]:self.assertNotIn('semantic_secondary_strategy',s.variant_config(config(),m)['policy_tree']['execution'])
    def test_seeds_are_off_minus_on_and_fixed(self):
        self.assertEqual([x[3] for x in s.CONTRASTS],list(range(20261027401,20261027408)))
        self.assertEqual([(x[1],x[2]) for x in s.CONTRASTS],[(s.off_id(name),name) for name in s.ON_IDS])


class HistoricalBridgeTests(unittest.TestCase):
    def history(self,root):
        root=root.resolve()
        archive=root/'archive';archive.mkdir();cpp=root/'algorithm.cpp';cpp.write_text('old native code');py=root/'primitive.py';py.write_text('old Python code')
        files={};versions={}
        for p in (cpp,py):
            h=s.source.sha(p);saved=archive/h;saved.write_bytes(p.read_bytes());entry=dict(archived_path=str(saved),sha256=h,bytes=p.stat().st_size);files[str(p)]=entry;versions[str(p)]={h:entry}
        return dict(_directory=str(archive),files=files,historical_expected_versions=versions),cpp,py
    def test_historical_cpp_is_authenticated_from_archive_after_current_cpp_changes(self):
        with tempfile.TemporaryDirectory() as name:
            h,cpp,_=self.history(Path(name));cpp.write_text('new exact-only native code');s.validate_historical_code(h)
    def test_imported_python_cannot_silently_change(self):
        with tempfile.TemporaryDirectory() as name:
            h,_,py=self.history(Path(name));py.write_text('changed primitive')
            with self.assertRaisesRegex(ValueError,'Python primitive'):s.validate_historical_code(h)
    def test_archived_historical_bytes_cannot_change(self):
        with tempfile.TemporaryDirectory() as name:
            h,cpp,_=self.history(Path(name));entry=h['files'][str(cpp)];Path(entry['archived_path']).write_text('forged')
            with self.assertRaisesRegex(ValueError,'archive changed'):s.validate_historical_code(h)
    def test_wrong_historical_expected_version_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            h,cpp,_=self.history(Path(name))
            with self.assertRaisesRegex(ValueError,'Missing exact historical'):s._historical_version(h,str(cpp),'0'*64)
    def test_escaping_archive_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            h,cpp,_=self.history(Path(name));digest=h['files'][str(cpp)]['sha256'];h['historical_expected_versions'][str(cpp)][digest]['archived_path']=str(cpp)
            with self.assertRaisesRegex(ValueError,'archive changed'):s._historical_version(h,str(cpp),digest)


class HistoricalCaptureBindingTests(unittest.TestCase):
    def fixture(self,root):
        root=root.resolve();replay=root/'replay';scene=root/'scene';replay.mkdir();scene.mkdir()
        (scene/'config.yaml').write_text('fixed configuration')
        (replay/'observations.json').write_text('{"fixed":"observations"}')
        files={'private/config.yaml':ref(scene/'config.yaml')['sha256'],'observations.json':ref(replay/'observations.json')['sha256']}
        (replay/'capture-proof.json').write_text(json.dumps({'files_sha256':files,'status':'verified'}))
        frozen=dict(capture_proof=ref(replay/'capture-proof.json'),config=ref(scene/'config.yaml'),capture_files_sha256=files)
        row=dict(group_id='group',split='train',replay_directory=str(replay),scene_directory=str(scene))
        saved=dict(row,capture_proof_sha256=frozen['capture_proof']['sha256'],observations_sha256=files['observations.json'],files_sha256={'replay/capture-proof.json':frozen['capture_proof']['sha256'],'scene/config.yaml':files['private/config.yaml'],'replay/observations.json':files['observations.json']})
        return row,saved,frozen
    @patch.object(s,'authenticated',side_effect=auth)
    def test_unchanged_proof_configuration_and_observations_are_bound(self,*mocks):
        with tempfile.TemporaryDirectory() as name:
            row,saved,frozen=self.fixture(Path(name));proof=s.authenticated_historical_capture(row,saved,frozen)
            self.assertEqual(proof['files_sha256'],frozen['capture_files_sha256'])
    @patch.object(s,'authenticated',side_effect=auth)
    def test_changed_proof_cannot_self_authorize_a_new_artifact_map(self,*mocks):
        with tempfile.TemporaryDirectory() as name:
            row,saved,frozen=self.fixture(Path(name));proof=Path(frozen['capture_proof']['path']);value=json.loads(proof.read_text());value['files_sha256']['observations.json']='0'*64;proof.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'reference changed'):s.authenticated_historical_capture(row,saved,frozen)
    @patch.object(s,'authenticated',side_effect=auth)
    def test_repointed_proof_rejected_even_with_identical_bytes_and_digest(self,*mocks):
        with tempfile.TemporaryDirectory() as name:
            row,saved,frozen=self.fixture(Path(name));original=Path(frozen['capture_proof']['path']);other=original.with_name('other-proof.json');other.write_bytes(original.read_bytes());frozen['capture_proof']=ref(other)
            with self.assertRaisesRegex(ValueError,'capture-proof binding'):s.authenticated_historical_capture(row,saved,frozen)
    @patch.object(s,'authenticated',side_effect=auth)
    def test_changed_configuration_or_observations_rejected(self,*mocks):
        for target in ('config','observations'):
            with tempfile.TemporaryDirectory() as name:
                row,saved,frozen=self.fixture(Path(name));path=Path(frozen['config']['path']) if target=='config' else Path(row['replay_directory'])/'observations.json';path.write_text('changed')
                with self.assertRaisesRegex(ValueError,'reference changed'):s.authenticated_historical_capture(row,saved,frozen)
    @patch.object(s,'authenticated',side_effect=auth)
    def test_repointed_configuration_or_saved_observation_digest_rejected(self,*mocks):
        with tempfile.TemporaryDirectory() as name:
            row,saved,frozen=self.fixture(Path(name));cfg=Path(frozen['config']['path']);other=cfg.with_name('other.yaml');other.write_bytes(cfg.read_bytes());altered=deepcopy(frozen);altered['config']=ref(other)
            with self.assertRaisesRegex(ValueError,'configuration binding'):s.authenticated_historical_capture(row,saved,altered)
            saved['observations_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'observations binding'):s.authenticated_historical_capture(row,saved,frozen)


class ImportedCaseMatrixTests(unittest.TestCase):
    def cases(self):return [dict(method_id=m['id'],world=w,status='verified',role='authenticated_historical_on') for m in s.ON_METHODS for w in ('IN','OUT')]
    def test_all_fourteen_imported_on_cases_required(self):s.validate_imported_cases(self.cases())
    def test_duplicate_missing_failed_or_wrong_role_imports_rejected(self):
        for mutate in (lambda v:v.pop(),lambda v:v.__setitem__(0,deepcopy(v[1])),lambda v:v[0].update(status='failed'),lambda v:v[0].update(role='headline')):
            cases=self.cases();mutate(cases)
            with self.assertRaises(ValueError):s.validate_imported_cases(cases)
    def test_arbitrary_self_described_history_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name).resolve()/'history.json';p.write_text(json.dumps({'schema':s.HISTORY_SCHEMA,'status':'verified'}))
            with self.assertRaisesRegex(ValueError,'trusted prechange'):s.authenticate_history(p)


class NativeTests(unittest.TestCase):
    def test_all_nine_native_headers_are_authenticated(self):
        for method in s.NATIVE_METHODS:s.validate_native(native(method),data(),config(),method)
    def test_enabled_or_missing_flag_cannot_be_labeled_off(self):
        for value in ('enabled',None):
            result=native(s.NATIVE_METHODS[0]);result['parameters']['semantic_generalization']=value
            with self.assertRaisesRegex(ValueError,'generalization'):s.validate_native(result,data(),config(),s.NATIVE_METHODS[0])
    def test_temporal_and_spatial_reject_semantic_only_metadata(self):
        for m in s.OFF_METHODS[2:4]:
            result=native(m);result['parameters']['release_trigger']='policy_satisfied'
            with self.assertRaisesRegex(ValueError,'semantic-only'):s.validate_native(result,data(),config(),m)
    def test_semantic_wait_priority_cannot_silently_be_immediate(self):
        m=s.OFF_METHODS[-1];result=native(m);result['parameters']['release_trigger']='policy_satisfied'
        with self.assertRaisesRegex(ValueError,'strategy metadata'):s.validate_native(result,data(),config(),m)
    def test_clock_source_bounds_accounting_mutations_rejected(self):
        m=s.OFF_METHODS[2]
        mutations=(lambda r:r['parameters'].update(progress_step_ms=100),lambda r:r['source'].update(sensor_id='other'),lambda r:r['parameters'].update(min_depth=1),lambda r:r.update(accounted_observation_contributions=0))
        for change in mutations:
            result=native(m);change(result)
            with self.assertRaises(ValueError):s.validate_native(result,data(),config(),m)
    def test_fixed_and_auxiliary_audits_project_common_window_without_policy_mutation(self):
        base=config();before=deepcopy(base)
        for method in (s.OFF_METHODS[0],*s.AUXILIARY_METHODS):
            result=native(method)
            with patch.object(s.primary.independent,'audit',return_value={'status':'verified'}) as audit:
                s.audit_native(data(),base,result,max_cells=12)
            args,kwargs=audit.call_args
            self.assertEqual(args[1]['temporal_adaptation']['coordination'],'common_window')
            self.assertEqual(kwargs['max_cells'],12)
            self.assertEqual(base,before)
            projected=deepcopy(args[1]);projected['temporal_adaptation']['coordination']='cell_local'
            self.assertEqual(projected,base)

    def test_existing_attempt_is_never_retried(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name);m=s.NATIVE_METHODS[0];(directory/(m['id']+'-attempt.json')).write_text('{}')
            with patch.object(s.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'retry'):
                s.run_case(directory,directory/'input',config(),m,dict(group_id='g'),'IN',[],{})
            run.assert_not_called()
    def test_recipient_digest_ignores_only_release_id(self):
        p=dict(releases=[dict(release_id='a',end_ms=400,cells=[dict(cell_id=3)])]);q=deepcopy(p);q['releases'][0]['release_id']='b'
        self.assertEqual(s.recipient_digest(p),s.recipient_digest(q));q['releases'][0]['end_ms']=500
        self.assertNotEqual(s.recipient_digest(p),s.recipient_digest(q))


class RegionalSingleWriterTests(unittest.TestCase):
    def test_composer_returns_receipt_for_exactly_one_caller_write(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();records={}
            for file in ('input.json','AggregationReplay'):(directory/file).write_text('{}')
            for ms in (400,1000,2000,4000):
                key=s.off_id('fixed20_'+str(ms)+'ms')
                for suffix in ('-policy.json','.json','-audit.json'):(directory/(key+suffix)).write_text('{}')
                records[key]={'status':'verified','independent_audit':{'status':'verified','scalar_valid':True,'published_policy_violations':0}}
            public={'releases':[]};audit={'stats':{}};value={'coverage':{},'sampling_period_ms':100,'end_ms':300000}
            with patch.object(s.primary.regional,'compose_family',return_value={'public_transcript':public,'private_audit':audit}),patch.object(s.primary.pilot,'public_contract'),patch.object(s,'exact_only_evidence',return_value={'status':'verified'}),patch.object(s.primary,'row_for',return_value={'utility':{}}),patch.object(s,'attach_queries'):
                record,row=s.compose(directory,config(),{'group_id':'g'},'IN',[],records,value,None)
            receipt=directory/(s.off_id('regional_static20')+'-receipt.json')
            self.assertFalse(receipt.exists())
            s.primary.write(receipt,record)
            self.assertEqual(json.loads(receipt.read_text()),record)


class ExactTerminalTests(unittest.TestCase):
    def fixtures(self):
        cfg={'semantic_taxonomy':dict(id='t',nodes=[dict(id='root',loss=1),dict(id='leaf',parent='root',loss=0,input_types=['Adult'])])}
        public=dict(releases=[dict(cells=[dict(semantic=dict(categories=[dict(category_id='leaf')],semantic_mean_loss=0,semantic_max_loss=0))])])
        return public,cfg
    def test_terminal_only_zero_loss_evidence_passes(self):
        p,c=self.fixtures();self.assertEqual(s.exact_only_evidence(p,c)['terminal_bins'],1)
    def test_generalized_category_rejected_even_with_claimed_zero_loss(self):
        p,c=self.fixtures();p['releases'][0]['cells'][0]['semantic']['categories'][0]['category_id']='root'
        with self.assertRaisesRegex(ValueError,'generalized'):s.exact_only_evidence(p,c)
    def test_nonzero_loss_rejected_even_with_terminal_label(self):
        p,c=self.fixtures();p['releases'][0]['cells'][0]['semantic']['semantic_mean_loss']=.5
        with self.assertRaisesRegex(ValueError,'semantic loss'):s.exact_only_evidence(p,c)
    def test_empty_output_is_valid_but_not_semantic_utility_success(self):
        _,c=self.fixtures();e=s.exact_only_evidence({'releases':[]},c);self.assertEqual(e['published_cells'],0);self.assertEqual(e['terminal_bins'],0)


class ImportedRowsTests(unittest.TestCase):
    def test_derived_query_diagnostics_do_not_allow_original_feature_control_changes(self):
        original=rows(False)[0];context={'all_historical_rows':[original]};r=deepcopy(original);r['imported_row_sha256']=s.analysis.digest(original);r['recipient_digest_no_release_ids']='sha';r['utility']['aligned_semantic_queries']={'exact':{},'estimate':{}}
        s.validate_imported_row(r,context)
        for mutate in (lambda x:x['features'].__setitem__(0,1),lambda x:x['controls'].update(unprotected=.5),lambda x:x.update(split='test')):
            altered=deepcopy(r);mutate(altered)
            with self.assertRaises(ValueError):s.validate_imported_row(altered,context)
    def test_duplicate_diagnostics_compare_every_source_world_without_dedup_execution(self):
        records=[]
        for i in range(72):
            for world in ('IN','OUT'):
                for m in s.OFF_METHODS:
                    records.append(dict(group_id=str(i),world=world,method_id=m['id'],recipient_digest_no_release_ids='same'))
        report=s.duplicate_check(records);self.assertEqual(len(report['by_pair']),10);self.assertTrue(all(v['compared_streams']==144 and v['all_equal'] for v in report['by_pair'].values()))
        next(r for r in records if r['method_id']==s.OFF_METHODS[2]['id'])['recipient_digest_no_release_ids']='different'
        changed=s.duplicate_check(records);self.assertTrue(any(v['equal_streams']==143 for v in changed['by_pair'].values()))


class QueryRoleTests(unittest.TestCase):
    def test_all_2016_headline_rows_get_queries_and_432_auxiliary_rows_do_not(self):
        headline=[];auxiliary=[]
        def attach(row,*args):
            row['utility']['aligned_semantic_queries']={'exact':{},'estimate':{}}
            return row
        with patch.object(s,'attach_queries',side_effect=attach) as evaluate:
            for group in range(72):
                for world in ('IN','OUT'):
                    for method in s.METHODS+s.AUXILIARY_METHODS:
                        row={'utility':{},'method_id':method['id'],'group_id':str(group),'world':world}
                        result=s.attach_case_queries(row,{},None,{},None,method)
                        (auxiliary if method in s.AUXILIARY_METHODS else headline).append(result)
        self.assertEqual(evaluate.call_count,2016)
        self.assertEqual(len(headline),2016);self.assertEqual(len(auxiliary),432)
        self.assertTrue(all('aligned_semantic_queries' in r['utility'] for r in headline))
        self.assertTrue(all('aligned_semantic_queries' not in r['utility'] for r in auxiliary))


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training=rows(False);cls.full=rows();cls.expected=expected();cls.original=s.analysis.prepare_models([r for r in cls.training if r['method_id'] in s.ON_IDS],expected_groups=cls.expected,method_ids=list(s.ON_IDS))
        cls.new={s.off_id(name):deepcopy(cls.original['attacks'][name]) for name in s.ON_IDS}
    def test_balanced_constant_features_converge_at_iteration_one_and_score_auc_half(self):
        for family in self.original['attacks'].values():
            for fitted in family.values():
                self.assertEqual(fitted['status'],'locked');self.assertTrue(fitted['model']['converged'])
                self.assertEqual(fitted['model']['iterations'],1)
        combined=s.combine_models(self.original,self.new,self.training,self.expected)
        result=s.analysis.evaluate_models(combined,self.full)
        for family in result['attacks'].values():
            for assessed in family.values():
                self.assertEqual(assessed['status'],'evaluated')
                self.assertEqual(assessed['metrics']['roc_auc'],.5)

    def test_combined_view_has_28_objects_and_original_controls_unchanged(self):
        before=deepcopy(self.original);result=s.combine_models(self.original,self.new,self.training,self.expected)
        self.assertEqual(len(result['models']),28);self.assertEqual(result['training_calibration_rows'],1120);self.assertEqual(result['controls'],before['controls']);self.assertEqual(self.original,before)
        for name in s.ON_IDS:self.assertEqual(result['attacks'][name],before['attacks'][name])
    def test_test_rows_cannot_enter_combined_fitting_view(self):
        with self.assertRaisesRegex(ValueError,'TEST rows'):s.combine_models(self.original,self.new,self.full,self.expected)
    def test_missing_or_replacement_off_attack_families_rejected(self):
        altered=deepcopy(self.new);altered.pop(next(iter(altered)))
        with self.assertRaises(ValueError):s.combine_models(self.original,altered,self.training,self.expected)
    def test_changed_duplicate_source_controls_rejected(self):
        changed=deepcopy(self.training);changed[-1]['auxiliary_features'][0]=.1
        with self.assertRaisesRegex(ValueError,'Method-dependent'):s.combine_models(self.original,self.new,changed,self.expected)
    def test_on_attacks_controls_and_original_primary_reproduce(self):
        models=s.combine_models(self.original,self.new,self.training,self.expected);old=s.analysis.evaluate_models(self.original,[r for r in self.full if r['method_id'] in s.ON_IDS]);new=s.analysis.evaluate_models(models,self.full)
        self.assertEqual(old['controls'],new['controls']);self.assertEqual(old['primary_contrast'],new['primary_contrast'])
        for name in s.ON_IDS:self.assertEqual(old['attacks'][name],new['attacks'][name])
    def test_any_fit_attempt_blocks_even_before_native_or_optimizer_work(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'mia-fit-attempt.json').write_text('{}')
            with patch.object(s,'read_protocol',return_value=(root,{},{})),patch.object(s.analysis,'_fit') as fit,self.assertRaisesRegex(ValueError,'retry'):s.fit_mia(root)
            fit.assert_not_called()
    @patch.object(s,'reference',side_effect=ref)
    @patch.object(s,'authenticated',side_effect=auth)
    def test_fourteen_fit_calls_use_only_train_cal_after_persistent_attempt(self,*mocks):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve();(root/'protocol.json').write_text('{}')
            manifest={'groups':[dict(group_id=g,split=split) for split,groups in self.expected.items() for g in groups]}
            context=dict(manifest=manifest,models=self.original,history={'bound_anchors':{'supplement_models':{'path':'old-model','sha256':'old-model-sha'},'supplement_model_lock':{'path':'old-lock','sha256':'old-lock-sha'}}})
            gate=dict(schema=s.UTILITY_SCHEMA,mia_status='not_started',semantic_ablation={'protocol':ref(root/'protocol.json')},all_rows_sha256=s.analysis.digest(s.analysis._checked_rows(self.full,self.expected,[m['id'] for m in s.METHODS],allow_test=True)),auxiliary_rows_sha256=s.analysis.digest([]))
            (root/'utility-report.json').write_text(json.dumps(gate))
            observed=[]
            def fitting(selected,vector,expected_groups):
                self.assertTrue((root/'mia-fit-attempt.json').is_file())
                self.assertEqual({r['split'] for r in selected},{'train','calibration'})
                self.assertEqual(len(selected),80)
                self.assertTrue(all(r['method_id'].endswith('_exact_only') for r in selected))
                observed.append(selected[0]['method_id'])
                rep='semantic111' if len(vector(selected[0]))==111 else 'scalar31'
                return deepcopy(self.original['attacks'][selected[0]['method_id'][:-len('_exact_only')]][rep])
            with patch.object(s,'read_protocol',return_value=(root,{'scope':'synthetic'},context)),patch.object(s,'collect',return_value=(self.full,[],[])),patch.object(s.analysis,'_fit',side_effect=fitting):
                lock=s.fit_mia(root)
            self.assertEqual(len(observed),14);self.assertEqual(Counter(observed),Counter({m['id']:2 for m in s.OFF_METHODS}))
            self.assertEqual(lock['new_fit_count'],14)
            result=s.authenticate_model_lock(root,{},context,self.training)
            self.assertEqual(result['controls'],self.original['controls'])
            lock['training_groups']=23;(root/'models-lock.json').write_text(json.dumps(lock))
            with self.assertRaisesRegex(ValueError,'scope differs'):s.authenticate_model_lock(root,{},context,self.training)

    def test_utility_cannot_run_after_fit_attempt(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'mia-fit-attempt.json').write_text('{}')
            with patch.object(s,'read_protocol',return_value=(root,{},{})),patch.object(s,'process_group') as run,self.assertRaisesRegex(ValueError,'fitting attempt'):s.run_utility(root)
            run.assert_not_called()


if __name__=='__main__':unittest.main()
