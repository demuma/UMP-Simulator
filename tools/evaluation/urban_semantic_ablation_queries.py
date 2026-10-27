"""Aligned category-count workload for the semantic-action ablation.

The recipient snapshot is fixed at the source horizon. Every full 20 m / 400 ms
query is asked for every taxonomy node, including its all-road-user root. Exact
answers require contained complete tiles. Estimates allocate identifiable counts
uniformly in sampled space/time only: semantic ambiguity always remains unknown.
Counts are observation contributions, not distinct people or instantaneous flow.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math

import scoped_semantic_queries as scoped

SCHEMA = 'ump.urban-semantic-ablation-queries.v1'
REFERENCE_SCHEMA = 'ump.urban-semantic-ablation-reference.v1'
SUMMARY_FIELDS = (
    'query_count', 'reference_available_query_count', 'reference_unavailable_query_count',
    'answered_query_count', 'scored_query_count', 'query_coverage', 'scored_query_coverage',
    'absolute_error_sum', 'answered_only_mae', 'known_zero_reference_query_count',
    'positive_reference_query_count', 'known_zero_scored_query_count', 'positive_scored_query_count')
REASONS = ('missing_public_support', 'semantic_generalization', 'crossing_public_support', 'no_scheduled_samples')
MAX_QUERIES = 500000


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def prepare_reference(replay, taxonomy, *, cell_side_m=20, window_ms=400):
    """Validate and cache a private source reference once per IN/OUT recording."""
    config = taxonomy if 'semantic_taxonomy' in taxonomy else {'semantic_taxonomy': taxonomy}
    catalog = scoped._catalog(config)
    grid = scoped._coverage(replay)
    side = scoped._number(cell_side_m, 'query cell side')
    if side <= 0 or grid['width'] != grid['height']:
        raise ValueError('Aligned queries require a positive side and square coverage')
    ratio = grid['width'] / side
    depth = round(math.log2(ratio)) if ratio > 0 else -1
    if depth < 0 or depth > grid['leaf_depth'] or not math.isclose(2 ** depth, ratio, rel_tol=1e-12):
        raise ValueError('Query side must be a quadtree partition within the source grid')
    period = scoped._integer(replay.get('sampling_period_ms'), 'sampling period', 1)
    window = scoped._integer(window_ms, 'query window', period)
    horizon = scoped._integer(replay.get('end_ms'), 'source horizon', period + 1)
    if window % period:
        raise ValueError('Query window must align with sensor cadence')
    windows = horizon // window
    categories = sorted(catalog['nodes'])
    if not windows or windows * 4 ** depth * len(categories) > MAX_QUERIES:
        raise ValueError('Aligned query budget exceeded or no full query window')
    targets = [scoped._geometry((3 << (2 * depth)) + i, depth, grid) for i in range(4 ** depth)]
    source, measured = scoped._source(replay, catalog, grid, period, horizon, window,
                                      {target['cell_id'] for target in targets})
    definition = dict(schema=SCHEMA, cell_side_m=side, window_ms=window,
        count_unit='observation_contributions', categories=categories,
        all_road_user_category=next(node for node, value in catalog['nodes'].items() if not value['parent']),
        taxonomy_sha256=_digest(catalog['declaration']), sampling_period_ms=period,
        source_horizon_ms=horizon, full_window_count=windows, spatial_cell_count=len(targets),
        query_count=windows * len(targets) * len(categories), trailing_time_ms=horizon-windows*window,
        recipient_view='one final snapshot at the source horizon', initial_sample_excluded=True,
        exact_rule='complete contained identifiable public space-time/category tiles only',
        estimate_rule='uniform sampled-space/time allocation of identifiable public category counts; semantic ambiguity remains unknown',
        reference_rule='each world own sampled input; missing/unavailable samples remain unknown',
        aggregation_rule='per-node workloads overlap taxonomically; never sum ancestor and descendant counts as independent traffic')
    return dict(schema=REFERENCE_SCHEMA, source_object_identity=id(replay), definition=definition, grid=grid, catalog=catalog,
                targets=targets, counts=source, measured=measured)


def _blank():
    return dict(query_count=0, reference_available_query_count=0, reference_unavailable_query_count=0,
        answered_query_count=0, scored_query_count=0, absolute_error_sum=0.,
        known_zero_reference_query_count=0, positive_reference_query_count=0,
        known_zero_scored_query_count=0, positive_scored_query_count=0,
        unknown_reasons={reason: 0 for reason in REASONS})


def _add(summary, reference, answered, prediction, reasons):
    summary['query_count'] += 1
    summary['reference_available_query_count' if reference is not None else 'reference_unavailable_query_count'] += 1
    summary['answered_query_count'] += int(answered)
    if reference is not None:
        summary['known_zero_reference_query_count' if reference == 0 else 'positive_reference_query_count'] += 1
        if answered:
            summary['scored_query_count'] += 1
            summary['absolute_error_sum'] += abs(prediction-reference)
            summary['known_zero_scored_query_count' if reference == 0 else 'positive_scored_query_count'] += 1
    if not answered:
        for reason in reasons:
            summary['unknown_reasons'][reason] += 1


def _finish(summary):
    n, available, scored = summary['query_count'], summary['reference_available_query_count'], summary['scored_query_count']
    summary.update(query_coverage=summary['answered_query_count']/n if n else None,
                   scored_query_coverage=scored/available if available else None,
                   answered_only_mae=summary['absolute_error_sum']/scored if scored else None)
    return summary


def evaluate(replay, public, taxonomy, *, cell_side_m=20, window_ms=400, reference=None, include_queries=False):
    """Decode public releases and return aggregate exact/estimated category errors.

    Suppressed or absent support is never treated as a known zero. Source counts
    enter error/reference availability only, never the recipient predictions.
    ``reference`` must come from prepare_reference on this same input; callers
    reuse it only within one authenticated recording/world.
    """
    prepared = prepare_reference(replay, taxonomy, cell_side_m=cell_side_m, window_ms=window_ms) if reference is None else reference
    if prepared.get('schema') != REFERENCE_SCHEMA or prepared.get('source_object_identity') != id(replay):
        raise ValueError('Expected a prepared aligned-query reference')
    definition = prepared['definition']
    if (definition['cell_side_m'] != cell_side_m or definition['window_ms'] != window_ms
            or definition['source_horizon_ms'] != replay.get('end_ms')
            or definition['sampling_period_ms'] != replay.get('sampling_period_ms')
            or prepared['grid'] != scoped._coverage(replay)):
        raise ValueError('Cached reference does not match query/source headers')
    config = taxonomy if 'semantic_taxonomy' in taxonomy else {'semantic_taxonomy': taxonomy}
    if _digest(scoped._catalog(config)['declaration']) != definition['taxonomy_sha256']:
        raise ValueError('Cached reference taxonomy changed')
    if not isinstance(public, dict) or not isinstance(public.get('releases'), list):
        raise ValueError('Expected a public recipient release object')
    catalog, targets = prepared['catalog'], prepared['targets']
    period, horizon, window = definition['sampling_period_ms'], definition['source_horizon_ms'], definition['window_ms']
    records = scoped._public(public['releases'], prepared['grid'], catalog, horizon, period)
    # Bounded Morton-space intersections avoid expanding fine leaves or checking
    # every public tile against every query. Uniform allocation remains explicit.
    candidates = defaultdict(list)
    for row in records:
        for target in targets:
            overlap_space = min(row['hi'], target['hi'])-max(row['lo'], target['lo'])
            if overlap_space <= 0:
                continue
            for index in range(max(0, row['start']//window), min(definition['full_window_count'], (row['end']-1)//window+1)):
                start, end = index*window, (index+1)*window
                tlo, thi = max(1, start//period), end//period
                overlap_time = min(row['thi'], thi)-max(row['tlo'], tlo)
                if overlap_time > 0:
                    candidates[(index, target['cell_id'])].append((row, overlap_space*overlap_time,
                        row['start'] >= start and row['end'] <= end and row['lo'] >= target['lo'] and row['hi'] <= target['hi']))
    output = {mode:dict(summary=_blank(), by_category={node:_blank() for node in definition['categories']}) for mode in ('exact','estimate')}
    if include_queries:
        for item in output.values(): item['queries'] = []
    count_cache = {}
    for index in range(definition['full_window_count']):
        start, end = index*window, (index+1)*window
        scheduled = end//period-max(1,start//period)
        available = scheduled > 0 and prepared['measured'][index] == scheduled
        for target in targets:
            rows = candidates.get((index,target['cell_id']),())
            required = (target['hi']-target['lo'])*scheduled
            raw = prepared['counts'].get((index,target['cell_id']),{})
            for category in definition['categories']:
                truth = sum(n for node,n in raw.items() if node in catalog['domains'][category]) if available else None
                volumes = {'exact':0,'estimate':0}; predictions = {'exact':0.,'estimate':0.}
                reasons = {'exact':set(),'estimate':set()}
                for row, volume, contained in rows:
                    key = (id(row),category)
                    if key not in count_cache:
                        count_cache[key] = scoped._category_count(row['bins'], category, catalog)
                    count = count_cache[key]
                    if count is None:
                        for mode in reasons: reasons[mode].add('semantic_generalization')
                        continue
                    volumes['estimate'] += volume
                    predictions['estimate'] += count*volume/((row['hi']-row['lo'])*(row['thi']-row['tlo']))
                    if contained:
                        volumes['exact'] += volume; predictions['exact'] += count
                    else:
                        reasons['exact'].add('crossing_public_support')
                for mode in ('exact','estimate'):
                    answered = scheduled > 0 and volumes[mode] == required
                    if not scheduled: reasons[mode].add('no_scheduled_samples')
                    if volumes[mode] < required: reasons[mode].add('missing_public_support')
                    prediction = predictions[mode] if answered else None
                    _add(output[mode]['summary'],truth,answered,prediction,reasons[mode])
                    _add(output[mode]['by_category'][category],truth,answered,prediction,reasons[mode])
                    if include_queries:
                        output[mode]['queries'].append(dict(start_ms=start,end_ms=end,cell_id=target['cell_id'],category_id=category,
                            reference=truth,answered=answered,prediction=prediction,
                            absolute_error=abs(prediction-truth) if answered and truth is not None else None,
                            unknown_reasons=[] if answered else sorted(reasons[mode])))
    for value in output.values():
        _finish(value['summary'])
        for entry in value['by_category'].values(): _finish(entry)
    return dict(schema=SCHEMA,query_definition=deepcopy(definition),
        decode_diagnostics=dict(public_tiles=len(records),candidate_intersections=sum(len(rows) for rows in candidates.values()),
            query_count=definition['query_count']),**output)
