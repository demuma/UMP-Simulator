#!/usr/bin/env python3
"""Export aggregate-only selective-suppression comparisons, without opening lineage artifacts.

All public strings and metric paths come from fixed allowlists. Source IDs,
individual predictions, model parameters and CAL thresholds remain private.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import report_urban_privacy_primary as strict
import report_urban_semantic_ablation as old

UTILITY_INPUT_SCHEMA = 'ump.urban-selective-suppression-utility.v1'
INPUT_SCHEMA = 'ump.urban-selective-suppression-report.v1'
SCHEMA = 'ump.urban-selective-suppression-public-report.v1'
ARTIFACT_SCHEMA = 'ump.urban-selective-suppression-public-artifacts.v1'
BASE_METHODS = old.BASE_METHODS
BASE_IDS = tuple(name for name, _ in BASE_METHODS)
NEW_IDS = tuple(name + '_selective' for name in BASE_IDS)
METHOD_IDS = BASE_IDS + NEW_IDS
REPRESENTATIONS = ('semantic111', 'scalar31')
SOURCE_TYPES = old.SOURCE_CLASSES
CONTRASTS = tuple((name + '_selective_vs_disabled', name + '_selective', name, 20261028501 + i)
                  for i, name in enumerate(BASE_IDS)) + tuple(
    (name + '_selective_vs_regional_selective', name + '_selective', 'regional_static20_selective', 20261028601 + i)
    for i, name in enumerate(BASE_IDS[2:]))
UTILITY_METRICS = ('retained_fraction', 'full_input_J', 'retained_semantic_loss',
                   'mean_retained_cell_side_m', 'mean_retained_interval_ms', 'logical_seal_delay_ms.mean')
COHORT_FIELDS = ('input_observations', 'retained_observations', 'selectively_suppressed_observations',
                 'whole_footprint_suppressed_observations', 'retained_fraction', 'selectively_suppressed_fraction',
                 'input_observation_contributions', 'retained_observation_contributions',
                 'unpublished_observation_contributions')
UTILITY_KEYS = frozenset(key for key in strict.UTILITY_KEYS
                         if not key.startswith(('query_exact.', 'query_estimate.'))) | frozenset((
    'selectively_suppressed_fraction_of_input', 'selectively_suppressed_observations',
    'whole_footprint_suppressed_observations', 'whole_footprint_suppressed_fraction_of_input')) | frozenset(
    'source_accounting.by_source_type.' + cohort + '.' + field
    for cohort in SOURCE_TYPES for field in COHORT_FIELDS)
LINEAGE_KEYS = ('protocol', 'history_snapshot', 'original_config', 'native_binary',
                'old_models', 'old_model_lock', 'old_report', 'parallel_execution_receipt')
DESIGN_COUNTS = dict(source_recordings=72, train=24, calibration=16, test=32, horizon_ms=300000,
                     workers=6, new_native_cases=1296, regional_compositions=144,
                     imported_headline_rows=1008, new_headline_rows=1008, new_models=14,
                     source_resimulations=0, old_model_refits=0)
SCOPE = (
    'Exploratory reuse of 72 already exposed recordings: 24 TRAIN, 16 CAL and 32 TEST. Previously exposed TEST evidence is not a fresh holdout.',
    'Semantic generalization is enabled throughout. The comparison changes selective suppression from OFF to ON with a per-candidate 0.10 input-contribution cap; whole failed footprints may still be withheld.',
    'The 0.10 selective cap is not a cap on total omitted traffic, each source type, or an empirical privacy guarantee. Read total retention and per-type omission together.',
    'J=(1-retained fraction)+retained fraction times retained taxonomy loss. It includes omission, excludes spatial and temporal distortion, and is not a privacy metric.',
    'Utility uses equal-recording TEST means and each world own input. Each metric and paired interval retains its available recording count; undefined conditional loss and absent historical cohorts remain unavailable.',
    'Per-type selective omission fractions divide omitted original contributions by that type original contributions in each recording, then average recordings. They are not ratios of macro-mean counts.',
    'MIA protects inclusion of all observed contributions of one operational track in [0,300 s), not identity, an entire journey or every visit. New scaling/fits use TRAIN only and operating choices use CAL only.',
    'Full111 versus Scalar31 is a joint representation comparison; it does not isolate semantic leakage. A lower observed attack AUC does not establish a universal privacy guarantee.',
    'AUC intervals resample paired TEST recordings 1000 times, conditional on fixed TRAIN fits and CAL choices. Utility intervals use available paired recordings. All intervals are marginal, exploratory and non-simultaneous; crossing zero establishes neither superiority nor equivalence.',
    'Native runs use six concurrent recording workers. These times describe batch throughput and are not isolated runtime benchmarks. Logical sealing delay is not measured live-delivery latency or a per-step guarantee.',
)
require = strict.require


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _catalog(raw):
    require(isinstance(raw, list) and [item.get('id') for item in raw if isinstance(item, dict)] == list(METHOD_IDS),
            'Exactly the registered seven OFF and seven selective ON methods are required in order')
    for item, identity in zip(raw, METHOD_IDS):
        base = identity.removesuffix('_selective')
        enabled = identity in NEW_IDS
        kind = 'regional_static' if base == 'regional_static20' else 'native_fixed' if base == 'fixed20_400ms' else 'native_adaptive'
        require(item.get('base_method_id') == base and item.get('kind') == kind
                and item.get('semantic_generalization') == 'enabled'
                and item.get('suppression_enabled') is enabled, 'Method capability/catalog differs')
        require(strict._number(item.get('suppression_cap'), 'suppression cap', 0, 1, nullable=False) == (.1 if enabled else 0),
                'Method suppression cap differs')


def _design(raw):
    raw = strict._object(raw, 'study design')
    require(all(type(raw.get(key)) is int and raw[key] == value for key, value in DESIGN_COUNTS.items()),
            'Study design counts or execution scope differ')
    require(raw.get('suppression_cap') == .1 and raw.get('semantic_generalization') == 'enabled'
            and raw.get('test_reused_exploratory') is True, 'Study capability/reused-TEST scope differs')
    return dict(DESIGN_COUNTS, suppression_cap=.1, semantic_generalization='enabled', test_reused_exploratory=True)


def _lineage(raw):
    raw = strict._object(raw, 'lineage')
    result = {}
    for key in LINEAGE_KEYS:
        reference = strict._object(raw.get(key), 'lineage reference')
        result[key + '_sha256'] = strict._hash(reference.get('sha256'))
        require(result[key + '_sha256'] is not None, 'Mandatory lineage hash missing: ' + key)
    return result


def _utility(raw):
    raw = {} if raw is None else strict._object(raw, 'utility world')
    observed = strict._integer(raw.get('observed_recordings', 0), 'observed utility recordings', nullable=False)
    require(raw.get('expected_recordings', 32) == 32 and observed <= 32, 'TEST utility denominator differs')
    means = strict._object(raw.get('macro_means', {}), 'utility means')
    result = dict(expected_recordings=32, observed_recordings=observed, macro_means={})
    for key in sorted(UTILITY_KEYS & means.keys()):
        entry = strict._object(means[key], 'utility metric')
        value = strict._number(entry.get('mean'), 'utility mean', 0)
        n = strict._integer(entry.get('recordings'), 'available utility recordings', nullable=False)
        require(n <= observed and ((value is None) == (n == 0)), 'Utility mean/available denominator differs')
        fractional = key in ('retained_fraction', 'full_input_J', 'full_input_semantic_loss', 'retained_semantic_loss',
                             'selectively_suppressed_fraction_of_input', 'whole_footprint_suppressed_fraction_of_input') or key.endswith(('.retained_fraction', '.selectively_suppressed_fraction', '.reference_availability',
                             '.answered_query_coverage', '.scored_query_coverage'))
        require(not fractional or value is None or value <= 1, 'Utility fraction exceeds one')
        result['macro_means'][key] = dict(mean=value, recordings=n)
    return result


def _attack(raw, features):
    checked = strict._attack(raw)
    complete = old._complete_attack(checked, features)
    metrics = checked['metrics']
    if metrics is not None:
        metrics = {key: value for key, value in metrics.items() if key != 'threshold'}
    return dict(status=checked['status'], metrics=metrics,
                expected_independent_test_groups=checked['expected_independent_test_groups'],
                complete_test_groups=checked['complete_test_groups'], observed_test_rows=checked['observed_test_rows'],
                fit_converged=(checked['fit_diagnostics'] or {}).get('converged'),
                complete=complete)


def _paired_utility(raw):
    raw = strict._object(raw or {}, 'paired utility contrasts')
    expected = {key for key, _, _, _ in CONTRASTS[:7]}
    require(set(raw) <= expected, 'Unknown paired utility comparator')
    result = {}
    for key, left, right, _ in CONTRASTS[:7]:
        item = strict._object(raw.get(key, {}), 'paired utility comparator')
        require(item.get('left', left) == left and item.get('right', right) == right and item.get('world', 'IN') == 'IN',
                'Paired utility comparator/world differs')
        metrics = strict._object(item.get('metrics', {}), 'paired utility metrics')
        require(set(metrics) <= UTILITY_KEYS, 'Unknown paired utility metric')
        projected = {}
        for metric in sorted(metrics):
            entry = strict._object(metrics[metric], 'paired utility metric')
            n = strict._integer(entry.get('paired_recordings'), 'paired utility recordings', nullable=False)
            require(n <= 32 and entry.get('replicates') == 1000 and entry.get('confidence_level') == .95,
                    'Paired utility bootstrap contract differs')
            difference = strict._number(entry.get('mean_difference'), 'paired mean difference')
            require((difference is None) == (n == 0), 'Paired utility availability differs')
            interval = entry.get('ci95')
            if interval is not None:
                require(n >= 2 and isinstance(interval, (list, tuple)) and len(interval) == 2, 'Invalid utility interval')
                interval = [strict._number(x, 'utility interval bound', nullable=False) for x in interval]
                require(interval[0] <= interval[1], 'Reversed utility interval')
            require(n < 2 or interval is not None, 'Missing available paired utility interval')
            projected[metric] = dict(mean_difference=difference, ci95=interval, paired_recordings=n,
                                     replicates=1000, confidence_level=.95)
        result[key] = dict(left=left, right=right, world='IN', direction='selective ON minus OFF', metrics=projected)
    return result


def _auc_contrasts(raw, phase, attacks):
    raw = strict._object(raw or {}, 'AUC contrasts')
    require(set(raw) <= {key for key, _, _, _ in CONTRASTS}, 'Unknown AUC comparator')
    require(phase != 'utility' or not raw, 'Utility report must not expose MIA contrasts')
    result = {}
    for key, left, right, seed in CONTRASTS:
        item = strict._object(raw.get(key, {}), 'AUC comparator')
        require(item.get('left', left) == left and item.get('right', right) == right
                and item.get('metric', 'ROC_AUC') == 'ROC_AUC', 'AUC comparator/direction differs')
        family = strict._object(item.get('representations', {}), 'AUC contrast representations')
        require(set(family) <= set(REPRESENTATIONS), 'Unknown AUC contrast representation')
        projected = {}
        for representation in REPRESENTATIONS:
            entry = strict._object(family.get(representation, {}), 'paired AUC estimate')
            if 'auc_difference' not in entry:
                projected[representation] = dict(status='not_evaluated' if phase == 'utility' else 'unavailable')
                continue
            require(entry.get('seed') == seed and entry.get('replicates') == 1000
                    and entry.get('confidence_level') == .95, 'Paired AUC bootstrap contract differs')
            n = strict._integer(entry.get('independent_groups'), 'paired AUC groups', nullable=False)
            require(2 <= n <= 32, 'Paired AUC denominator differs')
            interval = entry.get('interval')
            require(isinstance(interval, (list, tuple)) and len(interval) == 2, 'Missing paired AUC interval')
            bounds = [strict._number(x, 'AUC interval bound', -1, 1, nullable=False) for x in interval]
            require(bounds[0] <= bounds[1], 'Reversed paired AUC interval')
            difference = strict._number(entry['auc_difference'], 'AUC difference', -1, 1, nullable=False)
            left_metrics = attacks[left][representation]['metrics']
            right_metrics = attacks[right][representation]['metrics']
            if left_metrics is not None and right_metrics is not None:
                require(math.isclose(difference, left_metrics['roc_auc'] - right_metrics['roc_auc'], abs_tol=1e-12),
                        'AUC contrast disagrees with registered point estimates')
            projected[representation] = dict(status='evaluated', auc_difference=difference, interval=bounds,
                                              independent_groups=n, replicates=1000, confidence_level=.95)
        result[key] = dict(left=left, right=right, direction='left minus right', metric='ROC_AUC', representations=projected)
    return result


def build_report(report, *, input_sha256=None):
    report = strict._object(report, 'private suppression report')
    schema = report.get('schema')
    require(schema in (UTILITY_INPUT_SCHEMA, INPUT_SCHEMA), 'Unexpected selective-suppression report schema')
    phase = 'utility' if schema == UTILITY_INPUT_SCHEMA else 'assessed'
    require(report.get('phase') == phase, 'Report phase/schema differs')
    _catalog(report.get('method_catalog'))
    design = _design(report.get('study_design'))
    lineage = _lineage(report.get('lineage'))
    utility = strict._object(report.get('utility'), 'utility family')
    require(set(utility) <= set(METHOD_IDS), 'Unknown headline utility method')
    analysis = strict._object(report.get('analysis', {}) or {}, 'MIA assessment')
    if phase == 'utility':
        require(not analysis and not report.get('exploratory_contrasts') and report.get('mia_status', 'not_started') == 'not_started',
                'MIA must remain not started at utility stage')
    else:
        require(analysis.get('schema') == 'ump.urban-privacy-analysis.v1'
                and analysis.get('utility') == utility, 'Final utility/analysis family differs')
    raw_attacks = strict._object(analysis.get('attacks', {}), 'attack family')
    require(set(raw_attacks) <= set(METHOD_IDS), 'Unknown attack method')
    methods, attacks = [], {}
    utility_complete = True
    for base, label in BASE_METHODS:
        for identity, enabled in ((base, False), (base + '_selective', True)):
            worlds = strict._object(utility.get(identity, {}), 'utility worlds')
            require(set(worlds) <= {'IN', 'OUT'}, 'Unknown utility world')
            projected = {world: _utility(worlds.get(world)) for world in ('IN', 'OUT')}
            family = strict._object(raw_attacks.get(identity, {}), 'attack representations')
            require(set(family) <= set(REPRESENTATIONS), 'Unknown attack representation')
            attacks[identity] = {rep: _attack(family.get(rep), 111 if rep == 'semantic111' else 31)
                                 for rep in REPRESENTATIONS}
            for world in projected.values():
                means = world['macro_means']
                selective = means.get('selectively_suppressed_fraction_of_input', {}).get('mean')
                require(selective is None or selective <= (.1 if enabled else 0) + 1e-12,
                        'Selective omission contradicts the declared suppression capability/cap')
                if not enabled:
                    require(all(value['mean'] in (None, 0) for key, value in means.items()
                                if key.endswith(('.selectively_suppressed_observations', '.selectively_suppressed_fraction'))),
                            'Historical suppression-OFF cohort reports selective omission')
                utility_complete = utility_complete and world['observed_recordings'] == 32
                utility_complete = utility_complete and all(means.get(key, {}).get('recordings') == 32
                    for key in ('retained_fraction', 'full_input_J', 'published_policy_violations'))
                utility_complete = utility_complete and means.get('published_policy_violations', {}).get('mean') == 0
            methods.append(dict(id=identity, base_method_id=base, label=label,
                                suppression_enabled=enabled, suppression_cap=.1 if enabled else 0,
                                semantic_generalization='enabled', utility=projected, attacks=attacks[identity]))
    controls_raw = strict._object(analysis.get('controls', {}), 'controls')
    require(set(controls_raw) <= set(strict.CONTROLS), 'Unknown control')
    controls = {name: _attack(controls_raw.get(name), 8 if name == 'auxiliary_only' else 111 if name == 'no_output' else None)
                for name in strict.CONTROLS}
    checks = strict._object(analysis.get('negative_control_checks', {}), 'negative controls')
    negative = {name: strict._state(strict._object(checks.get(name, {}), 'negative control').get('status', 'unavailable'))
                for name in ('prior_only', 'auxiliary_only', 'no_output')}
    positive = strict._state(strict._object(analysis.get('positive_control_check', {}), 'positive control').get('status', 'unavailable'))
    gate = analysis.get('interpretation_gate', 'not_evaluated')
    require(gate in ('not_evaluated', 'controls_pass', 'diagnose_controls_before_interpreting_lower_attack_success'),
            'Unknown interpretation gate')
    contrasts = _auc_contrasts(report.get('exploratory_contrasts'), phase, attacks)
    paired = _paired_utility(report.get('paired_utility_contrasts'))
    by_id = {item['id']: item for item in methods}
    for item in paired.values():
        for metric, entry in item['metrics'].items():
            left = by_id[item['left']]['utility']['IN']['macro_means'].get(metric, {})
            right = by_id[item['right']]['utility']['IN']['macro_means'].get(metric, {})
            if entry['paired_recordings'] == left.get('recordings') == right.get('recordings') == 32:
                require(math.isclose(entry['mean_difference'], left['mean'] - right['mean'], abs_tol=1e-9),
                        'Paired utility difference disagrees with complete macro means')
    complete = (utility_complete and analysis.get('status') == 'complete'
                and all(value['complete'] for family in attacks.values() for value in family.values())
                and all(value['complete'] for value in controls.values())
                and all(value['status'] == 'evaluated' and value['independent_groups'] == 32
                        for item in contrasts.values() for value in item['representations'].values())
                and gate == 'controls_pass' and positive == 'pass' and all(value == 'pass' for value in negative.values()))
    return dict(schema=SCHEMA, phase=phase, study_design=design, methods=methods,
                utility_status='complete' if utility_complete else 'incomplete',
                mia_status='not_started' if phase == 'utility' else 'complete' if complete else 'incomplete_or_diagnostic',
                interpretation_gate=gate, controls=controls, negative_control_checks=negative,
                positive_control_status=positive, exploratory_contrasts=contrasts,
                paired_utility_contrasts=paired, lineage=lineage,
                provenance=dict(private_report_sha256=strict._hash(input_sha256)), scope=list(SCOPE))


compact_report = build_report


def _mean(method, world, key):
    return method['utility'][world]['macro_means'].get(key, {}).get('mean')


def _metric(method, key, scale=1, world='IN'):
    entry = method['utility'][world]['macro_means'].get(key, {})
    return strict._fmt(entry.get('mean'), scale) + ' (n=' + str(entry.get('recordings', 0)) + ')'


def _interval(entry, key='auc_difference', bounds='interval', scale=1):
    interval = entry.get(bounds)
    text = 'NA' if interval is None else '[' + ', '.join(strict._fmt(value, scale) for value in interval) + ']'
    return strict._fmt(entry.get(key), scale) + ' ' + text


def markdown(public):
    require(public.get('schema') == SCHEMA, 'Expected public suppression summary')
    selected = {item['id']: item for item in public['methods']}
    lines = ['# Selective suppression with semantic generalization enabled', '',
             '**Exploratory paired reuse; suppression OFF versus ON (0.10).**', '',
             f"Utility: **{public['utility_status']}**. MIA: **{public['mia_status']}**. Gate: **{public['interpretation_gate']}**.", '',
             '## TEST utility, IN world', '',
             'Each cell shows OFF → ON; metric-specific available recording counts are retained.', '',
             '| Method | Retained (%) | Full-input J (%) | Retained taxonomy loss (%) | Retained cell side (m) | Logical delay (ms) |',
             '|---|---:|---:|---:|---:|---:|']
    descriptors = (('retained_fraction', 100), ('full_input_J', 100), ('retained_semantic_loss', 100),
                   ('mean_retained_cell_side_m', 1), ('logical_seal_delay_ms.mean', 1))
    for base, label in BASE_METHODS:
        values = [_metric(selected[base], key, scale) + ' → ' + _metric(selected[base + '_selective'], key, scale)
                  for key, scale in descriptors]
        lines.append('| ' + ' | '.join([label, *values]) + ' |')
    lines += ['', 'J includes omitted input and retained taxonomy loss; lower is better. Conditional loss is undefined when no input survives. The selective 0.10 candidate cap does not bound total omission.', '',
              '## Paired utility changes: ON minus OFF', '',
              '| Method | Retention (pp) | J (pp) | Taxonomy loss (pp) | Cell side (m) | Interval (ms) | Logical delay (ms) |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for base, label in BASE_METHODS:
        values = public['paired_utility_contrasts'][base + '_selective_vs_disabled']['metrics']
        cells = [_interval(values.get(key, {}), 'mean_difference', 'ci95', scale) + ' (n=' + str(values.get(key, {}).get('paired_recordings', 0)) + ')'
                 for key, scale in (('retained_fraction', 100), ('full_input_J', 100),
                                     ('retained_semantic_loss', 100), ('mean_retained_cell_side_m', 1),
                                     ('mean_retained_interval_ms', 1), ('logical_seal_delay_ms.mean', 1))]
        lines.append('| ' + ' | '.join([label, *cells]) + ' |')
    lines += ['', 'Intervals use available paired recordings; these are marginal exploratory 95% intervals, not simultaneous comparisons.', '',
              '## Per-type selective omission', '',
              'The omission figure shows every registered source type and method. Summary JSON retains each type retention, selective omission fraction and contribution counts with its available N. Missing historical cohort fields remain NA; no missing field is replaced by zero.', '']
    if public['phase'] == 'utility':
        lines += ['## MIA pending', '', 'MIA has not started for the new methods. Historical attack results are omitted from this utility-stage report. Utility and hard-policy compliance do not establish a privacy gain.', '']
    else:
        lines += ['## MIA: planned 32 reused TEST pairs per method', '',
                  '| Method | Full111 AUC OFF → ON | Scalar31 AUC OFF → ON | Full111 ON−OFF [95% CI] | Scalar31 ON−OFF [95% CI] |',
                  '|---|---:|---:|---:|---:|']
        for base, label in BASE_METHODS:
            values = []
            for representation in REPRESENTATIONS:
                values.append(' → '.join(strict._fmt((selected[identity]['attacks'][representation]['metrics'] or {}).get('roc_auc'))
                                         for identity in (base, base + '_selective')))
            family = public['exploratory_contrasts'][base + '_selective_vs_disabled']['representations']
            values += [_interval(family[rep]) for rep in REPRESENTATIONS]
            lines.append('| ' + ' | '.join([label, *values]) + ' |')
        lines += ['', 'Lower AUC favors privacy only for this declared attack. A reduction can accompany information loss. Full111/Scalar31 does not isolate semantic leakage; crossing-zero intervals establish neither superiority nor equivalence.', '']
    lines += ['## Scope and provenance', '', *('- ' + line for line in public['scope']), '',
              'Lineage is exported as hashes only. Source IDs, paths, scores, features, model parameters and CAL thresholds are excluded.', '']
    return '\n'.join(lines)


def figures(public, output, *, synthetic=False):
    require(public.get('schema') == SCHEMA, 'Expected public suppression summary')
    output = Path(output)
    require(output.is_dir(), 'Figure directory must exist')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.lines import Line2D
    selected = {item['id']: item for item in public['methods']}
    labels = [label for _, label in BASE_METHODS]
    generated = []
    colors = ('#2869a1', '#c66a16')
    legend = [Line2D([], [], marker='o', ls='', color=colors[0], label='Suppression OFF'),
              Line2D([], [], marker='x', ls='', color=colors[1], label='Suppression ON (0.10)')]
    caption = ('SYNTHETIC layout fixture; not experimental evidence.\n' if synthetic else '') + (
        'Exploratory reused TEST recordings; metric-specific available N and paired Ns are retained in summary.json.\n'
        'Semantic generalization ON throughout. Logical delay is not live delivery; MIA intervals condition on fixed TRAIN/CAL.')

    def save(fig, stem, bottom=.16):
        fig.text(.01, .01, caption, fontsize=8)
        fig.tight_layout(rect=(0, bottom, 1, .94))
        for extension in ('png', 'svg'):
            path = output / (stem + '.' + extension)
            require(not path.exists(), 'Refuse figure overwrite')
            fig.savefig(path, dpi=160)
            generated.append(path.name)
        plt.close(fig)

    def axis(ax):
        ax.set_yticks(range(7), labels)
        ax.set_ylim(6.6, -.6)
        ax.grid(axis='x', alpha=.18)

    fig, axes = plt.subplots(1, 5, figsize=(21, 6.5), sharey=True)
    for ax, (key, scale, title) in zip(axes, (
            ('retained_fraction', 100, 'Retained input (%)'), ('full_input_J', 100, 'Full-input J (%)'),
            ('retained_semantic_loss', 100, 'Retained taxonomy loss (%)'),
            ('mean_retained_cell_side_m', 1, 'Retained cell side (m)'), ('logical_seal_delay_ms.mean', 1, 'Logical delay (ms)'))):
        for i, (base, _) in enumerate(BASE_METHODS):
            for identity, offset, color, marker in ((base, -.1, colors[0], 'o'), (base + '_selective', .1, colors[1], 'x')):
                value = _mean(selected[identity], 'IN', key)
                if value is not None:
                    ax.scatter(value * scale, i + offset, color=color, marker=marker, s=32)
                else:
                    ax.text(.01, i + offset, 'NA', transform=ax.get_yaxis_transform(), fontsize=7)
        axis(ax)
        ax.set_title(title)
        values = [_mean(item, 'IN', key) for item in selected.values()]
        maximum = max((value * scale for value in values if value is not None), default=0)
        ax.set_xlim(0, maximum * 1.08 if maximum else 1)
    axes[0].legend(handles=legend, loc='upper left', bbox_to_anchor=(0, -.13), fontsize=8)
    fig.suptitle('Selective suppression: TEST utility with semantic generalization enabled')
    save(fig, 'urban-selective-suppression-utility')

    fig, axes = plt.subplots(1, 2, figsize=(17, 7.4), sharey=True)
    titles = ('Selective omission of original type contributions (%)', 'Change in total type omission: ON minus OFF (pp)')
    for ax, mode, title in zip(axes, ('selective', 'total_change'), titles):
        values = np.full((len(SOURCE_TYPES), 7), np.nan)
        for i, cohort in enumerate(SOURCE_TYPES):
            stem = 'source_accounting.by_source_type.' + cohort + '.'
            for j, (base, _) in enumerate(BASE_METHODS):
                new = _mean(selected[base + '_selective'], 'IN', stem + ('selectively_suppressed_fraction' if mode == 'selective' else 'retained_fraction'))
                prior = _mean(selected[base], 'IN', stem + 'retained_fraction')
                new_n = selected[base + '_selective']['utility']['IN']['macro_means'].get(stem + 'retained_fraction', {}).get('recordings')
                old_n = selected[base]['utility']['IN']['macro_means'].get(stem + 'retained_fraction', {}).get('recordings')
                value = new if mode == 'selective' else None if new is None or prior is None or new_n != old_n else prior - new
                if value is not None:
                    values[i, j] = value * 100
        cmap = plt.get_cmap('YlOrRd' if mode == 'selective' else 'coolwarm').copy()
        cmap.set_bad('#e5e7eb')
        image = ax.imshow(values, aspect='auto', cmap=cmap, vmin=0 if mode == 'selective' else -100, vmax=100)
        for i in range(len(SOURCE_TYPES)):
            for j in range(7):
                ax.text(j, i, 'NA' if np.isnan(values[i, j]) else f'{values[i,j]:.1f}', ha='center', va='center', fontsize=7)
        ax.set_xticks(range(7), labels, rotation=35, ha='right', fontsize=8)
        ax.set_yticks(range(len(SOURCE_TYPES)), SOURCE_TYPES, fontsize=8)
        ax.set_title(title, fontsize=10)
        fig.colorbar(image, ax=ax, shrink=.65)
    fig.suptitle('Per-type omission: original contribution denominators; gray means unavailable')
    save(fig, 'urban-selective-suppression-omission', bottom=.10)
    if public['phase'] == 'utility':
        return generated
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.6), sharey=True)
    for ax, representation in zip(axes, REPRESENTATIONS):
        for i, (base, _) in enumerate(BASE_METHODS):
            for identity, offset, color, marker in ((base, -.1, colors[0], 'o'), (base + '_selective', .1, colors[1], 'x')):
                metrics = selected[identity]['attacks'][representation]['metrics']
                if metrics is not None:
                    ax.scatter(metrics['roc_auc'], i + offset, color=color, marker=marker, s=32)
        axis(ax)
        ax.axvline(.5, color='#777', linestyle='--', linewidth=.8)
        ax.set(title=('Full111' if representation == 'semantic111' else 'Scalar31') + ' ROC-AUC', xlim=(0, 1))
    axes[0].legend(handles=legend, loc='upper left', bbox_to_anchor=(0, -.13), fontsize=8)
    fig.suptitle('Declared membership attack: fixed TRAIN fits and CAL operating choices')
    save(fig, 'urban-selective-suppression-attack')
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for i, (base, _) in enumerate(BASE_METHODS):
        family = public['exploratory_contrasts'][base + '_selective_vs_disabled']['representations']
        for representation, offset, color, marker in (('semantic111', -.1, colors[0], 'o'), ('scalar31', .1, colors[1], 'x')):
            item = family[representation]
            if item['status'] == 'evaluated':
                lo, hi = item['interval']
                ax.plot([lo, hi], [i + offset, i + offset], color=color)
                ax.scatter(item['auc_difference'], i + offset, color=color, marker=marker, s=32)
    axis(ax)
    ax.axvline(0, color='#777', linestyle='--', linewidth=.8)
    ax.set_xlabel('ROC-AUC: selective ON minus OFF; marginal paired 95% interval')
    ax.legend(handles=[Line2D([], [], marker='o', color=colors[0], label='Full111'),
                       Line2D([], [], marker='x', color=colors[1], label='Scalar31')],
              loc='upper center', bbox_to_anchor=(.5, -.16), ncol=2, fontsize=8)
    fig.suptitle('Paired selective-suppression attack changes')
    save(fig, 'urban-selective-suppression-contrasts', bottom=.22)
    return generated


def export(report_path, output, *, make_figures=True):
    report_path, output = Path(report_path), Path(output)
    require(report_path.is_file() and report_path.stat().st_size <= 2 * 1024 ** 3, 'Expected bounded private report')
    require(not output.exists(), 'Refuse public artifact directory overwrite')
    public = build_report(json.loads(report_path.read_text()), input_sha256=sha(report_path))
    output.mkdir(parents=True)
    for name, value in (('summary.json', public), ('lineage-public.json', public['lineage'])):
        with (output / name).open('x') as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
    with (output / 'report.md').open('x') as stream:
        stream.write(markdown(public))
    names = figures(public, output) if make_figures else []
    paths = [output / name for name in ('summary.json', 'lineage-public.json', 'report.md', *names)]
    with (output / 'artifact-receipt.json').open('x') as stream:
        json.dump(dict(schema=ARTIFACT_SCHEMA, phase=public['phase'], source_sha256=sha(report_path),
                       reporter_code_sha256=sha(__file__),
                       files={path.name: dict(sha256=sha(path), bytes=path.stat().st_size) for path in paths}),
                  stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    return public


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-figures', action='store_true')
    args = parser.parse_args(argv)
    public = export(args.report, args.output, make_figures=not args.no_figures)
    print(json.dumps({key: public[key] for key in ('schema', 'phase', 'utility_status', 'mia_status')}))


if __name__ == '__main__':
    main()
