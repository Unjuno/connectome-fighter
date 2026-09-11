# Connectome Fighter

Cloud-only research testbed that connects the **MaleCNS v1.0 Drosophila connectome** to FightingICE through the pinned Shiu et al. LIF dynamics, records real body-ID neural activity, and publishes rolling watchable fights with post-hoc MaleCNS activity/morphology visualization.

**[Rolling MaleCNS Arena](https://liveunjuno.vercel.app/connectome)** · [Roadmap](ROADMAP.md) · [Status](docs/STATUS.md) · [Spectator contract](docs/SPECTATOR_PIPELINE.ja.md) · [日本語](README.ja.md)

## Canonical control path

```text
FightingICE numeric observation
        ↓
versioned sensory-body Poisson interface
        ↓
MaleCNS v1.0 real connectivity
        ↓
pinned Shiu et al. LIF dynamics
        ↓
real output-body spike counts
        ↓
versioned action groups
        ↓
FightingICE action
```

The canonical path does **not** replace the fly substrate with an MLP, RNN, PPO policy network, or the repository's older custom sigmoid scaffold. Legacy FlyWire/custom-network components remain engineering evidence only.

## Current demonstrated state

- MaleCNS v1.0 provenance/import: **PASS**
- pinned Shiu LIF reference/runtime: **PASS**
- strict runtime: **156,675 neurons / 6,025,920 recurrent synapses**
- real MaleCNS-controlled FightingICE rounds: **PASS**
- independent neural state for GARNET / ZEN / LUD / NEZ: **PASS**
- body-ID spike/event logs: **PASS**
- official FightingICE ScreenData → H.264 spectator video: **PASS**
- six real rounds → approximately one-minute clip: **PASS**
- rolling latest + previous two queue: **PASS**
- Vercel polling/countdown/current-clip switching: **PASS**
- playback-synchronized MaleCNS structural activity: **PASS**
- released MaleCNS SWC morphology visualization: **PASS**

Latest regression evidence is maintained in [`docs/STATUS.md`](docs/STATUS.md).

## Rolling spectator architecture

```text
GitHub Actions (hourly)
  ↓
select next character pairing
  ↓
6 canonical FightingICE rounds
  ↓
official 960×640 ScreenData
  ↓
~1 min H.264 video
  ↓
body-ID decision-window activity
  + released MaleCNS SWC skeletons
  ↓
latest / previous-1 / previous-2
  ↓
Vercel /connectome polls every 30 s
```

New clips do not require a Vercel redeploy. The viewer polls a no-store state endpoint and automatically returns to queue slot 0 when `current_clip_id` changes. A countdown shows the next expected generation time.

The viewer also shows four-fighter W/L/D, recent experiment logs, and two neural activity panels synchronized to video playback.

## Neural visualization boundary

The flat MaleCNS annotation table does not expose physical `pos_x/y/z`, so the project does not invent those coordinates.

For physical morphology, the spectator retrieves officially released MaleCNS centerline SWC skeletons **after** the fight and renders a compact X–Z projection in the released MaleCNS EM coordinate space (8 nm units). Active body IDs from the current decision window are highlighted.

Pixels, SWC geometry and visualization-only annotations are **never** policy inputs.

## Current experiment phase

**Production learning is intentionally OFF.**

The current gate freezes the rolling spectator/data contract before reward-driven plasticity is promoted into a persistent lineage. Existing reward/plasticity/checkpoint workflows are exploratory engineering smoke evidence, not a continuously learning production fighter.

The action mechanism remains unchanged during this gate:

- stochasticity: observation-driven Poisson sensory spikes;
- readout: deterministic spike-count argmax;
- no epsilon-greedy/random action injection.

## Next gates

1. confirm repeated hourly spectator regression stability;
2. freeze the spectator/queue/activity/SWC schemas;
3. choose and version the production reward contract, including explicit timeout/stalemate semantics;
4. start four separate character-specific plasticity/checkpoint lineages;
5. enable continuous learning only after exact resume/update invariants pass;
6. later add champion/archive evaluation and causal intervention experiments.

See [`ROADMAP.md`](ROADMAP.md) for the full sequence.

## Research boundary

MaleCNS anatomy, Shiu LIF dynamics, game I/O mappings, spectator data, and project-defined plasticity/reward rules are separate layers and are logged separately. A successful fighter would not prove that the fly uses the same reinforcement signal in vivo. Activity visualization identifies recruited structures; causal circuit claims require controlled interventions or ablations.

## License

Project-authored source code is MIT licensed. FightingICE, MaleCNS/connectome data, papers, and other third-party resources retain their own licenses and terms; see [`THIRD_PARTY.md`](THIRD_PARTY.md).
