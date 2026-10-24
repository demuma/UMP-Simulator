#!/usr/bin/env python3
"""Bounded, source-only benchmark of frozen storefront route generation and navigation.

No MongoDB, sensors, aggregation, renderer or sampled movement files are used.
Outputs are compact aggregate timings; YAML configurations and the temporary native
harness remain in the selected local output directory (normally ignored results/).
A cohort is not a claim about simultaneous active tracks. Native cases run serially.
"""
from __future__ import annotations
import argparse
import functools
import hashlib
import importlib.util
import json
import math
import pathlib
import platform
import subprocess
import sys
import time

HARNESS = r'''
#include "MappedSceneConfiguration.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <set>
#include <vector>
#ifdef UMP_NAV_BENCH_COMPONENTS
void umpNavigationBenchmarkPrintComponents();
#endif
using Clock=std::chrono::steady_clock;
double ms(Clock::time_point start){return std::chrono::duration<double,std::milli>(Clock::now()-start).count();}
void distribution(const std::vector<double>& input){
 auto a=input;std::sort(a.begin(),a.end());
 const auto q=[&](double p){return a.empty()?0.0:a[static_cast<std::size_t>(std::ceil(p*a.size()))-1];};
 std::cout<<"{\"count\":"<<a.size()<<",\"mean_ms\":"<<(a.empty()?0.0:std::accumulate(a.begin(),a.end(),0.0)/a.size())
 <<",\"p50_ms\":"<<q(.5)<<",\"p95_ms\":"<<q(.95)<<",\"p99_ms\":"<<q(.99)<<",\"max_ms\":"<<(a.empty()?0.0:a.back())
 <<",\"over_50ms\":"<<std::count_if(a.begin(),a.end(),[](double t){return t>50;})<<"}";
}
int main(int argc,char**argv){try{
 if(argc!=4)throw std::invalid_argument("config horizon_ms wall_budget_s");
 const auto begin=Clock::now();auto before=Clock::now();auto yaml=YAML::LoadFile(argv[1]);const double yamlMs=ms(before);
 std::unordered_set<std::string> profiles;for(const auto& r:yaml["agents"]["road_user_taxonomy"])profiles.insert(r["type"].as<std::string>());
 before=Clock::now();auto config=readMappedSceneConfiguration(yaml["mapped_scene"],yaml["simulation"]["width"].as<double>(),yaml["simulation"]["height"].as<double>(),profiles);const double adaptationMs=ms(before);
 before=Clock::now();ump::MappedScene scene(config);const double constructorMs=ms(before);
 const auto horizon=std::stoll(argv[2]);const double budget=std::stod(argv[3]);
 std::vector<double> advance,frames;std::size_t peak=0,frameCount=0;long long reached=0;bool budgetExceeded=false;
 struct Bucket{std::vector<double> advance,frames;std::size_t peak=0;};std::vector<Bucket>buckets((horizon+39999)/40000);
 scene.advanceTo(0);
 for(long long t=config.motionStepMs;t<=horizon;t+=config.motionStepMs){
  before=Clock::now();scene.advanceTo(t);const auto dt=ms(before);advance.push_back(dt);
  before=Clock::now();const auto frame=scene.frameAt(t);const auto ft=ms(before);frames.push_back(ft);frameCount+=frame.size();peak=std::max(peak,frame.size());
  auto&b=buckets[(t-1)/40000];b.advance.push_back(dt);b.frames.push_back(ft);b.peak=std::max(b.peak,frame.size());reached=t;
  if(ms(begin)>budget*1000){budgetExceeded=true;break;}
 }
 const auto d=scene.motionDiagnostics();const double totalMs=ms(begin);std::size_t expected=0,edges=0,serializedVertices=0;
 for(const auto&p:config.people)expected+=p.episodes.size();for(const auto&p:config.navigation.allowedCenterPolygons){serializedVertices+=p.outer.size();for(const auto&h:p.holes)serializedVertices+=h.size();}
 for(const auto&p:scene.configuration().navigation.allowedCenterPolygons){edges+=p.outer.size();for(const auto&h:p.holes)edges+=h.size();}
 std::cout<<std::setprecision(12)<<"{\"schema\":\"ump.mapped-navigation-benchmark.v1\",\"scope\":\"Source motion only; excludes policy, aggregation, MongoDB and rendering. Censored at requested horizon or wall budget.\",\"cohort_people\":"<<config.people.size()<<",\"scheduled_episodes\":"<<expected
 <<",\"requested_horizon_ms\":"<<horizon<<",\"reached_horizon_ms\":"<<reached<<",\"wall_budget_exceeded\":"<<(budgetExceeded?"true":"false")
 <<",\"wall_seconds\":"<<totalMs/1000<<",\"source_speedup\":"<<reached/totalMs
 <<",\"yaml_read_ms\":"<<yamlMs<<",\"configuration_adaptation_ms\":"<<adaptationMs<<",\"constructor_ms\":"<<constructorMs
 <<",\"peak_actual_active_tracks\":"<<peak<<",\"mean_actual_active_tracks\":"<<(frames.empty()?0.0:double(frameCount)/frames.size())<<",\"navigation_polygon_edges\":"<<edges<<",\"navigation_serialized_ring_vertices\":"<<serializedVertices<<",\"advance\":";distribution(advance);std::cout<<",\"frame\":";distribution(frames);
 std::cout<<",\"realized_starts\":"<<d.realizedStarts<<",\"realized_ends\":"<<d.realizedEnds<<",\"active_tracks\":"<<d.activeTracks<<",\"pending_tracks\":"<<d.pendingTracks<<",\"active_stalled_tracks\":"<<d.activeStalledTracks<<",\"max_stop_ms\":"<<d.maxConsecutiveStopMs<<",\"overlap_violations\":"<<d.overlapViolations
 <<",\"navigation_steering_steps\":"<<d.navigationSteeringSteps<<",\"navigation_replans\":"<<d.navigationReplans<<",\"navigation_replan_failures\":"<<d.navigationReplanFailures<<",\"navigation_candidate_checks\":"<<d.navigationCandidateChecks<<",\"navigation_max_search_nodes\":"<<d.navigationMaxSearchNodes
 <<",\"time_buckets\":[";bool first=true;for(std::size_t i=0;i<buckets.size();++i){const auto&b=buckets[i];if(b.advance.empty())continue;if(!first)std::cout<<",";first=false;std::cout<<"{\"from_ms\":"<<i*40000<<",\"to_ms\":"<<std::min<long long>((i+1)*40000,reached)<<",\"peak_active\":"<<b.peak<<",\"advance\":";distribution(b.advance);std::cout<<",\"frame\":";distribution(b.frames);std::cout<<"}";}std::cout<<"]";
#ifdef UMP_NAV_BENCH_COMPONENTS
 std::cout<<",\"component_timings_inclusive\":";umpNavigationBenchmarkPrintComponents();
#endif
 std::cout<<"}\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    parser.add_argument('--cases',default='64:1000,128:1000,500:1000,500:150',help='people:arrival_interval_ms pairs; intervals must be 50-ms aligned')
    parser.add_argument('--horizon-s',type=int,default=120)
    parser.add_argument('--wall-budget-s',type=float,default=180)
    parser.add_argument('--seed',type=int,default=20261023)
    parser.add_argument('--reuse-harness',action='store_true')
    parser.add_argument('--generation-only',action='store_true',help='Measure only frozen-map preprocessing and global route construction')
    parser.add_argument('--instrument-components',action='store_true',help='Stage a temporary source copy with inclusive geometry/A*/door timers; compare separately from pristine timings')
    args=parser.parse_args()
    if args.horizon_s<=0 or not math.isfinite(args.wall_budget_s) or args.wall_budget_s<=0:parser.error('Horizon and finite wall budget must be positive')
    repo=pathlib.Path(__file__).resolve().parents[2]
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    cases=[]
    for text in args.cases.split(','):
        people,interval=map(int,text.split(':'))
        if not 5<=people<=2048 or interval<50 or interval%50:parser.error('Expected 5..2048 people and 50-ms aligned intervals')
        cases.append((people,interval))
    if len(set(cases))!=len(cases):parser.error('Duplicate benchmark cases are not allowed')
    for people,interval in cases:
        if (output/f'people-{people}-arrival-{interval}ms').exists():
            parser.error('Refusing to overwrite an existing benchmark case; choose a fresh output directory')
    source_paths=['simulator/src/MappedScene.cpp','simulator/src/MappedSceneConfiguration.cpp','simulator/include/MappedScene.hpp','tools/mapped_scene/build_mapped_scene.py','tools/mapped_scene/storefront_scene.py','tools/mapped_scene/building_access.py','simulator/include/MappedSceneConfiguration.hpp','simulator/examples/temporal-aggregation/config.yaml','tools/osm_regions/build_map.py','tools/osm_regions/data/moenckeberg/source_geometry.geojson.gz','tools/osm_regions/data/moenckeberg/close/policy.json','tools/osm_regions/data/moenckeberg/close/poi_labels.json']
    source_hashes={p:digest(repo/p) for p in source_paths}
    compiler_version=subprocess.run(['c++','--version'],capture_output=True,text=True,check=True).stdout.strip()
    result={'compiler_version':compiler_version,'generation_only':args.generation_only,'component_instrumentation':args.instrument_components,'benchmark_tool_sha256':digest(pathlib.Path(__file__)),'schema':'ump.mapped-navigation-benchmark-set.v1','platform':platform.platform(),'machine':platform.machine(),'seed':args.seed,'horizon_s':args.horizon_s,'source_hashes':source_hashes,'scope':'Single process, serial cases; no concurrent benchmark cases. Not an end-to-end simulator deadline benchmark. All finite runs are horizon-censored unless all scheduled episodes ended.','cases':[]}
    summary_path=output/'summary.json'
    if summary_path.exists():
        previous=json.loads(summary_path.read_text())
        if any(previous.get(key,False if key in ['component_instrumentation','generation_only'] else None)!=result[key] for key in ['source_hashes','seed','horizon_s','component_instrumentation','generation_only']):
            raise RuntimeError('Existing benchmark summary has different sources, seed or horizon')
        result['cases']=previous['cases']
        if 'compile_command' in previous:result['compile_command']=previous['compile_command']
        if any(f'people-{people}-arrival-{interval}ms' in {r['id'] for r in result['cases']} for people,interval in cases):
            raise RuntimeError('Case already measured; use a fresh output directory for a repeat')
    harness=output/'mapped_navigation_benchmark.cpp';binary=output/'mapped_navigation_benchmark'
    build_manifest=output/'build_manifest.json'
    if args.reuse_harness and not args.generation_only:
        if not build_manifest.is_file():raise RuntimeError('Cannot reuse an unverified harness; rebuild in a fresh output directory')
        built=json.loads(build_manifest.read_text())
        if (built['source_hashes']!=source_hashes or built['component_instrumentation']!=args.instrument_components
                or built['harness_sha256']!=digest(harness) or built['binary_sha256']!=digest(binary)
                or built['harness_sha256']!=hashlib.sha256(HARNESS.encode()).hexdigest()):
            raise RuntimeError('Harness or production sources changed; refuse reuse')
    if not args.reuse_harness and not args.generation_only:
        harness.write_text(HARNESS)
        motion_source=repo/'simulator/src/MappedScene.cpp'
        profile_flags=[]
        if args.instrument_components:
            motion_source=output/'MappedScene.instrumented.cpp'
            source=(repo/'simulator/src/MappedScene.cpp').read_text()
            preamble=r'''#include <chrono>
#include <iostream>
#include <utility>
namespace ump_nav_bench {
struct Counter { unsigned long long calls=0; double ms=0; };
Counter geometry, replan, doors;
struct Scope { Counter& counter; std::chrono::steady_clock::time_point start=std::chrono::steady_clock::now();
 explicit Scope(Counter& c):counter(c) {}
 ~Scope(){++counter.calls;counter.ms+=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();} };
}
void umpNavigationBenchmarkPrintComponents(){
 std::cout<<"{";bool first=true;
 for(const auto& item:{std::pair<const char*,ump_nav_bench::Counter*>("navigation_segment_allowed",&ump_nav_bench::geometry),{"replan_navigation",&ump_nav_bench::replan},{"update_navigation_doors",&ump_nav_bench::doors}}){
 if(!first)std::cout<<",";first=false;
 std::cout<<"\""<<item.first<<"\":{\"calls\":"<<item.second->calls<<",\"wall_ms\":"<<item.second->ms<<"}";}std::cout<<"}";
}
'''
            for signature,counter in [('bool MappedScene::navigationSegmentAllowed(Point from,Point to,const MappedRoute* route) const {','geometry'),('bool MappedScene::replanNavigation(const std::string& id,Point goal) {','replan'),('void MappedScene::updateNavigationDoors(AggregationTime nowMs) {','doors')]:
                if source.count(signature)!=1:raise RuntimeError('Instrumentation signature mismatch: '+signature)
                source=source.replace(signature,signature+'\n    ump_nav_bench::Scope benchmarkScope(ump_nav_bench::'+counter+');')
            motion_source.write_text(preamble+source)
            profile_flags=['-DUMP_NAV_BENCH_COMPONENTS']
        command=['c++','-std=c++17','-O3','-DNDEBUG','-I',str(repo/'simulator/include'),'-I','/opt/homebrew/include',str(harness),str(motion_source),str(repo/'simulator/src/MappedSceneConfiguration.cpp'),'-L','/opt/homebrew/lib','-lyaml-cpp','-Wl,-rpath,/opt/homebrew/lib','-o',str(binary)]
        subprocess.run(command+profile_flags,check=True)
        result['compile_command']=command+profile_flags
        build_manifest.write_text(json.dumps({'source_hashes':source_hashes,'component_instrumentation':args.instrument_components,
            'harness_sha256':digest(harness),'binary_sha256':digest(binary),'compile_command':command+profile_flags},indent=2)+'\n')
    spec=importlib.util.spec_from_file_location('ump_mapped_builder',repo/'tools/mapped_scene/build_mapped_scene.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    # Wrappers measure inclusive component time without changing planning or routes.
    totals={}
    def wrap(obj,name,key):
        original=getattr(obj,name)
        @functools.wraps(original)
        def timed(*a,**kw):
            started=time.perf_counter()
            try:return original(*a,**kw)
            finally:
                row=totals.setdefault(key,{'calls':0,'wall_seconds':0.0});row['calls']+=1;row['wall_seconds']+=time.perf_counter()-started
        setattr(obj,name,timed)
    wrap(builder,'load_source','frozen_source_load_and_functional_layers')
    sf=builder.storefront_module()
    # The production accessor returns a freshly imported module on each call.
    # Reuse this instrumented module only within the benchmark process; no
    # routing decisions, cache lifetime per scene or geometry are changed.
    builder.storefront_module=lambda:sf
    for name in ['build_geometry','audit_scene']:wrap(sf,name,name)
    for name in ['__init__','route','varied_route']:wrap(sf.SafeRouter,name,'router_'+name)
    import yaml
    for people,interval in cases:
        totals.clear();name=f'people-{people}-arrival-{interval}ms';folder=output/name;folder.mkdir(exist_ok=True)
        print(f'Start generation {name}',flush=True);start=time.perf_counter()
        cfg=builder.make_config(repo,'UNUSED_NO_DATABASE',args.horizon_s,False,args.seed,'storefronts',people,interval)
        generation=time.perf_counter()-start
        path=folder/'config.yaml';path.write_text(yaml.safe_dump(cfg,sort_keys=False))
        row={'id':name,'cohort_people':people,'arrival_interval_ms':interval,'global_generation_wall_seconds':generation,'global_generation_components_inclusive':dict(totals),'config_sha256':digest(path)}
        print(f'Generation {generation:.3f}s'+('' if args.generation_only else f'; start native {name}'),flush=True)
        if not args.generation_only:
            native=subprocess.run([str(binary),str(path),str(args.horizon_s*1000),str(args.wall_budget_s)],capture_output=True,text=True,timeout=args.wall_budget_s+30)
            if native.returncode:raise RuntimeError(native.stderr or native.stdout)
            row['native']=json.loads(native.stdout)
            n=row['native'];print(f"Done {name}: peak={n['peak_actual_active_tracks']}, advance mean/p95/max={n['advance']['mean_ms']:.3f}/{n['advance']['p95_ms']:.3f}/{n['advance']['max_ms']:.3f}ms, wall={n['wall_seconds']:.2f}s, reached={n['reached_horizon_ms']}ms",flush=True)
        result['cases'].append(row)
        (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    if source_hashes!={p:digest(repo/p) for p in source_paths}:raise RuntimeError('Production source changed during benchmark; results need explicit review')
    print(str(output/'summary.json'),flush=True)

if __name__=='__main__':main()
