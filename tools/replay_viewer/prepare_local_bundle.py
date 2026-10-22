#!/usr/bin/env python3
"""Prepare a private common/local replay bundle from a verified frozen study."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

import serve


def prepare(study, output):
    study, output = Path(study).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Refusing to replace an existing replay directory')
    manifest = json.loads((study / 'study-manifest.json').read_text())
    if manifest.get('schema') != 'ump.semantic-cell-local-study.v1' or manifest.get('status') != 'verified':
        raise ValueError('Expected a verified semantic cell-local study')
    hashes = manifest.get('artifacts_sha256', {})
    # The list is deliberately fixed; paths from a manifest never choose output paths.
    variants = []
    for regional in (True, False):
        for secondary in ('temporal_first', 'spatial_first'):
            for coordination in ('common_window', 'cell_local'):
                name = f'{coordination}_{"regional" if regional else "uniform"}_{secondary}'
                variants.append((name, coordination, regional, secondary))
    required = ['observations.json'] + [f'{v[0]}{suffix}' for v in variants
                                        for suffix in ('.json', '-policy.json')]
    verified = {}
    for name in required:
        payload = (study / name).read_bytes()
        if not isinstance(hashes.get(name), str) or hashlib.sha256(payload).hexdigest() != hashes[name]:
            raise ValueError('Missing or mismatched frozen source digest: ' + name)
        verified[name] = payload
    output.parent.mkdir(parents=True, exist_ok=True)
    # Validate before publishing the new directory; failed preparation leaves no bundle.
    with tempfile.TemporaryDirectory(prefix='.ump-replay-', dir=output.parent) as temporary:
        staging = Path(temporary)
        (staging / 'observations.json').write_bytes(verified['observations.json'])
        entries = []
        for name, coordination, regional, secondary in variants:
            (staging / f'{name}.json').write_bytes(verified[f'{name}.json'])
            config = json.loads(verified[f'{name}-policy.json'])
            regions = [{**{key: region[key] for key in ('id', 'type', 'x', 'y', 'width', 'height')},
                        'requirements': [{'metric': metric, **bounds}
                            for metric, bounds in region['requirements'].items()]}
                       for region in config.get('policy_regions', [])]
            label = ('Regional' if regional else 'Uniform') + ' · ' + (
                'Local windows' if coordination == 'cell_local' else 'Common window') + ' · Semantic → ' + (
                'Temporal' if secondary == 'temporal_first' else 'Spatial')
            entries.append({'id': name, 'label': label, 'result': name + '.json', 'policy_regions': regions})
        bundle = {'schema': serve.SCHEMA,
                  'title': 'Independent cell windows versus common window · scripted mechanism test',
                  'observations': 'observations.json', 'variants': entries,
                  'sha256': {name: hashes[name] for name in ['observations.json'] + [v['result'] for v in entries]}}
        (staging / 'bundle.json').write_text(json.dumps(bundle, indent=2, sort_keys=True) + '\n')
        serve.validate_bundle(staging)
        # Refuse a concurrent destination as well; never overwrite a previous experiment.
        if output.exists():
            raise ValueError('Replay destination appeared during preparation')
        staging.rename(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print('Prepared private local replay:', prepare(args.study, args.output))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit('Replay preparation failed: ' + str(error))
