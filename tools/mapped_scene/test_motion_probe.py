#!/usr/bin/env python3
"""Aggregate-only motion probe contract; standard library, no map/DB dependencies."""
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROBE = Path(os.environ.get("UMP_MAPPED_MOTION_PROBE_BINARY", ""))
PERSON = "private-person-must-not-enter-probe-output"
TRACK = "opaque-track-must-not-enter-probe-output"
FIXTURE = f"""simulation:
  width: 10
  height: 10
agents:
  road_user_taxonomy:
    - type: Adult Pedestrian
mapped_scene:
  support_contract: one_episode_per_retained_history
  motion: {{mode: corridor_following, step_ms: 50, clearance_m: 0.1}}
  routes:
    - id: full-width-walk
      points: [[0,5], [10,5]]
  people:
    - person_id: {PERSON}
      type: Adult Pedestrian
      speed_mps: 1
      episodes:
        - {{track_id: {TRACK}, route_id: full-width-walk, start_ms: 0}}
"""


def reject_nonfinite(value):
    raise ValueError(f"Nonfinite JSON constant: {value}")


@unittest.skipUnless(PROBE.is_file(), "Set UMP_MAPPED_MOTION_PROBE_BINARY to the built probe")
class MotionProbeContractTests(unittest.TestCase):
    def invoke(self, *arguments):
        return subprocess.run([str(PROBE), *map(str, arguments)], text=True,
                              capture_output=True, timeout=10, check=False)

    def records(self, completed):
        self.assertEqual(completed.stderr, "")
        rows = [json.loads(line, parse_constant=reject_nonfinite)
                for line in completed.stdout.splitlines()]
        self.assertTrue(rows)
        self.assertEqual(rows[-1]["kind"], "final")
        self.assertEqual(sum(row["kind"] == "final" for row in rows), 1)
        for row in rows:
            self.assertIsInstance(row, dict)
            for value in row.values():
                if isinstance(value, (int, float)):
                    self.assertTrue(math.isfinite(value))
            self.assertNotIn("track_id", row)
            self.assertNotIn("person_id", row)
            self.assertNotIn("position", row)
        self.assertNotIn(PERSON, completed.stdout)
        self.assertNotIn(TRACK, completed.stdout)
        return rows

    def test_malformed_arguments_are_rejected_before_input_is_read(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / "input-must-not-be-read.yaml")
            base = [missing, "--end-ms", "50", "--wall-budget-s", "30"]
            cases = [[], [missing], base + ["--unknown", "1"],
                     base + ["--end-ms", "100"], base + ["--report-every-ms"],
                     [missing, "--end-ms", "0", "--wall-budget-s", "30"],
                     [missing, "--end-ms", "-50", "--wall-budget-s", "30"],
                     [missing, "--end-ms", "1.5", "--wall-budget-s", "30"],
                     [missing, "--end-ms", "50", "--wall-budget-s", "nan"],
                     [missing, "--end-ms", "50", "--wall-budget-s", "inf"],
                     [missing, "--end-ms", "18446744073709551616", "--wall-budget-s", "30"]]
            for arguments in cases:
                with self.subTest(arguments=arguments):
                    completed = self.invoke(*arguments)
                    self.assertEqual(completed.returncode, 64)
                    self.assertEqual(completed.stdout, "")
                    self.assertTrue(completed.stderr.startswith("MappedMotionProbe: "))
                    self.assertNotIn(missing, completed.stderr)

    def test_short_horizon_reports_unfinished_work_without_losing_tracks(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "simple.yaml"
            config.write_text(FIXTURE, encoding="utf-8")
            completed = self.invoke(config, "--end-ms", "50", "--wall-budget-s", "30")
        self.assertEqual(completed.returncode, 3)
        rows = self.records(completed)
        self.assertEqual(len(rows), 1)
        final = rows[-1]
        self.assertEqual(final["state"], "horizon_incomplete")
        self.assertEqual((final["expected_episodes"], final["starts"], final["ends"]), (1, 1, 0))
        self.assertEqual((final["active"], final["pending"], final["peak_active"]), (1, 0, 1))
        self.assertEqual((final["simulated_ms"], final["steps"], final["last_end_ms"]), (50, 1, 0))
        self.assertEqual(final["overlaps"], 0)
        for key in ("advance_wall_ms", "setup_wall_ms", "constructor_wall_ms", "total_wall_ms",
                    "step_wall_ms_mean", "step_wall_ms_p50", "step_wall_ms_p95", "step_wall_ms_p99", "step_wall_ms_max"):
            self.assertIn(key, final)

    def test_full_horizon_stops_at_complete_finite_cohort(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "simple.yaml"
            config.write_text(FIXTURE, encoding="utf-8")
            completed = self.invoke(config, "--end-ms", "30000", "--wall-budget-s", "30",
                                    "--report-every-ms", "1000")
        self.assertEqual(completed.returncode, 0)
        rows = self.records(completed)
        final = rows[-1]
        self.assertEqual(final["state"], "complete")
        self.assertEqual((final["expected_episodes"], final["starts"], final["ends"]), (1, 1, 1))
        self.assertEqual((final["active"], final["pending"], final["stalled"], final["overlaps"]), (0, 0, 0, 0))
        self.assertEqual((final["simulated_ms"], final["last_end_ms"], final["steps"]), (10000, 10000, 200))
        self.assertEqual(final["peak_active"], 1)
        for row in rows[:-1]:
            self.assertEqual((row["kind"], row["state"]), ("progress", "progress"))
        self.assertEqual([row["simulated_ms"] for row in rows], list(range(1000, 10001, 1000)))
        for key in ("passage_wait_steps", "passage_batches", "passage_cleared_tracks", "max_passage_wait_ms"):
            self.assertEqual(final[key], 0)

    def test_horizon_and_report_interval_must_align_with_motion_step(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "simple.yaml"
            config.write_text(FIXTURE, encoding="utf-8")
            for end, report in ((51, 1000), (100, 51)):
                with self.subTest(end=end, report=report):
                    completed = self.invoke(config, "--end-ms", end, "--wall-budget-s", "30",
                                            "--report-every-ms", report)
                    self.assertEqual(completed.returncode, 64)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn("multiples of the native motion step", completed.stderr)


if __name__ == "__main__":
    unittest.main()
