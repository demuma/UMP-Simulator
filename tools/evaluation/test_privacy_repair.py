"""Frozen-reference repair assessment, provenance and same-point timing checks."""
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from make_fixture import cell_id
from privacy_dataset import GRID, build_robustness_dataset
from run_comparison import digest, write_json
from run_coordination_study import source_files
from robustness_attacks import SKLEARN_VERSION
from run_privacy_robustness import (_load_reference, _repair_row, _repair_rollup,
                                    _source_point_ages, run_study)

ROOT=Path(__file__).resolve().parents[2]
BINARY=Path(os.environ.get('UMP_REPLAY_BINARY',str(ROOT/'simulator/build/AggregationReplay')))


def reference_fixture(directory):
    """Small completed mechanism-provenance fixture; no training data or pickles."""
    directory.mkdir(mode=0o700)
    shutil.copy2(BINARY,directory/'AggregationReplay.frozen')
    sources={}
    for path in source_files(ROOT):
        relative=str(path.relative_to(ROOT));destination=directory/'source'/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination);sources[relative]=digest(destination)
    write_json(directory/'protocol.json',dict(schema='ump.privacy-robustness-protocol.v1',
        status='predeclared',binary_sha256=digest(directory/'AggregationReplay.frozen'),source_sha256=sources))
    write_json(directory/'report.json',dict(schema='ump.privacy-robustness-report.v1',status='complete',
        protocol_sha256=digest(directory/'protocol.json')))
    artifacts={str(p.relative_to(directory)):digest(p) for p in directory.rglob('*') if p.is_file()}
    write_json(directory/'manifest.json',dict(schema='ump.privacy-robustness-manifest.v1',status='complete',
        binary_sha256=digest(directory/'AggregationReplay.frozen'),protocol_sha256=digest(directory/'protocol.json'),
        report_sha256=digest(directory/'report.json'),artifact_sha256=artifacts))
    return directory


def toy_source():
    identity=cell_id(2,2,GRID)
    return dict(coverage=deepcopy(GRID),sampling_period_ms=100,batches=[
        dict(observed_at_ms=t,observations=[dict(id='u',cell_id=identity)]) for t in (100,200)])


def release(start,end,sealed,contributions):
    return dict(start_ms=start,end_ms=end,sealed_at_ms=sealed,cells=[
        dict(depth=6,cell_id=cell_id(2,2,GRID),observation_contributions=contributions)])


def utility(errors):
    return dict(reference={'same_fixed_query':True},summary=dict(reference_queries=len(errors),
        answered_queries=sum(value is not None for value in errors)),queries=[
        dict(column=index,row=0,start_ms=0,end_ms=1000,absolute_error=value)
        for index,value in enumerate(errors)])


class SourceAgeComparisonTests(unittest.TestCase):
    def test_half_open_public_intervals_use_observation_time(self):
        source=toy_source()
        result=dict(releases=[release(100,200,300,1)])
        self.assertEqual(_source_point_ages(source,result),{(100,'u'):200})

    def test_overlapping_or_false_public_counts_are_rejected(self):
        source=toy_source()
        with self.assertRaisesRegex(ValueError,'Overlapping|Duplicate'):
            _source_point_ages(source,dict(releases=[release(100,300,300,2),release(100,200,200,1)]))
        with self.assertRaisesRegex(ValueError,'contribution count'):
            _source_point_ages(source,dict(releases=[release(100,300,300,1)]))

    def test_shared_source_age_prevents_suppression_selection_bias(self):
        source=toy_source()
        old=dict(releases=[release(100,300,300,2)])
        new=dict(releases=[release(200,300,300,1)])
        row=_repair_row(source,old,new,utility([1,2]),utility([2,None]))
        pooled=_repair_rollup([row])
        self.assertEqual(pooled['reference_retained_age_ms']['mean'],150)
        self.assertEqual(pooled['repaired_retained_age_ms']['mean'],100)
        self.assertEqual(pooled['shared_mean_age_delta_ms'],0)
        self.assertEqual(pooled['shared_count'],1)
        self.assertEqual(pooled['reference_retained_age_ms']['count'],2)
        self.assertEqual(pooled['repaired_retained_age_ms']['count'],1)
        self.assertEqual(pooled['lost'],1)
        self.assertEqual(pooled['gained'],0)
        self.assertEqual(pooled['matched_queries'],1)
        self.assertEqual(pooled['reference_matched_mae'],1)
        self.assertEqual(pooled['repaired_matched_mae'],2)
        self.assertEqual(pooled['reference_coverage'],1)
        self.assertEqual(pooled['repaired_coverage'],.5)
        self.assertEqual(pooled['reference_retained_age_ms']['p95'],200)


@unittest.skipUnless(BINARY.is_file(),'Build AggregationReplay for reference mechanism checks')
class ReferenceProvenanceTests(unittest.TestCase):
    def test_complete_reference_is_accepted_without_model_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            reference=reference_fixture(Path(temporary)/'reference')
            (reference/'unknown.joblib').write_bytes(b'Not a model; never deserialize')
            loaded=_load_reference(reference)
            self.assertEqual(loaded['binary'],reference.resolve()/'AggregationReplay.frozen')
            self.assertEqual(loaded['protocol']['binary_sha256'],digest(loaded['binary']))

    def test_incomplete_and_tampered_reference_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for name,target in [('binary','AggregationReplay.frozen'),('source','source/simulator/src/CellLocalAggregation.cpp'),
                                ('protocol','protocol.json'),('report','report.json')]:
                reference=reference_fixture(root/name)
                with (reference/target).open('ab') as stream:stream.write(b'\n')
                with self.subTest(target=target),self.assertRaises(ValueError):_load_reference(reference)
            reference=reference_fixture(root/'incomplete')
            manifest=json.loads((reference/'manifest.json').read_text());manifest['status']='running'
            (reference/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'completed'):_load_reference(reference)

    def test_reference_source_traversal_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);reference=reference_fixture(root/'reference')
            protocol=json.loads((reference/'protocol.json').read_text())
            protocol['source_sha256']['../escape']='0'*64
            (reference/'protocol.json').write_text(json.dumps(protocol))
            manifest=json.loads((reference/'manifest.json').read_text())
            manifest['protocol_sha256']=digest(reference/'protocol.json')
            manifest['artifact_sha256']['protocol.json']=manifest['protocol_sha256']
            report=json.loads((reference/'report.json').read_text())
            report['protocol_sha256']=manifest['protocol_sha256']
            (reference/'report.json').write_text(json.dumps(report))
            manifest['report_sha256']=digest(reference/'report.json')
            manifest['artifact_sha256']['report.json']=manifest['report_sha256']
            (reference/'manifest.json').write_text(json.dumps(manifest))
            dataset=root/'dataset';build_robustness_dataset(dataset,20261022,2,2,2,2,1000)
            with self.assertRaisesRegex(ValueError,'relative'):
                run_study(dataset,root/'output',BINARY,attack_families=('logistic',),reference_study=reference)
            self.assertFalse((root/'output').exists())


@unittest.skipUnless(BINARY.is_file(),'Build AggregationReplay for paired repair integration')
class RepairStudyIntegrationTests(unittest.TestCase):
    def test_identical_reference_binary_has_zero_repair_deltas_and_separate_attacks(self):
        with tempfile.TemporaryDirectory(prefix='ump-repair-study-') as temporary:
            root=Path(temporary);reference=reference_fixture(root/'reference')
            original_reference={str(p.relative_to(reference)):digest(p) for p in reference.rglob('*') if p.is_file()}
            dataset=root/'dataset';build_robustness_dataset(dataset,20261022,2,2,2,2,1000)
            output=root/'study'
            report=run_study(dataset,output,BINARY,bootstrap_repeats=5,
                             attack_families=('logistic',),reference_study=reference)
            self.assertEqual(report['independent_validation']['checks'],112)
            self.assertEqual(len(report['independent_validation']['deterministic_repeats']),6)
            controls=report['independent_validation']['shared_mechanism_reference_controls']
            self.assertEqual({r['variant'] for r in controls},
                             {'fixed_20m_1000ms','common_temporal_first','common_spatial_first'})
            self.assertTrue(all(r['identical'] and r['audit_valid'] for r in controls))
            self.assertEqual(len(report['attacks']),18)
            self.assertEqual(len({(a['variant'],a['knowledge_profile']) for a in report['attacks']}),18)
            for record in report['attacks']:
                self.assertEqual(record['training_groups'],2)
                self.assertEqual(record['calibration_groups'],2)
                for assessment in record['test_by_distribution'].values():
                    if record['variant'].startswith('local_'):
                        self.assertEqual(assessment['paired_vs_reference_local']['auc_difference'],0)
                        self.assertEqual(assessment['paired_vs_reference_local']['interval'],[0,0])
            for cohort,priorities in report['repair_comparison_by_distribution'].items():
                for priority,comparison in priorities.items():
                    self.assertEqual(comparison['delta_retention_pp'],0)
                    self.assertEqual(comparison['lost'],0)
                    self.assertEqual(comparison['gained'],0)
                    self.assertEqual(comparison['reference_coverage'],comparison['repaired_coverage'])
                    self.assertEqual(comparison['reference_matched_mae'],comparison['repaired_matched_mae'])
                    self.assertIn(comparison['shared_mean_age_delta_ms'],(None,0))
            protocol=json.loads((output/'protocol.json').read_text())
            self.assertEqual(len(protocol['variants']),7)
            self.assertEqual(protocol['reference_study']['binary_sha256'],digest(output/'AggregationReplay.reference.frozen'))
            self.assertEqual(protocol['reference_study']['source_sha256'],json.loads((reference/'protocol.json').read_text())['source_sha256'])
            commands=json.loads((output/'commands.json').read_text())
            self.assertEqual(len(commands),112)
            for row in commands:
                expected='AggregationReplay.reference.frozen' if row['variant'].startswith('reference_') else 'AggregationReplay.frozen'
                self.assertEqual(Path(row['command'][0]).name,expected)
            self.assertEqual(original_reference,{str(p.relative_to(reference)):digest(p) for p in reference.rglob('*') if p.is_file()})
            with self.assertRaises(FileExistsError):
                run_study(dataset,output,BINARY,attack_families=('logistic',),reference_study=reference)


def histogram_available():
    try:return sys.version_info >= (3,11) and importlib.metadata.version('scikit-learn') == SKLEARN_VERSION
    except importlib.metadata.PackageNotFoundError:return False


@unittest.skipUnless(BINARY.is_file() and histogram_available(),'Optional pinned histogram environment required')
class NonlinearRepairIntegrationTests(unittest.TestCase):
    def test_reference_mechanisms_get_separate_histogram_models(self):
        with tempfile.TemporaryDirectory(prefix='ump-repair-histogram-') as temporary:
            root=Path(temporary);reference=reference_fixture(root/'reference')
            dataset=root/'dataset';build_robustness_dataset(dataset,20261022,2,2,2,2,1000)
            output=root/'study'
            report=run_study(dataset,output,BINARY,bootstrap_repeats=2,reference_study=reference)
            self.assertEqual(len(report['attacks']),36)
            self.assertEqual(len(list((output/'models').glob('*.joblib'))),18)
            self.assertEqual(report['independent_validation']['checks'],112)
            for attack in report['attacks']:
                if attack['variant'].startswith('local_'):
                    for assessment in attack['test_by_distribution'].values():
                        self.assertEqual(assessment['paired_vs_reference_local']['auc_difference'],0)
                        self.assertEqual(assessment['paired_vs_reference_local']['interval'],[0,0])
                if attack['attack_family']=='hist_gradient_boosting':
                    self.assertEqual(attack['model_metadata']['versions']['scikit-learn'],SKLEARN_VERSION)
                    self.assertEqual(attack['model_metadata']['training_rows'],4)
                    self.assertEqual(Path(attack['model_metadata']['model_path']).parent,output.resolve()/'models')


if __name__=='__main__':unittest.main()
