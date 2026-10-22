#!/usr/bin/env node
/* Independently sample-check the private source-group inspector on real bundles.
 * Scope: first/last cells in the first/last nonempty recipient release of each
 * variant. Duplicate selections are checked once. This is not an exhaustive
 * audit of every cell or a replacement for bundle validation/model tests.
 */
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const M=require('./model.js');

function findBundles(directory) {
  return fs.readdirSync(directory,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))
    .flatMap(entry=>entry.isDirectory()?findBundles(path.join(directory,entry.name)):
      entry.isFile()&&entry.name==='bundle.json'?[path.join(directory,entry.name)]:[]);
}
function readJSON(filename) {return JSON.parse(fs.readFileSync(filename,'utf8'));}
function verify(root) {
  let bundles=0,variants=0,sampledPublicCells=0;
  for(const filename of findBundles(root)) {
    const directory=path.dirname(filename),manifest=readJSON(filename);
    if(manifest.schema!=='ump.replay-viewer.v1')continue;
    const replay=readJSON(path.resolve(directory,manifest.observations));
    const index=M.buildSourceIndex(replay);bundles++;
    for(const entry of manifest.variants) {
      variants++;
      const result=readJSON(path.resolve(directory,entry.result));
      const selectedRows=new Set([result.releases.find(row=>row.cells.length),
        [...result.releases].reverse().find(row=>row.cells.length)].filter(Boolean));
      for(const row of selectedRows)for(const cell of new Set([row.cells[0],row.cells[row.cells.length-1]])) {
        const context=`${filename} / ${entry.id} / [${row.start_ms},${row.end_ms}) / cell ${cell.cell_id}`;
        const groups=M.sourceGroups(index,cell,row,row.sealed_at_ms,true);
        const naive=new Map(),identities=new Set();let observations=0,measuredSamples=0,unavailableSamples=0;
        /* The reference intentionally does not call the model's index, hit-test,
           binary search, deduplication or timeline helpers. */
        for(const batch of replay.batches) {
          if(batch.observed_at_ms<row.start_ms||batch.observed_at_ms>=row.end_ms)continue;
          if(batch.status!=='measured'){unavailableSamples++;continue;}
          measuredSamples++;
          for(const observation of batch.observations) {
            if(!(observation.x>=cell.x&&observation.x<cell.x+cell.width&&
                 observation.y>=cell.y&&observation.y<cell.y+cell.height))continue;
            observations++;identities.add(observation.id);
            if(!naive.has(observation.type))naive.set(observation.type,{observations:0,identities:new Set()});
            const group=naive.get(observation.type);group.observations++;group.identities.add(observation.id);
          }
        }
        assert.ok(groups,context);
        assert.equal(groups.observations,observations,context+' input observations');
        assert.equal(groups.distinctRoadUsers,identities.size,context+' input distinct users');
        assert.equal(groups.measuredSamples,measuredSamples,context+' measured samples');
        assert.equal(groups.unavailableSamples,unavailableSamples,context+' unavailable samples');
        assert.equal(observations,cell.observation_contributions,context+' published total observations');
        assert.equal(identities.size,cell.distinct_road_users,context+' published total distinct users');
        assert.deepEqual(groups.groups,[...naive.entries()].sort((a,b)=>a[0].localeCompare(b[0])).map(([type,group])=>({
          type,observations:group.observations,distinctRoadUsers:group.identities.size,
          meanMeasuredSampleOccupancy:measuredSamples?group.observations/measuredSamples:null})),context+' type breakdown');
        assert.equal(M.sourceGroups(index,cell,row,row.sealed_at_ms-1,true),null,context+' pre-seal gate');
        assert.equal(M.sourceGroups(index,cell,row,row.sealed_at_ms,false),null,context+' explicit opt-in');
        sampledPublicCells++;
      }
    }
  }
  assert.ok(bundles>0,'No ump.replay-viewer.v1 bundles found under '+root);
  return {bundles,variants,sampledPublicCells,scope:'First/last cells of first/last nonempty releases; duplicate selections removed',result:'PASS'};
}
if(process.argv.length!==3) {
  process.stderr.write('Usage: node tools/replay_viewer/verify_source_groups.js BUNDLE_SEARCH_DIRECTORY\n');
  process.exitCode=2;
}else{
  try{process.stdout.write(JSON.stringify(verify(path.resolve(process.argv[2])),null,2)+'\n');}
  catch(error){process.stderr.write('Source-group verification failed: '+error.message+'\n');process.exitCode=1;}
}
