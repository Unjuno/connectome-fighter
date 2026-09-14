"use client";

import type { CSSProperties, ReactNode } from 'react';

type Json = Record<string, any>;
export type ObservationSnapshot = { live: Json; current: Json; activity: Json; fly: Json; selected: Json; images: string[] };
export type DecisionMoment = { key: string; frame: number; p1: string; p2: string; round: number };

export function metric(value: unknown, digits = 0): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value);
}
export function stamp(value: unknown): string {
  if (typeof value !== 'string') return 'Not recorded';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not recorded';
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Tokyo', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date) + ' JST';
}

function Empty({ title, children }: { title: string; children: ReactNode }) {
  return <div className="ob-empty"><span className="ob-crosshair" aria-hidden="true">+</span><strong>{title}</strong><p>{children}</p></div>;
}

function Bars({ rows, valueKey, label }: { rows: Json[]; valueKey: string; label: string }) {
  const valid = rows.filter(row => typeof row?.[valueKey] === 'number' && Number.isFinite(row[valueKey]) && row[valueKey] >= 0).slice(0, 5);
  const maximum = Math.max(1, ...valid.map(row => row[valueKey]));
  return <div className="ob-bars" aria-label={label}>{valid.map((row, index) => <div className="ob-bar" key={`${row.body_id ?? row.name}-${index}`}>
    <span title={String(row.body_id ?? row.name ?? '')}>{row.type || row.name || `Body ${row.body_id ?? '—'}`}</span><b>{metric(row[valueKey], 1)}</b>
    <div className="ob-bar-track"><i style={{ width: `${row[valueKey] / maximum * 100}%` }} /></div>
  </div>)}</div>;
}

function BrainPanel({ side, snapshot, replay }: { side: 'p1' | 'p2'; snapshot: ObservationSnapshot | null; replay: boolean }) {
  const data = snapshot?.activity.sides?.[side];
  const brain = snapshot?.live.brain?.[side];
  const character = snapshot?.live[side]?.character || (side === 'p1' ? 'GARNET' : 'ZEN');
  const top = Array.isArray(data?.top_bodies) ? data.top_bodies : [];
  const motor = Array.isArray(data?.motor_contributors) ? data.motor_contributors : [];
  return <aside className={`ob-brain ob-panel ${side}`} data-testid={`${side}-brain`} aria-label={`${side.toUpperCase()} neural activity`}>
    <div className="ob-panel-heading"><span className="ob-kicker">{side.toUpperCase()} / NEURAL ACTIVITY</span><span className="ob-signal-dot" data-active={Boolean(snapshot)} /></div>
    <h2>{character}</h2><p className="ob-caption">MaleCNS · Shiu LIF</p>
    <div className="ob-neural-count"><strong>{metric(brain?.total_spikes)}</strong><span>spikes / decision window</span></div>
    {snapshot ? <>
      <div className="ob-subheading">Top-spiking body IDs <span>spikes</span></div>
      {top.length ? <Bars rows={top} valueKey="spikes" label={`${side} top spiking bodies`} /> : <p className="ob-caption">No top-body records</p>}
      <div className="ob-subheading">Motor output <span>spikes</span></div>
      {motor.length ? <Bars rows={motor.slice(0, 3)} valueKey="spikes" label={`${side} motor contributors`} /> : <p className="ob-caption">No motor-output records</p>}
      <div className="ob-action" key={`${data?.round}/${data?.frame}/${data?.decision_index}`}><span>SELECTED ACTION</span><strong>{snapshot.live[side]?.action || '—'}</strong></div>
      <p className="ob-caption">Source age {metric(snapshot.selected.source_age_seconds?.[side], 2)} s · Top-body sample only, not an all-neuron activity distribution.</p>
    </> : <Empty title={replay ? 'Neural activity not recorded' : 'Awaiting neural input'}>{replay ? 'This video has no synchronized neural recording. Verified neural activity is shown in the LIVE view.' : 'Displayed only after verified input is received.'}</Empty>}
    <div className="ob-panel-foot">Simulation on biological connectivity</div>
  </aside>;
}

function BodyPanel({ side, snapshot, replay }: { side: 'p1' | 'p2'; snapshot: ObservationSnapshot | null; replay: boolean }) {
  const item = snapshot?.fly.sides?.[side];
  const command = item?.neural_command;
  const physics = item?.physics;
  const fields = [['drive', 'TOTAL'], ['t1_drive', 'T1'], ['t2_drive', 'T2'], ['t3_drive', 'T3']] as const;
  return <section className={`ob-body ob-panel ${side}`} aria-label={`${side.toUpperCase()} FlyBody`}>
    <div className="ob-panel-heading"><div><span className="ob-kicker">{side.toUpperCase()} / EMBODIMENT</span><h2>Read the body.</h2></div><span className="ob-tag">FlyBody / MuJoCo</span></div>
    <div className="ob-body-content">
      <div className="ob-body-image">{snapshot ? <img data-testid={`${side}-image`} src={snapshot.images[side === 'p1' ? 1 : 2]} alt={`${side.toUpperCase()} real MuJoCo fly`} /> : <Empty title={replay ? 'Body motion not recorded' : 'Awaiting physical render'}>{replay ? 'Body frames from another time are not overlaid on recordings.' : 'Displayed after verifying neural-input and PNG consistency.'}</Empty>}</div>
      <div className="ob-drive"><p className="ob-kicker">NEURAL MOTOR DRIVE</p>{fields.map(([field, name]) => <div className="ob-drive-row" key={field}><span>{name}</span><div><i style={{ width: `${typeof command?.[field] === 'number' && Number.isFinite(command[field]) ? Math.min(1, Math.max(0, command[field])) * 100 : 0}%` }} /></div><b>{metric(command?.[field], 2)}</b></div>)}<p className="ob-caption">Normalized command, 0–1. Not a physiological measure of muscle activity.</p></div>
    </div>
    <div className="ob-body-footer"><span>59 actuators · OSMesa</span><span>{snapshot ? `${metric(physics?.sim_steps)} steps · ${metric(physics?.sim_time_seconds, 3)} s simulated` : 'NO VERIFIED FRAME'}</span></div>
    {snapshot ? <p className="ob-caption">Held input R{item.decision.round} / F{item.decision.frame} / D{item.decision.decision_index} · Dropped wall time {metric(physics?.dropped_time_seconds, 3)} s</p> : null}
  </section>;
}

function Protocol({ snapshot }: { snapshot: ObservationSnapshot | null }) {
  return <section id="protocol" className="ob-protocol">
    <div><span className="ob-kicker">THE EXPERIMENT / INTERPRETATION BOUNDARIES</span><h2>Real structure.<br />Explicit assumptions.</h2><p>Spectator data is separate from policy input.</p></div>
    <div className="ob-protocol-list">
      <details><summary><span>01</span> Anatomy and neural activity <b>DATA / MODEL</b></summary><p>Neural activity is simulated by applying the Shiu LIF model to MaleCNS connectivity. It is neither activity recorded from a living fly nor a whole-brain activity map. The viewer displays a bounded sample of top body IDs.</p></details>
      <details><summary><span>02</span> From neural activity to game and body <b>PROJECT INTERFACE</b></summary><p>Game input/output and the MaleCNS-to-FlyBody actuator mapping are project-defined interfaces, not an experimentally identified muscle-innervation map. FightingICE coordinates do not position the fly.</p></details>
      <details><summary><span>03</span> Time and image correspondence <b>VERIFIED / LIMITED</b></summary><p>LIVE neural activity and held body input are matched to observed decision history, and body PNG bytes are verified by SHA-256. FightingICE ScreenData is sampled independently; exact image-frame synchronization is not claimed. Physics can run slower than wall time under load.</p></details>
      <details><summary><span>04</span> Inspect provenance and runtime state <b>PROVENANCE</b></summary><p>FlyBody upstream: d015e9bfe441bd90ae431bac24c55cb74bdbce26<br />Adapter: malecns-annotated-motor-to-flybody-tripod-v2<br />Observation is read-only. Pixels are not policy inputs.</p>{snapshot ? <pre>{JSON.stringify({ session: snapshot.live.session_id, selected: snapshot.selected, body: snapshot.fly }, null, 2)}</pre> : <p>No verified LIVE snapshot is available in this view.</p>}<a href="https://github.com/Unjuno/connectome-fighter">Source repository ↗</a></details>
    </div>
  </section>;
}

export function Observatory({ mode, snapshot = null, status, media, children, controls, moments = [], ci = false }: {
  mode: 'replay' | 'live'; snapshot?: ObservationSnapshot | null; status: string; media?: ReactNode; children?: ReactNode; controls?: ReactNode; moments?: DecisionMoment[]; ci?: boolean;
}) {
  const replay = mode === 'replay';
  const active = Boolean(snapshot);
  const blocked = status.includes('capacity-blocked');
  const paused = status === 'paused';
  const attributes = snapshot ? {
    'data-testid': 'arena-snapshot', 'data-session': snapshot.live.session_id, 'data-frame': snapshot.live.frame,
    'data-p1-decision': snapshot.fly.sides.p1.decision.decision_index, 'data-p2-decision': snapshot.fly.sides.p2.decision.decision_index,
    'data-p1-hash': snapshot.fly.sides.p1.png_sha256, 'data-p2-hash': snapshot.fly.sides.p2.png_sha256,
  } : {};
  return <main className="observatory">
    <a className="ob-skip" href="#ob-stage">Skip to the observatory</a>
    <div className="ob-wrap">
      <header className="ob-nav"><a href="/" className="ob-brand" aria-label="Connectome Fighter home"><span className="ob-brand-mark" aria-hidden="true">CF</span><span>CONNECTOME<br /><b>FIGHTER</b></span></a><nav aria-label="Main navigation"><a href="/" aria-current={replay ? 'page' : undefined}>REPLAY</a><a href="/live" aria-current={!replay ? 'page' : undefined}>LIVE observatory</a><a href="#protocol">About the experiment</a></nav><span className="ob-nav-note">NEURAL OBSERVATORY <span>01</span></span></header>
      <section className="ob-intro"><div><p className="ob-kicker">CONNECTIVITY → ACTIVITY → BEHAVIOR</p><h1>Watch the fight. See the circuitry.</h1><p>Observe fighting-game behavior and a fruit-fly body driven by neural activity.</p></div><div className="ob-intro-mode"><span className={`ob-tag ${active ? 'ob-verified' : ''}`}>{replay ? 'RECORDED EVALUATION' : active ? 'LIVE / VERIFIED INPUT' : paused ? 'VIEW PAUSED' : 'LIVE / NOT CONNECTED'}</span><small>{replay ? 'Recorded evaluation · not LIVE' : 'Read-only observation · no learning updates'}</small></div></section>
      <div className="ob-modebar"><div><span className={`ob-status-dot ${active ? 'is-active' : ''}`} />{replay ? 'CANDIDATE REPLAY' : <span data-testid="arena-status">{status}</span>}</div><div className="ob-controls">{controls}<span className="ob-tag">PIXELS → POLICY: OFF</span></div></div>
      {ci ? <p className="ob-notice">CI functional E2E · actual runtime on loopback, not evidence of Vercel production compute.</p> : null}
      {blocked ? <p className="ob-notice" role="status"><strong>LIVE compute is paused by the provider usage limit.</strong> A disconnected stream is not replaced with a recording or simulated display data.<a href="/">Watch recorded evaluations ↗</a></p> : null}
      {paused ? <p className="ob-notice" role="status">Display updates are paused. Resuming fetches the latest verified input; it does not control server computation.</p> : null}
      <div {...attributes}>
        <section id="ob-stage" className="ob-stage" aria-label="Combat and neural activity for both fighters">
          <BrainPanel side="p1" snapshot={snapshot} replay={replay} />
          <section className="ob-arena ob-panel">
            <div className="ob-panel-heading"><span className="ob-kicker">01 / FIGHTINGICE</span><span className="ob-tag">{replay ? 'REPLAY' : active ? 'OFFICIAL SCREENDATA' : 'AWAITING RUNTIME'}</span></div>
            {replay ? media : <><div className="ob-match"><strong className="p1">{snapshot?.live.p1?.character || 'GARNET'}</strong><span>VS</span><strong className="p2">{snapshot?.live.p2?.character || 'ZEN'}</strong></div><div className="ob-score"><span className="p1">HP {metric(snapshot?.current.p1?.hp)}</span><span>{active ? `ROUND ${snapshot?.current.round} · FRAME ${snapshot?.current.frame}` : 'NO VERIFIED TELEMETRY'}</span><span className="p2">HP {metric(snapshot?.current.p2?.hp)}</span></div><div className="ob-screen">{snapshot ? <img data-testid="game-image" src={snapshot.images[0]} alt="Official FightingICE screen" /> : <Empty title={blocked ? 'Awaiting compute capacity' : paused ? 'Display paused' : 'Awaiting verified combat data'}>Only actual FightingICE ScreenData is displayed in this area.</Empty>}</div></>}
            <p className="ob-arena-note">{replay ? 'Recorded evaluations and LIVE neural observations are separate records. Unrecorded activity is not invented for a video.' : 'Combat images are independently sampled. Neural and body panels match held input to observed decision history.'}</p>
          </section>
          <BrainPanel side="p2" snapshot={snapshot} replay={replay} />
        </section>
        <section className={`ob-flow ${active ? 'is-active' : ''}`} aria-label="Project-defined information path"><div className="ob-flow-title"><span className="ob-kicker">SIGNAL PATH</span><small>Designed connections, not proof of biological causation</small></div><div className="ob-flow-steps"><span>Game observation</span><i>→</i><span>Sensory input</span><i>→</i><strong>MaleCNS / LIF</strong><i>→</i><span>Motor output</span><i>→</i><div><span>Game action</span><small>＋ adapter → FlyBody</small></div></div></section>
        <div className="ob-section-title"><div><span className="ob-kicker">02 / PHYSICAL EMBODIMENT</span><h2>One neural signal. Another body.</h2></div><p>Actual MuJoCo physics, independent of FightingICE.</p></div>
        <div className="ob-bodies"><BodyPanel side="p1" snapshot={snapshot} replay={replay} /><BodyPanel side="p2" snapshot={snapshot} replay={replay} /></div>
      </div>
      {!replay ? <section className="ob-timeline ob-panel"><div className="ob-panel-heading"><div><span className="ob-kicker">03 / OBSERVED DECISIONS</span><h2>Observed actions</h2></div><span className="ob-caption">Last 8 observations in this visit · not lossless replay</span></div>{active && moments.length ? <ol>{moments.map(moment => <li key={moment.key}><span>R{moment.round} / F{moment.frame}</span><strong className="p1">{moment.p1}</strong><strong className="p2">{moment.p2}</strong></li>)}</ol> : <p className="ob-caption">The timeline appears only after verified observations are available.</p>}<a href="/">Candidate updates and evaluation history ↗</a></section> : null}
      {children}
      <Protocol snapshot={snapshot} />
      <footer className="ob-footer"><span>CONNECTOME FIGHTER / AN AUDITABLE EXPERIMENT</span><span>MaleCNS anatomy · Shiu LIF · project-defined interfaces</span><a href="https://unjuno.github.io/connectome-fighter/">Research ledger ↗</a></footer>
    </div>
  </main>;
}
