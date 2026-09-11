# Rolling Spectator Pipeline

## 目的

Connectome Fighter の観戦系は「真のリアルタイム配信」ではなく、**実際の FightingICE 対戦を約1分のクリップとして継続生成し、最新3本をキューで入れ替える擬似ライブ**として運用する。

重い神経シミュレーションは GitHub Actions、表示は Vercel に分離する。ローカルPCは不要。

```text
GitHub Actions (hourly)
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
rolling Release assets + queue.json
  ↓
Vercel /connectome polls every 30 s
  ↓
NOW / PREVIOUS 1 / PREVIOUS 2
```

## 実証済み条件

- canonical controller: MaleCNS v1.0 + pinned Shiu LIF
- FightingICE v7.1 / pyftg 2.3
- 6 rounds / clip
- approximately 56–61 s per clip
- 960×640 H.264 video
- `policy_pixel_access=false`
- latest + previous two clips retained
- Vercel polls state every 30 s; a new clip does not require a Vercel redeploy
- countdown uses `next_expected_at`
- all six character pairings rotate by workflow run number
- after one six-pair epoch, character-specific Poisson seeds advance by 1,000,000 so later epochs do not replay exactly the same stochastic sequence

## 脳活動表示

### Decision-window activity

For each P1/P2 brain, raw spike events are retained by real MaleCNS `body_id`. The public queue contains compact activity samples for each LIF decision window:

- total spike count
- unique active bodies
- top `somaNeuromere`
- top `superclass`
- top `type`
- top active body IDs

The spectator maps each decision window over the video duration and selects the nearest activity sample from the current playback time. This is a visualization alignment; it does not modify the controller.

### Released SWC morphology

The flat MaleCNS annotation table does **not** contain physical `pos_x/pos_y/pos_z` fields, so coordinates are not invented.

Instead, the spectator retrieves the officially released MaleCNS centerline SWC skeleton for the most active bodies after the fight:

`https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc/<bodyId>.swc`

Current public visualization:

- coordinate space: MaleCNS EM
- coordinate units: 8 nm
- projection: X–Z
- up to 6 highly active bodies per fighter
- up to 180 centerline segments per body for browser rendering
- bodies active in the current decision window are drawn brighter/thicker

This morphology is **post-hoc spectator data only**. It is never passed to the policy or plasticity code.

## Rolling storage contract

GitHub prerelease tag: `spectator-latest`

Stable assets:

- `latest-fight.mp4`
- `previous-1.mp4`
- `previous-2.mp4`
- `video.json`
- `queue.json`

`site/data/queue.json` is also committed as a small public state pointer for the Vercel proxy.

## Vercel viewer

Viewer repository: `Unjuno/live`

Routes:

- `/connectome` — spectator UI
- `/api/connectome/state` — no-store proxy for queue / match / status JSON

Production viewer:

`https://liveunjuno.vercel.app/connectome`

UI includes:

- current clip and previous two clips
- countdown until next expected clip
- 4-character W/L/D and win rate
- FightingICE video
- synchronized P1/P2 MaleCNS activity
- released SWC morphology projection
- body IDs / cell types / structural categories
- recent experiment logs
- Actions evidence links

## Scientific boundary

The spectator must never be confused with the policy path.

- Screen pixels: spectator only
- SWC geometry: spectator only
- structural annotations: post-hoc analysis only
- action selection: numeric FightingICE observation → Poisson sensory input → MaleCNS/Shiu LIF → spike-count readout

The visualization can identify recruited structures and candidate pathways. It does not establish causal circuit function without intervention/ablation.

## Learning state

Continuous reward-driven learning remains **OFF** while this spectator contract is being frozen.

Existing reward/plasticity/checkpoint workflows are engineering smoke evidence only unless explicitly promoted into the production learning lineage after the reward-design gate.
