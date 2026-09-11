const $=id=>document.getElementById(id);
let lastVideoRun=null;
const CHARACTERS=['GARNET','ZEN','LUD','NEZ'];
function pct(n,d){return d?`${(100*n/d).toFixed(1)}%`:'0.0%'}
async function getJSON(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json()}
function renderCards(stats={}){
  const root=$('cards');root.innerHTML='';
  for(const name of CHARACTERS){
    const s=stats[name]||{rounds:0,wins:0,losses:0,draws:0};
    const el=document.createElement('div');el.className='card';
    el.innerHTML=`<div class="name">${name}</div><div class="rate">${pct(Number(s.wins||0),Number(s.rounds||0))}</div><div class="small">W ${s.wins||0} · L ${s.losses||0} · D ${s.draws||0} · ${s.rounds||0} rounds</div>`;
    root.appendChild(el);
  }
}
async function refresh(){
  try{
    const [status,video]=await Promise.all([getJSON('/live-data/status.json'),getJSON('/live-data/video.json')]);
    $('updated').textContent=`updated ${status.updated_at||'—'}`;
    $('phase').textContent=String(status.phase||'—').replaceAll('-',' ');
    $('p1').textContent=video.p1?.character||'P1';$('p2').textContent=video.p2?.character||'P2';
    $('duration').textContent=`${Number(video.duration_seconds||0).toFixed(1)} sec`;
    $('rounds').textContent=`${video.rounds||1} rounds`;
    renderCards(status.metrics?.characters||{});
    const run=String(video.source_actions_run||'');
    if(run && run!==lastVideoRun){
      lastVideoRun=run;
      const player=$('fight'),src=$('fight-source');
      src.src=`/live-data/latest-fight.mp4?v=${encodeURIComponent(run)}`;
      player.load();
      player.play().catch(()=>{});
    }
    $('error').textContent='';
  }catch(err){$('error').textContent=`update failed: ${err.message}`}
}
refresh();setInterval(refresh,15000);
