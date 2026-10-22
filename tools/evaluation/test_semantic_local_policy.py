"""Real C++ scoped semantic release and independent raw-data audit regressions."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('UMP_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / 'tools/evaluation'))
from run_local_policy_replay import fixture, normalized
from run_semantic_local_policy import VARIANTS, checked_summary, configuration

BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT / 'simulator/build/AggregationReplay'))


class SemanticLocalTests(unittest.TestCase):
    @staticmethod
    def core(config, data=None, mode='semantic_first'):
        data = fixture() if data is None else data
        with tempfile.TemporaryDirectory(prefix='ump-semantic-local-') as temporary:
            work = Path(temporary)
            inp, cfg, out = (work / name for name in ('input.json', 'policy.json', 'result.json'))
            inp.write_text(json.dumps(data))
            cfg.write_text(json.dumps(config))
            completed = subprocess.run([str(BINARY), '--input', str(inp), '--config', str(cfg),
                                        '--mode', mode, '--output', str(out)],
                                       capture_output=True, text=True, timeout=30)
            if completed.returncode:
                raise AssertionError(completed.stdout + completed.stderr)
            result = json.loads(out.read_text())
        summary, checked = checked_summary(data, config, result)
        return result, summary, checked

    @classmethod
    def setUpClass(cls):
        cls.cases = {}
        for name, coord, regional, secondary in VARIANTS:
            cls.cases[name] = cls.core(configuration(coord, regional, secondary))

    def test_same_input_all_eight_modes_account_exact_source_and_respect_regions(self):
        for name, (_, summary, checked) in self.cases.items():
            with self.subTest(name=name):
                self.assertEqual(summary['input_observations'], 380)
                self.assertEqual(summary['independent_audit'], 'verified')
                self.assertTrue(checked['scalar']['valid'])
                self.assertEqual(summary['released_observations'], 285 if '_regional_' in name else 380)
                self.assertEqual(summary['per_source_group']['control-west']['released_observations'], 76)
                self.assertEqual(summary['per_source_group']['control-east']['released_observations'], 57)
                self.assertEqual(sum(g['input_observations'] for g in summary['per_source_group'].values()), 380)
                if '_regional_' in name:
                    missing = summary['per_source_group']['infeasible-scooter']
                    self.assertEqual(missing['unreleased_observations'], 57)
                    self.assertIsNone(missing['mean_interval_start_age_ms'])

    def test_valid_control_releases_at_base_period_independent_of_failed_region(self):
        for secondary in ('temporal_first', 'spatial_first'):
            common = self.cases[f'common_window_regional_{secondary}'][1]
            local = self.cases[f'cell_local_regional_{secondary}'][1]
            for group in ('control-west', 'control-east'):
                a, b = (s['per_source_group'][group] for s in (common, local))
                self.assertEqual(a['intervals'][0], [0, 600])
                self.assertEqual(b['intervals'], [[0, 400], [400, 800], [800, 1200],
                                                [1200, 1600], [1600, 2000]])
                self.assertLess(b['mean_interval_start_age_ms'], a['mean_interval_start_age_ms'])
                self.assertLess(b['mean_observation_to_release_delay_ms'], a['mean_observation_to_release_delay_ms'])
            self.assertEqual(common['mean_semantic_loss'], local['mean_semantic_loss'])

    def test_scopes_are_explicit_and_immediate_secondaries_can_match(self):
        for name, (result, _, _) in self.cases.items():
            local = name.startswith('cell_local')
            self.assertTrue(all(('coordination_cell' in w) == local for w in result['windows']))
            self.assertTrue(all(('coordination_cell' in r) == local for r in result['releases']))
        for coord in ('common_window', 'cell_local'):
            for scope in ('uniform', 'regional'):
                a, b = (self.cases[f'{coord}_{scope}_{secondary}'][0] for secondary in
                        ('temporal_first', 'spatial_first'))
                self.assertEqual(a['releases'], b['releases'])

    def test_exact_repeat_preserves_scientific_output(self):
        config = configuration('cell_local', True, 'temporal_first')
        repeated, _, _ = self.core(config)
        self.assertEqual(normalized(repeated), normalized(self.cases['cell_local_regional_temporal_first'][0]))

    def test_auditor_rejects_incorrect_semantics_and_reused_scope(self):
        config = configuration('cell_local', True, 'temporal_first')
        result = self.cases['cell_local_regional_temporal_first'][0]
        wrong = deepcopy(result)
        wrong['releases'][0]['cells'][0]['semantic']['categories'][0]['distinct_contributors'] += 1
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            checked_summary(fixture(), config, wrong)
        wrong = deepcopy(result)
        wrong['releases'][0]['cells'][0]['semantic']['schema'] = 'unknown.v0'
        with self.assertRaisesRegex(ValueError, 'schema'):
            checked_summary(fixture(), config, wrong)
        wrong = deepcopy(result)
        wrong['windows'].append(deepcopy(wrong['windows'][0]))
        with self.assertRaisesRegex(ValueError, 'scalar/retirement'):
            checked_summary(fixture(), config, wrong)
        wrong = deepcopy(result)
        wrong['releases'][0].pop('coordination_cell')
        with self.assertRaisesRegex(ValueError, 'scalar/retirement'):
            checked_summary(fixture(), config, wrong)

    def test_incomplete_measurement_is_not_released_and_eof_retires_every_scope(self):
        data = fixture()
        data['batches'][0] = {**data['batches'][0], 'status': 'unavailable', 'observations': []}
        result, _, checked = self.core(configuration('cell_local', True, 'temporal_first'), data)
        self.assertFalse(any(r['start_ms'] == 0 for r in result['releases']))
        self.assertTrue(checked['scalar']['valid'])
        # The scalar audit verifies both no overlap and full 4096-leaf space-time volume.
        self.assertEqual(result['accounted_observation_contributions'], 360)

    def test_taxonomy_enabled_tf_sf_are_accepted_with_scoped_publications(self):
        for mode in ('temporal_first', 'spatial_first'):
            config = configuration('cell_local', True, 'temporal_first')
            config['policy_tree']['execution']['strategy'] = mode
            config['policy_tree']['execution'].pop('semantic_secondary_strategy')
            result, _, checked = self.core(config, mode=mode)
            self.assertTrue(checked['scalar']['valid'])
            self.assertTrue(result['releases'])
            self.assertTrue(all('coordination_cell' in r for r in result['releases']))


if __name__ == '__main__':
    unittest.main()
