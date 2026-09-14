"use client";

import { useEffect, useState } from 'react';

type Json = Record<string, any>;
type Snapshot = { live: Json; activity: Json; fly: Json; images: string[] };
const ADAPTER = 'malecns-annotated-motor-to-flybody-tripod-v2';
const UPSTREAM = 'd015e9bfe441bd90ae431bac24c55cb74bdbce26';

function identity(row: Json | null | undefined) {
  if (!row || !['round', 'frame', 'decision_index'].every(k => Number.isInteger(row[k]) && row[k] >= 0)) return null;
  return `${row.round}/${row.frame}/${row.decision_index}`;
}

async function read(url: string) {
  const response = await fetch(`${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`, {
    cache: 'no-store', signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`Runtime HTTP ${response.status}`);
  return response;
}

async function hash(bytes: ArrayBuffer) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), n => n.toString(16).padStart(2, '0')).join('');
}

export function ArenaClient({ runtimeOrigin }: { runtimeOrigin: string }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState('connecting');
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let activeUrls: string[] = [];
    const discard = () => {
      activeUrls.forEach(url => URL.revokeObjectURL(url));
      activeUrls = [];
    };
    const poll = async () => {
      let retry = 250;
      try {
        let base = runtimeOrigin;
        if (!base) {
          const response = await fetch('/api/live', { cache: 'no-store', signal: AbortSignal.timeout(15000) });
          const control = await response.json();
          if (!response.ok || !control.ready || control.status !== 'running') {
            retry = control.capacity_blocked ? 60_000 : 5000;
            throw new Error(control.status || `Control HTTP ${response.status}`);
          }
          if (control.learning_enabled !== false || control.policy_pixel_access !== false) throw new Error('Policy boundary mismatch');
          const endpoint = new URL(control.telemetry_url);
          if (endpoint.protocol !== 'https:') throw new Error('Runtime endpoint requires HTTPS');
          base = endpoint.origin;
        }
        const [live, activity, fly, p1, p2, screen] = await Promise.all([
          read(base + '/state').then(r => r.json()),
          read(base + '/activity.json').then(r => r.json()),
          read(base + '/flybody.json').then(r => r.json()),
          read(base + '/flybody-p1.png').then(r => r.arrayBuffer()),
          read(base + '/flybody-p2.png').then(r => r.arrayBuffer()),
          read(base + '/screen.png').then(r => r.arrayBuffer()),
        ]);
        if (live.status !== 'running' || live.learning_enabled !== false || live.policy_pixel_access !== false) throw new Error('Arena not running read-only');
        if (fly.schema_version !== 2 || fly.publisher !== 'malecns-flybody-publisher-v2'
            || fly.adapter !== ADAPTER || fly.upstream?.commit !== UPSTREAM || fly.mujoco_gl !== 'osmesa'
            || fly.policy_access !== false || fly.game_telemetry_position_used !== false
            || activity.kind !== 'male-cns-live-anatomy-activity' || activity.policy_access !== false) throw new Error('Spectator contract mismatch');
        for (const side of ['p1', 'p2']) {
          const item = fly.sides?.[side];
          const expected = identity({ round: live.round, frame: live.frame, decision_index: live.brain?.[side]?.decision_index });
          if (!expected || identity(item?.decision) !== expected || identity(activity.sides?.[side]) !== expected
              || item?.input_status !== 'fresh' || !(item.input_age_seconds < fly.stale_after_seconds)
              || item.physics?.action_dimension !== 59 || !(item.physics.sim_steps > 0)
              || item.neural_command?.adapter !== ADAPTER) throw new Error('Awaiting aligned fresh input');
        }
        const hashes = await Promise.all([hash(p1), hash(p2)]);
        if (hashes[0] !== fly.sides.p1.png_sha256 || hashes[1] !== fly.sides.p2.png_sha256) throw new Error('Awaiting matching state and PNG bytes');
        if (stopped) return;
        const images = [screen, p1, p2].map(bytes => URL.createObjectURL(new Blob([bytes], { type: 'image/png' })));
        discard();
        activeUrls = images;
        setSnapshot({ live, activity, fly, images });
        setStatus('verified-held-input');
      } catch (error) {
        if (!stopped) {
          discard();
          setSnapshot(null);
          setStatus(error instanceof Error ? error.message : 'runtime unavailable');
        }
      } finally {
        if (!stopped) timer = setTimeout(poll, retry);
      }
    };
    void poll();
    return () => { stopped = true; clearTimeout(timer); discard(); };
  }, [runtimeOrigin]);

  const imageStyle = { display: 'block', maxWidth: '100%', width: '100%', height: 'auto' } as const;
  return <main className="shell" style={{ maxWidth: 1120, margin: 'auto', padding: 16, overflowWrap: 'anywhere' }}>
    <header>
      <p className="eyebrow">CONNECTOME FIGHTER · READ-ONLY LIVE</p>
      <h1>戦闘・神経活動・FlyBody</h1>
      <p><a href="/">Candidate evaluation videos</a> · policy_pixel_access=false · learning_enabled=false</p>
      <p data-testid="arena-status">{status}</p>
      {runtimeOrigin ? <p>CI functional E2E: real runtime on loopback. Vercel deployment is not under test.</p> : null}
      <p>FlyBody uses a project-defined motor adapter, not an identified biological muscle innervation map. The matching decision identifies held input, not lossless frame-locked replay.</p>
    </header>
    {!snapshot ? <section className="panel"><p>Waiting for verified live data. No synthetic fight, recorded LIVE, SVG fly or cached pose is substituted.</p></section> : <div
      data-testid="arena-snapshot"
      data-session={snapshot.live.session_id}
      data-frame={snapshot.live.frame}
      data-p1-decision={snapshot.fly.sides.p1.decision.decision_index}
      data-p2-decision={snapshot.fly.sides.p2.decision.decision_index}
      data-p1-hash={snapshot.fly.sides.p1.png_sha256}
      data-p2-hash={snapshot.fly.sides.p2.png_sha256}
    >
      <section className="panel" style={{ marginBottom: 16 }}>
        <h2>Official FightingICE ScreenData</h2>
        <p>Round {snapshot.live.round} · decision frame {snapshot.live.frame} · GARNET vs ZEN</p>
        <img data-testid="game-image" src={snapshot.images[0]} alt="Official FightingICE screen" style={imageStyle} />
        <p>ScreenData is an independently sampled spectator image; an exact image frame identity is not claimed.</p>
      </section>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))', gap: 16 }}>
        {['p1', 'p2'].map((side, index) => <section key={side} className="panel" style={{ minWidth: 0 }}>
          <h2>{side.toUpperCase()} MaleCNS activity / FlyBody</h2>
          <p>Input {identity(snapshot.fly.sides[side].decision)} · {snapshot.live.brain[side].total_spikes} simulated spikes</p>
          <p>Source body IDs: {snapshot.fly.sides[side].neural_command.source_body_ids.join(', ') || 'none'}</p>
          <p>Motor drive: {Number(snapshot.fly.sides[side].neural_command.drive).toFixed(4)}</p>
          <img data-testid={`${side}-image`} src={snapshot.images[index + 1]} alt={`${side.toUpperCase()} real MuJoCo fly`} style={imageStyle} />
          <p>59 actuators · {snapshot.fly.sides[side].physics.sim_steps} physics steps</p>
          <p>Executed simulation: {Number(snapshot.fly.sides[side].physics.sim_time_seconds).toFixed(3)} s · dropped wall time: {Number(snapshot.fly.sides[side].physics.dropped_time_seconds).toFixed(3)} s</p>
          <p>Body-ID activity is simulated on real anatomy, not recorded biological activity.</p>
        </section>)}
      </div>
    </div>}
  </main>;
}
