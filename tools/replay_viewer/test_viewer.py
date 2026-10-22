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
import unittest
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

    def test_matching_bundle_validates(self):
        _,files=serve.validate_bundle(self.root)
        self.assertEqual(set(files),{'bundle.json','observations.json','result.json'})

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
