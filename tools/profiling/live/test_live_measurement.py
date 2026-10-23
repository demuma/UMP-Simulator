import copy
import datetime as dt
import unittest
from live_measurement import summaries, validate_trace, validate_mongo_audit, stats


def event(stage, logical, offset, duration=0, count=0, a=0, b=0, c=0):
    return dict(stage=stage, logical_ms=logical, offset_ms=offset, duration_ms=duration,
                count=count, a=a, b=b, c=c)


def fixture():
    rows = []
    for i, population in enumerate([3, 2, 2, 0]):
        t, wall = i * 50, 1000 + i * 60
        rows.extend([event('source_state', t, wall, count=population),
                     event('simulation_step', t, wall, duration=55),
                     event('agent_queue_write', t, wall + 40, duration=10, count=6, a=7)])
    rows.extend([event('publication_ack', 100, 1130, 5, 1, 0, 100, 100),
                 event('publication_ack', 200, 1260, 5, 1, 100, 200, 200),
                 event('aggregation_finish', 200, 1250, 20),
                 event('history_state', 100, 1135, count=2, a=5, b=100, c=0),
                 event('local_state', 100, 1135, count=12, a=1, b=2, c=0),
                 event('timing_buffer', 200, 1270, count=64, a=256)])
    for i in range(4):
        t, wall = i * 50, 1200 + i * 60
        rows.extend([event('renderer_receipt', t, wall),
                     event('renderer_draw', t, wall + 3, 7, 1)])
    rows.append(event('renderer_draw', 150, 1395, 7, 0))  # UI-only redraw, not another observation.
    return rows


def iso(ms):
    return (dt.datetime(2026, 10, 14, 10, 30, tzinfo=dt.timezone.utc)
            + dt.timedelta(milliseconds=ms)).isoformat().replace('+00:00', 'Z')


def audit():
    return {'origin_timestamp': iso(0),
            'gt_frames': [{'_id': iso(t), 'count': n} for t, n in [(0, 3), (50, 2), (100, 2)]],
            'gt_inside_frames': [{'_id': iso(t), 'count': n} for t, n in [(0, 3), (50, 1), (100, 1)]],
            'sensor_frames': [{'_id': iso(100), 'road_users': 1, 'count': 1}],
            'journal_states': [{'_id': 'committed', 'count': 2}],
            'release_count': 2, 'journal_count': 2, 'reconciled_release_count': 2}


class LiveMeasurementTests(unittest.TestCase):
    def test_quantiles_and_empty(self):
        self.assertEqual(stats([]), {'count': 0})
        result = stats([5, 1, 4, 2, 3])
        self.assertEqual((result['p50_ms'], result['p95_ms'], result['max_ms']), (3, 5, 5))
        with self.assertRaises(ValueError):
            stats([float('nan')])

    def test_exact_cadence_and_queue_bound(self):
        self.assertEqual(validate_trace(fixture(), 200, True)['source_steps'], 4)
        for stage in ['source_state', 'simulation_step', 'renderer_receipt', 'renderer_draw']:
            rows = fixture()
            next(row for row in rows if row['stage'] == stage)['logical_ms'] = 50
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                validate_trace(rows, 200, True)
        rows = fixture()
        next(row for row in rows if row['stage'] == 'agent_queue_write')['a'] = 9
        with self.assertRaises(ValueError):
            validate_trace(rows, 200, True)
        with self.assertRaises(ValueError):
            validate_trace([row for row in fixture() if row['stage'] != 'aggregation_finish'], 200, True)

    def test_headless_has_no_renderer_events(self):
        rows = [row for row in fixture() if not row['stage'].startswith('renderer_')]
        self.assertEqual(validate_trace(rows, 200, False)['renderer_frames'], 0)
        with self.assertRaises(ValueError):
            validate_trace(fixture(), 200, False)

    def test_eof_ack_is_explicit_and_not_silently_dropped(self):
        report = summaries(fixture())
        self.assertEqual(report['publication_end_to_ack']['count'], 2)
        self.assertEqual(report['publication_end_to_ack']['mean_ms'], 15)
        self.assertEqual(report['publication_end_to_ack']['during_eof']['count'], 1)
        self.assertEqual(report['publication_end_to_ack']['during_regular_steps']['count'], 1)
        self.assertEqual(report['publication_end_to_ack']['unmatched_count'], 0)
        self.assertEqual(report['publication_start_to_ack']['mean_ms'], 140)
        self.assertEqual(report['publication_seal_to_ack']['mean_ms'], 15)
        self.assertEqual(report['publication_ack_counts']['during_eof'], 1)
        rows = fixture()
        next(row for row in rows if row['stage'] == 'publication_ack')['b'] = 99
        self.assertEqual(summaries(rows)['publication_end_to_ack']['unmatched_count'], 1)

    def test_display_drift_and_sampling_scopes(self):
        report = summaries(fixture())
        self.assertEqual(report['source_to_receipt']['mean_ms'], 200)
        self.assertEqual(report['source_to_draw']['mean_ms'], 210)
        self.assertEqual(report['source_to_draw']['count'], 4)
        self.assertEqual(report['renderer_progress']['wall_minus_logical_ms'], 30)
        self.assertEqual(report['source_step_groups']['sensor_due_100ms']['count'], 1)
        self.assertEqual(report['source_step_groups']['no_sensor_sample_50ms']['count'], 3)
        self.assertEqual(report['source_steps_over_50ms'], 4)
        self.assertEqual(report['history_maxima']['observations'], 5)
        self.assertEqual(report['queue_high_water']['agent'], 7)
        self.assertEqual(report['instrumentation_buffer_bytes'], 16384)

    def test_mongo_alignment_sensor_footprint_and_empty_source(self):
        checked = validate_mongo_audit(fixture(), audit())
        self.assertEqual((checked['ground_truth_frames'], checked['sensor_frames']), (3, 1))
        for field in ['gt_frames', 'sensor_frames']:
            changed = copy.deepcopy(audit())
            changed[field][0]['_id'] = iso(50)
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_mongo_audit(fixture(), changed)
        changed = audit()
        changed['sensor_frames'][0]['road_users'] = 2  # Outside-footprint person is not a sensor observation.
        with self.assertRaises(ValueError):
            validate_mongo_audit(fixture(), changed)

    def test_incomplete_publication_audit_rejected(self):
        for field in ['release_count', 'journal_count', 'reconciled_release_count']:
            changed = audit()
            changed[field] = 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_mongo_audit(fixture(), changed)
        changed = audit()
        changed['journal_states'] = [{'_id': 'prepared', 'count': 2}]
        with self.assertRaises(ValueError):
            validate_mongo_audit(fixture(), changed)


if __name__ == '__main__':
    unittest.main()
