"""Independent capture audit rejects early disappearance, wrong exits and overlap."""
import unittest

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
