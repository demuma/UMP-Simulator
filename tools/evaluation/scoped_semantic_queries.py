"""Exact semantic query utility for immutable common or cell-local releases.

The query bank is explicit and independent of released footprints. Answers use
only complete, contained public tiles and their declared taxonomy domains. This
is a conservative exact-answer workload, not a general transcript inference
solver or a privacy estimator. Counts are observation contributions, not sums
of distinct identities or a synchronized occupancy snapshot.
"""
from bisect import bisect_left, insort
from collections import Counter, defaultdict
from copy import deepcopy
import math


SCHEMA = 'ump.scoped-semantic-queries.v1'
MAX_COUNT = 9007199254740991
MAX_QUERIES = 500000
MAX_RECORDS = 100000
MAX_CANDIDATE_CHECKS = 20000000
MAX_TAXONOMY_NODES = 1024


def _integer(value, name, minimum=0, maximum=MAX_COUNT):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f'{name} must be an integer in [{minimum},{maximum}]')
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite numeric data')
    return value


def _text(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} must be a nonempty string')
    return value


def _catalog(config):
    if not isinstance(config, dict) or not isinstance(config.get('semantic_taxonomy'), dict):
        raise ValueError('A declared semantic_taxonomy is required')
    taxonomy = config['semantic_taxonomy']
    identity = _text(taxonomy.get('id'), 'taxonomy ID')
    raw_version = taxonomy.get('version')
    if isinstance(raw_version, bool) or not isinstance(raw_version, (str, int)):
        raise ValueError('Taxonomy version must be a string or integer')
    version = _text(str(raw_version), 'taxonomy version')
    rows = taxonomy.get('nodes')
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_TAXONOMY_NODES:
        raise ValueError('Taxonomy requires a bounded nonempty node list')
    nodes, labels, children = {}, {}, defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Taxonomy nodes must be objects')
        node = _text(row.get('id'), 'taxonomy node ID')
        if node in nodes:
            raise ValueError('Duplicate taxonomy node')
        parent = row.get('parent', '')
        if not isinstance(parent, str):
            raise ValueError('Taxonomy parent must be a string')
        loss = _number(row.get('loss'), 'taxonomy loss')
        if not 0 <= loss <= 1:
            raise ValueError('Taxonomy losses must lie in [0,1]')
        raw = row.get('input_types', [])
        if not isinstance(raw, list):
            raise ValueError('Taxonomy input_types must be a list')
        nodes[node] = dict(parent=parent, loss=loss, input_types=list(raw))
        for label in raw:
            label = _text(label, 'taxonomy input label')
            if label in labels:
                raise ValueError('Taxonomy input labels must be unambiguous')
            labels[label] = node
        if parent:
            children[parent].append(node)
    roots = [node for node, row in nodes.items() if not row['parent']]
    if len(roots) != 1:
        raise ValueError('Taxonomy must have exactly one root')
    for node, row in nodes.items():
        parent = row['parent']
        if parent and (parent not in nodes or nodes[parent]['loss'] < row['loss']):
            raise ValueError('Taxonomy requires known parents and monotone losses')
        if bool(children[node]) == bool(row['input_types']):
            raise ValueError('Only terminal nodes may declare input labels; every terminal needs one')
    # Iterative traversal also rejects disconnected cycles without recursion limits.
    order, pending, seen = [], [roots[0]], set()
    while pending:
        node = pending.pop()
        if node in seen:
            raise ValueError('Taxonomy contains a cycle')
        seen.add(node)
        order.append(node)
        pending.extend(children[node])
    if len(seen) != len(nodes):
        raise ValueError('Taxonomy must be connected and acyclic')
    domains = {}
    for node in reversed(order):
        domains[node] = (frozenset((node,)) if not children[node]
                         else frozenset().union(*(domains[child] for child in children[node])))
    declaration = dict(id=identity, version=version, nodes=[dict(id=node,
        parent=nodes[node]['parent'], loss=nodes[node]['loss'],
        input_types=sorted(nodes[node]['input_types'])) for node in sorted(nodes)])
    return dict(id=identity, version=version, nodes=nodes, labels=labels,
                domains=domains, declaration=declaration)


def _coverage(replay):
    if not isinstance(replay, dict) or replay.get('schema') != 'ump.observation-replay.v1':
        raise ValueError('Expected an observation replay')
    raw = replay.get('coverage')
    if not isinstance(raw, dict):
        raise ValueError('Replay requires coverage')
    grid = {key: _number(raw.get(key), f'coverage {key}') for key in ('x', 'y', 'width', 'height')}
    if grid['width'] <= 0 or grid['height'] <= 0:
        raise ValueError('Coverage dimensions must be positive')
    if not all(math.isfinite(grid[axis] + grid[size]) and grid[axis] + grid[size] > grid[axis]
               for axis, size in (('x', 'width'), ('y', 'height'))):
        raise ValueError('Coverage bounds must be finite and representably distinct')
    grid['leaf_depth'] = _integer(raw.get('leaf_depth'), 'finest depth', 0, 14)
    return grid


def _geometry(cell_id, depth, grid):
    depth = _integer(depth, 'cell depth', 0, grid['leaf_depth'])
    cell_id = _integer(cell_id, 'cell ID', 3)
    if cell_id >> (2 * depth) != 3:
        raise ValueError('Cell ID and depth disagree')
    x, y, width, height = (grid[key] for key in ('x', 'y', 'width', 'height'))
    for level in reversed(range(depth)):
        width /= 2
        height /= 2
        quadrant = cell_id >> (2 * level) & 3
        x += (quadrant & 1) * width
        y += ((quadrant >> 1) & 1) * height
    if width <= 0 or height <= 0 or x + width <= x or y + height <= y:
        raise ValueError('Cell geometry is not representable at this depth')
    shift = 2 * (grid['leaf_depth'] - depth)
    offset = cell_id - (3 << (2 * depth))
    return dict(cell_id=cell_id, depth=depth, x=x, y=y, width=width, height=height,
                lo=offset << shift, hi=(offset + 1) << shift)


def _declared_geometry(value, grid, name):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    geometry = _geometry(value.get('cell_id'), value.get('depth'), grid)
    for key in ('x', 'y', 'width', 'height'):
        actual = _number(value.get(key), f'{name} {key}')
        tolerance = min(4 * max(math.ulp(actual), math.ulp(geometry[key])),
                        min(geometry['width'], geometry['height']) * 1e-6)
        if abs(actual - geometry[key]) > tolerance:
            raise ValueError(f'{name} geometry disagrees with its quadtree ID')
    return geometry


def _source(replay, catalog, grid, period, horizon, window, target_ids):
    batches = replay.get('batches')
    if not isinstance(batches, list):
        raise ValueError('Source batches must be a list')
    counts, measured = defaultdict(Counter), Counter()
    previous, identity_types = 0, {}
    for batch in batches:
        if not isinstance(batch, dict):
            raise ValueError('Source batch must be an object')
        time = _integer(batch.get('observed_at_ms'), 'source time', 1, horizon - 1)
        if time <= previous or time % period:
            raise ValueError('Source timestamps must be unique, chronological and cadence-aligned; t0 is unsampled')
        previous = time
        status, observations = batch.get('status'), batch.get('observations')
        if status not in ('measured', 'unavailable') or not isinstance(observations, list):
            raise ValueError('Invalid source status or observations')
        if status == 'unavailable' and observations:
            raise ValueError('Unavailable source batch contains observations')
        window_index = time // window
        if status == 'measured':
            measured[window_index] += 1
        seen = set()
        for observation in observations:
            if not isinstance(observation, dict):
                raise ValueError('Source observation must be an object')
            identity = _text(observation.get('id'), 'source identity')
            if identity in seen:
                raise ValueError('Source identities must be unique within a sample')
            seen.add(identity)
            label = observation.get('type')
            if not isinstance(label, str) or label not in catalog['labels']:
                raise ValueError('Unknown source class')
            node = catalog['labels'][label]
            if identity in identity_types and identity_types[identity] != node:
                raise ValueError('This benchmark requires stable canonical types per identity')
            identity_types[identity] = node
            cell = _geometry(observation.get('cell_id'), grid['leaf_depth'], grid)
            x = _number(observation.get('x'), 'source x')
            y = _number(observation.get('y'), 'source y')
            if not cell['x'] <= x < cell['x'] + cell['width'] or not cell['y'] <= y < cell['y'] + cell['height']:
                raise ValueError('Source coordinate disagrees with its finest cell')
            ancestor = cell['cell_id']
            for _ in range(grid['leaf_depth'] + 1):
                if ancestor in target_ids:
                    counts[(window_index, ancestor)][node] += 1
                ancestor >>= 2
    return counts, measured


def _semantic(cell, catalog):
    observations = _integer(cell.get('observation_contributions'), 'public observations', 1)
    distinct = _integer(cell.get('distinct_road_users'), 'public distinct support', 1)
    if distinct > observations:
        raise ValueError('Public distinct support exceeds observations')
    value = cell.get('semantic')
    if not isinstance(value, dict) or value.get('schema') != 'ump.semantic-release.v1':
        raise ValueError('Every public cell requires a semantic representation')
    if value.get('taxonomy_id') != catalog['id'] or str(value.get('taxonomy_version')) != catalog['version']:
        raise ValueError('Public taxonomy does not match the declared taxonomy')
    rows = value.get('categories')
    if not isinstance(rows, list) or not 1 <= len(rows) <= len(catalog['nodes']):
        raise ValueError('Semantic categories require a bounded nonempty list')
    bins, occupied = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Semantic bin must be an object')
        node = row.get('category_id')
        if not isinstance(node, str) or node not in catalog['nodes']:
            raise ValueError('Unknown semantic category')
        domain = catalog['domains'][node]
        if occupied.intersection(domain):
            raise ValueError('Semantic categories overlap or repeat')
        occupied.update(domain)
        count = _integer(row.get('observation_contributions'), 'category observations', 1)
        support = _integer(row.get('distinct_contributors'), 'category distinct support', 1)
        if support > count:
            raise ValueError('Category distinct support exceeds observations')
        bins.append((node, count, support))
    if sum(row[1] for row in bins) != observations or sum(row[2] for row in bins) != distinct:
        raise ValueError('Semantic partition must account for cell observations and stable-type distinct support')
    minimum = _number(value.get('min_category_distinct_contributors'), 'minimum category support')
    maximum = _number(value.get('semantic_max_loss'), 'maximum semantic loss')
    mean = _number(value.get('semantic_mean_loss'), 'mean semantic loss')
    if minimum != min(row[2] for row in bins) or maximum != max(catalog['nodes'][row[0]]['loss'] for row in bins):
        raise ValueError('Semantic metric summary contradicts public bins')
    expected_mean = sum(count * catalog['nodes'][node]['loss'] for node, count, _ in bins) / observations
    if not 0 <= mean <= 1 or not math.isclose(mean, expected_mean, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError('Semantic mean loss contradicts public bins')
    return bins


def _public(releases, grid, catalog, horizon, period):
    if not isinstance(releases, list):
        raise ValueError('Recipient releases must be a list')
    if len(releases) > MAX_RECORDS:
        raise ValueError('Recipient release budget exceeded')
    records, identities, previous_seal, scoped = [], set(), 0, None
    for release in releases:
        if not isinstance(release, dict):
            raise ValueError('Recipient release must be an object')
        identity = _text(release.get('release_id'), 'release ID')
        if identity in identities:
            raise ValueError('Recipient release IDs must be unique')
        identities.add(identity)
        has_scope = release.get('coordination_cell') is not None
        if scoped is not None and scoped != has_scope:
            raise ValueError('Mixed scoped and unscoped recipient releases are not supported')
        scoped = has_scope
        scope = _declared_geometry(release['coordination_cell'], grid, 'coordination cell') if has_scope else None
        start = _integer(release.get('start_ms'), 'release start', 0, horizon)
        end = _integer(release.get('end_ms'), 'release end', 1, horizon)
        sealed = _integer(release.get('sealed_at_ms'), 'release seal', 1, horizon)
        if start >= end or sealed < end or sealed < previous_seal or start % period or end % period:
            raise ValueError('Invalid recipient interval, cadence or sealing chronology')
        previous_seal = sealed
        tlo, thi = max(1, start // period), end // period
        cells = release.get('cells')
        if tlo >= thi or not isinstance(cells, list) or not cells:
            raise ValueError('Recipient release requires sampled support and selected cells')
        if len(records) + len(cells) > MAX_RECORDS:
            raise ValueError('Public cell record budget exceeded')
        for cell in cells:
            geometry = _declared_geometry(cell, grid, 'public cell')
            if scope and not scope['lo'] <= geometry['lo'] < geometry['hi'] <= scope['hi']:
                raise ValueError('Public cell lies outside its coordination cell')
            bins = _semantic(cell, catalog)
            records.append(dict(**geometry, start=start, end=end, sealed=sealed,
                                tlo=tlo, thi=thi, bins=bins))
    # Sweep sampled time; active Morton intervals must be disjoint. No leaf expansion.
    events = sorted((time, kind, index) for index, row in enumerate(records)
                    for time, kind in ((row['tlo'], 1), (row['thi'], 0)))
    active = []
    for _, kind, index in events:
        row = records[index]
        item = (row['lo'], row['hi'], index)
        position = bisect_left(active, item)
        if not kind:
            if position >= len(active) or active[position] != item:
                raise ValueError('Invalid public support sweep')
            active.pop(position)
        else:
            if ((position and active[position - 1][1] > row['lo']) or
                    (position < len(active) and active[position][0] < row['hi'])):
                raise ValueError('Recipient cells overlap in space and sampled time')
            insort(active, item)
    return records


def _category_count(bins, category, catalog):
    domain = catalog['domains'][category]
    result = 0
    for node, count, _ in bins:
        public = catalog['domains'][node]
        if public <= domain:
            result += count
        elif public.intersection(domain):
            return None
    return result


def _summary(queries):
    observed = [q for q in queries if q['deadline_observed']]
    eligible = [q for q in observed if q['reference_available']]
    answered = [q for q in eligible if q['answered']]
    receiver_answered = sum(q['answered'] for q in observed)
    absolute_error_sum = sum(q['absolute_error'] for q in answered)
    return dict(query_count=len(queries), observed_query_count=len(observed),
        censored_query_count=len(queries) - len(observed),
        deadline_at_eof_query_count=sum(q['deadline_at_eof'] for q in queries),
        reference_available_query_count=len(eligible),
        reference_unavailable_query_count=len(observed) - len(eligible),
        receiver_answered_query_count=receiver_answered,
        receiver_query_coverage=receiver_answered / len(observed) if observed else None,
        answered_query_count=len(answered), query_coverage=len(answered) / len(eligible) if eligible else None,
        absolute_error_sum=absolute_error_sum,
        answered_only_mae=absolute_error_sum / len(answered) if answered else None)


def _summaries(queries, categories):
    result = _summary(queries)
    result['known_zero'] = _summary([q for q in queries if q['reference_available'] and q['reference_observation_contributions'] == 0])
    result['positive'] = _summary([q for q in queries if q['reference_available'] and q['reference_observation_contributions'] > 0])
    result['by_category'] = {category: _summary([q for q in queries if q['category_id'] == category]) for category in categories}
    return result


def _candidate_index(records, targets, window, period, window_count, categories_count, lags_count):
    """Index only explicit targets; bounded work, including crossing tile diagnostics."""
    target_ids = {row['cell_id'] for row in targets}
    by_cell = defaultdict(list)
    for index, row in enumerate(records):
        by_cell[row['cell_id']].append(index)
    by_target = defaultdict(list)
    for index, row in enumerate(records):
        ancestor = row['cell_id']
        for _ in range(row['depth'] + 1):
            if ancestor in target_ids:
                by_target[ancestor].append(index)
            ancestor >>= 2
    for target in targets:
        ancestor = target['cell_id'] >> 2
        for _ in range(target['depth']):
            by_target[target['cell_id']].extend(by_cell.get(ancestor, ()))
            ancestor >>= 2
    indexed, work = defaultdict(list), 0
    for identity, indexes in by_target.items():
        for index in indexes:
            row = records[index]
            first = row['tlo'] * period // window
            last = min(window_count - 1, (row['thi'] - 1) * period // window)
            occurrences = max(0, last - first + 1)
            work += occurrences * categories_count * lags_count
            if work > MAX_CANDIDATE_CHECKS:
                raise ValueError('Public tile/query comparison budget exceeded; reduce the declared workload')
            for window_index in range(first, last + 1):
                indexed[(identity, window_index)].append(row)
    return indexed


def evaluate(replay, config, releases, *, target_cells, categories, window_ms=400,
             lags_ms=(0, 400), max_queries=MAX_QUERIES):
    """Evaluate a preregistered exact query bank against recipient-visible releases.

    Initial state t=0 is not a scheduled measurement. All windows are half-open;
    only full fixed query windows are generated. Interior membership is identical
    across lags. A deadline at the source horizon is observed but marked as EOF.
    No private diagnostic window is read, and ground truth cannot repair a public
    answer. Sparse Morton intervals avoid expansion of the finest spatial grid.
    """
    catalog = _catalog(config)
    grid = _coverage(replay)
    period = _integer(replay.get('sampling_period_ms'), 'sampling period', 1)
    horizon = _integer(replay.get('end_ms'), 'source horizon', period + 1)
    window = _integer(window_ms, 'query window', period)
    if window % period:
        raise ValueError('Query windows must align with the sampling cadence')
    if not isinstance(lags_ms, (tuple, list)) or not lags_ms:
        raise ValueError('At least one declared deadline lag is required')
    lags = [_integer(lag, 'deadline lag') for lag in lags_ms]
    if lags != sorted(set(lags)):
        raise ValueError('Deadline lags must be unique and sorted')
    budget = _integer(max_queries, 'query budget', 1, MAX_QUERIES)
    if not isinstance(target_cells, (list, tuple)) or not target_cells:
        raise ValueError('A nonempty explicit target-cell mask is required')
    targets, seen = [], set()
    for target in target_cells:
        if not isinstance(target, dict):
            raise ValueError('Target cells must be objects')
        row = _geometry(target.get('cell_id'), target.get('depth'), grid)
        if row['cell_id'] in seen:
            raise ValueError('Duplicate query target cell')
        seen.add(row['cell_id'])
        targets.append(row)
    targets.sort(key=lambda row: (row['depth'], row['cell_id']))
    if not isinstance(categories, (tuple, list)) or not categories:
        raise ValueError('A nonempty explicit category list is required')
    if any(not isinstance(category, str) or category not in catalog['nodes'] for category in categories):
        raise ValueError('Unknown query category')
    if len(set(categories)) != len(categories):
        raise ValueError('Duplicate query category')
    categories = sorted(categories)
    window_count = horizon // window
    if not window_count:
        raise ValueError('Source horizon contains no complete query window')
    query_count = window_count * len(targets) * len(categories) * len(lags)
    if query_count > budget:
        raise ValueError('Expanded query budget exceeded; reduce the declared workload')
    source, measured = _source(replay, catalog, grid, period, horizon, window, seen)
    records = _public(releases, grid, catalog, horizon, period)
    candidates = _candidate_index(records, targets, window, period, window_count, len(categories), len(lags))
    evaluations = {}
    for lag in lags:
        queries = []
        for window_index in range(window_count):
            start, end = window_index * window, (window_index + 1) * window
            deadline = end + lag
            scheduled = end // period - max(1, start // period)
            reference_available = scheduled > 0 and measured[window_index] == scheduled
            for target in targets:
                required = (target['hi'] - target['lo']) * scheduled
                rows = candidates.get((target['cell_id'], window_index), ())
                for category in categories:
                    reference = None
                    if reference_available:
                        reference = sum(count for node, count in source.get((window_index, target['cell_id']), {}).items()
                                        if node in catalog['domains'][category])
                    covered, prediction, reasons = 0, 0, set()
                    observed = deadline <= horizon
                    if observed:
                        for row in rows:
                            if row['sealed'] > deadline:
                                continue
                            if row['start'] < start or row['end'] > end or row['lo'] < target['lo'] or row['hi'] > target['hi']:
                                reasons.add('crossing_public_support')
                                continue
                            category_counts = row.setdefault('category_counts', {})
                            if category not in category_counts:
                                category_counts[category] = _category_count(row['bins'], category, catalog)
                            count = category_counts[category]
                            if count is None:
                                reasons.add('semantic_generalization')
                                continue
                            covered += (row['hi'] - row['lo']) * (row['thi'] - row['tlo'])
                            prediction += count
                    answered = observed and scheduled > 0 and covered == required
                    if not answered:
                        if not scheduled:
                            reasons.add('no_scheduled_samples')
                        if not observed:
                            reasons.add('deadline_censored')
                        elif covered < required:
                            reasons.add('missing_public_support')
                    prediction = prediction if answered else None
                    queries.append(dict(start_ms=start, end_ms=end, category_id=category,
                        cell_id=target['cell_id'], target_cell_id=target['cell_id'], depth=target['depth'],
                        width_m=target['width'], height_m=target['height'], scheduled_sample_count=scheduled,
                        deadline_ms=deadline, deadline_observed=observed, deadline_at_eof=deadline == horizon,
                        cohort='interior' if end + max(lags) < horizon else 'boundary',
                        reference_available=reference_available, reference_observation_contributions=reference,
                        answered=answered, prediction=prediction,
                        absolute_error=abs(prediction - reference) if answered and reference_available else None,
                        unknown_reasons=sorted(reasons) if not answered else []))
        evaluations[str(lag)] = dict(queries=queries, summary={cohort: _summaries(
            [q for q in queries if q['cohort'] == cohort], categories) for cohort in ('interior', 'boundary')})
    return dict(schema=SCHEMA, query_definition=dict(
        target_cells=[dict(cell_id=row['cell_id'], depth=row['depth']) for row in targets],
        categories=categories, window_ms=window, lags_ms=lags,
        observation_sampling_period_ms=period, source_horizon_ms=horizon, coverage=grid,
        taxonomy=catalog['declaration'], query_count_per_lag=query_count // len(lags),
        full_window_count=window_count, trailing_time_ms=horizon - window_count * window,
        trailing_start_ms=window_count * window,
        count='observation_contributions', source_type_contract='stable canonical terminal category per identity throughout the reference run',
        public_rule='complete contained immutable space-time/category support only; no clipping or proportional allocation',
        reference='sampled source; unavailable or missing measurements remain unknown',
        initial_sample_excluded=True,
        scheduled_samples='sampling_period_ms, 2*sampling_period_ms, ... strictly before end_ms; t0 is unsampled',
        cohort='interior iff query_end + max(lags) < source_horizon; EOF and censored deadlines marked'),
        evaluations_by_lag_ms=evaluations)


def compact(evaluation):
    """Return definitions and aggregate summaries without observations or query rows."""
    if not isinstance(evaluation, dict) or evaluation.get('schema') != SCHEMA:
        raise ValueError('Expected a scoped semantic query evaluation')
    return dict(schema=SCHEMA, query_definition=deepcopy(evaluation['query_definition']),
        evaluations_by_lag_ms={lag: dict(summary=deepcopy(value['summary']))
                              for lag, value in evaluation['evaluations_by_lag_ms'].items()})


def _paired_counts(a, b):
    observed = [(left, right) for left, right in zip(a, b) if left['deadline_observed']]
    eligible = [(left, right) for left, right in observed if left['reference_available']]
    both = [(left, right) for left, right in observed if left['answered'] and right['answered']]
    scored = [(left, right) for left, right in both if left['reference_available']]
    return dict(query_count=len(a), observed_query_count=len(observed),
        reference_available_query_count=len(eligible),
        both_answered_query_count=len(both),
        only_a_answered_query_count=sum(left['answered'] and not right['answered'] for left, right in observed),
        only_b_answered_query_count=sum(right['answered'] and not left['answered'] for left, right in observed),
        neither_answered_query_count=sum(not left['answered'] and not right['answered'] for left, right in observed),
        scored_intersection_query_count=len(scored),
        intersection_a_absolute_error_sum=sum(left['absolute_error'] for left, _ in scored),
        intersection_b_absolute_error_sum=sum(right['absolute_error'] for _, right in scored),
        intersection_a_mae=sum(left['absolute_error'] for left, _ in scored) / len(scored) if scored else None,
        intersection_b_mae=sum(right['absolute_error'] for _, right in scored) / len(scored) if scored else None)


def paired_summary(a, b):
    """Pair identical workloads/references, exposing both coverage and intersection error.

    The intersection MAEs alone are not an overall utility ranking. Full eligible
    query denominators and exclusive answer counts are retained alongside them.
    """
    if any(not isinstance(value, dict) or value.get('schema') != SCHEMA for value in (a, b)):
        raise ValueError('Expected two scoped semantic query evaluations')
    if a.get('query_definition') != b.get('query_definition'):
        raise ValueError('Paired evaluations require identical query definitions')
    left_lags, right_lags = a.get('evaluations_by_lag_ms'), b.get('evaluations_by_lag_ms')
    if not isinstance(left_lags, dict) or not isinstance(right_lags, dict) or left_lags.keys() != right_lags.keys():
        raise ValueError('Paired evaluations require identical deadline lags')
    identities = ('target_cell_id', 'depth', 'start_ms', 'end_ms', 'category_id', 'deadline_ms',
                  'deadline_observed', 'deadline_at_eof', 'cohort', 'scheduled_sample_count',
                  'reference_available', 'reference_observation_contributions')
    categories = a['query_definition']['categories']
    output = {}
    for lag, left in left_lags.items():
        aq, bq = left.get('queries'), right_lags[lag].get('queries')
        if not isinstance(aq, list) or not isinstance(bq, list) or len(aq) != len(bq):
            raise ValueError('Pairing requires full query rows with identical lengths')
        if any(any(x.get(key) != y.get(key) for key in identities) for x, y in zip(aq, bq)):
            raise ValueError('Paired query identities or reference counts disagree')
        summaries = {}
        for cohort in ('interior', 'boundary'):
            ca = [q for q in aq if q['cohort'] == cohort]
            cb = [q for q in bq if q['cohort'] == cohort]
            summary = _paired_counts(ca, cb)
            summary['a'] = _summaries(ca, categories)
            summary['b'] = _summaries(cb, categories)
            summary['by_category'] = {category: _paired_counts(
                [q for q in ca if q['category_id'] == category],
                [q for q in cb if q['category_id'] == category]) for category in categories}
            for name, positive in (('known_zero', False), ('positive', True)):
                selector = lambda q: q['reference_available'] and (q['reference_observation_contributions'] > 0) == positive
                summary[name] = _paired_counts([q for q in ca if selector(q)], [q for q in cb if selector(q)])
            summaries[cohort] = summary
        output[lag] = dict(summary=summaries)
    return dict(schema='ump.scoped-semantic-queries-paired.v1',
                query_definition=deepcopy(a['query_definition']), evaluations_by_lag_ms=output)
