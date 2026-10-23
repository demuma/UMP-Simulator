#!/usr/bin/env python3
"""Independent support/fragmentation regression cases; no MongoDB or network."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import struct
import unittest
import zlib

import yaml

SPEC = importlib.util.spec_from_file_location('ump_track_analysis', Path(__file__).with_name('analyze_tracks.py'))
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def fixture():
    coverage = {'x': 0, 'y': 0, 'width': 20, 'height': 20, 'leaf_depth': 2}
    batches = []
    raw = {'agents': [{'data_type': 'metadata', 'timestamp': '2026-10-23T00:00:00Z'}]}
    origin = datetime(2026, 10, 23, tzinfo=timezone.utc)
    for time in range(100, 2000, 100):
        items = []
        if time < 1000 or time >= 1200:
            track = 'opaque-visible-a' if time < 1000 else 'opaque-visible-b'
            items = [{'id': track, 'type': 'Adult Pedestrian', 'x': 1., 'y': 1., 'cell_id': 48}]
            raw['agents'].append({'data_type': 'agent data', 'timestamp': (origin + timedelta(milliseconds=time)).isoformat(),
                                  'agent_id': track, 'observation_track_id': track,
                                  'private_person_id': 'private-person-secret', 'type': 'Adult Pedestrian',
                                  'position': {'x': 1., 'y': 1.}})
        batches.append({'sequence': time // 100, 'observed_at_ms': time, 'status': 'measured', 'observations': items})
    source = {'schema': 'ump.observation-replay.v1', 'run_id': 'controlled-track-counterexample', 'sensor_id': 'sensor',
              'coverage': coverage, 'sampling_period_ms': 100, 'end_ms': 2000, 'batches': batches}
    agg = {'enabled': True, 'application_id': 'support-audit', 'window_ms': 400,
           'history': {'retention_ms': 3000, 'max_bins': 32, 'max_observations': 1000,
                       'max_identity_bytes': 64000, 'max_buckets': 64},
           'spatial_selection': {'min_depth': 2, 'max_evaluations': 128, 'preserve_valid_descendants': False},
           'temporal_adaptation': {'coordination': 'cell_local', 'extension_step_ms': 100,
                                   'max_window_ms': 2000, 'max_evaluations': 32, 'max_active_cells': 64},
           'policy_tree': {'id': 'controlled-policy', 'version': '1', 'max_nodes': 128, 'regions': [],
                           'execution': {'publication_model': 'private_final_snapshot', 'strategy': 'semantic_first',
                                         'semantic_secondary_strategy': 'temporal_first', 'release_trigger': 'policy_satisfied'},
                           'root': {'distinct_contributors': {'min': 2}, 'min_category_distinct_contributors': {'min': 2},
                                    'semantic_max_loss': {'max': .5}, 'cell_side_m': {'max': 10},
                                    'window_duration_ms': {'min': 400, 'max': 2000}, 'age_at_evaluation_ms': {'max': 2000}}},
           'semantic_taxonomy': {'id': 'controlled-taxonomy', 'version': '1', 'nodes': [
               {'id': 'road_user', 'loss': 1}, {'id': 'pedestrian', 'parent': 'road_user', 'loss': .5},
               {'id': 'adult_pedestrian', 'parent': 'pedestrian', 'loss': 0, 'input_types': ['Adult Pedestrian']}]},
           'publication': {'database': 'must-not-enter-replay'}, 'diagnostics': {'mode': 'off'},
           'diagnostics_directory': 'must-not-enter-replay'}
    cfg = {'simulation': {'time_step': .05},
           'sensors': [{'type': 'adaptive-grid-based', 'aggregation': agg}], 'regions': [], 'region_taxonomy': []}
    count = sum(len(b['observations']) for b in batches)
    cell = {'cell_id': 48, 'depth': 2, 'x': 0., 'y': 0., 'width': 5., 'height': 5.,
            'observation_contributions': count, 'distinct_road_users': 2, 'mean_sample_occupancy': count / 19,
            'effective_policy_id': 'not-used-by-independent-audit', 'semantic': {
                'taxonomy_id': 'controlled-taxonomy', 'taxonomy_version': '1',
                'min_category_distinct_contributors': 2, 'semantic_max_loss': 0, 'semantic_mean_loss': 0,
                'categories': [{'category_id': 'adult_pedestrian', 'observation_contributions': count,
                                'distinct_contributors': 2}]}}
    result = {'schema': 'ump.replay-result.v1', 'source': {'coverage': coverage, 'sampling_period_ms': 100, 'end_ms': 2000},
              'input_observation_contributions': count, 'releases': [{'start_ms': 0, 'end_ms': 2000, 'sealed_at_ms': 2000,
                   'policy_id': 'controlled-policy', 'policy_version': '1', 'cells': [cell]}]}
    result['source'].update(run_id=source['run_id'], sensor_id=source['sensor_id'])
    result['windows'] = [{'start_ms': 0, 'end_ms': 2000, 'evaluated_at_ms': 2000,
                          'cells': [{**copy.deepcopy(cell), 'selected': True}]}]
    return source, raw, cfg, result


class TrackAnalysisTests(unittest.TestCase):
    def test_native_support_is_not_person_support(self):
        source, raw, cfg, result = fixture()
        registry = analysis.private_registry(raw, source)
        summary, cells = analysis.audit_releases(source, result, analysis.replay_config(cfg), registry)
        self.assertEqual((cells[0]['n_track'], cells[0]['n_gt'], cells[0]['peak_concurrent_gt']), (2, 1, 1))
        self.assertEqual(cells[0]['track_to_person_ratio'], 2)
        self.assertEqual(summary['false_person_threshold_pass_cell_windows'], 1)
        self.assertEqual(summary['false_person_threshold_pass_semantic_bins'], 1)
        self.assertEqual(summary['retained_observation_fraction'], 1)
        self.assertEqual(summary['checked_operational_policy_violations'], 0)
        self.assertNotIn('private-person-secret', json.dumps([summary, cells]))
        self.assertNotIn('opaque-visible-a', json.dumps([summary, cells]))

    def test_identity_interventions_leave_physics_and_types_exact(self):
        source, raw, _, _ = fixture()
        before = copy.deepcopy(source); registry = analysis.private_registry(raw, source)
        for interval in (500, 1000):
            changed, mapping, proof = analysis.identity_variant(source, registry, interval)
            self.assertEqual(proof, analysis.audit_stream(source))
            self.assertEqual(len(set(mapping.values())), 1)
            self.assertGreater(len(mapping), 2) if interval == 500 else self.assertEqual(len(mapping), 2)
            self.assertNotIn('private-person-secret', json.dumps(changed))
        oracle, mapping, proof = analysis.identity_variant(source, registry, oracle=True)
        self.assertEqual(proof, analysis.audit_stream(source)); self.assertEqual(len(mapping), 1)
        self.assertNotIn('private-person-secret', json.dumps(oracle))
        self.assertEqual(source, before)
        with self.assertRaises(ValueError): analysis.identity_variant(source, registry, 500, oracle=True)
        with self.assertRaises(ValueError): analysis.identity_variant(source, registry, 0)

    def test_category_threshold_can_fail_independently(self):
        source, raw, cfg, result = fixture()
        cfg['sensors'][0]['aggregation']['policy_tree']['root']['distinct_contributors']['min'] = 1
        _, cells = analysis.audit_releases(source, result, analysis.replay_config(cfg), analysis.private_registry(raw, source))
        self.assertEqual(cells[0]['person_threshold_failures'], ['min_category_distinct_contributors'])

    def test_overlapping_bounds_include_empty_patches_but_not_touching(self):
        config = analysis.replay_config(fixture()[2])
        config['policy_regions'] = [
            {'x': 0, 'y': 0, 'width': 5, 'height': 5, 'type_requirements': {'distinct_contributors': {'min': 3}},
             'requirements': {'distinct_contributors': {'min': 1}}},
            {'x': 2.5, 'y': 0, 'width': 5, 'height': 5, 'type_requirements': {'distinct_contributors': {'min': 4}},
             'requirements': {'window_duration_ms': {'max': 1000}}},
            {'x': 5, 'y': 0, 'width': 5, 'height': 5, 'requirements': {'distinct_contributors': {'min': 99}}}]
        bounds = analysis.effective_bounds(config, {'x': 0, 'y': 0, 'width': 5, 'height': 5})
        self.assertEqual(bounds['distinct_contributors']['min'], 4)
        self.assertEqual(bounds['window_duration_ms']['max'], 1000)

    def test_normal_region_adapter_is_lossless_and_does_not_mutate(self):
        _, _, cfg, _ = fixture()
        cfg['region_taxonomy'] = [{'type': 'door', 'metric_requirements': {'distinct_contributors': {'min': 5}}}]
        cfg['regions'] = [{'id': 'door-one', 'type': 'door', 'area': {'x': 0, 'y': 0, 'width': 5, 'height': 5},
                           'metric_requirements': {'window_duration_ms': {'max': 1000}}}]
        cfg['sensors'][0]['aggregation']['policy_tree']['regions'] = ['door-one']
        before = copy.deepcopy(cfg); result = analysis.replay_config(cfg)
        self.assertEqual(result['policy_regions'][0]['type_requirements'], {'distinct_contributors': {'min': 5}})
        self.assertEqual(result['policy_regions'][0]['requirements'], {'window_duration_ms': {'max': 1000}})
        self.assertEqual(cfg, before)
        for name in ('enabled', 'publication', 'diagnostics', 'diagnostics_directory'): self.assertNotIn(name, result)
        unknown = copy.deepcopy(cfg); unknown['sensors'][0]['aggregation']['future_unknown_feature'] = True
        with self.assertRaises(ValueError): analysis.replay_config(unknown)
        cfg['sensors'][0]['aggregation']['policy_tree']['regions'].append('missing')
        with self.assertRaises(ValueError): analysis.replay_config(cfg)

    def test_bad_counts_geometry_policy_and_reused_output_rejected(self):
        source, raw, cfg, good = fixture(); config = analysis.replay_config(cfg)
        registry = analysis.private_registry(raw, source)
        for mutate in (
            lambda r: r['releases'][0]['cells'][0].update(distinct_road_users=3),
            lambda r: r['releases'][0]['cells'][0].update(x=1),
            lambda r: r['releases'][0].update(policy_version='wrong'),
            lambda r: r['releases'].append(copy.deepcopy(r['releases'][0])),
            lambda r: r['releases'][0]['cells'][0]['semantic']['categories'][0].update(distinct_contributors=3),
        ):
            result = copy.deepcopy(good); mutate(result)
            with self.assertRaises(ValueError): analysis.audit_releases(source, result, config, registry)
        config['policy_tree']['root']['distinct_contributors']['min'] = 3
        with self.assertRaises(ValueError): analysis.audit_releases(source, good, config, registry)

    def test_empty_release_denominators_are_null(self):
        source, raw, cfg, result = fixture(); result['releases'] = []
        summary, cells = analysis.audit_releases(source, result, analysis.replay_config(cfg), analysis.private_registry(raw, source))
        self.assertFalse(cells)
        for key in ('inflated_cell_fraction', 'false_person_threshold_pass_cell_fraction',
                    'false_person_threshold_pass_semantic_bin_fraction', 'maximum_track_to_person_ratio',
                    'mean_cell_track_to_person_ratio', 'contribution_weighted_mean_cell_side_m'):
            self.assertIsNone(summary[key])
        self.assertEqual(summary['retained_observation_fraction'], 0)

    def test_registry_and_stream_fail_closed(self):
        source, raw, _, _ = fixture()
        bad = copy.deepcopy(raw); bad['agents'][1]['position']['x'] = 2
        with self.assertRaises(ValueError): analysis.private_registry(bad, source)
        bad = copy.deepcopy(source); bad['batches'][0]['observations'][0]['x'] = 8
        with self.assertRaises(ValueError): analysis.audit_stream(bad)
        bad = copy.deepcopy(source); bad['batches'][0]['observations'].append(copy.deepcopy(bad['batches'][0]['observations'][0]))
        with self.assertRaises(ValueError): analysis.audit_stream(bad)
        bad = copy.deepcopy(source); bad['batches'][0]['status'] = 'unavailable'
        with self.assertRaises(ValueError): analysis.audit_stream(bad)

    def test_logical_release_hash_normalizes_numeric_spelling_and_ids(self):
        result = fixture()[3]; changed = copy.deepcopy(result)
        changed['releases'][0]['release_id'] = 'different-generated-release'
        changed['releases'][0]['cells'][0]['effective_policy_id'] = 'different-generated-policy-index'
        changed['releases'][0]['cells'][0]['x'] = 0
        changed['releases'][0]['cells'][0]['width'] = 5
        self.assertEqual(analysis.logical_release_hash(result), analysis.logical_release_hash(changed))
        changed['releases'][0]['start_ms'] = 100
        self.assertNotEqual(analysis.logical_release_hash(result), analysis.logical_release_hash(changed))

    def recording(self, folder):
        source, raw, cfg, result = fixture()
        (folder / 'private').mkdir(parents=True)
        for filename, value in [('observations.json', source), ('native_result.json', result), ('private/native_source.json', raw)]:
            (folder / filename).write_text(json.dumps(value))
        (folder / 'private/config.yaml').write_text(yaml.safe_dump(cfg))
        def chunk(kind, payload):
            return (struct.pack('>I', len(payload)) + kind + payload
                    + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff))
        png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 6, 0, 0, 0))
               + chunk(b'IDAT', zlib.compress((b'\x00' + b'\xff' * 8) * 2)) + chunk(b'IEND', b''))
        (folder / 'map_background.png').write_bytes(png)
        bundle = {'schema': 'ump.replay-viewer.v1', 'observations': 'observations.json',
                  'variants': [{'id': 'native', 'label': 'Controlled native support fixture', 'result': 'native_result.json'}],
                  'map': {'image': 'map_background.png', 'bounds': {k: source['coverage'][k] for k in ('x', 'y', 'width', 'height')},
                          'attribution': 'Controlled geometry fixture; no external map data'}}
        (folder / 'bundle.json').write_text(json.dumps(bundle))
        names = ('observations.json', 'native_result.json', 'private/native_source.json',
                 'private/config.yaml', 'map_background.png', 'bundle.json')
        proof = {'schema': 'ump.mapped-recording-proof.v1', 'status': 'verified', 'source_completed': True,
                 'files_sha256': {name: analysis.digest_file(folder / name) for name in names}}
        (folder / 'capture-proof.json').write_text(json.dumps(proof))

    def test_local_report_is_compact_and_does_not_overwrite_or_expose_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); self.recording(base / 'recording')
            report = analysis.analyze_recording(base / 'recording', base / 'analysis')
            self.assertEqual(report['native']['false_person_threshold_pass_cell_windows'], 1)
            self.assertEqual(set(report['variants']), {'original_episodes', 'fragment_500ms', 'fragment_1000ms', 'evaluation_oracle'})
            self.assertTrue(all(row['rerun'] == 'not_requested' for row in report['variants'].values()))
            self.assertNotIn('private-person-secret', json.dumps(report))
            self.assertNotIn('opaque-visible-a', json.dumps(report))
            self.assertEqual(report['variants']['evaluation_oracle']['scope'], 'evaluation_oracle_only')
            self.assertEqual(report['progress_clock']['replay_progress_step_ms'], 50)
            with self.assertRaises(ValueError): analysis.analyze_recording(base / 'recording', base / 'analysis')

    def test_optional_native_cpp_identity_replays(self):
        if os.environ.get('UMP_SKIP_CPP_TRACK_TEST') == '1':
            self.skipTest('C++ binary is currently being rebuilt by the integrated runner')
        default = Path(__file__).resolve().parents[2] / 'simulator/build/AggregationReplay'
        binary = Path(os.environ.get('UMP_AGGREGATION_REPLAY', default))
        if not binary.is_file(): self.skipTest('Existing AggregationReplay binary not available')
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); self.recording(base / 'recording')
            report = analysis.analyze_recording(base / 'recording', base / 'analysis', binary)
            for row in report['variants'].values():
                self.assertEqual(row['rerun'], 'verified')
                self.assertEqual(row['source_invariants'], report['source_invariants'])
            self.assertGreater(report['variants']['fragment_500ms']['results']['false_person_threshold_pass_cell_windows'], 0)
            self.assertEqual(report['variants']['evaluation_oracle']['results']['published_cell_windows'], 0)

    def test_completed_proof_and_canonical_pinned_paths_are_required(self):
        for mutate in (
            lambda p: p.update(source_completed=False),
            lambda p: p.update(schema='other'),
            lambda p: p['files_sha256'].pop('private/config.yaml'),
            lambda p: p['files_sha256'].update({'../escape.json': '0' * 64}),
            lambda p: p['files_sha256'].update({'private//config.yaml': '0' * 64}),
            lambda p: p['files_sha256'].update({'private/config.yaml': 'not-a-digest'}),
        ):
            with tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary); self.recording(base / 'recording')
                path = base / 'recording/capture-proof.json'; proof = json.loads(path.read_text()); mutate(proof)
                path.write_text(json.dumps(proof))
                with self.assertRaises(ValueError): analysis.analyze_recording(base / 'recording', base / 'analysis')
                self.assertFalse((base / 'analysis').exists())
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); self.recording(base / 'recording')
            with (base / 'recording/private/config.yaml').open('a') as handle: handle.write('\n# changed\n')
            with self.assertRaises(ValueError): analysis.analyze_recording(base / 'recording', base / 'analysis')


if __name__ == '__main__':
    unittest.main()
