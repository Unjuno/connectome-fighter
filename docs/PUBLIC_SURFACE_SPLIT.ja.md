# Public LIVE / research ledger split

## 目的

Connectome Fighter の公開面を2つに分離する。

1. **Vercel public LIVE** — 全 viewer が同じ1本の FightingICE/MaleCNS process を見る共有 read-only inference 面。
2. **GitHub Pages / Actions research ledger** — training、reward、plasticity、checkpoint lineage、runtime provenance、実験条件、normalized/public logs、raw evidence を保持する研究面。

Vercel を学習ログや研究履歴の system of record にしない。研究上の再現性・学習証拠・provenance は GitHub 側で担保する。

## Vercel public LIVE

公開URL: `https://liveunjuno.vercel.app/connectome`

現行 primary arena は **single shared live broadcast** である。viewer ごとに対戦を作らない。固定名 `connectome-live-broadcast` の Vercel Sandbox を1つだけ配信対象とし、全 viewer が同じ stream / telemetry を見る。

共有 LIVE contract:

- public broadcast target は常に1つ
- viewer 数に応じて FightingICE / MaleCNS Sandbox を増やさない
- public viewer から個別 match を POST 生成できない
- `learning_enabled=false`
- `policy_pixel_access=false`
- immutable runtime は runtime archive SHA に対応する persistent runtime snapshot から供給する
- terminal/stopped shared Sandbox は current runtime base から recycle する
- Vercel 上では checkpoint/weight を更新しない
- recorded fight を LIVE として代替しない

現行 LIVE matchup は **GARNET approved generation-2 inference vs ZEN canonical baseline**。ZEN generation-2 candidate は production LIVE に serve していないため、trained-vs-trained とは表現しない。

Vercel で表示するもの:

- 共有 LIVE の P1/P2、HP、position、action、round/frame telemetry
- 両側 MaleCNS の decision-window activity
- released MaleCNS SWC 由来の X–Z morphology / anatomical context
- connection / warming / error state
- runtime SHA / runtime-base / supervisor state
- GARNET approved と ZEN/LUD/NEZ candidate の明示的な provenance 区分
- FightingICE telemetry に同期した fly-shaped visualization

fly visualization の position / facing / action は live FightingICE telemetry 由来。wingbeat は presentation-only であり、実 Drosophila locomotor biomechanics の再現とは主張しない。

Vercel で行わないもの:

- learning / weight update
- long-term match ledger の保存
- reward/plasticity rationale を runtime state として扱うこと
- optimizer/training history の保持
- screen pixels / SWC geometry / decorative graphics の policy input 化

LIVE が利用不能なら warming/error を表示し、架空の活動や録画を LIVE として補わない。

## GitHub research / training ledger

公開URL: `https://unjuno.github.io/connectome-fighter/`

GitHub を以下の公開元とする。

- canonical substrate / dynamics
- baseline/evaluation workflows
- reward / plasticity experiment contracts
- normalized/public match logs
- checkpoint lineage / resume evidence
- approved inference handoff
- arena runtime provenance / checksums
- GitHub Actions artifacts / logs
- interpretation boundaries

Production reward-driven learning は現在 **OFF**。reward/plasticity/checkpoint の既存 workflow は、明示的に昇格されない限り research / engineering evidence であり continuous production learning lineage ではない。

Pages は current runtime proof を `site/data/runtime-proof.json` から読み、runtime SHA / base / snapshot / observed telemetry を表示する。

## Training → LIVE inference handoff

研究 checkpoint を mutable Vercel state として直接扱わない。

`publish-arena-inference-snapshot` が approved canonical checkpoint から read-only inference に必要な state を抽出し、`arena-inference-latest` release へ公開する。

handoff manifest では最低限以下を検証する。

- character
- generation
- state filename
- state SHA-256
- canonical model identifier
- read-only inference contract

reward formula、plasticity rationale、match ledger、研究履歴は handoff と分離する。

### checkpoint lineage の現在地

- **GARNET generation 2** — approved read-only inference state。現行 production LIVE で使用。
- **ZEN generation 2** — candidate cross-run lineage。production learned inference へ未昇格。
- **LUD generation 2** — candidate cross-run lineage。production learned inference へ未昇格。
- **NEZ generation 2** — candidate cross-run lineage。production learned inference へ未昇格。

したがって「4キャラすべてに cross-run-resumable lineage evidence がある」とは言えるが、「4キャラ production-trained league が成立した」とは言わない。

## Runtime snapshot / compilerless Cython boundary

Vercel runtime bundle を viewer ごとに再取得・再構築しない。runtime archive SHA-addressed persistent Sandbox へ stage し、その filesystem snapshot を固定 shared LIVE Sandbox の起点にする。

runtime base には immutable runtime を置き、character inference state は `arena-inference-latest` の manifest/SHA で別途検証する。

Brian2 canonical codegen target は **Cython**。Vercel Sandbox に C compiler が無いため、GitHub Actions で production executable path identity を再現して Cython extension cache を事前 compile し、compiler を利用不能にした再起動でも同じ MaleCNS worker が `ready` になることを release gate にする。

これは deployment/cold-start/portability 対策であり、MaleCNS topology や Shiu dynamics の変更ではない。

## Current production inference proof — 2026-09-12

検証済み runtime evidence:

- archive SHA-256: `f4016e3a2f79968a3305818ad3b4ef2197802e36c647660c1ab524b098f27205`
- archive size: `439024170` bytes
- runtime base: `connectome-runtime-f4016e3a2f79968a`
- runtime snapshot: `snap_s5HpePEfgiNNAsLgE9UKsvOVwY5u`
- Python `3.10.21` / Brian2 `2.5.1` / Cython `0.29.36` / NumPy `1.24.0`
- included neurons: `156675`
- runtime recurrent synapses: `6025920`
- compilerless cache reuse verified
- cache: `30 files / 15 shared objects / 5776256 bytes`
- cache tree SHA-256: `772cf23de36484d12e9355334f116bad71b8a8d30e42531cc93b90e3670dcd92`
- host-specific `-march=native` excluded
- real FightingICE frame advancement verified
- P1/P2 MaleCNS decision telemetry verified
- compilerless release E2E: Actions `34690428080` — PASS
- independent production smoke: Actions `34690567057` — PASS

proof telemetry は **round 1 / frame 181 / GARNET decision 3 / ZEN decision 3 / P1 9245 spikes / P2 9098 spikes** を観測した。

proof bout は **GARNET approved generation-2 inference vs ZEN canonical baseline**。これは Vercel 上の production inference plumbing の証拠であり trained-vs-trained performance の証拠ではない。

Machine-readable proof: [`site/data/runtime-proof.json`](../site/data/runtime-proof.json)

## Shared LIVE handoff timing

Public broadcastだけ `post-fight=1s` / `post-session=1s` を既定値とし、通常one-shot診断は30秒既定を維持する。

新runtime採用後のサンプリングでは、旧bout running を `11:15:47Z`、新bout booting を `11:15:54Z`、同じ新bout running を `11:16:01Z` に観測した。これは厳密なdowntime測定値ではなくサンプリング上限だが、旧30秒+30秒の意図的terminal holdは再現していない。

## Public Surface Freeze gate

Reward tuning / continuous learning を進める前に以下を固定する。

1. `/api/connectome/live` が `single-shared-live-broadcast` / `shared-global` を返す
2. `connectome-live-broadcast` だけが public broadcast target である
3. public individual-session POST が拒否される
4. `learning_enabled=false` / `policy_pixel_access=false`
5. runtime archive SHA と runtime-base identity が一致する
6. `frame > 0`、両 MaleCNS decision、x/y/action telemetry を production smoke で確認する
7. GARNET approved と ZEN/LUD/NEZ candidate を UI/README/STATUS/ROADMAP/Pages で混同しない
8. stopped shared Sandbox から自動復旧できる
9. failure/warming state を明示し fake LIVE fallback を作らない
10. compilerless release E2E と独立production smokeが同じshared-LIVE contractを検証する

## Historical recorded spectator

以前の `latest-fight.mp4 / previous-1 / previous-2 / queue.json` rolling spectator は renderer / H.264 / activity timeline / SWC export の regression evidence として残す。

これは現行 production LIVE ではない。毎時 schedule は停止済みで、必要時の manual/regression workflow としてのみ使う。

## Scientific boundary

- MaleCNS anatomy: canonical biological structure
- pinned Shiu LIF: canonical dynamics layer
- Brian2 Cython precompile/cache: deployment optimization
- game observation → sensory input: project-defined experimental interface
- FightingICE reward: project-defined reinforcement signal
- game reward → plasticity mapping: project-defined learning assumption
- SWC/context-atlas/fly visualization: spectator only

Vercel へ inference state を渡しても、この境界は変わらない。
