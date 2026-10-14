"""Check diagnostic fidelity, embedding safety and debug-only MongoDB routing."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build_report import build, import_debug, load_records


def candidate():
    """Small schema-v3 fixture with a failed support check and an unavailable metric."""
    return {
        'schema': 'ump.fixed-candidate.v3', 'data_role': 'internal_research_candidate',
        'run_id': 'test-run', 'sensor_id': 'test-sensor', 'application_id': 'occupancy',
        'start_ms': 0, 'end_ms': 400,
        'grid': {'x': 0, 'y': 0, 'width': 80, 'height': 80},
        'cells': [{
            'cell_id': 192, 'x': 0, 'y': 0, 'width': 10, 'height': 10,
            'threshold_status': 'fail',
            'counts': {'distinct_contributors': 2},
            'metrics': {
                'distinct_contributors': {'value': 2, 'unit': 'contributors'},
                'occupancy_mae': {'value': None, 'unit': 'agents',
                                  'reason': 'offline_reference_required'},
            },
            'checks': [{'metric': 'distinct_contributors', 'status': 'fail',
                        'observed': 2, 'min': 5, 'max': None, 'unit': 'contributors'}],
            'policy': {'effective_id': 'test-policy/1', 'sources': ['region:west']},
        }],
    }


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'candidates.jsonl'

    def write(self, records):
        self.source.write_text(''.join(json.dumps(row) + '\n' for row in records))

    def test_export_preserves_values_and_unavailable_reason(self):
        first = candidate()
        later = copy.deepcopy(first)
        later.update(start_ms=400, end_ms=800)
        self.write([later, first])
        before = self.source.read_bytes()
        output = self.root / 'report.html'
        payload = build([self.source], output)
        html = output.read_text()
        embedded = html.split('<script type="application/json" id="diagnostics">', 1)[1].split('</script>', 1)[0]
        self.assertEqual(json.loads(embedded)['records'], [first, later])
        self.assertEqual(payload['records'], [first, later])
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(len(payload['sources'][0]['sha256']), 64)

    def test_spatial_decisions_and_finest_baseline_remain_separate(self):
        finest = candidate()
        spatial = copy.deepcopy(finest)
        spatial.update(schema='ump.spatial-selection.v1', data_role='internal_spatial_selection')
        spatial['source_cells'] = copy.deepcopy(finest['cells'])
        spatial['attempts'] = copy.deepcopy(finest['cells'])
        spatial['cells'][0]['decision'] = {'state': 'suppressed', 'reason': 'requirements_failed_at_depth_cap',
                                          'transition': 'suppressed', 'trigger_cells': []}
        self.write([finest, spatial])
        payload = build([self.source], self.root / 'spatial.html')
        self.assertEqual(payload['records'], [finest, spatial])
        self.assertNotIn('decision', payload['records'][1]['source_cells'][0])
        self.assertEqual(payload['records'][1]['cells'][0]['decision']['state'], 'suppressed')

    def test_metadata_cannot_close_the_inert_data_element(self):
        row = candidate()
        row['sensor_id'] = '</script><script>alert("example")</script> · sensor'
        self.write([row])
        output = self.root / 'report.html'
        build([self.source], output)
        embedded = output.read_text().split('<script type="application/json" id="diagnostics">', 1)[1].split('</script>', 1)[0]
        self.assertNotIn('<', embedded)
        self.assertEqual(json.loads(embedded)['records'][0], row)

    def test_duplicate_windows_and_wrong_schema_are_rejected(self):
        row = candidate()
        self.write([row, row])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            load_records([self.source])
        row['schema'] = 'ump.fixed-candidate.v2'
        self.write([row])
        with self.assertRaisesRegex(ValueError, 'v3'):
            load_records([self.source])

    def test_invalid_geometry_is_not_displayed_as_a_valid_cell(self):
        row = candidate()
        row['cells'][0]['x'] = 79
        self.write([row])
        with self.assertRaisesRegex(ValueError, 'outside'):
            load_records([self.source])

    @patch('build_report.subprocess.run')
    @patch('build_report.shutil.which', return_value='/example/mongoimport')
    def test_mongo_import_is_debug_only_and_upserts_window_keys(self, which, run):
        with self.assertRaisesRegex(ValueError, 'dedicated database'):
            import_debug([self.source], 'Simulation')
        run.assert_not_called()
        import_debug([self.source], 'UMP_Debug_Test')
        args = run.call_args.args[0]
        self.assertEqual(args[args.index('--db') + 1], 'UMP_Debug_Test')
        self.assertEqual(args[args.index('--collection') + 1], 'aggregation_candidates')
        self.assertEqual(args[args.index('--mode') + 1], 'upsert')
        self.assertEqual(args[args.index('--upsertFields') + 1],
                         'schema,run_id,sensor_id,application_id,start_ms,end_ms')
        self.assertNotIn('--drop', args)


if __name__ == '__main__':
    unittest.main()
