"use client";

import { useEffect, useState } from 'react';
import { Observatory, type ObservationSnapshot, type DecisionMoment } from '../observatory';

type Json = Record<string, any>;
const ADAPTER = 'malecns-annotated-motor-to-flybody-tripod-v2';
const UPSTREAM = 'd015e9bfe441bd90ae431bac24c55cb74bdbce26';

function identity(row: Json | null | undefined) {
  if (!row || !['round', 'frame', 'decision_index'].every(k => Number.isInteger(row[k]) && row[k] >= 0)) return null;
  return `${row.round}/${row.frame}/${row.decision_index}`;
}
async function read(url: string) {
  const response = await fetch(`${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`, { cache: 'no-store', signal: AbortSignal.timeout(8000) });
  if (!response.ok) throw new Error(`Runtime HTTP ${response.status}`);
  return response;
}
async function hash(bytes: ArrayBuffer) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), n => n.toString(16).padStart(2, '0')).join('');
}

export function ArenaClient({ runtimeOrigin }: { runtimeOrigin: string }) {
  const [snapshot, setSnapshot] = useState<ObservationSnapshot | null>(null);
  const [status, setStatus] = useState('connecting');
  const [paused, setPaused] = useState(false);
  const [moments, setMoments] = useState<DecisionMoment[]>([]);
  useEffect(() => {
    setSnapshot(null);
    setMoments([]);
    setStatus(paused ? 'paused' : 'connecting');
    if (paused) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let activeUrls: string[] = [];
    let knownBase = runtimeOrigin;
    let nextControlAt = 0;
    const discard = () => { activeUrls.forEach(url => URL.revokeObjectURL(url)); activeUrls = []; };
    const poll = async () => {
      let retry = 250;
      try {
        if (!runtimeOrigin && (!knownBase || Date.now() >= nextControlAt)) {
          const response = await fetch('/api/live', { cache: 'no-store', signal: AbortSignal.timeout(15000) });
          const control = await response.json();
          if (!response.ok || !control.ready || control.status !== 'running') {
            knownBase = '';
            const requestedRetry = Number(response.headers.get('retry-after') || '60');
            retry = control.capacity_blocked ? Math.max(60_000, Math.min(3600_000, requestedRetry * 1000 || 60_000)) : 5000;
            throw new Error(control.status || `Control HTTP ${response.status}`);
          }
          if (control.learning_enabled !== false || control.policy_pixel_access !== false) throw new Error('Policy boundary mismatch');
          const endpoint = new URL(control.telemetry_url);
          if (endpoint.protocol !== 'https:') throw new Error('Runtime endpoint requires HTTPS');
          knownBase = endpoint.origin;
          nextControlAt = Date.now() + 15_000;
        }
        if (stopped) return;
        const base = knownBase;
        const [current, latestActivity, fly] = await Promise.all([
          read(base + '/state').then(r => r.json()), read(base + '/activity.json').then(r => r.json()), read(base + '/flybody.json').then(r => r.json()),
        ]);
        if (current.status !== 'running' || current.learning_enabled !== false || current.policy_pixel_access !== false) throw new Error('Arena not running read-only');
        if (fly.schema_version !== 2 || fly.publisher !== 'malecns-flybody-publisher-v2' || fly.adapter !== ADAPTER
            || fly.upstream?.commit !== UPSTREAM || fly.mujoco_gl !== 'osmesa' || fly.policy_access !== false
            || fly.game_telemetry_position_used !== false || latestActivity.kind !== 'male-cns-live-anatomy-activity'
            || latestActivity.policy_access !== false) throw new Error('Spectator contract mismatch');
        const d1 = fly.sides?.p1?.decision, d2 = fly.sides?.p2?.decision;
        if (!identity(d1) || !identity(d2) || d1.round !== d2.round || d1.frame !== d2.frame) throw new Error('Awaiting aligned fresh input');
        const selector = new URLSearchParams({ session_id: current.session_id, round: String(d1.round), frame: String(d1.frame), p1: String(d1.decision_index), p2: String(d2.decision_index) });
        const [selected, p1, p2, screen] = await Promise.all([
          read(base + '/decision-snapshot?' + selector.toString()).then(r => r.json()),
          read(base + '/flybody-p1.png').then(r => r.arrayBuffer()), read(base + '/flybody-p2.png').then(r => r.arrayBuffer()), read(base + '/screen.png').then(r => r.arrayBuffer()),
        ]);
        if (selected.kind !== 'observed-decision-snapshot' || selected.session_id !== current.session_id
            || selected.selection_mode !== 'observed-decision-history-v1' || selected.policy_access !== false) throw new Error('Observed decision snapshot mismatch');
        const live = selected.telemetry, activity = selected.activity;
        if (live.status !== 'running' || live.learning_enabled !== false || live.policy_pixel_access !== false
            || activity.kind !== 'male-cns-live-anatomy-activity' || activity.policy_access !== false) throw new Error('Selected source policy boundary mismatch');
        for (const side of ['p1', 'p2']) {
          const item = fly.sides?.[side];
          const expected = identity({ round: live.round, frame: live.frame, decision_index: live.brain?.[side]?.decision_index });
          const age = selected.source_age_seconds?.[side];
          if (!expected || identity(item?.decision) !== expected || identity(activity.sides?.[side]) !== expected
              || !Number.isFinite(age) || age < 0 || age >= 30 || item?.input_status !== 'fresh'
              || !Number.isFinite(item.input_age_seconds) || item.input_age_seconds < 0
              || !(item.input_age_seconds < fly.stale_after_seconds) || item.physics?.action_dimension !== 59
              || !(item.physics.sim_steps > 0) || item.neural_command?.adapter !== ADAPTER) throw new Error('Awaiting aligned fresh input');
        }
        const hashes = await Promise.all([hash(p1), hash(p2)]);
        if (hashes[0] !== fly.sides.p1.png_sha256 || hashes[1] !== fly.sides.p2.png_sha256) throw new Error('Awaiting matching state and PNG bytes');
        if (stopped) return;
        const images = [screen, p1, p2].map(bytes => URL.createObjectURL(new Blob([bytes], { type: 'image/png' })));
        discard(); activeUrls = images;
        setSnapshot({ live, current, activity, fly, selected, images }); setStatus('verified-held-input');
        const sessionPrefix = `${live.session_id}|`;
        const key = `${sessionPrefix}${identity(d1)}|${identity(d2)}`;
        setMoments(prior => {
          const history = prior.filter(moment => moment.key.startsWith(sessionPrefix));
          if (history.some(moment => moment.key === key)) return history;
          return [...history, { key, frame: live.frame, round: live.round, p1: live.p1?.action || '—', p2: live.p2?.action || '—' }].slice(-8);
        });
      } catch (error) {
        if (!stopped) { discard(); setSnapshot(null); setStatus(error instanceof Error ? error.message : 'runtime unavailable'); }
      } finally { if (!stopped) timer = setTimeout(poll, retry); }
    };
    void poll();
    return () => { stopped = true; clearTimeout(timer); discard(); };
  }, [runtimeOrigin, paused]);

  return <Observatory mode="live" snapshot={snapshot} status={status} moments={moments} ci={Boolean(runtimeOrigin)} controls={<button type="button" className="ob-button" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? 'Resume LIVE display' : 'Pause display updates'}</button>} />;
}
