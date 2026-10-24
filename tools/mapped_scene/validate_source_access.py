"""Independently bind modeled shop access to the frozen public map evidence.

A source entrance location can be authentic while the named tenant association
and a missing approach surface remain explicit modeling assumptions. Connectors
extend walking surface; they never create additional holes through buildings.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

SOURCE_SHA256='afa2690e408f467af5ff679770bf872816cc568714d9171cf4efb493809e40ed'
LABELS_SHA256='20c8054effb92f10843e8ff6c70675f888fd6bec301ef3cf607aacee1e3b4333'
SOURCE_SCOPE='Exact frozen OSM entrance point; association to the named tenant is modeled.'
CONNECTOR_PROVENANCE='synthetic_approach_to_source_osm_entrance'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def connector_surface(context, walking, buildings, domain, tolerance=1e-5):
    """Validate bounded access approaches against independent physical layers.

    This geometry-level check intentionally does not authenticate OSM metadata;
    callers exporting a frozen scene also run validate_expanded_shop_context.
    """
    portals={portal['id']:portal for portal in context.get('portals',[])}
    fronts={front['portal_id']:front for front in context.get('store_fronts',[])}
    rows=context.get('navigation',{}).get('synthetic_access_connectors',[])
    require(isinstance(rows,list) and len(rows)<=16, 'Access connectors require a bounded list')
    seen=set();bound=set();surfaces=[]
    for row in rows:
        fields={'id','portal_id','centerline','width_m','provenance'}
        require(isinstance(row,dict) and set(row)==fields, 'Invalid access connector schema')
        require(isinstance(row['id'],str) and 0<len(row['id'])<=128 and row['id'] not in seen,
                'Duplicate or invalid access connector identity')
        require(isinstance(row['portal_id'],str) and row['portal_id'] not in bound,
                'Duplicate or invalid access connector target')
        seen.add(row['id']);bound.add(row['portal_id'])
        portal=portals.get(row['portal_id']);front=fronts.get(row['portal_id'])
        require(portal is not None and portal.get('provenance')=='osm'
                and portal.get('kind')!='surface_access' and front is not None
                and front.get('provenance')=='osm_entrance_association'
                and front.get('projection_method')=='source_entrance_on_original_facade'
                and isinstance(front.get('entrance_source'),dict),
                'Access connector is not bound to a source storefront entrance')
        require(row['provenance']==CONNECTOR_PROVENANCE, 'Unknown access connector provenance')
        points=row['centerline']
        require(isinstance(points,list) and 2<=len(points)<=8, 'Access centerline must be a bounded polyline')
        for point in points:
            require(isinstance(point,list) and len(point)==2
                    and all(type(v) in (int,float) and math.isfinite(v) for v in point)
                    and domain.buffer(tolerance).covers(Point(point)),
                    'Access centerline lies outside its finite physical domain')
        width=row['width_m']
        require(type(width) in (int,float) and math.isfinite(width) and 1.2<=width<=4,
                'Access connector width must lie between 1.2 and 4 m')
        require(all(math.dist(a,b)>tolerance for a,b in zip(points,points[1:])),
                'Access centerline contains a repeated vertex')
        line=LineString(points)
        require(line.is_simple and line.length<=12, 'Access centerline must be simple and no longer than 12 m')
        require(Point(points[0]).distance(Point(portal['point']))<=tolerance,
                'Access connector does not begin at its declared entrance')
        require(line.intersection(buildings.buffer(-tolerance)).length<=tolerance,
                'Access connector crosses a building outside the declared door')
        # The far end must connect to the original walking surface with full
        # declared circular-body clearance; a center-only touch is insufficient.
        clearance=context.get('navigation',{}).get('body_clearance_m',.55)
        require(type(clearance) in (int,float) and math.isfinite(clearance) and .01<=clearance<=10,
                'Access connector requires a finite body clearance')
        require(Point(points[-1]).buffer(clearance).difference(walking).area<=tolerance,
                'Access connector does not join body-safe original walking geometry')
        surfaces.append(line.buffer(width/2,cap_style=2).intersection(domain).difference(buildings))
    return unary_union(surfaces)


def validate_expanded_shop_context(repo, local, layers, source_hash, context):
    """Authenticate expanded public access without calling the scene generator.

    Return compact audit counts. ``local`` and ``layers`` must come from the
    frozen source loader; optional verified overhead removal is compatible.
    """
    source_fronts=[front for front in context.get('store_fronts',[]) if 'entrance_source' in front
                   or front.get('provenance')=='osm_entrance_association']
    connectors=context.get('navigation',{}).get('synthetic_access_connectors',[])
    if not source_fronts and not connectors:
        return {'status':'not_applicable','source_entrances':0,'access_connectors':0}
    require(source_hash==SOURCE_SHA256, 'Expanded shop access requires the exact frozen geometry hash')
    path=Path(repo)/'tools/osm_regions/data/moenckeberg/close/poi_labels.json'
    raw=path.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==LABELS_SHA256,
            'Expanded shop access label evidence differs from the reviewed snapshot')
    labels=json.loads(raw)
    poi_lookup={(row['osm_type'],row['osm_id']):row for row in labels['labels']}
    lookup={(props['osm_type'],props['osm_id']):(props,geometry) for props,geometry in local}
    portals={portal['id']:portal for portal in context.get('portals',[])}
    buildings={building['id']:building for building in context.get('buildings',[])}
    for front in source_fronts:
        meta=front.get('entrance_source',{});portal=portals.get(front.get('portal_id'))
        require(set(meta)=={'osm_type','osm_id','osm_version','osm_timestamp','scope'}
                and meta['osm_type']=='node' and type(meta['osm_id']) is int
                and type(meta['osm_version']) is int and meta['scope']==SOURCE_SCOPE,
                'Invalid explicit source entrance metadata')
        require(front.get('provenance')=='osm_entrance_association'
                and front.get('projection_method')=='source_entrance_on_original_facade'
                and portal is not None and portal.get('provenance')=='osm'
                and portal.get('building_id')==front.get('building_id'),
                'Source storefront association disagrees with its native entrance')
        evidence=lookup.get(('node',meta['osm_id']))
        require(evidence is not None, 'Source entrance is absent from frozen map')
        props,geometry=evidence
        require(props.get('kind')=='entrance' and props.get('osm_version')==meta['osm_version']
                and props.get('osm_timestamp')==meta['osm_timestamp']
                and geometry.distance(Point(portal['point']))<=1e-8,
                'Source entrance coordinate, version or timestamp differs from frozen map')
        public_building=buildings.get(front['building_id'])
        require(public_building is not None, 'Source entrance references an unknown public building')
        building_evidence=lookup.get((public_building.get('osm_type'),int(public_building.get('osm_id',0))))
        require(building_evidence is not None and building_evidence[0].get('kind')=='building',
                'Source entrance building is absent from frozen map')
        original=building_evidence[1]
        require(original.boundary.distance(geometry)<=1e-7,
                'Source entrance is not on its declared original building boundary')
        facade=LineString(portal['facade'])
        # A source door may sit at an almost collinear wall vertex. Permit
        # only a submillimetre local tangent approximation, never an invented wall.
        require(facade.length>0 and facade.difference(original.boundary.buffer(.001)).length<=1e-5,
                'Source entrance facade differs from its original wall')
        frontage=LineString(front['frontage'])
        require(frontage.difference(original.boundary.buffer(.001)).length<=1e-5,
                'Source storefront frontage leaves its original wall')
        poi=front.get('poi',{});label=poi_lookup.get((poi.get('osm_type'),poi.get('osm_id')))
        require(label is not None and poi.get('name')==label['text']
                and math.dist(poi.get('point',[]),[label['x'],label['y']])<=1e-8,
                'Source storefront tenant label differs from frozen POI evidence')
        require(original.buffer(1e-7).covers(Point(poi['point'])),
                'Source storefront POI does not lie in the associated building')
    bounds=context['bounds'];domain=box(bounds['x'],bounds['y'],bounds['x']+bounds['width'],bounds['y']+bounds['height'])
    ground=unary_union([geometry for props,geometry in local if props['kind']=='building'])
    surface=connector_surface(context,layers['walking'],ground,domain)
    return {'status':'pass','source_geometry_sha256':source_hash,'label_evidence_sha256':LABELS_SHA256,
            'source_entrances':len(source_fronts),'access_connectors':len(connectors),
            'synthetic_access_surface_area_m2':surface.area,
            'scope':'Exact frozen entrance locations and bounded synthetic surface approaches; named tenant association is modeled.'}
