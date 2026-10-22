"""Independent public-support audit for the bounded, uniform moving-data pilot.

This module does not select cells, choose semantic cuts, or create recipient
predictions. Original source rows are indexed by every spatial ancestor once.
The published intervals then select exact original rows using binary search.
Retirement geometry and full hard-policy coverage remain a separate scalar audit.
"""
from collections import Counter, defaultdict
import math


_LEAVES = {
    'child_pedestrian': ('pedestrian', 'Child Pedestrian'),
    'senior_pedestrian': ('pedestrian', 'Senior Pedestrian'),
    'adult_pedestrian': ('pedestrian', 'Adult Pedestrian'),
    'senior_cyclist': ('cyclist', 'Senior Cyclist'),
    'adult_cyclist': ('cyclist', 'Adult Cyclist'),
    'adult_cargo_cyclist': ('cyclist', 'Adult Cargo Cyclist'),
    'escooter': ('road_user', 'Adult E-Scooter Driver'),
}
_PARENTS = {'road_user': None, 'pedestrian': 'road_user', 'cyclist': 'road_user',
            **{category: parent for category, (parent, _) in _LEAVES.items()}}
_LOSSES = {category: (1 if category == 'road_user' else .5 if category in
                     ('pedestrian', 'cyclist') else 0) for category in _PARENTS}
_MAX_EXACT = 2**53 - 1


def _integer(value, name, minimum=0, maximum=_MAX_EXACT):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an exact integer in [{minimum}, {maximum}]')
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric data')
    return value


def _equal(actual, expected, name):
    actual = _number(actual, name)
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f'{name} disagrees with independently rebuilt source support')


def _bound(root, name, value):
    bound = root.get(name, {})
    for direction in ('min', 'max'):
        if direction in bound:
            limit = _number(bound[direction], f'{name}.{direction}')
            if (direction == 'min' and value < limit) or (direction == 'max' and value > limit):
                raise ValueError(f'Published {name} violates the hard policy {direction}')


def _lower_time(offsets, times, time):
    """Python 3.9-compatible lower bound without duplicating the timestamp index."""
    lo, hi = 0, len(offsets)
    while lo < hi:
        middle = (lo + hi) // 2
        if times[offsets[middle]] < time:
            lo = middle + 1
        else:
            hi = middle
    return lo


def _taxonomy(config):
    catalog = config['semantic_taxonomy']
    if catalog.get('id') != 'ump-seven-profile-release' or catalog.get('version') != '1':
        raise ValueError('Pilot requires its declared seven-profile taxonomy identity')
    expected = {}
    for category, parent in _PARENTS.items():
        node = {'id': category, 'loss': _LOSSES[category]}
        if parent is not None:
            node['parent'] = parent
        if category in _LEAVES:
            node['input_types'] = [_LEAVES[category][1]]
        expected[category] = node
    nodes = catalog.get('nodes', [])
    if len(nodes) != len(expected) or any(node != expected.get(node.get('id')) for node in nodes):
        raise ValueError('Pilot requires the complete declared taxonomy and losses')
    if len({node['id'] for node in nodes}) != len(expected):
        raise ValueError('Repeated taxonomy node')
    for node in nodes:
        _number(node['loss'], 'declared taxonomy loss')
    chains = {}
    for category in _PARENTS:
        chain, current = set(), category
        while current is not None:
            chain.add(current)
            current = _PARENTS[current]
        chains[category] = chain
    return catalog, {label: c for c, (_, label) in _LEAVES.items()}, chains


def _geometry(coverage, cell_id, depth):
    depth = _integer(depth, 'cell depth', 1, coverage['leaf_depth'])
    cell_id = _integer(cell_id, 'cell ID', 1)
    if cell_id >> (2 * depth) != 3:
        raise ValueError('Cell ID does not encode its declared depth')
    x, y, width, height = (coverage[k] for k in ('x', 'y', 'width', 'height'))
    for level in reversed(range(depth)):
        quadrant = (cell_id >> (2 * level)) & 3
        width /= 2
        height /= 2
        if quadrant & 1:
            x += width
        if quadrant & 2:
            y += height
    return {'x': x, 'y': y, 'width': width, 'height': height}


def audit_result(replay, config, result):
    """Return safe aggregate ``{'audit': ..., 'stats': ...}`` or reject input.

    The pilot assumes complete measured cadence and a stable terminal class per
    source identity. No source identity or trajectory is included in the output.
    Source rows can occur in at most one public cell across all release events.
    """
    if config.get('policy_regions') or config['policy_tree'].get('regions'):
        raise ValueError('Moving pilot audit supports a uniform root policy only')
    catalog, labels, chains = _taxonomy(config)
    root = config['policy_tree']['root']
    if replay.get('schema') != 'ump.observation-replay.v1':
        raise ValueError('Unsupported observation replay schema')
    coverage = replay['coverage']
    depth = _integer(coverage['leaf_depth'], 'source leaf depth', 1, 14)
    for name in ('x', 'y', 'width', 'height'):
        _number(coverage[name], f'coverage {name}')
    if coverage['width'] <= 0 or coverage['height'] != coverage['width']:
        raise ValueError('Source coverage must be a positive square')
    period = _integer(replay['sampling_period_ms'], 'sampling period', 1)
    end = _integer(replay['end_ms'], 'source end', 1)
    # Explicit bounds prevent a malformed pilot artifact from allocating without limit.
    if end // period > 1000000:
        raise ValueError('Source exceeds one-million-sample audit budget')
    times, identities, terminals = [], [], []
    indices, stable = defaultdict(list), {}
    source_types = Counter()
    previous_sequence = 0
    expected_times = iter(range(period, end, period))
    for batch in replay['batches']:
        time = _integer(batch['observed_at_ms'], 'source timestamp', 1)
        if time != next(expected_times, None) or batch.get('status') != 'measured':
            raise ValueError('Pilot requires a complete measured source cadence')
        sequence = _integer(batch['sequence'], 'source sequence', 1)
        if sequence <= previous_sequence:
            raise ValueError('Source sequences must increase')
        previous_sequence = sequence
        frame_identities = set()
        for row in batch['observations']:
            identity, terminal = row.get('id'), labels.get(row.get('type'))
            if not isinstance(identity, str) or not identity or terminal is None:
                raise ValueError('Unmapped source type or invalid source identity')
            if identity in frame_identities:
                raise ValueError('Repeated identity within one source sample')
            frame_identities.add(identity)
            if stable.setdefault(identity, terminal) != terminal:
                raise ValueError('Source identity has an unstable terminal type')
            cell_id = _integer(row['cell_id'], 'source leaf ID', 1)
            if cell_id >> (2 * depth) != 3:
                raise ValueError('Source cell is not a canonical leaf')
            offset = len(times)
            if offset >= 1000000:
                raise ValueError('Source exceeds one-million-observation audit budget')
            times.append(time)
            identities.append(identity)
            terminals.append(terminal)
            source_types[terminal] += 1
            for d in range(1, depth + 1):
                indices[cell_id >> (2 * (depth - d))].append(offset)
    if next(expected_times, None) is not None:
        raise ValueError('Pilot requires a complete measured source cadence')
    total = len(times)
    for key in ('input_observation_contributions', 'accounted_observation_contributions'):
        if _integer(result.get(key), key) != total:
            raise ValueError('Result input/accounting total disagrees with original observations')

    consumed = bytearray(total)
    released_types, released_categories = Counter(), Counter()
    retained = cells_count = bins_count = 0
    width_sum = semantic_sum = start_age_sum = delay_sum = duration_sum = 0
    durations, ages, delays, semantic_maxima = [], [], [], []
    for release in result['releases']:
        start = _integer(release['start_ms'], 'release start')
        finish = _integer(release['end_ms'], 'release end', 1, end)
        sealed = _integer(release['sealed_at_ms'], 'release seal', finish, end)
        if start >= finish or start % period or finish % period:
            raise ValueError('Public source interval must be positive and cadence aligned')
        duration, age = finish - start, sealed - start
        _bound(root, 'window_duration_ms', duration)
        _bound(root, 'age_at_evaluation_ms', age)
        if not release['cells']:
            raise ValueError('A public release event cannot contain no cells')
        for cell in release['cells']:
            geometry = _geometry(coverage, cell['cell_id'], cell['depth'])
            for name, value in geometry.items():
                _equal(cell[name], value, f'cell {name}')
            _bound(root, 'cell_side_m', geometry['width'])
            offsets = indices.get(cell['cell_id'], ())
            first = _lower_time(offsets, times, start)
            last = _lower_time(offsets, times, finish)
            matched = offsets[first:last]
            count = len(matched)
            if count == 0 or _integer(cell['observation_contributions'], 'cell count', 1) != count:
                raise ValueError('Published cell observation count disagrees with original support')
            people = {identities[i] for i in matched}
            if _integer(cell['distinct_road_users'], 'cell distinct road users', 1) != len(people):
                raise ValueError('Published cell identity union disagrees with original support')
            _bound(root, 'distinct_contributors', len(people))
            _bound(root, 'observation_contributions', count)
            counts, people_by_type = Counter(), defaultdict(set)
            for index in matched:
                if consumed[index]:
                    raise ValueError('A source contribution is reused by multiple public cells')
                consumed[index] = 1
                counts[terminals[index]] += 1
                people_by_type[terminals[index]].add(identities[index])
            semantic = cell['semantic']
            if (semantic.get('schema') != 'ump.semantic-release.v1'
                    or semantic.get('taxonomy_id') != catalog['id']
                    or semantic.get('taxonomy_version') != catalog['version']):
                raise ValueError('Published semantic schema or taxonomy mismatch')
            bins = semantic['categories']
            categories = [item['category_id'] for item in bins]
            if (not categories or len(categories) != len(set(categories))
                    or any(category not in chains for category in categories)):
                raise ValueError('Unknown, empty or repeated semantic category')
            if any(a != b and a in chains[b] for a in categories for b in categories):
                raise ValueError('Published semantic categories are not an antichain')
            if any(sum(category in chains[terminal] for category in categories) != 1 for terminal in counts):
                raise ValueError('Published semantic cut omits or repeats an observed terminal class')
            weighted, minimum = 0, math.inf
            for item in bins:
                category = item['category_id']
                descendants = [terminal for terminal in counts if category in chains[terminal]]
                expected_count = sum(counts[terminal] for terminal in descendants)
                union = set().union(*(people_by_type[terminal] for terminal in descendants))
                if (_integer(item['observation_contributions'], 'bin observation count', 1) != expected_count
                        or _integer(item['distinct_contributors'], 'bin distinct contributors', 1) != len(union)):
                    raise ValueError('Published semantic bin count/identity union disagrees with original support')
                minimum = min(minimum, len(union))
                weighted += expected_count * _LOSSES[category]
                released_categories[category] += expected_count
                bins_count += 1
            maximum = max(_LOSSES[category] for category in categories)
            mean = weighted / count
            for name, value in (('min_category_distinct_contributors', minimum),
                                ('semantic_max_loss', maximum), ('semantic_mean_loss', mean)):
                _equal(semantic[name], value, name)
                _bound(root, name, value)
            released_types.update(counts)
            retained += count
            cells_count += 1
            width_sum += count * geometry['width']
            semantic_sum += weighted
            start_age_sum += count * age
            duration_sum += count * duration
            cell_delays = [sealed - times[index] for index in matched]
            delay_sum += sum(cell_delays)
            delays.extend((min(cell_delays), max(cell_delays)))
            durations.append(duration)
            ages.append(age)
            semantic_maxima.append(maximum)

    def weighted(value):
        return value / retained if retained else None

    def extent(values):
        return {'min': min(values, default=None), 'max': max(values, default=None)}

    stats = {
        'input_observations': total, 'released_observations': retained,
        'unreleased_observations': total - retained,
        'retained_fraction': retained / total if total else None,
        'released_cells': cells_count, 'released_events': len(result['releases']),
        'retired_domains': len(result.get('windows', [])),
        'mean_cell_side_m': weighted(width_sum), 'mean_semantic_loss': weighted(semantic_sum),
        'maximum_semantic_loss': max(semantic_maxima, default=None),
        'mean_interval_start_age_ms': weighted(start_age_sum),
        'mean_observation_to_release_delay_ms': weighted(delay_sum),
        'mean_window_duration_ms': weighted(duration_sum),
        'window_duration_ms': extent(durations), 'interval_start_age_ms': extent(ages),
        'observation_to_release_delay_ms': extent(delays),
        'per_input_type': {terminal: {'input_observations': source_types[terminal],
                           'released_observations': released_types[terminal],
                           'unreleased_observations': source_types[terminal] - released_types[terminal],
                           'retained_fraction': released_types[terminal] / source_types[terminal]
                                                if source_types[terminal] else None}
                           for terminal in sorted(_LEAVES)},
        'released_category_observations': {category: released_categories[category]
                                           for category in sorted(_PARENTS)},
        'core_processing_ms': _number(result['runtime']['processing_ms'], 'core processing time'),
        'timing_scope': 'Source timestamps and seal times are logical simulation time; CPU is separate and excludes live DB/network latency.',
    }
    if stats['core_processing_ms'] < 0:
        raise ValueError('Core processing time cannot be negative')
    return {'audit': {'status': 'verified', 'input_observations': total,
                      'released_observations': retained, 'public_cells': cells_count,
                      'public_events': len(result['releases']), 'semantic_bins': bins_count,
                      'scope': 'Independent original row counts and identity unions, source nonreuse, complete truthful taxonomy antichains, declared semantic losses and uniform root bounds. Full retirement geometry is checked separately.'},
            'stats': stats}
