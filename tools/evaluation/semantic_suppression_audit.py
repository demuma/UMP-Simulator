"""Independent retained-population and full-input selective-suppression audit.

Private masks are checked against original observations, never trusted as counts.
The existing scalar oracle validates RAW ownership/coverage/retirement on an
explicit projection. All recipient constraints are separately recomputed on the
actual retained population here. No original-source exact-query claim follows.
"""
from bisect import bisect_left
from collections import Counter
from copy import deepcopy
import math

from oracle import decode_cell, validate_result
from run_semantic_priority_study import scalar_projection

METRIC = 'semantic_suppression_fraction'
TOL = 1e-12
MAX_OFFLINE_AUDIT_CELLS = 1_000_000


def audit_budget(value, default=200000):
    value = default if value is None else value
    require(type(value) is int and 1 <= value <= MAX_OFFLINE_AUDIT_CELLS,
            'Offline audit max_cells must be an integer from 1 to 1000000')
    return value


def close(a, b):
    return (isinstance(a, (int, float)) and not isinstance(a, bool)
            and math.isfinite(a) and math.isclose(a, b, abs_tol=TOL, rel_tol=TOL))


def require(value, message):
    if not value:
        raise ValueError(message)


def suppression_configured(config):
    groups = [config['policy_tree']['root']]
    for region in config.get('policy_regions', []):
        groups += [region.get('type_requirements', {}), region.get('requirements', {})]
    return any(METRIC in group for group in groups)


def may_filter(config):
    return config['policy_tree']['root'].get(METRIC, {}).get('max', 0) > 0


def intersects(a, b):
    return (a['x'] < b['x'] + b['width'] and b['x'] < a['x'] + a['width']
            and a['y'] < b['y'] + b['height'] and b['y'] < a['y'] + a['height'])


def effective(config, geometry):
    bounds = deepcopy(config['policy_tree']['root'])
    regions = {region['id']: region for region in config.get('policy_regions', [])}
    selected = config['policy_tree']['regions']
    require(len(selected) == len(set(selected)) and all(r in regions for r in selected), 'Invalid selected policy regions')
    if METRIC not in bounds and any(METRIC in region.get(kind, {}) for identity in selected
            for region in [regions[identity]] for kind in ('type_requirements', 'requirements')):
        bounds[METRIC] = {'max': 0}
    touched = []
    for identity in selected:
        region = regions[identity]
        if not intersects(geometry, region):
            continue
        touched.append(identity)
        for group in (region.get('type_requirements', {}), region.get('requirements', {})):
            for metric, extra in group.items():
                target = bounds.setdefault(metric, {})
                if 'min' in extra:
                    target['min'] = max(target.get('min', -math.inf), extra['min'])
                if 'max' in extra:
                    target['max'] = min(target.get('max', math.inf), extra['max'])
    if METRIC in bounds:
        limits = bounds[METRIC]
        require(set(limits) == {'max'} and type(limits['max']) in (int,float)
                and math.isfinite(limits['max']) and 0 <= limits['max'] <= 1, 'Invalid suppression policy cap')
    return bounds, touched


class SourceIndex:
    def __init__(self, data):
        self.data = data
        self.depth = data['coverage']['leaf_depth']
        self.times = [b['observed_at_ms'] for b in data['batches']]

    def rows(self, start, end, cell):
        shift = 2 * (self.depth - cell['depth'])
        return [(b['observed_at_ms'], row)
                for b in self.data['batches'][bisect_left(self.times, start):bisect_left(self.times, end)]
                for row in b['observations'] if row['cell_id'] >> shift == cell['cell_id']]

    def samples(self, start, end):
        period = self.data['sampling_period_ms']
        expected = len(range(max(period, ((start + period - 1) // period) * period), end, period))
        batches = self.data['batches'][bisect_left(self.times, start):bisect_left(self.times, end)]
        measured = sum(b['status'] == 'measured' for b in batches)
        return expected, measured


class Catalog:
    def __init__(self, config):
        self.taxonomy = config['semantic_taxonomy']
        self.nodes = {n['id']: n for n in self.taxonomy['nodes']}
        require(0 < len(self.nodes) <= 256 and len(self.nodes) == len(self.taxonomy['nodes']), 'Invalid bounded taxonomy')
        self.labels = {label: n['id'] for n in self.nodes.values() for label in n.get('input_types', [])}
        require(len(self.labels) == sum(len(n.get('input_types', [])) for n in self.nodes.values()) <= 4096,
                'Ambiguous or unbounded taxonomy labels')
        require(all(type(n.get('loss')) in (int,float) and math.isfinite(n['loss']) and 0 <= n['loss'] <= 1
                    for n in self.nodes.values()), 'Invalid taxonomy loss')
        self.children = {identity: [] for identity in self.nodes}
        roots = []
        for identity, n in self.nodes.items():
            if n.get('parent'):
                require(n['parent'] in self.nodes, 'Unknown taxonomy parent')
                self.children[n['parent']].append(identity)
            else:
                roots.append(identity)
        require(len(roots) == 1, 'Invalid taxonomy root')
        self.root = roots[0]
        self.chains = {}
        for identity in self.nodes:
            at, chain = identity, []
            while at:
                require(at not in chain and len(chain) <= 32, 'Taxonomy cycle/depth')
                chain.append(at)
                at = self.nodes[at].get('parent')
            require(self.root in chain, 'Disconnected taxonomy')
            self.chains[identity] = chain
        self.leaves = {identity for identity in self.nodes if not self.children[identity]}
        require(self.nodes[self.root]['loss'] == 1, 'Root loss must be one')
        for identity,n in self.nodes.items():
            if identity in self.leaves:
                require(n['loss'] == 0 and n.get('input_types'), 'Invalid terminal classification domain')
            else:
                require(not n.get('input_types'), 'Nonterminal raw label')
            if n.get('parent'):
                require(n['loss'] <= self.nodes[n['parent']]['loss'], 'Ancestor loss decreases')

    def source(self, rows):
        identities = {}
        for _, row in rows:
            require(row['type'] in self.labels, 'Unmapped original type')
            leaf = self.labels[row['type']]
            require(row['id'] not in identities or identities[row['id']] == leaf, 'Identity changed terminal within one candidate')
            identities[row['id']] = leaf
        return identities

    def ordinary_loss(self, rows, support):
        def visit(identity):
            matching = [(t, r) for t, r in rows if identity in self.chains[self.labels[r['type']]]]
            if not matching:
                return True, []
            if self.children[identity]:
                children = [visit(child) for child in self.children[identity]]
                if all(passes for passes, _ in children):
                    return True, [item for _, cut in children for item in cut]
            if len({r['id'] for _, r in matching}) >= support:
                return True, [(identity, len(matching))]
            return False, []
        passes, bins = visit(self.root)
        if not passes:
            bins = [(self.root, len(rows))]
        return sum(self.nodes[c]['loss'] * n for c, n in bins) / len(rows) if rows else 0


def _scope_key(record):
    scope = record.get('coordination_cell')
    return record['start_ms'], record['end_ms'], None if scope is None else (scope['cell_id'], scope['depth'])


def _raw_projection(data, config, actual, index, *, max_cells=200000):
    """Counterfactual raw support ONLY for the established retirement oracle."""
    max_cells = audit_budget(max_cells)
    cfg, projected = scalar_projection(config, actual)
    cfg['policy_tree']['execution']['strategy'] = 'temporal_first'
    projected['mode'] = 'temporal_first'
    groups = [cfg['policy_tree']['root']]
    for region in cfg.get('policy_regions', []):
        groups += [region.get('type_requirements', {}), region.get('requirements', {})]
    # These requirements are assessed independently on retained input below.
    # They cannot also be applied to this deliberately restored RAW projection.
    for bounds in groups:
        for metric in ('observation_contributions', 'distinct_contributors', 'mean_sample_occupancy'):
            bounds.pop(metric, None)
    cfg['policy_tree']['root'].setdefault('cell_side_m', {'min': 0})
    for window in projected['windows']:
        window['strategy'] = 'temporal_first'
        for cell in window['cells']:
            metrics = cell.get('metrics', {})
            for metric, field in (('observation_contributions', 'observation_contributions'),
                    ('distinct_contributors', 'distinct_road_users'), ('mean_sample_occupancy', 'mean_sample_occupancy')):
                if metric in metrics:
                    metrics[metric] = cell[field]
    for release in projected['releases']:
        _, measured = index.samples(release['start_ms'], release['end_ms'])
        for cell in release['cells']:
            raw = index.rows(release['start_ms'], release['end_ms'], cell)
            cell['observation_contributions'] = len(raw)
            cell['distinct_road_users'] = len({r['id'] for _, r in raw})
            cell['mean_sample_occupancy'] = len(raw) / measured if measured else None
    checked = validate_result(data, cfg, projected, max_cells=max_cells)
    require(checked['valid'], 'Independent raw ownership/retirement audit failed: ' + repr(checked['violations'][:4]))
    checked['scope']['projection'] = 'Original RAW counts restored solely for geometry, sample coverage and full-interval retirement; recipient counts and ALL hard bounds independently checked on retained population.'
    return checked


def audit_suppression(data, config, actual, *, max_cells=200000):
    index, catalog = SourceIndex(data), Catalog(config)
    scalar = _raw_projection(data, config, actual, index, max_cells=max_cells)
    selected = {}
    for window in actual['windows']:
        for cell in window['cells']:
            if cell['selected']:
                key = (_scope_key(window), cell['cell_id'])
                require(key not in selected, 'Duplicate selected cell-window')
                selected[key] = cell
    retained_keys, suppressed_keys = set(), set()
    records, groups = [], Counter()
    total_bins = selective_lost = candidate_checks = 0
    delays = Counter()
    for release in actual['releases']:
        expected, measured = index.samples(release['start_ms'], release['end_ms'])
        for cell in release['cells']:
            key = (_scope_key(release), cell['cell_id'])
            require(key in selected, 'Release has no matching private selected cell-window')
            diagnostic = selected.pop(key)
            geometry = decode_cell(data['coverage'], cell['cell_id'], cell['depth'])
            require(all(close(cell[k], v) for k, v in geometry.items()), 'Geometry disagrees with cell ID')
            raw = index.rows(release['start_ms'], release['end_ms'], cell)
            identities = catalog.source(raw)
            bounds, touched = effective(config, geometry)
            cap = bounds.get(METRIC, {}).get('max', 0)
            support = bounds['min_category_distinct_contributors']['min']
            audit = diagnostic.get('semantic_suppression')
            removed_leaves = [] if audit is None else audit['suppressed_terminal_categories']
            require(isinstance(removed_leaves, list) and len(removed_leaves) == len(set(removed_leaves))
                    and removed_leaves == sorted(removed_leaves) and set(removed_leaves) <= catalog.leaves,
                    'Invalid suppressed terminal mask')
            require(not audit or cap > 0, 'Suppression audit without policy permission')
            require(cap <= 0 or audit is not None, 'Enabled suppression has no private audit')
            retained = [(t, r) for t, r in raw if catalog.labels[r['type']] not in removed_leaves]
            removed = [(t, r) for t, r in raw if catalog.labels[r['type']] in removed_leaves]
            require(retained, 'Empty selected population')
            fraction = len(removed) / len(raw)
            require(fraction <= cap, 'Suppression exceeds strict regional fraction cap')
            retained_ids = {r['id'] for _, r in retained}
            require(len(retained) == cell['observation_contributions'] and len(retained_ids) == cell['distinct_road_users'],
                    'Retained observation/identity count mismatch')
            require(close(cell['mean_sample_occupancy'], len(retained) / measured), 'Retained occupancy mismatch')
            semantic = cell['semantic']
            require(diagnostic.get('semantic') == semantic, 'Private and immutable recipient semantic payload differ')
            require(semantic.get('schema') == 'ump.semantic-release.v1'
                    and (semantic['taxonomy_id'], semantic['taxonomy_version']) ==
                    (catalog.taxonomy['id'], catalog.taxonomy['version']), 'Wrong semantic release schema/catalog')
            categories = [item['category_id'] for item in semantic['categories']]
            require(categories and len(categories) == len(set(categories)) and all(c in catalog.nodes for c in categories),
                    'Invalid semantic categories')
            require(not any(a != b and a in catalog.chains[b] for a in categories for b in categories), 'Semantic antichain overlaps')
            require(all(sum(c in catalog.chains[catalog.labels[r['type']]] for c in categories) == 1 for _, r in retained),
                    'Retained class omitted or represented twice')
            supports, weighted = [], 0
            for item in semantic['categories']:
                matching = [(t, r) for t, r in retained if item['category_id'] in catalog.chains[catalog.labels[r['type']]]]
                n = len({r['id'] for _, r in matching})
                require(item['observation_contributions'] == len(matching) and item['distinct_contributors'] == n and n > 0,
                        'Semantic retained observation/identity count mismatch')
                supports.append(n)
                weighted += len(matching) * catalog.nodes[item['category_id']]['loss']
            values = {'observation_contributions': len(retained), 'distinct_contributors': len(retained_ids),
                'mean_sample_occupancy': len(retained) / measured, 'cell_side_m': cell['width'],
                'cell_area_m2': cell['width'] * cell['height'],
                'window_duration_ms': release['end_ms'] - release['start_ms'],
                'age_at_evaluation_ms': release['sealed_at_ms'] - release['start_ms'],
                'post_window_delay_ms': release['sealed_at_ms'] - release['end_ms'],
                'measured_sample_fraction': measured / expected,
                'min_category_distinct_contributors': min(supports),
                'semantic_max_loss': max(catalog.nodes[c]['loss'] for c in categories),
                'semantic_mean_loss': weighted / len(retained), METRIC: fraction}
            for metric in ('min_category_distinct_contributors', 'semantic_max_loss', 'semantic_mean_loss'):
                require(close(semantic[metric], values[metric]), 'Incorrect retained semantic summary')
            for metric, limits in bounds.items():
                require(metric in values, 'Unsupported independent retained metric: ' + metric)
                require(limits.get('min', -math.inf) <= values[metric] <= limits.get('max', math.inf),
                        'Retained cell violates strict regional requirement: ' + metric)
            require(diagnostic.get('assessment_status') == 'pass', 'Published private assessment is not passing')
            for metric, observed in diagnostic.get('metrics', {}).items():
                if metric == 'occupancy_mae':
                    require(observed is None, 'Online diagnostic fabricated occupancy reference error')
                else:
                    require(metric in values and close(observed, values[metric]), 'Private retained metric mismatch: ' + metric)
            checks = diagnostic.get('checks', [])
            require(len(checks) == len(bounds) and len({c['metric'] for c in checks}) == len(checks),
                    'Private policy checks omit or duplicate effective requirements')
            for check in checks:
                metric = check['metric']
                require(metric in bounds and all(check.get(k) == bounds[metric].get(k) for k in ('min','max'))
                        and close(check.get('observed'), values[metric]) and check.get('status') == 'pass',
                        'Private policy check disagrees with retained regional assessment')
            ordinary = catalog.ordinary_loss(raw, support)
            full_loss = (len(removed) + weighted) / len(raw)
            if audit is not None:
                require(audit.get('schema') == 'ump.semantic-suppression.v1', 'Wrong private suppression schema')
                counts = {'input_observation_contributions': len(raw), 'input_distinct_contributors': len(identities),
                    'retained_observation_contributions': len(retained), 'retained_distinct_contributors': len(retained_ids),
                    'suppressed_observation_contributions': len(removed),
                    'suppressed_distinct_contributors': len({r['id'] for _, r in removed})}
                require(all(type(audit.get(k)) is int and audit[k] == n for k, n in counts.items()), 'Incorrect private suppression counts')
                require(audit['suppressed_type_observation_contributions'] == dict(Counter(r['type'] for _, r in removed)),
                        'Suppressed raw-type map disagrees with original observations')
                require(close(audit['suppressed_fraction'], fraction) and close(audit['full_input_semantic_loss'], full_loss)
                        and close(audit['unsuppressed_semantic_loss'], ordinary), 'Suppression benefit/loss metadata mismatch')
                require(type(audit['evaluated_candidates']) is int and 0 <= audit['evaluated_candidates'] <= len(catalog.nodes),
                        'Unbounded suppression candidate count')
                candidate_checks += audit['evaluated_candidates']
            require(bool(removed) == ('retained_counts' in diagnostic), 'Missing or unexpected retained private counts')
            if removed:
                require(audit is not None and full_loss < ordinary - TOL, 'Suppression has no strict full-input semantic benefit')
                require(all(sum(leaf == catalog.labels[r['type']] for r in identities_to_rows(raw)) < support
                            for leaf in removed_leaves), 'Supported terminal was selectively removed')
                retained_diag = diagnostic['retained_counts']
                require(retained_diag['observation_contributions'] == len(retained)
                        and retained_diag['distinct_road_users'] == len(retained_ids)
                        and close(retained_diag['mean_sample_occupancy'], values['mean_sample_occupancy']),
                        'Private retained counts disagree with released population')
            for t, row in retained:
                observation_key = (t, row['id'])
                require(observation_key not in retained_keys and observation_key not in suppressed_keys, 'Observation support reused')
                retained_keys.add(observation_key)
                delays[release['sealed_at_ms'] - t] += 1
                groups[row['id'].rsplit('-', 1)[0]] += 1
            for t, row in removed:
                observation_key = (t, row['id'])
                require(observation_key not in retained_keys and observation_key not in suppressed_keys, 'Suppressed support reused')
                suppressed_keys.add(observation_key)
            selective_lost += len(removed)
            total_bins += len(categories)
            records.append({'start_ms': release['start_ms'], 'end_ms': release['end_ms'],
                'cell_id': cell['cell_id'], 'depth': cell['depth'], 'intersected_regions': touched,
                'effective_requirements': bounds, 'recomputed_metrics': values,
                'full_input_semantic_loss': full_loss, 'unsuppressed_semantic_loss': ordinary})
    require(not selected, 'Private selected cell has no actual recipient release')
    accounting = source_accounting(data, config, retained_keys, suppressed_keys)
    retained_total = sum(delays.values())
    def quantile(fraction):
        target = math.ceil(retained_total * fraction)
        cumulative = 0
        for delay, count in sorted(delays.items()):
            cumulative += count
            if cumulative >= target: return delay
        return None
    accounting['observation_to_release_delay_ms'] = {
        'mean':sum(delay * n for delay,n in delays.items()) / retained_total if retained_total else None,
        'p50':quantile(.5),'p95':quantile(.95),'p99':quantile(.99),'maximum':max(delays) if delays else None}
    return {'status': 'verified', 'scalar': scalar, 'semantic_published_cells': len(records),
        'semantic_published_bins': total_bins, 'retained_by_source_group': dict(groups),
        'regional_recomputations': records, 'source_accounting': accounting,
        'selectively_suppressed_observations': selective_lost, 'suppression_candidates': candidate_checks,
        'contribution_selection': 'policy_filtered' if may_filter(config) else 'all_contributions',
        'scope': 'Original full-interval retirement plus independently recomputed retained population, truthful semantic bins, strict regional requirements, observation fraction cap and unit-removal full-input loss; no optimality/privacy proof or original-source exact-query guarantee.'}


def identities_to_rows(rows):
    """One original row per identity; aliases map to the same stable terminal."""
    return list({r['id']: r for _, r in rows}.values())


def source_accounting(data, config, retained_keys, selective_keys):
    total, kept, removed = Counter(), Counter(), Counter()
    regions = {r['id']: r for r in config.get('policy_regions', [])}
    regional = {identity: {'input_observations': 0, 'retained_observations': 0,
                          'selectively_suppressed_observations': 0} for identity in config['policy_tree']['regions']}
    for batch in data['batches']:
        for row in batch['observations']:
            key = (batch['observed_at_ms'], row['id'])
            total[row['type']] += 1
            kept[row['type']] += key in retained_keys
            removed[row['type']] += key in selective_keys
            if 'x' in row and 'y' in row:
                for identity, values in regional.items():
                    region = regions[identity]
                    if region['x'] <= row['x'] < region['x'] + region['width'] and region['y'] <= row['y'] < region['y'] + region['height']:
                        values['input_observations'] += 1
                        values['retained_observations'] += key in retained_keys
                        values['selectively_suppressed_observations'] += key in selective_keys
    def counts(n, k, s):
        return {'input_observations': n, 'retained_observations': k,
                'selectively_suppressed_observations': s, 'whole_footprint_suppressed_observations': n-k-s,
                'retained_fraction': k/n if n else None, 'selectively_suppressed_fraction': s/n if n else None}
    return {**counts(sum(total.values()), sum(kept.values()), sum(removed.values())),
            'by_source_type': {kind: counts(n, kept[kind], removed[kind]) for kind, n in sorted(total.items())},
            'by_region': {identity: counts(v['input_observations'],v['retained_observations'],v['selectively_suppressed_observations'])
                          for identity, v in regional.items()},
            'region_scope': 'Nonexclusive original observation positions, half-open region footprints; overlap may count one contribution in multiple regions.'}
