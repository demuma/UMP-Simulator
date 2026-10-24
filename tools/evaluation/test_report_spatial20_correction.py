#!/usr/bin/env python3
"""Small aggregate-only correction-report consistency fixtures."""
import copy
import unittest
import report_spatial20_correction as report


def case(retained=10):
    n=20;loss=.2 if retained else None
    return dict(config_sha256='a'*64,result_sha256='b'*64,native_process_wall_seconds=.1,
        independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0),
        stats=dict(input_observation_contributions=n,retained_observation_contributions=retained,
            retained_fraction=retained/n,observation_weighted_semantic_loss=loss,
            full_input_semantic_distortion=(n-retained+retained*(loss or 0))/n,
            observation_weighted_cell_side_m=10 if retained else None,
            observation_weighted_interval_duration_ms=400 if retained else None,
            core_processing_ms=50,source_accounting=dict(
                observation_to_release_delay_ms=dict(mean=250 if retained else None,p95=400 if retained else None),
                by_source_point_region={'region':dict(input_observation_contributions=n,retained_observation_contributions=retained)})))


def fixture():
    originals={};sources={};cases={}
    for source in report.SOURCES:
        old=dict(schema='ump.mapped-comparison.v1',status='verified',cases={},
            protocol=dict(observations_sha256='c'*64,binary_sha256='d'*64))
        for contract in report.CONTRACTS:
            for method in (*report.ADAPTIVE,*report.BASELINES):
                old['cases'][contract+'_'+method]=case(0 if contract=='original' and method.startswith('fixed_20m') else 10)
        originals[source]=(old,'e'*64)
        sources[source]=dict(summary_sha256='e'*64,bundle_sha256='f'*64,observations_sha256='c'*64,
            capture_proof_sha256='1'*64,original_binary_sha256='d'*64,horizon_ms=1000,
            sampling_period_ms=100,input_observation_contributions=20)
        for contract in report.CONTRACTS:
            for method in report.ADAPTIVE:
                cases[f'{source}_{contract}_{method}_off']=dict(case(11),enabled=False,off_policy_byte_identity_verified=True)
        for method in (*report.ADAPTIVE,'fixed_20m_1000ms'):
            cases[f'{source}_spatial20_{method}_on']=dict(case(12),enabled=True)
        cases[f'{source}_spatial20_fixed_20m_1000ms_off']=dict(case(10),enabled=False,
            off_policy_byte_identity_verified=True,fixed_release_identity_verified=True,fixed_private_window_identity_verified=True)
    summary=dict(schema='ump.spatial20-correction.v1',status='verified',
        completion_scope='all_16_predeclared_cases',executed_case_count=16,planned_case_count=16,
        cases=cases,protocol_sha256='2'*64,protocol=dict(native_binary_sha256='3'*64,sources=sources,selected_cases=list(cases)))
    return summary,originals


class CorrectionReportTests(unittest.TestCase):
    def test_complete_matrix_objective_deltas_and_separate_filtering(self):
        summary,old=fixture();result=report.build_report(summary,old,'4'*64)
        self.assertEqual(len(result['primary_tables']),4)
        self.assertEqual(len(result['correction_changes']),8)
        self.assertEqual(len(result['baseline_comparisons']),48)
        self.assertEqual(len(result['filtering_sensitivity']),6)
        delta=result['correction_changes'][0]['delta']
        self.assertAlmostEqual(delta['retained_fraction'],.05)
        self.assertAlmostEqual(delta['full_input_semantic_distortion'],-.04)
        self.assertEqual(delta['source_point_regions']['region']['retained_observation_delta'],1)
        first=result['primary_tables'][0]['rows']
        negative=next(row for row in first if row['method']=='fixed_20m_400ms')['metrics']
        self.assertEqual(negative['full_input_semantic_distortion'],1)
        self.assertIsNone(negative['retained_only_semantic_loss'])
        text=report.markdown(result)
        self.assertIn('Separate filtering sensitivity',text)
        self.assertIn('not a disjoint regional partition',text)
        self.assertIn('neither attack resistance nor a privacy gain',text)

    def test_reject_incomplete_study_and_policy_identity_change(self):
        summary,old=fixture();summary['executed_case_count']=15
        with self.assertRaisesRegex(ValueError,'sixteen'):report.build_report(summary,old)
        summary,old=fixture();summary['cases']['mixed_original_adaptive_immediate_off']['config_sha256']='9'*64
        with self.assertRaisesRegex(ValueError,'OFF policy'):report.build_report(summary,old)

    def test_reject_objective_denominator_or_regional_cohort_change(self):
        bad=case();bad['stats']['full_input_semantic_distortion']=.9
        with self.assertRaisesRegex(ValueError,'objective'):report.checked_case(bad,'bad')
        a=report.checked_case(case(),'before');b=copy.deepcopy(a)
        b['source_point_regions']['region']['input_observations']=19
        with self.assertRaisesRegex(ValueError,'Regional source denominator'):report.changes(a,b)

    def test_normalize_corrected_named_region_schema_without_inventing_outside(self):
        old=case();old['stats']['source_accounting']['by_source_point_region']['outside_policy_regions']=dict(
            input_observation_contributions=7,retained_observation_contributions=3)
        new=case(11);accounting=new['stats']['source_accounting']
        accounting.pop('by_source_point_region')
        accounting['by_region']={'region':dict(input_observations=20,retained_observations=11)}
        before=report.checked_case(old,'old schema');after=report.checked_case(new,'corrected schema')
        self.assertEqual(before['outside_named_regions']['retained_observations'],3)
        self.assertIsNone(after['outside_named_regions'])
        delta=report.changes(before,after)
        self.assertEqual(set(delta['source_point_regions']),{'region'})
        self.assertEqual(delta['source_point_regions']['region']['retained_observation_delta'],1)

    def test_reject_source_provenance_and_unverified_fixed_control(self):
        summary,old=fixture();summary['protocol']['sources']['mixed']['observations_sha256']='9'*64
        with self.assertRaisesRegex(ValueError,'source digest'):report.build_report(summary,old)
        summary,old=fixture();summary['cases']['mixed_spatial20_fixed_20m_1000ms_off']['fixed_release_identity_verified']=False
        with self.assertRaisesRegex(ValueError,'Fixed identity'):report.build_report(summary,old)


if __name__=='__main__':unittest.main()
