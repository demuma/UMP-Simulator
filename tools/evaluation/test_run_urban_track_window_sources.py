"""Synthetic source-import, immutable-role, profile and TEST-gate regressions.

No primary observations, raw GT, native executable, MongoDB or fitted model is
used. The maintained split/physical/recording validators have separate tests;
these fixtures exercise adapter orchestration with explicitly mocked boundaries.
All paths, identities, code bytes and receipt payloads below are synthetic.
"""
from copy import deepcopy
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import run_urban_track_window_sources as runner


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def observations(index):
    return dict(schema='ump.observation-replay.v1', run_id='synthetic-run', sensor_id='synthetic-sensor',
        coverage=dict(x=0, y=0, width=80, height=80, leaf_depth=6), end_ms=300000, sampling_period_ms=100,
        batches=[dict(sequence=i, observed_at_ms=100*i, status='measured', observations=[
            dict(id='synthetic-track', type='Adult Pedestrian', x=1+index/100, y=i, cell_id=12288)]) for i in (1, 2)])


class TrackWindowSourceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.results = self.root/'results'; self.results.mkdir()
        self.freeze = self.results/'freeze'; self.freeze.mkdir()
        self.legacy = self.results/'legacy'; self.legacy.mkdir()
        self.strict = self.results/'strict'; (self.strict/'groups').mkdir(parents=True)
        self.output = self.results/'windowed'
        self.code = self.root/'source-dependency.py'; self.code.write_text('unchanged synthetic source dependency\n')
        self.auditor = self.root/'tools/mapped_scene/audit_building_access.py'; self.auditor.parent.mkdir(parents=True)
        self.auditor.write_text('original strict synthetic auditor\n')
        self.evaluation = self.root/'tools/evaluation'; self.evaluation.mkdir(parents=True)
        self.primary = self.evaluation/'run_urban_privacy_primary.py'; self.primary.write_text('original generic primitive\n')
        for name in ('run_urban_track_window_sources.py', 'track_window_source_validation.py'):
            (self.evaluation/name).write_text('synthetic new adapter dependency: '+name+'\n')
        self.binary = self.root/'simulator/build/Simulator'; self.binary.parent.mkdir(parents=True)
        self.binary.write_bytes(b'never executed synthetic native binary')
        self.archived_auditor = self.results/'original-auditor.py'; self.archived_auditor.write_bytes(self.auditor.read_bytes())
        self.archived_primary = self.results/'original-primary.py'; self.archived_primary.write_bytes(self.primary.read_bytes())
        self.manifest = dict(groups=[], exclusions=[])
        for split, count in (('train',24),('calibration',16),('test',32)):
            for _ in range(count):
                index = len(self.manifest['groups'])
                self.manifest['groups'].append(dict(group_id=f'synthetic-g{index:03d}', split=split,
                    seeds=dict(source_generation=2**50+index*3, target_selection=2**50+index*3+1,
                               auxiliary_selection=2**50+index*3+2), target_slots=[0]))
        dump(self.freeze/'manifest.json', self.manifest)
        self.manifest_sha = runner.source.sha(self.freeze/'manifest.json')
        self.environment = dict(synthetic_environment='no native/database/model work')
        self.patches = [mock.patch.object(runner, 'ROOT', self.root),
            mock.patch.object(runner.source, 'ROOT', self.root), \
            mock.patch.object(runner.validation, 'AUDITOR', self.auditor), \
            mock.patch.object(runner.split, 'validate_manifest'), \
            mock.patch.object(runner.source, 'environment', return_value=self.environment), \
            mock.patch.object(runner.source, 'source_paths', return_value=[self.code,self.auditor,self.primary]), \
            mock.patch.object(runner.source.fixture, 'new_output', side_effect=self.new_output), \
            mock.patch.object(runner.validation, 'validate_capture', side_effect=self.valid_capture)]
        for patch in self.patches: patch.start()
        self.addCleanup(mock.patch.stopall); self.addCleanup(self.temp.cleanup)
        self.old = dict(schema='ump.urban-primary-source-protocol.v1', freeze_directory=str(self.freeze),
            manifest_sha256=self.manifest_sha, historical_scene=str(self.legacy), environment=self.environment,
            simulator_path=str(self.binary), simulator_sha256=runner.source.sha(self.binary), source_horizon_ms=300000,
            process_wall_budget_s=420, physical_audit_wall_budget_s=420,
            frozen_files_sha256={str(p):runner.source.sha(p) for p in (self.code,self.auditor,self.primary,self.binary)},
            frozen_manifest_files_sha256={str(self.freeze/'manifest.json'): self.manifest_sha},
            cases=[])
        for index, group in enumerate(self.manifest['groups']):
            seed = group['seeds']['source_generation']; name='seed'+str(seed)
            row = dict(id=name,group_id=group['group_id'],split=group['split'],seed=seed,
                scene_directory=str(self.legacy/name/'scene'),replay_directory=str(self.legacy/name/'replay'),
                command=runner.source.command(self.legacy,seed),audit_command=runner.source.audit_command(self.legacy,seed))
            self.old['cases'].append(row)
            if group['split'] == 'test': continue
            scene,replay=Path(row['scene_directory']),Path(row['replay_directory'])
            scene.mkdir(parents=True); replay.mkdir()
            dump(replay/'capture-proof.json',dict(synthetic_proof=index))
            dump(replay/'observations.json',observations(index))
            value={key:row[key] for key in ('id','group_id','split','seed','scene_directory','replay_directory')}
            value['status']='invalid' if index==0 else 'verified'
            dump(scene.parent/'private-source-summary.json',value)
            dump(scene.parent/'motion-audit.json',dict(status='pass',synthetic_audit=index))
            dump(scene.parent/'audit-execution.json',dict(status='complete',returncode=0,command=row['audit_command']))
        self.rewrite_legacy()
        dump(self.strict/'driver-failed.json',dict(status='failed_or_interrupted',completed=['source_train_cal']))
        dump(self.strict/'train-cal-driver-source-gate.json',dict(status='failed',expected=40,observed=40))
        self.stdout=io.StringIO(); self.redirect=contextlib.redirect_stdout(self.stdout); self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def rewrite_legacy(self):
        dump(self.legacy/'protocol.json',self.old)
        (self.legacy/'protocol.sha256').write_text(runner.source.sha(self.legacy/'protocol.json')+'\n')
        strict = dict(schema='ump.urban-primary-execution.v1',source_directory=str(self.legacy),
            source_protocol_sha256=runner.source.sha(self.legacy/'protocol.json'),freeze_directory=str(self.freeze),manifest_sha256=self.manifest_sha)
        dump(self.strict/'protocol.json',strict)
        (self.strict/'protocol.sha256').write_text(runner.source.sha(self.strict/'protocol.json')+'\n')

    def new_output(self,path):
        self.assertTrue(path.is_relative_to(self.results))
        path.mkdir(mode=0o700)
        return path

    def valid_capture(self,row,protocol):
        self.assertEqual(protocol['schema'],runner.SCHEMA)
        self.assertEqual(protocol['source_validation_profile'],runner.PROFILE)
        data=runner.source.load(Path(row['replay_directory'])/'observations.json')
        return dict(status='verified',validation_profile=runner.PROFILE,
            observations_sha256=runner.source.sha(Path(row['replay_directory'])/'observations.json'),
            capture_proof_sha256=runner.source.sha(Path(row['replay_directory'])/'capture-proof.json'),
            normalized_source_fingerprint=runner.split.normalized_fingerprint(data,legacy=True),
            planned_route_fingerprint=runner.source.digest(['synthetic-route',row['seed']]),
            movement_quality=dict(lifecycle_quality=dict(active_episodes_at_horizon=2,pending_episodes_at_horizon=3),
                motion_quality=dict(reported_diagnostics=dict(active_stalled_tracks=1)),all_scheduled_episodes_completed=False))

    def prepared(self,**kwargs):
        runner.prepare(self.freeze,self.legacy,self.strict,self.archived_auditor,self.output,**kwargs)
        return runner.read_protocol(self.output)[1]

    def protocol_write(self,protocol):
        dump(self.output/'protocol.json',protocol)
        (self.output/'protocol.sha256').write_text(runner.source.sha(self.output/'protocol.json')+'\n')

    def gate(self):
        module=SimpleNamespace(authenticate_test_gate=mock.Mock(return_value=dict(source_protocol_sha256=runner.source.sha(self.output/'protocol.json'))))
        patch=mock.patch.dict(sys.modules,{'run_urban_track_window_primary':module});patch.start();self.addCleanup(patch.stop)
        return module.authenticate_test_gate

    def fake_attempt(self,output,protocol,row):
        directory=output/row['id'];directory.mkdir()
        item={key:row[key] for key in ('id','group_id','split','seed','scene_directory','replay_directory','origin')}
        item['status']='failed';dump(directory/'private-source-summary.json',item)
        return item

    def test_exact40_same_role_imports_32_prospective_slots_and_old_statuses_unchanged(self):
        old_bytes={p:p.read_bytes() for p in self.legacy.rglob('*') if p.is_file()}
        with mock.patch.object(runner.subprocess,'Popen') as native,mock.patch.object(runner.subprocess,'run') as physical:
            protocol=self.prepared()
        native.assert_not_called();physical.assert_not_called()
        self.assertEqual(len(protocol['cases']),72)
        self.assertEqual([c['split'] for c in protocol['cases']],[g['split'] for g in self.manifest['groups']])
        self.assertEqual(len(protocol['legacy_physical_audits']),40)
        self.assertFalse(protocol['windowed_physical_audits'])
        ledger=runner.source.load(self.output/'import-ledger.json')
        self.assertEqual(ledger['status'],'verified');self.assertEqual(len(ledger['cases']),40)
        self.assertEqual(ledger['cases'][0]['origin_strict_status'],'invalid')
        first=runner.source.load(Path(ledger['cases'][0]['receipt']['path']))
        self.assertEqual(first['status'],'verified');self.assertFalse(first['movement_quality']['all_scheduled_episodes_completed'])
        self.assertEqual(first['movement_quality']['motion_quality']['reported_diagnostics']['active_stalled_tracks'],1)
        self.assertTrue(all(p.read_bytes()==content for p,content in old_bytes.items()))
        for row in protocol['cases'][40:]:
            self.assertEqual(row['audit_command'][-2:],['--profile',runner.PROFILE])
            self.assertFalse(Path(row['scene_directory']).parent.exists())

    def test_prepare_requires_actual_strict_all40_closure_before_output(self):
        path=self.strict/'train-cal-driver-source-gate.json';dump(path,dict(status='failed',expected=40,observed=39))
        with self.assertRaisesRegex(ValueError,'all40 source gate'):
            self.prepared()
        self.assertFalse(self.output.exists())
        dump(path,dict(status='failed',expected=40,observed=40))
        dump(self.strict/'driver-failed.json',dict(status='failed_or_interrupted',completed=[]))
        with self.assertRaisesRegex(ValueError,'must close'):
            self.prepared()
        self.assertFalse(self.output.exists())

    def test_unrelated_strict_study_cannot_supply_a_compatible_closure(self):
        strict=runner.source.load(self.strict/'protocol.json');strict['source_protocol_sha256']='0'*64
        dump(self.strict/'protocol.json',strict)
        (self.strict/'protocol.sha256').write_text(runner.source.sha(self.strict/'protocol.json')+'\n')
        with self.assertRaisesRegex(ValueError,'another dataset/source study'):
            self.prepared()
        self.assertFalse(self.output.exists())

    def test_original_mechanism_or_model_use_blocks_reinterpretation(self):
        (self.strict/'groups/already-used').mkdir()
        with self.assertRaisesRegex(ValueError,'already used mechanism/model'):
            self.prepared()
        self.assertFalse(self.output.exists())

    def test_missing_original_attempt_or_seen_test_blocks_preparation(self):
        row=self.old['cases'][0];path=Path(row['scene_directory']).parent/'private-source-summary.json'
        saved=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(ValueError,'All40 original attempts'):
            self.prepared()
        path.write_bytes(saved)
        Path(self.old['cases'][40]['scene_directory']).parent.mkdir()
        with self.assertRaisesRegex(ValueError,'TEST source has been attempted'):
            self.prepared()
        self.assertFalse(self.output.exists())

    def test_test_role_seed_and_family_must_equal_original_manifest(self):
        self.old['cases'][40]['seed']+=10000;self.rewrite_legacy()
        with self.assertRaisesRegex(ValueError,'role/seed/identity changed'):
            self.prepared()
        self.assertFalse((self.output/'import-ledger.json').exists())

    def test_missing_old_group_cannot_reduce_the_original_family(self):
        self.old['cases'].pop();self.rewrite_legacy()
        with self.assertRaisesRegex(ValueError,'Legacy group family incomplete'):
            self.prepared()
        self.assertFalse(self.output.exists())

    def test_unapproved_source_change_rejected_but_two_archived_compatible_hooks_allowed(self):
        old=self.code.read_bytes();self.code.write_bytes(b'changed actual source')
        with self.assertRaisesRegex(ValueError,'Unapproved original source dependency'):
            self.prepared()
        self.code.write_bytes(old)
        self.auditor.write_bytes(b'new explicit-profile extension')
        self.primary.write_bytes(b'new optional pair-selector extension')
        with self.assertRaisesRegex(ValueError,'Unapproved original source dependency'):
            self.prepared()
        protocol=self.prepared(original_primary=self.archived_primary)
        self.assertEqual(set(protocol['original_dependency_archives']),{str(self.auditor),str(self.primary)})
        self.archived_primary.write_bytes(b'changed archived original')
        with self.assertRaisesRegex(ValueError,'Referenced artifact changed'):
            runner.read_protocol(self.output)

    def test_failed_old_audit_uses_new_profile_evidence_without_overwriting_old(self):
        row=self.old['cases'][0];audit=Path(row['scene_directory']).parent/'motion-audit.json'
        dump(audit,dict(status='fail',error='old destination coverage gate'))
        old_bytes=audit.read_bytes()
        def new_audit(output,row,protocol):
            directory=output/'import-audits'/row['group_id'];directory.mkdir(parents=True)
            report=directory/'motion-audit.json';execution=directory/'audit-execution.json'
            command=[sys.executable,str(runner.validation.AUDITOR),'--scene',row['scene_directory'],'--replay',row['replay_directory'],
                     '--output',str(report),'--profile',runner.PROFILE]
            dump(report,dict(status='pass',validation_profile=runner.PROFILE))
            dump(execution,dict(status='complete',returncode=0,command=command))
            return dict(report=runner.reference(report),execution=runner.reference(execution),command=command)
        with mock.patch.object(runner,'_windowed_import_audit',side_effect=new_audit) as physical:
            protocol=self.prepared()
        self.assertEqual(physical.call_count,1)
        self.assertEqual(len(protocol['legacy_physical_audits']),39)
        self.assertEqual(len(protocol['windowed_physical_audits']),1)
        self.assertEqual(audit.read_bytes(),old_bytes)

    def test_audit_failure_or_missing_proof_keeps_every_import_in_denominator(self):
        row=self.old['cases'][0];(Path(row['replay_directory'])/'capture-proof.json').unlink()
        second=self.old['cases'][1];dump(Path(second['scene_directory']).parent/'motion-audit.json',dict(status='fail'))
        with mock.patch.object(runner,'_windowed_import_audit',side_effect=ValueError('full physical audit failed')):
            protocol=self.prepared()
        ledger=runner.source.load(self.output/'import-ledger.json')
        self.assertEqual(len(ledger['cases']),40);self.assertEqual(ledger['status'],'incomplete')
        self.assertEqual([c['status'] for c in ledger['cases'][:3]],['invalid','invalid','verified'])
        summary=runner.summarize(self.output,protocol,self.manifest,verify=False)
        self.assertEqual(summary['attempted_count'],40)
        self.assertEqual(summary['by_split']['test'],{'not_attempted':32})
        self.assertEqual(summary['verified_count'],38)

    def test_malformed_original_receipt_is_invalid_without_losing_other39(self):
        row=self.old['cases'][0];path=Path(row['scene_directory']).parent/'private-source-summary.json';path.write_text('{bad json')
        self.prepared();ledger=runner.source.load(self.output/'import-ledger.json')
        self.assertEqual(len(ledger['cases']),40);self.assertEqual(ledger['cases'][0]['status'],'invalid')
        self.assertIsNone(ledger['cases'][0]['origin_strict_status'])
        self.assertEqual(sum(c['status']=='verified' for c in ledger['cases']),39)

    def test_delegated_hard_validation_failure_is_not_reclassified_as_quality(self):
        original=self.valid_capture
        def invalid(row,protocol):
            if row['group_id']==self.old['cases'][0]['group_id']: raise ValueError('real raw GT/swept geometry failure')
            return original(row,protocol)
        with mock.patch.object(runner.validation,'validate_capture',side_effect=invalid):
            self.prepared()
        ledger=runner.source.load(self.output/'import-ledger.json')
        self.assertEqual(ledger['cases'][0]['status'],'invalid')
        item=runner.source.load(Path(ledger['cases'][0]['receipt']['path']))
        self.assertIn('raw GT/swept geometry',item['error'])

    def test_windowed_import_audit_timeout_retains_failed_receipt_and_has_no_retry(self):
        output=self.results/'audit-only';output.mkdir();row=self.old['cases'][0]
        with mock.patch.object(runner.subprocess,'run',side_effect=subprocess.TimeoutExpired('synthetic audit',420)) as process:
            with self.assertRaisesRegex(ValueError,'New windowed physical audit failed'):
                runner._windowed_import_audit(output,row,dict(physical_audit_wall_budget_s=420))
            receipt=runner.source.load(output/'import-audits'/row['group_id']/'audit-execution.json')
            self.assertEqual(receipt['status'],'timeout')
            self.assertEqual(process.call_args.kwargs['timeout'],420)
            self.assertEqual(process.call_args.args[0][-2:],['--profile',runner.PROFILE])
            with self.assertRaises(FileExistsError):
                runner._windowed_import_audit(output,row,dict(physical_audit_wall_budget_s=420))
            self.assertEqual(process.call_count,1)

    def test_read_protocol_rejects_profile_cases_receipt_and_dependency_tampering(self):
        protocol=self.prepared()
        for mutate,expected in [('profile','schema/profile'),('case','paths/roles/seeds'),('dependency','dependency freeze')]:
            with self.subTest(mutate=mutate):
                bad=deepcopy(protocol)
                if mutate=='profile':bad['source_validation_profile']='legacy_completed_v1'
                elif mutate=='case':bad['cases'][40]['seed']+=7
                else:bad['frozen_files_sha256'].pop(str(self.code))
                self.protocol_write(bad)
                with self.assertRaisesRegex(ValueError,expected):runner.read_protocol(self.output)
        self.protocol_write(protocol)
        ledger=runner.source.load(self.output/'import-ledger.json');path=Path(ledger['cases'][0]['receipt']['path']);path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Referenced artifact changed'):runner.read_protocol(self.output)

    def test_original_test_attempt_after_prepare_is_rechecked(self):
        self.prepared();Path(self.old['cases'][40]['scene_directory']).parent.mkdir()
        with self.assertRaisesRegex(ValueError,'Original strict TEST source was already attempted'):
            runner.read_protocol(self.output)

    def test_duplicate_recordings_invalidate_both_without_replacement(self):
        first,second=self.old['cases'][:2]
        data=runner.source.load(Path(first['replay_directory'])/'observations.json')
        dump(Path(second['replay_directory'])/'observations.json',data)
        protocol=self.prepared();summary=runner.summarize(self.output,protocol,self.manifest,verify=False)
        self.assertEqual([c['status'] for c in summary['cases'][:2]],['invalid_duplicate','invalid_duplicate'])
        self.assertEqual(summary['attempted_count'],40);self.assertEqual(len(summary['cases']),72)

    def test_test_gate_rejects_before_snapshot_or_attempt(self):
        self.prepared();gate=self.gate();gate.side_effect=ValueError('missing real lock')
        with mock.patch.object(runner,'attempt') as attempt,mock.patch.object(runner,'snapshot') as snapshot:
            with self.assertRaisesRegex(ValueError,'missing real lock'):runner.capture_test(self.output,self.results/'evaluation')
        attempt.assert_not_called();snapshot.assert_not_called()
        gate.side_effect=None;gate.return_value=dict(source_protocol_sha256='0'*64)
        with mock.patch.object(runner,'attempt') as attempt:
            with self.assertRaisesRegex(ValueError,'another source.*protocol'):runner.capture_test(self.output,self.results/'evaluation')
        attempt.assert_not_called()

    def test_failed_import_blocks_test_even_with_an_authenticated_model_gate(self):
        with mock.patch.object(runner.validation,'validate_capture',side_effect=ValueError('hard invalid source')):
            self.prepared()
        self.gate()
        with mock.patch.object(runner,'attempt') as attempt:
            with self.assertRaisesRegex(ValueError,'All40 hard-valid imports'):runner.capture_test(self.output,self.results/'evaluation')
        attempt.assert_not_called()

    def test_test_capture_uses_original_slots_and_never_retries_existing_directories(self):
        protocol=self.prepared();gate=self.gate();tests=protocol['cases'][40:]
        (self.output/tests[0]['id']).mkdir()
        self.fake_attempt(self.output,protocol,tests[1])
        with mock.patch.object(runner,'attempt',side_effect=self.fake_attempt) as attempt, \
             mock.patch.object(runner.shutil,'disk_usage',return_value=SimpleNamespace(free=10*1024**3)):
            runner.capture_test(self.output,self.results/'evaluation',limit=2)
        self.assertEqual([c.args[2]['group_id'] for c in attempt.call_args_list],[r['group_id'] for r in tests[2:4]])
        self.assertEqual(gate.call_count,3)
        summary=runner.summarize(self.output,protocol,self.manifest,verify=False)
        self.assertEqual(summary['by_split']['test'],dict(interrupted=1,failed=3,not_attempted=28))

    def test_each_test_attempt_rechecks_model_gate_and_original_test_exposure(self):
        protocol=self.prepared();gate=self.gate();lock=gate.return_value
        gate.side_effect=[lock,lock,ValueError('lock changed after first capture')]
        with mock.patch.object(runner,'attempt',side_effect=self.fake_attempt) as attempt, \
             mock.patch.object(runner.shutil,'disk_usage',return_value=SimpleNamespace(free=10*1024**3)):
            with self.assertRaisesRegex(ValueError,'lock changed'):runner.capture_test(self.output,self.results/'evaluation',limit=2)
        self.assertEqual(attempt.call_count,1)
        gate.side_effect=None
        def expose_after_one(output,protocol,row):
            result=self.fake_attempt(output,protocol,row)
            Path(self.old['cases'][40]['scene_directory']).parent.mkdir()
            return result
        with mock.patch.object(runner,'attempt',side_effect=expose_after_one) as attempt, \
             mock.patch.object(runner.shutil,'disk_usage',return_value=SimpleNamespace(free=10*1024**3)):
            with self.assertRaisesRegex(ValueError,'Original strict TEST'):runner.capture_test(self.output,self.results/'evaluation',limit=2)
        self.assertEqual(attempt.call_count,1)

    def test_per_attempt_gate_must_still_bind_this_exact_source_protocol(self):
        self.prepared();gate=self.gate();lock=gate.return_value
        gate.side_effect=[lock,dict(source_protocol_sha256='0'*64)]
        with mock.patch.object(runner,'attempt',side_effect=self.fake_attempt) as attempt, \
             mock.patch.object(runner.shutil,'disk_usage',return_value=SimpleNamespace(free=10*1024**3)):
            with self.assertRaisesRegex(ValueError,'another source.*protocol'):
                runner.capture_test(self.output,self.results/'evaluation',limit=1)
        attempt.assert_not_called()

    def test_low_storage_stops_before_attempt(self):
        self.prepared();self.gate()
        with mock.patch.object(runner,'attempt') as attempt, \
             mock.patch.object(runner.shutil,'disk_usage',return_value=SimpleNamespace(free=runner.MIN_FREE_BYTES-1)):
            with self.assertRaisesRegex(ValueError,'Less than3GiB'):runner.capture_test(self.output,self.results/'evaluation',limit=1)
        attempt.assert_not_called()

    def test_native_timeout_is_retained_owned_group_stopped_and_never_retried(self):
        protocol=self.prepared();row=protocol['cases'][40]
        process=mock.Mock(returncode=-9);process.wait.side_effect=subprocess.TimeoutExpired('synthetic source',420)
        with mock.patch.object(runner.subprocess,'Popen',return_value=process) as native, \
             mock.patch.object(runner.source,'stop_owned_group') as stop, \
             mock.patch.object(runner.source,'run_physical_audit') as physical:
            item=runner.attempt(self.output,protocol,row)
            self.assertEqual(item['status'],'timeout');stop.assert_called_once_with(process);physical.assert_not_called()
            self.assertTrue(native.call_args.kwargs['start_new_session'])
            with self.assertRaisesRegex(ValueError,'No retry'):runner.attempt(self.output,protocol,row)
            self.assertEqual(native.call_count,1)
        saved=runner.source.load(self.output/row['id']/'private-source-summary.json');self.assertEqual(saved['status'],'timeout')

    def test_native_success_with_failed_physical_validation_stays_invalid(self):
        protocol=self.prepared();row=protocol['cases'][40];process=mock.Mock();process.wait.return_value=0
        with mock.patch.object(runner.subprocess,'Popen',return_value=process), \
             mock.patch.object(runner.source,'run_physical_audit',side_effect=ValueError('actual swept overlap')):
            item=runner.attempt(self.output,protocol,row)
        self.assertEqual(item['status'],'invalid');self.assertIn('swept overlap',item['error'])
        imported=protocol['cases'][0]
        with mock.patch.object(runner.subprocess,'Popen') as native:
            with self.assertRaisesRegex(ValueError,'Only prospective TEST'):runner.attempt(self.output,protocol,imported)
        native.assert_not_called()

    def test_existing_running_lock_blocks_concurrent_launch(self):
        self.prepared();path=self.output/'.running.lock';descriptor=os.open(path,os.O_WRONLY|os.O_CREAT,0o600)
        try:
            fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with mock.patch.object(runner,'capture_test') as capture:
                with self.assertRaises(BlockingIOError):runner.main(['--capture-test',str(self.output),'--evaluation',str(self.results/'evaluation')])
            capture.assert_not_called()
        finally:os.close(descriptor)


if __name__=='__main__':
    unittest.main()
