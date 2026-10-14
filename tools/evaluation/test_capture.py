"""Pure capture-adapter tests: no simulator process or MongoDB access."""

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from capture_simulator import capture_config, cell_for, utc_milliseconds, verify_and_replay


ORIGIN = datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc)
DATABASE = "UMP_Capture_" + "a" * 32


def timestamp(milliseconds):
    return (ORIGIN + timedelta(milliseconds=milliseconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def raw_capture():
    agents = [{"data_type": "metadata", "timestamp": timestamp(0), "frame_rate": 20,
               "simulation_area": {"width": 80, "height": 80}}]
    sensor = [{"data_type": "metadata", "timestamp": timestamp(0), "frame_rate": 10,
               "sensor_id": "temporal-aggregation-agbs", "max_depth": 6, "cell_size": 40,
               "position": {"x": 0, "y": 0}, "detection_area": {"width": 80, "height": 80}}]
    for time in range(0, 8000, 50):
        agents.append({"data_type": "agent data", "timestamp": timestamp(time),
                       "agent_id": "road-user-A", "type": "pedestrian", "position": {"x": .5, "y": .5}})
        if time and time % 100 == 0:
            sensor.append({"data_type": "adaptive grid data", "timestamp": timestamp(time),
                           "sensor_id": "temporal-aggregation-agbs", "cell_id": 12288,
                           "cell_position": {"x": 0, "y": 0}, "cell_size": 1.25,
                           "total_agents": 1, "agent_type_count": [{"type": "pedestrian", "count": 1}]})
    return agents, sensor


class CaptureTests(unittest.TestCase):
    def test_example_configuration_isolated_and_aggregation_disabled(self):
        path = Path(__file__).resolve().parents[2] / "simulator/examples/temporal-aggregation/config.yaml"
        original = path.read_text()
        configured = capture_config(original, DATABASE)
        self.assertIn("show_renderer: false", configured)
        self.assertIn("duration_seconds: 8", configured)
        self.assertIn("aggregation:\n      enabled: false", configured)
        self.assertIn("clear_database: false", configured)
        self.assertEqual(configured.count(DATABASE), 2)
        self.assertNotIn("UMP_Temporal_Demo_", configured)
        self.assertNotIn("publication:", configured)
        self.assertEqual(path.read_text(), original)
        for changed in (original.replace("time_step: 0.05", "time_step: 0.1"),
                        original.replace("clear_database: false", "clear_database: true"),
                        original.replace("max_depth: 6", "max_depth: 5"),
                        original.replace("sensors:\n", "sensors:\n  - id: extra\n"),
                        original.replace("collection_name: Agents", "db_name: other\n  collection_name: Agents")):
            with self.subTest(changed=changed[:20]), self.assertRaises(ValueError):
                capture_config(changed, DATABASE)
        with self.assertRaises(ValueError):
            capture_config(original, "Simulation")

    def test_quadtree_prefix_and_half_open_boundaries(self):
        self.assertEqual(cell_for(0, 0), (12288, 0, 0, 1.25))
        self.assertEqual(cell_for(1.249999, 1.249999), (12288, 0, 0, 1.25))
        self.assertEqual(cell_for(1.25, 0), (12289, 1.25, 0, 1.25))
        self.assertEqual(cell_for(0, 1.25), (12290, 0, 1.25, 1.25))
        self.assertEqual(cell_for(40, 0)[0] >> 10, 13)
        self.assertEqual(cell_for(0, 40)[0] >> 10, 14)
        self.assertEqual(cell_for(79.999999, 79.999999), (16383, 78.75, 78.75, 1.25))
        for x, y in ((80, 1), (1, 80), (-.001, 0), (0, -.001), (float("nan"), 0), (0, float("inf"))):
            with self.subTest(x=x, y=y), self.assertRaises(ValueError):
                cell_for(x, y)

    def test_utc_conversion_preserves_offset_and_exact_milliseconds(self):
        self.assertEqual(utc_milliseconds("1970-01-01T00:00:00.000Z"), 0)
        self.assertEqual(utc_milliseconds("1970-01-01T01:00:00.123+01:00"), 123)
        self.assertEqual(utc_milliseconds("1969-12-31T23:59:59.999Z"), -1)
        self.assertEqual(utc_milliseconds(timestamp(150)) - utc_milliseconds(timestamp(0)), 150)
        for value in ("2026-10-14T10:30:00", "2026-10-14T10:30:00.000001Z"):
            with self.assertRaises(ValueError):
                utc_milliseconds(value)

    def test_valid_capture_and_measured_empty_evidence(self):
        agents, sensor = raw_capture()
        replay, proof = verify_and_replay(agents, sensor, "frozen")
        self.assertEqual(len(replay["batches"]), 79)
        self.assertEqual(replay["batches"][0]["observed_at_ms"], 100)
        self.assertEqual(replay["batches"][-1]["observed_at_ms"], 7900)
        self.assertEqual(replay["end_ms"], 8000)
        self.assertEqual(proof["sampled_observation_contributions"], 79)
        self.assertEqual(proof["gt_frames"], 160)
        self.assertEqual(proof["measured_empty_frames"], 0)
        # A known GT frame entirely outside the sensor supports measured-empty;
        # a missing GT frame does not provide equivalent evidence.
        agents[3]["position"]["x"] = 80.1
        sensor.pop(1)
        replay, proof = verify_and_replay(agents, sensor, "frozen")
        self.assertEqual(replay["batches"][0]["status"], "measured")
        self.assertEqual(replay["batches"][0]["observations"], [])
        self.assertEqual(proof["measured_empty_frames"], 1)
        self.assertEqual(proof["sampled_gt_outside_sensor"], 1)

    def test_malformed_join_fails_explicitly(self):
        mutations = {
            "missing GT frame": lambda a, s: a.pop(4),
            "duplicate GT identity": lambda a, s: a.append(copy.deepcopy(a[1])),
            "duplicate AGBS cell": lambda a, s: s.append(copy.deepcopy(s[1])),
            "missing AGBS cell": lambda a, s: s.pop(1),
            "wrong total": lambda a, s: s[1].update(total_agents=2),
            "wrong cell": lambda a, s: s[1].update(cell_id=12289),
            "wrong geometry": lambda a, s: s[1].update(cell_size=2.5),
            "wrong time": lambda a, s: s[1].update(timestamp=timestamp(150)),
            "wrong metadata origin": lambda a, s: s[0].update(timestamp=timestamp(100)),
            "wrong sensor": lambda a, s: s[1].update(sensor_id="another"),
            "nonfinite GT": lambda a, s: a[3]["position"].update(x=float("nan")),
            "mismatched type": lambda a, s: s[1]["agent_type_count"][0].update(type="car"),
        }
        for name, mutation in mutations.items():
            agents, sensor = raw_capture()
            mutation(agents, sensor)
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify_and_replay(agents, sensor, "frozen")


if __name__ == "__main__":
    unittest.main()
