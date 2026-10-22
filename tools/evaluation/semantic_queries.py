"""Conservative exact category-count queries for the bounded semantic study.

Only recipient releases determine answers. Source observations supply a separate
reference, never missing public support. Crossing aggregates are not clipped or
proportionally allocated. This is a declared exact-answer rule, not a complete
solver for all information inferable from the transcript (e.g. zero specialization).
Counts are observation contributions, not sums of distinct-person counts.
"""
from collections import Counter
import math


SCHEMA = 'ump.semantic-fixed-queries.v1'
CATEGORIES = ('road_user', 'cyclist', 'adult_cyclist', 'child_cyclist')
PARENTS = {'road_user': '', 'pedestrian': 'road_user', 'cyclist': 'road_user',
           'adult_cyclist': 'cyclist', 'child_cyclist': 'cyclist'}
LOSSES = {'road_user': 1.0, 'pedestrian': 0.0, 'cyclist': .5,
          'adult_cyclist': 0.0, 'child_cyclist': 0.0}
MAX_COUNT = 9007199254740991


def _integer(value, name, minimum=0, maximum=MAX_COUNT):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer in [{minimum},{maximum}]')
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric data')
    return value


def _ancestor(ancestor, node):
    while node:
        if node == ancestor:
            return True
        node = PARENTS[node]
    return False


def _catalog(config):
    if not isinstance(config, dict) or not isinstance(config.get('semantic_taxonomy'), dict):
        raise ValueError('The fixed workload requires semantic_taxonomy')
    taxonomy = config['semantic_taxonomy']
    if taxonomy.get('id') != 'semantic-priority' or str(taxonomy.get('version')) != '1':
        raise ValueError('The fixed workload requires semantic-priority taxonomy version 1')
    nodes = taxonomy.get('nodes')
    if not isinstance(nodes, list) or len(nodes) != len(PARENTS):
        raise ValueError('The fixed workload requires its five-node taxonomy')
    labels, seen = {}, set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError('Taxonomy nodes must be objects')
        identity = node.get('id')
        if not isinstance(identity, str) or identity not in PARENTS or identity in seen or node.get('parent', '') != PARENTS[identity]:
            raise ValueError('Unsupported or duplicate semantic category/hierarchy')
        seen.add(identity)
        if _number(node.get('loss'), 'taxonomy loss') != LOSSES[identity]:
            raise ValueError('Unsupported fixed-workload semantic loss')
        raw = node.get('input_types', [])
        if not isinstance(raw, list) or (identity in ('road_user', 'cyclist') and raw):
            raise ValueError('Only terminal categories can define input labels')
        for label in raw:
            if not isinstance(label, str) or not label or label in labels:
                raise ValueError('Input labels must be nonempty and unambiguous')
            labels[label] = identity
        if identity not in ('road_user', 'cyclist') and not raw:
            raise ValueError('Every terminal category requires an input label')
    return taxonomy['id'], str(taxonomy['version']), labels


def _geometry(cell_id, depth):
    _integer(depth, 'cell depth', 1, 2)
    _integer(cell_id, 'cell ID', 1)
    if cell_id >> (2 * depth) != 3:
        raise ValueError('Cell ID and depth disagree')
    if (depth == 1 and cell_id != 12) or (depth == 2 and cell_id not in (48, 49, 50, 51)):
        raise ValueError('Fixed workload observations and releases must stay inside parent12')
    x = y = 0.0
    side = 80.0
    for level in reversed(range(depth)):
        side /= 2
        quadrant = cell_id >> (2 * level) & 3
        x += (quadrant & 1) * side
        y += ((quadrant >> 1) & 1) * side
    leaves = frozenset((cell_id,)) if depth == 2 else frozenset(range(cell_id * 4, cell_id * 4 + 4))
    return x, y, side, leaves


def _source(replay, labels):
    if not isinstance(replay, dict) or replay.get('schema') != 'ump.observation-replay.v1':
        raise ValueError('Expected an observation replay')
    grid = replay.get('coverage')
    if grid != dict(x=0, y=0, width=80, height=80, leaf_depth=2):
        raise ValueError('Fixed queries require the 80m/depth-2 source grid')
    for key in ('x', 'y', 'width', 'height'):
        _number(grid[key], 'source grid geometry')
    _integer(grid['leaf_depth'], 'source finest depth', 2, 2)
    if replay.get('sampling_period_ms') != 100:
        raise ValueError('Fixed queries require a 100ms public source cadence')
    horizon = _integer(replay.get('end_ms'), 'source horizon', 800, 60000)
    if horizon % 800:
        raise ValueError('Source horizon must contain whole 800ms workload intervals')
    batches = replay.get('batches')
    if not isinstance(batches, list):
        raise ValueError('Source batches must be a list')
    source, previous = {}, 0
    for batch in batches:
        if not isinstance(batch, dict):
            raise ValueError('Source batch must be an object')
        time = _integer(batch.get('observed_at_ms'), 'source time', 1, horizon - 1)
        if time <= previous or time % 100:
            raise ValueError('Source timestamps must be unique, chronological and aligned')
        previous = time
        status = batch.get('status')
        observations = batch.get('observations')
        if status not in ('measured', 'unavailable') or not isinstance(observations, list):
            raise ValueError('Invalid source measurement status or observations')
        if status == 'unavailable' and observations:
            raise ValueError('Unavailable source batch contains observations')
        counts, seen = Counter(), set()
        for observation in observations:
            if not isinstance(observation, dict):
                raise ValueError('Source observation must be an object')
            identity, raw = observation.get('id'), observation.get('type')
            if not isinstance(identity, str) or not identity or identity in seen:
                raise ValueError('Source identities must be unique in each sample')
            seen.add(identity)
            if not isinstance(raw, str) or raw not in labels:
                raise ValueError('Unknown raw source class')
            cell_id = observation.get('cell_id')
            x, y, side, _ = _geometry(cell_id, 2)
            if 'x' not in observation or 'y' not in observation:
                raise ValueError('Source observations require position coordinates')
            ox, oy = (_number(observation[key], 'source coordinate') for key in ('x', 'y'))
            if not x <= ox < x + side or not y <= oy < y + side:
                raise ValueError('Source coordinate disagrees with its finest cell')
            counts[(cell_id, labels[raw])] += 1
        source[time] = (status, counts)
    return horizon, source


def _semantic(cell, taxonomy_id, taxonomy_version):
    observations = _integer(cell.get('observation_contributions'), 'public observations', 1)
    distinct = _integer(cell.get('distinct_road_users'), 'public distinct support', 1)
    if distinct > observations:
        raise ValueError('Public distinct support exceeds observations')
    value = cell.get('semantic')
    if not isinstance(value, dict) or value.get('schema') != 'ump.semantic-release.v1':
        raise ValueError('Selected cell requires an approved semantic representation')
    if value.get('taxonomy_id') != taxonomy_id or str(value.get('taxonomy_version')) != taxonomy_version:
        raise ValueError('Public semantic taxonomy version does not match the workload')
    bins = value.get('categories')
    if not isinstance(bins, list) or not bins or len(bins) > len(PARENTS):
        raise ValueError('Semantic categories must be a nonempty bounded partition')
    parsed, seen = [], []
    for row in bins:
        if not isinstance(row, dict):
            raise ValueError('Semantic bin must be an object')
        category = row.get('category_id')
        if not isinstance(category, str) or category not in PARENTS or any(_ancestor(other, category) or _ancestor(category, other) for other in seen):
            raise ValueError('Semantic bins contain unknown, duplicate or overlapping categories')
        seen.append(category)
        count = _integer(row.get('observation_contributions'), 'category observations', 1)
        support = _integer(row.get('distinct_contributors'), 'category distinct support', 1)
        if support > count:
            raise ValueError('Category distinct support exceeds observations')
        parsed.append((category, count, support))
    if sum(row[1] for row in parsed) != observations or sum(row[2] for row in parsed) != distinct:
        raise ValueError('Semantic partition does not account for the entire selected cell')
    minimum = _number(value.get('min_category_distinct_contributors'), 'minimum category support')
    maximum = _number(value.get('semantic_max_loss'), 'maximum semantic loss')
    mean = _number(value.get('semantic_mean_loss'), 'mean semantic loss')
    if minimum != min(row[2] for row in parsed) or maximum != max(LOSSES[row[0]] for row in parsed):
        raise ValueError('Semantic metric summary contradicts the public bins')
    expected_mean = sum(count * LOSSES[category] for category, count, _ in parsed) / observations
    if not math.isclose(mean, expected_mean, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError('Semantic mean loss contradicts public category counts')
    return tuple(parsed)


def _public(releases, horizon, taxonomy_id, taxonomy_version):
    if not isinstance(releases, list):
        raise ValueError('Recipient releases must be a list')
    records, occupied, identities = [], set(), set()
    previous_seal = 0
    for release in releases:
        if not isinstance(release, dict) or release.get('coordination_cell') is not None:
            raise ValueError('Fixed semantic queries require common-window releases')
        identity = release.get('release_id')
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError('Recipient release identities must be nonempty and unique')
        identities.add(identity)
        start = _integer(release.get('start_ms'), 'release start', 0, horizon)
        end = _integer(release.get('end_ms'), 'release end', 1, horizon)
        sealed = _integer(release.get('sealed_at_ms'), 'release seal', 1, horizon)
        if start >= end or sealed < end or sealed < previous_seal or start % 100 or end % 100:
            raise ValueError('Invalid recipient interval, cadence or sealing chronology')
        previous_seal = sealed
        times = tuple(t for t in range(max(100, start), end, 100))
        cells = release.get('cells')
        if not times or not isinstance(cells, list) or not cells:
            raise ValueError('Recipient release requires sampled support and selected cells')
        for cell in cells:
            if not isinstance(cell, dict):
                raise ValueError('Selected cell must be an object')
            x, y, side, leaves = _geometry(cell.get('cell_id'), cell.get('depth'))
            for key, expected in (('x', x), ('y', y), ('width', side), ('height', side)):
                if _number(cell.get(key), 'public geometry') != expected:
                    raise ValueError('Public geometry disagrees with its quadtree ID')
            bins = _semantic(cell, taxonomy_id, taxonomy_version)
            support = frozenset((leaf, t) for leaf in leaves for t in times)
            if support & occupied:
                raise ValueError('Recipient releases overlap in space and sampled time')
            occupied.update(support)
            records.append(dict(start=start, end=end, sealed=sealed, leaves=leaves,
                                support=support, bins=bins))
    return records


def _category_count(bins, category):
    if any(_ancestor(identity, category) and identity != category for identity, _, _ in bins):
        return None
    return sum(count for identity, count, _ in bins if _ancestor(category, identity))


def _summary(queries):
    observed = [q for q in queries if q['deadline_observed']]
    eligible = [q for q in observed if q['reference_available']]
    answered = [q for q in eligible if q['answered']]
    result = dict(query_count=len(queries), observed_query_count=len(observed),
        censored_query_count=len(queries) - len(observed),
        reference_available_query_count=len(eligible),
        reference_unavailable_query_count=len(observed) - len(eligible),
        receiver_answered_query_count=sum(q['answered'] for q in observed),
        answered_query_count=len(answered),
        query_coverage=len(answered) / len(eligible) if eligible else None,
        answered_only_mae=sum(q['absolute_error'] for q in answered) / len(answered) if answered else None)
    return result


def _summaries(queries):
    result = _summary(queries)
    result['known_zero'] = _summary([q for q in queries if q['reference_available']
        and q['reference_observation_contributions'] == 0])
    result['positive'] = _summary([q for q in queries if q['reference_available']
        and q['reference_observation_contributions'] > 0])
    result['by_category'] = {category: _summary([q for q in queries if q['category_id'] == category])
        for category in CATEGORIES}
    return result


def evaluate_queries(replay, config, releases, window_ms=400, lags_ms=(0, 400)):
    """Evaluate a fixed query bank using complete, deadline-visible public tiles.

    A query can remain unknown even when some more elaborate transcript inference
    would recover its count. Reference availability never changes public prediction.
    Whole-horizon normalization, absent-as-zero filling and distinct-count summing
    are deliberately excluded. Deadline==EOF is observed but marked separately.
    """
    _integer(window_ms, 'query window', 400, 800)
    if window_ms not in (400, 800):
        raise ValueError('Fixed workload windows are 400 or 800ms')
    if not isinstance(lags_ms, (tuple, list)) or not lags_ms:
        raise ValueError('At least one declared deadline lag is required')
    for lag in lags_ms:
        _integer(lag, 'deadline lag', 0, 400)
        if lag not in (0, 400):
            raise ValueError('Fixed workload lags are 0 or 400ms')
    if list(lags_ms) != sorted(set(lags_ms)):
        raise ValueError('Deadline lags must be unique and sorted')
    taxonomy_id, taxonomy_version, labels = _catalog(config)
    horizon, source = _source(replay, labels)
    records = _public(releases, horizon, taxonomy_id, taxonomy_version)
    by_scale = {}
    for side, targets in ((20, (48, 49, 50, 51)), (40, (12,))):
        by_lag = {}
        for lag in lags_ms:
            queries = []
            for start in range(0, horizon, window_ms):
                end, deadline = start + window_ms, start + window_ms + lag
                times = tuple(range(max(100, start), end, 100))
                for cell_id in targets:
                    depth = 2 if side == 20 else 1
                    _, _, _, leaves = _geometry(cell_id, depth)
                    required = frozenset((leaf, time) for leaf in leaves for time in times)
                    reference_available = all(time in source and source[time][0] == 'measured' for time in times)
                    for category in CATEGORIES:
                        reference = None
                        if reference_available:
                            reference = sum(count for time in times for (leaf, node), count in source[time][1].items()
                                if leaf in leaves and _ancestor(category, node))
                        covered, prediction, reasons = set(), 0, set()
                        observed = deadline <= horizon
                        if observed:
                            for record in records:
                                if record['sealed'] > deadline or not record['support'] & required:
                                    continue
                                if record['start'] < start or record['end'] > end or not record['leaves'] <= leaves:
                                    reasons.add('crossing_public_support')
                                    continue
                                count = _category_count(record['bins'], category)
                                if count is None:
                                    reasons.add('semantic_generalization')
                                    continue
                                covered.update(record['support'])
                                prediction += count
                        answered = observed and covered == required
                        if not answered and not reasons:
                            reasons.add('missing_public_support' if observed else 'deadline_censored')
                        prediction = prediction if answered else None
                        queries.append(dict(start_ms=start, end_ms=end, category_id=category,
                            cell_id=cell_id, target_cell_id=cell_id, depth=depth, cell_side_m=side,
                            deadline_ms=deadline, deadline_observed=observed,
                            deadline_at_eof=deadline == horizon,
                            cohort='interior' if end + max(lags_ms) < horizon else 'boundary',
                            reference_available=reference_available,
                            reference_observation_contributions=reference,
                            answered=answered, prediction=prediction,
                            absolute_error=abs(prediction - reference) if answered and reference_available else None,
                            unknown_reasons=sorted(reasons) if not answered else []))
            by_lag[str(lag)] = dict(summary={cohort: _summaries([q for q in queries if q['cohort'] == cohort])
                for cohort in ('interior', 'boundary')}, queries=queries)
        by_scale[str(side)] = dict(by_lag_ms=by_lag)
    return dict(schema=SCHEMA, query_definition=dict(window_ms=window_ms, lags_ms=list(lags_ms),
        categories=list(CATEGORIES), observation_sampling_period_ms=100, source_horizon_ms=horizon,
        spatial_scope_cell_id=12, spatial_scope_depth=1,
        target_cells_by_scale={'20': [48, 49, 50, 51], '40': [12]},
        count='observation_contributions', public_rule='complete contained immutable space-time/category support only',
        reference='sampled source; unavailable or missing measurements remain unknown',
        cohort='interior iff query_end + max(lags) < source_horizon; EOF and censored deadlines marked'),
        by_scale=by_scale)
