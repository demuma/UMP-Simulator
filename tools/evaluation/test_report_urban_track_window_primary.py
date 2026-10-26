"""Synthetic contracts for aggregate-only fixed-window presentation.

No recordings, fitted model files, primary TRAIN/CAL/TEST artifacts or source
references are opened. Counts, scores and apparent identities here are fixtures.
"""
from copy import deepcopy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import report_urban_track_window_primary as reporting
import urban_privacy_statistics as statistics

SECRET = 'PRIVATE_SOURCE_TARGET_ID_seed1234567890123456789_and_path'


def metrics(scores=None, labels=None, threshold=.5):
    scores = ([.9] * 24 + [.1] * 8 + [.9] * 4 + [.1] * 28) if scores is None else scores
    labels = ([1] * 32 + [0] * 32) if labels is None else labels
    return statistics.attack_metrics_with_intervals(scores, labels, threshold)


def attack(representation='semantic111', *, control=None):
    test_metrics = metrics()
    if control in ('prior_only', 'auxiliary_only', 'no_output'):
        test_metrics = metrics([.5] * 64, [1] * 32 + [0] * 32, .5000000000000001)
    elif control == 'unprotected':
        test_metrics = metrics([1.] * 32 + [0.] * 32)
    calibration = metrics([.9] * 8 + [.1] * 8 + [.1] * 16, [1] * 16 + [0] * 16,
                          test_metrics['threshold'])
    return {'status': 'evaluated', 'metrics': test_metrics,
            'expected_independent_test_groups': 32, 'complete_test_groups': 32, 'observed_test_rows': 64,
            'fit_diagnostics': {'converged': True, 'iterations': 35, 'training_rows': 48,
                                'feature_count': 111 if representation == 'semantic111' else 31,
                                'training_objective': .25, 'private_model': SECRET},
            'locked_calibration': {'target_fpr': .1, 'threshold': test_metrics['threshold'],
                                   'negative_case_fpr_resolution': 1/16, 'calibration': calibration,
                                   'private_rows': SECRET},
            'group_scores': [{'group_id': SECRET, 'target_id': SECRET, 'score': .9}],
            'model_weights': SECRET}


def private_report(*, evaluated=True):
    groups = []
    for split, n in reporting.GROUP_COUNTS.items():
        for ordinal in range(n):
            groups.append({'group_id': f'{SECRET}-{split}-{ordinal}', 'split': split, 'status': 'verified',
                           'path': SECRET, 'target_id': SECRET, 'seed': SECRET,
                           'cases': [{'method_id': method, 'world': world, 'status': 'verified',
                                      'command': [SECRET], 'error': SECRET, 'rows': SECRET}
                                     for method, _ in reporting.METHODS for world in ('IN', 'OUT')]})
    quality = {'source_validation_profile': reporting.PROFILE, 'quality_filters_enrollment': False,
               'private_positions': SECRET, 'by_split': {}}
    for split, n in reporting.GROUP_COUNTS.items():
        quality['by_split'][split] = dict(planned_sources=n, verified_sources=n, quality_reports=n,
            sources_with_active_at_horizon=2 if split == 'test' else 1,
            sources_with_pending_at_horizon=0, sources_with_reported_stalls=1,
            raw_source_rows=SECRET)
    assessment = None
    if evaluated:
        attacks, utilities = {}, {}
        for method, _ in reporting.METHODS:
            attacks[method] = {representation: attack(representation) for representation in reporting.REPRESENTATIONS}
            utilities[method] = {}
            for world, retained in (('IN', .8), ('OUT', .7)):
                utilities[method][world] = {'expected_recordings': 32, 'observed_recordings': 32,
                    'macro_means': {key: {'mean': value, 'recordings': 32, 'private_rows': SECRET}
                                   for key, value in {'retained_fraction': retained, 'full_input_J': .4,
                                       'retained_semantic_loss': .25, 'mean_retained_cell_side_m': 8.,
                                       'logical_seal_delay_ms.mean': 500., 'query_exact.answered_query_coverage': .2,
                                       'query_estimate.occupancy_mae': .1, 'query_estimate.answered_query_coverage': .9,
                                       SECRET: 123}.items()}, 'source_rows': SECRET}
        reps = {name: {'auc_difference': -.05, 'interval': [-.1, .01], 'confidence_level': .95,
                       'seed': 20261025301, 'independent_groups': 32, 'replicates': 1000,
                       'private_bootstrap_rows': SECRET} for name in reporting.REPRESENTATIONS}
        assessment = {'schema': 'ump.urban-privacy-analysis.v1', 'status': 'complete',
            'interpretation_gate': 'controls_pass', 'attacks': attacks, 'utility': utilities,
            'controls': {name: attack(control=name) for name in reporting.strict.CONTROLS},
            'negative_control_checks': {name: {'status': 'pass', 'private_rows': SECRET}
                                        for name in ('prior_only', 'auxiliary_only', 'no_output')},
            'positive_control_check': {'status': 'pass', 'in_contains_all_approved_sightings': True,
                                       'OUT_removal_monotone': True, 'auc_above_chance': True, 'source': SECRET},
            'primary_contrast': {'left': 'adaptive_semantic_first', 'right': 'regional_static20',
                                 'representations': reps, 'private_rows': SECRET}}
    return {'schema': reporting.INPUT_SCHEMA, 'evaluation_id': SECRET,
            'source_validation_profile': reporting.PROFILE,
            'dataset_manifest_sha256': 'a' * 64, 'evaluation_manifest_sha256': 'b' * 64,
            'source_profile_sha256': 'c' * 64, 'implementation_sha256': 'd' * 64,
            'import_ledger': {'path': '/private/' + SECRET, 'sha256': 'e' * 64, 'rows': SECRET},
            'source_protocol': {'path': '/private/' + SECRET, 'sha256': 'f' * 64, 'seeds': SECRET},
            'source_split_audit': {'status': 'verified', 'group_ids': [SECRET], 'private_path': SECRET},
            'group_outcomes': groups if evaluated else [], 'analysis': assessment, 'source_quality': quality,
            'raw_motion': SECRET, 'weights': SECRET}


class TrackWindowPublicReportTests(unittest.TestCase):
    def test_explicit_profile_and_window_scope_without_legacy_protected_unit(self):
        public = reporting.compact_report(private_report())
        text = reporting.markdown(public)
        self.assertEqual(public['schema'], reporting.SCHEMA)
        self.assertEqual(public['source_validation_profile'], 'observed_track_window_v1')
        self.assertEqual(public['horizon_ms'], 300000)
        self.assertIn('all_observed_contributions', public['protected_unit'])
        self.assertIn('active/censored', text)
        self.assertIn('does not filter enrollment', text)
        for inherited in ('one complete visible episode contribution', 'bounded episode-contribution attack',
                          'episode-contribution attack', '# P25.4'):
            self.assertNotIn(inherited, text)
            self.assertNotIn(inherited, json.dumps(public))
        self.assertIn('A pathology is not a privacy benefit', text)

    def test_explicit_allowlist_discards_all_private_references_rows_and_identifiers(self):
        private = private_report()
        before = deepcopy(private)
        public = reporting.compact_report(private, input_sha256='0' * 64)
        self.assertEqual(private, before)
        encoded = json.dumps(public, allow_nan=False)
        self.assertNotIn(SECRET, encoded)
        self.assertNotIn('/private/', encoded)
        for key in ('group_id', 'target_id', 'seed', 'path', 'rows', 'weights', 'group_scores',
                    'model_weights', 'raw_motion', 'private_positions', 'command', 'error'):
            self.assertNotIn('"' + key + '"', encoded)
        provenance = public['provenance']
        self.assertEqual(provenance['import_ledger_sha256'], 'e' * 64)
        self.assertEqual(provenance['source_protocol_sha256'], 'f' * 64)
        self.assertEqual(provenance['private_evaluation_id_sha256'], hashlib.sha256(SECRET.encode()).hexdigest())
        self.assertEqual(public['source_split_audit_status'], 'verified')
        self.assertNotIn('source_split_audit', public)

    def test_all_methods_worlds_representations_and_denominators_are_retained(self):
        public = reporting.compact_report(private_report())
        self.assertEqual(len(public['methods']), 11)
        outcomes = public['source_and_execution']
        self.assertEqual(outcomes['planned_recordings'], 72)
        self.assertEqual(outcomes['recording_status_by_split']['test']['verified'], 32)
        for method in public['methods']:
            self.assertEqual(outcomes['method_world_status'][method['id']]['observed'], 144)
            for representation in reporting.REPRESENTATIONS:
                attack_result = method['attacks'][representation]
                self.assertEqual(attack_result['expected_independent_test_groups'], 32)
                self.assertEqual(attack_result['metrics']['positive_cases'], 32)
            self.assertEqual(method['utility']['IN']['macro_means']['retained_fraction']['mean'], .8)
            self.assertEqual(method['utility']['OUT']['macro_means']['retained_fraction']['mean'], .7)
        self.assertEqual(public['primary_contrast']['representations']['semantic111']['independent_groups'], 32)

    def test_quality_is_source_level_diagnostic_not_attack_or_enrollment_filter(self):
        private = private_report()
        public = reporting.compact_report(private)
        self.assertEqual(public['analysis_status'], 'complete')
        self.assertFalse(public['source_quality']['quality_filters_enrollment'])
        self.assertEqual(public['source_quality']['by_split']['test']['sources_with_active_at_horizon'], 2)
        self.assertEqual(public['source_quality']['by_split']['test']['sources_with_reported_stalls'], 1)
        self.assertEqual(public['source_and_execution']['recording_status_by_split']['test']['verified'], 32)
        for field in reporting.QUALITY_FIELDS:
            private['source_quality']['by_split']['test'][field] = None
        second = reporting.compact_report(private)
        self.assertEqual(second['methods'], public['methods'])
        self.assertEqual(second['analysis_status'], 'complete')
        self.assertEqual(second['source_quality']['availability'], 'partial')

    def test_missing_quality_counts_are_na_and_known_zero_remains_zero(self):
        private = private_report(evaluated=False)
        private['source_quality']['by_split'] = {'train': {'planned_sources': 24,
            'quality_reports': 10, 'sources_with_pending_at_horizon': 0}}
        public = reporting.compact_report(private)
        self.assertIsNone(public['source_quality']['by_split']['test']['sources_with_active_at_horizon'])
        self.assertEqual(public['source_quality']['by_split']['train']['sources_with_pending_at_horizon'], 0)
        self.assertIn('| test | NA | NA | NA | NA | NA | NA |', reporting.markdown(public))
        self.assertIn('| train | 24 | NA | 10 | NA | 0 | NA |', reporting.markdown(public))
        self.assertIn('No held-out privacy result', reporting.markdown(public))
        self.assertEqual(public['source_and_execution']['recording_status_by_split']['test']['not_reported'], 32)

    def test_empty_quality_counts_do_not_become_success_or_zero(self):
        private = private_report(evaluated=False)
        private['source_quality']['by_split'] = {}
        public = reporting.compact_report(private)
        self.assertEqual(public['source_quality']['availability'], 'unavailable')
        self.assertTrue(all(value is None for item in public['source_quality']['by_split'].values()
                            for value in item.values()))

    def test_wrong_schema_profile_quality_filter_and_missing_identity_rejected(self):
        mutations = [lambda p: p.update(schema='ump.urban-primary-report.v1'),
                     lambda p: p.update(source_validation_profile='complete_visible_episode'),
                     lambda p: p['source_quality'].update(source_validation_profile='complete_visible_episode'),
                     lambda p: p['source_quality'].update(quality_filters_enrollment=True),
                     lambda p: p['source_quality'].pop('quality_filters_enrollment'),
                     lambda p: p.pop('evaluation_id')]
        for mutate in mutations:
            private = private_report(evaluated=False)
            mutate(private)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                reporting.compact_report(private)

    def test_malformed_quality_counts_or_frozen_plan_are_rejected(self):
        mutations = [lambda p: p['source_quality']['by_split']['train'].update(quality_reports=True),
                     lambda p: p['source_quality']['by_split']['train'].update(verified_sources=-1),
                     lambda p: p['source_quality']['by_split']['train'].update(planned_sources=25),
                     lambda p: p['source_quality']['by_split']['test'].update(sources_with_reported_stalls=33),
                     lambda p: p['source_quality']['by_split']['test'].update(quality_reports=1, sources_with_active_at_horizon=2),
                     lambda p: p['source_quality']['by_split'].update({SECRET: {}})]
        for mutate in mutations:
            private = private_report(evaluated=False)
            mutate(private)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                reporting.compact_report(private)

    def test_invalid_hashes_references_numeric_metrics_and_changed_contrast_rejected(self):
        mutations = [lambda p: p.update(dataset_manifest_sha256=SECRET),
                     lambda p: p['source_protocol'].update(sha256=SECRET),
                     lambda p: p.update(import_ledger=SECRET),
                     lambda p: p['analysis']['attacks']['adaptive_semantic_first']['semantic111']['metrics'].update(roc_auc=float('nan')),
                     lambda p: p['analysis']['primary_contrast'].update(right='chosen_on_TEST'),
                     lambda p: p['analysis']['attacks']['fixed10_400ms']['scalar31']['metrics'].update(false_positive=99)]
        for mutate in mutations:
            private = private_report()
            mutate(private)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                reporting.compact_report(private)

    def test_unknown_status_and_quality_notes_do_not_publish_private_messages(self):
        private = private_report(evaluated=False)
        private['group_outcomes'] = [{'group_id': SECRET, 'split': 'train', 'status': SECRET}]
        private['source_split_audit']['status'] = SECRET
        public = reporting.compact_report(private)
        self.assertEqual(public['source_split_audit_status'], 'other')
        self.assertEqual(public['source_and_execution']['recording_status_by_split']['train']['other'], 1)
        self.assertNotIn(SECRET, json.dumps(public))

    def test_nonconverged_variant_stays_visible_as_na_without_changing_quality(self):
        private = private_report()
        result = private['analysis']['attacks']['adaptive_semantic_first']['semantic111']
        result.update(status='nonconverged', metrics=None, locked_calibration=None)
        result['fit_diagnostics']['converged'] = False
        public = reporting.compact_report(private)
        self.assertEqual(public['analysis_status'], 'incomplete_or_diagnostic')
        adaptive = public['methods'][-1]
        self.assertIsNone(adaptive['attacks']['semantic111']['metrics'])
        self.assertIn('nonconverged', reporting.markdown(public))
        self.assertEqual(public['source_quality']['by_split']['train']['sources_with_reported_stalls'], 1)

    def test_duplicate_source_or_method_world_rejected(self):
        for duplicate in ('source', 'case'):
            private = private_report()
            if duplicate == 'source':
                private['group_outcomes'].append(deepcopy(private['group_outcomes'][0]))
            else:
                private['group_outcomes'][0]['cases'].append(deepcopy(private['group_outcomes'][0]['cases'][0]))
            with self.subTest(duplicate=duplicate), self.assertRaises(ValueError):
                reporting.compact_report(private)

    def test_public_renderer_rejects_legacy_schema_or_wrong_profile(self):
        public = reporting.compact_report(private_report(evaluated=False))
        for change in ({'schema': reporting.strict.SCHEMA}, {'source_validation_profile': 'complete_visible_episode'}, {'horizon_ms': 1}):
            malformed = dict(public, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                reporting.markdown(malformed)

    def test_export_does_not_open_references_and_has_hash_receipt_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private_path = root / 'private.json'
            private_path.write_text(json.dumps(private_report(), allow_nan=False))
            output = root / 'public'
            public = reporting.export(private_path, output, make_figures=False)
            self.assertEqual(public, json.loads((output / 'summary.json').read_text()))
            self.assertEqual(public['provenance']['private_report_sha256'], hashlib.sha256(private_path.read_bytes()).hexdigest())
            receipt = json.loads((output / 'artifact-receipt.json').read_text())
            self.assertEqual(receipt['source_validation_profile'], reporting.PROFILE)
            for name, digest in receipt['artifacts_sha256'].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            self.assertNotIn(SECRET, ''.join(path.read_text() for path in output.iterdir()))
            self.assertLess(sum(path.stat().st_size for path in output.iterdir()), 200000)
            with self.assertRaises(FileExistsError):
                reporting.export(private_path, output, make_figures=False)

    def test_malformed_export_fails_before_creating_public_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = private_report(evaluated=False)
            private['source_quality']['quality_filters_enrollment'] = True
            report = root / 'private.json'
            report.write_text(json.dumps(private))
            output = root / 'public'
            with self.assertRaises(ValueError):
                reporting.export(report, output, make_figures=False)
            self.assertFalse(output.exists())

    def test_cli_does_not_echo_private_path_or_identity(self):
        with tempfile.TemporaryDirectory(prefix=SECRET) as temp:
            root = Path(temp)
            private = root / 'private.json'
            private.write_text(json.dumps(private_report(evaluated=False)))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                reporting.main(['--report', str(private), '--output', str(root / 'public'), '--no-figures'])
            payload = json.loads(out.getvalue())
            self.assertEqual(payload['source_validation_profile'], reporting.PROFILE)
            self.assertNotIn(SECRET, out.getvalue())
            self.assertNotIn('output', payload)

    def test_synthetic_figures_use_window_scope_show_all_na_and_are_hash_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / 'private.json'
            private.write_text(json.dumps(private_report(evaluated=False)))
            reporting.export(private, root / 'public', make_figures=True)
            output = root / 'public'
            self.assertTrue((output / 'urban-track-window-attack.png').stat().st_size > 1000)
            for name in ('urban-track-window-attack.svg', 'urban-track-window-utility.svg'):
                svg = (output / name).read_text()
                self.assertIn('All observed contributions of one track', svg)
                self.assertIn('Movement quality is reported separately', svg)
                self.assertNotIn('episode-contribution attack', svg)
                self.assertIn('Fixed 10 m / 0.4 s', svg)
                self.assertIn('Adaptive Semantic First', svg)
                self.assertIn('NA', svg)
                self.assertNotIn(SECRET, svg)
            receipt = json.loads((output / 'artifact-receipt.json').read_text())
            self.assertEqual(len(receipt['artifacts_sha256']), 6)


if __name__ == '__main__':
    unittest.main()
