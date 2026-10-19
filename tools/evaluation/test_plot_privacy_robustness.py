"""Full-cohort figure validation and deterministic immutable scientific exports."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from plot_privacy_robustness import COHORTS, COMBINATIONS, METHODS, export, prepare


def fixture():
    counts = {'base': 32, 'background_density_shift': 48}
    attacks = []
    for name, _ in METHODS:
        for family, profile, *_ in COMBINATIONS:
            attacks.append(dict(variant=name, attack_family=family, knowledge_profile=profile,
                test_by_distribution={distribution:dict(test_groups=counts[distribution], test={'roc_auc': .65},
                    uncertainty=dict(groups=counts[distribution],confidence=.95,repeats=400,intervals={'roc_auc': [.5,.8]}))
                    for distribution, _ in COHORTS}))
    return dict(schema='ump.privacy-robustness-report.v1',status='complete',test_cohorts_independent=True,
        membership_prior=.5,independent_validation={'all_valid': True},attacks=attacks,
        utility_by_distribution={distribution:{name:dict(case_worlds=2*counts[distribution],reference_queries=100,
            answered_queries=20,answered_query_coverage=.2,input_contributions=1000,released_contributions=700,
            contribution_retention=.7) for name,_ in METHODS} for distribution,_ in COHORTS})


class RobustnessFigureTests(unittest.TestCase):
    def test_all_seven_methods_four_attacks_and_actual_separate_cohort_counts(self):
        cohorts = prepare(fixture())
        self.assertEqual([c['test_groups'] for c in cohorts], [32, 48])
        for cohort in cohorts:
            self.assertEqual([r['name'] for r in cohort['rows']], [name for name,_ in METHODS])
            self.assertTrue(all(len(r['attacks'])==4 for r in cohort['rows']))

    def test_rejects_incomplete_duplicate_unknown_and_wrong_schema(self):
        for change in ('schema','status','missing_attack','duplicate_attack','unknown_attack','missing_cohort','missing_utility','independence'):
            report = fixture()
            if change=='schema': report['schema']='ump.empirical-privacy-report.v1'
            elif change=='status': report['status']='running'
            elif change=='missing_attack': report['attacks'].pop()
            elif change=='duplicate_attack': report['attacks'].append(deepcopy(report['attacks'][0]))
            elif change=='unknown_attack': report['attacks'][0]['attack_family']='unreviewed'
            elif change=='missing_cohort': report['attacks'][0]['test_by_distribution'].pop('base')
            elif change=='missing_utility': report['utility_by_distribution']['base'].pop(METHODS[0][0])
            else: report['test_cohorts_independent']=False
            with self.subTest(change=change), self.assertRaises(ValueError): prepare(report)

    def test_rejects_nonfinite_reversed_intervals_and_inconsistent_denominators(self):
        for change in ('nan_auc','inf_interval','reversed_interval','groups','ci_groups','confidence','zero_repeats',
                       'worlds','coverage','retention','nan_utility','missing_interval','boolean_count'):
            report=fixture()
            assessment=report['attacks'][0]['test_by_distribution']['base']
            utility=report['utility_by_distribution']['base'][METHODS[0][0]]
            if change=='nan_auc': assessment['test']['roc_auc']=float('nan')
            elif change=='inf_interval': assessment['uncertainty']['intervals']['roc_auc'][1]=float('inf')
            elif change=='reversed_interval': assessment['uncertainty']['intervals']['roc_auc']=[.8,.5]
            elif change=='groups': assessment['test_groups']=12
            elif change=='ci_groups': assessment['uncertainty']['groups']=12
            elif change=='confidence': assessment['uncertainty']['confidence']=.8
            elif change=='zero_repeats': assessment['uncertainty']['repeats']=0
            elif change=='worlds': utility['case_worlds']=10
            elif change=='coverage': utility['answered_query_coverage']=.9
            elif change=='retention': utility['contribution_retention']=.9
            elif change=='nan_utility': utility['contribution_retention']=float('nan')
            elif change=='missing_interval': assessment['uncertainty']['intervals']={}
            else: assessment['test_groups']=True
            with self.subTest(change=change), self.assertRaises(ValueError): prepare(report)

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'Optional matplotlib is not installed')
    def test_deterministic_exports_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='ump-robustness-figure-') as directory:
            first=export(fixture(),Path(directory)/'first')
            second=export(fixture(),Path(directory)/'second')
            self.assertEqual([p.read_bytes() for p in first],[p.read_bytes() for p in second])
            svg=first[1].read_text()
            for text in ('n = 32 independent paired groups','n = 48 independent paired groups',
                         'no pooling','no universal privacy guarantee','Boosted trees / uncertain 25%'):
                self.assertIn(text,svg)
            with self.assertRaises(ValueError): export(fixture(),Path(directory)/'first')
            self.assertEqual(first[0].read_bytes(),second[0].read_bytes())
            blocker=Path(directory)/'blocked.svg'
            blocker.symlink_to(Path(directory)/'not-existing')
            with self.assertRaises(ValueError): export(fixture(),Path(directory)/'blocked')
            self.assertFalse((Path(directory)/'blocked.png').exists())


if __name__=='__main__': unittest.main()
