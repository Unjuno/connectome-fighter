"use client";

import { useEffect, useMemo, useState } from "react";

type Evaluation = {
  status?: string;
  evaluated_at?: string;
  candidate_only?: boolean;
  served_by_vercel?: boolean;
  auto_promotion?: boolean;
  character?: string;
  opponent?: string;
  generation?: number;
  matches?: number;
  state_sha256?: string;
  model?: string;
  reward_id?: string;
  source_training_run_url?: string | null;
  policy_pixel_access?: boolean;
  evaluation?: {
    rounds?: number;
    fixed_opponent?: boolean;
    seed_p1?: number;
    seed_p2?: number;
    round_frame_limit?: number;
    nominal_game_fps?: number;
    configured_round_limit_seconds?: number;
    decision_interval_frames?: number;
  };
  result?: {
    winner?: string;
    p1_hp?: number | null;
    p2_hp?: number | null;
  };
  video?: {
    asset_url?: string;
    codec?: string;
    width?: number;
    height?: number;
    fps?: number;
    duration_seconds?: number;
    bytes?: number;
  };
  interpretation_boundary?: string;
};

type TrainingStatus = {
  generation?: number;
  matches?: number;
  updated_at?: string;
  state_sha256?: string;
  status?: string;
  opponent?: string;
  update_summary?: {
    changed_edges?: number;
    depressed_edges?: number;
    min_multiplier?: number;
    mean_multiplier?: number;
    max_multiplier?: number;
  };
  signal_summary?: {
    sum?: number;
    positive?: number;
    negative?: number;
    nonzero?: number;
  };
};

type EvaluationEnvelope = {
  ready?: boolean;
  status?: string;
  latest?: Evaluation | null;
  previous?: Evaluation | null;
  training?: TrainingStatus | null;
};

function withVersion(url: string | undefined, token: string | number | undefined) {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (token !== undefined) parsed.searchParams.set("v", String(token));
    return parsed.toString();
  } catch {
    return url;
  }
}

function fmt(value: unknown, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "—";
}

function when(value: string | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function resultLabel(evaluation: Evaluation | null | undefined) {
  if (!evaluation?.result) return "result pending";
  const winner = evaluation.result.winner ?? "UNKNOWN";
  if (winner === "DRAW") return "DRAW";
  if (winner === "UNKNOWN") return "result unknown";
  return `${winner} wins`;
}

function VideoCard({ evaluation, previous = false }: { evaluation: Evaluation; previous?: boolean }) {
  const version = evaluation.state_sha256?.slice(0, 16) ?? evaluation.generation ?? "model";
  const video = withVersion(evaluation.video?.asset_url, version);
  const p1 = evaluation.character ?? "GARNET";
  const p2 = evaluation.opponent ?? "ZEN";
  const roundLimit = evaluation.evaluation?.configured_round_limit_seconds;

  return (
    <article className={`panel video-card ${previous ? "previous-card" : "latest-card"}`}>
      <div className="section-head">
        <div>
          <p className="eyebrow">{previous ? "PREVIOUS MODEL" : "LATEST MODEL"}</p>
          <h2>Generation {evaluation.generation ?? "—"}</h2>
        </div>
        <span className={`pill ${previous ? "neutral" : "ok"}`}>{previous ? "comparison" : "post-update evaluation"}</span>
      </div>

      <div className="media-frame game-frame video-frame">
        {video ? (
          <video
            key={video}
            src={video}
            controls
            autoPlay={!previous}
            muted
            playsInline
            preload="metadata"
          />
        ) : (
          <div className="placeholder">Round video is not available.</div>
        )}
      </div>

      <div className="round-summary">
        <strong>{p1} vs {p2}</strong>
        <span>{resultLabel(evaluation)}</span>
        <span>HP {evaluation.result?.p1_hp ?? "—"} / {evaluation.result?.p2_hp ?? "—"}</span>
      </div>

      <div className="metrics compact-metrics">
        <div><span>Round limit</span><strong>{fmt(roundLimit)} s</strong></div>
        <div><span>Frame limit</span><strong>{evaluation.evaluation?.round_frame_limit ?? "—"}</strong></div>
        <div><span>Video</span><strong>{fmt(evaluation.video?.duration_seconds)} s</strong></div>
        <div><span>State</span><strong className="hash">{evaluation.state_sha256?.slice(0, 10) ?? "—"}</strong></div>
      </div>

      <p className="mono card-foot">Evaluated {when(evaluation.evaluated_at)} · fixed seeds {evaluation.evaluation?.seed_p1 ?? "—"}/{evaluation.evaluation?.seed_p2 ?? "—"}</p>
    </article>
  );
}

export function LiveClient() {
  const [data, setData] = useState<EvaluationEnvelope | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    const poll = async () => {
      try {
        const response = await fetch(`/api/evaluation?t=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const body = (await response.json()) as EvaluationEnvelope;
        if (!stopped) {
          setData(body);
          setError(null);
        }
      } catch (err) {
        if (!stopped) setError(err instanceof Error ? err.message : "evaluation API unreachable");
      }
    };
    poll();
    const id = window.setInterval(poll, 30_000);
    return () => {
      stopped = true;
      window.clearInterval(id);
    };
  }, []);

  const latest = data?.latest ?? null;
  const previous = data?.previous ?? null;
  const training = data?.training ?? null;
  const evaluationBehind = Boolean(
    latest?.generation !== undefined &&
    training?.generation !== undefined &&
    training.generation > latest.generation,
  );

  const statusText = useMemo(() => {
    if (error) return "viewer data unavailable";
    if (!latest) return "awaiting first post-update round";
    if (evaluationBehind) return `generation ${training?.generation} evaluation running`;
    return `generation ${latest.generation ?? "—"} ready`;
  }, [error, latest, evaluationBehind, training?.generation]);

  return (
    <main className="shell evaluation-shell">
      <header className="hero compact-hero">
        <p className="eyebrow">CONNECTOME FIGHTER · MODEL ROUND EVALUATION</p>
        <h1>最新モデルの1ラウンドを見る。</h1>
        <p className="lead">
          GARNET candidate が更新されるたび、更新後のcheckpointを固定条件 GARNET vs ZEN で1ラウンド再評価します。
          完了した動画だけを公開し、古い動画を新モデルとして扱いません。
        </p>
        <div className="status-row">
          <span className={`pill ${latest && !evaluationBehind ? "ok" : "warm"}`}>{statusText}</span>
          <span className="pill neutral">candidate only</span>
          <span className="mono">policy_pixel_access=false</span>
        </div>
        {evaluationBehind ? (
          <div className="notice">
            <strong>Model updated.</strong> Candidate generation {training?.generation} exists, but its fixed-condition round video is still being generated. The page keeps generation {latest?.generation} labeled as the previous completed evaluation until the new artifact is complete.
          </div>
        ) : null}
        {!latest ? (
          <div className="notice">
            <strong>First post-update evaluation is not published yet.</strong> Training status is generation {training?.generation ?? "—"}; the viewer will switch automatically after the first one-round evaluation finishes.
          </div>
        ) : null}
        {error ? <div className="notice bad-notice">Evaluation API error: {error}</div> : null}
      </header>

      {latest ? <VideoCard evaluation={latest} /> : null}

      <section className="panel model-panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">MODEL UPDATE</p>
            <h2>What changed in the latest candidate checkpoint</h2>
          </div>
          <span className="mono">training generation {training?.generation ?? "—"}</span>
        </div>
        <div className="metrics">
          <div><span>Matches</span><strong>{training?.matches ?? latest?.matches ?? "—"}</strong></div>
          <div><span>Changed edges</span><strong>{training?.update_summary?.changed_edges ?? "—"}</strong></div>
          <div><span>Depressed edges</span><strong>{training?.update_summary?.depressed_edges ?? "—"}</strong></div>
          <div><span>Reward signal</span><strong>{fmt(training?.signal_summary?.sum, 3)}</strong></div>
        </div>
        <p className="boundary">
          This is the rolling research candidate. It is not automatically promoted into the approved Vercel inference state. The comparison round uses a fixed opponent and fixed seeds so behavioral differences across generations are less confounded by matchup or seed changes.
        </p>
      </section>

      {previous ? (
        <section className="comparison-section">
          <div className="section-head comparison-head">
            <div>
              <p className="eyebrow">BEFORE / AFTER</p>
              <h2>Compare with the previous completed model</h2>
            </div>
            <span className="mono">generation {previous.generation ?? "—"} → {latest?.generation ?? "—"}</span>
          </div>
          <div className="comparison-grid">
            <VideoCard evaluation={previous} previous />
            {latest ? <VideoCard evaluation={latest} /> : null}
          </div>
        </section>
      ) : null}

      <footer className="footer">
        <span>Evaluation: 1 round · fixed GARNET vs ZEN · frame limit 600</span>
        <span>Latest training update: {when(training?.updated_at)}</span>
        <a href="https://unjuno.github.io/connectome-fighter/">Research ledger</a>
      </footer>
    </main>
  );
}
