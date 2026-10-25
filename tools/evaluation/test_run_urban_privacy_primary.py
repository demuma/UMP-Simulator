"""P25.4 orchestration tests using synthetic sources and mocked native execution.

No actual primary recording, TEST observation, attack score or MongoDB source is
opened or generated here. Full-horizon empty batches make exact OUT/background
preservation testable without inventing independent source realizations.
"""
from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import run_urban_privacy_primary as runner


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def source_data():
    coverage = dict(x=0,y=0,width=80,height=80,leaf_depth=6)
    batches = []
    for index in range(1, 3000):
        observations = []
        for identity, kind, length, x in (
                ('episode-a','Adult Pedestrian',7,1.),
                ('episode-b','Child Pedestrian',5,2.),
                ('episode-single','Adult Cyclist',1,3.)):
            if index <= length:
                y = index / 10
                observations.append(dict(id=identity,type=kind,x=x,y=y,
                    cell_id=runner.fixture.cell_id(x,y,coverage)))
        batches.append(dict(sequence=index,observed_at_ms=index*100,
                            status='measured',observations=observations))
    return dict(schema='ump.observation-replay.v1',run_id='synthetic-source',sensor_id='synthetic-agbs',
                coverage=coverage,sampling_period_ms=100,end_ms=300000,batches=batches)


def group(split='train'):
    return dict(group_id='synthetic-primary-g001',split=split,
                seeds=dict(source_generation=1001,target_selection=2001,auxiliary_selection=3001))


def methods():
    native = [dict(id=f'fixed{side}_{window}ms',kind='native_fixed',grid_side_m=side,
                   fixed_depth=depth,window_ms=window)
              for side,depth in ((10,3),(20,2)) for window in (400,1000,2000,4000)]
    derived = [dict(id=f'regional_static{side}',kind='regional_static',grid_side_m=side,
                    components=[f'fixed{side}_{window}ms' for window in (400,1000,2000,4000)])
               for side in (10,20)]
    adaptive = dict(id='adaptive_semantic_first',kind='native_adaptive',strategy='semantic_first',
                    secondary_strategy='temporal_first',release_trigger='policy_satisfied')
    return native + derived + [adaptive]


def native_result(data=None, method=None):
    data = source_data() if data is None else data
    method = methods()[0] if method is None else method
    fixed = method['kind'] == 'native_fixed'
    parameters = dict(progress_step_ms=50,progress_origin_ms=0,
                      coordination='common_window' if fixed else 'cell_local')
    if fixed:
        parameters.update(fixed_depth=method['fixed_depth'],window_ms=method['window_ms'])
    else:
        parameters.update(semantic_secondary_strategy=method['secondary_strategy'],release_trigger=method['release_trigger'])
    total = sum(len(batch['observations']) for batch in data['batches'])
    return dict(schema='ump.replay-result.v1',mode='fixed' if fixed else method['strategy'],
        source={**{key:deepcopy(data[key]) for key in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms')},
                'application_id':'synthetic-app'},parameters=parameters,
        input_observation_contributions=total,accounted_observation_contributions=total,releases=[])


class PrimaryPairTests(unittest.TestCase):
    def setUp(self):
        self.data = source_data();self.group = group()
        self.source_sha = hashlib.sha256(canonical(self.data)).hexdigest()

    def selection(self, candidate=None):
        return runner.select_pair(self.data,self.source_sha,candidate or self.group)

    def test_target_and_auxiliary_ranking_use_their_own_role_seed(self):
        absent,knowledge,selection = self.selection()
        traces = {identity:[dict(observed_at_ms=batch['observed_at_ms'],
            **{key:row[key] for key in ('x','y','cell_id')}) for batch in self.data['batches']
            for row in batch['observations'] if row['id']==identity]
            for identity in ('episode-a','episode-b')}
        expected = min(traces,key=lambda identity:(hashlib.sha256(canonical(
            ['target-v1',2001,self.source_sha,identity])).hexdigest(),identity))
        ranked = sorted(traces[expected],key=lambda point:(hashlib.sha256(canonical(
            ['aux-v1',3001,self.source_sha,expected,point])).hexdigest(),canonical(point)))
        expected_knowledge = sorted(ranked[:(len(ranked)+3)//4],key=lambda p:p['observed_at_ms'])
        self.assertEqual(selection['target_id'],expected)
        self.assertEqual(knowledge,expected_knowledge)
        self.assertEqual(selection['target_role_seed'],2001)
        self.assertEqual(selection['auxiliary_role_seed'],3001)
        self.assertEqual(selection['eligible_episodes'],2)
        self.assertNotEqual(selection['target_id'],'episode-single')

    def test_out_removes_only_target_and_preserves_every_other_byte_value(self):
        original = deepcopy(self.data)
        absent,knowledge,selection = self.selection()
        expected = deepcopy(original)
        for batch in expected['batches']:
            batch['observations'] = [row for row in batch['observations'] if row['id']!=selection['target_id']]
        self.assertEqual(absent,expected)
        self.assertEqual(self.data,original)
        self.assertEqual(absent['batches'][-1]['status'],'measured')
        self.assertEqual(absent['batches'][-1]['observations'],[])
        self.assertEqual(len(absent['batches']),2999)
        self.assertEqual(selection['target_observations'],
                         sum(len(b['observations']) for b in original['batches']) -
                         sum(len(b['observations']) for b in absent['batches']))
        self.assertTrue(all(set(point)=={'observed_at_ms','x','y','cell_id'} for point in knowledge))

    def test_pair_selection_is_deterministic_and_not_affected_by_source_rng_role(self):
        a=self.selection();changed=deepcopy(self.group);changed['seeds']['source_generation']=987654321
        self.assertEqual(a,self.selection(changed))
        a[0]['batches'][0]['observations'].clear()
        self.assertNotEqual(a,self.selection())

    def test_target_role_can_change_target_without_auxiliary_role_changes(self):
        targets=set()
        for seed in range(10):
            changed=deepcopy(self.group);changed['seeds']['target_selection']=seed
            targets.add(self.selection(changed)[2]['target_id'])
        self.assertEqual(targets,{'episode-a','episode-b'})

    def test_auxiliary_role_changes_points_without_changing_selected_target(self):
        choices=set();targets=set()
        for seed in range(10):
            changed=deepcopy(self.group);changed['seeds']['auxiliary_selection']=seed
            _,knowledge,selection=self.selection(changed)
            choices.add(canonical(knowledge));targets.add(selection['target_id'])
        self.assertEqual(len(targets),1)
        self.assertGreater(len(choices),1)

    def test_no_eligible_episode_rejected(self):
        data=source_data()
        for batch in data['batches'][1:]:batch['observations']=[]
        with self.assertRaisesRegex(ValueError,'No eligible'):
            runner.select_pair(data,self.source_sha,self.group)

    def test_positive_control_uses_only_public_time_position_and_derived_cell(self):
        absent,knowledge,selection=self.selection()
        self.assertEqual(runner.positive_control(self.data,knowledge),1)
        self.assertEqual(runner.positive_control(absent,knowledge),0)
        for batch in self.data['batches']:
            for row in batch['observations']:
                row['id']='changed-'+row['id'];row['type']='a secret type that must not be consulted'
                row['cell_id']=1  # derive from x/y, rather than trust source/private aliases.
        self.assertEqual(runner.positive_control(self.data,knowledge),1)

    def test_positive_control_background_coincidence_is_not_forced_to_zero(self):
        absent,knowledge,selection=self.selection()
        matching={point['observed_at_ms']:point for point in knowledge}
        for batch in absent['batches']:
            if batch['observed_at_ms'] in matching:
                point=matching[batch['observed_at_ms']]
                batch['observations'].append(dict(id='coincident-background',type='Unrelated type',
                    x=point['x'],y=point['y'],cell_id=point['cell_id']))
        self.assertEqual(runner.positive_control(absent,knowledge),1)


class PrimaryExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.directory=self.root/'work';self.directory.mkdir()
        self.data=source_data();self.method=methods()[0]
        self.config={'application_id':'synthetic-app','temporal_adaptation':{}}
        self.input=self.directory/'input.json';dump(self.input,self.data)
        (self.directory/'AggregationReplay').write_bytes(b'synthetic native executable never run')
        dump(self.directory/'policy.json',self.config)
        self.group=group();self.protocol={'native_wall_budget_s':7,'audit_max_cells':100}
        self.patches=[mock.patch.object(runner,'ROOT',self.root)]
        for patch in self.patches:patch.start()
        self.addCleanup(mock.patch.stopall);self.addCleanup(self.temp.cleanup)

    def invoke(self):
        return runner.run_native(self.directory,self.input,self.config,self.method,self.group,'IN',[],self.protocol)

    def test_frozen_family_nine_native_two_derived_correct_depths_and_commands(self):
        family=methods();native=[m for m in family if m['kind']!='regional_static']
        self.assertEqual(len(native),9)
        self.assertEqual(len([m for m in family if m['kind']=='regional_static']),2)
        for method in native:
            command=runner.native_command('binary','input','policy','output',method)
            self.assertEqual(command[:7],['binary','--input','input','--config','policy','--mode',
                'fixed' if method['kind']=='native_fixed' else 'semantic_first'])
            if method['kind']=='native_fixed':
                self.assertEqual(command[command.index('--fixed-depth')+1],str(3 if method['grid_side_m']==10 else 2))
                self.assertEqual(command[command.index('--fixed-window-ms')+1],str(method['window_ms']))
            else:self.assertNotIn('--fixed-depth',command)

    def test_native_header_guards_source_method_clock_schedule_and_accounting(self):
        good=native_result(self.data,self.method)
        runner.validate_native(good,self.data,self.config,self.method)
        changes=[('schema','bad'),('mode','semantic_first'),('input_observation_contributions',999),
                 ('accounted_observation_contributions',999),('source.end_ms',299900),
                 ('source.sensor_id','other'),('source.application_id','other'),
                 ('parameters.progress_step_ms',100),('parameters.progress_origin_ms',50),
                 ('parameters.fixed_depth',2),('parameters.window_ms',1000),
                 ('parameters.coordination','cell_local')]
        for path,value in changes:
            with self.subTest(path=path):
                bad=deepcopy(good);parts=path.split('.');target=bad
                for key in parts[:-1]:target=target[key]
                target[parts[-1]]=value
                with self.assertRaises(ValueError):runner.validate_native(bad,self.data,self.config,self.method)
        adaptive=methods()[-1]
        runner.validate_native(native_result(self.data,adaptive),self.data,self.config,adaptive)
        for key,value in (('coordination','common_window'),('semantic_secondary_strategy','spatial_first'),('release_trigger','maximum_window')):
            with self.subTest(adaptive_parameter=key):
                bad=native_result(self.data,adaptive);bad['parameters'][key]=value
                with self.assertRaises(ValueError):runner.validate_native(bad,self.data,self.config,adaptive)

    def test_timeout_receipt_cap_and_never_retry(self):
        with mock.patch.object(runner.subprocess,'run',side_effect=subprocess.TimeoutExpired(['binary'],7)) as run:
            with self.assertRaisesRegex(ValueError,'failed or exceeded'):
                self.invoke()
            receipt=json.loads((self.directory/(self.method['id']+'-execution.json')).read_text())
            self.assertEqual(receipt['status'],'timeout')
            self.assertEqual(run.call_args.kwargs['timeout'],7)
            self.assertEqual(run.call_args.kwargs['umask'],0o077)
            with self.assertRaisesRegex(ValueError,'never retry'):self.invoke()
            self.assertEqual(run.call_count,1)
        self.assertTrue((self.directory/(self.method['id']+'-attempt.json')).is_file())
        self.assertFalse((self.directory/(self.method['id']+'-row.json')).exists())

    def test_failed_exit_is_retained_and_not_retried(self):
        with mock.patch.object(runner.subprocess,'run',return_value=subprocess.CompletedProcess([],3,'stdout','stderr')) as run:
            with self.assertRaises(ValueError):self.invoke()
            receipt=json.loads((self.directory/(self.method['id']+'-execution.json')).read_text())
            self.assertEqual(receipt['status'],'failed');self.assertEqual(receipt['returncode'],3)
            self.assertEqual(receipt['stdout'],'stdout');self.assertEqual(receipt['stderr'],'stderr')
            with self.assertRaises(ValueError):self.invoke()
            self.assertEqual(run.call_count,1)

    def test_interruption_is_recorded_and_propagated(self):
        with mock.patch.object(runner.subprocess,'run',side_effect=KeyboardInterrupt('synthetic interrupt')):
            with self.assertRaises(KeyboardInterrupt):self.invoke()
        receipt=json.loads((self.directory/(self.method['id']+'-execution.json')).read_text())
        self.assertEqual(receipt['status'],'interrupted')
        self.assertIn('synthetic interrupt',receipt['error'])

    def test_preexisting_attempt_cannot_be_overwritten_even_without_execution_receipt(self):
        path=self.directory/(self.method['id']+'-attempt.json');dump(path,{'preserve':'first attempt'})
        before=path.read_bytes()
        with mock.patch.object(runner.subprocess,'run') as run:
            with self.assertRaises(FileExistsError):self.invoke()
        run.assert_not_called();self.assertEqual(path.read_bytes(),before)

    def test_native_mutation_of_frozen_input_is_rejected_before_audit(self):
        def mutation(*args,**kwargs):
            (self.directory/'policy.json').write_bytes(b'modified frozen policy')
            return subprocess.CompletedProcess([],0,'','')
        with mock.patch.object(runner.subprocess,'run',side_effect=mutation), \
             mock.patch.object(runner.independent,'audit') as audit:
            with self.assertRaisesRegex(ValueError,'Frozen source or artifact changed'):
                self.invoke()
        audit.assert_not_called()

    def test_failed_independent_audit_prevents_feature_or_result_acceptance(self):
        dump(self.directory/(self.method['id']+'.json'),native_result(self.data,self.method))
        with mock.patch.object(runner.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')), \
             mock.patch.object(runner.independent,'audit',return_value={'status':'invalid','scalar':{'valid':False}}), \
             mock.patch.object(runner,'row_for') as row:
            with self.assertRaisesRegex(ValueError,'Independent policy/source audit'):
                self.invoke()
        row.assert_not_called()
        self.assertFalse((self.directory/(self.method['id']+'-receipt.json')).exists())


class PrimaryArchiveAndGroupingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.output=self.root/'results/study';(self.output/'groups').mkdir(parents=True)
        self.addCleanup(self.temp.cleanup)

    def test_archive_roundtrip_sha_permissions_and_deterministic_no_filename_header(self):
        payload=(bytes(range(256))*5000)+b'private movement\x00\n'
        checks=[]
        for name in ('first.json','second.json'):
            path=self.output/name;path.write_bytes(payload)
            receipt=runner.archive_file(path);archived=self.output/receipt['path']
            self.assertFalse(path.exists())
            self.assertEqual(gzip.decompress(archived.read_bytes()),payload)
            self.assertEqual(receipt['uncompressed_sha256'],hashlib.sha256(payload).hexdigest())
            self.assertEqual(receipt['sha256'],hashlib.sha256(archived.read_bytes()).hexdigest())
            self.assertEqual(receipt['uncompressed_bytes'],len(payload))
            self.assertEqual(archived.stat().st_mode & 0o777,0o600)
            checks.append(archived.read_bytes())
        self.assertEqual(checks[0],checks[1])

    def test_archive_collision_preserves_both_existing_files(self):
        path=self.output/'native.json';path.write_bytes(b'new plain')
        target=self.output/'native.json.gz';target.write_bytes(b'old archive')
        with self.assertRaisesRegex(ValueError,'overwrite archive'):runner.archive_file(path)
        self.assertEqual(path.read_bytes(),b'new plain');self.assertEqual(target.read_bytes(),b'old archive')

    def test_archive_roundtrip_failure_preserves_original(self):
        path=self.output/'native.json';path.write_bytes(b'original')
        with mock.patch.object(runner.source,'sha',return_value=hashlib.sha256(b'original').hexdigest()), \
             mock.patch.object(runner.hashlib,'sha256') as sha:
            sha.return_value.hexdigest.return_value='0'*64
            with self.assertRaisesRegex(ValueError,'round-trip hash mismatch'):runner.archive_file(path)
        self.assertEqual(path.read_bytes(),b'original')

    def archive_fixture(self):
        work=self.output/'IN';work.mkdir()
        raw=work/'native.json';raw.write_bytes(b'original audited result bytes')
        reference=runner.artifact(work,raw)
        receipt=runner.archive_file(raw)
        archives={'IN':{'native.json':receipt}}
        dump(self.output/'archive-receipt.json',archives)
        summary={'archives':runner.artifact(self.output,self.output/'archive-receipt.json'),
                 'cases':[{'world':'IN','artifacts':{'native.json':reference}}]}
        return work,archives,summary

    def test_final_archive_authentication_detects_compressed_corruption(self):
        work,archives,summary=self.archive_fixture()
        runner.verify_group_artifacts(self.output,summary)
        path=work/'native.json.gz';path.write_bytes(path.read_bytes()+b'corrupt suffix')
        with self.assertRaisesRegex(ValueError,'provenance hash mismatch'):
            runner.verify_group_artifacts(self.output,summary)

    def test_final_archive_authentication_detects_original_byte_mismatch(self):
        work,archives,summary=self.archive_fixture()
        path=work/'native.json.gz'
        path.write_bytes(gzip.compress(b'different body'))
        archives['IN']['native.json']['sha256']=runner.source.sha(path)
        dump(self.output/'archive-receipt.json',archives)
        summary['archives']=runner.artifact(self.output,self.output/'archive-receipt.json')
        with self.assertRaisesRegex(ValueError,'original bytes changed'):
            runner.verify_group_artifacts(self.output,summary)

    def test_final_archive_authentication_preserves_native_audit_chain(self):
        work,archives,summary=self.archive_fixture()
        summary['cases'][0]['artifacts']['native.json']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'native audit receipt disagree'):
            runner.verify_group_artifacts(self.output,summary)

    def test_collect_preserves_group_splits_missing_interrupted_and_row_hash(self):
        groups=[dict(group_id=f'synthetic-g{i}',split=role) for i,role in enumerate(('train','calibration','test'))]
        directory=self.output/'groups'/groups[0]['group_id'];directory.mkdir()
        rows=[dict(group_id=groups[0]['group_id'],split='train',world='IN')];dump(directory/'rows.json',rows)
        summary=dict(**groups[0],status='incomplete',rows=runner.artifact(directory,directory/'rows.json'))
        dump(directory/'summary.json',summary)
        (self.output/'groups'/groups[1]['group_id']).mkdir()
        actual,summaries=runner.collect(self.output,{'groups':groups})
        self.assertEqual(actual,rows)
        self.assertEqual([s['status'] for s in summaries],['incomplete','interrupted','not_attempted'])
        self.assertEqual([s['split'] for s in summaries],['train','calibration','test'])
        dump(directory/'rows.json',[])
        with self.assertRaisesRegex(ValueError,'provenance hash mismatch'):
            runner.collect(self.output,{'groups':groups})

    def test_group_failed_native_and_dependent_regional_remain_in_family(self):
        raw=self.root/'raw';raw.mkdir();data=source_data();dump(raw/'observations.json',data)
        frozen=self.root/'freeze';frozen.mkdir();dump(frozen/'policy-local400.json',{'fixture':True})
        binary=self.root/'simulator/build/AggregationReplay';binary.parent.mkdir(parents=True);binary.write_bytes(b'not executed')
        source_case=dict(replay_directory=str(raw),observations_sha256=runner.source.sha(raw/'observations.json'))
        g=group();events=[]
        def native(directory,path,config,method,current,world,knowledge,protocol):
            events.append(('native',world,method['id']))
            self.assertEqual(current,g)
            if world=='IN' and method['id']=='fixed10_400ms':raise ValueError('synthetic native failure')
            return dict(method_id=method['id'],world=world,status='verified'),dict(group_id=g['group_id'],split='train',world=world)
        def compose(directory,config,method,current,world,knowledge,records):
            events.append(('derived',world,method['id']))
            runner.require(all(records[key]['status']=='verified' for key in method['components']),'synthetic missing dependency')
            return dict(method_id=method['id'],world=world,status='verified'),dict(group_id=g['group_id'],split='train',world=world)
        def audit_pair(manifest,pairs,root):
            events.append(('pair_audit',));self.assertEqual(pairs[0]['split'],'train');return {'status':'verified'}
        with mock.patch.object(runner,'ROOT',self.root),mock.patch.object(runner,'run_native',side_effect=native) as native_mock, \
             mock.patch.object(runner,'compose',side_effect=compose) as compose_mock, \
             mock.patch.object(runner.split,'verify_actual_sources',side_effect=audit_pair):
            summary=runner.process_group(self.output,{'freeze_directory':str(frozen),'minimum_free_bytes':0},
                {'design':{'methods':methods()}},g,source_case)
            self.assertEqual(events[0],('pair_audit',))
            self.assertEqual(native_mock.call_count,18);self.assertEqual(compose_mock.call_count,4)
            self.assertEqual(summary['status'],'incomplete');self.assertEqual(len(summary['cases']),22)
            failed=[(c['method_id'],c['world'],c['status']) for c in summary['cases'] if c['status']!='verified']
            self.assertEqual(failed,[('fixed10_400ms','IN','failed'),('regional_static10','IN','failed_dependency_or_audit')])
            rows=json.loads((self.output/'groups'/g['group_id']/'rows.json').read_text())
            self.assertEqual(len(rows),20)
            self.assertTrue(all(row['group_id']==g['group_id'] and row['split']=='train' for row in rows))
            with self.assertRaisesRegex(ValueError,'Group exists'):
                runner.process_group(self.output,{}, {},g,source_case)


if __name__=='__main__':
    unittest.main()
