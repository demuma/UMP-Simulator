#!/usr/bin/env python3
"""Independently check precise door lifecycle and body separation in a local capture.

Private native GT is evaluation evidence only; no identities are returned in the
compact report. This does not replace the normal mapped export/policy verifier.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import yaml
from shapely.geometry import LineString, Point


def require(condition, message):
    if not condition:
        raise ValueError(message)


def epoch_ms(text):
    parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Native timestamps require an explicit timezone')
    return round(parsed.timestamp() * 1000)


def audit(cfg, raw, tolerance=1e-4):
    scene = cfg['mapped_scene']
    portals = {p['id']: p for p in scene.get('portals', [])}
    require(len(portals) >= 2, 'At least two explicit building portals are required')
    require(len({p['building_id'] for p in portals.values()}) >= 2,
            'Visit targets must include at least two distinct buildings')
    routes = {r['id']: r for r in scene['routes']}
    lines = {key: LineString(route['points']) for key, route in routes.items()}
    episodes = {}
    radii, speeds = {}, {}
    planned = Counter()
    for person in scene['people']:
        previous = None
        for episode in person['episodes']:
            track = episode['track_id']
            require(track not in episodes, 'Duplicate configured episode')
            route = routes[episode['route_id']]
            episodes[track] = episode
            radii[track] = person['radius_m']
            speeds[track] = person['speed_mps']
            if route.get('end_portal') in portals:
                planned[route['end_portal']] += 1
            for field, index in [('start_portal', 0), ('end_portal', -1)]:
                if route.get(field) in portals:
                    portal = portals[route[field]]
                    require(math.dist(route['points'][index], portal['point']) <= tolerance,
                            'Route endpoint differs from its exact door point')
            if previous is not None:
                before = routes[previous['route_id']]
                require(before['end_portal'] in portals and route['start_portal'] in portals
                        and portals[before['end_portal']]['building_id']
                            == portals[route['start_portal']]['building_id'],
                        'Return episode changes its declared building')
            previous = episode
    metadata = [row for row in raw['agents'] if row.get('data_type') == 'metadata']
    require(len(metadata) == 1, 'One source origin is required')
    origin = epoch_ms(metadata[0]['timestamp'])
    step_ms = round(cfg['simulation']['time_step'] * 1000)
    frames, tracks = defaultdict(list), defaultdict(list)
    event_rows = []
    max_route_error = 0.0
    for row in raw['agents']:
        if row.get('data_type') == 'mapped lifecycle event':
            event_rows.append(row)
        if row.get('data_type') != 'agent data':
            continue
        track = row['agent_id']
        require(track in episodes, 'GT contains an undeclared track')
        at = epoch_ms(row['timestamp']) - origin
        point = [row['position']['x'], row['position']['y']]
        error = lines[episodes[track]['route_id']].distance(Point(point))
        max_route_error = max(max_route_error, error)
        require(error <= tolerance, 'Observed position leaves its declared route')
        frames[at].append((track, point))
        tracks[track].append((at, point))
    for rows in tracks.values():
        rows.sort()
    clearance = scene['motion'].get('clearance_m', .1)
    minimum_margin = math.inf
    compared = 0
    for rows in frames.values():
        for i, (first, a) in enumerate(rows):
            for second, b in rows[i + 1:]:
                margin = math.dist(a, b) - radii[first] - radii[second] - clearance
                minimum_margin = min(minimum_margin, margin)
                compared += 1
                require(margin >= -tolerance, 'Independent GT body-clearance violation')
    counts = {key: {'planned_entries': planned[key], 'completed_entries': 0,
                    'realized_exits': 0, 'max_start_distance_m': 0.0,
                    'max_last_frame_distance_m': 0.0} for key in portals}
    events = {}
    for event in event_rows:
        track = event['observation_track_id']
        require(track in episodes, 'Lifecycle event contains an undeclared track')
        kind = event['event']
        require(kind in ['visible_start', 'visible_end'], 'Unknown lifecycle kind')
        require((track, kind) not in events, 'Duplicate lifecycle event')
        events[(track, kind)] = event
        route = routes[episodes[track]['route_id']]
        portal_id = route['start_portal' if kind == 'visible_start' else 'end_portal']
        require(event['portal_id'] == portal_id, 'Lifecycle event uses a different portal')
        if portal_id not in portals:
            continue
        point = portals[portal_id]['point']
        at = epoch_ms(event['timestamp']) - origin
        rows = tracks[track]
        require(rows, 'Door event has no observed outdoor episode')
        if kind == 'visible_start':
            require(rows[0][0] == at, 'Exit has no matching first outdoor frame')
            distance = math.dist(rows[0][1], point)
            require(distance <= tolerance, 'Building exit does not start at its exact door')
            counts[portal_id]['realized_exits'] += 1
            counts[portal_id]['max_start_distance_m'] = max(counts[portal_id]['max_start_distance_m'], distance)
        else:
            require(rows[-1][0] == at - step_ms, 'Entry does not follow the final outdoor step')
            distance = math.dist(rows[-1][1], point)
            require(distance <= speeds[track] * step_ms / 1000 + tolerance,
                    'Road user disappears before reaching its exact door')
            counts[portal_id]['completed_entries'] += 1
            counts[portal_id]['max_last_frame_distance_m'] = max(counts[portal_id]['max_last_frame_distance_m'], distance)
    visited_buildings = {portals[key]['building_id'] for key, row in counts.items()
                         if row['completed_entries'] > 0}
    exited_buildings = {portals[key]['building_id'] for key, row in counts.items()
                        if row['realized_exits'] > 0}
    require(len(visited_buildings) >= 2 and len(exited_buildings) >= 2,
            'Acceptance requires realized entry and return at two distinct buildings')
    minimum_gap = math.inf
    for person in scene['people']:
        for previous, following in zip(person['episodes'], person['episodes'][1:]):
            begin = events.get((following['track_id'], 'visible_start'))
            if begin is None:
                continue
            end = events.get((previous['track_id'], 'visible_end'))
            require(end is not None, 'Return starts before an entry event exists')
            gap = epoch_ms(begin['timestamp']) - epoch_ms(end['timestamp'])
            require(gap >= following['after_previous_ms'], 'Return precedes its realized indoor gap')
            minimum_gap = min(minimum_gap, gap)
    return {'status': 'pass', 'independent_gt_body_pair_checks': compared,
            'minimum_body_clearance_margin_m': None if minimum_margin == math.inf else minimum_margin,
            'maximum_observed_route_distance_m': max_route_error,
            'minimum_realized_hidden_gap_ms': None if minimum_gap == math.inf else minimum_gap,
            'targets_with_completed_entries': sum(row['completed_entries'] > 0 for row in counts.values()),
            'buildings_with_completed_entries': len(visited_buildings),
            'buildings_with_realized_exits': len(exited_buildings),
            'all_planned_entries_completed': all(row['completed_entries'] == row['planned_entries'] for row in counts.values()),
            'portals': counts,
            'scope': 'All stored native source frames, route containment, pairwise circular body+clearance separation, exact portal lifecycle and realized indoor timing; no private identities in this report.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Choose a fresh compact output file')
    config_path = args.scene / 'config.yaml'
    raw_path = args.replay / 'private/native_source.json'
    result = audit(yaml.safe_load(config_path.read_text()), json.loads(raw_path.read_text()))
    result['config_sha256'] = hashlib.sha256(config_path.read_bytes()).hexdigest()
    result['native_source_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
