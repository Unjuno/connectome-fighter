const $ = (id) => document.getElementById(id);
const COLORS = {GARNET:'#f0b65b', ZEN:'#8ecbff', LUD:'#8fe0a3', NEZ:'#d8a4ff'};
let replayState = {replay:null, frames:[], timer:null};

function fmt(v, fallback='—') { return v === null || v === undefined ? fallback : String(v); }

function renderCharacters(characters={}) {
  const root = $('characters');
  root.innerHTML = '';
  for (const name of ['GARNET','ZEN','LUD','NEZ']) {
    const c = characters[name] || {};
    const card = document.createElement('div');
    card.className = 'card';
    card.style.borderTop = `3px solid ${COLORS[name]}`;
    card.innerHTML = `
      <div class="character-name">${name}</div>
      <div class="label">generation</div><div class="metric">${fmt(c.generation,'0')}</div>
      <div class="label">training matches</div><div>${fmt(c.training_matches,'0')}</div>
      <div class="label">Elo</div><div>${fmt(c.elo,'1500')}</div>
      <div class="label">checkpoint</div><div style="overflow-wrap:anywhere">${fmt(c.checkpoint_id,'not initialized')}</div>`;
    root.appendChild(card);
  }
}

function setupCanvas(canvas, height) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || 800;
  const h = height;
  canvas.width = Math.floor(w*dpr); canvas.height = Math.floor(h*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  return {ctx,w,h};
}

function drawHistory(characters={}) {
  const {ctx,w,h} = setupCanvas($('history'), 240);
  ctx.clearRect(0,0,w,h); ctx.strokeStyle='#273242'; ctx.strokeRect(.5,.5,w-1,h-1);
  const series = Object.entries(characters)
    .map(([name,c]) => [name,(c.history||[]).filter(x => Number.isFinite(Number(x.elo)))])
    .filter(([,points]) => points.length);
  if (!series.length) { ctx.fillStyle='#91a0b5'; ctx.font='14px system-ui'; ctx.fillText('No learning history yet.',18,32); return; }
  const values = series.flatMap(([,p]) => p.map(x => Number(x.elo)));
  const minY=Math.min(...values), maxY=Math.max(...values), span=Math.max(1,maxY-minY);
  const maxN=Math.max(...series.map(([,p])=>p.length));
  series.forEach(([name,points],si) => {
    ctx.strokeStyle=COLORS[name]||'#fff'; ctx.lineWidth=2; ctx.beginPath();
    points.forEach((p,i) => {
      const x=18+(maxN===1?0:i/(maxN-1))*(w-36);
      const y=h-24-(Number(p.elo)-minY)/span*(h-50);
      if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }); ctx.stroke();
    ctx.fillStyle=COLORS[name]||'#fff'; ctx.fillText(name,18+si*90,18);
  });
  ctx.fillStyle='#91a0b5'; ctx.fillText(`${minY.toFixed(0)}–${maxY.toFixed(0)} Elo`,w-120,h-8);
}

function drawReplayFrame(frame, replay) {
  const {ctx,w,h}=setupCanvas($('replay'),330);
  ctx.fillStyle='#0f1720'; ctx.fillRect(0,0,w,h);
  ctx.strokeStyle='#3c4b60'; ctx.beginPath(); ctx.moveTo(20,h-38); ctx.lineTo(w-20,h-38); ctx.stroke();
  const mapX=x=>30+Math.max(0,Math.min(960,Number(x||0)))/960*(w-60);
  const mapY=y=>h-40-Math.max(0,Math.min(640,Number(y||0)))/640*(h-100);
  const fighters=[['p1','#8ecbff',replay?.p1?.character||'P1'],['p2','#ff9f8e',replay?.p2?.character||'P2']];
  for(const [key,color,label] of fighters){
    const s=frame?.[key]||{}, x=mapX(s.x), y=mapY(s.y);
    ctx.fillStyle=color; ctx.fillRect(x-13,y-36,26,36);
    ctx.fillStyle='#e7edf5'; ctx.font='12px system-ui';
    ctx.fillText(`${label} HP ${fmt(s.hp)} · ${fmt(s.action,'')}`,Math.max(8,Math.min(w-190,x-75)),Math.max(18,y-44));
  }
  ctx.fillStyle='#91a0b5'; ctx.fillText(`frame ${fmt(frame?.frame,0)}`,16,20);
  $('frame-label').textContent=`frame ${fmt(frame?.frame,0)}`;
}

function renderBrain(target, summaryTarget, activity) {
  const root=$(target), summary=$(summaryTarget); root.innerHTML='';
  if(!activity){ summary.textContent='No connectome activity telemetry.'; return; }
  summary.textContent=`mean ${Number(activity.mean??0).toFixed(3)} · max ${Number(activity.max??0).toFixed(3)} · >0.75 ${((Number(activity.fraction_gt_0_75)||0)*100).toFixed(2)}%`;
  const rows=[];
  (activity.top_global||[]).slice(0,7).forEach(x=>rows.push({...x,kind:'whole'}));
  (activity.top_descending||[]).slice(0,5).forEach(x=>rows.push({...x,kind:'desc'}));
  rows.forEach(x=>{
    const row=document.createElement('div'); row.className='brain-row';
    const label=fmt(x.node_id,`index ${x.node_index}`);
    const value=Math.max(0,Math.min(1,Number(x.value)||0));
    row.innerHTML=`<div class="brain-label" title="${label}">${x.kind==='desc'?'D':'G'} · ${label}</div><div class="bar"><span style="width:${(value*100).toFixed(1)}%"></span></div><div>${value.toFixed(3)}</div>`;
    root.appendChild(row);
  });
}

function renderReplayIndex(index){
  const frames=replayState.frames, replay=replayState.replay;
  if(!frames.length) return;
  const i=Math.max(0,Math.min(frames.length-1,Number(index)||0));
  $('replay-slider').value=i;
  const frame=frames[i]; drawReplayFrame(frame,replay);
  renderBrain('brain-p1','brain-p1-summary',frame?.p1?.activity);
  renderBrain('brain-p2','brain-p2-summary',frame?.p2?.activity);
}

function stopReplay(){ if(replayState.timer){ clearInterval(replayState.timer); replayState.timer=null; } }
function playReplay(){
  stopReplay(); if(!replayState.frames.length) return;
  replayState.timer=setInterval(()=>{
    let next=Number($('replay-slider').value)+1;
    if(next>=replayState.frames.length) next=0;
    renderReplayIndex(next);
  },Number($('speed').value)||120);
}

async function loadReplay(url){
  stopReplay();
  if(!url){ $('replay-status').textContent='No evaluation replay yet.'; return; }
  try{
    const replay=await fetch(url,{cache:'no-store'}).then(r=>{if(!r.ok) throw new Error(`HTTP ${r.status}`); return r.json();});
    const frames=replay.frames||[]; if(!frames.length) throw new Error('replay has no frames');
    replayState={replay,frames,timer:null};
    const slider=$('replay-slider'); slider.max=frames.length-1; slider.value=0;
    $('brain-p1-title').textContent=`${replay.p1?.character||'P1'} brain`;
    $('brain-p2-title').textContent=`${replay.p2?.character||'P2'} brain`;
    $('replay-status').textContent=`${replay.p1?.character||'P1'} (${fmt(replay.p1?.checkpoint)}) vs ${replay.p2?.character||'P2'} (${fmt(replay.p2?.checkpoint)}) · winner: ${fmt(replay.result?.winner)}`;
    renderReplayIndex(0);
  }catch(err){ $('replay-status').textContent=`Replay unavailable: ${err.message}`; }
}

async function main(){
  try{
    const status=await fetch('./data/status.json',{cache:'no-store'}).then(r=>{if(!r.ok) throw new Error(`HTTP ${r.status}`); return r.json();});
    $('phase').textContent=fmt(status.phase);
    $('updated').textContent=fmt(status.updated_at,'not started');
    renderCharacters(status.characters||{}); drawHistory(status.characters||{});
    await loadReplay(status.latest_match?.replay_url||null);
  }catch(err){ $('phase').textContent='status load failed'; $('error').textContent=err.message; }
}

$('replay-slider').addEventListener('input',e=>{stopReplay(); renderReplayIndex(e.target.value);});
$('play').addEventListener('click',playReplay); $('pause').addEventListener('click',stopReplay);
$('speed').addEventListener('change',()=>{if(replayState.timer) playReplay();});
window.addEventListener('resize',()=>{if(replayState.frames.length) renderReplayIndex($('replay-slider').value);});
main();
