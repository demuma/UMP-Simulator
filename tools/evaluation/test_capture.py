"""Pure capture-adapter tests: no simulator process or MongoDB access."""

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import tempfile
from types import SimpleNamespace
from unittest import mock

from capture_simulator import (MIXED_TYPE_PROBABILITIES, behavior_taxonomy, capture_parameters,
                               capture_config, cell_for, export_collection, utc_milliseconds,
                               verify_and_replay, write_json)


ORIGIN = datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc)
DATABASE = "UMP_Capture_" + "a" * 32


def timestamp(milliseconds):
    return (ORIGIN + timedelta(milliseconds=milliseconds)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def raw_capture(end_ms=8000):
    agents = [{"data_type": "metadata", "timestamp": timestamp(0), "frame_rate": 20,
               "simulation_area": {"width": 80, "height": 80}}]
    sensor = [{"data_type": "metadata", "timestamp": timestamp(0), "frame_rate": 10,
               "sensor_id": "temporal-aggregation-agbs", "max_depth": 6, "cell_size": 40,
               "position": {"x": 0, "y": 0}, "detection_area": {"width": 80, "height": 80}}]
    for time in range(0, end_ms, 50):
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

    def test_requested_population_duration_and_mixed_profiles_are_explicit(self):
        repository = Path(__file__).resolve().parents[2]
        original = (repository / "simulator/examples/temporal-aggregation/config.yaml").read_text()
        source = (repository / "simulator/config.yaml").read_text()
        mixed = behavior_taxonomy(source)
        for population in (200, 500, 1000):
            configured = capture_config(original, DATABASE, num_agents=population,
                                        duration_seconds=20, mixed_taxonomy=mixed)
            self.assertIn(f"  num_agents: {population}\n", configured)
            self.assertIn("  duration_seconds: 20\n", configured)
            self.assertIn(mixed, configured)
            self.assertEqual(configured.count(DATABASE), 2)
            self.assertNotIn("db_name: Simulation", configured)
            self.assertNotIn("clear_database: true", configured)
            self.assertNotIn("publication:", configured)
            for name in MIXED_TYPE_PROBABILITIES:
                self.assertEqual(configured.count(f"    - type: {name}\n"), 1)
        self.assertEqual((repository / "simulator/config.yaml").read_text(), source)

    def test_mixed_source_edits_and_parameter_errors_fail_closed(self):
        source = (Path(__file__).resolve().parents[2] / "simulator/config.yaml").read_text()
        for changed in (source.replace("      probability: 0.35", "      probability: 0.34"),
                        source.replace("    - type: Adult Cyclist", "    - type: Car"),
                        source + "\nagents:\n  num_agents: 2\n"):
            with self.subTest(changed=changed[-40:]), self.assertRaises(ValueError):
                behavior_taxonomy(changed)
        for population, duration in ((0, 8), (5001, 8), (True, 8), (1.5, 8),
                                     (200, 0), (200, 601), (200, True), (200, 2.5)):
            with self.subTest(population=population, duration=duration), self.assertRaises(ValueError):
                capture_parameters(population, duration)
        self.assertEqual(capture_parameters(200, 20), 20000)
        self.assertEqual(capture_parameters(), 8000)

    def test_duration_changes_expected_complete_cadence_and_population_summary(self):
        agents, sensor = raw_capture(20000)
        # One extra initialized participant leaves after 100 ms; the remaining
        # identity proves subsequent complete frames without pretending density
        # stays equal to the requested initial population.
        agents.extend({"data_type": "agent data", "timestamp": timestamp(time),
                       "agent_id": "departing", "type": "cyclist",
                       "position": {"x": 80.1, "y": .5}} for time in (0, 50, 100))
        replay, proof = verify_and_replay(agents, sensor, "long-frozen", 20000)
        self.assertEqual(replay["end_ms"], 20000)
        self.assertEqual(len(replay["batches"]), 199)
        self.assertEqual(proof["gt_frames"], 400)
        self.assertEqual(proof["population"], {
            "initial_road_users": 2, "final_road_users": 1,
            "min_road_users": 1, "max_road_users": 2, "distinct_road_users": 2,
            "initial_type_counts": {"cyclist": 1, "pedestrian": 1},
            "final_type_counts": {"pedestrian": 1},
        })
        with self.assertRaises(ValueError):
            verify_and_replay(agents, sensor, "wrong-default-horizon")
        for end in (0, 8001, 600001, True):
            with self.subTest(end=end), self.assertRaises(ValueError):
                verify_and_replay(agents, sensor, "invalid-end", end)

    def test_late_global_extinction_is_not_inferred_as_empty_measurement(self):
        agents, sensor = raw_capture(1000)
        agents = [row for row in agents if row["data_type"] == "metadata"
                  or utc_milliseconds(row["timestamp"]) < utc_milliseconds(timestamp(900))]
        with self.assertRaisesRegex(ValueError, "population extinction"):
            verify_and_replay(agents, sensor, "extinct", 1000)

    def test_json_artifact_budget_counts_utf8_and_preserves_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            write_json(path, {"x": "ä"}, max_bytes=11)
            self.assertEqual(json.loads(path.read_text()), {"x": "ä"})
            self.assertEqual(path.stat().st_size, 11)
            with self.assertRaises(FileExistsError):
                write_json(path, {"other": 1})
            oversized = Path(directory) / "large.json"
            with self.assertRaisesRegex(ValueError, "exceeds 10 bytes"):
                write_json(oversized, {"x": "ä"}, max_bytes=10)
            self.assertLessEqual(oversized.stat().st_size, 10)

    def test_raw_export_streams_bounded_cursor_and_validates_complete_array(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.json"
            def run(command, **kwargs):
                script = command[-1]
                self.assertNotIn(".toArray()", script)
                self.assertIn("while (cursor.hasNext())", script)
                self.assertIn("Buffer.byteLength", script)
                self.assertIn("const maximum = 100;", script)
                kwargs["stdout"].write('[\n{"agent_id":"A"}\n]\n')
                return SimpleNamespace(returncode=0)
            with mock.patch("capture_simulator.subprocess.run", side_effect=run):
                self.assertEqual(export_collection("mongosh", DATABASE, "Agents", path, max_bytes=100),
                                 [{"agent_id": "A"}])
                with self.assertRaises(FileExistsError):
                    export_collection("mongosh", DATABASE, "Agents", path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_raw_export_error_budget_invalid_array_and_destination_fail_closed(self):
        cases = [("[]", 1, 0, "exceeds"), ("[", 100, 0, "complete JSON array"),
                 ("{}", 100, 0, "not an array"), ("[", 100, 1, "Raw Agents export failed")]
        with tempfile.TemporaryDirectory() as directory:
            for index, (payload, budget, returncode, reason) in enumerate(cases):
                def run(command, **kwargs):
                    kwargs["stdout"].write(payload)
                    kwargs["stderr"].write("bounded export test")
                    return SimpleNamespace(returncode=returncode)
                with self.subTest(reason=reason), mock.patch("capture_simulator.subprocess.run", side_effect=run):
                    with self.assertRaisesRegex((ValueError, RuntimeError), reason):
                        export_collection("mongosh", DATABASE, "Agents", Path(directory) / f"raw{index}.json", max_bytes=budget)
            with mock.patch("capture_simulator.subprocess.run") as called:
                for database, collection in (("Simulation", "Agents"), (DATABASE, "other")):
                    with self.assertRaises(ValueError):
                        export_collection("mongosh", database, collection, Path(directory) / "unsafe.json")
                called.assert_not_called()

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
