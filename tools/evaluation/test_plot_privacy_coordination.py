"""Validate the privacy figure's experimental units and immutable export."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from plot_privacy_coordination import METHODS, export, prepare


def fixture():
    return dict(schema='ump.empirical-privacy-report.v1', status='complete', coordination_study=True,
        attacks=[dict(variant=name, knowledge_fraction=fraction, feature_set='counts_geometry_time',
            test_groups=80, test={'roc_auc': .6}, test_uncertainty={'intervals': {'roc_auc': [.4, .8]}})
            for name, _ in METHODS for fraction in (.25, 1.0)],
        utility={name:dict(answered_query_coverage=.2,contribution_retention=.7) for name, _ in METHODS})


class PrivacyFigureTests(unittest.TestCase):
    def test_realized_group_count_and_all_nine_methods_plus_controls(self):
        rows, groups = prepare(fixture())
        self.assertEqual(groups, 80)
        self.assertEqual(len(rows), 11)
        self.assertEqual([row['name'] for row in rows], [name for name, _ in METHODS])

    def test_rejects_legacy_partial_duplicate_and_inconsistent_units(self):
        for change in ('legacy', 'incomplete', 'missing', 'duplicate', 'group_count', 'interval', 'nan'):
            report=fixture()
            if change=='legacy': report['coordination_study']=False
            elif change=='incomplete': report['status']='running'
            elif change=='missing': report['attacks'].pop()
            elif change=='duplicate': report['attacks'].append(deepcopy(report['attacks'][0]))
            elif change=='group_count': report['attacks'][0]['test_groups']=32
            elif change=='interval': report['attacks'][0]['test_uncertainty']['intervals']['roc_auc']=[.8,.4]
            else: report['attacks'][0]['test']['roc_auc']=float('nan')
            with self.subTest(change=change), self.assertRaises(ValueError): prepare(report)

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'Optional matplotlib is not installed')
    def test_frozen_exports_are_identical_and_preserve_existing_files(self):
        with tempfile.TemporaryDirectory(prefix='ump-privacy-figure-') as temporary:
            first=export(fixture(),Path(temporary)/'first')
            second=export(fixture(),Path(temporary)/'second')
            for a,b in zip(first,second): self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertIn('80 independent paired held-out groups',first[1].read_text())
            with self.assertRaises(ValueError): export(fixture(),Path(temporary)/'first')
            self.assertEqual(first[0].read_bytes(),second[0].read_bytes())


if __name__=='__main__': unittest.main()
