"""Synthetic independent-auditor boundaries; no study data or fitting runs."""
from copy import deepcopy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_urban_selective_suppression as auditor
import test_urban_selective_suppression_utility as fixture
import urban_selective_suppression_utility as producer


def groups():
    return [dict(group_id='train-0', split='train'),
            dict(group_id='cal-0', split='calibration'), dict(group_id='test-0', split='test')]


def rows(methods=('old', 'new'), include_test=True):
    output = []
    for group in groups():
        if group['split'] == 'test' and not include_test:
            continue
        for method in methods:
            for world, label in (('IN', 1), ('OUT', 0)):
                output.append(dict(**group, method_id=method, world=world, label=label,
                    features=[float(label)] + [0.] * 110,
                    scalar_features=[float(label)] + [0.] * 30,
                    auxiliary_features=[0.] * 8,
                    controls=dict(prior_only=.5, unprotected=label, no_output_features=[0.] * 111),
                    utility=dict(retained_fraction=.25 if world == 'IN' else .5, optional=None)))
    return sorted(output, key=lambda row: (auditor.SPLITS.index(row['split']), row['group_id'], row['method_id'], -row['label']))


def fitted(dimension):
    # Hand-calculated balanced-prior, zero-weight arithmetic fixture.
    # The auditor verifies stored arithmetic and never invokes optimization.
    base = dict(schema='ump.logistic-classifier.v1', feature_count=dimension,
        training_rows=2, training_prior=.5, means=[.5] + [0.] * (dimension - 1),
        scales=[.5] + [1.] * (dimension - 1), weights=[0.] * dimension,
        intercept=0., l2=.1, iterations=1, converged=True,
        training_objective=math.log(2))
    threshold = math.nextafter(.5, math.inf)
    calibration = auditor.metrics([.5, .5], [1, 0], threshold)
    return dict(status='locked', missing=[], model=base, calibration=dict(
        schema='ump.attack-calibration.v1', threshold=threshold, target_fpr=.1,
        negative_case_fpr_resolution=1., selection='fixture', calibration=calibration))


def model_fixture():
    training = rows(include_test=False)
    attack = dict(semantic111=fitted(111), scalar31=fitted(31))
    original = dict(attacks={'old': deepcopy(attack)}, controls={'prior_only': {'fixture': True}})
    model = dict(model_parameters=dict(l2=.1, max_iterations=500, tolerance=1e-8),
        test_rows_seen=0, attacks={'old': deepcopy(attack), 'new': deepcopy(attack)},
        controls=deepcopy(original['controls']), method_ids=['old', 'new'], expected_method_ids=['old', 'new'],
        expected_groups={split: [group['group_id'] for group in groups() if group['split'] == split]
                         for split in auditor.SPLITS},
        training_group_ids=['train-0'], calibration_group_ids=['cal-0'],
        training_calibration_rows=len(training), training_calibration_rows_sha256=auditor.digest(training))
    model['models'] = [dict(method_id=method, representation=rep, **deepcopy(model['attacks'][method][rep]))
                       for method in ('old', 'new') for rep in auditor.REPRESENTATIONS]
    model['prepared_sha256'] = auditor.digest(model)
    return model, training, original


def reseal(model):
    model['models'] = [dict(method_id=method, representation=rep, **deepcopy(model['attacks'][method][rep]))
                      for method in model['method_ids'] for rep in auditor.REPRESENTATIONS]
    model.pop('prepared_sha256', None)
    model['prepared_sha256'] = auditor.digest(model)


class UtilityArithmeticAuditTests(unittest.TestCase):
    def setUp(self):
        self.data, self.config = fixture.query_fixture.source(1200), fixture.config()
        self.public, self.audit = fixture.public(self.data), fixture.checked(self.data, self.config)
        self.row = dict(utility=producer.utility(self.data, self.public, self.config, self.audit))

    def test_independent_public_arithmetic_accepts_retained_product(self):
        with patch.object(producer, 'utility', side_effect=AssertionError('Producer reuse forbidden')):
            count = auditor.check_filtered_row(self.row, self.public, self.audit, self.data, self.config)
        self.assertGreater(count, 15)

    def test_wrong_full_input_loss_or_cohort_or_exact_claim_rejected(self):
        def loss(row): row['utility']['full_input_J'] = 0
        def kept(row): row['utility']['retained_observations'] += 1
        def exact(row): row['utility']['query_exact']['answered_queries'] = 1
        def category(row): row['utility']['aligned_semantic_queries']['exact']['summary']['original_source_exact_available'] = True
        def bias(row): row['utility']['aligned_semantic_queries']['estimate']['summary']['answered_only_bias'] = 999
        for mutation in (loss, kept, exact, category, bias):
            row = deepcopy(self.row)
            mutation(row)
            with self.subTest(mutation=mutation.__name__), self.assertRaises(ValueError):
                auditor.check_filtered_row(row, self.public, self.audit, self.data, self.config)

    def test_auxiliary_query_exclusion_is_audited(self):
        self.row['utility'] = producer.utility(self.data, self.public, self.config, self.audit, include_queries=False)
        auditor.check_filtered_row(self.row, self.public, self.audit, self.data, self.config, include_queries=False)
        self.row['utility']['query_exact'] = {}
        with self.assertRaisesRegex(ValueError, 'Auxiliary'):
            auditor.check_filtered_row(self.row, self.public, self.audit, self.data, self.config, include_queries=False)

    def test_macro_means_use_recordings_and_keep_missing_n(self):
        values = rows()
        values += [dict(row, group_id='test-1', utility={'retained_fraction': .75, 'optional': 8})
                   for row in rows() if row['split'] == 'test']
        metadata = groups() + [dict(group_id='test-1', split='test')]
        report = auditor.macro_utility(values, ['old', 'new'], metadata)
        self.assertEqual(report['new']['IN']['macro_means']['retained_fraction'], {'mean': .5, 'recordings': 2})
        self.assertEqual(report['new']['IN']['macro_means']['optional'], {'mean': 8., 'recordings': 1})


class MatrixAuditTests(unittest.TestCase):
    def test_complete_world_matrix_and_different_positive_control_are_valid(self):
        self.assertEqual(auditor.checked_rows(rows(), groups(), ['old', 'new']), rows())

    def test_duplicate_missing_wrongrole_and_method_dependent_controls_fail(self):
        cases = []
        values = rows(); values.append(deepcopy(values[0])); cases.append(values)
        cases.append(rows()[:-1])
        values = rows(); values[0]['split'] = 'test'; cases.append(values)
        values = rows(); values[0]['controls']['unprotected'] = .25; cases.append(values)
        for values in cases:
            with self.assertRaises(ValueError):
                auditor.checked_rows(values, groups(), ['old', 'new'])

    def test_model_boundary_rejects_even_one_test_row(self):
        with self.assertRaisesRegex(ValueError, 'TEST boundary'):
            auditor.checked_rows(rows(), groups(), ['old', 'new'], allow_test=False)


class ModelAuditTests(unittest.TestCase):
    def audit(self, model, training, original):
        return auditor.check_model_bundle(model, training, original, groups(), ['old', 'new'], ['old'],
                                          dict(l2=.1, max_iterations=500, tolerance=1e-8))

    def test_hand_model_train_scaling_objective_and_calibration_without_fitting(self):
        model, training, original = model_fixture()
        result = self.audit(model, training, original)
        self.assertEqual(result['test_rows_read'], 0)
        self.assertEqual(result['new_models'], 2)

    def test_wrong_train_scale_objective_or_historical_control_rejected(self):
        def means(model): model['attacks']['new']['semantic111']['model']['means'][0] = .6
        def objective(model): model['attacks']['new']['semantic111']['model']['training_objective'] = .2
        def prior(model): model['attacks']['new']['scalar31']['model']['training_prior'] = .9
        def controls(model): model['controls']['prior_only']['fixture'] = False
        for mutation in (means, objective, prior, controls):
            model, training, original = model_fixture()
            mutation(model); reseal(model)
            with self.subTest(mutation=mutation.__name__), self.assertRaises(ValueError):
                self.audit(model, training, original)

    def test_threshold_adjacent_float_boundary_is_not_accepted_by_tolerance(self):
        model, training, original = model_fixture()
        model['attacks']['new']['semantic111']['calibration']['threshold'] = .5
        reseal(model)
        with self.assertRaisesRegex(ValueError, 'boundary ULPs'):
            self.audit(model, training, original)

    def test_tied_auc_and_fixed_threshold_metrics(self):
        measured = auditor.metrics([.5, .5], [1, 0], math.nextafter(.5, math.inf))
        self.assertEqual(measured['roc_auc'], .5)
        self.assertEqual(measured['true_positive'], 0)
        self.assertEqual(measured['false_positive'], 0)

    def test_independent_final_scores_and_wrong_score_rejection(self):
        model, _, _ = model_fixture()
        values = rows()
        assessed = {'attacks': {name: {} for name in ('old', 'new')}}
        for name in ('old', 'new'):
            selected = [row for row in values if row['method_id'] == name and row['split'] == 'test']
            for rep, (field, _) in auditor.REPRESENTATIONS.items():
                locked = model['attacks'][name][rep]
                scores = [auditor.score(locked['model'], row[field]) for row in selected]
                assessed['attacks'][name][rep] = dict(status='evaluated', observed_test_rows=2, missing_test_rows=[],
                    locked_calibration=deepcopy(locked['calibration']),
                    group_scores=[dict(group_id=row['group_id'], label=row['label'], score=value)
                                  for row, value in zip(selected, scores)],
                    metrics=auditor.metrics(scores, [row['label'] for row in selected], locked['calibration']['threshold']))
        self.assertEqual(auditor.check_assessment(assessed, model, values, ['old', 'new'], groups()), 8)
        assessed['attacks']['new']['semantic111']['group_scores'][0]['score'] = .75
        with self.assertRaisesRegex(ValueError, 'TEST score'):
            auditor.check_assessment(assessed, model, values, ['old', 'new'], groups())


class ArchiveAuditTests(unittest.TestCase):
    def test_archive_hash_round_trip_and_escape_rejection(self):
        import gzip
        import json
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = json.dumps({'retained': 3}).encode()
            path = root / 'payload.json.gz'
            path.write_bytes(gzip.compress(content))
            ref = dict(path=path.name, sha256=auditor.sha(path), uncompressed_sha256=__import__('hashlib').sha256(content).hexdigest(),
                       uncompressed_bytes=len(content))
            self.assertEqual(auditor.archive(root, ref), {'retained': 3})
            ref['uncompressed_bytes'] -= 1
            with self.assertRaises(ValueError): auditor.archive(root, ref)
            ref['path'] = '../outside'
            with self.assertRaises(ValueError): auditor.relative(root, ref)

    def test_cli_refuses_existing_receipt_before_any_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'existing.json'
            output.write_text('preserve')
            with patch.object(auditor, 'audit_utility') as execute, self.assertRaisesRegex(ValueError, 'overwrite'):
                auditor.main(['--study', directory, '--phase', 'utility', '--output', str(output)])
            execute.assert_not_called()
            self.assertEqual(output.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
