"""Independent control/denominator tests and a real grouped seven-mode study."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest

from empirical_privacy import export_public, feature_vector
from occupancy import evaluate
from privacy_dataset import build_dataset, generate_case
from run_privacy_study import (clustered_intervals, control_result, load_dataset,
    paired_auc_difference, relative_file, run_study, stable_seed, utility_rollup)

ROOT=Path(__file__).resolve().parents[2]
BINARY=Path(os.environ.get('UMP_REPLAY_BINARY',str(ROOT/'simulator/build/AggregationReplay')))


class ControlAndStatisticsTests(unittest.TestCase):
    def test_exact_control_answers_unchanged_query_without_error(self):
        case=generate_case(17,'heterogeneous','control',2000)
        for world in ('present','absent'):
            replay=case[world]
            result=control_result(replay,'control_exact_count')
            utility=evaluate(replay,result)['summary']
            self.assertEqual(utility['answered_query_coverage'],1)
            self.assertAlmostEqual(utility['occupancy_mae'],0)
            export_public(result)
            public_total=sum(c['observation_contributions'] for r in result['releases'] for c in r['cells'])
            self.assertEqual(public_total,sum(len(b['observations']) for b in replay['batches']))

    def test_no_output_control_has_no_utility_or_membership_features(self):
        case=generate_case(18,'dense','hidden',1000)
        views=[export_public(control_result(case[world],'control_no_output')) for world in ('present','absent')]
        self.assertEqual(views[0],views[1])
        self.assertEqual(feature_vector(views[0],case['target_trace']),feature_vector(views[1],case['target_trace']))
        utility=evaluate(case['present'],control_result(case['present'],'control_no_output'))['summary']
        self.assertEqual(utility['answered_query_coverage'],0)
        self.assertIsNone(utility['occupancy_mae'])

    def test_cluster_bootstrap_keeps_paired_labels_and_sampling_unit(self):
        rows=[dict(group_id=group,label=label,score=float(label)) for group in ('a','b','c') for label in (0,1)]
        interval=clustered_intervals(rows,.5,40,9)
        self.assertEqual(interval['groups'],3)
        self.assertEqual(interval['intervals']['roc_auc'],[1,1])
        self.assertEqual(interval,clustered_intervals(rows,.5,40,9))
        with self.assertRaisesRegex(ValueError,'exactly one IN'):
            clustered_intervals(rows[:-1],.5,40,9)

    def test_paired_difference_uses_identical_case_support(self):
        rows=[dict(group_id=group,label=label,score=float(label)) for group in ('a','b') for label in (0,1)]
        result=paired_auc_difference(rows,deepcopy(rows),30,19)
        self.assertEqual(result['auc_difference'],0)
        self.assertEqual(result['interval'],[0,0])
        with self.assertRaisesRegex(ValueError,'identical test cases'):
            paired_auc_difference(rows,rows[:-1],30,19)

    def test_utility_rollup_preserves_missing_error_and_pools_denominators(self):
        common=dict(reference_queries=10,input_contributions=10,release_ages_ms=[],common_scored_queries=0)
        rows=[dict(common,answered_queries=2,scored_queries=2,occupancy_mae=3,released_contributions=4),
              dict(common,answered_queries=0,scored_queries=0,occupancy_mae=None,released_contributions=0)]
        report=utility_rollup(rows)
        self.assertEqual(report['answered_query_coverage'],.1)
        self.assertEqual(report['occupancy_mae'],3)
        self.assertEqual(report['contribution_retention'],.2)
        self.assertIsNone(utility_rollup(rows[1:])['occupancy_mae'])
        self.assertIsNone(report['common_support_mae'])
        self.assertIsNone(report['mean_release_age_ms'])

    def test_dataset_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            directory=root/'dataset'
            directory.mkdir()
            outside=root/'outside.json'
            outside.write_text('{}')
            with self.assertRaisesRegex(ValueError,'escapes'):
                relative_file(directory,'../outside.json')
            with self.assertRaisesRegex(ValueError,'relative paths'):
                relative_file(directory,str(outside))
            (directory/'link.json').symlink_to(outside)
            with self.assertRaisesRegex(ValueError,'escapes'):
                relative_file(directory,'link.json')

    def test_insufficient_split_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)/'dataset'
            build_dataset(directory,20,1,2,2,1000)
            with self.assertRaisesRegex(ValueError,'at least two'):
                load_dataset(directory)

    def test_stable_seeds_fit_generator_contract(self):
        value=stable_seed('a',17,.25)
        self.assertEqual(value,stable_seed('a',17,.25))
        self.assertGreaterEqual(value,0)
        self.assertLess(value,2**63)
        self.assertNotEqual(value,stable_seed('b',17,.25))


@unittest.skipUnless(BINARY.is_file(),'Build AggregationReplay for the real pipeline study')
class FullStudyIntegrationTests(unittest.TestCase):
    def test_real_study_is_public_only_grouped_deterministic_and_exclusive(self):
        with tempfile.TemporaryDirectory(prefix='ump-privacy-study-test-') as temporary:
            directory=Path(temporary)
            dataset=directory/'dataset'
            manifest=build_dataset(dataset,20261019,2,2,2,1000)
            dataset_bytes=(dataset/'manifest.json').read_bytes()
            outputs=[directory/'first',directory/'second']
            reports=[run_study(dataset,output,BINARY,knowledge_fractions=(.25,),
                               target_fpr=.1,bootstrap_repeats=10) for output in outputs]
            self.assertEqual(reports[0],reports[1])
            report=reports[0]
            self.assertEqual(report['independent_validation']['checks'],6*2*7)
            self.assertTrue(report['independent_validation']['all_valid'])
            self.assertEqual(len(report['attacks']),9*2)
            self.assertEqual(report['prior_only']['roc_auc'],.5)
            for attack in report['attacks']:
                self.assertEqual(attack['test_groups'],2)
                self.assertEqual(attack['calibration_groups'],2)
                self.assertEqual(attack['calibration']['negative_case_fpr_resolution'],.5)
                self.assertEqual(attack['test_uncertainty']['groups'],2)
                if attack['variant']=='control_no_output':
                    self.assertEqual(attack['test']['roc_auc'],.5)
            self.assertEqual(report['utility']['control_exact_count']['answered_query_coverage'],1)
            self.assertAlmostEqual(report['utility']['control_exact_count']['occupancy_mae'],0)
            self.assertEqual(report['utility']['control_no_output']['answered_query_coverage'],0)
            self.assertIsNone(report['utility']['control_no_output']['occupancy_mae'])
            for path in (outputs[0]/'public').glob('*.json'):
                public=json.loads(path.read_text())
                self.assertEqual(set(public),{'schema','coverage','sampling_period_ms','end_ms','releases'})
                self.assertNotIn('windows',public)
                self.assertNotIn('label',public)
                self.assertNotIn('run_id',public)
            self.assertEqual((dataset/'manifest.json').read_bytes(),dataset_bytes)
            evidence=(outputs[0]/'manifest.json').read_bytes()
            with self.assertRaises(FileExistsError):
                run_study(dataset,outputs[0],BINARY,knowledge_fractions=(.25,),bootstrap_repeats=10)
            self.assertEqual((outputs[0]/'manifest.json').read_bytes(),evidence)
            dangling=directory/'dangling'
            missing=directory/'missing-output'
            dangling.symlink_to(missing)
            with self.assertRaises(FileExistsError):
                run_study(dataset,dangling,BINARY,knowledge_fractions=(.25,),bootstrap_repeats=0)
            self.assertFalse(missing.exists())
            self.assertTrue(dangling.is_symlink())
            for output in outputs:
                saved=json.loads((output/'manifest.json').read_text())
                self.assertEqual(saved['status'],'complete')
                self.assertEqual(saved['split_groups'],manifest['group_counts'])
                self.assertTrue((output/'commands.json').is_file())
                self.assertTrue((output/'test-predictions-private.json').is_file())


if __name__=='__main__':
    unittest.main()
