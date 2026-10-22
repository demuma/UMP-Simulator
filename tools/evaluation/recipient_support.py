"""Additive recipient support diagnostics for the conservative exact decoder.

Public record/query intersections partition Morton-leaf x scheduled-sample
support. They diagnose representation compatibility, not the reason a producer
withheld a value. An optional uniform-allocation estimate is a separate decoder;
it never replaces the exact answers, imputes semantic categories, or fills gaps.
"""
from copy import deepcopy
import math

import scoped_semantic_queries as exact

SCHEMA = 'ump.recipient-support.v1'
SPATIAL_CROSSING = 1
TEMPORAL_CROSSING = 2
SEMANTIC_AMBIGUITY = 4
LATE = 8
UNPUBLISHED = 16
MASK_NAMES = {'1': 'spatial_crossing', '2': 'temporal_crossing',
              '4': 'semantic_ambiguity', '8': 'late', '16': 'unpublished_at_eof'}


def _partition(query, target, records, catalog, period, estimate_enabled):
    """Partition intersecting public support without reading private references."""
    start, end = query['start_ms'], query['end_ms']
    tlo, thi = max(1, start // period), end // period
    scheduled = query['scheduled_sample_count']
    required = (target['hi'] - target['lo']) * scheduled
    volumes = [0] * 16
    estimated_terms, estimated_covered = [], 0
    for row in records:
        spatial = min(target['hi'], row['hi']) - max(target['lo'], row['lo'])
        temporal = min(thi, row['thi']) - max(tlo, row['tlo'])
        if spatial <= 0 or temporal <= 0:
            continue
        volume = spatial * temporal
        counts = row.setdefault('category_counts', {})
        category = query['category_id']
        if category not in counts:
            counts[category] = exact._category_count(row['bins'], category, catalog)
        count = counts[category]
        mask = 0
        if row['lo'] < target['lo'] or row['hi'] > target['hi']:
            mask |= SPATIAL_CROSSING
        if row['start'] < start or row['end'] > end:
            mask |= TEMPORAL_CROSSING
        if count is None:
            mask |= SEMANTIC_AMBIGUITY
        if row['sealed'] > query['deadline_ms']:
            mask |= LATE
        volumes[mask] += volume
        if estimate_enabled and count is not None and not mask & LATE:
            estimated_covered += volume
            # The denominator counts sampled slots, not milliseconds. In
            # particular [0,400) has three 100-ms samples, not four.
            estimated_terms.append(count * (spatial / (row['hi'] - row['lo'])) *
                                   (temporal / (row['thi'] - row['tlo'])))
    published = sum(volumes)
    if published > required:
        # Public overlap is already rejected by exact._public. This catches a
        # future indexing/partition regression rather than masking double count.
        raise ValueError('Public intersections exceed required query support')
    unpublished = required - published
    signature = UNPUBLISHED if unpublished else 0
    for mask, volume in enumerate(volumes):
        if volume:
            signature |= mask
    observed = query['deadline_observed']
    result = dict(required_leaf_samples=required,
        published_leaf_samples_at_eof=published,
        unpublished_leaf_samples_at_eof=unpublished,
        leaf_samples_by_mask={str(mask): volume for mask, volume in enumerate(volumes)},
        visible_leaf_samples_at_deadline=sum(volumes[:8]) if observed else None,
        exact_usable_leaf_samples_at_deadline=volumes[0] if observed else None,
        signature_mask=signature if observed and scheduled else None,
        no_scheduled_samples=not bool(scheduled), deadline_censored=not observed)
    if observed and scheduled and query['answered'] != (volumes[0] == required):
        raise ValueError('Support diagnostics disagree with the conservative exact decoder')
    estimate = None
    if estimate_enabled:
        answered = observed and scheduled > 0 and estimated_covered == required
        prediction = math.fsum(estimated_terms) if answered else None
        if prediction is not None and not math.isfinite(prediction):
            raise ValueError('Uniform estimate exceeds finite numeric range')
        if query['answered'] and (not answered or not math.isclose(
                prediction, query['prediction'], rel_tol=1e-12, abs_tol=1e-12)):
            raise ValueError('Uniform estimate must preserve every conservative exact answer')
        estimate = dict(answered=answered,
            estimated_observation_contributions=prediction,
            estimated_mean_sample_occupancy=prediction / scheduled if answered else None,
            covered_leaf_samples_at_deadline=estimated_covered if observed else None)
    return result, estimate


def _estimate_score(query, estimate):
    """Attach scores only after the public-only decoder has produced its answer."""
    scored = estimate['answered'] and query['reference_available']
    error = (abs(estimate['estimated_observation_contributions'] -
                 query['reference_observation_contributions']) if scored else None)
    estimate['absolute_error'] = error
    estimate['mean_sample_occupancy_absolute_error'] = (
        error / query['scheduled_sample_count'] if scored else None)


def _summary(queries, estimate_enabled):
    observed = [q for q in queries if q['deadline_observed']]
    supported = [q for q in observed if q['scheduled_sample_count'] > 0]
    signatures = {str(mask): 0 for mask in range(32)}
    volumes = {str(mask): 0 for mask in range(16)}
    for query in supported:
        support = query['recipient_support']
        signatures[str(support['signature_mask'])] += 1
        for mask, count in support['leaf_samples_by_mask'].items():
            volumes[mask] += count
    required = sum(q['recipient_support']['required_leaf_samples'] for q in supported)
    unpublished = sum(q['recipient_support']['unpublished_leaf_samples_at_eof'] for q in supported)
    result = dict(query_count=len(queries), observed_query_count=len(observed),
        censored_query_count=len(queries) - len(observed),
        no_scheduled_samples_query_count=len(observed) - len(supported),
        signature_query_count=len(supported), query_counts_by_signature_mask=signatures,
        required_leaf_samples=required, leaf_samples_by_mask=volumes,
        unpublished_leaf_samples_at_eof=unpublished,
        published_leaf_samples_at_eof=sum(volumes.values()),
        visible_leaf_samples_at_deadline=sum(volumes[str(mask)] for mask in range(8)),
        exact_usable_leaf_samples_at_deadline=volumes['0'])
    if sum(signatures.values()) != len(supported) or sum(volumes.values()) + unpublished != required:
        raise ValueError('Recipient support summaries do not partition their declared denominator')
    if estimate_enabled:
        answered = [q for q in observed if q['uniform_estimate']['answered']]
        scored = [q for q in answered if q['reference_available']]
        errors = math.fsum(q['uniform_estimate']['absolute_error'] for q in scored)
        occupancy_errors = math.fsum(q['uniform_estimate']['mean_sample_occupancy_absolute_error'] for q in scored)
        reference_count = sum(q['reference_available'] for q in observed)
        result['uniform_estimate'] = dict(
            receiver_answered_query_count=len(answered),
            receiver_estimated_only_answered_query_count=sum(not q['answered'] for q in answered),
            scored_estimated_only_answered_query_count=sum(not q['answered'] for q in scored),
            receiver_query_coverage=len(answered) / len(observed) if observed else None,
            reference_available_query_count=reference_count,
            answered_query_count=len(scored),
            query_coverage=len(scored) / reference_count if reference_count else None,
            absolute_error_sum=errors, answered_only_mae=errors / len(scored) if scored else None,
            mean_sample_occupancy_absolute_error_sum=occupancy_errors,
            answered_only_mean_sample_occupancy_mae=occupancy_errors / len(scored) if scored else None)
    return result


def _summaries(queries, categories, estimate_enabled):
    result = _summary(queries, estimate_enabled)
    result['by_category'] = {category: _summary([q for q in queries if q['category_id'] == category], estimate_enabled)
                             for category in categories}
    for name, positive in (('known_zero', False), ('positive', True)):
        result[name] = _summary([q for q in queries if q['reference_available'] and
                                (q['reference_observation_contributions'] > 0) == positive], estimate_enabled)
    return result


def evaluate(replay, config, releases, *, target_cells, categories, window_ms=400,
             lags_ms=(0, 400), max_queries=exact.MAX_QUERIES, uniform_estimate=False):
    """Preserve exact results and add a disjoint public-support diagnosis.

    Signature masks are a mutually exclusive partition of observed queries with
    scheduled samples; each mask is the union of its intersecting support flags,
    plus bit 16 for support without any public record through the source EOF.
    Empty or censored queries are counted separately. Volumes count leaf-sample
    positions and are repeated across category queries; they are not person counts.

    Optional uniform estimates assume even distribution over each whole public
    tile's leaves and scheduled samples. Full visible, semantically resolved
    coverage is mandatory. Missing support never becomes an estimated zero.
    """
    if not isinstance(uniform_estimate, bool):
        raise ValueError('uniform_estimate must be a boolean')
    evaluation = exact.evaluate(replay, config, releases, target_cells=target_cells,
        categories=categories, window_ms=window_ms, lags_ms=lags_ms, max_queries=max_queries)
    definition = evaluation['query_definition']
    catalog, grid = exact._catalog(config), exact._coverage(replay)
    period, horizon = definition['observation_sampling_period_ms'], definition['source_horizon_ms']
    records = exact._public(releases, grid, catalog, horizon, period)
    targets = [exact._geometry(row['cell_id'], row['depth'], grid) for row in definition['target_cells']]
    by_target = {row['cell_id']: row for row in targets}
    candidates = exact._candidate_index(records, targets, window_ms, period,
        definition['full_window_count'], len(definition['categories']), len(definition['lags_ms']))
    for value in evaluation['evaluations_by_lag_ms'].values():
        for query in value['queries']:
            rows = candidates.get((query['target_cell_id'], query['start_ms'] // window_ms), ())
            support, estimate = _partition(query, by_target[query['target_cell_id']], rows,
                                           catalog, period, uniform_estimate)
            query['recipient_support'] = support
            if uniform_estimate:
                _estimate_score(query, estimate)
                query['uniform_estimate'] = estimate
        value['recipient_support_summary'] = {cohort: _summaries(
            [q for q in value['queries'] if q['cohort'] == cohort],
            definition['categories'], uniform_estimate) for cohort in ('interior', 'boundary')}
    evaluation['schema'] = SCHEMA
    evaluation['recipient_contract'] = dict(exact_schema=exact.SCHEMA,
        exact_decoder='conservative whole-public-tile containment; not maximal transcript inference',
        support_unit='finest Morton leaf x scheduled sample; repeated for each category query',
        mask_bits=deepcopy(MASK_NAMES),
        signature='bitwise union over positive intersecting volumes, plus bit 16 for unpublished support; censored and unsampled queries separate',
        unpublished='no public record through EOF, not a claim of emptiness or a producer suppression cause',
        lateness='seal exceeds query deadline; every diagnosed release is observed by source EOF',
        uniform_estimate_enabled=uniform_estimate,
        uniform_estimate_rule=('public category count x intersected leaves / public leaves x '
            'intersected scheduled samples / public scheduled samples; full visible semantically '
            'resolved support required; no missing-zero or semantic imputation'))
    return evaluation


def compact(evaluation):
    """Keep only the unchanged query definition and aggregate diagnostic results."""
    if not isinstance(evaluation, dict) or evaluation.get('schema') != SCHEMA:
        raise ValueError('Expected a recipient support evaluation')
    return dict(schema=SCHEMA, query_definition=deepcopy(evaluation['query_definition']),
        recipient_contract=deepcopy(evaluation['recipient_contract']),
        evaluations_by_lag_ms={lag: dict(summary=deepcopy(value['summary']),
            recipient_support_summary=deepcopy(value['recipient_support_summary']))
            for lag, value in evaluation['evaluations_by_lag_ms'].items()})


def _estimated_pair(a, b):
    observed = [(left, right) for left, right in zip(a, b) if left['deadline_observed']]
    both = [(left, right) for left, right in observed
            if left['uniform_estimate']['answered'] and right['uniform_estimate']['answered']]
    scored = [(left, right) for left, right in both if left['reference_available']]
    ae = math.fsum(left['uniform_estimate']['absolute_error'] for left, _ in scored)
    be = math.fsum(right['uniform_estimate']['absolute_error'] for _, right in scored)
    ao = math.fsum(left['uniform_estimate']['mean_sample_occupancy_absolute_error'] for left, _ in scored)
    bo = math.fsum(right['uniform_estimate']['mean_sample_occupancy_absolute_error'] for _, right in scored)
    return dict(query_count=len(a), observed_query_count=len(observed),
        reference_available_query_count=sum(left['reference_available'] for left, _ in observed),
        both_answered_query_count=len(both),
        only_a_answered_query_count=sum(left['uniform_estimate']['answered'] and
            not right['uniform_estimate']['answered'] for left, right in observed),
        only_b_answered_query_count=sum(right['uniform_estimate']['answered'] and
            not left['uniform_estimate']['answered'] for left, right in observed),
        neither_answered_query_count=sum(not left['uniform_estimate']['answered'] and
            not right['uniform_estimate']['answered'] for left, right in observed),
        scored_intersection_query_count=len(scored),
        intersection_a_absolute_error_sum=ae, intersection_b_absolute_error_sum=be,
        intersection_a_mae=ae / len(scored) if scored else None,
        intersection_b_mae=be / len(scored) if scored else None,
        intersection_a_mean_sample_occupancy_absolute_error_sum=ao,
        intersection_b_mean_sample_occupancy_absolute_error_sum=bo,
        intersection_a_mean_sample_occupancy_mae=ao / len(scored) if scored else None,
        intersection_b_mean_sample_occupancy_mae=bo / len(scored) if scored else None)


def paired_summary(a, b):
    """Pair the exact and optional estimated decoders on identical query cohorts."""
    if any(not isinstance(value, dict) or value.get('schema') != SCHEMA for value in (a, b)):
        raise ValueError('Expected two recipient support evaluations')
    if a.get('recipient_contract') != b.get('recipient_contract'):
        raise ValueError('Paired evaluations require the same recipient contract and estimator mode')
    # The established exact pairing validates definitions, row identities,
    # reference availability/counts, and deadlines before either paired score.
    output = exact.paired_summary({**a, 'schema': exact.SCHEMA}, {**b, 'schema': exact.SCHEMA})
    output['schema'] = 'ump.recipient-support-paired.v1'
    output['recipient_contract'] = deepcopy(a['recipient_contract'])
    enabled = a['recipient_contract']['uniform_estimate_enabled']
    if enabled:
        for lag, value in output['evaluations_by_lag_ms'].items():
            aq = a['evaluations_by_lag_ms'][lag]['queries']
            bq = b['evaluations_by_lag_ms'][lag]['queries']
            for cohort, summary in value['summary'].items():
                ca = [q for q in aq if q['cohort'] == cohort]
                cb = [q for q in bq if q['cohort'] == cohort]
                pair = _estimated_pair(ca, cb)
                pair['a'] = _summary(ca, True)['uniform_estimate']
                pair['b'] = _summary(cb, True)['uniform_estimate']
                pair['by_category'] = {category: _estimated_pair(
                    [q for q in ca if q['category_id'] == category],
                    [q for q in cb if q['category_id'] == category])
                    for category in a['query_definition']['categories']}
                for name, positive in (('known_zero', False), ('positive', True)):
                    selector = lambda q: q['reference_available'] and (q['reference_observation_contributions'] > 0) == positive
                    pair[name] = _estimated_pair([q for q in ca if selector(q)], [q for q in cb if selector(q)])
                summary['uniform_estimate'] = pair
    return output
