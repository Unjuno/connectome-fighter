"use client";

import { useEffect, useMemo, useState } from "react";

type LiveStatus = {
  ready?: boolean;
  status?: string;
  reason?: string | null;
  blocked_until?: string | null;
  runtime_archive_sha256?: string | null;
  source_runtime_base?: string | null;
  maintenance_action?: string | null;
  telemetry_url?: string | null;
  screen_url?: string | null;
  activity_url?: string | null;
  flybody_p1_url?: string | null;
  flybody_p2_url?: string | null;
  flybody_state_url?: string | null;
};

type BrainSample = { decision_index?: number; total_spikes?: number; unique_bodies?: number; output_group_spikes?: Record<string, number> };
type Telemetry = { status?: string; round?: number; frame?: number; p1?: any; p2?: any; brain?: { p1?: BrainSample; p2?: BrainSample }; learning_enabled?: boolean; policy_pixel_access?: boolean };
type ActivitySide = { decision_index?: number; round?: number; frame?: number; character?: string; neuromeres?: Array<{ name: string; value: number }>; top_bodies?: Array<{ body_id: number; spikes: number; superclass?: string; soma_neuromere?: string }>; motor_contributors?: Array<{ body_id: number; spikes: number; superclass?: string; soma_neuromere?: string }> };
type Activity = { kind?: string; policy_access?: boolean; sides?: { p1?: ActivitySide | null; p2?: ActivitySide | null } };
type FlySide = { decision?: { round?: number; frame?: number; decision_index?: number }; neural_command?: { adapter?: string; drive?: number; t1_drive?: number; t2_drive?: number; t3_drive?: number; source_body_ids?: number[] }; physics?: { sim_steps?: number; action_dimension?: number; thorax_world_position?: number[] } };
type FlyState = { kind?: string; adapter?: string; mujoco_gl?: string; game_telemetry_position_used?: boolean; sides?: { p1?: FlySide; p2?: FlySide } };

function sameDecision(telemetry: Telemetry | null, activity: Activity | null, fly: FlyState | null, side: "p1" | "p2") {
  const brain = telemetry?.brain?.[side];
  const a = activity?.sides?.[side];
  const f = fly?.sides?.[side]?.decision;
  return Boolean(
    telemetry && brain && a && f &&
    a.round === telemetry.round && a.frame === telemetry.frame && a.decision_index === brain.decision_index &&
    f.round === telemetry.round && f.frame === telemetry.frame && f.decision_index === brain.decision_index
  );
}

function fmt(value: unknown, digits = 2) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : "—";
}

function cacheBust(url: string | null | undefined, tick: number) {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    parsed.searchParams.set("t", String(tick));
    return parsed.toString();
  } catch {
    return `${url}${url.includes("?") ? "&" : "?"}t=${tick}`;
  }
}

async function fetchJson<T>(url: string | null | undefined): Promise<T | null> {
  if (!url) return null;
  try {
    const response = await fetch(cacheBust(url, Date.now())!, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export function LiveClient() {
  const [live, setLive] = useState<LiveStatus | null>(null);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [fly, setFly] = useState<FlyState | null>(null);
  const [tick, setTick] = useState(Date.now());

  useEffect(() => {
    let stopped = false;
    const poll = async () => {
      try {
        const response = await fetch(`/api/live?t=${Date.now()}`, { cache: "no-store" });
        const body = (await response.json()) as LiveStatus;
        if (!stopped) setLive(body);
      } catch {
        if (!stopped) setLive({ ready: false, status: "control-unreachable", reason: "The dedicated control API is unreachable." });
      }
    };
    poll();
    const id = window.setInterval(poll, 4000);
    return () => { stopped = true; window.clearInterval(id); };
  }, []);

  useEffect(() => {
    if (!live?.telemetry_url) {
      setTelemetry(null); setActivity(null); setFly(null); return;
    }
    let stopped = false;
    const poll = async () => {
      const [nextTelemetry, nextActivity, nextFly] = await Promise.all([
        fetchJson<Telemetry>(live.telemetry_url),
        fetchJson<Activity>(live.activity_url),
        fetchJson<FlyState>(live.flybody_state_url),
      ]);
      if (!stopped) {
        if (nextTelemetry) setTelemetry(nextTelemetry);
        if (nextActivity) setActivity(nextActivity);
        if (nextFly) setFly(nextFly);
        setTick(Date.now());
      }
    };
    poll();
    const id = window.setInterval(poll, 800);
    return () => { stopped = true; window.clearInterval(id); };
  }, [live?.telemetry_url, live?.activity_url, live?.flybody_state_url]);

  const alignedP1 = sameDecision(telemetry, activity, fly, "p1");
  const alignedP2 = sameDecision(telemetry, activity, fly, "p2");
  const aligned = alignedP1 && alignedP2;
  const screen = cacheBust(live?.screen_url, tick);
  const flyP1 = cacheBust(live?.flybody_p1_url, tick);
  const flyP2 = cacheBust(live?.flybody_p2_url, tick);
  const capacity = live?.status === "capacity-blocked";
  const decisionLabel = useMemo(() => {
    if (!telemetry) return "waiting";
    return `round ${telemetry.round ?? "—"} · frame ${telemetry.frame ?? "—"} · decisions ${telemetry.brain?.p1?.decision_index ?? "—"}/${telemetry.brain?.p2?.decision_index ?? "—"}`;
  }, [telemetry]);

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">CONNECTOME FIGHTER · DEDICATED LIVE</p>
        <h1>MaleCNS → action → FightingICE, with neural-driven FlyBody physics</h1>
        <p className="lead">One shared public broadcast. The game screen, annotated neural activity, and FlyBody physics are spectator channels; policy pixels remain disabled and candidate training is never auto-promoted.</p>
        <div className="status-row">
          <span className={`pill ${live?.ready ? "ok" : capacity ? "bad" : "warm"}`}>{live?.status ?? "loading"}</span>
          <span className={`pill ${aligned ? "ok" : "warm"}`}>{aligned ? "same-decision aligned" : "alignment pending"}</span>
          <span className="mono">{decisionLabel}</span>
        </div>
        {capacity ? <div className="notice bad-notice"><strong>Vercel Sandbox compute is capacity-blocked.</strong><br />{live?.reason ?? "Shared compute cannot start."}{live?.blocked_until ? ` Provider reset: ${live.blocked_until}.` : ""} No fake body motion or synthetic fight frame is substituted.</div> : null}
        {!capacity && !live?.ready ? <div className="notice"><strong>Shared LIVE is warming.</strong> {live?.maintenance_action ?? live?.reason ?? "Runtime base and shared Sandbox are being prepared."}</div> : null}
      </header>

      <section className="panel game-panel">
        <div className="section-head"><div><p className="eyebrow">PRIMARY GAME VIEW</p><h2>Official FightingICE ScreenData</h2></div><span className="mono">policy_pixel_access=false</span></div>
        <p className="boundary">No synthetic fight frame is substituted. This image is the official FightingICE ScreenData spectator stream and is not a policy input.</p>
        <div className="media-frame game-frame">{screen && live?.ready ? <img src={screen} alt="Official FightingICE live frame" /> : <div className="placeholder">FightingICE frame unavailable while LIVE is warming.</div>}</div>
        <div className="fighters"><strong>{telemetry?.p1?.character ?? "GARNET"}</strong><span>HP {telemetry?.p1?.hp ?? "—"} · {telemetry?.p1?.action ?? "—"}</span><strong>{telemetry?.p2?.character ?? "ZEN"}</strong><span>HP {telemetry?.p2?.hp ?? "—"} · {telemetry?.p2?.action ?? "—"}</span></div>
      </section>

      <section className="grid2">
        {(["p1", "p2"] as const).map((side) => {
          const brain = telemetry?.brain?.[side];
          const a = activity?.sides?.[side];
          const f = fly?.sides?.[side];
          const sideAligned = side === "p1" ? alignedP1 : alignedP2;
          return <article className="panel" key={side}>
            <div className="section-head"><div><p className="eyebrow">{side.toUpperCase()} NEURAL ACTIVITY</p><h2>{side.toUpperCase()} MaleCNS activity</h2></div><span className={`pill ${sideAligned ? "ok" : "warm"}`}>{sideAligned ? "aligned" : "pending"}</span></div>
            <div className="metrics"><div><span>Total spikes</span><strong>{brain?.total_spikes ?? "—"}</strong></div><div><span>Active bodies</span><strong>{brain?.unique_bodies ?? "—"}</strong></div><div><span>Motor source bodies</span><strong>{f?.neural_command?.source_body_ids?.length ?? "—"}</strong></div><div><span>Fly drive</span><strong>{fmt(f?.neural_command?.drive)}</strong></div></div>
            <h3>Top neuromere load</h3>
            <div className="bars">{(a?.neuromeres ?? []).slice(0, 6).map((row) => <div className="bar-row" key={row.name}><span>{row.name}</span><meter min={0} max={Math.max(1, ...(a?.neuromeres ?? []).map((x) => Number(x.value) || 0))} value={row.value} /><strong>{fmt(row.value, 0)}</strong></div>)}</div>
            <p className="boundary">Region loads aggregate only the bounded top-spiking real body-ID sample for this decision window; they are not an all-neuron activity map.</p>
          </article>;
        })}
      </section>

      <section className="panel">
        <div className="section-head"><div><p className="eyebrow">PHYSICAL EMBODIMENT</p><h2>MaleCNS activity drives the actual FlyBody MuJoCo fly.</h2></div><span className="mono">adapter v2 · OSMesa</span></div>
        <p className="boundary">Real annotated MaleCNS motor/descending body activity drives FlyBody through a project-defined actuator adapter. No SVG or FightingICE-position puppet is substituted here. FightingICE x/y/action do not position the FlyBody body.</p>
        <div className="fly-grid">
          <div><h3>P1 FlyBody</h3><div className="media-frame fly-frame">{flyP1 && live?.ready ? <img src={flyP1} alt="P1 FlyBody MuJoCo render" /> : <div className="placeholder">FlyBody paused</div>}</div><p className="mono">drive {fmt(fly?.sides?.p1?.neural_command?.drive)} · T1/T2/T3 {fmt(fly?.sides?.p1?.neural_command?.t1_drive)}/{fmt(fly?.sides?.p1?.neural_command?.t2_drive)}/{fmt(fly?.sides?.p1?.neural_command?.t3_drive)} · sim {fly?.sides?.p1?.physics?.sim_steps ?? "—"}</p></div>
          <div><h3>P2 FlyBody</h3><div className="media-frame fly-frame">{flyP2 && live?.ready ? <img src={flyP2} alt="P2 FlyBody MuJoCo render" /> : <div className="placeholder">FlyBody paused</div>}</div><p className="mono">drive {fmt(fly?.sides?.p2?.neural_command?.drive)} · T1/T2/T3 {fmt(fly?.sides?.p2?.neural_command?.t1_drive)}/{fmt(fly?.sides?.p2?.neural_command?.t2_drive)}/{fmt(fly?.sides?.p2?.neural_command?.t3_drive)} · sim {fly?.sides?.p2?.physics?.sim_steps ?? "—"}</p></div>
        </div>
      </section>

      <footer className="footer"><span>Runtime {live?.runtime_archive_sha256?.slice(0, 16) ?? "—"}</span><span>Base {live?.source_runtime_base ?? "—"}</span><a href="https://unjuno.github.io/connectome-fighter/">Research ledger</a></footer>
    </main>
  );
}
