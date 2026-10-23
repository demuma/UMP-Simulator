#!/usr/bin/env python3
"""Audit track/person support and controlled fragmentation on one local recording.

No database or network access. GT linkage is an independent evaluation oracle,
never an operational sensor capability. Generated observations/results remain
local and must not be committed. Optional reruns use the maintained C++ core.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess

import yaml

MAX_BYTES = 256 * 1024 * 1024
EPS = 1e-7


def insist(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest_value(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    path = Path(path)
    insist(path.is_file() and path.stat().st_size <= MAX_BYTES, 'Input must be a regular file of at most 256 MiB')
    return json.loads(path.read_text())


def write_json(path, value):
    data = (canonical(value) + '\n').encode()
    insist(len(data) <= MAX_BYTES, 'Analysis artifact exceeds 256 MiB')
    with Path(path).open('xb') as stream:
        stream.write(data)


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def integer(value):
    return type(value) is int


def epoch_ms(text):
    parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    insist(parsed.tzinfo is not None, 'Private GT timestamp requires an explicit UTC offset')
    return round(parsed.timestamp() * 1000)


def replay_config(cfg):
    """Keep actual hard rules/execution; adapt normal Region definitions to replay."""
    sensors = [s for s in cfg['sensors'] if s['type'] == 'adaptive-grid-based']
    insist(len(sensors) == 1, 'Analysis requires exactly one enabled AGBS configuration')
    aggregation = copy.deepcopy(sensors[0]['aggregation'])
    allowed = {'application_id', 'window_ms', 'max_observations_per_window', 'history', 'spatial_selection',
               'temporal_adaptation', 'metric_policy', 'policy_tree', 'policy_regions', 'semantic_taxonomy'}
    adapter_only = {'enabled', 'publication', 'diagnostics', 'diagnostics_directory'}
    insist(set(aggregation).issubset(allowed | adapter_only), 'Unsupported production aggregation option for replay adaptation')
    insist(aggregation.get('enabled', True) is True, 'Recording aggregation must be enabled')
    # Replay has an in-memory publication coordinator; production DB/file sinks
    # are not valid replay configuration options and cannot affect hard policy.
    for key in adapter_only:
        aggregation.pop(key, None)
    tree = aggregation['policy_tree']
    types = {row['type']: row for row in cfg.get('region_taxonomy', [])}
    definitions = {row['id']: row for row in cfg.get('regions', [])}
    insist(len(types) == len(cfg.get('region_taxonomy', []))
           and len(definitions) == len(cfg.get('regions', [])), 'Duplicate Region/type definitions')
    selected = tree['regions']
    insist(len(set(selected)) == len(selected), 'Duplicate selected Region reference')
    adapted = []
    for reference in selected:
        insist(reference in definitions, 'Unknown selected Region reference')
        region = definitions[reference]
        insist(region['type'] in types, 'Unknown selected Region type')
        adapted.append({'id': region['id'], 'type': region['type'], **copy.deepcopy(region['area']),
                        'type_requirements': copy.deepcopy(types[region['type']].get('metric_requirements', {})),
                        'requirements': copy.deepcopy(region.get('metric_requirements', {}))})
    aggregation['policy_regions'] = adapted
    insist(set(aggregation).issubset(allowed), 'Replay adapter emitted an unsupported configuration option')
    return aggregation


def decoded_cell(cell_id, coverage, depth=None):
    depth = coverage['leaf_depth'] if depth is None else depth
    insist(integer(cell_id) and integer(depth) and 1 <= depth <= coverage['leaf_depth']
           and cell_id >> (2 * depth) == 3, 'Invalid canonical quadtree cell ID/depth')
    x, y = coverage['x'], coverage['y']
    side = coverage['width']
    for level in range(depth - 1, -1, -1):
        side /= 2
        quadrant = (cell_id >> (2 * level)) & 3
        x += (quadrant & 1) * side
        y += (quadrant >> 1) * side
    return {'cell_id': cell_id, 'depth': depth, 'x': x, 'y': y, 'width': side, 'height': side}


def inside(observation, cell):
    return (cell['x'] <= observation['x'] < cell['x'] + cell['width']
            and cell['y'] <= observation['y'] < cell['y'] + cell['height'])


def audit_stream(observations):
    insist(observations['schema'] == 'ump.observation-replay.v1', 'Unsupported observation replay schema')
    coverage = observations['coverage']
    insist(all(finite(coverage[k]) for k in ('x', 'y', 'width', 'height'))
           and coverage['width'] > 0 and coverage['width'] == coverage['height']
           and integer(coverage['leaf_depth']) and 1 <= coverage['leaf_depth'] <= 14, 'Invalid observation coverage')
    period, end = observations['sampling_period_ms'], observations['end_ms']
    insist(integer(period) and period > 0 and integer(end) and end > 0, 'Invalid observation clock')
    physical, occupancy, total = [], [], 0
    previous_sequence, previous_time = 0, 0
    times = []
    for batch in observations['batches']:
        time, sequence = batch['observed_at_ms'], batch['sequence']
        insist(integer(time) and previous_time < time < end and time % period == 0
               and integer(sequence) and sequence > previous_sequence, 'Off-cadence or unordered observation batch')
        insist(batch['status'] in ('measured', 'unavailable'), 'Unknown observation status')
        insist(batch['status'] == 'measured' or not batch['observations'], 'Unavailable batch contains observations')
        ids, physical_rows, counts = set(), [], Counter()
        for item in batch['observations']:
            insist(isinstance(item['id'], str) and item['id'] and item['id'] not in ids
                   and isinstance(item['type'], str) and item['type'], 'Empty or duplicate observation identity/type')
            ids.add(item['id'])
            insist(finite(item['x']) and finite(item['y']), 'Nonfinite observation coordinate')
            cell = decoded_cell(item['cell_id'], coverage)
            insist(inside(item, cell), 'Observation coordinates disagree with their cell ID')
            physical_rows.append([item['type'], item['cell_id'], item['x'], item['y']])
            counts[(item['cell_id'], item['type'])] += 1
        physical.append([sequence, time, batch['status'], sorted(physical_rows)])
        occupancy.append([sequence, time, batch['status'], sorted([*key, count] for key, count in counts.items())])
        total += len(batch['observations'])
        previous_sequence, previous_time = sequence, time
        times.append(time)
    scope = {k: observations[k] for k in ('coverage', 'sampling_period_ms', 'end_ms')}
    return {'observation_contributions': total, 'batches': len(times),
            'complete_scheduled_batches': times == list(range(period, end, period)),
            'position_type_cadence_sha256': digest_value([scope, physical]),
            'occupancy_type_sha256': digest_value([scope, occupancy])}


def private_registry(raw, observations):
    """Independently match every replay observation to its private native GT row."""
    metadata = [r for r in raw['agents'] if r.get('data_type') == 'metadata']
    insist(len(metadata) == 1, 'Exactly one private source metadata record required')
    origin = epoch_ms(metadata[0]['timestamp'])
    mapping, frames = {}, {}
    for row in raw['agents']:
        if row.get('data_type') != 'agent data':
            continue
        track, person = row['agent_id'], row.get('private_person_id')
        insist(isinstance(person, str) and person and row.get('observation_track_id') == track,
               'Private GT identity boundary is missing')
        insist(mapping.setdefault(track, person) == person, 'One observation track maps to multiple private people')
        key = (epoch_ms(row['timestamp']) - origin, track)
        insist(key not in frames, 'Duplicate private source track/time')
        frames[key] = row
    for batch in observations['batches']:
        people = set()
        for observation in batch['observations']:
            row = frames.get((batch['observed_at_ms'], observation['id']))
            insist(row is not None and row['type'] == observation['type']
                   and row['position']['x'] == observation['x'] and row['position']['y'] == observation['y'],
                   'Observation replay differs from private native position/type/time')
            person = mapping[observation['id']]
            insist(person not in people, 'Private person has multiple simultaneous observation tracks')
            people.add(person)
    return mapping


def verify_recording(recording):
    """Validate the completed capture and all pinned artifacts before a rerun."""
    recording = Path(recording).resolve()
    proof = read_json(recording / 'capture-proof.json')
    insist(proof.get('schema') == 'ump.mapped-recording-proof.v1'
           and proof.get('status') == 'verified' and proof.get('source_completed') is True,
           'Require a completed verified mapped recording')
    hashes = proof.get('files_sha256')
    required = {'observations.json', 'native_result.json', 'private/native_source.json',
                'private/config.yaml', 'map_background.png', 'bundle.json'}
    insist(isinstance(hashes, dict) and required.issubset(hashes), 'Incomplete recording digest set')
    for name, expected in hashes.items():
        insist(isinstance(name, str) and name and '\\' not in name and not Path(name).is_absolute()
               and all(part not in ('', '.', '..') for part in name.split('/')),
               'Recording artifact path must be canonical and relative')
        path = (recording / name).resolve()
        insist(path.is_relative_to(recording) and path.is_file() and path.stat().st_size <= MAX_BYTES
               and isinstance(expected, str) and re.fullmatch(r'[0-9a-f]{64}', expected)
               and digest_file(path) == expected, 'Changed, malformed or escaping recording artifact')
    server = Path(__file__).resolve().parents[2] / 'tools/replay_viewer/serve.py'
    spec = importlib.util.spec_from_file_location('ump_track_source_bundle_validation', server)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    validator.validate_bundle(recording)
    return hashes


def identity_variant(source, registry, interval_ms=None, oracle=False):
    insist(not oracle or interval_ms is None, 'Oracle and fragmentation are separate experimental variants')
    insist(interval_ms is None or integer(interval_ms) and interval_ms > 0, 'Fragmentation interval must be positive milliseconds')
    result, mapping = copy.deepcopy(source), {}
    for batch in result['batches']:
        for item in batch['observations']:
            original = item['id']
            insist(original in registry, 'Observation identity has no private evaluation reference')
            person = registry[original]
            if oracle:
                token = 'oracle-' + digest_value(['evaluation-person-reference-v1', person])
            elif interval_ms is not None:
                token = 'fragment-' + digest_value(['aligned-track-fragmentation-v1', original,
                                                  interval_ms, batch['observed_at_ms'] // interval_ms])
            else:
                token = original
            item['id'] = token
            insist(mapping.setdefault(token, person) == person, 'Identity variant token collision')
    source_audit, variant_audit = audit_stream(source), audit_stream(result)
    insist(source_audit == variant_audit, 'Identity intervention changed positions, types, cadence or occupancy')
    return result, mapping, variant_audit


def tighten(target, additions):
    for metric, bounds in additions.items():
        value = target.setdefault(metric, {})
        if 'min' in bounds:
            value['min'] = max(value.get('min', -math.inf), bounds['min'])
        if 'max' in bounds:
            value['max'] = min(value.get('max', math.inf), bounds['max'])


def effective_bounds(config, cell):
    result = copy.deepcopy(config['policy_tree']['root'])
    for region in config.get('policy_regions', []):
        width = min(cell['x'] + cell['width'], region['x'] + region['width']) - max(cell['x'], region['x'])
        height = min(cell['y'] + cell['height'], region['y'] + region['height']) - max(cell['y'], region['y'])
        if width > 0 and height > 0:
            tighten(result, region.get('type_requirements', {}))
            tighten(result, region.get('requirements', {}))
    return result


def taxonomy_index(config):
    taxonomy = config.get('semantic_taxonomy')
    if not taxonomy:
        return {}, {}
    nodes = {node['id']: node for node in taxonomy['nodes']}
    insist(len(nodes) == len(taxonomy['nodes']), 'Duplicate taxonomy node')
    leaves = {}
    for node in nodes.values():
        seen, current = set(), node
        while current is not None:
            insist(current['id'] not in seen, 'Cyclic semantic taxonomy')
            seen.add(current['id'])
            if current.get('parent') is None:
                break
            insist(current['parent'] in nodes, 'Unknown semantic parent')
            current = nodes[current['parent']]
        for label in node.get('input_types', []):
            insist(label not in leaves, 'Duplicate raw semantic label')
            leaves[label] = node['id']
    return nodes, leaves


def is_descendant(nodes, category, leaf):
    while leaf is not None:
        if leaf == category:
            return True
        leaf = nodes[leaf].get('parent')
    return False


def support(rows, registry):
    tracks, people, tracks_per_time, people_per_time = set(), set(), {}, {}
    for time, observation in rows:
        track = observation['id']
        insist(track in registry, 'Observation has no evaluation-only person reference')
        person = registry[track]
        tracks.add(track); people.add(person)
        tracks_per_time.setdefault(time, set()).add(track)
        people_per_time.setdefault(time, set()).add(person)
    return {'n_track': len(tracks), 'n_gt': len(people),
            'peak_concurrent_tracks': max(map(len, tracks_per_time.values()), default=0),
            'peak_concurrent_gt': max(map(len, people_per_time.values()), default=0),
            'track_to_person_ratio': ratio(len(tracks), len(people))}


def within(value, bounds):
    return bounds.get('min', -math.inf) - EPS <= value <= bounds.get('max', math.inf) + EPS


def flattened_counts(cell):
    counts = cell.get('counts', cell)
    return (counts['observation_contributions'],
            counts.get('distinct_contributors', counts.get('distinct_road_users')),
            counts.get('mean_sample_occupancy'))


def audit_releases(observations, result, config, registry):
    """Audit every public count/category/rule; compute private support diagnostics."""
    stream = audit_stream(observations)
    insist(result['schema'] == 'ump.replay-result.v1', 'Unsupported result schema')
    insist(result['input_observation_contributions'] == stream['observation_contributions'], 'Result input denominator mismatch')
    insist(result['source']['coverage'] == observations['coverage']
           and result['source']['sampling_period_ms'] == observations['sampling_period_ms']
           and result['source']['end_ms'] == observations['end_ms'], 'Result source differs from observation stream')
    nodes, leaves = taxonomy_index(config)
    times = [batch['observed_at_ms'] for batch in observations['batches']]
    cells, support_ratios, semantic_bins = [], [], 0
    selected_contributions = 0
    weighted_side = weighted_duration = weighted_delay = weighted_age = weighted_semantic = 0.
    ledger = {}
    for release_index, release in enumerate(result['releases']):
        start, end, sealed = release['start_ms'], release['end_ms'], release['sealed_at_ms']
        insist(all(integer(t) for t in (start, end, sealed))
               and 0 <= start < end <= observations['end_ms'] and sealed >= end, 'Invalid published interval')
        insist(release['policy_id'] == config['policy_tree']['id']
               and release['policy_version'] == config['policy_tree']['version'], 'Published policy identity mismatch')
        section = observations['batches'][bisect_left(times, start):bisect_left(times, end)]
        period = observations['sampling_period_ms']
        first = max(period, ((start + period - 1) // period) * period)
        expected = len(range(first, end, period))
        insist(expected > 0 and len(section) == expected and all(b['status'] == 'measured' for b in section),
               'Publication lacks complete measured sample coverage')
        for cell_index, cell in enumerate(release['cells']):
            geometry = decoded_cell(cell['cell_id'], observations['coverage'], cell['depth'])
            insist(all(finite(cell[k]) and abs(cell[k] - geometry[k]) <= EPS
                       for k in ('x', 'y', 'width', 'height')), 'Published cell geometry disagrees with canonical ID')
            # Expand the small canonical domain to leaf IDs for an independent
            # public support ledger, rather than trusting controller ownership.
            shift = 2 * (observations['coverage']['leaf_depth'] - cell['depth'])
            for leaf_id in range(cell['cell_id'] << shift, (cell['cell_id'] + 1) << shift):
                intervals = ledger.setdefault(leaf_id, [])
                insist(all(end <= old_start or start >= old_end for old_start, old_end in intervals),
                       'Public releases overlap in space-time')
                intervals.append((start, end))
            observed = [(b['observed_at_ms'], item) for b in section for item in b['observations'] if inside(item, geometry)]
            counters = support(observed, registry)
            contributions, distinct, occupancy = flattened_counts(cell)
            insist(integer(contributions) and integer(distinct)
                   and contributions == len(observed) and distinct == counters['n_track'] and observed
                   and finite(occupancy) and abs(occupancy - len(observed) / expected) <= EPS,
                   'Published scalar counts differ from independent observations')
            bounds = effective_bounds(config, geometry)
            bins, assigned, weighted_loss, maximum_loss = [], set(), 0., 0.
            semantic = cell.get('semantic')
            if semantic is not None:
                taxonomy = config['semantic_taxonomy']
                insist(semantic['taxonomy_id'] == taxonomy['id'] and semantic['taxonomy_version'] == taxonomy['version'],
                       'Published semantic taxonomy mismatch')
                category_ids = set()
                for category in semantic['categories']:
                    category_id = category['category_id']
                    insist(category_id in nodes and category_id not in category_ids, 'Unknown or duplicate published category')
                    category_ids.add(category_id)
                    indices = set()
                    for index, (_, item) in enumerate(observed):
                        insist(item['type'] in leaves, 'Raw observation type has no taxonomy terminal')
                        if is_descendant(nodes, category_id, leaves[item['type']]):
                            indices.add(index)
                    insist(indices and not assigned.intersection(indices), 'Empty or overlapping semantic partition')
                    assigned.update(indices)
                    members = [observed[index] for index in sorted(indices)]
                    counter = support(members, registry)
                    insist(integer(category['observation_contributions']) and integer(category['distinct_contributors'])
                           and category['observation_contributions'] == len(members)
                           and category['distinct_contributors'] == counter['n_track'], 'Published semantic count mismatch')
                    requirement = bounds.get('min_category_distinct_contributors', {})
                    bins.append({'category_id': category_id, 'observation_contributions': len(members), **counter,
                                 'required_minimum_track_support': requirement.get('min'),
                                 'false_person_threshold_pass': (within(counter['n_track'], requirement)
                                                               and not within(counter['n_gt'], requirement))})
                    cost = nodes[category_id]['loss']
                    maximum_loss = max(maximum_loss, cost); weighted_loss += len(members) * cost
                insist(len(assigned) == len(observed) and bins, 'Semantic representation omitted observations')
                minimum_track = min(b['n_track'] for b in bins)
                insist(semantic['min_category_distinct_contributors'] == minimum_track
                       and abs(semantic['semantic_max_loss'] - maximum_loss) <= EPS
                       and abs(semantic['semantic_mean_loss'] - weighted_loss / len(observed)) <= EPS,
                       'Published semantic summaries differ from their partition')
            else:
                minimum_track = None
            metrics = {'observation_contributions': len(observed), 'distinct_contributors': counters['n_track'],
                       'mean_sample_occupancy': len(observed) / expected, 'cell_side_m': geometry['width'],
                       'cell_area_m2': geometry['width'] * geometry['height'], 'window_duration_ms': end - start,
                       'age_at_evaluation_ms': sealed - start, 'post_window_delay_ms': sealed - end,
                       'measured_sample_fraction': 1}
            if bins:
                metrics.update(min_category_distinct_contributors=minimum_track, semantic_max_loss=maximum_loss,
                               semantic_mean_loss=weighted_loss / len(observed))
            insist(all(metric in metrics and within(metrics[metric], requirement) for metric, requirement in bounds.items()),
                   'Publication violates an independently resolved effective policy')
            oracle_metrics = {**metrics, 'distinct_contributors': counters['n_gt']}
            peak_metrics = {**metrics, 'distinct_contributors': counters['peak_concurrent_gt']}
            if bins:
                oracle_metrics['min_category_distinct_contributors'] = min(b['n_gt'] for b in bins)
                peak_metrics['min_category_distinct_contributors'] = min(b['peak_concurrent_gt'] for b in bins)
            person_failures = [metric for metric in ('distinct_contributors', 'min_category_distinct_contributors')
                               if metric in bounds and not within(oracle_metrics[metric], bounds[metric])]
            peak_failures = [metric for metric in ('distinct_contributors', 'min_category_distinct_contributors')
                             if metric in bounds and not within(peak_metrics[metric], bounds[metric])]
            cells.append({'release_index': release_index, 'cell_index': cell_index, **geometry,
                          'start_ms': start, 'end_ms': end, 'sealed_at_ms': sealed,
                          'observation_contributions': len(observed), **counters,
                          'effective_bounds': bounds, 'semantic_bins': bins,
                          'false_person_threshold_pass': bool(person_failures),
                          'person_threshold_failures': person_failures,
                          'diagnostic_peak_would_fail_support': bool(peak_failures),
                          'diagnostic_peak_failure_metrics': peak_failures})
            support_ratios.append(counters['track_to_person_ratio'])
            semantic_bins += len(bins); selected_contributions += len(observed)
            weighted_side += len(observed) * geometry['width']; weighted_duration += len(observed) * (end - start)
            weighted_delay += len(observed) * (sealed - end); weighted_age += len(observed) * (sealed - start)
            weighted_semantic += weighted_loss
    false_cells = sum(c['false_person_threshold_pass'] for c in cells)
    inflated = sum(c['n_track'] != c['n_gt'] for c in cells)
    false_bins = sum(b['false_person_threshold_pass'] for c in cells for b in c['semantic_bins'])
    summary = {'status': 'verified', 'published_cell_windows': len(cells), 'published_semantic_bins': semantic_bins,
               'published_observation_contributions': selected_contributions,
               'input_observation_contributions': stream['observation_contributions'],
               'retained_observation_fraction': ratio(selected_contributions, stream['observation_contributions']),
               'track_person_inflated_cell_windows': inflated, 'inflated_cell_fraction': ratio(inflated, len(cells)),
               'false_person_threshold_pass_cell_windows': false_cells,
               'false_person_threshold_pass_cell_fraction': ratio(false_cells, len(cells)),
               'false_person_threshold_pass_semantic_bins': false_bins,
               'false_person_threshold_pass_semantic_bin_fraction': ratio(false_bins, semantic_bins),
               'diagnostic_peak_would_fail_support_cell_windows': sum(c['diagnostic_peak_would_fail_support'] for c in cells),
               'maximum_track_to_person_ratio': max(support_ratios, default=None),
               'mean_cell_track_to_person_ratio': ratio(sum(support_ratios), len(support_ratios)),
               'contribution_weighted_mean_cell_side_m': ratio(weighted_side, selected_contributions),
               'contribution_weighted_mean_window_ms': ratio(weighted_duration, selected_contributions),
               'contribution_weighted_mean_post_window_delay_ms': ratio(weighted_delay, selected_contributions),
               'contribution_weighted_mean_age_ms': ratio(weighted_age, selected_contributions),
               'contribution_weighted_mean_semantic_cost': ratio(weighted_semantic, selected_contributions) if nodes else None,
               'checked_operational_policy_violations': 0, 'public_spacetime_overlaps': 0,
               'peak_metric_scope': 'Diagnostic maximum simultaneous sampled modeled-person support only; not an implemented policy variant or proof of privacy.',
               'utility_scope': 'Observation retention and weighted representation/delay summaries; no task-query error or measured privacy risk.'}
    return summary, cells


def logical_release_hash(result):
    """Ignore run-dependent release identifiers and generated effective policy IDs."""
    def numbers(value):
        # MongoDB JSON and C++ JSON may spell an equal numeric value as 5.0 or
        # 5. This normalization must not turn equivalent releases into a mismatch.
        if isinstance(value, float) and math.isfinite(value) and value.is_integer():
            return int(value)
        if isinstance(value, list):
            return [numbers(item) for item in value]
        if isinstance(value, dict):
            return {key: numbers(item) for key, item in value.items()}
        return value
    releases = []
    for release in result['releases']:
        cells = []
        for cell in release['cells']:
            contributions, distinct, occupancy = flattened_counts(cell)
            row = {k: cell[k] for k in ('cell_id', 'depth', 'x', 'y', 'width', 'height')}
            row.update(observation_contributions=contributions, distinct_road_users=distinct,
                       mean_sample_occupancy=occupancy)
            if 'semantic' in cell:
                row['semantic'] = cell['semantic']
            cells.append(row)
        releases.append({'start_ms': release['start_ms'], 'end_ms': release['end_ms'],
                         'sealed_at_ms': release['sealed_at_ms'], 'cells': sorted(cells, key=canonical)})
    return digest_value(sorted(numbers(releases), key=canonical))


def analyze_recording(recording, output, binary=None):
    recording, output = Path(recording).resolve(), Path(output).resolve()
    insist(not output.exists(), 'Choose a new analysis output directory')
    repo = Path(__file__).resolve().parents[2]
    if output.is_relative_to(repo):
        insist(output.is_relative_to(repo / 'results'), 'Generated identity experiments must stay under ignored results/')
    pinned = verify_recording(recording)
    files = {name: recording / name for name in ('observations.json', 'native_result.json', 'private/native_source.json', 'private/config.yaml')}
    hashes = {name: digest_file(path) for name, path in files.items()}
    observations = read_json(files['observations.json']); native = read_json(files['native_result.json'])
    raw = read_json(files['private/native_source.json'])
    cfg = yaml.safe_load(files['private/config.yaml'].read_text())
    config = replay_config(cfg)
    source_audit = audit_stream(observations)
    raw_step_ms = cfg['simulation']['time_step'] * 1000
    insist(finite(raw_step_ms) and raw_step_ms > 0 and abs(raw_step_ms - round(raw_step_ms)) <= 1e-6,
           'Native progress clock must use positive whole milliseconds')
    progress_step_ms = round(raw_step_ms)
    insist(observations['sampling_period_ms'] % progress_step_ms == 0, 'Progress clock must divide the sensor period')
    registry = private_registry(raw, observations)
    native_summary, native_cells = audit_releases(observations, native, config, registry)
    variants = [('original_episodes', None, False), ('fragment_500ms', 500, False),
                ('fragment_1000ms', 1000, False), ('evaluation_oracle', None, True)]
    output.mkdir(parents=True, mode=0o700)
    private = output / 'private'; private.mkdir(mode=0o700)
    write_json(output / 'replay_policy.json', config)
    write_json(private / 'native_cell_support.json', native_cells)
    report = {'schema': 'ump.track-support-analysis.v1', 'classification': 'private_research_evaluation',
              'analyzer_sha256': digest_file(Path(__file__).resolve()),
              'input_sha256': hashes, 'recording_proof_sha256': digest_file(recording / 'capture-proof.json'),
              'source_invariants': source_audit, 'native': native_summary,
              'progress_clock': {'native_simulation_step_ms': progress_step_ms,
                                 'replay_progress_step_ms': progress_step_ms,
                                 'sampling_period_ms': observations['sampling_period_ms'],
                                 'includes_origin_advance': True,
                                 'scope': 'Replay uses every native numerical source tick, including no-measurement ticks; identity interventions preserve the same clock.'},
              'native_logical_release_sha256': logical_release_hash(native), 'variants': {},
              'interpretation': 'Track support is operational. GT person support is evaluator-only. False passes mean the same numeric track-support threshold would fail on modeled people, not a measured attack or k-anonymity proof.',
              'intervention': 'Only identity labels change. Fragment boundaries are global simulation-time multiples of the declared interval; positions, types, batches and cadence are fixed.',
              'oracle_scope': 'Stable GT identity variant is an explicitly privileged evaluation reference; never a sensor/aggregator capability or proposed production fix.'}
    if binary is not None:
        binary = Path(binary).resolve()
        insist(binary.is_file(), 'AggregationReplay binary is missing')
        report['replay_binary_sha256'] = digest_file(binary)
    for name, interval, oracle in variants:
        changed, mapping, invariants = identity_variant(observations, registry, interval, oracle)
        input_path = private / (name + '_observations.json')
        write_json(input_path, changed)
        row = {'scope': 'evaluation_oracle_only' if oracle else 'operational_identity_intervention',
               'fragmentation_interval_ms': interval, 'observations_sha256': digest_file(input_path),
               'source_invariants': invariants, 'rerun': 'not_requested'}
        if binary is not None:
            insist(digest_file(binary) == report['replay_binary_sha256'], 'Replay binary changed during analysis')
            destination = private / (name + '_result.json')
            mode = config['policy_tree']['execution']['strategy']
            command = [str(binary), '--input', str(input_path), '--config', str(output / 'replay_policy.json'),
                       '--mode', mode, '--progress-step-ms', str(progress_step_ms), '--output', str(destination)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=240)
            insist(completed.returncode == 0, 'C++ identity replay failed; private input/output artifacts retained for inspection')
            result = read_json(destination)
            insist(digest_file(binary) == report['replay_binary_sha256'], 'Replay binary changed during analysis')
            summary, cells = audit_releases(changed, result, config, mapping)
            write_json(private / (name + '_cell_support.json'), cells)
            row.update(rerun='verified', results=summary, result_sha256=digest_file(destination),
                       logical_release_sha256=logical_release_hash(result))
            if name == 'original_episodes':
                row['logical_releases_match_native'] = row['logical_release_sha256'] == report['native_logical_release_sha256']
        report['variants'][name] = row
    insist(hashes == {name: digest_file(path) for name, path in files.items()}, 'Recording changed during analysis')
    insist(pinned == verify_recording(recording)
           and digest_file(recording / 'capture-proof.json') == report['recording_proof_sha256'],
           'Recording proof changed during analysis')
    insist(digest_file(Path(__file__).resolve()) == report['analyzer_sha256'], 'Analyzer changed during analysis')
    write_json(output / 'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New ignored/local directory; never overwrite')
    parser.add_argument('--binary', type=Path, help='Optional existing AggregationReplay executable; run all identity variants')
    args = parser.parse_args()
    report = analyze_recording(args.recording, args.output, args.binary)
    print(canonical({'status': 'verified', 'output': str(args.output.resolve()),
                     'published_cell_windows': report['native']['published_cell_windows'],
                     'native_false_person_threshold_passes': report['native']['false_person_threshold_pass_cell_windows'],
                     'variant_reruns': args.binary is not None}))


if __name__ == '__main__':
    main()
