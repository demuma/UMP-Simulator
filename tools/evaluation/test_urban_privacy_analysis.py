"""Synthetic evidence for the frozen urban training/calibration/test boundary."""
from copy import deepcopy
import math
import unittest
from unittest.mock import patch

import urban_privacy_analysis as analysis

GROUPS = {'train': ['train-a', 'train-b'], 'calibration': ['cal-a', 'cal-b'],
          'test': ['test-a', 'test-b']}
METHODS = ['adaptive_semantic_first', 'regional_static20']


def rows():
    result = []
    for split, groups in GROUPS.items():
        for index, group in enumerate(groups):
            for method in METHODS:
                for label, world in ((1, 'IN'), (0, 'OUT')):
                    feature = label + .01 * index
                    result.append({'group_id': group, 'split': split, 'world': world, 'label': label,
                        'method_id': method, 'features': [feature] + [0] * 110,
                        'scalar_features': [feature] + [0] * 30,
                        'auxiliary_features': [2, .1, .2, .15, .3 + .01 * index, .4, .1, .1],
                        'controls': {'prior_only': .5, 'unprotected': label,
                                     'no_output_features': [0] * 111},
                        'utility': {'retained_fraction': .8 if world == 'IN' else .7,
                                    'queries': {'conditional_mae': None, 'answered_fraction': .2}}})
    return result


def prepare(source=None):
    source = rows() if source is None else source
    return analysis.prepare_models([r for r in source if r['split'] != 'test'],
                                   expected_groups=GROUPS, method_ids=METHODS)


class FrozenAnalysisTests(unittest.TestCase):
    def test_end_to_end_controls_rates_contrast_and_world_specific_utility(self):
        source = rows(); locked = prepare(source)
        report = analysis.evaluate_models(locked, source)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['interpretation_gate'], 'controls_pass')
        for method in METHODS:
            for representation in analysis.REPRESENTATIONS:
                value = report['attacks'][method][representation]
                self.assertEqual(value['status'], 'evaluated')
                self.assertEqual(value['complete_test_groups'], 2)
                self.assertEqual(value['metrics']['roc_auc'], 1)
                self.assertEqual(value['metrics']['positive_cases'], 2)
                self.assertEqual(value['metrics']['negative_cases'], 2)
                self.assertGreater(value['metrics']['fpr_interval']['upper'], 0)
        for name in ('prior_only', 'auxiliary_only', 'no_output'):
            self.assertEqual(report['controls'][name]['metrics']['roc_auc'], .5)
            self.assertEqual(report['controls'][name]['observed_test_rows'], 4)
        self.assertEqual(report['controls']['unprotected']['metrics']['roc_auc'], 1)
        self.assertEqual(report['primary_contrast']['representations']['semantic111']['auc_difference'], 0)
        self.assertEqual(report['primary_contrast']['representations']['semantic111']['independent_groups'], 2)
        utility = report['utility'][METHODS[0]]
        self.assertEqual(utility['IN']['macro_means']['retained_fraction']['mean'], .8)
        self.assertEqual(utility['OUT']['macro_means']['retained_fraction']['mean'], .7)
        self.assertNotIn('queries.conditional_mae', utility['IN']['macro_means'])

    def test_authenticated_gate_checks_actual_unique_models_and_complete_pairs(self):
        source = rows(); locked = prepare(source)
        training = [r for r in source if r['split'] != 'test']
        self.assertEqual(analysis.validate_model_lock(locked, training)['status'], 'verified')
        bad = deepcopy(locked); bad['models'][0] = deepcopy(bad['models'][1])
        bad.pop('prepared_sha256'); bad['prepared_sha256'] = analysis.digest(bad)
        with self.assertRaisesRegex(ValueError, 'actual attack family'):
            analysis.validate_model_lock(bad, training)
        incomplete = [r for r in source if not (r['group_id'] == 'train-a' and r['world'] == 'OUT')]
        incomplete_locked = prepare(incomplete)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            analysis.validate_model_lock(incomplete_locked, [r for r in incomplete if r['split'] != 'test'])

    def test_test_rows_forbidden_before_fit(self):
        with self.assertRaisesRegex(ValueError, 'TEST rows'):
            analysis.prepare_models(rows(), expected_groups=GROUPS, method_ids=METHODS)

    def test_training_scaling_excludes_cal_and_test_and_inputs_not_mutated(self):
        source = rows(); before = deepcopy(source)
        locked = prepare(source)
        self.assertEqual(source, before)
        self.assertAlmostEqual(locked['attacks'][METHODS[0]]['semantic111']['model']['means'][0], .505)
        changed = deepcopy(source)
        for row in changed:
            if row['split'] == 'calibration':
                row['features'][0] += 100
                row['scalar_features'][0] += 100
        second = prepare(changed)
        self.assertEqual(locked['attacks'][METHODS[0]]['semantic111']['model'],
                         second['attacks'][METHODS[0]]['semantic111']['model'])
        before_locked = deepcopy(locked)
        analysis.evaluate_models(locked, source)
        self.assertEqual(locked, before_locked)

    def test_cal_threshold_remains_locked_and_test_score_direction_not_flipped(self):
        source = rows(); locked = prepare(source)
        threshold = locked['attacks'][METHODS[0]]['semantic111']['calibration']['threshold']
        for row in source:
            if row['split'] == 'test':
                row['features'][0] = 1 - row['label']
                row['scalar_features'][0] = 1 - row['label']
        report = analysis.evaluate_models(locked, source)
        attack = report['attacks'][METHODS[0]]['semantic111']
        self.assertEqual(attack['metrics']['roc_auc'], 0)
        self.assertEqual(attack['metrics']['threshold'], threshold)

    def test_changed_training_or_calibration_rows_rejected_at_test(self):
        for split in ('train', 'calibration'):
            source = rows(); locked = prepare(source)
            next(r for r in source if r['split'] == split)['features'][0] += .1
            with self.subTest(split=split), self.assertRaisesRegex(ValueError, 'TRAIN/CAL rows differ'):
                analysis.evaluate_models(locked, source)

    def test_modified_model_or_threshold_rejected(self):
        source = rows(); locked = prepare(source)
        locked['attacks'][METHODS[0]]['semantic111']['calibration']['threshold'] += .1
        with self.assertRaisesRegex(ValueError, 'bundle changed'):
            analysis.evaluate_models(locked, source)

    def test_wrong_source_split_world_label_or_method_rejected(self):
        mutations = [{'split': 'test'}, {'label': 0}, {'world': 'OUT'}, {'method_id': 'chosen-after-test'},
                     {'group_id': 'unknown-source'}]
        for change in mutations:
            source = [r for r in rows() if r['split'] != 'test']; source[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                analysis.prepare_models(source, expected_groups=GROUPS, method_ids=METHODS)

    def test_duplicate_pair_row_and_cross_split_group_rejected(self):
        source = [r for r in rows() if r['split'] != 'test']; source.append(deepcopy(source[0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            analysis.prepare_models(source, expected_groups=GROUPS, method_ids=METHODS)
        groups = deepcopy(GROUPS); groups['test'][0] = groups['train'][0]
        with self.assertRaisesRegex(ValueError, 'unique'):
            analysis.prepare_models([], expected_groups=groups, method_ids=METHODS)

    def test_missing_train_cal_cases_remain_na_without_substitution(self):
        source = rows()
        source = [r for r in source if not (r['group_id'] == 'train-a' and r['method_id'] == METHODS[0] and r['world'] == 'OUT')]
        locked = prepare(source)
        self.assertEqual(locked['attacks'][METHODS[0]]['semantic111']['status'], 'incomplete')
        report = analysis.evaluate_models(locked, source)
        self.assertIsNone(report['attacks'][METHODS[0]]['semantic111']['metrics'])
        self.assertEqual(report['attacks'][METHODS[1]]['semantic111']['status'], 'evaluated')
        self.assertEqual(report['status'], 'incomplete_or_diagnostic')

    def test_missing_test_pair_remains_na_and_denominator_preserved(self):
        source = rows(); locked = prepare(source)
        source = [r for r in source if not (r['group_id'] == 'test-a' and r['method_id'] == METHODS[0] and r['world'] == 'OUT')]
        report = analysis.evaluate_models(locked, source)
        attack = report['attacks'][METHODS[0]]['semantic111']
        self.assertEqual(attack['status'], 'incomplete')
        self.assertEqual(attack['expected_independent_test_groups'], 2)
        self.assertEqual(attack['complete_test_groups'], 1)
        self.assertIsNone(attack['metrics'])
        self.assertEqual(report['primary_contrast']['status'], 'unavailable')

    def test_nonconverged_fit_no_budget_extension_no_test_attack(self):
        original = analysis.empirical.fit_classifier
        calls = []
        def nonconverged(*args, **kwargs):
            calls.append(kwargs.copy())
            model = original(*args, **kwargs); model['converged'] = False
            return model
        with patch.object(analysis.empirical, 'fit_classifier', side_effect=nonconverged):
            locked = prepare()
        self.assertTrue(calls)
        self.assertTrue(all(call == analysis.MODEL_PARAMETERS for call in calls))
        report = analysis.evaluate_models(locked, rows())
        self.assertEqual(report['attacks'][METHODS[0]]['semantic111']['status'], 'nonconverged')
        self.assertIsNone(report['attacks'][METHODS[0]]['semantic111']['metrics'])
        self.assertIsNone(locked['attacks'][METHODS[0]]['semantic111']['calibration'])
        self.assertEqual(report['primary_contrast']['status'], 'unavailable')

    def test_method_duplicate_controls_must_be_identical(self):
        for field in ('auxiliary_features', 'controls'):
            source = rows()
            chosen = next(r for r in source if r['split'] == 'train' and r['method_id'] == METHODS[1])
            if field == 'auxiliary_features': chosen[field][0] += 1
            else: chosen[field]['unprotected'] = .2
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'Method-dependent'):
                prepare(source)

    def test_auxiliary_world_difference_rejected(self):
        source = rows()
        for row in source:
            if row['group_id'] == 'train-a' and row['world'] == 'OUT': row['auxiliary_features'][0] += 1
        with self.assertRaisesRegex(ValueError, 'Auxiliary knowledge differs'):
            prepare(source)

    def test_wrong_dimensions_nonfinite_scores_and_no_output_signal_rejected(self):
        for mutate in (lambda r: r['features'].pop(),
                       lambda r: r['scalar_features'].__setitem__(0, math.inf),
                       lambda r: r['auxiliary_features'].__setitem__(0, True),
                       lambda r: r['controls'].__setitem__('prior_only', .6),
                       lambda r: r['controls'].__setitem__('unprotected', 1.01),
                       lambda r: r['controls']['no_output_features'].__setitem__(0, 1)):
            source = rows(); mutate(source[0])
            with self.assertRaises(ValueError): prepare(source)

    def test_positive_control_coincident_background_not_forced_auc_one(self):
        source = rows()
        for row in source:
            if row['world'] == 'OUT' and row['group_id'].endswith('-a'):
                row['controls']['unprotected'] = 1
        report = analysis.evaluate_models(prepare(source), source)
        self.assertEqual(report['controls']['unprotected']['metrics']['roc_auc'], .75)
        self.assertEqual(report['positive_control_check']['status'], 'pass')
        for row in source:
            row['controls']['unprotected'] = 1
        report = analysis.evaluate_models(prepare(source), source)
        self.assertEqual(report['positive_control_check']['status'], 'diagnostic_required')
        self.assertEqual(report['interpretation_gate'], 'diagnose_controls_before_interpreting_lower_attack_success')

    def test_control_collapse_does_not_inflate_independent_recordings(self):
        source = rows(); report = analysis.evaluate_models(prepare(source), source)
        self.assertEqual(report['controls']['unprotected']['metrics']['positive_cases'], 2)
        self.assertEqual(report['controls']['unprotected']['metrics']['negative_cases'], 2)
        self.assertEqual(report['controls']['auxiliary_only']['fit_diagnostics']['training_rows'], 4)

    def test_auxiliary_summaries_hand_computed_only_whitelisted_coordinates(self):
        coverage = {'x': 10, 'y': 20, 'width': 80, 'height': 80, 'leaf_depth': 6}
        points = [{'observed_at_ms': 100, 'x': 18, 'y': 36, 'cell_id': 4096},
                  {'observed_at_ms': 300, 'x': 34, 'y': 52, 'cell_id': 4097}]
        values = analysis.auxiliary_features(points, coverage, 1000)
        for observed, expected in zip(values, [2, .1, .3, .2, .2, .3, .2, .2]):
            self.assertAlmostEqual(observed, expected)
        self.assertEqual(values, analysis.auxiliary_features(list(reversed(points)), coverage, 1000))
        for key in ('type', 'id', 'membership'):
            bad = deepcopy(points); bad[0][key] = 'private'
            with self.subTest(key=key), self.assertRaises(ValueError):
                analysis.auxiliary_features(bad, coverage, 1000)
        for bad in ([], [points[0], points[0]], [dict(points[0], observed_at_ms=0)], [dict(points[0], x=90)]):
            with self.assertRaises(ValueError): analysis.auxiliary_features(bad, coverage, 1000)


if __name__ == '__main__':
    unittest.main()
