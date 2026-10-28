"""Retained-population utility and original-source proxies for filtered releases.

Public predictions use released bins only. Original observations provide private
reference errors and audited input denominators, never missing recipient counts.
The existing suppression-OFF evaluators and workloads are unchanged.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import math

import urban_privacy_queries as occupancy_queries
import urban_semantic_ablation_queries as aligned

SCHEMA = 'ump.urban-selective-suppression-utility.v1'
QUERY_SCHEMA = 'ump.urban-selective-suppression-queries.v1'
FILTERED_REASON = 'filtered_population'
_DELAY_FIELDS = ('mean', 'p50', 'p95', 'p99', 'maximum')
_COUNT_FIELDS = ('input_observations', 'retained_observations',
                 'selectively_suppressed_observations',
                 'whole_footprint_suppressed_observations')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, name, minimum=0, maximum=None):
    _require(type(value) in (int, float) and math.isfinite(value)
             and value >= minimum and (maximum is None or value <= maximum),
             'Invalid ' + name)
    return value


def _close(actual, expected):
    return (type(actual) in (int, float) and math.isfinite(actual)
            and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12))


def _fraction(actual, numerator, denominator, name):
    _require(actual is None if not denominator else _close(actual, numerator / denominator),
             name + ' accounting fraction differs')


def _cohort(value, name):
    _require(isinstance(value, dict), name + ' accounting missing')
    for key in _COUNT_FIELDS:
        _require(type(value.get(key)) is int and value[key] >= 0,
                 name + ' invalid ' + key)
    total, kept, selected, whole = (value[key] for key in _COUNT_FIELDS)
    _require(kept + selected + whole == total, name + ' contribution conservation differs')
    _fraction(value.get('retained_fraction'), kept, total, name + ' retained')
    _fraction(value.get('selectively_suppressed_fraction'), selected, total, name + ' selective')


def _validate_accounting(data, config, audit, retained):
    _require(audit.get('status') == 'verified', 'Verified independent audit required')
    if 'scalar' in audit:
        _require(audit['scalar'].get('valid') is True, 'Independent raw ownership audit failed')
    _require(audit.get('published_policy_violations', 0) == 0,
             'Independent audit reports publication policy violations')
    _require(audit.get('contribution_selection', 'policy_filtered') == 'policy_filtered',
             'Expected policy-filtered audit')
    value = audit.get('source_accounting', audit.get('stats', {}).get('source_accounting'))
    _cohort(value, 'Full input')
    expected_types = Counter()
    regions = {r['id']: r for r in config.get('policy_regions', [])}
    selected_regions = config['policy_tree']['regions']
    _require(len(selected_regions) == len(set(selected_regions))
             and all(identity in regions for identity in selected_regions), 'Invalid policy regions')
    expected_regions = Counter({identity: 0 for identity in selected_regions})
    for batch in data['batches']:
        for row in batch['observations']:
            expected_types[row['type']] += 1
            if 'x' in row and 'y' in row:
                for identity in selected_regions:
                    region = regions[identity]
                    if (region['x'] <= row['x'] < region['x'] + region['width']
                            and region['y'] <= row['y'] < region['y'] + region['height']):
                        expected_regions[identity] += 1
    total = sum(expected_types.values())
    _require(value['input_observations'] == total and value['retained_observations'] == retained,
             'Source/public retained total accounting differs')
    if 'selectively_suppressed_observations' in audit:
        _require(audit['selectively_suppressed_observations'] == value['selectively_suppressed_observations'],
                 'Selective audit total differs')
    cohorts = value.get('by_source_type')
    _require(isinstance(cohorts, dict) and set(cohorts) == set(expected_types),
             'Original source type accounting differs')
    for kind, count in expected_types.items():
        _cohort(cohorts[kind], 'Source type ' + kind)
        _require(cohorts[kind]['input_observations'] == count, 'Source type denominator differs')
    for key in _COUNT_FIELDS:
        _require(sum(cohort[key] for cohort in cohorts.values()) == value[key],
                 'Source type total accounting differs: ' + key)
    cohorts = value.get('by_region')
    _require(isinstance(cohorts, dict) and set(cohorts) == set(expected_regions),
             'Original-position region accounting differs')
    for identity, count in expected_regions.items():
        _cohort(cohorts[identity], 'Region ' + identity)
        _require(cohorts[identity]['input_observations'] == count, 'Region denominator differs')
    delays = value.get('observation_to_release_delay_ms')
    _require(isinstance(delays, dict) and all(key in delays for key in _DELAY_FIELDS),
             'Retained-observation delay accounting missing')
    if not retained:
        _require(all(delays[key] is None for key in _DELAY_FIELDS),
                 'Empty retained population has delay values')
    else:
        for key in _DELAY_FIELDS:
            _number(delays[key], 'retained delay ' + key, maximum=data['end_ms'])
        _require(delays['p50'] <= delays['p95'] <= delays['p99'] <= delays['maximum']
                 and delays['mean'] <= delays['maximum'], 'Retained delay ordering differs')
    return deepcopy(value)


def _blank_proxy():
    return dict(aligned._blank(), signed_error_sum=0., public_prediction_sum=0.,
                reference_sum_on_scored_queries=0.)


def _add_proxy(summary, truth, answered, prediction, reasons):
    aligned._add(summary, truth, answered, prediction, reasons)
    if answered:
        summary['public_prediction_sum'] += prediction
        if truth is not None:
            summary['reference_sum_on_scored_queries'] += truth
            summary['signed_error_sum'] += prediction - truth


def _finish_proxy(summary):
    aligned._finish(summary)
    scored = summary['scored_query_count']
    summary['answered_only_bias'] = summary['signed_error_sum'] / scored if scored else None
    summary['prediction_contract'] = 'original-source proxy from identifiable retained public counts'
    return summary


def _unavailable_exact(proxy):
    def unavailable(summary):
        result = aligned._blank()
        for key in ('query_count', 'reference_available_query_count',
                    'reference_unavailable_query_count', 'known_zero_reference_query_count',
                    'positive_reference_query_count'):
            result[key] = summary[key]
        result['unknown_reasons'][FILTERED_REASON] = result['query_count']
        aligned._finish(result)
        result.update(status='unavailable', reason=FILTERED_REASON,
                      original_source_exact_available=False)
        return result
    return dict(status='unavailable', reason=FILTERED_REASON,
                summary=unavailable(proxy['summary']),
                by_category={key: unavailable(value) for key, value in proxy['by_category'].items()})


def evaluate_filtered_queries(data, public, config, *, reference=None):
    """Evaluate the frozen aligned count workload as original-source proxies.

    No original-source count is certified exact, even when geometry aligns or an
    absent retained category decodes to zero. An ancestor bin still makes its
    ambiguous descendant unknown. Missing public support stays unknown. Private
    source counts enter errors and reference-availability diagnostics only.
    No per-query list is materialized, keeping concurrent worker memory bounded.
    """
    prepared = aligned.prepare_reference(data, config) if reference is None else reference
    _require(prepared.get('schema') == aligned.REFERENCE_SCHEMA
             and prepared.get('source_object_identity') == id(data),
             'Expected a prepared aligned-query reference for this source object')
    definition = prepared['definition']
    _require(definition['cell_side_m'] == 20 and definition['window_ms'] == 400
             and definition['source_horizon_ms'] == data.get('end_ms')
             and definition['sampling_period_ms'] == data.get('sampling_period_ms')
             and prepared['grid'] == aligned.scoped._coverage(data),
             'Cached reference does not match filtered query/source headers')
    taxonomy_config = config if 'semantic_taxonomy' in config else {'semantic_taxonomy': config}
    catalog = prepared['catalog']
    _require(aligned._digest(aligned.scoped._catalog(taxonomy_config)['declaration'])
             == definition['taxonomy_sha256'], 'Cached reference taxonomy changed')
    _require(isinstance(public, dict) and isinstance(public.get('releases'), list),
             'Expected a public recipient release object')
    period, horizon, window = (definition[key] for key in
                               ('sampling_period_ms', 'source_horizon_ms', 'window_ms'))
    records = aligned.scoped._public(public['releases'], prepared['grid'], catalog, horizon, period)
    candidates = defaultdict(list)
    for row in records:
        for target in prepared['targets']:
            overlap_space = min(row['hi'], target['hi']) - max(row['lo'], target['lo'])
            if overlap_space <= 0:
                continue
            for index in range(max(0, row['start'] // window),
                               min(definition['full_window_count'], (row['end'] - 1) // window + 1)):
                start, end = index * window, (index + 1) * window
                tlo, thi = max(1, start // period), end // period
                overlap_time = min(row['thi'], thi) - max(row['tlo'], tlo)
                if overlap_time > 0:
                    candidates[index, target['cell_id']].append((row, overlap_space * overlap_time))
    proxy = dict(status='proxy_estimate', summary=_blank_proxy(),
                 by_category={category: _blank_proxy() for category in definition['categories']})
    count_cache = {}
    for index in range(definition['full_window_count']):
        start, end = index * window, (index + 1) * window
        scheduled = end // period - max(1, start // period)
        available = scheduled > 0 and prepared['measured'][index] == scheduled
        for target in prepared['targets']:
            required = (target['hi'] - target['lo']) * scheduled
            raw = prepared['counts'].get((index, target['cell_id']), {})
            rows = candidates.get((index, target['cell_id']), ())
            for category in definition['categories']:
                truth = (sum(n for node, n in raw.items() if node in catalog['domains'][category])
                         if available else None)
                volume, prediction, reasons = 0, 0., set()
                for row, overlap in rows:
                    key = (id(row), category)
                    if key not in count_cache:
                        count_cache[key] = aligned.scoped._category_count(row['bins'], category, catalog)
                    count = count_cache[key]
                    if count is None:
                        reasons.add('semantic_generalization')
                        continue
                    volume += overlap
                    prediction += count * overlap / ((row['hi'] - row['lo']) * (row['thi'] - row['tlo']))
                answered = scheduled > 0 and volume == required
                if not scheduled:
                    reasons.add('no_scheduled_samples')
                if volume < required:
                    reasons.add('missing_public_support')
                prediction = prediction if answered else None
                _add_proxy(proxy['summary'], truth, answered, prediction, reasons)
                _add_proxy(proxy['by_category'][category], truth, answered, prediction, reasons)
    _finish_proxy(proxy['summary'])
    for summary in proxy['by_category'].values():
        _finish_proxy(summary)
    output_definition = deepcopy(definition)
    output_definition.update(schema=QUERY_SCHEMA,
        exact_rule='unavailable for original input because public counts describe a filtered population',
        estimate_rule='uniform sampled-space/time allocation of identifiable retained public category counts as original-source proxies; semantic ambiguity remains unknown')
    return dict(schema=QUERY_SCHEMA, query_definition=output_definition,
        count_contract='retained observation contributions; original-source counts are proxy estimates only',
        zero_prediction_rule='zero retained identifiable contributions never certifies an original-source zero',
        reference_scope='Original source is private evaluation truth only; reference zeros are not recipient certificates.',
        original_source_exact=_unavailable_exact(proxy), source_proxy_estimate=proxy,
        decode_diagnostics=dict(public_tiles=len(records),
            candidate_intersections=sum(len(rows) for rows in candidates.values()),
            query_count=definition['query_count']))


def _occupancy_proxies(data, public):
    # Preserve the legacy 10 m / 1 s root-occupancy workload under its old keys.
    evaluated = occupancy_queries.evaluate(data, public, include_queries=True)
    proxy = deepcopy(evaluated['estimate']['summary'])
    rows = evaluated['estimate']['queries']
    scored = [row for row in rows if row['absolute_error'] is not None]
    signed_error = math.fsum(row['prediction'] - row['reference'] for row in scored)
    proxy.update(status='proxy_estimate', signed_error_sum=signed_error,
                 occupancy_bias=signed_error / len(scored) if scored else None,
                 prediction_contract='original-source proxy from retained public occupancy')
    exact = deepcopy(evaluated['exact']['summary'])
    exact.update(status='unavailable', reason=FILTERED_REASON,
        original_source_exact_available=False, answered_queries=0, scored_queries=0,
        answered_query_coverage=0. if exact['reference_queries'] else None,
        scored_query_coverage=0. if exact['reference_queries'] else None,
        absolute_error_sum=0., occupancy_mae=None)
    return exact, proxy


def utility(data, public, config, audit, result=None, *, query_reference=None, include_queries=True):
    """Return audited full-input utility with truthful filtered count contracts.

    Delay summaries come from the retained-source audit, including only actual
    retained observations. Recounting every raw observation in released geometry
    would incorrectly include selectively omitted contributions.
    """
    _require(isinstance(audit, dict), 'Independent audit must be an object')
    cap = config['policy_tree']['root'].get('semantic_suppression_fraction', {}).get('max', 0)
    _number(cap, 'selective suppression root cap', maximum=1)
    _require(cap > 0, 'Filtered utility requires positive suppression permission')
    _require(type(include_queries) is bool, 'include_queries must be a boolean')
    if include_queries:
        application = evaluate_filtered_queries(data, public, config, reference=query_reference)
    else:
        # Auxiliary fixed-window dependencies are not query-workload arms.
        catalog = aligned.scoped._catalog(config)
        aligned.scoped._public(public['releases'], aligned.scoped._coverage(data), catalog,
                               data['end_ms'], data['sampling_period_ms'])
        application = None
    cells = [(release, cell) for release in public['releases'] for cell in release['cells']]
    kept = sum(cell['observation_contributions'] for _, cell in cells)
    loss = math.fsum(cell['observation_contributions'] * cell['semantic']['semantic_mean_loss']
                     for _, cell in cells)
    accounting = _validate_accounting(data, config, audit, kept)
    total = accounting['input_observations']
    selected = accounting['selectively_suppressed_observations']
    whole = accounting['whole_footprint_suppressed_observations']
    _require(not selected or selected <= cap * (kept + selected) + 1e-12,
             'Global selective count is incompatible with the per-cell cap')
    if 'semantic_published_cells' in audit:
        _require(audit['semantic_published_cells'] == len(cells), 'Audited published cell count differs')
    if result is not None:
        _require(result.get('input_observation_contributions') == total
                 and result.get('accounted_observation_contributions') == total,
                 'Native full-input retirement accounting differs')
    processing = result.get('runtime', {}).get('processing_ms') if result is not None else None
    if processing is not None:
        _number(processing, 'core processing time')

    def mean(function):
        return (math.fsum(cell['observation_contributions'] * function(release, cell)
                         for release, cell in cells) / kept if kept else None)

    full_loss = (total - kept + loss) / total if total else None
    value = dict(schema=SCHEMA, input_observations=total, retained_observations=kept,
        retained_fraction=kept / total if total else None,
        full_input_J=full_loss, full_input_semantic_loss=full_loss,
        full_input_loss_definition='J=(N_input-N_retained+sum_retained taxonomy_loss)/N_input; unit omission penalty is a utility convention, not a privacy metric.',
        retained_semantic_loss=loss / kept if kept else None,
        mean_retained_cell_side_m=mean(lambda release, cell: cell['width']),
        mean_retained_interval_ms=mean(lambda release, cell: release['end_ms'] - release['start_ms']),
        logical_seal_delay_ms=deepcopy(accounting['observation_to_release_delay_ms']),
        published_cells=len(cells), core_processing_ms=processing, published_policy_violations=0,
        source_accounting=accounting, contribution_selection='policy_filtered',
        selectively_suppressed_observations=selected, whole_footprint_suppressed_observations=whole,
        selectively_suppressed_fraction_of_input=selected / total if total else None,
        whole_footprint_suppressed_fraction_of_input=whole / total if total else None,
        selective_suppression_root_cap=cap,
        selective_suppression_cap_scope='Each original cell-window observation multiset, with the strictest intersected regional cap; not a distinct-person or whole-run allowance.',
        original_gt_exact_queries='unavailable: filtered_population',
        query_workload_status='evaluated' if include_queries else 'excluded_auxiliary_dependency',
        runtime_scope='Native operational diagnostic; regional runtime unavailable; logical delay is not wall-clock delivery.')
    if include_queries:
        exact, estimate = _occupancy_proxies(data, public)
        value.update(query_exact=exact, query_estimate=estimate,
            query_contract='Legacy 10 m / 1 s root occupancy: original-source exact answers unavailable; estimates use retained public occupancy as a proxy.',
            aligned_semantic_queries=dict(exact=application['original_source_exact'],
                                          estimate=application['source_proxy_estimate']),
            aligned_query_definition=application['query_definition'])
    return value
