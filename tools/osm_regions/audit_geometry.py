"""Independent bounded audit. Does not import or call the map-builder script."""
import argparse
import gzip
import collections
import hashlib
import json
import pathlib
import xml.etree.ElementTree as ET
import numpy as np
import shapely
from shapely.affinity import affine_transform
from shapely.geometry import Polygon, LineString, Point, box, shape
from shapely.ops import unary_union
from pyproj import Transformer

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=pathlib.Path,required=True,help='Frozen source geometry, .geojson or .gz')
parser.add_argument('--out',type=pathlib.Path,required=True,help='Existing exported overview/detail/close directory; writes audit results')
parser.add_argument('--xml',type=pathlib.Path,help='Optional original API XML for additional source reconstruction')
args=parser.parse_args()
OUT=args.out.resolve()
source_path=args.source.resolve()
source_bytes=(gzip.decompress(source_path.read_bytes()) if source_path.suffix=='.gz' else source_path.read_bytes())
source=json.loads(source_bytes)
checked=collections.Counter()
relation_count=None
max_source_discrepancy_m=None
if args.xml:
    xml_bytes=args.xml.read_bytes()
    assert hashlib.sha256(xml_bytes).hexdigest()==source['source_xml_sha256']
    xml = ET.fromstring(xml_bytes)
    project = Transformer.from_crs(4326, 25832, always_xy=True)
    coords = {n.attrib['id']:project.transform(float(n.attrib['lon']),float(n.attrib['lat'])) for n in xml.findall('node')}
    ways = {w.attrib['id']:w for w in xml.findall('way')}
    centre = project.transform(10.0015, 53.5512)
    clip = box(centre[0]-544, centre[1]-544, centre[0]+544, centre[1]+544)
    checked = collections.Counter()
    relation_count = 0
    max_source_discrepancy_m = 0
    for feature in source['features']:
        p=feature['properties']
        actual=shape(feature['geometry'])
        if p['osm_type']=='relation':
            relation_count += 1
            continue
        key=str(p['osm_id'])
        if p['osm_type']=='node':
            expected=Point(coords[key])
        else:
            pts=[coords[n.attrib['ref']] for n in ways[key].findall('nd')]
            expected=Polygon(pts) if p['kind'] in ['building','transport_area'] else LineString(pts)
        expected=shapely.make_valid(expected).intersection(clip)
        distance=float(expected.hausdorff_distance(actual))
        assert np.isfinite(distance) and distance < 1e-6, (p,distance)
        assert abs(expected.area-actual.area)<1e-5
        assert abs(expected.length-actual.length)<1e-5
        max_source_discrepancy_m=max(max_source_discrepancy_m,distance)
        checked[p['osm_type']+'/'+p['kind']] += 1


case_results={}
for case in ['overview','detail','close']:
    folder=OUT/case
    cfg=json.loads((folder/'policy.json').read_text())
    grid=cfg['grid']; side=grid['width']; step=side/64
    tf=cfg['coordinate_transform']
    left,top=tf['x_equals_easting_minus'],tf['y_equals_top_northing_minus_northing']
    domain=box(0,0,side,side)
    regions=json.loads((folder/'functional_regions.geojson').read_text())
    layers={f['properties']['class']:shape(f['geometry']) for f in regions['features']}
    cells=json.loads((folder/'cells.json').read_text())
    rows=np.asarray(cells['rows_y_south'],dtype=np.uint8)
    assert rows.shape==(64,64) and set(cells['classes'].values())=={1,2,4,8,16,32}
    y,x=np.indices((64,64))
    squares=shapely.box(x*step,y*step,(x+1)*step,(y+1)*step)
    independent=np.zeros((64,64),dtype=np.uint8)
    for category,bit in cells['classes'].items():
        geom=layers.get(category,Polygon())
        hit=shapely.area(shapely.intersection(squares,geom))>1e-8
        independent[hit]|=bit
    assert np.array_equal(independent,rows), 'Independent vector-to-raster comparison failed'
    assigned=np.zeros((64,64),dtype=np.uint8)
    ownership=np.zeros((64,64),dtype=np.uint8)
    for region in cfg['regions']:
        x0,y0,w,h=[round(region[k]/step) for k in ['x','y','width','height']]
        assigned[y0:y0+h,x0:x0+w]=region['class_mask']
        ownership[y0:y0+h,x0:x0+w]+=1
    assert np.array_equal(assigned,rows) and np.all(ownership==1)
    # Independently connect source-derived buildings and entrance buffers to output.
    buildings=[]; entrances=[]
    for feature in source['features']:
        p=feature['properties'];t=p['tags']
        geom=affine_transform(shape(feature['geometry']),[1,0,0,-1,-left,top])
        if p['kind']=='building':
            buildings.append(geom.intersection(domain))
        elif p['kind']=='entrance' and t.get('indoor')!='yes' and t.get('level','0') in ['0','0.0'] and t.get('layer','0') in ['0','0.0']:
            entrances.append(geom.buffer(3,resolution=12).intersection(domain))
    errors={}
    for category,items in [('building',buildings),('entrance',entrances)]:
        expected=shapely.make_valid(unary_union(items)).intersection(domain)
        actual=layers.get(category,Polygon())
        delta=expected.symmetric_difference(actual).area
        assert delta < 1e-6, (case,category,delta)
        errors[category+'_symmetric_difference_m2']=float(delta)
    result={'status':'pass','domain_side_m':side,'leaf_side_m':step,'independent_raster_cells_compared':4096,
            'raster_class_bits_compared':24576,'policy_rectangles_match_raster':True,
            'source_building_and_entrance_geometry_checked':True,**errors,
            'source_geometry_sha256':hashlib.sha256(source_bytes).hexdigest(),
            'policy_sha256':hashlib.sha256((folder/'policy.json').read_bytes()).hexdigest(),
            'cells_sha256':hashlib.sha256((folder/'cells.json').read_bytes()).hexdigest(),
            'transport_semantics_scope':'Vector-to-raster fidelity checked; transport class/width interpretation remains declared model assumptions.'}
    (folder/'geometry_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    case_results[case]=result
summary={'status':'pass','source_xml_sha256':source['source_xml_sha256'],
         'original_xml_reconstruction_status':'pass' if args.xml else 'not_run_raw_xml_not_supplied',
         'source_geometry_sha256':hashlib.sha256(source_bytes).hexdigest(),
         'original_xml_node_way_features_checked':dict(checked),
         'original_xml_node_way_feature_count':sum(checked.values()),
         'relation_features_not_independently_reconstructed':relation_count,
         'max_original_source_hausdorff_discrepancy_m':max_source_discrepancy_m,
         'cases':case_results}
(OUT/'geometry_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'status':'pass','original_node_way_features':sum(checked.values()),
                  'relations_excluded_from_original_reconstruction':relation_count,
                  'cases':list(case_results)}))
