"use client";

import { useEffect, useState } from 'react';
import { Observatory, metric, stamp } from './observatory';

type Json = Record<string, any>;
type Envelope = { latest?: Json | null; previous?: Json | null; training?: Json | null; colosseum?: Json | null; source?: string };
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

export function LiveClient() {
  const [data, setData] = useState<Envelope | null>(null);
  const [error, setError] = useState<string | null>(null);
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
      } finally { if (!stopped) timer = setTimeout(poll, 30_000); }
    };
    void poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [paused]);
  const latest = completed(data?.latest) ? data!.latest! : null;
  const prior = completed(data?.previous) ? data!.previous! : null;
  const comparisonKey = (row: Json | null) => JSON.stringify([row?.lineage, row?.reward_id,
    row?.evaluation?.protocol, row?.evaluation?.decision_interval_frames,
    row?.evaluation?.seed_p1, row?.evaluation?.seed_p2, row?.opponent]);
  const older = prior && latest && comparisonKey(prior) === comparisonKey(latest) ? prior : null;
  const selected = previous && older ? older : latest;
  const training = data?.training;
  const season = data?.colosseum;
  const seasonReady = season?.status === 'evaluation-ready';
  const elapsedSinceUpdate = typeof training?.updated_at === 'string' ? Date.now() - Date.parse(training.updated_at) : NaN;
  const staleSeason = seasonReady && Number.isFinite(elapsedSinceUpdate) && elapsedSinceUpdate > 30 * 60_000;
  const video = videoUrl(selected);
  useEffect(() => setVideoError(false), [video]);
  const behind = typeof training?.generation === 'number' && typeof latest?.generation === 'number' && training.generation > latest.generation;
  const result = selected?.result;
  const verdict = result?.winner === 'DRAW' ? 'DRAW' : typeof result?.winner === 'string' ? `${result.winner} WINS` : 'Result not recorded';

  const media = <>
    <div className="ob-match"><strong className="p1">{selected?.character || 'GARNET'}</strong><span>VS</span><strong className="p2">{selected?.opponent || 'ZEN'}</strong></div>
    <div className="ob-score"><span>GEN {metric(selected?.generation)}</span><span>FIXED-CONDITION EVALUATION</span><span>1 ROUND</span></div>
    <div className="ob-screen">{video && !videoError ? <video key={video} data-testid="evaluation-video" src={video} controls muted playsInline preload="metadata" onError={() => setVideoError(true)} aria-label={`Generation ${selected?.generation} recorded evaluation`} /> : <div className="ob-empty"><span className="ob-crosshair" aria-hidden="true">+</span><strong>{videoError ? 'Video could not be loaded' : 'Awaiting an evaluation video'}</strong><p>{videoError ? 'Check the connection to the published video asset.' : 'A completed evaluation will appear after publication.'}</p>{videoError ? <button type="button" className="ob-button" onClick={() => setVideoError(false)}>Reload video</button> : null}</div>}</div>
    <div className="ob-result"><div><span className="ob-kicker">FINAL RESULT / Final result</span><strong>{verdict}</strong></div><div><span className="p1">HP {metric(result?.p1_hp)}</span><i> / </i><span className="p2">{metric(result?.p2_hp)}</span><small>{result?.ended_by || '—'} · game {metric(result?.elapsed_seconds, 1)} s</small></div></div>
    <p className="ob-caption">Generation {metric(selected?.generation)} · {stamp(selected?.evaluated_at)} · video {metric(selected?.video?.duration_seconds, 1)} s<br />Final HP describes the recorded result, not the current playback frame or time.</p>
    <div className="ob-model-switch" role="group" aria-label="Switch evaluation generation"><button className="ob-button" type="button" aria-pressed={!previous || !older} onClick={() => setPrevious(false)}>Latest completed Gen {metric(latest?.generation)}</button><button className="ob-button" type="button" aria-pressed={previous && Boolean(older)} disabled={!older} onClick={() => setPrevious(true)}>Previous Gen {metric(older?.generation)}</button></div>
  </>;

  return <Observatory mode="replay" status="recorded-evaluation" media={media} controls={<><button className="ob-button" type="button" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? 'Resume history updates' : 'Pause history updates'}</button><a className="ob-button ob-button-primary" href="/live">Open LIVE ↗</a></>}>
    {error ? <p className="ob-notice" role="status">Evaluation API unavailable: {error}. Any visible result is the last successfully retrieved record.</p> : null}
    {paused ? <p className="ob-notice" role="status">History polling is paused. Video playback remains controlled by the player.</p> : null}
    {behind ? <p className="ob-notice">Candidate is now Gen {metric(training?.generation)}; the latest completed evaluation shown here is Gen {metric(latest?.generation)}. Completion of the new evaluation has not yet been verified.</p> : null}
    <section className="ob-panel ob-colosseum" aria-label="Colosseum training season">
      <div className="ob-section-title"><div><span className="ob-kicker">COLOSSEUM / EXPERIMENTAL SEASON</span><h2>Train. Challenge. Measure.</h2></div><span className="ob-tag">10-MINUTE REQUESTED CADENCE</span></div>
      <p>{seasonReady ? 'R3 candidate learning is active. Each completed cycle includes a fixed-seed parent challenge, a training round, and the same challenge after the update.' : 'Waiting for the first completed R3 cycle, or its status is temporarily unavailable. Any video above remains explicitly labeled with its existing reward and protocol.'}</p>
      <div className="ob-history-grid">
        <div><span className="ob-kicker">DECISION INTERVAL</span><h3>{seasonReady ? '15 game frames / 250 ms' : 'R3 target: 15 game frames'}</h3><p>Weights remain fixed throughout each round.</p></div>
        <div><span className="ob-kicker">PAIRED HP-MARGIN CHANGE</span><h3>{metric(season?.diagnostics?.paired_hp_margin_change)} HP</h3><p>Child minus parent under the same opponent and seeds.</p></div>
        <div><span className="ob-kicker">EVALUATION DAMAGE DEALT</span><h3>{metric(season?.latest?.result?.damage_dealt_hp)} HP</h3><p>{season?.latest?.result?.no_damage_draw ? 'No-damage draw: stronger play has not been demonstrated.' : 'One diagnostic matchup, not a held-out win-rate estimate.'}</p></div>
      </div>
      <p className="ob-caption">GitHub schedules are best-effort; delayed runs never overlap an active cycle. Requested cadence is not a guaranteed completion time. {staleSeason ? 'The latest completed result is over 30 minutes old; check the workflow for delays, pause state, or failures.' : ''}</p>
      {seasonReady ? <details><summary>Open season history and provenance</summary><p>Lineage: {season.lineage} · Reward: {training?.reward_id} · Saturated edge fraction: {metric(season.diagnostics?.saturated_fraction, 4)}</p>
        <div className="ob-season-history">{(season.history || []).slice(-12).reverse().map((row: Json) => <p key={row.state_sha256 + ':' + row.generation}>Gen {row.generation} · {row.result?.winner} · HP {row.result?.p1_hp}/{row.result?.p2_hp} · paired margin change {row.paired_hp_margin_change} HP</p>)}</div>
        <p>These records contain changing candidates, not repeated trials of one fixed policy. No strength claim follows from generation count.</p></details> : null}
      <a href="https://github.com/Unjuno/connectome-fighter/actions/workflows/colosseum-training.yml">Open training cycles and evidence ↗</a>
    </section>
    <section id="evolution" className="ob-evolution">
      <div className="ob-section-title"><div><span className="ob-kicker">03 / RESEARCH TIMELINE</span><h2>Current behavior. A recorded history of change.</h2></div><span className="ob-tag">candidate only · no automatic promotion</span></div>
      <div className="ob-history-grid">
        <article className="ob-panel ob-history-card"><span className="ob-step-number">01</span><span className="ob-kicker">CANDIDATE UPDATE</span><h3>Gen {metric(training?.generation)}</h3><p>Research checkpoint update</p><div className="ob-data-pair"><span>Cumulative matches</span><strong>{metric(training?.matches)}</strong></div><div className="ob-data-pair"><span>Changed connections</span><strong>{metric(training?.update_summary?.changed_edges)}</strong></div><small>{stamp(training?.updated_at)}</small></article>
        <article className="ob-panel ob-history-card"><span className="ob-step-number">02</span><span className="ob-kicker">FROZEN EVALUATION</span><h3>Gen {metric(latest?.generation)}</h3><p>Latest completed fixed-condition evaluation</p><div className="ob-data-pair"><span>Previous completed generation</span><strong>{metric(older?.generation)}</strong></div><div className="ob-data-pair"><span>Evaluation rounds</span><strong>{metric(latest?.evaluation?.rounds)}</strong></div><small>{stamp(latest?.evaluated_at)}</small></article>
        <article className="ob-panel ob-history-card"><span className="ob-step-number">03</span><span className="ob-kicker">PROMOTION BOUNDARY</span><h3>Review, then promote.</h3><p>Candidates stay separate from approved inference</p><div className="ob-data-pair"><span>Automatic promotion</span><strong>OFF</strong></div><p className="ob-caption">Generation counts and changed connections alone do not establish learning efficacy or stronger play.</p><small>Explicit evaluation and approval required</small></article>
      </div>
      <details className="ob-evaluation-details"><summary>Open evaluation protocol and checkpoint records</summary><p>full-round protocol: max 60 s / 3600 frames · policy_pixel_access=false</p><p>Selected evaluation: {selected?.evaluation?.protocol || 'Not recorded'} · seeds {metric(selected?.evaluation?.seed_p1)}/{metric(selected?.evaluation?.seed_p2)} · decision interval {metric(selected?.evaluation?.decision_interval_frames)} frames</p><p>Reward ID: {selected?.reward_id || 'Not recorded'} · Model: {selected?.model || 'Not recorded'}<br />State SHA-256: <code>{selected?.state_sha256 || 'Not recorded'}</code></p><p>This viewer cannot change rewards. Different evaluation protocols are not presented as like-for-like comparisons.</p></details>
    </section>
  </Observatory>;
}
