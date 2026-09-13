# Connectome Fighter

FightingICE を対戦環境として、**MaleCNS v1.0 の実 Drosophila connectome** を pinned Shiu LIF dynamics で動かし、実 body ID の神経活動、checkpoint lineage、runtime provenance を公開する研究・実装基盤です。

**Dedicated LIVE:** 公開先は repository variable `CONNECTOME_PUBLIC_BASE_URL` で指定します。無関係な Vercel project は Connectome の公開先として扱いません。 · [Research ledger](https://unjuno.github.io/connectome-fighter/) · [Status](docs/STATUS.md) · [Roadmap](ROADMAP.md) · [English](README.md)

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

MLP / RNN / PPO 等を MaleCNS の代用品として canonical policy path に置きません。game I/O mapping は人工的な実験 interface です。

## FlyBody 物理 embodiment

物理ハエは upstream `TuragaLab/flybody` の MuJoCo body を commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26` に固定して使用します。

```text
annotated MaleCNS motor / descending activity
  → project-defined bounded adapter
  → 59 FlyBody actuators
  → MuJoCo physics
  → FlyBody render
```

adapter は `malecns-annotated-motor-to-flybody-tripod-v2`。これは project-defined interface であり、生物学的な motor-neuron→muscle 対応を同定したものとは主張しません。FightingICE の x/y/action を FlyBody の位置やposeにコピーしません。神経 motor drive がゼロなら active gait もゼロです。

## 現在の状態

- MaleCNS v1.0 provenance/import: **PASS**
- pinned Shiu LIF runtime: **PASS**
- 約 **156,675 neurons / 6,025,920 recurrent synapses**
- real MaleCNS-controlled FightingICE: **PASS**
- compilerless Brian2 Cython bundle: **PASS**
- actual FlyBody MuJoCo physics contract: **independent CI PASS**
- FlyBody actuator dimension: **59**
- zero-drive phase invariance: **PASS**
- neural-drive trajectory divergence: **PASS**
- dedicated Next.js public app: **IMPLEMENTED / production deployment verification pending**
- dedicated Vercel shared-LIVE E2E: **NOT YET VERIFIED**
- continuous production reward-driven learning: **OFF**

既存の `Unjuno/live` は Connectome のdeployment targetではなく、dedicated workflowから変更しません。

## Dedicated public architecture

```text
GitHub rolling runtime release
  → SHA-addressed persistent runtime base
     (runtime + FightingICE fonts + OSMesa)
  → connectome-fighter-live-broadcast
  → FightingICE + 2 MaleCNS/Shiu workers
  → Official ScreenData + neural activity + FlyBody physics
  → 全 viewer が同じ broadcast を見る
```

public app はこのrepoの `app/` / `lib/` にあります。control API は `/api/live`、runtime materialization は `/api/runtime-base`。Vercel deployment 自身の `VERCEL_PROJECT_ID` のみを使用し、他projectのIDをhard-codeしません。

Production smoke は `CONNECTOME_PUBLIC_BASE_URL` が設定されている場合だけ実行します。未設定時に別サイトへfallbackしません。

## Runtime publication boundary

`publish-arena-runtime-bundle → precompile-arena-brian2-cython-cache → publish-flybody-runtime-addon` はGitHub releaseだけを更新します。Vercelへのstageは専用Connectome control plane側が行います。

## 学習境界

continuous production learning は **OFF**。candidate training / history は GitHub 側で保持し、Vercel inference state への自動promotionはしません。

## ライセンス

本リポジトリのproject-authored codeはMIT License。MaleCNS、FightingICE、FlyBody等には各ライセンス/利用条件が適用されます。
