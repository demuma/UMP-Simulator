'use strict';
const assert = require('node:assert/strict');
const M = require('./model.js');
let passed = 0;
function test(name, action) {action();passed++;process.stdout.write('PASS '+name+'\n');}
const replay={sampling_period_ms:100,end_ms:600,batches:[
 {observed_at_ms:100,status:'measured',observations:[{id:'one',x:2,y:3}]},
 {observed_at_ms:200,status:'measured',observations:[]},
 {observed_at_ms:400,status:'unavailable',observations:[]},
 {observed_at_ms:500,status:'measured',observations:[{id:'two',x:4,y:5}]}
]};
const first={start_ms:0,end_ms:200,sealed_at_ms:250,cells:[{observation_contributions:3}]};
const second={start_ms:200,end_ms:400,sealed_at_ms:400,cells:[{observation_contributions:5},{observation_contributions:2}]};
const result={releases:[first,second],windows:[{evaluated_at_ms:200,cells:[{selected:true},{selected:false}]}]};
test('No observation before first sample',()=>assert.equal(M.observationAt(replay,99).status,'not_yet_sampled'));
test('Exact sampled position is displayed without interpolation',()=>assert.deepEqual(M.observationAt(replay,150).visible,replay.batches[0].observations));
test('Measured empty is a genuine empty sample',()=>{const f=M.observationAt(replay,200);assert.equal(f.status,'measured');assert.deepEqual(f.visible,[]);});
test('Expired positions clear at one full sampling interval',()=>{assert.equal(M.observationAt(replay,300).status,'missing_sample');assert.deepEqual(M.observationAt(replay,300).visible,[]);});
test('Unavailable frame does not reuse a previous position',()=>{assert.equal(M.observationAt(replay,400).status,'unavailable');assert.deepEqual(M.observationAt(replay,400).visible,[]);});
test('A later valid sample resumes position display',()=>assert.equal(M.observationAt(replay,500).visible[0].id,'two'));
test('Window end alone never makes a release visible',()=>assert.equal(M.releaseAt(result,200),null));
test('One millisecond before sealing is still hidden',()=>assert.equal(M.releaseAt(result,249),null));
test('Exact sealing timestamp makes release visible',()=>assert.equal(M.releaseAt(result,250),first));
test('Historical release is retained explicitly until next seal',()=>assert.equal(M.releaseAt(result,399),first));
test('A newer release replaces whole displayed cut',()=>assert.equal(M.releaseAt(result,400),second));
test('Private diagnostics use evaluation timestamp independently',()=>{assert.equal(M.diagnosticAt(result,199),null);assert.equal(M.diagnosticAt(result,200),result.windows[0]);});
test('Cumulative accounting includes only sealed release cells',()=>{assert.deepEqual(M.cumulativeReleased(result,249),{contributions:0,count:0});assert.deepEqual(M.cumulativeReleased(result,400),{contributions:10,count:2});});
test('Shared event timeline is sorted and deduplicated',()=>assert.deepEqual(M.eventTimes([{result},{result}],600),[0,250,400,600]));
test('Event seek moves strictly forward/backward',()=>{const times=[0,250,400,600];assert.equal(M.eventAfter(times,250),400);assert.equal(M.eventBefore(times,250),0);});
test('Half-open cell hit test never crosses right/bottom edge',()=>{const c={x:10,y:20,width:5,height:8};assert.equal(M.contains(c,10,20),true);assert.equal(M.contains(c,15,24),false);assert.equal(M.contains(c,12,28),false);});
test('Only explicit private unselected cells are suppressed',()=>assert.deepEqual(M.privateCells(result.windows[0]),[{selected:false}]));

const inspectionReplay={coverage:{x:0,y:0,width:8,height:8,leaf_depth:3},sampling_period_ms:100,end_ms:600,batches:[
 {observed_at_ms:0,status:'measured',observations:[{id:'a',type:'Adult Pedestrian',x:1,y:1},{id:'b',type:'Child Pedestrian',x:3,y:3}]},
 {observed_at_ms:100,status:'measured',observations:[{id:'a',type:'Adult Pedestrian',x:1,y:1},{id:'c',type:'Cyclist',x:4,y:4}]},
 {observed_at_ms:200,status:'measured',observations:[]},
 {observed_at_ms:300,status:'unavailable',observations:[]},
 {observed_at_ms:400,status:'measured',observations:[{id:'future',type:'Scooter',x:1,y:1}]}
]};
const inspectedCell={cell_id:12,x:0,y:0,width:4,height:4};
const inspectedWindow={start_ms:0,end_ms:300,sealed_at_ms:350,cells:[inspectedCell]};
const sourceIndex=M.buildSourceIndex(inspectionReplay);
test('Cell selector preserves numeric IDs from HTML string values',()=>assert.equal(M.selectCell([{cell_id:12},{cell_id:13}],'13').cell_id,13));
test('Cell selector replaces stale selection or empty cut safely',()=>{assert.equal(M.selectCell([{cell_id:12}],13).cell_id,12);assert.equal(M.selectCell([],12),null);});
test('Private input groups are absent without explicit opt-in',()=>assert.equal(M.sourceGroups(sourceIndex,inspectedCell,inspectedWindow,500,false),null));
test('Private source groups cannot leak before displayed sealing event',()=>{assert.equal(M.sourceGroups(sourceIndex,inspectedCell,inspectedWindow,349,true),null);assert.equal(sourceIndex.cache.size,0);});
test('Private groups use exact half-open cell and whole interval, not current sample',()=>{
 const result=M.sourceGroups(sourceIndex,inspectedCell,inspectedWindow,350,true);
 assert.deepEqual(result,{observations:3,distinctRoadUsers:2,measuredSamples:3,unavailableSamples:0,groups:[
 {type:'Adult Pedestrian',observations:2,distinctRoadUsers:1,meanMeasuredSampleOccupancy:2/3},
 {type:'Child Pedestrian',observations:1,distinctRoadUsers:1,meanMeasuredSampleOccupancy:1/3}]});
 assert.equal(M.observationAt(inspectionReplay,350).visible.length,0);
});
test('Cached private summaries remain hidden when disabled or sought backwards',()=>{
 assert.equal(sourceIndex.cache.size,1);
 assert.equal(M.sourceGroups(sourceIndex,inspectedCell,inspectedWindow,349,true),null);
 assert.equal(M.sourceGroups(sourceIndex,inspectedCell,inspectedWindow,500,false),null);
});
test('Private diagnostics use their evaluation gate and include unavailable metadata',()=>{
 const window={start_ms:100,end_ms:400,evaluated_at_ms:450};
 assert.equal(M.sourceGroups(sourceIndex,inspectedCell,window,449,true),null);
 const result=M.sourceGroups(sourceIndex,inspectedCell,window,450,true);
 assert.equal(result.observations,1);assert.equal(result.measuredSamples,2);assert.equal(result.unavailableSamples,1);
 assert.equal(result.groups[0].meanMeasuredSampleOccupancy,.5);
});
test('No identities escape in private summaries and recipient data is not modified',()=>{
 const before=JSON.stringify(inspectedWindow),result=M.sourceGroups(sourceIndex,inspectedCell,inspectedWindow,500,true);
 assert.equal(JSON.stringify(inspectedWindow),before);
 assert.equal(Object.hasOwn(result.groups[0],'identities'),false);
 assert.equal(Object.hasOwn(result.groups[0],'ids'),false);
});
test('Non-aligned cell index lookup still applies exact geometry',()=>{
 const result=M.sourceGroups(sourceIndex,{cell_id:15,x:.75,y:.75,width:.5,height:.5},inspectedWindow,500,true);
 assert.equal(result.observations,2);assert.equal(result.distinctRoadUsers,1);
});
test('Measured-empty source footprint remains empty without invented zeros or types',()=>{
 const result=M.sourceGroups(sourceIndex,{cell_id:15,x:6,y:6,width:1,height:1},inspectedWindow,500,true);
 assert.deepEqual(result.groups,[]);assert.equal(result.observations,0);assert.equal(result.measuredSamples,3);
});
test('Different interval cache keys do not reuse older group totals',()=>{
 const result=M.sourceGroups(sourceIndex,inspectedCell,{start_ms:400,end_ms:500,sealed_at_ms:500},500,true);
 assert.equal(result.observations,1);assert.equal(result.groups[0].type,'Scooter');
});
test('Private summary cache is bounded and carries counts instead of raw tracks',()=>{
 for(let i=1;i<=40;i++)M.sourceGroups(sourceIndex,{cell_id:i,x:0,y:0,width:i/100,height:1},inspectedWindow,500,true);
 assert.equal(sourceIndex.cache.size,32);
 assert.equal(JSON.stringify([...sourceIndex.cache.values()]).includes('future'),false);
});
test('Reference counts separate IDs from exactly coincident XY positions',()=>{
 const rows=[{id:'adult',type:'Adult',x:1,y:2},{id:'child',type:'Child',x:1,y:2},{id:'other',type:'Adult',x:3,y:4}];
 const sample=M.referenceSample(rows);
 assert.equal(sample.totalCount,3);assert.equal(sample.totalPositions,2);assert.equal(sample.visibleCount,3);assert.equal(sample.visiblePositions,2);
 assert.equal(sample.groups[0].observations.length,2);assert.equal(sample.groups[0].observations[0],rows[0]);
});
test('Reference never merges nearby distinct coordinates or jitters input',()=>{
 const rows=[{id:'a',x:1,y:2},{id:'b',x:1.0000001,y:2}],before=JSON.stringify(rows);
 const sample=M.referenceSample(rows);assert.equal(sample.visiblePositions,2);
 assert.deepEqual(sample.groups.map(g=>[g.x,g.y]),[[1,2],[1.0000001,2]]);assert.equal(JSON.stringify(rows),before);
});
test('Reference selected-cell focus applies half-open geometry to current sample only',()=>{
 const rows=[{id:'inside',x:1,y:1},{id:'right',x:2,y:1},{id:'bottom',x:1,y:2},{id:'other',x:3,y:3}];
 const sample=M.referenceSample(rows,{x:1,y:1,width:1,height:1});
 assert.equal(sample.totalCount,4);assert.equal(sample.totalPositions,4);assert.equal(sample.visibleCount,1);
 assert.equal(sample.groups[0].observations[0].id,'inside');
});
test('Reference focus preserves four close distinct users rather than one screen cluster',()=>{
 const rows=[0,1,2,3].map(i=>({id:'person-'+i,x:2.8+i*.05,y:2.8+i*.04}));
 const sample=M.referenceSample(rows,{x:2.5,y:2.5,width:1.25,height:1.25});
 assert.equal(sample.visibleCount,4);assert.equal(sample.visiblePositions,4);
});
test('Missing current samples cannot retain old focused positions',()=>{
 const frame=M.observationAt(inspectionReplay,600),sample=M.referenceSample(frame.visible,{x:0,y:0,width:4,height:4});
 assert.equal(sample.totalCount,0);assert.equal(sample.visibleCount,0);assert.deepEqual(sample.groups,[]);
});
test('Declared scripted tag is explicit provenance, other titles do not imply simulator capture',()=>{
 assert.equal(M.inputProvenance({title:'Local patches · scripted mechanism test'}).kind,'scripted');
 assert.equal(M.inputProvenance({title:'Recorded movement',run_id:'simulator-capture-example'}).kind,'unspecified');
 assert.equal(M.inputProvenance({title:'Not a scripted mechanism test'}).kind,'unspecified');
 assert.equal(M.inputProvenance({}).kind,'unspecified');
});
process.stdout.write(passed+' model tests passed\n');
