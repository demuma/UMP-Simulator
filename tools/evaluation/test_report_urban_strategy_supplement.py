"""Synthetic public-boundary tests; no sources, native replay or fitted models."""
from copy import deepcopy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import report_urban_strategy_supplement as reporting
from test_report_urban_track_window_primary import private_report as original_fixture

SECRET = 'PRIVATE_TARGET_seed1125899906842699_GROUP_/private/source'


def private_report(*, utility=False):
    value=original_fixture()
    value.update(schema=reporting.INPUT_SCHEMA,supplement_id=SECRET,original_primary_result_preserved=True,
        method_catalog=[{'id':name,'label':SECRET,'source_path':SECRET} for name,_ in reporting.METHODS])
    for entry in value['method_catalog']:
        if entry['id'] in reporting.EXECUTION_CATALOG:
            strategy,secondary,trigger=reporting.EXECUTION_CATALOG[entry['id']]
            entry.update(kind='native_adaptive',strategy=strategy,secondary_strategy=secondary,release_trigger=trigger)
    template=deepcopy(value['analysis']['attacks']['adaptive_semantic_first'])
    worldutility=deepcopy(value['analysis']['utility']['adaptive_semantic_first'])
    for name in reporting.NEW_IDS:
        value['analysis']['attacks'][name]=deepcopy(template)
        value['analysis']['utility'][name]=deepcopy(worldutility)
    for group in value['group_outcomes']:
        group['cases'].extend({'method_id':name,'world':world,'status':'verified','private_target':SECRET}
                              for name in reporting.NEW_IDS for world in ('IN','OUT'))
    repair={key:'a'*64 for key in reporting.REPAIR_HASH_FIELDS}
    repair.update(reporting.REPAIR_COUNTS)
    repair.update(source_validation_profile=reporting.PROFILE,original_test_source_status_counts={'invalid':32},private_source=SECRET)
    lineage={key:'b'*64 for key in reporting.HASH_FIELDS}
    lineage.update(source_resimulations=0,source_replacements=0,original_model_refits=0,original_threshold_retunes=0,imported_groups=72,
        imported_method_world_rows=1584,new_method_world_rows=576,new_native_executions=576,
        old_locked_variants=22,new_attack_variants=8,hard_policy_unchanged=True,diagnostic_repair=repair,
        feature_vectors=SECRET,original_model_weights=SECRET)
    value['strategy_supplement']={'public_lineage':lineage,'raw_references':SECRET}
    value['native_execution_summary']={key:{name:dict(runs=144 if key=='by_method' else 64,wall_seconds_mean=34.,wall_seconds_p50=33.,
        wall_seconds_p95=36.,wall_seconds_maximum=39.,raw_native_rows=SECRET) for name in reporting.NEW_IDS}
        for key in ('by_method','by_method_test')}
    value['exploratory_contrasts']={}
    for key,left,right,seed in reporting.CONTRASTS:
        value['exploratory_contrasts'][key]=dict(left=left,right=right,metric='ROC_AUC',private_scores=SECRET,
            representations={name:dict(auc_difference=.01,interval=[-.05,.07],confidence_level=.95,
                seed=seed,replicates=1000,independent_groups=32,private_samples=SECRET)
                for name in reporting.REPRESENTATIONS})
    if utility:
        value['schema']=reporting.UTILITY_INPUT_SCHEMA;value['mia_status']='not_started'
        value['utility']=value.pop('analysis')['utility'];value.pop('exploratory_contrasts')
        lineage['new_attack_variants']=0
    return value


class SupplementaryReportTests(unittest.TestCase):
    def test_fifteen_methods_all_worlds_and_actual_planned_counts(self):
        result=reporting.compact_report(private_report())
        self.assertEqual(result['phase'],'mia');self.assertEqual(result['analysis_status'],'complete')
        self.assertEqual(result['utility_status'],'complete');self.assertEqual(len(result['methods']),15)
        outcomes=result['source_and_execution']
        self.assertEqual(outcomes['planned_native_cases'],1872)
        self.assertEqual(outcomes['planned_new_native_cases'],576)
        self.assertEqual(outcomes['planned_recipient_streams'],2160)
        self.assertEqual(outcomes['recording_status_by_split']['test']['verified'],32)
        for method in result['methods']:
            self.assertEqual(outcomes['method_world_status'][method['id']]['observed'],144)
            self.assertEqual(method['attacks']['semantic111']['complete_test_groups'],32)
            self.assertEqual(method['utility']['IN']['macro_means']['retained_fraction']['recordings'],32)
        self.assertEqual(sum(m['origin']=='supplementary_new' for m in result['methods']),4)

    def test_utility_stage_has_no_new_or_historical_attack_results(self):
        result=reporting.compact_report(private_report(utility=True))
        text=reporting.markdown(result)
        self.assertEqual(result['phase'],'utility');self.assertEqual(result['mia_status'],'not_started')
        self.assertEqual(result['interpretation_gate'],'not_evaluated')
        self.assertTrue(all(m['attacks'][r]['metrics'] is None for m in result['methods'] for r in reporting.REPRESENTATIONS))
        self.assertIn('MIA for the new strategies has not started',text)
        self.assertIn('Historical original attack scores are omitted',text)
        self.assertNotIn('| Full111 AUC |',text)
        self.assertTrue(all(v['status']=='not_evaluated' for c in result['exploratory_contrasts'].values() for v in c['representations'].values()))

    def test_utility_stage_rejects_analysis_contrasts_or_started_mia(self):
        mutations=[lambda p:p.update(mia_status='started'),lambda p:p.update(analysis={'status':'complete'}),
            lambda p:p.update(exploratory_contrasts={'temporal_vs_spatial':{}}),
            lambda p:p['strategy_supplement']['public_lineage'].update(new_attack_variants=8)]
        for mutate in mutations:
            value=private_report(utility=True);mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)

    def test_private_inputs_and_messages_are_projected_away_without_mutation(self):
        value=private_report();before=deepcopy(value)
        result=reporting.compact_report(value,input_sha256='0'*64)
        self.assertEqual(value,before)
        encoded=json.dumps(result,allow_nan=False)
        self.assertNotIn(SECRET,encoded)
        self.assertNotIn('PRIVATE_SOURCE_TARGET',encoded)
        self.assertNotIn('/private/',encoded)
        for key in ('group_id','target_id','seed','path','rows','weights','group_scores','model_weights',
                    'raw_motion','private_positions','command','error','raw_references','feature_vectors'):
            self.assertNotIn('"'+key+'"',encoded)
        self.assertEqual(result['provenance']['private_report_sha256'],'0'*64)
        self.assertEqual(result['provenance']['supplement_id_sha256'],hashlib.sha256(SECRET.encode()).hexdigest())

    def test_repair_failure_history_and_hard_policy_are_mandatory(self):
        mutations=[lambda p:p['strategy_supplement']['public_lineage'].pop('diagnostic_repair'),
            lambda p:p['strategy_supplement']['public_lineage'].update(hard_policy_unchanged=False),
            lambda p:p['strategy_supplement']['public_lineage']['diagnostic_repair'].update(original_test_source_status_counts={'verified':32}),
            lambda p:p['strategy_supplement']['public_lineage'].update(source_resimulations=1),
            lambda p:p['strategy_supplement']['public_lineage'].update(imported_groups=71),
            lambda p:p['strategy_supplement']['public_lineage'].update(original_models_sha256=SECRET)]
        for mutate in mutations:
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)
        lineage=reporting.compact_report(private_report())['supplementary_lineage']
        self.assertEqual(lineage['diagnostic_repair']['original_test_source_status_counts'],{'invalid':32})
        self.assertEqual(lineage['old_locked_variants'],22);self.assertEqual(lineage['new_attack_variants'],8)

    def test_catalog_missing_duplicate_or_unregistered_method_rejected(self):
        for mutate in (lambda p:p['method_catalog'].pop(),
                       lambda p:p['method_catalog'].__setitem__(0,deepcopy(p['method_catalog'][1])),
                       lambda p:p['method_catalog'][0].update(id='test_chosen_winner')):
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)

    def test_extra_method_or_representation_or_world_rejected(self):
        mutations=[lambda p:p['analysis']['attacks'].update(unregistered={}),
            lambda p:p['analysis']['utility'].update(unregistered={}),
            lambda p:p['analysis']['attacks']['adaptive_temporal_first'].update(best_attack={}),
            lambda p:p['analysis']['utility']['adaptive_temporal_first'].update(unregistered={})]
        for mutate in mutations:
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)

    def test_duplicate_recording_and_case_or_bad_split_rejected(self):
        mutations=[lambda p:p['group_outcomes'].append(deepcopy(p['group_outcomes'][0])),
            lambda p:p['group_outcomes'][0]['cases'].append(deepcopy(p['group_outcomes'][0]['cases'][0])),
            lambda p:p['group_outcomes'][0].update(split='unregistered'),
            lambda p:p['group_outcomes'][0]['cases'][0].update(method_id='unregistered')]
        for mutate in mutations:
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)

    def test_missing_groups_or_utility_remain_incomplete_not_available_case_success(self):
        value=private_report(utility=True);value['group_outcomes'].pop()
        value['utility']['adaptive_temporal_first']['IN']['observed_recordings']=31
        for item in value['utility']['adaptive_temporal_first']['IN']['macro_means'].values():item['recordings']=31
        result=reporting.compact_report(value)
        self.assertEqual(result['utility_status'],'incomplete')
        self.assertEqual(result['source_and_execution']['recording_status_by_split']['test']['not_reported'],1)
        self.assertEqual(result['methods'][-4]['utility']['IN']['observed_recordings'],31)

    def test_per_metric_denominators_are_kept_and_not_assumed_all32(self):
        value=private_report()
        world=value['analysis']['utility']['adaptive_semantic_wait_temporal']['IN']
        world['macro_means']['query_exact.occupancy_mae']={'mean':0.,'recordings':14}
        result=reporting.compact_report(value)
        found=next(m for m in result['methods'] if m['id']=='adaptive_semantic_wait_temporal')
        self.assertEqual(found['utility']['IN']['macro_means']['query_exact.occupancy_mae'],{'mean':0.,'recordings':14})
        world['macro_means']['query_exact.occupancy_mae']['recordings']=33
        with self.assertRaises(ValueError):reporting.compact_report(value)

    def test_undefined_means_and_zero_have_distinct_denominators(self):
        value=private_report();w=value['analysis']['utility']['adaptive_spatial_first']['IN']
        w['macro_means']['retained_semantic_loss']={'mean':0.,'recordings':32}
        w['macro_means']['query_exact.occupancy_mae']={'mean':None,'recordings':0}
        result=reporting.compact_report(value)
        item=next(m for m in result['methods'] if m['id']=='adaptive_spatial_first')['utility']['IN']
        self.assertEqual(reporting.strict._fmt(reporting.strict._mean(item,'retained_semantic_loss')),'0.000')
        self.assertEqual(reporting.strict._fmt(reporting.strict._mean(item,'query_exact.occupancy_mae')),'NA')
        w['macro_means']['query_exact.occupancy_mae']['recordings']=2
        with self.assertRaises(ValueError):reporting.compact_report(value)

    def test_bad_utility_or_runtime_numbers_rejected(self):
        mutations=[lambda p:p['analysis']['utility']['adaptive_temporal_first']['IN']['macro_means']['retained_fraction'].update(mean=float('nan')),
            lambda p:p['analysis']['utility']['adaptive_temporal_first']['IN'].update(expected_recordings=31),
            lambda p:p['native_execution_summary']['by_method']['adaptive_temporal_first'].update(wall_seconds_mean=-1),
            lambda p:p['native_execution_summary']['by_method'].update(unregistered={})]
        for mutate in mutations:
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)

    def test_new_contrast_seeds_pairs_and_families_are_frozen(self):
        mutations=[lambda p:p['exploratory_contrasts']['temporal_vs_spatial'].update(right='regional_static20'),
            lambda p:p['exploratory_contrasts']['temporal_vs_spatial']['representations']['semantic111'].update(seed=123),
            lambda p:p['exploratory_contrasts']['temporal_vs_spatial']['representations']['semantic111'].update(replicates=2000),
            lambda p:p['exploratory_contrasts']['temporal_vs_spatial']['representations']['semantic111'].update(independent_groups=33),
            lambda p:p['exploratory_contrasts']['temporal_vs_spatial']['representations']['semantic111'].update(interval=[.1,-.1]),
            lambda p:p['exploratory_contrasts'].update(chosen_after_TEST={})]
        for mutate in mutations:
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)

    def test_original_primary_is_separate_and_cannot_be_replaced(self):
        value=private_report();result=reporting.compact_report(value)
        self.assertEqual(result['original_primary_contrast']['left'],'adaptive_semantic_first')
        self.assertEqual(len(result['exploratory_contrasts']),8)
        self.assertTrue(result['exploratory_contrasts']['temporal_vs_spatial']['representations']['semantic111']['interval'][0]<0)
        text=reporting.markdown(result)
        self.assertIn('neither superiority nor equivalence',text)
        self.assertIn('not fresh confirmatory evidence',text)
        self.assertIn('not a replacement for the original primary comparison',text)
        value['analysis']['primary_contrast']['left']='adaptive_temporal_first'
        with self.assertRaises(ValueError):reporting.compact_report(value)

    def test_nonconverged_or_missing_new_models_never_show_complete(self):
        value=private_report();a=value['analysis']['attacks']['adaptive_temporal_first']['semantic111']
        a.update(status='nonconverged',metrics=None);a['fit_diagnostics']['converged']=False
        result=reporting.compact_report(value)
        self.assertEqual(result['analysis_status'],'incomplete_or_diagnostic')
        row=next(m for m in result['methods'] if m['id']=='adaptive_temporal_first')['attacks']['semantic111']
        self.assertEqual(row['status'],'nonconverged');self.assertIsNone(row['metrics'])
        self.assertIn('nonconverged',reporting.markdown(result))

    def test_failed_controls_keep_diagnostic_gate(self):
        value=private_report();value['analysis']['interpretation_gate']='diagnose_controls_before_interpreting_lower_attack_success'
        value['analysis']['negative_control_checks']['auxiliary_only']['status']='fail'
        result=reporting.compact_report(value)
        self.assertEqual(result['analysis_status'],'incomplete_or_diagnostic')
        self.assertEqual(result['negative_control_checks']['auxiliary_only'],'fail')
        self.assertIn('diagnose_controls_before_interpreting_lower_attack_success',reporting.markdown(result))

    def test_finite_reject_all_threshold_above_one_is_not_clipped(self):
        value=private_report();a=value['analysis']['attacks']['adaptive_temporal_first']['semantic111']
        a['metrics']['threshold']=1.0000000000000002;a['locked_calibration']['threshold']=1.0000000000000002
        result=reporting.compact_report(value)
        row=next(m for m in result['methods'] if m['id']=='adaptive_temporal_first')['attacks']['semantic111']
        self.assertGreater(row['metrics']['threshold'],1)
        self.assertEqual(row['metrics']['threshold'],row['calibration']['threshold'])

    def test_runtime_is_aggregate_only_and_distinct_from_core_and_logical_delay(self):
        result=reporting.compact_report(private_report())
        row=result['native_runtime']['by_method_test']['adaptive_temporal_first']
        self.assertEqual(row['runs'],64);self.assertEqual(row['wall_seconds_mean'],34.)
        self.assertNotIn('raw_native_rows',row)
        self.assertIn('different boundaries',reporting.markdown(result))
        self.assertIn('not a per-step',result['native_runtime']['scope'])

    def test_wrong_schema_profile_and_nonfinite_input_rejected(self):
        for mutate in (lambda p:p.update(schema='old'),lambda p:p.update(source_validation_profile='complete_episode'),
                       lambda p:(p.pop('supplement_id'),p.pop('evaluation_id'))):
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)

    def test_export_binds_numeric_assets_lineage_context_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'private.json';path.write_text(json.dumps(private_report(utility=True)))
            output=root/'public';result=reporting.export(path,output,make_figures=False)
            receipt=json.loads((output/'artifact-receipt.json').read_text())
            self.assertEqual(receipt['phase'],'utility');self.assertEqual(receipt['source_report_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(set(receipt['artifacts_sha256']),{'summary.json','report.md','repair-lineage-public.json'})
            for name,digest in receipt['artifacts_sha256'].items():self.assertEqual(digest,hashlib.sha256((output/name).read_bytes()).hexdigest())
            self.assertEqual(json.loads((output/'repair-lineage-public.json').read_text()),result['supplementary_lineage'])
            self.assertNotIn(SECRET,(output/'summary.json').read_text())
            with self.assertRaises(FileExistsError):reporting.export(path,output,make_figures=False)

    def test_figure_phase_and_files_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'input.json';p.write_text(json.dumps(private_report(utility=True)))
            reporting.export(p,root/'utility')
            self.assertEqual(len(list((root/'utility').glob('*.png'))),2)
            self.assertFalse((root/'utility/urban-strategy-supplement-attack.png').exists())
            p.write_text(json.dumps(private_report()))
            reporting.export(p,root/'final')
            self.assertEqual(len(list((root/'final').glob('*.png'))),4)
            self.assertTrue((root/'final/urban-strategy-supplement-contrasts.svg').is_file())
            receipt=json.loads((root/'final/artifact-receipt.json').read_text())
            self.assertEqual(len(receipt['artifacts_sha256']),11)

    def test_labelled_execution_settings_cannot_be_swapped(self):
        value=private_report()
        next(e for e in value['method_catalog'] if e['id']=='adaptive_semantic_wait_spatial')['release_trigger']='policy_satisfied'
        with self.assertRaises(ValueError):reporting.compact_report(value)

    def test_verified_group_label_cannot_hide_missing_native_case(self):
        value=private_report(utility=True)
        value['group_outcomes'][0]['cases'].pop()
        result=reporting.compact_report(value)
        self.assertEqual(result['utility_status'],'incomplete')

    def test_original_refit_or_missing_preservation_declaration_rejected(self):
        for mutate in (lambda p:p['strategy_supplement']['public_lineage'].update(original_model_refits=1),
                       lambda p:p['strategy_supplement']['public_lineage'].update(original_threshold_retunes=1),
                       lambda p:p.pop('original_primary_result_preserved')):
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)

    def test_fraction_over_one_and_inconsistent_control_gate_do_not_pass(self):
        value=private_report()
        value['analysis']['utility']['adaptive_spatial_first']['IN']['macro_means']['retained_fraction']['mean']=1.1
        with self.assertRaises(ValueError):reporting.compact_report(value)
        value=private_report();value['analysis']['negative_control_checks']['auxiliary_only']['status']='fail'
        self.assertEqual(reporting.compact_report(value)['analysis_status'],'incomplete_or_diagnostic')

    def test_partial_recording_matrix_cannot_be_complete_mia(self):
        for mutate in (lambda p:p['group_outcomes'].pop(),
                       lambda p:p['group_outcomes'][0]['cases'].pop(),
                       lambda p:p['group_outcomes'][0].update(status='failed'),
                       lambda p:p['source_split_audit'].update(status='unavailable')):
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate):
                result=reporting.compact_report(value)
                self.assertEqual(result['mia_status'],'incomplete_or_diagnostic')
                self.assertEqual(result['analysis_status'],'incomplete_or_diagnostic')
                self.assertEqual(result['utility_status'],'incomplete')

    def test_partial_attack_or_control_pairs_cannot_be_complete_mia(self):
        mutations=[lambda a:a.update(complete_test_groups=31),lambda a:a.update(observed_test_rows=62),
                   lambda a:a.update(expected_independent_test_groups=31)]
        for family in ('attacks','controls'):
            for mutate in mutations:
                value=private_report()
                item=(value['analysis']['attacks']['adaptive_temporal_first']['semantic111']
                      if family=='attacks' else value['analysis']['controls']['auxiliary_only'])
                mutate(item)
                with self.subTest(family=family,mutate=mutate):
                    self.assertEqual(reporting.compact_report(value)['mia_status'],'incomplete_or_diagnostic')
        value=private_report();metrics=value['analysis']['attacks']['adaptive_temporal_first']['semantic111']['metrics']
        metrics.update(positive_cases=31,false_negative=7,tpr=24/31)
        self.assertEqual(reporting.compact_report(value)['mia_status'],'incomplete_or_diagnostic')

    def test_missing_partial_or_unavailable_contrasts_cannot_be_complete_mia(self):
        mutations=[lambda p:p['exploratory_contrasts'].pop('temporal_vs_spatial'),
                   lambda p:p['exploratory_contrasts']['temporal_vs_spatial']['representations']['semantic111'].update(independent_groups=31),
                   lambda p:p['exploratory_contrasts']['temporal_vs_spatial']['representations'].__setitem__('scalar31',{'status':'unavailable'}),
                   lambda p:p['analysis']['primary_contrast']['representations']['semantic111'].update(independent_groups=31)]
        for mutate in mutations:
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate):
                self.assertEqual(reporting.compact_report(value)['analysis_status'],'incomplete_or_diagnostic')

    def test_native_runtime_rejects_regional_or_wrong_scope_counts(self):
        mutations=[lambda p:p['native_execution_summary']['by_method'].update(regional_static20={'runs':144}),
                   lambda p:p['native_execution_summary']['by_method']['adaptive_temporal_first'].update(runs=64),
                   lambda p:p['native_execution_summary']['by_method_test']['adaptive_temporal_first'].update(runs=144)]
        for mutate in mutations:
            value=private_report();mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(value)
        value=private_report();value['native_execution_summary']={}
        self.assertEqual(reporting.compact_report(value)['native_runtime']['by_method'],{})

    def test_cli_prints_no_private_source_or_output_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'private.json';path.write_text(json.dumps(private_report(utility=True)))
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):reporting.main(['--report',str(path),'--output',str(root/'output'),'--no-figures'])
            value=json.loads(stream.getvalue());self.assertEqual(value['mia_status'],'not_started')
            self.assertNotIn(str(root),stream.getvalue());self.assertNotIn(SECRET,stream.getvalue())


if __name__=='__main__':unittest.main()
