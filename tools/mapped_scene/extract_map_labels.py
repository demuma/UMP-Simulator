#!/usr/bin/env python3
"""Extract a small attributed local POI-label snapshot from an existing OSM XML.

No network request or route/entrance association is performed. These labels are
map context from the source snapshot, not verified current tenants or policies.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from pyproj import Transformer


def extract(osm, policy):
    raw=Path(osm).read_bytes();definition=json.loads(Path(policy).read_text())
    transform=definition['coordinate_transform'];projection=Transformer.from_crs('EPSG:4326',transform['source_crs'],always_xy=True)
    labels=[]
    for node in ET.fromstring(raw).iter('node'):
        tags={t.attrib['k']:t.attrib['v'] for t in node.findall('tag')}
        if not tags.get('name') or not (tags.get('shop') or tags.get('amenity')):continue
        east,north=projection.transform(float(node.attrib['lon']),float(node.attrib['lat']))
        x=east-transform['x_equals_easting_minus'];y=transform['y_equals_top_northing_minus_northing']-north
        if not (0<=x<=80 and 0<=y<=80):continue
        labels.append({'text':tags['name'],'x':x,'y':y,'kind':'shop' if tags.get('shop') else 'place',
                       'osm_type':'node','osm_id':int(node.attrib['id']),
                       'osm_version':node.attrib.get('version'),'osm_timestamp':node.attrib.get('timestamp')})
    return {'schema':'ump.osm-label-snapshot.v1','attribution':'© OpenStreetMap contributors; ODbL 1.0',
            'copyright_url':'https://www.openstreetmap.org/copyright',
            'source_xml_sha256':hashlib.sha256(raw).hexdigest(),'coordinate_transform':transform,
            'bounds':{'x':0,'y':0,'width':80,'height':80},'labels':sorted(labels,key=lambda row:row['osm_id']),
            'scope':'Source-snapshot POI names only. No current-tenant verification, entrance linkage, movement destination or policy assignment.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--osm',type=Path,required=True);parser.add_argument('--policy',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=extract(args.osm,args.policy)
    with args.output.open('x') as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'status':'extracted','labels':len(result['labels']),'output':str(args.output)}))


if __name__=='__main__':main()
