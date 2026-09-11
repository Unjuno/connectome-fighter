const $ = (id) => document.getElementById(id);

function fmt(v, fallback = '—') {
  return v === null || v === undefined ? fallback : String(v);
}

function pct(v) {
  return v === null || v === undefined ? '—' : `${(Number(v) * 100).toFixed(1)}%`;
}

function drawHistory(history) {
  const canvas = $('history');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || 800;
  const h = canvas.clientHeight || 220;
  canvas.width = Math.floor(w * dpr);
  canvas.height = Math.floor(h * dpr);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = '#273242';
  ctx.strokeRect(0.5, 0.5, w - 1, h - 1);
  if (!history || history.length < 2) {
    ctx.fillStyle = '#91a0b5';
    ctx.font = '14px system-ui';
    ctx.fillText('No learning history yet.', 18, 32);
    return;
  }
  const points = history.filter(x => Number.isFinite(Number(x.elo)));
  if (points.length < 2) return;
  const ys = points.map(x => Number(x.elo));
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const span = Math.max(1, maxY - minY);
  ctx.strokeStyle = '#8ecbff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((p, i) => {
    const x = 16 + i * (w - 32) / (points.length - 1);
    const y = h - 16 - (Number(p.elo) - minY) / span * (h - 32);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawReplayFrame(ctx, w, h, frame, replay) {
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#0f1720';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = '#3c4b60';
  ctx.beginPath();
  ctx.moveTo(20, h - 36); ctx.lineTo(w - 20, h - 36); ctx.stroke();

  const xs = [frame?.p1?.x, frame?.p2?.x].filter(Number.isFinite);
  const minX = xs.length ? Math.min(...xs, -960) : -960;
  const maxX = xs.length ? Math.max(...xs, 960) : 960;
  const span = Math.max(1, maxX - minX);
  const mapX = x => 30 + ((Number(x || 0) - minX) / span) * (w - 60);

  const fighters = [
    {k:'p1', fill:'#8ecbff', label: replay?.p1?.label || 'P1'},
    {k:'p2', fill:'#ff9f8e', label: replay?.p2?.label || 'P2'},
  ];
  for (const f of fighters) {
    const s = frame?.[f.k] || {};
    const x = mapX(s.x);
    const y = h - 70 - Math.max(0, Number(s.y || 0)) * 0.15;
    ctx.fillStyle = f.fill;
    ctx.fillRect(x - 12, y - 32, 24, 32);
    ctx.fillStyle = '#e7edf5';
    ctx.font = '12px system-ui';
    ctx.fillText(`${f.label} · HP ${fmt(s.hp)} · ${fmt(s.action, '')}`, Math.max(8, x - 70), y - 42);
  }
  ctx.fillStyle = '#91a0b5';
  ctx.fillText(`frame ${fmt(frame?.frame, 0)}`, 16, 20);
}

async function loadReplay(url) {
  if (!url) {
    $('replay-status').textContent = 'No evaluation replay yet.';
    return;
  }
  try {
    const replay = await fetch(url, {cache:'no-store'}).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
    const frames = replay.frames || [];
    if (!frames.length) throw new Error('replay has no frames');
    const canvas = $('replay');
    const slider = $('replay-slider');
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 800;
    const h = canvas.clientHeight || 300;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    ctx.scale(dpr, dpr);
    slider.max = frames.length - 1;
    slider.value = 0;
    const render = () => drawReplayFrame(ctx, w, h, frames[Number(slider.value)], replay);
    slider.addEventListener('input', render);
    $('replay-status').textContent = `${replay.p1?.label || 'P1'} vs ${replay.p2?.label || 'P2'} · ${fmt(replay.result?.winner, 'result pending')}`;
    render();
  } catch (err) {
    $('replay-status').textContent = `Replay unavailable: ${err.message}`;
  }
}

async function main() {
  try {
    const status = await fetch('./data/status.json', {cache:'no-store'}).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
    $('phase').textContent = fmt(status.phase);
    $('generation').textContent = fmt(status.generation, '0');
    $('matches').textContent = fmt(status.training_matches, '0');
    $('checkpoint').textContent = fmt(status.checkpoint_id);
    $('champion').textContent = fmt(status.champion_id);
    $('elo').textContent = fmt(status.elo);
    $('baseline').textContent = pct(status.fixed_baseline_win_rate);
    $('updated').textContent = fmt(status.updated_at, 'not started');
    drawHistory(status.history || []);
    await loadReplay(status.latest_match?.replay_url || null);
  } catch (err) {
    $('phase').textContent = 'status load failed';
    $('error').textContent = err.message;
  }
}

window.addEventListener('resize', () => main());
main();
