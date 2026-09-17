"use client";

import { useEffect, useState } from 'react';
import { Observatory, metric, stamp } from './observatory';

type Json = Record<string, any>;
type Envelope = { latest?: Json | null; previous?: Json | null; training?: Json | null };
type ResearchEnvelope = { ready?: boolean; research?: Json | null };

function videoUrl(evaluation: Json | null) {
  const raw = evaluation?.video?.asset_url;
  if (typeof raw !== 'string') return null;
  try {
    const url = new URL(raw);
    if (url.protocol !== 'https:') return null;
    url.searchParams.set('v', String(evaluation?.state_sha256 || evaluation?.generation || 'recording'));
    return url.toString();
  } catch { return null; }
}

function completed(value: unknown): value is Json {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const row = value as Json;
  return row.status === 'COMPLETED' && row.candidate_only === true && row.auto_promotion === false && row.policy_pixel_access === false;
}

function signed(value: unknown, digits = 0) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  const rendered = metric(Math.abs(value), digits);
  return value > 0 ? `+${rendered}` : value < 0 ? `-${rendered}` : rendered;
}

export function LiveClient() {
  const [data, setData] = useState<Envelope | null>(null);
  const [researchData, setResearchData] = useState<ResearchEnvelope | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [previous, setPrevious] = useState(false);
  const [paused, setPaused] = useState(false);
  const [videoError, setVideoError] = useState(false);

  useEffect(() => {
    if (paused) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const response = await fetch('/api/evaluation', { cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const body = await response.json();
        if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('Invalid evaluation response');
        if (!stopped) { setData(body); setError(null); }
      } catch (reason) {
        if (!stopped) setError(reason instanceof Error ? reason.message : 'Evaluation data unavailable');
      }

      try {
        const response = await fetch('/api/research-status', { cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)]) });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const body = await response.json();
        if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('Invalid research status response');
        if (!stopped) { setResearchData(body); setResearchError(null); }
      } catch (reason) {
        if (!stopped) setResearchError(reason instanceof Error ? reason.message : 'Research status unavailable');
      } finally {
        if (!stopped) timer = setTimeout(poll, 30_000);
      }
    };
    void poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [paused]);

  const latest = completed(data?.latest) ? data!.latest! : null;
  const older = completed(data?.previous) ? data!.previous! : null;
  const selected = previous && older ? older : latest;
  const training = data?.training;
  const research = researchData?.ready === true ? researchData.research : null;
  const control = research?.control_contract;
  const holdout = research?.heldout_readout;
  const search = research?.paired_search;
  const gate = training?.acceptance_gate;
  const liveCompute = research?.live_compute_snapshot;
  const video = videoUrl(selected);
  useEffect(() => setVideoError(false), [video]);
  const behind = typeof training?.generation === 'number' && typeof latest?.generation === 'number' && training.generation > latest.generation;
  const result = selected?.result;
  const verdict = result?.winner === 'DRAW' ? 'DRAW' : typeof result?.winner === 'string' ? `${result.winner} WINS` : 'Result not recorded';

  const media = <>
    <div className="ob-match"><strong className="p1">{selected?.character || 'GARNET'}</strong><span>VS</span><strong className="p2">{selected?.opponent || 'ZEN'}</strong></div>
    <div className="ob-score"><span>GEN {metric(selected?.generation)}</span><span>FIXED-CONDITION EVALUATION</span><span>1 ROUND</span></div>
    <div className="ob-screen">{video && !videoError ? <video key={video} data-testid="evaluation-video" src={video} controls muted playsInline preload="metadata" onError={() => setVideoError(true)} aria-label={`Generation ${selected?.generation} recorded evaluation`} /> : <div className="ob-empty"><span className="ob-crosshair" aria-hidden="true">+</span><strong>{videoError ? 'Video could not be loaded' : 'Awaiting an evaluation video'}</strong><p>{videoError ? 'Check the connection to the published asset.' : 'A completed evaluation will appear here after publication.'}</p>{videoError ? <button type="button" className="ob-button" onClick={() => setVideoError(false)}>Reload video</button> : null}</div>}</div>
    <div className="ob-result"><div><span className="ob-kicker">FINAL RESULT</span><strong>{verdict}</strong></div><div><span className="p1">HP {metric(result?.p1_hp)}</span><i> / </i><span className="p2">{metric(result?.p2_hp)}</span><small>{result?.ended_by || '—'} · game {metric(result?.elapsed_seconds, 1)} s</small></div></div>
    <p className="ob-caption">Generation {metric(selected?.generation)} · {stamp(selected?.evaluated_at)} · video {metric(selected?.video?.duration_seconds, 1)} s<br />HP values describe the final recorded result, not the current playback frame.</p>
    <div className="ob-model-switch" role="group" aria-label="Select evaluation generation"><button className="ob-button" type="button" aria-pressed={!previous || !older} onClick={() => setPrevious(false)}>Latest completed Gen {metric(latest?.generation)}</button><button className="ob-button" type="button" aria-pressed={previous && Boolean(older)} disabled={!older} onClick={() => setPrevious(true)}>Previous Gen {metric(older?.generation)}</button></div>
  </>;

  return <Observatory mode="replay" status="recorded-evaluation" media={media} controls={<><button className="ob-button" type="button" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? 'Resume history updates' : 'Pause history updates'}</button><a className="ob-button ob-button-primary" href="/live">Observe LIVE ↗</a></>}>
    {error ? <p className="ob-notice" role="status">Evaluation API unavailable: {error}. Any displayed records are from the last successful fetch.</p> : null}
    {researchError ? <p className="ob-notice" role="status">Research status API unavailable: {researchError}. Evaluation records remain independent.</p> : null}
    {paused ? <p className="ob-notice" role="status">History updates are paused. Use the video player controls to play or pause the recording.</p> : null}
    {behind ? <p className="ob-notice">Candidate is now Gen {metric(training?.generation)}. The latest completed evaluation shown here is Gen {metric(latest?.generation)}. Completion of the newer evaluation has not yet been verified.</p> : null}

    <section id="research" className="ob-evolution">
      <div className="ob-section-title"><div><span className="ob-kicker">03 / ACTIVE RESEARCH STATUS</span><h2>What changed, what passed, what was rejected.</h2></div><span className="ob-tag">experimental · candidate only</span></div>
      {liveCompute?.status === 'capacity-blocked' ? <p className="ob-notice">LIVE compute snapshot: Vercel Sandbox is capacity-blocked until {stamp(liveCompute?.blocked_until)}. Recorded evaluations and research evidence remain available. This operational state is separate from model performance.</p> : null}
      <div className="ob-history-grid">
        <article className="ob-panel ob-history-card">
          <span className="ob-step-number">A</span><span className="ob-kicker">CONTROL CONTRACT</span><h3>{control?.readout_mode || '—'}</h3><p>Project-defined temporal neural readout for candidate-training experiments.</p>
          <div className="ob-data-pair"><span>Decision interval</span><strong>{metric(control?.decision_interval_frames)} frames</strong></div>
          <div className="ob-data-pair"><span>Neural window</span><strong>{metric(control?.neural_window_ms)} ms</strong></div>
          <div className="ob-data-pair"><span>Game state used by readout</span><strong>{control?.readout_game_state_used === false ? 'NO' : '—'}</strong></div>
          <small>{control?.readout_contract || 'Not recorded'}</small>
        </article>
        <article className="ob-panel ob-history-card">
          <span className="ob-step-number">B</span><span className="ob-kicker">HELD-OUT READOUT CHECK</span><h3>{metric(holdout?.improved_pairs)}/{metric(holdout?.seed_pairs)} improved</h3><p>Canonical and EMA-residual used the same checkpoint under held-out seed pairs.</p>
          <div className="ob-data-pair"><span>Damage dealt</span><strong>{metric(holdout?.canonical_damage_dealt_hp_total)} → {metric(holdout?.ema_damage_dealt_hp_total)} HP</strong></div>
          <div className="ob-data-pair"><span>Aggregate net HP</span><strong>{signed(holdout?.canonical_aggregate_net_hp)} → {signed(holdout?.ema_aggregate_net_hp)}</strong></div>
          <small>One held-out pair worsened · no general strength claim</small>
        </article>
        <article className="ob-panel ob-history-card">
          <span className="ob-step-number">C</span><span className="ob-kicker">SCHEDULED UPDATE GATE</span><h3>{gate?.accepted_update === true ? 'UPDATE ACCEPTED' : gate?.accepted_update === false ? 'UPDATE REJECTED' : 'NOT YET RECORDED'}</h3><p>{gate?.reason || 'Published candidates before this gate do not have a paired acceptance record.'}</p>
          <div className="ob-data-pair"><span>Paired utility</span><strong>{metric(gate?.before_utility, 5)} → {metric(gate?.after_utility, 5)}</strong></div>
          <div className="ob-data-pair"><span>Utility delta</span><strong>{signed(gate?.utility_delta, 5)}</strong></div>
          <div className="ob-data-pair"><span>Parent → candidate</span><strong>Gen {metric(gate?.parent_generation)} → {metric(gate?.proposed_generation)}</strong></div>
          <div className="ob-data-pair"><span>Changed connections</span><strong>{metric(training?.update_summary?.changed_edges)}</strong></div>
          <small>Same-seed frozen evaluation · publication requires strict improvement</small>
        </article>
      </div>
      <details className="ob-evaluation-details"><summary>Inspect current gate and earlier search evidence</summary>
        <p>Readout: <code>{control?.readout_contract || training?.readout_contract || 'Not recorded'}</code> · mode <code>{training?.readout_mode || control?.readout_mode || 'Not recorded'}</code> · policy_pixel_access=false</p>
        <p>Current scheduled gate: utility {metric(gate?.before_utility, 5)} → {metric(gate?.after_utility, 5)} ({signed(gate?.utility_delta, 5)}). Protocol: <code>{gate?.protocol || 'Not recorded'}</code>.</p>
        {typeof training?.source_run_url === 'string' ? <p><a href={training.source_run_url}>Open current candidate Actions run ↗</a></p> : null}
        <p>Earlier paired-search pilot, parent: dealt {metric(search?.combat_before?.damage_dealt_hp)} HP / took {metric(search?.combat_before?.damage_taken_hp)} HP / score {metric(search?.combat_before?.score, 5)}.<br />Proposal: dealt {metric(search?.combat_proposal?.damage_dealt_hp)} HP / took {metric(search?.combat_proposal?.damage_taken_hp)} HP / score {metric(search?.combat_proposal?.score, 5)}.</p>
        <p>Earlier pilot accepted update: {search?.accepted_update === true ? 'YES' : search?.accepted_update === false ? 'NO' : '—'}. Reward coefficients changed in that experiment: {search?.reward_coefficients_changed === false ? 'NO' : '—'}.</p>
        {typeof search?.source_run_url === 'string' ? <p><a href={search.source_run_url}>Open earlier paired-search Actions run ↗</a></p> : null}
        <p>{search?.interpretation || 'Earlier paired-search evidence is not available.'}</p>
      </details>
    </section>

    <section id="evolution" className="ob-evolution">
      <div className="ob-section-title"><div><span className="ob-kicker">04 / RESEARCH TIMELINE</span><h2>Current behavior. Recorded progress.</h2></div><span className="ob-tag">candidate only · no automatic promotion</span></div>
      <div className="ob-history-grid">
        <article className="ob-panel ob-history-card"><span className="ob-step-number">01</span><span className="ob-kicker">CANDIDATE UPDATE</span><h3>Gen {metric(training?.generation)}</h3><p>Research checkpoint update</p><div className="ob-data-pair"><span>Completed matches</span><strong>{metric(training?.matches)}</strong></div><div className="ob-data-pair"><span>Changed connections</span><strong>{metric(training?.update_summary?.changed_edges)}</strong></div><small>{stamp(training?.updated_at)}</small></article>
        <article className="ob-panel ob-history-card"><span className="ob-step-number">02</span><span className="ob-kicker">FROZEN EVALUATION</span><h3>Gen {metric(latest?.generation)}</h3><p>Latest completed fixed-condition evaluation</p><div className="ob-data-pair"><span>Previous evaluated generation</span><strong>{metric(older?.generation)}</strong></div><div className="ob-data-pair"><span>Evaluation rounds</span><strong>{metric(latest?.evaluation?.rounds)}</strong></div><small>{stamp(latest?.evaluated_at)}</small></article>
        <article className="ob-panel ob-history-card"><span className="ob-step-number">03</span><span className="ob-kicker">PROMOTION BOUNDARY</span><h3>Review, then promote.</h3><p>Candidates remain separate from approved inference</p><div className="ob-data-pair"><span>Automatic promotion</span><strong>OFF</strong></div><p className="ob-caption">Generation counts and changed connections alone do not demonstrate learning effectiveness or improved performance.</p><small>Explicit evaluation and approval required</small></article>
      </div>
      <details className="ob-evaluation-details"><summary>Inspect evaluation and checkpoint records</summary><p>full-round protocol: max 60 s / 3600 frames · policy_pixel_access=false</p><p>Selected evaluation: {selected?.evaluation?.protocol || 'Not recorded'} · seeds {metric(selected?.evaluation?.seed_p1)}/{metric(selected?.evaluation?.seed_p2)} · decision interval {metric(selected?.evaluation?.decision_interval_frames)} frames</p><p>Reward ID: {selected?.reward_id || 'Not recorded'} · Model: {selected?.model || 'Not recorded'}<br />State SHA-256: <code>{selected?.state_sha256 || 'Not recorded'}</code></p><p>This viewer does not change reward settings. Evaluations with different protocols are not presented as matched comparisons.</p></details>
    </section>
  </Observatory>;
}
