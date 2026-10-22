"""Causal score-path calibration, completed-source provenance and runner integration."""
from copy import deepcopy
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from empirical_privacy import attack_metrics, calibrate_threshold, export_public
from privacy_dataset import build_robustness_dataset
from robustness_attacks import SKLEARN_VERSION
from run_comparison import digest, write_json
from run_privacy_study import control_result, read_json
from run_privacy_prefix_study import (AUXILIARY_STREAM, CHECKPOINTS, ROOT, VARIANTS,
    _first_crossings, _path_rows, assess_paths, calibrate_paths, load_source, public_relative, run_study)


def path(group,label,scores,scenario='sparse'):
    return dict(group_id=group,scenario=scenario,distribution='base',label=label,scores=scores)


def completed_source(directory):
    """Small synthetic completed-channel fixture; its inert binary is never run.

    This exercises provenance/analysis contracts, not C++ policy correctness. Real
    mechanism execution and independent policy audits have their own regressions.
    """
    dataset=directory/'dataset';study=directory/'source'
    data=build_robustness_dataset(dataset,seed=303,train_groups=2,calibration_groups=2,
        test_groups=2,shifted_test_groups=2,end_ms=1000)
    study.mkdir(mode=0o700);(study/'public').mkdir();(study/'policies').mkdir();(study/'models').mkdir()
    shutil.copyfile(dataset/'manifest.json',study/'dataset-manifest.json')
    (study/'AggregationReplay.frozen').write_bytes(b'Inert fixture: this file must never execute')
    required=('simulator/CMakeLists.txt','simulator/tools/AggregationReplay.cpp','simulator/src/CellLocalAggregation.cpp')
    sources={}
    for relative in required:
        destination=study/'source'/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text('Fixture snapshot: '+relative+'\n');sources[relative]=digest(destination)
    policies={}
    for variant in VARIANTS:
        if not variant.startswith('control_'):
            write_json(study/'policies'/(variant+'.json'),dict(fixture=variant))
            policies[variant]=digest(study/'policies'/(variant+'.json'))
    for case in data['cases']:
        for world in ('present','absent'):
            replay=read_json(dataset/case[world+'_input'])
            for variant in VARIANTS:
                control='control_no_output' if variant=='control_no_output' else 'control_exact_count'
                write_json(study/public_relative(case,world,variant),export_public(control_result(replay,control)))
    write_json(study/'protocol.json',dict(schema='ump.privacy-robustness-protocol.v1',status='predeclared',
        dataset_manifest_sha256=digest(dataset/'manifest.json'),binary_sha256=digest(study/'AggregationReplay.frozen'),
        source_sha256=sources,effective_policy_sha256=policies,
        variants=[[v,'fixture',None,None,'common_window'] for v in VARIANTS if not v.startswith('control_')],
        controls=['control_exact_count','control_no_output']))
    write_json(study/'report.json',dict(schema='ump.privacy-robustness-report.v1',status='complete',
        protocol_sha256=digest(study/'protocol.json'),independent_validation=dict(all_valid=True)))
    # This untrusted input model must never be opened or deserialized.
    (study/'models'/'never-load.joblib').write_bytes(b'not a model')
    artifacts={str(p.relative_to(study)):digest(p) for p in study.rglob('*') if p.is_file()}
    write_json(study/'manifest.json',dict(schema='ump.privacy-robustness-manifest.v1',status='complete',
        protocol_sha256=digest(study/'protocol.json'),report_sha256=digest(study/'report.json'),
        binary_sha256=digest(study/'AggregationReplay.frozen'),artifact_sha256=artifacts))
    return study,dataset


class ScorePathTests(unittest.TestCase):
    def test_one_calibration_caps_ever_false_alarms_instead_of_each_look(self):
        rows=[]
        for group in range(10):
            positive=.95 if group<5 else .85
            rows.append(path(str(group),1,[positive,positive]))
            rows.append(path(str(group),0,[.9 if group==0 else .1,.9 if group==1 else .1]))
        naive=[calibrate_threshold([r['scores'][i] for r in rows],[r['label'] for r in rows],.1) for i in range(2)]
        self.assertTrue(all(c['calibration']['fpr']==.1 and c['calibration']['tpr']==1 for c in naive))
        false_any=sum(r['label']==0 and any(s>=c['threshold'] for s,c in zip(r['scores'],naive)) for r in rows)/10
        self.assertEqual(false_any,.2)
        calibrated=calibrate_paths(rows,(100,200))
        self.assertEqual(calibrated['threshold'],.95)
        self.assertEqual(calibrated['calibration']['fpr'],0)
        self.assertEqual(calibrated['calibration']['tpr'],.5)
        maximum=_path_rows(rows,(100,200))
        self.assertEqual(calibrated['calibration'],attack_metrics([r['score'] for r in maximum],
            [r['label'] for r in maximum],calibrated['threshold']))

    def test_first_crossing_is_once_and_cumulative_rates_keep_denominators(self):
        rows=[path('a',1,[.2,.9,.3]),path('a',0,[.8,.1,.1]),
              path('b',1,[.1,.2,.9]),path('b',0,[.1,.2,.3]),
              path('c',1,[.1,.2,.3]),path('c',0,[.1,.8,.1])]
        result=assess_paths(rows,(100,200,300),.8,4,('handcase',))
        self.assertEqual(result['first_crossing_cdf']['positive']['never_alarm'],1)
        self.assertEqual([p['cdf'] for p in result['first_crossing_cdf']['positive']['curve']],[0,1/3,2/3])
        self.assertEqual([p['cdf'] for p in result['first_crossing_cdf']['negative']['curve']],[1/3,2/3,2/3])
        for checkpoint in result['checkpoints']:
            self.assertEqual(checkpoint['cumulative_alarm']['positive_cases'],3)
            self.assertEqual(checkpoint['cumulative_alarm']['negative_cases'],3)
        self.assertEqual(result['max_score'],result['checkpoints'][-1]['cumulative_alarm'])
        self.assertEqual([r['eof_checkpoint'] for r in result['checkpoints']],[False,False,True])

    def test_bad_score_paths_rejected(self):
        for scores in ([],[.1],[.1,float('nan')],[.1,1.1]):
            with self.subTest(scores=scores),self.assertRaises(ValueError):
                _path_rows([path('a',0,scores)],(100,200))


class ProvenanceTests(unittest.TestCase):
    def test_completed_source_verified_without_touching_models_or_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            study,dataset=completed_source(Path(temporary))
            before=(study/'models'/'never-load.joblib').read_bytes()
            loaded=load_source(study,dataset)
            self.assertEqual(len(loaded['data']['cases']),8)
            self.assertEqual((study/'models'/'never-load.joblib').read_bytes(),before)
            self.assertTrue(any('/public/' in p for p in loaded['consumed']))
            self.assertFalse(any('/models/' in p for p in loaded['consumed']))

    def test_tampered_public_or_report_refused_before_output(self):
        for target in ('public','report.json'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as temporary:
                study,dataset=completed_source(Path(temporary));output=Path(temporary)/'analysis'
                path_to_change=next((study/'public').glob('*.json')) if target=='public' else study/target
                with path_to_change.open('ab') as stream:stream.write(b'\n')
                with self.assertRaisesRegex(ValueError,'provenance|linkage'):
                    run_study(study,dataset,output,checkpoints=(200,1000),attack_families=('logistic',))
                self.assertFalse(output.exists())

    def test_invalid_schedule_and_dependency_failure_precede_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'output'
            for checkpoints in ((),(1000,1000),(1000,200),(True,1000)):
                with self.subTest(checkpoints=checkpoints),self.assertRaises(ValueError):
                    run_study('missing','missing',output,checkpoints=checkpoints,attack_families=('logistic',))
            with self.assertRaisesRegex(ValueError,'recent'):
                run_study('missing','missing',output,recent_window_ms=2000,attack_families=('logistic',))
            with patch('run_privacy_prefix_study._optional_libraries',side_effect=RuntimeError('missing pinned dependencies')):
                with self.assertRaisesRegex(RuntimeError,'pinned'):
                    run_study('missing','missing',output,attack_families=('hist_gradient_boosting',))
            self.assertFalse(output.exists())


class RunnerIntegrationTests(unittest.TestCase):
    def test_logistic_paths_preserve_calibration_split_control_and_utility(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);study,dataset=completed_source(root);output=root/'analysis'
            report=run_study(study,dataset,output,checkpoints=(200,1000),bootstrap_repeats=3,attack_families=('logistic',))
            output=output.resolve();manifest=read_json(output/'manifest.json');protocol=read_json(output/'protocol.json')
            self.assertEqual(manifest['status'],'complete')
            self.assertEqual(report['model_count'],60)
            self.assertEqual(len(report['attacks']),30)
            self.assertEqual(protocol['checkpoints_ms'],[200,1000])
            self.assertEqual(report['interior_checkpoints_ms'],[200])
            self.assertEqual(report['eof_checkpoint_ms'],1000)
            self.assertEqual(len(list((output/'models').glob('*.json'))),60)
            self.assertEqual(len(list((output/'models').glob('*.joblib'))),0)
            paths={tuple(r['key']):r for r in read_json(output/'score-paths-private.json')}
            self.assertEqual(len(paths),30)
            for attack in report['attacks']:
                key=tuple(attack[k] for k in ('stream','view','knowledge_profile','attack_family'))
                trajectory=paths[key]
                self.assertEqual(attack['training_groups'],2)
                self.assertEqual(attack['calibration_groups'],2)
                self.assertEqual(len(trajectory['calibration_rows']),4)
                self.assertTrue(all(len(r['scores'])==2 for r in trajectory['calibration_rows']))
                self.assertTrue(all(r['distribution']=='base' and r['group_id'].startswith('calibration-') for r in trajectory['calibration_rows']))
                self.assertEqual(attack['calibration'],calibrate_paths(trajectory['calibration_rows'],(200,1000)))
                for model in attack['checkpoint_models']:
                    saved=read_json(output/'models'/(model['model_id']+'.json'))
                    self.assertEqual(saved['metadata'],model['metadata'])
                    self.assertEqual(len(saved['calibration_scores']),4)
                    self.assertEqual(model['metadata']['fit_partition'],'training_only')
                    self.assertEqual(model['metadata']['training_rows'],4)
                for distribution,assessment in attack['test_by_distribution'].items():
                    rows=trajectory['test_by_distribution'][distribution]
                    self.assertEqual(len(rows),4)
                    self.assertTrue(all(r['distribution']==distribution and len(r['scores'])==2 for r in rows))
                    self.assertEqual(assessment['max_score']['threshold'],attack['calibration']['threshold'])
                    if attack['stream'] in (AUXILIARY_STREAM,'control_no_output'):
                        self.assertEqual(assessment['max_score']['roc_auc'],.5)
                        self.assertEqual(assessment['max_score']['tpr'],assessment['max_score']['fpr'])
                    if attack['stream']!=AUXILIARY_STREAM:self.assertIn('paired_vs_auxiliary',assessment)
                    if attack['view']=='history':self.assertIn('paired_history_minus_recent',assessment)
            compact=read_json(output/'online-utility-private.json')
            self.assertEqual(set(compact),{'compact_by_variant','paired_by_priority'})
            self.assertEqual(set(compact['compact_by_variant']),set(VARIANTS))
            for rows in compact['compact_by_variant'].values():
                self.assertEqual(len(rows),8)
                self.assertTrue(all(r['split']=='test' for r in rows))
                def contains_queries(value):
                    if isinstance(value,dict):return 'queries' in value or any(contains_queries(v) for v in value.values())
                    if isinstance(value,list):return any(contains_queries(v) for v in value)
                    return False
                self.assertFalse(contains_queries(rows))
            for distribution in ('base','background_density_shift'):
                self.assertEqual(report['online_utility'][distribution]['local_temporal_first']['worlds'],4)
                self.assertIn('temporal_first',report['online_matched_utility'][distribution])
            for relative,expected in manifest['artifact_sha256'].items():self.assertEqual(digest(output/relative),expected)
            marker=output/'untouched';marker.write_text('keep')
            with self.assertRaises(FileExistsError):
                run_study(study,dataset,output,checkpoints=(200,1000),attack_families=('logistic',))
            self.assertEqual(marker.read_text(),'keep')

    def test_manifest_tracks_analysis_freeze_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);study,dataset=completed_source(root);output=root/'freeze-failed'
            with patch('run_privacy_prefix_study.shutil.copyfile',side_effect=OSError('intentional freeze failure')):
                with self.assertRaisesRegex(OSError,'freeze failure'):
                    run_study(study,dataset,output,checkpoints=(1000,),attack_families=('logistic',))
            self.assertEqual(read_json(output/'manifest.json')['status'],'failed')
            self.assertEqual(read_json(output/'failure.json')['error_type'],'OSError')
            self.assertFalse((output/'report.json').exists())

    def test_failure_manifest_and_source_mutation_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);study,dataset=completed_source(root);output=root/'failed'
            with patch('run_privacy_prefix_study.fit_attack',side_effect=RuntimeError('intentional fitting failure')):
                with self.assertRaisesRegex(RuntimeError,'intentional'):
                    run_study(study,dataset,output,checkpoints=(200,1000),bootstrap_repeats=0,attack_families=('logistic',))
            self.assertEqual(read_json(output/'manifest.json')['status'],'failed')
            self.assertTrue((output/'failure.json').is_file())
            from run_privacy_prefix_study import fit_attack as original
            changed=[];public_path=next((study/'public').glob('*.json'))
            def mutate(*args,**kwargs):
                if not changed:
                    with public_path.open('ab') as stream:stream.write(b'\n')
                    changed.append(True)
                return original(*args,**kwargs)
            with patch('run_privacy_prefix_study.fit_attack',side_effect=mutate):
                with self.assertRaisesRegex(ValueError,'changed during analysis'):
                    run_study(study,dataset,root/'changed',checkpoints=(200,1000),bootstrap_repeats=0,attack_families=('logistic',))
            self.assertEqual(read_json(root/'changed'/'manifest.json')['status'],'failed')


def optional_histogram_available():
    try:return sys.version_info>=(3,11) and importlib.metadata.version('scikit-learn')==SKLEARN_VERSION
    except importlib.metadata.PackageNotFoundError:return False


@unittest.skipUnless(optional_histogram_available(),'Requires pinned optional histogram environment')
class HistogramIntegrationTests(unittest.TestCase):
    def test_histogram_calibration_scores_persist_without_loading_input_models(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);study,dataset=completed_source(root);output=root/'histogram'
            report=run_study(study,dataset,output,checkpoints=(1000,),bootstrap_repeats=0,attack_families=('hist_gradient_boosting',))
            self.assertEqual(report['model_count'],30)
            self.assertEqual(len(list((output/'models').glob('*.joblib'))),30)
            for attack in report['attacks']:
                model=attack['checkpoint_models'][0]
                saved=read_json(output/'models'/(model['model_id']+'.json'))
                self.assertEqual(len(saved['calibration_scores']),4)
                rows=saved['calibration_scores']
                self.assertEqual(attack['calibration'],calibrate_threshold([r['score'] for r in rows],[r['label'] for r in rows],.1))
                self.assertEqual(digest(Path(model['metadata']['model_path'])),model['metadata']['model_sha256'])
                self.assertEqual(Path(model['metadata']['model_path']).stat().st_mode&0o777,0o600)
            self.assertEqual((study/'models'/'never-load.joblib').read_bytes(),b'not a model')


if __name__=='__main__':unittest.main()
