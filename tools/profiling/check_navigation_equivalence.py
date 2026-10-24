#!/usr/bin/env python3
"""Compare staged and working native geometry/navigation without saving movement.

Two temporary native builds use identical configuration readers and headers. One
includes MappedScene.cpp from --baseline-ref, the other the working file. Python
SHA-256 hashes canonical binary stdout directly: no frame or oracle data is saved.
Geometry probes include the exact configured rings, holes and segments, seeded
points, edge/vertex tolerance cases and synthetic scales from 1e-6 to 1e12.
The source-only motion stream contains every frame and diagnostic at every fixed
step, followed by the complete private lifecycle. This is equivalence evidence
for the specified corpus/horizon, not a proof for all floating-point inputs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import pathlib
import platform
import subprocess
import tempfile
import threading
import time

HARNESS = r'''
#include "MappedSceneConfiguration.hpp"
#include "MappedScene.subject.cpp"
#include <array>
#include <chrono>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <random>
#include <unordered_set>
using namespace ump;
// Explicit little-endian fields; double bit patterns retain signed zero/ULPs.
void number(std::uint64_t n){for(int i=0;i<8;++i){std::cout.put(char(n&255));n>>=8;}}
void real(double d){std::uint64_t n;static_assert(sizeof(n)==sizeof(d));std::memcpy(&n,&d,sizeof(n));number(n);}
void word(const std::string&s){number(s.size());std::cout.write(s.data(),s.size());}
void point(Point p){real(p.x);real(p.y);}
void diagnostics(const MappedMotionDiagnostics&d){
 number(d.blockedMotionSteps);number(d.admissionWaitSteps);number(d.realizedStarts);number(d.realizedEnds);
 number(d.overlapViolations);number(d.mergeAdmissionWaitSteps);number(d.navigationSteeringSteps);number(d.navigationReplans);
 number(d.navigationReplanFailures);number(d.navigationCandidateChecks);number(d.navigationMaxSearchNodes);
 number(d.maxConsecutiveStopMs);number(d.activeStalledTracks);number(d.pendingTracks);number(d.activeTracks);
}
MappedSceneConfig configuration(const char*path){
 const auto yaml=YAML::LoadFile(path);std::unordered_set<std::string>profiles;
 for(const auto&r:yaml["agents"]["road_user_taxonomy"])profiles.insert(r["type"].as<std::string>());
 return readMappedSceneConfiguration(yaml["mapped_scene"],yaml["simulation"]["width"].as<double>(),yaml["simulation"]["height"].as<double>(),profiles);
}
struct Probes{
 std::uint64_t rings=0,locations=0,segments=0,polygons=0;std::array<std::uint64_t,3>results{};
 std::mt19937_64 rng{0x4d41505045444e41ULL};
 double uniform(double a,double b){return a+(b-a)*double(rng()>>11)*0x1.0p-53;}
 void location(Point p,const std::vector<Point>&r){word("ring");number(rings);point(p);const int v=ump::ringLocation(p,r);number(std::int64_t(v));++locations;++results[v+1];}
 void ring(const std::vector<Point>&r,std::size_t randomCount){
  ++rings;word("ring_geometry");number(rings);number(r.size());
  double minx=INFINITY,miny=INFINITY,maxx=-INFINITY,maxy=-INFINITY;
  for(const auto&p:r){point(p);minx=std::min(minx,p.x);miny=std::min(miny,p.y);maxx=std::max(maxx,p.x);maxy=std::max(maxy,p.y);}
  const double tol=1e-8,inf=std::numeric_limits<double>::infinity();
  const std::array<double,11> offsets{{-2*tol,-std::nextafter(tol,inf),-tol,-std::nextafter(tol,0.),-.5*tol,0.,.5*tol,std::nextafter(tol,0.),tol,std::nextafter(tol,inf),2*tol}};
  for(std::size_t i=0,j=r.size()-1;i<r.size();j=i++){
   const auto a=r[j],b=r[i];const double dx=b.x-a.x,dy=b.y-a.y,length=std::hypot(dx,dy);
   for(double t:{0.,.25,.5,.75,1.}){
    const Point p{a.x+t*dx,a.y+t*dy};location(p,r);
    for(double d:offsets){
     location({p.x+d,p.y},r);location({p.x,p.y+d},r);
     if(length)location({p.x-d*dy/length,p.y+d*dx/length},r);
    }
    for(double target:{-inf,inf}){location({std::nextafter(p.x,target),p.y},r);location({p.x,std::nextafter(p.y,target)},r);}
   }
  }
  const double margin=std::max({1e-7,(maxx-minx)*.1,(maxy-miny)*.1});
  for(std::size_t i=0;i<randomCount;++i)location({uniform(minx-margin,maxx+margin),uniform(miny-margin,maxy+margin)},r);
 }
 void segment(Point a,Point b,const std::vector<MappedNavigationPolygon>&p){word("segment");point(a);point(b);number(ump::navigationSegment(a,b,p));++segments;}
 void geometry(const std::vector<MappedNavigationPolygon>&p,std::size_t randomCount,double width,double height){
  for(const auto&q:p){ring(q.outer,randomCount);for(const auto&h:q.holes)ring(h,randomCount);}
  // Hole/union semantics and long complete segments use the production oracle.
  for(std::size_t i=0;i<randomCount;++i){
   Point a{uniform(-.1*width,1.1*width),uniform(-.1*height,1.1*height)};
   Point b{uniform(-.1*width,1.1*width),uniform(-.1*height,1.1*height)};
   segment(a,b,p);segment(a,a,p);
   for(const auto&q:p){word("polygon");point(a);number(ump::polygonContains(a,q));++polygons;}
  }
  for(const auto&q:p){
   std::vector<const std::vector<Point>*>all{&q.outer};for(const auto&h:q.holes)all.push_back(&h);
   for(const auto*rp:all){const auto&r=*rp;for(std::size_t i=0,j=r.size()-1;i<r.size();j=i++){
    const auto a=r[j],b=r[i];segment(a,b,p);const Point m{(a.x+b.x)/2,(a.y+b.y)/2};
    segment({m.x-2e-8,m.y-2e-8},{m.x+2e-8,m.y+2e-8},p);
    segment({0,m.y},{width,m.y},p);segment({m.x,0},{m.x,height},p);
   }}
  }
 }
};
void probes(const MappedSceneConfig&config,std::size_t count){
 MappedScene scene(config);Probes p;word("ump.navigation-equivalence.probes.v1");
 p.geometry(scene.configuration().navigation.allowedCenterPolygons,count,config.width,config.height);
 for(double scale:{1e-6,1.,80.,1e6,1e12}){
  std::vector<MappedNavigationPolygon>polygons{{{{0,0},{10*scale,0},{10*scale,10*scale},{0,10*scale}},{{{3*scale,3*scale},{7*scale,3*scale},{7*scale,7*scale},{3*scale,7*scale}}}},
   {{{12*scale,0},{20*scale,0},{20*scale,2*scale},{15*scale,2*scale},{15*scale,10*scale},{12*scale,10*scale}},{}},
   {{{22*scale,0},{30*scale,scale},{26*scale,9*scale}}, {}}};
  p.geometry(polygons,count,30*scale,10*scale);
  // Long nearly horizontal/vertical edges with a large translation as well.
  p.ring({{1e12,1e12},{1e12+scale,1e12},{1e12+scale,1e12+scale},{1e12,1e12+scale}},count);
 }
 std::cout.flush();std::cerr<<"{\"ring_count\":"<<p.rings<<",\"location_count\":"<<p.locations<<",\"segment_count\":"<<p.segments<<",\"polygon_count\":"<<p.polygons
 <<",\"outside\":"<<p.results[0]<<",\"boundary\":"<<p.results[1]<<",\"inside\":"<<p.results[2]<<"}\n";
}
void motion(const MappedSceneConfig&config,AggregationTime horizon){
 MappedScene scene(config);if(horizon<0||horizon%config.motionStepMs)throw std::invalid_argument("Horizon must align with source motion step");
 word("ump.navigation-equivalence.motion.v1");number(config.motionStepMs);number(horizon);std::uint64_t frames=0,records=0;
 const auto start=std::chrono::steady_clock::now();double lastProgress=0;
 for(AggregationTime t=0;t<=horizon;t+=config.motionStepMs){
  scene.advanceTo(t);const auto frame=scene.frameAt(t);word("frame");number(t);number(frame.size());++frames;records+=frame.size();
  for(const auto&r:frame){word(r.trackId);word(r.type);word(r.routeId);number(std::int64_t(r.nextWaypointIndex));point(r.position);point(r.velocity);}
  diagnostics(scene.motionDiagnostics());
  const double wall=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
  if(wall-lastProgress>=30){std::cerr<<"progress simulation_ms="<<t<<" wall_s="<<wall<<"\n";lastProgress=wall;}
 }
 word("lifecycle");number(scene.events().size());
 for(const auto&e:scene.events()){number(static_cast<int>(e.kind));number(e.atMs);word(e.personId);word(e.trackId);word(e.routeId);word(e.portalId);}
 diagnostics(scene.motionDiagnostics());std::cout.flush();const auto d=scene.motionDiagnostics();
 std::size_t expected=0;for(const auto&p:config.people)expected+=p.episodes.size();std::set<std::string>starts,ends;AggregationTime lastEnd=0;
 for(const auto&e:scene.events())if(e.kind==MappedEventKind::EpisodeStart)starts.insert(e.trackId);else{ends.insert(e.trackId);lastEnd=std::max(lastEnd,e.atMs);}
 const bool complete=starts.size()==expected&&ends==starts&&scene.events().size()==2*expected&&d.realizedStarts==expected&&d.realizedEnds==expected&&d.activeTracks==0&&d.pendingTracks==0&&d.activeStalledTracks==0&&d.overlapViolations==0;
 std::cerr<<"{\"frames\":"<<frames<<",\"visible_records\":"<<records<<",\"events\":"<<scene.events().size()<<",\"realized_starts\":"<<d.realizedStarts<<",\"realized_ends\":"<<d.realizedEnds
 <<",\"active_tracks\":"<<d.activeTracks<<",\"pending_tracks\":"<<d.pendingTracks<<",\"overlap_violations\":"<<d.overlapViolations<<",\"expected_episodes\":"<<expected<<",\"unique_starts\":"<<starts.size()<<",\"unique_ends\":"<<ends.size()<<",\"last_end_ms\":"<<lastEnd<<",\"complete_cohort\":"<<(complete?"true":"false")<<"}\n";
}
int main(int argc,char**argv){try{
 if(argc!=5)throw std::invalid_argument("Expected mode config horizon_ms random_probes");const auto config=configuration(argv[2]);
 const std::string mode=argv[1];if(mode=="probes")probes(config,std::stoull(argv[4]));else if(mode=="motion")motion(config,std::stoll(argv[3]));else throw std::invalid_argument("Unknown mode");
 if(!std::cout)throw std::runtime_error("Binary output stream failed");return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stream_digest(command, budget):
    """Hash stdout without persisting it; kill even a silent/blocked native run."""
    started = time.perf_counter()
    digest = hashlib.sha256()
    byte_count = 0
    expired = threading.Event()
    # Stderr contains aggregate counts/progress only, never raw oracle records.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        def timeout():
            expired.set()
            process.kill()
        timer = threading.Timer(budget, timeout)
        timer.start()
        try:
            while chunk := process.stdout.read(65536):
                digest.update(chunk)
                byte_count += len(chunk)
            code = process.wait()
        finally:
            timer.cancel()
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
        errors.seek(0)
        lines = errors.read().decode(errors='replace').splitlines()
    if expired.is_set() or code:
        raise RuntimeError(f'Native run failed (return={code}, timeout={expired.is_set()}): '+ '\n'.join(lines[-5:]))
    summary = json.loads(lines[-1])
    return {'sha256': digest.hexdigest(), 'stream_bytes': byte_count,
            'wall_seconds': time.perf_counter()-started, 'summary': summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=pathlib.Path, required=True, help='Fresh local output directory; compact summaries/builds only')
    parser.add_argument('--config', type=pathlib.Path, action='append', required=True, help='Exact saved source YAML; repeat for serial cases')
    parser.add_argument('--baseline-ref', default='HEAD', help='Git commit to stage MappedScene.cpp from')
    parser.add_argument('--horizon-s', type=int, action='append', help='One common horizon or one per --config, in config order; default 120')
    parser.add_argument('--wall-budget-s', type=float, default=300, help='Per native invocation, including probes')
    parser.add_argument('--random-probes', type=int, default=10000, help='Seeded samples per ring/geometry set in addition to all boundary probes')
    parser.add_argument('--probes-only', action='store_true')
    parser.add_argument('--require-complete', action='store_true', help='Require every scheduled episode to finish in both motion runs')
    args = parser.parse_args()
    if any(h < 0 for h in (args.horizon_s or [120])) or args.random_probes < 1 or args.random_probes > 1000000 or not math.isfinite(args.wall_budget_s) or args.wall_budget_s <= 0:
        parser.error('Nonnegative horizon, 1..1000000 probes and finite positive budget required')
    if args.probes_only and args.require_complete:
        parser.error('--require-complete needs motion comparisons')
    repo = pathlib.Path(__file__).resolve().parents[2]
    configs = [p.resolve(strict=True) for p in args.config]
    if len(set(configs)) != len(configs):
        parser.error('Duplicate configurations are not allowed')
    horizons = args.horizon_s or [120]
    if len(horizons) not in (1, len(configs)):
        parser.error('Supply either one common horizon or one per configuration')
    if len(horizons) == 1:
        horizons *= len(configs)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    baseline_commit = subprocess.run(['git', 'rev-parse', '--verify', args.baseline_ref+'^{commit}'], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    baseline = subprocess.run(['git', 'show', baseline_commit+':simulator/src/MappedScene.cpp'], cwd=repo, capture_output=True, check=True).stdout
    source_paths = ['simulator/src/MappedScene.cpp','simulator/src/MappedSceneConfiguration.cpp','simulator/include/MappedScene.hpp','simulator/include/MappedSceneConfiguration.hpp','simulator/include/AggregationInput.hpp']
    source_hashes = {p: sha(repo/p) for p in source_paths}
    result = {'schema': 'ump.navigation-equivalence.v1', 'baseline_commit': baseline_commit,
              'baseline_motion_source_sha256': hashlib.sha256(baseline).hexdigest(),
              'working_source_hashes': source_hashes, 'tool_sha256': sha(pathlib.Path(__file__)),
              'compiler_version': subprocess.run(['c++','--version'], capture_output=True, text=True, check=True).stdout.strip(),
              'platform': platform.platform(), 'machine': platform.machine(),
              'scope': 'Exact binary frame/diagnostic/lifecycle equality and native geometry-oracle probes for listed configurations/horizon. Source-only, no aggregate publication pipeline, no saved frame data; not a universal proof or hard real-time benchmark.',
              'horizons_ms': [h*1000 for h in horizons], 'random_probes_per_ring_or_geometry': args.random_probes,
              'require_complete': args.require_complete, 'builds': {}, 'cases': [], 'passed': False}
    for variant, source in [('baseline', baseline), ('working', (repo/source_paths[0]).read_bytes())]:
        folder = output/variant
        folder.mkdir()
        (folder/'MappedScene.subject.cpp').write_bytes(source)
        harness = folder/'equivalence.cpp'
        harness.write_text(HARNESS)
        binary = folder/'equivalence'
        command = ['c++','-std=c++17','-O3','-DNDEBUG','-I',str(repo/'simulator/include'),'-I','/opt/homebrew/include',str(harness),str(repo/'simulator/src/MappedSceneConfiguration.cpp'),'-L','/opt/homebrew/lib','-lyaml-cpp','-Wl,-rpath,/opt/homebrew/lib','-o',str(binary)]
        print(f'Build {variant}', flush=True)
        subprocess.run(command, check=True)
        result['builds'][variant] = {'source_sha256': sha(folder/'MappedScene.subject.cpp'), 'harness_sha256': sha(harness), 'binary_sha256': sha(binary), 'compile_command': command}
    report = output/'summary.json'
    report.write_text(json.dumps(result, indent=2)+'\n')
    for config, horizon in zip(configs, horizons):
        row = {'config_path': str(config), 'config_sha256': sha(config), 'horizon_ms': horizon*1000}
        for mode in ['probes'] + ([] if args.probes_only else ['motion']):
            outcomes = {}
            for variant in ['baseline','working']:
                print(f'{mode}: {config.parent.name} / {variant}', flush=True)
                command = [str(output/variant/'equivalence'), mode, str(config), str(horizon*1000), str(args.random_probes)]
                outcomes[variant] = stream_digest(command, args.wall_budget_s)
            outcomes['equal'] = all(outcomes['baseline'][key] == outcomes['working'][key] for key in ['sha256','stream_bytes','summary'])
            row[mode] = outcomes
            print(f"{mode}: {'PASS' if outcomes['equal'] else 'FAIL'}, digest={outcomes['working']['sha256']}", flush=True)
        if sha(config) != row['config_sha256']:
            raise RuntimeError('Configuration changed during comparison: '+str(config))
        result['cases'].append(row)
        report.write_text(json.dumps(result, indent=2)+'\n')
    if source_hashes != {p: sha(repo/p) for p in source_paths}:
        raise RuntimeError('Production sources changed during comparison; rerun on a fixed version')
    result['passed'] = all(row[mode]['equal'] for row in result['cases'] for mode in ['probes']+([] if args.probes_only else ['motion']))
    if args.require_complete:
        result['passed'] = result['passed'] and all(row['motion'][v]['summary']['complete_cohort'] for row in result['cases'] for v in ['baseline','working'])
    report.write_text(json.dumps(result, indent=2)+'\n')
    print(str(report), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
