"use client";
import { useEffect, useState } from 'react';
import { isPairedView } from '../../lib/paired-view';

type View = Record<string, any>;
export default function TrainingConsole() {
  const [view, setView] = useState<View | null>(null);
  const [notice, setNotice] = useState('Connecting to the published experiment record.');
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (paused) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const response = await fetch('/api/evaluation', { cache: 'no-store', signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]) });
        if (!response.ok) throw new Error('Evidence temporarily unavailable.');
        const data: unknown = await response.json();
        if (!isPairedView(data)) throw new Error('A completed recurring paired cycle has not yet been published.');
        if (!controller.signal.aborted) { setView(data); setNotice('Recorded experiment · not LIVE · no automatic promotion.'); }
      } catch (reason) {
        if (!controller.signal.aborted) setNotice((reason instanceof Error ? reason.message : 'Evidence unavailable.') + ' Any displayed record is the last successful fetch.');
      } finally { if (!controller.signal.aborted) timer = setTimeout(poll, 30000); }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [paused]);
  return <main className="observatory"><div className="ob-wrap">
    <header className="ob-nav"><a className="ob-brand" href="/">CONNECTOME FIGHTER</a><nav aria-label="Training navigation"><a href="/">Observatory</a><a href="/training" aria-current="page">Training console</a><a href="/live">LIVE</a></nav></header>
    <section className="ob-intro"><div><p className="ob-kicker">PAIRED NEURAL LEARNING</p><h1>Trials are not victories.</h1><p>Compare the same parent and candidate. Keep the weights when the evidence is unchanged.</p></div></section>
    <div className="ob-modebar"><p role="status">{notice}</p><button type="button" className="ob-button" aria-pressed={paused} onClick={() => setPaused(v => !v)}>{paused ? 'Resume viewer updates' : 'Pause viewer updates'}</button></div>
    <p className="ob-caption">Five-minute wake-up requests are best effort. A cycle may run longer. Viewer pause does not stop training.</p>
    {view ? <>
      <div className="ob-history-grid">
        <article className="ob-panel ob-history-card"><p className="ob-kicker">EXPERIMENT CYCLE</p><h2>{view.cycle_index}</h2><p>{view.training.matches_this_cycle} completed games in this cycle</p></article>
        <article className="ob-panel ob-history-card"><p className="ob-kicker">ACCEPTED WEIGHT UPDATES</p><h2>{view.accepted_update_count}</h2><p>{view.training.accepted_update ? 'A candidate change passed the selection condition.' : 'NO UPDATE · parent weights retained.'}</p></article>
        <article className="ob-panel ob-history-card"><p className="ob-kicker">TRAINING OBJECTIVE</p><h2>{view.training.phase === 'curriculum' ? 'Contact curriculum' : 'Combat outcome'}</h2><p>{view.training.update_reason}</p><p className="ob-caption">Curriculum success is not competitive strength.</p></article>
      </div>
      <section className="ob-bodies" aria-label="Recorded before and after comparison">
        {(['previous', 'latest'] as const).map(key => { const e = view[key]; return <article key={key} className="ob-panel ob-body">
          <p className="ob-kicker">{e.comparison_phase.toUpperCase()} · FROZEN EVALUATION</p><h2>Generation {e.generation}</h2>
          <video src={e.video.asset_url} controls muted playsInline preload="metadata" style={{ width: '100%' }} aria-label={`${e.comparison_phase} recorded combat`} />
          <p>{e.result.winner} · Final HP {e.result.p1_hp} / {e.result.p2_hp}</p><p>Damage dealt: {e.result.damage_dealt_hp} · Damage taken: {e.result.damage_taken_hp}</p>
          <p className="ob-caption">Game: {e.result.elapsed_seconds} s · Recording: {e.video.duration_seconds} s</p>
        </article>; })}
      </section>
      <details className="ob-evaluation-details"><summary>Inspect reward, schedule and provenance</summary>
        <p>Combat: win +1, draw 0, loss -1; normalized final HP advantage weighted by 0.02.</p>
        <p>Curriculum: approach progress weighted by 0.1; actual first hit 0.4; normalized damage dealt weighted by 0.5. No attack-button reward.</p>
        <p>Decision interval: 60 game frames. Neural window: 20 ms. These clocks are unchanged by the scheduler.</p>
        <p>Last publication: {view.updated_at} · Next phase: {view.training.next_phase}</p>
        <p>Protocol SHA-256: <code>{view.protocol_sha256}</code></p><p>Effective weight ID: <code>{view.latest.state_sha256}</code></p>
        <a href={view.source_run_url}>Source CI run ↗</a>
      </details>
    </> : <section className="ob-panel"><h2>Awaiting published paired evidence</h2><p>No synthetic scores, videos or generation increments are substituted.</p></section>}
  </div></main>;
}
