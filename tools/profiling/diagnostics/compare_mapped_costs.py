#!/usr/bin/env python3
"""Require exact source, releases and complete final journal in mapped cost runs."""
import argparse
import hashlib
import json
from pathlib import Path


def canonical_rows(rows, run_id, generated_ids=False):
    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, str):
            return value.replace(run_id, '<run-id>')
        return value
    return sorted(json.dumps(normalize({key: value for key, value in row.items()
                  if not (generated_ids and key == '_id')}), sort_keys=True,
                  separators=(',', ':')) for row in rows)


def compare(before, after):
    output = {'schema': 'ump.mapped-mongo-cost-comparison.v1', 'equal': True, 'checks': {}}
    sources = [json.loads((path / 'replay/private/native_source.json').read_text())
               for path in [before, after]]
    run_ids = [json.loads((path / 'replay/observations.json').read_text())['run_id']
               for path in [before, after]]
    for channel in ['agents', 'sensor', 'releases', 'journals']:
        rows = [canonical_rows(source[channel], run_id, channel in ['agents', 'sensor'])
                for source, run_id in zip(sources, run_ids)]
        if rows[0] != rows[1]:
            raise ValueError('Mapped source/publication mismatch: ' + channel)
        output['checks'][channel] = {'equal': True, 'rows': len(rows[0]),
            'normalized_sha256': hashlib.sha256('\n'.join(rows[0]).encode()).hexdigest()}
    # All final journal fields are checked above, including state, payload and IDs.
    # Fresh raw BSON IDs and the run UUID (including its release-ID embedding) are
    # the only normalization. Timestamps, positions, identities and order within
    # each aggregate remain unchanged. Database cursor row order is immaterial.
    output['normalization'] = 'fresh raw BSON _id, run UUID, database cursor row order only'
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.before, args.after), indent=2))


if __name__ == '__main__':
    main()
