"""Causal recipient views and bounded attack features; no classifier fitting.

Availability equals logical sealing, not measured delivery. Candidate sightings are
selected independently per acquisition timestamp with deterministic Bernoulli p=.25,
unlike the earlier fixed-size sample from a complete trajectory. A fixed declared
horizon is public. Extending a trace within that horizon cannot change earlier
selection/noise. Noisy sightings arrive in checkpoint batches only once both their
true acquisition and reported timestamp have passed. Acquisition metadata is used
only for gating, never as an attack feature.
"""
from copy import deepcopy
import math
import random

from empirical_privacy import (_coverage, _feature_vector_validated, _validated_public, feature_vector,
                               feature_names as legacy_feature_names)
from make_fixture import cell_id
from run_privacy_study import stable_seed

CHECKPOINTS = (1000, 2000, 4000, 8000, 12000, 16000)
RECENT_WINDOW_MS = 1000
PROFILES = ('exact_25', 'noisy_25')
VIEWS = ('auxiliary', 'recent', 'history')
AUXILIARY_NAMES = ('point_count', 'mean_x', 'mean_y', 'std_x', 'std_y',
                   'min_reported_time_ms', 'max_reported_time_ms',
                   'mean_reported_time_ms', 'first_last_distance_m')
POINT_KEYS = {'observed_at_ms', 'x', 'y', 'cell_id'}
EVENT_KEYS = {'acquired_at_ms', 'available_at_ms', 'reported'}


def _integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(name+' must be an integer >= '+str(minimum))
    return value


def _point(value):
    if not isinstance(value, dict) or set(value) != POINT_KEYS:
        raise ValueError('Knowledge point has missing or unknown/private fields')
    _integer(value['observed_at_ms'], 'reported time', 1)
    _integer(value['cell_id'], 'cell_id', 1)
    for axis in ('x', 'y'):
        if isinstance(value[axis], bool) or not isinstance(value[axis], (int, float)) or not math.isfinite(value[axis]):
            raise ValueError('Knowledge coordinates must be finite numbers')
    return value


def knowledge_events(trace, coverage, end_ms, seed, profile):
    """Return acquisition-provenance events, identically selected across profiles.

    These private evaluation events must pass through ``knowledge_at`` before
    prediction. Noise has its own per-timestamp RNG: independent 2-m Gaussian x/y
    errors and uniform integer [-200,200]-ms timestamp errors. Clip into the public
    half-open grid and [1,end_ms-1], recompute cell ID, and defer deduplication until
    the events actually become available. Empty partial traces are valid.
    """
    grid = _coverage(coverage)
    _integer(end_ms, 'end_ms', 2)
    _integer(seed, 'seed')
    if seed >= 2**63:
        raise ValueError('seed must fit the supported nonnegative 63-bit range')
    if profile not in PROFILES:
        raise ValueError('Unknown causal knowledge profile')
    if not isinstance(trace, list):
        raise ValueError('trace must be a list')
    previous = 0
    result = []
    for original in trace:
        _point(original)
        acquired = original['observed_at_ms']
        if not previous < acquired < end_ms:
            raise ValueError('Trace acquisition times must increase inside the declared horizon')
        previous = acquired
        if (not grid['x'] <= original['x'] < grid['x'] + grid['width']
                or not grid['y'] <= original['y'] < grid['y'] + grid['height']
                or original['cell_id'] != cell_id(original['x'], original['y'], grid)):
            raise ValueError('Trace point differs from declared public grid geometry')
        if random.Random(stable_seed(seed, acquired, 'select')).random() >= .25:
            continue
        reported = deepcopy(original)
        if profile == 'noisy_25':
            rng = random.Random(stable_seed(seed, acquired, 'noise'))
            for axis, size in (('x', 'width'), ('y', 'height')):
                reported[axis] = min(math.nextafter(grid[axis] + grid[size], -math.inf),
                    max(grid[axis], original[axis] + rng.gauss(0, 2.0)))
            reported['observed_at_ms'] = min(end_ms - 1, max(1, acquired + rng.randint(-200, 200)))
            reported['cell_id'] = cell_id(reported['x'], reported['y'], grid)
        result.append(dict(acquired_at_ms=acquired,
            available_at_ms=max(acquired, reported['observed_at_ms']), reported=reported))
    return result


def knowledge_at(events, now_ms):
    """Gate first, then deduplicate public triples and strip acquisition metadata."""
    _integer(now_ms, 'now_ms')
    if not isinstance(events, list):
        raise ValueError('events must be a list')
    points = {}
    for event in events:
        if not isinstance(event, dict) or set(event) != EVENT_KEYS:
            raise ValueError('Knowledge event has missing or unknown/private fields')
        acquired = _integer(event['acquired_at_ms'], 'acquired_at_ms', 1)
        available = _integer(event['available_at_ms'], 'available_at_ms', 1)
        point = _point(event['reported'])
        if available != max(acquired, point['observed_at_ms']):
            raise ValueError('Knowledge availability violates acquisition/reported-time provenance')
        if available <= now_ms:
            key = (point['observed_at_ms'], point['x'], point['y'])
            points.setdefault(key, deepcopy(point))
    return [points[key] for key in sorted(points)]


def public_view(public, now_ms, *, recent_window_ms=None):
    """Return whole immutable releases received by now; never clip their support.

    Recent arrival blocks are (now-window,now], and cumulative views use seal<=now.
    Header horizon/coverage remain fixed. Reindex aliases AFTER filtering so indices
    cannot disclose unseen future records. Input objects are never mutated.
    """
    _validated_public(public)
    _integer(now_ms, 'now_ms')
    if now_ms > public['end_ms']:
        raise ValueError('Checkpoint exceeds the fixed public horizon')
    if recent_window_ms is not None:
        _integer(recent_window_ms, 'recent_window_ms', 1)
    result = _public_subset(public, now_ms, recent_window_ms)
    _validated_public(result)
    return result


def _public_subset(public, now_ms, recent_window_ms=None):
    """Copy whole ordered records from an already validated public transcript."""
    result = deepcopy({key: value for key, value in public.items() if key != 'releases'})
    result['releases'] = []
    for release in public['releases']:
        if release['sealed_at_ms'] > now_ms:
            continue
        if recent_window_ms is not None and release['sealed_at_ms'] <= now_ms - recent_window_ms:
            continue
        copied = deepcopy(release)
        copied['release_id'] = 'release-'+str(len(result['releases'])).zfill(6)
        result['releases'].append(copied)
    return result


def auxiliary_features(knowledge):
    """Nine public-coordinate/reported-time features; population standard deviation."""
    if not isinstance(knowledge, list):
        raise ValueError('knowledge must be a list')
    for point in knowledge:
        _point(point)
    points = sorted(knowledge, key=lambda p: (p['observed_at_ms'], p['x'], p['y']))
    if not points:
        return [0.0] * len(AUXILIARY_NAMES)
    count = len(points)
    x, y, times = ([point[key] for point in points] for key in ('x', 'y', 'observed_at_ms'))
    mx, my = math.fsum(x)/count, math.fsum(y)/count
    values = [count, mx, my,
        math.sqrt(math.fsum((value-mx)**2 for value in x)/count),
        math.sqrt(math.fsum((value-my)**2 for value in y)/count),
        min(times), max(times), math.fsum(times)/count,
        math.hypot(points[-1]['x']-points[0]['x'], points[-1]['y']-points[0]['y'])]
    if any(not math.isfinite(value) for value in values):
        raise ValueError('Auxiliary feature arithmetic is nonfinite')
    return [float(value) for value in values]


def feature_names(view):
    if view not in VIEWS:
        raise ValueError('Unknown causal feature view')
    names = ['auxiliary.'+name for name in AUXILIARY_NAMES]
    if view != 'auxiliary':
        names += ['recent.'+name for name in legacy_feature_names(True)]
    if view == 'history':
        names += ['cumulative.'+name for name in legacy_feature_names(True)]
    return names


def feature_views(public, events, now_ms):
    """Return nested auxiliary9, recent40 and history71 public-only features."""
    known = knowledge_at(events, now_ms)
    auxiliary = auxiliary_features(known)
    recent = public_view(public, now_ms, recent_window_ms=RECENT_WINDOW_MS)
    cumulative = public_view(public, now_ms)
    recent_values = auxiliary + feature_vector(recent, known, include_geometry=True)
    return dict(auxiliary=auxiliary, recent=recent_values,
                history=recent_values + feature_vector(cumulative, known, include_geometry=True))


def feature_views_many(public, events_by_profile, checkpoints=CHECKPOINTS):
    """Batch strict-equivalent views with one complete-transcript validation.

    A validated transcript stays valid when whole records are selected in order,
    the fixed public header is retained, and aliases are normalized. Construct
    these private, detached subsets once per checkpoint and reuse them across
    knowledge profiles. Every knowledge list is still strictly validated before
    entering unchanged legacy feature arithmetic. Only new numeric lists escape;
    no internal transcript, event, or caller-owned mutable object is returned.
    """
    _validated_public(public)
    if not isinstance(events_by_profile, dict) or not events_by_profile:
        raise ValueError('events_by_profile must be a nonempty profile/event mapping')
    if any(profile not in PROFILES for profile in events_by_profile):
        raise ValueError('Unknown causal knowledge profile')
    if not isinstance(checkpoints, (tuple, list)) or not checkpoints:
        raise ValueError('checkpoints must be a nonempty list or tuple')
    for checkpoint in checkpoints:
        _integer(checkpoint, 'checkpoint')
        if checkpoint > public['end_ms']:
            raise ValueError('Checkpoint exceeds the fixed public horizon')
    if list(checkpoints) != sorted(set(checkpoints)):
        raise ValueError('Checkpoints must be strictly increasing and unique')
    result = {profile: {} for profile in events_by_profile}
    for checkpoint in checkpoints:
        recent = _public_subset(public, checkpoint, RECENT_WINDOW_MS)
        cumulative = _public_subset(public, checkpoint)
        for profile, events in events_by_profile.items():
            known = knowledge_at(events, checkpoint)
            auxiliary = auxiliary_features(known)
            recent_values = auxiliary + _feature_vector_validated(recent, known, True)
            result[profile][checkpoint] = dict(auxiliary=auxiliary, recent=recent_values,
                history=recent_values + _feature_vector_validated(cumulative, known, True))
    return result


# Equivalent explicit name for callers that organize features as a profile/time grid.
feature_grid = feature_views_many
