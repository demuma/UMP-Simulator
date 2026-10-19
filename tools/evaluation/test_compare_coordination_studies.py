"""Provenance failures and paired-support semantics for frozen study comparisons."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import compare_coordination_studies as comparison
from run_comparison import digest, write_json
from run_coordination_study import STUDY_VARIANTS


def overwrite(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def utility(side, errors):
    return dict(schema='ump.occupancy-evaluation.v1', reference=dict(cell_side_m=side, window_ms=1000),
        queries=[dict(column=0, row=0, x=0, y=0, start_ms=index*1000, end_ms=(index+1)*1000,
            scheduled_samples=9 if index==0 else 10, reference_available=True,
            answered=error is not None, reference=2, prediction=2+error if error is not None else None,
            absolute_error=error) for index, error in enumerate(errors)])


def reseal(root):
    """Rehash deliberate semantic mutations so tests distinguish integrity from parity."""
    case_dir = root / 'cases/mixed_density-seed-19'
    manifest = json.loads((case_dir / 'manifest.json').read_text())
    manifest['artifact_sha256'] = {p.name: digest(p) for p in case_dir.iterdir() if p.name!='manifest.json'}
    manifest['input_sha256'] = digest(case_dir / 'observations.json')
    manifest['policy_sha256'] = digest(case_dir / 'policy.json')
    for variant in manifest['variants']:
        variant['config_sha256'] = digest(case_dir / (variant['name'] + '.policy.json'))
        variant['result_sha256'] = digest(case_dir / (variant['name'] + '.json'))
    overwrite(case_dir / 'manifest.json', manifest)
    protocol = json.loads((root / 'protocol.json').read_text())
    summary = json.loads((root / 'summary.json').read_text())
    summary['protocol_sha256'] = digest(root / 'protocol.json')
    summary['cases']['mixed_density-seed-19'] = json.loads((case_dir / 'summary.json').read_text())
    overwrite(root / 'summary.json', summary)
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest.update(protocol_sha256=digest(root / 'protocol.json'), summary_sha256=digest(root / 'summary.json'),
        binary_sha256=protocol['binary_sha256'],
        case_manifests={'mixed_density-seed-19': digest(case_dir / 'manifest.json')})
    overwrite(root / 'manifest.json', manifest)


def bundle(root, after=False):
    root.mkdir()
    case_dir = root / 'cases/mixed_density-seed-19'
    case_dir.mkdir(parents=True)
    source = root / 'source/simulator/src/CellLocalAggregation.cpp'
    source.parent.mkdir(parents=True)
    source.write_text('new controller' if after else 'old controller')
    (root / 'AggregationReplay').write_bytes(b'new executable' if after else b'old executable')
    write_json(root / 'protocol.json', dict(schema='ump.coordination-protocol.v1',
        binary_sha256=digest(root / 'AggregationReplay'),
        source_sha256={'simulator/src/CellLocalAggregation.cpp': digest(source)},
        case_order=['mixed_density-seed-19'], seeds=[19], variants=STUDY_VARIANTS,
        query_presets={'primary': [10,1000], 'fine': [5,200]}, horizons={'full':'all', 'interior':'trim1000'},
        metrics=list(comparison.METRICS), statistical_unit='complete realization',
        reporting_regions='fixed quadrants', publication='private_final_snapshot'))
    write_json(case_dir / 'observations.json', dict(coverage=dict(x=0,y=0,width=80,height=80), end_ms=4000))
    write_json(case_dir / 'policy.json', {'same':'original policy'})
    write_json(case_dir / 'case.json', dict(kind='replicate', seed=19, description='frozen synthetic source'))
    summaries, variants = {}, []
    for name, _, _, _, coordination in STUDY_VARIANTS:
        local = name.startswith('local_')
        write_json(case_dir / (name + '.policy.json'), dict(coordination=coordination, numerical_bounds='same'))
        write_json(case_dir / (name + '.json'), dict(schema='test-evidence',
            output_support='changed' if after and local else 'same', runtime={'processing_ms':2 if after else 1}))
        write_json(case_dir / (name + '.audit.json'), dict(valid=True, violations=[]))
        write_json(case_dir / (name + '.metrics.json'), {})
        for preset, side in [('primary',10), ('fine',5)]:
            errors = [2,4,None,None] if after and local else [1,None,3,None]
            write_json(case_dir / (name + '.' + preset + '.utility.json'), utility(side, errors))
        summaries[name] = dict(retained_observation_fraction=.75 if after and local else .5,
            answered_query_coverage=.5, occupancy_mae=3 if after and local else 2,
            mean_observation_age_ms=100 if after and local else 200,
            p95_observation_age_ms=200 if after and local else 400, core_processing_ms=2 if after else 1)
        variants.append(dict(name=name, config_sha256=digest(case_dir / (name + '.policy.json')),
            result_sha256=digest(case_dir / (name + '.json')), independent_audit_valid=True))
    write_json(case_dir / 'summary.json', summaries)
    write_json(case_dir / 'pairs.json', [])
    write_json(case_dir / 'manifest.json', dict(schema='ump.coordination-case.v1', variants=variants,
        adaptive_deterministic_repeats=4))
    write_json(root / 'summary.json', dict(schema='ump.coordination-study.v1', protocol_sha256='',
        cases={'mixed_density-seed-19':summaries}, completed_cases=1, audited_replays=9, deterministic_repeats=4))
    write_json(root / 'manifest.json', dict(schema='ump.coordination-study-manifest.v1', source_unchanged=True))
    reseal(root)
    return root


class CoordinationComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ump-compare-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.before = bundle(self.root / 'before')
        self.after = bundle(self.root / 'after', True)
        self.output = self.root / 'comparison'

    def test_honest_delta_uses_same_old_new_scored_queries_and_counts_complete_cases(self):
        report = comparison.compare_studies(self.before, self.after, self.output)
        self.assertEqual(report['cases_verified'],1)
        self.assertEqual(report['reference_outputs_identical'],7)
        self.assertEqual(len(report['pairs']),2)
        pair = report['pairs'][0]
        self.assertEqual(pair['metrics']['retained_observation_fraction'],
                         dict(before=.5,after=.75,delta_after_minus_before=.25))
        self.assertEqual(pair['metrics']['mean_observation_age_ms']['delta_after_minus_before'],-100)
        self.assertEqual(pair['queries']['primary_full']['matched'],
                         dict(scored_queries=1,before=1,after=2,delta_after_minus_before=1))
        self.assertEqual(pair['queries']['primary_full']['before']['occupancy_mae'],2)
        self.assertEqual(pair['queries']['primary_full']['after']['occupancy_mae'],3)
        self.assertEqual(pair['queries']['primary_interior']['matched']['scored_queries'],0)
        self.assertIsNone(pair['queries']['primary_interior']['matched']['delta_after_minus_before'])
        self.assertEqual(report['aggregates'][0]['n'],1)
        self.assertEqual(report['aggregates'][0]['metrics']['matched_occupancy_mae']['n'],1)
        self.assertTrue((self.output/'paired-results.csv').is_file())
        manifest = json.loads((self.output/'manifest.json').read_text())
        self.assertEqual(manifest['comparison_sha256'],digest(self.output/'comparison.json'))
        self.assertEqual(manifest['paired_results_sha256'],digest(self.output/'paired-results.csv'))

    def test_artifact_tampering_fails_before_creating_output(self):
        path=self.after/'cases/mixed_density-seed-19/local_temporal_first.json'
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Artifact hash mismatch'):
            comparison.compare_studies(self.before,self.after,self.output)
        self.assertFalse(self.output.exists())

    def test_honestly_rehashed_reference_change_is_rejected(self):
        path=self.after/'cases/mixed_density-seed-19/common_temporal_first.json'
        value=json.loads(path.read_text()); value['output_support']='changed'
        overwrite(path,value); reseal(self.after)
        with self.assertRaisesRegex(ValueError,'Unmodified reference scientific output changed'):
            comparison.compare_studies(self.before,self.after,self.output)
        self.assertFalse(self.output.exists())

    def test_changed_input_original_policy_or_effective_policy_cannot_be_compared(self):
        for relative in ['observations.json','policy.json','local_spatial_first.policy.json']:
            with self.subTest(relative=relative):
                path=self.after/'cases/mixed_density-seed-19'/relative
                original=json.loads(path.read_text()); altered=deepcopy(original); altered['changed']=True
                overwrite(path,altered); reseal(self.after)
                with self.assertRaisesRegex(ValueError,'Frozen input or policy changed'):
                    comparison.compare_studies(self.before,self.after,self.output)
                overwrite(path,original); reseal(self.after)
                self.assertFalse(self.output.exists())

    def test_unequal_query_protocol_is_rejected(self):
        path=self.after/'protocol.json'; protocol=json.loads(path.read_text())
        protocol['query_presets']['primary'][0]=20
        overwrite(path,protocol); reseal(self.after)
        with self.assertRaisesRegex(ValueError,'query_presets'):
            comparison.compare_studies(self.before,self.after,self.output)

    def test_invalid_stored_independent_audit_is_rejected_even_when_rehashed(self):
        path=self.after/'cases/mixed_density-seed-19/local_temporal_first.audit.json'
        overwrite(path,dict(valid=False,violations=['source mismatch'])); reseal(self.after)
        with self.assertRaisesRegex(ValueError,'passing independent audit'):
            comparison.load_bundle(self.after)

    def test_missing_required_artifact_hash_and_source_tampering_are_rejected(self):
        path=self.after/'cases/mixed_density-seed-19/manifest.json'
        value=json.loads(path.read_text()); del value['artifact_sha256']['local_temporal_first.metrics.json']
        overwrite(path,value)
        top=self.after/'manifest.json'; manifest=json.loads(top.read_text())
        manifest['case_manifests']['mixed_density-seed-19']=digest(path); overwrite(top,manifest)
        with self.assertRaisesRegex(ValueError,'required artifact hashes'):
            comparison.load_bundle(self.after)
        source=self.before/'source/simulator/src/CellLocalAggregation.cpp'; source.write_text('tampered')
        with self.assertRaisesRegex(ValueError,'Artifact hash mismatch'):
            comparison.load_bundle(self.before)

    def test_existing_output_is_never_overwritten(self):
        comparison.compare_studies(self.before,self.after,self.output)
        original=digest(self.output/'comparison.json')
        with self.assertRaises(FileExistsError):
            comparison.compare_studies(self.before,self.after,self.output)
        self.assertEqual(digest(self.output/'comparison.json'),original)

    def test_manifest_paths_cannot_escape_bundle(self):
        for path in ('../elsewhere','/private/tmp/elsewhere','.'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                comparison.child(self.root,path)

    def test_undefined_metrics_are_preserved_and_not_counted_as_zero(self):
        self.assertEqual(comparison.paired_value(None,3),dict(before=None,after=3,delta_after_minus_before=None))
        with self.assertRaises(ValueError): comparison.paired_value(float('nan'),2)
        with self.assertRaises(ValueError): comparison.paired_value(True,2)
        pairs=[]
        for seed,values in [(19,(2,3)),(20,(4,1)),(21,(None,5))]:
            pairs.append(dict(kind='replicate',family='mixed_density',strategy='spatial_first',seed=seed,
                metrics={metric:comparison.paired_value(*values) for metric in comparison.METRICS}))
        original=deepcopy(pairs)
        pairs.append(dict(kind='mechanism',family='control',strategy='spatial_first',metrics={}))
        aggregate=comparison.aggregate_pairs(pairs)[0]
        self.assertEqual(aggregate['n'],3)
        self.assertEqual(aggregate['metrics']['occupancy_mae'],dict(n=2,mean=-1,median=-1,min=-3,max=1))
        self.assertEqual(pairs[:3],original)


if __name__=='__main__':
    unittest.main()
