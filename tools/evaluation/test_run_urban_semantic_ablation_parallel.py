"""Synthetic adapter boundaries: no study, native replay or MIA execution."""
from contextlib import nullcontext, redirect_stderr
import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_urban_semantic_ablation_parallel as p

_REAL_LOCK = p.study_lock


def reference(path):
    path = Path(path)
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def authenticated(value):
    path = Path(value['path'])
    p.require(reference(path) == value, 'Synthetic bytes changed')
    return path


class ParallelAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.output = self.root / 'results' / 'study'
        self.output.mkdir(parents=True)
        (self.output / 'groups').mkdir()
        (self.output / 'protocol.json').write_text('{"frozen":"serial protocol"}')
        self.protocol_before = (self.output / 'protocol.json').read_bytes()
        self.protocol = dict(schema=p.s.SCHEMA, original_config={'sha256': 'config'},
                             variant_configs={'method': {'sha256': 'variant'}},
                             native_binary={'sha256': 'native'}, minimum_free_bytes=100)
        self.context = dict(manifest=dict(groups=[dict(group_id='second', split='train'),
                                                       dict(group_id='first', split='test')]))
        self.files = []
        for name in ('wrapper.py', 'wrapper_test.py', 'helper.py', 'helper_test.py'):
            path = self.root / name
            path.write_text(name)
            self.files.append(path)
        self.read = self.start(patch.object(p.s, 'read_protocol',
                                            return_value=(self.output, self.protocol, self.context)))
        self.lock = self.start(patch.object(p, 'study_lock', side_effect=lambda output: nullcontext(self.output)))
        self.start(patch.object(p.s, 'reference', side_effect=reference))
        self.start(patch.object(p.s, 'authenticated', side_effect=authenticated))
        self.start(patch.object(p, '_implementation_files', side_effect=lambda: [reference(f) for f in self.files]))
        self.disk = self.start(patch.object(p.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 10**15})()))
        self.collect = self.start(patch.object(p.s, 'collect', return_value=([{}, {}], [{}, {}], [{}])))
        self.group = self.start(patch.object(p.s, 'process_group', side_effect=self.process_group))

    def start(self, mock):
        value = mock.start()
        self.addCleanup(mock.stop)
        return value

    def process_group(self, output, protocol, context, group):
        directory = output / 'groups' / group['group_id']
        directory.mkdir()
        summary = dict(group, status='verified')
        (directory / 'summary.json').write_text(json.dumps(summary))
        return summary

    def scheduler(self, groups, worker, *, workers, initializer, initargs, before_submit, on_result):
        initializer(*initargs)
        results = []
        for group in groups:
            before_submit(group)
            result = worker(group)
            on_result(group, result)
            results.append(result)
        return results

    def prepare(self, **kwargs):
        return p.prepare_execution(self.output, **kwargs)

    def rewrite_plan(self, mutate):
        path = self.output / p.PLAN
        plan = json.loads(path.read_text())
        mutate(plan)
        path.write_text(json.dumps(plan))
        (self.output / p.PLAN_SHA).write_text(json.dumps({'sha256': reference(path)['sha256']}))

    def test_prepare_freezes_six_workers_new_code_and_base_without_changing_protocol(self):
        plan = self.prepare()
        self.assertEqual(plan['workers'], 6)
        self.assertEqual(plan['base_protocol'], reference(self.output / 'protocol.json'))
        self.assertEqual(plan['base_protocol_schema'], p.s.SCHEMA)
        self.assertEqual(plan['original_config'], self.protocol['original_config'])
        self.assertEqual(plan['group_order'], self.context['manifest']['groups'])
        self.assertEqual(len(plan['implementation_files']), 4)
        self.assertFalse(plan['mia_allowed'])
        self.assertFalse(plan['isolated_runtime_benchmark'])
        self.assertEqual((self.output / 'protocol.json').read_bytes(), self.protocol_before)
        with self.assertRaisesRegex(ValueError, 'Existing'):
            self.prepare()
        self.group.assert_not_called()
        self.collect.assert_not_called()

    def test_invalid_workers_or_disk_allowance_never_prepare(self):
        for workers in (0, 7, True, 1.5):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                self.prepare(workers=workers)
        for reserve in (0, -1, float('inf'), float('nan'), True):
            with self.subTest(reserve=reserve), self.assertRaises(ValueError):
                self.prepare(worker_disk_reserve_gib=reserve)
        self.assertFalse((self.output / p.PLAN).exists())

    def test_completed_or_attempted_group_forbids_prepare_and_is_untouched(self):
        directory = self.output / 'groups' / 'second'
        directory.mkdir()
        path = directory / 'summary.json'
        path.write_text('{"status":"verified"}')
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'completed or attempted'):
            self.prepare()
        self.assertEqual(path.read_bytes(), before)
        self.lock.assert_not_called()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'completed or attempted'):
            self.prepare()

    def test_every_mia_or_utility_artifact_forbids_prepare(self):
        for name in (*p.s.FIT_OUTPUTS, 'utility-report.json', p.ATTEMPT, p.RECEIPT, p.FAILED):
            with self.subTest(name=name):
                path = self.output / name
                path.write_text('{}')
                with self.assertRaisesRegex(ValueError, 'Existing'):
                    self.prepare()
                path.unlink()

    def test_run_uses_one_parent_authentication_initializes_context_and_collects_after_results(self):
        self.prepare()
        self.read.reset_mock()
        with patch.object(p, 'execute_recordings', side_effect=self.scheduler) as scheduler:
            receipt = p.run_utility(self.output)
        self.read.assert_called_once_with(self.output)
        self.assertEqual(receipt['workers'], 6)
        self.assertEqual(receipt['ordered_group_ids'], ['second', 'first'])
        self.assertEqual([c.args[3]['group_id'] for c in self.group.call_args_list], ['second', 'first'])
        kwargs = scheduler.call_args.kwargs
        self.assertIs(kwargs['initializer'], p._initialize_worker)
        self.assertIs(kwargs['initargs'][2], self.context)
        self.collect.assert_called_once_with(self.output, self.protocol, self.context,
                                             verify_archives=True, require_complete=True)
        self.assertEqual(receipt['mia_status'], 'not_started')
        self.assertFalse(receipt['isolated_runtime_benchmark'])
        self.assertTrue((self.output / p.RECEIPT).exists())
        self.assertEqual((self.output / 'protocol.json').read_bytes(), self.protocol_before)
        with self.assertRaisesRegex(ValueError, 'fresh study'):
            p.run_utility(self.output)
        self.assertEqual(self.group.call_count, 2)

    def test_incomplete_summary_fails_without_collect_or_success_receipt_or_retry(self):
        self.prepare()
        self.group.side_effect = lambda output, protocol, context, group: dict(group, status='incomplete')
        with patch.object(p, 'execute_recordings', side_effect=self.scheduler), self.assertRaisesRegex(ValueError, 'incomplete'):
            p.run_utility(self.output)
        self.collect.assert_not_called()
        self.assertFalse((self.output / p.RECEIPT).exists())
        self.assertEqual(json.loads((self.output / p.FAILED).read_text())['status'], 'failed')
        with self.assertRaisesRegex(ValueError, 'Existing'):
            p.run_utility(self.output)
        self.assertEqual(self.group.call_count, 1)

    def test_aggregate_disk_floor_and_all_active_allowances_are_required_before_launch(self):
        self.prepare(workers=6, worker_disk_reserve_gib=2)
        required = 100 + 2 * 2 * 1024**3  # Only two declared recordings can be active.
        self.disk.return_value.free = required - 1
        with patch.object(p, 'execute_recordings') as scheduler, self.assertRaisesRegex(ValueError, 'aggregate free disk'):
            p.run_utility(self.output)
        scheduler.assert_not_called()
        self.assertFalse((self.output / p.ATTEMPT).exists())
        self.collect.assert_not_called()

    def test_changed_wrapper_helper_or_test_bytes_forbid_launch(self):
        self.prepare()
        self.files[2].write_text('changed helper')
        with patch.object(p, 'execute_recordings') as scheduler, self.assertRaisesRegex(ValueError, 'bytes changed'):
            p.run_utility(self.output)
        scheduler.assert_not_called()
        self.assertFalse((self.output / p.ATTEMPT).exists())

    def test_reordered_groups_rejected_even_with_new_plan_digest(self):
        self.prepare()
        self.rewrite_plan(lambda plan: plan['group_order'].reverse())
        with self.assertRaisesRegex(ValueError, 'recording order'):
            p.run_utility(self.output)
        self.group.assert_not_called()

    def test_changed_plan_digest_rejected(self):
        self.prepare()
        (self.output / p.PLAN).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'digest differs'):
            p.run_utility(self.output)

    def test_atomic_exclusive_write_keeps_existing_bytes(self):
        path = self.output / 'atomic.json'
        p._write_new(path, {'status': 'first'})
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            p._write_new(path, {'status': 'second'})
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(list(self.output.glob('atomic.json.tmp-*')))

    def test_real_lock_shares_the_serial_root_lock_and_excludes_another_runner(self):
        with patch.object(p.s, 'ROOT', self.root):
            with _REAL_LOCK(self.output):
                self.assertTrue((self.output / '.semantic-ablation.lock').is_file())
                with self.assertRaises(BlockingIOError):
                    with _REAL_LOCK(self.output):
                        self.fail('Second runner acquired the same root lock')

    def test_scheduler_failure_records_errors_and_never_collects_or_retries(self):
        self.prepare()
        error = p.BatchFailure({}, {'second': TimeoutError('native timeout')}, ['first'], ['first'])
        with patch.object(p, 'execute_recordings', side_effect=error), self.assertRaises(p.BatchFailure):
            p.run_utility(self.output)
        failure = json.loads((self.output / p.FAILED).read_text())
        self.assertEqual(failure['errors'], {'second': 'native timeout'})
        self.assertEqual(failure['unsubmitted_group_ids'], ['first'])
        self.collect.assert_not_called()
        self.assertFalse((self.output / p.RECEIPT).exists())
        with self.assertRaisesRegex(ValueError, 'Existing'):
            p.run_utility(self.output)

    def test_receipt_directory_failure_is_recorded_after_attempt(self):
        self.prepare()
        with patch.object(p.Path, 'mkdir', side_effect=OSError('synthetic mkdir failure')), self.assertRaises(OSError):
            p.run_utility(self.output)
        self.assertTrue((self.output / p.ATTEMPT).exists())
        self.assertTrue((self.output / p.FAILED).exists())
        self.group.assert_not_called()

    def test_failed_full_collection_prevents_success_receipt(self):
        self.prepare()
        self.collect.side_effect = ValueError('artifact validation failed')
        with patch.object(p, 'execute_recordings', side_effect=self.scheduler), self.assertRaisesRegex(ValueError, 'artifact validation'):
            p.run_utility(self.output)
        self.assertFalse((self.output / p.RECEIPT).exists())
        self.assertTrue((self.output / p.FAILED).exists())

    def test_cli_has_no_mia_action_and_cannot_override_frozen_worker_count(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            p.main(['--fit-mia', str(self.output)])
        with self.assertRaisesRegex(ValueError, 'frozen'):
            p.main(['--run-utility', str(self.output), '--workers', '6'])
        self.group.assert_not_called()


if __name__ == '__main__':
    unittest.main()
