# Historical Rolling Spectator Pipeline

> **Not the current production LIVE specification.** English translation retained at its original compatibility path. References below to `/connectome` and `connectome-live-broadcast` describe the historical deployment, not a current deployment target. Current contracts are `PUBLIC_SURFACE_SPLIT.md` and `STATUS.md`.

The rolling MP4 / three-clip queue described here is retained for regression checks of official FightingICE ScreenData, activity timelines, and SWC export.

## Relationship to production

The historical production architecture was:

```text
SHA-addressed runtime snapshot
  -> connectome-live-broadcast
  -> FightingICE + MaleCNS/Shiu
  -> /state + /events
  -> all viewers observe the same live session
```

Recordings must not substitute for LIVE. The read-only serving contract keeps `learning_enabled=false` and `policy_pixel_access=false`, with approved GARNET G2 versus the canonical ZEN baseline.

The archival pipeline is limited to official-renderer/ScreenData regression, H.264 export verification, body-ID timeline export, released MaleCNS SWC projection, and archival evidence generation. Its hourly cron was stopped; manual dispatch and implementation-regression runs remain its intended use.

## Historical pipeline

```text
GitHub Actions (manual/regression)
  -> MaleCNS v1.0 + pinned Shiu LIF
  -> six actual FightingICE rounds
  -> separate spectator socket
  -> official ScreenData, 960x640 RGB
  -> ffmpeg, approximately one-minute H.264 MP4
  -> body-ID spike logs
      -> decision-window structural activity
      -> released MaleCNS SWC skeleton projection
  -> archival release assets + queue.json
```

It records actual fights but is not the current Vercel LIVE input.

## Recorded demonstrated conditions

Canonical MaleCNS v1.0/Shiu controller; FightingICE v7.1 and pyftg 2.3; six rounds per clip; approximately 56–61 seconds per clip; 960x640 H.264; `policy_pixel_access=false`; latest and two previous clips retained. All six pairings can rotate for regression, and character-specific Poisson seeds can advance between epochs. These are historical evidence reports, not new measurements by this translation.

## Decision-window activity

P1/P2 spike events retain actual MaleCNS body IDs. Compact archival samples include total spikes, unique active bodies, top `somaNeuromere`, `superclass`, `type`, and active body IDs. Alignment to playback time is a visualization alignment, not a controller modification.

## Released SWC morphology

The flat annotation table has no physical `pos_x/pos_y/pos_z`, so no coordinates are invented. Use officially released centerline SWCs:

`https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc/<bodyId>.swc`

The regression projection uses MaleCNS EM coordinates in 8-nanometre units, X–Z projection, at most six highly active bodies per fighter, and at most 180 segments per body. Bodies active at the displayed decision are brighter/thicker. Morphology is spectator/post-hoc data, never policy or plasticity input.

## Archival storage

GitHub prerelease tag: `spectator-latest`. Legacy assets: `latest-fight.mp4`, `previous-1.mp4`, `previous-2.mp4`, `video.json`, and `queue.json`. They are archival/regression evidence, not the system of record for current production LIVE state.

## Scientific boundary

Screen pixels and SWC geometry are spectator-only. Structural annotations support post-hoc analysis. Action selection follows numeric observations, Poisson sensory inputs, MaleCNS/Shiu LIF, and spike-count readout. Visual recruitment correlations can motivate pathway hypotheses; causal circuit claims require interventions or ablations.

## Learning state

Production reward-driven learning is OFF under this serving contract. The existence of historical spectator recordings says nothing about current candidate-training state. Use `PUBLIC_SURFACE_SPLIT.md` and `STATUS.md` for the current public/runtime contract.
