#!/usr/bin/env python3
"""Build a source-authenticated, isolated live measurement executable (no DB I/O)."""
import argparse, hashlib, json, platform, shutil, subprocess
from pathlib import Path

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-revision');a=p.parse_args()
 root=a.repo.resolve();out=a.output.resolve();here=Path(__file__).resolve().parent
 if out.exists() or root==out or root in out.parents:raise ValueError('Require a fresh output directory outside the repository')
 revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
 if a.expected_revision and not revision.startswith(a.expected_revision):raise ValueError('Unexpected production revision')
 original={str(f.relative_to(root)):digest(f) for directory in ['simulator/src','simulator/include'] for f in sorted((root/directory).glob('*')) if f.is_file()}
 original['simulator/CMakeLists.txt']=digest(root/'simulator/CMakeLists.txt')
 out.mkdir(mode=0o700);project=out/'project';project.mkdir()
 subprocess.run(['python3',str(here/'stage_instrumentation.py'),'--repo',str(root),'--output',str(out/'overlay')],check=True)
 for name in ['src','include']:shutil.copytree(root/'simulator'/name,project/name)
 for file in (out/'overlay/simulator').rglob('*'):
  if file.is_file():shutil.copyfile(file,project/file.relative_to(out/'overlay/simulator'))
 shutil.copyfile(here/'LiveTiming.hpp',project/'include/LiveTiming.hpp')
 cmake=(root/'simulator/CMakeLists.txt').read_text().split('# Opt-in integration test:')[0]+'\ntarget_link_libraries(Simulator PRIVATE ump_semantic)\n'
 (project/'CMakeLists.txt').write_text(cmake)
 subprocess.run(['cmake','-S',str(project),'-B',str(out/'build'),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_OSX_ARCHITECTURES='+platform.machine()],check=True)
 subprocess.run(['cmake','--build',str(out/'build'),'--parallel','4'],check=True)
 if any(digest(root/path)!=wanted for path,wanted in original.items()):raise RuntimeError('Production source changed during isolated build')
 result={'schema':'ump.live-instrumented-build.v1','revision':revision,'worktree_status':subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True),'production_sources_sha256':original,'prepared_sources_sha256':{str(f.relative_to(project)):digest(f) for f in sorted(project.rglob('*')) if f.is_file()},'tool_sha256':{f.name:digest(f) for f in [Path(__file__),here/'stage_instrumentation.py',here/'LiveTiming.hpp']},'binary_sha256':digest(out/'build/Simulator'),'production_modified':False}
 (out/'build-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'binary':str(out/'build/Simulator'),'sha256':result['binary_sha256']}))
if __name__=='__main__':main()
