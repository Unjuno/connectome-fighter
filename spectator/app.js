const $ = (id) => document.getElementById(id);
const CHARACTERS = ['GARNET', 'ZEN', 'LUD', 'NEZ'];
const DATA_BASE = location.hostname.endsWith('github.io') ? '../data' : '/live-data';

const state = { queue: null, status: null, selectedClipId: null, followLatest: true, currentClip: null };
const esc = (value = '') => String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = (n, d) => d ? `${(100 * Number(n || 0) / Number(d)).toFixed(1)}%` : '0.0%';

function dateLabel(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' });
}

async function getJSON(path) {
  const response = await fetch(`${path}${path.includes('?') ? '&' : '?'}_=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function renderCards(stats = {}) {
  const root = $('cards'); root.innerHTML = '';
  for (const name of CHARACTERS) {
    const s = stats[name] || { rounds: 0, wins: 0, losses: 0, draws: 0 };
    const rounds = Number(s.rounds || 0), wins = Number(s.wins || 0), losses = Number(s.losses || 0), draws = Number(s.draws || 0);
    const el = document.createElement('div'); el.className = 'card';
    el.innerHTML = `<div class="name">${esc(name)}</div><div class="rate">${pct(wins, rounds)}</div><div class="small">W ${wins} · L ${losses} · D ${draws} · ${rounds} rounds</div>`;
    root.appendChild(el);
  }
}

function renderQueue() {
  const root = $('queue'); root.innerHTML = '';
  const clips = state.queue?.clips || [];
  if (!clips.length) { root.innerHTML = '<div class="muted">spectator queue is waiting for the first rendered simulation.</div>'; return; }
  clips.forEach((clip, index) => {
    const button = document.createElement('button');
    if (clip.clip_id === state.selectedClipId) button.classList.add('active');
    const slot = index === 0 ? 'NOW / latest' : `history -${index}`;
    button.innerHTML = `<div class="slot">${slot}</div><div class="pair">${esc(clip.p1?.character || 'P1')} vs ${esc(clip.p2?.character || 'P2')}</div><div class="stamp">${esc(dateLabel(clip.created_at))} · ${Number(clip.duration_seconds || 0).toFixed(0)} sec</div>`;
    button.onclick = () => { state.followLatest = index === 0; selectClip(clip.clip_id); };
    root.appendChild(button);
  });
}

function renderRounds(clip) {
  const root = $('rounds'); root.innerHTML = '';
  const rounds = clip?.outcomes?.rounds || [];
  if (!rounds.length) { root.innerHTML = '<span class="muted">round summary unavailable</span>'; return; }
  rounds.forEach((row, i) => {
    const pill = document.createElement('span'); pill.className = 'round-pill';
    const hp = Array.isArray(row.remaining_hps) ? row.remaining_hps.join('–') : JSON.stringify(row.remaining_hps ?? '—');
    const rewards = Array.isArray(row.rewards) ? row.rewards.join(' / ') : JSON.stringify(row.rewards ?? '—');
    pill.textContent = `R${row.round ?? (i + 1)} · HP ${hp} · reward ${rewards}`;
    root.appendChild(pill);
  });
}

function selectClip(clipId) {
  const clips = state.queue?.clips || [];
  const clip = clips.find((x) => x.clip_id === clipId) || clips[0]; if (!clip) return;
  const changed = state.currentClip?.clip_id !== clip.clip_id;
  state.selectedClipId = clip.clip_id; state.currentClip = clip;
  $('p1').textContent = clip.p1?.character || 'P1'; $('p2').textContent = clip.p2?.character || 'P2';
  $('duration').textContent = `${Number(clip.duration_seconds || 0).toFixed(1)} sec`; $('round-count').textContent = `${Number(clip.round_count || 0)} rounds`;
  $('brain-p1-title').textContent = `${clip.p1?.character || 'P1'} MaleCNS`; $('brain-p2-title').textContent = `${clip.p2?.character || 'P2'} MaleCNS`;
  renderRounds(clip); renderQueue();
  if (changed) {
    const raw = String(clip.video_url || ''); const player = $('fight');
    player.src = raw ? `${raw}${raw.includes('?') ? '&' : '?'}clip=${encodeURIComponent(clip.clip_id)}` : '';
    player.load(); player.play().catch(() => {});
  }
  renderBrainPanels();
}

function timelineAt(clip, side, timeSeconds) {
  const timeline = clip?.activity_timeline?.[side] || []; if (!timeline.length) return null;
  const t = Number(timeSeconds || 0); let best = timeline[0], dist = Math.abs(Number(best.t_seconds || 0) - t);
  for (let i = 1; i < timeline.length; i += 1) {
    const d = Math.abs(Number(timeline[i].t_seconds || 0) - t); if (d < dist) { best = timeline[i]; dist = d; }
  }
  return best;
}

function canvasContext(canvas) {
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const cssWidth = Math.max(300, Math.floor(canvas.clientWidth || 600));
  const cssHeight = Math.max(145, Math.floor(cssWidth / 2.1));
  const width = Math.floor(cssWidth * dpr), height = Math.floor(cssHeight * dpr);
  if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
  return { ctx: canvas.getContext('2d'), width, height, dpr };
}

function drawMorphology(side, clip, row) {
  const canvas = $(`brain-${side}-canvas`); if (!canvas) return;
  const { ctx, width, height, dpr } = canvasContext(canvas); ctx.clearRect(0, 0, width, height);
  const morphology = clip?.morphology || {}; const items = morphology?.sides?.[side] || []; const bounds = morphology?.bounds || null;
  ctx.fillStyle = 'rgba(225,235,247,.62)'; ctx.font = `${11 * dpr}px ui-monospace, SFMono-Regular, monospace`;
  if (!items.length || !bounds) {
    ctx.fillText('released morphology is not attached to this clip', 16 * dpr, 25 * dpr); return;
  }
  const pad = 18 * dpr;
  const xMin = Number(bounds.x_min), xMax = Number(bounds.x_max), zMin = Number(bounds.z_min), zMax = Number(bounds.z_max);
  const xSpan = Math.max(1, xMax - xMin), zSpan = Math.max(1, zMax - zMin);
  const xMap = (x) => pad + ((Number(x) - xMin) / xSpan) * (width - 2 * pad);
  const zMap = (z) => height - pad - ((Number(z) - zMin) / zSpan) * (height - 2 * pad);
  const active = new Map((row?.top_bodies || []).map((x) => [Number(x.body_id), Number(x.spikes || 0)]));
  const maxActive = Math.max(1, ...active.values());
  let activeDisplayed = 0;

  for (const item of items) {
    const bodyId = Number(item.body_id); const segments = item?.morphology?.segments || []; const spikes = active.get(bodyId) || 0;
    if (spikes > 0) activeDisplayed += 1;
    const power = spikes > 0 ? Math.min(1, spikes / maxActive) : 0;
    const alpha = spikes > 0 ? 0.42 + 0.55 * power : 0.10;
    const rgb = side === 'p1' ? '91,181,255' : '255,112,145';
    ctx.strokeStyle = `rgba(${rgb},${alpha})`; ctx.lineWidth = (spikes > 0 ? 1.35 + 1.2 * power : 0.55) * dpr; ctx.beginPath();
    for (const segment of segments) {
      if (!Array.isArray(segment) || segment.length < 4) continue;
      ctx.moveTo(xMap(segment[0]), zMap(segment[1])); ctx.lineTo(xMap(segment[2]), zMap(segment[3]));
    }
    ctx.stroke();
  }

  ctx.fillStyle = 'rgba(225,235,247,.72)';
  const coordinate = `${morphology.coordinate_space || 'MaleCNS EM'} · ${morphology.coordinate_units || '8 nm'} · X–Z`;
  ctx.fillText(coordinate, 14 * dpr, 20 * dpr);
  ctx.fillStyle = 'rgba(150,165,184,.76)';
  ctx.fillText(`${items.length} clip-active skeletons · ${activeDisplayed} highlighted now`, 14 * dpr, height - 11 * dpr);
}

function renderBrain(side, summary, clip) {
  const row = timelineAt(clip, side, $('fight').currentTime || 0); drawMorphology(side, clip, row);
  $(`brain-${side}-time`).textContent = row ? `t ${Number(row.t_seconds || 0).toFixed(1)}s` : 'clip summary';
  $(`brain-${side}-metrics`).innerHTML = row
    ? `<span>decision ${Number(row.decision_index) + 1}</span><span>${Number(row.total_spikes || 0).toLocaleString()} spikes</span><span>${Number(row.unique_bodies || 0).toLocaleString()} active bodies</span>`
    : `<span>${Number(summary?.total_spikes || 0).toLocaleString()} clip spikes</span><span>${Number(summary?.unique_bodies || 0).toLocaleString()} active bodies</span>`;
  const bars = $(`brain-${side}-bars`); bars.innerHTML = '';
  const visible = (row?.neuromeres || summary?.top_neuromeres || []).slice(0, 6); const total = visible.reduce((a, x) => a + Number(x.spikes || 0), 0);
  if (!visible.length) bars.innerHTML = '<div class="tiny">no annotated regional spikes in this window</div>';
  for (const item of visible) {
    const line = document.createElement('div'); line.className = 'bar-row'; const f = total ? Number(item.spikes || 0) / total : 0;
    line.innerHTML = `<div class="bar-label" title="${esc(item.name)}">${esc(item.name)}</div><div class="track"><div class="fill" style="width:${(100 * f).toFixed(2)}%"></div></div><div class="bar-value">${Number(item.spikes || 0)}</div>`;
    bars.appendChild(line);
  }
  const types = (row?.types || summary?.top_types || []).slice(0, 3).map((x) => `${x.name} (${x.spikes})`).join(' · ');
  const bodies = (row?.top_bodies || summary?.top_bodies || []).slice(0, 3).map((x) => `${x.body_id} (${x.spikes})`).join(' · ');
  $(`brain-${side}-summary`).innerHTML = `clip total: ${Number(summary?.total_spikes || 0).toLocaleString()} spikes / ${Number(summary?.unique_bodies || 0).toLocaleString()} bodies<br>active types: ${esc(types || '—')}<br>active body IDs: ${esc(bodies || '—')}`;
}

function renderBrainPanels() { const clip = state.currentClip; if (clip) { renderBrain('p1', clip.activity?.p1 || {}, clip); renderBrain('p2', clip.activity?.p2 || {}, clip); } }

function updateCountdown() {
  const target = state.queue?.next_expected_at ? new Date(state.queue.next_expected_at).getTime() : NaN;
  if (!Number.isFinite(target)) { $('countdown').textContent = '—'; return; }
  const diff = target - Date.now(); if (diff <= 0) { $('countdown').textContent = 'waiting for next run…'; return; }
  const sec = Math.floor(diff / 1000), h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  $('countdown').textContent = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function fallbackQueue(video) {
  const id = `legacy-${video?.source_actions_run || 'latest'}`;
  return { current_clip_id: id, clips: [{ clip_id:id, video_url:video?.asset_url || '', duration_seconds:video?.duration_seconds || 0, round_count:video?.rounds || 0, p1:video?.p1 || {}, p2:video?.p2 || {}, activity:{}, activity_timeline:{}, outcomes:{rounds:[]} }], poll_interval_seconds:30 };
}

async function refresh() {
  try {
    const statusPromise = getJSON(`${DATA_BASE}/status.json`); let queue;
    try { queue = await getJSON(`${DATA_BASE}/queue.json`); } catch (_) { queue = fallbackQueue(await getJSON(`${DATA_BASE}/video.json`)); }
    const status = await statusPromise; const oldLatest = state.queue?.current_clip_id; state.queue = queue; state.status = status;
    $('updated').textContent = `data updated ${dateLabel(status.updated_at)}`; $('phase').textContent = String(status.phase || '—').replaceAll('-', ' '); renderCards(status.metrics?.characters || {});
    const clips = queue.clips || [], latestId = queue.current_clip_id || clips[0]?.clip_id, exists = clips.some((x) => x.clip_id === state.selectedClipId);
    if (!state.selectedClipId || !exists || (state.followLatest && latestId !== oldLatest)) state.selectedClipId = latestId;
    selectClip(state.selectedClipId); const poll = Number(queue.poll_interval_seconds || 30); $('poll-note').textContent = `queue metadata is checked every ${poll}s; current clip swaps when a fresh simulation is published.`;
    $('error').textContent = ''; updateCountdown();
  } catch (error) { $('error').textContent = `update failed: ${error.message}`; }
}

$('fight').addEventListener('timeupdate', renderBrainPanels); $('fight').addEventListener('seeked', renderBrainPanels); $('fight').addEventListener('loadedmetadata', renderBrainPanels);
window.addEventListener('resize', renderBrainPanels);
refresh(); setInterval(refresh, 30000); setInterval(updateCountdown, 1000);
