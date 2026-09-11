# Status

Canonical production path: **MaleCNS v1.0 anatomy + pinned Shiu et al. 2024 LIF dynamics + FightingICE v7.1**.

Production reward-driven learning is currently **OFF**. Existing reward/plasticity/checkpoint workflows are engineering or exploratory smoke evidence only; they are not the continuously learning production lineage.

## Current production spectator — PASS

The project now has a cloud-only rolling spectator system:

```text
GitHub Actions
  ↓
MaleCNS + pinned Shiu LIF
  ↓
6 real FightingICE rounds
  ↓
official ScreenData spectator stream
  ↓
~1 minute H.264 clip
  ↓
body-ID spike timeline + released MaleCNS SWC morphology
  ↓
latest / previous-1 / previous-2 rolling queue
  ↓
Vercel viewer polls every 30 s
```

Viewer: **https://liveunjuno.vercel.app/connectome**

Detailed contract: [`SPECTATOR_PIPELINE.ja.md`](SPECTATOR_PIPELINE.ja.md).

### Latest regression evidence

Latest validated rolling run: **Actions `34636959865` — PASS**.

- matchup: **LUD vs NEZ**
- characters completed: **6 / 6 rounds each**
- video: **55.7 s**, **557 ScreenData frames**, **10 fps**, **960×640 H.264**
- encoded video bytes: **7,439,678**
- invalid ScreenData frames: **0**
- policy pixel access: **false**
- rolling queue clips: **3**
- P1 activity timeline samples: **60**
- P2 activity timeline samples: **60**
- released SWC morphology: **6 bodies/side**
- SWC fetch failures: **0**
- current character-specific seeds: LUD `3030303`, NEZ `3040404`
- artifact: `10278598106`
- artifact digest: `sha256:c35dd0abd995546d1534c19719ca59376febe7058903231444a6f1804455027c`

Queue at that gate:

1. LUD vs NEZ — 55.7 s — morphology enabled — 60 activity samples/side
2. ZEN vs NEZ — 57.2 s — morphology enabled — 60 activity samples/side
3. ZEN vs LUD — 55.4 s — 60 activity samples/side; this older queue entry predates the morphology payload

A subsequent generated clip replaces the remaining pre-morphology slot automatically.

The viewer does **not** need to redeploy for each clip. `/api/connectome/state` is a no-store Vercel proxy and the client polls every 30 seconds. `next_expected_at` drives the countdown. New `current_clip_id` values automatically move the viewer back to queue slot 0.

## Canonical substrate — PASS

- anatomy: **MaleCNS v1.0**
- dynamics: pinned Shiu et al. reference code commit `2a83ad611cd9768f8c9723fc613ed27761a5feb5`
- game: **FightingICE v7.1 + pyftg 2.3 + Java 21**
- current strict runtime adapter: **156,675 neurons / 6,025,920 recurrent synapses**
- artificial game I/O, reward and project plasticity are versioned separately from biological anatomy/dynamics

The old FlyWire v783 + custom sigmoid recurrent/PPO route is legacy engineering evidence only.

## Canonical live control — PASS

- each fighter uses an independent persistent Brian2 worker process;
- GARNET / ZEN / LUD / NEZ have independent mutable neural state and RNG;
- FightingICE numeric observations drive selected real MaleCNS sensory bodies through observation-dependent Poisson input;
- the whole pinned Shiu LIF network advances;
- selected real output-body spike groups choose the FightingICE action using spike-count argmax;
- no epsilon-greedy/random action injection is currently used;
- all body-ID spike events are retained for post-hoc analysis.

## Four-character baseline — PASS

`.github/workflows/malecns-baseline-batch.yml` runs all six pairings:

- GARNET–ZEN
- GARNET–LUD
- GARNET–NEZ
- ZEN–LUD
- ZEN–NEZ
- LUD–NEZ

Baseline weights remain unchanged. Logged results populate the four-fighter W/L/D display and analysis dataset.

The rolling spectator uses the same Poisson mechanism but advances character seed blocks after a full six-pair spectator epoch, avoiding an indefinitely repeated stochastic trajectory.

## Spectator video — PASS

The primary video is not the older rectangle reconstruction.

- FightingICE headless rendering produces official `ScreenData` RGB frames;
- a **separate** pyftg spectator stream receives them;
- the controller never receives pixels;
- ffmpeg encodes H.264;
- six real 600-frame rounds create approximately one minute of footage;
- stable rolling release assets are `latest-fight.mp4`, `previous-1.mp4`, `previous-2.mp4`.

## Playback-synchronized neural activity — PASS

For each fighter, the public queue contains compact decision-window samples derived from the recorded spike log:

- total spikes;
- unique active body IDs;
- top `somaNeuromere`;
- top `superclass`;
- top `type`;
- top active body IDs.

There are typically **60 decision samples per side** for a six-round clip at the current 60-frame decision interval. The viewer selects the sample nearest the current video playback position.

This time alignment is for visualization and does not affect action selection.

## Released MaleCNS morphology — PASS

The flat MaleCNS annotation table did not provide physical `pos_x/pos_y/pos_z` columns. Those coordinates were **not invented**.

Instead, the spectator retrieves officially released centerline SWC skeletons after a match from:

`https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc/<bodyId>.swc`

Current viewer behavior:

- top six highly active bodies per fighter;
- MaleCNS EM coordinate system;
- released **8 nm** coordinate units;
- compact X–Z projection;
- up to 180 centerline segments/body;
- bodies active in the current decision window are rendered brighter/thicker.

SWC geometry is strictly spectator/post-hoc data and is never a policy input.

## Vercel viewer — PASS

Viewer repository: `Unjuno/live`.

Implemented routes:

- `/connectome` — rolling arena UI
- `/api/connectome/state` — dynamic no-store state proxy

UI currently provides:

- current clip + previous two clips;
- next-clip countdown;
- automatic current-clip switching;
- actual FightingICE video;
- four-character W/L/D + win rate;
- recent experiment logs;
- playback-synchronized P1/P2 MaleCNS structural activity;
- released SWC morphology projection;
- body IDs / cell types / anatomical categories;
- direct Actions evidence links.

## Reward/plasticity smoke evidence — NOT production learning

Earlier exploratory workflows established several engineering mechanisms:

- offline reward re-scoring;
- a project-defined MBON valence partition;
- one-match KC→MBON multiplier updates;
- durable checkpoint pack/restore across separate Actions runs.

Those experiments are useful implementation evidence, but they have **not** been promoted into the production fighter lineage. In particular, previously tested R2c/R2d variants and stalemate penalties are not the current accepted reward contract.

## Current gate

**P6 — freeze spectator/data contracts.**

Before enabling production learning, hold fixed and regression-test:

1. queue schema and max-three rotation;
2. stable video asset names;
3. H.264 960×640 / 45–100 s video gate;
4. body-ID spike schema;
5. non-empty P1/P2 decision-window timelines;
6. released SWC morphology available for at least one body/side;
7. Vercel polling/current-clip switch without viewer redeploy;
8. learning disabled throughout the gate.

The latest run `34636959865` satisfies the substantive spectator conditions above. The hourly scheduled loop is left running to confirm repeated regression stability.

## Not yet demonstrated

- a frozen production reward specification;
- reproducible behavioral improvement caused by MaleCNS plasticity;
- four durable learned character lineages advancing continuously;
- stable champion/archive league learning;
- causal circuit mechanism from activity alone;
- biological-structure advantage over matched controls.

These claims remain explicitly unproven.
