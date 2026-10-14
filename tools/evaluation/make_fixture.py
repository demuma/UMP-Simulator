#!/usr/bin/env python3
"""Create a deterministic mechanism-test input; this is not a realistic traffic model."""
import argparse
import json
import math
from pathlib import Path


def cell_id(x, y, coverage):
    """Encode the simulator's 11 prefix followed by x/y quadrant bits."""
    left, top = coverage['x'], coverage['y']
    width, height = coverage['width'], coverage['height']
    if not (left <= x < left + width and top <= y < top + height):
        raise ValueError('Position outside coverage')
    value = 3
    for _ in range(coverage['leaf_depth']):
        width /= 2
        height /= 2
        right, bottom = x >= left + width, y >= top + height
        value = value * 4 + int(right) + 2 * int(bottom)
        if right:
            left += width
        if bottom:
            top += height
    return value


def make_fixture():
    grid = dict(x=0, y=0, width=80, height=80, leaf_depth=6)
    batches = []
    # Different densities, cross-cell motion and one completely empty second.
    # Stable identities and deterministic positions make neighbour removals exact.
    clusters = [(12, 12, 12), (29, 28, 6), (52, 14, 3), (71, 30, 2),
                (14, 56, 8), (33, 70, 4), (60, 58, 1)]
    for sequence, time in enumerate(range(100, 8000, 100), 1):
        observations = []
        if not 6000 <= time < 7000:
            for cluster, (cx, cy, count) in enumerate(clusters):
                for i in range(count):
                    phase = time / 1000 + i * 0.3
                    x = cx + (i % 4 - 1.5) * 2.2 + 3.1 * math.sin(phase * 0.6)
                    y = cy + (i // 4 - 1) * 2.5 + 2.4 * math.cos(phase * 0.4)
                    observations.append(dict(id=f'ru-{cluster:02d}-{i:02d}',
                        type='pedestrian', cell_id=cell_id(x, y, grid), x=x, y=y))
        batches.append(dict(sequence=sequence, observed_at_ms=time,
                            status='measured', observations=observations))
    return dict(schema='ump.observation-replay.v1', run_id='heterogeneous-fixture-v1',
                sensor_id='ideal-agbs', coverage=grid, sampling_period_ms=100,
                end_ms=8000, batches=batches)


def make_handover_fixture():
    """Analytical handovers isolate the two action orders; no physical realism claim."""
    grid = dict(x=0, y=0, width=80, height=80, leaf_depth=6)
    batches = []
    for sequence, time in enumerate(range(100, 4000, 100), 1):
        generation = (time // 400) % 2
        observations = []
        for index, (x, y) in enumerate([(50.2, 10.2), (59.2, 19.2)]):
            observations.append(dict(id=f'handover-{generation}-{index}', type='pedestrian',
                cell_id=cell_id(x, y, grid), x=x, y=y))
        batches.append(dict(sequence=sequence, observed_at_ms=time,
                            status='measured', observations=observations))
    return dict(schema='ump.observation-replay.v1', run_id='analytical-handover-v1',
                sensor_id='ideal-agbs', coverage=grid, sampling_period_ms=100,
                end_ms=4000, batches=batches)


def make_policy():
    return dict(application_id='occupancy-evaluation', window_ms=400,
        max_observations_per_window=1000000,
        history=dict(retention_ms=2000, max_bins=32, max_observations=100000,
                     max_identity_bytes=16000000, max_buckets=128),
        spatial_selection=dict(min_depth=1, max_evaluations=4096),
        temporal_adaptation=dict(extension_step_ms=100, max_window_ms=1000, max_evaluations=16),
        policy_tree=dict(id='evaluation-regions', version='1', max_nodes=65536,
            execution=dict(publication_model='private_final_snapshot', strategy='spatial_first'),
            root=dict(distinct_contributors=dict(min=2), cell_side_m=dict(min=1.25, max=40),
                      window_duration_ms=dict(max=1000), age_at_evaluation_ms=dict(max=1000)),
            regions=['west']),
        policy_regions=[dict(id='west', type='residential', x=0, y=0, width=40, height=40,
            type_requirements=dict(distinct_contributors=dict(min=5)),
            requirements=dict(distinct_contributors=dict(min=2)))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory')
    parser.add_argument('--scenario', choices=['heterogeneous', 'handover'], default='heterogeneous')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, data in [('observations.json', make_handover_fixture() if args.scenario == 'handover' else make_fixture()),
                       ('policy.json', make_policy())]:
        (args.output / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
