#!/usr/bin/env python3
"""Replay identical private observations through seven aggregation configurations."""
import argparse
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from occupancy import evaluate

VARIANTS = [(f'fixed_{side}m_{window}ms', 'fixed', depth, window)
            for side, depth in [(10, 3), (20, 2)] for window in (400, 1000)] + [
                ('spatial', 'spatial', None, None),
                ('temporal_first', 'temporal_first', None, None),
                ('spatial_first', 'spatial_first', None, None)]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def run_variant(binary, observations, policy, output, mode, depth, window):
    command = [str(binary), '--input', str(observations), '--config', str(policy),
               '--mode', mode, '--output', str(output)]
    if depth is not None:
        command += ['--fixed-depth', str(depth), '--fixed-window-ms', str(window)]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f'Replay failed: {completed.stderr.strip()}')
    return json.loads(output.read_text()), command


def scientific_result(result):
    """Runtime is the only intentionally nondeterministic replay result field."""
    return {key: value for key, value in result.items() if key != 'runtime'}


def summarize(result, utility):
    cells = [cell for release in result['releases'] for cell in release['cells']]
    def count(value):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError('Observation counts must be nonnegative integers')
        return value
    input_count = count(result['input_observation_contributions'])
    count(result['accounted_observation_contributions'])
    for cell in cells:
        count(cell['observation_contributions'])
    released = sum(cell['observation_contributions'] for cell in cells)
    # The coordinator re-evaluates every release. Verify private decision evidence too.
    selected = [cell for window in result['windows'] for cell in window['cells'] if cell['selected']]
    for cell in selected:
        count(cell['observation_contributions'])
    if any(cell['assessment_status'] != 'pass'
           or any(check['status'] != 'pass' for check in cell.get('checks', []))
           for cell in selected):
        raise ValueError('A selected cell did not pass its effective policy')
    if sum(cell['observation_contributions'] for cell in selected) != released:
        raise ValueError('Public and selected observation counts differ')
    if result['accounted_observation_contributions'] != input_count or released > input_count:
        raise ValueError('Observation conservation failed')
    ages = [release['sealed_at_ms'] - release['start_ms'] for release in result['releases']]
    return dict(utility['summary'],
                input_observations=input_count, released_observations=released,
                retained_observation_fraction=released / input_count if input_count else None,
                released_cells=len(cells), released_windows=len(result['releases']),
                selected_policy_failures=0,
                mean_release_age_ms=sum(ages) / len(ages) if ages else None,
                max_release_age_ms=max(ages) if ages else None,
                core_processing_ms=result['runtime']['processing_ms'])


def git_state(root):
    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    return dict(commit=git('rev-parse', 'HEAD'), status=git('status', '--short'))


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New private result directory')
    parser.add_argument('--provenance', type=Path, help='Optional capture manifest to preserve with the input')
    parser.add_argument('--binary', type=Path, default=root / 'simulator/build/AggregationReplay')
    parser.add_argument('--privacy-targets', type=int, default=0,
                        help='First N lexically sorted IDs for the strong known-background stress test')
    args = parser.parse_args()
    if args.privacy_targets < 0:
        parser.error('--privacy-targets must be nonnegative')
    input_bytes = args.input.read_bytes()
    replay = json.loads(input_bytes)
    grid = replay['coverage']
    if grid['width'] != 80 or grid['height'] != 80 or grid['leaf_depth'] < 3:
        parser.error('This comparison preset requires an 80-m square with leaf depth >= 3')
    if replay['sampling_period_ms'] != 100 or replay['end_ms'] < 1000:
        parser.error('This comparison preset requires 100-ms sampling and at least 1 second')
    binary = args.binary.resolve(strict=True)
    # Resolve both sources before creating anything; output is never reused/overwritten.
    input_path, config_path = args.input.resolve(strict=True), args.config.resolve(strict=True)
    provenance_bytes = args.provenance.read_bytes() if args.provenance else None
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    frozen, config = output / 'observations.json', output / 'policy.yaml'
    frozen.write_bytes(input_bytes)
    shutil.copyfile(config_path, config)
    if provenance_bytes is not None:
        (output / 'input-provenance.json').write_bytes(provenance_bytes)
    source_files = [root / 'simulator/tools/AggregationReplay.cpp', root / 'simulator/CMakeLists.txt']
    source_files += sorted((root / 'simulator/src').glob('*Aggregation*'))
    source_files += [root / 'simulator/src' / name for name in
                     ['CandidateMetrics.cpp', 'PolicyTree.cpp', 'PolicyConfiguration.cpp',
                      'SpatialSelection.cpp', 'PublicationCoordinator.cpp']]
    source_files += sorted((root / 'simulator/include').glob('*.hpp'))
    source_files += sorted((root / 'tools/evaluation').glob('*.py'))
    manifest = dict(schema='ump.comparison.v1', classification='private_research_bundle',
        created_utc=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
        python=sys.version, git=git_state(root), source_input=str(input_path),
        source_config=str(config_path), input_sha256=digest(frozen),
        input_provenance_sha256=digest(output / 'input-provenance.json') if provenance_bytes is not None else None,
        config_sha256=digest(config), binary_sha256=digest(binary),
        source_sha256={str(p.relative_to(root)): digest(p) for p in source_files},
        privacy_scope='deterministic_full_known_background_neighbour_stress_test',
        reference_cell_m=10, reference_window_ms=1000, variants=[])
    results, utilities, summaries = {}, {}, {}
    for name, mode, depth, window in VARIANTS:
        destination = output / (name + '.json')
        result, command = run_variant(binary, frozen, config, destination, mode, depth, window)
        utility = evaluate(replay, result)
        write_json(output / (name + '.utility.json'), utility)
        results[name], utilities[name] = result, utility
        summaries[name] = summarize(result, utility)
        manifest['variants'].append(dict(name=name, command=command, result_sha256=digest(destination)))
        print(f'{name}: {summaries[name]["released_cells"]} cells; '
              f'coverage={summaries[name]["answered_query_coverage"]:.3f}; '
              f'MAE={summaries[name]["occupancy_mae"]}', flush=True)
    # Demonstrate deterministic mechanism output on an identical second execution.
    repeated_path = output / 'determinism-repeat.json'
    repeated, _ = run_variant(binary, frozen, config, repeated_path, 'spatial_first', None, None)
    if scientific_result(repeated) != scientific_result(results['spatial_first']):
        raise ValueError('Identical input produced different scientific output')
    repeated_path.unlink()
    manifest['deterministic_repeat_verified'] = True
    if args.privacy_targets:
        from privacy import neighbouring_replay, compare_pair
        targets = sorted({o['id'] for b in replay['batches'] for o in b['observations']})[:args.privacy_targets]
        if not targets:
            raise ValueError('No observed target IDs for the requested privacy check')
        pairs = {name: [] for name, *_ in VARIANTS}
        privacy_dir = output / 'private-neighbours'
        privacy_dir.mkdir(mode=0o700)
        for index, target in enumerate(targets):
            neighbour_path = privacy_dir / f'input-{index}.json'
            write_json(neighbour_path, neighbouring_replay(replay, target))
            for name, mode, depth, window in VARIANTS:
                neighbour, _ = run_variant(binary, neighbour_path, config,
                    privacy_dir / f'{name}-{index}.json', mode, depth, window)
                comparison = compare_pair(results[name], neighbour)
                pairs[name].append(dict(target_id=target, **comparison))
        write_json(output / 'privacy.json', dict(target_selection='first N lexically sorted observed IDs',
            targets=targets, assumptions='exact deterministic target and other-trajectories knowledge', pairs=pairs))
        for name, comparisons in pairs.items():
            rate = sum(bool(c['public_transcript_changed']) for c in comparisons) / len(comparisons)
            summaries[name]['known_background_distinguishability_rate'] = rate
            summaries[name]['derived_ideal_balanced_success'] = (1 + rate) / 2
        manifest['privacy_target_count'] = len(targets)
    # Common query support is an additional comparator, not a replacement denominator.
    common = [i for i in range(len(next(iter(utilities.values()))['queries']))
              if all(u['queries'][i]['absolute_error'] is not None for u in utilities.values())]
    for name, utility in utilities.items():
        summaries[name]['common_scored_queries_all_variants'] = len(common)
        summaries[name]['common_support_mae_all_variants'] = (
            sum(utility['queries'][i]['absolute_error'] for i in common) / len(common) if common else None)
    write_json(output / 'summary.json', summaries)
    columns = ['variant', 'occupancy_mae', 'answered_query_coverage', 'scored_query_coverage',
               'retained_observation_fraction', 'released_cells', 'mean_release_age_ms',
               'common_scored_queries_all_variants', 'common_support_mae_all_variants',
               'core_processing_ms']
    if args.privacy_targets:
        columns += ['known_background_distinguishability_rate', 'derived_ideal_balanced_success']
    with (output / 'summary.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(dict(variant=name, **summary) for name, summary in summaries.items())
    write_json(output / 'manifest.json', manifest)
    print(f'Private evaluation complete: {output}')


if __name__ == '__main__':
    main()
