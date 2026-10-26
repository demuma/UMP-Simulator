"""Synthetic/mocked orchestration tests; no native, recorded model or TEST jobs."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import run_urban_track_window_primary as runner


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(runner.primary.fixture.encoded(value))


def data():
    coverage=dict(x=0,y=0,width=80,height=80,leaf_depth=6)
    return dict(schema='ump.observation-replay.v1',run_id='synthetic-window',sensor_id='synthetic-sensor',
        coverage=coverage,sampling_period_ms=100,end_ms=300000,
        batches=[dict(sequence=i,observed_at_ms=i*100,status='measured',observations=(
            [dict(id='observed-active',type='Adult Pedestrian',x=1.,y=2.,cell_id=runner.primary.fixture.cell_id(1.,2.,coverage))]
            if i in (1,2999) else [])) for i in range(1,3000)])


def manifest():
    groups=[]
    for role,count in (('train',24),('calibration',16),('test',32)):
        for index in range(count):
            k=len(groups)+1
            groups.append(dict(group_id=f'unit-window-{role}-{index:03}',split=role,
                seeds=dict(source_generation=k,target_selection=k+100,auxiliary_selection=k+200),target_slots=['target-00']))
    return dict(groups=groups,design=dict(study_id='unchanged-dataset',master_seed=123,
        group_counts=dict(train=24,calibration=16,test=32),methods=[dict(id='method-'+str(i)) for i in range(11)],
        generator={'evidence_files':[]},targets_per_recording=1,conditions=[{'id':'unchanged-policy'}],
        analysis_protocol={'statistics':'unchanged'},resource_limits={'caps':'unchanged'},
        attack_protocol={'secret':'Original complete-episode unit','auxiliary':{'acquisition':'Original full episode','fraction':.25},
                         'model':{'l2':.1,'max_iterations':500},'availability_model':'final_snapshot_at_horizon'}))


class PairTests(unittest.TestCase):
    def test_window_selector_preserves_exact_arithmetic_and_renames_scope(self):
        raw=data();before=deepcopy(raw);g=manifest()['groups'][0]
        expected=runner.primary.select_pair(raw,'a'*64,g)
        absent,knowledge,selection=runner.select_window_pair(raw,'a'*64,g)
        self.assertEqual((absent,knowledge),expected[:2]);self.assertEqual(raw,before)
        self.assertEqual(selection['target_id'],'observed-active')
        self.assertEqual(selection['eligible_observed_tracks'],1)
        self.assertNotIn('eligible_episodes',selection)
        self.assertEqual(selection['source_validation_profile'],runner.PROFILE)
        self.assertEqual(selection['target_observations'],2)
        self.assertEqual(len(knowledge),1)
        self.assertEqual(len(absent['batches']),2999)
        self.assertFalse(any(b['observations'] for b in absent['batches']))

    def test_wrong_horizon_is_rejected(self):
        raw=data();raw['end_ms']=1000
        with self.assertRaisesRegex(ValueError,'horizon'):
            runner.select_window_pair(raw,'a'*64,manifest()['groups'][0])

    def test_missing_explicit_hook_is_rejected_without_monkeypatching(self):
        def old_process(a,b,c,d,e):pass
        with mock.patch.object(runner.primary,'process_group',old_process):
            with self.assertRaisesRegex(ValueError,'pair_selector'):
                runner.require_pair_injection()


class WindowAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.results=self.root/'results';self.results.mkdir()
        self.freeze=self.results/'dataset';self.freeze.mkdir()
        self.src=self.results/'window-sources';self.src.mkdir()
        self.output=self.results/'window-study';self.output.mkdir();(self.output/'groups').mkdir()
        patch=mock.patch.object(runner,'ROOT',self.root);patch.start();self.addCleanup(patch.stop)
        self.m=manifest();dump(self.freeze/'manifest.json',self.m);dump(self.freeze/'policy-local400.json',{})
        self.dataset_sha=runner.primary.source.sha(self.freeze/'manifest.json')
        contract=self.root/runner.CONTRACT_PATH;contract.parent.mkdir(parents=True);contract.write_text('Synthetic immutable contract')
        self.ledger=dict(schema='ump.observed-track-window-import-ledger.v1',evaluation_id='unit-window-evaluation',
            source_validation_profile=runner.PROFILE,dataset_manifest_sha256=self.dataset_sha,
            dataset_assignment_sha256=runner.assignment_digest(self.m),imported_count=40,prospective_test_count=32,
            status='verified',cases=[dict(group_id=g['group_id'],split=g['split'],status='verified') for g in self.m['groups'] if g['split']!='test'])
        dump(self.src/'import-ledger.json',self.ledger)
        self.sp=dict(schema=runner.validation.PROTOCOL_SCHEMA,source_validation_profile=runner.PROFILE,
            evaluation_id='unit-window-evaluation',manifest_sha256=self.dataset_sha,dataset_manifest_sha256=self.dataset_sha,
            dataset_assignment_sha256=runner.assignment_digest(self.m),freeze_directory=str(self.freeze),
            import_ledger=runner.reference(self.src/'import-ledger.json'),cases=[dict(id=g['group_id'],**g,
                scene_directory=str(self.src/g['group_id']/'scene'),replay_directory=str(self.src/g['group_id']/'replay')) for g in self.m['groups']])
        dump(self.src/'protocol.json',self.sp)
        self.cases=[]
        for g in self.m['groups']:
            self.cases.append(dict(group_id=g['group_id'],split=g['split'],seed=g['seeds']['source_generation'],
                status='not_attempted' if g['split']=='test' else 'verified',validation_profile=runner.PROFILE,
                observations_sha256='b'*64,capture_proof_sha256='c'*64,checks={'hard_integrity':True},
                origin_strict_status='invalid' if g==self.m['groups'][0] else 'verified',
                movement_quality={'lifecycle_quality':{'active_episodes_at_horizon':3 if g==self.m['groups'][0] else 0,
                    'pending_episodes_at_horizon':0},'motion_quality':{'reported_diagnostics':{'active_stalled_tracks':2 if g==self.m['groups'][0] else 0}}}))
        self.summary=dict(evaluation_id=self.sp['evaluation_id'],source_validation_profile=runner.PROFILE,cases=self.cases)
        def unseen(protocol):
            if any(Path(r['scene_directory']).parent.exists() for r in protocol['cases'] if r['split']=='test'):
                raise ValueError('TEST source was already attempted')
        self.api=SimpleNamespace(read_protocol=mock.Mock(return_value=(self.src,self.sp,self.m)),
            summarize=mock.Mock(side_effect=lambda *a,**k:deepcopy(self.summary)),require_unseen_test=mock.Mock(side_effect=unseen))
        patch=mock.patch.object(runner,'sources',return_value=self.api);patch.start();self.addCleanup(patch.stop)
        self.p=dict(evaluation_id=self.sp['evaluation_id'],source_validation_profile=runner.PROFILE,
            source_profile_sha256=runner.primary.split.digest(runner.PROFILE_DEFINITION),dataset_manifest_sha256=self.dataset_sha,
            dataset_assignment_sha256=runner.assignment_digest(self.m),evaluation_manifest_sha256='d'*64,
            source_directory=str(self.src),source_protocol_sha256=runner.primary.source.sha(self.src/'protocol.json'),
            import_ledger=deepcopy(self.sp['import_ledger']),import_ledger_sha256=self.sp['import_ledger']['sha256'],
            implementation_files_sha256={},freeze_directory=str(self.freeze),output_directory=str(self.output),
            native_binary_sha256='e'*64,native_wall_budget_s=180,audit_max_cells=1000000)
        dump(self.output/'protocol.json',self.p)

    def auth_patch(self):
        return mock.patch.object(runner,'authenticate_protocol',return_value=(self.output,self.p,self.m))

    def write_group(self,g,*,sidecar=True):
        folder=self.output/'groups'/g['group_id'];folder.mkdir()
        dump(folder/'rows.json',[])
        summary=dict(group_id=g['group_id'],split=g['split'],status='verified',rows=runner.primary.artifact(folder,folder/'rows.json'),cases=[])
        dump(folder/'summary.json',summary)
        if sidecar:
            case=next(c for c in self.cases if c['group_id']==g['group_id'])
            dump(folder/'window-evaluation-receipt.json',dict(schema=runner.SIDECAR_SCHEMA,binding=runner._bindings(self.p),
                group_id=g['group_id'],split=g['split'],source_validation_sha256=runner._case_digest(case),
                summary_sha256=runner.primary.source.sha(folder/'summary.json'),rows_sha256=summary['rows']['sha256']))
        return summary

    def test_scientific_amendment_changes_only_two_declared_text_fields(self):
        original=deepcopy(self.m['design']['attack_protocol'])
        changed=runner.resolved_attack_protocol(self.m['design'])
        self.assertEqual(changed['secret'],runner.WINDOW_SECRET)
        self.assertEqual(changed['auxiliary']['acquisition'],runner.WINDOW_AUXILIARY)
        changed['secret']=original['secret'];changed['auxiliary']['acquisition']=original['auxiliary']['acquisition']
        self.assertEqual(changed,original)
        self.assertEqual(self.m['design']['attack_protocol'],original)
        self.assertEqual(set(runner.scientific_block_hashes(self.m['design'])),set(runner.UNCHANGED_BLOCKS))

    def test_source_contract_requires_explicit_profile_and_all40(self):
        runner._source_contract(self.sp,self.m)
        for mutation in ('missing','legacy','39'):
            sp=deepcopy(self.sp)
            if mutation=='missing':sp.pop('source_validation_profile')
            elif mutation=='legacy':sp['source_validation_profile']='legacy_completed_v1'
            else:
                ledger=deepcopy(self.ledger);ledger['cases'].pop();dump(self.src/'bad-ledger.json',ledger)
                sp['import_ledger']=runner.reference(self.src/'bad-ledger.json')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):runner._source_contract(sp,self.m)

    def test_prepare_creates_separate_evaluation_identity_without_reseeding(self):
        for name in set(runner.NEW_FILES)|set(runner.primary.IMPLEMENTATION_FILES):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic unexecuted code')
        binary=self.root/'simulator/build/AggregationReplay';binary.parent.mkdir(parents=True);binary.write_bytes(b'not executed')
        output=self.results/'new-evaluation'
        def new_output(path):path.mkdir(mode=0o700);return path
        with mock.patch.object(runner,'require_pair_injection'),mock.patch.object(runner.primary.split,'verify_freeze',return_value={'manifest_sha256':self.dataset_sha}), \
             mock.patch.object(runner.primary.fixture,'new_output',side_effect=new_output):
            runner.prepare(self.freeze,self.src,output)
        value=runner.primary.source.load(output/'evaluation-manifest.json')
        self.assertEqual(value['schema'],runner.EVALUATION_SCHEMA)
        self.assertEqual(value['dataset_study_id'],self.m['design']['study_id'])
        self.assertEqual(value['dataset_master_seed'],123)
        self.assertEqual(value['same_role_imports'],40);self.assertEqual(value['prospective_TEST_slots'],32)
        self.assertNotIn('actual_recordings',value)
        self.assertEqual(value['unchanged_scientific_blocks'],runner.scientific_block_hashes(self.m['design']))
        self.assertEqual(value['resolved_attack_protocol'],runner.resolved_attack_protocol(self.m['design']))
        self.assertEqual(value['contract'],runner.reference(self.root/runner.CONTRACT_PATH))
        runner.authenticate_protocol(output)
        ledger=deepcopy(self.ledger);ledger['status']='incomplete';dump(self.src/'import-ledger.json',ledger)
        with self.assertRaises(ValueError):runner.authenticate_protocol(output)

    def test_coherently_rehashed_extra_attack_change_is_rejected(self):
        for name in set(runner.NEW_FILES)|set(runner.primary.IMPLEMENTATION_FILES):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'unexecuted code')
        binary=self.root/'simulator/build/AggregationReplay';binary.parent.mkdir(parents=True);binary.write_bytes(b'not executed')
        output=self.results/'amendment-check'
        def new_output(path):path.mkdir(mode=0o700);return path
        with mock.patch.object(runner,'require_pair_injection'),mock.patch.object(runner.primary.split,'verify_freeze',return_value={'manifest_sha256':self.dataset_sha}), \
             mock.patch.object(runner.primary.fixture,'new_output',side_effect=new_output):
            runner.prepare(self.freeze,self.src,output)
        evaluation=runner.primary.source.load(output/'evaluation-manifest.json')
        evaluation['resolved_attack_protocol']['model']['l2']=999
        dump(output/'evaluation-manifest.json',evaluation)
        protocol=runner.primary.source.load(output/'protocol.json')
        protocol['evaluation_manifest_sha256']=runner.primary.source.sha(output/'evaluation-manifest.json')
        dump(output/'protocol.json',protocol)
        (output/'protocol.sha256').write_text(runner.primary.source.sha(output/'protocol.json')+'\n')
        with self.assertRaisesRegex(ValueError,'deterministic two-text delta'):
            runner.authenticate_protocol(output)

    def test_39of40_blocks_all_native_calls_even_limit1(self):
        self.cases[30]['status']='invalid'
        with self.auth_patch(),mock.patch.object(runner,'require_pair_injection'),mock.patch.object(runner.primary,'process_group') as native:
            with self.assertRaisesRegex(ValueError,'Incomplete hard-valid'):
                runner.run(self.output,['train'],limit=1)
            native.assert_not_called()

    def test_31of32_blocks_all_TEST_calls_even_limit1(self):
        for case in self.cases:
            if case['split']=='test':case['status']='verified'
        self.cases[-1]['status']='invalid'
        with self.auth_patch(),mock.patch.object(runner,'require_pair_injection'),mock.patch.object(runner,'authenticate_test_gate'), \
             mock.patch.object(runner.primary,'process_group') as native:
            with self.assertRaisesRegex(ValueError,'Incomplete hard-valid'):
                runner.run(self.output,['test'],limit=1)
            native.assert_not_called()

    def test_hard_valid_legacy_invalid_quality_flagged_case_is_not_filtered(self):
        events=[]
        def process(output,p,m,g,case,*,pair_selector):
            events.append((g,case,pair_selector));return self.write_group(g,sidecar=False)
        with self.auth_patch(),mock.patch.object(runner,'require_pair_injection'),mock.patch.object(runner.primary,'process_group',side_effect=process):
            runner.run(self.output,['train'],limit=1)
        self.assertEqual(len(events),1);self.assertEqual(events[0][1]['origin_strict_status'],'invalid')
        self.assertIs(events[0][2],runner.select_window_pair)
        self.assertTrue((self.output/'groups'/self.m['groups'][0]['group_id']/'window-evaluation-receipt.json').is_file())
        self.api.summarize.assert_called_with(self.src,self.sp,self.m,verify=True)

    def test_missing_and_wrong_scope_sidecar_reject_old_same_group_outputs(self):
        g=self.m['groups'][0];self.write_group(g,sidecar=False)
        with self.assertRaisesRegex(ValueError,'sidecar missing'):
            runner.collect(self.output,self.p,self.m,self.summary)
        folder=self.output/'groups'/g['group_id']
        dump(folder/'window-evaluation-receipt.json',dict(schema=runner.SIDECAR_SCHEMA,binding={**runner._bindings(self.p),'evaluation_manifest_sha256':'old'},group_id=g['group_id'],split=g['split']))
        with self.assertRaisesRegex(ValueError,'Old/wrong evaluation'):
            runner.collect(self.output,self.p,self.m,self.summary)

    def test_sidecar_authenticates_source_quality_and_row_summary_hashes(self):
        g=self.m['groups'][0];self.write_group(g)
        runner.collect(self.output,self.p,self.m,self.summary)
        self.cases[0]['checks']['hard_integrity']=False
        with self.assertRaisesRegex(ValueError,'provenance differs'):
            runner.collect(self.output,self.p,self.m,self.summary)

    def test_quality_is_reported_without_unknown_zero_or_filter(self):
        value=runner.source_quality(self.cases,self.m)
        self.assertFalse(value['quality_filters_enrollment'])
        self.assertEqual(value['by_split']['train']['sources_with_active_at_horizon'],1)
        self.assertEqual(value['by_split']['train']['sources_with_reported_stalls'],1)
        self.cases[24].pop('movement_quality')
        value=runner.source_quality(self.cases,self.m)
        self.assertIsNone(value['by_split']['calibration']['sources_with_active_at_horizon'])
        self.assertEqual(value['by_split']['calibration']['quality_reports'],15)

    def model_fixture(self):
        methods=[m['id'] for m in self.m['design']['methods']];expected=runner.expected_groups(self.m)
        rows=[dict(group_id=g['group_id'],split=g['split'],method_id=method,world=world,label=int(world=='IN'))
              for g in self.m['groups'] if g['split']!='test' for method in methods for world in ('IN','OUT')]
        models=dict(training_group_ids=expected['train'],calibration_group_ids=expected['calibration'],
                    expected_method_ids=methods,models=[dict(status='nonconverged') for _ in range(22)])
        dump(self.output/'models.json',models);dump(self.output/'train-cal-rows.json',rows)
        dump(self.output/'implementation-supplement.json',{})
        lock=dict(schema=runner.LOCK_SCHEMA,status='locked_before_test',**runner._bindings(self.p),
            implementation_sha256=runner.primary.source.sha(self.output/'implementation-supplement.json'),
            implementation_files_sha256={},group_counts={'train':24,'calibration':16},test_rows_seen=0,
            models=runner.reference(self.output/'models.json'),data=runner.reference(self.output/'train-cal-rows.json'))
        dump(self.output/'models-lock.json',lock)
        return rows,models,lock

    def test_old_same_group_lock_rejected_by_new_evaluation_profile_binding(self):
        rows,models,lock=self.model_fixture();lock['evaluation_manifest_sha256']='old-complete-episode'
        dump(self.output/'models-lock.json',lock)
        with self.auth_patch(),mock.patch.object(runner,'authenticate_supplement',return_value={'files_sha256':{}}), \
             mock.patch.object(runner.primary.analysis,'validate_model_lock') as validate:
            with self.assertRaisesRegex(ValueError,'Old or wrong evaluation'):
                runner.authenticate_test_gate(self.output)
            validate.assert_not_called()

    def test_repeated_gate_checks_actual_models_rows_sidecars_without_raw_rebuild(self):
        rows,models,lock=self.model_fixture()
        with self.auth_patch(),mock.patch.object(runner,'authenticate_supplement',return_value={'files_sha256':{}}), \
             mock.patch.object(runner,'collect',return_value=(rows,[])) as collect, \
             mock.patch.object(runner.primary.analysis,'validate_model_lock',return_value={'status':'verified'}) as validate:
            self.assertEqual(runner.authenticate_test_gate(self.output),lock)
            self.api.summarize.assert_called_with(self.src,self.sp,self.m,verify=False)
            self.assertFalse(collect.call_args.kwargs['verify_archives'])
            validate.assert_called_once_with(models,rows,require_complete=True)
            # New TEST receipt/state cannot change the immutable import/model binding.
            self.cases[-1]['status']='verified'
            self.assertEqual(runner.authenticate_test_gate(self.output),lock)
            collect.return_value=(rows[:-1],[])
            with self.assertRaisesRegex(ValueError,'Locked rows differ'):
                runner.authenticate_test_gate(self.output)

    def test_coherently_rehashed_runtime_change_rejects_existing_lock(self):
        rows,models,lock=self.model_fixture()
        self.p['native_wall_budget_s']=181
        dump(self.output/'protocol.json',self.p)
        (self.output/'protocol.sha256').write_text(runner.primary.source.sha(self.output/'protocol.json')+'\n')
        with self.auth_patch(),mock.patch.object(runner,'authenticate_supplement',return_value={'files_sha256':{}}), \
             mock.patch.object(runner.primary.analysis,'validate_model_lock') as validate:
            with self.assertRaisesRegex(ValueError,'Old or wrong evaluation'):
                runner.authenticate_test_gate(self.output)
            validate.assert_not_called()

    def validation_receipt(self,kind):
        path=self.root/'tools/evaluation/validated.py';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'code-B')
        self.p['implementation_files_sha256']={'tools/evaluation/validated.py':runner.primary.source.sha(path)}
        value=dict(schema=runner.UNIT_VALIDATION_SCHEMA if kind=='unit' else runner.DEV_VALIDATION_SCHEMA,
            status='verified',test_data_seen=False,evaluation_id=self.p['evaluation_id'],source_validation_profile=runner.PROFILE,
            actual_primary_model_fits=False,full_code_sha256=deepcopy(self.p['implementation_files_sha256']))
        if kind=='unit':value.update(tests=200,failures=0,errors=0,skipped=0,native_jobs=0,modules=sorted(runner.REQUIRED_UNIT_MODULES))
        else:value.update(new_native_cases=0,retained_native_cases=18,derived_cases=4,recipient_streams=22,methods=11,
                          query_count_per_world=19200,native_binary_sha256=self.p['native_binary_sha256'],
                          archive_roundtrip_authenticated=True,raw_policy_audits_recomputed=True,
                          regional_transcripts_recomposed=True,rows_recomputed=True)
        return value

    def test_stale_same_profile_validation_code_cannot_certify_current_execution(self):
        value=self.validation_receipt('unit')
        value['full_code_sha256']['tools/evaluation/validated.py']='0'*64
        with self.assertRaisesRegex(ValueError,'stale code'):
            runner.validate_validation_receipt(value,'unit',self.p)
        value=self.validation_receipt('unit');value['full_code_sha256']={}
        with self.assertRaisesRegex(ValueError,'actual execution code'):
            runner.validate_validation_receipt(value,'unit',self.p)

    def test_distinct_unit_DEV_coverage_and_retained_native_provenance(self):
        for kind in ('unit','dev'):
            value=self.validation_receipt(kind)
            runner.validate_validation_receipt(value,kind,self.p)
            wrong=deepcopy(value);wrong['schema']='old-untyped-receipt'
            with self.assertRaises(ValueError):runner.validate_validation_receipt(wrong,kind,self.p)
        dev=self.validation_receipt('dev');dev['retained_native_cases']=17
        with self.assertRaisesRegex(ValueError,'DEV validation coverage'):
            runner.validate_validation_receipt(dev,'dev',self.p)
        dev=self.validation_receipt('dev');dev['rows_recomputed']=False
        with self.assertRaisesRegex(ValueError,'DEV validation coverage'):
            runner.validate_validation_receipt(dev,'dev',self.p)
        unit=self.validation_receipt('unit');unit['modules']=[]
        with self.assertRaisesRegex(ValueError,'Unit validation coverage'):
            runner.validate_validation_receipt(unit,'unit',self.p)

    def test_gate_propagates_missing_sidecar_rejection(self):
        self.model_fixture()
        with self.auth_patch(),mock.patch.object(runner,'authenticate_supplement',return_value={'files_sha256':{}}), \
             mock.patch.object(runner,'collect',side_effect=ValueError('Windowed evaluation sidecar missing')), \
             mock.patch.object(runner.primary.analysis,'validate_model_lock') as validate:
            with self.assertRaisesRegex(ValueError,'sidecar missing'):runner.authenticate_test_gate(self.output)
            validate.assert_not_called()

    def test_lock_uses_explicit_groups_and_allows_frozen_nonconvergence(self):
        rows,models,_=self.model_fixture()
        summaries=[dict(group_id=g['group_id'],split=g['split'],status='verified',pair={}) for g in self.m['groups'] if g['split']!='test']
        # lock outputs are new one-shot files; fixture inputs above are removed only inside this synthetic temp tree.
        for name in ('models-lock.json','models.json','train-cal-rows.json'):(self.output/name).unlink()
        with self.auth_patch(),mock.patch.object(runner,'authenticate_supplement',return_value={}), \
             mock.patch.object(runner,'collect',return_value=(rows,summaries)) as collect, \
             mock.patch.object(runner.primary.split,'verify_actual_sources',return_value={}), \
             mock.patch.object(runner.primary.analysis,'prepare_models',return_value=models) as prepare, \
             mock.patch.object(runner.primary.analysis,'validate_model_lock',return_value={}) as validate, \
             mock.patch.object(runner,'authenticate_test_gate'):
            value=runner.lock_models(self.output)
        prepare.assert_called_once_with(rows,expected_groups=runner.expected_groups(self.m),method_ids=[m['id'] for m in self.m['design']['methods']])
        validate.assert_called_once_with(models,rows,require_complete=True)
        self.assertTrue(collect.call_args.kwargs['verify_archives'])
        self.assertEqual(value['evaluation_manifest_sha256'],self.p['evaluation_manifest_sha256'])
        self.assertEqual(value['import_ledger_sha256'],self.p['import_ledger_sha256'])

    def test_existing_TEST_source_blocks_new_lock_before_any_fit(self):
        test=next(r for r in self.sp['cases'] if r['split']=='test')
        Path(test['scene_directory']).parent.mkdir(parents=True)
        with self.auth_patch(),mock.patch.object(runner,'authenticate_supplement',return_value={}), \
             mock.patch.object(runner.primary.analysis,'prepare_models') as prepare:
            with self.assertRaisesRegex(ValueError,'TEST source'):runner.lock_models(self.output)
            prepare.assert_not_called()


if __name__=='__main__':unittest.main()
