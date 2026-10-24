"""Viewer projections preserve complete retirement behavior and frozen evidence."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import zlib

import compact_bundle as compact
import serve


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def png():
    def chunk(kind,payload):
        return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\xff\xff\xff'))+chunk(b'IEND',b'')


def fixture(root):
    coverage=dict(x=0,y=0,width=80,height=80,leaf_depth=2)
    observations={'schema':'ump.observation-replay.v1','run_id':'fixture','sensor_id':'agbs',
        'coverage':coverage,'sampling_period_ms':100,'end_ms':500,
        'batches':[{'observed_at_ms':at,'status':'measured','observations':[
            {'id':'episode-1','type':'Adult Pedestrian','x':1,'y':1}]} for at in (100,200,300,400)]}
    parent=dict(cell_id=12,depth=1,x=0,y=0,width=40,height=40)
    first=dict(cell_id=48,depth=2,x=0,y=0,width=20,height=20)
    second=dict(cell_id=49,depth=2,x=20,y=0,width=20,height=20)
    def cell(geometry,selected):
        return {**geometry,'observation_contributions':1,'distinct_road_users':1,'mean_sample_occupancy':1,
            'selected':selected,'reason':'policy_satisfied' if selected else 'minimum_support_failed',
            'assessment_status':'pass' if selected else 'fail','metrics':{'distinct_contributors':1},
            'checks':[{'metric':'distinct_contributors','min':1 if selected else 5,'max':None,
                'observed':1,'status':'pass' if selected else 'fail','reason':'fixture'}]}
    def window(start,end,scope,cells):
        return {'start_ms':start,'end_ms':end,'evaluated_at_ms':end,'coordination_cell':scope,'cells':cells,
            'policy_id':'fixture-policy','policy_version':'1','completion_reason':'fixture_finalization',
            'truncated':False,'expected_samples':1,'measured_samples':1,'unavailable_samples':0,
            'missing_samples':0,'coverage':'complete','strategy':'spatial_first','temporal_extensions':0,
            'temporal_decisions':[{'action':'fixture_action','status':'pass'}]}
    windows=[window(0,100,parent,[cell(parent,True)]),window(100,200,first,[]),
             window(200,300,parent,[cell(first,False),cell(second,True)]),window(300,400,parent,[])]
    releases=[]
    for row in windows:
        selected=[{k:v for k,v in c.items() if k not in ('selected','reason','assessment_status','metrics','checks')}
                  for c in row['cells'] if c['selected']]
        if selected:releases.append({'start_ms':row['start_ms'],'end_ms':row['end_ms'],'sealed_at_ms':row['end_ms'],
            'coordination_cell':row['coordination_cell'],'policy_id':'fixture-policy','policy_version':'1','cells':selected})
    result={'schema':'ump.replay-result.v1','classification':'private_research_diagnostics',
        'source':{k:observations[k] for k in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms')},
        'parameters':{'coordination':'cell_local','strategy':'spatial_first'},
        'input_observation_contributions':4,'runtime':{'processing_ms':1.25},'windows':windows,'releases':releases}
    access={'schema':'ump.building-access.v1','bounds':{k:coverage[k] for k in ('x','y','width','height')},
        'buildings':[],'portals':[]}
    manifest={'schema':serve.SCHEMA,'title':'Projection fixture','identity_unit':'visible_episode_track',
        'input_provenance':'Small synthetic packaging fixture.','observations':'observations.json',
        'map':{'image':'map_background.png','building_access':'building_access.json',
            'bounds':access['bounds'],'attribution':'Fixture context, not a surveyed map.','labels':[],'legend':[]},
        'variants':[{'id':'one','label':'One','result':'one.json','policy_tree_id':'fixture-policy','policy_tree_version':'1'}]}
    for name,value in [('observations.json',observations),('one.json',result),('one-policy.json',{'policy':'fixture'}),('building_access.json',access)]:write(root/name,value)
    (root/'map_background.png').write_bytes(png())
    manifest['sha256']={name:compact.sha(root/name) for name in ('observations.json','one.json','map_background.png','building_access.json')}
    write(root/'bundle.json',manifest)
    summary={'schema':'ump.mapped-comparison.v1','status':'verified',
        'protocol':{'observations_sha256':manifest['sha256']['observations.json']},'cases':{'one':{
            'result_sha256':manifest['sha256']['one.json'],'config_sha256':compact.sha(root/'one-policy.json'),
            'independent_audit':{'status':'verified','scalar_valid':True,'published_policy_violations':0}}}}
    write(root/'summary.json',summary)
    serve.validate_bundle(root)
    return observations,result,manifest,summary


class CompactBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name).resolve()
        self.source=self.root/'source';self.source.mkdir();self.output=self.root/'derived'
        self.observations,self.result,self.manifest,self.summary=fixture(self.source)

    def tearDown(self):self.temporary.cleanup()

    def test_only_empty_window_unused_fields_are_removed_without_mutation(self):
        original=copy.deepcopy(self.result);projected,report=compact.project_result(self.result)
        self.assertEqual(self.result,original)
        self.assertEqual(len(projected['windows']),len(original['windows']))
        for before,after in zip(original['windows'],projected['windows']):
            if before['cells']:self.assertEqual(before,after)
            else:self.assertEqual(after,{key:before[key] for key in compact.EMPTY_FIELDS if key in before})
        self.assertEqual({k:v for k,v in projected.items() if k!='windows'},{k:v for k,v in original.items() if k!='windows'})
        self.assertEqual(report['empty_window_count'],2);self.assertEqual(report['private_cell_count'],3)
        self.assertEqual(report['removed_empty_window_fields']['temporal_decisions'],2)
        self.assertTrue(all(row['completion_reason']=='fixture_finalization' for row in projected['windows']))

    def test_fresh_projection_is_self_contained_hashed_and_does_not_modify_full_source(self):
        before={path.name:path.read_bytes() for path in self.source.iterdir()}
        compact.compact(self.source,self.output)
        self.assertEqual({path.name:path.read_bytes() for path in self.source.iterdir()},before)
        manifest,files=serve.validate_bundle(self.output)
        self.assertEqual(set(files),{'bundle.json','observations.json','one.json','map_background.png','building_access.json'})
        for name in ('observations.json','map_background.png','building_access.json'):
            self.assertEqual((self.output/name).read_bytes(),before[name])
        projection=manifest['variants'][0]['viewer_projection']
        self.assertEqual(projection['schema'],compact.SCHEMA)
        self.assertEqual(projection['source_result_sha256'],self.summary['cases']['one']['result_sha256'])
        self.assertEqual(projection['derived_result_sha256'],compact.sha(self.output/'one.json'))
        self.assertEqual(projection['verified_summary_sha256'],hashlib.sha256(before['summary.json']).hexdigest())
        self.assertEqual(projection['source_bundle_sha256'],hashlib.sha256(before['bundle.json']).hexdigest())
        self.assertLess(projection['derived_bytes'],projection['source_bytes'])
        self.assertIn('every retirement',manifest['input_provenance'])
        self.assertFalse(any(path.is_symlink() for path in self.output.rglob('*')))

    @unittest.skipUnless(shutil.which('node'),'Node is required for the actual replay-model equivalence gate')
    def test_actual_js_model_equivalence_at_all_boundaries_and_reverse_seeks(self):
        compact.compact(self.source,self.output)
        script=r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const M=require(process.argv[1]),original=JSON.parse(fs.readFileSync(process.argv[2])),derived=JSON.parse(fs.readFileSync(process.argv[3])),source=JSON.parse(fs.readFileSync(process.argv[4]));
const stamps=[0,source.end_ms,...original.windows.flatMap(r=>[r.start_ms,r.end_ms,r.evaluated_at_ms]),...original.releases.map(r=>r.sealed_at_ms)];
const times=[...new Set(stamps.flatMap(t=>[t-1,t,t+1]).filter(t=>t>=0&&t<=source.end_ms))].sort((a,b)=>a-b);
const interval=r=>r?{start_ms:r.start_ms,end_ms:r.end_ms,evaluated_at_ms:r.evaluated_at_ms,sealed_at_ms:r.sealed_at_ms,coordination_cell:r.coordination_cell,cells:r.cells,completion_reason:r.completion_reason}:null;
const view=v=>({local:v.local,asOfMs:v.asOfMs,eventCount:v.eventCount,latestEvent:interval(v.latestEvent),entries:v.entries.map(e=>({key:e.key,cell:e.cell,row:interval(e.row),fragments:e.fragments,eventTime:e.eventTime,eventIndex:e.eventIndex,partial:e.partial}))});
const a=M.buildSourceIndex(source),b=M.buildSourceIndex(source);
for(const privateMode of [false,true]){
 assert.deepEqual(M.eventTimes([{result:original}],source.end_ms,privateMode),M.eventTimes([{result:derived}],source.end_ms,privateMode));
 for(const t of [...times,...times.slice().reverse()]){
  const first=M.mosaicAt(original,t,privateMode),second=M.mosaicAt(derived,t,privateMode);
  assert.deepEqual(view(first),view(second));
  assert.deepEqual(M.releaseAccounting(original,t),M.releaseAccounting(derived,t));
  for(let i=0;i<first.entries.length;i++)assert.deepEqual(M.sourceGroups(a,first.entries[i].cell,first.entries[i].row,t,true),M.sourceGroups(b,second.entries[i].cell,second.entries[i].row,t,true));
 }
}
assert.equal(M.mosaicAt(derived,400,true).entries.length,0,'the final empty parent still clears every private footprint');
assert.ok(M.mosaicAt(derived,300,true).entries.some(e=>e.cell.selected===false),'negative policy decisions remain visible');
assert.deepEqual(M.variantIdentity({result:original}),M.variantIdentity({result:derived}));
assert.deepEqual(original.releases,derived.releases);
process.stdout.write('Equivalent replay/model states at '+times.length+' boundary timestamps in both seek directions and channels.\n');
'''
        run=subprocess.run([shutil.which('node'),'-e',script,str(Path(__file__).with_name('model.js')),
            str(self.source/'one.json'),str(self.output/'one.json'),str(self.source/'observations.json')],text=True,capture_output=True,timeout=20)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_unverified_incomplete_or_failed_independent_evidence_is_rejected_before_output(self):
        for mutation in ('running','wrong_schema','missing_case','audit_failed','scalar_failed','violations','native_digest','policy_digest','observation_digest'):
            with self.subTest(mutation=mutation):
                value=copy.deepcopy(self.summary);case=value['cases']['one']
                if mutation=='running':value['status']='running'
                if mutation=='wrong_schema':value['schema']='unverified'
                if mutation=='missing_case':value['cases']={}
                if mutation=='audit_failed':case['independent_audit']['status']='fail'
                if mutation=='scalar_failed':case['independent_audit']['scalar_valid']=False
                if mutation=='violations':case['independent_audit']['published_policy_violations']=1
                if mutation=='native_digest':case['result_sha256']='0'*64
                if mutation=='policy_digest':case['config_sha256']='0'*64
                if mutation=='observation_digest':value['protocol']['observations_sha256']='0'*64
                write(self.source/'summary.json',value)
                with self.assertRaises(ValueError):compact.compact(self.source,self.output)
                self.assertFalse(self.output.exists())

    def test_manifest_digest_mismatch_and_undeclared_hashes_are_rejected(self):
        for mutation in ('wrong','missing','extra'):
            with self.subTest(mutation=mutation):
                value=copy.deepcopy(self.manifest)
                if mutation=='wrong':value['sha256']['one.json']='0'*64
                if mutation=='missing':value['sha256'].pop('one.json')
                if mutation=='extra':value['sha256']['summary.json']=compact.sha(self.source/'summary.json')
                write(self.source/'bundle.json',value)
                with self.assertRaises(ValueError):compact.compact(self.source,self.output)
                self.assertFalse(self.output.exists())

    def test_escaping_or_symbolic_source_artifacts_are_rejected(self):
        for name in ('../outside.json','/tmp/outside.json','one/../one.json','one\\result.json'):
            with self.subTest(name=name):
                value=copy.deepcopy(self.manifest);value['variants'][0]['result']=name
                write(self.source/'bundle.json',value)
                with self.assertRaises(ValueError):compact.compact(self.source,self.output)
        write(self.source/'bundle.json',self.manifest)
        outside=self.root/'outside.json';outside.write_bytes((self.source/'one.json').read_bytes())
        (self.source/'one.json').unlink();(self.source/'one.json').symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'Symbolic'):compact.compact(self.source,self.output)
        self.assertFalse(self.output.exists())

    def test_existing_or_nested_destination_is_preserved(self):
        self.output.mkdir();(self.output/'keep.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError,'fresh'):compact.compact(self.source,self.output)
        self.assertEqual((self.output/'keep.txt').read_text(),'keep')
        with self.assertRaisesRegex(ValueError,'separate'):compact.compact(self.source,self.source/'new')
        self.assertFalse((self.source/'new').exists())

    def test_failed_projection_or_validation_removes_only_its_owned_new_output(self):
        before={path.name:path.read_bytes() for path in self.source.iterdir()}
        with mock.patch.object(compact.serve,'validate_bundle',side_effect=ValueError('fixture validation failure')):
            with self.assertRaisesRegex(ValueError,'validation failure'):compact.compact(self.source,self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual({path.name:path.read_bytes() for path in self.source.iterdir()},before)

    def test_source_change_during_projection_is_detected_and_not_published(self):
        original=compact.project_result
        def changed(result):
            projected=original(result)
            with (self.source/'one.json').open('a') as stream:stream.write(' ')
            return projected
        with mock.patch.object(compact,'project_result',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed during projection'):compact.compact(self.source,self.output)
        self.assertFalse(self.output.exists())

    def test_common_window_empty_events_keep_legacy_scope_absence(self):
        result=copy.deepcopy(self.result);result['parameters']['coordination']='common_window'
        for row in result['windows']:row.pop('coordination_cell')
        projected,_=compact.project_result(result)
        self.assertNotIn('coordination_cell',projected['windows'][1])
        self.assertEqual(projected['windows'][1]['cells'],[])


if __name__=='__main__':unittest.main()
