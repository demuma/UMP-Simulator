#!/usr/bin/env python3
"""Aggregate-only report for observed track contributions within a fixed window.

This presentation layer accepts authenticated private study reports. It neither
loads source/model artifacts from their references nor fits, calibrates, selects
targets, or changes scientific estimates. Numeric/metric/outcome validation is
shared with the unchanged strict primary reporter. Scope, provenance, quality,
Markdown and figure labels are explicitly the observed-track-window profile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import report_urban_privacy_primary as strict

INPUT_SCHEMA = 'ump.urban-track-window-report.v1'
SCHEMA = 'ump.urban-track-window-public-report.v1'
ARTIFACT_SCHEMA = 'ump.urban-track-window-public-artifacts.v1'
PROFILE = 'observed_track_window_v1'
HORIZON_MS = 300000
GROUP_COUNTS = dict(strict.GROUP_COUNTS)
METHODS = strict.METHODS
REPRESENTATIONS = strict.REPRESENTATIONS
QUALITY_FIELDS = (
    'planned_sources', 'verified_sources', 'quality_reports',
    'sources_with_active_at_horizon', 'sources_with_pending_at_horizon',
    'sources_with_reported_stalls',
)
SCOPE = (
    'Protected secret: inclusion of all observed contributions of one operational track within [0,300 s), including valid censored/active tracks; not a full journey, person identity, physical presence or all visits.',
    'Source validation profile: observed_track_window_v1. Full clock, hashes, source law, recorded-visible-interval agreement and physical/data validity remain hard gates. Scheduled journey/visit completion and reported stalls are separate quality diagnostics.',
    'Movement quality does not filter enrollment. A pathology or oscillation is not a privacy benefit; interpret measured risk and utility for the recorded source distribution.',
    'Targets require at least two observations; all short/unselected traces remain input. Auxiliary knowledge is the unchanged exact quarter-count sample with upward rounding, identical in IN and OUT.',
    'Recipient availability: one retrospective final snapshot at H=300 s. Logical sealing delay is not measured live delivery latency; mechanism EOF does not manufacture a road-user exit.',
    'Same local400 hard requirements and suppression OFF for every comparator/world; operational track support is distinct from empirical privacy.',
    'Models and scaling use TRAIN only; operating thresholds use CAL only. No TEST-dependent score-direction flip, tuning or comparator selection.',
    'Rate intervals are two-sided exact 95% Clopper-Pearson. Primary AUC-difference interval is a 1000-replicate paired TEST-recording bootstrap conditional on fixed fitted models.',
    'Scalar31 is a joint representation ablation removing semantic and availability coordinates; it does not isolate semantic leakage.',
    'Utility macro means weight recordings equally and use each world\'s own sampled input. Conditional occupancy MAE must be read with answered/scored coverage; unknown output is not zero.',
    'Source artifacts, old status and original TRAIN/CAL roles are preserved under the new binding. A former exposed TEST source/model is not new held-out evidence.',
    'No universal privacy guarantee, population FPR bound, person-level guarantee, navigation-liveness guarantee or real-time certification follows from these measurements.',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False,
                      ensure_ascii=True).encode('ascii')


def _reference_hash(value, label):
    if value is None:
        return None
    value = strict._object(value, label)
    # The caller authenticates the reference. Never open or publish its path.
    return strict._hash(value.get('sha256'))


def _quality(value):
    value = strict._object(value, 'source quality')
    require(value.get('source_validation_profile') == PROFILE,
            'Source quality belongs to another validation profile')
    require(value.get('quality_filters_enrollment') is False,
            'Movement quality must not filter window enrollment')
    by_split = strict._object(value.get('by_split', {}), 'source quality split summaries')
    require(set(by_split) <= set(GROUP_COUNTS), 'Unregistered source quality split')
    result = {}
    for split, planned in GROUP_COUNTS.items():
        entry = strict._object(by_split.get(split, {}), 'source quality summary')
        counts = {key: strict._integer(entry.get(key), 'source quality ' + key)
                  for key in QUALITY_FIELDS}
        require(counts['planned_sources'] in (None, planned), 'Quality plan differs from frozen source slots')
        require(all(count is None or count <= planned for count in counts.values()),
                'Source quality count exceeds planned slots')
        denominator = counts['quality_reports']
        if denominator is not None:
            require(all(counts[key] is None or counts[key] <= denominator for key in
                        ('sources_with_active_at_horizon', 'sources_with_pending_at_horizon',
                         'sources_with_reported_stalls')),
                    'Quality condition count exceeds its reported denominator')
        result[split] = counts
    known = sum(count is not None for entry in result.values() for count in entry.values())
    availability = ('unavailable' if known == 0 else
                    'reported' if known == len(GROUP_COUNTS) * len(QUALITY_FIELDS) else 'partial')
    return {'source_validation_profile': PROFILE, 'quality_filters_enrollment': False,
            'availability': availability, 'by_split': result,
            'count_unit': 'sources, not tracks or observation contributions',
            'missing_count_semantics': 'Unknown counts are null/NA, never inferred zero.',
            'quality_scope': 'Diagnostic reporting only; active/pending/stall counts do not establish normal movement, completed journeys or privacy protection.'}


def compact_report(report, *, input_sha256=None):
    """Project approved aggregate fields only; source references remain unopened."""
    report = strict._object(report, 'private track-window report')
    require(report.get('schema') == INPUT_SCHEMA, 'Unexpected track-window report schema')
    require(report.get('source_validation_profile') == PROFILE, 'Unexpected source validation profile')
    evaluation_id = report.get('evaluation_id')
    require(isinstance(evaluation_id, str) and 0 < len(evaluation_id) <= 256,
            'Expected bounded private evaluation identity')
    quality = _quality(report.get('source_quality'))
    split_audit = report.get('source_split_audit')
    if split_audit is not None:
        split_audit = strict._object(split_audit, 'source split audit')
    # Only the existing numeric/metric/outcome projector sees this minimal
    # adapter. Its legacy scope/provenance/schema are deliberately not copied.
    numeric = strict.compact_report({
        'schema': 'ump.urban-primary-report.v1',
        'group_outcomes': report.get('group_outcomes', []),
        'analysis': report.get('analysis'),
    })
    result = {key: numeric[key] for key in (
        'analysis_status', 'interpretation_gate', 'source_and_execution',
        'methods', 'controls', 'negative_control_checks', 'positive_control_check',
        'primary_contrast')}
    result.update({
        'schema': SCHEMA, 'source_validation_profile': PROFILE,
        'protected_unit': 'all_observed_contributions_of_one_operational_track_within_fixed_300s',
        'horizon_ms': HORIZON_MS,
        'provenance': {
            'private_report_sha256': strict._hash(input_sha256),
            'private_evaluation_id_sha256': hashlib.sha256(evaluation_id.encode('utf-8')).hexdigest(),
            'dataset_manifest_sha256': strict._hash(report.get('dataset_manifest_sha256')),
            'evaluation_manifest_sha256': strict._hash(report.get('evaluation_manifest_sha256')),
            'source_profile_sha256': strict._hash(report.get('source_profile_sha256')),
            'import_ledger_sha256': _reference_hash(report.get('import_ledger'), 'import ledger'),
            'source_protocol_sha256': _reference_hash(report.get('source_protocol'), 'source protocol'),
            'implementation_sha256': strict._hash(report.get('implementation_sha256')),
            'source_split_audit_sha256': (hashlib.sha256(_canonical(split_audit)).hexdigest()
                                           if split_audit is not None else None),
        },
        'source_split_audit_status': strict._state(split_audit.get('status', 'unavailable'))
                                     if split_audit is not None else 'unavailable',
        'source_quality': quality,
        'scope': list(SCOPE),
    })
    return result


def _public(public):
    require(isinstance(public, dict) and public.get('schema') == SCHEMA
            and public.get('source_validation_profile') == PROFILE
            and public.get('horizon_ms') == HORIZON_MS,
            'Unexpected public track-window report profile')
    return public


def _count(value):
    return 'NA' if value is None else str(value)


def markdown(public):
    public = _public(public)
    measured = any(method['attacks'][representation]['metrics'] is not None
                   for method in public['methods'] for representation in REPRESENTATIONS)
    lines = ['# Fixed-window track contributions: joint privacy and utility evidence', '',
             f"Analysis status: **{public['analysis_status']}**. Interpretation gate: **{public['interpretation_gate']}**.", '',
             ('These are held-out results for the declared observed-track-window contribution-membership attack.' if measured else
              '**No held-out privacy result is available in this report.** Unmeasured or incomplete methods remain NA.'), '',
             'Protected unit: all observed contributions of one operational track within [0,300 s), including valid active/censored tracks. '
             'The secret concerns contribution inclusion, not a completed journey, physical presence or a person.', '',
             'The declared comparison has 24 TRAIN, 16 CAL and 32 TEST source recordings, one matched IN/OUT target pair per source. '
             'Source quality is reported separately and does not filter enrollment.', '',
             '## Source and execution outcomes', '', '| Split | Planned | Reported outcomes |', '|---|---:|---|']
    for split, planned in GROUP_COUNTS.items():
        states = ', '.join(f'{state}: {count}' for state, count in
                           public['source_and_execution']['recording_status_by_split'][split].items() if count)
        lines.append(f'| {split} | {planned} | {states} |')
    lines += ['', 'All planned cases stay in the denominator. No missing case is replaced by another seed.', '',
              '## Movement quality, separate from validity and membership', '',
              f"Quality-summary availability: **{public['source_quality']['availability']}**. Profile: `{PROFILE}`. "
              'Counts below are sources, not tracks. Unknown counts remain NA.', '',
              '| Split | Planned sources | Window-verified sources | Quality reports | Sources with active tracks at H | Sources with pending tracks at H | Sources with reported stalls |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for split, quality in public['source_quality']['by_split'].items():
        lines.append('| ' + ' | '.join([split] + [_count(quality[key]) for key in QUALITY_FIELDS]) + ' |')
    lines += ['', 'Full-clock/provenance, GT-visible-interval agreement and physical/data checks remain hard gates. '
              'Journey/visit completion and reported stalls are quality diagnostics. A pathology is not a privacy benefit; '
              'no trace is dropped or given an artificial EOF exit to improve these results.', '',
              '## Held-out attack assessment', '',
              '| Method | Full111 AUC | Scalar31 AUC | Full111 TPR [95% CI] | Full111 FPR [95% CI] | Complete TEST groups | Full111 status |',
              '|---|---:|---:|---|---|---:|---|']
    for method in public['methods']:
        full, scalar = (method['attacks'][name] for name in REPRESENTATIONS)
        fm, sm = full['metrics'], scalar['metrics']
        lines.append('| ' + ' | '.join((method['label'], strict._fmt(fm.get('roc_auc') if fm else None),
            strict._fmt(sm.get('roc_auc') if sm else None), strict._rate(fm, 'tpr'), strict._rate(fm, 'fpr'),
            f"{full['complete_test_groups']}/{full['expected_independent_test_groups']}", full['status'])) + ' |')
    lines += ['', 'TPR/FPR use the threshold locked on CAL with an empirical FPR cap of 0.1. This cap is not a population guarantee. '
              'AUC is reported without score-direction reversal. No individual-method AUC confidence interval was predeclared.', '',
              'Primary contrast: AUC(Adaptive Semantic First) − AUC(Regional static 20 m).', '']
    for representation in REPRESENTATIONS:
        entry = public['primary_contrast']['representations'][representation]
        if entry['status'] != 'evaluated':
            lines.append(f'- {representation}: NA.')
        else:
            interval = entry['interval']
            ci = f"[{strict._fmt(interval[0])}, {strict._fmt(interval[1])}]" if interval else 'NA'
            lines.append(f"- {representation}: {strict._fmt(entry['auc_difference'])}; paired 95% CI {ci}, N={entry['independent_groups']}.")
    lines += ['', 'A negative contrast means lower discrimination by this declared attack, not universal protection. '
              'Bootstrap uncertainty is conditional on fitted models and fixed CAL thresholds.', '',
              '## Controls', '', '| Control | AUC | TPR [95% CI] | FPR [95% CI] | Status |', '|---|---:|---|---|---|']
    for name, attack in public['controls'].items():
        metrics = attack['metrics']
        lines.append('| ' + ' | '.join((name, strict._fmt(metrics.get('roc_auc') if metrics else None),
            strict._rate(metrics, 'tpr'), strict._rate(metrics, 'fpr'), attack['status'])) + ' |')
    lines += ['', 'Pair-identical prior/auxiliary/no-output controls should have AUC 0.5. The unprotected control uses exact '
              'approved time/position/cell matches; background points can also match in OUT. Diagnose failed controls before '
              'interpreting lower attack success.', '', '## World-specific TEST utility', '',
              '| Method | World | Available recordings | Retained (%) | Full-input J (%) | Retained semantic loss (%) | Mean cell side (m) | Mean logical delay (ms) | Exact query coverage (%) | Estimated occupancy MAE | Estimated answered (%) |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for method in public['methods']:
        for world, utility in method['utility'].items():
            values = [method['label'], world, f"{utility['observed_recordings']}/{utility['expected_recordings']}",
                strict._fmt(strict._mean(utility, 'retained_fraction'), 100),
                strict._fmt(strict._mean(utility, 'full_input_J'), 100),
                strict._fmt(strict._mean(utility, 'retained_semantic_loss'), 100),
                strict._fmt(strict._mean(utility, 'mean_retained_cell_side_m')),
                strict._fmt(strict._mean(utility, 'logical_seal_delay_ms.mean')),
                strict._fmt(strict._mean(utility, 'query_exact.answered_query_coverage'), 100),
                strict._fmt(strict._mean(utility, 'query_estimate.occupancy_mae')),
                strict._fmt(strict._mean(utility, 'query_estimate.answered_query_coverage'), 100)]
            lines.append('| ' + ' | '.join(values) + ' |')
    lines += ['', 'Utility values are equal-recording macro means; JSON retains the available-recording denominator for each metric. '
              'J assigns unit loss to omitted observations plus retained taxonomy loss. Conditional MAE must be read with query coverage.', '',
              '## Interpretation limits', '']
    lines.extend('- ' + line for line in public['scope'])
    lines += ['', '## Provenance', '',
              f"Source split audit status: **{public['source_split_audit_status']}**. Private references are represented only by hashes.", '']
    lines.extend(f"- {key}: `{value or 'unavailable'}`" for key, value in public['provenance'].items())
    return '\n'.join(lines) + '\n'


def figures(public, output):
    """Write fixed-profile scientific figures; preserve every method and its NA."""
    public = _public(public)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    output = Path(output)
    require(output.is_dir(), 'Figure output must be an existing directory')
    methods = public['methods']
    labels = [method['label'] for method in methods]
    ys = list(range(len(methods)))
    caption = ('All observed contributions of one track within H=300 s; final snapshot; TEST planned N=32. '
               'Missing results are NA.\nMovement quality is reported separately; no full-journey, person-level or real-time guarantee.')
    generated = []

    def save(fig, stem):
        fig.text(.01, .012, caption, fontsize=8)
        fig.tight_layout(rect=(0, .13, 1, .96))
        for extension in ('png', 'svg'):
            path = output / (stem + '.' + extension)
            require(not path.exists(), 'Refuse to overwrite figure')
            fig.savefig(path, dpi=170, metadata={'Creator': 'UMP-Simulator observed track-window aggregate report'})
            generated.append(path.name)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 6.5), sharey=True)
    for index, method in enumerate(methods):
        for representation, marker, offset, color in (('semantic111', 'o', -.12, '#2669a1'),
                                                       ('scalar31', 'x', .12, '#c66a16')):
            metrics = method['attacks'][representation]['metrics']
            if metrics is None or metrics['roc_auc'] is None:
                axes[0].text(.015, index + offset, 'NA', va='center', fontsize=7, color=color)
            else:
                axes[0].scatter(metrics['roc_auc'], index + offset, marker=marker, color=color, zorder=3)
        metrics = method['attacks']['semantic111']['metrics']
        for key, offset, color in (('tpr', -.12, '#2b8a63'), ('fpr', .12, '#b4413d')):
            if metrics is None or metrics[key] is None:
                axes[1].text(.015, index + offset, 'NA', va='center', fontsize=7, color=color)
            else:
                axes[1].scatter(metrics[key], index + offset, color=color, s=24, zorder=3)
                interval = metrics.get(key + '_interval')
                if interval is not None:
                    axes[1].hlines(index + offset, interval['lower'], interval['upper'], color=color, linewidth=1.2)
    axes[0].axvline(.5, color='#666666', linestyle='--', linewidth=1)
    axes[0].set(title='Track-window membership: held-out ROC-AUC', xlabel='ROC-AUC')
    axes[1].set(title='Full111 operating rates (exact 95% intervals)', xlabel='Rate')
    for ax in axes:
        ax.set_xlim(-.015, 1.015)
        ax.set_yticks(ys, labels)
        ax.grid(axis='x', alpha=.18)
    axes[0].legend(handles=[Line2D([], [], linestyle='', marker='o', color='#2669a1', label='Full111'),
                           Line2D([], [], linestyle='', marker='x', color='#c66a16', label='Scalar31')],
                   fontsize=8, loc='upper center', bbox_to_anchor=(.5, -.12), ncol=2)
    axes[1].legend(handles=[Line2D([], [], linestyle='-', marker='o', color='#2b8a63', label='TPR'),
                           Line2D([], [], linestyle='-', marker='o', color='#b4413d', label='FPR')],
                   fontsize=8, loc='upper center', bbox_to_anchor=(.5, -.12), ncol=2)
    axes[0].set_ylim(len(methods) - .5, -.5)
    save(fig, 'urban-track-window-attack')

    fig, axes = plt.subplots(1, 4, figsize=(16, 6.5), sharey=True)
    specs = (('retained_fraction', 100, 'Retained input (%)'),
             ('full_input_J', 100, 'Full-input J (%)'),
             ('mean_retained_cell_side_m', 1, 'Mean retained cell side (m)'),
             ('logical_seal_delay_ms.mean', 1, 'Mean logical seal delay (ms)'))
    for ax, (key, scale, title) in zip(axes, specs):
        for index, method in enumerate(methods):
            value = strict._mean(method['utility']['IN'], key)
            if value is None:
                ax.text(.015, index, 'NA', transform=ax.get_yaxis_transform(), va='center', fontsize=7)
            else:
                color = '#c56627' if method['id'] == 'adaptive_semantic_first' else '#4677a4'
                ax.scatter(value * scale, index, color=color, s=30, zorder=3)
        ax.set_title(title, fontsize=10)
        ax.set_yticks(ys, labels)
        ax.grid(axis='x', alpha=.18)
        ax.set_xlim(left=0)
    axes[0].set_ylim(len(methods) - .5, -.5)
    fig.suptitle('Track-window TEST utility: IN world, equal recording weights', fontsize=12)
    save(fig, 'urban-track-window-utility')
    return generated


def export(report_path, output, *, make_figures=True):
    report_path, output = Path(report_path), Path(output)
    require(report_path.is_file() and report_path.stat().st_size <= 2 * 1024**3,
            'Expected bounded private report file')
    payload = report_path.read_bytes()
    report = json.loads(payload, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON input')))
    public = compact_report(report, input_sha256=hashlib.sha256(payload).hexdigest())
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'summary.json').open('x') as stream:
        json.dump(public, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    with (output / 'report.md').open('x') as stream:
        stream.write(markdown(public))
    generated = figures(public, output) if make_figures else []
    files = [output / 'summary.json', output / 'report.md', *(output / name for name in generated)]
    with (output / 'artifact-receipt.json').open('x') as stream:
        json.dump({'schema': ARTIFACT_SCHEMA, 'source_validation_profile': PROFILE,
                   'source_report_sha256': hashlib.sha256(payload).hexdigest(),
                   'artifacts_sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}},
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
    # CLI output contains no caller-provided identity or local filesystem path.
    print(json.dumps({'schema': SCHEMA, 'source_validation_profile': PROFILE,
                      'status': public['analysis_status'], 'methods': len(public['methods'])}))


if __name__ == '__main__':
    main()
