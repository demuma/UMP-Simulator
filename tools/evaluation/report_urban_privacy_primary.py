#!/usr/bin/env python3
"""Aggregate-only P25.4 public evidence, Markdown and static scientific figures.

This presentation layer accepts independently authenticated private reports; it
never fits models, chooses a comparator or recalibrates a threshold. Projection is
an explicit allowlist, not a recursive removal of a few known private fields.
Private group scores, labels, IDs, motion, model weights, source paths and failure
messages are not published. Missing methods remain visible as unavailable rows.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

SCHEMA = 'ump.urban-primary-public-report.v1'
METHODS = tuple((f'fixed{side}_{window}ms', f'Fixed {side} m / {window / 1000:g} s')
                for side in (10, 20) for window in (400, 1000, 2000, 4000)) + (
    ('regional_static10', 'Regional static 10 m'), ('regional_static20', 'Regional static 20 m'),
    ('adaptive_semantic_first', 'Adaptive Semantic First'))
METHOD_IDS = tuple(name for name, _ in METHODS)
REPRESENTATIONS = ('semantic111', 'scalar31')
CONTROLS = ('prior_only', 'auxiliary_only', 'no_output', 'unprotected')
GROUP_COUNTS = {'train': 24, 'calibration': 16, 'test': 32}
STATES = frozenset(('verified', 'complete', 'evaluated', 'locked', 'incomplete', 'interrupted',
    'not_attempted', 'not_evaluated', 'failed', 'timeout', 'invalid', 'invalid_duplicate',
    'failed_dependency_or_audit', 'nonconverged', 'missing', 'unavailable', 'diagnostic_required',
    'incomplete_or_diagnostic', 'pass', 'fail', 'other'))
METRIC_RATES = ('roc_auc', 'tpr', 'fpr', 'balanced_accuracy', 'precision_at_evaluation_prior', 'evaluation_prior')
METRIC_COUNTS = ('positive_cases', 'negative_cases', 'true_positive', 'false_positive', 'true_negative', 'false_negative')
UTILITY_KEYS = frozenset(('input_observations', 'retained_observations', 'retained_fraction',
    'full_input_J', 'full_input_semantic_loss', 'retained_semantic_loss', 'mean_retained_cell_side_m',
    'mean_retained_interval_ms', 'published_cells', 'core_processing_ms', 'published_policy_violations') +
    tuple('logical_seal_delay_ms.' + field for field in ('mean', 'p50', 'p95', 'p99', 'maximum')) +
    tuple(kind + '.' + field for kind in ('query_exact', 'query_estimate') for field in (
        'reference_queries', 'reference_available_queries', 'answered_queries', 'scored_queries',
        'reference_availability', 'answered_query_coverage', 'scored_query_coverage',
        'absolute_error_sum', 'occupancy_mae', 'known_zero_reference_queries', 'positive_reference_queries')))
SCOPE = (
    'Protected secret: inclusion of one complete visible episode contribution; not person identity, physical presence or all visits.',
    'Recipient availability: one retrospective final snapshot at H=300 s. Logical sealing delay is not measured live delivery latency.',
    'Same local400 hard requirements and suppression OFF for every comparator/world; operational track support is distinct from empirical privacy.',
    'Models and scaling use TRAIN only; operating thresholds use CAL only. No TEST-dependent score-direction flip, tuning or comparator selection.',
    'Rate intervals are two-sided exact 95% Clopper-Pearson. Primary AUC-difference interval is a 1000-replicate paired TEST-recording bootstrap conditional on fixed fitted models.',
    'Scalar31 is a joint representation ablation removing semantic and availability coordinates; it does not isolate semantic leakage.',
    'Utility macro means weight recordings equally and use each world\'s own sampled input. Conditional occupancy MAE must be read with answered/scored coverage; unknown output is not zero.',
    'No universal privacy guarantee, population FPR bound, person-level guarantee or real-time certification follows from these measurements.',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _object(value, label):
    require(isinstance(value, dict), label + ' must be an object')
    return value


def _number(value, label, low=None, high=None, nullable=True):
    if value is None and nullable:
        return None
    require(type(value) in (int, float) and math.isfinite(value), label + ' must be finite numeric data')
    require((low is None or value >= low) and (high is None or value <= high), label + ' is outside its range')
    return value


def _integer(value, label, nullable=True):
    if value is None and nullable:
        return None
    require(type(value) is int and value >= 0, label + ' must be a nonnegative integer')
    return value


def _hash(value):
    if value is None:
        return None
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'Invalid provenance hash')
    return value


def _state(value):
    return value if isinstance(value, str) and value in STATES else 'other'


def _interval(value):
    if value is None:
        return None
    value = _object(value, 'rate interval')
    require(value.get('method') == 'two_sided_exact_clopper_pearson'
            and value.get('confidence_level') == .95, 'Unexpected rate interval contract')
    result = {field: _number(value.get(field), field, 0, 1, nullable=(field == 'estimate'))
              for field in ('estimate', 'lower', 'upper')}
    result.update({field: _integer(value.get(field), field, nullable=False) for field in ('successes', 'trials')})
    require(result['successes'] <= result['trials'] and result['lower'] <= result['upper'], 'Invalid binomial interval')
    require((result['estimate'] is None and result['trials'] == 0) or
            (result['trials'] > 0 and math.isclose(result['estimate'], result['successes'] / result['trials'])),
            'Binomial estimate/count mismatch')
    return dict(result, confidence_level=.95, method='two_sided_exact_clopper_pearson')


def _metrics(value):
    if value is None:
        return None
    value = _object(value, 'attack metrics')
    result = {field: _number(value.get(field), field, 0, 1) for field in METRIC_RATES}
    result.update({field: _integer(value.get(field), field) for field in METRIC_COUNTS})
    result['advantage'] = _number(value.get('advantage'), 'threshold advantage', -1, 1)
    result['threshold'] = _number(value.get('threshold'), 'locked threshold')
    for field in ('tpr_interval', 'fpr_interval'):
        result[field] = _interval(value.get(field))
    if all(result[field] is not None for field in METRIC_COUNTS):
        require(result['true_positive'] + result['false_negative'] == result['positive_cases']
                and result['false_positive'] + result['true_negative'] == result['negative_cases'],
                'Confusion counts differ from evaluated population')
        for rate, numerator, denominator in (('tpr', 'true_positive', 'positive_cases'),
                                               ('fpr', 'false_positive', 'negative_cases')):
            n = result[denominator]
            require((n == 0 and result[rate] is None) or
                    (n > 0 and result[rate] is not None and math.isclose(result[rate], result[numerator]/n)),
                    'Operating rate/count mismatch')
    return result


def _attack(value):
    value = {} if value is None else _object(value, 'attack assessment')
    status = _state(value.get('status', 'missing'))
    metrics = _metrics(value.get('metrics'))
    require((status == 'evaluated') == (metrics is not None), 'Attack status and estimate availability disagree')
    result = {'status': status, 'metrics': metrics,
              'expected_independent_test_groups': _integer(value.get('expected_independent_test_groups', 32), 'expected TEST groups'),
              'complete_test_groups': _integer(value.get('complete_test_groups', 0), 'complete TEST groups'),
              'observed_test_rows': _integer(value.get('observed_test_rows', 0), 'observed TEST rows')}
    fit = value.get('fit_diagnostics')
    if fit is not None:
        fit = _object(fit, 'fit diagnostics')
        require(type(fit.get('converged')) is bool, 'Convergence diagnostic must be boolean')
        result['fit_diagnostics'] = dict(converged=fit['converged'],
            **{field: _integer(fit.get(field), field) for field in ('iterations', 'training_rows', 'feature_count')},
            training_objective=_number(fit.get('training_objective'), 'training objective', 0))
    else:
        result['fit_diagnostics'] = None
    calibration = value.get('locked_calibration')
    if calibration is not None:
        calibration = _object(calibration, 'calibration')
        require(calibration.get('target_fpr') == .1, 'Unexpected calibration cap')
        result['calibration'] = dict(target_fpr=.1, threshold=_number(calibration.get('threshold'), 'CAL threshold'),
            negative_case_fpr_resolution=_number(calibration.get('negative_case_fpr_resolution'), 'CAL FPR resolution', 0, 1),
            metrics=_metrics(calibration.get('calibration')))
    else:
        result['calibration'] = None
    return result


def _utility(value):
    value = {} if value is None else _object(value, 'world utility')
    means = _object(value.get('macro_means', {}), 'utility macro means')
    result = {'expected_recordings': _integer(value.get('expected_recordings', 32), 'expected utility recordings'),
              'observed_recordings': _integer(value.get('observed_recordings', 0), 'observed utility recordings'),
              'macro_means': {}}
    for key in sorted(UTILITY_KEYS & means.keys()):
        entry = _object(means[key], 'utility mean')
        result['macro_means'][key] = {'mean': _number(entry.get('mean'), 'utility value', 0),
                                    'recordings': _integer(entry.get('recordings'), 'utility available recordings', nullable=False)}
    return result


def _contrast(value):
    value = {} if value is None else _object(value, 'primary contrast')
    require(value.get('left', 'adaptive_semantic_first') == 'adaptive_semantic_first'
            and value.get('right', 'regional_static20') == 'regional_static20', 'Primary comparator changed')
    reps = _object(value.get('representations', {}), 'contrast representations')
    result = {'left': 'adaptive_semantic_first', 'right': 'regional_static20', 'metric': 'ROC_AUC', 'representations': {}}
    for name in REPRESENTATIONS:
        entry = _object(reps.get(name, {}), 'contrast assessment')
        if 'auc_difference' not in entry:
            result['representations'][name] = {'status': 'unavailable'}
            continue
        difference = _number(entry['auc_difference'], 'AUC difference', -1, 1, nullable=False)
        raw_interval = entry.get('interval')
        interval = None
        if raw_interval is not None:
            require(isinstance(raw_interval, (list, tuple)) and len(raw_interval) == 2, 'Invalid AUC interval')
            interval = [_number(v, 'AUC interval', -1, 1, nullable=False) for v in raw_interval]
            require(interval[0] <= interval[1], 'Reversed AUC interval')
        require(entry.get('confidence_level') == .95 and entry.get('seed') == 20261025301,
                'Unexpected primary bootstrap contract')
        require((interval is None and entry.get('independent_groups', 0) < 2) or
                (interval is not None and entry.get('replicates') == 1000 and entry.get('independent_groups', 0) >= 2),
                'Unexpected bootstrap replication or availability')
        result['representations'][name] = dict(status='evaluated', auc_difference=difference, interval=interval,
            confidence_level=.95, independent_groups=_integer(entry.get('independent_groups'), 'bootstrap groups', nullable=False),
            replicates=_integer(entry.get('replicates'), 'bootstrap replicates', nullable=False),
            scope='Conditional on frozen TRAIN models/CAL thresholds; paired TEST-recording resampling.')
    return result


def _outcomes(groups):
    require(isinstance(groups, list), 'Recording outcomes must be a list')
    counts = {s: Counter() for s in GROUP_COUNTS}
    methods = {m: Counter() for m in METHOD_IDS}
    seen = set()
    for group in groups:
        group = _object(group, 'recording outcome')
        name, split = group.get('group_id'), group.get('split')
        require(isinstance(name, str) and name and name not in seen and split in GROUP_COUNTS,
                'Invalid/repeated recording outcome or split')
        seen.add(name); counts[split][_state(group.get('status'))] += 1
        cases = group.get('cases', [])
        require(isinstance(cases, list), 'Case outcomes must be a list')
        keys = set()
        for case in cases:
            case = _object(case, 'case outcome')
            method, world = case.get('method_id'), case.get('world')
            require(method in methods and world in ('IN', 'OUT') and (method, world) not in keys,
                    'Unknown or repeated method/world case')
            keys.add((method, world)); methods[method][_state(case.get('status'))] += 1
    for s, n in GROUP_COUNTS.items():
        require(sum(counts[s].values()) <= n, 'More recording outcomes than frozen slots')
        counts[s]['not_reported'] += n - sum(counts[s].values())
    return {'planned_recordings': sum(GROUP_COUNTS.values()), 'planned_by_split': dict(GROUP_COUNTS),
            'recording_status_by_split': {s: dict(sorted(c.items())) for s, c in counts.items()},
            'planned_native_cases': 1296, 'planned_recipient_streams': 1584,
            'method_world_status': {m: dict(planned=144, observed=sum(c.values()),
                                    unreported=144-sum(c.values()), statuses=dict(sorted(c.items()))) for m, c in methods.items()}}


def compact_report(report, *, input_sha256=None):
    """Project only explicitly approved aggregate fields; never emit private rows."""
    report = _object(report, 'private report')
    require(report.get('schema') == 'ump.urban-primary-report.v1', 'Unexpected primary report schema')
    assessment = report.get('analysis')
    assessment = {} if assessment is None else _object(assessment, 'analysis')
    require(assessment.get('schema', 'ump.urban-privacy-analysis.v1') == 'ump.urban-privacy-analysis.v1', 'Unexpected analysis schema')
    attacks = _object(assessment.get('attacks', {}), 'attack family')
    utilities = _object(assessment.get('utility', {}), 'utility family')
    require(set(attacks) <= set(METHOD_IDS) and set(utilities) <= set(METHOD_IDS), 'Unregistered comparator in report')
    controls = _object(assessment.get('controls', {}), 'controls')
    require(set(controls) <= set(CONTROLS), 'Unregistered control')
    methods = []
    for name, label in METHODS:
        family = _object(attacks.get(name, {}), 'representation family')
        require(set(family) <= set(REPRESENTATIONS), 'Unregistered representation')
        utility = _object(utilities.get(name, {}), 'world utility family')
        methods.append({'id': name, 'label': label,
                        'attacks': {representation: _attack(family.get(representation)) for representation in REPRESENTATIONS},
                        'utility': {world: _utility(utility.get(world)) for world in ('IN', 'OUT')}})
    checks = _object(assessment.get('negative_control_checks', {}), 'negative control checks')
    positive = _object(assessment.get('positive_control_check', {}), 'positive control check')
    gate = assessment.get('interpretation_gate', 'not_evaluated')
    require(gate in ('controls_pass', 'diagnose_controls_before_interpreting_lower_attack_success', 'not_evaluated'),
            'Unknown interpretation gate')
    status = _state(assessment.get('status', 'not_evaluated'))
    if status == 'complete' and any(m['attacks'][r]['status'] != 'evaluated' for m in methods for r in REPRESENTATIONS):
        status = 'incomplete_or_diagnostic'
    return {'schema': SCHEMA, 'analysis_status': status,
            'interpretation_gate': gate,
            'provenance': {'private_report_sha256': _hash(input_sha256),
                           'manifest_sha256': _hash(report.get('manifest_sha256')),
                           'implementation_sha256': _hash(report.get('implementation_sha256'))},
            'source_and_execution': _outcomes(report.get('group_outcomes', [])),
            'methods': methods, 'controls': {name: _attack(controls.get(name)) for name in CONTROLS},
            'negative_control_checks': {name: _state(_object(checks.get(name, {}), 'control check').get('status', 'unavailable'))
                                        for name in ('prior_only', 'auxiliary_only', 'no_output')},
            'positive_control_check': {key: value for key in ('status', 'in_contains_all_approved_sightings', 'OUT_removal_monotone', 'auc_above_chance')
                                       if (value := (_state(positive.get(key, 'unavailable')) if key == 'status'
                                                     else positive.get(key))) is not None and (key == 'status' or type(value) is bool)},
            'primary_contrast': _contrast(assessment.get('primary_contrast')),
            'scope': list(SCOPE)}


def _fmt(value, scale=1, places=3):
    return 'NA' if value is None else f'{value*scale:.{places}f}'


def _rate(metrics, name):
    if metrics is None:
        return 'NA'
    value = metrics.get(name)
    interval = metrics.get(name + '_interval')
    return _fmt(value) + (f" [{_fmt(interval['lower'])}, {_fmt(interval['upper'])}]" if interval else '')


def _mean(world, key):
    return world['macro_means'].get(key, {}).get('mean')


def markdown(public):
    require(public.get('schema') == SCHEMA, 'Unexpected public report schema')
    measured = any(m['attacks']['semantic111']['metrics'] is not None for m in public['methods'])
    lines = ['# P25.4 — Joint urban privacy and utility evidence', '',
             f"Analysis status: **{public['analysis_status']}**. Interpretation gate: **{public['interpretation_gate']}**.", '',
             ('These are held-out results for the frozen bounded episode-contribution attack.' if measured else
              '**No held-out privacy result is available in this report.** Unmeasured or incomplete methods remain NA.'), '',
             'The predeclared comparison has 24 TRAIN, 16 CAL and 32 TEST recordings, one matched IN/OUT target pair per recording.', '',
             '## Recording and execution outcomes', '', '| Split | Planned | Reported outcomes |', '|---|---:|---|']
    outcomes = public['source_and_execution']
    for s, n in GROUP_COUNTS.items():
        states = ', '.join(f'{state}: {count}' for state, count in outcomes['recording_status_by_split'][s].items() if count)
        lines.append(f'| {s} | {n} | {states} |')
    lines += ['', 'All planned cases stay in the denominator. No missing case is replaced by another seed.', '',
              '## Held-out attack assessment', '',
              '| Method | Full111 AUC | Scalar31 AUC | Full111 TPR [95% CI] | Full111 FPR [95% CI] | Complete TEST groups | Full111 status |',
              '|---|---:|---:|---|---|---:|---|']
    for method in public['methods']:
        full, scalar = (method['attacks'][name] for name in REPRESENTATIONS)
        fm, sm = full['metrics'], scalar['metrics']
        lines.append('| ' + ' | '.join((method['label'], _fmt(fm.get('roc_auc') if fm else None),
            _fmt(sm.get('roc_auc') if sm else None), _rate(fm, 'tpr'), _rate(fm, 'fpr'),
            f"{full['complete_test_groups']}/{full['expected_independent_test_groups']}", full['status'])) + ' |')
    lines += ['', 'TPR/FPR use the threshold locked on CAL with an empirical FPR cap of 0.1. This cap is not a population guarantee. '
              'AUC is reported without score-direction reversal. No individual-method AUC confidence interval was predeclared.', '',
              'The primary contrast is AUC(Adaptive Semantic First) − AUC(Regional static 20 m):', '']
    for name in REPRESENTATIONS:
        entry = public['primary_contrast']['representations'][name]
        if entry['status'] != 'evaluated':
            lines.append(f'- {name}: NA.')
        else:
            interval = entry['interval']
            ci = f"[{_fmt(interval[0])}, {_fmt(interval[1])}]" if interval else 'NA'
            lines.append(f"- {name}: {_fmt(entry['auc_difference'])}; paired 95% CI {ci}, N={entry['independent_groups']}.")
    lines += ['', 'A negative contrast means lower discrimination by this declared attack. It is not a universal privacy guarantee. '
              'The bootstrap is conditional on the fitted models and fixed CAL thresholds.', '', '## Controls', '',
              '| Control | AUC | TPR [95% CI] | FPR [95% CI] | Status |', '|---|---:|---|---|---|']
    for name, attack in public['controls'].items():
        metrics = attack['metrics']
        lines.append('| ' + ' | '.join((name, _fmt(metrics.get('roc_auc') if metrics else None),
                                      _rate(metrics, 'tpr'), _rate(metrics, 'fpr'), attack['status'])) + ' |')
    lines += ['', 'Pair-identical prior/auxiliary/no-output controls should have AUC 0.5. The unprotected control uses only exact approved '
              'time/position/cell matches; coincident background points can match in OUT. Diagnose failed controls before interpreting lower attack success.', '',
              '## World-specific TEST utility', '',
              '| Method | World | Available recordings | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell side (m) | Mean logical delay (ms) | Exact query coverage (%) | Estimated occupancy MAE | Estimated answered (%) |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for method in public['methods']:
        for world, utility in method['utility'].items():
            values = [method['label'], world, f"{utility['observed_recordings']}/{utility['expected_recordings']}",
                      _fmt(_mean(utility, 'retained_fraction'), 100), _fmt(_mean(utility, 'full_input_J'), 100),
                      _fmt(_mean(utility, 'retained_semantic_loss'), 100), _fmt(_mean(utility, 'mean_retained_cell_side_m')),
                      _fmt(_mean(utility, 'logical_seal_delay_ms.mean')),
                      _fmt(_mean(utility, 'query_exact.answered_query_coverage'), 100),
                      _fmt(_mean(utility, 'query_estimate.occupancy_mae')),
                      _fmt(_mean(utility, 'query_estimate.answered_query_coverage'), 100)]
            lines.append('| ' + ' | '.join(values) + ' |')
    lines += ['', 'Utility values are equal-recording macro means; JSON includes the available-recording denominator for each metric. '
              'J assigns unit loss to omitted observations plus retained taxonomy loss. Conditional MAE is separate from exact query coverage.', '',
              '## Interpretation limits', '']
    lines.extend('- ' + line for line in public['scope'])
    lines += ['', '## Provenance', '']
    lines.extend(f"- {key}: `{value or 'unavailable'}`" for key, value in public['provenance'].items())
    return '\n'.join(lines) + '\n'


def figures(public, output):
    """Write point/rate and utility figures; missing methods are labeled NA."""
    require(public.get('schema') == SCHEMA, 'Unexpected public report schema')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output = Path(output)
    require(output.is_dir(), 'Figure output must be an existing directory')
    methods = public['methods']; ys = list(range(len(methods)))
    labels = [m['label'] for m in methods]
    caption = ('Retrospective snapshot; episode-contribution attack. Thresholds fixed on CAL. '
               'TEST planned N=32; actual N in report. Missing/nonconverged results are NA; no live-delivery claim.')
    files = []

    def save(fig, name):
        fig.text(.01, .012, caption, fontsize=8)
        fig.tight_layout(rect=(0, .12, 1, .97))
        for extension in ('png', 'svg'):
            path = output / (name + '.' + extension)
            require(not path.exists(), 'Refuse to overwrite figure')
            fig.savefig(path, dpi=170, metadata={'Creator': 'UMP-Simulator P25.4 aggregate report'})
            files.append(path.name)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 6.5), sharey=True)
    for index, method in enumerate(methods):
        for representation, marker, offset, color in (('semantic111', 'o', -.12, '#2669a1'), ('scalar31', 'x', .12, '#c66a16')):
            metrics = method['attacks'][representation]['metrics']
            if metrics is not None and metrics['roc_auc'] is not None:
                axes[0].scatter(metrics['roc_auc'], index + offset, marker=marker, color=color,
                                label=representation if index == 0 else None, zorder=3)
            else:
                axes[0].text(.015, index + offset, 'NA', va='center', fontsize=7, color=color)
        metrics = method['attacks']['semantic111']['metrics']
        for key, offset, color in (('tpr', -.12, '#2b8a63'), ('fpr', .12, '#b4413d')):
            if metrics is None or metrics[key] is None:
                axes[1].text(.015, index + offset, 'NA', va='center', fontsize=7, color=color)
                continue
            ci = metrics.get(key + '_interval')
            axes[1].scatter(metrics[key], index + offset, color=color, s=24,
                            label=key.upper() if index == 0 else None, zorder=3)
            if ci is not None:
                axes[1].hlines(index + offset, ci['lower'], ci['upper'], color=color, linewidth=1.2)
    axes[0].axvline(.5, color='#666666', linestyle='--', linewidth=1)
    axes[0].set(title='Held-out ROC-AUC (point estimates)', xlabel='ROC-AUC')
    axes[1].set(title='Full111 operating rates (exact 95% intervals)', xlabel='Rate')
    for ax in axes:
        ax.set_xlim(-.015, 1.015); ax.set_yticks(ys, labels); ax.grid(axis='x', alpha=.18)
        handles, names = ax.get_legend_handles_labels()
        if handles: ax.legend(handles, names, fontsize=8, loc='lower right')
    from matplotlib.lines import Line2D
    axes[0].legend(handles=[Line2D([], [], linestyle='', marker='o', color='#2669a1', label='Full111'),
                           Line2D([], [], linestyle='', marker='x', color='#c66a16', label='Scalar31')],
                   fontsize=8, loc='upper center', bbox_to_anchor=(.5, -.14), ncol=2)
    axes[1].legend(handles=[Line2D([], [], linestyle='-', marker='o', color='#2b8a63', label='TPR'),
                           Line2D([], [], linestyle='-', marker='o', color='#b4413d', label='FPR')],
                   fontsize=8, loc='upper center', bbox_to_anchor=(.5, -.14), ncol=2)
    axes[0].set_ylim(len(methods)-.5, -.5)
    save(fig, 'urban-primary-attack')

    fig, axes = plt.subplots(1, 4, figsize=(16, 6.5), sharey=True)
    specs = (('retained_fraction', 100, 'Retained input (%)'), ('full_input_J', 100, 'Full-input J (%)'),
             ('mean_retained_cell_side_m', 1, 'Mean retained cell side (m)'),
             ('logical_seal_delay_ms.mean', 1, 'Mean logical seal delay (ms)'))
    for ax, (key, scale, title) in zip(axes, specs):
        for i, method in enumerate(methods):
            value = _mean(method['utility']['IN'], key)
            if value is None:
                ax.text(.015, i, 'NA', transform=ax.get_yaxis_transform(), va='center', fontsize=7)
            else:
                color = '#c56627' if method['id'] == 'adaptive_semantic_first' else '#4677a4'
                ax.scatter(value * scale, i, color=color, s=30, zorder=3)
        ax.set_title(title, fontsize=10); ax.set_yticks(ys, labels); ax.grid(axis='x', alpha=.18)
        ax.set_xlim(left=0)
    axes[0].set_ylim(len(methods)-.5, -.5)
    fig.suptitle('TEST utility: IN world, equal recording weights', fontsize=12)
    save(fig, 'urban-primary-utility')
    return files


def export(report_path, output, *, make_figures=True):
    report_path, output = Path(report_path), Path(output)
    require(report_path.is_file() and report_path.stat().st_size <= 2*1024**3, 'Expected bounded private report file')
    payload = report_path.read_bytes()
    private = json.loads(payload, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON input')))
    public = compact_report(private, input_sha256=hashlib.sha256(payload).hexdigest())
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'summary.json').open('x') as stream:
        json.dump(public, stream, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')
    with (output / 'report.md').open('x') as stream:
        stream.write(markdown(public))
    generated = figures(public, output) if make_figures else []
    with (output / 'artifact-receipt.json').open('x') as stream:
        json.dump({'schema': 'ump.urban-primary-public-artifacts.v1',
                   'source_report_sha256': hashlib.sha256(payload).hexdigest(),
                   'artifacts_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [output/'summary.json', output/'report.md', *(output/name for name in generated)]}},
                  stream, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')
    return public


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-figures', action='store_true')
    args = parser.parse_args(argv)
    result = export(args.report, args.output, make_figures=not args.no_figures)
    print(json.dumps({'status': result['analysis_status'], 'methods': len(result['methods']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
