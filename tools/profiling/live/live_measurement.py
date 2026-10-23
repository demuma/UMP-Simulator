"""Pure validation and summary math for isolated live-pipeline traces.

All wall offsets use the instrumentation's one steady-clock epoch. Source state
means simulator state processing, not a physical sensor arrival. EOF is a separate
source boundary and must not be silently excluded from release-latency summaries.
"""
import datetime as dt
import math


def stats(values):
    values = sorted(values)
    if not values:
        return {'count': 0}
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Nonfinite summary value')
    return {'count': len(values), 'total_ms': sum(values), 'mean_ms': sum(values) / len(values),
            **{name + '_ms': values[math.ceil(q * len(values)) - 1]
               for name, q in [('p50', .5), ('p95', .95), ('p99', .99)]},
            'max_ms': values[-1]}


def _selected(events, stage):
    return [event for event in events if event['stage'] == stage]


def validate_trace(events, duration_ms, renderer, capacity=8, step_ms=50):
    if duration_ms <= 0 or duration_ms % step_ms:
        raise ValueError('Duration must be a positive whole number of simulation steps')
    for event in events:
        if (not math.isfinite(event['offset_ms']) or event['offset_ms'] < 0
                or not math.isfinite(event['duration_ms']) or event['duration_ms'] < 0):
            raise ValueError('Trace contains invalid wall-clock offsets/durations')
    expected = list(range(0, duration_ms, step_ms))
    for stage in ['source_state', 'simulation_step']:
        rows = _selected(events, stage)
        if [row['logical_ms'] for row in rows] != expected:
            raise ValueError(stage + ' does not match the exact source cadence')
    finish = _selected(events, 'aggregation_finish')
    if len(finish) != 1 or finish[0]['logical_ms'] != duration_ms:
        raise ValueError('Exactly one aggregation EOF boundary is required')
    source = _selected(events, 'source_state')
    if any(y['offset_ms'] <= x['offset_ms'] for x, y in zip(source, source[1:])):
        raise ValueError('Source wall clock is not strictly increasing')
    for stage in ['renderer_receipt', 'renderer_draw']:
        rows = _selected(events, stage)
        if stage == 'renderer_draw':
            rows = [row for row in rows if row['count']]
        if [row['logical_ms'] for row in rows] != (expected if renderer else []):
            raise ValueError(stage + ' does not match source frame order exactly')
    for stage in ['agent_queue_write', 'sensor_queue_write']:
        if any(not 1 <= row['a'] <= capacity for row in _selected(events, stage)):
            raise ValueError('Observed queue occupancy violates configured capacity')
    return {'source_steps': len(expected), 'renderer_frames': len(expected) if renderer else 0,
            'exclusive_end_ms': duration_ms, 'queue_capacity': capacity}


def _timestamp_ms(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Mongo timestamps must have an explicit timezone')
    return round(parsed.timestamp() * 1000)


def validate_mongo_audit(events, audit, sensor_period_ms=100):
    origin = _timestamp_ms(audit['origin_timestamp'])
    source = {row['logical_ms']: row['count'] for row in _selected(events, 'source_state')}
    expected_gt = [(time, population) for time, population in source.items() if population]
    actual_gt = [(_timestamp_ms(row['_id']) - origin, row['count']) for row in audit['gt_frames']]
    if actual_gt != expected_gt:
        raise ValueError('Ground-truth timestamps/populations differ from source states')
    inside = [(_timestamp_ms(row['_id']) - origin, row['count']) for row in audit['gt_inside_frames']]
    if len(dict(inside)) != len(inside) or any(time not in source or not 0 < count <= source[time]
                                             for time, count in inside):
        raise ValueError('Inside-footprint ground truth has invalid timestamps/populations')
    expected_sensor = [(time, population) for time, population in inside
                       if time > 0 and time % sensor_period_ms == 0]
    actual_sensor = [(_timestamp_ms(row['_id']) - origin, row['road_users'])
                     for row in audit['sensor_frames']]
    if actual_sensor != expected_sensor:
        raise ValueError('Sensor timestamps/counts differ from in-footprint ground truth at sampling instants')
    if any(row['_id'] != 'committed' for row in audit['journal_states']):
        raise ValueError('Publication journal contains pending/unknown states')
    acknowledgements = sum(row['count'] == 1 for row in _selected(events, 'publication_ack'))
    if not (audit['release_count'] == audit['journal_count']
            == audit['reconciled_release_count'] == acknowledgements):
        raise ValueError('Recipient, committed journal and acknowledged call counts differ')
    return {'ground_truth_frames': len(actual_gt), 'sensor_frames': len(actual_sensor),
            'acknowledged_releases': acknowledgements,
            'publication_contract': 'fresh no-retry namespace; complete recipient/journal payload equality checked by Mongo audit'}


def summaries(events):
    stages = sorted(set(row['stage'] for row in events))
    out = {stage: stats(row['duration_ms'] for row in _selected(events, stage)) for stage in stages}
    source = {row['logical_ms']: row for row in _selected(events, 'source_state')}
    finish = _selected(events, 'aggregation_finish')
    boundary = dict(source)
    boundary.update({row['logical_ms']: row for row in finish})
    eof_times = {row['logical_ms'] for row in finish}
    receipt = _selected(events, 'renderer_receipt')
    draws = [row for row in _selected(events, 'renderer_draw') if row['count']]
    for name, rows in [('source_to_receipt', receipt), ('source_to_draw', draws)]:
        out[name] = stats(row['offset_ms'] + row['duration_ms'] - source[row['logical_ms']]['offset_ms']
                          for row in rows if row['logical_ms'] in source)
        out[name]['unmatched_count'] = sum(row['logical_ms'] not in source for row in rows)
    ordered = sorted(source.values(), key=lambda row: row['logical_ms'])
    out['source_wall_intervals'] = stats(y['offset_ms'] - x['offset_ms'] for x, y in zip(ordered, ordered[1:]))
    out['population'] = ({'initial': ordered[0]['count'], 'final': ordered[-1]['count'],
                          'minimum': min(row['count'] for row in ordered),
                          'maximum': max(row['count'] for row in ordered)} if ordered else None)
    steps = _selected(events, 'simulation_step')
    out['source_steps_over_50ms'] = sum(row['duration_ms'] > 50 for row in steps)
    out['source_step_groups'] = {
        'sensor_due_100ms': stats(row['duration_ms'] for row in steps
                                 if row['logical_ms'] > 0 and row['logical_ms'] % 100 == 0),
        'no_sensor_sample_50ms': stats(row['duration_ms'] for row in steps
                                     if row['logical_ms'] == 0 or row['logical_ms'] % 100 != 0)}
    out['source_step_group_scope'] = '50-ms simulation / 100-ms sensor configuration; includes all synchronous writes and queue blocking'
    for label, stage, fields in [
            ('history_maxima', 'history_state', [('bins', 'count'), ('observations', 'a'), ('identity_bytes', 'b'), ('buckets', 'c')]),
            ('local_maxima', 'local_state', [('frontier', 'count'), ('handoffs', 'a'), ('handoff_intents', 'b'), ('pending', 'c')])]:
        rows = _selected(events, stage)
        out[label] = {key: max((row[field] for row in rows), default=0) for key, field in fields}
        out[label]['sample_count'] = len(rows)
    out['state_maxima_scope'] = 'sampled after normal sensor ingest/local advance; not peaks within a call or EOF'
    out['instrumentation_buffer_bytes'] = sum(row['count'] * row['a'] for row in _selected(events, 'timing_buffer'))
    ack = [row for row in _selected(events, 'publication_ack') if row['count'] == 1]
    out['publication_ack_counts'] = {'acknowledged_calls': len(ack),
        'unacknowledged_calls': sum(row['count'] != 1 for row in _selected(events, 'publication_ack')),
        'during_eof': sum(row['logical_ms'] in eof_times for row in ack)}
    for label, field in [('publication_start_to_ack', 'a'), ('publication_end_to_ack', 'b'),
                         ('publication_seal_to_ack', 'c')]:
        def values(rows):
            return [row['offset_ms'] + row['duration_ms'] - boundary[row[field]]['offset_ms']
                    for row in rows if row[field] in boundary]
        out[label] = stats(values(ack))
        out[label]['unmatched_count'] = sum(row[field] not in boundary for row in ack)
        out[label]['during_eof'] = stats(values([row for row in ack if row['logical_ms'] in eof_times]))
        out[label]['during_regular_steps'] = stats(values([row for row in ack if row['logical_ms'] not in eof_times]))
    out['publication_latency_scope'] = ('Start/end/seal refer to logical window boundaries mapped to source-state wall starts; '
        'EOF uses aggregation_finish start. ACK is recipient database acknowledgment before private-journal commit, '
        'not external client receipt. No external source schedule is implied.')
    out['queue_high_water'] = {name: max((row['a'] for row in _selected(events, name + '_queue_write')), default=0)
                               for name in ['agent', 'sensor']}
    if len(receipt) > 1:
        first, last = receipt[0], receipt[-1]
        wall = last['offset_ms'] - first['offset_ms']
        logical = last['logical_ms'] - first['logical_ms']
        out['renderer_progress'] = {'observed_wall_ms': wall, 'logical_progress_ms': logical,
                                    'wall_minus_logical_ms': wall - logical,
                                    'logical_per_wall_ratio': logical / wall if wall else None,
                                    'scope': 'first-to-last frame read; excludes initial wait, final draw and shutdown; requested playback 1x'}
    return out
