# Status

Updated for the canonical MaleCNS pipeline.

## Canonical substrate

- anatomy: **MaleCNS v1.0**
- dynamics: **pinned Shiu et al. 2024 LIF reference code** at commit `2a83ad611cd9768f8c9723fc613ed27761a5feb5`
- game: **FightingICE v7.1 + pyftg 2.3**
- canonical runtime adapter: **156,675 neurons / 6,025,920 recurrent synapses** under the current strict-Shiu/min-weight-5 condition
- artificial game I/O is versioned separately from the biological structure.

The old FlyWire v783 + custom sigmoid recurrent/PPO path is legacy engineering evidence only and is not canonical biological evidence.

## PASS — demonstrated in GitHub Actions

### 1. Canonical MaleCNS → Shiu LIF runtime

- official MaleCNS v1.0 inputs are provenance-checked and converted to the pinned Shiu input contract;
- upstream Shiu LIF code is executed directly rather than replaced by a custom neural-network dynamics model;
- the whole canonical runtime builds and advances successfully in CI.

### 2. Canonical live FightingICE control

- two independent MaleCNS+Shiu LIF worker processes have completed real FightingICE rounds;
- each side has independent membrane/synaptic state and RNG;
- game observations drive sensory Poisson inputs and MaleCNS output-body spike counts choose actions;
- body-ID spike events and decision telemetry are logged for post-hoc analysis.

### 3. Four-character continuous baseline

`.github/workflows/malecns-baseline-batch.yml` runs every six hours:

- GARNET–ZEN
- GARNET–LUD
- GARNET–NEZ
- ZEN–LUD
- ZEN–NEZ
- LUD–NEZ

Each pair currently runs eight rounds, giving 48 rounds per scheduled chunk. Learning is deliberately **OFF** while the pipeline and reward design are characterized.

First confirmed four-character chunk: Actions run `34620984683`.

- all six pair jobs: PASS
- 48 independent rounds
- 960 decisions
- 1/48 non-zero terminal rewards in that chunk
- current randomness: observation-driven Poisson sensory spikes
- current readout: deterministic spike-count argmax

### 4. Real FightingICE spectator video

The Pages spectator does not reconstruct the game with rectangles as the primary view.

- FightingICE headless renderer produces official `ScreenData` RGB frames;
- a separate pyftg spectator socket receives those frames;
- policy pixel access is explicitly `false`;
- frames are encoded to H.264 MP4;
- the lower rectangle view remains only a labeled telemetry schematic.

Validated ScreenData video run: Actions run `34625054830`.

Latest fully integrated render/deploy run: **`34628459203` — PASS**.

That run passed:

1. latest public matchup resolution;
2. canonical MaleCNS adapter restore;
3. structural annotation index restore;
4. active-body structural enrichment;
5. canonical FightingICE match;
6. official ScreenData recording;
7. artifact validation;
8. GitHub Pages deployment.

Integrated artifact `rendered-fightingice-spectator`:

- artifact ID `10275496675`
- SHA-256 digest `7ca104a49744ee7f3c7af9b8e4bb4d6f294a5a579efe2099f15d214250eb334f`
- video: ZEN vs NEZ
- 960×640 H.264
- 10 fps
- 103 ScreenData frames
- 10.3 s
- policy pixel access: false

### 5. Structural activity visualization

A spectator-only structural index joins active MaleCNS body IDs to released/canonical metadata such as:

- `superclass`
- `class`
- `subclass`
- `type`
- `instance`
- `somaNeuromere`
- `rootSide`
- `somaSide`

Structure-index workflow run `34628145680`: PASS.

In integrated run `34628459203`:

- 97 requested active body IDs
- 97/97 resolved
- 240 top-active-body rows enriched with anatomical categories.

These are **categorical anatomical annotations**, not neuron XY coordinates or synapse locations. The flat MaleCNS body-annotation table used by this project does not expose the previously assumed `pos_x/pos_y/pos_z` fields; the unsupported coordinate attempt was removed rather than inventing coordinates.

## Current reward / learning state

Current public experiment phase: `canonical-baseline-no-weight-updates`.

Reward baseline R0 is logged but not applied to plasticity:

- win / higher remaining HP: `+1`
- draw / equal remaining HP: `0`
- loss / lower remaining HP: `-1`

Character-specific KC→MBON plasticity-state infrastructure exists, but automatic canonical learning is **not enabled yet**. Reward design is the next experimental decision after the spectator/logging pipeline.

## Not yet demonstrated

- reward-driven improvement of a MaleCNS fighter;
- durable canonical plasticity checkpoints advancing across scheduled jobs;
- character-specific learned divergence across GARNET / ZEN / LUD / NEZ;
- league/champion learning;
- biological-structure advantage over a matched null/control.

Those claims remain explicitly unproven.
