#!/usr/bin/env python3
"""Synthetic RED/GREEN checks for a held one-line coverage-reporting repair.

This does not execute source generation, read recorded TEST data, fit models,
modify the frozen auditor or infer a physical PASS from an interrupted report.
The target auditor is loaded as a library from an explicitly supplied copy.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools/mapped_scene'),str(ROOT/'tools/evaluation')]
PROFILE='observed_track_window_v1'
TARGET=None


def surface_fixture():
    """Four real synthetic outdoor trips use two non-building surface portals."""
    portals=[dict(id='surface-'+name,kind='surface_access',point=[x,1.],approach=[x,.5])
             for name,x in (('A1',2.),('A2',8.))]
    cfg=dict(simulation=dict(time_step=.05,duration_seconds=3,width=10,height=3),mapped_scene=dict(
        portals=portals,routes=[],people=[],motion=dict(mode='local_navigation',clearance_m=.05,
        navigation=dict(allowed_center_polygons=[dict(outer=[[0.,0.],[10.,0.],[10.,1.05],[0.,1.05]])]))))
    origin=datetime(2026,1,1,tzinfo=timezone.utc)
    stamp=lambda at:(origin+timedelta(milliseconds=at)).isoformat(timespec='milliseconds')
    raw=dict(agents=[dict(data_type='metadata',timestamp=stamp(0))])
    for portal in portals:
        x=portal['point'][0]
        for leaving,start in ((False,0),(True,2000)):
            track=portal['id']+('-out' if leaving else '-in');route='route-'+track
            points=[[x,1.],[x,0.]] if leaving else [[x,0.],[x,1.]]
            start_portal=portal['id'] if leaving else 'bottom-boundary'
            end_portal='bottom-boundary' if leaving else portal['id']
            cfg['mapped_scene']['routes'].append(dict(id=route,points=points,start_portal=start_portal,end_portal=end_portal))
            cfg['mapped_scene']['people'].append(dict(person_id='person-'+track,type='Adult Pedestrian',
                radius_m=.2,speed_mps=1.,episodes=[dict(track_id=track,route_id=route,start_ms=start)]))
            for elapsed in range(0,1000,50):
                y=1-elapsed/1000 if leaving else elapsed/1000
                raw['agents'].append(dict(data_type='agent data',agent_id=track,timestamp=stamp(start+elapsed),
                    position=dict(x=x,y=y),velocity=dict(x=0.,y=0. if elapsed==0 else -1. if leaving else 1.)))
            for event,at,where in (('visible_start',start,start_portal),('visible_end',start+1000,end_portal)):
                raw['agents'].append(dict(data_type='mapped lifecycle event',event=event,observation_track_id=track,
                    timestamp=stamp(at),at_ms=at,portal_id=where,route_id=route))
    context=dict(boundary_intervals=[dict(points=[[0.,0.],[10.,0.]],mode='walking',spawn_supported=True)])
    from shapely.geometry import box
    layers=dict(walking=box(0,0,10,1.3),buildings=box(0,1.3,10,3))
    return cfg,raw,context,layers


class SurfaceAccessDiagnosticTests(unittest.TestCase):
    def check(self,cfg,raw,context,layers,**kwargs):
        return TARGET.audit(cfg,raw,public_context=context,map_layers=layers,**kwargs)

    def test_actual_surface_entries_and_exits_need_no_building_identity(self):
        cfg,raw,context,layers=surface_fixture()
        self.assertTrue(all('building_id' not in p for p in cfg['mapped_scene']['portals']))
        before=deepcopy((cfg,raw,context))
        report=self.check(cfg,raw,context,layers,profile=PROFILE)
        quality=report['movement_coverage_quality']
        self.assertEqual(quality['declared_destination_count'],2)
        self.assertEqual(quality['declared_building_count'],0)
        self.assertEqual(report['surface_access_entries'],2);self.assertEqual(report['surface_access_exits'],2)
        self.assertEqual(report['buildings_with_completed_entries'],0)
        self.assertEqual(report['buildings_with_realized_exits'],0)
        self.assertEqual(report['navigation_static_body_checks'],80)
        self.assertEqual(report['navigation_motion_segments_checked'],80)
        self.assertEqual(report['navigation_terminal_segments_checked'],4)
        self.assertEqual(report['navigation_velocity_checks'],76)
        self.assertEqual(report['boundary_endpoint_checks'],4)
        self.assertGreater(report['independent_gt_body_pair_checks'],0)
        self.assertGreater(report['independent_gt_swept_body_pair_checks'],0)
        self.assertEqual((cfg,raw,context),before)

    def test_unused_surface_portal_does_not_change_building_or_physical_counts(self):
        import test_audit_building_access as maintained
        cfg,raw,context,layers=maintained.navigation_fixture()
        baseline=self.check(cfg,raw,context,layers,profile=PROFILE)
        cfg['mapped_scene']['portals'].append(dict(id='unused-public-stair',kind='surface_access',
            point=[5.,.8],approach=[5.,.5]))
        report=self.check(cfg,raw,context,layers,profile=PROFILE)
        self.assertEqual(report['movement_coverage_quality']['declared_destination_count'],3)
        self.assertEqual(report['movement_coverage_quality']['declared_building_count'],1)
        self.assertEqual(report['surface_access_entries'],0);self.assertEqual(report['surface_access_exits'],0)
        for field in ('navigation_static_body_checks','navigation_motion_segments_checked','navigation_velocity_checks',
                      'independent_gt_body_pair_checks','independent_gt_swept_body_pair_checks','boundary_endpoint_checks'):
            self.assertEqual(report[field],baseline[field])

    def test_nonsurface_building_portal_still_requires_building_identity(self):
        cfg,raw,context,layers=surface_fixture()
        cfg['mapped_scene']['portals'].insert(0,dict(id='malformed-building-door',point=[5.,1.],
            facade=[[4.5,1.],[5.5,1.]],width_m=1.))
        with self.assertRaisesRegex(KeyError,'building_id'):
            self.check(cfg,raw,context,layers,profile=PROFILE)

    def test_legacy_default_report_and_surface_physics_are_unchanged(self):
        cfg,raw,context,layers=surface_fixture()
        implicit=self.check(cfg,raw,context,layers)
        explicit=self.check(cfg,raw,context,layers,profile='legacy_completed_v1')
        self.assertEqual(implicit,explicit)
        self.assertNotIn('validation_profile',implicit)
        self.assertNotIn('movement_coverage_quality',implicit)
        self.assertEqual(implicit['surface_access_entries'],2)
        self.assertEqual(implicit['surface_access_exits'],2)
        self.assertEqual(implicit['navigation_static_body_checks'],80)

    def test_surface_access_keeps_profile_and_approach_geometry_guards(self):
        for failure,expected in (('type','Stairs access uses an ineligible mobility profile'),
                                 ('approach','Surface approach leaves allowed walking geometry')):
            with self.subTest(failure=failure):
                cfg,raw,context,layers=surface_fixture()
                if failure=='type':cfg['mapped_scene']['people'][0]['type']='Adult Cyclist'
                else:cfg['mapped_scene']['portals'][0]['approach']=[2.,2.]
                with self.assertRaisesRegex(ValueError,expected):self.check(cfg,raw,context,layers,profile=PROFILE)

    def test_surface_access_keeps_gt_speed_sweep_and_body_guards(self):
        for failure,expected in (('missing','missing source frames'),('speed','preferred speed'),
                                 ('hole','sweep leaves navigation'),('overlap','body-clearance violation')):
            with self.subTest(failure=failure):
                cfg,raw,context,layers=surface_fixture()
                rows=[r for r in raw['agents'] if r.get('agent_id')=='surface-A1-in']
                if failure=='missing':raw['agents'].remove(rows[5])
                elif failure=='speed':rows[5]['position']['x']+=.2
                elif failure=='hole':
                    cfg['mapped_scene']['motion']['navigation']['allowed_center_polygons'][0]['holes']=[
                        [[1.95,.07],[2.05,.07],[2.05,.08],[1.95,.08]]]
                else:
                    cfg['mapped_scene']['portals'][1]['point'][0]=2.
                    cfg['mapped_scene']['portals'][1]['approach'][0]=2.
                    for route in cfg['mapped_scene']['routes']:
                        if 'surface-A2' in route['id']:
                            for point in route['points']:point[0]=2.
                    for row in raw['agents']:
                        if 'surface-A2' in row.get('agent_id',''):row['position']['x']=2.
                with self.assertRaisesRegex(ValueError,expected):self.check(cfg,raw,context,layers,profile=PROFILE)


def test_names(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from test_names(item)
        else:yield item.id()


def main():
    global TARGET
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--auditor',type=Path,required=True)
    parser.add_argument('--mode',choices=('positive','regression','physics','legacy','window'),required=True)
    parser.add_argument('--expect-red',action='store_true')
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('audit_building_access',args.auditor)
    TARGET=importlib.util.module_from_spec(spec);sys.modules[spec.name]=TARGET;spec.loader.exec_module(TARGET)
    if args.mode=='positive':
        suite=unittest.TestSuite(SurfaceAccessDiagnosticTests(name) for name in (
            'test_actual_surface_entries_and_exits_need_no_building_identity',
            'test_unused_surface_portal_does_not_change_building_or_physical_counts'))
    elif args.mode=='regression':suite=unittest.defaultTestLoader.loadTestsFromTestCase(SurfaceAccessDiagnosticTests)
    else:
        module={'physics':'test_audit_building_access','legacy':'test_run_urban_privacy_sources','window':'test_track_window_source_validation'}[args.mode]
        import os
        if args.mode=='window':os.environ['UMP_WINDOW_AUDITOR_TEST_COPY']=str(args.auditor)
        suite=unittest.defaultTestLoader.loadTestsFromName(module)
    methods=list(test_names(suite));stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    output=stream.getvalue()
    red=(args.expect_red and args.mode=='positive' and result.testsRun==2 and len(result.errors)==2
         and not result.failures and all("KeyError: 'building_id'" in text for _,text in result.errors))
    record=dict(schema='ump.surface-access-diagnostic-regression.v1',
        status='expected_red' if red else 'pass' if result.wasSuccessful() else 'fail',
        auditor_sha256=hashlib.sha256(args.auditor.read_bytes()).hexdigest(),mode=args.mode,
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),test_methods=methods,
        output=output,native_jobs=0,model_fits=0,actual_TEST_raw_or_mechanism_data_read=False)
    print(json.dumps(record,sort_keys=True,indent=2))
    raise SystemExit(0 if red or result.wasSuccessful() and not args.expect_red else 1)


if __name__=='__main__':main()
