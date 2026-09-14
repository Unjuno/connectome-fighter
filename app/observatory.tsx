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
  if (typeof value !== 'string') return '未記録';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '未記録';
  return new Intl.DateTimeFormat('ja-JP', { timeZone: 'Asia/Tokyo', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date) + ' JST';
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
  return <aside className={`ob-brain ob-panel ${side}`} data-testid={`${side}-brain`} aria-label={`${side.toUpperCase()} 神経活動`}>
    <div className="ob-panel-heading"><span className="ob-kicker">{side.toUpperCase()} / NEURAL ACTIVITY</span><span className="ob-signal-dot" data-active={Boolean(snapshot)} /></div>
    <h2>{character}</h2><p className="ob-caption">MaleCNS · Shiu LIF</p>
    <div className="ob-neural-count"><strong>{metric(brain?.total_spikes)}</strong><span>spikes / decision window</span></div>
    {snapshot ? <>
      <div className="ob-subheading">発火上位のbody ID <span>spikes</span></div>
      {top.length ? <Bars rows={top} valueKey="spikes" label={`${side} top spiking bodies`} /> : <p className="ob-caption">上位bodyの記録なし</p>}
      <div className="ob-subheading">運動出力 <span>spikes</span></div>
      {motor.length ? <Bars rows={motor.slice(0, 3)} valueKey="spikes" label={`${side} motor contributors`} /> : <p className="ob-caption">運動出力の記録なし</p>}
      <div className="ob-action" key={`${data?.round}/${data?.frame}/${data?.decision_index}`}><span>SELECTED ACTION</span><strong>{snapshot.live[side]?.action || '—'}</strong></div>
      <p className="ob-caption">受信元の経過 {metric(snapshot.selected.source_age_seconds?.[side], 2)} s · 上位標本のみ。全神経の活動分布ではありません。</p>
    </> : <Empty title={replay ? '神経活動は未収録' : '神経入力を待機中'}>{replay ? 'この評価動画に同期した神経記録はありません。LIVE観測で表示します。' : '検証済みの入力を受信したときだけ表示します。'}</Empty>}
    <div className="ob-panel-foot">実接続データ上のシミュレーション</div>
  </aside>;
}

function BodyPanel({ side, snapshot, replay }: { side: 'p1' | 'p2'; snapshot: ObservationSnapshot | null; replay: boolean }) {
  const item = snapshot?.fly.sides?.[side];
  const command = item?.neural_command;
  const physics = item?.physics;
  const fields = [['drive', 'TOTAL'], ['t1_drive', 'T1'], ['t2_drive', 'T2'], ['t3_drive', 'T3']] as const;
  return <section className={`ob-body ob-panel ${side}`} aria-label={`${side.toUpperCase()} FlyBody`}>
    <div className="ob-panel-heading"><div><span className="ob-kicker">{side.toUpperCase()} / EMBODIMENT</span><h2>身体で、読む。</h2></div><span className="ob-tag">FlyBody / MuJoCo</span></div>
    <div className="ob-body-content">
      <div className="ob-body-image">{snapshot ? <img data-testid={`${side}-image`} src={snapshot.images[side === 'p1' ? 1 : 2]} alt={`${side.toUpperCase()} real MuJoCo fly`} /> : <Empty title={replay ? '身体記録は未収録' : '物理レンダー待機中'}>{replay ? '録画に別時刻の身体を重ねません。' : '神経入力とPNGの整合確認後に表示。'}</Empty>}</div>
      <div className="ob-drive"><p className="ob-kicker">NEURAL MOTOR DRIVE</p>{fields.map(([field, name]) => <div className="ob-drive-row" key={field}><span>{name}</span><div><i style={{ width: `${typeof command?.[field] === 'number' && Number.isFinite(command[field]) ? Math.min(1, Math.max(0, command[field])) * 100 : 0}%` }} /></div><b>{metric(command?.[field], 2)}</b></div>)}<p className="ob-caption">正規化指令 0–1 · 生理学的な筋活動量ではありません。</p></div>
    </div>
    <div className="ob-body-footer"><span>59 actuators · OSMesa</span><span>{snapshot ? `${metric(physics?.sim_steps)} steps · ${metric(physics?.sim_time_seconds, 3)} s simulated` : 'NO VERIFIED FRAME'}</span></div>
    {snapshot ? <p className="ob-caption">保持入力 R{item.decision.round} / F{item.decision.frame} / D{item.decision.decision_index} · 破棄した実時間 {metric(physics?.dropped_time_seconds, 3)} s</p> : null}
  </section>;
}

function Protocol({ snapshot }: { snapshot: ObservationSnapshot | null }) {
  return <section id="protocol" className="ob-protocol">
    <div><span className="ob-kicker">THE EXPERIMENT / 観測の境界</span><h2>本物の構造。<br />明示された仮定。</h2><p>見るためのデータと、行動を決める入力を分ける。</p></div>
    <div className="ob-protocol-list">
      <details><summary><span>01</span> 解剖学と神経活動 <b>DATA / MODEL</b></summary><p>MaleCNSの接続データにShiu LIFモデルを適用した神経活動です。生きたハエからの活動実測でも、全脳活動の可視化でもありません。上位body IDの標本を表示します。</p></details>
      <details><summary><span>02</span> 神経からゲーム・身体へ <b>PROJECT INTERFACE</b></summary><p>ゲーム入出力とMaleCNS→FlyBody actuatorの変換はプロジェクト定義です。生物学的に同定された筋支配地図ではありません。FightingICEの位置をコピーしてハエを動かすことはしません。</p></details>
      <details><summary><span>03</span> 時刻と画像の対応 <b>VERIFIED / LIMITED</b></summary><p>LIVEでは神経活動・身体の保持入力を、実際に観測したdecision履歴に照合し、身体PNGをSHA-256で検証します。戦闘ScreenDataは独立に取得され、画像の厳密なframe同期は主張しません。負荷時に物理時間が遅れることがあります。</p></details>
      <details><summary><span>04</span> 出典・実行状態を開く <b>PROVENANCE</b></summary><p>FlyBody upstream: d015e9bfe441bd90ae431bac24c55cb74bdbce26<br />Adapter: malecns-annotated-motor-to-flybody-tripod-v2<br />観測はread-only。画素はpolicy入力に使いません。</p>{snapshot ? <pre>{JSON.stringify({ session: snapshot.live.session_id, selected: snapshot.selected, body: snapshot.fly }, null, 2)}</pre> : <p>この画面には検証済みLIVE snapshotはありません。</p>}<a href="https://github.com/Unjuno/connectome-fighter">Source repository ↗</a></details>
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
    <a className="ob-skip" href="#ob-stage">観測画面へスキップ</a>
    <div className="ob-wrap">
      <header className="ob-nav"><a href="/" className="ob-brand" aria-label="Connectome Fighter ホーム"><span className="ob-brand-mark" aria-hidden="true">CF</span><span>CONNECTOME<br /><b>FIGHTER</b></span></a><nav aria-label="メインナビゲーション"><a href="/" aria-current={replay ? 'page' : undefined}>REPLAY</a><a href="/live" aria-current={!replay ? 'page' : undefined}>LIVE観測</a><a href="#protocol">実験について</a></nav><span className="ob-nav-note">NEURAL OBSERVATORY <span>01</span></span></header>
      <section className="ob-intro"><div><p className="ob-kicker">CONNECTIVITY → ACTIVITY → BEHAVIOR</p><h1>戦う。その内側を、観る。</h1><p>ゲームの行動と、神経活動から動くショウジョウバエの身体を観測する。</p></div><div className="ob-intro-mode"><span className={`ob-tag ${active ? 'ob-verified' : ''}`}>{replay ? 'RECORDED EVALUATION' : active ? 'LIVE / VERIFIED INPUT' : paused ? 'VIEW PAUSED' : 'LIVE / NOT CONNECTED'}</span><small>{replay ? '録画評価 · LIVEではありません' : '観測専用 · 学習更新なし'}</small></div></section>
      <div className="ob-modebar"><div><span className={`ob-status-dot ${active ? 'is-active' : ''}`} />{replay ? 'CANDIDATE REPLAY' : <span data-testid="arena-status">{status}</span>}</div><div className="ob-controls">{controls}<span className="ob-tag">PIXELS → POLICY: OFF</span></div></div>
      {ci ? <p className="ob-notice">CI functional E2E · loopback上の実runtimeです。本番Vercelの稼働証明ではありません。</p> : null}
      {blocked ? <p className="ob-notice" role="status"><strong>LIVE計算は利用枠の上限で停止しています。</strong> 接続がない状態を録画や擬似活動で置き換えません。<a href="/">評価録画を見る ↗</a></p> : null}
      {paused ? <p className="ob-notice" role="status">表示更新を停止しました。再開時には最新の検証済み入力を取得します。サーバーの計算は操作しません。</p> : null}
      <div {...attributes}>
        <section id="ob-stage" className="ob-stage" aria-label="戦闘と両側の神経活動">
          <BrainPanel side="p1" snapshot={snapshot} replay={replay} />
          <section className="ob-arena ob-panel">
            <div className="ob-panel-heading"><span className="ob-kicker">01 / FIGHTINGICE</span><span className="ob-tag">{replay ? 'REPLAY' : active ? 'OFFICIAL SCREENDATA' : 'AWAITING RUNTIME'}</span></div>
            {replay ? media : <><div className="ob-match"><strong className="p1">{snapshot?.live.p1?.character || 'GARNET'}</strong><span>VS</span><strong className="p2">{snapshot?.live.p2?.character || 'ZEN'}</strong></div><div className="ob-score"><span className="p1">HP {metric(snapshot?.current.p1?.hp)}</span><span>{active ? `ROUND ${snapshot?.current.round} · FRAME ${snapshot?.current.frame}` : 'NO VERIFIED TELEMETRY'}</span><span className="p2">HP {metric(snapshot?.current.p2?.hp)}</span></div><div className="ob-screen">{snapshot ? <img data-testid="game-image" src={snapshot.images[0]} alt="Official FightingICE screen" /> : <Empty title={blocked ? '計算リソース待ち' : paused ? '表示を一時停止' : '検証済みの戦闘を待機中'}>この領域には実FightingICEのScreenDataだけを表示します。</Empty>}</div></>}
            <p className="ob-arena-note">{replay ? '評価動画とLIVE神経観測は別の記録です。録画に未収録の活動は生成しません。' : '戦闘画像は独立サンプリング。神経・身体は実観測履歴の保持入力に照合しています。'}</p>
          </section>
          <BrainPanel side="p2" snapshot={snapshot} replay={replay} />
        </section>
        <section className={`ob-flow ${active ? 'is-active' : ''}`} aria-label="プロジェクト定義の情報経路"><div className="ob-flow-title"><span className="ob-kicker">SIGNAL PATH</span><small>設計上の接続 · 生物学的因果の証明ではない</small></div><div className="ob-flow-steps"><span>ゲーム観測</span><i>→</i><span>感覚入力</span><i>→</i><strong>MaleCNS / LIF</strong><i>→</i><span>運動出力</span><i>→</i><div><span>ゲームaction</span><small>＋ adapter → FlyBody</small></div></div></section>
        <div className="ob-section-title"><div><span className="ob-kicker">02 / PHYSICAL EMBODIMENT</span><h2>同じ神経活動、もうひとつの身体。</h2></div><p>FightingICEとは独立した、実MuJoCo物理。</p></div>
        <div className="ob-bodies"><BodyPanel side="p1" snapshot={snapshot} replay={replay} /><BodyPanel side="p2" snapshot={snapshot} replay={replay} /></div>
      </div>
      {!replay ? <section className="ob-timeline ob-panel"><div className="ob-panel-heading"><div><span className="ob-kicker">03 / OBSERVED DECISIONS</span><h2>行動の記録</h2></div><span className="ob-caption">この閲覧中の直近8記録 · 欠落なしのreplayではない</span></div>{active && moments.length ? <ol>{moments.map(moment => <li key={moment.key}><span>R{moment.round} / F{moment.frame}</span><strong className="p1">{moment.p1}</strong><strong className="p2">{moment.p2}</strong></li>)}</ol> : <p className="ob-caption">検証済みの観測記録が得られるまで、タイムラインを描画しません。</p>}<a href="/">Candidateの更新・評価履歴へ ↗</a></section> : null}
      {children}
      <Protocol snapshot={snapshot} />
      <footer className="ob-footer"><span>CONNECTOME FIGHTER / AN AUDITABLE EXPERIMENT</span><span>MaleCNS anatomy · Shiu LIF · project-defined interfaces</span><a href="https://unjuno.github.io/connectome-fighter/">Research ledger ↗</a></footer>
    </div>
  </main>;
}
