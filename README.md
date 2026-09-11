# Connectome Fighter

Cloud-only research testbed that connects the **MaleCNS v1.0 Drosophila connectome** to FightingICE through the pinned Shiu et al. LIF dynamics, logs real body-ID neural activity, and publishes actual FightingICE spectator video on GitHub Pages.

[MaleCNS Arena](https://unjuno.github.io/connectome-fighter/) · [Roadmap](ROADMAP.md) · [Status](docs/STATUS.md) · [日本語](README.ja.md)

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

The canonical path does **not** replace the fly substrate with an MLP, RNN, PPO policy network, or the repository's older custom sigmoid scaffold. Those older FlyWire/custom-network components are retained only as legacy engineering evidence.

## Current demonstrated state

- MaleCNS v1.0 provenance/import: PASS
- pinned Shiu LIF reference/runtime: PASS
- canonical runtime: 156,675 neurons / 6,025,920 recurrent synapses under the current strict adapter condition
- real MaleCNS-controlled FightingICE rounds: PASS
- independent neural state for GARNET / ZEN / LUD / NEZ: PASS
- continuous six-pair baseline: 48 rounds per scheduled chunk, every 6 hours
- chunk-specific deterministic Poisson seeds: enabled, so scheduled chunks do not simply repeat the same random sequence
- body-ID spike/event logs: PASS
- actual FightingICE ScreenData → H.264 spectator video: PASS
- GitHub Pages deployment: PASS
- spectator-only structural activity labels (`superclass`, `class`, `type`, `somaNeuromere`, side): PASS

Latest fully integrated video/structure/Pages run is documented in [`docs/STATUS.md`](docs/STATUS.md).

## Current experiment phase

**Learning is intentionally OFF.**

The project is characterizing reward design on logged trajectories before changing KC→MBON weights. The action mechanism remains unchanged during this comparison:

- stochasticity: observation-driven Poisson sensory spikes
- readout: deterministic spike-count argmax
- no epsilon-greedy or random action injection

R0/R1/R2 reward candidates are rescored offline on the same trajectories. See [`docs/REWARD_DESIGN.ja.md`](docs/REWARD_DESIGN.ja.md).

## Spectator / analysis split

The Pages site shows two different views on purpose:

1. **Rendered FightingICE fight** — official 960×640 FightingICE `ScreenData` received through a separate spectator socket and encoded to H.264. Pixel data is not provided to the fighter policy.
2. **Telemetry / MaleCNS activity** — game state plus top active MaleCNS body IDs and categorical structural annotations for analysis.

The telemetry schematic is not presented as the game renderer.

## Next gates

1. validate reward density on at least two independent Poisson-seed chunks;
2. freeze the first reward specification;
3. run one audited character-specific KC→MBON plasticity update;
4. demonstrate exact checkpoint resume across separate Actions runs;
5. only then enable continuous canonical learning.

See [`ROADMAP.md`](ROADMAP.md) for the full sequence.

## Research boundary

MaleCNS anatomy, Shiu LIF dynamics, game I/O mappings, and project-defined plasticity/reward rules are separate layers and are logged separately. A successful fighter would not by itself prove that the fly uses the same reinforcement signal in vivo. Causal circuit claims require controlled interventions/ablations beyond activity correlation.

## License

Project-authored source code is MIT licensed. FightingICE, MaleCNS/connectome data, papers, and other third-party resources retain their own licenses and terms; see [`THIRD_PARTY.md`](THIRD_PARTY.md).
