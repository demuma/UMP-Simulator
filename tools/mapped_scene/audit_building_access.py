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
from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep

from validate_source_access import connector_surface, validate_expanded_shop_context


def require(condition, message):
    if not condition:
        raise ValueError(message)


def epoch_ms(text):
    parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Native timestamps require an explicit timezone')
    return round(parsed.timestamp() * 1000)


def audit(cfg, raw, tolerance=1e-4, public_context=None, map_layers=None):
    scene = cfg['mapped_scene']
    local_navigation = scene.get('motion', {}).get('mode') == 'local_navigation'
    portals = {p['id']: p for p in scene.get('portals', [])}
    require(len(portals) >= 2, 'At least two explicit building portals are required')
    if not local_navigation:
        require(len({p['building_id'] for p in portals.values()}) >= 2,
                'Visit targets must include at least two distinct buildings')
    routes = {r['id']: r for r in scene['routes']}
    lines = {key: LineString(route['points']) for key, route in routes.items()}
    allowed = None
    allowed_by_space = {}
    space_modes={'':'walking','carriageway':'road'}
    for space in (public_context or {}).get('navigation',{}).get('spaces',[]):
        mode=space.get('mode','road' if space.get('id')=='carriageway' else None)
        require(mode in ('walking','cycling','road'), 'Public navigation space has no supported physical mode')
        space_modes[space['id']]=mode
    if local_navigation:
        navigation = scene['motion']['navigation']
        allowed = unary_union([Polygon(p['outer'], p.get('holes', []))
                               for p in navigation['allowed_center_polygons']])
        require(not allowed.is_empty and allowed.is_valid, 'Invalid allowed center geometry')
        allowed_by_space[''] = allowed.buffer(tolerance)
        for space in navigation.get('spaces', []):
            require(space['id'] not in allowed_by_space, 'Duplicate navigation space')
            geometry=unary_union([Polygon(p['outer'], p.get('holes', [])) for p in space['allowed_center_polygons']])
            require(not geometry.is_empty and geometry.is_valid, 'Invalid named allowed center geometry')
            allowed_by_space[space['id']]=geometry.buffer(tolerance)
    episodes = {}
    radii, speeds, track_portals, track_spaces = {}, {}, {}, {}
    planned = Counter()
    for person in scene['people']:
        previous = None
        for episode in person['episodes']:
            track = episode['track_id']
            require(track not in episodes, 'Duplicate configured episode')
            route = routes[episode['route_id']]
            episodes[track] = episode
            track_spaces[track] = route.get('navigation_space', '')
            if local_navigation:
                require(track_spaces[track] in allowed_by_space, 'Route references undeclared navigation space')
            radii[track] = person['radius_m']
            speeds[track] = person['speed_mps']
            track_portals[track] = tuple(sorted({route.get(field) for field in ['start_portal', 'end_portal']
                                                 if route.get(field) in portals}))
            if route.get('end_portal') in portals:
                planned[route['end_portal']] += 1
            for field, index in [('start_portal', 0), ('end_portal', -1)]:
                if route.get(field) in portals:
                    portal = portals[route[field]]
                    if portal.get('kind')=='surface_access':
                        require(person['type'] in ('Adult Pedestrian','Child Pedestrian','Senior Pedestrian'),
                                'Stairs access uses an ineligible mobility profile')
                    require(math.dist(route['points'][index], portal['point']) <= tolerance,
                            'Route endpoint differs from its exact door point')
            if previous is not None:
                before = routes[previous['route_id']]
                require(before['end_portal'] in portals and route['start_portal'] in portals
                        and portals[before['end_portal']].get('kind')!='surface_access'
                        and portals[route['start_portal']].get('kind')!='surface_access'
                        and portals[before['end_portal']]['building_id']
                            == portals[route['start_portal']]['building_id'],
                        'Return episode changes its declared building')
                if local_navigation:
                    require(before['end_portal'] == route['start_portal'],
                            'Return episode changes its declared shop entrance')
            previous = episode
    metadata = [row for row in raw['agents'] if row.get('data_type') == 'metadata']
    require(len(metadata) == 1, 'One source origin is required')
    origin = epoch_ms(metadata[0]['timestamp'])
    step_ms = round(cfg['simulation']['time_step'] * 1000)
    frames, tracks = defaultdict(list), defaultdict(list)
    event_rows = []
    max_route_error = 0.0
    actual_segments_checked = 0
    velocity_checks = 0
    maximum_velocity_error = 0.0
    points_off_guide = 0
    frame_rows = {}
    static_body_checks = 0
    terminal_segments_checked = 0
    terminal_positions = {}
    physical_domain = None
    allowed_tolerant = allowed.buffer(tolerance) if allowed is not None else None
    if local_navigation and map_layers is not None:
        physical_domain = box(0, 0, cfg['simulation']['width'], cfg['simulation']['height'])
        portal_throats = {}
        for key in set(portal for ids in track_portals.values() for portal in ids):
            portal = portals[key]
            if portal.get('kind')=='surface_access':
                # Surface sinks are not wall openings and grant no extra walkable
                # area or building exception. The full body must fit the source.
                portal_throats[key]=GeometryCollection()
                require(allowed_tolerant.covers(LineString([portal['point'],portal['approach']])),
                        'Surface approach leaves allowed walking geometry')
                continue
            a, b = portal['facade']
            length = math.dist(a, b)
            require(length > 0, 'Degenerate declared facade')
            tangent = [(b[i] - a[i]) / length for i in [0, 1]]
            center = portal['point']
            normals = [(-tangent[1], tangent[0]), (tangent[1], -tangent[0])]
            candidates = [normal for normal in normals if allowed_tolerant.covers(LineString(
                [center, [center[i] + normal[i] * min(1.5, max(.5, navigation.get('center_clearance_m', .55))) for i in [0, 1]]]))]
            require(len(candidates) == 1, 'Door must have one unambiguous public normal approach')
            normal = candidates[0]
            half = portal['width_m'] / 2
            # Finite rectangular facade exception: never relax wall/body checks
            # through the wider sides of a circular door marker.
            portal_throats[key] = Polygon([[center[i] + normal[i] * depth + tangent[i] * width
                                           for i in [0, 1]]
                for depth, width in [(-.56, -half), (1.7, -half), (1.7, half), (-.56, half)]])
        crossing_surfaces=[]
        for connector in (public_context or {}).get('navigation', {}).get('synthetic_crossing_connectors', []):
            require(connector.get('provenance') in ('synthetic_crossing_and_curb_gap_connector','synthetic_widening_of_preferred_barkhof_crossing'),
                    'Unknown synthetic crossing provenance')
            crossing_surfaces.append(LineString(connector['centerline']).buffer(connector['width_m']/2,cap_style=2)
                .intersection(physical_domain).difference(map_layers['buildings']))
        access_surface=connector_surface(public_context or {},map_layers['walking'],map_layers['buildings'],physical_domain)
        walking_surface=map_layers['walking'].union(unary_union(crossing_surfaces)).union(access_surface)
        physical_masks = {}
        for space, portal_ids in {(track_spaces[track], ids) for track,ids in track_portals.items()}:
            mode=space_modes.get(space)
            require(mode in ('walking','cycling','road'), 'Independent physical audit requires a declared navigation space mode')
            require(mode=='walking' or not portal_ids, 'Rider route cannot use pedestrian facade portals')
            # A body may cross the facade only at its own declared entrance.
            # A global union would incorrectly exempt unrelated shop doors.
            transitions = unary_union([portal_throats[key] for key in portal_ids])
            base=walking_surface if mode=='walking' else map_layers[mode]
            walk = base.union(transitions)
            walls = map_layers['buildings'].difference(transitions)
            physical_masks[(space,portal_ids)] = (walk, walls, prep(walk), prep(walls))
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
        if local_navigation:
            require(allowed_by_space[track_spaces[track]].covers(Point(point)), 'Observed position leaves navigation geometry')
            points_off_guide += error > .02
            if physical_domain is not None:
                physical_walk, physical_walls, prepared_walk, prepared_walls = physical_masks[(track_spaces[track],track_portals[track])]
                body = Point(point).buffer(radii[track] + scene['motion'].get('clearance_m', .1)).intersection(physical_domain)
                require(prepared_walk.covers(body) or body.difference(physical_walk).area <= 1e-4,
                        'Observed body leaves derived walking geometry')
                require(not prepared_walls.intersects(body) or body.intersection(physical_walls).area <= 1e-4,
                        'Observed body penetrates a building outside declared doors')
                static_body_checks += 1
        else:
            require(error <= tolerance, 'Observed position leaves its declared route')
        frames[at].append((track, point))
        tracks[track].append((at, point))
        require((track, at) not in frame_rows, 'Duplicate stored track/timestamp')
        frame_rows[(track, at)] = row
    for rows in tracks.values():
        rows.sort()
    if local_navigation:
        for event in event_rows:
            if event['event'] != 'visible_end':
                continue
            track = event['observation_track_id']
            require(track in episodes, 'Lifecycle event contains an undeclared track')
            route = routes[episodes[track]['route_id']]
            at = epoch_ms(event['timestamp']) - origin
            require(tracks[track] and tracks[track][-1][0] == at - step_ms,
                    'End event does not follow the final outdoor step')
            endpoint=route['points'][-1]
            if 'end_boundary' in route:
                position=event.get('position')
                require(isinstance(position,dict) and set(position)=={'x','y'}
                        and all(isinstance(position[axis],(int,float)) and not isinstance(position[axis],bool)
                                and math.isfinite(position[axis]) for axis in ('x','y')),
                        'Interval exit requires an explicit finite terminal position')
                endpoint=[position['x'],position['y']]
                require(LineString(route['end_boundary']).distance(Point(endpoint))<=tolerance,
                        'Terminal position leaves declared exit interval')
                require(allowed_by_space[track_spaces[track]].covers(Point(endpoint)),
                        'Terminal position leaves selected navigation geometry')
            terminal_positions[(track, at)] = endpoint
        for track, rows in tracks.items():
            extended = rows + [(at, point) for (ended, at), point in terminal_positions.items() if ended == track]
            for (before_ms, before), (after_ms, after) in zip(extended, extended[1:]):
                require(after_ms - before_ms == step_ms, 'Navigation episode has missing source frames')
                displacement = math.dist(before, after)
                # GEOS treats a repeated-coordinate LineString as invalid; on
                # nonrectangular polygons its covers result can be false even
                # for an interior stationary point. Waiting is a valid sweep.
                segment = Point(before) if displacement == 0 else LineString([before, after])
                require(allowed_by_space[track_spaces[track]].covers(segment), 'Observed sweep leaves navigation geometry')
                require(displacement <= speeds[track] * step_ms / 1000 + tolerance,
                        'Observed displacement exceeds preferred speed bound')
                actual_segments_checked += 1
                row = frame_rows.get((track, after_ms), {})
                if (track, after_ms) in terminal_positions:
                    terminal_segments_checked += 1
                if 'velocity' in row:
                    expected = [(after[i] - before[i]) * 1000 / step_ms for i in [0, 1]]
                    got = [row['velocity']['x'], row['velocity']['y']]
                    error = math.dist(expected, got)
                    maximum_velocity_error = max(maximum_velocity_error, error)
                    require(error <= tolerance * 2000 / step_ms,
                            'Reported velocity differs from actual displacement')
                    velocity_checks += 1
                if physical_domain is not None:
                    physical_walk, physical_walls, prepared_walk, prepared_walls = physical_masks[(track_spaces[track],track_portals[track])]
                    sweep = segment.buffer(radii[track] + scene['motion'].get('clearance_m', .1)).intersection(physical_domain)
                    require(prepared_walk.covers(sweep) or sweep.difference(physical_walk).area <= 1e-4,
                            'Observed swept body leaves derived walking geometry')
                    require(not prepared_walls.intersects(sweep) or sweep.intersection(physical_walls).area <= 1e-4,
                            'Observed swept body cuts a building corner')
    clearance = scene['motion'].get('clearance_m', .1)
    minimum_margin = math.inf
    compared = 0
    swept_compared = 0
    minimum_swept_margin = math.inf
    positions_by_frame = {at: dict(rows) for at, rows in frames.items()}
    for (track, at), endpoint in terminal_positions.items():
        # Geometric end-of-step boundary conditions, not invented GT rows.
        # Newly admitted tracks are not added to the preceding frame, so
        # nonoverlapping half-open episodes do not falsely coexist.
        positions_by_frame.setdefault(at, {})[track] = endpoint
    for at, rows in frames.items():
        for i, (first, a) in enumerate(rows):
            for second, b in rows[i + 1:]:
                margin = math.dist(a, b) - radii[first] - radii[second] - clearance
                minimum_margin = min(minimum_margin, margin)
                compared += 1
                require(margin >= -tolerance, 'Independent GT body-clearance violation')
                following = positions_by_frame.get(at + step_ms, {})
                if local_navigation and first in following and second in following:
                    # Minimize relative linear motion over the whole source step.
                    # Endpoint separation alone could hide bodies crossing.
                    da = [following[first][i] - a[i] for i in [0, 1]]
                    db = [following[second][i] - b[i] for i in [0, 1]]
                    relative = [a[i] - b[i] for i in [0, 1]]
                    change = [da[i] - db[i] for i in [0, 1]]
                    squared = sum(value * value for value in change)
                    phase = 0 if squared == 0 else max(0, min(1, -sum(relative[i] * change[i] for i in [0, 1]) / squared))
                    distance = math.hypot(*(relative[i] + phase * change[i] for i in [0, 1]))
                    swept_margin = distance - radii[first] - radii[second] - clearance
                    minimum_swept_margin = min(minimum_swept_margin, swept_margin)
                    swept_compared += 1
                    require(swept_margin >= -tolerance, 'Independent GT swept body-clearance violation')
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
                         if row['completed_entries'] > 0 and portals[key].get('kind')!='surface_access'}
    exited_buildings = {portals[key]['building_id'] for key, row in counts.items()
                        if row['realized_exits'] > 0 and portals[key].get('kind')!='surface_access'}
    if local_navigation:
        require(sum(row['completed_entries'] > 0 and row['realized_exits'] > 0 for row in counts.values()) >= 2,
                'Acceptance requires realized entry and return at two distinct destinations')
    else:
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
    boundary_endpoint_checks = 0
    if local_navigation and public_context is not None:
        intervals_by_mode={mode:[LineString(row['points']) for row in public_context['boundary_intervals']
                                if row['mode']==mode and row['spawn_supported']] for mode in ('walking','road')}
        require(intervals_by_mode['walking'], 'No eligible pedestrian boundary interval')
        for event in event_rows:
            route = routes[episodes[event['observation_track_id']]['route_id']]
            entering = event['event'] == 'visible_start'
            portal = route['start_portal' if entering else 'end_portal']
            if portal in portals:
                continue
            endpoint = route['points'][0 if entering else -1]
            if not entering and 'end_boundary' in route:
                at=epoch_ms(event['timestamp'])-origin
                endpoint=terminal_positions[(event['observation_track_id'],at)]
            mode=space_modes.get(route.get('navigation_space',''))
            require(mode in intervals_by_mode, 'Boundary source/target navigation mode is unsupported')
            intervals=intervals_by_mode[mode]
            require(intervals and min(line.distance(Point(endpoint)) for line in intervals) <= tolerance,
                    'Boundary source/target is outside eligible walking intervals or mode-compatible road intervals')
            if entering:
                actual = tracks[event['observation_track_id']][0][1]
                require(math.dist(actual, endpoint) <= tolerance, 'Admission differs from sampled boundary origin')
            else:
                track = event['observation_track_id']
                require(math.dist(tracks[track][-1][1], endpoint) <= speeds[track] * step_ms / 1000 + tolerance,
                        'Road user disappears before its sampled boundary target')
            boundary_endpoint_checks += 1
    return {'status': 'pass', 'independent_gt_body_pair_checks': compared,
            'independent_gt_swept_body_pair_checks': swept_compared,
            'minimum_swept_body_clearance_margin_m': None if minimum_swept_margin == math.inf else minimum_swept_margin,
            'minimum_body_clearance_margin_m': None if minimum_margin == math.inf else minimum_margin,
            'maximum_observed_route_distance_m': max_route_error,
            'navigation_motion_segments_checked': actual_segments_checked,
            'navigation_terminal_segments_checked': terminal_segments_checked,
            'navigation_static_body_checks': static_body_checks,
            'navigation_positions_over_2cm_from_original_guide': points_off_guide,
            'navigation_velocity_checks': velocity_checks,
            'maximum_navigation_velocity_error_mps': maximum_velocity_error,
            'boundary_endpoint_checks': boundary_endpoint_checks,
            'minimum_realized_hidden_gap_ms': None if minimum_gap == math.inf else minimum_gap,
            'targets_with_completed_entries': sum(row['completed_entries'] > 0 for row in counts.values()),
            'buildings_with_completed_entries': len(visited_buildings),
            'buildings_with_realized_exits': len(exited_buildings),
            'all_planned_entries_completed': all(row['completed_entries'] == row['planned_entries'] for row in counts.values()),
            'surface_access_entries':sum(row['completed_entries'] for key,row in counts.items() if portals[key].get('kind')=='surface_access'),
            'surface_access_exits':sum(row['realized_exits'] for key,row in counts.items() if portals[key].get('kind')=='surface_access'),
            'portals': counts,
            'scope': 'All stored native source frames, route or navigation-geometry containment, pairwise circular body+clearance separation, exact portal lifecycle and realized indoor timing; local navigation additionally checks actual sweeps, speed/velocity and compatible boundary endpoints when source geometry is supplied. No private identities in this report.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Choose a fresh compact output file')
    config_path = args.scene / 'config.yaml'
    raw_path = args.replay / 'private/native_source.json'
    cfg = yaml.safe_load(config_path.read_text())
    context = None
    layers = None
    source_access_validation=None
    if cfg['mapped_scene'].get('motion', {}).get('mode') == 'local_navigation':
        import importlib.util
        context = json.loads((args.scene / 'building_access.json').read_text())
        builder_path = Path(__file__).with_name('build_mapped_scene.py')
        spec = importlib.util.spec_from_file_location('ump_audit_source_builder', builder_path)
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        _, local, layers, _, provenance = builder.load_source(Path(__file__).resolve().parents[2])
        if any(p.get('kind')=='surface_access' for p in cfg['mapped_scene']['portals']):
            helper_path=Path(__file__).with_name('transit_access.py')
            spec=importlib.util.spec_from_file_location('ump_audit_transit',helper_path)
            transit=importlib.util.module_from_spec(spec);spec.loader.exec_module(transit)
            local,layers,_=transit.ground_environment(Path(__file__).resolve().parents[2],local,layers,provenance['source_geometry_sha256'])
            require(context.get('transit_access',{}).get('source_geometry_sha256')==transit.SOURCE_SHA256,
                    'Surface physical audit requires verified frozen source metadata')
        layers = dict(layers)
        layers['buildings'] = unary_union([geom for props, geom in local if props['kind'] == 'building'])
        source_access_validation=validate_expanded_shop_context(Path(__file__).resolve().parents[2],local,layers,provenance['source_geometry_sha256'],context)
    result = audit(cfg, json.loads(raw_path.read_text()), public_context=context, map_layers=layers)
    if source_access_validation and source_access_validation['status']=='pass':
        result['source_access_validation']=source_access_validation
    result['config_sha256'] = hashlib.sha256(config_path.read_bytes()).hexdigest()
    result['native_source_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
