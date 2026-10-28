"""Actual spawned scheduler checks using synthetic workers and temporary files."""
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import parallel_recordings as scheduler

_TAG = None
_BARRIER = None


def initialize_worker(tag, barrier=None):
    global _TAG, _BARRIER
    _TAG, _BARRIER = tag, barrier


def fail_initializer():
    raise RuntimeError("synthetic initializer failure")


def synthetic_worker(group):
    start = time.time()
    if group.get("barrier"):
        _BARRIER.wait(timeout=15)
    if "directory" in group:
        marker = Path(group["directory"]) / (group["group_id"] + ".started")
        marker.write_text(str(os.getpid()))
    time.sleep(group.get("delay", 0))
    if group.get("action") == "raise":
        raise RuntimeError("synthetic worker failure: " + group["group_id"])
    if group.get("action") == "exit":
        os._exit(7)
    return dict(group_id=group["group_id"], pid=os.getpid(), tag=_TAG,
                start=start, end=time.time())


def peak_overlap(results):
    events = [(r["start"], 1) for r in results] + [(r["end"], -1) for r in results]
    current = peak = 0
    for _, delta in sorted(events):
        current += delta
        peak = max(peak, current)
    return peak


class ParallelRecordingTests(unittest.TestCase):
    def test_default_six_workers_really_overlap_with_initializer(self):
        barrier = multiprocessing.get_context("spawn").Barrier(6)
        groups = [dict(group_id=f"g{i}", barrier=True) for i in range(6)]
        results = scheduler.execute_recordings(
            groups, synthetic_worker, initializer=initialize_worker,
            initargs=("initialized", barrier))
        self.assertEqual(scheduler.DEFAULT_WORKERS, 6)
        self.assertEqual(peak_overlap(results), 6)
        self.assertEqual(len({r["pid"] for r in results}), 6)
        self.assertTrue(all(r["pid"] != os.getpid() and r["tag"] == "initialized"
                            for r in results))

    def test_bounded_admission_parent_callbacks_and_manifest_order(self):
        barrier = multiprocessing.get_context("spawn").Barrier(3)
        groups = [dict(group_id=f"g{i}", barrier=i < 3,
                       delay=.10 if i == 0 else .01) for i in range(8)]
        admitted, received = [], []
        outstanding = set()
        peak_admitted = 0

        def before(group):
            nonlocal peak_admitted
            self.assertEqual(os.getpid(), parent_pid)
            outstanding.add(group["group_id"])
            admitted.append(group["group_id"])
            peak_admitted = max(peak_admitted, len(outstanding))

        def after(group, result):
            self.assertEqual(os.getpid(), parent_pid)
            self.assertEqual(group["group_id"], result["group_id"])
            outstanding.remove(group["group_id"])
            received.append(group["group_id"])

        parent_pid = os.getpid()
        results = scheduler.execute_recordings(
            groups, synthetic_worker, workers=3, initializer=initialize_worker,
            initargs=("three", barrier), before_submit=before, on_result=after)
        expected = [g["group_id"] for g in groups]
        self.assertEqual([r["group_id"] for r in results], expected)
        self.assertEqual(admitted, expected)
        self.assertEqual(set(received), set(expected))
        self.assertNotEqual(received, expected)
        self.assertEqual(peak_overlap(results), 3)
        self.assertEqual(peak_admitted, 3)
        self.assertFalse(outstanding)

    def test_worker_failure_stops_admission_and_drains_running_work(self):
        barrier = multiprocessing.get_context("spawn").Barrier(2)
        with tempfile.TemporaryDirectory() as directory:
            groups = [dict(group_id="g0", barrier=True, action="raise", directory=directory),
                      dict(group_id="g1", barrier=True, delay=.15, directory=directory),
                      dict(group_id="g2", directory=directory),
                      dict(group_id="g3", directory=directory)]
            admitted, received = [], []
            with self.assertRaises(scheduler.BatchFailure) as caught:
                scheduler.execute_recordings(
                    groups, synthetic_worker, workers=2, initializer=initialize_worker,
                    initargs=("failure", barrier),
                    before_submit=lambda group: admitted.append(group["group_id"]),
                    on_result=lambda group, result: received.append(group["group_id"]))
            failure = caught.exception
            self.assertEqual(admitted, ["g0", "g1"])
            self.assertEqual(received, ["g1"])
            self.assertEqual(list(failure.completed_results), ["g1"])
            self.assertEqual(list(failure.errors), ["g0"])
            self.assertIsInstance(failure.errors["g0"], RuntimeError)
            self.assertEqual(failure.cancelled_group_ids, ("g2", "g3"))
            self.assertEqual(failure.unsubmitted_group_ids, ("g2", "g3"))
            self.assertEqual(sorted(p.stem for p in Path(directory).iterdir()), ["g0", "g1"])

    def test_admission_failure_keeps_inflight_and_never_submits_failure(self):
        groups = [dict(group_id=f"g{i}", delay=.05) for i in range(4)]
        admitted, received = [], []

        def before(group):
            admitted.append(group["group_id"])
            if group["group_id"] == "g1":
                raise OSError("synthetic disk admission failure")

        with self.assertRaises(scheduler.BatchFailure) as caught:
            scheduler.execute_recordings(
                groups, synthetic_worker, workers=2, before_submit=before,
                on_result=lambda group, result: received.append(group["group_id"]))
        failure = caught.exception
        self.assertEqual(admitted, ["g0", "g1"])
        self.assertEqual(list(failure.errors), ["g1"])
        self.assertIsInstance(failure.errors["g1"], OSError)
        # The first future may be cancelled before a child starts, or finish.
        self.assertEqual(received, list(failure.completed_results))
        self.assertEqual(failure.unsubmitted_group_ids, ("g2", "g3"))
        self.assertTrue({"g2", "g3"}.issubset(failure.cancelled_group_ids))
        self.assertEqual(set(failure.completed_results) | set(failure.errors)
                         | set(failure.cancelled_group_ids), {"g0", "g1", "g2", "g3"})

    def test_result_callback_failure_preserves_result_and_stops_admission(self):
        groups = [dict(group_id=f"g{i}") for i in range(3)]
        admitted = []

        def after(group, result):
            raise ValueError("synthetic publication callback failure")

        with self.assertRaises(scheduler.BatchFailure) as caught:
            scheduler.execute_recordings(
                groups, synthetic_worker, workers=1, on_result=after,
                before_submit=lambda group: admitted.append(group["group_id"]))
        failure = caught.exception
        self.assertEqual(admitted, ["g0"])
        self.assertEqual(list(failure.completed_results), ["g0"])
        self.assertEqual(list(failure.errors), ["g0"])
        self.assertEqual(failure.cancelled_group_ids, ("g1", "g2"))

    def test_initializer_failure_is_reported_without_retry(self):
        groups = [dict(group_id=f"g{i}") for i in range(4)]
        admitted = []
        with self.assertRaises(scheduler.BatchFailure) as caught:
            scheduler.execute_recordings(
                groups, synthetic_worker, workers=2, initializer=fail_initializer,
                before_submit=lambda group: admitted.append(group["group_id"]))
        failure = caught.exception
        self.assertLessEqual(len(admitted), 2)
        self.assertTrue(failure.errors)
        self.assertFalse(failure.completed_results)
        self.assertEqual(failure.unsubmitted_group_ids,
                         tuple(g["group_id"] for g in groups[len(admitted):]))

    def test_abrupt_worker_exit_is_reported_without_retry(self):
        groups = [dict(group_id="g0", action="exit"), dict(group_id="g1")]
        with self.assertRaises(scheduler.BatchFailure) as caught:
            scheduler.execute_recordings(groups, synthetic_worker, workers=1)
        self.assertEqual(list(caught.exception.errors), ["g0"])
        self.assertEqual(caught.exception.unsubmitted_group_ids, ("g1",))

    def test_nonpicklable_worker_submission_is_batch_failure(self):
        with self.assertRaises(scheduler.BatchFailure) as caught:
            scheduler.execute_recordings([dict(group_id="g0"), dict(group_id="g1")],
                                         lambda group: group, workers=1)
        self.assertEqual(list(caught.exception.errors), ["g0"])
        self.assertEqual(caught.exception.unsubmitted_group_ids, ("g1",))

    def test_validation_finishes_before_spawning(self):
        invalid_groups = [
            [dict(group_id="same"), dict(group_id="same")],
            [dict(group_id="valid"), dict(group_id="../escape")],
            [dict()], [None], ["group"],
        ]
        invalid_groups += [[dict(group_id=value)] for value in
                           ("", ".", "..", "a/b", "a\\b", " white", "g\n", "é", 1, True, None)]
        with patch.object(scheduler, "ProcessPoolExecutor") as executor:
            for groups in invalid_groups:
                with self.subTest(groups=groups), self.assertRaises(ValueError):
                    scheduler.execute_recordings(groups, synthetic_worker)
            for workers in (True, False, 0, -1, 7, 1.0, "2", None):
                with self.subTest(workers=workers), self.assertRaises(ValueError):
                    scheduler.execute_recordings([dict(group_id="g0")],
                                                 synthetic_worker, workers=workers)
            executor.assert_not_called()

    def test_empty_manifest_does_not_spawn(self):
        with patch.object(scheduler, "ProcessPoolExecutor") as executor:
            self.assertEqual(scheduler.execute_recordings([], synthetic_worker), [])
            executor.assert_not_called()

    def test_callback_cannot_change_group_id(self):
        group = dict(group_id="g0")

        def before(value):
            value["group_id"] = "different"

        with self.assertRaises(scheduler.BatchFailure) as caught:
            scheduler.execute_recordings([group], synthetic_worker,
                                         before_submit=before)
        self.assertEqual(list(caught.exception.errors), ["g0"])
        self.assertEqual(group, dict(group_id="g0"))
        self.assertRegex(str(caught.exception.errors["g0"]), "changed group_id")

    def test_all_running_failures_are_drained(self):
        barrier = multiprocessing.get_context("spawn").Barrier(2)
        groups = [dict(group_id=f"g{i}", barrier=i < 2, action="raise")
                  for i in range(4)]
        with self.assertRaises(scheduler.BatchFailure) as caught:
            scheduler.execute_recordings(groups, synthetic_worker, workers=2,
                                         initializer=initialize_worker,
                                         initargs=("errors", barrier))
        self.assertEqual(list(caught.exception.errors), ["g0", "g1"])
        self.assertEqual(caught.exception.cancelled_group_ids, ("g2", "g3"))


if __name__ == "__main__":
    unittest.main()
