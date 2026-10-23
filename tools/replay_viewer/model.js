/* Pure timeline helpers. No interpolation, inference or recipient-policy evaluation. */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.UMPReplay = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  function lastAtOrBefore(rows, time, key) {
    let lo = 0, hi = rows.length;
    while (lo < hi) { const mid = (lo + hi) >>> 1; if (key(rows[mid]) <= time) lo = mid + 1; else hi = mid; }
    return lo ? rows[lo - 1] : null;
  }
  function observationAt(replay, time) {
    const batch = lastAtOrBefore(replay.batches, time, row => row.observed_at_ms);
    if (!batch) return {batch:null, visible:[], age:null, status:'not_yet_sampled'};
    const age = time - batch.observed_at_ms;
    const valid = batch.status === 'measured' && age < replay.sampling_period_ms;
    return {batch, visible:valid ? batch.observations : [], age,
      status:valid ? 'measured' : batch.status !== 'measured' ? 'unavailable' : 'missing_sample'};
  }
  function releaseAt(result, time) {
    return lastAtOrBefore(result.releases, time, row => row.sealed_at_ms);
  }
  function diagnosticAt(result, time) {
    return lastAtOrBefore(result.windows, time, row => row.evaluated_at_ms);
  }
  function cumulativeReleased(result, time) {
    let contributions = 0, count = 0;
    for (const release of result.releases) {
      if (release.sealed_at_ms > time) break;
      count++;
      for (const cell of release.cells) contributions += cell.observation_contributions;
    }
    return {contributions, count};
  }
  /* Count immutable original records, never the clipped display fragments. */
  function releaseAccounting(result,time) {
    const spatial=new Set();let publishedCellWindows=0,releaseEvents=0,contributions=0;
    for(const release of result.releases){
      if(release.sealed_at_ms>time)break;
      releaseEvents++;
      for(const cell of release.cells){
        publishedCellWindows++;spatial.add(String(cell.cell_id));
        contributions+=cell.observation_contributions??0;
      }
    }
    return {publishedCellWindows,uniqueSpatialCells:spatial.size,releaseEvents,contributions};
  }
  function intersects(a,b) {return a.x<b.x+b.width&&b.x<a.x+a.width&&a.y<b.y+b.height&&b.y<a.y+a.height;}
  /* Declaration inspection only: no observed values or pass/fail are invented.
     A coarse cell inherits every positively intersected regional declaration. */
  function policyAt(variant,cell) {
    const regions=(variant.policy_regions??[]).filter(region=>intersects(region,cell));
    const combined=new Map();
    const add=(requirements,source)=>{for(const requirement of requirements??[]){
      let bound=combined.get(requirement.metric);
      if(!bound){bound={metric:requirement.metric,sources:[]};combined.set(requirement.metric,bound);}
      if(requirement.min!=null)bound.min=bound.min==null?requirement.min:Math.max(bound.min,requirement.min);
      if(requirement.max!=null)bound.max=bound.max==null?requirement.max:Math.min(bound.max,requirement.max);
      bound.sources.push({source,...requirement});
    }};
    add(variant.policy_root_requirements,'root');
    for(const region of regions)add(region.requirements,region.id);
    const requirements=[...combined.values()].map(bound=>({...bound,conflict:bound.min!=null&&bound.max!=null&&bound.min>bound.max}));
    return {rootDeclared:Array.isArray(variant.policy_root_requirements),regions,requirements,
      conflicting:requirements.some(bound=>bound.conflict)};
  }
  function mapImageRectangle(bounds,viewport,layout) {
    return {x:layout.left+(bounds.x-viewport.x)*layout.scale,y:layout.top+(bounds.y-viewport.y)*layout.scale,
      width:bounds.width*layout.scale,height:bounds.height*layout.scale};
  }
  function eventTimes(variants, end, privateMode=false) {
    const rows=privateMode?'windows':'releases',stamp=privateMode?'evaluated_at_ms':'sealed_at_ms';
    return [...new Set([0,end,...variants.flatMap(v => v.result[rows].map(r => r[stamp]))])].sort((a,b)=>a-b);
  }
  function eventAfter(times, now) { return times.find(t => t > now) ?? times[times.length-1]; }
  function eventBefore(times, now) { return [...times].reverse().find(t => t < now) ?? times[0]; }
  function contains(cell, x, y) { return x >= cell.x && y >= cell.y && x < cell.x+cell.width && y < cell.y+cell.height; }
  function privateCells(window) { return window ? window.cells.filter(c => !c.selected) : []; }
  /* Group only exactly coincident recorded coordinates. Close screen markers
     are never moved, merged by distance or interpreted as a single person. */
  function referenceSample(observations, viewport) {
    const allPositions=new Set(),positions=new Map();let visibleCount=0;
    for(const observation of observations){
      const key=JSON.stringify([observation.x,observation.y]);allPositions.add(key);
      if(viewport&&!contains(viewport,observation.x,observation.y))continue;
      visibleCount++;
      if(!positions.has(key))positions.set(key,{x:observation.x,y:observation.y,observations:[]});
      positions.get(key).observations.push(observation);
    }
    return {totalCount:observations.length,totalPositions:allPositions.size,visibleCount,
      visiblePositions:positions.size,groups:[...positions.values()]};
  }
  function inputProvenance(manifest) {
    /* The frozen legacy local-policy bundle declares its source in its title.
       Other source kinds must remain unspecified rather than inferred from IDs. */
    if(typeof manifest.input_provenance==='string'&&manifest.input_provenance.trim())
      return {kind:'declared',text:'Declared input: '+manifest.input_provenance};
    if(typeof manifest.title==='string'&&/(?:^|·\s*)scripted mechanism test$/i.test(manifest.title))
      return {kind:'scripted',text:'Declared input: scripted mechanism test (bundle title). This analytical setup is designed to exercise policy decisions; its small coordinate changes do not represent realistic traffic movement.'};
    return {kind:'unspecified',text:'Replay input. The bundle does not declare its generation method here; the reference displays its recorded coordinates.'};
  }
  function selectCell(cells, selectedId) {
    return cells.find(cell => String(cell.cell_id) === String(selectedId)) || cells[0] || null;
  }
  const MAX_VISIBLE_FRAGMENTS=65536,mosaicCache=new WeakMap();
  function rectangle(cell) {return {x:cell.x,y:cell.y,width:cell.width,height:cell.height};}
  function sameRectangle(a,b) {return a.x===b.x&&a.y===b.y&&a.width===b.width&&a.height===b.height;}
  function subtractRectangle(fragment,scope) {
    const left=Math.max(fragment.x,scope.x),top=Math.max(fragment.y,scope.y);
    const right=Math.min(fragment.x+fragment.width,scope.x+scope.width),bottom=Math.min(fragment.y+fragment.height,scope.y+scope.height);
    if(left>=right||top>=bottom)return [fragment];
    const remaining=[];
    if(top>fragment.y)remaining.push({x:fragment.x,y:fragment.y,width:fragment.width,height:top-fragment.y});
    if(left>fragment.x)remaining.push({x:fragment.x,y:top,width:left-fragment.x,height:bottom-top});
    if(right<fragment.x+fragment.width)remaining.push({x:right,y:top,width:fragment.x+fragment.width-right,height:bottom-top});
    if(bottom<fragment.y+fragment.height)remaining.push({x:fragment.x,y:bottom,width:fragment.width,height:fragment.y+fragment.height-bottom});
    return remaining;
  }
  function frozenEntry(entry,fragments) {
    return Object.freeze({...entry,fragments:Object.freeze(fragments.map(fragment=>Object.freeze(fragment))),
      partial:fragments.length!==1||!sameRectangle(fragments[0],entry.cell)});
  }
  function resetMosaic(channel) {channel.entries=Object.freeze([]);channel.applied=0;channel.latestEvent=null;channel.lastTime=-Infinity;}
  /* A mosaic contains visible geometry and original immutable event references.
     Geometry fragments are display masks, never new cells or redistributed
     statistics. The original cell and its full source interval remain intact.

     Inputs are frozen replay artifacts. One incremental state per result and
     channel is retained; seeking backwards rebuilds it, without caching an
     unbounded series of historical mosaics or expanding the finest grid. */
  function mosaicAt(result,time,privateMode=false) {
    if(!Number.isFinite(time))throw new TypeError('Replay mosaic time must be finite');
    const coordination=result.parameters?.coordination??'common_window';
    if(coordination!=='common_window'&&coordination!=='cell_local')throw new Error('Unsupported replay coordination');
    const local=coordination==='cell_local',name=privateMode?'private':'recipient',stamp=privateMode?'evaluated_at_ms':'sealed_at_ms';
    const rows=privateMode?result.windows:result.releases;
    let cache=mosaicCache.get(result);if(!cache){cache={};mosaicCache.set(result,cache);}
    let channel=cache[name];
    if(!channel||channel.rows!==rows||channel.length!==rows.length||channel.local!==local){
      channel={rows,length:rows.length,local,events:rows.map((row,eventIndex)=>({row,eventIndex,eventTime:row[stamp]}))
        .sort((a,b)=>a.eventTime-b.eventTime||a.eventIndex-b.eventIndex)};
      resetMosaic(channel);cache[name]=channel;
    }
    if(time<channel.lastTime)resetMosaic(channel);
    while(channel.applied<channel.events.length&&channel.events[channel.applied].eventTime<=time){
      const event=channel.events[channel.applied],{row,eventTime,eventIndex}=event;
      let entries=[];
      if(local){
        if(!row.coordination_cell)throw new Error('Local replay event lacks a coordination scope');
        for(const entry of channel.entries){
          const fragments=entry.fragments.flatMap(fragment=>subtractRectangle(fragment,row.coordination_cell));
          if(fragments.length)entries.push(frozenEntry(entry,fragments));
        }
      }
      for(const [cellIndex,cell]of row.cells.entries())entries.push(frozenEntry({
        key:`${name}:${eventIndex}:${cellIndex}`,cell,row,eventTime,eventIndex},[rectangle(cell)]));
      let fragments=0;
      for(const entry of entries){fragments+=entry.fragments.length;if(fragments>MAX_VISIBLE_FRAGMENTS){
        resetMosaic(channel);throw new RangeError('Replay mosaic exceeds the visible-fragment limit; clear the view');
      }}
      channel.entries=Object.freeze(entries);channel.latestEvent=row;channel.applied++;
    }
    channel.lastTime=time;
    return {local,entries:channel.entries,latestEvent:channel.latestEvent,eventCount:channel.applied,asOfMs:time};
  }
  function selectEntry(entries,key,preferredCellId=null) {
    return entries.find(entry=>entry.key===key)
      ||(preferredCellId==null?null:entries.find(entry=>String(entry.cell.cell_id)===String(preferredCellId)))
      ||entries[0]||null;
  }
  function entryContains(entry,x,y) {return entry.fragments.some(fragment=>contains(fragment,x,y));}
  function firstAtOrAfter(rows, time, key) {
    let lo=0,hi=rows.length;
    while(lo<hi){const mid=(lo+hi)>>>1;if(key(rows[mid])<time)lo=mid+1;else hi=mid;}
    return lo;
  }
  /* The index holds references to existing observations, not copied tracks or
     identity sets. Spatial buckets are capped at 256 x 256 for unusual inputs;
     exact half-open geometry is always checked after the index lookup. */
  function buildSourceIndex(replay) {
    const coverage=replay.coverage,side=2**Math.max(0,Math.min(8,Math.floor(coverage.leaf_depth))),buckets=new Map();
    const column=x=>Math.max(0,Math.min(side-1,Math.floor((x-coverage.x)/coverage.width*side)));
    const row=y=>Math.max(0,Math.min(side-1,Math.floor((y-coverage.y)/coverage.height*side)));
    for(const batch of replay.batches)if(batch.status==='measured')for(const observation of batch.observations){
      const key=row(observation.y)*side+column(observation.x);
      if(!buckets.has(key))buckets.set(key,[]);
      buckets.get(key).push({time:batch.observed_at_ms,observation});
    }
    return {replay,coverage,side,buckets,column,row,cache:new Map()};
  }
  /* This is private research inspection, gated by the same finalized event as
     the displayed cell. No exact type counts are attached to recipient cells. */
  function sourceGroups(index, cell, window, time, enabled) {
    if(!enabled)return null;
    const finalized=window?.sealed_at_ms??window?.evaluated_at_ms;
    if(!cell||!window||!Number.isFinite(finalized)||finalized>time)return null;
    const key=[window.start_ms,window.end_ms,cell.x,cell.y,cell.width,cell.height].join(':');
    if(index.cache.has(key))return index.cache.get(key);
    const groups=new Map(),identities=new Set();let observations=0;
    const minX=index.column(cell.x),minY=index.row(cell.y);
    const maxX=Math.min(index.side-1,Math.ceil((cell.x+cell.width-index.coverage.x)/index.coverage.width*index.side)-1);
    const maxY=Math.min(index.side-1,Math.ceil((cell.y+cell.height-index.coverage.y)/index.coverage.height*index.side)-1);
    for(let y=minY;y<=maxY;y++)for(let x=minX;x<=maxX;x++){
      const entries=index.buckets.get(y*index.side+x)||[];
      for(let i=firstAtOrAfter(entries,window.start_ms,item=>item.time);i<entries.length&&entries[i].time<window.end_ms;i++){
        const observation=entries[i].observation;if(!contains(cell,observation.x,observation.y))continue;
        if(!groups.has(observation.type))groups.set(observation.type,{type:observation.type,observations:0,identities:new Set()});
        const group=groups.get(observation.type);group.observations++;group.identities.add(observation.id);identities.add(observation.id);observations++;
      }
    }
    let measuredSamples=0,unavailableSamples=0;
    for(let i=firstAtOrAfter(index.replay.batches,window.start_ms,b=>b.observed_at_ms);i<index.replay.batches.length&&index.replay.batches[i].observed_at_ms<window.end_ms;i++){
      if(index.replay.batches[i].status==='measured')measuredSamples++;else unavailableSamples++;
    }
    const summary={observations,distinctRoadUsers:identities.size,measuredSamples,unavailableSamples,
      groups:[...groups.values()].sort((a,b)=>a.type.localeCompare(b.type)).map(group=>({type:group.type,
        observations:group.observations,distinctRoadUsers:group.identities.size,
        meanMeasuredSampleOccupancy:measuredSamples?group.observations/measuredSamples:null}))};
    /* At most 32 summaries; cached summaries contain counts, never identities. */
    if(index.cache.size>=32)index.cache.delete(index.cache.keys().next().value);
    index.cache.set(key,summary);return summary;
  }
  return {lastAtOrBefore, observationAt, releaseAt, diagnosticAt, cumulativeReleased,eventTimes,eventAfter,eventBefore,contains,privateCells,referenceSample,inputProvenance,selectCell,mosaicAt,selectEntry,entryContains,MAX_VISIBLE_FRAGMENTS,buildSourceIndex,sourceGroups,releaseAccounting,policyAt,mapImageRectangle};
}));
