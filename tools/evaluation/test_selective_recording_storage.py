"""Synthetic recording storage integration; real archive/binding/collect gates.

Native production and historical source qualification are mocked. No study,
real recording, native executable or model fitting is used.
"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run_urban_selective_suppression as s
from run_semantic_priority_study import fixture, policy


def reference(path):
    path = Path(path)
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def rewrite(path, value):
    """Deliberate synthetic corruption; production writes stay exclusive."""
    Path(path).write_text(json.dumps(value, sort_keys=True, allow_nan=False))


class SelectiveRecordingStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ump-selective-storage-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.output = self.root/'study'; self.output.mkdir()
        (self.output/'groups').mkdir()
        imported_dir = self.root/'historical'; imported_dir.mkdir()
        self.group = dict(group_id='synthetic-train', split='train')
        self.pair = dict(self.group, source='synthetic-pair-receipt')
        data = fixture('rare_local'); data['end_ms'] = 800
        data['batches'] = [b for b in data['batches'] if b['observed_at_ms'] < 800]
        for name, value in (('in.json',data),('out.json',deepcopy(data)),('auxiliary.json',[]),('pair.json',self.pair)):
            s.write(imported_dir/name,value)
        base = policy('rare_local',5,1,20,800,'temporal_first')
        base['policy_tree']['root']['semantic_suppression_fraction'] = {'max':0}
        s.write(self.output/'base-policy.json',base)
        (self.output/'synthetic-binary').write_bytes(b'Synthetic storage fixture; never executable')
        s.write(self.output/'protocol.json',dict(schema='synthetic-storage-protocol',output_directory=str(self.output)))
        self.protocol = dict(original_config=reference(self.output/'base-policy.json'),
                             native_binary=reference(self.output/'synthetic-binary'),minimum_free_bytes=0)
        imported = dict(directory=str(imported_dir), split='train',
                        files={name:reference(imported_dir/name) for name in ('in.json','out.json','auxiliary.json','pair.json')})
        self.context = dict(manifest={'groups':[self.group]},
                            history={'original_groups':{self.group['group_id']:imported}},
                            all_historical_rows=[self.row(m,w) for w in ('IN','OUT') for m in s.OLD_METHODS])
        self.original_rows = deepcopy(self.context['all_historical_rows'])
        self.start(patch.object(s,'reference',side_effect=reference))
        self.start(patch.object(s,'authenticated',side_effect=self.authenticated))
        self.validator = self.start(patch.object(s.legacy.previous,'validate_pair_import',side_effect=self.validate_pair))
        self.source_check = self.start(patch.object(s.primary.split,'verify_actual_sources'))
        self.native = self.start(patch.object(s,'run_case',side_effect=self.run_case))
        self.regional = self.start(patch.object(s,'compose',side_effect=self.compose))

    def start(self, mock):
        value=mock.start();self.addCleanup(mock.stop);return value

    def authenticated(self, value):
        path=Path(value['path'])
        s.require(path.resolve().is_relative_to(self.root) and reference(path)==value,'Synthetic artifact reference changed')
        return path

    def validate_pair(self, directory, imported):
        self.authenticated(imported['files']['pair.json'])
        s.require(reference(directory/'pair.json')['sha256']==imported['files']['pair.json']['sha256'],
                  'Synthetic pair changed')
        pair=s.source.load(directory/'pair.json')
        s.require(pair==self.pair,'Synthetic pair identity changed')
        return pair

    def row(self, method, world):
        return dict(group_id=self.group['group_id'],split='train',world=world,label=int(world=='IN'),
                    method_id=method['id'],features=[0.]*111,scalar_features=[0.]*31,auxiliary_features=[0.]*8,
                    controls=dict(prior_only=.5,unprotected=int(world=='IN'),no_output_features=[0.]*111),
                    utility={'retained_observations':0})

    def produce(self, directory, method, world, *, regional=False):
        name=method['id'];row=self.row(method,world)
        values={name+'-policy.json':{'synthetic_policy':True},name+'-row.json':row,
                name+'-public.json':{'schema':'ump.public-transcript.v2','releases':[]},
                name+'-audit.json':{'status':'verified','scalar':{'valid':True}}}
        if regional:
            values[name+'-family.json']={'schema':s.regional.FAMILY_SCHEMA,'synthetic':True}
        else:
            values[name+'.json']={'schema':'ump.replay-result.v1','releases':[],'windows':[]}
            values[name+'-execution.json']={'status':'complete','seconds':0}
        for relative,value in values.items():s.write(directory/relative,value)
        record=dict(method_id=name,world=world,status='verified',
            role='auxiliary' if method in s.AUXILIARY_METHODS else 'headline',
            independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0),
            artifacts={relative:s.primary.artifact(directory,directory/relative) for relative in values})
        s.write(directory/(name+'-receipt.json'),record)
        return record,row

    def run_case(self,directory,data_path,base,method,group,world,knowledge,protocol,**kwargs):
        return self.produce(directory,method,world)

    def compose(self,directory,base,group,world,knowledge,records,data,query_reference):
        s.require(set(records)=={m['id'] for m in s.NATIVE_METHODS},'Synthetic regional dependency family differs')
        return self.produce(directory,s.NEW_METHODS[1],world,regional=True)

    def process(self):
        return s.process_group(self.output,self.protocol,self.context,self.group)

    def collect(self):
        return s.collect(self.output,self.protocol,self.context,verify_archives=True,require_complete=False)

    @property
    def directory(self):
        return self.output/'groups'/self.group['group_id']

    def test_real_archive_sidecar_collect_roundtrip_and_no_recording_retry(self):
        summary=self.process()
        self.assertEqual(summary['status'],'verified')
        rows,summaries,auxiliary=self.collect()
        self.assertEqual((len(rows),len(summaries),len(auxiliary)),(28,1,6))
        self.assertEqual([r for r in rows if r['method_id'] in s.BASE_IDS],self.original_rows)
        self.assertEqual(self.context['all_historical_rows'],self.original_rows)
        self.assertEqual(self.native.call_count,18);self.assertEqual(self.regional.call_count,2)
        self.assertEqual(self.validator.call_count,2)
        self.source_check.assert_called_once_with(self.context['manifest'],[self.pair],s.ROOT)
        side=s.source.load(self.directory/'selective-receipt.json')
        self.assertEqual(side['protocol_sha256'],s.source.sha(self.output/'protocol.json'))
        self.assertEqual(side['summary'],reference(self.directory/'summary.json'))
        for world in ('IN','OUT'):
            work=self.directory/world;name=s.NATIVE_METHODS[0]['id']
            self.assertFalse((work/(name+'.json')).exists())
            with gzip.open(work/(name+'.json.gz'),'rt') as stream:
                self.assertEqual(json.load(stream)['schema'],'ump.replay-result.v1')
            self.assertTrue((work/(name+'-policy.json')).is_file())
        with self.assertRaisesRegex(ValueError,'retries'):
            self.process()
        self.assertEqual(self.native.call_count,18)

    def test_reforged_compressed_hash_still_rejects_changed_archived_original_bytes(self):
        self.process()
        archive_path=self.directory/'archive-receipt.json';archives=s.source.load(archive_path)
        name=s.NATIVE_METHODS[0]['id']+'.json';entry=archives['IN'][name]
        compressed=self.directory/'IN'/entry['path']
        with gzip.open(compressed,'wb') as stream:stream.write(b'{"forged_original":true}')
        entry['sha256']=s.source.sha(compressed);rewrite(archive_path,archives)
        summary_path=self.directory/'summary.json';summary=s.source.load(summary_path)
        summary['archives']=s.primary.artifact(self.directory,archive_path);rewrite(summary_path,summary)
        side_path=self.directory/'selective-receipt.json';side=s.source.load(side_path)
        side['summary']=reference(summary_path);rewrite(side_path,side)
        with self.assertRaisesRegex(ValueError,'Archived original bytes changed'):
            self.collect()

    def test_changed_stored_row_hash_is_rejected(self):
        self.process();path=self.directory/'rows.json';rows=s.source.load(path)
        rows[0]['features'][0]=1;rewrite(path,rows)
        with self.assertRaisesRegex(ValueError,'provenance hash mismatch'):
            self.collect()

    def test_sidecar_protocol_binding_mismatch_is_rejected(self):
        self.process();path=self.directory/'selective-receipt.json';side=s.source.load(path)
        side['protocol_sha256']='0'*64;rewrite(path,side)
        with self.assertRaisesRegex(ValueError,'Recording binding changed'):
            self.collect()

    def test_collect_invokes_pair_validator_and_rejects_swapped_pair(self):
        self.process();pair=self.directory/'pair.json';pair.unlink()
        s.write(pair,dict(self.pair,group_id='swapped-group'))
        with self.assertRaisesRegex(ValueError,'Synthetic pair changed'):
            self.collect()
        self.assertEqual(self.validator.call_count,2)
        self.assertEqual(self.validator.call_args.args[0],self.directory)
        self.assertEqual(s.source.load(Path(self.context['history']['original_groups'][self.group['group_id']]['files']['pair.json']['path'])),self.pair)


if __name__=='__main__':unittest.main()
