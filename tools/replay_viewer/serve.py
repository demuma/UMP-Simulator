#!/usr/bin/env python3
"""Serve a validated private UMP replay bundle on 127.0.0.1 (stdlib only).

Only the manifest's allowlisted JSON files and the viewer's three assets are
served. No directory listing, arbitrary project file, write endpoint, CDN or
external connection is required. This is a private research viewer, not an
anonymized export service.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, insort
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import struct
import zlib
from urllib.parse import unquote, urlsplit

SCHEMA = 'ump.replay-viewer.v1'
ASSETS = ('index.html', 'model.js', 'viewer.js')
MAX_MAP_BYTES = 16 * 1024 * 1024
MAX_MAP_SIDE = 4096


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


def validate_requirements(requirements, description):
    if not isinstance(requirements, list) or len(requirements) > 64:
        raise ValueError(description+' requires a list of at most 64 bounds')
    for requirement in requirements:
        if not isinstance(requirement, dict) or not isinstance(requirement.get('metric'), str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,95}', requirement['metric']):
            raise ValueError(description+' metrics must be lowercase identifier strings')
        if 'min' not in requirement and 'max' not in requirement:
            raise ValueError(description+' requires a minimum or maximum')
        for bound in ('min', 'max'):
            if bound in requirement:
                numeric(requirement[bound], description+' '+bound, -math.inf)
        if 'min' in requirement and 'max' in requirement and requirement['min'] > requirement['max']:
            raise ValueError(description+' minimum cannot exceed its maximum')


def validate_policy_regions(variant: dict, coverage: dict):
    """Validate declarations, never reconstruct missing observed metric checks."""
    if 'policy_root_requirements' in variant:
        validate_requirements(variant['policy_root_requirements'], 'Root policy')
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
        validate_requirements(region.get('requirements', []), 'Policy region')


def validate_png(path: Path):
    """Bound and structurally validate the one local RGB/RGBA map asset.

    Header dimensions alone do not stop a compressed pixel bomb. Validate chunk
    CRCs and bound decompression to the declared noninterlaced scanline size.
    No optional image decoder, arbitrary file serving or animation is used.
    """
    if path.stat().st_size > MAX_MAP_BYTES:
        raise ValueError('Map PNG exceeds 16 MiB')
    data = path.read_bytes()
    if len(data) < 45 or data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Map image must be a complete PNG')
    offset, header, chunks, ended = 8, None, [], False
    while offset < len(data):
        if offset+12 > len(data):
            raise ValueError('Truncated map PNG chunk')
        length = struct.unpack('>I', data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        end = offset+12+length
        if end > len(data):
            raise ValueError('Truncated map PNG payload')
        payload = data[offset+8:offset+8+length]
        crc = struct.unpack('>I', data[offset+8+length:end])[0]
        if zlib.crc32(kind+payload) & 0xffffffff != crc:
            raise ValueError('Map PNG chunk checksum mismatch')
        if header is None:
            if kind != b'IHDR' or length != 13:
                raise ValueError('Map PNG needs an initial IHDR')
            width,height,depth,color,compression,filtering,interlace = struct.unpack('>IIBBBBB',payload)
            if not 1 <= width <= MAX_MAP_SIDE or not 1 <= height <= MAX_MAP_SIDE or depth != 8 or color not in (2,6) or compression or filtering or interlace:
                raise ValueError('Map PNG must be bounded noninterlaced 8-bit RGB or RGBA')
            header = (width,height,3 if color==2 else 4)
        elif kind == b'IHDR':
            raise ValueError('Duplicate map PNG header')
        elif kind == b'IDAT':
            chunks.append(payload)
        elif kind == b'IEND':
            if length or end != len(data):
                raise ValueError('Map PNG must end at IEND')
            ended = True
        elif kind in (b'acTL',b'fcTL',b'fdAT') or not (kind[0] & 32):
            raise ValueError('Unsupported animated or critical map PNG chunk')
        offset = end
    if not ended or not chunks:
        raise ValueError('Incomplete map PNG')
    width,height,channels = header
    row_bytes = width*channels+1
    expected = row_bytes*height
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(b''.join(chunks), expected+1)
        if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('Map PNG decompressed size disagrees with its dimensions')
        if any(pixels[index] > 4 for index in range(0,expected,row_bytes)):
            raise ValueError('Invalid map PNG scanline filter')
    except zlib.error as error:
        raise ValueError('Invalid compressed map PNG') from error
    return width,height


def validate_map(root: Path, manifest: dict, coverage: dict):
    if 'identity_unit' in manifest and manifest['identity_unit'] not in ('visible_episode_track','observed_identity'):
        raise ValueError('Unsupported replay identity unit')
    if 'input_provenance' in manifest and (not isinstance(manifest['input_provenance'],str) or not manifest['input_provenance'].strip() or len(manifest['input_provenance']) > 1024):
        raise ValueError('Input provenance must be nonempty text up to 1024 characters')
    if 'map' not in manifest:
        return None
    mapping = manifest['map']
    if not isinstance(mapping,dict) or mapping.get('image') != 'map_background.png':
        raise ValueError('Map image must be the literal allowlisted map_background.png')
    bounds = mapping.get('bounds')
    if not isinstance(bounds,dict) or any(type(bounds.get(key)) not in (int,float) or not math.isfinite(bounds[key]) or bounds[key] != coverage[key] for key in ('x','y','width','height')):
        raise ValueError('Map bounds must exactly match observation coverage')
    attribution = mapping.get('attribution')
    if not isinstance(attribution,str) or not attribution.strip() or len(attribution) > 512:
        raise ValueError('Map requires attribution text up to 512 characters')
    legend = mapping.get('legend',[])
    if not isinstance(legend,list) or len(legend) > 32:
        raise ValueError('Map legend requires at most 32 entries')
    for entry in legend:
        if not isinstance(entry,dict) or not isinstance(entry.get('label'),str) or not entry['label'].strip() or len(entry['label']) > 160 or not isinstance(entry.get('color'),str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',entry['color']):
            raise ValueError('Map legend needs bounded text and RGB hex colors')
    labels = mapping.get('labels',[])
    if not isinstance(labels,list) or len(labels) > 200:
        raise ValueError('Map labels require at most 200 entries')
    for label in labels:
        if not isinstance(label,dict) or not isinstance(label.get('text'),str) or not label['text'].strip() or len(label['text']) > 160 or label.get('kind','place') not in ('street','building','shop','entrance','place'):
            raise ValueError('Invalid map label')
        for key in ('x','y'):
            numeric(label.get(key),'map label '+key,-math.inf)
        if not coverage['x'] <= label['x'] <= coverage['x']+coverage['width'] or not coverage['y'] <= label['y'] <= coverage['y']+coverage['height']:
            raise ValueError('Map label lies outside coverage')
    path = (root/'map_background.png').resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Missing or escaping map image')
    validate_png(path)
    return path


def canonical_cell(cell: dict, coverage: dict) -> tuple[int, int, int, int]:
    """Validate an ID-derived rectangle and return its finest Morton interval."""
    if not isinstance(cell, dict):
        raise ValueError('Result cells and coordination scopes must be objects')
    identity, depth = cell.get('cell_id'), cell.get('depth')
    if (type(identity) is not int or type(depth) is not int or not 1 <= depth <= coverage['leaf_depth']
            or identity >> (2 * depth) != 3):
        raise ValueError('Invalid canonical quadtree cell ID or depth')
    x, y, width, height = (coverage[key] for key in ('x', 'y', 'width', 'height'))
    for level in range(1, depth + 1):
        width /= 2
        height /= 2
        quadrant = (identity >> (2 * (depth - level))) & 3
        x += (quadrant & 1) * width
        y += (quadrant >> 1) * height
    for key, expected in (('x', x), ('y', y), ('width', width), ('height', height)):
        numeric(cell.get(key), 'cell '+key, -1e12 if key in ('x', 'y') else 0)
        tolerance = min(min(coverage['width'], coverage['height']) / 2**coverage['leaf_depth'] * 1e-4,
                        1e-6 * max(1, abs(expected), abs(cell[key])))
        if abs(cell[key] - expected) > tolerance:
            raise ValueError('Result cell geometry disagrees with its quadtree ID')
    shift = 2 * (coverage['leaf_depth'] - depth)
    return identity, depth, identity << shift, (identity + 1) << shift


def disjoint_space_time(records: list[tuple], description: str) -> None:
    """Sweep exact half-open time/Morton intervals; touching boundaries are legal."""
    events = []
    for index, (start, end, lo, hi) in enumerate(records):
        events.extend(((start, 1, lo, hi, index), (end, 0, lo, hi, index)))
    active = []
    for _, opening, lo, hi, index in sorted(events):
        token = (lo, hi, index)
        at = bisect_left(active, token)
        if not opening:
            if at == len(active) or active[at] != token:
                raise ValueError('Invalid '+description+' sweep state')
            active.pop(at)
            continue
        if (at and active[at-1][1] > lo) or (at < len(active) and active[at][0] < hi):
            raise ValueError('Overlapping space-time '+description)
        insort(active, token)


def validate_result_events(result: dict, coverage: dict, horizon, variant: str) -> None:
    parameters = result.get('parameters', {})
    if not isinstance(parameters, dict) or parameters.get('coordination', 'common_window') not in ('common_window', 'cell_local'):
        raise ValueError('Unsupported replay coordination mode')
    local = parameters.get('coordination', 'common_window') == 'cell_local'
    retirement, public_support, private, public_keys = [], [], {}, set()
    for collection, event in [('windows', 'evaluated_at_ms'), ('releases', 'sealed_at_ms')]:
        rows = result.get(collection)
        if not isinstance(rows, list):
            raise ValueError(f'{variant}: missing {collection}')
        previous = -1
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('Result event must be an object')
            stamp, start, end = row.get(event), row.get('start_ms'), row.get('end_ms')
            for value, name in ((stamp, event), (start, 'interval start'), (end, 'interval end')):
                numeric(value, name)
            if stamp < previous or stamp > horizon or not 0 <= start < end <= stamp:
                raise ValueError(f'{variant}: unordered, future-dated or invalid {collection}')
            previous = stamp
            scope = row.get('coordination_cell')
            if local:
                scope_id, scope_depth, scope_lo, scope_hi = canonical_cell(scope, coverage)
                key = (scope_id, scope_depth, start, end)
            elif scope is not None:
                raise ValueError('Common-window events cannot carry local coordination scopes')
            cells = row.get('cells')
            if not isinstance(cells, list):
                raise ValueError('Missing result cells')
            if local and collection == 'releases' and not cells:
                raise ValueError('Local public releases require selected cells')
            checked_cells, cut = {}, []
            for cell in cells:
                identity, depth, lo, hi = canonical_cell(cell, coverage)
                for name in ('observation_contributions', 'distinct_road_users'):
                    if name in cell and (type(cell[name]) is not int or cell[name] < 0):
                        raise ValueError('Recorded cell counts must be nonnegative integers')
                if cell.get('mean_sample_occupancy') is not None:
                    numeric(cell['mean_sample_occupancy'], 'mean sample occupancy')
                if local and not (scope_lo <= lo < hi <= scope_hi):
                    raise ValueError('Result cell lies outside its coordination scope')
                cut.append((lo, hi))
                checked_cells[identity] = cell
                if collection == 'releases':
                    public_support.append((start, end, lo, hi))
            cut.sort()
            if any(cut[index-1][1] > cut[index][0] for index in range(1, len(cut))):
                raise ValueError('Result cell cut contains duplicate or overlapping cells')
            if not local:
                continue
            if collection == 'windows':
                retirement.append((start, end, scope_lo, scope_hi))
                if key in private or any(type(cell.get('selected')) is not bool for cell in cells):
                    raise ValueError('Local private windows need unique scopes and Boolean selection flags')
                private[key] = (stamp, {identity: cell for identity, cell in checked_cells.items() if cell['selected']})
            else:
                expected = private.get(key)
                if expected is None or stamp < expected[0] or set(checked_cells) != set(expected[1]):
                    raise ValueError('Local release does not match its private selected scope/interval')
                if key in public_keys:
                    raise ValueError('Duplicate local public scope/interval')
                public_keys.add(key)
                for identity, cell in checked_cells.items():
                    diagnostic = expected[1][identity]
                    for name in ('observation_contributions', 'distinct_road_users', 'mean_sample_occupancy', 'semantic'):
                        if (name in cell) != (name in diagnostic) or cell.get(name) != diagnostic.get(name):
                            raise ValueError('Local release changed approved selected cell counts or semantics')
    if local:
        if any(selected and key not in public_keys for key, (_, selected) in private.items()):
            raise ValueError('Selected local private window has no corresponding public release')
        disjoint_space_time(retirement, 'private retirement')
        disjoint_space_time(public_support, 'public support')


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
    if type(coverage['leaf_depth']) is not int or not 1 <= coverage['leaf_depth'] <= 14:
        raise ValueError('Coverage requires an integer leaf depth in [1,14]')
    map_path = validate_map(root, manifest, coverage)
    if map_path:
        paths['map_background.png'] = map_path
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
        if result.get('schema') != 'ump.replay-result.v1' or any(source.get(k) != replay.get(k) for k in ('run_id', 'sensor_id', 'sampling_period_ms', 'end_ms', 'coverage')):
            raise ValueError(f'{variant["id"]}: result belongs to different observations')
        validate_result_events(result, coverage, replay['end_ms'], variant['id'])
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
            self.send_header('Content-Type', 'application/json; charset=utf-8' if source.suffix == '.json' else 'text/javascript; charset=utf-8' if source.suffix == '.js' else 'image/png' if source.suffix == '.png' else 'text/html; charset=utf-8')
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
