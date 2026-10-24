"""Scientific orchestration checks without motion generation or timed jobs."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import run_strategy_window_extension as runner
import test_run_spatial20_correction as fixtures


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


class StrategyWindowExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.mixed=self.root/'mixed';self.ped=self.root/'ped'
        self.data,self.result=fixtures.portfolio(self.mixed);fixtures.portfolio(self.ped)
        self.binary=self.root/'AggregationReplay';self.binary.write_text('corrected-native-fixture')
        self.output=self.root/'extension';self.corrected=self.root/'corrected';self.corrected.mkdir()
        self.accounting={'input_observations':95,'retained_observations':95,
            'selectively_suppressed_observations':0,'whole_footprint_suppressed_observations':0,
            'by_source_type':{},'by_region':{},'observation_to_release_delay_ms':{'mean':500,'p95':900}}
        for root in (self.mixed,self.ped):
            summary=runner.read(root/'summary.json')
            for case in summary['cases'].values():case['stats']['source_accounting']=copy.deepcopy(self.accounting)
            write(root/'summary.json',summary)
        sources={name:runner.helper.verify_portfolio(path) for name,path in (('mixed',self.mixed),('pedestrians',self.ped))}
        protocol={'native_binary_sha256':runner.sha(self.binary),'sources':{name:{
            'summary_sha256':source['summary_sha256'],'observations_sha256':source['observations_sha256']}
            for name,source in sources.items()}}
        write(self.corrected/'protocol.json',protocol)
        cases={}
        for name,source in sources.items():
            for contract in runner.CONTRACTS:
                for method in ('adaptive_immediate','adaptive_spatial_first'):
                    identifier=f'{name}_{contract}_{method}_off';prior=source['references'][contract+'_'+method]
                    config=source['configs'][contract+'_'+method]
                    (self.corrected/(identifier+'-policy.json')).write_bytes(config.read_bytes())
                    cases[identifier]={**copy.deepcopy(prior),'off_policy_byte_identity_verified':True}
        write(self.corrected/'summary.json',dict(schema='ump.spatial20-correction.v1',status='verified',
            completion_scope='all_16_predeclared_cases',executed_case_count=16,planned_case_count=16,
            protocol=protocol,protocol_sha256=runner.sha(self.corrected/'protocol.json'),cases=cases))

    def tearDown(self):self.temp.cleanup()

    def checked(self,*args,**kwargs):
        self.assertEqual(kwargs,{'max_cells':1000000})
        return {'status':'verified','scalar':{'valid':True},'semantic_published_cells':2,
            'suppression_candidates':0,'contribution_selection':'all_contributions',
            'source_accounting':copy.deepcopy(self.accounting)}

    def run_mock(self,cases=None,*,change=None,fail=False):
        calls=[]
        def native(command,**kwargs):
            protocol=runner.read(self.output/'protocol.json')
            self.assertEqual(len(protocol['matrix']),28)
            self.assertEqual(len(list(self.output.glob('*-policy.json'))),28)
            self.assertFalse((self.output/'summary.json').exists())
            runner.helper.check_frozen(self.output,protocol['pre_execution_artifacts_sha256'])
            self.assertEqual(kwargs['timeout'],240);self.assertNotIn('shell',kwargs)
            self.assertEqual(Path(command[0]),self.output/'provenance/AggregationReplay')
            write(Path(command[command.index('--output')+1]),self.result);calls.append(command)
            if change:change(command)
            return subprocess.CompletedProcess(command,1 if fail else 0,'mock native\n','failure' if fail else '')
        with mock.patch.object(runner.subprocess,'run',side_effect=native),\
             mock.patch.object(runner.helper,'audit',side_effect=self.checked) as audit,\
             contextlib.redirect_stdout(io.StringIO()):
            result=runner.extension(self.mixed,self.ped,self.corrected,self.output,self.binary,cases=cases)
        return result,calls,audit

    def test_matrix_covers_both_streams_contracts_and_all_long_fixed_controls(self):
        rows=runner.matrix();self.assertEqual(len(rows),28);self.assertEqual(len({r['id'] for r in rows}),28)
        for source in runner.SOURCES:
            for contract in runner.CONTRACTS:
                cohort=[r for r in rows if r['source']==source and r['contract']==contract]
                self.assertEqual(len(cohort),7)
                self.assertEqual(sum(r['mode']=='temporal_first' for r in cohort),1)
                self.assertEqual({(r['fixed_depth'],r['fixed_window_ms']) for r in cohort if r['mode']=='fixed'},
                    {(depth,window) for depth in (4,3,2) for window in (2000,4000)})
        self.assertTrue(all(r['enabled'] is False for r in rows))
        for bad in ([],['unknown'],[runner.PILOT,runner.PILOT],['all',runner.PILOT]):
            with self.assertRaises(ValueError):runner.selected_cases(bad)

    def test_temporal_first_changes_only_explicit_strategy_secondary_and_ids(self):
        original=runner.read(self.mixed/'spatial20_adaptive_immediate-policy.json');before=copy.deepcopy(original)
        row=next(r for r in runner.matrix() if r['id']==runner.PILOT)
        config=runner.config_for(original,row)
        self.assertEqual(config['policy_tree']['execution']['strategy'],'temporal_first')
        self.assertNotIn('semantic_secondary_strategy',config['policy_tree']['execution'])
        self.assertEqual(runner.hard_policy(config),runner.hard_policy(original));self.assertEqual(original,before)
        config['application_id']=original['application_id'];config['policy_tree']['id']=original['policy_tree']['id']
        config['policy_tree']['execution']=original['policy_tree']['execution']
        self.assertEqual(config,original)
        original['policy_tree']['root']['semantic_suppression_fraction']={'max':.1}
        with self.assertRaisesRegex(ValueError,'OFF-only'):runner.config_for(original,row)

    def test_fixed_controls_do_not_relax_regional_time_or_space_bounds(self):
        original=runner.read(self.mixed/'original_adaptive_immediate-policy.json')
        for row in runner.matrix():
            if row['mode']!='fixed':continue
            config=runner.config_for(original,row)
            self.assertEqual(runner.hard_policy(config),runner.hard_policy(original))
            self.assertEqual(config['policy_tree']['execution'],original['policy_tree']['execution'])
            self.assertEqual(config['policy_regions'],original['policy_regions'])
            self.assertEqual(config['window_ms'],400)

    def test_all_predeclared_artifacts_are_frozen_before_pilot_and_references_are_hashed(self):
        before={str(p.relative_to(self.mixed)):p.read_bytes() for p in self.mixed.rglob('*') if p.is_file()}
        result,calls,audit=self.run_mock([runner.PILOT])
        self.assertEqual(result['completion_scope'],'explicit_predeclared_subset')
        self.assertEqual(result['planned_case_count'],28);self.assertEqual(result['executed_case_count'],1)
        self.assertEqual(len(calls),1);self.assertEqual(audit.call_count,1)
        self.assertEqual(len(result['reference_cases']),32);self.assertEqual(len(result['comparison_rows']),33)
        self.assertEqual(result['protocol']['selected_cases'],[runner.PILOT])
        self.assertTrue(result['cases'][runner.PILOT]['hard_policy_identity_verified'])
        self.assertEqual(result['protocol']['corrected_reference_summary_sha256'],runner.sha(self.corrected/'summary.json'))
        self.assertEqual(before,{str(p.relative_to(self.mixed)):p.read_bytes() for p in self.mixed.rglob('*') if p.is_file()})
        self.assertTrue((self.output/'report.md').is_file())

    def test_all_28_cases_and_independent_audits_and_fixed_cli_parameters(self):
        result,calls,audit=self.run_mock()
        self.assertEqual(result['completion_scope'],'all_28_predeclared_cases')
        self.assertEqual(len(calls),28);self.assertEqual(audit.call_count,28)
        self.assertEqual({c[c.index('--fixed-depth')+1] for c in calls if '--fixed-depth' in c},{'2','3','4'})
        self.assertEqual({c[c.index('--fixed-window-ms')+1] for c in calls if '--fixed-window-ms' in c},{'2000','4000'})
        self.assertEqual(sum(c[c.index('--mode')+1]=='temporal_first' for c in calls),4)

    def test_reference_wrong_binary_source_or_audit_is_rejected_before_execution(self):
        self.binary.write_text('different-native')
        with mock.patch.object(runner.subprocess,'run') as native:
            with self.assertRaisesRegex(ValueError,'same corrected binary'):
                runner.extension(self.mixed,self.ped,self.corrected,self.output,self.binary)
            native.assert_not_called()
        self.assertFalse(self.output.exists())
        self.binary.write_text('corrected-native-fixture')
        summary=runner.read(self.corrected/'summary.json')
        first=next(iter(summary['cases'].values()));first['independent_audit']['published_policy_violations']=1
        write(self.corrected/'summary.json',summary)
        with self.assertRaisesRegex(ValueError,'Unverified reference'):
            runner.extension(self.mixed,self.ped,self.corrected,self.output,self.binary)
        self.assertFalse(self.output.exists())

    def test_source_and_frozen_config_mutations_abort_without_verified_summary(self):
        def change(command):
            policy=Path(command[command.index('--config')+1]);policy.write_bytes(policy.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'Frozen correction artifact changed'):
            self.run_mock([runner.PILOT],change=change)
        self.assertFalse((self.output/'summary.json').exists())
        self.assertTrue((self.output/'protocol.json').exists())

    def test_failed_native_keeps_execution_receipt_and_never_claims_verified(self):
        with self.assertRaisesRegex(ValueError,'native execution failed'):self.run_mock([runner.PILOT],fail=True)
        self.assertFalse((self.output/'summary.json').exists())
        receipt=runner.read(self.output/(runner.PILOT+'-execution.json'));self.assertEqual(receipt['returncode'],1)

    def test_existing_output_and_invalid_budgets_leave_user_files_untouched(self):
        self.output.mkdir();(self.output/'keep').write_text('keep')
        with mock.patch.object(runner.subprocess,'run') as native:
            with self.assertRaisesRegex(ValueError,'fresh'):
                runner.extension(self.mixed,self.ped,self.corrected,self.output,self.binary)
            native.assert_not_called()
        self.assertEqual((self.output/'keep').read_text(),'keep')
        for budget in (0,241,True,1.1):
            with self.assertRaisesRegex(ValueError,'wall budget'):
                runner.extension(self.mixed,self.ped,self.corrected,self.root/'new',self.binary,wall_budget_s=budget)

    def test_failed_audit_and_unconserved_input_cannot_be_reported(self):
        checked=self.checked(max_cells=1000000);checked['source_accounting']['retained_observations']=94
        with self.assertRaisesRegex(ValueError,'accounting'):
            runner.helper.summarize(self.data,runner.read(self.mixed/'original_adaptive_immediate-policy.json'),self.result,checked)
        checked=self.checked(max_cells=1000000);checked['status']='failed'
        with self.assertRaisesRegex(ValueError,'audit did not pass'):
            runner.helper.summarize(self.data,runner.read(self.mixed/'original_adaptive_immediate-policy.json'),self.result,checked)


if __name__=='__main__':unittest.main()
