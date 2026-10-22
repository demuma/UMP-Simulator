#!/usr/bin/env python3
"""Serve a validated private UMP replay bundle on 127.0.0.1 (stdlib only).

Only the manifest's allowlisted JSON files and the viewer's three assets are
served. No directory listing, arbitrary project file, write endpoint, CDN or
external connection is required. This is a private research viewer, not an
anonymized export service.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import unquote, urlsplit

SCHEMA = 'ump.replay-viewer.v1'
ASSETS = ('index.html', 'model.js', 'viewer.js')


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f'Non-finite number: {v}')))


def local_file(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or '\\' in value or '%' in value or '?' in value or '#' in value:
        raise ValueError('Bundle paths must be ordinary relative POSIX filenames')
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(p in ('..', '.') for p in value.split('/')):
        raise ValueError('Bundle paths cannot traverse outside the bundle')
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'Missing or escaping bundle file: {value}')
    if path.suffix != '.json':
        raise ValueError('Only JSON bundle data is served')
    return path


def numeric(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(f'Invalid {name}')


def validate_policy_regions(variant: dict, coverage: dict):
    """Optional display metadata remains bounded and spatially truthful.

    These declarations do not evaluate policy or certify recorded cell checks.
    They only supply local overlays for private research inspection.
    """
    if 'policy_regions' not in variant:
        return
    regions = variant['policy_regions']
    if not isinstance(regions, list) or len(regions) > 4096:
        raise ValueError('Policy region overlays require a list of at most 4096 regions')
    ids = set()
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError('Policy region overlays require region objects')
        identity = region.get('id')
        if not isinstance(identity, str) or not identity.strip() or identity != identity.strip() or len(identity) > 128 or identity in ids:
            raise ValueError('Policy region IDs must be unique nonempty text up to 128 characters')
        ids.add(identity)
        if 'type' in region and (not isinstance(region['type'], str) or not region['type'].strip() or len(region['type']) > 128):
            raise ValueError('Policy region type must be nonempty text up to 128 characters')
        for key in ('x', 'y', 'width', 'height'):
            numeric(region.get(key), 'policy region '+key, -math.inf if key in ('x', 'y') else 0)
        if region['width'] <= 0 or region['height'] <= 0 or region['x'] < coverage['x'] or region['y'] < coverage['y'] or region['x']+region['width'] > coverage['x']+coverage['width'] or region['y']+region['height'] > coverage['y']+coverage['height']:
            raise ValueError('Policy region rectangle must have positive size and lie inside coverage')
        requirements = region.get('requirements', [])
        if not isinstance(requirements, list) or len(requirements) > 64:
            raise ValueError('Policy region requirements must be a list of at most 64 bounds')
        for requirement in requirements:
            if not isinstance(requirement, dict) or not isinstance(requirement.get('metric'), str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,95}', requirement['metric']):
                raise ValueError('Policy region metrics must be lowercase identifier strings')
            if 'min' not in requirement and 'max' not in requirement:
                raise ValueError('Policy region requirements need a minimum or maximum')
            for bound in ('min', 'max'):
                if bound in requirement:
                    numeric(requirement[bound], 'policy region requirement '+bound, -math.inf)
            if 'min' in requirement and 'max' in requirement and requirement['min'] > requirement['max']:
                raise ValueError('Policy region minimum cannot exceed its maximum')


def validate_bundle(root: Path) -> tuple[dict, dict[str, Path]]:
    root = root.resolve()
    manifest = read_json(root / 'bundle.json')
    if manifest.get('schema') != SCHEMA or not isinstance(manifest.get('variants'), list) or not manifest['variants']:
        raise ValueError('Expected ump.replay-viewer.v1 with nonempty variants')
    if len(manifest['variants']) > 64:
        raise ValueError('At most 64 variants are supported')
    paths = {'bundle.json': root / 'bundle.json'}
    observation_path = local_file(root, manifest.get('observations'))
    paths[manifest['observations']] = observation_path
    replay = read_json(observation_path)
    if replay.get('schema') != 'ump.observation-replay.v1':
        raise ValueError('Unsupported observation schema')
    numeric(replay.get('end_ms'), 'end_ms', 1)
    numeric(replay.get('sampling_period_ms'), 'sampling period', 1)
    coverage = replay.get('coverage', {})
    for key in ('x', 'y', 'width', 'height', 'leaf_depth'):
        numeric(coverage.get(key), key, -1e12 if key in ('x', 'y') else 0)
    if coverage['width'] <= 0 or coverage['height'] <= 0:
        raise ValueError('Coverage must have positive dimensions')
    previous = -1
    if not isinstance(replay.get('batches'), list):
        raise ValueError('Missing replay batches')
    for batch in replay['batches']:
        stamp = batch.get('observed_at_ms')
        numeric(stamp, 'observation timestamp')
        if stamp <= previous or stamp >= replay['end_ms']:
            raise ValueError('Observation timestamps must increase strictly before end_ms')
        previous = stamp
        if batch.get('status') not in ('measured', 'unavailable') or not isinstance(batch.get('observations'), list):
            raise ValueError('Invalid observation batch')
        if batch['status'] != 'measured' and batch['observations']:
            raise ValueError('Unavailable batches cannot expose observed positions')
        identities = set()
        for item in batch['observations']:
            if not isinstance(item.get('id'), str) or not item['id'] or item['id'] in identities or not isinstance(item.get('type'), str):
                raise ValueError('Empty or duplicate observation identity / invalid type')
            identities.add(item['id'])
            for key in ('x', 'y'):
                numeric(item.get(key), 'observation '+key, -1e12)
            if not (coverage['x'] <= item['x'] < coverage['x']+coverage['width'] and coverage['y'] <= item['y'] < coverage['y']+coverage['height']):
                raise ValueError('Observation outside declared coverage')
    ids = set()
    for variant in manifest['variants']:
        if not isinstance(variant, dict) or not re.fullmatch(r'[A-Za-z0-9_-]+', variant.get('id', '')) or variant['id'] in ids or not isinstance(variant.get('label'), str):
            raise ValueError('Variants require unique simple IDs and text labels')
        ids.add(variant['id'])
        validate_policy_regions(variant, coverage)
        path = local_file(root, variant.get('result'))
        paths[variant['result']] = path
        result = read_json(path)
        source = result.get('source', {})
        if result.get('parameters', {}).get('coordination', 'common_window') != 'common_window':
            raise ValueError('The snapshot viewer supports common-window results only')
        if result.get('schema') != 'ump.replay-result.v1' or any(source.get(k) != replay.get(k) for k in ('run_id', 'sensor_id', 'sampling_period_ms', 'end_ms', 'coverage')):
            raise ValueError(f'{variant["id"]}: result belongs to different observations')
        for collection, event in [('releases', 'sealed_at_ms'), ('windows', 'evaluated_at_ms')]:
            rows = result.get(collection)
            if not isinstance(rows, list):
                raise ValueError(f'{variant["id"]}: missing {collection}')
            previous = -1
            for row in rows:
                stamp = row.get(event)
                numeric(stamp, event)
                numeric(row.get('start_ms'), 'window start')
                numeric(row.get('end_ms'), 'window end')
                if stamp < previous or stamp > replay['end_ms'] or not 0 <= row['start_ms'] < row['end_ms'] <= stamp:
                    raise ValueError(f'{variant["id"]}: unordered, future-dated or invalid {collection}')
                previous = stamp
                if not isinstance(row.get('cells'), list):
                    raise ValueError('Missing result cells')
                for cell in row['cells']:
                    for key in ('x', 'y', 'width', 'height'):
                        numeric(cell.get(key), 'cell '+key, -1e12 if key in ('x', 'y') else 0)
                    if cell['width'] <= 0 or cell['height'] <= 0 or cell['x'] < coverage['x'] or cell['y'] < coverage['y'] or cell['x']+cell['width'] > coverage['x']+coverage['width'] or cell['y']+cell['height'] > coverage['y']+coverage['height']:
                        raise ValueError('Result cell outside declared coverage')
    # Optional hashes make copied result packages auditable. They are not a
    # cryptographic trust assertion: users can edit both data and manifest.
    for relative, expected in manifest.get('sha256', {}).items():
        if relative not in paths or not re.fullmatch(r'[0-9a-f]{64}', expected) or hashlib.sha256(paths[relative].read_bytes()).hexdigest() != expected:
            raise ValueError(f'Bundle digest mismatch: {relative}')
    return manifest, paths


def handler_for(root: Path, assets: Path):
    manifest, files = validate_bundle(root)
    routes = {'/': assets/'index.html', '/index.html': assets/'index.html'}
    routes.update({'/assets/'+name: assets/name for name in ASSETS if name != 'index.html'})
    routes.update({'/bundle/'+name: path for name,path in files.items()})

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            request = urlsplit(self.path)
            path = unquote(request.path)
            if path not in routes:
                self.send_error(404, 'File not in validated replay bundle')
                return
            source = routes[path]
            data = source.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8' if source.suffix == '.json' else 'text/javascript; charset=utf-8' if source.suffix == '.js' else 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            if self.server.verbose:
                super().log_message(fmt,*args)

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True, help='Private directory with bundle.json and frozen JSON inputs/results')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--check', action='store_true', help='Validate bundle without starting a server')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    root = args.bundle.expanduser().resolve()
    handler = handler_for(root,Path(__file__).resolve().parent)
    if args.check:
        print(f'Validated replay bundle: {root}')
        return 0
    server = ThreadingHTTPServer(('127.0.0.1',args.port),handler)
    server.verbose = args.verbose
    print(f'Private replay viewer: http://127.0.0.1:{args.port}/',flush=True)
    print(f'Bundle: {root}\nPress Ctrl+C to stop. No simulation or MongoDB connection is started.',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(f'Replay viewer failed: {error}',file=sys.stderr)
        raise SystemExit(1)
