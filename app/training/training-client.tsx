'use client';
import { useEffect, useState } from 'react';
import { parseTrainingReport, type TrainingReport } from '../../lib/paired-training-contract';

type Phase = 'before' | 'after' | 'curriculum';
const number = (n: number | undefined, digits = 0) => typeof n === 'number' ? new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(n) : '—';
const date = (text: string) => new Date(text).toISOString().replace('T',' ').replace(/\.\d+Z$/, ' UTC');
export function TrainingClient() {
  const [report, setReport] = useState<TrainingReport | null>(null);
  const [phase, setPhase] = useState<Phase>('after');
  const [paused, setPaused] = useState(false);
  const [status, setStatus] = useState('Connecting to the experiment ledger');
  const [error, setError] = useState(false);
  const [videoError, setVideoError] = useState(false);
  useEffect(() => {
    if (paused) return;
    let stopped = false; let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const response = await fetch('/api/paired-training', { cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) });
        const data = await response.json();
        if (!response.ok) throw new Error('Experiment receipt is unavailable');
        if (data.status === 'awaiting-first-cycle' && data.latest === null) {
          if (!stopped) { setStatus('Awaiting the first published cycle'); setError(false); }
        } else {
          const next = parseTrainingReport(data.latest);
          if (!next) throw new Error('Experiment receipt failed validation');
          if (!stopped) { setReport(next); setStatus(`Completed cycle ${next.cycle}`); setError(false); }
        }
      } catch {
        if (!stopped) { setError(true); setStatus('Latest receipt unavailable. Any visible result is the last verified fetch.'); }
      } finally { if (!stopped) timer = setTimeout(poll, 30000); }
    }
    void poll();
    return () => { stopped=true; controller.abort(); clearTimeout(timer); };
  }, [paused]);
  const video = report?.videos[phase];
  useEffect(() => setVideoError(false), [video?.url]);
  const metrics = report ? phase === 'before' ? report.combat_before : phase === 'after' ? report.combat_after : report.baseline_curriculum : null;
  const stale = report && Date.now()-Date.parse(report.completed_at) > 3600000;
  return <main className="training-shell">
    <header className="training-nav"><a href="/" className="training-brand">CONNECTOME <b>FIGHTER</b></a><nav aria-label="Training navigation"><a href="/">Evaluation archive</a><a href="/training" aria-current="page">Training</a><a href="/live">LIVE observatory</a></nav></header>
    <section className="training-hero"><p className="training-kicker">THE COLOSSEUM / PAIRED NEURAL SEARCH</p><h1>Train. Compare.<br />Earn the next update.</h1><p>Real FightingICE. Actual MaleCNS neural control. Every accepted change must outperform its parent in the curriculum.</p></section>
    <div className={`training-status ${error ? 'has-error' : ''}`} role="status"><span data-testid="training-status">{paused ? 'Viewer updates paused' : status}</span><button type="button" aria-pressed={paused} onClick={() => setPaused(x => !x)}>{paused ? 'Resume viewer' : 'Pause viewer'}</button></div>
    <p className="training-caption">Ten-minute requested starts · one active cycle · completion times may vary. Pausing this viewer does not stop CI.</p>
    {stale ? <p className="training-warning">The last completed cycle is over one hour old. This page does not claim that training is currently running.</p> : null}
    <section className="training-stats" aria-label="Measured training progress"><div><span>Completed cycle</span><strong data-testid="cycle-count">{number(report?.cycle)}</strong></div><div><span>Accepted weight updates</span><strong data-testid="accepted-count">{number(report?.state.accepted_updates)}</strong></div><div><span>Completed games, total</span><strong>{number(report?.state.total_completed_games)}</strong></div><div><span>This cycle</span><strong className="training-verdict">{report ? report.accepted_update ? 'UPDATE ACCEPTED' : 'NO UPDATE' : 'NOT MEASURED'}</strong></div></section>
    <section className="training-stage">
      <div className="training-panel training-player"><div className="training-panel-title"><span>GARNET / {phase === 'curriculum' ? 'NEUTRAL TRAINING DUMMY' : 'CANONICAL ZEN'}</span><b>RECORDED · NOT LIVE</b></div>
        <div className="training-phase" role="group" aria-label="Select recorded phase">{(['before','after','curriculum'] as Phase[]).map(p => <button key={p} type="button" aria-pressed={phase===p} onClick={() => setPhase(p)}>{p==='before' ? 'Parent combat' : p==='after' ? 'Selected combat' : 'Parent practice'}</button>)}</div>
        <div className="training-video">{video && !videoError ? <video key={video.url} data-testid="training-video" src={video.url} controls muted playsInline preload="metadata" onError={() => setVideoError(true)} aria-label={`${phase} recorded FightingICE evaluation`} /> : <div className="training-empty"><strong>{videoError ? 'Recording could not be loaded' : 'Awaiting a verified recording'}</strong><p>{videoError ? 'The receipt remains available. Retry the actual asset; no substitute footage is shown.' : 'Only completed real-game records appear here.'}</p>{videoError ? <button type="button" onClick={() => setVideoError(false)}>Retry recording</button> : null}</div>}</div>
        <div className="training-result"><strong>{metrics ? metrics.outcome>0 ? 'GARNET WINS' : metrics.outcome<0 ? 'GARNET LOSES' : 'DRAW' : 'NO RESULT'}</strong><span>Final HP {number(metrics?.p1_hp)} / {number(metrics?.p2_hp)}</span><span>Damage {number(metrics?.damage_dealt_hp)} dealt / {number(metrics?.damage_taken_hp)} taken</span></div>
        <p className="training-caption">{phase==='curriculum' ? 'Practice uses an explicitly neutral opponent; this is not competitive strength.' : 'Parent and selected weights are evaluated against the same fixed canonical opponent and seed, not a held-out tournament.'} Final statistics do not track the video playhead.</p>
        {report ? <p className="training-caption">Recorded {date(report.completed_at)} · video {number(video?.recording_seconds,1)} s · game {number(metrics ? metrics.elapsed_frame/60 : undefined,1)} s</p> : null}
      </div>
      <aside className="training-panel training-explanation"><p className="training-kicker">CHANGE MUST BE EARNED</p><h2>{report?.update_reason || 'Waiting for measured contrast'}</h2><p>Two symmetric probe pairs. One fixed parent. New training seeds and search directions on every completed cycle.</p><dl><dt>Action decision interval</dt><dd>60 game frames</dd><dt>Neural window</dt><dd>20 ms per decision</dd><dt>Allowed existing edge multipliers</dt><dd>0.8–1.0</dd><dt>Automatic production promotion</dt><dd>OFF</dd></dl><p className="training-caption">Equal paired scores mean no update. A proposed change needs positive training gain and confirmation on two other seeds. These checks do not establish general fighting strength.</p>{report ? <a href={report.source_run_url}>Inspect this Actions run ↗</a> : null}</aside>
    </section>
    <section className="training-bottom"><div className="training-panel"><p className="training-kicker">FIXED REWARD CONTRACT</p><h2>Win the fight.<br />Learn contact separately.</h2><dl><dt>Combat outcome</dt><dd>Win +1 · draw 0 · loss −1</dd><dt>Combat HP advantage</dt><dd>Normalized by 400 HP, weight 0.02</dd><dt>Practice score</dt><dd>Progress 0.1 · actual hit 0.4 · damage 0.5</dd></dl><p className="training-caption">No reward for button pressing or neural activity. No no-contact penalty is sent through the former depression-only rule. Game utilities and the optimizer are project-defined, not identified biological learning signals.</p></div>
      <div className="training-panel"><p className="training-kicker">RECENT EXPERIMENT HISTORY</p><h2>Attempts are not progress.</h2>{report ? <div className="training-history">{[...report.history].reverse().map(h => <div key={h.cycle}><span>Cycle {h.cycle}</span><strong>{h.accepted_update ? 'ACCEPTED' : 'NO UPDATE'}</strong><span>{number(h.damage_dealt_hp)} HP dealt</span><small>{h.update_reason}</small></div>)}</div> : <p>No completed cycle has been loaded.</p>}<p className="training-caption">Latest 30 completed cycles. Each full report is retained at its run-addressed release.</p></div></section>
    <details className="training-panel training-provenance"><summary>Inspect evidence and scientific boundaries</summary><p>P1 uses MaleCNS connectivity and Shiu LIF. Only the allowed existing KC–MBON magnitudes are searched. Recovery within bounds is allowed; this is not the former monotonic depression-only rule. Neural activity is simulated, not recorded from a living fly.</p><p>FlyBody is not rendered in this training recording. The separate LIVE observatory has its own verified neural/physical serving contract. No unrelated fly frames are overlaid here.</p>{report ? <><p>Experiment: {report.experiment}<br />Tested commit: <code>{report.source_commit}</code><br />Numerical weights: <code>{report.state.weights_sha256}</code><br />State archive: <code>{report.state.state_file_sha256}</code></p><p><a href={report.report_url}>Full cycle receipt</a> · <a href={report.state_url}>Research state</a> · <a href={report.source_run_url}>CI evidence</a></p></> : null}<p>Set repository variable CONNECTOME_TRAINING_PAUSED=true or disable the paired-neural-training workflow to prevent subsequent cycles. A currently running computation is not automatically cancelled.</p></details>
    <footer className="training-footer">CONNECTOME FIGHTER · AN AUDITABLE EXPERIMENT · NO AUTOMATIC PROMOTION</footer>
  </main>;
}
