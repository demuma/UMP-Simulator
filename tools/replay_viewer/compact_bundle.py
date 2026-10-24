#!/usr/bin/env python3
"""Create a fresh, verified viewer-only projection of a completed comparison.

Full native results, audits, summary and source bundle stay untouched. Every
private retirement remains in order; only unused metadata of empty windows is
removed. Nonempty windows, all cells, releases and other result fields are kept.
Process one result at a time. This is packaging, not another scientific result.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil

import serve

SCHEMA='ump.viewer-empty-window-projection.v1'
EMPTY_FIELDS=('start_ms','end_ms','evaluated_at_ms','coordination_cell','cells',
              'completion_reason','policy_id','policy_version')
NOTE=(' Derived viewer projection: every retirement and full nonempty diagnostics are retained; '
      'only unused empty-window metadata is removed. Original full results remain local.')


def require(condition,message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def local_file(root,name):
    require(isinstance(name,str) and bool(name), 'Missing source artifact filename')
    relative=PurePosixPath(name)
    require(not relative.is_absolute() and all(part not in ('','.','..') for part in relative.parts)
            and relative.as_posix()==name and '\\' not in name, 'Unsafe source artifact path')
    current=root
    for part in relative.parts:
        current=current/part
        require(not current.is_symlink(), 'Symbolic links are not valid compact-bundle inputs')
    require(current.is_file() and current.resolve().is_relative_to(root), 'Missing or escaping source artifact')
    return current


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,allow_nan=False,ensure_ascii=False,separators=(',',':'))
        stream.write('\n')


def project_result(original):
    """Keep every retirement, cell and consumed private reason without mutation."""
    require(isinstance(original,dict) and original.get('schema')=='ump.replay-result.v1',
            'Expected a full replay result')
    windows=original.get('windows');require(isinstance(windows,list), 'Missing original private windows')
    projected=[];removed={};empty=0;cells=0
    for row in windows:
        require(isinstance(row,dict) and isinstance(row.get('cells'),list), 'Invalid original private window')
        cells+=len(row['cells'])
        if row['cells']:
            projected.append(row)
            continue
        for field in ('start_ms','end_ms','evaluated_at_ms','cells'):
            require(field in row, 'Empty private window lacks required event metadata')
        if original.get('parameters',{}).get('coordination')=='cell_local':
            require('coordination_cell' in row, 'Local empty window lacks its clearing scope')
        projected.append({field:row[field] for field in EMPTY_FIELDS if field in row})
        for field in set(row)-set(EMPTY_FIELDS):removed[field]=removed.get(field,0)+1
        empty+=1
    result=dict(original);result['windows']=projected
    return result,{'original_window_count':len(windows),'derived_window_count':len(projected),
        'empty_window_count':empty,'nonempty_window_count':len(windows)-empty,'private_cell_count':cells,
        'kept_empty_window_fields':list(EMPTY_FIELDS),'removed_empty_window_fields':dict(sorted(removed.items())),
        'nonempty_windows_unchanged':True,'releases_unchanged':True,'all_other_result_fields_unchanged':True}


def preflight(source):
    """Authenticate summary, manifest and every declared artifact before writing."""
    manifest_path=local_file(source,'bundle.json');summary_path=local_file(source,'summary.json')
    manifest=read(manifest_path);summary=read(summary_path)
    require(summary.get('schema')=='ump.mapped-comparison.v1' and summary.get('status')=='verified',
            'Only a completed verified comparison can be projected')
    require(manifest.get('schema')==serve.SCHEMA and isinstance(manifest.get('variants'),list)
            and 1<=len(manifest['variants'])<=64, 'Invalid original viewer manifest')
    variants=manifest['variants'];ids=[v.get('id') for v in variants]
    require(all(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_-]+',name) for name in ids)
            and len(set(ids))==len(ids) and set(summary.get('cases',{}))==set(ids),
            'Verified summary cases do not match the viewer variants')
    shared=[manifest.get('observations')]
    if manifest.get('map'):
        shared.append(manifest['map'].get('image'))
        if manifest['map'].get('building_access'):shared.append(manifest['map']['building_access'])
    result_names=[v.get('result') for v in variants]
    require(len(set(result_names))==len(result_names), 'Result aliases cannot be projected')
    names=shared+result_names
    require(len(set(names))==len(names) and set(manifest.get('sha256',{}))==set(names),
            'Original manifest must hash exactly its declared artifacts')
    hashes={}
    for name in names:
        path=local_file(source,name);expected=manifest['sha256'][name]
        require(isinstance(expected,str) and re.fullmatch(r'[a-f0-9]{64}',expected), 'Invalid original artifact digest')
        hashes[name]=sha(path);require(hashes[name]==expected,'Original artifact digest mismatch: '+name)
    require(summary.get('protocol',{}).get('observations_sha256')==hashes[manifest['observations']],
            'Verified summary refers to different observations')
    for variant in variants:
        case=summary['cases'][variant['id']];audit=case.get('independent_audit',{})
        require(audit.get('status')=='verified' and audit.get('scalar_valid') is True
                and audit.get('published_policy_violations')==0,
                'Every original case requires a successful independent full audit')
        require(case.get('result_sha256')==hashes[variant['result']],
                'Verified native result digest differs from the manifest')
        policy=local_file(source,variant['id']+'-policy.json')
        require(case.get('config_sha256')==sha(policy), 'Verified policy configuration digest mismatch')
    return manifest,summary,shared,hashes,sha(manifest_path),sha(summary_path)


def compact(source,output):
    source=Path(source);output=Path(output)
    require(not source.is_symlink(), 'Source bundle cannot be a symbolic link')
    source=source.resolve(strict=True)
    require(not output.exists() and not output.is_symlink(), 'Choose a fresh derived viewer directory')
    output=output.resolve()
    require(not output.is_relative_to(source) and not source.is_relative_to(output),
            'Derived viewer must be separate from its unchanged source bundle')
    manifest,summary,shared,hashes,manifest_sha,summary_sha=preflight(source)
    provenance=manifest.get('input_provenance','')+NOTE
    require(len(provenance)<=1024, 'Original provenance leaves no room for an explicit projection notice')
    derived=copy.deepcopy(manifest);derived['input_provenance']=provenance;derived['sha256']={}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.mkdir()  # Atomic exclusive ownership; a concurrent destination is never replaced.
    try:
        for name in shared:
            target=output/name;target.parent.mkdir(parents=True,exist_ok=True)
            with local_file(source,name).open('rb') as incoming,target.open('xb') as outgoing:
                shutil.copyfileobj(incoming,outgoing,1024*1024)
            require(sha(target)==hashes[name], 'Source changed while copying: '+name)
            derived['sha256'][name]=hashes[name]
        for variant in derived['variants']:
            name=variant['result'];path=local_file(source,name)
            require(sha(path)==hashes[name], 'Source result changed before projection: '+name)
            original=read(path);result,counts=project_result(original)
            target=output/name;write(target,result)
            require(sha(path)==hashes[name], 'Source result changed during projection: '+name)
            derived_sha=sha(target);derived['sha256'][name]=derived_sha
            variant['viewer_projection']={'schema':SCHEMA,'source_result':name,'source_result_sha256':hashes[name],
                'derived_result_sha256':derived_sha,'source_bundle_sha256':manifest_sha,
                'verified_summary_sha256':summary_sha,'source_bytes':path.stat().st_size,
                'derived_bytes':target.stat().st_size,**counts,
                'scope':'Viewer-only empty-window field projection after the independent native audit; every retirement remains, and negative/selected nonempty diagnostics are unchanged.'}
            del original,result
        require(sha(local_file(source,'bundle.json'))==manifest_sha and sha(local_file(source,'summary.json'))==summary_sha,
                'Verified source manifest or summary changed during projection')
        for name in shared:require(sha(local_file(source,name))==hashes[name], 'Shared source changed during projection: '+name)
        write(output/'bundle.json',derived)
        serve.validate_bundle(output)
    except BaseException:
        shutil.rmtree(output)
        raise
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path,help='Completed comparison directory with summary.json and bundle.json')
    parser.add_argument('--output',required=True,type=Path,help='Fresh separate derived viewer directory')
    args=parser.parse_args()
    print('Prepared verified compact viewer:',compact(args.source,args.output))


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise SystemExit('Compact viewer preparation failed: '+str(error))
