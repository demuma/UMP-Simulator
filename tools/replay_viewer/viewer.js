/* Research UI: all dynamic labels are text, and all result cells come from recorded output. */
'use strict';
const $ = id => document.getElementById(id);
const M = UMPReplay;
const palette = ['#236594','#a95f27','#438360','#925fa3','#b14f6c','#8b8330','#4a7e82','#755f4a'];
const seconds = ms => (ms / 1000).toFixed(2) + ' s';
const number = value => value == null ? '—' : Number(value).toLocaleString('en-US',{maximumFractionDigits:3});
const readable = name => name.replaceAll('_',' ');
const element = (tag,text,className) => {const item=document.createElement(tag);if(text!=null)item.textContent=text;if(className)item.className=className;return item;};
let replay, manifest, variants, events, allTypes, sourceIndex, mapImage=null, time=0, playing=false, lastTick=0;
const selections = {A:null,B:null};
const selectionCellIds = {A:null,B:null};
const selectorRows = {A:undefined,B:undefined};
const layouts = {};
let overviewVariants=null;
const mappedTracks=()=>manifest.identity_unit==='visible_episode_track';
const identityLabel=()=>mappedTracks()?'distinct tracks':'distinct observed IDs';
function stats(id, entries) {const parent=$(id);parent.replaceChildren();for(const [label,value]of entries){const item=element('div',null,'stat');item.append(element('strong',value,'mono'),document.createTextNode(label));parent.append(item);}}
function canvasContext(id) {
 const canvas=$(id), bounds=canvas.getBoundingClientRect(), ratio=window.devicePixelRatio||1;
 const width=Math.max(120,bounds.width),height=Math.max(65,bounds.height);
 canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
 const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,width,height);
 return {ctx,width,height};
}
function baseMap(id,g=replay.coverage) {
 const {ctx,width,height}=canvasContext(id);
 const scale=Math.min((width-57)/g.width,(height-45)/g.height),w=g.width*scale,h=g.height*scale;
 const left=39+(width-49-w)/2,top=12+(height-42-h)/2;
 const layout={left,top,scale,w,h,width,height,ctx,viewport:g};layouts[id]=layout;
 ctx.fillStyle='#f0f3f5';ctx.fillRect(left,top,w,h);
 if(mapImage){const rect=M.mapImageRectangle(manifest.map.bounds,g,layout);ctx.save();ctx.beginPath();ctx.rect(left,top,w,h);ctx.clip();ctx.drawImage(mapImage,rect.x,rect.y,rect.width,rect.height);ctx.restore();}
 ctx.strokeStyle='#d3dce3';ctx.lineWidth=1;ctx.strokeRect(left,top,w,h);
 ctx.fillStyle='#657886';ctx.font='10px -apple-system, sans-serif';
 for(let i=0;i<=4;i++) {ctx.textAlign='center';ctx.fillText(number(g.x+g.width*i/4),left+w*i/4,top+h+17);ctx.textAlign='right';ctx.fillText(number(g.y+g.height*i/4),left-6,top+h*i/4+3);}
 ctx.textAlign='right';ctx.fillText('x / y (m)',left+w,top+h+31);
 return layout;
}
function geographyLabels(layout){
 if(!manifest.map||!$('mapNames').checked)return;
 const {ctx,left,top,w,h,scale,viewport:g}=layout;
 ctx.save();ctx.beginPath();ctx.rect(left,top,w,h);ctx.clip();ctx.font='600 10px -apple-system,sans-serif';ctx.textAlign='center';ctx.lineWidth=3;ctx.strokeStyle='rgba(255,255,255,.95)';
 for(const label of manifest.map.labels??[]){if(label.x<g.x||label.x>g.x+g.width||label.y<g.y||label.y>g.y+g.height)continue;
   const x=left+(label.x-g.x)*scale,y=top+(label.y-g.y)*scale;
   ctx.fillStyle=label.kind==='street'?'#41546a':'#68482b';ctx.strokeText(label.text,x,y);ctx.fillText(label.text,x,y);
 }
 ctx.restore();
}
function drawPolicyRegions(layout,selectedVariants){
 if(!$('policyRegions').checked)return;
 const {ctx,left,top,w:mapWidth,h:mapHeight,scale,viewport:g}=layout,seen=new Set();
 ctx.save();ctx.beginPath();ctx.rect(left,top,mapWidth,mapHeight);ctx.clip();
 for(const v of selectedVariants)for(const region of policyRegions(v)){
   const key=JSON.stringify([region.id,region.x,region.y,region.width,region.height]);if(seen.has(key))continue;seen.add(key);
   const x=left+(region.x-g.x)*scale,y=top+(region.y-g.y)*scale,w=region.width*scale,h=region.height*scale;
   ctx.strokeStyle='#704ca0';ctx.lineWidth=1.8;ctx.setLineDash([5,3]);ctx.strokeRect(x,y,w,h);ctx.setLineDash([]);
   if(w>30&&h>18){ctx.font='10px -apple-system,sans-serif';ctx.textAlign='left';ctx.lineWidth=3;ctx.strokeStyle='#fff';ctx.strokeText(region.id,x+3,y+12);ctx.fillStyle='#523277';ctx.fillText(region.id,x+3,y+12);}
 }
 ctx.restore();
}
function motion() {
 const frame=M.observationAt(replay,time),focus=$('referenceFocus').value;
 const selected=focus==='A'||focus==='B'?displayed(focus):null;
 const chosenEntry=selected?M.selectEntry(selected.entries,selections[focus],selectionCellIds[focus]):null;
 const chosen=chosenEntry?.cell;
 const g=chosen||replay.coverage,{ctx,left,top,scale,w,h}=baseMap('reference',g);
 const sample=M.referenceSample(frame.visible,g),types=new Map();
 geographyLabels(layouts.reference);drawPolicyRegions(layouts.reference,[variant('A'),variant('B')]);
 for(const observation of frame.visible){if(!types.has(observation.type))types.set(observation.type,{total:0,shown:0});types.get(observation.type).total++;}
 ctx.save();ctx.beginPath();ctx.rect(left,top,w,h);ctx.clip();
 for(const group of sample.groups){
   const x=left+(group.x-g.x)*scale,y=top+(group.y-g.y)*scale,radius=group.observations.length>1?3.3:2.6;
   for(const [index,roadUser]of group.observations.entries()){
     const color=palette[allTypes.indexOf(roadUser.type)%palette.length],start=-Math.PI/2+index/group.observations.length*Math.PI*2,end=start+Math.PI*2/group.observations.length;
     ctx.beginPath();ctx.moveTo(x,y);ctx.arc(x,y,radius,start,end);ctx.closePath();ctx.fillStyle=color;ctx.fill();types.get(roadUser.type).shown++;
   }
   if(group.observations.length>1){ctx.font='bold 10px -apple-system,sans-serif';ctx.textAlign='left';ctx.lineWidth=3;ctx.strokeStyle='#fff';ctx.strokeText(String(group.observations.length),x+5,y-4);ctx.fillStyle='#263b49';ctx.fillText(String(group.observations.length),x+5,y-4);}
 }
 ctx.restore();
 const labels={not_yet_sampled:'No sensor sample has arrived yet.',unavailable:'The most recent scheduled measurement is unavailable.',missing_sample:'No current sensor sample is available. Previous positions are cleared.'};
 const positionText=frame.status==='measured'?`Current recorded sample at ${seconds(frame.batch.observed_at_ms)} · held for ${seconds(frame.age)} until the next expected sample. Positions are not interpolated.`:labels[frame.status];
 const focusText=chosen?` Viewport: comparison ${focus}, cell ${chosen.cell_id}, ${number(chosen.width)} × ${number(chosen.height)} m. This footprint comes from historical [${seconds(chosenEntry.row.start_ms)}, ${seconds(chosenEntry.row.end_ms)}); the dots above remain the current sample.${chosenEntry.partial?' This is the original whole footprint of a partially covered historical aggregate.':''}`:focus!=='full'?' The selected comparison has no finalized cell yet; the full area is shown.':' Full recorded area.';
 $('referenceCaption').textContent=positionText+focusText;
 stats('referenceStats',[[mappedTracks()?'track IDs in full sample':'observed IDs in full sample',number(sample.totalCount)],['distinct XY in full sample',number(sample.totalPositions)],[mappedTracks()?'track IDs in this viewport':'observed IDs in this viewport',number(sample.visibleCount)]]);
 const detail=$('referenceDetail');detail.replaceChildren(element('h3','Current sample · recorded road-user types'));
 detail.append(element('p',`${number(sample.visibleCount)} IDs at ${number(sample.visiblePositions)} distinct coordinates in this viewport · sample interval ${seconds(replay.sampling_period_ms)} · finest cell side ${number(replay.coverage.width/2**replay.coverage.leaf_depth)} m`,'scope'));
 if(!types.size)detail.append(element('p','No measured positions are displayed at this timestamp.','muted'));
 else {
   const sorted=[...types].sort((a,b)=>a[0].localeCompare(b[0]));
   const table=groupTable(['Recorded type','Full sample','In viewport'],sorted.map(([type,count])=>[type,number(count.total),number(count.shown)]));
   for(const [index,[type]]of sorted.entries()){const dot=element('i',null,'dot');dot.style.background=palette[allTypes.indexOf(type)%palette.length];table.tBodies[0].rows[index].cells[0].prepend(dot);}
   detail.append(table);
 }
 detail.append(element('p','A numbered dot represents multiple IDs at exactly the same recorded XY position. Its colored sectors show their types. Close but different positions can still overlap at this scale; zoom preserves their exact coordinates.','scope'));
 detail.append(element('p','These counts describe one current sample. Selected release cells and private source-group tables describe whole historical windows; their identity counts can differ.','scope'));
}
function variant(side) {return variants[Number($('variant'+side).value)];}
function displayed(side) {
 const v=variant(side),privateMode=$('private').checked;
 return {v,privateMode,...M.mosaicAt(v.result,time,privateMode)};
}
function releaseMap(side) {
 const view=displayed(side),{v,entries,privateMode,local,latestEvent}=view,id='map'+side;
 const chosen=M.selectEntry(entries,selections[side],selectionCellIds[side]);selections[side]=chosen?.key??null;selectionCellIds[side]=chosen?.cell.cell_id??null;
 const g=$('focus'+side).checked&&chosen?chosen.cell:replay.coverage,{ctx,left,top,scale,w:mapWidth,h:mapHeight}=baseMap(id,g);
 ctx.save();ctx.beginPath();ctx.rect(left,top,mapWidth,mapHeight);ctx.clip();
 for(const entry of entries){
   const cell=entry.cell,suppressed=privateMode&&!cell.selected,loss=cell.semantic?.semantic_max_loss??0;
   for(const fragment of entry.fragments){
     const x=left+(fragment.x-g.x)*scale,y=top+(fragment.y-g.y)*scale,w=fragment.width*scale,h=fragment.height*scale;
     ctx.globalAlpha=mapImage ? 0.65 : 1;ctx.fillStyle=suppressed?'#edb4a1':`hsl(${166-loss*21} ${39+loss*4}% ${80-loss*9}%)`;ctx.fillRect(x,y,w,h);ctx.globalAlpha=1;
     ctx.strokeStyle=entry.key===selections[side]?'#16529e':suppressed?'#bb654d':'#4b7f81';ctx.lineWidth=entry.key===selections[side]?2.6:1;
     if(entry.partial)ctx.setLineDash([4,3]);
     ctx.strokeRect(x+.5,y+.5,Math.max(0,w-1),Math.max(0,h-1));ctx.setLineDash([]);
     if(suppressed||entry.partial){ctx.save();ctx.beginPath();ctx.rect(x,y,w,h);ctx.clip();ctx.strokeStyle=suppressed?'#ba604a':'#648a8c';ctx.lineWidth=.7;for(let a=-h;a<w;a+=10){ctx.beginPath();ctx.moveTo(x+a,y);ctx.lineTo(x+a+h,y+h);ctx.stroke();}ctx.restore();}
     // A mask is not a newly measured cell. Whole-cell counts must not be
     // repeated or apportioned into the visible remnants of an older parent.
     if(w>28&&h>22&&!entry.partial){ctx.fillStyle='#23464c';ctx.font=`${w>55?13:10}px -apple-system,sans-serif`;ctx.textAlign='center';ctx.fillText(suppressed?'×':number(cell.mean_sample_occupancy),x+w/2,y+h/2+4);}
   }
 }
 ctx.restore();
 geographyLabels(layouts[id]);drawPolicyRegions(layouts[id],[v]);
 $('map'+side).setAttribute('aria-label',`${privateMode?'Finalized decision':'Released aggregation'} mosaic ${side}`);
 const title=$('variant'+side).previousElementSibling;
 title.textContent=`Comparison ${side} · ${privateMode?'Private finalized decisions':'Published history'}${local?' · local windows':' · common window'}`;
 if(!latestEvent)$('caption'+side).textContent=`No ${privateMode?'finalized decision':'release'} is available yet. Blank areas are unknown; they do not mean zero traffic.`;
 else if(local){
   const stamp=privateMode?latestEvent.evaluated_at_ms:latestEvent.sealed_at_ms;
   $('caption'+side).textContent=`Historical mosaic of ${number(entries.length)} original aggregates with independent intervals. Latest ${privateMode?'decision':'publication'} at ${seconds(stamp)}. Select a cell for its own interval and age. ${privateMode?'Empty private retirements clear only this diagnostic view.':'Last published values remain visible without a newer publication; they are not current occupancy.'}`;
 } else {
   const stamp=privateMode?latestEvent.evaluated_at_ms:latestEvent.sealed_at_ms;
   $('caption'+side).textContent=`[${seconds(latestEvent.start_ms)}, ${seconds(latestEvent.end_ms)}) · ${privateMode?'evaluated':'sealed'} at ${seconds(stamp)} · ${seconds(time-latestEvent.end_ms)} since window end. ${privateMode?'Private diagnostics; suppressed cells are hatched.':'Latest released historical aggregate, retained on screen until another release. This is not a current occupancy measurement.'}`;
 }
 const released=M.releaseAccounting(v.result,time),fragments=entries.reduce((sum,entry)=>sum+entry.fragments.length,0);
 stats('stats'+side,[[privateMode?'visible finalized footprints':'visible historical aggregates',number(entries.length)],['published cell-windows so far',number(released.publishedCellWindows)],['unique published spatial IDs',number(released.uniqueSpatialCells)],['released / total run observations',number(released.contributions)+' / '+number(v.result.input_observation_contributions)],['actual release events so far',number(released.releaseEvents)],['visible geometry fragments',number(fragments)]]);
 updateCellSelector(side,entries);
 details(side);
}
function updateCellSelector(side,entries) {
 const select=$('cell'+side);
 if(selectorRows[side]!==entries){
   select.replaceChildren();
   if(!entries.length){const option=element('option','No visible aggregates at this timestamp');option.value='';select.append(option);}
   for(const entry of entries){const cell=entry.cell,row=entry.row;const option=element('option',`${cell.cell_id} · d${cell.depth} · ${number(cell.width)} × ${number(cell.height)} m · [${seconds(row.start_ms)}, ${seconds(row.end_ms)})${cell.selected===false?' · suppressed':''}${entry.partial?' · partially covered':''}`);option.value=entry.key;select.append(option);}
   selectorRows[side]=entries;
 }
 select.disabled=!entries.length;select.value=selections[side]??'';
}
function groupTable(headers,rows) {
 const table=element('table'),caption=element('caption');caption.className='sr-only';caption.textContent=headers[0]+' breakdown';table.append(caption);
 const head=element('thead'),heading=element('tr');for(const name of headers){const th=element('th',name);th.scope='col';heading.append(th);}head.append(heading);table.append(head);
 const body=element('tbody');for(const values of rows){const tr=element('tr');for(const value of values)tr.append(element('td',value));body.append(tr);}table.append(body);return table;
}
function policyRegions(v) {
 return (Array.isArray(v.policy_regions)?v.policy_regions:[]).filter(region=>typeof region.id==='string'&&['x','y','width','height'].every(key=>Number.isFinite(region[key]))&&region.width>0&&region.height>0);
}
function details(side) {
 const {v,entries,privateMode}=displayed(side),detail=$('detail'+side),entry=entries.find(e=>e.key===selections[side]),cell=entry?.cell,row=entry?.row;detail.replaceChildren();
 if(!cell){detail.append(element('h3','No cell to inspect'),element('p','Seek to a release event. A suppressed or absent recipient footprint is unknown, not a released zero.','muted'));return;}
 detail.append(element('h3',`Cell ${cell.cell_id} · depth ${cell.depth} · ${number(cell.width)} × ${number(cell.height)} m`));
 detail.append(element('p',`x ∈ [${number(cell.x)}, ${number(cell.x+cell.width)}) m · y ∈ [${number(cell.y)}, ${number(cell.y+cell.height)}) m · source interval [${seconds(row.start_ms)}, ${seconds(row.end_ms)})`,'scope'));
 const finalized=privateMode?row.evaluated_at_ms:row.sealed_at_ms;
 detail.append(element('p',`${privateMode?'Evaluated':'Published'} at ${seconds(finalized)} · ${seconds(time-row.end_ms)} since this interval ended · ${seconds(finalized-row.start_ms)} interval-start age at ${privateMode?'evaluation':'release'}. Historical values, not a synchronized current measurement.`,'scope'));
 if(entry.partial)detail.append(element('p',`Partially covered by newer ${privateMode?'decisions':'publications'}: ${number(entry.fragments.length)} visible fragment(s) remain. All counts and groups below belong to the entire original ${number(cell.width)} × ${number(cell.height)} m cell and its original interval. Counts for the visible fragments alone are unknown.`,'notice'));
 detail.append(element('p',`${number(cell.observation_contributions)} observations · ${number(cell.distinct_road_users)} ${identityLabel()} · mean occupancy ${number(cell.mean_sample_occupancy)}`));
 if(privateMode)detail.append(element('p',`${cell.selected?'Selected':'Suppressed'} · ${readable(cell.reason||'')} · ${readable(row.completion_reason||'')}`,'scope'));
 if($('policyRegions').checked)appendPolicy(detail,v,cell);
 detail.append(element('h4',privateMode&&!cell.selected?'Recorded candidate groups · private':'Released road-user groups'));
 if(cell.semantic){const s=cell.semantic;detail.append(groupTable(['Category','Observations',mappedTracks()?'Distinct tracks':'Distinct IDs'],s.categories.map(b=>[readable(b.category_id),number(b.observation_contributions),number(b.distinct_contributors)])));detail.append(element('p',`Smallest category support ${number(s.min_category_distinct_contributors)} · semantic loss max ${number(s.semantic_max_loss)}, mean ${number(s.semantic_mean_loss)} · taxonomy ${s.taxonomy_id} v${s.taxonomy_version}`,'scope'));}
 else detail.append(element('p','No semantic category breakdown was recorded for this cell. Total counts do not identify its road-user types.','muted'));
 if($('sourceGroups').checked){
   const source=M.sourceGroups(sourceIndex,cell,row,time,true),box=element('section',null,'private-source');box.append(element('h4','Private source groups · same cell and window'));
   box.append(element('p','Exact recorded input types before semantic generalization. This information is not part of the recipient release.','scope'));
   if(source){
     if(source.groups.length)box.append(groupTable(['Recorded type','Observations',mappedTracks()?'Distinct tracks':'Distinct IDs','Mean / measured sample'],source.groups.map(g=>[g.type,number(g.observations),number(g.distinctRoadUsers),number(g.meanMeasuredSampleOccupancy)])));
     else box.append(element('p','No measured input observations lie in this footprint and interval.'));
     box.append(element('p',`${number(source.observations)} input observations · ${number(source.distinctRoadUsers)} ${identityLabel()} · ${number(source.measuredSamples)} measured samples · ${number(source.unavailableSamples)} explicitly unavailable samples. Coverage: means use recorded measured samples only; unavailable or absent scheduled samples are not reconstructed.`,'scope'));
     box.append(element('p','Counts cover the entire displayed interval, not the current position sample. An observed ID can contribute to multiple types if its recorded classification changes; per-type distinct counts must not be summed.','scope'));
   }else box.append(element('p','No finalized cell interval is available for private inspection.'));
   detail.append(box);
 }
 if(privateMode&&cell.checks?.length){const table=element('table'),head=element('tr');for(const name of ['Policy metric','Observed','Required'])head.append(element('th',name));table.append(head);for(const check of cell.checks){const tr=element('tr',null,check.status==='pass'?'':'fail'),bounds=(check.min!=null?'≥ '+number(check.min):'')+(check.min!=null&&check.max!=null?' · ':'')+(check.max!=null?'≤ '+number(check.max):'');tr.append(element('td',readable(check.metric)),element('td',number(check.observed)),element('td',bounds+' · '+check.status));table.append(tr);}detail.append(table);}
 else detail.append(element('p',privateMode?'Observed metric checks were not recorded for this cell. The declared bounds above do not constitute a reconstructed pass/fail evaluation.':'Observed metric checks and failed candidates are private diagnostics. Enable the diagnostic overlay to inspect them when recorded.','scope'));
}
function boundText(requirement){return [requirement.min!=null?'≥ '+number(requirement.min):'',requirement.max!=null?'≤ '+number(requirement.max):''].filter(Boolean).join(' · ');}
function appendPolicy(detail,v,cell){
 const policy=M.policyAt(v,cell);detail.append(element('h4','Declared effective policy · private metadata'));
 detail.append(element('p',`Tree: ${v.policy_tree_id??v.result.parameters?.policy_tree_id??'ID not supplied'}. ${policy.rootDeclared?'Root requirements supplied.':'Root requirements not supplied; the full effective policy is unknown.'}`,'scope'));
 const rows=policy.requirements.map(bound=>[readable(bound.metric),boundText(bound)+(bound.conflict?' · CONFLICT':''),bound.sources.map(source=>source.source+' '+boundText(source)).join('; ')]);
 if(rows.length)detail.append(groupTable(['Metric','Combined bounds','Provenance'],rows));
 else detail.append(element('p','No declared bounds are supplied for this footprint.','muted'));
 if(policy.conflicting)detail.append(element('p','Conflicting declared bounds: no candidate can satisfy these bounds together. This is a metadata consistency finding, not an observed metric check.','notice'));
 detail.append(element('p',policy.regions.length?'Intersecting regions: '+policy.regions.map(region=>region.id+(region.type?' ('+region.type+')':'')).join(', ')+'. All intersecting bounds combine; minimum requirements increase and maximum allowances decrease.':'No declared region intersects this footprint.','scope'));
 detail.append(element('p','This inspector combines declared numeric bounds across the whole original cell footprint. It does not invent metric values or reproduce an unrecorded runtime decision.','scope'));
}
function policyOverview(){
 const selected=[variant('A'),variant('B')];if(overviewVariants&&selected.every((v,i)=>v===overviewVariants[i]))return;overviewVariants=selected;
 const parent=$('policyOverview');parent.replaceChildren();
 for(const side of ['A','B']){const v=variant(side),box=element('section',null,'policy-card');box.append(element('h3',`Comparison ${side} · ${v.label}`));
   box.append(element('p',`Tree: ${v.policy_tree_id??v.result.parameters?.policy_tree_id??'ID not supplied'}`,'scope'));
   box.append(element('h4','Root requirements'));
   if(Array.isArray(v.policy_root_requirements))box.append(groupTable(['Metric','Bound'],v.policy_root_requirements.map(bound=>[readable(bound.metric),boundText(bound)])));
   else box.append(element('p','Root requirements were not included in this older bundle.','muted'));
   box.append(element('h4','Declared regions'));
   const regions=policyRegions(v);
   if(!regions.length)box.append(element('p','No region metadata is supplied.','muted'));
   for(const region of regions){box.append(element('p',`${region.id}${region.type?' · '+region.type:''} · x [${number(region.x)}, ${number(region.x+region.width)}) · y [${number(region.y)}, ${number(region.y+region.height)}) m`));
     box.append(element('p',(region.requirements??[]).map(bound=>readable(bound.metric)+' '+boundText(bound)).join('; ')||'No additional bounds supplied.','scope'));
   }
   parent.append(box);
 }
}
function legends(){
 const geography=$('geographyLegend');geography.replaceChildren();
 if(manifest.map){geography.append(element('strong','Map geography'));for(const entry of manifest.map.legend??[]){const label=element('span'),swatch=element('i',null,'swatch');swatch.style.background=entry.color;label.append(swatch,document.createTextNode(entry.label));geography.append(label);}}
 else geography.hidden=true;
 const types=$('typeLegend');types.replaceChildren(element('strong','Observed track types'));
 for(const [index,type]of allTypes.entries()){const label=element('span'),dot=element('i',null,'dot');dot.style.background=palette[index%palette.length];label.append(dot,document.createTextNode(type));types.append(label);}
 $('mapAttribution').textContent=manifest.map?.attribution??'';
 $('identityNotice').textContent=mappedTracks()?'Identity unit: visible-episode track. Reappearance after an indoor gap gets a new ID. Distinct tracks are not a count of distinct people; stable private person identities are not supplied to this viewer.':'Identity unit: recorded observed ID. The bundle does not establish that every ID corresponds to a different person.';
 $('mapNamesControl').hidden=!manifest.map;
}
function history() {
 const {ctx,width,height}=canvasContext('lanes'),left=85,w=width-left-12,privateMode=$('private').checked;
 $('lanes').setAttribute('aria-label',privateMode?'Private finalized decision timeline':'Release event timeline');
 $('historyTitle').textContent=privateMode?'Finalized decision events · private':'Actual release events';
 $('historyHint').textContent=privateMode?'Marks are evaluation times, including empty and suppressed retirements.':'Marks are sealing times, not measurement times. Click the timeline to seek.';
 for(const [i,side]of ['A','B'].entries()){const y=19+i*27,v=variant(side),rows=privateMode?v.result.windows:v.result.releases;ctx.font='11px -apple-system,sans-serif';ctx.fillStyle='#536574';ctx.textAlign='left';ctx.fillText('Comparison '+side,0,y+4);ctx.strokeStyle='#dce4ea';ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(left+w,y);ctx.stroke();for(const row of rows){const stamp=privateMode?row.evaluated_at_ms:row.sealed_at_ms,x=left+w*stamp/replay.end_ms;ctx.fillStyle=stamp<=time?'#258b87':'#b9c9d4';ctx.fillRect(x-1,y-5,2,10);}}
 const marker=left+w*time/replay.end_ms;ctx.strokeStyle='#215984';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(marker,2);ctx.lineTo(marker,height-3);ctx.stroke();layouts.lanes={left,w};
}
function renderFrame(){time=Math.max(0,Math.min(replay.end_ms,time));if(!playing)$('play').textContent=time>=replay.end_ms?'↺ Replay':'▶ Play';$('clock').textContent=seconds(time);$('timeline').value=time;motion();releaseMap('A');releaseMap('B');history();policyOverview();$('previous').disabled=time<=0;$('next').disabled=time>=replay.end_ms;}
function render(){try{renderFrame();}catch(error){pause();$('application').hidden=true;$('error').hidden=false;$('error').textContent='Replay display stopped: '+error.message;}}
function pause(){playing=false;$('play').textContent=time>=replay.end_ms?'↺ Replay':'▶ Play';}
function tick(timestamp){if(playing){if(lastTick)time+=Math.min(250,timestamp-lastTick)*Number($('speed').value);if(time>=replay.end_ms){time=replay.end_ms;pause();}render();}lastTick=timestamp;requestAnimationFrame(tick);}
async function fetchJSON(path){const response=await fetch(path);if(!response.ok)throw new Error(`${response.status}: ${path}`);return response.json();}
async function start(){
 manifest=await fetchJSON('/bundle/bundle.json');if(manifest.schema!=='ump.replay-viewer.v1')throw new Error('Unsupported viewer bundle schema');
 replay=await fetchJSON('/bundle/'+manifest.observations);
 if(manifest.map){mapImage=await new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('Declared local map PNG could not be decoded'));image.src='/bundle/'+manifest.map.image;});}
 sourceIndex=M.buildSourceIndex(replay);
 allTypes=[...new Set(replay.batches.flatMap(b=>b.observations.map(o=>o.type)))].sort();
 variants=await Promise.all(manifest.variants.map(async v=>({...v,result:await fetchJSON('/bundle/'+v.result)})));
 if(manifest.title)$('title').textContent=manifest.title;
 $('referenceProvenance').textContent=M.inputProvenance(manifest).text;
 legends();
 events=M.eventTimes(variants,replay.end_ms);
 $('duration').textContent=seconds(replay.end_ms)+' recorded';$('timeline').max=replay.end_ms;
 $('source').textContent=`${replay.run_id} · ${number(replay.coverage.width)} × ${number(replay.coverage.height)} m · leaf depth ${replay.coverage.leaf_depth}`;
 $('provenance').textContent=`${variants.length} frozen result variants · shared observations`;
 for(const side of ['A','B']){const select=$('variant'+side);for(const [index,v]of variants.entries()){const option=element('option',v.label);option.value=index;select.append(option);}select.value=side==='A'?0:Math.min(1,variants.length-1);select.addEventListener('change',()=>{selections[side]=null;selectionCellIds[side]=null;render();});$('cell'+side).addEventListener('change',event=>{selections[side]=event.target.value;selectionCellIds[side]=displayed(side).entries.find(e=>e.key===event.target.value)?.cell.cell_id??null;render();});$('focus'+side).addEventListener('change',render);$('map'+side).addEventListener('click',event=>{const l=layouts['map'+side],r=event.currentTarget.getBoundingClientRect(),x=(event.clientX-r.left-l.left)/l.scale+l.viewport.x,y=(event.clientY-r.top-l.top)/l.scale+l.viewport.y;const entry=displayed(side).entries.find(e=>M.entryContains(e,x,y));selections[side]=entry?.key??null;selectionCellIds[side]=entry?.cell.cell_id??null;render();});}
 $('play').addEventListener('click',()=>{if(playing){pause();return;}if(time>=replay.end_ms)time=0;playing=true;lastTick=0;$('play').textContent='Ⅱ Pause';});
 $('previous').addEventListener('click',()=>{pause();time=M.eventBefore(events,time);render();});$('next').addEventListener('click',()=>{pause();time=M.eventAfter(events,time);render();});
 $('timeline').addEventListener('input',event=>{pause();time=Number(event.target.value);render();});$('private').addEventListener('change',()=>{events=M.eventTimes(variants,replay.end_ms,$('private').checked);selections.A=null;selections.B=null;selectionCellIds.A=null;selectionCellIds.B=null;render();});$('sourceGroups').addEventListener('change',render);$('policyRegions').addEventListener('change',render);$('mapNames').addEventListener('change',render);$('referenceFocus').addEventListener('change',render);
 $('lanes').addEventListener('click',event=>{pause();const r=event.currentTarget.getBoundingClientRect(),l=layouts.lanes;time=(event.clientX-r.left-l.left)/l.w*replay.end_ms;render();});
 window.addEventListener('resize',render);$('application').hidden=false;render();requestAnimationFrame(tick);
}
start().catch(error=>{$('application').hidden=true;$('error').hidden=false;$('error').textContent='Replay could not be loaded: '+error.message;});
