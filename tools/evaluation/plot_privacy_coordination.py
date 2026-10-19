#!/usr/bin/env python3
"""Export the scoped synthetic membership/utility comparison as PNG and SVG."""
import argparse
import io
import json
import math
from pathlib import Path

METHODS = [('fixed_10m_400ms', 'Fixed 10 m / 400 ms'),
           ('fixed_10m_1000ms', 'Fixed 10 m / 1000 ms'),
           ('fixed_20m_400ms', 'Fixed 20 m / 400 ms'),
           ('fixed_20m_1000ms', 'Fixed 20 m / 1000 ms'), ('spatial', 'Spatial only'),
           ('common_temporal_first', 'Common / Temporal First'),
           ('local_temporal_first', 'Local / Temporal First'),
           ('common_spatial_first', 'Common / Spatial First'),
           ('local_spatial_first', 'Local / Spatial First'),
           ('control_exact_count', 'Unprotected exact-count control'),
           ('control_no_output', 'No-output control')]


def number(value, label, low=0, high=1):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(label + ' must be a finite value within the declared bounds')
    return value


def prepare(report, fractions=(.25, 1.0)):
    if report.get('schema') != 'ump.empirical-privacy-report.v1' or report.get('status') != 'complete' or report.get('coordination_study') is not True:
        raise ValueError('A complete coordination privacy report is required')
    if not fractions or len(set(fractions)) != len(fractions):
        raise ValueError('Knowledge fractions must be nonempty and unique')
    for fraction in fractions:
        number(fraction, 'knowledge fraction')
    selected = {}
    for attack in report['attacks']:
        if attack['feature_set'] != 'counts_geometry_time' or attack['knowledge_fraction'] not in fractions:
            continue
        key = (attack['variant'], attack['knowledge_fraction'])
        if key in selected:
            raise ValueError('Duplicate attack projection')
        selected[key] = attack
    rows, counts = [], set()
    for name, label in METHODS:
        utility = report['utility'][name]
        coverage = number(utility['answered_query_coverage'], 'answered query coverage')
        retention = number(utility['contribution_retention'], 'retention')
        attacks = []
        for fraction in fractions:
            if (name, fraction) not in selected:
                raise ValueError('Missing attack for ' + name)
            attack = selected[(name, fraction)]
            count = attack['test_groups']
            if isinstance(count, bool) or not isinstance(count, int) or count < 2:
                raise ValueError('At least two independent test groups are required')
            counts.add(count)
            auc = number(attack['test']['roc_auc'], 'ROC-AUC')
            interval = attack['test_uncertainty'].get('intervals', {}).get('roc_auc')
            if not isinstance(interval, (list, tuple)) or len(interval) != 2:
                raise ValueError('AUC bootstrap interval is required')
            lo, hi = [number(value, 'AUC interval') for value in interval]
            if lo > hi:
                raise ValueError('AUC interval endpoints are reversed')
            attacks.append(dict(fraction=fraction, auc=auc, low=lo, high=hi))
        rows.append(dict(name=name, label=label, coverage=coverage, retention=retention, attacks=attacks))
    if len(counts) != 1:
        raise ValueError('All attacks must use the same independent test group count')
    return rows, counts.pop()


def export(report, output, fractions=(.25, 1.0)):
    rows, groups = prepare(report, fractions)
    output = Path(output)
    destinations = [output.with_suffix(suffix) for suffix in ('.png', '.svg')]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise ValueError('Output files already exist')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = ['#2463a2', '#b85e20', '#43805d', '#865db2']
    created = []
    with plt.rc_context({'svg.hashsalt': 'ump-privacy-coordination-v1', 'svg.fonttype': 'none',
                         'font.family': 'DejaVu Sans', 'font.size': 10}):
        figure, axes = plt.subplots(1, 3, figsize=(15, 8.4), sharey=True,
                                    gridspec_kw={'width_ratios': [1.5, 1, 1]})
        try:
            for position, row in enumerate(rows):
                for index, attack in enumerate(row['attacks']):
                    y = position + (index - (len(fractions) - 1) / 2) * .2
                    color = colors[index % len(colors)]
                    axes[0].hlines(y, attack['low'], attack['high'], color=color, linewidth=1.2)
                    axes[0].plot(attack['auc'], y, 'o', color=color, markersize=4.5,
                                 label=f"{100*attack['fraction']:g}% candidate trace" if position == 0 else None)
                axes[1].plot(100 * row['coverage'], position, 'o', color='#333333', markersize=5)
                axes[2].plot(100 * row['retention'], position, 'o', color='#333333', markersize=5)
            axes[0].axvline(.5, color='#888888', linestyle='--', linewidth=1)
            axes[0].set_xlim(0, 1)
            axes[0].set_xlabel('Held-out membership ROC-AUC')
            axes[0].set_title('Evaluated attack; 95% conditional interval')
            axes[1].set_xlabel('Answered fixed queries (%)')
            axes[1].set_title('Retrospective occupancy availability')
            axes[2].set_xlabel('Retained observations (%)')
            axes[2].set_title('Included source contributions')
            for axis in axes[1:]:
                axis.set_xlim(-2, 102)
            axes[0].set_yticks(range(len(rows)), [row['label'] for row in rows])
            axes[0].invert_yaxis()
            for axis in axes:
                axis.grid(axis='x', alpha=.18)
                axis.spines[['top', 'right', 'left']].set_visible(False)
                axis.tick_params(axis='y', length=0)
            axes[0].legend(loc='lower left', bbox_to_anchor=(0, 1.04), fontsize=9, frameon=False)
            figure.suptitle('Synthetic source-contribution membership: common versus local coordination', y=.97, fontsize=15)
            figure.text(.5, .06,
                f'{groups} independent paired held-out groups; 31 public count/geometry/time features; balanced IN/OUT prior.\n'
                'Models fit on training groups; thresholds calibrated separately. Intervals condition on those fitted models.\n'
                'Utility: same 10 m / 1 s query, unknown missing support. Exact-count control bypasses policy.\n'
                'Attack failure does not establish privacy. Synthetic population; no physical-presence or universal guarantee.',
                ha='center', va='bottom', fontsize=9, linespacing=1.5)
            figure.subplots_adjust(left=.24, right=.98, top=.86, bottom=.22, wspace=.27)
            output.parent.mkdir(parents=True, exist_ok=True)
            for path in destinations:
                with path.open('xb') as stream:
                    created.append(path)
                    buffer = io.BytesIO()
                    metadata = {'Date': None, 'Creator': 'UMP privacy coordination'} if path.suffix == '.svg' else {'Software': 'UMP privacy coordination'}
                    figure.savefig(buffer, format=path.suffix[1:], dpi=180, metadata=metadata)
                    payload = buffer.getvalue()
                    if path.suffix == '.svg':
                        payload = b'\n'.join(line.rstrip() for line in payload.splitlines()) + b'\n'
                    stream.write(payload)
        except Exception:
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
    parser.add_argument('--knowledge-fractions', nargs='+', type=float, default=[.25, 1.0])
    args = parser.parse_args()
    paths = export(json.loads(args.report.read_text()), args.output, tuple(args.knowledge_fractions))
    print('Exported ' + ', '.join(map(str, paths)))


if __name__ == '__main__':
    main()
