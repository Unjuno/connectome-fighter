const $ = (id) => document.getElementById(id);
const CHARACTERS = ['GARNET', 'ZEN', 'LUD', 'NEZ'];

const state = {
  queue: null,
  status: null,
  selectedClipId: null,
  followLatest: true,
  currentClip: null,
};

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function pct(n, d) {
  return d ? `${(100 * Number(n || 0) / Number(d)).toFixed(1)}%` : '0.0%';
}

function dateLabel(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' });
}

async function getJSON(path) {
  const joiner = path.includes('?') ? '&' : '?';
  const response = await fetch(`${path}${joiner}_=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function renderCards(stats = {}) {
  const root = $('cards');
  root.innerHTML = '';
  for (const name of CHARACTERS) {
    const s = stats[name] || { rounds: 0, wins: 0, losses: 0, draws: 0 };
    const rounds = Number(s.rounds || 0);
    const wins = Number(s.wins || 0);
    const losses = Number(s.losses || 0);
    const draws = Number(s.draws || 0);
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `<div class="name">${esc(name)}</div><div class="rate">${pct(wins, rounds)}</div><div class="small">W ${wins} · L ${losses} · D ${draws} · ${rounds} rounds</div>`;
    root.appendChild(el);
  }
}

function queueLabel(index) {
  return index === 0 ? 'NOW / latest' : `history -${index}`;
}

function renderQueue() {
  const root = $('queue');
  root.innerHTML = '';
  const clips = state.queue?.clips || [];
  if (!clips.length) {
    root.innerHTML = '<div class="muted">spectator queue is waiting for the first rendered simulation.</div>';
    return;
  }
  clips.forEach((clip, index) => {
    const button = document.createElement('button');
    if (clip.clip_id === state.selectedClipId) button.classList.add('active');
    button.innerHTML = `<div class="slot">${esc(queueLabel(index))}</div><div class="pair">${esc(clip.p1?.character || 'P1')} vs ${esc(clip.p2?.character || 'P2')}</div><div class="stamp">${esc(dateLabel(clip.created_at))} · ${Number(clip.duration_seconds || 0).toFixed(0)} sec</div>`;
    button.addEventListener('click', () => {
      state.followLatest = index === 0;
      selectClip(clip.clip_id);
    });
    root.appendChild(button);
  });
}

function renderRounds(clip) {
  const root = $('rounds');
  root.innerHTML = '';
  const rounds = clip?.outcomes?.rounds || [];
  if (!rounds.length) {
    root.innerHTML = '<span class="muted">round summary unavailable</span>';
    return;
  }
  for (let i = 0; i < rounds.length; i += 1) {
    const row = rounds[i];
    const pill = document.createElement('span');
    pill.className = 'round-pill';
    const hp = Array.isArray(row.remaining_hps) ? row.remaining_hps.join('–') : JSON.stringify(row.remaining_hps ?? '—');
    const rewards = Array.isArray(row.rewards) ? row.rewards.join(' / ') : JSON.stringify(row.rewards ?? '—');
    pill.textContent = `R${row.round ?? (i + 1)} · HP ${hp} · reward ${rewards}`;
    root.appendChild(pill);
  }
}

function videoUrl(clip) {
  const raw = String(clip?.video_url || '');
  if (!raw) return '';
  return `${raw}${raw.includes('?') ? '&' : '?'}clip=${encodeURIComponent(clip.clip_id || Date.now())}`;
}

function selectClip(clipId) {
  const clips = state.queue?.clips || [];
  const clip = clips.find((x) => x.clip_id === clipId) || clips[0];
  if (!clip) return;
  const changed = state.currentClip?.clip_id !== clip.clip_id;
  state.selectedClipId = clip.clip_id;
  state.currentClip = clip;
  $('p1').textContent = clip.p1?.character || 'P1';
  $('p2').textContent = clip.p2?.character || 'P2';
  $('duration').textContent = `${Number(clip.duration_seconds || 0).toFixed(1)} sec`;
  $('round-count').textContent = `${Number(clip.round_count || 0)} rounds`;
  $('brain-p1-title').textContent = `${clip.p1?.character || 'P1'} MaleCNS`;
  $('brain-p2-title').textContent = `${clip.p2?.character || 'P2'} MaleCNS`;
  renderRounds(clip);
  renderQueue();
  if (changed) {
    const player = $('fight');
    player.src = videoUrl(clip);
    player.load();
    player.play().catch(() => {});
  }
  renderBrainPanels();
}

function currentTimelineRow(summary, clip, timeSeconds) {
  const timeline = summary?.timeline || [];
  if (!timeline.length) return null;
  const duration = Number(clip?.duration_seconds || $('fight').duration || timeline.length);
  const ratio = duration > 0 ? Math.max(0, Math.min(0.999999, Number(timeSeconds || 0) / duration)) : 0;
  const index = Math.min(timeline.length - 1, Math.floor(ratio * timeline.length));
  return timeline[index];
}

function renderBrain(side, summary, clip) {
  const player = $('fight');
  const row = currentTimelineRow(summary, clip, player.currentTime || 0);
  const actionEl = $(`brain-${side}-action`);
  const metricsEl = $(`brain-${side}-metrics`);
  const barsEl = $(`brain-${side}-bars`);
  const summaryEl = $(`brain-${side}-summary`);

  actionEl.textContent = row?.action || (summary?.timeline ? '—' : 'clip summary');
  metricsEl.innerHTML = row
    ? `<span>decision ${Number(row.decision_index) + 1}</span><span>${Number(row.total_spikes || 0).toLocaleString()} spikes</span><span>${Number(row.unique_bodies || 0).toLocaleString()} active bodies</span>`
    : `<span>${Number(summary?.total_spikes || 0).toLocaleString()} clip spikes</span><span>${Number(summary?.unique_bodies || 0).toLocaleString()} active bodies</span>`;

  barsEl.innerHTML = '';
  const regions = row?.regions || summary?.top_neuromeres || [];
  const visible = regions.slice(0, 6);
  const visibleTotal = visible.reduce((acc, item) => acc + Number(item.spikes || 0), 0);
  if (!visible.length) {
    barsEl.innerHTML = '<div class="tiny">no annotated regional spikes in this window</div>';
  } else {
    for (const item of visible) {
      const line = document.createElement('div');
      line.className = 'bar-row';
      const fallbackFraction = visibleTotal ? Number(item.spikes || 0) / visibleTotal : 0;
      const fraction = Math.max(0, Math.min(1, Number(item.fraction ?? fallbackFraction)));
      line.innerHTML = `<div class="bar-label" title="${esc(item.name)}">${esc(item.name)}</div><div class="track"><div class="fill" style="width:${(fraction * 100).toFixed(2)}%"></div></div><div class="bar-value">${Number(item.spikes || 0)}</div>`;
      barsEl.appendChild(line);
    }
  }

  const topTypes = (summary?.top_types || []).slice(0, 3).map((x) => `${x.name} (${x.spikes})`).join(' · ');
  const topBodies = (summary?.top_bodies || []).slice(0, 3).map((x) => `${x.body_id} (${x.spikes})`).join(' · ');
  summaryEl.innerHTML = `clip total: ${Number(summary?.total_spikes || 0).toLocaleString()} spikes / ${Number(summary?.unique_bodies || 0).toLocaleString()} bodies<br>top types: ${esc(topTypes || '—')}<br>top body IDs: ${esc(topBodies || '—')}`;
}

function renderBrainPanels() {
  const clip = state.currentClip;
  if (!clip) return;
  renderBrain('p1', clip.activity?.p1 || {}, clip);
  renderBrain('p2', clip.activity?.p2 || {}, clip);
}

function updateCountdown() {
  const value = state.queue?.next_expected_at;
  const target = value ? new Date(value).getTime() : NaN;
  if (!Number.isFinite(target)) {
    $('countdown').textContent = '—';
    return;
  }
  const diff = target - Date.now();
  if (diff <= 0) {
    $('countdown').textContent = 'waiting for next run…';
    return;
  }
  const seconds = Math.floor(diff / 1000);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  $('countdown').textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function fallbackQueue(video) {
  if (!video || (!video.asset_url && !video.p1)) return { clips: [], poll_interval_seconds: 30 };
  const id = `legacy-${video.source_actions_run || 'latest'}`;
  return {
    schema_version: 0,
    mode: 'legacy-single-video',
    poll_interval_seconds: 30,
    next_expected_at: null,
    current_clip_id: id,
    clips: [{
      clip_id: id,
      created_at: null,
      video_url: video.asset_url || '/live-data/latest-fight.mp4',
      duration_seconds: video.duration_seconds || 0,
      round_count: video.rounds || 0,
      p1: video.p1 || { character: 'P1' },
      p2: video.p2 || { character: 'P2' },
      activity: {},
      outcomes: { rounds: [] },
    }],
  };
}

async function refresh() {
  try {
    const statusPromise = getJSON('/live-data/status.json');
    let queue;
    try {
      queue = await getJSON('/live-data/queue.json');
    } catch (_) {
      queue = fallbackQueue(await getJSON('/live-data/video.json'));
    }
    const status = await statusPromise;
    const oldLatest = state.queue?.current_clip_id;
    state.queue = queue;
    state.status = status;
    $('updated').textContent = `data updated ${dateLabel(status.updated_at)}`;
    $('phase').textContent = String(status.phase || '—').replaceAll('-', ' ');
    renderCards(status.metrics?.characters || {});

    const clips = queue.clips || [];
    const latestId = queue.current_clip_id || clips[0]?.clip_id;
    const selectionStillExists = clips.some((x) => x.clip_id === state.selectedClipId);
    if (!state.selectedClipId || !selectionStillExists || (state.followLatest && latestId !== oldLatest)) {
      state.selectedClipId = latestId;
    }
    selectClip(state.selectedClipId);
    const poll = Number(queue.poll_interval_seconds || 30);
    $('poll-note').textContent = `queue metadata is checked every ${poll}s; the current clip swaps when a fresh rendered simulation is published.`;
    $('error').textContent = '';
    updateCountdown();
  } catch (error) {
    $('error').textContent = `update failed: ${error.message}`;
  }
}

$('fight').addEventListener('timeupdate', renderBrainPanels);
$('fight').addEventListener('seeked', renderBrainPanels);
$('fight').addEventListener('loadedmetadata', renderBrainPanels);

refresh();
setInterval(refresh, 30000);
setInterval(updateCountdown, 1000);
