"""Small mocked orchestration checks; no urban motion generation or timed jobs."""
import contextlib
import copy
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import run_spatial20_correction as runner
_fixture_spec=importlib.util.spec_from_file_location('ump_spatial20_correction_test_fixtures',
    Path(__file__).resolve().parents[1]/'mapped_scene/test_run_comparison.py')
_fixture_module=importlib.util.module_from_spec(_fixture_spec)
# The existing fixture module uses its own sibling's generic import name. Bind
# that dependency only while loading it, then restore any caller's cache entry.
_cached_comparison=sys.modules.get('run_comparison')
sys.modules['run_comparison']=runner.mapped
try:
    _fixture_spec.loader.exec_module(_fixture_module)
finally:
    if _cached_comparison is None:sys.modules.pop('run_comparison',None)
    else:sys.modules['run_comparison']=_cached_comparison
config_fixture,source_fixture=_fixture_module.config_fixture,_fixture_module.source_fixture


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')


def portfolio(root):
    root.mkdir();(root/'provenance').mkdir()
    data,result=source_fixture();cfg=config_fixture();base=copy.deepcopy(cfg['sensors'][0]['aggregation'])
    base['policy_regions']=[dict(id='small-local-patch',type='local',x=10,y=10,width=2.5,height=2.5,
        type_requirements={'window_duration_ms':{'max':1000}},requirements={'semantic_max_loss':{'max':.5}})]
    base['spatial_selection']={'min_depth':3};base['temporal_adaptation']={'coordination':'cell_local'}
    write(root/'observations.json',data)
    proof={'schema':'ump.mapped-recording-proof.v1','status':'verified','source_completed':True,
        'all_scheduled_episodes_completed':True,'lifecycle_quality':{'scheduled_episodes':5,
            'pending_episodes_at_horizon':0,'active_episodes_at_horizon':0},
        'sensor_observability':{'schema':'ump.source-sensor-episode-observability.v1','status':'pass',
            'scheduled_tracks':5,'sensor_observed_tracks':5,'missing_track_count':0,'unexpected_track_count':0}}
    write(root/'provenance/capture-proof.json',proof);(root/'provenance/AggregationReplay').write_text('old-native-fixture')
    cases={};variants=[]
    for row in runner.mapped.spatial_portfolio_variants(data['coverage']):
        name=row['id'];config=runner.mapped.settings_for(base,row)
        write(root/(name+'-policy.json'),config);write(root/(name+'.json'),result)
        variants.append(dict(id=name,result=name+'.json',label=name))
        cases[name]=dict(policy_profile=row['policy_profile'],policy_tree_id=config['policy_tree']['id'],
            stats=runner.mapped.summarize(data,config,result),independent_audit={
                'status':'verified','scalar_valid':True,'published_policy_violations':0},
            result_sha256=runner.sha(root/(name+'.json')),config_sha256=runner.sha(root/(name+'-policy.json')),
            native_process_wall_seconds=.01)
    bundle={'schema':'ump.replay-viewer.v1','observations':'observations.json','variants':variants,
        'sha256':{name:runner.sha(root/name) for name in ['observations.json']+[r['result'] for r in variants]}}
    write(root/'bundle.json',bundle)
    frozen={str(p.relative_to(root)):runner.sha(p) for p in root.rglob('*') if p.is_file() and p.name!='bundle.json'}
    summary={'schema':'ump.mapped-comparison.v1','status':'verified','cases':cases,
        'source':dict(horizon_ms=2000,sampling_period_ms=100,input_observation_contributions=95,peak_observed_simultaneous_tracks=5),
        'protocol':dict(comparison_kind='spatial_resolution_portfolio',observations_sha256=runner.sha(root/'observations.json'),
            binary_sha256=runner.sha(root/'provenance/AggregationReplay'),source_proof_sha256=runner.sha(root/'provenance/capture-proof.json'),
            progress_step_ms=50,pre_execution_artifacts_sha256=frozen)}
    write(root/'summary.json',summary)
    return data,result


class CorrectionProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.mixed=self.root/'mixed';self.ped=self.root/'ped';self.data,self.result=portfolio(self.mixed);portfolio(self.ped)
        self.binary=self.root/'new-binary';self.binary.write_text('new-native-fixture');self.output=self.root/'correction'

    def tearDown(self):self.temp.cleanup()

    def checked(self,*args,**kwargs):
        self.assertEqual(kwargs,{'max_cells':1000000})
        return {'status':'verified','scalar':{'valid':True},'semantic_published_cells':2,
            'suppression_candidates':0,'contribution_selection':'all_contributions',
            'source_accounting':{'input_observations':95,'retained_observations':95,
                'selectively_suppressed_observations':0,'whole_footprint_suppressed_observations':0,
                'by_source_type':{},'by_region':{},'observation_to_release_delay_ms':{'mean':500,'p95':900}}}

    def run_mock(self,cases=None,*,change=None,fail=False):
        calls=[]
        def native(command,**kwargs):
            protocol=runner.read(self.output/'protocol.json')
            self.assertEqual(len(protocol['matrix']),16)
            self.assertEqual(len(list(self.output.glob('*-policy.json'))),16)
            runner.check_frozen(self.output,protocol['pre_execution_artifacts_sha256'])
            self.assertEqual(kwargs['timeout'],240);self.assertNotIn('shell',kwargs)
            self.assertFalse((self.output/'summary.json').exists())
            self.assertEqual(Path(command[0]),self.output/'provenance/AggregationReplay')
            result=copy.deepcopy(self.result)
            output=Path(command[command.index('--output')+1]);write(output,result)
            calls.append(command)
            if change:change(command)
            return subprocess.CompletedProcess(command,1 if fail else 0,'fixture native output\n','fixture failure' if fail else '')
        with mock.patch.object(runner.subprocess,'run',side_effect=native),mock.patch.object(runner,'audit',side_effect=self.checked) as audit,contextlib.redirect_stdout(io.StringIO()):
            result=runner.correction(self.mixed,self.ped,self.output,self.binary,cases=cases)
        return result,calls,audit

    def test_mapped_helper_import_ignores_an_unrelated_cached_module_name(self):
        code=r"""
import pathlib,sys,types
sys.path.insert(0,sys.argv[1])
foreign=types.ModuleType('run_comparison');foreign.origin='unrelated cached evaluation helper'
sys.modules['run_comparison']=foreign
import run_spatial20_correction as runner
assert runner.mapped is not foreign
assert pathlib.Path(runner.mapped.__file__).resolve()==pathlib.Path(sys.argv[2]).resolve()
assert callable(runner.mapped.summarize) and callable(runner.mapped.validate_completed_source)
assert sys.modules['run_comparison'] is foreign, 'Pinned loading must not replace another consumer cache entry'
"""
        process=subprocess.run([sys.executable,'-B','-c',code,str(Path(__file__).resolve().parent),
            str(Path(__file__).resolve().parents[1]/'mapped_scene/run_comparison.py')],
            text=True,capture_output=True,timeout=20)
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)

    def test_matrix_has_eight_primary_six_on_and_two_matched_identity_controls(self):
        rows=runner.matrix();self.assertEqual(len(rows),16);self.assertEqual(len({r['id'] for r in rows}),16)
        self.assertEqual(sum(r['role']=='primary_correction' for r in rows),8)
        self.assertEqual(sum(r['role']=='separate_filtering_sensitivity' for r in rows),6)
        self.assertEqual(sum(r['role']=='fixed_identity_control' for r in rows),2)
        self.assertTrue(all(r['contract']=='spatial20' for r in rows if r['enabled']))
        self.assertEqual(runner.selected_cases([runner.PILOT])[0]['id'],runner.PILOT)
        for bad in ([],['unknown'],[runner.PILOT,runner.PILOT],['all',runner.PILOT]):
            with self.assertRaises(ValueError):runner.selected_cases(bad)

    def test_on_config_changes_only_permission_and_explicit_ids(self):
        source=runner.read(self.mixed/'spatial20_adaptive_immediate-policy.json');before=copy.deepcopy(source)
        on=runner.on_config(source)
        self.assertEqual(source,before);self.assertEqual(on['policy_tree']['root']['semantic_suppression_fraction'],{'max':.1})
        on['policy_tree']['root']['semantic_suppression_fraction']={'max':0}
        on['policy_tree']['id']=source['policy_tree']['id'];on['application_id']=source['application_id']
        self.assertEqual(on,source)

    def test_verified_source_hashes_and_all_original_audits_are_required(self):
        self.assertEqual(len(runner.verify_portfolio(self.mixed)['configs']),16)
        summary=runner.read(self.mixed/'summary.json');summary['cases']['original_fixed_20m_1000ms']['independent_audit']['scalar_valid']=False
        write(self.mixed/'summary.json',summary)
        with self.assertRaisesRegex(ValueError,'independent audit'):runner.verify_portfolio(self.mixed)

    def test_source_policy_result_proof_and_binary_mutations_are_rejected(self):
        for relative in ('observations.json','spatial20_adaptive_immediate-policy.json','spatial20_fixed_20m_1000ms.json','provenance/capture-proof.json','provenance/AggregationReplay'):
            with self.subTest(relative=relative):
                path=self.mixed/relative;before=path.read_bytes();path.write_bytes(before+b' ')
                with self.assertRaises(ValueError):runner.verify_portfolio(self.mixed)
                path.write_bytes(before)

    def test_pilot_freezes_all_commands_and_exact_off_bytes_before_one_execution(self):
        before={str(p.relative_to(self.mixed)):p.read_bytes() for p in self.mixed.rglob('*') if p.is_file()}
        result,calls,audit=self.run_mock([runner.PILOT])
        self.assertEqual(result['status'],'verified');self.assertEqual(result['completion_scope'],'explicit_predeclared_subset')
        self.assertEqual(result['executed_case_count'],1);self.assertEqual(result['planned_case_count'],16)
        self.assertEqual(len(calls),1);self.assertEqual(audit.call_count,1)
        self.assertEqual(result['protocol']['selected_cases'],[runner.PILOT])
        self.assertEqual(len(result['historical_fixed_baselines']),12)
        self.assertTrue(result['cases'][runner.PILOT]['off_policy_byte_identity_verified'])
        for row in runner.matrix():
            if not row['enabled']:
                original=(self.mixed if row['source']=='mixed' else self.ped)/(row['original_case']+'-policy.json')
                self.assertEqual((self.output/(row['id']+'-policy.json')).read_bytes(),original.read_bytes())
        self.assertEqual(before,{str(p.relative_to(self.mixed)):p.read_bytes() for p in self.mixed.rglob('*') if p.is_file()})
        self.assertEqual(result['cases'][runner.PILOT]['native_runtime'],self.result['runtime'])
        self.assertEqual(result['cases'][runner.PILOT]['stats']['source_accounting']['observation_to_release_delay_ms']['p95'],900)

    def test_all_sixteen_and_fixed_logical_identity_are_checked(self):
        result,calls,audit=self.run_mock()
        self.assertEqual(result['completion_scope'],'all_16_predeclared_cases');self.assertEqual(len(calls),16);self.assertEqual(audit.call_count,16)
        for case in result['cases'].values():
            if case['role']=='fixed_identity_control':
                self.assertTrue(case['fixed_release_identity_verified']);self.assertTrue(case['fixed_private_window_identity_verified'])
        self.assertEqual({c[c.index('--fixed-depth')+1] for c in calls if '--fixed-depth' in c},{'2'})
        self.assertEqual({c[c.index('--fixed-window-ms')+1] for c in calls if '--fixed-window-ms' in c},{'1000'})

    def test_midrun_source_or_configuration_change_aborts_without_verified_summary(self):
        def change(command):
            policy=Path(command[command.index('--config')+1]);policy.write_bytes(policy.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'Frozen correction artifact changed'):self.run_mock([runner.PILOT],change=change)
        self.assertFalse((self.output/'summary.json').exists());self.assertTrue((self.output/'protocol.json').exists())

    def test_native_failure_preserves_receipt_but_never_writes_verified_summary(self):
        with self.assertRaisesRegex(ValueError,'native execution failed'):self.run_mock([runner.PILOT],fail=True)
        self.assertFalse((self.output/'summary.json').exists());self.assertTrue((self.output/(runner.PILOT+'-execution.json')).exists())

    def test_existing_output_and_invalid_budget_fail_before_any_native_work(self):
        self.output.mkdir();(self.output/'keep').write_text('keep')
        with mock.patch.object(runner.subprocess,'run') as native:
            with self.assertRaisesRegex(ValueError,'fresh'):runner.correction(self.mixed,self.ped,self.output,self.binary)
            native.assert_not_called()
        self.assertEqual((self.output/'keep').read_text(),'keep')
        for budget in (0,241,True,1.5):
            with self.assertRaisesRegex(ValueError,'wall budget'):runner.correction(self.mixed,self.ped,self.root/'other',self.binary,wall_budget_s=budget)

    def test_accounting_conservation_and_failed_independent_audit_cannot_pass(self):
        checked=self.checked(max_cells=1000000);config=runner.read(self.mixed/'spatial20_adaptive_immediate-policy.json')
        checked['source_accounting']['retained_observations']=94
        with self.assertRaisesRegex(ValueError,'accounting'):runner.summarize(self.data,config,self.result,checked)
        checked=self.checked(max_cells=1000000);checked['status']='failed'
        with self.assertRaisesRegex(ValueError,'audit did not pass'):runner.summarize(self.data,config,self.result,checked)


if __name__=='__main__':unittest.main()
