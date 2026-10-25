"""Exact recipient materialization and adversarial frozen-family tests."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import regional_public_transcript as subject
import semantic_privacy
import static_regional_schedule as static
from collections import defaultdict


def source_fixture(local=False):
    data = dict(schema='ump.observation-replay.v1', run_id='static-test', sensor_id='sensor', coverage=copy.deepcopy(static.PUBLIC_COVERAGE), sampling_period_ms=100, end_ms=8000, batches=[])
    for time in range(100, 8000, 100):
        rows = []
        for (cell, x) in ((12288, 1), (12544, 21)):
            for person in range(3):
                rows.append(dict(id=f'{cell}-{person}', type='Adult' if person < 2 else 'Child', x=x + person * 0.02, y=1, cell_id=cell))
        data['batches'].append(dict(observed_at_ms=time, sequence=time // 100, status='measured', observations=rows))
    root = dict(distinct_contributors={'min': 2}, min_category_distinct_contributors={'min': 2}, cell_side_m={'min': 1.25, 'max': 20}, window_duration_ms={'min': 400, 'max': 4000}, age_at_evaluation_ms={'max': 4000}, semantic_max_loss={'max': 1}, semantic_suppression_fraction={'max': 0})
    config = dict(application_id='fixture', window_ms=400, policy_tree=dict(id='fixture', version='1', root=root, regions=['central'], execution=dict(strategy='semantic_first', semantic_secondary_strategy='temporal_first', release_trigger='policy_satisfied', publication_model='private_final_snapshot')), policy_regions=[dict(id='central', type='fresh', x=0, y=0, width=10, height=10, type_requirements={'window_duration_ms': {'max': 400}, 'age_at_evaluation_ms': {'max': 400}} if local else {}, requirements={})], semantic_taxonomy=dict(id='fixture', version='1', nodes=[dict(id='root', loss=1), dict(id='pedestrian', parent='root', loss=0.5), dict(id='adult', parent='pedestrian', loss=0, input_types=['Adult']), dict(id='child', parent='pedestrian', loss=0, input_types=['Child'])]))
    return (data, config)

def source_native(data, config, side, window):
    depth = {10: 3, 20: 2}[side]
    shift = 2 * (6 - depth)
    groups = defaultdict(list)
    for batch in data['batches']:
        t = batch['observed_at_ms']
        start = t // window * window
        end = min(start + window, data['end_ms'])
        for row in batch['observations']:
            groups[start, end, row['cell_id'] >> shift].append((t, row))
    windows = []
    releases = []
    for start in range(0, data['end_ms'], window):
        end = min(start + window, data['end_ms'])
        cells = []
        public = []
        for ((group_start, group_end, cid), rows) in sorted(groups.items()):
            if (group_start, group_end) != (start, end):
                continue
            geometry = static.decode_cell(data['coverage'], cid, depth)
            samples = sum((start <= b['observed_at_ms'] < end for b in data['batches']))
            n = len(rows)
            values = dict(observation_contributions=n, distinct_contributors=3, mean_sample_occupancy=n / samples, cell_side_m=side, cell_area_m2=side * side, window_duration_ms=end - start, age_at_evaluation_ms=end - start, post_window_delay_ms=0, measured_sample_fraction=1, min_category_distinct_contributors=3, semantic_max_loss=0.5, semantic_mean_loss=0.5, semantic_suppression_fraction=0, occupancy_mae=None)
            bounds = copy.deepcopy(config['policy_tree']['root'])
            if geometry['x'] == 0 and local_bound(config):
                bounds['window_duration_ms']['max'] = 400
                bounds['age_at_evaluation_ms']['max'] = 400
            checks = [dict(metric=metric, min=limits.get('min'), max=limits.get('max'), observed=values[metric], status='pass' if limits.get('min', float('-inf')) <= values[metric] <= limits.get('max', float('inf')) else 'fail') for (metric, limits) in bounds.items()]
            passing = all((check['status'] == 'pass' for check in checks))
            semantic = dict(schema='ump.semantic-release.v1', taxonomy_id='fixture', taxonomy_version='1', min_category_distinct_contributors=3, semantic_max_loss=0.5, semantic_mean_loss=0.5, categories=[dict(category_id='pedestrian', observation_contributions=n, distinct_contributors=3)])
            cell = dict(geometry, observation_contributions=n, distinct_road_users=3, mean_sample_occupancy=n / samples, selected=passing, assessment_status='pass' if passing else 'fail', semantic=semantic, metrics=values, checks=checks)
            cells.append(cell)
            if passing:
                public.append({key: copy.deepcopy(value) for (key, value) in cell.items() if key not in ('selected', 'assessment_status', 'metrics', 'checks')})
        windows.append(dict(start_ms=start, end_ms=end, evaluated_at_ms=end, cells=cells))
        if public:
            releases.append(dict(start_ms=start, end_ms=end, sealed_at_ms=end, cells=public))
    return dict(schema='ump.replay-result.v1', source={key: copy.deepcopy(data[key]) for key in ('run_id', 'sensor_id', 'coverage', 'sampling_period_ms', 'end_ms')}, parameters=dict(coordination='common_window', fixed_depth=depth, window_ms=window), windows=windows, releases=releases, runtime=dict(processing_ms=12345))

def local_bound(config):
    return bool(config['policy_regions'][0]['type_requirements'])


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def fixture(root, *, local=False, side=20, empty=False, varied_ids=False):
    data, base = source_fixture(local)
    if empty:
        for batch in data['batches']: batch['observations'] = []
    write(root / 'source.json', data)
    (root / 'native-binary').write_bytes(b'Frozen fixture binary; never executed')
    def receipt(name): return dict(path=name, sha256=subject.sha(root / name))
    cases = {}
    for window in static.WINDOWS:
        config = copy.deepcopy(base)
        if varied_ids:
            config['application_id'] += '/' + str(window)
            config['policy_tree']['id'] += '/' + str(window)
        result = source_native(data, config, side, window)
        for release in result['releases']:
            release.update(release_id='private-source-IN-' + str(release['start_ms']),
                model='private_final_snapshot', policy_id=config['policy_tree']['id'], policy_version='1')
            for cell in release['cells']:
                # This fixture has one selected region at [0,10)x[0,10).
                # Native preorder interns its union first (p0), then outside p1.
                cell['effective_policy_id'] = config['policy_tree']['id'] + '/1/' + (
                    'p0' if cell['x'] == 0 and cell['y'] == 0 else 'p1')
        plan = static.plan_schedule(data['coverage'], config, side)
        scalar = dict(valid=True, violations=[], input_observation_contributions=sum(
            len(batch['observations']) for batch in data['batches']), released_observation_contributions=0, released_cell_count=0)
        regional = []; bins = 0
        for private in result['windows']:
            for cell in private['cells']:
                if not cell['selected']: continue
                scalar['released_cell_count'] += 1
                scalar['released_observation_contributions'] += cell['observation_contributions']
                bins += len(cell['semantic']['categories'])
                geometry = plan['cells'][cell['cell_id']]['geometry']; bounds, touched = subject.effective(config, geometry)
                regional.append(dict(start_ms=private['start_ms'], end_ms=private['end_ms'], cell_id=cell['cell_id'],
                    depth=cell['depth'], intersected_regions=touched, effective_requirements=bounds,
                    recomputed_metrics={key: value for key, value in cell['metrics'].items() if key != 'occupancy_mae'}))
        audit = dict(status='verified', scalar=scalar, contribution_selection='all_contributions',
            selectively_suppressed_observations=0, semantic_published_cells=scalar['released_cell_count'],
            semantic_published_bins=bins, regional_recomputations=regional,
            source_accounting=dict(input_observations=scalar['input_observation_contributions'],
                retained_observations=scalar['released_observation_contributions'], selectively_suppressed_observations=0,
                whole_footprint_suppressed_observations=scalar['input_observation_contributions'] - scalar['released_observation_contributions']))
        names = {kind: f'{window}-{kind}.json' for kind in ('config', 'result', 'private_audit')}
        for kind, value in (('config', config), ('result', result), ('private_audit', audit)): write(root / names[kind], value)
        cases[str(window)] = {kind: receipt(name) for kind, name in names.items()}
        cases[str(window)]['independent_audit'] = dict(status='verified', scalar_valid=True, published_policy_violations=0)
    return dict(schema=subject.FAMILY_SCHEMA, public_coverage=data['coverage'], sampling_period_ms=100,
        end_ms=8000, side_m=side, public_policy_id='public-policy', method_alias=f'regional-static-{side}m',
        source=receipt('source.json'), native_binary=receipt('native-binary'), cases=cases)


def mutate(root, manifest, window, kind, change, *, refresh=True):
    receipt = manifest['cases'][str(window)][kind]
    path = root / receipt['path']; value = subject.read(path); change(value); write(path, value)
    if refresh: receipt['sha256'] = subject.sha(path)


class RegionalPublicTranscriptTests(unittest.TestCase):
    def test_control_matches_exact_native_4s_payload_grouping_semantics_and_accounting(self):
        for side in static.SIDES:
            with self.subTest(side=side), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); manifest = fixture(root, side=side, varied_ids=True)
                result = subject.compose_family(root, manifest); public = result['public_transcript']; audit = result['private_audit']
                native = subject.read(root / manifest['cases']['4000']['result']['path'])
                for release in native['releases']:
                    release['policy_id'] = manifest['public_policy_id']
                    for cell in release['cells']:
                        cell['effective_policy_id'] = manifest['public_policy_id'] + '/1/' + cell['effective_policy_id'].rsplit('/', 1)[1]
                expected = semantic_privacy.export_public(native, source_fixture()[1]['semantic_taxonomy'])
                self.assertEqual(public, expected)
                self.assertEqual(len(public['releases']), 2)
                self.assertTrue(all(len(r['cells']) == 2 for r in public['releases']))
                self.assertEqual(audit['stats']['retained_observation_contributions'], 474)
                self.assertEqual(audit['stats']['partition_audit']['nonempty_cell_intervals'], 4)
                self.assertTrue(audit['positive_control_equal_native_4s'])
                self.assertIsNone(audit['native_runtime']); self.assertIsNone(audit['native_process_wall_seconds'])
                text = json.dumps(public)
                for private in ('private-source', 'static-test', '12288-0', 'runtime', 'batches', 'retained_by_source_group'):
                    self.assertNotIn(private, text)

    def test_regional_cells_keep_exact_original_intervals_payloads_and_sealing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manifest = fixture(root, local=True)
            result = subject.compose_family(root, manifest); public = result['public_transcript']
            expected = {}
            for window in (400, 4000):
                native = subject.read(root / manifest['cases'][str(window)]['result']['path'])
                for release in native['releases']:
                    for cell in release['cells']:
                        if (cell['cell_id'] == 48) != (window == 400): continue
                        expected[(cell['cell_id'], release['start_ms'], release['end_ms'])] = (cell, release['sealed_at_ms'])
            actual = {(c['cell_id'], r['start_ms'], r['end_ms']): (c, r['sealed_at_ms']) for r in public['releases'] for c in r['cells']}
            self.assertEqual(set(actual), set(expected))
            for key, (cell, sealed) in actual.items():
                original, original_sealed = expected[key]
                self.assertEqual(sealed, original_sealed)
                self.assertEqual({k: v for k, v in cell.items() if k != 'effective_policy_id'},
                                 {k: v for k, v in original.items() if k != 'effective_policy_id'})
            self.assertEqual(result['private_audit']['stats']['retained_observation_contributions'], 474)
            self.assertFalse(result['private_audit']['positive_control_equal_native_4s'])

    def test_snapshot_default_hides_interior_views_and_logical_mode_requires_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manifest = fixture(root, local=True)
            snapshot = subject.compose_family(root, manifest)['public_transcript']
            self.assertEqual(snapshot['availability_model'], 'final_snapshot_at_horizon')
            self.assertEqual(semantic_privacy.public_view(snapshot, 7999)['releases'], [])
            self.assertEqual(semantic_privacy.public_view(snapshot, 8000)['releases'], snapshot['releases'])
            with self.assertRaisesRegex(ValueError, 'assumption/evidence'):
                subject.compose_family(root, manifest, availability_model='logical_sealing')
            result = subject.compose_family(root, manifest, availability_model='logical_sealing',
                logical_sealing_evidence='Offline logical visibility assumes instantaneous recipient delivery; no execution evidence.')
            logical = result['public_transcript']
            self.assertTrue(semantic_privacy.public_view(logical, 400)['releases'])
            self.assertTrue(all(r['available_at_ms'] == r['sealed_at_ms'] for r in logical['releases']))

    def test_empty_partition_exports_no_zero_certificates_or_retirement_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manifest = fixture(root, empty=True)
            result = subject.compose_family(root, manifest)
            self.assertEqual(result['public_transcript']['releases'], [])
            partition = result['private_audit']['stats']['partition_audit']
            self.assertEqual(partition['nonempty_cell_intervals'], 0)
            self.assertEqual(partition['empty_cell_intervals'], 32)
            self.assertEqual(result['private_audit']['stats']['input_observation_contributions'], 0)

    def test_schedule_is_declared_before_source_or_outcome_reads_and_is_outcome_independent(self):
        schedules = []
        for empty in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); manifest = fixture(root, local=True, empty=empty)
                original_read = subject.read; reads = []
                def record(path): reads.append(Path(path).name); return original_read(path)
                with patch.object(subject, 'read', side_effect=record), patch.object(static, 'plan_schedule', wraps=static.plan_schedule) as planned:
                    result = subject.compose_family(root, manifest)
                self.assertEqual(reads[:4], [f'{w}-config.json' for w in static.WINDOWS])
                self.assertEqual(reads[4], 'source.json')
                self.assertGreaterEqual(planned.call_count, 1)
                schedules.append(result['private_audit']['cell_window_ms'])
        self.assertEqual(schedules[0], schedules[1])
        self.assertEqual(set(schedules[0].values()), {400, 4000})

    def test_frozen_source_config_binary_result_and_private_audit_receipts_reject_tampering(self):
        for kind in ('source', 'native_binary', 'config', 'result', 'private_audit'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); manifest = fixture(root)
                receipt = manifest[kind] if kind in ('source', 'native_binary') else manifest['cases']['400'][kind]
                path = root / receipt['path']; path.write_bytes(path.read_bytes() + b' ')
                with self.assertRaisesRegex(ValueError, 'receipt differs'): subject.compose_family(root, manifest)

    def test_reforged_receipts_do_not_hide_public_private_semantic_count_or_timing_changes(self):
        changes = [
            ('public-private-field', lambda r: r['releases'][0]['cells'][0].update(private_track_id='secret')),
            ('missing-private-cell', lambda r: r['windows'][0]['cells'].pop(0)),
            ('missing-public-cell', lambda r: r['releases'][0]['cells'].pop(0)),
            ('count', lambda r: r['releases'][0]['cells'][0].update(observation_contributions=999)),
            ('semantic', lambda r: r['releases'][0]['cells'][0]['semantic'].update(semantic_mean_loss=0)),
            ('timing', lambda r: r['releases'][0].update(sealed_at_ms=399)),
            ('post-horizon-seal', lambda r: r['releases'][0].update(sealed_at_ms=8001)),
            ('effective-id', lambda r: r['releases'][0]['cells'][0].update(effective_policy_id='fixture/1/p999')),
            ('policy-id', lambda r: r['releases'][0].update(policy_id='OUT-policy')),
        ]
        for name, change in changes:
            with self.subTest(change=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); manifest = fixture(root, local=True)
                mutate(root, manifest, 400, 'result', change)
                with self.assertRaises((ValueError, KeyError)): subject.compose_family(root, manifest)

    def test_independent_audit_catches_unused_native_semantics_and_reforged_private_receipts(self):
        for change in ('unused-semantic', 'audit-metrics', 'audit-count', 'source-support'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); manifest = fixture(root)
                if change == 'unused-semantic':
                    def corrupt(result):
                        for container in (result['windows'][0]['cells'][0], result['releases'][0]['cells'][0]):
                            container['semantic']['categories'][0]['distinct_contributors'] = 2
                            container['semantic']['min_category_distinct_contributors'] = 2
                    mutate(root, manifest, 400, 'result', corrupt)
                elif change == 'audit-metrics':
                    mutate(root, manifest, 400, 'private_audit', lambda a: a['regional_recomputations'][0]['recomputed_metrics'].update(distinct_contributors=4))
                elif change == 'audit-count':
                    mutate(root, manifest, 400, 'private_audit', lambda a: a.update(semantic_published_cells=999))
                else:
                    path = root / 'source.json'; data = subject.read(path)
                    data['batches'][0]['observations'][0]['id'] = 'new-identity'; write(path, data)
                    manifest['source']['sha256'] = subject.sha(path)
                with self.assertRaises(ValueError): subject.compose_family(root, manifest)

    def test_family_cli_writes_only_private_permissioned_public_channel_and_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manifest = fixture(root); write(root / 'family.json', manifest)
            output = root / 'recipient'
            arguments = ['regional_public_transcript', '--family-manifest', str(root / 'family.json'), '--output', str(output)]
            with patch('sys.argv', arguments), contextlib.redirect_stdout(io.StringIO()): subject.main()
            self.assertEqual({p.name for p in output.iterdir()}, {'public.json', 'private-audit.json'})
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            for path in output.iterdir(): self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            semantic_privacy.validate_public(subject.read(output / 'public.json'))
            with patch('sys.argv', arguments), self.assertRaisesRegex(ValueError, 'fresh'): subject.main()

    def test_hard_policy_and_predeclared_family_constraints_cannot_be_changed(self):
        for change in ('hard-policy', 'missing-window', 'world-alias', 'private-source-alias'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); manifest = fixture(root)
                if change == 'hard-policy':
                    mutate(root, manifest, 1000, 'config', lambda c: c['policy_tree']['root']['distinct_contributors'].update(min=1))
                elif change == 'missing-window': del manifest['cases']['1000']
                elif change == 'world-alias': manifest['public_policy_id'] = 'urban-OUT-policy'
                else: manifest['method_alias'] = 'method-static-test'
                with self.assertRaises(ValueError): subject.compose_family(root, manifest)


if __name__ == '__main__': unittest.main()
