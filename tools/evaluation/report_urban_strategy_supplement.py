#!/usr/bin/env python3
"""Aggregate-only supplementary strategy reports, with MIA explicitly last.

Read an authenticated runner report; never load its references, fit attacks,
select targets, or modify numerical estimates. Original primary artifacts remain
separate. Unknown private fields are dropped through fixed projections.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import report_urban_privacy_primary as strict
import report_urban_track_window_primary as window

INPUT_SCHEMA = 'ump.urban-strategy-supplement-report.v1'
UTILITY_INPUT_SCHEMA = 'ump.urban-strategy-supplement-utility.v1'
SCHEMA = 'ump.urban-strategy-supplement-public-report.v1'
ARTIFACT_SCHEMA = 'ump.urban-strategy-supplement-public-artifacts.v1'
PROFILE, HORIZON_MS = window.PROFILE, window.HORIZON_MS
GROUP_COUNTS, REPRESENTATIONS, CONTROLS = strict.GROUP_COUNTS, strict.REPRESENTATIONS, strict.CONTROLS
NEW_METHODS = (
    ('adaptive_temporal_first', 'Temporal First'),
    ('adaptive_spatial_first', 'Spatial First'),
    ('adaptive_semantic_wait_temporal', 'Semantic First → Temporal First / wait'),
    ('adaptive_semantic_wait_spatial', 'Semantic First → Spatial First / wait'),
)
METHODS = strict.METHODS[:-1] + (('adaptive_semantic_first', 'Semantic First / immediate policy release'),) + NEW_METHODS
METHOD_IDS = tuple(name for name, _ in METHODS)
NEW_IDS = tuple(name for name, _ in NEW_METHODS)
EXECUTION_CATALOG = {
    'adaptive_semantic_first': ('semantic_first', 'temporal_first', 'policy_satisfied'),
    'adaptive_temporal_first': ('temporal_first', None, 'policy_satisfied'),
    'adaptive_spatial_first': ('spatial_first', None, 'policy_satisfied'),
    'adaptive_semantic_wait_temporal': ('semantic_first', 'temporal_first', 'priority_satisfied'),
    'adaptive_semantic_wait_spatial': ('semantic_first', 'spatial_first', 'priority_satisfied'),
}
CONTRASTS = (
    ('temporal_vs_regional20', 'adaptive_temporal_first', 'regional_static20', 20261026311),
    ('spatial_vs_regional20', 'adaptive_spatial_first', 'regional_static20', 20261026312),
    ('semantic_wait_temporal_vs_regional20', 'adaptive_semantic_wait_temporal', 'regional_static20', 20261026313),
    ('semantic_wait_spatial_vs_regional20', 'adaptive_semantic_wait_spatial', 'regional_static20', 20261026314),
    ('temporal_vs_spatial', 'adaptive_temporal_first', 'adaptive_spatial_first', 20261026315),
    ('semantic_wait_temporal_vs_immediate', 'adaptive_semantic_wait_temporal', 'adaptive_semantic_first', 20261026316),
    ('semantic_wait_spatial_vs_immediate', 'adaptive_semantic_wait_spatial', 'adaptive_semantic_first', 20261026317),
    ('semantic_wait_temporal_vs_semantic_wait_spatial', 'adaptive_semantic_wait_temporal', 'adaptive_semantic_wait_spatial', 20261026318),
)
HASH_FIELDS = (
    'original_report_sha256', 'original_models_sha256', 'original_model_lock_sha256',
    'original_rows_sha256', 'original_train_cal_rows_sha256', 'repair_protocol_sha256',
    'validation_ledger_sha256', 'supplement_protocol_sha256', 'hard_policy_sha256',
    'original_config_sha256',
)
REPAIR_HASH_FIELDS = (
    'corrected_auditor_sha256', 'original_auditor_sha256', 'original_execution_protocol_sha256',
    'original_model_lock_sha256', 'original_models_sha256', 'original_rows_sha256',
    'original_source_protocol_sha256', 'repair_id_sha256', 'repair_protocol_sha256',
    'source_binary_sha256', 'validation_ledger_sha256',
)
REPAIR_COUNTS = dict(corrected_verified_sources=72, full_raw_validations=72,
    imported_mechanism_groups=40, imported_rows=880, locked_variants=22,
    model_refits=0, new_physical_audit_jobs=32, reused_legacy_physical_proofs=40,
    same_role_sources=72, source_replacements=0, source_resimulations=0, threshold_retunes=0)
SCOPE = (
    'Supplementary exploratory comparison selected after the original main TEST results; the reused TEST recordings are not a fresh confirmatory sample.',
    'Protected secret: inclusion of all observed contributions of one operational track within [0,300 s), not identity, physical presence, a complete journey or all visits.',
    'Same 24 TRAIN / 16 CAL / 32 TEST source roles, target pairs, auxiliary knowledge, local400 hard requirements and taxonomy; no source resimulation or replacement.',
    'Only execution strategy, semantic secondary preference and release trigger vary. Selective semantic contribution suppression is OFF; whole failed candidates can still be withheld.',
    'Semantic preference waiting seeks zero loss before the local terminal boundary; that boundary may be regional or coordinated, not always the nominal four-second maximum. Allowed fallback remains possible.',
    'Semantic First with immediate policy release is the imported reference. Its secondary switch alone is not an additional independent execution variant.',
    'New attack models/scaling use TRAIN only; thresholds use CAL only. No TEST-dependent retuning or score-direction reversal. Original fitted models and controls are reused without refitting.',
    'Exploratory paired AUC differences use 1000 source-pair bootstrap replicates, conditional on the fixed fitted models/CAL thresholds; intervals are not simultaneous and establish no equivalence margin.',
    'Scalar31 jointly removes semantic and availability coordinates; it does not isolate semantic leakage. The empirical CAL FPR cap is not a population or TEST guarantee.',
    'Utility is an equal-recording TEST macro mean using each world own input. Every metric retains its available-recording N. Conditional MAE must be read with query coverage; unknown is not zero.',
    'Full-input J combines omitted observations and retained taxonomy loss; it does not include spatial or temporal loss. Retained-only detail and delay are conditional on survival.',
    'One retrospective recipient snapshot at H=300 s. Logical seal delay and offline core/native throughput do not establish live delivery or per-step real-time guarantees.',
    'Full clock/provenance, GT/sensor and physical/data validity remain hard gates. Movement quality is separate and does not filter enrollment.',
    'No universal privacy, person-level protection, navigation-liveness or real-time guarantee follows from these finite experiments.',
)
require = strict.require


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _counts(value, expected, label):
    value = strict._object(value, label)
    result = {}
    for key, count in expected.items():
        require(strict._integer(value.get(key), label + ' ' + key, nullable=False) == count,
                label + ' count differs: ' + key)
        result[key] = count
    return result


def _lineage(report, phase):
    supplement = strict._object(report.get('strategy_supplement'), 'strategy supplement')
    value = strict._object(supplement.get('public_lineage'), 'public supplementary lineage')
    require(value.get('hard_policy_unchanged') is True, 'Hard policy must remain unchanged')
    result = {key: strict._hash(value.get(key)) for key in HASH_FIELDS}
    require(all(result.values()), 'Missing mandatory supplementary provenance hash')
    result.update(_counts(value, dict(source_resimulations=0, source_replacements=0, original_model_refits=0, original_threshold_retunes=0,
        imported_groups=72, imported_method_world_rows=1584, new_method_world_rows=576,
        new_native_executions=576, old_locked_variants=22,
        new_attack_variants=0 if phase == 'utility' else 8), 'supplementary lineage'))
    repair = strict._object(value.get('diagnostic_repair'), 'original diagnostic repair lineage')
    require(repair.get('source_validation_profile') == PROFILE, 'Original repair profile differs')
    projected_repair = {key: strict._hash(repair.get(key)) for key in REPAIR_HASH_FIELDS}
    require(all(projected_repair.values()), 'Missing original diagnostic repair hash')
    projected_repair.update(_counts(repair, REPAIR_COUNTS, 'diagnostic repair'))
    statuses = strict._object(repair.get('original_test_source_status_counts'), 'original source statuses')
    require(set(statuses) == {'invalid'} and statuses['invalid'] == 32, 'Original diagnostic failures must remain visible')
    projected_repair.update(source_validation_profile=PROFILE, original_test_source_status_counts={'invalid': 32},
        scope='Original diagnostic source-qualification failures preserved; exact reporting-only correction and unchanged original model/row bindings.')
    result.update(hard_policy_unchanged=True, diagnostic_repair=projected_repair,
        scope='Authenticated imports and new execution variants on already exposed sources; exploratory supplement, not replacement of the original primary study.')
    return result


def _catalog(value):
    require(isinstance(value, list), 'Method catalog must be a list')
    names = [strict._object(row, 'catalog entry').get('id') for row in value]
    require(len(names) == len(METHOD_IDS) and set(names) == set(METHOD_IDS), 'Exactly fifteen registered methods required')
    require(len(set(names)) == len(names), 'Repeated method catalog entry')
    for entry in value:
        if entry['id'] in EXECUTION_CATALOG:
            expected = EXECUTION_CATALOG[entry['id']]
            require(entry.get('kind') == 'native_adaptive'
                    and tuple(entry.get(key) for key in ('strategy', 'secondary_strategy', 'release_trigger')) == expected,
                    'Catalog execution settings disagree with the labelled variant')


def _outcomes(groups):
    require(isinstance(groups, list), 'Recording outcomes must be a list')
    counts = {split: Counter() for split in GROUP_COUNTS}
    methods = {method: Counter() for method in METHOD_IDS}
    seen = set()
    for group in groups:
        group = strict._object(group, 'recording outcome')
        identity, split = group.get('group_id'), group.get('split')
        require(isinstance(identity, str) and identity and identity not in seen and split in GROUP_COUNTS,
                'Invalid/repeated recording or split')
        seen.add(identity); counts[split][strict._state(group.get('status'))] += 1
        cases = group.get('cases', [])
        require(isinstance(cases, list), 'Case outcomes must be a list')
        keys = set()
        for case in cases:
            case = strict._object(case, 'case outcome')
            method, world = case.get('method_id'), case.get('world')
            require(method in methods and world in ('IN', 'OUT') and (method, world) not in keys,
                    'Unregistered or repeated method/world case')
            keys.add((method, world)); methods[method][strict._state(case.get('status'))] += 1
    for split, n in GROUP_COUNTS.items():
        require(sum(counts[split].values()) <= n, 'Too many recording slots')
        counts[split]['not_reported'] += n - sum(counts[split].values())
    return dict(planned_recordings=72, planned_by_split=dict(GROUP_COUNTS),
        recording_status_by_split={split: dict(sorted(c.items())) for split, c in counts.items()},
        planned_new_native_cases=576, imported_native_cases=1296, planned_native_cases=1872,
        imported_regional_compositions=288, planned_recipient_streams=2160,
        method_world_status={method: dict(planned=144, observed=sum(c.values()),
            unreported=144-sum(c.values()), statuses=dict(sorted(c.items()))) for method, c in methods.items()})


def _utility(value):
    result = strict._utility(value)
    require(result['expected_recordings'] == 32 and result['observed_recordings'] <= 32,
            'Unexpected TEST utility denominator')
    for entry in result['macro_means'].values():
        require(entry['recordings'] <= result['observed_recordings'], 'Metric N exceeds observed recordings')
        require((entry['mean'] is None) == (entry['recordings'] == 0), 'Mean and available denominator disagree')
    for key, entry in result['macro_means'].items():
        if key in ('retained_fraction', 'full_input_J', 'full_input_semantic_loss', 'retained_semantic_loss') or key.endswith(('.reference_availability', '.answered_query_coverage', '.scored_query_coverage')):
            require(entry['mean'] is None or entry['mean'] <= 1, 'Fractional utility exceeds one')
    return result


def _extra_contrasts(value, phase):
    value = {} if value is None else strict._object(value, 'exploratory contrasts')
    require(set(value) <= {name for name, *_ in CONTRASTS}, 'Unregistered supplementary contrast')
    require(phase != 'utility' or not value, 'Utility phase cannot contain new MIA contrasts')
    result = {}
    for name, left, right, seed in CONTRASTS:
        raw = strict._object(value.get(name, {}), 'exploratory contrast')
        require(raw.get('left', left) == left and raw.get('right', right) == right
                and raw.get('metric', 'ROC_AUC') == 'ROC_AUC', 'Supplementary comparator changed')
        reps = strict._object(raw.get('representations', {}), 'exploratory representations')
        require(set(reps) <= set(REPRESENTATIONS), 'Unregistered contrast representation')
        projected = {}
        for representation in REPRESENTATIONS:
            item = strict._object(reps.get(representation, {}), 'exploratory estimate')
            if 'auc_difference' not in item:
                projected[representation] = {'status': 'not_evaluated' if phase == 'utility' else 'unavailable'}
                continue
            difference = strict._number(item['auc_difference'], 'AUC difference', -1, 1, nullable=False)
            require(item.get('confidence_level') == .95 and item.get('seed') == seed
                    and item.get('replicates') == 1000, 'Exploratory bootstrap contract differs')
            n = strict._integer(item.get('independent_groups'), 'bootstrap recording groups', nullable=False)
            require(2 <= n <= 32, 'Invalid paired TEST denominator')
            interval = item.get('interval')
            require(isinstance(interval, (list, tuple)) and len(interval) == 2, 'Invalid exploratory interval')
            bounds = [strict._number(v, 'AUC interval', -1, 1, nullable=False) for v in interval]
            require(bounds[0] <= bounds[1], 'Reversed exploratory interval')
            projected[representation] = dict(status='evaluated', auc_difference=difference,
                interval=bounds, confidence_level=.95, independent_groups=n, replicates=1000,
                scope='Exploratory paired-source contrast; conditional on fixed fits/CAL, no simultaneous interval or equivalence margin.')
        result[name] = dict(left=left, right=right, metric='ROC_AUC', representations=projected)
    return result


def _runtime(value):
    value = {} if value is None else strict._object(value, 'native execution summary')
    result = {'scope': 'Recorded native subprocess wall time; not a per-step or live-delivery guarantee. Old and new runs occurred at different times. Regional compositions have no native runtime.'}
    for key, expected_runs in (('by_method', 144), ('by_method_test', 64)):
        raw = strict._object(value.get(key, {}), 'native runtime family')
        require(set(raw) <= set(METHOD_IDS) - {'regional_static10', 'regional_static20'}, 'Unregistered or nonnative runtime method')
        result[key] = {}
        for method, row in raw.items():
            row = strict._object(row, 'native runtime')
            projected = {'runs': strict._integer(row.get('runs'), 'native runtime runs')}
            require(projected['runs'] in (None, expected_runs), 'Native runtime denominator differs from the complete execution scope')
            for field in ('wall_seconds_mean', 'wall_seconds_p50', 'wall_seconds_p95', 'wall_seconds_maximum', 'core_ms_mean'):
                projected[field] = strict._number(row.get(field), field, 0)
            result[key][method] = projected
    return result


def _complete_attack(value):
    metrics = value['metrics']
    return (value['status'] == 'evaluated' and value['expected_independent_test_groups'] == 32
            and value['complete_test_groups'] == 32 and value['observed_test_rows'] == 64
            and metrics is not None and metrics['positive_cases'] == metrics['negative_cases'] == 32)


def _complete_contrasts(value):
    return all(entry.get('status') == 'evaluated' and entry.get('independent_groups') == 32
               for contrast in value.values() for entry in contrast['representations'].values())


def compact_report(report, *, input_sha256=None):
    report = strict._object(report, 'private supplementary report')
    schema = report.get('schema')
    require(schema in (INPUT_SCHEMA, UTILITY_INPUT_SCHEMA), 'Unexpected supplementary report schema')
    phase = 'utility' if schema == UTILITY_INPUT_SCHEMA else 'mia'
    require(report.get('source_validation_profile') == PROFILE, 'Unexpected protected-unit profile')
    identity = report.get('supplement_id', report.get('evaluation_id'))
    require(isinstance(identity, str) and 0 < len(identity) <= 256, 'Expected bounded supplement identity')
    _catalog(report.get('method_catalog'))
    lineage = _lineage(report, phase)
    assessment = {} if phase == 'utility' else strict._object(report.get('analysis'), 'MIA assessment')
    if phase == 'utility':
        require(report.get('mia_status') == 'not_started', 'Utility stage requires MIA not started')
        require(not report.get('analysis') and not report.get('exploratory_contrasts'), 'Utility stage contains MIA assessment')
    else:
        require(assessment.get('schema') == 'ump.urban-privacy-analysis.v1', 'Unexpected MIA analysis schema')
        require(report.get('original_primary_result_preserved') is True, 'Original primary result preservation is not declared')
    attacks = strict._object(assessment.get('attacks', {}), 'attack family')
    utilities = strict._object(report.get('utility', {}) if phase == 'utility' else assessment.get('utility', {}), 'utility family')
    require(set(attacks) <= set(METHOD_IDS) and set(utilities) <= set(METHOD_IDS), 'Unregistered method in results')
    methods = []
    for name, label in METHODS:
        family = strict._object(attacks.get(name, {}), 'attack representations')
        require(set(family) <= set(REPRESENTATIONS), 'Unregistered attack representation')
        utility = strict._object(utilities.get(name, {}), 'world utilities')
        require(set(utility) <= {'IN', 'OUT'}, 'Unregistered utility world')
        methods.append(dict(id=name, label=label, origin='supplementary_new' if name in NEW_IDS else 'imported_original',
            attacks={representation: strict._attack(family.get(representation)) if phase == 'mia'
                     else strict._attack({'status': 'not_evaluated'}) for representation in REPRESENTATIONS},
            utility={world: _utility(utility.get(world)) for world in ('IN', 'OUT')}))
    controls = strict._object(assessment.get('controls', {}), 'controls')
    require(set(controls) <= set(CONTROLS), 'Unregistered control')
    checks = strict._object(assessment.get('negative_control_checks', {}), 'negative controls')
    positive = strict._object(assessment.get('positive_control_check', {}), 'positive control')
    gate = assessment.get('interpretation_gate', 'not_evaluated')
    require(gate in ('controls_pass', 'diagnose_controls_before_interpreting_lower_attack_success', 'not_evaluated'), 'Unknown interpretation gate')
    status = 'not_evaluated' if phase == 'utility' else strict._state(assessment.get('status', 'not_evaluated'))
    outcomes = _outcomes(report.get('group_outcomes', []))
    complete_utility = all(outcomes['recording_status_by_split'][split].get('verified', 0) == n for split, n in GROUP_COUNTS.items())
    complete_utility = complete_utility and all(m['utility'][world]['observed_recordings'] == 32 for m in methods for world in ('IN', 'OUT'))
    complete_utility = complete_utility and all(row['observed'] == 144 and row['statuses'] == {'verified': 144} for row in outcomes['method_world_status'].values())
    audit = report.get('source_split_audit')
    audit = {} if audit is None else strict._object(audit, 'source split audit')
    source_audit_verified = audit.get('status') == 'verified'
    complete_utility = complete_utility and source_audit_verified
    projected_controls = {name: strict._attack(controls.get(name)) for name in CONTROLS}
    original_contrast = strict._contrast(assessment.get('primary_contrast'))
    exploratory = _extra_contrasts(report.get('exploratory_contrasts'), phase)
    mia_pairs_complete = (all(_complete_attack(m['attacks'][r]) for m in methods for r in REPRESENTATIONS)
                          and all(_complete_attack(value) for value in projected_controls.values()))
    contrasts_complete = (_complete_contrasts(exploratory)
                          and all(entry.get('status') == 'evaluated' and entry.get('independent_groups') == 32
                                  for entry in original_contrast['representations'].values()))
    controls_pass = (gate == 'controls_pass' and positive.get('status') == 'pass'
                     and all(strict._object(checks.get(name, {}), 'control check').get('status') == 'pass'
                             for name in ('prior_only', 'auxiliary_only', 'no_output')))
    if status == 'complete' and not (complete_utility and source_audit_verified and mia_pairs_complete
                                     and contrasts_complete and controls_pass):
        status = 'incomplete_or_diagnostic'
    return dict(schema=SCHEMA, phase=phase, study_design='supplementary_exploratory_existing_recordings',
        source_validation_profile=PROFILE, protected_unit='all_observed_contributions_of_one_operational_track_within_fixed_300s',
        horizon_ms=HORIZON_MS, mia_status='not_started' if phase == 'utility' else status,
        analysis_status=status, interpretation_gate=gate, utility_status='complete' if complete_utility else 'incomplete',
        source_and_execution=outcomes, methods=methods,
        controls=projected_controls,
        negative_control_checks={name: strict._state(strict._object(checks.get(name, {}), 'control check').get('status', 'unavailable')) for name in ('prior_only', 'auxiliary_only', 'no_output')},
        positive_control_check={key: value for key in ('status', 'in_contains_all_approved_sightings', 'OUT_removal_monotone', 'auc_above_chance')
            if (value := (strict._state(positive.get(key, 'unavailable')) if key == 'status' else positive.get(key))) is not None and (key == 'status' or type(value) is bool)},
        original_primary_contrast=original_contrast,
        exploratory_contrasts=exploratory,
        source_quality=window._quality(report.get('source_quality')),
        source_split_audit_status=strict._state(audit.get('status', 'unavailable')),
        native_runtime=_runtime(report.get('native_execution_summary')), supplementary_lineage=lineage,
        provenance=dict(private_report_sha256=strict._hash(input_sha256),
            supplement_id_sha256=hashlib.sha256(identity.encode()).hexdigest(),
            dataset_manifest_sha256=strict._hash(report.get('dataset_manifest_sha256')),
            source_split_audit_sha256=hashlib.sha256(canonical(audit)).hexdigest(),
            native_execution_summary_sha256=hashlib.sha256(canonical(report.get('native_execution_summary', {}))).hexdigest()),
        scope=list(SCOPE))


def _public(public):
    require(isinstance(public, dict) and public.get('schema') == SCHEMA and public.get('source_validation_profile') == PROFILE,
            'Unexpected public supplementary schema/profile')
    return public


def _count(value):
    return 'NA' if value is None else str(value)


def markdown(public):
    public = _public(public)
    lines = ['# Supplementary strategy comparison on reused recordings', '',
        '**Exploratory supplement. The original primary study remains unchanged.**', '',
        f"Phase: **{public['phase']}**. Utility status: **{public['utility_status']}**. MIA status: **{public['mia_status']}**. Interpretation gate: **{public['interpretation_gate']}**.", '',
        'The same 24 TRAIN / 16 CAL / 32 TEST sources and matched IN/OUT target pairs are reused. TEST recordings were already evaluated in the original study; these added comparisons are not fresh confirmatory evidence.', '',
        'All observed contributions of one operational track within [0,300 s) form the protected unit. Hard regional requirements remain identical. Only execution preferences and release rules differ.', '',
        '## Execution and movement quality', '', '| Split | Planned | Reported outcomes |', '|---|---:|---|']
    for split, n in GROUP_COUNTS.items():
        states = ', '.join(f'{state}: {count}' for state, count in public['source_and_execution']['recording_status_by_split'][split].items() if count)
        lines.append(f'| {split} | {n} | {states} |')
    lines += ['', 'Planned recipient streams: 2160 = 1584 imported + 576 new. Native executions: 1872 = 1296 imported + 576 new; regional compositions remain 288. Missing/failed cases are retained, never replaced.', '',
        '| Split | Quality reports | Sources active at H | Sources pending at H | Sources with reported stalls |', '|---|---:|---:|---:|---:|']
    for split, row in public['source_quality']['by_split'].items():
        lines.append('| ' + ' | '.join([split] + [_count(row[key]) for key in ('quality_reports', 'sources_with_active_at_horizon', 'sources_with_pending_at_horizon', 'sources_with_reported_stalls')]) + ' |')
    lines += ['', 'Quality counts are sources, not tracks or contributions. Movement quality does not filter enrollment or count as a privacy benefit.', '', '## TEST utility and runtime', '',
        '| Method | World | Available recordings | Retained (%) | J (%) | Retained semantic loss (%) | Mean side (m) | Mean logical delay (ms) | Core processing (s) | Exact coverage (%) | Estimated MAE | Estimated coverage (%) |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for method in public['methods']:
        for world, utility in method['utility'].items():
            values = [method['label'], world, f"{utility['observed_recordings']}/{utility['expected_recordings']}"]
            for key, scale in (('retained_fraction', 100), ('full_input_J', 100), ('retained_semantic_loss', 100),
                ('mean_retained_cell_side_m', 1), ('logical_seal_delay_ms.mean', 1), ('core_processing_ms', .001),
                ('query_exact.answered_query_coverage', 100), ('query_estimate.occupancy_mae', 1), ('query_estimate.answered_query_coverage', 100)):
                values.append(strict._fmt(strict._mean(utility, key), scale))
            lines.append('| ' + ' | '.join(values) + ' |')
    lines += ['', 'Means weight recordings equally; each metric has its own available N in summary.json. J covers omission plus taxonomy loss, not spatial/temporal loss. Retained detail is conditional on retained input. Compare conditional MAE together with answered coverage; unknown queries are not zero.', '',
        '| Native method | TEST runs | Mean subprocess wall (s) | p95 subprocess wall (s) | Maximum subprocess wall (s) |', '|---|---:|---:|---:|---:|']
    runtime = public['native_runtime']['by_method_test']
    for method in public['methods']:
        row = runtime.get(method['id'], {})
        lines.append('| ' + ' | '.join((method['label'], _count(row.get('runs')), strict._fmt(row.get('wall_seconds_mean')), strict._fmt(row.get('wall_seconds_p95')), strict._fmt(row.get('wall_seconds_maximum')))) + ' |')
    lines += ['', 'Core-processing and native-subprocess wall times have different boundaries. Old and new executions occurred at different times. Neither is a per-step deadline or live-delivery benchmark. Regional composition native runtime is unavailable.', '', '## MIA assessment', '']
    if public['phase'] == 'utility':
        lines += ['**MIA for the new strategies has not started.** Historical original attack scores are omitted from this utility-stage report. No new privacy benefit is inferred from native execution, utility or policy compliance.', '']
    else:
        lines += ['The new models use TRAIN scaling/fits and CAL thresholds only. Original 22 locked variants and controls are imported without refitting; eight new method/representation variants are added. All additions are exploratory.', '',
            '| Method | Full111 AUC | Scalar31 AUC | Full111 TPR [95% CI] | Full111 FPR [95% CI] | Complete TEST pairs | Full111 status |', '|---|---:|---:|---|---|---:|---|']
        for method in public['methods']:
            full, scalar = (method['attacks'][name] for name in REPRESENTATIONS)
            fm, sm = full['metrics'], scalar['metrics']
            lines.append('| ' + ' | '.join((method['label'], strict._fmt(fm.get('roc_auc') if fm else None), strict._fmt(sm.get('roc_auc') if sm else None), strict._rate(fm, 'tpr'), strict._rate(fm, 'fpr'), f"{full['complete_test_groups']}/{full['expected_independent_test_groups']}", full['status'])) + ' |')
        lines += ['', 'The CAL FPR cap is empirical, not a TEST/population guarantee. No individual-method AUC CI was declared. Scalar31 removes semantic and availability coordinates jointly.', '', '### Exploratory paired AUC differences', '',
            '| Contrast (left minus right) | Representation | Difference | Paired 95% interval | Independent groups |', '|---|---|---:|---|---:|']
        labels = dict(METHODS)
        for contrast in public['exploratory_contrasts'].values():
            for representation, entry in contrast['representations'].items():
                interval = entry.get('interval')
                bounds = '[' + ', '.join(strict._fmt(x) for x in interval) + ']' if interval else 'NA'
                lines.append('| ' + ' | '.join((labels[contrast['left']] + ' − ' + labels[contrast['right']], representation, strict._fmt(entry.get('auc_difference')), bounds, _count(entry.get('independent_groups')))) + ' |')
        lines += ['', 'These eight exploratory contrasts are not a replacement for the original primary comparison. Intervals are conditional on fixed fits/CAL and are not simultaneous. An interval crossing zero establishes neither superiority nor equivalence.', '', '### Preserved original primary contrast', '']
        for representation, entry in public['original_primary_contrast']['representations'].items():
            bounds = entry.get('interval')
            lines.append(f"- {representation}: {strict._fmt(entry.get('auc_difference'))}; paired 95% interval " + ('[' + ', '.join(strict._fmt(x) for x in bounds) + ']' if bounds else 'NA') + '.')
        lines += ['', '### Imported controls', '', '| Control | AUC | TPR [95% CI] | FPR [95% CI] | Status |', '|---|---:|---|---|---|']
        for name, attack in public['controls'].items():
            metrics = attack['metrics']
            lines.append('| ' + ' | '.join((name, strict._fmt(metrics.get('roc_auc') if metrics else None), strict._rate(metrics, 'tpr'), strict._rate(metrics, 'fpr'), attack['status'])) + ' |')
    lines += ['', '## Interpretation scope', ''] + ['- ' + line for line in public['scope']]
    lines += ['', '## Lineage', '', 'The original diagnostic repair is included in summary.json and repair-lineage-public.json. Hashes expose lineage, not private file paths or payloads. Keep both with the figures.', '']
    lines.extend(f"- {key}: `{value or 'unavailable'}`" for key, value in public['provenance'].items())
    return '\n'.join(lines) + '\n'


def figures(public, output, *, synthetic=False):
    public = _public(public)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    output = Path(output); require(output.is_dir(), 'Figure directory must exist')
    methods = public['methods']; labels = [m['label'] for m in methods]; ys = list(range(len(methods)))
    caption = ('SYNTHETIC layout fixture — not experimental evidence.\n' if synthetic else '') + ('Exploratory supplement on reused recordings; all observed track contributions in H=300 s; final snapshot. TEST N=32.\n'
        'Identical hard policies; metric-specific N in JSON. Logical delay/offline throughput are not live-delivery guarantees.')
    generated = []
    def save(fig, stem, *, bottom=.11):
        fig.text(.01, .012, caption, fontsize=8)
        fig.tight_layout(rect=(0, bottom, 1, .96))
        for extension in ('png', 'svg'):
            path = output / (stem + '.' + extension); require(not path.exists(), 'Refuse figure overwrite')
            fig.savefig(path, dpi=170, metadata={'Creator': 'UMP-Simulator exploratory strategy supplement'})
            generated.append(path.name)
        plt.close(fig)
    def axis(ax):
        ax.set_yticks(ys, labels); ax.set_ylim(len(methods)-.5, -.5); ax.grid(axis='x', alpha=.18)
    def color(method):
        return '#c56627' if method['id'] in NEW_IDS else '#287f73' if method['id'] == 'adaptive_semantic_first' else '#4677a4'
    fig, axes = plt.subplots(1, 4, figsize=(19, 8.6), sharey=True)
    for ax, (key, scale, title) in zip(axes, (('retained_fraction',100,'Retained input (%)'),('full_input_J',100,'Full-input J (%)'),('retained_semantic_loss',100,'Retained semantic loss (%)'),('logical_seal_delay_ms.mean',1,'Logical seal delay (ms)'))):
        for i, method in enumerate(methods):
            value = strict._mean(method['utility']['IN'], key)
            if value is None: ax.text(.01,i,'NA',transform=ax.get_yaxis_transform(),va='center',fontsize=7)
            else: ax.scatter(value*scale,i,color=color(method),s=28,zorder=3)
        axis(ax); ax.set_title(title,fontsize=10); ax.set_xlim(left=0)
    fig.suptitle('Supplementary TEST utility: IN world, equal recording weights',fontsize=12)
    save(fig,'urban-strategy-supplement-utility')
    fig, axes = plt.subplots(1,2,figsize=(13.5,8.6),sharey=True)
    for ax,(key,scale,title) in zip(axes,(('mean_retained_cell_side_m',1,'Mean retained cell side (m)'),('core_processing_ms',.001,'Whole-recording core processing (s)'))):
        for i, method in enumerate(methods):
            value = strict._mean(method['utility']['IN'],key)
            if value is None: ax.text(.01,i,'NA',transform=ax.get_yaxis_transform(),va='center',fontsize=7)
            else: ax.scatter(value*scale,i,color=color(method),s=28,zorder=3)
        axis(ax);ax.set_title(title,fontsize=10);ax.set_xlim(left=0)
    fig.suptitle('Supplementary retained geometry and offline runtime: IN world',fontsize=12)
    save(fig,'urban-strategy-supplement-detail-runtime')
    if public['phase'] == 'utility': return generated
    fig, axes = plt.subplots(1,2,figsize=(15,8.6),sharey=True)
    for i,method in enumerate(methods):
        for representation,marker,offset,tone in (('semantic111','o',-.12,'#2669a1'),('scalar31','x',.12,'#c66a16')):
            metrics=method['attacks'][representation]['metrics']
            if metrics is None or metrics['roc_auc'] is None:axes[0].text(.01,i+offset,'NA',va='center',fontsize=7,color=tone)
            else:axes[0].scatter(metrics['roc_auc'],i+offset,marker=marker,color=tone,zorder=3)
        metrics=method['attacks']['semantic111']['metrics']
        for key,offset,tone in (('tpr',-.12,'#2b8a63'),('fpr',.12,'#b4413d')):
            if metrics is None or metrics[key] is None:axes[1].text(.01,i+offset,'NA',va='center',fontsize=7,color=tone)
            else:
                axes[1].scatter(metrics[key],i+offset,color=tone,s=25,zorder=3)
                interval=metrics.get(key+'_interval')
                if interval:axes[1].hlines(i+offset,interval['lower'],interval['upper'],color=tone,linewidth=1.2)
    for ax in axes:axis(ax);ax.set_xlim(-.015,1.015)
    axes[0].axvline(.5,color='#666666',ls='--',lw=1);axes[0].set(title='Supplementary track-window ROC-AUC',xlabel='ROC-AUC')
    axes[1].set(title='Full111 rates: exact 95% intervals',xlabel='Rate')
    axes[0].legend(handles=[Line2D([],[],ls='',marker='o',color='#2669a1',label='Full111'),Line2D([],[],ls='',marker='x',color='#c66a16',label='Scalar31')],loc='upper center',bbox_to_anchor=(.5,-.06),ncol=2,fontsize=8)
    axes[1].legend(handles=[Line2D([],[],marker='o',color='#2b8a63',label='TPR'),Line2D([],[],marker='o',color='#b4413d',label='FPR')],loc='upper center',bbox_to_anchor=(.5,-.06),ncol=2,fontsize=8)
    save(fig,'urban-strategy-supplement-attack')
    fig,ax=plt.subplots(figsize=(15,6.5));contrast_labels=[]
    short={name:label for name,label in METHODS}
    for i,(_,left,right,_) in enumerate(CONTRASTS):
        contrast_labels.append(short[left]+' − '+short[right])
        entries=list(public['exploratory_contrasts'].values())[i]['representations']
        for representation,offset,tone,marker in (('semantic111',-.12,'#2669a1','o'),('scalar31',.12,'#c66a16','x')):
            entry=entries[representation]
            if entry.get('status')!='evaluated':ax.text(.01,i+offset,'NA',transform=ax.get_yaxis_transform(),va='center',fontsize=7,color=tone)
            else:ax.hlines(i+offset,*entry['interval'],color=tone,lw=1.2);ax.scatter(entry['auc_difference'],i+offset,color=tone,marker=marker,zorder=3)
    ax.axvline(0,color='#666666',ls='--',lw=1);ax.set_yticks(range(len(CONTRASTS)),contrast_labels);ax.set_ylim(len(CONTRASTS)-.5,-.5);ax.grid(axis='x',alpha=.18);ax.set(title='Exploratory paired ROC-AUC differences: conditional 95% intervals',xlabel='AUC(left) − AUC(right); intervals are not simultaneous')
    ax.legend(handles=[Line2D([],[],marker='o',color='#2669a1',label='Full111'),Line2D([],[],marker='x',color='#c66a16',label='Scalar31')],loc='upper center',bbox_to_anchor=(.5,-.15),ncol=2,fontsize=8)
    save(fig,'urban-strategy-supplement-contrasts',bottom=.22)
    return generated


def export(report_path, output, *, make_figures=True):
    report_path,output=Path(report_path),Path(output)
    require(report_path.is_file() and report_path.stat().st_size<=2*1024**3,'Expected bounded private report')
    payload=report_path.read_bytes();report=json.loads(payload,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    public=compact_report(report,input_sha256=hashlib.sha256(payload).hexdigest())
    output.mkdir(parents=True,exist_ok=False)
    for name,value in (('summary.json',public),('repair-lineage-public.json',public['supplementary_lineage'])):
        with (output/name).open('x') as stream:json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    with (output/'report.md').open('x') as stream:stream.write(markdown(public))
    generated=figures(public,output) if make_figures else []
    files=[output/name for name in ('summary.json','report.md','repair-lineage-public.json',*generated)]
    with (output/'artifact-receipt.json').open('x') as stream:
        json.dump(dict(schema=ARTIFACT_SCHEMA,source_validation_profile=PROFILE,phase=public['phase'],
            study_design=public['study_design'],source_report_sha256=hashlib.sha256(payload).hexdigest(),
            reporter_sha256=sha(Path(__file__)),artifacts_sha256={p.name:sha(p) for p in files}),stream,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
    return public


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--no-figures',action='store_true');args=parser.parse_args(argv)
    value=export(args.report,args.output,make_figures=not args.no_figures)
    print(json.dumps(dict(schema=SCHEMA,phase=value['phase'],utility_status=value['utility_status'],mia_status=value['mia_status'])))


if __name__=='__main__':main()
