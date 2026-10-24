#!/usr/bin/env python3
"""Small aggregate-plot contract checks; no native simulation or raw motion."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import plot_policy_comparison as plotting


def fixture():
    cases = {}
    for profile in plotting.PROFILES:
        for method, _ in plotting.METHODS:
            cases[profile + '_' + method] = {
                'independent_audit': {'status': 'verified', 'scalar_valid': True, 'published_policy_violations': 0},
                'stats': {'retained_fraction': .25, 'observation_weighted_semantic_loss': .5,
                          'observation_weighted_cell_side_m': 5,
                          'source_accounting': {'observation_to_release_delay_ms': {'p95': 3000}}}}
    return {'schema': 'ump.mapped-comparison.v1', 'status': 'verified',
            'protocol': {'comparison_kind': 'support_policy_sensitivity', 'matrix': [{'id': identity} for identity in cases]},
            'cases': cases}


class AggregatePlotTests(unittest.TestCase):
    def test_units_and_missing_are_preserved_without_mutating_summary(self):
        summary = fixture(); name = 'original_adaptive_immediate'
        summary['cases'][name]['stats']['observation_weighted_semantic_loss'] = None
        before = copy.deepcopy(summary)
        values = plotting.series(summary)
        self.assertEqual(values['retention']['original'], [25] * 5)
        self.assertIsNone(values['semantic_loss']['original'][0])
        self.assertEqual(values['semantic_loss']['support60'], [50] * 5)
        self.assertEqual(values['side']['original'], [5] * 5)
        self.assertEqual(values['delay_p95']['support60'], [3] * 5)
        self.assertEqual(summary, before)

    def test_reject_wrong_experiment_incomplete_matrix_failed_audit_and_invalid_metrics(self):
        for field, value in [('retained_fraction', float('nan')), ('retained_fraction', True),
                             ('retained_fraction', 1.1), ('observation_weighted_cell_side_m', -2)]:
            summary = fixture(); summary['cases']['original_adaptive_immediate']['stats'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): plotting.series(summary)
        for mutation in ('experiment', 'case', 'matrix', 'audit'):
            summary = fixture()
            if mutation == 'experiment': summary['protocol']['comparison_kind'] = 'methods'
            if mutation == 'case': summary['cases'].pop('support60_adaptive_immediate')
            if mutation == 'matrix': summary['protocol']['matrix'].append(summary['protocol']['matrix'][0])
            if mutation == 'audit': summary['cases']['original_adaptive_immediate']['independent_audit']['published_policy_violations'] = 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): plotting.series(summary)

    def test_render_fresh_png_svg_and_aggregate_provenance_with_explicit_na(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'summary.json'; output = root / 'figures'
            summary = fixture(); summary['cases']['original_adaptive_immediate']['stats']['observation_weighted_semantic_loss'] = None
            path.write_text(json.dumps(summary))
            metadata = plotting.plot(path, output)
            self.assertEqual((output / 'support-policy-comparison.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            svg = (output / 'support-policy-comparison.svg').read_text()
            self.assertIn('n/a', svg)
            self.assertIn('do not measure a privacy gain', svg)
            self.assertIsNone(metadata['metrics']['semantic_loss']['original'][0])
            self.assertNotIn('observations.json', (output / 'figure-provenance.json').read_text())
            before = (output / 'support-policy-comparison.png').read_bytes()
            with self.assertRaisesRegex(ValueError, 'fresh'): plotting.plot(path, output)
            self.assertEqual((output / 'support-policy-comparison.png').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
