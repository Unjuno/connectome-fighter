const $ = (id) => document.getElementById(id);

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function pct(value) {
  return `${(100 * Number(value || 0)).toFixed(1)}%`;
}

function dateLabel(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' });
}

function renderCharacters(stats = {}) {
  const root = $('characters');
  root.innerHTML = '';
  for (const name of ['GARNET', 'ZEN', 'LUD', 'NEZ']) {
    const s = stats[name] || { rounds: 0, wins: 0, losses: 0, draws: 0, win_rate: 0 };
    const tr = document.createElement('tr');
    tr.innerHTML = `<td><strong>${name}</strong></td><td>${s.rounds}</td><td>${s.wins}</td><td>${s.losses}</td><td>${s.draws}</td><td>${pct(s.win_rate)}</td>`;
    root.appendChild(tr);
  }
}

function renderMatches(matches = []) {
  const root = $('matches');
  root.innerHTML = '';
  if (!matches.length) {
    root.textContent = 'まだ正規化された対戦ログがありません。';
    return;
  }
  for (const match of [...matches].reverse().slice(0, 50)) {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.innerHTML = `<strong>${esc(match.p1.character)} vs ${esc(match.p2.character)}</strong> · round ${match.round} · HP ${match.p1.final_hp}-${match.p2.final_hp} · ${esc(match.winner)}`;
    details.appendChild(summary);
    const body = document.createElement('div');
    body.className = 'muted';
    body.style.padding = '8px 0 0';
    body.innerHTML = [
      `recorded: ${esc(dateLabel(match.recorded_at))}`,
      `run: ${esc(match.run_id)}`,
      `seed: ${match.p1.seed} / ${match.p2.seed}`,
      `damage: ${match.p1.damage_dealt_hp} / ${match.p2.damage_dealt_hp}`,
      `min distance: ${match.min_distance_px == null ? '—' : Number(match.min_distance_px).toFixed(1) + ' px'}`,
    ].join('<br>');
    if (match.source_run_url) {
      body.innerHTML += `<br><a href="${esc(match.source_run_url)}">source Actions run</a>`;
    }
    details.appendChild(body);
    root.appendChild(details);
  }
}

async function load() {
  try {
    const [statusRes, matchRes] = await Promise.all([
      fetch('./data/status.json', { cache: 'no-store' }),
      fetch('./data/matches.json', { cache: 'no-store' }),
    ]);
    const status = statusRes.ok ? await statusRes.json() : {};
    const log = matchRes.ok ? await matchRes.json() : { matches: [], character_stats: {}, match_count: 0 };
    $('match-count').textContent = log.match_count ?? 0;
    $('updated').textContent = dateLabel(log.updated_at || status.updated_at);
    $('phase').textContent = status.phase || '—';
    renderCharacters(log.character_stats || {});
    renderMatches(log.matches || []);
  } catch (error) {
    $('error').textContent = `load failed: ${error.message}`;
  }
}

load();
