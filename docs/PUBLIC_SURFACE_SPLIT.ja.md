# Public LIVE / research ledger split

## 目的

Connectome Fighter の公開面を2つに分離する。

1. **Vercel public LIVE** — 全viewerが同じ1本のFightingICE対戦を見る共有配信面。Vercelではread-only推論のみを行う。
2. **GitHub Pages / Actions research ledger** — 学習、報酬、plasticity、checkpoint lineage、runtime provenance、実験条件、normalized/public logs、raw evidenceを公開する研究面。

Vercelを学習ログや研究履歴の保存先にしない。研究上の説明可能性・再現性・学習の証拠はGitHub側で担保する。

## Vercel public LIVE

公開URL: `https://liveunjuno.vercel.app/connectome`

現行のprimary arenaは **single shared live broadcast** である。viewerごとに対戦を作らない。固定名 `connectome-live-broadcast` のVercel Sandboxを1つだけ配信対象とし、全viewerが同じstream / telemetryを見る。

共有LIVEのcontract:

- public broadcast targetは常に1つ
- viewer数に応じてFightingICE / MaleCNS Sandboxを増やさない
- public viewerから個別matchをPOST生成しない
- `learning_enabled=false`
- `policy_pixel_access=false`
- immutable runtimeはruntime archive SHAに対応するpersistent runtime snapshotから供給する
- bout終了後は同じ共有Sandbox内で次boutを開始する
- Vercel上では重み更新を行わない

現行LIVE matchupは **GARNET approved generation-2 checkpoint vs ZEN canonical baseline**。ZENはapproved learned checkpointではないため、trained-vs-trainedとは表現しない。

Vercelで表示するもの:

- 共有LIVEのP1/P2、HP、position、action、round/frame telemetry
- 両側MaleCNSのdecision-window spike activity
- released MaleCNS SWC由来のX–Z morphology / anatomical context atlas
- 共有LIVEの接続・warming状態

Vercelで研究履歴として保持・表示しないもの:

- 長期match ledger
- reward formula
- plasticity rationale
- checkpoint training history
- optimizer / experiment history
- Actions raw logs

録画clipをLIVEの代替として偽装しない。LIVEが利用不能ならwarming/errorを表示する。

### spectator morphology boundary

背景の `malecns-context-atlas-v1` は、official MaleCNS v1.0 released SWCから決定論的に層化した**代表サンプル**である。128 bodies / 6,087 X–Z segmentsを含み、21 soma neuromeres、17 superclasses、左右root sideをカバーする。

これは156k neuronsの完全描画ではない。liveで強調する神経活動もspectator-onlyであり、policy inputには入れない。

## GitHub research / training ledger

公開URL: `https://unjuno.github.io/connectome-fighter/`

GitHubを以下の公開元とする。

- canonical substrate / dynamics
- training workflows
- reward contract (`R2d-v0`)
- plasticity contract (`KC-MBON-valence-depression-v0`)
- 固定比較条件
- normalized/public match logs
- checkpoint lineage / resume evidence
- approved inference handoff
- arena runtime provenance
- GitHub Actions artifacts / checksums / logs
- interpretation boundaries

学習処理はGitHub Actions側で行う。Vercelは学習済みとして承認されたstateをread-only inferenceへ渡すだけで、学習履歴を持たない。

GitHub Pages deploy時には `configs/` のcanonical JSONを `site/research-data/` へコピーし、公開説明と実設定の乖離を防ぐ。

## Training → LIVE inference handoff

研究checkpointをそのままVercelの内部状態として扱わない。

GitHub Actionsの `publish-arena-inference-snapshot` が、承認済みcanonical checkpointから**推論に必要なstateのみ**を抽出して `arena-inference-latest` releaseへ公開する。

handoff manifestに含めるもの:

- character
- generation
- state file name
- state SHA-256
- canonical model identifier
- read-only inference contract

reward式、plasticity rationale、match ledger、研究履歴はhandoffに埋め込まない。

### checkpoint lineage の現在地

- **GARNET generation 2** — `arena-inference-latest` のapproved read-only inference state。現行共有LIVEで利用する学習済みstate。
- **ZEN / LUD / NEZ generation 2** — `canonical-missing-lineage-smoke-v1` で独立state・RNG・履歴とcross-run generation resumeを実証済み。ただしcandidate lineageでありproduction LIVEへ未昇格。

したがって「4キャラすべてにcross-run resume可能なcandidate lineageがある」とは言えるが、「4キャラproduction-trained leagueが成立した」とは言わない。

## Runtime snapshot / compilerless Cython boundary

Vercel runtimeはGitHub Releaseのruntime bundleをviewerごとに再取得しない。runtime archive SHA-addressed persistent Sandboxへ一度stageし、そのfilesystem snapshotを共有LIVE Sandboxの起点にする。

runtime baseにはimmutable runtimeだけを置き、character stateは `arena-inference-latest` のmanifest/SHAで別途検証する。

Brian2のcanonical codegen targetは **Cython**。Vercel SandboxにC compilerがないため、GitHub ActionsでVercelと同一の`sys.executable` pathを再現してCython extension cacheを事前compileし、compilerをPATHから除いた再起動でも同じMaleCNS workerがreadyになることをrelease gateで検証する。

CPU固有命令による移植性事故を避けるため、Brian2 2.5.1の既定GCC flagsから `-march=native` を除外してcacheを再生成する。既存host-specific cacheは再pack前に破棄する。

これはdeployment/cold-start/portability対策であり、MaleCNS topologyやShiu dynamicsの変更ではない。

## Production inference proof — 2026-09-12

GitHub Actions `precompile-arena-brian2-cython-cache` run **34663496545** で、portable compilerless runtimeからVercel実機end-to-end inferenceを確認した。

検証されたruntime evidence:

- archive SHA-256: `b4511a0d5287384d2ca130ef58b40adb2786c6b0968ec961d5b41af13441d510`
- Vercel runtime base: `connectome-runtime-b4511a0d5287384d`
- Vercel snapshot: `snap_W1KOgl6TIUSgK4k8D6lpR29wcAhX`
- Brian2 `2.5.1` / Cython `0.29.36` / NumPy `1.24.0`
- included neurons: `156675`
- runtime synapses: `6025920`
- precompiled Cython shared objects: `15`
- `compilerless_reuse_verified: true`
- `host_specific_march_native: false`

proof boutは **GARNET approved generation-2 checkpoint vs ZEN canonical baseline**。round 1 / frame 61、P1 decision index 1、P2 decision index 1、P1 spikes 5458、P2 spikes 4965を確認した。これはVercel上でFightingICEと2つのMaleCNS workerが実decisionを生成したruntime proofであり、trained-vs-trainedの証拠ではない。

2026-09-12にはVercel公開面も固定名 `connectome-live-broadcast` の**single shared live broadcast**へ変更し、`ready=true` / `status=running` / shared `/events` streamを確認した。viewerごとのmatch作成endpointは無効化している。

## Scientific boundary

- MaleCNS anatomy: canonical biological structure
- pinned Shiu LIF: canonical dynamics layer
- Brian2 Cython precompile/cache: deployment optimization; dynamicsの置換ではない
- game observation → sensory input: project-defined experimental interface
- FightingICE reward: project-defined reinforcement signal
- game reward → valence/plasticity mapping: project-defined learning assumption
- SWC/context-atlas/live visualization: spectator only

Vercelへ推論stateを渡しても、この境界は変わらない。
