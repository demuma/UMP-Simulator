"""Policy-only regional composition of independently audited filtered fixed runs.

Masks and source accounting stay private. The recipient channel remains the
unchanged semantic_privacy v2 schema and contains exactly native retained cells.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

import regional_public_transcript as old
import semantic_privacy
import semantic_suppression_audit as suppression
import static_regional_schedule as static

FAMILY_SCHEMA = 'ump.regional-selective-public-family.v1'
AUDIT_SCHEMA = 'ump.regional-selective-public-composition-audit.v1'
require, read, sha = static.require, static.read, static.sha
canonical_sha = old.canonical_sha


def plan_schedule(coverage, config, side):
    """Reuse the old geometry/time schedule without treating filtering as OFF."""
    projected = deepcopy(config)
    bounds = [projected['policy_tree']['root']]
    for region in projected.get('policy_regions', []):
        bounds.extend((region.get('requirements', {}), region.get('type_requirements', {})))
    for limits in bounds:
        if suppression.METRIC in limits:
            limits[suppression.METRIC] = {'max': 0}
    plan = static.plan_schedule(coverage, projected, side)
    # Suppression never participates in the old geometry/time-only choice.
    # Restore actual retained-population requirements in the declared plan.
    for cell in plan['cells'].values():
        cell['effective_requirements'], touched = suppression.effective(config, cell['geometry'])
        require(touched == cell['intersected_regions'], 'Regional policy scope changed')
    return plan


def _private_population(cell, rows, config, catalog, measured):
    """Check masks/counts even on failed or schedule-unowned native cells."""
    bounds, _ = suppression.effective(config, cell)
    audit = cell.get('semantic_suppression')
    cap = bounds.get(suppression.METRIC, {}).get('max', 0)
    require((audit is not None) == (cap > 0), 'Private suppression permission/audit differs')
    mask = [] if audit is None else audit.get('suppressed_terminal_categories')
    require(isinstance(mask, list) and mask == sorted(set(mask)) and set(mask) <= catalog.leaves,
            'Invalid private suppressed terminal mask')
    retained = [(t, r) for t, r in rows if catalog.labels[r['type']] not in mask]
    removed = [(t, r) for t, r in rows if catalog.labels[r['type']] in mask]
    require(retained, 'Private candidate has an empty retained population')
    require(bool(removed) == ('retained_counts' in cell), 'Private retained-count presence differs')
    counts = cell.get('retained_counts', cell)
    require(counts.get('observation_contributions') == len(retained)
            and counts.get('distinct_road_users') == len({r['id'] for _, r in retained})
            and suppression.close(counts.get('mean_sample_occupancy'), len(retained)/measured),
            'Private retained counts differ from source mask')
    semantic = cell['semantic']
    require(semantic.get('schema') == 'ump.semantic-release.v1'
            and (semantic.get('taxonomy_id'), semantic.get('taxonomy_version')) ==
                (catalog.taxonomy['id'], catalog.taxonomy['version']), 'Private semantic catalog differs')
    categories = semantic['categories']
    represented = set(); weighted = 0; supports = []
    for category in categories:
        identity = category['category_id']
        require(identity in catalog.nodes, 'Unknown private semantic category')
        matching = [(t, r) for t, r in retained if identity in catalog.chains[catalog.labels[r['type']]]]
        keys = {(t, r['id']) for t, r in matching}
        require(not keys & represented and matching, 'Private semantic category overlap/empty support')
        represented.update(keys)
        support = len({r['id'] for _, r in matching}); supports.append(support)
        require(category['observation_contributions'] == len(matching)
                and category['distinct_contributors'] == support, 'Private semantic support differs from retained source')
        weighted += len(matching)*catalog.nodes[identity]['loss']
    require(represented == {(t, r['id']) for t, r in retained}, 'Private semantic cut omits retained input')
    values = dict(min_category_distinct_contributors=min(supports), semantic_mean_loss=weighted/len(retained),
                  semantic_max_loss=max(catalog.nodes[c['category_id']]['loss'] for c in categories))
    require(all(suppression.close(cell['semantic'].get(k), v) for k, v in values.items()),
            'Private semantic summary differs')
    if audit is not None:
        expected = dict(input_observation_contributions=len(rows), input_distinct_contributors=len(catalog.source(rows)),
                        retained_observation_contributions=len(retained), retained_distinct_contributors=len({r['id'] for _, r in retained}),
                        suppressed_observation_contributions=len(removed), suppressed_distinct_contributors=len({r['id'] for _, r in removed}))
        require(audit.get('schema') == 'ump.semantic-suppression.v1'
                and all(type(audit.get(k)) is int and audit[k] == v for k, v in expected.items()),
                'Private suppression counts differ from original source mask')
        require(audit.get('suppressed_type_observation_contributions') == dict(Counter(r['type'] for _, r in removed)),
                'Private suppressed raw-type map differs')
        support = bounds['min_category_distinct_contributors']['min']
        ordinary = catalog.ordinary_loss(rows, support); full = (len(removed)+weighted)/len(rows)
        require(len(removed)/len(rows) <= cap
                and suppression.close(audit.get('suppressed_fraction'), len(removed)/len(rows))
                and suppression.close(audit.get('full_input_semantic_loss'), full)
                and suppression.close(audit.get('unsuppressed_semantic_loss'), ordinary),
                'Private suppression cap/loss metadata differs')
        if removed:
            require(full < ordinary-suppression.TOL, 'Private suppression has no strict full-input benefit')
            require(all(sum(catalog.labels[r['type']] == leaf for r in suppression.identities_to_rows(rows)) < support
                        for leaf in mask), 'Private mask removes a supported terminal')


def _records(data, config, plan, result, window, public):
    params = result.get('parameters', {})
    require(result.get('mode') == 'fixed' and params.get('fixed_depth') == plan['depth']
            and params.get('window_ms') == window and params.get('coordination') == 'common_window'
            and params.get('semantic_generalization') == 'enabled', 'Filtered fixed native parameters differ')
    require(all(result.get('source', {}).get(key) == data[key] for key in
                ('run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms')),
            'Native source identity/geometry/horizon differs')
    uniform = deepcopy(plan)
    for cell in uniform['cells'].values():
        cell['window_ms'] = window
    raw_groups, _, _ = static.groups_for(data, uniform)
    horizon = data['end_ms']
    expected = {(start, min(start + window, horizon)) for start in range(0, horizon, window)}
    intervals, seen, selected, owned = set(), set(), set(), {}
    catalog = suppression.Catalog(config); index = suppression.SourceIndex(data)
    for diagnostic in result['windows']:
        start, end = diagnostic['start_ms'], diagnostic['end_ms']
        interval = (start, end)
        require(interval in expected and interval not in intervals and 'coordination_cell' not in diagnostic,
                'Native global intervals are not an exact fixed partition')
        intervals.add(interval)
        require(type(diagnostic['evaluated_at_ms']) is int and end <= diagnostic['evaluated_at_ms'] <= horizon,
                'Invalid native fixed evaluation time')
        for cell in diagnostic['cells']:
            identity = cell['cell_id']; key = (identity, start, end)
            require(key in raw_groups and key not in seen and identity in plan['cells']
                    and cell['depth'] == plan['depth'], 'Duplicate, empty or wrong-grid native private cell')
            seen.add(key)
            rows = raw_groups[key]
            identities = catalog.source(rows)
            _, measured = index.samples(start, end)
            require(cell['observation_contributions'] == len(rows)
                    and cell['distinct_road_users'] == len(identities)
                    and suppression.close(cell['mean_sample_occupancy'], len(rows) / measured),
                    'Private raw cell counts differ from source')
            _private_population(cell, rows, config, catalog, measured)
            require(type(cell.get('selected')) is bool, 'Private selected flag is not Boolean')
            if cell['selected']:
                require(key in public, 'Selected private cell has no immutable public cell')
                released, release = public[key]
                require(all(suppression.close(cell.get(k), v) for k, v in plan['cells'][identity]['geometry'].items()),
                        'Private cell geometry differs from encoded cell')
                counts = cell.get('retained_counts', cell)
                require(all(counts.get(k) == released.get(k) for k in
                            ('observation_contributions', 'distinct_road_users', 'mean_sample_occupancy'))
                        and cell.get('semantic') == released.get('semantic')
                        and release['sealed_at_ms'] == diagnostic['evaluated_at_ms'],
                        'Private retained payload and immutable recipient payload differ')
                selected.add(key)
            else:
                require(key not in public, 'Failed native private cell was published')
            if plan['cells'][identity]['window_ms'] == window:
                owned[key] = dict(cell=cell, evaluated_at_ms=diagnostic['evaluated_at_ms'],
                                  sealed_at_ms=public[key][1]['sealed_at_ms'] if key in public else None)
    require(intervals == expected and seen == set(raw_groups), 'Native private source partition is incomplete')
    require(selected == set(public), 'Native public cell has no selected private record')
    return owned


def _stats(data, config, plan, records):
    groups, total, scheduled = static.groups_for(data, plan)
    require(set(records) == set(groups), 'Scheduled nonempty source group lacks its native private record')
    catalog = suppression.Catalog(config)
    kept_keys, selective_keys = set(), set()
    delays, categories, sizes = Counter(), Counter(), Counter()
    loss = side_sum = duration_sum = age_sum = 0.
    exact = published = failed = 0
    spatial = set()
    recomputations = []
    for key, rows in groups.items():
        identity, start, end = key
        record = records[key]; cell = record['cell']
        if not cell['selected']:
            failed += 1
            continue
        mask = cell.get('semantic_suppression', {}).get('suppressed_terminal_categories', [])
        retained = [(time, row) for time, row in rows if catalog.labels[row['type']] not in mask]
        removed = [(time, row) for time, row in rows if catalog.labels[row['type']] in mask]
        require(retained, 'Selected regional footprint has no retained source')
        bounds, touched = suppression.effective(config, plan['cells'][identity]['geometry'])
        require(bounds == plan['cells'][identity]['effective_requirements'], 'Scheduled policy requirements changed')
        losses = {}
        for category in cell['semantic']['categories']:
            matching = [(time, row) for time, row in retained
                        if category['category_id'] in catalog.chains[catalog.labels[row['type']]]]
            require(category['observation_contributions'] == len(matching)
                    and category['distinct_contributors'] == len({row['id'] for _, row in matching}),
                    'Composed semantic support differs from retained source')
            categories[category['category_id']] += len(matching)
            for time, row in matching:
                observation = (time, row['id'])
                require(observation not in losses, 'Composed semantic categories overlap')
                losses[observation] = catalog.nodes[category['category_id']]['loss']
        require(set(losses) == {(time, row['id']) for time, row in retained}, 'Retained class omitted from semantic cut')
        for time, row in retained:
            observation = (time, row['id'])
            require(observation not in kept_keys and observation not in selective_keys, 'Composed source support reused')
            kept_keys.add(observation)
            delay = record['sealed_at_ms'] - time
            require(delay >= 0, 'Composed release predates retained source')
            delays[delay] += 1
            loss += losses[observation]; exact += losses[observation] == 0
        for time, row in removed:
            observation = (time, row['id'])
            require(observation not in kept_keys and observation not in selective_keys, 'Composed suppressed support reused')
            selective_keys.add(observation)
        n = len(retained); published += 1; spatial.add(identity)
        width = plan['cells'][identity]['geometry']['width']; sizes[str(width)] += 1
        side_sum += n * width; duration_sum += n * (end - start)
        age_sum += n * (record['sealed_at_ms'] - start)
        recomputations.append(dict(cell_id=identity, start_ms=start, end_ms=end,
                                   retained_observations=n, selectively_suppressed_observations=len(removed),
                                   effective_requirements=bounds, intersected_regions=touched))
    accounting = suppression.source_accounting(data, config, kept_keys, selective_keys)
    kept = len(kept_keys)
    accounting['observation_to_release_delay_ms'] = static.delay_stats(delays)
    cohorts = deepcopy(accounting['by_region'])
    regions = {r['id']: r for r in config.get('policy_regions', [])}
    outside = Counter()
    for batch in data['batches']:
        for row in batch['observations']:
            touched = any(regions[i]['x'] <= row['x'] < regions[i]['x']+regions[i]['width']
                          and regions[i]['y'] <= row['y'] < regions[i]['y']+regions[i]['height']
                          for i in config['policy_tree']['regions'])
            if not touched:
                key = (batch['observed_at_ms'], row['id'])
                outside['input'] += 1
                outside['retained'] += key in kept_keys
                outside['selective'] += key in selective_keys
    n, k, removed = outside['input'], outside['retained'], outside['selective']
    cohorts['outside_policy_regions'] = dict(input_observations=n, retained_observations=k,
            selectively_suppressed_observations=removed, whole_footprint_suppressed_observations=n-k-removed,
            retained_fraction=k/n if n else None, selectively_suppressed_fraction=removed/n if n else None)
    accounting['by_source_point_region'] = cohorts
    require(total == accounting['input_observations'] and kept == sum(delays.values()), 'Composed source conservation differs')
    return dict(input_observation_contributions=total, retained_observation_contributions=kept,
                unpublished_observation_contributions=total-kept, retained_fraction=kept/total if total else None,
                full_input_semantic_distortion=(total-kept+loss)/total if total else None,
                observation_weighted_semantic_loss=loss/kept if kept else None,
                observation_weighted_cell_side_m=side_sum/kept if kept else None,
                observation_weighted_interval_duration_ms=duration_sum/kept if kept else None,
                observation_weighted_age_at_release_ms=age_sum/kept if kept else None,
                exact_subtype_observation_contributions=exact,
                exact_subtype_fraction_of_input=exact/total if total else None,
                exact_subtype_fraction_of_retained=exact/kept if kept else None,
                published_category_observations=dict(sorted(categories.items())), published_cell_sizes=dict(sorted(sizes.items())),
                published_cell_windows=published, unique_published_spatial_ids=len(spatial), core_processing_ms=None,
                source_accounting=accounting, regional_recomputations=recomputations,
                partition_audit=dict(status='verified', scheduled_cell_intervals=scheduled,
                                     nonempty_cell_intervals=len(groups), empty_cell_intervals=scheduled-len(groups),
                                     published_nonempty_cell_intervals=published, failed_nonempty_cell_intervals=failed,
                                     input_assigned_once=total), published_policy_violations=0)


def compose_family(root, manifest, *, availability_model='final_snapshot_at_horizon'):
    root = Path(root)
    require(not root.is_symlink(), 'Family root cannot be symbolic')
    root = root.resolve(strict=True); manifest = deepcopy(manifest)
    old._keys(manifest, ('schema', 'public_coverage', 'sampling_period_ms', 'end_ms', 'side_m',
                         'public_policy_id', 'method_alias', 'source', 'native_binary', 'cases'), 'family manifest')
    require(manifest['schema'] == FAMILY_SCHEMA and manifest['side_m'] == 20, 'Require declared selective 20 m family')
    require(availability_model == 'final_snapshot_at_horizon', 'Selective family requires declared final snapshot availability')
    public_id = old._alias(manifest['public_policy_id'], 'policy ID')
    old._alias(manifest['method_alias'], 'method alias')
    require(type(manifest['end_ms']) is int and manifest['end_ms'] > 0
            and type(manifest['sampling_period_ms']) is int and manifest['sampling_period_ms'] > 0,
            'Invalid declared public cadence/horizon')
    require(isinstance(manifest['cases'], dict) and set(manifest['cases']) == {str(w) for w in static.WINDOWS},
            'Require exactly four predeclared filtered fixed native cases')
    frozen = {}; source_path = old._receipt(root, manifest['source'], 'Source observations', frozen)
    old._receipt(root, manifest['native_binary'], 'Source native binary', frozen)
    configs = {}; paths = {}; canonical = None
    for window in static.WINDOWS:
        case = manifest['cases'][str(window)]
        old._keys(case, ('config', 'result', 'private_audit', 'independent_audit'), 'native case')
        receipt = case['independent_audit']
        old._keys(receipt, ('status', 'scalar_valid', 'published_policy_violations'), 'independent audit')
        require(receipt['status'] == 'verified' and receipt['scalar_valid'] is True
                and type(receipt['published_policy_violations']) is int and receipt['published_policy_violations'] == 0,
                'Native case lacks verified independent receipt')
        config = read(old._receipt(root, case['config'], 'Native configuration', frozen))
        require(config['policy_tree']['root'].get(suppression.METRIC) == {'max': .10}, 'Selective root cap must be exactly .10')
        require(canonical is None or static.hard_policy(config) == static.hard_policy(canonical),
                'Filtered native cases differ in hard policy/configuration')
        canonical = config; configs[window] = config
        paths[window] = (old._receipt(root, case['result'], 'Native result', frozen),
                         old._receipt(root, case['private_audit'], 'Native private audit', frozen))
    plan = plan_schedule(manifest['public_coverage'], canonical, manifest['side_m'])
    plan_sha = canonical_sha(plan)
    data = read(source_path)
    require(data.get('schema') == 'ump.observation-replay.v1'
            and data.get('coverage') == manifest['public_coverage']
            and all(data.get(k) == manifest[k] for k in ('sampling_period_ms', 'end_ms')),
            'Source differs from declared public header')
    for value in (data.get('run_id'), data.get('sensor_id')):
        require(not value or value not in public_id and value not in manifest['method_alias'], 'Public alias contains private source identity')
    records = {}; native_public = {}; results = {}
    for window in static.WINDOWS:
        result_path, audit_path = paths[window]
        result, saved = read(result_path), read(audit_path)
        native_public[window] = old._native_public(result, configs[window], plan, public_id, availability_model)
        audited = deepcopy(configs[window])
        audited['temporal_adaptation']['coordination'] = 'common_window'
        budget = suppression.audit_budget(saved.get('scalar', {}).get('scope', {}).get('max_cells'))
        checked = suppression.audit_suppression(data, audited, result, max_cells=budget)
        static.recursively_equal(checked, saved, 'independent_filtered_native_audit')
        require(checked['contribution_selection'] == 'policy_filtered', 'Native family is not independently audited filtered input')
        owned = _records(data, configs[window], plan, result, window, native_public[window])
        require(not set(owned) & set(records), 'Regional private scopes overlap')
        records.update(owned); results[window] = result
    stats = _stats(data, canonical, plan, records)
    grouped = defaultdict(list); selected_keys = set()
    for window in static.WINDOWS:
        for key, (cell, release) in native_public[window].items():
            if plan['cells'][key[0]]['window_ms'] != window:
                continue
            require(key in records and records[key]['cell']['selected'] and key not in selected_keys,
                    'Composed recipient scope is absent, failed or duplicated')
            selected_keys.add(key)
            group = (release['start_ms'], release['end_ms'], release['sealed_at_ms'],
                     release['model'], public_id, release['policy_version'])
            grouped[group].append(cell)
    releases = []
    for group, cells in sorted(grouped.items(), key=lambda item: (item[0][2], item[0][0], item[0][1], item[0][3:])):
        start, end, sealed, model, policy_id, version = group
        releases.append(dict(release_id='recipient-' + str(len(releases)), start_ms=start, end_ms=end,
                             sealed_at_ms=sealed, model=model, policy_id=policy_id, policy_version=version,
                             cells=sorted(cells, key=lambda cell: (cell['cell_id'], cell['depth']))))
    public = semantic_privacy.export_releases(coverage=manifest['public_coverage'],
                sampling_period_ms=manifest['sampling_period_ms'], end_ms=manifest['end_ms'], releases=releases,
                taxonomy=canonical['semantic_taxonomy'], availability_model=availability_model)
    require(sum(c['observation_contributions'] for r in public['releases'] for c in r['cells'])
            == stats['retained_observation_contributions'] and len(selected_keys) == stats['published_cell_windows'],
            'Composed recipient payload and retained source accounting differ')
    for path, digest in frozen.items():
        require(sha(path) == digest, 'Frozen artifact changed during composition')
    require(canonical_sha(plan) == plan_sha, 'Policy-only schedule changed')
    positive_control = set(plan['cell_window_ms'].values()) == {4000}
    if positive_control:
        reference = []
        for release in results[4000]['releases']:
            row = deepcopy(release); row['policy_id'] = public_id
            row['cells'] = [deepcopy(native_public[4000][(c['cell_id'], row['start_ms'], row['end_ms'])][0]) for c in row['cells']]
            reference.append(row)
        expected = semantic_privacy.export_releases(coverage=manifest['public_coverage'],
                    sampling_period_ms=manifest['sampling_period_ms'], end_ms=manifest['end_ms'], releases=reference,
                    taxonomy=canonical['semantic_taxonomy'], availability_model=availability_model)
        require(public == expected, 'Uniform 4s control differs from filtered native transcript')
    audit = dict(schema=AUDIT_SCHEMA, status='verified', family_manifest_sha256=canonical_sha(manifest),
                 source_artifacts=manifest, policy_only_schedule_sha256=plan_sha, cell_window_ms=plan['cell_window_ms'],
                 method_alias=manifest['method_alias'], stats=stats, source_accounting=stats['source_accounting'],
                 contribution_selection='policy_filtered', positive_control_equal_native_4s=positive_control,
                 native_runtime=None, native_process_wall_seconds=None, availability_model=availability_model,
                 public_transcript_sha256=canonical_sha(public),
                 scope='All four full native families independently reaudited against original observations; only policy-scheduled native retained cells composed. Masks remain private; no optimality or privacy proof.',
                 utility_timing_scope='Native logical sealing delays on retained original observations only; recipient availability is the declared horizon.')
    return dict(public_transcript=public, private_audit=audit)
