"""Primary-slot provenance, TEST gate and no-retry tests; no source generation.

All sources, groups and locks below are synthetic. The maintained capture helper
has separate native/process timeout tests; this suite verifies wrapper delegation
and freeze/gate boundaries without MongoDB, TEST observations or mechanism scores.
"""
from copy import deepcopy
import json
import fcntl
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import run_urban_privacy_primary_sources as runner
import urban_privacy_analysis as analysis


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def observations(offset=0):
    return {'schema': 'ump.observation-replay.v1', 'run_id': 'fixture', 'sensor_id': 'fixture',
            'coverage': {'x': 0, 'y': 0, 'width': 80, 'height': 80, 'leaf_depth': 6},
            'sampling_period_ms': 100, 'end_ms': 300000,
            'batches': [{'sequence': 1, 'observed_at_ms': 100, 'status': 'measured',
                         'observations': [{'id': 'fixture-track', 'type': 'Adult Pedestrian',
                                           'x': 1+offset, 'y': 2, 'cell_id': 12288}]}]}


class PrimarySourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.results = self.root / 'results'; self.results.mkdir()
        self.freeze = self.results / 'freeze'; self.freeze.mkdir()
        self.output = self.results / 'primary'
        self.code = self.root / 'source.py'; self.code.write_text('frozen fixture source\n')
        self.pilot_path = self.results / 'dev/protocol.json'
        self.pilot = {'schema': 'ump.urban-privacy-sources-protocol.v1',
                      'frozen_files_sha256': {str(self.code): runner.source.sha(self.code)},
                      'source_horizon_ms': 300000, 'process_wall_budget_s': 420,
                      'physical_audit_wall_budget_s': 420,
                      'max_capture_mib': 2048, 'max_capture_bytes': 2147483648,
                      'failure_rule': 'One attempt per slot; retain every failure.'}
        dump(self.pilot_path, self.pilot)
        groups = []
        for split, count in (('train',24),('calibration',16),('test',32)):
            for index in range(count):
                slot = len(groups)
                groups.append({'group_id': f'fixture-g{slot:03}', 'split': split,
                               'seeds': {'source_generation': 2**50 + slot * 3,
                                         'target_selection': 2**50 + slot * 3+1,
                                         'auxiliary_selection': 2**50 + slot * 3+2},
                               'source_state': 'planned_not_generated'})
        self.manifest = {'groups': groups, 'exclusions': [],
                         'design': {'group_counts': {'train':24,'calibration':16,'test':32},
                                    'methods':[{'id':f'fixture-method-{i}'} for i in range(11)],
                                    'generator': {'evidence_files': [
                                        {'path': str(self.pilot_path.relative_to(self.root)),
                                         'sha256': runner.source.sha(self.pilot_path)},
                                        {'path': 'source.py', 'sha256': runner.source.sha(self.code)}]}}}
        dump(self.freeze / 'manifest.json', self.manifest)
        self.manifest_sha = runner.source.sha(self.freeze / 'manifest.json')
        self.patches = [mock.patch.object(runner,'ROOT',self.root),
                        mock.patch.object(runner.source,'ROOT',self.root),
                        mock.patch.object(runner.split,'verify_freeze',return_value={'manifest_sha256':self.manifest_sha}),
                        mock.patch.object(runner.source,'frozen_check'),
                        mock.patch.object(runner.fixture,'new_output',side_effect=self.new_output)]
        for patch in self.patches: patch.start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(self.temp.cleanup)

    def new_output(self,path):
        self.assertTrue(path.is_relative_to(self.results))
        path.mkdir(mode=0o700)
        return path

    def prepared(self):
        runner.prepare(self.freeze,self.output)
        return runner.read_protocol(self.output)[1]

    def receipt(self,row,status='failed',offset=0,route=None,**extra):
        directory=self.output/row['id']; directory.mkdir(exist_ok=True)
        value={key: row[key] for key in ('id','group_id','seed','scene_directory','replay_directory')}
        value['status']=status
        if status=='verified':
            data=observations(offset)
            dump(Path(row['replay_directory'])/'observations.json',data)
            value.update(observations_sha256=runner.source.sha(Path(row['replay_directory'])/'observations.json'),
                         normalized_source_fingerprint=runner.split.normalized_fingerprint(data,legacy=True),
                         planned_route_fingerprint=route or runner.source.digest(['route',offset]))
        value.update(extra)
        dump(directory/'private-source-summary.json',value)
        return value

    def fake_attempt(self,output,protocol,row):
        self.assertEqual(output,self.output)
        return self.receipt(row)

    def summary(self,protocol,verify=False):
        return runner.summarize(self.output,protocol,self.manifest,verify=verify)

    def gate_fixture(self):
        self.prepared()
        directory=self.results/'implementation'; directory.mkdir()
        names=('run_urban_privacy_primary_sources.py','run_urban_privacy_primary.py',
               'urban_privacy_statistics.py','urban_privacy_queries.py','urban_privacy_analysis.py',
               'test_run_urban_privacy_primary_sources.py','test_run_urban_privacy_primary.py',
               'test_urban_privacy_statistics.py','test_urban_privacy_queries.py','test_urban_privacy_analysis.py')
        hashes={}
        for name in names:
            relative='tools/evaluation/'+name
            path=self.root/relative; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('Synthetic implementation-evidence fixture: '+name+'\n')
            hashes[relative]=runner.source.sha(path)
        receipts=[]
        for name in ('unit-validation.json','dev-integration.json'):
            dump(directory/name,{'status':'pass','synthetic_test_fixture':True})
            receipts.append({'path':name,'sha256':runner.source.sha(directory/name)})
        implementation=directory/'supplement.json'
        supplement={'schema':'ump.urban-primary-implementation.v1','status':'verified_before_test',
                    'manifest_sha256':self.manifest_sha,'freeze_directory':str(self.freeze),
                    'files_sha256':hashes,'test_receipts':receipts}
        dump(implementation,supplement)
        expected={role:[g['group_id'] for g in self.manifest['groups'] if g['split']==role]
                  for role in ('train','calibration','test')}
        methods=[row['id'] for row in self.manifest['design']['methods']]
        data=[{'group_id':group['group_id'],'split':group['split'],'method_id':method,
               'world':world,'label':label,'features':[0.]*111,'scalar_features':[0.]*31,
               'auxiliary_features':[1.,0.,0.,0.,0.,0.,0.,0.],
               'controls':{'prior_only':.5,'unprotected':float(label),'no_output_features':[0.]*111},
               'utility':{}}
              for group in self.manifest['groups'] if group['split']!='test'
              for method in methods for world,label in (('IN',1),('OUT',0))]
        fitted=analysis.prepare_models(data,expected_groups=expected,method_ids=methods)
        self.assertEqual(analysis.validate_model_lock(fitted,data)['status'],'verified')
        dump(directory/'fitted.json',fitted);dump(directory/'data.json',data)
        lock=directory/'lock.json'
        models={'schema':'ump.urban-primary-model-lock.v1','status':'locked_before_test',
                'manifest_sha256':self.manifest_sha,'implementation_sha256':runner.source.sha(implementation),
                'group_counts':{'train':24,'calibration':16},'test_rows_seen':0,
                'implementation_files_sha256':hashes,
                'models':{'path':'fitted.json','sha256':runner.source.sha(directory/'fitted.json')},
                'data':{'path':'data.json','sha256':runner.source.sha(directory/'data.json')}}
        dump(lock,models)
        return implementation,lock,supplement,models,fitted,data

    def test_prepares_exact_group_seed_roles_paths_and_capture_law_before_execution(self):
        with mock.patch.object(runner.source,'attempt') as attempt:
            protocol=self.prepared()
        attempt.assert_not_called()
        self.assertEqual(len(protocol['cases']),72)
        self.assertEqual(protocol['planned_group_counts'],{'train':24,'calibration':16,'test':32})
        self.assertEqual(protocol['process_wall_budget_s'],420)
        self.assertEqual(protocol['physical_audit_wall_budget_s'],420)
        self.assertEqual(protocol['max_capture_bytes'],2*1024**3)
        self.assertEqual(protocol['minimum_free_bytes'],3*1024**3)
        for group,row in zip(self.manifest['groups'],protocol['cases']):
            self.assertEqual(row['group_id'],group['group_id'])
            self.assertEqual(row['seed'],group['seeds']['source_generation'])
            self.assertEqual(row['split'],group['split'])
            self.assertEqual(row['command'],runner.source.command(self.output,row['seed']))
            self.assertEqual(row['audit_command'],runner.source.audit_command(self.output,row['seed']))
            self.assertEqual(row['command'][row['command'].index('--seed')+1],str(row['seed']))
            self.assertNotIn('--cleanup',row['command'])
        self.assertEqual(protocol['manifest_sha256'],self.manifest_sha)

    def test_prepare_is_no_overwrite_and_authenticates_frozen_evidence(self):
        self.prepared()
        with self.assertRaises(FileExistsError):
            runner.prepare(self.freeze,self.output)
        self.code.write_text('changed law')
        with self.assertRaisesRegex(ValueError,'Frozen implementation changed'):
            runner.prepare(self.freeze,self.results/'another')

    def test_resume_protocol_rejects_manifest_and_case_tampering_even_with_new_protocol_digest(self):
        protocol=self.prepared()
        for field,value in (('seed',123),('split','test'),('group_id','other'),('command',['fake'])):
            changed=deepcopy(protocol); changed['cases'][0][field]=value
            dump(self.output/'protocol.json',changed)
            (self.output/'protocol.sha256').write_text(runner.source.sha(self.output/'protocol.json')+'\n')
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'assignment changed'):
                runner.read_protocol(self.output)
        dump(self.output/'protocol.json',protocol)
        (self.output/'protocol.sha256').write_text(runner.source.sha(self.output/'protocol.json')+'\n')
        dump(self.freeze/'manifest.json',{'changed':True})
        with self.assertRaisesRegex(ValueError,'Frozen main design changed'):
            runner.read_protocol(self.output)

    def test_all_failed_interrupted_and_not_attempted_slots_remain_in_split_denominators(self):
        protocol=self.prepared()
        self.receipt(protocol['cases'][0],status='timeout')
        self.receipt(protocol['cases'][24],status='invalid')
        (self.output/protocol['cases'][40]['id']).mkdir()
        report=self.summary(protocol)
        self.assertEqual(report['planned_count'],72)
        self.assertEqual(report['attempted_count'],3)
        self.assertEqual(report['verified_count'],0)
        self.assertEqual(report['status'],'incomplete')
        self.assertEqual(sum(report['by_split']['train'].values()),24)
        self.assertEqual(sum(report['by_split']['calibration'].values()),16)
        self.assertEqual(sum(report['by_split']['test'].values()),32)
        self.assertEqual(report['by_split']['train']['timeout'],1)
        self.assertEqual(report['by_split']['test']['interrupted'],1)

    def test_verified_capture_is_reauthenticated_and_rejected_if_audit_changes(self):
        protocol=self.prepared(); row=protocol['cases'][0]
        self.receipt(row,status='verified')
        with mock.patch.object(runner.source,'validate_capture',side_effect=ValueError('changed physical audit')):
            report=self.summary(protocol,verify=True)
        self.assertEqual(report['cases'][0]['status'],'invalid')
        self.assertIn('changed physical audit',report['cases'][0]['error'])

    def test_duplicate_source_or_route_invalidates_both_slots_without_replacement(self):
        for same_route in (False,True):
            with self.subTest(same_route=same_route):
                if self.output.exists():
                    import shutil
                    shutil.rmtree(self.output)
                protocol=self.prepared()
                self.receipt(protocol['cases'][0],status='verified',offset=0,route='shared')
                self.receipt(protocol['cases'][1],status='verified',offset=1 if same_route else 0,route='shared' if same_route else 'other')
                report=self.summary(protocol)
                self.assertEqual([r['status'] for r in report['cases'][:2]],['invalid_duplicate']*2)
                self.assertEqual(report['attempted_count'],2)
                self.assertEqual(report['verified_count'],0)

    def test_excluded_dev_fingerprint_cannot_become_a_primary_group(self):
        protocol=self.prepared(); row=protocol['cases'][0]
        saved=self.receipt(row,status='verified')
        self.manifest['exclusions']=[{'normalized_source_fingerprint':saved['normalized_source_fingerprint']}]
        report=self.summary(protocol)
        self.assertEqual(report['cases'][0]['status'],'invalid')
        self.assertIn('excluded DEV',report['cases'][0]['error'])

    def test_resume_selects_requested_split_uses_same_helper_and_never_retries(self):
        self.prepared()
        with mock.patch.object(runner,'snapshot'),mock.patch.object(runner.source,'attempt',side_effect=self.fake_attempt) as attempt:
            runner.resume(self.output,['train'],limit=1)
            first=attempt.call_args.args[2]
            self.assertEqual(first['split'],'train')
            runner.resume(self.output,['train'],limit=1)
            second=attempt.call_args.args[2]
            self.assertEqual(second['split'],'train')
            self.assertNotEqual(first['id'],second['id'])
            self.assertEqual(attempt.call_count,2)
            runner.resume(self.output,['calibration'],limit=1)
            self.assertEqual(attempt.call_args.args[2]['split'],'calibration')
            self.assertEqual(attempt.call_args.args[1]['process_wall_budget_s'],420)

    def test_low_storage_stops_before_any_attempt(self):
        self.prepared()
        with mock.patch.object(runner,'snapshot'),mock.patch.object(runner.shutil,'disk_usage',return_value=mock.Mock(free=3*1024**3-1)),mock.patch.object(runner.source,'attempt') as attempt:
            with self.assertRaisesRegex(ValueError,'3 GiB'):
                runner.resume(self.output,['train'],limit=1)
        attempt.assert_not_called()

    def test_test_requires_authentication_before_any_snapshot_or_attempt(self):
        self.prepared()
        with mock.patch.object(runner,'snapshot') as snapshot,mock.patch.object(runner.source,'attempt') as attempt:
            with self.assertRaisesRegex(ValueError,'TEST needs'):
                runner.resume(self.output,['test'],limit=1)
        snapshot.assert_not_called(); attempt.assert_not_called()

    def test_self_asserted_empty_supplement_and_model_counts_do_not_unlock_test(self):
        self.prepared()
        implementation=self.results/'implementation.json'
        lock=self.results/'models.json'
        supplement={'schema':'ump.urban-primary-implementation.v1','status':'verified_before_test',
                    'manifest_sha256':self.manifest_sha,'files_sha256':{},'test_receipts':[]}
        dump(implementation,supplement)
        dump(lock,{'schema':'ump.urban-primary-model-lock.v1','status':'locked_before_test',
                   'manifest_sha256':self.manifest_sha,'implementation_sha256':runner.source.sha(implementation),
                   'group_counts':{'train':24,'calibration':16},'test_rows_seen':0,'implementation_files_sha256':{}})
        with self.assertRaises((ValueError,KeyError)):
            runner.authenticate_test_gate(implementation,lock,self.manifest_sha)

    def test_preexisting_running_lock_prevents_concurrent_source_launch(self):
        self.prepared()
        descriptor=os.open(self.output/'.running.lock',os.O_WRONLY|os.O_CREAT,0o600)
        try:
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with mock.patch.object(runner,'snapshot'),mock.patch.object(runner.source,'attempt') as attempt:
                with self.assertRaisesRegex(ValueError,'lock|running|runner|concurrent'):
                    runner.resume(self.output,['train'],limit=1)
            attempt.assert_not_called()
        finally:
            fcntl.flock(descriptor,fcntl.LOCK_UN)
            os.close(descriptor)

    def test_saved_receipt_cannot_override_predeclared_split(self):
        protocol=self.prepared(); row=protocol['cases'][0]
        self.receipt(row,status='failed',split='test')
        try:
            report=self.summary(protocol)
        except ValueError:
            return
        self.assertEqual(report['cases'][0]['split'],row['split'])
        self.assertEqual(sum(report['by_split']['train'].values()),24)


    def test_actual_synthetic_train_cal_models_and_hash_bound_evidence_unlock_gate(self):
        implementation,lock,_,models,_,_=self.gate_fixture()
        actual=runner.authenticate_test_gate(implementation,lock,self.manifest_sha)
        self.assertEqual(actual,models)

    def test_supplement_code_and_validation_receipts_are_reauthenticated(self):
        implementation,lock,supplement,_,_,_=self.gate_fixture()
        receipt=implementation.parent/supplement['test_receipts'][0]['path']
        original=receipt.read_bytes();receipt.write_text('altered validation')
        with self.assertRaisesRegex(ValueError,'validation receipt changed'):
            runner.authenticate_test_gate(implementation,lock,self.manifest_sha)
        receipt.write_bytes(original)
        code=self.root/next(iter(supplement['files_sha256']))
        code.write_text('altered implementation')
        with self.assertRaisesRegex(ValueError,'implementation changed'):
            runner.authenticate_test_gate(implementation,lock,self.manifest_sha)

    def test_model_bytes_and_rows_are_reauthenticated_not_only_claimed_counts(self):
        implementation,lock,_,models,fitted,data=self.gate_fixture()
        artifact=lock.parent/'fitted.json';original=artifact.read_bytes()
        artifact.write_text('{}')
        with self.assertRaisesRegex(ValueError,'hash|provenance'):
            runner.authenticate_test_gate(implementation,lock,self.manifest_sha)
        artifact.write_bytes(original)
        # Rebinding a changed data hash cannot hide duplicate method/world rows.
        data[0]=deepcopy(data[1]);dump(lock.parent/'data.json',data)
        models['data']['sha256']=runner.source.sha(lock.parent/'data.json');dump(lock,models)
        with self.assertRaisesRegex(ValueError,'Duplicate|rows|digest|pairs'):
            runner.authenticate_test_gate(implementation,lock,self.manifest_sha)

    def test_hash_rebound_model_family_and_wrong_manifest_are_rejected(self):
        implementation,lock,supplement,models,fitted,_=self.gate_fixture()
        fitted['models'].pop()
        fitted['prepared_sha256']=analysis.digest({k:v for k,v in fitted.items() if k!='prepared_sha256'})
        dump(lock.parent/'fitted.json',fitted)
        models['models']['sha256']=runner.source.sha(lock.parent/'fitted.json');dump(lock,models)
        with self.assertRaisesRegex(ValueError,'family|model list'):
            runner.authenticate_test_gate(implementation,lock,self.manifest_sha)
        # A different manifest is forbidden even when a supplement points to it.
        changed=self.results/'other-freeze';changed.mkdir()
        dump(changed/'manifest.json',{'groups':[],'design':{'methods':[]}})
        supplement['freeze_directory']=str(changed);dump(implementation,supplement)
        models['implementation_sha256']=runner.source.sha(implementation);dump(lock,models)
        with self.assertRaisesRegex(ValueError,'manifest|Manifest'):
            runner.authenticate_test_gate(implementation,lock,self.manifest_sha)


if __name__=='__main__':
    unittest.main()
