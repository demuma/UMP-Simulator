"""Synthetic repair-boundary tests; never read actual source/model rows or run jobs."""
from copy import deepcopy
import ast
import json
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import importlib
repair=importlib.import_module(Path(__file__).stem.removeprefix('test_'))


def family():
    groups=[];cases=[]
    for i in range(72):
        role='train' if i<24 else 'calibration' if i<40 else 'test'
        groups.append(dict(group_id='g'+str(i),split=role,seeds={'source_generation':100+i}))
        cases.append(dict(group_id='g'+str(i),split=role,seed=100+i,status='verified',validation_profile=repair.PROFILE,
            observations_sha256='o'+str(i),normalized_source_fingerprint='f'+str(i),normalized_source_fingerprint_v2='n'+str(i),planned_route_fingerprint='r'+str(i)))
    return dict(groups=groups,exclusions=[]),cases


class RepairBoundaryTests(unittest.TestCase):
    def test_exact_one_line_diagnostic_delta(self):
        old=b'before\n'+repair.OLD_EXPR+b'\nafter\n'
        repair.exact_diagnostic_delta(old,old.replace(repair.OLD_EXPR,repair.NEW_EXPR))

    def test_unrelated_identical_legacy_value_is_preserved(self):
        legacy=b"require("+repair.OLD_VALUE+b" >= 2, 'legacy coverage')\n"
        old=legacy+b"'movement_coverage_quality': {"+repair.OLD_EXPR+b"}\n"
        new=legacy+b"'movement_coverage_quality': {"+repair.NEW_EXPR+b"}\n"
        self.assertEqual(old.count(repair.OLD_VALUE),2)
        self.assertEqual(old.count(repair.OLD_EXPR),1)
        repair.exact_diagnostic_delta(old,new)
        with self.assertRaises(ValueError):repair.exact_diagnostic_delta(old,new.replace(legacy,legacy.replace(repair.OLD_VALUE,repair.NEW_VALUE)))

    def test_duplicate_actual_diagnostic_field_is_rejected(self):
        old=repair.OLD_EXPR+b"\n"+repair.OLD_EXPR
        with self.assertRaises(ValueError):repair.exact_diagnostic_delta(old,old.replace(repair.OLD_EXPR,repair.NEW_EXPR,1))

    def test_second_change_rejected(self):
        old=b'before\n'+repair.OLD_EXPR+b'\nafter\n'
        with self.assertRaises(ValueError):repair.exact_diagnostic_delta(old,old.replace(repair.OLD_EXPR,repair.NEW_EXPR).replace(b'after',b'waived'))

    def test_inexact_or_duplicate_expression_rejected(self):
        for old in (b'wrong',repair.OLD_EXPR+b'\n'+repair.OLD_EXPR):
            with self.subTest(old=old),self.assertRaises(ValueError):repair.exact_diagnostic_delta(old,old.replace(repair.OLD_EXPR,repair.NEW_EXPR))

    def test_only_surface_portals_excluded_malformed_building_still_fails(self):
        expression=repair.NEW_VALUE.decode()
        portals={'A1':{'kind':'surface_access'},'A2':{'kind':'surface_access'},'B1':{'kind':'building','building_id':'B'},'B2':{'kind':'building','building_id':'B'}}
        self.assertEqual(eval(expression,{},dict(portals=portals)),1)
        portals['bad']={'kind':'building'}
        with self.assertRaises(KeyError):eval(expression,{},dict(portals=portals))

    def test_all72_same_role_family_accepted(self):
        manifest,cases=family();repair.validate_family(cases,manifest)

    def test_missing_one_test_or_import_rejected(self):
        manifest,cases=family()
        for index in (0,40,71):
            with self.subTest(index=index),self.assertRaises(ValueError):repair.validate_family(cases[:index]+cases[index+1:],manifest)

    def test_duplicate_id_cannot_replace_missing_case(self):
        manifest,cases=family();cases[-1]=deepcopy(cases[0])
        with self.assertRaises(ValueError):repair.validate_family(cases,manifest)

    def test_role_seed_invalid_profile_or_status_change_rejected(self):
        manifest,cases=family()
        for field,value in [('split','train'),('seed',777),('status','invalid'),('validation_profile','legacy_completed_v1')]:
            bad=deepcopy(cases);bad[40][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):repair.validate_family(bad,manifest)

    def test_source_and_route_clones_rejected(self):
        manifest,cases=family()
        for field in ('normalized_source_fingerprint_v2','planned_route_fingerprint'):
            bad=deepcopy(cases);bad[71][field]=bad[0][field]
            with self.subTest(field=field),self.assertRaises(ValueError):repair.validate_family(bad,manifest)

    def test_historical_clone_rejected(self):
        manifest,cases=family()
        for field in ('observations_sha256','normalized_source_fingerprint','normalized_source_fingerprint_v2','planned_route_fingerprint'):
            bad=deepcopy(manifest);bad['exclusions']=[{field:cases[50][field]}]
            with self.subTest(field=field),self.assertRaises(ValueError):repair.validate_family(cases,bad)

    def test_code_map_allows_only_exact_archived_auditor(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();old=directory/'old.py';new=directory/'new.py';other=directory/'other.py'
            old.write_bytes(b'old');new.write_bytes(b'new');other.write_bytes(b'other')
            with patch.object(repair,'AUDITOR',new):
                mapping={str(new):repair.source.sha(old),str(other):repair.source.sha(other)}
                repair.verify_code_map(mapping,old,repair.source.sha(new))
                other.write_bytes(b'changed')
                with self.assertRaises(ValueError):repair.verify_code_map(mapping,old,repair.source.sha(new))

    def test_changed_or_missing_old_archive_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();old=directory/'old';new=directory/'new';old.write_bytes(b'old');new.write_bytes(b'new')
            mapping={str(new):repair.source.sha(old)}
            with patch.object(repair,'AUDITOR',new):
                old.write_bytes(b'changed')
                with self.assertRaises(ValueError):repair.verify_code_map(mapping,old,repair.source.sha(new))
                old.unlink()
                with self.assertRaises((ValueError,OSError)):repair.verify_code_map(mapping,old,repair.source.sha(new))

    def test_binding_pins_original_models_rows_lock_and_actual_protocol(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();(output/'protocol.json').write_text('protocol');(output/'validation-ledger.json').write_text('ledger')
            p=dict(repair_id='repair',evaluation_id='evaluation',anchors={name:{'sha256':name+'-hash'} for name in ('model_lock','models','rows','execution_protocol','dataset_manifest')})
            value=repair.bindings(output,p)
            self.assertEqual(value['original_models_lock_sha256'],'model_lock-hash')
            self.assertEqual(value['original_models_sha256'],'models-hash')
            self.assertEqual(value['original_train_cal_rows_sha256'],'rows-hash')
            (output/'protocol.json').write_text('changed budget')
            self.assertNotEqual(value,repair.bindings(output,p))
            (output/'validation-ledger.json').write_text('changed ledger')
            self.assertNotEqual(value['validation_ledger_sha256'],repair.bindings(output,p)['validation_ledger_sha256'])

    def test_validation_view_changes_only_explicit_provenance_fields(self):
        sp=dict(schema='old',frozen_files_sha256={str(repair.AUDITOR):'oldhash','other':'same'},legacy_physical_audits={'old':'legacy'},windowed_physical_audits={'old':'window'},cases=[],source_horizon_ms=300000)
        context={'source':sp};p=dict(corrected_auditor={'sha256':'newhash'},output_directory='/synthetic',anchors={'source_protocol':{'sha256':'source'}})
        with patch.object(repair,'reference',return_value={'sha256':'repair'}),patch.object(repair,'legacy_proof_refs',return_value=deepcopy(sp['legacy_physical_audits'])):result=repair.validation_view(p,context)
        self.assertEqual(sp['frozen_files_sha256'][str(repair.AUDITOR)],'oldhash')
        self.assertEqual(result['frozen_files_sha256'],{str(repair.AUDITOR):'newhash','other':'same'})
        self.assertEqual(result['diagnostic_repair_producer']['kind'],'derived_validation_view_not_original_protocol')
        self.assertEqual(result['legacy_physical_audits'],sp['legacy_physical_audits']);self.assertEqual(result['windowed_physical_audits'],{})
        for field in set(sp)-{'frozen_files_sha256','legacy_physical_audits','windowed_physical_audits'}:self.assertEqual(result[field],sp[field])

    def test_source_closure_rejects_pending_counts_or_nonzero_test_analysis(self):
        context={'source':{'output_directory':'/synthetic'},'manifest':{'groups':[]}}
        base=dict(schema=repair.CLOSURE_SCHEMA,status='closed',source_protocol_sha256='sha',attempted_test_count=32,capture_complete_test_count=32,test_mechanism_groups=0,test_model_evaluations=0)
        with patch.object(repair.source,'sha',return_value='sha'):
            for field,value in [('status','running'),('attempted_test_count',31),('capture_complete_test_count',31),('test_mechanism_groups',1),('test_model_evaluations',1)]:
                bad=dict(base);bad[field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):repair.validate_closure(bad,context)

    def test_all32_gate_precedes_any_mechanism(self):
        manifest,cases=family();context=dict(manifest=manifest)
        with patch.object(repair,'read_protocol',return_value=(Path('/synthetic'),{},context)),patch.object(repair,'authenticated_validation',return_value=cases[:40]),patch.object(repair.primary,'process_group') as process:
            with self.assertRaises(ValueError):repair.run_test(Path('/synthetic'))
            process.assert_not_called()

    def test_training_group_cannot_be_run_through_test_interface(self):
        manifest,cases=family();context=dict(manifest=manifest)
        with patch.object(repair,'authenticate_test_gate',return_value=(Path('/synthetic'),{},context,cases)),patch.object(repair.window,'require_pair_injection'),patch.object(repair.primary,'process_group',side_effect=RuntimeError('stop at first TEST')) as process:
            with self.assertRaisesRegex(RuntimeError,'first TEST'):repair.run_test(Path('/synthetic'),limit=1)
            args=process.call_args.args
            self.assertEqual(args[3]['split'],'test');self.assertIs(process.call_args.kwargs['pair_selector'],repair.window.select_window_pair)

    def test_no_fitting_or_source_generation_dispatch(self):
        tree=ast.parse(Path(repair.__file__).read_text())
        forbidden={'prepare_models','fit_logistic','lock_models','capture_test','attempt','command','run_scene'}
        calls={node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,(ast.Attribute,ast.Name))}
        self.assertFalse(calls & forbidden)
        names={node.name for node in tree.body if isinstance(node,ast.FunctionDef)}
        self.assertFalse(names & {'fit','lock_models','run_train','run_calibration','capture_test'})

    def test_merge_acknowledges_original_sidecars_and_rejects_new_train_rows(self):
        context=dict(main={'output_directory':'/old'},manifest={},old_summary={})
        old_rows=[{'split':'train','group_id':'g0'}];old_summaries=[{'split':'train','group_id':'g0'}]
        with patch.object(repair.window,'collect',return_value=(old_rows,old_summaries)) as old_collect,patch.object(repair.primary,'collect',return_value=([{'split':'train'}],[])):
            with self.assertRaises(ValueError):repair.collect_repair(Path('/new'),{},context,[])
            self.assertEqual(old_collect.call_args.args[0],Path('/old'))

    def test_merge_keeps_exactly40_imports_and32_test_outcomes(self):
        manifest,cases=family()
        old_rows=[{'group_id':'g0','split':'train'}]
        old_summaries=[dict(group_id=g['group_id'],split=g['split'],status='verified' if g['split']!='test' else 'not_attempted') for g in manifest['groups']]
        new_summaries=[dict(group_id=g['group_id'],split=g['split'],status='not_attempted') for g in manifest['groups']]
        context=dict(main={'output_directory':'/old'},manifest=manifest,old_summary={})
        with patch.object(repair.window,'collect',return_value=(old_rows,old_summaries)),patch.object(repair.primary,'collect',return_value=([],new_summaries)),patch.object(repair,'authenticated',return_value=Path('/rows')),patch.object(repair.source,'load',return_value=old_rows):
            rows,summaries=repair.collect_repair(Path('/new'),{'anchors':{'rows':{}}},context,cases)
            self.assertEqual(rows,old_rows);self.assertEqual(len(summaries),72)
            self.assertEqual(sum(s['split']=='test' for s in summaries),32)

    def test_original_failure_requires_actual_diagnostic_trace_and_execution(self):
        row={'scene_directory':'/synthetic/scene','audit_command':['python','original-auditor']}
        saved={'status':'invalid','error':'Independent physical audit failed or exceeded its finite wall cap'}
        execution=dict(status='failed',returncode=1,command=row['audit_command'])
        stderr=b'trace '+repair.OLD_EXPR+b"\nKeyError: 'building_id'\n"
        with patch.object(repair.source,'load',return_value=execution),patch.object(repair.primary.fixture,'read_bytes',return_value=stderr):
            repair.expected_diagnostic_failure(row,saved)
            for key,value in [('status','timeout'),('returncode',2),('command',['wrong'])]:
                bad=dict(execution);bad[key]=value
                with self.subTest(key=key),patch.object(repair.source,'load',return_value=bad),self.assertRaises(ValueError):repair.expected_diagnostic_failure(row,saved)
        for bad_trace in (b"KeyError: 'building_id'",repair.OLD_EXPR+b"\nAssertionError: overlap\n"):
            with patch.object(repair.source,'load',return_value=execution),patch.object(repair.primary.fixture,'read_bytes',return_value=bad_trace),self.assertRaises(ValueError):repair.expected_diagnostic_failure(row,saved)

    def test_physical_proof_requires_known_unambiguous_role_correct_origin(self):
        legacy={k:{'path':k,'sha256':k} for k in ('report','execution','producer_protocol','archived_auditor')}
        windowed={k:{'path':k,'sha256':k} for k in ('report','execution')}
        view=dict(legacy_physical_audits={'old':legacy},windowed_physical_audits={'new':windowed})
        with patch.object(repair,'authenticated') as auth:
            self.assertEqual(repair.physical_proof(view,dict(capture_proof_sha256='old',split='train'))['origin'],'authenticated_legacy_proof_reuse')
            self.assertEqual(auth.call_count,4)
            self.assertEqual(repair.physical_proof(view,dict(capture_proof_sha256='new',split='test'))['origin'],'new_corrected_test_audit')
            self.assertEqual(auth.call_count,6)
            for key,role in [('unknown','test'),('old','test'),('new','train')]:
                with self.subTest(key=key,role=role),self.assertRaises(ValueError):repair.physical_proof(view,dict(capture_proof_sha256=key,split=role))
            ambiguous=deepcopy(view);ambiguous['windowed_physical_audits']['old']=windowed
            with self.assertRaises(ValueError):repair.physical_proof(ambiguous,dict(capture_proof_sha256='old',split='train'))

    def test_legacy_map_must_authenticate_exact40_original_proof_keys(self):
        rows=[dict(split='train' if i<24 else 'calibration',replay_directory='/synthetic/g'+str(i)+'/replay') for i in range(40)]
        proof={k:{'path':k,'sha256':k} for k in ('report','execution','producer_protocol','archived_auditor')}
        context={'source':dict(cases=rows,legacy_physical_audits={'g'+str(i):deepcopy(proof) for i in range(40)})}
        with patch.object(repair.source,'sha',side_effect=lambda path:Path(path).parents[1].name),patch.object(repair,'authenticated') as auth:
            self.assertEqual(len(repair.legacy_proof_refs(context)),40);self.assertEqual(auth.call_count,160)
            context['source']['legacy_physical_audits']['unknown']=context['source']['legacy_physical_audits'].pop('g0')
            with self.assertRaises(ValueError):repair.legacy_proof_refs(context)

    def test_revalidate_runs32_auditors_and72_raw_validations_without_fake_import_execution(self):
        manifest,cases=family()
        rows=[dict(id='s'+str(i),group_id=c['group_id'],split=c['split'],seed=c['seed'],scene_directory='/synthetic/'+c['group_id']+'/scene',replay_directory='/synthetic/'+c['group_id']+'/replay',origin='same-original') for i,c in enumerate(cases)]
        expected={c['group_id']:c for c in cases}
        legacy={'proof-'+c['group_id']:{'original':'proof'} for c in cases if c['split']!='test'}
        original_sha,original_load=repair.source.sha,repair.source.load
        def fake_sha(path):
            path=Path(path)
            return 'proof-'+path.parents[1].name if path.name=='capture-proof.json' else original_sha(path)
        def fake_load(path):return {} if str(path).startswith('/synthetic/') else original_load(path)
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();(output/'groups').mkdir();(output/'validation').mkdir();(output/'protocol.json').write_text('{}')
            p=dict(anchors={'model_lock':{'path':'old-lock','sha256':'lock'}},original_source_receipts={r['group_id']:{'path':'old-'+r['group_id'],'sha256':'old'} for r in rows})
            context=dict(source=dict(cases=rows,physical_audit_wall_budget_s=1),manifest=manifest)
            refs=lambda path:dict(path=str(path),sha256=original_sha(path))
            with patch.object(repair,'read_protocol',return_value=(output,p,context)),patch.object(repair,'legacy_proof_refs',return_value=legacy),patch.object(repair,'validation_view',return_value={}),patch.object(repair.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as audit,patch.object(repair.validation,'validate_capture',side_effect=lambda row,view:deepcopy(expected[row['group_id']])) as raw,patch.object(repair.primary.split,'normalized_fingerprint',side_effect=['n'+str(i) for i in range(72)]),patch.object(repair.source,'sha',side_effect=fake_sha),patch.object(repair.source,'load',side_effect=fake_load),patch.object(repair,'reference',side_effect=refs),patch.object(repair,'authenticated',side_effect=lambda ref:Path(ref['path'])):
                ledger=repair.revalidate(output)
            self.assertEqual(audit.call_count,32);self.assertEqual(raw.call_count,72)
            self.assertEqual({call.args[0]['group_id'] for call in raw.call_args_list},{r['group_id'] for r in rows})
            for call in audit.call_args_list:self.assertIn(call.args[0][call.args[0].index('--scene')+1],{r['scene_directory'] for r in rows if r['split']=='test'})
            self.assertEqual((ledger['new_physical_audit_jobs'],ledger['reused_legacy_physical_proofs'],ledger['full_raw_validations']),(32,40,72))
            self.assertEqual(ledger['status'],'verified')
            for row in rows:
                directory=output/'validation'/row['group_id']
                self.assertTrue((directory/'receipt.json').is_file())
                if row['split']!='test':
                    self.assertFalse((directory/'audit-execution.json').exists())
                    self.assertFalse(json.loads((directory/'reused-physical-proof.json').read_text())['physical_audit_executed'])

    def test_driver_closure_requires_actual_failed_gate_complete_phase_and_no_test_start(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name).resolve();summary_ref={'path':'final-summary','sha256':'summary-hash'}
            records={
                'driver-failed.json':dict(status='failed_or_interrupted',completed=['native_train_cal','lock_models','source_test'],error='Full32 hard-valid TEST sources required; no available-case estimates'),
                'source_test-driver-receipt.json':dict(status='complete',returncode=0),
                'test-driver-source-gate.json':dict(schema='ump.observed-track-window-driver-source-gate.v1',status='failed',expected=32,observed=32,verified=0,source_summary_sha256='summary-hash')}
            for filename,value in records.items():(output/filename).write_text(json.dumps(value))
            refs=lambda path:dict(path=str(path),sha256=repair.source.sha(path))
            with patch.object(repair,'reference',side_effect=refs),patch.object(repair,'authenticated',side_effect=lambda ref:Path(ref['path'])):
                self.assertEqual(len(repair.driver_phase_closure(output,summary_ref)),3)
                mutations=[('driver-failed.json','completed',['native_train_cal','lock_models']),('source_test-driver-receipt.json','returncode',1),('source_test-driver-receipt.json','status','running'),('test-driver-source-gate.json','source_summary_sha256','other'),('test-driver-source-gate.json','status','verified'),('test-driver-source-gate.json','observed',31)]
                for filename,key,value in mutations:
                    bad=deepcopy(records[filename]);bad[key]=value;(output/filename).write_text(json.dumps(bad))
                    with self.subTest(filename=filename,key=key),self.assertRaises(ValueError):repair.driver_phase_closure(output,summary_ref)
                    (output/filename).write_text(json.dumps(records[filename]))
                (output/'native_test-driver-start.json').write_text('{}')
                with self.assertRaises(ValueError):repair.driver_phase_closure(output,summary_ref)
                (output/'native_test-driver-start.json').unlink();(output/'driver-failed.json').unlink()
                with self.assertRaises((ValueError,OSError)):repair.driver_phase_closure(output,summary_ref)

    def test_explicit_anchors_are_supported_and_bound_for_promoted_adapter(self):
        import inspect
        self.assertIn('anchors_path',inspect.signature(repair.close_source_phase).parameters)
        self.assertIn('anchors_path',inspect.signature(repair.prepare).parameters)
        code=Path(repair.__file__).read_text()
        self.assertIn("parser.add_argument('--anchors',type=Path)",code)
        self.assertIn("source.load(authenticated(p['anchors_reference']))==p['anchors']",code)
        self.assertIn("closure.get('anchors_reference')==context['anchors_reference']",code)

    def test_report_uses_original_models_without_fit(self):
        tree=ast.parse(Path(repair.__file__).read_text());method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='report')
        calls=[n for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='evaluate_models']
        self.assertEqual(len(calls),1)
        self.assertEqual(ast.unparse(calls[0].args[0]),"context['models']")


if __name__=='__main__':unittest.main(verbosity=2)
