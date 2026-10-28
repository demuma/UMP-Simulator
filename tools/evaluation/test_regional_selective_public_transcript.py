"""Real four-window native families and adversarial filtered composition tests."""
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import regional_public_transcript as old
import regional_selective_public_transcript as subject
import semantic_privacy
import semantic_suppression_audit as suppression
import static_regional_schedule as static
from run_semantic_priority_study import fixture, policy

ROOT = Path(__file__).resolve().parents[2]
BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT/'simulator/build-semantic-ablation/AggregationReplay'))


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False))


def settings(local=True):
    config = policy('rare_local', 5, 1, 20, 800, 'temporal_first')
    config['history'].update(retention_ms=4000, max_bins=64)
    config['temporal_adaptation'].update(max_window_ms=4000, max_evaluations=64)
    config['policy_tree']['root'].update(window_duration_ms={'max':4000}, age_at_evaluation_ms={'max':4000},
                                         semantic_suppression_fraction={'max':.10})
    config['policy_tree']['execution'] = dict(publication_model='private_final_snapshot', strategy='semantic_first',
                                              semantic_secondary_strategy='temporal_first', release_trigger='policy_satisfied')
    config['policy_regions'] = [dict(id='failed', type='support', x=20, y=0, width=20, height=20,
                                    requirements={'distinct_contributors':{'min':6}})]
    if local:
        config['policy_regions'].append(dict(id='fresh', type='fresh', x=0, y=0, width=20, height=20,
                requirements={'window_duration_ms':{'max':400}, 'age_at_evaluation_ms':{'max':400}}))
    config['policy_tree']['regions'] = [r['id'] for r in config['policy_regions']]
    return config


def make_family(root, *, local=True, empty=False, strict_filter=False):
    data = fixture('rare_local'); data['end_ms'] = 8000
    template = deepcopy(data['batches'][0]['observations'])
    data['batches'] = [dict(sequence=t//100, observed_at_ms=t, status='measured',
                            observations=[] if empty else deepcopy(template)) for t in range(100,8000,100)]
    write(root/'source.json', data)
    shutil.copy2(BINARY, root/'AggregationReplay')
    def receipt(name):
        return dict(path=name, sha256=subject.sha(root/name))
    cases = {}
    for window in static.WINDOWS:
        config = settings(local)
        if strict_filter:
            config['policy_regions'][-1]['requirements'][suppression.METRIC] = {'max':0}
        config['application_id'] += '/' + str(window)
        config['policy_tree']['id'] += '/' + str(window)
        cp = root/(str(window)+'-config.json'); rp = root/(str(window)+'-result.json')
        ap = root/(str(window)+'-audit.json'); write(cp, config)
        completed = subprocess.run([str(BINARY), '--input', str(root/'source.json'), '--config', str(cp),
                '--mode','fixed', '--fixed-depth','2','--fixed-window-ms',str(window),
                '--semantic-generalization','enabled','--progress-step-ms','50','--output',str(rp)],
                capture_output=True, text=True, timeout=15)
        if completed.returncode:
            raise AssertionError(completed.stdout+completed.stderr)
        audited = deepcopy(config); audited['temporal_adaptation']['coordination'] = 'common_window'
        write(ap, suppression.audit_suppression(data, audited, subject.read(rp)))
        cases[str(window)] = dict(config=receipt(cp.name),result=receipt(rp.name),private_audit=receipt(ap.name),
                     independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0))
    return dict(schema=subject.FAMILY_SCHEMA, public_coverage=data['coverage'],sampling_period_ms=100,end_ms=8000,
                side_m=20,public_policy_id='public-selective-policy',method_alias='regional_static20_selective',
                source=receipt('source.json'),native_binary=receipt('AggregationReplay'),cases=cases)


def mutate(root, manifest, window, kind, change):
    receipt = manifest['cases'][str(window)][kind]
    path = root/receipt['path']; value = subject.read(path); change(value); write(path,value)
    receipt['sha256'] = subject.sha(path)


@unittest.skipUnless(BINARY.is_file(), 'Build native semantic-suppression AggregationReplay')
class RegionalSelectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = tempfile.TemporaryDirectory(prefix='ump-regional-selective-native-')
        cls.root = Path(cls.storage.name)
        cls.manifest = make_family(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.storage.cleanup()

    def copied(self):
        temporary = tempfile.TemporaryDirectory(prefix='ump-regional-selective-case-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)/'family'
        shutil.copytree(self.root, root)
        return root, deepcopy(self.manifest)

    def test_real_native_composition_reconstructs_masks_retained_delays_and_all_partitions(self):
        result = subject.compose_family(self.root,self.manifest)
        audit = result['private_audit']; stats = audit['stats']; accounting = stats['source_accounting']
        self.assertEqual(result['public_transcript']['schema'], semantic_privacy.PUBLIC_SCHEMA)
        self.assertEqual(accounting['input_observations'],35*79)
        self.assertEqual(accounting['retained_observations'],29*79)
        self.assertEqual(accounting['selectively_suppressed_observations'],79)
        self.assertEqual(accounting['whole_footprint_suppressed_observations'],5*79)
        self.assertEqual(accounting['by_source_type']['adult_cyclist']['retained_observations'],0)
        self.assertEqual(accounting['by_region']['failed']['whole_footprint_suppressed_observations'],5*79)
        self.assertEqual(accounting['by_region']['fresh']['selectively_suppressed_observations'],79)
        self.assertEqual(accounting['by_source_point_region']['outside_policy_regions']['retained_observations'],10*79)
        partition = stats['partition_audit']
        self.assertEqual(partition['scheduled_cell_intervals'],50)
        self.assertEqual(partition['nonempty_cell_intervals'],26)
        self.assertEqual(partition['empty_cell_intervals'],24)
        self.assertEqual(partition['failed_nonempty_cell_intervals'],2)
        self.assertEqual(partition['published_nonempty_cell_intervals'],24)
        self.assertEqual(set(audit['cell_window_ms'].values()),{400,4000})
        retained_delays = Counter()
        for batch in subject.read(self.root/'source.json')['batches']:
            t = batch['observed_at_ms']
            for row in batch['observations']:
                if row['cell_id']==49 or row['cell_id']==48 and row['type']=='adult_cyclist':
                    continue
                window = 400 if row['cell_id']==48 else 4000
                retained_delays[min((t//window+1)*window,8000)-t] += 1
        self.assertEqual(accounting['observation_to_release_delay_ms'],static.delay_stats(retained_delays))
        public_text=json.dumps(result['public_transcript'])
        for private in ('semantic_suppression','retained_counts','source_accounting','suppressed_terminal_categories','semantic-priority-rare_local'):
            self.assertNotIn(private,public_text)

    def test_exact_native_owned_cells_and_policy_suffixes_are_preserved(self):
        composed=subject.compose_family(self.root,self.manifest)
        public=composed['public_transcript']; plan=subject.plan_schedule(self.manifest['public_coverage'],settings(),20)
        expected={}
        for window in static.WINDOWS:
            case=self.manifest['cases'][str(window)]
            native=old._native_public(subject.read(self.root/case['result']['path']),
                    subject.read(self.root/case['config']['path']),plan,self.manifest['public_policy_id'],'final_snapshot_at_horizon')
            expected.update({key:cell for key,(cell,_) in native.items() if plan['cells'][key[0]]['window_ms']==window})
        actual={(c['cell_id'],r['start_ms'],r['end_ms']):c for r in public['releases'] for c in r['cells']}
        self.assertEqual(actual,expected)
        self.assertTrue(all(c['effective_policy_id'].startswith(self.manifest['public_policy_id']+'/') for c in actual.values()))

    def test_reforged_mask_counts_support_and_saved_audit_are_independently_rejected(self):
        changes=[('mask',lambda r:r['windows'][0]['cells'][0]['semantic_suppression'].update(suppressed_terminal_categories=[])),
                 ('count',lambda r:r['releases'][0]['cells'][0].update(observation_contributions=999)),
                 ('support',lambda r:r['releases'][0]['cells'][0]['semantic']['categories'][0].update(distinct_contributors=99)),
                 ('ownership',lambda r:r['windows'][0]['cells'].pop(0))]
        for name,change in changes:
            with self.subTest(change=name):
                root,manifest=self.copied();mutate(root,manifest,400,'result',change)
                with self.assertRaises((ValueError,KeyError)):subject.compose_family(root,manifest)
        root,manifest=self.copied()
        mutate(root,manifest,1000,'private_audit',lambda a:a['source_accounting'].update(retained_observations=0))
        with self.assertRaises(ValueError):subject.compose_family(root,manifest)

    def test_unused_native_family_is_reaudited_and_missing_empty_intervals_fail(self):
        root,manifest=self.copied()
        mutate(root,manifest,1000,'result',lambda r:r['windows'][0]['cells'][0]['semantic_suppression'].update(suppressed_terminal_categories=['pedestrian']))
        with self.assertRaises(ValueError):subject.compose_family(root,manifest)
        root,manifest=self.copied();mutate(root,manifest,4000,'result',lambda r:r['windows'].pop())
        with self.assertRaises(ValueError):subject.compose_family(root,manifest)

    def test_frozen_receipts_source_paths_and_family_configs_reject_tampering(self):
        root,manifest=self.copied();(root/'source.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'receipt differs'):subject.compose_family(root,manifest)
        root,manifest=self.copied();manifest['source']['path']='../source.json'
        with self.assertRaisesRegex(ValueError,'canonical and relative'):subject.compose_family(root,manifest)
        root,manifest=self.copied();mutate(root,manifest,1000,'config',lambda c:c['policy_tree']['root'].update(distinct_contributors={'min':4}))
        with self.assertRaisesRegex(ValueError,'hard policy'):subject.compose_family(root,manifest)
        root,manifest=self.copied();data=subject.read(root/'source.json');data['batches'][0]['observations'][0]['id']='forged-source'
        write(root/'source.json',data);manifest['source']['sha256']=subject.sha(root/'source.json')
        with self.assertRaises(ValueError):subject.compose_family(root,manifest)

    def test_schedule_uses_public_geometry_before_observations_and_matches_old_off_schedule(self):
        config=settings();before=deepcopy(config);off=deepcopy(config)
        off['policy_tree']['root']['semantic_suppression_fraction']={'max':0}
        self.assertEqual(subject.plan_schedule(self.manifest['public_coverage'],config,20)['cell_window_ms'],
                         static.plan_schedule(self.manifest['public_coverage'],off,20)['cell_window_ms'])
        self.assertEqual(config,before)
        events=[];realread=subject.read;realplan=subject.plan_schedule
        def read(path):events.append(Path(path).name);return realread(path)
        def plan(*args):events.append('schedule');return realplan(*args)
        with patch.object(subject,'read',side_effect=read),patch.object(subject,'plan_schedule',side_effect=plan):
            subject.compose_family(self.root,self.manifest)
        self.assertLess(events.index('schedule'),events.index('source.json'))

    def test_strict_region_forbids_selective_removal_despite_global_cap(self):
        with tempfile.TemporaryDirectory(prefix='ump-regional-selective-strict-') as name:
            root=Path(name);manifest=make_family(root,strict_filter=True)
            composed=subject.compose_family(root,manifest)
            accounting=composed['private_audit']['source_accounting']
            self.assertEqual(accounting['selectively_suppressed_observations'],0)
            self.assertEqual(accounting['retained_observations'],30*79)
            self.assertEqual(accounting['whole_footprint_suppressed_observations'],5*79)
            self.assertEqual(accounting['by_region']['fresh']['retained_fraction'],1)

    def test_uniform_control_matches_filtered_native_4s_and_empty_source_is_accounted(self):
        for empty in (False,True):
            with self.subTest(empty=empty),tempfile.TemporaryDirectory(prefix='ump-regional-selective-control-') as name:
                root=Path(name);manifest=make_family(root,local=False,empty=empty)
                composed=subject.compose_family(root,manifest)
                self.assertTrue(composed['private_audit']['positive_control_equal_native_4s'])
                if empty:
                    self.assertEqual(composed['public_transcript']['releases'],[])
                    partition=composed['private_audit']['stats']['partition_audit']
                    self.assertEqual(partition['nonempty_cell_intervals'],0)
                    self.assertEqual(partition['empty_cell_intervals'],32)


if __name__=='__main__':
    unittest.main()
