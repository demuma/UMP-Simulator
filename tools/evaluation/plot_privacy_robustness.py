#!/usr/bin/env python3
"""Export separate robustness-cohort membership and utility panels as PNG/SVG."""
import argparse
import io
import json
import math
from pathlib import Path

METHODS = [
    ('fixed_20m_1000ms', 'Fixed 20 m / 1 s'),
    ('common_temporal_first', 'Common / Temporal First'),
    ('local_temporal_first', 'Local / Temporal First'),
    ('common_spatial_first', 'Common / Spatial First'),
    ('local_spatial_first', 'Local / Spatial First'),
    ('control_exact_count', 'Unprotected exact-count control'),
    ('control_no_output', 'No-output control'),
]
COHORTS = [('base', 'Base test'), ('background_density_shift', 'Background-density shift')]
COMBINATIONS = [
    ('logistic', 'exact_25', 'Logistic / exact 25%', '#2463a2', 'o'),
    ('logistic', 'noisy_25', 'Logistic / uncertain 25%', '#2463a2', 's'),
    ('hist_gradient_boosting', 'exact_25', 'Boosted trees / exact 25%', '#b85e20', 'o'),
    ('hist_gradient_boosting', 'noisy_25', 'Boosted trees / uncertain 25%', '#b85e20', 's'),
]


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + ' must be an object')
    return value


def _number(value, label, low=0, high=1):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(label + ' must be finite and within its declared bounds')
    return value


def _integer(value, label, low=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise ValueError(label + ' must be an integer at least ' + str(low))
    return value


def prepare(report):
    """Require the full frozen comparison; never silently omit a missing attack."""
    report = _object(report, 'report')
    if report.get('schema') != 'ump.privacy-robustness-report.v1' or report.get('status') != 'complete':
        raise ValueError('A complete privacy robustness report is required')
    if report.get('test_cohorts_independent') is not True or report.get('membership_prior') != .5:
        raise ValueError('Independent cohorts and the balanced membership evaluation prior are required')
    if _object(report.get('independent_validation'), 'independent validation').get('all_valid') is not True:
        raise ValueError('Successful independent validation is required')
    attacks = report.get('attacks')
    if not isinstance(attacks, list):
        raise ValueError('attacks must be an array')
    selected = {}
    names = {name for name, _ in METHODS}
    combinations = {(family, profile) for family, profile, *_ in COMBINATIONS}
    for attack in attacks:
        attack = _object(attack, 'attack')
        key = (attack.get('variant'), attack.get('attack_family'), attack.get('knowledge_profile'))
        if key[0] not in names or key[1:] not in combinations:
            raise ValueError('Unknown attack mechanism, family or knowledge profile')
        if key in selected:
            raise ValueError('Duplicate attack projection')
        assessments = _object(attack.get('test_by_distribution'), 'test cohorts')
        if set(assessments) != {name for name, _ in COHORTS}:
            raise ValueError('Both separate test cohorts are required for every attack')
        selected[key] = assessments
    if len(selected) != len(METHODS) * len(COMBINATIONS):
        raise ValueError('Missing attack for the complete seven-mechanism comparison')
    utilities = _object(report.get('utility_by_distribution'), 'utility cohorts')
    if set(utilities) != {name for name, _ in COHORTS}:
        raise ValueError('Both separate utility cohorts are required')
    cohorts = []
    for distribution, label in COHORTS:
        counts, rows = set(), []
        utility_cohort = _object(utilities[distribution], 'cohort utility')
        if set(utility_cohort) != names:
            raise ValueError('All seven utility mechanisms are required without duplicates')
        for name, method_label in METHODS:
            projections = []
            for family, profile, combo_label, color, marker in COMBINATIONS:
                assessment = _object(selected[(name, family, profile)][distribution], 'test assessment')
                groups = _integer(assessment.get('test_groups'), 'test groups', 2)
                counts.add(groups)
                auc = _number(_object(assessment.get('test'), 'test metrics').get('roc_auc'), 'ROC-AUC')
                uncertainty = _object(assessment.get('uncertainty'), 'test uncertainty')
                if uncertainty.get('groups') != groups or uncertainty.get('confidence') != .95:
                    raise ValueError('The 95% conditional interval must use the stated test groups')
                _integer(uncertainty.get('repeats'), 'bootstrap repeats', 1)
                interval = _object(uncertainty.get('intervals'), 'confidence intervals').get('roc_auc')
                if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                    raise ValueError('AUC bootstrap interval is required')
                low, high = [_number(value, 'AUC interval') for value in interval]
                if low > high:
                    raise ValueError('AUC interval endpoints are reversed')
                projections.append(dict(family=family, profile=profile, label=combo_label,
                    color=color, marker=marker, auc=auc, low=low, high=high))
            utility = _object(utility_cohort[name], 'utility')
            worlds = _integer(utility.get('case_worlds'), 'case worlds', 4)
            reference = _integer(utility.get('reference_queries'), 'reference queries', 1)
            answered = _integer(utility.get('answered_queries'), 'answered queries')
            inputs = _integer(utility.get('input_contributions'), 'input contributions', 1)
            retained = _integer(utility.get('released_contributions'), 'released contributions')
            coverage = _number(utility.get('answered_query_coverage'), 'answered query coverage')
            retention = _number(utility.get('contribution_retention'), 'contribution retention')
            if answered > reference or retained > inputs or not math.isclose(coverage, answered / reference, rel_tol=1e-12, abs_tol=1e-12) or not math.isclose(retention, retained / inputs, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError('Utility fractions must match their fixed-query/contribution denominators')
            rows.append(dict(name=name, label=method_label, attacks=projections,
                             coverage=coverage, retention=retention, case_worlds=worlds))
        if len(counts) != 1:
            raise ValueError('Attacks within one cohort must use the same independent test group count')
        groups = counts.pop()
        if any(row['case_worlds'] != 2 * groups for row in rows):
            raise ValueError('Utility must use both IN/OUT worlds of the same test cohort')
        cohorts.append(dict(distribution=distribution, label=label, test_groups=groups, rows=rows))
    return cohorts


def export(report, output):
    """Write exclusive deterministic exports; remove partial files on failure."""
    cohorts = prepare(report)
    output = Path(output)
    destinations = [output.with_suffix(suffix) for suffix in ('.png', '.svg')]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise ValueError('Output files already exist')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    created = []
    with plt.rc_context({'svg.hashsalt': 'ump-privacy-robustness-v1', 'svg.fonttype': 'none',
                         'font.family': 'DejaVu Sans', 'font.size': 10}):
        figure, axes = plt.subplots(2, 3, figsize=(17, 11), sharey='row',
                                    gridspec_kw={'width_ratios': [1.65, 1, 1]})
        try:
            for cohort_index, cohort in enumerate(cohorts):
                row_axes = axes[cohort_index]
                for position, row in enumerate(cohort['rows']):
                    for index, attack in enumerate(row['attacks']):
                        y = position + (index - 1.5) * .16
                        row_axes[0].hlines(y, attack['low'], attack['high'], color=attack['color'], linewidth=1.25)
                        row_axes[0].plot(attack['auc'], y, marker=attack['marker'], linestyle='none',
                            color=attack['color'], markersize=4.3, markeredgewidth=.8,
                            markerfacecolor=attack['color'] if attack['profile']=='exact_25' else 'white',
                            label=attack['label'] if position==0 and cohort_index==0 else None)
                    row_axes[1].plot(100 * row['coverage'], position, 'o', color='#333333', markersize=5)
                    row_axes[2].plot(100 * row['retention'], position, 'o', color='#333333', markersize=5)
                row_axes[0].set_yticks(range(len(METHODS)), [row['label'] for row in cohort['rows']])
                row_axes[0].set_ylim(len(METHODS)-.5, -.5)
                row_axes[0].set_xlim(-.02, 1.02)
                row_axes[0].axvline(.5, color='#888888', linestyle='--', linewidth=1)
                row_axes[0].set_title(f"{cohort['label']}: n = {cohort['test_groups']} independent paired groups", loc='left', fontsize=11)
                row_axes[0].set_xlabel('Held-out membership ROC-AUC (95% conditional interval)')
                row_axes[1].set_title('Retrospective occupancy availability', fontsize=11)
                row_axes[1].set_xlabel('Answered 10 m / 1 s queries (%)')
                row_axes[2].set_title('Source-contribution retention', fontsize=11)
                row_axes[2].set_xlabel('Retained observations (%)')
                for axis in row_axes[1:]:
                    axis.set_xlim(-2, 102)
                for axis in row_axes:
                    axis.grid(axis='x', alpha=.18)
                    axis.spines[['top', 'right', 'left']].set_visible(False)
                    axis.tick_params(axis='y', length=0)
            handles, labels = axes[0, 0].get_legend_handles_labels()
            figure.legend(handles, labels, loc='upper center', bbox_to_anchor=(.59, .945), ncol=2,
                          frameon=False, fontsize=10, columnspacing=2.5)
            figure.suptitle('Synthetic source-contribution membership: longer trajectories and uncertain knowledge',
                            x=.56, y=.982, fontsize=15)
            figure.text(.58, .035,
                'Separate independent base and density-shift test cohorts; no pooling and no cross-cohort pairing. Balanced IN/OUT evaluation prior.\n'
                'All attacks use the same 25% of candidate points; uncertain knowledge adds 2 m spatial / 200 ms temporal uncertainty.\n'
                'Intervals condition on frozen models; thresholds were calibrated on base groups only. Utility uses both worlds; absent public support is unknown.\n'
                'Exact-count control bypasses policy. No-output control preserves no utility. Attack failure establishes no universal privacy guarantee.',
                ha='center', va='bottom', fontsize=9, linespacing=1.55)
            figure.subplots_adjust(left=.245, right=.98, top=.86, bottom=.17, hspace=.52, wspace=.23)
            output.parent.mkdir(parents=True, exist_ok=True)
            for path in destinations:
                buffer = io.BytesIO()
                metadata = {'Date': None, 'Creator': 'UMP privacy robustness'} if path.suffix=='.svg' else {'Software': 'UMP privacy robustness'}
                figure.savefig(buffer, format=path.suffix[1:], dpi=180, metadata=metadata)
                payload = buffer.getvalue()
                if path.suffix=='.svg':
                    payload = b'\n'.join(line.rstrip() for line in payload.splitlines()) + b'\n'
                with path.open('xb') as destination:
                    created.append(path)
                    destination.write(payload)
        except BaseException:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        finally:
            plt.close(figure)
    return destinations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = export(json.loads(args.report.read_text()), args.output)
    print('Exported ' + ', '.join(map(str, paths)))


if __name__ == '__main__':
    main()
