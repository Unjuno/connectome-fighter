# Public spectator / research ledger split

## 目的

Connectome Fighter の公開面を2つに分離する。

1. **Vercel public arena** — viewerごとの短命Sandboxでread-only推論対戦を実行し、FightingICE telemetryと両MaleCNSの活動を見せる。
2. **GitHub Pages / Actions research ledger** — 報酬、plasticity、checkpoint lineage、runtime provenance、実験条件、raw evidenceを残す。

Vercel側を研究ログの保存先にしない。研究上の説明可能性と再現性はGitHub側で担保する。

## Vercel public arena

公開URL: `https://liveunjuno.vercel.app/connectome`

現行のprimary arenaは録画再生ではなく、**per-viewer live inference session** である。

viewerが対戦を開始すると、Vercelは現在のruntime release SHAに対応するpersistent runtime snapshotから短命Sandboxをforkし、そこでFightingICE v7.1 + MaleCNS v1.0 + pinned Shiu LIFを起動する。承認済みcharacter stateが存在する場合は `arena-inference-latest` のmanifestとSHA-256を検証してread-onlyでmaterializeする。

保持・表示するもの:

- current ephemeral FightingICE inference session
- P1/P2 character、HP、position、action、round/frame telemetry
- 両側MaleCNSのdecision windowごとのspike activity
- released MaleCNS morphologyのX–Z投影 / reference morphology
- 短命sessionの状態

研究面の長期記録として保持・表示しないもの:

- 長期match ledger
- reward formula
- plasticity rationale
- checkpoint training history
- optimizer / experiment history
- Actions raw logs

録画clipやreference morphology payloadが補助表示に使われる場合があっても、**live fightの代替として録画を偽装しない**。live runtimeが利用不能ならその状態を表示する。

## GitHub research ledger

公開URL: `https://unjuno.github.io/connectome-fighter/`

公開するもの:

- canonical substrate / dynamics
- current phase
- reward contract (`R2d-v0`)
- plasticity contract (`KC-MBON-valence-depression-v0`)
- 固定比較条件
- normalized match ledger
- checkpoint smoke releases
- arena runtime / inference handoff provenance
- GitHub Actions evidence
- interpretation boundaries

GitHub Pages deploy時に `configs/` のcanonical JSONを `site/research-data/` へコピーするため、表示用の手入力値と実際の設定が乖離しないようにする。

## Training → arena inference handoff

研究checkpointをそのままVercelの表示データとして扱わない。

GitHub Actionsの `publish-arena-inference-snapshot` が、承認済みcanonical checkpointから**推論に必要なstateのみ**を抽出して `arena-inference-latest` releaseへ公開する。

handoff manifestには以下だけを含める。

- character
- generation
- state file name
- state SHA-256
- canonical model identifier
- read-only inference contract

reward式、plasticity rationale、match ledger、研究履歴はhandoffに埋め込まない。

### checkpoint lineage の現在地

- **GARNET generation 2** — `arena-inference-latest` に承認済みのread-only inference state。現行public arenaが利用できる学習済みstateはこれだけ。
- **ZEN / LUD / NEZ generation 2** — `canonical-missing-lineage-smoke-v1` で、各キャラ独立state・RNG・履歴を持つgeneration 1 seedと、別GitHub Actions runからgeneration 2へresumeするcross-run smokeを実証済み。ただし `R2d-v0` / `KC-MBON-valence-depression-v0` は依然として**candidate smoke contract**であり、これら3キャラはproduction arenaへ未昇格。

したがって「4キャラすべてにcross-run resume可能なcandidate lineageが存在する」とは言えるが、「4キャラproduction-trained leagueが成立した」とはまだ言わない。ZEN/LUD/NEZを `arena-inference-latest` へ入れるには、報酬・plasticity実験の採用判断と明示的なpromotion gateが別途必要。

## Runtime snapshot boundary

Vercel側の実行環境は、GitHub Releaseのruntime bundleをviewerごとに再取得せず、**runtime archive SHA-addressed persistent Sandbox**へ一度だけstageし、そのfilesystem snapshotから短命viewer Sandboxをforkする。

runtime baseにはimmutable runtimeだけを置き、character stateは `arena-inference-latest` のmanifest/SHAで別途検証する。viewer sessionでは `learning_enabled=false`、`policy_pixel_access=false` を固定する。

Brian2のcanonical codegen targetは引き続き **Cython**。Vercel SandboxにはC compilerがないため、GitHub Actionsで同一のVercel `sys.executable` pathを再現してCython extension cacheを事前compileし、compilerをPATHから除いた再起動でも同一MaleCNS workerがreadyになることをrelease gateで検証する。

CPU固有命令による移植性事故を避けるため、release cacheはBrian2 2.5.1の既定GCC flagsから `-march=native` のみ除外して再生成する。既存cacheは再pack前に破棄し、host-specific `.so` を継承しない。

このruntime snapshot / precompiled cacheは計算環境のcold-start・portability対策であり、学習checkpointの承認状態やcanonical dynamicsを変更しない。

## Production inference proof — 2026-09-12

GitHub Actions `precompile-arena-brian2-cython-cache` run **34663496545** で、portable compilerless runtimeからVercel実機のend-to-end inferenceを確認した。

検証されたruntime evidence:

- archive SHA-256: `b4511a0d5287384d2ca130ef58b40adb2786c6b0968ec961d5b41af13441d510`
- Vercel runtime base: `connectome-runtime-b4511a0d5287384d`
- Vercel snapshot: `snap_W1KOgl6TIUSgK4k8D6lpR29wcAhX`
- Brian2 `2.5.1` / Cython `0.29.36` / NumPy `1.24.0`
- canonical included neurons: `156675`
- canonical runtime synapses: `6025920`
- precompiled Cython shared objects: `15`
- `compilerless_reuse_verified: true`
- `host_specific_march_native: false`

Vercel上のproof boutは **GARNET approved generation-2 checkpoint vs ZEN canonical baseline**。観測時点で round 1 / frame 61、P1 decision index 1、P2 decision index 1まで進み、両brainから実spike telemetry（P1 5458、P2 4965）が返った。これはVercel Sandbox上でFightingICEと2つのMaleCNS workerが実際にdecisionを生成したことのruntime proofである。

このproofは **trained-vs-trainedの証拠ではない**。ZENはapproved learned checkpointではなくcanonical baselineとして参加している。

## Scientific boundary

- MaleCNS anatomy: canonical biological structure
- pinned Shiu LIF: canonical dynamics layer
- Brian2 Cython precompile/cache: deployment optimization; dynamicsの置換ではない
- game observation → sensory input: project-defined experimental interface
- FightingICE reward: project-defined reinforcement signal
- game reward → valence/plasticity mapping: project-defined learning assumption
- SWC/video/reference visualization: post-hoc spectator only

Vercelへ推論stateを渡しても、この境界は変わらない。
