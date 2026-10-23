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

const geometry=(cell_id,x,y,width,height)=>({cell_id,x,y,width,height,observation_contributions:80,distinct_road_users:8});
const scopedRelease=(cell,start,end,sealed,cells=[cell])=>({start_ms:start,end_ms:end,sealed_at_ms:sealed,coordination_cell:geometry(cell.cell_id,cell.x,cell.y,cell.width,cell.height),cells});
const scopedWindow=(scope,start,end,evaluated,cells=[])=>({start_ms:start,end_ms:end,evaluated_at_ms:evaluated,coordination_cell:scope,cells});
const localResult=(releases,windows=[])=>({parameters:{coordination:'cell_local'},releases,windows});
const coarse=geometry(3,0,0,8,8),child=geometry(12,2,2,2,2),sibling=geometry(13,8,0,8,8);
const rootEvent=scopedRelease(coarse,0,200,200),childEvent=scopedRelease(child,200,400,450),siblingEvent=scopedRelease(sibling,0,400,400);
const overlapResult=localResult([rootEvent,siblingEvent,childEvent]);
const area=fragment=>fragment.width*fragment.height;
const directContains=(rectangle,x,y)=>x>=rectangle.x&&x<rectangle.x+rectangle.width&&y>=rectangle.y&&y<rectangle.y+rectangle.height;
const overlapping=(a,b)=>a.x<b.x+b.width&&b.x<a.x+a.width&&a.y<b.y+b.height&&b.y<a.y+a.height;
test('Common-window mosaic retains the legacy whole latest released snapshot',()=>{
 const input={releases:[first,second],windows:result.windows};
 assert.equal(M.mosaicAt(input,249).entries.length,0);
 const old=M.mosaicAt(input,399);assert.equal(old.local,false);assert.equal(old.latestEvent,first);assert.equal(old.eventCount,1);
 assert.equal(old.entries[0].cell,first.cells[0]);assert.equal(old.entries[0].row,first);assert.equal(old.entries[0].partial,false);
 const next=M.mosaicAt(input,400);assert.equal(next.latestEvent,second);assert.equal(next.entries.length,2);assert.equal(next.eventCount,2);
});
test('Independent local releases retain differently timed neighboring cells',()=>{
 const mosaic=M.mosaicAt(overlapResult,400);
 assert.equal(mosaic.local,true);assert.equal(mosaic.entries.length,2);assert.equal(mosaic.latestEvent,siblingEvent);
 assert.equal(mosaic.entries.find(e=>e.cell===coarse).row,rootEvent);assert.equal(mosaic.entries.find(e=>e.cell===sibling).row,siblingEvent);
 assert.equal(mosaic.asOfMs,400);assert.equal(mosaic.eventCount,2);
});
test('A local release is invisible one millisecond before sealing',()=>{
 assert.equal(M.mosaicAt(overlapResult,449).entries.some(e=>e.cell===child),false);
 assert.equal(M.mosaicAt(overlapResult,450).entries.some(e=>e.cell===child),true);
});
test('Fine overwrite clips only visible geometry and keeps coarse original counts',()=>{
 const mosaic=M.mosaicAt(overlapResult,450),entry=mosaic.entries.find(e=>e.cell===coarse);
 assert.equal(entry.partial,true);assert.equal(entry.fragments.length,4);
 assert.equal(entry.fragments.reduce((sum,f)=>sum+area(f),0),60);
 assert.equal(entry.cell,coarse);assert.equal(entry.row,rootEvent);assert.equal(entry.cell.observation_contributions,80);
 assert.equal(entry.cell.width,8);assert.equal(entry.cell.height,8);
 for(const fragment of entry.fragments){assert.ok(!overlapping(fragment,child));assert.ok(fragment.width>0&&fragment.height>0);}
 for(const [i,a]of entry.fragments.entries())for(const b of entry.fragments.slice(i+1))assert.ok(!overlapping(a,b));
});
test('Mosaic hit-testing uses visible half-open fragments rather than original support',()=>{
 const mosaic=M.mosaicAt(overlapResult,450),old=mosaic.entries.find(e=>e.cell===coarse),newer=mosaic.entries.find(e=>e.cell===child);
 assert.equal(M.entryContains(old,3,3),false);assert.equal(M.entryContains(newer,3,3),true);
 assert.equal(M.entryContains(old,4,3),true);assert.equal(M.entryContains(newer,4,3),false);
 assert.equal(M.entryContains(old,8,3),false);
});
test('Touching sibling scopes do not partially mask each other',()=>{
 const entries=M.mosaicAt(localResult([rootEvent,siblingEvent]),450).entries;
 assert.equal(entries.length,2);assert.ok(entries.every(e=>!e.partial&&e.fragments.length===1));
});
test('A later coarse release replaces older finer entries only within its scope',()=>{
 const fineFirst=scopedRelease(child,0,100,100),coarseLater=scopedRelease(coarse,100,200,200);
 const mosaic=M.mosaicAt(localResult([fineFirst,siblingEvent,coarseLater]),500);
 assert.deepEqual(mosaic.entries.map(e=>e.cell.cell_id),[3,13]);assert.ok(mosaic.entries.every(e=>!e.partial));
});
test('Late publication wins by sealing time even with an older source interval',()=>{
 const fine=scopedRelease(child,100,300,400),late=scopedRelease(coarse,0,100,600),input=localResult([late,fine]);
 assert.equal(M.mosaicAt(input,500).entries[0].cell,child);
 assert.equal(M.mosaicAt(input,600).entries[0].cell,coarse);
 assert.equal(M.mosaicAt(input,600).entries[0].row.end_ms,100);
});
test('Simultaneous overlapping events follow their authoritative array order',()=>{
 const a=scopedRelease(coarse,0,100,500),b=scopedRelease(child,100,200,500);
 const input=localResult([a,b]),mosaic=M.mosaicAt(input,500);
 assert.equal(mosaic.entries[0].partial,true);assert.equal(mosaic.entries[1].cell,child);assert.equal(mosaic.latestEvent,b);
 const reverse=M.mosaicAt(localResult([b,a]),500);assert.equal(reverse.entries.length,1);assert.equal(reverse.entries[0].cell,coarse);
});
test('Reverse seek rebuilds a deterministic mosaic instead of retaining future masks',()=>{
 const firstView=M.mosaicAt(overlapResult,200),key=firstView.entries[0].key;
 M.mosaicAt(overlapResult,500);const reverse=M.mosaicAt(overlapResult,200);
 assert.equal(reverse.entries.length,1);assert.equal(reverse.entries[0].key,key);assert.equal(reverse.entries[0].partial,false);
 assert.equal(reverse.entries[0].fragments.reduce((sum,f)=>sum+area(f),0),64);
 assert.equal(M.mosaicAt(overlapResult,199).entries.length,0);
});
test('Recipient mosaics never inspect private window arrays or empty retirements',()=>{
 const input=localResult([rootEvent]);Object.defineProperty(input,'windows',{get(){throw new Error('Private array accessed');}});
 assert.equal(M.mosaicAt(input,500,false).entries.length,1);
 assert.deepEqual(M.eventTimes([{result:input}],600),[0,200,600]);
});
test('Private mosaics never inspect recipient arrays',()=>{
 const input=localResult([],[scopedWindow(coarse,0,200,200,[coarse])]);
 Object.defineProperty(input,'releases',{get(){throw new Error('Recipient array accessed');}});
 assert.equal(M.mosaicAt(input,500,true).entries.length,1);
});
test('An empty private retirement clears its scope only in the private channel',()=>{
 const initial=scopedWindow(coarse,0,200,200,[coarse]),retirement=scopedWindow(child,200,400,400,[]);
 const input=localResult([rootEvent],[initial,retirement]);
 assert.equal(M.mosaicAt(input,399,true).entries[0].partial,false);
 const privateView=M.mosaicAt(input,400,true);assert.equal(privateView.entries.length,1);assert.equal(privateView.entries[0].partial,true);
 assert.equal(M.entryContains(privateView.entries[0],3,3),false);assert.equal(privateView.latestEvent,retirement);assert.equal(privateView.eventCount,2);
 assert.equal(M.mosaicAt(input,500,false).entries[0].partial,false);
});
test('Whole-scope private retirement removes the old entry without inventing a zero cell',()=>{
 const input=localResult([],[scopedWindow(coarse,0,200,200,[coarse]),scopedWindow(coarse,200,400,400,[])]);
 const mosaic=M.mosaicAt(input,400,true);assert.deepEqual(mosaic.entries,[]);assert.equal(mosaic.eventCount,2);
});
test('Private-only events join the optional private event timeline',()=>{
 const input=localResult([rootEvent],[scopedWindow(coarse,0,200,200,[coarse]),scopedWindow(child,200,400,400)]);
 assert.deepEqual(M.eventTimes([{result:input}],600),[0,200,600]);
 assert.deepEqual(M.eventTimes([{result:input}],600,true),[0,200,400,600]);
});
test('Mosaic entry keys persist through geometry masks and selection uses those keys',()=>{
 const input=localResult([rootEvent,childEvent]),before=M.mosaicAt(input,200).entries[0];
 const entries=M.mosaicAt(input,450).entries;assert.equal(M.selectEntry(entries,before.key).cell,coarse);
 assert.equal(M.selectEntry(entries,'stale').cell,coarse);assert.equal(M.selectEntry([],before.key),null);
 assert.equal(entries[0].eventIndex,0);assert.equal(entries[1].eventIndex,1);assert.equal(entries[1].eventTime,450);
});
test('Inspecting a cell follows its new publication key and original new interval',()=>{
 const replacement={...coarse,observation_contributions:120,distinct_road_users:12};
 const next=scopedRelease(replacement,200,400,500),input=localResult([rootEvent,siblingEvent,next]);
 const selected=M.mosaicAt(input,200).entries.find(entry=>entry.cell===coarse);
 const entries=M.mosaicAt(input,500).entries;assert.equal(entries[0].cell,sibling);
 const followed=M.selectEntry(entries,selected.key,coarse.cell_id);
 assert.notEqual(followed.key,selected.key);assert.equal(followed.cell,replacement);assert.equal(followed.row,next);
 assert.equal(followed.row.start_ms,200);assert.equal(followed.cell.observation_contributions,120);
});
test('An exact surviving historical key wins before a preferred cell ID',()=>{
 const entries=M.mosaicAt(overlapResult,450).entries,old=entries.find(entry=>entry.cell===coarse);
 assert.equal(old.partial,true);assert.equal(M.selectEntry(entries,old.key,child.cell_id),old);
});
test('Missing preferred cell falls back safely and string IDs can follow numeric cells',()=>{
 const entries=M.mosaicAt(overlapResult,450).entries;
 assert.equal(M.selectEntry(entries,'stale',String(child.cell_id)).cell,child);
 assert.equal(M.selectEntry(entries,'stale',99999),entries[0]);
 assert.equal(M.selectEntry([],null,coarse.cell_id),null);
});
test('A mosaic entry retains its own source window for private source grouping',()=>{
 const left={...inspectedCell,observation_contributions:3,distinct_road_users:2},right=geometry(13,4,0,4,4);
 const leftEvent=scopedRelease(left,0,300,350),rightEvent=scopedRelease(right,0,200,500),input=localResult([leftEvent,rightEvent]);
 const entry=M.mosaicAt(input,500).entries.find(e=>e.cell===left);
 const source=M.sourceGroups(sourceIndex,entry.cell,entry.row,500,true);
 assert.equal(entry.row,leftEvent);assert.equal(source.observations,3);assert.equal(source.distinctRoadUsers,2);
});
test('Mosaic construction never mutates original result cells or events',()=>{
 const input=localResult([rootEvent,childEvent]),before=JSON.stringify(input);
 M.mosaicAt(input,500);M.mosaicAt(input,100);M.mosaicAt(input,500,true);
 assert.equal(JSON.stringify(input),before);assert.equal(Object.isFrozen(coarse),false);
});
test('Mosaic rejects nonfinite playhead times and missing local scope',()=>{
 for(const stamp of [NaN,Infinity,-Infinity])assert.throws(()=>M.mosaicAt(overlapResult,stamp),/finite/);
 const input=localResult([{start_ms:0,end_ms:100,sealed_at_ms:100,cells:[coarse]}]);
 assert.throws(()=>M.mosaicAt(input,100),/scope/);
});
test('Mosaic has a visible-fragment cap and can rebuild safely after a rejected view',()=>{
 const cells=Array.from({length:M.MAX_VISIBLE_FRAGMENTS+1},(_,i)=>geometry(i,i,0,1,1));
 const huge=scopedRelease(geometry(1,0,0,cells.length,1),100,200,200,cells),input=localResult([rootEvent,huge]);
 assert.equal(M.mosaicAt(input,100).entries.length,0);
 assert.throws(()=>M.mosaicAt(input,200),/visible-fragment limit/);
 assert.equal(M.mosaicAt(input,199).entries.length,0);
});
test('Published cell-window counts are independent from event counts and visible fragments',()=>{
 const a=geometry(12,0,0,4,4),b=geometry(13,4,0,4,4);
 const input={releases:[{sealed_at_ms:200,cells:[a,b]},{sealed_at_ms:400,cells:[a]}]};
 assert.deepEqual(M.releaseAccounting(input,199),{publishedCellWindows:0,uniqueSpatialCells:0,releaseEvents:0,contributions:0});
 assert.deepEqual(M.releaseAccounting(input,200),{publishedCellWindows:2,uniqueSpatialCells:2,releaseEvents:1,contributions:160});
 assert.deepEqual(M.releaseAccounting(input,400),{publishedCellWindows:3,uniqueSpatialCells:2,releaseEvents:2,contributions:240});
 assert.equal(M.releaseAccounting(input,200).publishedCellWindows,2);
});
test('Policy inspection intersects root and all overlapping regional requirements',()=>{
 const policy={policy_root_requirements:[{metric:'support',min:5},{metric:'duration_ms',max:4000}],policy_regions:[
  {id:'entrance',x:1,y:1,width:2,height:2,requirements:[{metric:'support',min:10}]},
  {id:'fast',x:2,y:2,width:2,height:2,requirements:[{metric:'duration_ms',max:1000},{metric:'support',min:7}]},
  {id:'touching',x:4,y:0,width:1,height:4,requirements:[{metric:'support',min:100}]}]};
 const before=JSON.stringify(policy),resolved=M.policyAt(policy,{x:0,y:0,width:4,height:4});
 assert.equal(resolved.rootDeclared,true);assert.deepEqual(resolved.regions.map(r=>r.id),['entrance','fast']);
 const support=resolved.requirements.find(r=>r.metric==='support');
 assert.equal(support.min,10);assert.equal(support.sources.length,3);assert.equal(support.conflict,false);
 assert.equal(resolved.requirements.find(r=>r.metric==='duration_ms').max,1000);
 assert.equal(resolved.conflicting,false);assert.equal(JSON.stringify(policy),before);
 assert.equal(Object.hasOwn(support,'observed'),false);assert.equal(Object.hasOwn(support,'status'),false);
});
test('Policy contradictions are explicit and missing root declarations remain unknown',()=>{
 const policy={policy_regions:[{id:'minimum',x:0,y:0,width:4,height:4,requirements:[{metric:'cell_side_m',min:10}]},
 {id:'maximum',x:2,y:2,width:4,height:4,requirements:[{metric:'cell_side_m',max:5}]}]};
 const overlap=M.policyAt(policy,{x:2,y:2,width:1,height:1});
 assert.equal(overlap.rootDeclared,false);assert.equal(overlap.conflicting,true);
 assert.equal(overlap.requirements[0].min,10);assert.equal(overlap.requirements[0].max,5);
 assert.deepEqual(M.policyAt({},coarse),{rootDeclared:false,regions:[],requirements:[],conflicting:false});
 assert.equal(M.policyAt(policy,{x:0,y:0,width:1,height:1}).conflicting,false);
});
test('Map placement preserves global world coordinates through zoom and crop',()=>{
 const bounds={x:0,y:0,width:80,height:80},layout={left:40,top:10,scale:8};
 assert.deepEqual(M.mapImageRectangle(bounds,{x:20,y:30,width:5,height:5},layout),{x:-120,y:-230,width:640,height:640});
 const shifted={x:-10,y:5,width:80,height:80};
 assert.deepEqual(M.mapImageRectangle(shifted,shifted,{left:40,top:10,scale:2}),{x:40,y:10,width:160,height:160});
});
test('Declared mapped source provenance does not rely on names or presumed realism',()=>{
 assert.deepEqual(M.inputProvenance({input_provenance:'Kinematic mapped routes; no collision solver.'}),
 {kind:'declared',text:'Declared input: Kinematic mapped routes; no collision solver.'});
});
/* Optional real-artifact check: no generated dataset is required by the normal
   regression suite or stored in this test. Pass a local replay-result filename. */
if(process.argv[2]) {
 const fs=require('node:fs'),actual=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 test('Optional frozen local artifact mosaics agree with an independent pointwise event scan',()=>{
  assert.equal(actual.parameters.coordination,'cell_local');
  const coverage=actual.source.coverage,grid=Math.min(64,2**actual.source.coverage.leaf_depth);
  for(const privateMode of [false,true]){
   const field=privateMode?'windows':'releases',stamp=privateMode?'evaluated_at_ms':'sealed_at_ms';
   const events=actual[field].map((row,index)=>({row,index,time:row[stamp]})).sort((a,b)=>a.time-b.time||a.index-b.index);
   const ascending=[...new Set([0,actual.source.end_ms,...events.map(e=>e.time),...events.map(e=>Math.max(0,e.time-1)),...events.map(e=>Math.min(actual.source.end_ms,e.time+1))])].sort((a,b)=>a-b);
   for(const now of [...ascending,...ascending.slice().reverse()]){
    const mosaic=M.mosaicAt(actual,now,privateMode);
    for(let y=0;y<grid;y++)for(let x=0;x<grid;x++){
     const px=coverage.x+(x+.5)/grid*coverage.width,py=coverage.y+(y+.5)/grid*coverage.height;let expected=null;
     for(const event of events){if(event.time>now)break;if(directContains(event.row.coordination_cell,px,py))expected=event.row.cells.find(cell=>directContains(cell,px,py))||null;}
     const found=mosaic.entries.filter(entry=>entry.fragments.some(fragment=>directContains(fragment,px,py)));
     assert.ok(found.length<=1,'Visible geometry cannot overlap');assert.equal(found[0]?.cell??null,expected);
    }
   }
  }
 });
}
process.stdout.write(passed+' model tests passed\n');
