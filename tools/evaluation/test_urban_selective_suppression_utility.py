"""Filtered-query truthfulness and retained utility, including a native fixture."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import semantic_privacy
from run_local_policy_replay import audit as independent_audit
from semantic_suppression_audit import source_accounting
import test_semantic_suppression_audit as native_fixture
import test_urban_semantic_ablation_queries as query_fixture
import urban_semantic_ablation_queries as original_queries
import urban_selective_suppression_utility as filtered

ROOT = Path(__file__).resolve().parents[2]
BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT / 'simulator/build-semantic-ablation/AggregationReplay'))


def config():
    return dict(semantic_taxonomy=query_fixture.taxonomy(),
                policy_tree=dict(root=dict(semantic_suppression_fraction={'max': .5}), regions=[]),
                policy_regions=[])


def public(data, bins=None):
    bins = [('adult', len(data['batches']), 1)] if bins is None else bins
    cell = query_fixture.cell(bins=bins)
    cell.update(mean_sample_occupancy=cell['observation_contributions'] / len(data['batches']),
                effective_policy_id='test')
    release = query_fixture.release([cell], end=data['end_ms'])
    release.update(model='common_window', policy_id='test', policy_version='1')
    return semantic_privacy.export_releases(
        coverage=data['coverage'], sampling_period_ms=data['sampling_period_ms'],
        end_ms=data['end_ms'], releases=[release], taxonomy=query_fixture.taxonomy())


def checked(data, settings):
    retained = {(batch['observed_at_ms'], row['id']) for batch in data['batches']
                for row in batch['observations'] if row['type'] == 'Adult'}
    removed = {(batch['observed_at_ms'], row['id']) for batch in data['batches']
               for row in batch['observations'] if row['type'] == 'Child'}
    accounting = source_accounting(data, settings, retained, removed)
    delays = sorted(data['end_ms'] - time for time, _ in retained)
    def quantile(fraction):
        import math
        return delays[math.ceil(len(delays) * fraction) - 1] if delays else None
    accounting['observation_to_release_delay_ms'] = dict(
        mean=sum(delays) / len(delays) if delays else None,
        p50=quantile(.5), p95=quantile(.95), p99=quantile(.99),
        maximum=max(delays) if delays else None)
    return dict(status='verified', scalar=dict(valid=True), source_accounting=accounting,
                selectively_suppressed_observations=len(removed), contribution_selection='policy_filtered')


class FilteredQueryTests(unittest.TestCase):
    def test_retained_zero_is_only_an_original_source_proxy(self):
        data = query_fixture.source()
        value = filtered.evaluate_filtered_queries(data, public(data), config())
        exact, estimate = value['original_source_exact'], value['source_proxy_estimate']
        self.assertEqual(exact['status'], 'unavailable')
        self.assertEqual(exact['summary']['answered_query_count'], 0)
        self.assertEqual(exact['summary']['unknown_reasons']['filtered_population'], 12)
        self.assertFalse(exact['summary']['original_source_exact_available'])
        child = estimate['by_category']['child']
        self.assertEqual(child['answered_query_count'], 1)
        self.assertEqual(child['public_prediction_sum'], 0)
        self.assertEqual(child['answered_only_mae'], 3)
        self.assertEqual(child['answered_only_bias'], -3)
        self.assertEqual(estimate['summary']['signed_error_sum'], -6)
        self.assertEqual(estimate['summary']['answered_only_bias'], -2)
        self.assertIn('never certifies', value['zero_prediction_rule'])

    def test_ancestor_semantic_ambiguity_remains_unknown(self):
        data = query_fixture.source()
        value = filtered.evaluate_filtered_queries(
            data, public(data, [('road_user', 6, 2)]), config())
        estimate = value['source_proxy_estimate']
        self.assertEqual(estimate['by_category']['road_user']['answered_query_count'], 1)
        self.assertEqual(estimate['by_category']['child']['answered_query_count'], 0)
        self.assertIsNone(estimate['by_category']['child']['answered_only_bias'])
        self.assertEqual(estimate['by_category']['child']['unknown_reasons']['semantic_generalization'], 1)
        self.assertEqual(value['original_source_exact']['summary']['answered_query_count'], 0)

    def test_missing_support_does_not_become_original_or_retained_zero(self):
        data = query_fixture.source()
        recipient = public(data)
        recipient['releases'] = []
        value = filtered.evaluate_filtered_queries(data, recipient, config())
        estimate = value['source_proxy_estimate']['summary']
        self.assertEqual(estimate['answered_query_count'], 0)
        self.assertEqual(estimate['known_zero_reference_query_count'], 9)
        self.assertEqual(estimate['unknown_reasons']['missing_public_support'], 12)
        self.assertIsNone(estimate['answered_only_mae'])
        self.assertIsNone(estimate['answered_only_bias'])

    def test_private_truth_changes_errors_but_never_public_predictions(self):
        data = query_fixture.source()
        recipient = public(data)
        before = filtered.evaluate_filtered_queries(data, recipient, config())
        changed = deepcopy(data)
        for batch in changed['batches']:
            batch['observations'].append(dict(id='private-extra', type='Child', cell_id=12, x=3, y=1))
        after = filtered.evaluate_filtered_queries(changed, recipient, config())
        for category in ('adult', 'child', 'road_user'):
            a = before['source_proxy_estimate']['by_category'][category]
            b = after['source_proxy_estimate']['by_category'][category]
            self.assertEqual(a['public_prediction_sum'], b['public_prediction_sum'])
            self.assertEqual(a['answered_query_count'], b['answered_query_count'])
        self.assertNotEqual(before['source_proxy_estimate']['summary']['signed_error_sum'],
                            after['source_proxy_estimate']['summary']['signed_error_sum'])

    def test_estimation_matches_frozen_workload_without_changing_old_exact(self):
        data = query_fixture.source()
        recipient = public(data)
        bank = original_queries.prepare_reference(data, config())
        old = original_queries.evaluate(data, recipient, config(), reference=bank)
        value = filtered.evaluate_filtered_queries(data, recipient, config(), reference=bank)
        for key in original_queries.SUMMARY_FIELDS:
            self.assertEqual(value['source_proxy_estimate']['summary'][key], old['estimate']['summary'][key])
        self.assertGreater(old['exact']['summary']['answered_query_count'], 0)
        self.assertEqual(value['original_source_exact']['summary']['answered_query_count'], 0)
        self.assertEqual(original_queries.evaluate(data, recipient, config(), reference=bank), old)
        self.assertNotIn('queries', value['source_proxy_estimate'])

    def test_reference_is_bound_to_source_and_taxonomy(self):
        data = query_fixture.source()
        bank = original_queries.prepare_reference(data, config())
        with self.assertRaisesRegex(ValueError, 'source object'):
            filtered.evaluate_filtered_queries(deepcopy(data), public(data), config(), reference=bank)
        changed = config()
        changed['semantic_taxonomy']['version'] = 'different'
        with self.assertRaisesRegex(ValueError, 'taxonomy'):
            filtered.evaluate_filtered_queries(data, public(data), changed, reference=bank)


class FilteredUtilityTests(unittest.TestCase):
    def test_full_input_loss_retained_delay_and_legacy_query_contract(self):
        data, settings = query_fixture.source(1200), config()
        audit = checked(data, settings)
        value = filtered.utility(data, public(data), settings, audit)
        self.assertEqual(value['input_observations'], 22)
        self.assertEqual(value['retained_observations'], 11)
        self.assertEqual(value['retained_fraction'], .5)
        self.assertEqual(value['full_input_J'], .5)
        self.assertEqual(value['full_input_semantic_loss'], .5)
        self.assertEqual(value['retained_semantic_loss'], 0)
        self.assertEqual(value['selectively_suppressed_observations'], 11)
        self.assertEqual(value['whole_footprint_suppressed_observations'], 0)
        self.assertEqual(value['selectively_suppressed_fraction_of_input'], .5)
        self.assertEqual(value['logical_seal_delay_ms'], audit['source_accounting']['observation_to_release_delay_ms'])
        self.assertEqual(value['logical_seal_delay_ms']['maximum'], 1100)
        self.assertEqual(value['mean_retained_cell_side_m'], 20)
        self.assertEqual(value['mean_retained_interval_ms'], 1200)
        self.assertEqual(value['query_exact']['reference_queries'], 16)
        self.assertEqual(value['query_exact']['answered_queries'], 0)
        self.assertIsNone(value['query_exact']['occupancy_mae'])
        self.assertEqual(value['query_estimate']['answered_queries'], 4)
        self.assertLess(value['query_estimate']['occupancy_bias'], 0)
        self.assertEqual(value['aligned_semantic_queries']['exact']['summary']['answered_query_count'], 0)
        self.assertEqual(value['source_accounting']['by_source_type']['Child']['retained_fraction'], 0)
        self.assertEqual(value['source_accounting']['by_source_type']['Child']['selectively_suppressed_fraction'], 1)
        self.assertIsNone(value['core_processing_ms'])
        value['source_accounting']['retained_observations'] = 0
        self.assertEqual(audit['source_accounting']['retained_observations'], 11)

    def test_auxiliary_dependencies_skip_both_query_workloads(self):
        data, settings = query_fixture.source(), config()
        audit, recipient = checked(data, settings), public(data)
        with patch.object(filtered, 'evaluate_filtered_queries') as aligned_workload, \
                patch.object(filtered, '_occupancy_proxies') as occupancy_workload:
            value = filtered.utility(data, recipient, settings, audit, include_queries=False)
        aligned_workload.assert_not_called()
        occupancy_workload.assert_not_called()
        self.assertEqual(value['full_input_J'], .5)
        self.assertEqual(value['retained_observations'], 3)
        self.assertEqual(value['query_workload_status'], 'excluded_auxiliary_dependency')
        for key in ('query_exact', 'query_estimate', 'aligned_semantic_queries', 'aligned_query_definition'):
            self.assertNotIn(key, value)
        damaged = deepcopy(recipient)
        damaged['releases'][0]['cells'][0]['semantic']['semantic_mean_loss'] = .9
        with self.assertRaises(ValueError):
            filtered.utility(data, damaged, settings, audit, include_queries=False)

    def test_include_queries_requires_a_boolean(self):
        data, settings = query_fixture.source(), config()
        for value in (0, 1, None, 'no'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'boolean'):
                filtered.utility(data, public(data), settings, checked(data, settings), include_queries=value)

    def test_tampered_totals_cohorts_delay_and_public_counts_rejected(self):
        data, settings = query_fixture.source(1200), config()
        original = checked(data, settings)
        def kept(a): a['source_accounting']['retained_observations'] += 1
        def whole(a): a['source_accounting']['whole_footprint_suppressed_observations'] += 1
        def fraction(a): a['source_accounting']['retained_fraction'] = .9
        def cohort(a): a['source_accounting']['by_source_type']['Adult']['input_observations'] += 1
        def delay(a): a['source_accounting']['observation_to_release_delay_ms']['maximum'] = -1
        def status(a): a['status'] = 'failed'
        def scalar(a): a['scalar']['valid'] = False
        def selective(a): a['selectively_suppressed_observations'] += 1
        for mutate in (kept, whole, fraction, cohort, delay, status, scalar, selective):
            with self.subTest(mutate=mutate.__name__), self.assertRaises(ValueError):
                damaged = deepcopy(original)
                mutate(damaged)
                filtered.utility(data, public(data), settings, damaged)
        recipient = public(data, [('adult', 12, 1)])
        with self.assertRaisesRegex(ValueError, 'total accounting'):
            filtered.utility(data, recipient, settings, original)

    def test_nonexclusive_original_position_regions_preserved(self):
        data, settings = query_fixture.source(), config()
        settings['policy_tree']['regions'] = ['one', 'two']
        settings['policy_regions'] = [dict(id=identity, x=0, y=0, width=20, height=20)
                                      for identity in ('one', 'two')]
        value = filtered.utility(data, public(data), settings, checked(data, settings))
        regions = value['source_accounting']['by_region']
        self.assertEqual(sum(r['input_observations'] for r in regions.values()), 12)
        self.assertEqual(value['input_observations'], 6)
        self.assertTrue(all(r['selectively_suppressed_fraction'] == .5 for r in regions.values()))

    def test_native_full_input_retirement_and_positive_cap_required(self):
        data, settings = query_fixture.source(), config()
        audit = checked(data, settings)
        result = dict(input_observation_contributions=6, accounted_observation_contributions=5)
        with self.assertRaisesRegex(ValueError, 'retirement'):
            filtered.utility(data, public(data), settings, audit, result)
        settings['policy_tree']['root']['semantic_suppression_fraction']['max'] = 0
        with self.assertRaisesRegex(ValueError, 'positive suppression'):
            filtered.utility(data, public(data), settings, audit)

    def test_whole_footprint_omission_charged_against_full_input(self):
        data, settings = query_fixture.source(), config()
        recipient = public(data)
        recipient['releases'] = []
        audit = dict(status='verified', source_accounting=source_accounting(data, settings, set(), set()))
        audit['source_accounting']['observation_to_release_delay_ms'] = dict.fromkeys(filtered._DELAY_FIELDS)
        value = filtered.utility(data, recipient, settings, audit)
        self.assertEqual(value['full_input_J'], 1)
        self.assertEqual(value['whole_footprint_suppressed_observations'], 6)
        self.assertEqual(value['selectively_suppressed_observations'], 0)
        self.assertIsNone(value['retained_semantic_loss'])
        self.assertIsNone(value['logical_seal_delay_ms']['maximum'])


@unittest.skipUnless(BINARY.is_file(), 'Build AggregationReplay for native filtered fixture')
class NativeFilteredUtilityTests(unittest.TestCase):
    def test_actual_filtered_native_release_uses_retained_delay_and_full_input(self):
        data, settings = native_fixture.source(), native_fixture.settings()
        with tempfile.TemporaryDirectory(prefix='ump-filtered-utility-fixture-') as temporary:
            directory = Path(temporary)
            source_path, config_path, result_path = [directory / name for name in
                                                     ('input.json', 'config.json', 'result.json')]
            source_path.write_text(json.dumps(data))
            config_path.write_text(json.dumps(settings))
            done = subprocess.run([str(BINARY), '--input', str(source_path), '--config', str(config_path),
                                   '--mode', 'semantic_first', '--output', str(result_path)],
                                  capture_output=True, text=True, timeout=20)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            result = json.loads(result_path.read_text())
        audited = independent_audit(data, settings, result)
        recipient = semantic_privacy.export_public(result, settings['semantic_taxonomy'])
        value = filtered.utility(data, recipient, settings, audited, result)
        self.assertEqual(value['input_observations'], 140)
        self.assertEqual(value['retained_observations'], 133)
        self.assertEqual(value['selectively_suppressed_observations'], 7)
        self.assertEqual(value['whole_footprint_suppressed_observations'], 0)
        self.assertAlmostEqual(value['full_input_J'], .05)
        self.assertEqual(value['logical_seal_delay_ms'], audited['source_accounting']['observation_to_release_delay_ms'])
        self.assertEqual(value['source_accounting']['by_source_type']['adult_cyclist']['retained_fraction'], 0)
        self.assertEqual(value['aligned_semantic_queries']['exact']['summary']['answered_query_count'], 0)
        self.assertEqual(value['selective_suppression_root_cap'], .1)


if __name__ == '__main__':
    unittest.main()
