"use client";

import { useEffect, useState } from 'react';
import { Observatory, metric, stamp } from './observatory';

type Json = Record<string, any>;
type Envelope = { latest?: Json | null; previous?: Json | null; training?: Json | null };
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
        if (!stopped) setError(reason instanceof Error ? reason.message : '評価データを取得できません');
      } finally { if (!stopped) timer = setTimeout(poll, 30_000); }
    };
    void poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [paused]);
  const latest = completed(data?.latest) ? data!.latest! : null;
  const older = completed(data?.previous) ? data!.previous! : null;
  const selected = previous && older ? older : latest;
  const training = data?.training;
  const video = videoUrl(selected);
  useEffect(() => setVideoError(false), [video]);
  const behind = typeof training?.generation === 'number' && typeof latest?.generation === 'number' && training.generation > latest.generation;
  const result = selected?.result;
  const verdict = result?.winner === 'DRAW' ? 'DRAW' : typeof result?.winner === 'string' ? `${result.winner} WINS` : '結果未記録';

  const media = <>
    <div className="ob-match"><strong className="p1">{selected?.character || 'GARNET'}</strong><span>VS</span><strong className="p2">{selected?.opponent || 'ZEN'}</strong></div>
    <div className="ob-score"><span>GEN {metric(selected?.generation)}</span><span>FIXED-CONDITION EVALUATION</span><span>1 ROUND</span></div>
    <div className="ob-screen">{video && !videoError ? <video key={video} data-testid="evaluation-video" src={video} controls muted playsInline preload="metadata" onError={() => setVideoError(true)} aria-label={`Generation ${selected?.generation} 評価録画`} /> : <div className="ob-empty"><span className="ob-crosshair" aria-hidden="true">+</span><strong>{videoError ? '動画を読み込めませんでした' : '評価動画を待機中'}</strong><p>{videoError ? '公開アセットの接続を確認してください。' : '完了済みの評価が公開されると表示します。'}</p>{videoError ? <button type="button" className="ob-button" onClick={() => setVideoError(false)}>動画を再読込み</button> : null}</div>}</div>
    <div className="ob-result"><div><span className="ob-kicker">FINAL RESULT / 最終結果</span><strong>{verdict}</strong></div><div><span className="p1">HP {metric(result?.p1_hp)}</span><i> / </i><span className="p2">{metric(result?.p2_hp)}</span><small>{result?.ended_by || '—'} · game {metric(result?.elapsed_seconds, 1)} s</small></div></div>
    <p className="ob-caption">Generation {metric(selected?.generation)} · {stamp(selected?.evaluated_at)} · video {metric(selected?.video?.duration_seconds, 1)} s<br />最終HPは録画の最終結果です。再生中のHPや時刻を表しません。</p>
    <div className="ob-model-switch" role="group" aria-label="評価世代を切替"><button className="ob-button" type="button" aria-pressed={!previous || !older} onClick={() => setPrevious(false)}>最新完了 Gen {metric(latest?.generation)}</button><button className="ob-button" type="button" aria-pressed={previous && Boolean(older)} disabled={!older} onClick={() => setPrevious(true)}>前回 Gen {metric(older?.generation)}</button></div>
  </>;

  return <Observatory mode="replay" status="recorded-evaluation" media={media} controls={<><button className="ob-button" type="button" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? '履歴更新を再開' : '履歴更新を停止'}</button><a className="ob-button ob-button-primary" href="/live">LIVE観測へ ↗</a></>}>
    {error ? <p className="ob-notice" role="status">評価APIを取得できません: {error}。表示がある場合は最終取得時の記録です。</p> : null}
    {paused ? <p className="ob-notice" role="status">履歴の自動更新を停止中。動画はプレイヤーの再生・停止操作で制御できます。</p> : null}
    {behind ? <p className="ob-notice">CandidateはGen {metric(training?.generation)}に更新済み。ここに表示する最新完了評価はGen {metric(latest?.generation)}です。新世代の評価完了はまだ確認できていません。</p> : null}
    <section id="evolution" className="ob-evolution">
      <div className="ob-section-title"><div><span className="ob-kicker">03 / RESEARCH TIMELINE</span><h2>いまの行動と、これまでの変化。</h2></div><span className="ob-tag">candidate only · 自動昇格なし</span></div>
      <div className="ob-history-grid">
        <article className="ob-panel ob-history-card"><span className="ob-step-number">01</span><span className="ob-kicker">CANDIDATE UPDATE</span><h3>Gen {metric(training?.generation)}</h3><p>研究用checkpointの更新</p><div className="ob-data-pair"><span>累積matches</span><strong>{metric(training?.matches)}</strong></div><div className="ob-data-pair"><span>変更された結合</span><strong>{metric(training?.update_summary?.changed_edges)}</strong></div><small>{stamp(training?.updated_at)}</small></article>
        <article className="ob-panel ob-history-card"><span className="ob-step-number">02</span><span className="ob-kicker">FROZEN EVALUATION</span><h3>Gen {metric(latest?.generation)}</h3><p>最新の完了済み固定条件評価</p><div className="ob-data-pair"><span>前回完了世代</span><strong>{metric(older?.generation)}</strong></div><div className="ob-data-pair"><span>評価ラウンド数</span><strong>{metric(latest?.evaluation?.rounds)}</strong></div><small>{stamp(latest?.evaluated_at)}</small></article>
        <article className="ob-panel ob-history-card"><span className="ob-step-number">03</span><span className="ob-kicker">PROMOTION BOUNDARY</span><h3>Review, then promote.</h3><p>Candidateと承認済み推論を分離</p><div className="ob-data-pair"><span>自動昇格</span><strong>OFF</strong></div><p className="ob-caption">世代数や結合の変化だけでは、学習効果や性能向上を証明できません。</p><small>明示的な評価・承認が必要</small></article>
      </div>
      <details className="ob-evaluation-details"><summary>評価条件・checkpointの記録を開く</summary><p>full-round protocol: max 60 s / 3600 frames · policy_pixel_access=false</p><p>選択中の評価: {selected?.evaluation?.protocol || '未記録'} · seeds {metric(selected?.evaluation?.seed_p1)}/{metric(selected?.evaluation?.seed_p2)} · decision interval {metric(selected?.evaluation?.decision_interval_frames)} frames</p><p>Reward ID: {selected?.reward_id || '未記録'} · Model: {selected?.model || '未記録'}<br />State SHA-256: <code>{selected?.state_sha256 || '未記録'}</code></p><p>報酬の設定変更はこの画面から行いません。異なる評価条件を同一条件の比較として扱いません。</p></details>
    </section>
  </Observatory>;
}
