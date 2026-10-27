"""Synthetic projection, completeness and interpretation-boundary fixtures."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import report_urban_semantic_ablation as reporting
from test_report_urban_strategy_supplement import private_report as old_report

SECRET='PRIVATE_SOURCE_TARGET'


def private_report(utility=False):
    old=old_report(utility=utility)
    old_analysis={} if utility else old['analysis']
    old_utility=old['utility'] if utility else old_analysis['utility']
    catalog=[];utilities={};attacks={}
    for base,label in reporting.BASE_METHODS:
        kind='regional_static' if base=='regional_static20' else 'native_fixed' if base=='fixed20_400ms' else 'native_adaptive'
        for suffix in ('','_exact_only'):
            identity=base+suffix
            item=dict(id=identity,on_method_id=base,kind=kind,semantic_generalization='exact_only' if suffix else 'enabled',label=label)
            if base=='fixed20_400ms':item.update(fixed_depth=2,window_ms=400,grid_side_m=20)
            if base=='regional_static20':item.update(grid_side_m=20)
            if base in reporting.previous.EXECUTION_CATALOG:
                item.update(zip(('strategy','secondary_strategy','release_trigger'),reporting.previous.EXECUTION_CATALOG[base]))
            catalog.append(item)
            utilities[identity]=deepcopy(old_utility[base])
            if not utility:
                attacks[identity]=deepcopy(old_analysis['attacks'][base])
                attacks[identity]['scalar31']['fit_diagnostics']['feature_count']=31
            for world in ('IN','OUT'):
                means=utilities[identity][world]['macro_means']
                means['published_policy_violations']=dict(mean=0.,recordings=32)
                if suffix:
                    means['retained_semantic_loss']=dict(mean=0.,recordings=32)
                    means['full_input_J']=dict(mean=1-means['retained_fraction']['mean'],recordings=32)
                for mode in ('exact','estimate'):
                    for stem in (f'aligned_semantic_queries.{mode}.summary',*(f'aligned_semantic_queries.{mode}.by_category.{category}' for category in reporting.CATEGORIES)):
                        for field in reporting.queries.SUMMARY_FIELDS:
                            value=.25 if field.endswith('coverage') else 2. if field=='answered_only_mae' else 12.
                            means[stem+'.'+field]=dict(mean=value,recordings=32)
                    means[f'aligned_semantic_queries.{mode}.summary.query_count']=dict(mean=144000.,recordings=32)
                for family,cohorts in (('by_source_type',reporting.SOURCE_CLASSES),('by_source_point_region',reporting.REGIONS)):
                    for cohort in cohorts:
                        for field in reporting.COHORT_FIELDS:
                            means['source_accounting.'+family+'.'+cohort+'.'+field]=dict(mean=.4 if field=='retained_fraction' else 100. if field=='input_observation_contributions' else 40. if field=='retained_observation_contributions' else 60.,recordings=32)
    groups=[]
    for group in old['group_outcomes']:
        groups.append(dict(group_id=group['group_id'],split=group['split'],status='verified',
            cases=[dict(method_id=m,world=w,status='verified') for m in reporting.OFF_IDS+reporting.AUXILIARY_IDS for w in ('IN','OUT')],
            imported_on_cases=[dict(method_id=m,world=w,status='verified',role='authenticated_historical_on') for m in reporting.ON_IDS for w in ('IN','OUT')]))
    lineage={field:'a'*64 for field in reporting.HASH_FIELDS}
    lineage.update(hard_policy_unchanged=True,imported_groups=72,imported_headline_rows=1008,new_headline_rows=1008,auxiliary_rows=432,
        new_native_executions=1296,regional_compositions=144,ONmodel_refits=0,new_attack_variants=0 if utility else 14,
        imported_attack_variants=14,source_resimulations=0,source_replacements=0,diagnostic_repair=deepcopy(old['strategy_supplement']['public_lineage']['diagnostic_repair']))
    result=dict(schema=reporting.UTILITY_INPUT_SCHEMA if utility else reporting.INPUT_SCHEMA,ablation_id=SECRET,
        source_validation_profile=reporting.PROFILE,method_catalog=catalog,
        auxiliary_method_catalog=[dict(id=m,kind='native_fixed',fixed_depth=2,grid_side_m=20,window_ms=int(m.split('_')[1].removesuffix('ms')),semantic_generalization='exact_only') for m in reporting.AUXILIARY_IDS],group_outcomes=groups,
        source_split_audit=deepcopy(old['source_split_audit']),source_quality=deepcopy(old['source_quality']),
        semantic_ablation=dict(public_lineage=lineage),
        aligned_query_definition=dict(schema=reporting.queries.SCHEMA,cell_side_m=20,window_ms=400,count_unit='observation_contributions',
            all_road_user_category='road_user',categories=list(reporting.CATEGORIES),taxonomy_sha256='b'*64,source_horizon_ms=300000,
            full_window_count=750,spatial_cell_count=16,query_count=144000,initial_sample_excluded=True,sampling_period_ms=100),
        duplicate_check=dict(status='verified',scope='recipient_payload_ignoring_release_ids',expected_streams_per_pair=144,
            by_pair={left+'__vs__'+right:dict(left=left,right=right,compared_streams=144,equal_streams=143,all_equal=False) for left,right in reporting.DUPLICATE_PAIRS}),
        native_execution_summary=dict(by_method={},by_method_test={}),dataset_manifest_sha256='c'*64,
        raw_motion={'target_id':SECRET,'seed':123,'weights':[1,2]},private_path='/private/'+SECRET)
    if utility:result.update(utility=utilities,mia_status='not_started')
    else:
        analysis=deepcopy(old_analysis);analysis.update(attacks=attacks,utility=utilities)
        for name,value in analysis['controls'].items():
            if name in ('prior_only','unprotected'):value['fit_diagnostics']=None
            if name=='auxiliary_only':value['fit_diagnostics']['feature_count']=8
        result.update(analysis=analysis,original_primary_result_preserved=True,
            exploratory_contrasts={key:dict(left=left,right=right,metric='ROC_AUC',representations={rep:dict(
                auc_difference=-.02,interval=[-.08,.03],confidence_level=.95,seed=seed,replicates=1000,independent_groups=32)
                for rep in reporting.REPRESENTATIONS}) for key,left,right,seed in reporting.CONTRASTS})
    return result


class SemanticAblationReportingTests(unittest.TestCase):
    def test_complete_final_has_fourteen_methods_and_three_nonheadline_dependencies(self):
        result=reporting.compact_report(private_report())
        self.assertEqual(result['utility_status'],'complete');self.assertEqual(result['mia_status'],'complete')
        self.assertEqual(len(result['methods']),14);self.assertEqual(len(result['auxiliary_methods']),3)
        self.assertEqual(len(result['exploratory_contrasts']),7)
        self.assertEqual(result['source_and_execution']['planned_headline_rows'],2016)
        self.assertEqual(result['source_and_execution']['auxiliary_rows'],432)
        self.assertTrue(all(row['statuses']=={'verified':144} for row in result['source_and_execution']['method_world_status'].values()))

    def test_utility_stage_hides_new_and_historical_mia(self):
        result=reporting.compact_report(private_report(utility=True));text=reporting.markdown(result)
        self.assertEqual(result['mia_status'],'not_started');self.assertEqual(result['utility_status'],'complete')
        self.assertTrue(all(m['attacks'][rep]['metrics'] is None for m in result['methods'] for rep in reporting.REPRESENTATIONS))
        self.assertIn('MIA has not started',text);self.assertNotIn('| Full111 AUC |',text)
        self.assertIn('OFF zero retained semantic loss does not mean zero full-input loss',text)

    def test_private_fields_are_removed_without_mutating_input(self):
        raw=private_report();before=deepcopy(raw);raw['analysis']['utility'][reporting.ON_IDS[0]]['IN']['macro_means']['target_id.'+SECRET]=dict(mean=1.,recordings=32)
        expected=deepcopy(raw);result=reporting.compact_report(raw,input_sha256='d'*64)
        self.assertEqual(raw,expected);encoded=json.dumps(result,allow_nan=False)
        for value in (SECRET,'/private/','"group_id"','"seed"','"weights"','"group_scores"','"feature_vectors"','"raw_motion"'):
            self.assertNotIn(value,encoded)
        self.assertNotEqual(raw,before)
        self.assertEqual(result['provenance']['ablation_id_sha256'],hashlib.sha256(SECRET.encode()).hexdigest())

    def test_missing_group_or_case_or_source_audit_cannot_claim_complete(self):
        for mutate in (lambda p:p['group_outcomes'].pop(),lambda p:p['group_outcomes'][0]['cases'].pop(),
                       lambda p:p['group_outcomes'][0]['imported_on_cases'].pop(),
                       lambda p:p['source_split_audit'].update(status='invalid')):
            raw=private_report();mutate(raw);result=reporting.compact_report(raw)
            self.assertEqual(result['utility_status'],'incomplete');self.assertEqual(result['mia_status'],'incomplete_or_diagnostic')

    def test_historical_cases_must_not_pretend_to_be_new_native_artifacts(self):
        raw=private_report();raw['group_outcomes'][0]['cases'].append(raw['group_outcomes'][0]['imported_on_cases'].pop())
        with self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_unknown_duplicate_catalog_or_world_rejected(self):
        for mutate in (lambda p:p['method_catalog'].pop(),lambda p:p['method_catalog'].__setitem__(0,deepcopy(p['method_catalog'][1])),
            lambda p:p['method_catalog'][0].update(id='newwinner'),lambda p:p['group_outcomes'][0]['cases'][0].update(world='best'),
            lambda p:p['auxiliary_method_catalog'].pop()):
            raw=private_report();mutate(raw)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_catalog_capability_and_preference_are_validated(self):
        for mutate in (lambda p:p['method_catalog'][0].update(semantic_generalization='exact_only'),
            lambda p:p['method_catalog'][0].update(on_method_id='different'),
            lambda p:next(row for row in p['method_catalog'] if row['id']=='adaptive_temporal_first').update(strategy='spatial_first')):
            raw=private_report();mutate(raw)
            with self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_auxiliary_methods_are_not_in_attack_or_headline_utility_families(self):
        for family in ('utility','attacks'):
            raw=private_report();raw['analysis'][family][reporting.AUXILIARY_IDS[0]]={}
            with self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_lineage_policy_counts_and_original_diagnostic_history_required(self):
        for mutate in (lambda p:p['semantic_ablation']['public_lineage'].update(hard_policy_unchanged=False),
            lambda p:p['semantic_ablation']['public_lineage'].update(auxiliary_rows=0),
            lambda p:p['semantic_ablation']['public_lineage'].update(ONmodel_refits=1),
            lambda p:p['semantic_ablation']['public_lineage'].pop('historical_snapshot_sha256'),
            lambda p:p['semantic_ablation']['public_lineage']['diagnostic_repair'].update(original_test_source_status_counts={'verified':32})):
            raw=private_report();mutate(raw)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_aligned_query_denominator_and_category_workload_frozen(self):
        for changes in ({'cell_side_m':10},{'window_ms':1000},{'query_count':1},{'count_unit':'people'},
            {'categories':['private_category']},{'initial_sample_excluded':False},{'sampling_period_ms':50}):
            raw=private_report();raw['aligned_query_definition'].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_per_metric_available_N_is_preserved(self):
        raw=private_report();world=raw['analysis']['utility'][reporting.OFF_IDS[0]]['IN']
        key='aligned_semantic_queries.exact.by_category.adult_pedestrian.answered_only_mae'
        world['macro_means'][key]=dict(mean=0.,recordings=3)
        result=reporting.compact_report(raw);item=next(m for m in result['methods'] if m['id']==reporting.OFF_IDS[0])
        self.assertEqual(item['utility']['IN']['macro_means'][key],dict(mean=0.,recordings=3))

    def test_undefined_error_and_zero_semantic_loss_remain_distinct(self):
        raw=private_report();means=raw['analysis']['utility'][reporting.OFF_IDS[0]]['IN']['macro_means']
        means['retained_semantic_loss']=dict(mean=0.,recordings=32)
        means['aligned_semantic_queries.exact.summary.answered_only_mae']=dict(mean=None,recordings=0)
        result=reporting.compact_report(raw);item=next(m for m in result['methods'] if m['id']==reporting.OFF_IDS[0])
        self.assertEqual(reporting._metric(item,'IN','retained_semantic_loss'),'0.000 (n=32)')
        self.assertEqual(reporting._metric(item,'IN','aligned_semantic_queries.exact.summary.answered_only_mae'),'NA (n=0)')

    def test_bad_metric_values_or_denominators_rejected(self):
        for entry in (dict(mean=float('nan'),recordings=32),dict(mean=-1.,recordings=32),dict(mean=.1,recordings=33),dict(mean=None,recordings=1),dict(mean=2.,recordings=32)):
            raw=private_report();key='aligned_semantic_queries.exact.summary.query_coverage'
            raw['analysis']['utility'][reporting.ON_IDS[0]]['IN']['macro_means'][key]=entry
            with self.subTest(entry=entry),self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_missing_aligned_queries_cannot_inherit_historical_complete_utility(self):
        raw=private_report();raw['analysis']['utility'][reporting.ON_IDS[0]]['IN']['macro_means'].pop('aligned_semantic_queries.exact.summary.query_count')
        result=reporting.compact_report(raw)
        self.assertEqual(result['utility_status'],'incomplete');self.assertEqual(result['mia_status'],'incomplete_or_diagnostic')

    def test_policy_violation_downgrades_interpretation(self):
        raw=private_report();raw['analysis']['utility'][reporting.ON_IDS[0]]['IN']['macro_means']['published_policy_violations']['mean']=1
        self.assertEqual(reporting.compact_report(raw)['mia_status'],'incomplete_or_diagnostic')

    def test_mia_partial_group_model_control_or_contrast_is_not_complete(self):
        mutations=(lambda p:p['analysis']['attacks'][reporting.OFF_IDS[0]]['semantic111'].update(complete_test_groups=31),
            lambda p:p['analysis']['controls']['no_output'].update(observed_test_rows=63),
            lambda p:p['analysis']['attacks'][reporting.OFF_IDS[0]]['semantic111'].update(status='nonconverged',metrics=None),
            lambda p:p['exploratory_contrasts'][reporting.CONTRASTS[0][0]]['representations']['scalar31'].update(independent_groups=31),
            lambda p:p['analysis']['negative_control_checks']['no_output'].update(status='fail'))
        for mutate in mutations:
            raw=private_report();mutate(raw)
            self.assertEqual(reporting.compact_report(raw)['mia_status'],'incomplete_or_diagnostic')

    def test_missing_or_invalid_CAL_and_fit_cannot_claim_complete(self):
        for mutate in (lambda a:a.update(locked_calibration=None),lambda a:a.update(fit_diagnostics=None),
            lambda a:a['fit_diagnostics'].update(converged=False),lambda a:a['fit_diagnostics'].update(training_rows=64),
            lambda a:a['fit_diagnostics'].update(feature_count=31),lambda a:a['fit_diagnostics'].update(iterations=501),
            lambda a:a['locked_calibration'].update(negative_case_fpr_resolution=.1),
            lambda a:a['locked_calibration'].update(threshold=.9)):
            raw=private_report();mutate(raw['analysis']['attacks'][reporting.OFF_IDS[0]]['semantic111'])
            self.assertEqual(reporting.compact_report(raw)['mia_status'],'incomplete_or_diagnostic')
        raw=private_report();raw['analysis']['controls']['auxiliary_only']['fit_diagnostics']=None
        self.assertEqual(reporting.compact_report(raw)['mia_status'],'incomplete_or_diagnostic')
        raw=private_report();raw['analysis']['controls']['prior_only']['locked_calibration']=None
        self.assertEqual(reporting.compact_report(raw)['mia_status'],'incomplete_or_diagnostic')

    def test_converged_constant_feature_model_is_valid_at_first_iteration(self):
        raw=private_report()
        for method in reporting.OFF_IDS:
            for rep in reporting.REPRESENTATIONS:
                raw['analysis']['attacks'][method][rep]['fit_diagnostics'].update(iterations=1,converged=True)
        self.assertEqual(reporting.compact_report(raw)['mia_status'],'complete')

    def test_fixed_and_dependency_schedule_metadata_is_validated(self):
        for mutate in (lambda p:p['method_catalog'][0].update(fixed_depth=3),
            lambda p:p['method_catalog'][0].update(window_ms=1000),
            lambda p:p['auxiliary_method_catalog'][0].update(semantic_generalization='enabled'),
            lambda p:p['auxiliary_method_catalog'][0].update(window_ms=400)):
            raw=private_report();mutate(raw)
            with self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_paired_contrasts_have_prespecified_direction_seed_budget(self):
        key,left,right,seed=reporting.CONTRASTS[0]
        for mutate in (lambda p:p['exploratory_contrasts'][key].update(left=right,right=left),
            lambda p:p['exploratory_contrasts'][key]['representations']['semantic111'].update(seed=seed+1),
            lambda p:p['exploratory_contrasts'][key]['representations']['semantic111'].update(replicates=10),
            lambda p:p['exploratory_contrasts'][key]['representations']['semantic111'].update(interval=[.2,-.1])):
            raw=private_report();mutate(raw)
            with self.assertRaises(ValueError):reporting.compact_report(raw)
        result=reporting.compact_report(private_report());self.assertEqual(result['exploratory_contrasts'][key]['direction'],'OFF minus ON')
        self.assertIn('neither superiority nor equivalence',reporting.markdown(result))

    def test_utility_phase_rejects_started_attacks_or_contrasts(self):
        for mutate in (lambda p:p.update(mia_status='started'),lambda p:p.update(analysis={'status':'complete'}),
            lambda p:p.update(exploratory_contrasts={reporting.CONTRASTS[0][0]:{}})):
            raw=private_report(utility=True);mutate(raw)
            with self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_duplicate_counts_are_reported_not_assumed(self):
        raw=private_report();key=next(iter(raw['duplicate_check']['by_pair']))
        raw['duplicate_check']['by_pair'][key].update(equal_streams=144,all_equal=True)
        result=reporting.compact_report(raw)
        self.assertEqual(sum(row['all_equal'] is True for row in result['duplicate_check']['by_pair'].values()),1)
        self.assertIn('not a universal algorithm-equivalence claim',reporting.markdown(result))
        raw['duplicate_check']['by_pair'][key]['all_equal']=False
        with self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_missing_duplicate_measurement_downgrades_complete(self):
        raw=private_report();raw['duplicate_check']['by_pair'].pop(next(iter(raw['duplicate_check']['by_pair'])))
        result=reporting.compact_report(raw);self.assertEqual(result['duplicate_check']['status'],'incomplete')
        self.assertEqual(result['mia_status'],'incomplete_or_diagnostic')

    def test_runtime_rejects_regional_or_wrong_scope_counts(self):
        for name,n in (('regional_static20',64),(reporting.OFF_IDS[0],144)):
            raw=private_report();raw['native_execution_summary']['by_method_test'][name]=dict(runs=n)
            with self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_impossible_exact_only_loss_J_and_empty_loss_are_rejected(self):
        for updates in ({'retained_semantic_loss':dict(mean=.25,recordings=32)},
                        {'full_input_J':dict(mean=.9,recordings=32)},
                        {'retained_fraction':dict(mean=0.,recordings=32),'full_input_J':dict(mean=1.,recordings=32),'retained_semantic_loss':dict(mean=0.,recordings=32)}):
            raw=private_report();raw['analysis']['utility'][reporting.OFF_IDS[0]]['IN']['macro_means'].update(updates)
            with self.subTest(updates=updates),self.assertRaises(ValueError):reporting.compact_report(raw)
        raw=private_report();raw['analysis']['utility'][reporting.OFF_IDS[0]]['IN']['macro_means'].update(
            retained_fraction=dict(mean=0.,recordings=32),full_input_J=dict(mean=1.,recordings=32),retained_semantic_loss=dict(mean=None,recordings=0))
        result=reporting.compact_report(raw)
        self.assertEqual(next(m for m in result['methods'] if m['id']==reporting.OFF_IDS[0])['utility']['IN']['macro_means']['retained_semantic_loss'],dict(mean=None,recordings=0))

    def test_native_source_accounting_aliases_are_projected_without_inventing_outside(self):
        raw=private_report();means=raw['analysis']['utility'][reporting.ON_IDS[0]]['IN']['macro_means']
        for key in list(means):
            if key.startswith('source_accounting.'):del means[key]
        for stem in ('source_accounting.by_source_type.Adult Pedestrian.','source_accounting.by_region.entrance-vicinity.'):
            means[stem+'input_observations']=dict(mean=100.,recordings=32)
            means[stem+'retained_observations']=dict(mean=40.,recordings=32)
            means[stem+'retained_fraction']=dict(mean=.4,recordings=32)
        result=reporting.compact_report(raw);projected=result['methods'][0]['utility']['IN']['macro_means']
        self.assertEqual(projected['source_accounting.by_source_type.Adult Pedestrian.unpublished_observation_contributions'],dict(mean=60.,recordings=32))
        self.assertEqual(projected['source_accounting.by_source_point_region.entrance-vicinity.retained_fraction']['mean'],.4)
        self.assertFalse(any(key.startswith('source_accounting.by_source_point_region.outside_policy_regions') for key in projected))
        means['source_accounting.by_source_type.Adult Pedestrian.input_observation_contributions']=dict(mean=99.,recordings=32)
        with self.assertRaises(ValueError):reporting.compact_report(raw)
        means.pop('source_accounting.by_source_type.Adult Pedestrian.input_observation_contributions')
        means['source_accounting.selectively_suppressed_observations']=dict(mean=1.,recordings=32)
        with self.assertRaises(ValueError):reporting.compact_report(raw)

    def test_export_is_aggregate_only_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);report=root/'private.json';report.write_text(json.dumps(private_report(utility=True)))
            result=reporting.export(report,root/'export',make_figures=False)
            self.assertEqual(result['mia_status'],'not_started');self.assertTrue((root/'export/artifact-receipt.json').is_file())
            self.assertNotIn(SECRET,(root/'export/summary.json').read_text())
            with self.assertRaises(ValueError):reporting.export(report,root/'export',make_figures=False)


if __name__=='__main__':unittest.main()
