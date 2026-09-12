# Public LIVE / research ledger split

## 目的

Connectome Fighter の公開面を明確に分離する。

1. **Vercel public LIVE** — 全 viewer が同じ1本の FightingICE/MaleCNS process を見る shared read-only inference 面。
2. **GitHub Pages / Actions research ledger** — training、reward、plasticity、checkpoint lineage、runtime provenance、public logs、raw evidence を保持する研究面。

Vercel を学習履歴の system of record にしない。研究再現性と provenance は GitHub 側で担保する。

## Vercel public LIVE

公開URL: `https://liveunjuno.vercel.app/connectome`

現行 primary arena は **single shared live broadcast**。固定名 `connectome-live-broadcast` の1つだけを配信対象とし、viewer 数に応じて FightingICE / MaleCNS process を増やさない。

固定 contract:

- `mode=single-shared-live-broadcast`
- `audience_scope=shared-global`
- public individual-session POST は拒否
- `learning_enabled=false`
- `policy_pixel_access=false`
- immutable runtime は runtime archive SHA-addressed persistent snapshot から供給
- public process は1 bootstrapで **6 rounds** を実行
- viewer の `/api/connectome/live` read は同じ shared session の heartbeat としてのみ使う
- session expiry が近い場合だけ同一sessionを延長し、viewer-specific processは作らない
- viewer がいなければ audience-driven extension は発生しない
- Vercel 上で weight/checkpoint を更新しない
- recorded fight を LIVE として代替しない

現行 matchup は **GARNET approved generation-2 inference vs ZEN canonical baseline**。ZEN/LUD/NEZ generation-2 candidate は production learned fighter として serve していない。

## Neural activity → action → fight

同一 decision window について次を同期表示する。

1. real MaleCNS sensory body ID + Poisson rate
2. whole-network spikes / active bodies / biological time window / membrane summary
3. real output-body motor contribution
4. `FORWARD/BACKWARD/UP/DOWN/A/B/C` 7群の spike counts
5. selected action + actual FightingICE x/y / facing / HP

fly glyph の位置は FightingICE 実座標、pose は selected action、damage pulse は実 HP loss に従う。ランダムな「ハエっぽい」移動は加えない。released spatial coordinate がない body ID は **non-spatial activity index** として表示し、架空の解剖座標を作らない。

## GitHub research / training ledger

GitHub は以下の system of record:

- canonical substrate / dynamics / interface
- baseline/evaluation workflows
- reward / plasticity contracts
- checkpoint lineage / resume evidence
- approved inference handoff
- normalized/public match logs
- runtime provenance / checksum
- Actions artifacts / logs

**Production reward-driven learning は現在 **OFF****。既存reward/plasticity evidenceは、明示的に昇格するまで continuous production learning lineage ではない。

## Training → LIVE handoff

Approved checkpoint から read-only inference に必要なstateのみ `arena-inference-latest` へ公開し、state/metadata SHA をVercel側で検証する。

- GARNET G2 — approved inference / LIVEでserve
- ZEN G2 — candidate lineage
- LUD G2 — candidate lineage
- NEZ G2 — candidate lineage

「4キャラすべてにcross-run lineage evidenceがある」とは言えるが、「4キャラproduction-trained league」とは言わない。

## Runtime snapshot / compilerless Cython

Canonical backend は **Brian2 Cython**。Vercel SandboxにはC compilerがないため、GitHub Actionsでproduction path identityを再現してcacheをprecompileし、compiler無しでもworker `ready` をgateする。

runtime bundleはviewerごとに再構築せず、runtime SHA-addressed persistent Sandbox snapshotをshared LIVEの起点にする。

## Current production inference proof — 2026-09-12

- archive SHA-256: `f304bc4f0e7c19faca517a550f36dd566cb2f8b34e9a33627370aa3fec074004`
- archive size: `439021953` bytes
- runtime base: `connectome-runtime-f304bc4f0e7c19fa`
- runtime snapshot: `snap_GnmkXhXrF8QAbow2cxdqDq3q9rL5`
- Python `3.10.21` / Brian2 `2.5.1` / Cython `0.29.36` / NumPy `1.24.0`
- 156675 neurons / 6025920 recurrent synapses
- compilerless cache reuse verified
- telemetry schema: **v3**
- shared process: **6 rounds**
- compilerless release E2E: Actions `34700529205` — PASS
- strict production causal-LIVE smoke: Actions `34700813732` — PASS

strict smoke sample: round 1 / frame **421** / GARNET decision **7** / ZEN decision **7** / 8971 vs 8813 whole-network spikes。両側 action は `B` で、B group がそれぞれ 55 / 56 spikes と最大。real sensory drive / real motor contributors も同じ decision window に存在する。

Machine-readable proof: [`site/data/runtime-proof.json`](../site/data/runtime-proof.json)

## Shared LIVE lifecycle

Public process は6 roundsをwarmに維持し、viewer heartbeatはsession期限が近い場合だけ同一sessionを延長する。supervisor command timeoutはVercel Sandboxの5時間上限に合わせる。idle時は無制限常駐させない。

## Public Surface Freeze gate

Reward tuning / continuous learning 前に以下を固定する。

1. shared-globalの単一broadcast
2. per-viewer session禁止
3. learning/policy-pixel OFF
4. runtime SHA/base/snapshot一致
5. schema-v3 + 6-round warm process
6. actual FightingICE x/y/HP/action + both MaleCNS decisions
7. sensory drive + motor contributors
8. 7 action groups + selected-action整合
9. approved/candidate provenance分離
10. fake LIVE fallbackなし

## Historical recorded spectator

旧 `latest-fight.mp4 / previous-* / queue.json` はrenderer/H.264/SWC regression evidenceとして残すだけで、production LIVEではない。**毎時 schedule は停止済み**。

## Scientific boundary

MaleCNS anatomy、pinned Shiu LIF、project-defined game I/O、reward/plasticity、spectator visualizationは別layerとして扱う。Vercelへのinference handoffでこの境界は変えない。
