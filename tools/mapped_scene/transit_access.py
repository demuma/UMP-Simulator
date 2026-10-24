"""Exact frozen A1/A2 provenance and opt-in surface access geometry.

Only the two verified building=roof,layer=1 objects become overhead context.
Unknown buildings, levels and rooftops remain conservative ground obstacles.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

METADATA_SHA256 = 'b40a1e49dcf7d21b50f2b1e4ab961c257abd1b8cfe028633ff23497c850fd41c'
SOURCE_SHA256 = 'afa2690e408f467af5ff679770bf872816cc568714d9171cf4efb493809e40ed'
OVERHEAD_WAY_IDS = frozenset({425508816, 425508817})
ENTRANCE_NODE_IDS = frozenset({280355670, 348025368})
ELIGIBLE_PROFILES = frozenset({'Adult Pedestrian','Child Pedestrian','Senior Pedestrian'})


def metadata(repo, local, source_hash):
    path = repo / 'tools/osm_regions/data/moenckeberg/subway_surface_metadata.json'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=METADATA_SHA256:
        raise ValueError('Subway metadata supplement hash differs from the reviewed public evidence')
    result=json.loads(raw)
    if (result.get('schema')!='ump.subway-surface-metadata.v1'
            or source_hash!=SOURCE_SHA256 or result.get('source_geometry_sha256')!=SOURCE_SHA256
            or result.get('stop_area',{}).get('osm_id')!=300934
            or {r['node']['osm_id'] for r in result.get('entrances',[])}!=ENTRANCE_NODE_IDS
            or len(result['entrances'])!=2):
        raise ValueError('Subway access metadata does not match the exact frozen source and stop area')
    lookup={(p['osm_type'],p['osm_id']):(p,g) for p,g in local}
    roofs=set()
    for row in result['entrances']:
        node=row['node'];roof=row['overhead_roof'];surface=row['connected_surface_way']
        if node['tags'].get('railway')!='subway_entrance' or node['tags'].get('wheelchair')!='no':
            raise ValueError('Subway access identity/accessibility metadata is missing')
        p,g=lookup[('node',node['osm_id'])]
        if (p['kind']!='entrance' or g.distance(Point(node['local_point_m']))>1e-8
                or p['osm_version']!=node['version'] or p['osm_timestamp']!=node['timestamp']
                or p['tags'].get('name')!=row['name'] or node['tags'].get('ref')!=row['reference']):
            raise ValueError('Subway entrance coordinate, version or public identity differs from frozen source')
        p,g=lookup[('way',roof['osm_id'])]
        if (roof['osm_id'] not in OVERHEAD_WAY_IDS or p['kind']!='building'
                or p['tags']!={'building':'roof','layer':'1'} or roof['tags']!=p['tags']
                or not g.covers(Point(node['local_point_m']))):
            raise ValueError('Subway canopy is not the verified overhead roof')
        roofs.add(roof['osm_id'])
        p,g=lookup[('way',surface['osm_id'])]
        if p['kind']!='transport_line' or g.geom_type!='LineString' or g.distance(Point(node['local_point_m']))>1e-8:
            raise ValueError('Subway entrance lacks its exact connected surface way')
        if row['connected_steps']['tags'].get('ramp')!='no':
            raise ValueError('Subway source requires the explicit stairs accessibility assumption')
    if roofs!=OVERHEAD_WAY_IDS:
        raise ValueError('Duplicate/unknown subway canopy metadata')
    return result


def ground_environment(repo, local, layers, source_hash):
    data=metadata(repo,local,source_hash)
    ground=[(p,g) for p,g in local if not(p['kind']=='building' and p['osm_type']=='way' and p['osm_id'] in OVERHEAD_WAY_IDS)]
    adjusted=dict(layers)
    adjusted['building']=unary_union([g for p,g in ground if p['kind']=='building']).intersection(box(0,0,80,80))
    return ground,adjusted,data


def add_surface_portals(context, safe, local, data):
    lookup={(p['osm_type'],p['osm_id']):(p,g) for p,g in local}
    portals=[]
    for row in sorted(data['entrances'],key=lambda row:row['reference']):
        node=row['node'];point=node['local_point_m']
        line=lookup[('way',row['connected_surface_way']['osm_id'])][1]
        coordinates=list(line.coords)
        if math.dist(point,coordinates[0])>1e-8:
            coordinates.reverse()
        if math.dist(point,coordinates[0])>1e-8:
            raise ValueError('Subway access point must be an endpoint of its public surface approach')
        dx,dy=coordinates[1][0]-point[0],coordinates[1][1]-point[1]
        length=math.hypot(dx,dy);normal=(dx/length,dy/length);tangent=(-normal[1],normal[0])
        approach=[point[i]+normal[i]*1.5 for i in (0,1)]
        admission=[[point[i]+sign*tangent[i]*.6 for i in (0,1)] for sign in (-1,1)]
        if not safe.buffer(1e-8).covers(LineString([point,approach])) or not safe.buffer(1e-8).covers(LineString(admission)):
            raise ValueError('Exact subway surface admission does not fit existing body-safe walking geometry')
        native={'id':f"subway-{row['reference']}",'kind':'surface_access','point':copy.deepcopy(point),
                'admission_segment':admission,'approach':approach,'width_m':1.2,'provenance':'osm'}
        public=copy.deepcopy(native)
        public['surface_access']={'reference':row['reference'],'name':row['name'],'osm_node_id':node['osm_id'],
            'stop_area_id':300934,'wheelchair':'no','steps_way_id':row['connected_steps']['osm_id'],
            'ramp':'no','step_count':int(row['connected_steps']['tags']['step_count']),'scope':'surface_only'}
        portals.append(native);context['portals'].append(public)
    context['transit_access']={'schema':'ump.subway-surface-access.v1','source_geometry_sha256':SOURCE_SHA256,
        'metadata_sha256':hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),
        'overhead_roof_way_ids':sorted(OVERHEAD_WAY_IDS),'eligible_profiles':sorted(ELIGIBLE_PROFILES),
        'demand_scope':'Seeded synthetic independent one-episode station arrivals/departures; no measured passenger volumes or hidden re-identification.'}
    return portals
