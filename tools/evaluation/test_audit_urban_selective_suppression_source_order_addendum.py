"""Synthetic ordering regressions; no real model audit, fitting or TEST payloads."""
from copy import deepcopy
import math
import unittest
from unittest.mock import patch

import audit_urban_selective_suppression_source_order_addendum as addon
import audit_urban_selective_suppression as frozen
import test_audit_urban_selective_suppression as old_fixture

COUNTS = dict(train=2, calibration=2, test=2)
PARAMETERS = dict(l2=.1, max_iterations=500, tolerance=1e-8)


def fixture():
    groups = [dict(group_id=role + '-' + suffix, split=role, opaque={'preserve': suffix})
              for suffix in ('b', 'a') for role in frozen.SPLITS]
    rows = []
    for group in groups:
        if group['split'] == 'test':
            continue
        for original in old_fixture.rows():
            if original['split'] == group['split']:
                row = deepcopy(original)
                row['group_id'] = group['group_id']
                rows.append(row)
    rows = sorted(rows, key=lambda row: (frozen.SPLITS.index(row['split']), row['group_id'], row['method_id'], -row['label']))
    models, _, _ = old_fixture.model_fixture()
    for method in ('old', 'new'):
        for representation in frozen.REPRESENTATIONS:
            item = models['attacks'][method][representation]
            item['model']['training_rows'] = 4
            item['calibration']['negative_case_fpr_resolution'] = .5
            item['calibration']['calibration'] = frozen.metrics([.5] * 4, [1, 0, 1, 0], math.nextafter(.5, math.inf))
    models.update(expected_groups={role: sorted(group['group_id'] for group in groups if group['split'] == role)
                                   for role in frozen.SPLITS},
                  training_group_ids=['train-a', 'train-b'], calibration_group_ids=['calibration-a', 'calibration-b'],
                  training_calibration_rows=len(rows), training_calibration_rows_sha256=frozen.digest(rows))
    old_fixture.reseal(models)
    original = dict(attacks={'old': deepcopy(models['attacks']['old'])}, controls=deepcopy(models['controls']))
    return groups, rows, models, original


class SourceOrderAddendumTests(unittest.TestCase):
    def check(self, groups, rows, models, original):
        return addon.check_model_bundle_addendum(models, rows, original, groups, ['old', 'new'], ['old'],
                                                PARAMETERS, expected_counts=COUNTS)

    def test_regression_frozen_v1_rejects_valid_manifest_permutation(self):
        groups, rows, models, original = fixture()
        with self.assertRaisesRegex(ValueError, 'Model source assignments differ'):
            frozen.check_model_bundle(models, rows, original, groups, ['old', 'new'], ['old'], PARAMETERS)
        result = self.check(groups, rows, models, original)
        self.assertEqual(result['test_rows_read'], 0)
        self.assertEqual(result['training_calibration_rows'], 16)

    def test_different_execution_orders_have_same_validation_and_preserve_inputs(self):
        groups, rows, models, original = fixture()
        before = frozen.digest([groups, rows, models, original])
        first = self.check(groups, rows, models, original)
        self.assertEqual(self.check(list(reversed(groups)), rows, models, original), first)
        self.assertEqual(before, frozen.digest([groups, rows, models, original]))
        canonical = addon.canonical_groups(groups, expected_counts=COUNTS)
        self.assertIsNot(canonical[0]['opaque'], groups[3]['opaque'])

    def test_role_membership_swap_is_rejected_even_with_same_counts(self):
        groups, rows, models, original = fixture()
        changed = deepcopy(groups)
        changed[0]['group_id'], changed[1]['group_id'] = changed[1]['group_id'], changed[0]['group_id']
        with self.assertRaisesRegex(ValueError, 'membership differs'):
            self.check(changed, rows, models, original)

    def test_duplicate_cross_role_and_wrong_counts_rejected_before_frozen_check(self):
        groups, rows, models, original = fixture()
        duplicate = deepcopy(groups); duplicate[0]['group_id'] = duplicate[1]['group_id']
        for invalid in (duplicate, groups[:-1], groups + [dict(group_id='extra', split='other')]):
            with patch.object(frozen, 'check_model_bundle') as checker, self.assertRaises(ValueError):
                self.check(invalid, rows, models, original)
            checker.assert_not_called()

    def test_model_metadata_duplicates_or_reassignments_are_not_normalized_away(self):
        groups, rows, models, original = fixture()
        for replacement in (['train-a', 'train-a'], ['train-a', 'calibration-a']):
            changed = deepcopy(models)
            changed['expected_groups']['train'] = replacement
            old_fixture.reseal(changed)
            with self.assertRaisesRegex(ValueError, 'membership differs'):
                self.check(groups, rows, changed, original)

    def test_numerical_and_calibration_checks_are_still_enforced(self):
        groups, rows, models, original = fixture()
        changed = deepcopy(models)
        changed['attacks']['new']['semantic111']['model']['means'][0] = .6
        old_fixture.reseal(changed)
        with self.assertRaisesRegex(ValueError, 'TRAIN means'):
            self.check(groups, rows, changed, original)
        changed = deepcopy(models)
        changed['attacks']['new']['semantic111']['calibration']['threshold'] = .5
        old_fixture.reseal(changed)
        with self.assertRaisesRegex(ValueError, 'boundary ULPs'):
            self.check(groups, rows, changed, original)

    def test_test_feature_row_is_still_rejected_by_original_guard(self):
        groups, rows, models, original = fixture()
        extra = deepcopy(rows[0]); extra.update(group_id='test-a', split='test')
        with self.assertRaisesRegex(ValueError, 'TEST boundary'):
            self.check(groups, rows + [extra], models, original)

    def test_real_cli_role_counts_are_strict_and_metadata_can_be_copied(self):
        groups = [dict(group_id=role + '-' + str(index), split=role)
                  for role, count in addon.EXPECTED_COUNTS.items() for index in reversed(range(count))]
        canonical = addon.canonical_groups(groups)
        self.assertEqual(len(canonical), 72)
        for role in frozen.SPLITS:
            values = [group['group_id'] for group in canonical if group['split'] == role]
            self.assertEqual(values, sorted(values))
        with self.assertRaisesRegex(ValueError, 'counts differ'):
            addon.canonical_groups(groups[:-1])

    def test_models_phase_never_imports_runner_or_final_phase(self):
        groups, rows, models, original = fixture()
        inputs = (dict(group_order=groups, model_parameters=PARAMETERS), {}, rows, models, original, ['old', 'new'], ['old'])
        with patch.object(frozen, '_model_inputs', return_value=inputs), \
                patch.object(addon, 'check_model_bundle_addendum', return_value={'test_rows_read': 0}) as checker, \
                patch.object(addon, 'order_metadata', return_value={}), \
                patch.object(frozen, 'sha', return_value='f' * 64), \
                patch.object(addon, 'audit_final', side_effect=AssertionError('Final phase forbidden')):
            from pathlib import Path
            result, _ = addon.audit_models(Path('/synthetic-not-opened'))
        self.assertEqual(result['test_rows_read'], 0)
        checker.assert_called_once()


if __name__ == '__main__':
    unittest.main()
