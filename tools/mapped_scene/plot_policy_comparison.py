#!/usr/bin/env python3
"""Plot aggregate support-policy comparison metrics without opening source data."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

MAX_SUMMARY_BYTES = 4 * 1024 * 1024
METHODS = (
    ('adaptive_immediate', 'Adaptive'),
    ('fixed_5m_400ms', 'Fixed 5 m\n0.4 s'),
    ('fixed_5m_1000ms', 'Fixed 5 m\n1 s'),
    ('fixed_10m_400ms', 'Fixed 10 m\n0.4 s'),
    ('fixed_10m_1000ms', 'Fixed 10 m\n1 s'),
)
PROFILES = ('original', 'support60')
COLORS = ('#2A5674', '#C56B27')


def metric(value, name, *, maximum=None):
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum):
        raise ValueError('Invalid plotted metric: ' + name)
    return value


def series(summary):
    """Preserve missing metrics; convert proportions to percent and ms to seconds."""
    if summary.get('schema') != 'ump.mapped-comparison.v1' or summary.get('status') != 'verified':
        raise ValueError('Require a verified compact mapped comparison summary')
    protocol = summary.get('protocol', {})
    if protocol.get('comparison_kind') != 'support_policy_sensitivity':
        raise ValueError('Require the explicitly declared support-policy sensitivity comparison')
    expected = {profile + '_' + method for profile in PROFILES for method, _ in METHODS}
    if {row.get('id') for row in protocol.get('matrix', [])} != expected or len(protocol['matrix']) != len(expected):
        raise ValueError('Require the complete predeclared ten-case support-policy matrix')
    if set(summary.get('cases', {})) != expected:
        raise ValueError('Summary cases must exactly match the predeclared matrix')
    values = {key: {profile: [] for profile in PROFILES} for key in ('retention', 'semantic_loss', 'side', 'delay_p95')}
    for profile in PROFILES:
        for method, _ in METHODS:
            name = profile + '_' + method
            case = summary['cases'][name]
            audit = case.get('independent_audit', {})
            if audit.get('status') != 'verified' or audit.get('scalar_valid') is not True or audit.get('published_policy_violations') != 0:
                raise ValueError('Every plotted case requires verified zero-violation policy audit: ' + name)
            stats = case['stats']
            raw = {
                'retention': metric(stats.get('retained_fraction'), name + ' retention', maximum=1),
                'semantic_loss': metric(stats.get('observation_weighted_semantic_loss'), name + ' semantic loss', maximum=1),
                'side': metric(stats.get('observation_weighted_cell_side_m'), name + ' cell side'),
                'delay_p95': metric(stats.get('source_accounting', {}).get('observation_to_release_delay_ms', {}).get('p95'), name + ' p95 delay'),
            }
            for key, value in raw.items():
                scale = 100 if key in ('retention', 'semantic_loss') else .001 if key == 'delay_p95' else 1
                values[key][profile].append(None if value is None else value * scale)
    return values


def plot(summary_path, output):
    """Write a fresh aggregate-only figure directory, leaving existing data intact."""
    summary_path, output = Path(summary_path).resolve(), Path(output).resolve()
    if not summary_path.is_file() or summary_path.stat().st_size > MAX_SUMMARY_BYTES:
        raise ValueError('Summary must be a regular JSON file of at most 4 MiB')
    if output.exists():
        raise ValueError('Choose a fresh figure output directory')
    raw = summary_path.read_bytes()
    summary = json.loads(raw)
    values = series(summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'svg.fonttype': 'none', 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.titleweight': 'semibold'})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5))
    positions = list(range(len(METHODS)))
    labels = [label for _, label in METHODS]
    definitions = (
        ('retention', 'Retained observation contributions', 'Full input retained (%)', 100),
        ('semantic_loss', 'Semantic loss of retained contributions', 'Observation-weighted loss (%)', 100),
        ('side', 'Spatial detail of retained contributions', 'Observation-weighted cell side (m)', None),
        ('delay_p95', 'Release delay of retained contributions', 'Observation-to-seal p95 (s)', None),
    )
    for ax, (key, title, ylabel, upper) in zip(axes.flat, definitions):
        present = [value for profile in PROFILES for value in values[key][profile] if value is not None]
        top = upper if upper is not None else max(present, default=1) * 1.18
        if top <= 0:
            top = 1
        ax.set_ylim(0, top)
        for index, profile in enumerate(PROFILES):
            offset = -.19 if index == 0 else .19
            for position, value in zip(positions, values[key][profile]):
                if value is None:
                    ax.text(position + offset, .025, 'n/a', transform=ax.get_xaxis_transform(),
                            color=COLORS[index], ha='center', va='bottom', rotation=90, fontsize=8)
                else:
                    bars = ax.bar(position + offset, value, width=.34, color=COLORS[index], zorder=3)
                    text = f'{value:.1f}' if key in ('retention', 'semantic_loss') else f'{value:.2f}'
                    ax.bar_label(bars, labels=[text], padding=3, fontsize=8)
        ax.set_title(title, fontsize=12, pad=13)
        ax.set_ylabel(ylabel)
        ax.set_xticks(positions, labels)
        ax.tick_params(axis='x', length=0, pad=7)
        ax.set_xlim(-.65, len(METHODS) - .35)
        ax.grid(axis='y', color='#E2E5E7', linewidth=.7, zorder=0)
        ax.set_axisbelow(True)
    fig.suptitle('Support policy sensitivity · identical recorded observations', fontsize=16, fontweight='semibold', y=.975)
    fig.text(.5, .936, 'Support60: every support floor becomes ceil(0.6 × q); all other hard bounds stay fixed.',
             ha='center', fontsize=10, color='#40464A')
    fig.legend(handles=[Patch(facecolor=color, label=label) for color, label in zip(COLORS, ('Original Policy Tree', 'Relaxed support Policy Tree'))],
               loc='upper center', bbox_to_anchor=(.5, .918), ncol=2, frameon=False, fontsize=10)
    fig.text(.5, .024, 'Missing metrics are n/a. Detail and delay condition on retained data; retention uses the full input.\n'
             'Adaptive windows may reach 4 s; the original fixed portfolio uses 0.4/1 s. Maximum-window results are separate.\n'
             'Between-policy utility differences change the protection contract; they do not measure a privacy gain.',
             ha='center', fontsize=9, color='#40464A', linespacing=1.5)
    fig.subplots_adjust(left=.08, right=.98, top=.835, bottom=.145, wspace=.25, hspace=.48)
    output.mkdir(parents=True, mode=0o700)
    try:
        fig.savefig(output / 'support-policy-comparison.png', dpi=180, facecolor='white')
        fig.savefig(output / 'support-policy-comparison.svg', facecolor='white', metadata={'Date': None})
    finally:
        plt.close(fig)
    metadata = {'schema': 'ump.support-policy-figure.v1', 'summary_sha256': hashlib.sha256(raw).hexdigest(),
                'methods': [method for method, _ in METHODS], 'profiles': list(PROFILES),
                'metrics': values, 'missing_value_rule': 'No bar, explicitly marked n/a; never substituted with zero.',
                'scope': 'Aggregate-only policy sensitivity. Between-policy differences change the protection contract; no privacy-gain claim.'}
    with (output / 'figure-provenance.json').open('x') as stream:
        json.dump(metadata, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Fresh local figure directory')
    args = parser.parse_args()
    plot(args.summary, args.output)


if __name__ == '__main__':
    main()
