# Historical Rolling Spectator Pipeline

> **現在の production LIVE 仕様ではありません。**
>
> 現在の `/connectome` は Vercel 上の固定 `connectome-live-broadcast` Sandbox で動く **one shared real LIVE** を表示します。本書で説明する rolling MP4 / 3-clip queue は、公式 FightingICE ScreenData、activity timeline、SWC export の回帰検証用に保持している旧 spectator pipeline です。

## 現在の production との関係

現在の production path:

```text
SHA-addressed runtime snapshot
        ↓
connectome-live-broadcast
        ↓
FightingICE + MaleCNS/Shiu
        ↓
/state + /events
        ↓
全 viewer が同じ LIVE を観測
```

現在の LIVE では recorded clip を LIVE として代替しません。`learning_enabled=false`、`policy_pixel_access=false` を維持し、GARNET approved G2 vs ZEN canonical baseline を read-only inference として配信します。

この文書の pipeline は以下の用途に限定します。

- FightingICE 公式 renderer / ScreenData の回帰検証
- H.264 export の検証
- body-ID activity timeline export の検証
- released MaleCNS SWC projection の検証
- archival evidence の生成

毎時 cron は停止済みで、手動 dispatch または実装変更時の regression verification に使います。

## Historical pipeline

```text
GitHub Actions (manual/regression)
  ↓
MaleCNS v1.0 + pinned Shiu LIF
  ↓
FightingICE 6 real rounds
  ↓ separate spectator socket
Official ScreenData 960×640 RGB
  ↓ ffmpeg
~1 minute H.264 MP4
  ↓
body-ID spike logs
  ├─ decision-window structural activity
  └─ released MaleCNS SWC skeleton projection
  ↓
archival Release assets + queue.json
```

この経路は実対戦を録画しますが、現在の Vercel LIVE の入力ではありません。

## 実証済み条件

- canonical controller: MaleCNS v1.0 + pinned Shiu LIF
- FightingICE v7.1 / pyftg 2.3
- 6 rounds / clip
- approximately 56–61 s per clip
- 960×640 H.264 video
- `policy_pixel_access=false`
- latest + previous two archival clips retained
- all six character pairings can be rotated for regression evidence
- character-specific Poisson seeds can advance between epochs

## Decision-window activity

P1/P2 の raw spike event は real MaleCNS `body_id` で保持されます。Archival queue には各 LIF decision window の compact activity sample を含めます。

- total spike count
- unique active bodies
- top `somaNeuromere`
- top `superclass`
- top `type`
- top active body IDs

Recorded video の playback time への対応付けは visualization alignment です。Controller 自体を変更しません。

## Released SWC morphology

flat MaleCNS annotation table には物理 `pos_x/pos_y/pos_z` が存在しないため、座標を捏造していません。

代わりに公式公開 MaleCNS centerline SWC skeleton を使います。

`https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc/<bodyId>.swc`

Regression visualization の条件:

- coordinate space: MaleCNS EM
- coordinate units: 8 nm
- projection: X–Z
- up to 6 highly active bodies per fighter
- up to 180 centerline segments per body
- current decision で active な body を brighter/thicker に描画

Morphology は **spectator/post-hoc data only** で、policy/plasticity input には入りません。

## Archival storage contract

GitHub prerelease tag: `spectator-latest`

Legacy stable assets:

- `latest-fight.mp4`
- `previous-1.mp4`
- `previous-2.mp4`
- `video.json`
- `queue.json`

これらは regression / archival evidence であり、現在の production LIVE state の system of record ではありません。

## Scientific boundary

- Screen pixels: spectator only
- SWC geometry: spectator only
- structural annotations: post-hoc analysis only
- action selection: numeric FightingICE observation → Poisson sensory input → MaleCNS/Shiu LIF → spike-count readout

Visualization から recruitment/candidate pathway は観測できますが、activity correlation だけで causal circuit function は主張しません。因果主張には intervention / ablation が必要です。

## Learning state

Continuous production reward-driven learning は現在 **OFF** です。旧 rolling spectator の有無は training state と無関係です。

現行 public/runtime contract は [`PUBLIC_SURFACE_SPLIT.md`](PUBLIC_SURFACE_SPLIT.md) と [`STATUS.md`](STATUS.md) を正とします。
