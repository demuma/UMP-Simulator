#!/usr/bin/env python3
"""Two isolated 90-s source runs: full independent audit and private-GT renaming.

Retains compact configuration, logs and results only. Never exports sampled GT or
observations; removes only its own initially empty UUID-named MongoDB namespaces.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time
import uuid
import yaml


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shell_json(shell, script=None, file=None):
    command=[shell,'mongodb://localhost:27017/?serverSelectionTimeoutMS=3000','--quiet']
    command += ['--file',str(file)] if file else ['--eval',script]
    result=subprocess.run(command,text=True,capture_output=True,timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout.strip().splitlines()[-1])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=pathlib.Path,required=True,help='Fresh output directory')
    args=parser.parse_args()
    if args.output.exists(): parser.error('Choose a fresh output directory')
    repo=pathlib.Path(__file__).resolve().parents[2]
    binary=repo/'simulator/build/Simulator'
    shell=shutil.which('mongosh')
    if not shell or not binary.is_file(): parser.error('Build the Simulator and provide mongosh first')
    binary_sha=sha(binary)
    args.output.mkdir(parents=True)
    cases=[]
    for label,rename in [('reference',False),('renamed_private_gt',True)]:
        base='UMP_Mapped_'+uuid.uuid4().hex
        names=[base,base+'_Releases',base+'_Private']
        folder=args.output/label
        subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('build_mapped_scene.py')),
            '--repo',str(repo),'--output',str(folder),'--database',base,'--duration-s','90'],check=True)
        cfg=yaml.safe_load((folder/'config.yaml').read_text())
        if rename:
            for index,person in enumerate(cfg['mapped_scene']['people']):
                person['person_id']=f'renamed-private-oracle-{index:03}'
            (folder/'config.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False,allow_unicode=True))
        manifest=json.loads((folder/'scene_manifest.json').read_text())
        manifest['configuration_sha256']=sha(folder/'config.yaml')
        manifest['verification_variant']=label
        (folder/'scene_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        names_json=json.dumps(names)
        existing=shell_json(shell,'const names='+names_json+'; print(JSON.stringify(names.filter(n=>db.getSiblingDB(n).getCollectionNames().length>0)));')
        if existing: raise RuntimeError('Refusing to reuse nonempty test namespaces: '+str(existing))
        report={'variant':label,'binary_sha256':binary_sha,'config_sha256':sha(folder/'config.yaml')}
        try:
            if sha(binary)!=binary_sha: raise RuntimeError('Simulator changed between source runs')
            started=time.perf_counter()
            result=subprocess.run([str(binary)],cwd=folder,text=True,capture_output=True,timeout=240)
            report['binary_wall_seconds']=time.perf_counter()-started
            report['gross_source_speedup']=90/report['binary_wall_seconds']
            (folder/'simulator.log').write_text(result.stdout+result.stderr)
            if result.returncode: raise RuntimeError('Simulator failed: '+result.stderr)
            script=folder/'audit.js'
            script.write_text('const cfg='+json.dumps(cfg)+';\n'+pathlib.Path(__file__).with_name('audit_live_scene.js').read_text())
            report['audit']=shell_json(shell,file=script)
            if report['audit'].get('status')!='pass': raise RuntimeError('Independent source audit failed')
            if sha(binary)!=binary_sha: raise RuntimeError('Simulator changed during source audit')
        finally:
            # Names were generated here and confirmed empty before any source write.
            cleanup=shell_json(shell,'const names='+names_json+'; for(const n of names) db.getSiblingDB(n).dropDatabase(); '
                'print(JSON.stringify({owned:names,remaining:names.filter(n=>db.getSiblingDB(n).getCollectionNames().length>0)}));')
            report['cleanup']=cleanup
            (folder/'compact_result.json').write_text(json.dumps(report,indent=2)+'\n')
            if cleanup['remaining']: raise RuntimeError('Owned namespace cleanup failed')
        cases.append(report)
        print(json.dumps({'case':label,'status':'pass','wall_s':report['binary_wall_seconds'],
            'releases':report['audit']['recipient_release_documents'],'owned_databases_removed':3}),flush=True)
    invariant=all(cases[0]['audit'][key]==cases[1]['audit'][key] for key in
        ['normalized_raw_sha256','normalized_recipient_sha256'])
    if not invariant: raise RuntimeError('Private GT renaming changed operational observations or releases')
    production={str(p.relative_to(repo)):sha(p) for folder in ['simulator/src','simulator/include']
                for p in sorted((repo/folder).glob('*')) if p.suffix in {'.hpp','.cpp','.tpp'}}
    final={'status':'pass','same_binary_sha256':binary_sha,'private_gt_renaming_invariant':True,
           'cases':cases,'production_source_sha256':production,
           'runtime_scope':'Gross binary wall time includes DB I/O and startup. This is not a per-step deadline or optimization comparison.',
           'data_scope':'No sampled motion/observation files exported. Only owned initially-empty test namespaces were removed.'}
    (args.output/'verification.json').write_text(json.dumps(final,indent=2)+'\n')
    print(json.dumps({'status':'pass','private_gt_renaming_invariant':True,'report':str(args.output/'verification.json')}))


if __name__=='__main__':
    main()
