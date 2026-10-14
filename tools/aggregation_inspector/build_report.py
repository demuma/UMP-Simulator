#!/usr/bin/env python3
"""Create an offline inspector from UMP candidate/spatial diagnostics (stdlib only)."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys


def load_records(paths):
    records, seen, sources = [], set(), []
    for path in paths:
        raw = path.read_bytes()
        sources.append({'name': path.name, 'sha256': hashlib.sha256(raw).hexdigest()})
        for line_number, line in enumerate(raw.decode('utf-8').splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            if (row.get('schema'), row.get('data_role')) not in (('ump.fixed-candidate.v3', 'internal_research_candidate'), ('ump.spatial-selection.v1', 'internal_spatial_selection')):
                raise ValueError(f'{path.name}:{line_number}: expected internal ump.fixed-candidate.v3 or ump.spatial-selection.v1 diagnostics')
            key = tuple(row[k] for k in ('schema', 'run_id', 'sensor_id', 'application_id', 'start_ms', 'end_ms'))
            if key in seen:
                raise ValueError(f'Duplicate candidate window: {key}')
            seen.add(key)
            if row['end_ms'] <= row['start_ms'] or row['start_ms'] < 0:
                raise ValueError('Invalid half-open window')
            grid = row['grid']
            if not all(isinstance(grid[k], (float, int)) and math.isfinite(grid[k]) for k in ('x', 'y', 'width', 'height')):
                raise ValueError('Non-finite grid geometry')
            if grid['width'] <= 0 or grid['height'] <= 0:
                raise ValueError('Non-positive grid geometry')
            for cell in row['cells'] + row.get('source_cells', []) + row.get('attempts', []):
                if not all(isinstance(cell[k], (float, int)) and math.isfinite(cell[k]) for k in ('x', 'y', 'width', 'height')):
                    raise ValueError('Non-finite cell geometry')
                if cell['width'] <= 0 or cell['height'] <= 0 or cell['x'] < grid['x'] or cell['y'] < grid['y'] \
                    or cell['x'] + cell['width'] > grid['x'] + grid['width'] \
                    or cell['y'] + cell['height'] > grid['y'] + grid['height']:
                    raise ValueError('Cell outside declared grid')
                if cell['threshold_status'] not in ('pass', 'fail', 'unavailable', 'not_configured'):
                    raise ValueError('Unknown cell assessment status')
                for field in ('metrics', 'checks', 'counts', 'policy'):
                    if field not in cell:
                        raise ValueError('Incomplete cell diagnostic record')
            records.append(row)
    if not records:
        raise ValueError('No candidate windows found')
    records.sort(key=lambda r: (r['run_id'], r['sensor_id'], r['application_id'], r['start_ms'], r['end_ms']))
    return {'records': records, 'sources': sources}


def build(paths, destination, template=None):
    payload = load_records(paths)
    template = template or Path(__file__).with_name('inspector.html')
    text = template.read_text()
    if text.count('__UMP_DIAGNOSTICS__') != 1:
        raise ValueError('Inspector template must contain exactly one payload marker')
    # JSON is inert script data; escape the HTML parser's closing-tag character.
    data = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text.replace('__UMP_DIAGNOSTICS__', data))
    return payload


def import_debug(paths, database):
    if not database.startswith('UMP_Debug') or not all(c.isalnum() or c in '_-' for c in database):
        raise ValueError('Debug imports require a dedicated database named UMP_Debug...')
    command = shutil.which('mongoimport')
    if not command:
        raise RuntimeError('mongoimport is required only for --mongo-database')
    # Same window keys overwrite only this debug copy; raw sensor collections are separate.
    for path in paths:
        subprocess.run([command, '--host', 'localhost', '--port', '27017', '--db', database,
            '--collection', 'aggregation_candidates', '--mode', 'upsert', '--upsertFields',
            'schema,run_id,sensor_id,application_id,start_ms,end_ms', '--stopOnError', '--file', str(path)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jsonl', type=Path, nargs='+', help='Existing v3 candidate or v1 spatial-selection diagnostic files')
    parser.add_argument('--output', '-o', type=Path, required=True, help='Self-contained HTML report')
    parser.add_argument('--mongo-database', help='Optional local debug copy in UMP_Debug.../aggregation_candidates')
    args = parser.parse_args()
    payload = build(args.jsonl, args.output)
    print(f"Inspector: {args.output.resolve()} ({len(payload['records'])} actual windows)")
    if args.mongo_database:
        import_debug(args.jsonl, args.mongo_database)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Inspector failed: {error}', file=sys.stderr)
        raise SystemExit(1)
