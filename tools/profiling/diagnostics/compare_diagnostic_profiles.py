#!/usr/bin/env python3
"""Require complete same-input logical equality and optional exact JSONL equality."""
import argparse, hashlib, json
from pathlib import Path


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda:file.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def diagnostic_files(root):
    result={}
    for file in sorted((root/'diagnostics').glob('*.jsonl')):
        kind=file.name.split('-',1)[0]
        if kind not in {'candidates','selection'} or kind in result:
            raise ValueError('Unexpected diagnostic file set')
        result[kind]={'bytes':file.stat().st_size,'sha256':digest(file)}
    if result and set(result)!={'candidates','selection'}:raise ValueError('Both diagnostic files are required when diagnostics are enabled')
    return result


def compare(first,second,require_diagnostics=False):
    a=json.loads((first/'result.json').read_text());b=json.loads((second/'result.json').read_text())
    a.pop('runtime');b.pop('runtime')
    if a!=b:raise ValueError('Complete logical results differ')
    af=diagnostic_files(first);bf=diagnostic_files(second)
    same=af==bf
    if require_diagnostics and not same:raise ValueError('Full diagnostic JSONL bytes differ')
    return {'schema':'ump.diagnostic-profile-comparison.v1','complete_logical_equal_except_runtime':True,
        'logical_result_sha256':hashlib.sha256(json.dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'first_diagnostics':af,'second_diagnostics':bf,'diagnostic_jsonl_byte_equal':same,
        'input_contributions':a['input_observation_contributions'],'accounted_contributions':a['accounted_observation_contributions'],
        'windows':len(a['windows']),'releases':len(a['releases'])}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('first',type=Path);p.add_argument('second',type=Path)
    p.add_argument('--require-diagnostics',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args();result=compare(a.first.resolve(),a.second.resolve(),a.require_diagnostics)
    text=json.dumps(result,indent=2)+'\n'
    if a.output:
        with a.output.open('x') as file:file.write(text)
    print(text,end='')

if __name__=='__main__':main()
