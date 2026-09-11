# Status

Updated for the canonical MaleCNS pipeline.

## Canonical substrate

- anatomy: **MaleCNS v1.0**
- dynamics: **pinned Shiu et al. 2024 LIF reference code** at commit `2a83ad611cd9768f8c9723fc613ed27761a5feb5`
- game: **FightingICE v7.1 + pyftg 2.3**
- canonical runtime adapter: **156,675 neurons / 6,025,920 recurrent synapses** under the current strict-Shiu/min-weight-5 condition
- artificial game I/O, game reward and project plasticity are versioned separately from the biological anatomy/dynamics.

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

Each pair currently runs eight rounds, giving 48 rounds per scheduled chunk. Baseline learning remains **OFF**.

Scheduled chunks use the same Poisson mechanism but different deterministic seed blocks so the six-hour schedule does not simply replay one random sequence. Within a chunk, the same character uses the same character-specific seed across pairings.

First confirmed four-character chunk: Actions run `34620984683`.

- all six pair jobs: PASS
- 48 rounds
- 960 brain decision windows
- 1/48 non-zero terminal outcomes
- spike-count argmax strongly B-biased

Independent-seed chunk: Actions run `34629644845`.

- all six pair jobs: PASS
- 48/48 no-damage draws
- demonstrates that terminal reward sparsity is not fixed by simply repeating more of the original policy.

### 4. Real FightingICE spectator video

The Pages spectator does not reconstruct the game with rectangles as the primary view.

- FightingICE headless renderer produces official `ScreenData` RGB frames;
- a separate pyftg spectator socket receives those frames;
- policy pixel access is explicitly `false`;
- frames are encoded to H.264 MP4;
- the lower rectangle view remains only a labeled telemetry schematic.

Validated ScreenData video run: Actions run `34625054830`.

Latest fully integrated render/deploy run: **`34628459203` — PASS**.

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

A spectator-only structural index joins active MaleCNS body IDs to canonical metadata such as:

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

These are **categorical anatomical annotations**, not neuron XY coordinates or synapse locations. The unsupported coordinate assumption was removed rather than inventing geometry.

### 6. Offline reward-design characterization

All reward comparisons below re-score identical logged trajectories; they do not alter actions or weights.

First chunk, run `34620984683`:

- R0 terminal-sign non-zero decisions: **2/960 = 0.2083%**
- local damage windows: **4/960 = 0.4167%** from the two player perspectives
- R1 final-margin augmentation: same density as R0
- R2a local damage + terminal: still very sparse.

Independent-seed chunk, run `34629644845`:

- R0/R1/R2a produced zero signal because all 48 rounds were no-damage draws.

Cross-seed reward comparison: workflow run `34631037696` — PASS.

Conservative engagement/stalemate candidate R2d (`contact=180 px`, potential weight `0.05`, `+0.1/10HP`, terminal `±1`, no-damage draw `-0.01`):

- chunk A non-zero decision rate: **17.5%** (71 positive / 97 negative)
- chunk B: **13.33%** (32 positive / 96 negative)

However, the no-damage negative signal is not automatically biologically appropriate when coupled to MBON valence plasticity; see below. R2d is therefore an engineering/checkpoint smoke reward, not the currently accepted continuous-learning reward.

R2c removes the no-damage penalty and retains engagement potential + damage + terminal outcome. A paired learning A/B against R2d is currently the next reward-selection gate.

### 7. MBON valence partition for plasticity modeling

Aso et al. 2014 motivates a population-level model partition in which glutamatergic MBON activity is avoidance-associated and GABAergic/cholinergic MBON activity is approach-associated. This is a **project modeling adapter**, not a MaleCNS-supplied fixed-valence annotation for every MBON.

Valence partition workflow run `34630909774`: PASS.

Real KC→MBON candidate edges: **33,496**.

- approach-associated: **21,421 edges / 69 MBONs**
  - acetylcholine: 11,854 edges
  - GABA: 9,567 edges
- avoidance-associated: **12,075 edges / 22 MBONs**
  - glutamate: 12,075 edges
- unresolved: 0

No topology, weight or transmitter sign was changed while constructing the partition.

### 8. Single-match valence-gated plasticity smoke

Workflow run `34631587091`: **PASS**.

GARNET was updated for one real canonical FightingICE match while ZEN remained unchanged.

R2d-v0 smoke result:

- 10 decision windows
- 5 positive / 4 negative non-zero signals
- 9,121/33,496 KC→MBON multipliers depressed
  - 5,960 approach-associated edges
  - 3,161 avoidance-associated edges
- potentiated edges: **0**
- multiplier range after the match: `[0.9999, 1.0]`
- GARNET generation advanced 0 → 1
- generation-1 GARNET adapter completed another audited FightingICE round against unchanged ZEN.

This demonstrates the update mechanism/invariants, not behavioral improvement.

### 9. Durable checkpoint resume across separate Actions runs

Generation-1 state was promoted to prerelease `canonical-state-smoke-v1`, then restored by a **separate** workflow run.

Seed/promotion workflow: `canonical-checkpoint-seed`.

Resume workflow run `34632209463`: **PASS**.

Exact-restore gate:

- release manifest, packed manifest, state metadata and restored state SHA-256 agreed;
- restored GARNET generation: 1;
- restored state was materialized into the canonical Shiu input ordering;
- a new audited FightingICE match completed;
- post-match state advanced generation 1 → 2;
- generation-2 state SHA-256: `509ba9a8025e511c4785d13481fa6d1d68f500eb507a10ab64dfd3845961f119`;
- generation-2 update depressed 5,883 approach-associated edges, potentiated 0.

The generation-2 match had only the R2d no-damage penalty (`-0.01`), which is direct evidence for the concern that treating stalemate as negative valence may push the model toward avoidance. This state is therefore smoke evidence only, not the production training lineage.

## Current reward / learning state

Baseline public experiment phase remains `canonical-baseline-no-weight-updates`.

Continuous canonical learning is **still disabled**.

Current work is a paired short learning experiment:

- control: no plasticity
- R2c: engagement potential + damage + terminal outcome, no no-damage penalty
- R2d: same plus no-damage draw `-0.01`

Both learning conditions use the same valence-gated depression rule and paired seeds. The purpose is to determine whether the extra stalemate penalty makes engagement better or worse before any long-running lineage is enabled.

## Not yet demonstrated

- reproducible behavioral improvement from reward-driven MaleCNS plasticity;
- stable superiority of R2c or R2d;
- four durable learned character lineages advancing continuously;
- league/champion learning;
- biological-structure advantage over a matched null/control;
- causal circuit mechanism from activity logs alone.

Those claims remain explicitly unproven.
