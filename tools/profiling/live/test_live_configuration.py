"""Safety and policy-transcription checks; no subprocess, MongoDB or renderer use."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
import run_live

class LiveConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(os.environ.get('UMP_LIVE_TEST_REPO', str(Path(__file__).resolve().parents[3])))
        spec = importlib.util.spec_from_file_location('capture_helper', repo / 'tools/evaluation/capture_simulator.py')
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        run_live.REPO, run_live.cap = repo, helper
        run_live.POLICY = Path(__file__).with_name('semantic_local_policy.json')

    def test_owned_names_and_no_destructive_clear(self):
        text, databases, policy = run_live.configuration('a' * 32, False, 120)
        self.assertEqual(len(databases), 3)
        self.assertEqual(len(set(databases)), 3)
        self.assertTrue(all(name.startswith('UMP_Live_' + 'a' * 32 + '_') for name in databases))
        self.assertNotIn('Simulation', text)
        self.assertIn('clear_database: false', text)
        self.assertNotIn('clear_database: true', text)
        self.assertIn('  buffer_capacity: 8\n', text)
        self.assertEqual(text.count(databases[0]), 2)
        self.assertEqual(text.count(databases[1]), 1)
        self.assertEqual(text.count(databases[2]), 1)

    def test_semantic_policy_is_exact(self):
        text, databases, policy = run_live.configuration('b' * 32, True, 120)
        original = json.loads(run_live.POLICY.read_text())
        self.assertEqual(original.pop('policy_regions'), [])
        self.assertEqual({key: policy[key] for key in original}, original)
        self.assertIn('  show_renderer: true\n', text)
        self.assertIn('  playback_speed: 1.0\n', text)
        self.assertIn('  num_agents: 500\n', text)
        self.assertEqual(policy['policy_tree']['regions'], [])

    def test_invalid_namespace_token_rejected(self):
        for token in ['', 'x' * 32, 'a' * 31, '../Simulation', 'A' * 32]:
            with self.subTest(token=token), self.assertRaises(ValueError):
                run_live.configuration(token, False, 120)

    def test_bounded_duration_rejected_before_run(self):
        for duration in [0, -1, 601, 1.5, True]:
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                run_live.configuration('c' * 32, False, duration)

if __name__ == '__main__':
    unittest.main()
