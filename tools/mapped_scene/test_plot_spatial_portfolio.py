#!/usr/bin/env python3
"""Contract checks for measured spatial responses; no source motion or fitting."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest

import plot_spatial_portfolio as plotting
import run_comparison


def fixture(profiles=run_comparison.SPATIAL_PROFILES):
    matrix=run_comparison.spatial_portfolio_variants(dict(width=80,height=80,leaf_depth=6),profiles)
    cases={}
    for row in matrix:
        n=0 if row['id'].startswith('original_fixed_20m') else 75
        cases[row['id']]={'independent_audit':{'status':'verified','scalar_valid':True,'published_policy_violations':0},
            'stats':{'input_observation_contributions':100,'retained_fraction':n/100,
                'observation_weighted_semantic_loss':.5 if n else None,
                'full_input_semantic_distortion':.625 if n else 1,
                'source_accounting':{'observation_to_release_delay_ms':{'p95':1500 if n else None}}}}
    return {'schema':'ump.mapped-comparison.v1','status':'verified','source':{'input_observation_contributions':100},
            'protocol':{'comparison_kind':'spatial_resolution_portfolio','spatial_profiles':list(profiles),'matrix':matrix},'cases':cases}


class SpatialPortfolioPlotTests(unittest.TestCase):
    def test_percent_seconds_missing_and_actual_zero_are_distinct(self):
        summary=fixture();before=copy.deepcopy(summary)
        values=plotting.measured_series(summary)
        self.assertEqual(values['profiles'],['original','spatial20'])
        self.assertEqual(values['cases']['spatial20_fixed_20m_400ms']['retained_fraction'],75)
        self.assertEqual(values['cases']['spatial20_fixed_20m_400ms']['delay_p95_ms'],1.5)
        self.assertEqual(values['cases']['original_fixed_20m_400ms']['retained_fraction'],0)
        self.assertIsNone(values['cases']['original_fixed_20m_400ms']['observation_weighted_semantic_loss'])
        self.assertEqual(values['cases']['original_fixed_20m_400ms']['full_input_semantic_distortion'],100)
        self.assertEqual(summary,before)

    def test_declared_one_contract_subset_is_allowed(self):
        values=plotting.measured_series(fixture(('spatial20',)))
        self.assertEqual(values['profiles'],['spatial20'])
        self.assertEqual(len(values['cases']),8)

    def test_reject_missing_cases_failed_audits_changed_methods_and_different_denominators(self):
        for mutation in ('status','experiment','matrix_duplicate','missing_case','bad_audit','filtering','wrong_side','wrong_window','different_denominator'):
            summary=fixture();case=summary['cases']['original_adaptive_immediate'];matrix=summary['protocol']['matrix']
            if mutation=='status':summary['status']='running'
            if mutation=='experiment':summary['protocol']['comparison_kind']='support_policy_sensitivity'
            if mutation=='matrix_duplicate':matrix.append(matrix[0])
            if mutation=='missing_case':summary['cases'].pop('original_fixed_20m_1000ms')
            if mutation=='bad_audit':case['independent_audit']['published_policy_violations']=1
            if mutation=='filtering':matrix[0]['suppression_cap']=.1
            if mutation=='wrong_side':next(row for row in matrix if row['mode']=='fixed')['side_m']=7
            if mutation=='wrong_window':next(row for row in matrix if row['mode']=='fixed')['window']=750
            if mutation=='different_denominator':case['stats']['input_observation_contributions']=99
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):plotting.measured_series(summary)
        for invalid in (True,-.1,1.1,float('nan'),float('inf')):
            summary=fixture();summary['cases']['original_adaptive_immediate']['stats']['retained_fraction']=invalid
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):plotting.measured_series(summary)

    def test_render_aggregate_figures_na_and_explicit_nonregression_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);summary_path=root/'summary.json';summary_path.write_text(json.dumps(fixture()))
            output=root/'figures';metadata=plotting.plot(summary_path,output)
            for profile in ('original','spatial20'):
                self.assertEqual((output/f'spatial-portfolio-{profile}.png').read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
                svg=(output/f'spatial-portfolio-{profile}.svg').read_text()
                self.assertIn('not a fitted regression',svg)
                self.assertIn('same-policy reference',svg)
            self.assertIn('n/a',(output/'spatial-portfolio-original.svg').read_text())
            self.assertIn('negative controls',(output/'spatial-portfolio-original.svg').read_text())
            self.assertEqual(metadata['fixed_grid_sides_m'],[5,10,20])
            self.assertIn('no regression',metadata['trend_scope'])
            self.assertNotIn('observations.json',(output/'figure-provenance.json').read_text())
            with self.assertRaisesRegex(ValueError,'fresh'):plotting.plot(summary_path,output)


if __name__=='__main__':unittest.main()
