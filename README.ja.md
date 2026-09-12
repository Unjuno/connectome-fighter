# Connectome Fighter

FightingICE を対戦環境として、**MaleCNS v1.0 の実 Drosophila connectome** を pinned Shiu LIF dynamics で動かし、実 body ID の神経活動、checkpoint lineage、runtime provenance を公開する研究・実装基盤です。

**[Public LIVE](https://liveunjuno.vercel.app/connectome)** · [GitHub Pages research ledger](https://unjuno.github.io/connectome-fighter/) · [Status](docs/STATUS.md) · [Roadmap](ROADMAP.md) · [English](README.md)

## Canonical control path

```text
FightingICE 数値観測
  → project-defined Poisson sensory interface
  → MaleCNS v1.0 connectivity
  → pinned Shiu LIF dynamics
  → real output-body spike counts
  → versioned action groups
  → FightingICE action
```

MLP / RNN / PPO 等を MaleCNS の代用品として canonical policy path に置きません。game I/O mapping は人工的な実験 interface であり、native Drosophila sensorimotor semantics とは主張しません。

## Production 公開構成

Vercel は **1つの shared read-only LIVE broadcast** だけを提供します。viewer ごとに FightingICE/MaleCNS process を増やしません。

```text
approved inference state + SHA-addressed runtime snapshot
  → connectome-live-broadcast
  → FightingICE + 2 MaleCNS/Shiu workers
  → shared SSE/state telemetry
  → 全 viewer が同じ戦闘を見る
```

視聴者がいる間は `/api/connectome/live` の共有 heartbeat により、同じ Sandbox session の期限が近づいた場合だけ延長します。viewer がいなくなれば heartbeat も止まり、ephemeral LIVE Sandbox は自然終了できます。public broadcast は1 bootstrapで **6 rounds** を連続実行し、roundごとの再起動を避けます。

固定境界:

- `mode=single-shared-live-broadcast`
- `audience_scope=shared-global`
- `learning_enabled=false`
- `policy_pixel_access=false`
- public viewer から個別 match を POST 作成できない
- screen pixels / visualization は policy input に入らない
- recorded clip を LIVE の代替にしない

## Neural activity → action → fight

Public LIVE は同一 decision window について次を同期表示します。

1. real MaleCNS sensory body ID と Poisson drive rate
2. whole-network spike load / active body count / membrane summary
3. real output-body motor contribution
4. `FORWARD/BACKWARD/UP/DOWN/A/B/C` の7 action-group spike counts
5. selected action と、その action が実行された FightingICE の x/y・HP・facing

fly glyph の **x/y は実 FightingICE 座標**、pose は selected action、damage pulse は実 HP 低下です。body ID activity は非空間 index として表示し、存在しない解剖座標を捏造しません。

production smoke は schema v3、6-round warm process、sensory drive、motor contributors、7 group counts、selected action と最大 group の一致、実 FightingICE x/y/HP/action を同時に gate します。

## Checkpoint lineage

- **GARNET generation 2 = APPROVED INFERENCE**
- **ZEN generation 2 = CANDIDATE LINEAGE**
- **LUD generation 2 = CANDIDATE LINEAGE**
- **NEZ generation 2 = CANDIDATE LINEAGE**

現行 LIVE は **GARNET approved G2 vs ZEN canonical baseline** です。ZEN/LUD/NEZ の candidate G2 は production learned fighter として serve していません。

## Current production runtime proof

2026-09-12 の current production evidence:

- runtime archive SHA-256: `f304bc4f0e7c19faca517a550f36dd566cb2f8b34e9a33627370aa3fec074004`
- runtime archive size: `439021953` bytes
- runtime base: `connectome-runtime-f304bc4f0e7c19fa`
- runtime snapshot: `snap_GnmkXhXrF8QAbow2cxdqDq3q9rL5`
- Python `3.10.21` / Brian2 `2.5.1` / Cython `0.29.36` / NumPy `1.24.0`
- compilerless Cython cache reuse: **verified**
- **156,675 neurons / 6,025,920 recurrent synapses**
- telemetry schema: **v3**
- shared process: **6 rounds**
- compilerless release E2E: Actions `34700529205` — **PASS**
- strict production causal-LIVE smoke: Actions `34700813732` — **PASS**

Machine-readable proof は [`site/data/runtime-proof.json`](site/data/runtime-proof.json) を正本とします。

## GitHub Pages / Actions

GitHub は研究・学習・provenance の system of record です。

- baseline/public match logs
- reward / plasticity contracts
- checkpoint lineage / hashes
- training workflows
- approved inference handoff
- runtime manifest / checksums
- Actions artifacts / logs

Vercel は read-only inference / presentation surface です。

## 学習 phase

**continuous production reward-driven learning は OFF** です。continuous trainer はまだ production-active ではありません。現在は公開面とruntime contractを固定し、reward/stalemate semantics の変更はその後に比較可能な形で行います。

## Current gate

**Public Surface Freeze** の production 条件は現在、single shared LIVE、schema-v3 causal telemetry、6-round warm process、viewer heartbeat、compilerless Cython、approved/candidate provenance、fake LIVE fallback 不在まで自動検証します。

Reward/plasticity を次段へ進める際も、model/game/interface/runtime/evaluation 条件を固定し、reward だけを独立変数として比較します。

## ライセンス

本リポジトリの新規コードは MIT License。MaleCNS、FightingICE、Shiu model 等の外部成果物には各ライセンス/利用条件が適用されます。