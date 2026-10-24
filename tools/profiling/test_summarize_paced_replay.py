#!/usr/bin/env python3
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import summarize_paced_replay as summary


def pair():
    events = []
    for logical, start, finish in ((100, 100.2, 110.2), (200, 200.2, 210.2), (250, 250.2, 255.2)):
        events.append(dict(logical_time_ms=logical, kind='finish' if logical == 250 else 'cadence',
                           scheduled_arrival_ms=logical, enqueue_attempt_ms=logical + .05,
                           enqueued_ms=logical + .1, service_start_ms=start,
                           service_finish_ms=finish, queue_depth_after_enqueue=1))
    memory = []
    for logical, wall, count in ((0, .01, 0), (250, 254, 6)):
        memory.append(dict(logical_time_ms=logical, wall_ms=wall, process_resident_bytes=1000 + count,
                           process_peak_resident_bytes=1200 + count, history_bins=count,
                           history_observations=count, history_identity_bytes=100 * count,
                           history_buckets=0, retained_result_bytes=100 * count))
    paced = dict(schema='ump.replay-result.v1', mode='semantic_first',
                 source=dict(sampling_period_ms=100, end_ms=250),
                 parameters=dict(coordination='cell_local'), input_observation_contributions=6,
                 accounted_observation_contributions=6,
                 windows=[dict(secret_identity='never-copy-this-private-road-user')],
                 releases=[dict(release_id='never-copy-this-release-id', end_ms=200, sealed_at_ms=200)],
                 runtime=dict(processing_ms=256, pacing=dict(schema='ump.paced-replay.v1', rate=1,
                    queue_capacity=4, peak_queue_depth=1, overload_behavior='fail_without_successful_output',
                    events=events, memory_samples=memory,
                    release_acknowledgements=[dict(release_id='never-copy-this-release-id', input_event_ms=200,
                        logical_window_end_ms=200, logical_sealed_at_ms=200, in_memory_ack_ms=205)])))
    reference = copy.deepcopy(paced)
    reference['runtime'] = dict(processing_ms=25)
    return paced, reference


def add_audit(value, mode='full'):
    value['runtime']['diagnostics'] = mode
    value['runtime']['decision_audit'] = dict(schema='ump.replay-decision-audit.v1', algorithm='SHA-256',
        retirement_count=1, release_count=1, selected_cell_count=1, suppressed_cell_count=0,
        retirement_sha256='a' * 64, release_sha256='b' * 64)
    if mode == 'minimal':
        value['windows'] = []


def failed_prefix():
    paced, _ = pair()
    events = copy.deepcopy(paced['runtime']['pacing']['events'][:2])
    events[1]['service_finish_ms'] = 410.2
    return dict(schema='ump.paced-replay-failure.v1', successful_replay_result=False,
                mode='semantic_first', diagnostics='minimal', rate=1, progress_step_ms=100,
                sampling_period_ms=100, source_end_ms=500, queue_capacity=1, peak_queue_depth=1,
                scheduled_event_count=5, enqueued_event_count=3, completed_event_count=2,
                wall_elapsed_ms=450, completed_events=events,
                rejected_event=dict(logical_time_ms=400, kind='cadence', scheduled_arrival_ms=400,
                                    enqueue_attempt_ms=400.2, queue_depth_at_rejection=1))


class SummaryTests(unittest.TestCase):
    def test_separate_cadence_finish_delays_and_memory(self):
        paced, reference = pair()
        original = copy.deepcopy(paced)
        result = summary.summarize(paced, reference)
        self.assertEqual(paced, original, 'Summary must not mutate its source objects')
        self.assertEqual(result['cadence']['service']['count'], 2)
        self.assertAlmostEqual(result['cadence']['service']['p95_ms'], 10)
        self.assertAlmostEqual(result['finish']['service']['p95_ms'], 5)
        self.assertAlmostEqual(result['cadence']['queue_wait']['mean_ms'], .1)
        self.assertAlmostEqual(result['cadence']['source_scheduling_lateness']['mean_ms'], .05)
        self.assertAlmostEqual(result['consumer_service_total_ms'], 25)
        self.assertAlmostEqual(result['consumer_busy_fraction'], 25 / 255.2)
        self.assertEqual(result['release']['logical_sealing_delay']['max_ms'], 0)
        self.assertEqual(result['release']['scheduled_window_end_to_in_memory_ack']['max_ms'], 5)
        self.assertEqual(result['memory']['counters']['history_observations']['sampled_max'], 6)
        text = json.dumps(result)
        self.assertNotIn('never-copy', text)
        self.assertNotIn('release_id', text)

    def test_complete_logical_equivalence_required(self):
        paced, reference = pair()
        reference['windows'][0]['secret_identity'] = 'different-private-value'
        with self.assertRaisesRegex(ValueError, 'Logical replay output differs'):
            summary.summarize(paced, reference)

    def test_rejects_missing_noncausal_and_overflow_telemetry(self):
        mutations = [
            lambda d: d['events'].pop(0),
            lambda d: d['events'][0].update(kind='finish'),
            lambda d: d['events'][0].update(scheduled_arrival_ms=99),
            lambda d: d['events'][0].update(enqueued_ms=102),
            lambda d: d['events'][1].update(service_start_ms=100),
            lambda d: d.update(peak_queue_depth=2),
            lambda d: d['events'][0].update(queue_depth_after_enqueue=5),
            lambda d: d['events'][0].update(service_finish_ms=float('nan')),
            lambda d: d['release_acknowledgements'][0].update(in_memory_ack_ms=240),
            lambda d: d['release_acknowledgements'][0].update(release_id='other'),
            lambda d: d['memory_samples'].pop(),
            lambda d: d['memory_samples'][1].update(history_observations=None),
            lambda d: d.update(rate=0),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                paced, reference = pair()
                mutation(paced['runtime']['pacing'])
                with self.assertRaises(ValueError):
                    summary.summarize(paced, reference)

    def test_accelerated_pacing_keeps_logical_delay_unscaled(self):
        paced, reference = pair()
        telemetry = paced['runtime']['pacing']
        telemetry['rate'] = 2
        for event in telemetry['events']:
            for key in ('scheduled_arrival_ms', 'enqueue_attempt_ms', 'enqueued_ms', 'service_start_ms', 'service_finish_ms'):
                event[key] /= 2
        for sample in telemetry['memory_samples']:
            sample['wall_ms'] /= 2
        telemetry['release_acknowledgements'][0]['in_memory_ack_ms'] /= 2
        result = summary.summarize(paced, reference)
        self.assertEqual(result['offered_load']['wall_cadence_ms'], 50)
        self.assertEqual(result['release']['scheduled_window_end_to_in_memory_ack']['max_ms'], 2.5)
        self.assertEqual(result['release']['logical_sealing_delay']['max_ms'], 0)

    def test_explicit_progress_clock_keeps_sensor_and_service_intervals_separate(self):
        paced, _ = pair()
        paced['parameters'].update(progress_step_ms=50, progress_origin_ms=0)
        rows = []
        for logical, start, finish in ((50, 50.2, 110.2), (100, 110.2, 120.2),
                                       (150, 150.2, 160.2), (200, 200.2, 210.2), (250, 250.2, 255.2)):
            rows.append(dict(logical_time_ms=logical, kind='finish' if logical == 250 else 'cadence',
                             scheduled_arrival_ms=logical, enqueue_attempt_ms=logical + .05,
                             enqueued_ms=logical + .1, service_start_ms=start,
                             service_finish_ms=finish, queue_depth_after_enqueue=1))
        paced['runtime']['pacing']['events'] = rows
        reference = copy.deepcopy(paced)
        reference['runtime'] = dict(processing_ms=95)
        result = summary.summarize(paced, reference)
        self.assertEqual(result['source']['sampling_period_ms'], 100)
        self.assertEqual(result['source']['progress_step_ms'], 50)
        self.assertTrue(result['source']['explicit_native_progress'])
        self.assertEqual(result['offered_load']['wall_cadence_ms'], 50)
        self.assertEqual(result['offered_load']['wall_sensor_sampling_period_ms'], 100)
        self.assertEqual(result['cadence']['service']['count'], 4)
        self.assertEqual(result['sample_steps']['service']['count'], 2)
        self.assertEqual(result['no_sample_steps']['service']['count'], 2)
        self.assertEqual(result['cadence_service_over_offered_interval'], 1)
        self.assertEqual(result['response_deadlines']['cadence_deadline_ms'], 50)
        self.assertEqual(result['response_deadlines']['cadence_miss_count'], 1)
        self.assertEqual(result['response_deadlines']['sensor_period_miss_count'], 0)
        self.assertEqual(result['no_sample_steps']['service']['max_ms'], 60)
        self.assertEqual(result['finish']['service']['count'], 1)
        self.assertEqual(result['release']['scheduled_window_end_to_in_memory_ack']['max_ms'], 5)
        self.assertNotIn('never-copy', json.dumps(result))

    def test_explicit_progress_rejects_invalid_clocks_and_missing_origin(self):
        invalid = [dict(progress_step_ms=0, progress_origin_ms=0),
                   dict(progress_step_ms=True, progress_origin_ms=0),
                   dict(progress_step_ms=75, progress_origin_ms=0),
                   dict(progress_step_ms=200, progress_origin_ms=0),
                   dict(progress_step_ms=100, progress_origin_ms=0),  # 250-ms horizon is unaligned
                   dict(progress_step_ms=50), dict(progress_step_ms=50, progress_origin_ms=1),
                   dict(progress_step_ms=50, progress_origin_ms=False), dict(progress_origin_ms=0)]
        for clock in invalid:
            with self.subTest(clock=clock):
                paced, _ = pair()
                paced['parameters'].update(clock)
                reference = copy.deepcopy(paced)
                reference['runtime'] = dict(processing_ms=25)
                with self.assertRaises(ValueError):
                    summary.summarize(paced, reference)

    def test_missing_rss_is_explicit_and_empty_distribution_not_zero(self):
        paced, reference = pair()
        for sample in paced['runtime']['pacing']['memory_samples']:
            sample['process_resident_bytes'] = None
        result = summary.summarize(paced, reference)
        self.assertIsNone(result['memory']['counters']['process_resident_bytes']['sampled_max'])
        self.assertIsNone(summary.distribution([])['max_ms'])
        self.assertEqual(summary.distribution([1, 2, 3, 4])['p95_ms'], 4)

    def test_minimal_requires_matching_complete_native_audits_and_exact_public_output(self):
        paced, reference = pair()
        add_audit(paced, 'minimal')
        add_audit(reference)
        result = summary.summarize(paced, reference)
        self.assertEqual(result['diagnostics']['paced'], 'minimal')
        self.assertIn('complete typed SHA-256', result['diagnostics']['equality_method'])
        mutations = [lambda p, r: r['runtime'].pop('decision_audit'),
                     lambda p, r: r['runtime']['decision_audit'].update(retirement_sha256='c' * 64),
                     lambda p, r: p['runtime']['decision_audit'].update(release_count=0),
                     lambda p, r: p['runtime']['decision_audit'].update(retirement_sha256='not-a-hash'),
                     lambda p, r: p['windows'].append({}),
                     lambda p, r: p['releases'][0].update(end_ms=201)]
        for mutation in mutations:
            p, r = copy.deepcopy(paced), copy.deepcopy(reference)
            mutation(p, r)
            with self.assertRaises(ValueError):
                summary.summarize(p, r)

    def test_failure_is_partial_with_explicit_misses_and_no_success_claim(self):
        failure = failed_prefix()
        result = summary.summarize_failure(failure)
        self.assertFalse(result['successful_replay_result'])
        self.assertIsNone(result['logical_output_equal_excluding_runtime'])
        self.assertEqual(result['events']['completed'], 2)
        self.assertEqual(result['events']['pending_or_uncompleted'], 1)
        self.assertEqual(result['completed_prefix_cadence_response_misses'], 1)
        self.assertEqual(result['completed_sensor_period_response_misses'], 1)
        self.assertEqual(result['completed_prefix']['service']['max_ms'], 210)
        self.assertNotIn('release_id', json.dumps(result))
        empty = failed_prefix()
        empty.update(completed_events=[], completed_event_count=0, enqueued_event_count=1)
        empty['rejected_event'].update(logical_time_ms=200, scheduled_arrival_ms=200, enqueue_attempt_ms=200.2)
        self.assertIsNone(summary.summarize_failure(empty)['completed_prefix']['service']['max_ms'])
        mutations = [lambda f: f.update(successful_replay_result=True),
                     lambda f: f.update(completed_event_count=3),
                     lambda f: f.update(peak_queue_depth=0),
                     lambda f: f.update(scheduled_event_count=6),
                     lambda f: f['completed_events'][0].update(service_start_ms=99),
                     lambda f: f['completed_events'][1].update(logical_time_ms=300),
                     lambda f: f['rejected_event'].update(queue_depth_at_rejection=0),
                     lambda f: f['rejected_event'].update(enqueue_attempt_ms=399)]
        for mutation in mutations:
            malformed = failed_prefix()
            mutation(malformed)
            with self.assertRaises(ValueError):
                summary.summarize_failure(malformed)

    def test_failure_cli_requires_no_reference_and_keeps_explicit_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'failure.json'
            source.write_text(json.dumps(failed_prefix()))
            command = [sys.executable, summary.__file__, '--failure', str(source), '--output', str(root / 'summary.json')]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads((root / 'summary.json').read_text())
            self.assertEqual(output['schema'], 'ump.paced-replay-failure-summary.v1')
            self.assertEqual(output['artifacts']['failure_telemetry'], summary.fingerprint(source))
            self.assertNotEqual(subprocess.run(command + ['--reference', str(source)], capture_output=True).returncode, 0)

    def test_cli_hashes_and_no_overwrite(self):
        paced, reference = pair()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'paced.json').write_text(json.dumps(paced))
            (root / 'reference.json').write_text(json.dumps(reference))
            command = [sys.executable, summary.__file__, '--paced', str(root / 'paced.json'),
                       '--reference', str(root / 'reference.json'), '--output', str(root / 'summary.json')]
            process = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads((root / 'summary.json').read_text())
            self.assertEqual(result['artifacts']['paced_output'], summary.fingerprint(root / 'paced.json'))
            before = (root / 'summary.json').read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual((root / 'summary.json').read_bytes(), before)
            for malformed in ('{"a": 1, "a": 2}', '{"a": NaN}'):
                (root / 'bad.json').write_text(malformed)
                with self.assertRaises(ValueError):
                    summary.load(root / 'bad.json')


if __name__ == '__main__':
    unittest.main()
