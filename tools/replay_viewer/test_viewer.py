#!/usr/bin/env python3
"""Validate the viewer data boundary and local serving scope without a browser."""
import copy
import hashlib
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import struct
import zlib
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import urlopen

import serve
import prepare_local_bundle


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.replay = {'schema':'ump.observation-replay.v1','run_id':'test','sensor_id':'agbs',
            'coverage':{'x':0,'y':0,'width':80,'height':80,'leaf_depth':2},
            'sampling_period_ms':100,'end_ms':500,'batches':[
                {'observed_at_ms':100,'status':'measured','observations':[{'id':'one','type':'Adult Pedestrian','x':1,'y':2}]},
                {'observed_at_ms':200,'status':'measured','observations':[]}]}
        cell = {'cell_id':12,'depth':1,'x':0,'y':0,'width':40,'height':40,'observation_contributions':1}
        self.result = {'schema':'ump.replay-result.v1',
            'source':{k:v for k,v in self.replay.items() if k in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms')},
            'releases':[{'start_ms':0,'end_ms':400,'sealed_at_ms':400,'cells':[cell]}],
            'windows':[{'start_ms':0,'end_ms':400,'evaluated_at_ms':400,'cells':[{**cell,'selected':True}]}]}
        self.manifest = {'schema':serve.SCHEMA,'observations':'observations.json',
            'variants':[{'id':'fixed','label':'Fixed <not markup>','result':'result.json'}]}
        self.write()

    def tearDown(self):
        self.directory.cleanup()

    def write(self):
        for name,data in [('bundle.json',self.manifest),('observations.json',self.replay),('result.json',self.result)]:
            (self.root/name).write_text(json.dumps(data),encoding='utf-8')

    def rejected(self):
        self.write()
        with self.assertRaises(ValueError):
            serve.validate_bundle(self.root)

    def add_transit_access(self):
        value=self.add_storefront_access()
        value['transit_access']={'schema':'ump.subway-surface-access.v1',
            'source_geometry_sha256':'a'*64,'metadata_sha256':'b'*64,
            'overhead_roof_way_ids':[425508816,425508817],
            'eligible_profiles':['Adult Pedestrian','Child Pedestrian','Senior Pedestrian'],
            'demand_scope':'Synthetic independent station journeys.'}
        for ref,node,x in [('A1',280355670,40),('A2',348025368,50)]:
            value['portals'].append({'id':'subway-'+ref,'kind':'surface_access','point':[x,40],
                'admission_segment':[[x-.6,40],[x+.6,40]],'approach':[x,41.5],
                'width_m':1.2,'provenance':'osm','surface_access':{
                    'reference':ref,'name':'Station '+ref,'osm_node_id':node,'stop_area_id':300934,
                    'wheelchair':'no','steps_way_id':123,'ramp':'no','step_count':24,'scope':'surface_only'}})
        return value

    def test_surface_access_is_not_a_facade_and_rejects_private_or_inconsistent_metadata(self):
        value=self.add_transit_access()
        (self.root/'building_access.json').write_text(json.dumps(value));self.write()
        serve.validate_bundle(self.root)
        for failure in ('private','missing_second','off_center','parallel','wrong_node','stairs','roof','crossing'):
            with self.subTest(failure=failure):
                value=self.add_transit_access();portal=value['portals'][1]
                if failure=='private':portal['surface_access']['private_person_id']='secret'
                if failure=='missing_second':value['portals'].pop()
                if failure=='off_center':portal['point'][0]+=.1
                if failure=='parallel':portal['approach']=[41.5,40]
                if failure=='wrong_node':portal['surface_access']['osm_node_id']=1
                if failure=='stairs':value['transit_access']['eligible_profiles'].append('Pedestrian With Mobility Aid')
                if failure=='roof':value['buildings'][0].update(overhead=True,ground_obstacle=False)
                if failure=='crossing':value['navigation']['crossing_priority']={'resources':[],'scope':'Synthetic'}
                (self.root/'building_access.json').write_text(json.dumps(value));self.rejected()

    def test_matching_bundle_validates(self):
        _,files=serve.validate_bundle(self.root)
        self.assertEqual(set(files),{'bundle.json','observations.json','result.json'})

    @staticmethod
    def png(width=2, height=2, *, depth=8, color=6, interlace=0, pixels=None):
        def chunk(kind,payload):
            return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
        if pixels is None:
            channels=3 if color==2 else 4
            pixels=(b'\x00'+b'\xff'*width*channels)*height
        return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,depth,color,0,0,interlace))
                +chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b''))

    def add_map(self):
        self.manifest['identity_unit']='visible_episode_track'
        self.manifest['input_provenance']='Native mapped pedestrian test; recorded observations, not interpolated positions.'
        self.manifest['map']={'image':'map_background.png',
            'bounds':{key:self.replay['coverage'][key] for key in ('x','y','width','height')},
            'attribution':'© OpenStreetMap contributors',
            'legend':[{'label':'Walking area','color':'#e8dfce'}],
            'labels':[{'text':'Mönckebergstraße','x':40,'y':50,'kind':'street'}]}
        (self.root/'map_background.png').write_bytes(self.png())
        return self.manifest['map']

    def add_building_access(self):
        self.add_map()['building_access']='building_access.json'
        value={'schema':'ump.building-access.v1','bounds':dict(x=0,y=0,width=80,height=80),
               'buildings':[{'id':'way1','name':'Example building','osm_type':'way','osm_id':1,
                             'building_type':'retail','polygons':[[[10,10],[30,10],[30,30],[10,30],[10,10]]]}],
               'portals':[{'id':'door1','building_id':'way1','point':[20,10],
                           'facade':[[10,10],[30,10]],'width_m':1.2,'provenance':'synthetic'}]}
        (self.root/'building_access.json').write_text(json.dumps(value))
        return value

    def add_storefront_access(self):
        value=self.add_building_access();value['schema']='ump.building-access.v2'
        value['portals'][0]['point']=[18,10]  # Projection need not be facade midpoint.
        value.update(store_fronts=[{'id':'front1','destination_id':'shop1','building_id':'way1',
            'poi':{'osm_type':'node','osm_id':2,'name':'Example shop','point':[18,16]},
            'portal_id':'door1','frontage':[[10,10],[25,10]],'provenance':'synthetic_poi_projection',
            'projection_method':'orthogonal_to_reachable_original_facade'}],
            facade_separators=[{'id':'divider1','building_id':'way1','points':[[25,10],[25,11]],
                'provenance':'synthetic_frontage_division_not_interior_wall'}],
            boundary_intervals=[{'id':'walk-west','mode':'walking','side':'west',
                'points':[[0,40],[0,60]],'length_m':20,'spawn_supported':True,
                'provenance':'derived_frozen_functional_zone_boundary'}],
            navigation={'body_clearance_m':.55,'allowed_center_polygons_sha256':'a'*64,
                'scope':'Bounded body-clearance navigation, not inferred indoor walls.'})
        (self.root/'building_access.json').write_text(json.dumps(value));return value

    def test_storefront_v2_non_midpoint_entrance_and_boundary_geometry_validate(self):
        value=self.add_storefront_access();self.write();serve.validate_bundle(self.root)
        for mode in ('cycling','road'):
            value['boundary_intervals'][0].update(mode=mode,spawn_supported=False)
            (self.root/'building_access.json').write_text(json.dumps(value));serve.validate_bundle(self.root)

    def add_mixed_traffic_access(self):
        value=self.add_storefront_access()
        value['boundary_intervals'].append({'id':'road-west','mode':'road','side':'west',
            'points':[[0,30],[0,36]],'length_m':6,'spawn_supported':True,
            'provenance':'synthetic_rider_source_on_body_safe_frozen_carriageway'})
        value['navigation'].update(spaces=[{'id':'carriageway-east','mode':'road','body_clearance_m':1.05,
            'allowed_center_polygons_sha256':'b'*64}],synthetic_crossing_connectors=[{
                'id':'crossing-1','centerline':[[30,25],[30,45]],'width_m':4,
                'provenance':'synthetic_crossing_and_curb_gap_connector'}])
        (self.root/'building_access.json').write_text(json.dumps(value));return value

    def test_mixed_traffic_navigation_spaces_and_declared_road_sources_validate(self):
        self.add_mixed_traffic_access();self.write();serve.validate_bundle(self.root)

    def test_disabled_road_source_keeps_its_construction_provenance_as_context(self):
        value=self.add_mixed_traffic_access();boundary=value['boundary_intervals'][-1]
        boundary['spawn_supported']=False
        before=copy.deepcopy(boundary)
        (self.root/'building_access.json').write_text(json.dumps(value));self.write()
        serve.validate_bundle(self.root)
        self.assertEqual(json.loads((self.root/'building_access.json').read_text())['boundary_intervals'][-1],before)
        self.assertEqual(boundary['provenance'],'synthetic_rider_source_on_body_safe_frozen_carriageway')

    def test_context_only_rider_intervals_still_require_road_mode_space_and_exact_provenance(self):
        for mutation in ('walking','cycling','no_road_space','wrong_space_mode','unknown_provenance'):
            with self.subTest(mutation=mutation):
                value=self.add_mixed_traffic_access();boundary=value['boundary_intervals'][-1]
                boundary['spawn_supported']=False
                if mutation in ('walking','cycling'):boundary['mode']=mutation
                if mutation=='no_road_space':value['navigation']['spaces']=[]
                if mutation=='wrong_space_mode':value['navigation']['spaces'][0]['mode']='walking'
                if mutation=='unknown_provenance':boundary['provenance']='measured_road_source'
                (self.root/'building_access.json').write_text(json.dumps(value));self.rejected()

    def test_mixed_traffic_nested_fields_and_geometry_are_strictly_bounded(self):
        for mutation in ('missing_space','space_private','space_digest','space_clearance','duplicate_space',
                         'crossing_private','crossing_provenance','crossing_width','crossing_outside','duplicate_crossing','road_provenance','unknown_mode'):
            with self.subTest(mutation=mutation):
                value=self.add_mixed_traffic_access();nav=value['navigation']
                if mutation=='missing_space':nav['spaces']=[]
                if mutation=='space_private':nav['spaces'][0]['person_id']='private'
                if mutation=='space_digest':nav['spaces'][0]['allowed_center_polygons_sha256']='invalid'
                if mutation=='space_clearance':nav['spaces'][0]['body_clearance_m']=0
                if mutation=='unknown_mode':nav['spaces'][0]['mode']='unknown'
                if mutation=='duplicate_space':nav['spaces'].append(copy.deepcopy(nav['spaces'][0]))
                if mutation=='crossing_private':nav['synthetic_crossing_connectors'][0]['track_id']='private'
                if mutation=='crossing_provenance':nav['synthetic_crossing_connectors'][0]['provenance']='surveyed'
                if mutation=='crossing_width':nav['synthetic_crossing_connectors'][0]['width_m']=21
                if mutation=='crossing_outside':nav['synthetic_crossing_connectors'][0]['centerline'][0]=[-1,30]
                if mutation=='duplicate_crossing':nav['synthetic_crossing_connectors'].append(copy.deepcopy(nav['synthetic_crossing_connectors'][0]))
                if mutation=='road_provenance':value['boundary_intervals'][-1]['provenance']='derived_frozen_functional_zone_boundary'
                (self.root/'building_access.json').write_text(json.dumps(value));self.rejected()

    def test_storefront_v2_manual_override_preserves_exact_checked_door_without_orthogonal_claim(self):
        value=self.add_storefront_access();front=value['store_fronts'][0]
        front['projection_method']='manual_original_facade_override'
        front['poi']['point']=[19,16]
        (self.root/'building_access.json').write_text(json.dumps(value));self.write()
        serve.validate_bundle(self.root)
        front['projection_method']='unverified_real_door'
        (self.root/'building_access.json').write_text(json.dumps(value));self.rejected()

    def add_source_storefront_access(self):
        value=self.add_storefront_access();front=value['store_fronts'][0]
        value['portals'][0]['provenance']='osm'
        front.update(provenance='osm_entrance_association',projection_method='source_entrance_on_original_facade',
            entrance_source={'osm_type':'node','osm_id':9370793427,'osm_version':2,
                'osm_timestamp':'2023-07-22T18:14:47Z',
                'scope':'Exact frozen OSM entrance point; association to the named tenant is modeled.'})
        value['navigation']['synthetic_access_connectors']=[{'id':'access1','portal_id':'door1',
            'centerline':[[18,10],[18,7],[16,6]],'width_m':3.,
            'provenance':'synthetic_approach_to_source_osm_entrance'}]
        (self.root/'building_access.json').write_text(json.dumps(value));return value

    def test_source_storefront_association_and_bounded_synthetic_approach_validate(self):
        self.add_source_storefront_access();self.write();serve.validate_bundle(self.root)

    def test_source_storefront_metadata_is_closed_and_cannot_upgrade_a_synthetic_door(self):
        for mutation in ('missing','private','boolean_node','version','timestamp','scope','method','portal_provenance','synthetic_claim'):
            with self.subTest(mutation=mutation):
                value=self.add_source_storefront_access();front=value['store_fronts'][0];source=front['entrance_source']
                if mutation=='missing':front.pop('entrance_source')
                if mutation=='private':source['person_id']='private'
                if mutation=='boolean_node':source['osm_id']=True
                if mutation=='version':source['osm_version']=0
                if mutation=='timestamp':source['osm_timestamp']='recent'
                if mutation=='scope':source['scope']='Verified tenant entrance'
                if mutation=='method':front['projection_method']='manual_original_facade_override'
                if mutation=='portal_provenance':value['portals'][0]['provenance']='synthetic'
                if mutation=='synthetic_claim':front['provenance']='synthetic_poi_projection'
                (self.root/'building_access.json').write_text(json.dumps(value));self.rejected()

    def test_source_access_connectors_are_closed_bounded_and_bound_to_one_named_entrance(self):
        for mutation in ('private','unknown_portal','duplicate','duplicate_portal','wrong_provenance',
                         'short','wide','boolean_width','long','off_target','outside','vertices','repeated','not_source'):
            with self.subTest(mutation=mutation):
                value=self.add_source_storefront_access();rows=value['navigation']['synthetic_access_connectors'];row=rows[0]
                if mutation=='private':row['track_id']='private'
                if mutation=='unknown_portal':row['portal_id']='unknown'
                if mutation=='duplicate':rows.append(copy.deepcopy(row))
                if mutation=='duplicate_portal':rows.append(dict(row,id='access2'))
                if mutation=='wrong_provenance':row['provenance']='measured_forecourt'
                if mutation=='short':row['width_m']=1
                if mutation=='wide':row['width_m']=4.1
                if mutation=='boolean_width':row['width_m']=True
                if mutation=='long':row['centerline']=[[18,10],[18,23]]
                if mutation=='off_target':row['centerline'][0]=[18.1,10]
                if mutation=='outside':row['centerline'][1]=[-1,10]
                if mutation=='vertices':row['centerline']=[[18,10]]
                if mutation=='repeated':row['centerline'][1]=[18,10]
                if mutation=='not_source':
                    front=value['store_fronts'][0];front.pop('entrance_source')
                    front.update(provenance='synthetic_poi_projection',projection_method='orthogonal_to_reachable_original_facade')
                (self.root/'building_access.json').write_text(json.dumps(value));self.rejected()

    def test_storefront_v2_rejects_private_fields_at_every_new_level(self):
        for level in ('front','poi','separator','boundary','navigation'):
            with self.subTest(level=level):
                value=self.add_storefront_access()
                target={'front':value['store_fronts'][0],'poi':value['store_fronts'][0]['poi'],
                    'separator':value['facade_separators'][0],'boundary':value['boundary_intervals'][0],
                    'navigation':value['navigation']}[level]
                target['person_schedule']='private';(self.root/'building_access.json').write_text(json.dumps(value));self.rejected()

    def test_storefront_v2_checks_geometry_relationships_and_source_eligibility(self):
        for mutation in ('unknown_portal','different_building','duplicate_front','unmatched_portal',
                'poi_outside','projection_not_orthogonal','frontage_off_wall','entrance_outside_frontage','end_width','separator_off_front',
                'separator_too_long','boundary_interior','boundary_side','boundary_length','cycling_source',
                'boolean_eligibility','boundary_shadows_portal','navigation_digest','navigation_clearance'):
            with self.subTest(mutation=mutation):
                value=self.add_storefront_access();front=value['store_fronts'][0];boundary=value['boundary_intervals'][0]
                if mutation=='unknown_portal':front['portal_id']='missing'
                if mutation=='different_building':front['building_id']='missing'
                if mutation=='duplicate_front':value['store_fronts'].append(copy.deepcopy(front))
                if mutation=='unmatched_portal':value['store_fronts']=[]
                if mutation=='poi_outside':front['poi']['point']=[81,10]
                if mutation=='projection_not_orthogonal':front['poi']['point']=[19,16]
                if mutation=='frontage_off_wall':front['frontage'][1]=[25,11]
                if mutation=='entrance_outside_frontage':front['frontage']=[[10,10],[15,10]]
                if mutation=='end_width':value['portals'][0]['point']=[10.1,10]
                if mutation=='separator_off_front':value['facade_separators'][0]['points'][0]=[24,10]
                if mutation=='separator_too_long':value['facade_separators'][0]['points'][1]=[25,20]
                if mutation=='boundary_interior':boundary['points']=[[1,40],[1,60]]
                if mutation=='boundary_side':boundary['side']='east'
                if mutation=='boundary_length':boundary['length_m']=19
                if mutation=='cycling_source':boundary['mode']='cycling'
                if mutation=='boolean_eligibility':boundary['spawn_supported']=1
                if mutation=='boundary_shadows_portal':boundary['id']='door1'
                if mutation=='navigation_digest':value['navigation']['allowed_center_polygons_sha256']='bad'
                if mutation=='navigation_clearance':value['navigation']['body_clearance_m']=0
                (self.root/'building_access.json').write_text(json.dumps(value));self.rejected()

    def test_public_building_geometry_is_optional_and_hash_checked(self):
        self.add_building_access();self.write()
        _,files=serve.validate_bundle(self.root)
        self.assertEqual(files['building_access.json'],(self.root/'building_access.json').resolve())
        self.manifest['sha256']={'building_access.json':hashlib.sha256((self.root/'building_access.json').read_bytes()).hexdigest()}
        self.write();serve.validate_bundle(self.root)
        with (self.root/'building_access.json').open('a') as stream: stream.write(' ')
        with self.assertRaisesRegex(ValueError,'digest mismatch'):
            serve.validate_bundle(self.root)

    def test_public_building_schema_rejects_private_identity_and_schedule_fields(self):
        for level in ('root','building','portal'):
            with self.subTest(level=level):
                value=self.add_building_access()
                target=value if level=='root' else value['buildings' if level=='building' else 'portals'][0]
                target['private_person_id']='must-never-be-served'
                (self.root/'building_access.json').write_text(json.dumps(value));self.rejected()

    def test_public_building_geometry_limits_and_relationships_are_validated(self):
        for mutation in ('bounds','open_ring','few_vertices','outside','boolean','nonfinite','duplicate_building',
                         'duplicate_portal','unknown_building','bad_provenance','off_facade','zero_facade','width','buildings','portals'):
            with self.subTest(mutation=mutation):
                value=self.add_building_access();building=value['buildings'][0];portal=value['portals'][0]
                if mutation=='bounds':value['bounds']['width']=81
                if mutation=='open_ring':building['polygons'][0][-1]=[11,10]
                if mutation=='few_vertices':building['polygons']=[[[1,1],[2,2],[1,1]]]
                if mutation=='outside':building['polygons'][0][1]=[81,10]
                if mutation=='boolean':building['polygons'][0][1]=[True,10]
                if mutation=='nonfinite':portal['point']=[float('nan'),10]
                if mutation=='duplicate_building':value['buildings'].append(copy.deepcopy(building))
                if mutation=='duplicate_portal':value['portals'].append(copy.deepcopy(portal))
                if mutation=='unknown_building':portal['building_id']='unknown'
                if mutation=='bad_provenance':portal['provenance']='realistic'
                if mutation=='off_facade':portal['point']=[20,11]
                if mutation=='zero_facade':portal['facade']=[[10,10],[10,10]]
                if mutation=='width':portal['width_m']=21
                if mutation=='buildings':value['buildings']=[building]*257
                if mutation=='portals':value['portals']=[portal]*513
                (self.root/'building_access.json').write_text(json.dumps(value));self.rejected()
        self.add_building_access();self.write()
        with mock.patch.object(serve,'MAX_BUILDING_VERTICES',4):
            with self.assertRaisesRegex(ValueError,'vertex limit'):serve.validate_bundle(self.root)

    def test_public_building_holes_and_real_entrance_provenance_are_preserved(self):
        value=self.add_building_access()
        value['buildings'][0]['holes']=[[[14,14],[16,14],[16,16],[14,16],[14,14]]]
        value['portals'][0]['provenance']='osm'
        (self.root/'building_access.json').write_text(json.dumps(value));self.write()
        serve.validate_bundle(self.root)

    def test_public_building_path_missing_symlink_and_size_are_rejected(self):
        self.add_building_access()
        for path in ('../building_access.json','private/config.yaml','scene_manifest.json','https://example.org/access.json'):
            self.manifest['map']['building_access']=path;self.rejected()
        self.manifest['map']['building_access']='building_access.json'
        (self.root/'building_access.json').unlink();self.rejected()
        with tempfile.TemporaryDirectory() as other:
            external=Path(other)/'external.json';external.write_text('{}')
            (self.root/'building_access.json').symlink_to(external);self.rejected()
            (self.root/'building_access.json').unlink()
        self.add_building_access();self.write()
        with mock.patch.object(serve,'MAX_BUILDING_ACCESS_BYTES',2):
            with self.assertRaisesRegex(ValueError,'2 MiB'):serve.validate_bundle(self.root)

    def test_only_validated_public_building_artifact_is_served(self):
        self.add_building_access();self.write()
        (self.root/'scene_manifest.json').write_text('{"private_person_id":"private"}')
        server=ThreadingHTTPServer(('127.0.0.1',0),serve.handler_for(self.root,Path(__file__).parent));server.verbose=False
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_address[1])
        try:
            with urlopen(url+'/bundle/building_access.json') as response:
                self.assertEqual(response.headers['Content-Type'],'application/json; charset=utf-8')
                self.assertEqual(json.load(response)['schema'],'ump.building-access.v1')
            with self.assertRaises(HTTPError):urlopen(url+'/bundle/scene_manifest.json')
        finally:
            server.shutdown();thread.join();server.server_close()

    def test_optional_map_png_and_track_metadata_validate(self):
        self.add_map()
        self.write()
        manifest,files=serve.validate_bundle(self.root)
        self.assertEqual(manifest['identity_unit'],'visible_episode_track')
        self.assertEqual(files['map_background.png'],(self.root/'map_background.png').resolve())
        self.manifest['sha256']={'map_background.png':hashlib.sha256((self.root/'map_background.png').read_bytes()).hexdigest()}
        self.write()
        serve.validate_bundle(self.root)

    def test_map_image_path_is_a_single_literal_allowlist_entry(self):
        for path in ('other.png','../map_background.png','https://example.org/map.png','map_background.svg','sub/map_background.png'):
            with self.subTest(path=path):
                self.add_map()['image']=path
                self.rejected()

    def test_map_image_external_symlink_and_missing_image_rejected(self):
        self.add_map()
        (self.root/'map_background.png').unlink()
        self.rejected()
        with tempfile.TemporaryDirectory() as other:
            external=Path(other)/'outside.png'
            external.write_bytes(self.png())
            (self.root/'map_background.png').symlink_to(external)
            self.rejected()

    def test_map_bounds_must_match_frozen_observations(self):
        for bounds in (None,{},dict(x=0,y=0,width=160,height=80),dict(x=True,y=0,width=80,height=80),dict(x=0,y=0,width=80,height=float('nan'))):
            with self.subTest(bounds=bounds):
                self.add_map()['bounds']=bounds
                self.rejected()

    def test_map_metadata_limits_and_types_are_enforced(self):
        for key,value in [('attribution',''),('attribution','x'*513),('legend',{}),('legend',[{'label':'Walk','color':'url(external)'}]),
                ('legend',[{'label':'Walk','color':'#abcdef'}]*33),('labels',{}),('labels',[{'text':'Outside','x':81,'y':0}]),
                ('labels',[{'text':'Bad','x':0,'y':0,'kind':'guess'}]),('labels',[{'text':'x'*161,'x':0,'y':0}]),
                ('labels',[{'text':'More','x':0,'y':0}]*201)]:
            with self.subTest(key=key,value=value):
                self.add_map()[key]=value
                self.rejected()
        for key,value in [('identity_unit','person'),('input_provenance',''),('input_provenance','x'*1025)]:
            with self.subTest(key=key):
                self.add_map()
                self.manifest[key]=value
                self.rejected()

    def test_png_header_crc_pixel_size_filter_and_animation_guards(self):
        self.add_map()
        valid=self.png()
        cases=[b'not a PNG', valid[:-1], valid+b'extra', valid[:29]+bytes([valid[29]^1])+valid[30:],
               self.png(width=4097),self.png(depth=16),self.png(interlace=1),
               self.png(pixels=b'\x00'*100),self.png(pixels=(b'\x05'+b'\xff'*8)*2)]
        animation=b'acTL'+struct.pack('>II',2,0)
        animation_chunk=struct.pack('>I',8)+animation+struct.pack('>I',zlib.crc32(animation)&0xffffffff)
        cases.append(valid[:33]+animation_chunk+valid[33:])
        for data in cases:
            with self.subTest(size=len(data)):
                (self.root/'map_background.png').write_bytes(data)
                self.rejected()
        # A valid RGB image uses a different scanline size from RGBA.
        (self.root/'map_background.png').write_bytes(self.png(color=2))
        self.write()
        serve.validate_bundle(self.root)

    def test_png_oversized_file_is_rejected_before_decoding(self):
        self.add_map()
        with (self.root/'map_background.png').open('r+b') as image:
            image.truncate(serve.MAX_MAP_BYTES+1)
        self.rejected()

    def test_overlapping_region_metadata_and_cross_region_conflicts_are_retained(self):
        region=self.add_policy_region(requirements=[{'metric':'support','min':10}])
        self.manifest['variants'][0]['policy_regions'].append(dict(region,id='overlap',requirements=[{'metric':'support','max':5}]))
        self.manifest['variants'][0]['policy_root_requirements']=[{'metric':'support','min':5}]
        self.write()
        serve.validate_bundle(self.root)
        # Viewer preserves declarations to expose the conflict; it does not
        # pretend the source mechanism could satisfy both inequalities.

    def test_root_requirement_schema_is_validated(self):
        for value in (None,{},[{'metric':'support'}],[{'metric':'bad metric','min':1}],[{'metric':'support','min':True}]):
            with self.subTest(value=value):
                self.manifest['variants'][0]['policy_root_requirements']=value
                self.rejected()

    def test_map_serves_png_mime_without_exposing_other_images(self):
        self.add_map()
        self.write()
        (self.root/'other.png').write_bytes(self.png())
        server=ThreadingHTTPServer(('127.0.0.1',0),serve.handler_for(self.root,Path(__file__).parent))
        server.verbose=False
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url='http://127.0.0.1:'+str(server.server_address[1])
        try:
            with urlopen(url+'/bundle/map_background.png') as response:
                self.assertEqual(response.headers['Content-Type'],'image/png')
                self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
                self.assertEqual(response.read(),self.png())
            with self.assertRaises(HTTPError):
                urlopen(url+'/bundle/other.png')
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def frozen_study(self):
        """Small independent source files exercise preparation without real datasets."""
        study = self.root/'frozen-study'
        study.mkdir()
        artifacts = {}
        def freeze(name, value):
            path = study/name
            # Deliberate formatting proves inputs are copied, rather than reencoded.
            path.write_text(json.dumps(value, indent=4)+'\n\n', encoding='utf-8')
            artifacts[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        freeze('observations.json', self.replay)
        for regional in (True,False):
            for secondary in ('temporal_first','spatial_first'):
                for coordination in ('common_window','cell_local'):
                    name=f'{coordination}_{"regional" if regional else "uniform"}_{secondary}'
                    result=copy.deepcopy(self.result)
                    result['parameters']={'coordination':coordination}
                    if coordination=='cell_local':
                        scope={k:result['releases'][0]['cells'][0][k]
                               for k in ('cell_id','depth','x','y','width','height')}
                        result['windows'][0]['coordination_cell']=copy.deepcopy(scope)
                        result['releases'][0]['coordination_cell']=copy.deepcopy(scope)
                    freeze(name+'.json', result)
                    regions=([{'id':'small-patch','type':'residential','x':10,'y':10,'width':2.5,'height':2.5,
                               'requirements':{'semantic_max_loss':{'max':.5}}}] if regional else [])
                    freeze(name+'-policy.json', {'policy_regions':regions})
        manifest={'schema':'ump.semantic-cell-local-study.v1','status':'verified',
                  'artifacts_sha256':artifacts}
        (study/'study-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        return study, artifacts

    def test_prepare_verified_study_preserves_frozen_bytes_and_overlay_metadata(self):
        study,hashes=self.frozen_study()
        original={p.name:p.read_bytes() for p in study.iterdir()}
        destination=self.root/'prepared'
        self.assertEqual(prepare_local_bundle.prepare(study,destination),destination.resolve())
        manifest,files=serve.validate_bundle(destination)
        self.assertEqual(len(manifest['variants']),8)
        self.assertEqual(len(files),10)
        for name in ['observations.json']+[v['result'] for v in manifest['variants']]:
            self.assertEqual((destination/name).read_bytes(),original[name])
            self.assertEqual(manifest['sha256'][name],hashes[name])
        for variant in manifest['variants']:
            self.assertEqual(len(variant['policy_regions']),1 if '_regional_' in variant['id'] else 0)
        self.assertEqual({p.name:p.read_bytes() for p in study.iterdir()},original)

    def test_prepare_existing_destination_is_rejected_without_changing_it(self):
        study,_=self.frozen_study()
        destination=self.root/'existing'
        destination.mkdir()
        (destination/'sentinel.json').write_bytes(b'preserve this existing directory\n')
        original={p.name:p.read_bytes() for p in destination.iterdir()}
        with self.assertRaisesRegex(ValueError,'existing replay directory'):
            prepare_local_bundle.prepare(study,destination)
        self.assertEqual({p.name:p.read_bytes() for p in destination.iterdir()},original)

    def test_prepare_incorrect_frozen_source_hash_leaves_no_output(self):
        study,_=self.frozen_study()
        manifest_path=study/'study-manifest.json'
        manifest=json.loads(manifest_path.read_text())
        manifest['artifacts_sha256']['cell_local_regional_temporal_first-policy.json']='0'*64
        manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
        destination=self.root/'rejected'
        with self.assertRaisesRegex(ValueError,'mismatched frozen source digest'):
            prepare_local_bundle.prepare(study,destination)
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.root.glob('.ump-replay-*')),[])

    def test_cell_local_scope_is_required(self):
        self.result['parameters']={'coordination':'cell_local'}
        self.rejected()

    def local_events(self, events):
        """Small hand-worked canonical cells; events need not share time cuts."""
        geometry = {12:(1,0,0,40,40), 13:(1,40,0,40,40),
                    48:(2,0,0,20,20), 49:(2,20,0,20,20), 52:(2,40,0,20,20)}
        def cell(identity):
            depth,x,y,width,height = geometry[identity]
            return dict(cell_id=identity,depth=depth,x=x,y=y,width=width,height=height)
        self.result['parameters']={'coordination':'cell_local'}
        self.result['windows'], self.result['releases'] = [], []
        for scope,start,end,stamp,identities in events:
            cells = [dict(cell(identity),observation_contributions=1) for identity in identities]
            window = dict(start_ms=start,end_ms=end,evaluated_at_ms=stamp,
                          coordination_cell=cell(scope),cells=[dict(c,selected=True) for c in cells])
            self.result['windows'].append(window)
            if cells:
                self.result['releases'].append(dict(start_ms=start,end_ms=end,sealed_at_ms=stamp,
                    coordination_cell=cell(scope),cells=copy.deepcopy(cells)))

    def test_local_asynchrony_equal_event_times_and_partial_horizon_validate(self):
        self.local_events([(48,0,400,400,[48]),(52,100,200,400,[52])])
        self.write()
        serve.validate_bundle(self.root)
        # Endpoints need not be sorted or equal, and missing older/final regions
        # are not invented as complete source retirement by a viewer validator.
        self.assertLess(self.result['windows'][1]['end_ms'],self.result['windows'][0]['end_ms'])

    def test_local_parent_handoff_and_empty_private_retirement_validate(self):
        self.local_events([(48,0,200,200,[]),(12,200,400,400,[12])])
        self.write()
        serve.validate_bundle(self.root)
        self.local_events([(48,0,200,200,[48]),(12,200,400,400,[49])])
        self.write()
        serve.validate_bundle(self.root)

    def test_local_scope_ids_geometry_and_containment_rejected(self):
        for mutation in ('missing','wrong_prefix','boolean_depth','deep','geometry','outside'):
            with self.subTest(mutation=mutation):
                self.local_events([(12,0,400,400,[48])])
                row=self.result['windows'][0]
                if mutation=='missing': row.pop('coordination_cell')
                if mutation=='wrong_prefix': row['coordination_cell']['cell_id']=4
                if mutation=='boolean_depth': row['coordination_cell']['depth']=True
                if mutation=='deep': row['coordination_cell']['depth']=3
                if mutation=='geometry': row['coordination_cell']['width']=20
                if mutation=='outside': row['cells'][0].update(cell_id=52,x=40)
                self.rejected()

    def test_local_overlapping_retirement_and_duplicate_public_support_rejected(self):
        self.local_events([(12,0,300,300,[48]),(48,200,400,400,[48])])
        self.rejected()
        self.local_events([(48,0,400,400,[48])])
        self.result['releases'].append(copy.deepcopy(self.result['releases'][0]))
        self.rejected()

    def test_duplicate_or_parent_child_cell_cut_rejected(self):
        for cells in ([48,48],[12,48]):
            with self.subTest(cells=cells):
                self.local_events([(12,0,400,400,cells)])
                self.rejected()

    def test_local_public_private_scope_interval_selection_counts_and_semantics_match(self):
        for mutation in ('interval','selection','count','semantic','missing_public','empty_public'):
            with self.subTest(mutation=mutation):
                self.local_events([(12,0,400,400,[48])])
                if mutation=='interval': self.result['releases'][0]['start_ms']=100
                if mutation=='selection': self.result['windows'][0]['cells'][0]['selected']=False
                if mutation=='count': self.result['releases'][0]['cells'][0]['observation_contributions']=2
                if mutation=='semantic': self.result['releases'][0]['cells'][0]['semantic']={'schema':'changed'}
                if mutation=='missing_public': self.result['releases']=[]
                if mutation=='empty_public': self.result['releases'][0]['cells']=[]
                self.rejected()

    def add_local_filtered_release(self):
        self.local_events([(12,0,400,400,[48])])
        self.manifest['variants'][0]['contribution_selection']='policy_filtered'
        diagnostic=self.result['windows'][0]['cells'][0]
        public=self.result['releases'][0]['cells'][0]
        semantic={'schema':'ump.semantic-release.v1','taxonomy_id':'test','taxonomy_version':'1',
            'min_category_distinct_contributors':20,'semantic_max_loss':0,'semantic_mean_loss':0,
            'categories':[{'category_id':'pedestrian','observation_contributions':60,'distinct_contributors':20}]}
        diagnostic.update(observation_contributions=63,distinct_road_users=21,mean_sample_occupancy=21,
            semantic=copy.deepcopy(semantic),retained_counts={'observation_contributions':60,'distinct_road_users':20,'mean_sample_occupancy':20},
            checks=[{'metric':'semantic_suppression_fraction','min':None,'max':.1,'observed':1/21,'status':'pass'}],
            semantic_suppression={'schema':'ump.semantic-suppression.v1','input_observation_contributions':63,
                'input_distinct_contributors':21,'retained_observation_contributions':60,'retained_distinct_contributors':20,
                'suppressed_observation_contributions':3,'suppressed_distinct_contributors':1,'suppressed_fraction':1/21,
                'suppressed_type_observation_contributions':{'Cyclist':3},'suppressed_terminal_categories':['cyclist'],
                'full_input_semantic_loss':1/21,'unsuppressed_semantic_loss':1,'evaluated_candidates':1})
        public.update(observation_contributions=60,distinct_road_users=20,mean_sample_occupancy=20,semantic=semantic)
        return diagnostic,public

    def test_local_filtered_release_matches_retained_counts_preserving_original_ownership(self):
        diagnostic,public=self.add_local_filtered_release()
        self.write();serve.validate_bundle(self.root)
        self.assertEqual(diagnostic['observation_contributions'],63)
        self.assertEqual(public['observation_contributions'],60)
        self.assertEqual(self.result['windows'][0]['coordination_cell']['cell_id'],12)

    def test_local_filtered_counts_masks_fractions_and_recipient_semantics_are_strict(self):
        for mutation in ('raw','retained','fraction','cap','mask','public_count','public_semantic','private_leak','missing_audit','benefit','occupancy','semantic_sum'):
            with self.subTest(mutation=mutation):
                diagnostic,public=self.add_local_filtered_release()
                if mutation=='raw':diagnostic['observation_contributions']=64
                if mutation=='retained':diagnostic['retained_counts']['distinct_road_users']=19
                if mutation=='fraction':diagnostic['semantic_suppression']['suppressed_fraction']=0
                if mutation=='cap':diagnostic['checks'][0]['max']=0
                if mutation=='mask':diagnostic['semantic_suppression']['suppressed_type_observation_contributions']={}
                if mutation=='public_count':public['observation_contributions']=63
                if mutation=='public_semantic':public['semantic']['categories'][0]['distinct_contributors']=21
                if mutation=='private_leak':public['semantic_suppression']=copy.deepcopy(diagnostic['semantic_suppression'])
                if mutation=='missing_audit':diagnostic.pop('semantic_suppression')
                if mutation=='benefit':diagnostic['semantic_suppression']['unsuppressed_semantic_loss']=0
                if mutation=='occupancy':
                    diagnostic['retained_counts']['mean_sample_occupancy']=19
                    public['mean_sample_occupancy']=19
                if mutation=='semantic_sum':
                    diagnostic['semantic']['categories'][0]['observation_contributions']=59
                    public['semantic']['categories'][0]['observation_contributions']=59
                self.rejected()

    def test_local_event_time_order_is_strict_except_equal_timestamps(self):
        self.local_events([(48,0,400,400,[48]),(52,0,200,300,[52])])
        self.rejected()

    def test_coordination_modes_and_common_window_scope_are_checked(self):
        for mode in ('unknown',True,None,[]):
            with self.subTest(mode=mode):
                self.result['parameters']={'coordination':mode}
                self.rejected()
        self.result['parameters']={'coordination':'common_window'}
        self.result['windows'][0]['coordination_cell']=dict(cell_id=12,depth=1,x=0,y=0,width=40,height=40)
        self.rejected()

    def test_canonical_cell_geometry_and_integral_counts_checked_in_both_modes(self):
        for local in (False,True):
            for mutation in ('id','depth','position','count'):
                with self.subTest(local=local,mutation=mutation):
                    self.local_events([(12,0,400,400,[48])])
                    if not local:
                        self.result['parameters']={'coordination':'common_window'}
                        for name in ('windows','releases'):
                            self.result[name][0].pop('coordination_cell')
                    cell=self.result['windows'][0]['cells'][0]
                    if mutation=='id':cell['cell_id']=12
                    if mutation=='depth':cell['depth']=True
                    if mutation=='position':cell['x']=0.1
                    if mutation=='count':cell['observation_contributions']=True
                    self.rejected()

    def test_cross_run_rejected(self):
        self.result['source']['run_id']='other'
        self.rejected()

    def test_cross_geometry_rejected(self):
        self.result['source']['coverage']=dict(self.replay['coverage'],width=160)
        self.rejected()

    def test_duplicate_variant_rejected(self):
        self.manifest['variants'].append(copy.deepcopy(self.manifest['variants'][0]))
        self.rejected()

    def test_parent_traversal_rejected(self):
        self.manifest['observations']='../observations.json'
        self.rejected()

    def test_absolute_path_rejected(self):
        self.manifest['observations']=str(self.root/'observations.json')
        self.rejected()

    def test_external_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            outside=Path(other)/'outside.json'
            outside.write_text(json.dumps(self.replay))
            (self.root/'link.json').symlink_to(outside)
            self.manifest['observations']='link.json'
            self.rejected()

    def test_duplicate_timestamp_rejected(self):
        self.replay['batches'][1]['observed_at_ms']=100
        self.rejected()

    def test_nonfinite_position_rejected(self):
        self.replay['batches'][0]['observations'][0]['x']=float('nan')
        self.rejected()

    def test_unavailable_with_positions_rejected(self):
        self.replay['batches'][0]['status']='unavailable'
        self.rejected()

    def test_future_sealing_rejected(self):
        self.result['releases'][0]['sealed_at_ms']=600
        self.rejected()

    def test_release_before_window_end_rejected(self):
        self.result['releases'][0]['sealed_at_ms']=399
        self.rejected()

    def test_out_of_area_cell_rejected(self):
        self.result['releases'][0]['cells'][0]['width']=81
        self.rejected()

    def test_hash_mismatch_rejected(self):
        self.manifest['sha256']={'observations.json':'0'*64}
        self.rejected()

    def add_policy_region(self, **changes):
        region = {'id':'small-patch', 'type':'residential', 'x':10, 'y':10, 'width':2.5, 'height':2.5,
                  'requirements':[{'metric':'semantic_max_loss', 'min':0, 'max':0.5}]}
        region.update(changes)
        self.manifest['variants'][0]['policy_regions'] = [region]
        return region

    def test_valid_optional_policy_regions_validate(self):
        self.add_policy_region()
        self.write()
        serve.validate_bundle(self.root)
        self.manifest['variants'][0]['policy_regions'] = []
        self.write()
        serve.validate_bundle(self.root)

    def test_policy_region_container_and_region_object_rejected(self):
        for value in (None, {}, 'region', [None], [1]):
            with self.subTest(value=value):
                self.manifest['variants'][0]['policy_regions'] = value
                self.rejected()

    def test_duplicate_or_empty_policy_region_ids_rejected(self):
        for identity in ('', ' ', ' padded ', 42, 'x'*129):
            with self.subTest(identity=identity):
                self.add_policy_region(id=identity)
                self.rejected()
        region = self.add_policy_region()
        self.manifest['variants'][0]['policy_regions'].append(copy.deepcopy(region))
        self.rejected()

    def test_nonfinite_or_nonpositive_policy_region_geometry_rejected(self):
        for changes in ({'x':float('nan')}, {'y':float('inf')}, {'width':True}, {'width':0}, {'height':-1}):
            with self.subTest(changes=changes):
                self.add_policy_region(**changes)
                self.rejected()

    def test_outside_policy_region_rejected(self):
        for changes in ({'x':-0.01}, {'y':79, 'height':2}, {'x':79, 'width':2}):
            with self.subTest(changes=changes):
                self.add_policy_region(**changes)
                self.rejected()

    def test_policy_region_metric_and_bounds_rejected(self):
        for requirement in (None, {}, {'metric':'Bad Metric', 'min':1}, {'metric':3, 'min':1},
                {'metric':'support'}, {'metric':'support', 'min':True},
                {'metric':'support', 'max':float('nan')}, {'metric':'support', 'min':4, 'max':3}):
            with self.subTest(requirement=requirement):
                self.add_policy_region(requirements=[requirement])
                self.rejected()

    def test_policy_region_metadata_limits_enforced(self):
        region = self.add_policy_region()
        self.manifest['variants'][0]['policy_regions'] = [dict(region, id=str(index)) for index in range(4097)]
        self.rejected()
        self.add_policy_region(requirements=[{'metric':'support', 'min':1}]*65)
        self.rejected()

    def test_policy_region_requirements_container_and_type_rejected(self):
        for changes in ({'requirements':None}, {'requirements':{}}, {'type':None}, {'type':''}):
            with self.subTest(changes=changes):
                self.add_policy_region(**changes)
                self.rejected()

    def test_cell_inspection_controls_are_keyboard_accessible(self):
        class Controls(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = {}
                self.labels = set()
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs:
                    self.ids[attrs['id']] = (tag, attrs)
                if tag == 'label' and 'for' in attrs:
                    self.labels.add(attrs['for'])
        controls = Controls()
        controls.feed((Path(__file__).parent/'index.html').read_text())
        for side in ('A', 'B'):
            tag, attrs = controls.ids['cell'+side]
            self.assertEqual(tag, 'select')
            self.assertIn('cell'+side, controls.labels)
            self.assertEqual(attrs['aria-controls'], 'detail'+side)
            self.assertIn(attrs['aria-describedby'], controls.ids)
            self.assertEqual(controls.ids['focus'+side][1]['type'], 'checkbox')

    def test_reference_focus_control_is_labeled_and_defaults_to_full_area(self):
        class ReferenceControls(HTMLParser):
            def __init__(self):
                super().__init__()
                self.label = False
                self.select = None
                self.options = []
                self.in_select = False
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'label' and attrs.get('for') == 'referenceFocus':
                    self.label = True
                if tag == 'select' and attrs.get('id') == 'referenceFocus':
                    self.select = attrs
                    self.in_select = True
                if tag == 'option' and self.in_select:
                    self.options.append(attrs)
            def handle_endtag(self, tag):
                if tag == 'select':
                    self.in_select = False
        controls = ReferenceControls()
        controls.feed((Path(__file__).parent/'index.html').read_text())
        self.assertTrue(controls.label)
        self.assertEqual(controls.select['aria-describedby'], 'referenceFocusHint')
        self.assertEqual([option['value'] for option in controls.options], ['full', 'A', 'B'])
        self.assertFalse(any('selected' in option for option in controls.options[1:]))

    def test_policy_tree_view_controls_keep_distinct_locators_and_method_descriptions(self):
        class PolicyControls(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = {}
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs:
                    self.ids[attrs['id']] = (tag, attrs)
        html = (Path(__file__).parent/'index.html').read_text()
        controls = PolicyControls()
        controls.feed(html)
        self.assertNotIn('Comparison A', html)
        self.assertNotIn('Comparison B', html)
        self.assertEqual(controls.ids['selectionRelationship'][1]['role'], 'status')
        for side in ('A', 'B'):
            self.assertEqual(controls.ids['policyTitle'+side][0], 'h2')
            self.assertEqual(controls.ids['variant'+side][1]['aria-describedby'], 'policyMethod'+side)
            self.assertIn('Policy tree result and execution method', controls.ids['variant'+side][1]['aria-label'])
            self.assertIn('view '+side, controls.ids['variant'+side][1]['aria-label'])
        viewer = (Path(__file__).parent/'viewer.js').read_text()
        self.assertIn('M.variantIdentity(v)', viewer)
        self.assertIn('M.selectionRelationship(...selected)', viewer)
        self.assertIn("identity(v).selectionLabel", viewer)
        self.assertNotIn('Comparison ${side}', viewer)

    def test_storefront_overlay_controls_are_explicitly_highlights_of_fixed_map_context(self):
        html=(Path(__file__).parent/'index.html').read_text()
        self.assertIn('Highlight modeled shop fronts',html)
        self.assertIn('Highlight source / sink intervals',html)
        self.assertNotIn('Show modeled shop fronts',html)
        self.assertNotIn('Show source / sink intervals',html)

    def test_verbose_source_provenance_is_below_reference_map_and_outside_its_header(self):
        html=(Path(__file__).parent/'index.html').read_text()
        reference=html.split('<section class="panel reference">',1)[1].split('</section>',1)[0]
        header=reference.split('<div class="map">',1)[0]
        self.assertNotIn('id="source"',header)
        self.assertNotIn('id="referenceProvenance"',header)
        self.assertLess(reference.index('id="reference"'),reference.index('id="referenceProvenance"'))
        self.assertIn('class="source-provenance"',reference)

    def test_reference_wording_does_not_assume_simulator_generation(self):
        html = (Path(__file__).parent/'index.html').read_text()
        self.assertNotIn('Private sensor observations from the recorded simulator run', html)
        self.assertIn('Private input observations from this recorded replay', html)
        self.assertIn('id="referenceProvenance"', html)
        self.assertIn('the dots and counts remain the current recorded sample', html)

    def test_exact_source_group_inspection_requires_explicit_opt_in(self):
        class SourceToggle(HTMLParser):
            attrs = None
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get('id') == 'sourceGroups':
                    self.attrs = attrs
        toggle = SourceToggle()
        toggle.feed((Path(__file__).parent/'index.html').read_text())
        self.assertIsNotNone(toggle.attrs)
        self.assertEqual(toggle.attrs['type'], 'checkbox')
        self.assertNotIn('checked', toggle.attrs)

    def test_only_allowlisted_routes_are_served(self):
        (self.root/'secret.txt').write_text('not public')
        server=ThreadingHTTPServer(('127.0.0.1',0),serve.handler_for(self.root,Path(__file__).parent))
        server.verbose=False
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url='http://127.0.0.1:'+str(server.server_address[1])
        try:
            for path in ['/','/assets/model.js','/bundle/bundle.json','/bundle/result.json']:
                with urlopen(url+path) as response:
                    self.assertEqual(response.status,200)
                    self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
                    self.assertEqual(response.headers['Cache-Control'],'no-store')
            for path in ['/bundle/secret.txt','/bundle/','/assets/serve.py','/bundle/../serve.py','/assets/%2e%2e/serve.py']:
                with self.assertRaises(HTTPError) as caught:
                    urlopen(url+path)
                self.assertEqual(caught.exception.code,404)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
