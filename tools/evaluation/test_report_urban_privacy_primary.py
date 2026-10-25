"""Aggregate allowlist, missing-case visibility and scientific report contracts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import report_urban_privacy_primary as reporting
import urban_privacy_analysis as analysis
from test_urban_privacy_analysis import GROUPS, METHODS, rows

SECRET = 'PRIVATE_TARGET_IDENTIFIER_AND_PATH'


def private_report():
    source = rows()
    models = analysis.prepare_models([r for r in source if r['split'] != 'test'],
                                    expected_groups=GROUPS, method_ids=METHODS)
    assessment = analysis.evaluate_models(models, source)
    groups = []
    for split, ids in GROUPS.items():
        for group in ids:
            groups.append({'group_id': group, 'split': split, 'status': 'verified',
                           'pair': {'target_id': SECRET, 'private_path': SECRET},
                           'cases': [{'method_id': method, 'world': world, 'status': 'verified',
                                      'command': [SECRET], 'error': SECRET, 'artifacts': {SECRET: SECRET}}
                                     for method in METHODS for world in ('IN', 'OUT')]})
    return {'schema': 'ump.urban-primary-report.v1', 'manifest_sha256': 'a'*64,
            'implementation_sha256': 'b'*64, 'group_outcomes': groups, 'analysis': assessment,
            'model_weights': [SECRET], 'native_source': SECRET}


class PublicPrimaryReportTests(unittest.TestCase):
    def test_allowlist_discards_private_ids_scores_paths_weights_and_unknown_metadata(self):
        private = private_report()
        for method in private['analysis']['attacks'].values():
            for representation in method.values():
                representation['group_scores'][0]['target_id'] = SECRET
                representation['private_model'] = {'weights': SECRET}
                representation['fit_diagnostics']['private_note'] = SECRET
                representation['locked_calibration']['private_note'] = SECRET
        private['analysis']['utility'][METHODS[0]]['IN']['macro_means'][SECRET] = {'mean': 999, 'recordings': 2}
        private['analysis']['negative_control_checks']['prior_only']['private_note'] = SECRET
        public = reporting.compact_report(private)
        encoded = json.dumps(public, allow_nan=False)
        self.assertNotIn(SECRET, encoded)
        for forbidden in ('group_scores', 'target_id', 'group_id', 'private_path', 'weights', 'command', 'error'):
            self.assertNotIn('"'+forbidden+'"', encoded)
        self.assertEqual(len(public['methods']), 11)
        self.assertEqual(public['methods'][-1]['id'], 'adaptive_semantic_first')
        self.assertEqual(public['methods'][-1]['attacks']['semantic111']['metrics']['roc_auc'], 1)

    def test_missing_and_nonconverged_methods_remain_visible_without_estimates(self):
        private = private_report()
        missing = reporting.compact_report(private)['methods'][0]
        self.assertEqual(missing['attacks']['semantic111']['status'], 'missing')
        self.assertIsNone(missing['attacks']['semantic111']['metrics'])
        for name in ('semantic111', 'scalar31'):
            attack = private['analysis']['attacks'][METHODS[0]][name]
            attack.update(status='nonconverged', metrics=None, locked_calibration=None)
            attack['fit_diagnostics']['converged'] = False
        public = reporting.compact_report(private)
        adaptive = public['methods'][-1]
        self.assertEqual(adaptive['attacks']['semantic111']['status'], 'nonconverged')
        self.assertIn('nonconverged', reporting.markdown(public))
        self.assertIn('Fixed 10 m / 0.4 s', reporting.markdown(public))

    def test_incomplete_structural_report_explicitly_states_no_heldout_result(self):
        private = {'schema': 'ump.urban-primary-report.v1', 'group_outcomes': [], 'analysis': None}
        public = reporting.compact_report(private)
        self.assertEqual(public['analysis_status'], 'not_evaluated')
        self.assertTrue(all(m['attacks']['semantic111']['metrics'] is None for m in public['methods']))
        self.assertIn('No held-out privacy result', reporting.markdown(public))
        outcome = public['source_and_execution']
        self.assertEqual(outcome['planned_recordings'], 72)
        self.assertEqual(outcome['recording_status_by_split']['test']['not_reported'], 32)
        self.assertEqual(outcome['method_world_status'][METHODS[0]]['unreported'], 144)

    def test_counts_are_aggregated_not_multiplied_by_attack_representations(self):
        public = reporting.compact_report(private_report())
        counts = public['source_and_execution']
        self.assertEqual(counts['recording_status_by_split']['train']['verified'], 2)
        self.assertEqual(counts['method_world_status'][METHODS[0]]['observed'], 12)
        self.assertEqual(public['controls']['auxiliary_only']['metrics']['positive_cases'], 2)
        self.assertEqual(public['primary_contrast']['representations']['semantic111']['independent_groups'], 2)

    def test_unknown_status_is_normalized_without_publishing_private_reason(self):
        private = private_report()
        private['group_outcomes'][0]['status'] = SECRET
        private['analysis']['attacks'][METHODS[0]]['semantic111'].update(status=SECRET, metrics=None)
        public = reporting.compact_report(private)
        self.assertNotIn(SECRET, json.dumps(public))
        self.assertEqual(public['source_and_execution']['recording_status_by_split']['train']['other'], 1)

    def test_unknown_method_representation_control_and_wrong_hash_rejected(self):
        changes = [lambda p: p['analysis']['attacks'].update({SECRET: {}}),
                   lambda p: p['analysis']['attacks'][METHODS[0]].update({SECRET: {}}),
                   lambda p: p['analysis']['controls'].update({SECRET: {}}),
                   lambda p: p.update(manifest_sha256=SECRET)]
        for mutate in changes:
            private = private_report(); mutate(private)
            with self.assertRaises(ValueError): reporting.compact_report(private)

    def test_unregistered_comparator_or_changed_interval_contract_rejected(self):
        changes = [lambda p: p['analysis']['primary_contrast'].update(right='chosen_on_test'),
                   lambda p: p['analysis']['primary_contrast']['representations']['semantic111'].update(seed=1),
                   lambda p: p['analysis']['attacks'][METHODS[0]]['semantic111']['metrics']['tpr_interval'].update(confidence_level=.8),
                   lambda p: p['analysis']['attacks'][METHODS[0]]['semantic111']['locked_calibration'].update(target_fpr=.2)]
        for mutate in changes:
            private = private_report(); mutate(private)
            with self.assertRaises(ValueError): reporting.compact_report(private)

    def test_duplicate_source_or_case_rejected_instead_of_double_counted(self):
        private = private_report(); private['group_outcomes'].append(deepcopy(private['group_outcomes'][0]))
        with self.assertRaises(ValueError): reporting.compact_report(private)
        private = private_report(); cases = private['group_outcomes'][0]['cases']; cases.append(deepcopy(cases[0]))
        with self.assertRaises(ValueError): reporting.compact_report(private)

    def test_world_utility_has_own_reference_and_per_metric_available_denominator(self):
        public = reporting.compact_report(private_report())
        utility = public['methods'][-1]['utility']
        self.assertEqual(utility['IN']['macro_means']['retained_fraction'], {'mean': .8, 'recordings': 2})
        self.assertEqual(utility['OUT']['macro_means']['retained_fraction'], {'mean': .7, 'recordings': 2})
        self.assertNotIn('queries.conditional_mae', utility['IN']['macro_means'])
        text = reporting.markdown(public)
        self.assertIn('Conditional MAE', text)
        self.assertIn('not measured live delivery', text)
        self.assertIn('not isolate semantic leakage', text)

    def test_export_roundtrip_small_hash_receipt_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); private = root/'private.json'
            private.write_text(json.dumps(private_report(), allow_nan=False))
            output = root/'public'
            public = reporting.export(private, output, make_figures=False)
            self.assertEqual(public, json.loads((output/'summary.json').read_text()))
            self.assertEqual(public['provenance']['private_report_sha256'], hashlib.sha256(private.read_bytes()).hexdigest())
            receipt = json.loads((output/'artifact-receipt.json').read_text())
            for name, expected in receipt['artifacts_sha256'].items():
                self.assertEqual(hashlib.sha256((output/name).read_bytes()).hexdigest(), expected)
            self.assertLess(sum(p.stat().st_size for p in output.iterdir()), 100000)
            self.assertNotIn(SECRET, ''.join(p.read_text() for p in output.iterdir()))
            with self.assertRaises(FileExistsError): reporting.export(private, output, make_figures=False)


if __name__ == '__main__':
    unittest.main()
