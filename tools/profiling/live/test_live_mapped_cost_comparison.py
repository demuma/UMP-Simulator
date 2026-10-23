"""The performance equality gate must retain identity, timestamps and journal state."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'diagnostics/compare_mapped_costs.py'
spec = importlib.util.spec_from_file_location('mapped_cost_comparison', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MappedCostComparisonTests(unittest.TestCase):
    def test_only_fresh_raw_ids_and_run_uuid_are_normalized(self):
        before = [{'_id': 'fresh-before', 'run_id': 'run-before', 'track_id': 'track',
                   'timestamp': '2026-10-23T12:00:00Z', 'position': {'x': 1, 'y': 2}}]
        after = [{**before[0], '_id': 'fresh-after', 'run_id': 'run-after'}]
        normalize = module.canonical_rows
        self.assertEqual(normalize(before, 'run-before', True), normalize(after, 'run-after', True))
        for key, value in [('track_id', 'another-track'), ('timestamp', '2026-10-23T12:00:01Z'),
                           ('position', {'x': 2, 'y': 2})]:
            changed = [{**after[0], key: value}]
            self.assertNotEqual(normalize(before, 'run-before', True),
                                normalize(changed, 'run-after', True))

    def test_journal_ids_state_and_embedded_payload_remain_checked(self):
        before = [{'_id': 'release/run-before/0/100', 'state': 'committed',
                   'release': {'run_id': 'run-before', 'cells': []}}]
        after = [{'_id': 'release/run-after/0/100', 'state': 'committed',
                  'release': {'run_id': 'run-after', 'cells': []}}]
        normalize = module.canonical_rows
        self.assertEqual(normalize(before, 'run-before'), normalize(after, 'run-after'))
        for key, value in [('_id', 'another-id'), ('state', 'prepared'),
                           ('release', {'run_id': 'run-after', 'cells': [123]})]:
            self.assertNotEqual(normalize(before, 'run-before'),
                                normalize([{**after[0], key: value}], 'run-after'))


if __name__ == '__main__':
    unittest.main()
