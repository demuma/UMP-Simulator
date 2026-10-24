"""Independent capture audit rejects early disappearance, wrong exits and overlap."""
import math
import unittest
from datetime import datetime, timedelta, timezone

from shapely.geometry import box

from audit_building_access import audit


def fixture():
    def route(name, x, exiting=False):
        return {'id': name, 'points': [[x, 1], [x, 0]] if exiting else [[x, 0], [x, 1]],
                'start_portal': 'door-' + str(x) if exiting else 'boundary',
                'end_portal': 'boundary' if exiting else 'door-' + str(x)}
    cfg = {'simulation': {'time_step': .05}, 'mapped_scene': {
        'portals': [{'id': 'door-' + str(x), 'building_id': 'building-' + str(x), 'point': [x, 1]}
                    for x in [1, 8]],
        'routes': [route(str(x) + direction, x, direction == 'out')
                   for x in [1, 8] for direction in ['in', 'out']],
        'people': [{'radius_m': .25, 'speed_mps': 1, 'episodes': [
            {'track_id': str(x) + 'a', 'route_id': str(x) + 'in', 'start_ms': 0},
            {'track_id': str(x) + 'b', 'route_id': str(x) + 'out', 'start_ms': 0,
             'after_previous_ms': 8000}]} for x in [1, 8]], 'motion': {'clearance_m': .1}}}
    raw = {'agents': [{'data_type': 'metadata', 'timestamp': '2026-10-24T00:00:00Z'}]}
    for x in [1, 8]:
        for track, at, y in [(str(x)+'a', '00.000', 0), (str(x)+'a', '00.950', .95),
                             (str(x)+'b', '09.000', 1)]:
            raw['agents'].append({'data_type': 'agent data', 'agent_id': track,
                'timestamp': '2026-10-24T00:00:' + at + 'Z', 'position': {'x': x, 'y': y}})
        for track, event, at, portal in [(str(x)+'a', 'visible_start', '00.000', 'boundary'),
                (str(x)+'a', 'visible_end', '01.000', 'door-'+str(x)),
                (str(x)+'b', 'visible_start', '09.000', 'door-'+str(x))]:
            raw['agents'].append({'data_type': 'mapped lifecycle event',
                'observation_track_id': track, 'event': event,
                'timestamp': '2026-10-24T00:00:' + at + 'Z', 'portal_id': portal})
    return cfg, raw


def navigation_fixture():
    cfg, raw = fixture()
    cfg['simulation'].update(width=10, height=3)
    scene = cfg['mapped_scene']
    for portal in scene['portals']:
        portal['building_id'] = 'one-physical-building'
        x = portal['point'][0]
        portal.update(facade=[[x - .6, 1], [x + .6, 1]], width_m=1.2)
    scene['motion'].update(mode='local_navigation', navigation={
        'allowed_center_polygons': [{'outer': [[0, 0], [10, 0], [10, 1], [0, 1]]}]})
    for person in scene['people']:
        person['speed_mps'] = 1.5
    raw['agents'] = [row for row in raw['agents'] if row['data_type'] != 'agent data']
    origin = datetime(2026, 10, 24, tzinfo=timezone.utc)
    for x in [1, 8]:
        previous = None
        for ms in range(0, 1000, 50):
            point = [x + .02 * math.sin(math.pi * ms / 950), ms / 1000]
            velocity = [0, 0] if previous is None else [(point[i] - previous[i]) / .05 for i in [0, 1]]
            raw['agents'].append({'data_type': 'agent data', 'agent_id': str(x) + 'a',
                'timestamp': (origin + timedelta(milliseconds=ms)).isoformat(),
                'position': dict(zip(['x', 'y'], point)), 'velocity': dict(zip(['x', 'y'], velocity))})
            previous = point
        raw['agents'].append({'data_type': 'agent data', 'agent_id': str(x) + 'b',
                'timestamp': (origin + timedelta(seconds=9)).isoformat(),
                'position': {'x': x, 'y': 1}, 'velocity': {'x': 0, 'y': 0}})
    context = {'boundary_intervals': [{'points': [[0, 0], [10, 0]],
                                      'mode': 'walking', 'spawn_supported': True}]}
    layers = {'walking': box(0, 0, 10, 1.3), 'buildings': box(0, 1.3, 10, 3)}
    return cfg, raw, context, layers


class NavigationAuditTests(unittest.TestCase):
    def test_actual_off_guide_motion_two_shops_same_building_and_boundaries(self):
        cfg, raw, context, layers = navigation_fixture()
        result = audit(cfg, raw, public_context=context, map_layers=layers)
        self.assertEqual(result['buildings_with_completed_entries'], 1)
        self.assertEqual(result['targets_with_completed_entries'], 2)
        self.assertEqual(result['navigation_motion_segments_checked'], 40)
        self.assertEqual(result['navigation_terminal_segments_checked'], 2)
        self.assertEqual(result['navigation_velocity_checks'], 38)
        self.assertEqual(result['boundary_endpoint_checks'], 2)
        self.assertGreater(result['maximum_observed_route_distance_m'], .019)
        self.assertGreater(result['navigation_static_body_checks'], 40)

    def test_off_navigation_missing_frames_speed_and_velocity_are_rejected(self):
        for failure in ['outside', 'missing', 'speed', 'velocity']:
            with self.subTest(failure=failure):
                cfg, raw, _, _ = navigation_fixture()
                rows = [row for row in raw['agents'] if row.get('agent_id') == '1a']
                if failure == 'outside':
                    rows[0]['position']['x'] = -.2
                    expected = 'position leaves navigation'
                elif failure == 'missing':
                    raw['agents'].remove(rows[5])
                    expected = 'missing source frames'
                elif failure == 'speed':
                    rows[5]['position']['x'] += 1
                    expected = 'preferred speed'
                else:
                    rows[5]['velocity']['x'] += .1
                    expected = 'velocity differs'
                with self.assertRaisesRegex(ValueError, expected):
                    audit(cfg, raw)

    def test_continuous_sweep_rejects_thin_hole_between_valid_endpoints(self):
        cfg, raw, _, _ = navigation_fixture()
        cfg['mapped_scene']['motion']['navigation']['allowed_center_polygons'][0]['holes'] = [
            [[1.002, .07], [1.009, .07], [1.009, .08], [1.002, .08]]]
        with self.assertRaisesRegex(ValueError, 'sweep leaves navigation'):
            audit(cfg, raw)

    def test_other_shops_door_does_not_exempt_body_from_wall_checks(self):
        cfg, raw, context, layers = navigation_fixture()
        cfg['mapped_scene']['portals'].append({'id': 'unrelated-shop',
            'building_id': 'one-physical-building', 'point': [4, 1.3]})
        row = next(row for row in raw['agents'] if row.get('agent_id') == '1a')
        row['position'] = {'x': 4, 'y': 1}
        layers = {'walking': box(0, 0, 10, 1), 'buildings': box(0, 1, 10, 3)}
        with self.assertRaisesRegex(ValueError, 'body leaves derived walking'):
            audit(cfg, raw, public_context=context, map_layers=layers)

    def test_stationary_sweep_in_nonrectangular_geometry_is_a_point(self):
        cfg, raw, _, _ = navigation_fixture()
        cfg['mapped_scene']['motion']['navigation']['allowed_center_polygons'][0]['outer'] = [
            [0, 0], [10, 0], [10, 2], [6, 1.9], [0, 2]]
        raw['agents'].append({'data_type': 'agent data', 'agent_id': '1b',
            'timestamp': '2026-10-24T00:00:09.050Z', 'position': {'x': 1, 'y': 1},
            'velocity': {'x': 0, 'y': 0}})
        result = audit(cfg, raw)
        self.assertEqual(result['navigation_motion_segments_checked'], 41)

    def test_final_half_open_step_still_checks_holes_and_other_bodies(self):
        cfg, raw, _, _ = navigation_fixture()
        cfg['mapped_scene']['motion']['navigation']['allowed_center_polygons'][0]['holes'] = [
            [[.995, .97], [1.005, .97], [1.005, .98], [.995, .98]]]
        with self.assertRaisesRegex(ValueError, 'sweep leaves navigation'):
            audit(cfg, raw)
        cfg, raw, _, _ = navigation_fixture()
        cfg['mapped_scene']['people'][0]['speed_mps'] = 200
        cfg['mapped_scene']['portals'][0]['point'] = [7.5, 1]
        cfg['mapped_scene']['routes'][0]['points'][-1] = [7.5, 1]
        cfg['mapped_scene']['routes'][1]['points'][0] = [7.5, 1]
        with self.assertRaisesRegex(ValueError, 'swept body-clearance'):
            audit(cfg, raw)

    def test_declared_door_width_is_not_a_wider_circular_marker(self):
        cfg, raw, context, _ = navigation_fixture()
        row = next(row for row in raw['agents'] if row.get('agent_id') == '1a')
        row['position'] = {'x': 1.3, 'y': 1}
        layers = {'walking': box(0, 0, 10, 1), 'buildings': box(0, 1, 10, 3)}
        with self.assertRaisesRegex(ValueError, 'body leaves derived walking'):
            audit(cfg, raw, public_context=context, map_layers=layers)

    def test_crossing_bodies_are_rejected_between_separated_frames(self):
        cfg, raw, _, _ = navigation_fixture()
        for person in cfg['mapped_scene']['people']:
            person['speed_mps'] = 200
        for x, swapped in [(1, 8), (8, 1)]:
            rows = [row for row in raw['agents'] if row.get('agent_id') == str(x) + 'a']
            rows[1]['position']['x'] = swapped
            for previous, row in zip(rows, rows[1:]):
                row['velocity'] = {axis: (row['position'][axis] - previous['position'][axis]) / .05
                                   for axis in ['x', 'y']}
        with self.assertRaisesRegex(ValueError, 'swept body-clearance'):
            audit(cfg, raw)

    def test_boundary_compatibility_and_exact_same_shop_return(self):
        cfg, raw, context, _ = navigation_fixture()
        context['boundary_intervals'][0]['points'] = [[5, 0], [10, 0]]
        with self.assertRaisesRegex(ValueError, 'eligible walking intervals'):
            audit(cfg, raw, public_context=context)
        cfg, raw, _, _ = navigation_fixture()
        cfg['mapped_scene']['routes'][1]['start_portal'] = 'door-8'
        cfg['mapped_scene']['routes'][1]['points'][0] = [8, 1]
        with self.assertRaisesRegex(ValueError, 'shop entrance'):
            audit(cfg, raw)


    def test_route_specific_space_checks_positions_sweeps_and_mode_boundaries(self):
        cfg,raw,context,layers=navigation_fixture()
        navigation=cfg['mapped_scene']['motion']['navigation']
        navigation['spaces']=[{'id':'carriageway-east','allowed_center_polygons':[{'outer':[[0,2],[10,2],[10,3],[0,3]]}]}]
        cfg['mapped_scene']['routes'].append({'id':'rider-route','navigation_space':'carriageway-east',
            'points':[[0,2.5],[10,2.5]],'start_portal':'road-west','end_portal':'road-east'})
        cfg['mapped_scene']['people'].append({'radius_m':.25,'speed_mps':10,
            'episodes':[{'track_id':'rider','route_id':'rider-route','start_ms':0}]})
        origin=datetime(2026,10,24,tzinfo=timezone.utc)
        for ms in range(0,1000,50):
            raw['agents'].append({'data_type':'agent data','agent_id':'rider',
                'timestamp':(origin+timedelta(milliseconds=ms)).isoformat(),
                'position':{'x':ms/100,'y':2.5},'velocity':{'x':10 if ms else 0,'y':0}})
        for kind,ms,portal in [('visible_start',0,'road-west'),('visible_end',1000,'road-east')]:
            raw['agents'].append({'data_type':'mapped lifecycle event','event':kind,
                'observation_track_id':'rider','timestamp':(origin+timedelta(milliseconds=ms)).isoformat(),'portal_id':portal})
        context['navigation']={'spaces':[{'id':'carriageway-east','mode':'road'}]}
        context['boundary_intervals'] += [{'points':[[x,2],[x,3]],'mode':'road','spawn_supported':True} for x in (0,10)]
        layers['road']=box(0,2,10,3)
        layers['buildings']=box(0,1.3,10,1.9)
        result=audit(cfg,raw,public_context=context,map_layers=layers)
        self.assertEqual(result['boundary_endpoint_checks'],4)
        cfg['mapped_scene']['routes'][-1]['end_boundary']=[[10,2],[10,3]]
        cfg['mapped_scene']['people'][-1]['speed_mps']=11
        end=next(row for row in raw['agents'] if row.get('observation_track_id')=='rider' and row['event']=='visible_end')
        end['position']={'x':10,'y':2.55}
        self.assertEqual(audit(cfg,raw,public_context=context,map_layers=layers)['boundary_endpoint_checks'],4)
        end.pop('position')
        with self.assertRaisesRegex(ValueError,'explicit finite terminal position'):
            audit(cfg,raw)
        end['position']={'x':9.9,'y':2.55}
        with self.assertRaisesRegex(ValueError,'declared exit interval'):
            audit(cfg,raw)
        end['position']={'x':10,'y':2.55}
        cfg['mapped_scene']['routes'][-1].pop('navigation_space')
        with self.assertRaisesRegex(ValueError,'position leaves navigation'):
            audit(cfg,raw)
        cfg['mapped_scene']['routes'][-1]['navigation_space']='carriageway-east'
        next(r for r in raw['agents'] if r.get('agent_id')=='rider')['position']['y']=1.8
        with self.assertRaisesRegex(ValueError,'position leaves navigation'):
            audit(cfg,raw)


class BuildingAccessAuditTests(unittest.TestCase):
    def test_two_doors_exact_arrival_return_and_body_clearance(self):
        cfg, raw = fixture()
        result = audit(cfg, raw)
        self.assertEqual(result['targets_with_completed_entries'], 2)
        self.assertEqual(result['minimum_realized_hidden_gap_ms'], 8000)
        self.assertEqual(result['portals']['door-1']['realized_exits'], 1)
        self.assertNotIn('track_id', str(result))

    def test_configured_targets_without_real_visits_do_not_pass_acceptance(self):
        cfg, raw = fixture()
        with self.assertRaisesRegex(ValueError, 'two distinct buildings'):
            audit(cfg, {'agents': [raw['agents'][0]]})
        raw['agents'] = [row for row in raw['agents']
                         if not str(row.get('agent_id', row.get('observation_track_id', ''))).startswith('8')]
        with self.assertRaisesRegex(ValueError, 'two distinct buildings'):
            audit(cfg, raw)

    def test_no_disappearance_on_entering_a_nearby_circle(self):
        cfg, raw = fixture()
        next(row for row in raw['agents'] if row.get('agent_id') == '1a'
             and '.950' in row['timestamp'])['position']['y'] = .5
        with self.assertRaisesRegex(ValueError, 'disappears before'):
            audit(cfg, raw)

    def test_exit_and_realized_gap_are_not_inferred_from_schedule(self):
        cfg, raw = fixture()
        next(row for row in raw['agents'] if row.get('agent_id') == '1b')['position']['y'] = .9
        with self.assertRaisesRegex(ValueError, 'exact door'):
            audit(cfg, raw)
        cfg, raw = fixture()
        cfg['mapped_scene']['people'][0]['episodes'][1]['after_previous_ms'] = 9000
        with self.assertRaisesRegex(ValueError, 'realized indoor gap'):
            audit(cfg, raw)

    def test_detects_off_route_positions_and_physical_overlap(self):
        cfg, raw = fixture()
        next(row for row in raw['agents'] if row.get('agent_id') == '1a')['position']['x'] += .1
        with self.assertRaisesRegex(ValueError, 'declared route'):
            audit(cfg, raw)
        cfg, raw = fixture()
        cfg['mapped_scene']['routes'][2]['points'][0] = [1, 0]
        next(row for row in raw['agents'] if row.get('agent_id') == '8a')['position']['x'] = 1
        # Keep its later point on its changed route; only the shared initial body
        # position is the violation under test.
        later = next(row for row in raw['agents'] if row.get('agent_id') == '8a'
                     and '.950' in row['timestamp'])
        later['position'] = {'x': 7.65, 'y': .95}
        with self.assertRaisesRegex(ValueError, 'body-clearance'):
            audit(cfg, raw)


if __name__ == '__main__':
    unittest.main()
