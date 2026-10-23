#!/usr/bin/env python3
"""Bounded real-OSM geometry -> D6 Region feasibility experiment.

No motion, sensor observations, aggregation decisions or privacy outcomes are generated.
"""
import argparse
import os
import tempfile
import collections
import gzip
import hashlib
import json
import math
import pathlib
import re
import xml.etree.ElementTree as ET

os.environ.setdefault('MPLCONFIGDIR', str(pathlib.Path(tempfile.gettempdir())/'ump-osm-mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch, Polygon as MplPolygon, Rectangle
from matplotlib.path import Path
from matplotlib.patches import PathPatch
import numpy as np
from pyproj import Transformer
from shapely import make_valid
from shapely.affinity import affine_transform
from shapely.geometry import Point, LineString, Polygon, box, shape, mapping
from shapely.ops import polygonize, transform, unary_union
from shapely.prepared import prep

CLASSES = ['road', 'walking', 'cycling', 'building', 'entrance', 'crossing']
BITS = {name: 1 << i for i, name in enumerate(CLASSES)}
COLORS = {'background': '#F4F5F7', 'road': '#E4B66B', 'walking': '#58AC9B',
          'cycling': '#658ECC', 'building': '#B8C1CE', 'entrance': '#D5693A', 'crossing': '#A477BC'}
LABELS = {'background': 'Unclassified / root policy', 'road': 'Road corridor',
          'walking': 'Walking corridor / area', 'cycling': 'Cycling / shared corridor',
          'building': 'Building footprint', 'entrance': 'Entrance vicinity (3 m)',
          'crossing': 'Crossing corridor'}
PRIORITY = ['building', 'road', 'walking', 'cycling', 'crossing', 'entrance']
KEEP_TAGS = {'name', 'highway', 'area', 'area:highway', 'building', 'entrance', 'width',
             'est_width', 'lanes', 'foot', 'bicycle', 'access', 'motor_vehicle',
             'sidewalk', 'sidewalk:both', 'sidewalk:left', 'sidewalk:right',
             'cycleway', 'cycleway:both', 'cycleway:left', 'cycleway:right',
             'layer', 'level', 'tunnel', 'bridge', 'indoor', 'footway', 'segregated', 'surface'}
PROJECT = Transformer.from_crs('EPSG:4326', 'EPSG:25832', always_xy=True)


def tags(element):
    return {t.attrib['k']: t.attrib['v'] for t in element.findall('tag')}


def poly_parts(geom):
    if geom.geom_type == 'Polygon':
        yield geom
    elif hasattr(geom, 'geoms'):
        for sub in geom.geoms:
            yield from poly_parts(sub)


def freeze(xml_path, output):
    root = ET.parse(xml_path).getroot()
    nodes = {n.attrib['id']: n for n in root.findall('node')}
    coords = {i: PROJECT.transform(float(n.attrib['lon']), float(n.attrib['lat'])) for i, n in nodes.items()}
    ways = {w.attrib['id']: w for w in root.findall('way')}
    features, issues = [], collections.Counter()
    # Leave margin within the downloaded bounding box; roads can extend outside it.
    cx, cy = PROJECT.transform(10.0015, 53.5512)
    clip = box(cx-544, cy-544, cx+544, cy+544)  # Retain 32 m margin for boundary corridors.

    def append(geom, kind, e, source_tags):
        if geom is None or geom.is_empty:
            return
        geom = make_valid(geom).intersection(clip)
        if geom.is_empty:
            return
        features.append({'type': 'Feature', 'geometry': mapping(geom), 'properties': {
            'osm_type': e.tag, 'osm_id': int(e.attrib['id']), 'osm_version': int(e.attrib.get('version', 0)),
            'osm_timestamp': e.attrib.get('timestamp'), 'kind': kind,
            'tags': {k: v for k, v in source_tags.items() if k in KEEP_TAGS}}})

    for way in ways.values():
        t = tags(way)
        refs = [a.attrib['ref'] for a in way.findall('nd')]
        if not (t.get('building') not in (None, 'no') or 'highway' in t or 'area:highway' in t):
            continue
        if not refs or any(i not in coords for i in refs):
            issues['incomplete_ways_skipped'] += 1
            continue
        pts = [coords[i] for i in refs]
        if t.get('building') not in (None, 'no') and len(pts) >= 4 and refs[0] == refs[-1]:
            append(Polygon(pts), 'building', way, t)
        if t.get('area:highway') or ('highway' in t and t.get('area') == 'yes'):
            if len(pts) >= 4 and refs[0] == refs[-1]:
                append(Polygon(pts), 'transport_area', way, t)
            else:
                issues['unclosed_transport_areas_skipped'] += 1
        elif 'highway' in t and len(pts) >= 2:
            append(LineString(pts), 'transport_line', way, t)

    for relation in root.findall('relation'):
        t = tags(relation)
        if not (t.get('type') == 'multipolygon' and
                (t.get('building') not in (None, 'no') or 'area:highway' in t or 'highway' in t)):
            continue
        lines = {'outer': [], 'inner': []}
        incomplete = False
        for member in relation.findall('member'):
            if member.attrib['type'] != 'way':
                continue
            w = ways.get(member.attrib['ref'])
            if w is None:
                incomplete = True
                break
            refs = [n.attrib['ref'] for n in w.findall('nd')]
            if any(i not in coords for i in refs) or len(refs) < 2:
                incomplete = True
                break
            lines['inner' if member.attrib.get('role') == 'inner' else 'outer'].append(LineString([coords[i] for i in refs]))
        if incomplete:
            issues['incomplete_multipolygon_relations_skipped'] += 1
            continue
        outer = unary_union(list(polygonize(unary_union(lines['outer']))))
        inner = unary_union(list(polygonize(unary_union(lines['inner']))))
        geom = outer.difference(inner)
        append(geom, 'building' if 'building' in t else 'transport_area', relation, t)

    for n in nodes.values():
        t = tags(n)
        if t.get('entrance') not in (None, 'no'):
            append(Point(coords[n.attrib['id']]), 'entrance', n, t)

    # Stable order and trimmed public metadata. No user names or unrelated map nodes are retained.
    features.sort(key=lambda f: (f['properties']['osm_type'], f['properties']['osm_id'], f['properties']['kind']))
    body = {'type': 'FeatureCollection', 'name': 'Monckebergstrasse OSM source geometry',
            'coordinate_reference_system': 'EPSG:25832; easting/northing metres (not RFC7946 lon/lat GeoJSON)',
            'attribution': '© OpenStreetMap contributors; ODbL 1.0',
            'source_bbox_lon_lat': [9.9925, 53.5455, 10.0165, 53.5565],
            'source_xml_sha256': hashlib.sha256(xml_path.read_bytes()).hexdigest(),
            'issues': dict(issues), 'features': features}
    output.write_text(json.dumps(body, separators=(',', ':'), ensure_ascii=False) + '\n')
    return body


def number(value):
    if value is None:
        return None
    value = str(value).strip()
    # Avoid silently interpreting compound values, estimated ranges or feet.
    match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:m)?', value)
    return float(match[1]) if match else None


def transport_class(t):
    h = t.get('area:highway', t.get('highway'))
    if t.get('footway') == 'crossing':
        return 'crossing'
    if h == 'cycleway':
        return 'cycling'
    if h in {'footway', 'path', 'pedestrian', 'steps', 'corridor'}:
        return 'walking'
    if h in {'residential', 'service', 'living_street', 'unclassified', 'tertiary',
             'secondary', 'primary', 'trunk', 'motorway', 'busway', 'bus_guideway',
             'primary_link', 'secondary_link', 'tertiary_link', 'trunk_link', 'motorway_link'}:
        return 'road'
    return None


def corridor_layers(data, left, top, side):
    domain = box(0, 0, side, side)
    pieces = {c: [] for c in CLASSES}
    counts = collections.Counter()
    assumptions = []
    landmarks = []
    shift = [1, 0, 0, -1, -left, top]  # x=east, y=south, matching simulator screen axes.
    for f in data['features']:
        p, t = f['properties'], f['properties']['tags']
        geom = affine_transform(shape(f['geometry']), shift)
        if geom.distance(domain) > 32:
            continue
        if p['kind'] == 'building':
            pieces['building'].append(geom.intersection(domain))
            counts['building_source_features'] += 1
            continue
        if p['kind'] == 'entrance':
            if t.get('indoor') == 'yes' or t.get('level', '0') not in {'0', '0.0'} or t.get('layer', '0') not in {'0', '0.0'}:
                counts['non_ground_entrances_skipped'] += 1
                continue
            pieces['entrance'].append(geom.buffer(3, resolution=12).intersection(domain))
            counts['entrance_nodes'] += 1
            assumptions.append({'source': f"{p['osm_type']}/{p['osm_id']}", 'kind': 'entrance_vicinity', 'radius_m': 3})
            continue
        # A 2D proof of concept omits explicitly underground/indoor/nonzero-level routes.
        if t.get('tunnel') in {'yes', 'building_passage'} or t.get('indoor') == 'yes' or t.get('level', '0') not in {'0', '0.0'} or t.get('layer', '0') not in {'0', '0.0'}:
            counts['non_ground_routes_skipped'] += 1
            continue
        if t.get('bridge') == 'yes' and 'layer' not in t:
            counts['bridge_without_layer_kept_in_2d'] += 1
        category = transport_class(t)
        if category is None:
            counts['unhandled_transport_features'] += 1
            continue
        if p['kind'] == 'transport_area':
            pieces[category].append(geom.intersection(domain))
            counts['explicit_transport_areas'] += 1
            if category in {'walking', 'crossing'} and t.get('bicycle') in {'yes', 'designated', 'permissive', 'official'}:
                pieces['cycling'].append(geom.intersection(domain))
                counts['shared_walking_cycling_areas'] += 1
            elif category == 'cycling' and t.get('foot') in {'yes', 'designated', 'permissive', 'official'}:
                pieces['walking'].append(geom.intersection(domain))
                counts['shared_walking_cycling_areas'] += 1
            continue
        explicit_width = number(t.get('width'))
        default = {'road': 6, 'walking': 2.5, 'cycling': 2.5, 'crossing': 3}[category]
        if t.get('highway') == 'pedestrian':
            default = 10
        if t.get('highway') == 'service':
            default = 4
        lanes = number(t.get('lanes'))
        if category == 'road' and lanes:
            default = max(default, lanes * 3)
        width = explicit_width if explicit_width and explicit_width > 0 else default
        pieces[category].append(geom.buffer(width/2, cap_style=2, join_style=2).intersection(domain))
        counts['line_width_from_osm' if explicit_width else 'line_width_assumed'] += 1
        if explicit_width is None:
            assumptions.append({'source': f"{p['osm_type']}/{p['osm_id']}", 'kind': 'line_width', 'width_m': width})
        # Shared paths preserve both functions on the SAME corridor; no offset is invented.
        shared = ((category in {'walking', 'crossing'} and t.get('bicycle') in {'yes', 'designated', 'permissive', 'official'})
                  or (category == 'cycling' and t.get('foot') in {'yes', 'designated', 'permissive', 'official'}))
        if shared:
            second = 'cycling' if category in {'walking', 'crossing'} else 'walking'
            pieces[second].append(geom.buffer(width/2, cap_style=2, join_style=2).intersection(domain))
            counts['shared_walking_cycling_lines'] += 1
        # Attribute-only sidewalk / cycle lane is recorded as unresolved, never invented at an offset.
        for prefix in ['sidewalk', 'cycleway']:
            if any(k.startswith(prefix) and v not in {'no', 'none', 'separate'} for k, v in t.items()):
                counts[prefix + '_attribute_features_unresolved'] += 1
        if t.get('name') in {'Mönckebergstraße', 'Spitalerstraße', 'Steinstraße', 'Lange Mühren'}:
            landmarks.append((t['name'], geom.intersection(domain)))
    layers = {c: make_valid(unary_union(v)).intersection(domain) for c, v in pieces.items()}
    return layers, dict(counts), assumptions, landmarks


def cell_id(x, y, depth=6):
    result = 3
    for bit in range(depth-1, -1, -1):
        result = (result << 2) | ((x >> bit) & 1) | (((y >> bit) & 1) << 1)
    return result


def coalesce(mask):
    # Vertical extension of identical horizontal runs: rectangles are exact and disjoint.
    active, finished = {}, []
    for y in range(64):
        runs, x = [], 0
        while x < 64:
            start, value = x, int(mask[y, x])
            while x < 64 and int(mask[y, x]) == value:
                x += 1
            runs.append((start, x, value))
        current = {}
        for run in runs:
            if run in active:
                current[run] = active.pop(run)
                current[run][3] += 1
            else:
                current[run] = [run[0], y, run[1]-run[0], 1, run[2]]
        finished.extend(active.values())
        active = current
    finished.extend(active.values())
    return sorted(finished, key=lambda r: (r[1], r[0]))


def raster(layers, side):
    step = side / 64
    masks = np.zeros((64, 64), dtype=np.uint8)
    stats = {}
    for c, geom in layers.items():
        prepared = prep(geom)
        covered = []
        for y in range(64):
            for x in range(64):
                cell = box(x*step, y*step, (x+1)*step, (y+1)*step)
                # Positive area only. Edge touches do not contribute policy requirements.
                if prepared.intersects(cell) and geom.intersection(cell).area > 1e-8:
                    masks[y, x] |= BITS[c]
                    covered.append(cell)
        area = len(covered)*step*step
        stats[c] = {'original_area_m2': geom.area, 'raster_covered_area_m2': area,
                    'expansion_m2': area-geom.area, 'covered_leaf_count': len(covered)}
    rectangles = coalesce(masks)
    reconstructed = np.zeros_like(masks)
    ownership = np.zeros_like(masks, dtype=int)
    for x, y, w, h, value in rectangles:
        reconstructed[y:y+h, x:x+w] = value
        ownership[y:y+h, x:x+w] += 1
    assert np.array_equal(reconstructed, masks) and np.all(ownership == 1)
    return masks, rectangles, stats


def requirements(mask, step):
    rules = {
        'road': (5, step*4, 1000), 'walking': (5, step*2, 4000),
        'cycling': (5, step*4, 1000), 'building': (1, step*8, 4000),
        'entrance': (10, step*2, 4000), 'crossing': (5, step*2, 400)}
    selected = [rules[c] for c in CLASSES if mask & BITS[c]]
    if not selected:
        return {}
    return {'distinct_contributors': {'min': max(r[0] for r in selected)},
            'cell_side_m': {'max': min(r[1] for r in selected)},
            'window_duration_ms': {'max': min(r[2] for r in selected)},
            'age_at_evaluation_ms': {'max': min(r[2] for r in selected)}}


def export_case(name, centre, side, data, out):
    cx, cy = PROJECT.transform(*centre)
    left, top = cx-side/2, cy+side/2
    layers, counts, assumptions, landmarks = corridor_layers(data, left, top, side)
    masks, rects, areas = raster(layers, side)
    folder = out/name
    folder.mkdir(parents=True, exist_ok=True)
    step = side/64
    root = {'distinct_contributors': {'min': 1}, 'min_category_distinct_contributors': {'min': 5}, 'cell_side_m': {'min': step, 'max': step*8},
            'window_duration_ms': {'min': 400, 'max': 4000}, 'age_at_evaluation_ms': {'max': 4000},
            'semantic_max_loss': {'max': 1}}
    regions = []
    for i, (x,y,w,h,value) in enumerate(rects):
        kind = '__'.join(c for c in CLASSES if value & BITS[c]) or 'background'
        regions.append({'id': f'{name}-patch-{i:04}', 'type': 'osm_'+kind,
                        'x': x*step, 'y': y*step, 'width': w*step, 'height': h*step,
                        'type_requirements': requirements(value, step), 'requirements': {},
                        'class_mask': value})
    config = {'grid': {'x': 0, 'y': 0, 'width': side, 'height': side, 'leaf_depth': 6},
              'root_requirements': root, 'regions': regions,
              'status': 'Illustrative geometry/PolicyTree compilation probe; not a validated privacy policy',
              'coordinate_transform': {'source_crs': 'EPSG:25832', 'x_equals_easting_minus': left,
                                       'y_equals_top_northing_minus_northing': top}}
    (folder/'policy.json').write_text(json.dumps(config, separators=(',', ':'))+'\n')
    # Exact raster source for independent audit; no trajectory/person data.
    (folder/'cells.json').write_text(json.dumps({'cell_side_m': step, 'depth': 6,
        'classes': BITS, 'rows_y_south': masks.tolist()}, separators=(',', ':'))+'\n')
    area_features = [{'type':'Feature', 'properties':{'class': c}, 'geometry': mapping(g)} for c,g in layers.items() if not g.is_empty]
    (folder/'functional_regions.geojson').write_text(json.dumps({'type':'FeatureCollection',
        'coordinate_reference_system':'local metres, x east / y south', 'features':area_features}, separators=(',', ':'))+'\n')
    stats = {'domain_side_m': side, 'leaf_side_m': step, 'possible_leaves': 4096,
             'nonempty_functional_leaves': int(np.count_nonzero(masks)),
             'mixed_function_leaves': int(sum(bin(int(v)).count('1')>1 for v in masks.flat)),
             'rectangle_count': len(rects), 'class_areas': areas, 'source_counts': counts,
             'assumptions': assumptions,
             'cell_id_min': min(cell_id(x,y) for x in range(64) for y in range(64)),
             'cell_id_max': max(cell_id(x,y) for x in range(64) for y in range(64))}
    (folder/'summary.json').write_text(json.dumps(stats, indent=2)+'\n')
    return {'name':name, 'side':side, 'step':step, 'left':left, 'top':top,
            'layers':layers, 'mask':masks, 'landmarks':landmarks, 'stats':stats}


def polygon_path(poly):
    vertices, codes = [], []
    for ring in [poly.exterior, *poly.interiors]:
        xy = list(ring.coords)
        vertices.extend(xy)
        codes.extend([Path.MOVETO] + [Path.LINETO]*(len(xy)-2) + [Path.CLOSEPOLY])
    return Path(vertices, codes)


def draw_polygons(ax, geom, color, alpha=1, edge='none', lw=.3, z=2):
    for p in poly_parts(geom):
        ax.add_patch(PathPatch(polygon_path(p), facecolor=color, edgecolor=edge, linewidth=lw, alpha=alpha, zorder=z))


def decorate(ax, case, title, subtitle, labels=False):
    side = case['side']
    ax.set(xlim=(0,side), ylim=(side,0), aspect='equal')
    ax.set_facecolor(COLORS['background'])
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color('#CAD1DA')
    ax.text(0,1.085,title,transform=ax.transAxes,fontsize=16,fontweight='bold',color='#172D43')
    ax.text(0,1.035,subtitle,transform=ax.transAxes,fontsize=11,color='#53657A')
    ax.annotate('N', xy=(.95,.92), xytext=(.95,.82), xycoords='axes fraction',
                ha='center', fontsize=11, color='#263B50', arrowprops={'arrowstyle':'-|>','color':'#263B50','lw':1.3})
    length=200 if side>500 else 25 if side>=160 else 10
    x0,y0=side*.045,side*.95
    ax.plot([x0,x0+length],[y0,y0],color='#1E3449',lw=3,zorder=10)
    ax.text(x0,y0-side*.025,f'{length} m',color='#1E3449',fontsize=10,zorder=11)
    if labels:
        # Label one longest mapped segment per selected street.
        for name in ['Mönckebergstraße','Spitalerstraße','Steinstraße']:
            segments=[g for n,g in case['landmarks'] if n==name and g.length>0]
            if not segments: continue
            line=max(segments,key=lambda g:g.length)
            if line.geom_type != 'LineString': continue
            p=line.interpolate(.5,normalized=True)
            ends=list(line.coords)
            angle=math.degrees(math.atan2(-(ends[-1][1]-ends[0][1]), ends[-1][0]-ends[0][0]))
            if angle>90: angle-=180
            if angle< -90: angle+=180
            ax.text(p.x,p.y-side*.012,name,ha='center',va='center',rotation=angle,
                    fontsize=10 if side>500 else 11,color='#172D43',zorder=12,
                    bbox={'facecolor':'white','alpha':.88,'edgecolor':'none','pad':1.5})


def draw_vector(ax, case, title, subtitle, labels=False):
    for c in PRIORITY:
        draw_polygons(ax,case['layers'][c],COLORS[c], edge='white', lw=.3)
    decorate(ax,case,title,subtitle,labels)


def draw_raster(ax, case, title, subtitle):
    rgba=np.empty((64,64,4))
    from matplotlib.colors import to_rgba
    for y in range(64):
        for x in range(64):
            value=int(case['mask'][y,x])
            chosen='background'
            for c in PRIORITY:
                if value & BITS[c]: chosen=c
            rgba[y,x]=to_rgba(COLORS[chosen])
    ax.imshow(rgba,extent=(0,case['side'],case['side'],0),interpolation='nearest',zorder=1)
    # White slash means ALL intersected requirements are retained despite one fill colour.
    segments=[]
    step=case['step']
    for y in range(64):
        for x in range(64):
            if bin(int(case['mask'][y,x])).count('1')>1:
                segments.append([(x*step+.2*step,(y+1)*step-.2*step),((x+1)*step-.2*step,y*step+.2*step)])
    ax.add_collection(LineCollection(segments,colors='white',linewidths=.9,alpha=.95,zorder=3))
    grid=[]
    for i in range(65):
        grid.extend([[(i*step,0),(i*step,case['side'])],[(0,i*step),(case['side'],i*step)]])
    ax.add_collection(LineCollection(grid,colors='#61718A',linewidths=.23,alpha=.42,zorder=4))
    for c in ['building','road','walking','cycling','crossing']:
        draw_polygons(ax,case['layers'][c], 'none', edge='#354456',lw=.3,z=5)
    decorate(ax,case,title,subtitle)


def figures(overview,detail,close,out):
    plt.rcParams.update({'font.family':'DejaVu Sans', 'svg.fonttype':'none', 'svg.hashsalt':'ump-osm-feasibility-v1'})
    fig,axes=plt.subplots(1,3,figsize=(18,7.6))
    fig.subplots_adjust(left=.035,right=.98,top=.80,bottom=.20,wspace=.10)
    fig.text(.035,.955,'MÖNCKEBERGSTRASSE · HAMBURG',fontsize=24,fontweight='bold',color='#172D43')
    fig.text(.035,.907,'Real map geometry → functional regions → separate D6 sensing footprints',fontsize=15,color='#53657A')
    draw_vector(axes[0],overview,'A  Functional map','1,024 × 1,024 m · map + declared buffers',True)
    draw_raster(axes[1],overview,'B  Whole-area D6','64 × 64 cells · each cell 16 × 16 m')
    draw_raster(axes[2],detail,'C  Local D6','160 × 160 m · each cell 2.5 × 2.5 m')
    for ax in axes[:2]:
        dx=detail['left']-overview['left'];dy=overview['top']-detail['top']
        ax.add_patch(Rectangle((dx,dy),160,160,fill=False,edgecolor='#E05237',linewidth=2.2,zorder=14))
    handles=[Patch(facecolor=COLORS[c],label=LABELS[c]) for c in ['walking','road','cycling','building','entrance','crossing']]
    fig.legend(handles=handles,loc='lower left',bbox_to_anchor=(.03,.105),ncol=3,frameon=False,fontsize=11,columnspacing=2.5)
    fig.text(.035,.077,'White slash = mixed cell: all requirements retained. Red box = separate local footprint, not a refinement of panel B.',fontsize=10,color='#53657A')
    fig.text(.035,.046,'Widths without explicit OSM values are assumptions; orange entrance vicinities use a declared 3 m radius. Geometry test only.',fontsize=9.5,color='#53657A')
    fig.text(.035,.019,'© OpenStreetMap contributors · ODbL 1.0 · openstreetmap.org/copyright  |  UMP-Simulator · 23 Oct 2026',fontsize=9,color='#53657A')
    fig.savefig(out/'monckeberg_regions_d6.png',dpi=180,facecolor='white')
    fig.savefig(out/'monckeberg_regions_d6.svg',facecolor='white',metadata={'Date':None})
    plt.close(fig)

    fig,axes=plt.subplots(1,3,figsize=(18,7.6))
    fig.subplots_adjust(left=.035,right=.98,top=.80,bottom=.20,wspace=.10)
    fig.text(.035,.955,'MÖNCKEBERGSTRASSE · LOCAL RESOLUTION',fontsize=23,fontweight='bold',color='#172D43')
    fig.text(.035,.907,'A smaller sensing footprint preserves fine detail at the same quadtree depth',fontsize=15,color='#53657A')
    draw_vector(axes[0],detail,'A  Source-derived regions','160 × 160 m · projected OSM geometry',True)
    draw_raster(axes[1],detail,'B  D6 / 160 m','64 × 64 cells · each cell 2.5 × 2.5 m')
    draw_raster(axes[2],close,'C  D6 / 80 m','64 × 64 cells · each cell 1.25 × 1.25 m')
    dx=close['left']-detail['left'];dy=detail['top']-close['top']
    for ax in axes[:2]:
        ax.add_patch(Rectangle((dx,dy),80,80,fill=False,edgecolor='#E05237',linewidth=2,zorder=14))
    fig.legend(handles=handles,loc='lower left',bbox_to_anchor=(.03,.105),ncol=3,frameon=False,fontsize=11,columnspacing=2.5)
    fig.text(.035,.077,'White slash = mixed cell: all requirements retained. Each raster panel uses a separate D6 root domain.',fontsize=10,color='#53657A')
    fig.text(.035,.046,'Assumed line widths and 3 m entrance vicinities are explicit model inputs. This is no movement or privacy experiment.',fontsize=9.5,color='#53657A')
    fig.text(.035,.019,'© OpenStreetMap contributors · ODbL 1.0 · openstreetmap.org/copyright  |  UMP-Simulator · 23 Oct 2026',fontsize=9,color='#53657A')
    fig.savefig(out/'monckeberg_regions_detail.png',dpi=180,facecolor='white')
    fig.savefig(out/'monckeberg_regions_detail.svg',facecolor='white',metadata={'Date':None})
    plt.close(fig)
    # Matplotlib emits trailing spaces in SVG path data; keep generated files clean.
    for path in out.glob('monckeberg_regions*.svg'):
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml',type=pathlib.Path)
    parser.add_argument('--source',type=pathlib.Path)
    parser.add_argument('--out',type=pathlib.Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    source=args.out/'source_geometry.geojson'
    if args.xml:
        data=freeze(args.xml,source)
    else:
        if not args.source: parser.error('supply --xml or --source')
        data=json.loads(gzip.decompress(args.source.read_bytes()) if args.source.suffix == '.gz' else args.source.read_bytes())
        if args.source.resolve()!=source.resolve(): source.write_text(json.dumps(data,separators=(',', ':'),ensure_ascii=False)+'\n')
    overview=export_case('overview',(10.0015,53.5512),1024,data,args.out)
    detail=export_case('detail',(10.0010,53.5512),160,data,args.out)
    close=export_case('close',(10.0010,53.5512),80,data,args.out)
    figures(overview,detail,close,args.out)
    summary={'status':'geometry and policy compilation feasibility only',
             'source_features':len(data['features']), 'source_issues':data.get('issues',{}),
             'cases':{c['name']:c['stats'] for c in [overview,detail,close]}}
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'source_features':len(data['features']),'cases':{
        c['name']:{k:v for k,v in c['stats'].items() if k in ['domain_side_m','leaf_side_m','rectangle_count','mixed_function_leaves','source_counts']}
        for c in [overview,detail,close]}},indent=2))


if __name__=='__main__':
    main()
