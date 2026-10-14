#!/usr/bin/env python3
"""Export a standalone figure from one controlled comparison (requires matplotlib)."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('comparison', type=Path)
    parser.add_argument('--title', default='Frozen-input aggregation comparison')
    args = parser.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary = json.loads((args.comparison / 'summary.json').read_text())
    labels = {'spatial': 'Spatial only', 'temporal_first': 'Temporal First',
              'spatial_first': 'Spatial First'}
    names = list(summary)
    display = [labels.get(name, name.replace('fixed_', 'Fixed ').replace('_', ' / ')) for name in names]
    colors = ['#8595a8'] * 4 + ['#3b7a98', '#2a9d8f', '#df9a33']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    figure, axes = plt.subplots(1, 3, figsize=(12.5, 5.3), sharey=True)
    specs = [('occupancy_mae', 'Conditional occupancy MAE\n[road users]', 1),
             ('answered_query_coverage', 'Answered query coverage\n[% of fixed domain]', 100),
             ('mean_release_age_ms', 'Mean simulated sealing age\n[ms; one weight per release]', 1)]
    for axis, (key, title, factor) in zip(axes, specs):
        values = [summary[name][key] for name in names]
        scaled = [(value * factor if value is not None else 0) for value in values]
        axis.barh(range(len(names)), scaled, color=colors, height=.64)
        axis.set_title(title, fontsize=10, pad=15)
        axis.set_yticks(range(len(names)), labels=display)
        axis.grid(axis='x', alpha=.2)
        axis.set_axisbelow(True)
        axis.spines[['right', 'top']].set_visible(False)
        upper = max(scaled, default=0) or 1
        axis.set_xlim(0, upper * 1.24)
        for row, (raw, value) in enumerate(zip(values, scaled)):
            label = 'undefined' if raw is None else f'{value:.2f}' if factor == 1 and key == 'occupancy_mae' else f'{value:.1f}'
            axis.text(value + upper * .025, row, label, va='center', fontsize=9)
    axes[0].invert_yaxis()
    figure.suptitle(args.title, fontsize=14, x=.03, ha='left')
    figure.text(.03, .035, 'Same observations and policy; 10-m / 1-s query. MAE uses answered queries only: subsets differ.\n'
                'Missing public cells are unknown. Sealing age is simulated time, not network latency. No general privacy claim.',
                fontsize=9, color='#454545')
    figure.tight_layout(rect=(0, .12, 1, .91), w_pad=2)
    for extension in ('png', 'svg', 'pdf'):
        path = args.comparison / f'comparison.{extension}'
        if path.exists():
            raise FileExistsError(path)
        figure.savefig(path, dpi=180)
    print(args.comparison / 'comparison.png')


if __name__ == '__main__':
    main()
