"""Synthetic public projection tests; no source reads, model fitting or TEST execution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import report_urban_selective_suppression as r

SECRET = 'PRIVATE_TARGET_PATH_SCORE_AND_MODEL'


def rate(successes, trials):
    return dict(method='two_sided_exact_clopper_pearson', confidence_level=.95,
                successes=successes, trials=trials, estimate=successes / trials,
                lower=0., upper=1.)


def metrics(auc=.7, n=32):
    tp, fp = (16, 2) if n == 32 else (8, 1)
    return dict(roc_auc=auc, tpr=tp/n, fpr=fp/n, balanced_accuracy=.7,
                precision_at_evaluation_prior=.7, evaluation_prior=.5,
                positive_cases=n, negative_cases=n, true_positive=tp, false_positive=fp,
                true_negative=n-fp, false_negative=n-tp, advantage=(tp-fp)/n,
                threshold=.67321, tpr_interval=rate(tp, n), fpr_interval=rate(fp, n))


def attack(features, auc=.7):
    return dict(status='evaluated', metrics=metrics(auc), expected_independent_test_groups=32,
                complete_test_groups=32, observed_test_rows=64,
                fit_diagnostics=None if features is None else dict(converged=True, training_rows=48,
                    feature_count=features, iterations=3, training_objective=.4),
                locked_calibration=dict(target_fpr=.1, threshold=.67321,
                    negative_case_fpr_resolution=1/16, calibration=metrics(.7, 16)),
                group_scores=[dict(group_id=SECRET, score=.7, label=1)],
                model=dict(weights=[SECRET], threshold=SECRET))


def private_report(utility=False):
    catalog, utilities, attacks = [], {}, {}
    for identity in r.METHOD_IDS:
        base = identity.removesuffix('_selective')
        enabled = identity in r.NEW_IDS
        kind = 'regional_static' if base == 'regional_static20' else 'native_fixed' if base == 'fixed20_400ms' else 'native_adaptive'
        catalog.append(dict(id=identity, base_method_id=base, label=SECRET, kind=kind,
                            suppression_enabled=enabled, suppression_cap=.1 if enabled else 0,
                            semantic_generalization='enabled'))
        means = {key: dict(mean=value, recordings=32) for key, value in (
            ('retained_fraction', .85 if enabled else .8), ('full_input_J', .2 if enabled else .25),
            ('retained_semantic_loss', .1), ('mean_retained_cell_side_m', 20.),
            ('mean_retained_interval_ms', 400.), ('logical_seal_delay_ms.mean', 200.),
            ('published_policy_violations', 0.), ('selectively_suppressed_fraction_of_input', .05 if enabled else 0.))}
        for source_type in r.SOURCE_TYPES:
            stem = 'source_accounting.by_source_type.' + source_type + '.'
            for key, value in (('retained_fraction', .85 if enabled else .8),
                               ('selectively_suppressed_fraction', .05 if enabled else 0.),
                               ('selectively_suppressed_observations', 5. if enabled else 0.)):
                means[stem + key] = dict(mean=value, recordings=32)
        utilities[identity] = {world: dict(expected_recordings=32, observed_recordings=32, macro_means=deepcopy(means))
                               for world in ('IN', 'OUT')}
        attacks[identity] = {rep: attack(111 if rep == 'semantic111' else 31, .65 if enabled else .7)
                             for rep in r.REPRESENTATIONS}
    paired = {}
    for key, left, right, _ in r.CONTRASTS[:7]:
        paired[key] = dict(left=left, right=right, world='IN', metrics={
            metric: dict(mean_difference=.05 if metric == 'retained_fraction' else -.05 if metric == 'full_input_J' else 0.,
                         ci95=[-.1, .1], paired_recordings=32, replicates=1000, confidence_level=.95)
            for metric in r.UTILITY_METRICS})
    result = dict(schema=r.UTILITY_INPUT_SCHEMA if utility else r.INPUT_SCHEMA,
                  phase='utility' if utility else 'assessed', method_catalog=catalog,
                  study_design=dict(r.DESIGN_COUNTS, suppression_cap=.1, semantic_generalization='enabled',
                                    test_reused_exploratory=True, protected_unit=SECRET, attackscope=SECRET),
                  utility=utilities, paired_utility_contrasts=paired,
                  lineage={key: dict(path='/private/' + SECRET, sha256=hashlib.sha256(key.encode()).hexdigest())
                           for key in r.LINEAGE_KEYS}, target_id=SECRET, model_weights=[SECRET])
    if utility:
        result['mia_status'] = 'not_started'
    else:
        controls = {name: attack(8 if name == 'auxiliary_only' else 111 if name == 'no_output' else None)
                    for name in r.strict.CONTROLS}
        result['analysis'] = dict(schema='ump.urban-privacy-analysis.v1', status='complete', attacks=attacks,
                                  utility=deepcopy(utilities), controls=controls,
                                  negative_control_checks={name: dict(status='pass', private=SECRET)
                                      for name in ('prior_only', 'auxiliary_only', 'no_output')},
                                  positive_control_check=dict(status='pass'), interpretation_gate='controls_pass')
        result['exploratory_contrasts'] = {}
        for key, left, right, seed in r.CONTRASTS:
            difference = -.05 if right in r.BASE_IDS else 0.
            result['exploratory_contrasts'][key] = dict(left=left, right=right, metric='ROC_AUC', representations={
                rep: dict(auc_difference=difference, interval=[-.1, .1], confidence_level=.95,
                          seed=seed, replicates=1000, independent_groups=32, group_ids=[SECRET])
                for rep in r.REPRESENTATIONS})
    return result


class SelectiveSuppressionReportingTests(unittest.TestCase):
    def test_complete_assessment_has_seven_registered_pairs_and_twelve_contrasts(self):
        public = r.build_report(private_report())
        self.assertEqual(public['utility_status'], 'complete')
        self.assertEqual(public['mia_status'], 'complete')
        self.assertEqual(len(public['methods']), 14)
        self.assertEqual(len(public['exploratory_contrasts']), 12)
        self.assertTrue(all(item['semantic_generalization'] == 'enabled' for item in public['methods']))
        self.assertEqual(public['study_design']['workers'], 6)
        self.assertIn('ON minus OFF', r.markdown(public))

    def test_utility_stage_does_not_expose_old_or_new_attack_scores(self):
        public = r.build_report(private_report(utility=True))
        self.assertEqual(public['mia_status'], 'not_started')
        self.assertTrue(all(item['attacks'][rep]['metrics'] is None for item in public['methods'] for rep in r.REPRESENTATIONS))
        self.assertIn('MIA has not started', r.markdown(public))
        for mutate in (lambda raw: raw.update(analysis={'status': 'complete'}),
                       lambda raw: raw.update(exploratory_contrasts={'unexpected': {}}),
                       lambda raw: raw.update(mia_status='started')):
            raw = private_report(utility=True)
            mutate(raw)
            with self.assertRaises(ValueError):
                r.build_report(raw)

    def test_allowlist_removes_private_ids_paths_scores_models_and_thresholds_without_mutation(self):
        raw = private_report()
        raw['utility'][r.BASE_IDS[0]]['IN']['macro_means'][SECRET] = dict(mean=1., recordings=32)
        raw['analysis']['utility'] = deepcopy(raw['utility'])
        before = deepcopy(raw)
        public = r.build_report(raw)
        self.assertEqual(raw, before)
        encoded = json.dumps(public, allow_nan=False)
        for forbidden in (SECRET, '/private/', 'group_scores', 'group_id', 'weights', 'threshold', 'seed', 'training_objective'):
            self.assertNotIn(forbidden, encoded)
        self.assertTrue(all(value is not None for value in public['lineage'].values()))

    def test_no_referenced_artifact_is_opened(self):
        raw = private_report()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Referenced artifact read')):
            self.assertEqual(r.build_report(raw)['mia_status'], 'complete')

    def test_catalog_capability_counts_and_lineage_are_validated(self):
        mutations = (lambda raw: raw['method_catalog'].pop(),
                     lambda raw: raw['method_catalog'][0].update(suppression_enabled=True),
                     lambda raw: raw['method_catalog'][-1].update(suppression_cap=.2),
                     lambda raw: raw['method_catalog'][0].update(semantic_generalization='exact_only'),
                     lambda raw: raw['study_design'].update(test=31),
                     lambda raw: raw['study_design'].update(old_model_refits=1),
                     lambda raw: raw['study_design'].update(test_reused_exploratory=False),
                     lambda raw: raw['lineage']['old_report'].update(sha256='missing'))
        for mutate in mutations:
            raw = private_report()
            mutate(raw)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                r.build_report(raw)

    def test_missing_historical_cohort_remains_unavailable(self):
        raw = private_report(utility=True)
        key = 'source_accounting.by_source_type.' + r.SOURCE_TYPES[0] + '.selectively_suppressed_fraction'
        raw['utility'][r.BASE_IDS[0]]['IN']['macro_means'].pop(key)
        public = r.build_report(raw)
        self.assertNotIn(key, public['methods'][0]['utility']['IN']['macro_means'])
        self.assertEqual(r._metric(public['methods'][0], key), 'NA (n=0)')

    def test_undefined_conditional_loss_and_metric_specific_N_are_preserved(self):
        raw = private_report(utility=True)
        means = raw['utility'][r.NEW_IDS[0]]['IN']['macro_means']
        means['retained_semantic_loss'] = dict(mean=None, recordings=0)
        key = 'source_accounting.by_source_type.' + r.SOURCE_TYPES[0] + '.retained_fraction'
        means[key] = dict(mean=.4, recordings=3)
        public = r.build_report(raw)
        method = next(item for item in public['methods'] if item['id'] == r.NEW_IDS[0])
        self.assertEqual(r._metric(method, 'retained_semantic_loss'), 'NA (n=0)')
        self.assertEqual(r._metric(method, key), '0.400 (n=3)')

    def test_invalid_utility_values_denominators_or_worlds_fail(self):
        for entry in (dict(mean=float('nan'), recordings=32), dict(mean=-1., recordings=32),
                      dict(mean=2., recordings=32), dict(mean=None, recordings=1), dict(mean=.3, recordings=33)):
            raw = private_report(utility=True)
            raw['utility'][r.NEW_IDS[0]]['IN']['macro_means']['retained_fraction'] = entry
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                r.build_report(raw)
        raw = private_report(utility=True)
        raw['utility'][r.NEW_IDS[0]]['PRIVATE_WORLD'] = {}
        with self.assertRaises(ValueError):
            r.build_report(raw)

    def test_missing_utility_policy_violations_and_incomplete_attacks_downgrade_status(self):
        for mutate in (lambda raw: raw['utility'][r.NEW_IDS[0]]['IN'].update(observed_recordings=31, macro_means={}),
                       lambda raw: raw['utility'][r.NEW_IDS[0]]['IN']['macro_means']['published_policy_violations'].update(mean=1.),
                       lambda raw: raw['analysis']['attacks'][r.NEW_IDS[0]]['semantic111'].update(complete_test_groups=31),
                       lambda raw: raw['analysis']['attacks'][r.NEW_IDS[0]]['semantic111']['fit_diagnostics'].update(converged=False),
                       lambda raw: raw['analysis']['negative_control_checks']['no_output'].update(status='fail')):
            raw = private_report()
            mutate(raw)
            raw['analysis']['utility'] = deepcopy(raw['utility'])
            self.assertEqual(r.build_report(raw)['mia_status'], 'incomplete_or_diagnostic')

    def test_final_utility_must_equal_analysis_utility(self):
        raw = private_report()
        raw['analysis']['utility'][r.NEW_IDS[0]]['IN']['macro_means']['retained_fraction']['mean'] = .1
        with self.assertRaisesRegex(ValueError, 'utility/analysis'):
            r.build_report(raw)

    def test_paired_auc_direction_seed_budget_and_point_consistency_are_validated(self):
        key, left, right, _ = r.CONTRASTS[0]
        for mutate in (lambda item: item.update(left=right, right=left),
                       lambda item: item['representations']['semantic111'].update(seed=1),
                       lambda item: item['representations']['semantic111'].update(replicates=10),
                       lambda item: item['representations']['semantic111'].update(interval=[.2, -.1]),
                       lambda item: item['representations']['semantic111'].update(auc_difference=.05)):
            raw = private_report()
            mutate(raw['exploratory_contrasts'][key])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                r.build_report(raw)
        raw = private_report()
        raw['exploratory_contrasts'].pop(key)
        self.assertEqual(r.build_report(raw)['mia_status'], 'incomplete_or_diagnostic')

    def test_paired_utility_CIs_keep_available_pairs_and_reject_reversed_bounds(self):
        raw = private_report(utility=True)
        key = r.CONTRASTS[0][0]
        entry = raw['paired_utility_contrasts'][key]['metrics']['retained_semantic_loss']
        entry.update(mean_difference=None, ci95=None, paired_recordings=0)
        public = r.build_report(raw)
        self.assertIsNone(public['paired_utility_contrasts'][key]['metrics']['retained_semantic_loss']['mean_difference'])
        entry.update(mean_difference=.1, ci95=[.2, -.1], paired_recordings=32)
        with self.assertRaisesRegex(ValueError, 'Reversed utility'):
            r.build_report(raw)

    def test_observed_selective_omission_respects_capability_and_input_cap(self):
        for identity, value in ((r.BASE_IDS[0], .01), (r.NEW_IDS[0], .11)):
            raw = private_report(utility=True)
            raw['utility'][identity]['IN']['macro_means']['selectively_suppressed_fraction_of_input']['mean'] = value
            with self.assertRaisesRegex(ValueError, 'capability/cap'):
                r.build_report(raw)

    def test_one_available_utility_pair_has_no_invented_interval(self):
        raw = private_report(utility=True)
        key = r.CONTRASTS[0][0]
        entry = raw['paired_utility_contrasts'][key]['metrics']['retained_semantic_loss']
        entry.update(mean_difference=.1, ci95=None, paired_recordings=1)
        public = r.build_report(raw)
        self.assertEqual(public['paired_utility_contrasts'][key]['metrics']['retained_semantic_loss']['paired_recordings'], 1)
        self.assertIsNone(public['paired_utility_contrasts'][key]['metrics']['retained_semantic_loss']['ci95'])

    def test_export_hash_receipt_no_overwrite_and_no_private_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report = directory / 'private.json'
            report.write_text(json.dumps(private_report(), allow_nan=False))
            output = directory / 'public'
            public = r.export(report, output, make_figures=False)
            self.assertEqual(json.loads((output / 'summary.json').read_text()), public)
            receipt = json.loads((output / 'artifact-receipt.json').read_text())
            for name, expected in receipt['files'].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), expected['sha256'])
            self.assertNotIn(SECRET, ''.join(path.read_text() for path in output.iterdir()))
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                r.export(report, output, make_figures=False)


if __name__ == '__main__':
    unittest.main()
