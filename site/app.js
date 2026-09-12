const $ = (id) => document.getElementById(id);

function esc(value = '') {
  return String(value).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
}

function pct(value) {
  return `${(100 * Number(value || 0)).toFixed(1)}%`;
}

function num(value, digits = 2) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits).replace(/\.00$/, '') : '—';
}

function dateLabel(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString('en-US', { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'medium' });
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
    root.textContent = 'No normalized match records are available yet.';
    return;
  }
  for (const match of [...matches].reverse().slice(0, 36)) {
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
    if (match.source_run_url) body.innerHTML += `<br><a href="${esc(match.source_run_url)}">source Actions run ↗</a>`;
    details.appendChild(body);
    root.appendChild(details);
  }
}

function renderReward(cfg = {}) {
  const terminal = cfg.terminal || {};
  const damage = cfg.damage || {};
  const engagement = cfg.engagement_potential || {};
  $('reward-id').textContent = cfg.id || '—';
  $('reward-win').textContent = num(terminal.win);
  $('reward-loss').textContent = num(terminal.loss);
  $('reward-draw').textContent = num(terminal.ordinary_draw);
  $('reward-nodamage').textContent = num(terminal.no_damage_draw_penalty);
  $('damage-formula').textContent = [
    damage.formula || '—',
    `unit_hp = ${damage.unit_hp ?? '—'}`,
    `weight_per_unit = ${damage.weight_per_unit ?? '—'}`,
  ].join('\n');
  $('engagement-formula').textContent = engagement.enabled ? [
    engagement.phi || '—',
    engagement.local_reward || '—',
    `contact_band_px = ${engagement.contact_band_px ?? '—'}`,
    `weight = ${engagement.weight ?? '—'}`,
  ].join('\n') : 'disabled';
  $('reward-boundary').textContent = cfg.interpretation_boundary || '—';

  const fixed = $('fixed-controls');
  fixed.innerHTML = '';
  const controls = cfg.fixed_during_comparison || {};
  for (const [key, value] of Object.entries(controls)) {
    const div = document.createElement('div');
    div.innerHTML = `<strong>${esc(key.replaceAll('_', ' '))}</strong><br><span class="muted">${esc(String(value))}</span>`;
    fixed.appendChild(div);
  }
}

function renderPlasticity(cfg = {}) {
  $('plasticity-id').textContent = cfg.id || '—';
  $('plasticity-status').textContent = cfg.status || '—';
  $('plasticity-lr').textContent = num(cfg.learning_rate_per_unit_modulatory_signal, 3);
  $('plasticity-decay').textContent = num(cfg.eligibility_decay_per_decision, 3);
  $('plasticity-detail').textContent = [
    `update_direction = ${cfg.update_direction ?? '—'}`,
    `positive_signal_target = ${cfg.positive_signal_target ?? '—'}`,
    `negative_signal_target = ${cfg.negative_signal_target ?? '—'}`,
    `pair_count_cap = ${cfg.pair_count_cap ?? '—'}`,
    `normalization_percentile = ${cfg.normalization_percentile ?? '—'}`,
    `multiplier range = ${cfg.multiplier_min ?? '—'} .. ${cfg.multiplier_max ?? '—'}`,
    `reward_config = ${cfg.reward_config ?? '—'}`,
  ].join('\n');
  $('plasticity-boundary').textContent = cfg.interpretation_boundary || '—';
}

function renderRuntimeProof(proof = {}) {
  const telemetry = proof.proof_telemetry || {};
  if ($('proof-verified-at')) $('proof-verified-at').textContent = `Verified ${dateLabel(proof.verified_at)}`;
  if ($('proof-run')) {
    $('proof-run').href = proof.precompile_e2e_run ? `https://github.com/Unjuno/connectome-fighter/actions/runs/${proof.precompile_e2e_run}` : '#';
  }
  if ($('proof-runtime')) {
    $('proof-runtime').textContent = [
      `proof runtime archive SHA-256: ${proof.runtime_archive_sha256 ?? '—'}`,
      `runtime base: ${proof.runtime_base ?? '—'}`,
      `snapshot: ${proof.runtime_snapshot_id ?? '—'}`,
      `observed proof telemetry: round ${telemetry.round ?? '—'} · frame ${telemetry.frame ?? '—'} · GARNET decision ${telemetry.p1_decision_index ?? '—'} / ZEN decision ${telemetry.p2_decision_index ?? '—'} · P1 spikes ${telemetry.p1_total_spikes ?? '—'} / P2 spikes ${telemetry.p2_total_spikes ?? '—'}`,
      `public broadcast target: ${proof.broadcast_target ?? '—'}`,
      `learning_enabled=${proof.learning_enabled ?? '—'} · policy_pixel_access=${proof.policy_pixel_access ?? '—'}`,
    ].join('\n');
  }
  if ($('proof-cache')) $('proof-cache').textContent = `verified · ${proof.shared_object_count ?? '—'} shared objects`;
  if ($('proof-model-size')) $('proof-model-size').textContent = `${Number(proof.neurons || 0).toLocaleString()} neurons / ${Number(proof.recurrent_synapses || 0).toLocaleString()} synapses`;
  if ($('proof-runtime-json')) $('proof-runtime-json').href = './data/runtime-proof.json';
}

function renderCandidateTraining(training = {}) {
  let panel = $('candidate-learning');
  if (!panel) {
    panel = document.createElement('section');
    panel.id = 'candidate-learning';
    panel.className = 'panel';
    const lineage = $('lineage');
    if (lineage) lineage.insertAdjacentElement('afterend', panel);
  }

  const generation = Number(training.generation);
  if (!Number.isFinite(generation)) {
    panel.innerHTML = `
      <div class="section-title"><div><div class="eyebrow">background candidate learning</div><h2>Rolling GitHub training lane</h2></div><span class="muted">initializing</span></div>
      <div class="notice"><strong>LIVE remains unchanged.</strong> The candidate-learning lane has not published its first rolling checkpoint yet. Vercel continues to serve only the separately approved inference state.</div>`;
    return;
  }

  const update = training.update_summary || {};
  const signals = training.signal_summary || {};
  const stateSha = String(training.state_sha256 || '—');
  const shortSha = stateSha.length > 20 ? `${stateSha.slice(0, 16)}…${stateSha.slice(-8)}` : stateSha;
  const sourceUrl = training.source_run_url ? esc(training.source_run_url) : '#';
  const changed = Number(update.changed_edges || 0).toLocaleString();
  const generationLabel = Number.isFinite(generation) ? generation.toLocaleString() : '—';
  const matches = Number(training.matches || 0).toLocaleString();
  const signalSum = num(signals.sum, 4);

  panel.innerHTML = `
    <div class="section-title">
      <div><div class="eyebrow">background candidate learning</div><h2>GitHub single-writer candidate checkpoint</h2></div>
      <a class="muted" href="${sourceUrl}">latest training run ↗</a>
    </div>
    <div class="proof"><span class="statusline"><span class="dot live"></span><strong>Learning lane active:</strong></span> GARNET candidate generation ${generationLabel} is advancing on GitHub. It is <strong>not</strong> the state currently served by Vercel and is never auto-promoted to the public fight.</div>
    <div class="grid" style="margin:12px 0 0">
      <div class="card"><div class="label">candidate generation</div><div class="value">${generationLabel}</div></div>
      <div class="card"><div class="label">candidate matches</div><div class="value">${matches}</div></div>
      <div class="card"><div class="label">latest opponent</div><div class="value small">${esc(training.opponent || '—')}</div></div>
      <div class="card"><div class="label">changed KC→MBON edges</div><div class="value">${changed}</div></div>
      <div class="card"><div class="label">modulatory signal sum</div><div class="value">${signalSum}</div></div>
    </div>
    <div class="formula">status: ${esc(training.status || 'candidate-only-not-arena-approved')}
reward: ${esc(training.reward_id || '—')}
state SHA-256: ${esc(stateSha)}
state id: ${esc(shortSha)}
served_by_vercel=${String(training.served_by_vercel === true)} · auto_promotion=${String(training.auto_promotion === true)}</div>
    <p class="boundary">${esc(training.interpretation_boundary || 'This is project-defined game learning over the versioned candidate plasticity contract. Candidate progression is evidence of the implemented learning rule, not evidence of biological reinforcement semantics or improved fighting performance.')}</p>
    <div class="actions"><a class="btn" href="https://github.com/Unjuno/connectome-fighter/releases/tag/canonical-training-latest">rolling candidate checkpoint ↗</a><a class="btn" href="./data/training-status.json">training status JSON ↗</a></div>`;
}

async function json(url, fallback) {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) return fallback;
  return response.json();
}

async function load() {
  try {
    const [status, log, reward, plasticity, runtimeProof, trainingStatus] = await Promise.all([
      json('./data/status.json', {}),
      json('./data/matches.json', { matches: [], character_stats: {}, match_count: 0 }),
      json('./research-data/reward.json', {}),
      json('./research-data/plasticity.json', {}),
      json('./data/runtime-proof.json', {}),
      json('./data/training-status.json', {}),
    ]);

    $('match-count').textContent = log.match_count ?? 0;
    $('updated').textContent = `updated ${dateLabel(log.updated_at || status.updated_at)}`;
    const dataPhase = status.phase || reward.status || 'unknown-data-phase';
    $('phase').textContent = `Public Surface Freeze · data: ${dataPhase}`;
    $('phase').title = `Project gate: Public Surface Freeze; latest baseline data phase: ${dataPhase}`;
    renderCharacters(log.character_stats || status.character_stats || {});
    renderMatches(log.matches || []);
    renderReward(reward);
    renderPlasticity(plasticity);
    renderRuntimeProof(runtimeProof);
    renderCandidateTraining(trainingStatus);
  } catch (error) {
    $('error').textContent = `load failed: ${error.message}`;
  }
}

load();
