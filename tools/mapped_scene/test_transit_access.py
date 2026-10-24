#!/usr/bin/env python3
"""Source-only subway/yield acceptance; raw trajectories and databases are unused."""
import copy
import importlib.util
import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import yaml
from shapely.geometry import LineString, Point

HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import build_mapped_scene as builder
import transit_access as transit
import urban_traffic_scene as urban
REPO=HERE.parents[1]
DATABASE='UMP_Mapped_00000000000000000000000000000000'

class TransitAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,cls.local,cls.layers,_,cls.provenance=builder.load_source(REPO)
        cls.scene,cls.context,cls.construction,cls.audit=builder.storefront_scene(str(REPO),20261024,64,180,500,
            urban_traffic=True,subway_access=True,rider_priority=True)

    def test_exact_public_metadata_and_conservative_overhead_classification(self):
        ground,layers,data=transit.ground_environment(REPO,self.local,self.layers,self.provenance['source_geometry_sha256'])
        removed={(p['osm_type'],p['osm_id']) for p,g in self.local}-{(p['osm_type'],p['osm_id']) for p,g in ground}
        self.assertEqual(removed,{('way',425508816),('way',425508817)})
        self.assertEqual(data['stop_area']['osm_id'],300934)
        for row in data['entrances']:
            point=Point(row['node']['local_point_m'])
            self.assertTrue(self.layers['building'].covers(point))
            self.assertFalse(layers['building'].covers(point))
        roofs=[r for r in self.context['buildings'] if r.get('overhead')]
        self.assertEqual({r['osm_id'] for r in roofs},transit.OVERHEAD_WAY_IDS)
        self.assertTrue(all(r['ground_obstacle'] is False and r['polygons'] for r in roofs))
        self.assertTrue(all(r.get('ground_obstacle',True) for r in self.context['buildings'] if not r.get('overhead')))
        # An unrelated overhead-looking object is NOT blanket permission.
        props=copy.deepcopy(next(p for p,g in self.local if p['osm_id']==425508816));props['osm_id']=999999
        geom=next(g for p,g in self.local if p['osm_id']==425508816)
        extra,_layers,_=transit.ground_environment(REPO,self.local+[(props,geom)],self.layers,self.provenance['source_geometry_sha256'])
        self.assertIn(999999,{p['osm_id'] for p,g in extra if p['kind']=='building'})

    def test_source_and_metadata_mismatches_fail_closed(self):
        with self.assertRaises(ValueError):transit.metadata(REPO,self.local,'0'*64)
        altered=copy.deepcopy(self.local)
        node=next(p for p,g in altered if p['osm_id']==280355670);node['osm_version']+=1
        with self.assertRaises(ValueError):transit.metadata(REPO,altered,self.provenance['source_geometry_sha256'])
        altered=copy.deepcopy(self.local)
        roof=next(p for p,g in altered if p['osm_id']==425508816);roof['tags']['layer']='0'
        with self.assertRaises(ValueError):transit.metadata(REPO,altered,self.provenance['source_geometry_sha256'])
        with mock.patch.object(pathlib.Path,'read_bytes',return_value=b'{}'),self.assertRaises(ValueError):
            transit.metadata(REPO,self.local,self.provenance['source_geometry_sha256'])

    def test_typed_surface_portals_fit_checked_existing_geometry_without_fake_facades(self):
        safe=builder.storefront_module().geometry_from_rows(self.scene['motion']['navigation']['allowed_center_polygons'])
        source_portals={p['id']:p for p in self.scene['portals']}
        surfaces=[p for p in self.context['portals'] if p.get('kind')=='surface_access']
        self.assertEqual({p['surface_access']['reference'] for p in surfaces},{'A1','A2'})
        for portal in surfaces:
            native=source_portals[portal['id']]
            self.assertNotIn('building_id',native);self.assertNotIn('facade',native)
            self.assertNotIn('surface_access',native)
            self.assertAlmostEqual(math.dist(portal['point'],portal['approach']),1.5)
            self.assertAlmostEqual(LineString(portal['admission_segment']).length,1.2)
            self.assertTrue(safe.buffer(1e-8).covers(LineString([portal['point'],portal['approach']])))
            self.assertTrue(safe.buffer(1e-8).covers(LineString(portal['admission_segment'])))
            self.assertEqual(portal['surface_access']['wheelchair'],'no')

    def test_independent_station_trips_have_eligible_profiles_and_both_directions(self):
        routes={r['id']:r for r in self.scene['routes']}
        counts={portal:{'in':0,'out':0} for portal in ('subway-A1','subway-A2')}
        tracks=[]
        for person in self.scene['people']:
            for episode in person['episodes']:
                tracks.append(episode['track_id'])
                route=routes[episode['route_id']]
                for endpoint,direction in [('end_portal','in'),('start_portal','out')]:
                    if route[endpoint] in counts:
                        self.assertIn(person['type'],transit.ELIGIBLE_PROFILES)
                        self.assertEqual(len(person['episodes']),1)
                        counts[route[endpoint]][direction]+=1
        self.assertEqual(len(tracks),len(set(tracks)))
        self.assertTrue(all(count>0 for directions in counts.values() for count in directions.values()))
        self.assertEqual(sum(sum(row.values()) for row in counts.values()),10)
        self.assertEqual(self.audit['status'],'pass')
        self.assertEqual(max(r['body_building_intersection_outside_portal_m2'] for r in self.audit['routes'].values()),0)
        self.assertNotIn('person_id',json.dumps(self.context))

    def test_crossing_resources_are_finite_explicit_and_do_not_reduce_bodies(self):
        resources=self.scene['motion']['navigation']['crossings']
        self.assertEqual(len(resources),5)
        self.assertEqual(resources,self.context['navigation']['crossing_priority']['resources'])
        for row in resources:
            self.assertEqual(set(row['priority_spaces']),{'carriageway-east','carriageway-west'})
            self.assertEqual(row['max_batch_size'],6)
            self.assertEqual(row['pedestrian_max_wait_ms'],8000)
            self.assertEqual(row['pedestrian_admission_ms'],2000)
            self.assertEqual(row['rider_service_ms'],1500)
        original={r['type']:r['radius'] for r in builder.profiles()}
        original.update(urban.RIDER_RADII)
        self.assertTrue(all(p['radius_m']==original[p['type']] for p in self.scene['people']))
        self.assertEqual(self.scene['motion']['clearance_m'],.05)

    def test_new_source_repeats_without_mutating_frozen_layers(self):
        before=self.layers['building'].wkb
        repeated=builder.storefront_scene(str(REPO),20261024,64,180,500,urban_traffic=True,subway_access=True,rider_priority=True)
        self.assertEqual((self.scene,self.context,self.construction,self.audit),repeated)
        self.assertEqual(self.layers['building'].wkb,before)
        plain=builder.storefront_scene(str(REPO),20261024,32,120,1000,urban_traffic=True)
        explicit=builder.storefront_scene(str(REPO),20261024,32,120,1000,urban_traffic=True,subway_access=False,rider_priority=False)
        self.assertEqual(plain,explicit)
        self.assertNotIn('transit_access',plain[1]);self.assertNotIn('crossings',plain[0]['motion']['navigation'])
        # Reviewed historical full scene/context/construction/audit digest.
        self.assertEqual(builder.storefront_module().canonical_hash(plain),LEGACY_DIGEST)

    @unittest.skipUnless(os.environ.get('UMP_TRANSIT_DRAIN_TEST_BINARY'),'Opt-in native source drainage integration')
    def test_native_combined_source_drains_and_all_tracks_are_observed(self):
        cfg=builder.make_config(REPO,DATABASE,180,False,20261024,'storefronts',64,500,
            urban_traffic=True,subway_access=True,rider_priority=True)
        expected=sum(len(p['episodes']) for p in cfg['mapped_scene']['people'])
        self.assertEqual(expected,85)
        with tempfile.TemporaryDirectory(prefix='ump-transit-drain-test-') as temporary:
            path=pathlib.Path(temporary)/'config.yaml';path.write_text(yaml.safe_dump(cfg,sort_keys=False))
            result=subprocess.run([os.environ['UMP_TRANSIT_DRAIN_TEST_BINARY'],'--drain-config',str(path),
                '--end-ms','300000','--require-observed-period-ms','100'],capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn(f'scheduled={expected} starts={expected} ends={expected} active=0 pending=0',result.stdout)
            self.assertIn(f'observed={expected}',result.stdout)
            self.assertIn('stalled=0 overlaps=0',result.stdout)
            self.assertIn('crossing_pedestrian_wait_steps=',result.stdout)
            print(result.stdout.strip(),flush=True)

LEGACY_DIGEST='054fcf2dbdfdbf7826fc67c798239b2327aa294002efea7581f006960fe61e67'
if __name__=='__main__':unittest.main()
