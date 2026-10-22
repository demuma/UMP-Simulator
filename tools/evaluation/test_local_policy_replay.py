"""Actual C++ local-leaf policy integration and independent-audit regressions."""
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

from run_local_policy_replay import VARIANTS, audit, effective, fixture, intersects, policy, regions, summarize
from oracle import decode_cell

BINARY = Path(os.environ.get('UMP_REPLAY_BINARY', ROOT / 'simulator/build/AggregationReplay'))


class LocalPolicyTests(unittest.TestCase):
    def core(self, config, data=None):
        data = fixture() if data is None else data
        with tempfile.TemporaryDirectory(prefix='ump-local-policy-') as temporary:
            work = Path(temporary)
            inp, cfg, out = (work / name for name in ('input.json', 'policy.json', 'result.json'))
            inp.write_text(json.dumps(data))
            cfg.write_text(json.dumps(config))
            completed = subprocess.run([str(BINARY), '--input', str(inp), '--config', str(cfg),
                                         '--mode', 'semantic_first', '--output', str(out)],
                                        capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = json.loads(out.read_text())
        checked = audit(data, config, result)
        return result, checked

    def test_fixture_is_exact_same_source_for_four_policies_and_only_sixteen_leaves(self):
        data = fixture()
        self.assertEqual(len(data['batches']), 19)
        self.assertEqual(sum(len(b['observations']) for b in data['batches']), 380)
        initial = {r['id']: (r['type'], r['cell_id']) for r in data['batches'][0]['observations']}
        self.assertEqual(len(initial), 20)
        for batch in data['batches']:
            self.assertEqual({r['id']: (r['type'], r['cell_id']) for r in batch['observations']}, initial)
        leaves = [decode_cell(data['coverage'], cid, 6) for cid in range(3 * 4**6, 4 * 4**6)]
        selected = [c for c in leaves if any(intersects(c, r) for r in regions())]
        self.assertEqual(len(selected), 16)
        self.assertTrue(all(sum(intersects(c, r) for r in regions()) == 1 for c in selected))
        guard = regions()[-1]
        self.assertFalse(any(intersects(decode_cell(data['coverage'], r['cell_id'], 6), guard)
                             for r in data['batches'][0]['observations']))

    def test_strict_positive_area_bounds_include_empty_patch_but_not_boundary_neighbours(self):
        config = policy(True, 'temporal_first')
        coarse = {'x': 40, 'y': 10, 'width': 5, 'height': 5}
        bounds, touched = effective(config, coarse)
        self.assertEqual(touched, ['empty-guard-patch'])
        self.assertEqual(bounds['min_category_distinct_contributors']['min'], 5)
        self.assertEqual(bounds['cell_side_m']['max'], 1.25)
        self.assertEqual(bounds['window_duration_ms']['max'], 600)
        for neighbour in ({'x': 42.5, 'y': 10, 'width': 2.5, 'height': 2.5},
                          {'x': 40, 'y': 12.5, 'width': 2.5, 'height': 2.5}):
            bounds, touched = effective(config, neighbour)
            self.assertEqual(touched, [])
            self.assertEqual(bounds, config['policy_tree']['root'])

    def test_four_real_cpp_variants_generalize_merge_suppress_and_preserve_controls(self):
        results = {}
        for name, local, secondary in VARIANTS:
            with self.subTest(name=name):
                config = policy(local, secondary)
                result, checked = self.core(config)
                results[name] = result
                summary = summarize(result, checked)
                self.assertEqual(summary['released_observations'], 285 if local else 380)
                self.assertEqual(summary['retained_fraction'], .75 if local else 1)
                expected = [[0, 600], [600, 1200], [1200, 1800], [1800, 2000]] if local else [
                    [0, 400], [400, 800], [800, 1200], [1200, 1600], [1600, 2000]]
                self.assertEqual(summary['release_intervals_ms'], expected)
                groups = checked['retained_by_source_group']
                self.assertEqual(groups['control-west'], 76)
                self.assertEqual(groups['control-east'], 57)
                self.assertEqual(groups.get('infeasible-scooter', 0), 0 if local else 57)
                self.assertEqual(groups.get('guard-east', 0), 0 if local else 19)
                self.assertEqual(groups.get('guard-south', 0), 0 if local else 19)
                if local:
                    for window in result['windows']:
                        failed = {cell['x']: cell for cell in window['cells'] if not cell['selected']}
                        self.assertEqual(set(failed), {30, 40})
                        self.assertEqual(failed[30]['distinct_road_users'], 3)
                        self.assertEqual(failed[40]['distinct_road_users'], 2)
                        failures = {c['metric']: c for c in failed[40]['checks'] if c['status'] == 'fail'}
                        self.assertEqual(failures['cell_side_m']['max'], 1.25)
                        self.assertEqual(failures['min_category_distinct_contributors']['min'], 5)
                for release in result['releases']:
                    for cell in release['cells']:
                        categories = {b['category_id']: b['distinct_contributors'] for b in cell['semantic']['categories']}
                        if local and cell['x'] == 10:
                            self.assertEqual(categories, {'pedestrian': 4})
                        if local and cell['x'] == 20:
                            self.assertEqual((cell['width'], categories), (2.5, {'cyclist': 4}))
                        if cell['x'] in (2.5, 50):
                            self.assertEqual(cell['width'], 1.25)
                            self.assertEqual(set(categories), {'adult_pedestrian'})
        self.assertEqual(results['uniform_temporal']['releases'], results['uniform_spatial']['releases'])
        self.assertEqual(results['local_temporal']['releases'], results['local_spatial']['releases'])

    def test_audit_rejects_mutated_counts_and_root_coarse_release_under_local_policy(self):
        config = policy(False, 'temporal_first')
        result, _ = self.core(config)
        wrong = deepcopy(result)
        wrong['releases'][0]['cells'][0]['semantic']['categories'][0]['distinct_contributors'] += 1
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            audit(fixture(), config, wrong)
        # The uniform output includes a 5-m guard release crossing an empty strict patch.
        self.assertTrue(any(c['x'] == 40 and c['width'] == 5 for c in result['releases'][0]['cells']))
        with self.assertRaises(ValueError):
            audit(fixture(), policy(True, 'temporal_first'), result)

    def test_unavailable_measurement_never_becomes_complete_release(self):
        data = fixture()
        data['batches'][0] = {**data['batches'][0], 'status': 'unavailable', 'observations': []}
        actual, _ = self.core(policy(True, 'temporal_first'), data)
        self.assertFalse(any(r['start_ms'] == 0 for r in actual['releases']))
        self.assertEqual(actual['windows'][0]['coverage'], 'incomplete')


if __name__ == '__main__':
    unittest.main()
