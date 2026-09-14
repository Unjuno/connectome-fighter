# Historical Rolling Spectator Pipeline

English-only compatibility document. This describes an archival MP4/three-clip pipeline, **not the current production LIVE contract**. Current routing and deployment status are defined by [PUBLIC_SURFACE_SPLIT.md](PUBLIC_SURFACE_SPLIT.md) and [STATUS.md](STATUS.md).

## Relationship to the public runtime

The shared-LIVE architecture restores a SHA-addressed runtime snapshot, starts a fixed named broadcast sandbox, runs FightingICE and MaleCNS/Shiu, and exposes `/state` and `/events` to viewers. Its learning and policy-pixel-access flags remain false. Recordings must never impersonate LIVE.

The older rolling spectator is retained only for official-renderer/ScreenData regression, H.264 export, body-ID activity timeline export, released SWC projection, and archival evidence. Its hourly cron was stopped; it is manual/regression tooling.

## Historical pipeline

```text
GitHub Actions manual/regression run
  -> MaleCNS v1.0 and pinned Shiu LIF
  -> six actual FightingICE rounds
  -> separate spectator socket / official 960x640 RGB ScreenData
  -> ffmpeg / approximately one-minute H.264 video
  -> body-ID spike logs and structural-activity windows
  -> released MaleCNS SWC skeleton projections
  -> archival release assets and queue.json
```

This records actual fights but does not supply current production LIVE input.

## Recorded historical checks

Canonical MaleCNS/Shiu control; FightingICE v7.1/pyftg 2.3; six rounds per clip; approximately 56–61 seconds per clip; 960x640 H.264; policy-pixel access false; latest plus two older clips; all six character pairings available for regression; and advancing character-specific Poisson seed series.

## Decision-window activity

Raw P1/P2 simulated spike events preserve real MaleCNS body IDs. The compact archival sample includes total spikes, unique active bodies, top somaNeuromere/superclass/type aggregates, and top active body IDs. Mapping a decision window to video playback time is visualization alignment and does not alter the controller.

## Released SWC morphology

The flat annotation table lacks physical x/y/z coordinates; positions were not fabricated. The historical renderer uses official centerline SWC skeletons at:

`https://storage.googleapis.com/flyem-male-cns/v1.0/segmentation/skeletons-malecns/skeletons-swc/<bodyId>.swc`

The coordinate space is MaleCNS EM, in 8 nm units. The viewer projects X–Z, with up to six highly active bodies per fighter and up to 180 centerline segments per body. Bodies active in the selected decision are brighter/thicker. Morphology is spectator/post-hoc data only, never policy or plasticity input.

## Archival storage

Historical prerelease `spectator-latest` contains `latest-fight.mp4`, `previous-1.mp4`, `previous-2.mp4`, `video.json`, and `queue.json`. These are archival evidence, not the current production state record.

## Scientific boundary

Pixels and SWC geometry are spectator-only. Structural annotations support post-hoc analysis. Actions follow numeric FightingICE observations, Poisson sensory inputs, MaleCNS/Shiu LIF, and spike-count readout. Activity correlations suggest recruitment candidates; causal circuit claims require interventions or ablations.

Production learning remains off. Archival clips do not determine the current training state.
