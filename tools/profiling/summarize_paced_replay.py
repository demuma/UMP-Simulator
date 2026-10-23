#!/usr/bin/env python3
"""Validate a paced replay against its unpaced control and emit compact timings.

No replay is executed. Per-event records, release IDs and private cell contents
are never copied into the compact report. Timing percentiles use nearest rank.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


SCHEMA = 'ump.paced-replay-summary.v1'


def finite(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(name + ' must be finite and >= ' + str(minimum))
    return value


def integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(name + ' must be an integer >= ' + str(minimum))
    return value


def distribution(values):
    if not values:
        return {'count': 0, 'mean_ms': None, 'p50_ms': None, 'p95_ms': None, 'p99_ms': None, 'max_ms': None}
    ordered = sorted(values)
    quantile = lambda p: ordered[max(0, math.ceil(p * len(ordered)) - 1)]
    return dict(count=len(values), mean_ms=sum(values) / len(values), p50_ms=quantile(.5),
                p95_ms=quantile(.95), p99_ms=quantile(.99), max_ms=ordered[-1])


def event_metrics(events):
    deltas = {
        'source_scheduling_lateness': ('enqueue_attempt_ms', 'scheduled_arrival_ms'),
        'enqueue_lock_delay': ('enqueued_ms', 'enqueue_attempt_ms'),
        'queue_wait': ('service_start_ms', 'enqueued_ms'),
        'service': ('service_finish_ms', 'service_start_ms'),
        'scheduled_arrival_to_completion': ('service_finish_ms', 'scheduled_arrival_ms'),
        'actual_enqueue_to_completion': ('service_finish_ms', 'enqueued_ms'),
    }
    return {name: distribution([event[later] - event[earlier] for event in events])
            for name, (later, earlier) in deltas.items()}


def summarize(paced, reference):
    # Shallow projections avoid cloning either large windows/releases structure.
    if {k: v for k, v in paced.items() if k != 'runtime'} != {k: v for k, v in reference.items() if k != 'runtime'}:
        raise ValueError('Logical replay output differs outside the complete runtime field')
    if paced.get('schema') != 'ump.replay-result.v1':
        raise ValueError('Unexpected replay result schema')
    data = paced['runtime']['pacing']
    if data.get('schema') != 'ump.paced-replay.v1':
        raise ValueError('Missing paced replay telemetry schema')
    if reference.get('runtime', {}).get('pacing'):
        raise ValueError('The control must be an unpaced replay')
    rate = finite(data['rate'], 'rate')
    if rate <= 0 or rate > 1000:
        raise ValueError('Pace rate must lie in (0,1000]')
    capacity = integer(data['queue_capacity'], 'queue capacity', 1)
    peak = integer(data['peak_queue_depth'], 'peak queue depth', 1)
    if capacity > 100000 or peak > capacity or data.get('overload_behavior') != 'fail_without_successful_output':
        raise ValueError('Invalid bounded-queue contract')
    period = integer(paced['source']['sampling_period_ms'], 'sampling period', 1)
    end = integer(paced['source']['end_ms'], 'end', 1)
    expected_count = (end - 1) // period + 1
    events = data['events']
    if expected_count > 100000 or not events or len(events) != expected_count:
        raise ValueError('Missing/excess cadence or finish telemetry')
    expected_times = list(range(period, end, period)) + [end]
    previous_finish = 0
    for index, (event, logical_time) in enumerate(zip(events, expected_times)):
        if event['logical_time_ms'] != logical_time or event['kind'] != ('finish' if index == len(events) - 1 else 'cadence'):
            raise ValueError('Cadence/finish schedule does not match the recorded source')
        names = ('scheduled_arrival_ms', 'enqueue_attempt_ms', 'enqueued_ms', 'service_start_ms', 'service_finish_ms')
        values = [finite(event[name], name) for name in names]
        if not math.isclose(values[0], logical_time / rate, rel_tol=1e-12, abs_tol=1e-6):
            raise ValueError('Scheduled arrival differs from logical time / rate')
        # duration_cast rounds an absolute deadline by less than one clock tick.
        if values[1] + 1e-6 < values[0] or any(a > b for a, b in zip(values[1:], values[2:])):
            raise ValueError('Noncausal per-event wall-clock timestamps')
        if event['service_start_ms'] < previous_finish:
            raise ValueError('Consumer events overlap or arrive out of order')
        previous_finish = event['service_finish_ms']
        if not 1 <= integer(event['queue_depth_after_enqueue'], 'queue depth', 1) <= capacity:
            raise ValueError('A queue occupancy exceeds its bound')
    if max(event['queue_depth_after_enqueue'] for event in events) != peak:
        raise ValueError('Reported peak queue depth does not match every-event telemetry')

    releases = paced['releases']
    acknowledgements = data['release_acknowledgements']
    if len(acknowledgements) != len(releases):
        raise ValueError('Release acknowledgement count differs from public release count')
    by_time = {event['logical_time_ms']: event for event in events}
    logical_lags, readiness_lags, runtime_lags = [], [], []
    for release, ack in zip(releases, acknowledgements):
        if ack['release_id'] != release['release_id'] or ack['logical_window_end_ms'] != release['end_ms'] or ack['logical_sealed_at_ms'] != release['sealed_at_ms']:
            raise ValueError('Release acknowledgement provenance mismatch')
        event = by_time.get(ack['input_event_ms'])
        wall = finite(ack['in_memory_ack_ms'], 'in-memory acknowledgement')
        if event is None or not event['service_start_ms'] <= wall <= event['service_finish_ms']:
            raise ValueError('Release acknowledgement falls outside its consumer event')
        logical_lag = release['sealed_at_ms'] - release['end_ms']
        if logical_lag < 0:
            raise ValueError('Release logically precedes its window end')
        logical_lags.append(logical_lag)
        readiness_lags.append(wall - release['end_ms'] / rate)
        runtime_lags.append(wall - release['sealed_at_ms'] / rate)

    memory = data['memory_samples']
    if not memory or memory[0]['logical_time_ms'] != 0 or memory[-1]['logical_time_ms'] != end:
        raise ValueError('Initial/final memory samples missing')
    counters = ('process_resident_bytes', 'process_peak_resident_bytes', 'history_bins', 'history_observations',
                'history_identity_bytes', 'history_buckets', 'retained_result_bytes')
    previous_logical = -1
    previous_wall = -1
    for sample in memory:
        logical = integer(sample['logical_time_ms'], 'memory sample time')
        wall = finite(sample['wall_ms'], 'memory sample wall time')
        if logical <= previous_logical or logical > end or wall < previous_wall or wall > events[-1]['service_finish_ms']:
            raise ValueError('Invalid memory sampling order')
        previous_logical, previous_wall = logical, wall
        for counter in counters:
            if sample[counter] is None and not counter.startswith('process_'):
                raise ValueError('History/result counters cannot be unavailable')
            if sample[counter] is not None:
                integer(sample[counter], counter)
    sampled = {name: {
        'initial': memory[0][name], 'final': memory[-1][name],
        'sampled_max': max((sample[name] for sample in memory if sample[name] is not None), default=None)}
        for name in counters}
    cadence, finish = events[:-1], events[-1:]
    service_total = sum(event['service_finish_ms'] - event['service_start_ms'] for event in events)
    horizon = events[-1]['service_finish_ms']
    return {
        'schema': SCHEMA, 'logical_output_equal_excluding_runtime': True,
        'source': {'logical_duration_ms': end, 'sampling_period_ms': period,
                   'input_observation_contributions': paced['input_observation_contributions'],
                   'accounted_observation_contributions': paced['accounted_observation_contributions']},
        'mode': paced['mode'], 'coordination': paced['parameters']['coordination'],
        'offered_load': {'rate': rate, 'wall_cadence_ms': period / rate,
                         'queue_capacity': capacity, 'peak_queue_depth': peak},
        'quantile_definition': 'nearest rank, ceil(p*n)',
        'cadence': event_metrics(cadence), 'finish': event_metrics(finish),
        'cadence_service_over_offered_interval': sum(event['service_finish_ms'] - event['service_start_ms'] > period / rate for event in cadence),
        'consumer_service_total_ms': service_total, 'wall_horizon_through_finish_ms': horizon,
        'consumer_busy_fraction': service_total / horizon if horizon else None,
        'unpaced_control_processing_ms': finite(reference['runtime']['processing_ms'], 'control processing time'),
        'paced_processing_ms_including_waits': finite(paced['runtime']['processing_ms'], 'paced processing time'),
        'release': {'count': len(releases), 'logical_sealing_delay': distribution(logical_lags),
                    'scheduled_window_end_to_in_memory_ack': distribution(readiness_lags),
                    'scheduled_logical_seal_to_in_memory_ack': distribution(runtime_lags)},
        'memory': {'sample_count': len(memory), 'counters': sampled},
        'limitations': [
            'The producer replays preloaded observations; parsing, validation and core setup precede the arrival origin.',
            'Service includes per-step in-memory serialization and telemetry; consumer busy fraction is wall-clock occupancy, not CPU utilization.',
            'EOF is separate from ordinary cadence events; paced processing time includes intentional waits.',
            'Release timing is an in-memory acknowledgement, not external application or MongoDB receipt.',
            'Process RSS includes preloaded input and retained research diagnostics; history counters are sampled and not total heap accounting.',
            'Sampled maxima are not continuous peaks, except the process high-water RSS counter itself.',
            'Logical equivalence and measured latency do not establish a hard realtime guarantee.',
        ],
    }


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return {'sha256': digest.hexdigest(), 'bytes': Path(path).stat().st_size}


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON object key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Non-finite JSON token: ' + value)
    with Path(path).open() as stream:
        return json.load(stream, object_pairs_hook=pairs, parse_constant=invalid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paced', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New compact JSON report; never overwritten')
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--protocol', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Output already exists')
    paths = {'paced_output': args.paced, 'unpaced_output': args.reference, 'summarizer': Path(__file__)}
    for name in ('binary', 'source', 'protocol'):
        if getattr(args, name):
            paths[name] = getattr(args, name)
    before = {name: fingerprint(path) for name, path in paths.items()}
    report = summarize(load(args.paced), load(args.reference))
    after = {name: fingerprint(path) for name, path in paths.items()}
    if before != after:
        raise ValueError('A source artifact changed during summarization')
    report['artifacts'] = before
    text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n'
    with args.output.open('x') as stream:
        stream.write(text)
    print('Validated logical equivalence and wrote compact paced summary: ' + str(args.output))


if __name__ == '__main__':
    main()
