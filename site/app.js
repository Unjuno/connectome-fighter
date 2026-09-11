const $ = (id) => document.getElementById(id);
const ACTION_ORDER = ['NEUTRAL','FORWARD','BACKWARD','UP','DOWN','A','B','C'];
let replayState = { replay:null, frames:[], timer:null };
let experimentHistory = [];

function fmt(v, fallback='—') { return v === null || v === undefined ? fallback : String(v); }
function pct(v) { return `${(100*Number(v||0)).toFixed(2)}%`; }
function esc(v='') { return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function setupCanvas(canvas, height) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || 800;
  canvas.width = Math.floor(w*dpr); canvas.height = Math.floor(height*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  return {ctx,w,h:height};
}

function renderCharacterTable(characters={}) {
  const root = $('character-table'); root.innerHTML='';
  for (const name of ['GARNET','ZEN','LUD','NEZ']) {
    const c = characters[name] || {rounds:0,wins:0,losses:0,draws:0,decisions:0};
    const tr=document.createElement('tr');
    tr.innerHTML=`<td><strong>${name}</strong></td><td>${fmt(c.rounds,0)}</td><td>${fmt(c.wins,0)}</td><td>${fmt(c.losses,0)}</td><td>${fmt(c.draws,0)}</td><td>${fmt(c.decisions,0)}</td>`;
    root.appendChild(tr);
  }
}

function renderActionBars(counts={}, rates={}) {
  const root=$('action-bars'); root.innerHTML='';
  for(const action of ACTION_ORDER){
    const rate=Number(rates[action]||0), count=Number(counts[action]||0);
    const row=document.createElement('div'); row.className='bar-row';
    row.innerHTML=`<div>${action}</div><div class="bar"><span style="width:${Math.min(100,rate*100).toFixed(2)}%"></span></div><div>${pct(rate)} · ${count}</div>`;
    root.appendChild(row);
  }
}

function drawHistory(history=experimentHistory) {
  const {ctx,w,h}=setupCanvas($('history'),220);
  ctx.fillStyle='#0c121b'; ctx.fillRect(0,0,w,h); ctx.strokeStyle='#273242'; ctx.strokeRect(.5,.5,w-1,h-1);
  if(!history.length){ ctx.fillStyle='#91a0b5'; ctx.fillText('No scheduled experiment history yet.',18,30); return; }
  const pad=28, n=history.length;
  const x=i=>pad+(n===1?0:i/(n-1))*(w-pad*2);
  const y=v=>h-pad-Math.max(0,Math.min(1,Number(v||0)))*(h-pad*2);
  const series=[
    {color:'#8ecbff', vals:history.map(x=>x.nonzero_reward_rate||0)},
    {color:'#f0b65b', vals:history.map(x=>x.action_rates?.B||0)},
  ];
  ctx.strokeStyle='#314054'; ctx.beginPath(); ctx.moveTo(pad,pad); ctx.lineTo(pad,h-pad); ctx.lineTo(w-pad,h-pad); ctx.stroke();
  for(const s of series){
    ctx.strokeStyle=s.color; ctx.lineWidth=2; ctx.beginPath();
    s.vals.forEach((v,i)=>{ const xx=x(i), yy=y(v); if(i===0) ctx.moveTo(xx,yy); else ctx.lineTo(xx,yy); }); ctx.stroke();
  }
  ctx.font='12px system-ui'; ctx.fillStyle='#8ecbff'; ctx.fillText('non-zero reward',pad+4,17); ctx.fillStyle='#f0b65b'; ctx.fillText('B action',pad+125,17);
  ctx.fillStyle='#91a0b5'; ctx.fillText('0%',2,h-pad+4); ctx.fillText('100%',2,pad+4);
}

function drawReplayFrame(frame, replay) {
  const {ctx,w,h}=setupCanvas($('replay'),330);
  ctx.fillStyle='#0f1720'; ctx.fillRect(0,0,w,h); ctx.strokeStyle='#3c4b60'; ctx.beginPath(); ctx.moveTo(20,h-38); ctx.lineTo(w-20,h-38); ctx.stroke();
  const mapX=x=>30+Math.max(0,Math.min(960,Number(x||0)))/960*(w-60);
  const mapY=y=>h-40-Math.max(0,Math.min(640,Number(y||0)))/640*(h-100);
  const fighters=[['p1','#8ecbff',replay?.p1?.character||'P1'],['p2','#ff9f8e',replay?.p2?.character||'P2']];
  for(const [key,color,label] of fighters){
    const s=frame?.[key]||{}, xx=mapX(s.x), yy=mapY(s.y);
    ctx.fillStyle=color; ctx.fillRect(xx-13,yy-36,26,36); ctx.fillStyle='#e7edf5'; ctx.font='12px system-ui';
    ctx.fillText(`${label} HP ${fmt(s.hp)} · ${fmt(s.action,'')}`,Math.max(8,Math.min(w-210,xx-85)),Math.max(18,yy-44));
  }
  ctx.fillStyle='#91a0b5'; ctx.fillText(`frame ${fmt(frame?.frame,0)}`,16,20); $('frame-label').textContent=`frame ${fmt(frame?.frame,0)}`;
}

function renderStructure(prefix, brain) {
  const root=$(`${prefix}-structure`); root.innerHTML='';
  const agg=new Map();
  for(const item of (brain?.top_bodies||[])){
    const a=item.annotation||{};
    const key=a.somaNeuromere || a.superclass || 'unresolved';
    const old=agg.get(key)||{spikes:0,bodies:0,classes:new Set()};
    old.spikes += Number(item.spikes||0); old.bodies += 1;
    if(a.superclass) old.classes.add(a.superclass);
    agg.set(key,old);
  }
  const entries=[...agg.entries()].sort((a,b)=>b[1].spikes-a[1].spikes);
  if(!entries.length){ root.innerHTML='<span class="muted">structural annotation unavailable</span>'; return; }
  const max=Math.max(1,...entries.map(x=>x[1].spikes));
  const isP2=prefix.includes('p2');
  for(const [name,v] of entries.slice(0,10)){
    const alpha=0.10+0.38*(v.spikes/max);
    const cell=document.createElement('div'); cell.className='structure-cell';
    cell.style.background=isP2?`rgba(255,159,142,${alpha})`:`rgba(142,203,255,${alpha})`;
    const classes=[...v.classes].slice(0,2).join(', ');
    cell.innerHTML=`<strong>${esc(name)}</strong><span>${v.spikes} spk · ${v.bodies} bodies</span><span class="muted">${esc(classes)}</span>`;
    root.appendChild(cell);
  }
}

function renderBrain(prefix, brain) {
  const summary=$(`${prefix}-summary`), groups=$(`${prefix}-groups`), list=$(prefix);
  groups.innerHTML=''; list.innerHTML='';
  if(!brain){ summary.textContent='No spike telemetry.'; renderStructure(prefix,null); return; }
  const m=brain.membrane_summary||{};
  summary.textContent=`total spikes ${fmt(brain.total_spikes,0)} · v mean ${Number(m.v_mean_mV||0).toFixed(2)} mV`;
  renderStructure(prefix,brain);
  const groupCounts=brain.group_spike_counts||{};
  const maxGroup=Math.max(1,...Object.values(groupCounts).map(Number));
  for(const action of ACTION_ORDER.slice(1)){
    const n=Number(groupCounts[action]||0); const row=document.createElement('div'); row.className='bar-row';
    row.innerHTML=`<div>${action}</div><div class="bar"><span style="width:${(100*n/maxGroup).toFixed(1)}%"></span></div><div>${n}</div>`; groups.appendChild(row);
  }
  for(const item of (brain.top_bodies||[])){
    const a=item.annotation||{};
    const detail=[a.somaNeuromere,a.superclass,a.type].filter(Boolean).join(' · ');
    const row=document.createElement('div'); row.className='brain-row';
    row.innerHTML=`<div class="brain-label" title="${esc(detail)}">body ${item.body_id}${detail?` · ${esc(detail)}`:''}</div><div class="bar"><span style="width:${(100*Number(item.relative||0)).toFixed(1)}%"></span></div><div>${item.spikes} spk</div>`; list.appendChild(row);
  }
}

function renderReplayIndex(index){
  const frames=replayState.frames, replay=replayState.replay; if(!frames.length) return;
  const i=Math.max(0,Math.min(frames.length-1,Number(index)||0)); $('replay-slider').value=i;
  const frame=frames[i]; drawReplayFrame(frame,replay); renderBrain('brain-p1',frame?.p1?.brain); renderBrain('brain-p2',frame?.p2?.brain);
}
function stopReplay(){ if(replayState.timer){ clearInterval(replayState.timer); replayState.timer=null; } }
function playReplay(){ stopReplay(); if(!replayState.frames.length) return; replayState.timer=setInterval(()=>{ let n=Number($('replay-slider').value)+1; if(n>=replayState.frames.length) n=0; renderReplayIndex(n); },Number($('speed').value)||130); }

async function loadReplay(url){
  stopReplay(); if(!url){ $('replay-status').textContent='No canonical replay yet.'; return; }
  try{
    const replay=await fetch(url,{cache:'no-store'}).then(r=>{if(!r.ok) throw new Error(`HTTP ${r.status}`); return r.json();});
    const frames=replay.frames||[]; if(!frames.length) throw new Error('replay has no frames'); replayState={replay,frames,timer:null};
    $('replay-slider').max=frames.length-1; $('replay-slider').value=0;
    $('brain-p1-title').textContent=`${replay.p1?.character||'P1'} brain`;
    $('brain-p2-title').textContent=`${replay.p2?.character||'P2'} brain`;
    const hp=replay.result?.remaining_hps||[];
    $('replay-status').textContent=`${replay.p1?.character} vs ${replay.p2?.character} · round ${fmt(replay.round_ordinal)} · HP ${fmt(hp[0])}-${fmt(hp[1])} · winner ${fmt(replay.result?.winner)}`;
    renderReplayIndex(0);
  } catch(err){ $('replay-status').textContent=`Replay unavailable: ${err.message}`; }
}

async function loadVideoMetadata(){
  try{
    const v=await fetch('./data/video.json',{cache:'no-store'}).then(r=>{if(!r.ok) throw new Error(`HTTP ${r.status}`); return r.json();});
    const video=$('fight-video');
    const source=video.querySelector('source');
    if(source && v.source_actions_run){ source.src=`./data/latest-fight.mp4?v=${encodeURIComponent(v.source_actions_run)}`; video.load(); }
    $('video-p1').textContent=fmt(v.p1?.character);
    $('video-p2').textContent=fmt(v.p2?.character);
    $('video-duration').textContent=`${Number(v.duration_seconds||0).toFixed(1)} sec`;
    $('video-rounds').textContent=fmt(v.rounds,1);
    $('pixel-access').textContent=v.policy_pixel_access?'YES':'NO';
    const ref=v.telemetry_reference||{};
    $('video-note').textContent=`${fmt(v.frames,0)} ScreenData frames · ${fmt(v.width)}×${fmt(v.height)} · ${fmt(v.fps)} fps。telemetry ref ${fmt(ref.run_id)} round ${fmt(ref.round_ordinal)} と同じキャラ/seed条件のfresh spectator runで、同一trajectoryとは断定していません。`;
    const videoRun=$('video-run');
    if(v.source_actions_run){ videoRun.href=`https://github.com/Unjuno/connectome-fighter/actions/runs/${encodeURIComponent(v.source_actions_run)}`; }
  } catch(err){ $('video-note').textContent=`Video metadata unavailable: ${err.message}`; }
}

async function main(){
  try{
    const status=await fetch('./data/status.json',{cache:'no-store'}).then(r=>{if(!r.ok) throw new Error(`HTTP ${r.status}`); return r.json();});
    const m=status.metrics||{}; experimentHistory=status.history||[];
    $('phase').textContent=fmt(status.phase); $('phase-pill').textContent=String(status.phase||'baseline').replace('canonical-','').replaceAll('-',' '); $('updated').textContent=fmt(status.updated_at);
    $('independent-rounds').textContent=fmt(m.independent_rounds,0); $('raw-rounds').textContent=fmt(m.raw_rounds,0); $('reward-rate').textContent=`${fmt(m.independent_nonzero_reward_rounds,0)} / ${fmt(m.independent_rounds,0)} (${pct(m.independent_nonzero_reward_rate)})`; $('decisions').textContent=fmt(m.total_decisions,0);
    renderCharacterTable(m.characters||{}); renderActionBars(m.action_counts||{},m.action_rates||{}); drawHistory();
    const src=$('source-run'); if(status.source_run_url){ src.href=status.source_run_url; } else { src.href='https://github.com/Unjuno/connectome-fighter/actions'; }
    await Promise.all([loadReplay(status.latest_match?.replay_url||null), loadVideoMetadata()]);
  } catch(err){ $('phase').textContent='status load failed'; $('phase-pill').textContent='status error'; $('error').textContent=err.message; await loadVideoMetadata(); }
}

$('replay-slider').addEventListener('input',e=>{stopReplay(); renderReplayIndex(e.target.value);});
$('play').addEventListener('click',playReplay); $('pause').addEventListener('click',stopReplay);
$('speed').addEventListener('change',()=>{if(replayState.timer) playReplay();});
window.addEventListener('resize',()=>{if(replayState.frames.length) renderReplayIndex($('replay-slider').value); drawHistory();});
main();
