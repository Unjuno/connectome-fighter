# Connectome Fighter Roadmap

Primary goal:

> Run real MaleCNS-constrained fighters continuously in GitHub Actions, keep each FightingICE character as a separate brain lineage, preserve body-ID neural logs for circuit analysis, and publish actual FightingICE fight video plus neural activity on GitHub Pages.

Canonical control path:

```text
FightingICE numeric observation
        ↓
versioned artificial sensory interface
        ↓
MaleCNS v1.0 real body-ID connectivity
        ↓
pinned Shiu et al. LIF dynamics
        ↓
versioned artificial output groups
        ↓
FightingICE key action
```

No MLP/RNN/custom-sigmoid network replaces the fly neural substrate in the canonical path.

---

## Current state

| Stage | Status | Evidence / note |
|---|---|---|
| MaleCNS provenance + Shiu adapter | **PASS** | 156,675 neurons / 6,025,920 runtime synapses |
| Pinned Shiu LIF reference gate | **PASS** | upstream `model.py` executes directly |
| MaleCNS-controlled FightingICE round | **PASS** | independent per-character Brian2 workers |
| 4-character continuous baseline | **PASS** | 6 pairs × 8 rounds, scheduled every 6 h |
| Body-ID spike/decision logging | **PASS** | raw spike Parquet + decision/game traces |
| Real FightingICE spectator video | **PASS** | official headless `ScreenData`, separate spectator socket |
| Pages auto-deploy | **PASS** | render workflow deploys video + telemetry |
| Structural activity annotation | **PASS** | body ID → cell/soma-neuromere categories, spectator-only |
| Reward-driven plasticity | **NOT ENABLED** | next experiment |
| Durable canonical learned lineage | **NOT RUN** | follows reward selection |
| League/champion learning | **NOT RUN** | later |
| Biological-vs-control causal comparison | **NOT RUN** | later |

Latest fully integrated spectator pipeline: Actions run `34628459203` — PASS.

---

# P0 — Canonical biological substrate ✅

**Goal:** freeze the distinction between anatomy, dynamics, and artificial game interface.

Completed:

- MaleCNS v1.0 is the canonical anatomy.
- Shiu et al. 2024 LIF reference code is pinned separately.
- transmitter filtering/sign convention and connection threshold are manifest-recorded.
- legacy FlyWire/custom-sigmoid/PPO path is excluded from canonical evidence.

**Gate:** PASS.

---

# P1 — Real MaleCNS → FightingICE control ✅

**Goal:** prove the biological substrate is actually in the game-control path.

Completed:

- numeric FightingICE observations stimulate selected real MaleCNS body IDs through Poisson input;
- the pinned LIF network advances in biological simulation time;
- action groups are read from real output body IDs;
- action is selected from spike counts;
- complete real FightingICE rounds finish with audited traces.

**Gate:** PASS.

---

# P2 — Character-specific independent brains ✅

**Goal:** ensure FightingICE characters do not share mutable neural state.

Characters:

- GARNET
- ZEN
- LUD
- NEZ

Completed:

- separate Brian2 process/state per fighter;
- separate RNG sequence per character seed;
- separate recurrent state/reset history;
- character identity carried into traces and future plasticity-state format;
- immutable anatomy files may be shared as read-only assets only.

Learning is currently off, so these are separate neural simulation states but not yet separate *learned* weight lineages.

**Gate:** PASS for state isolation; learned divergence remains future work.

---

# P3 — Continuous baseline experiment ✅

**Goal:** characterize behavior before changing reward/plasticity.

Workflow: `.github/workflows/malecns-baseline-batch.yml`

Current schedule:

```text
every 6 hours
  ↓
GARNET–ZEN       8 rounds
GARNET–LUD       8 rounds
GARNET–NEZ       8 rounds
ZEN–LUD          8 rounds
ZEN–NEZ          8 rounds
LUD–NEZ          8 rounds
  ↓
48 rounds / chunk
  ↓
body-ID neural logs + public summary
```

Current fixed conditions:

- no weight updates;
- observation-driven Poisson randomness only;
- spike-count argmax action readout;
- decision interval: 60 FightingICE frames;
- R0 terminal HP-sign reward is logged only.

**Gate:** PASS.

---

# P4 — Analysis-grade logging ✅

**Goal:** retain enough information to later ask which neural structures were recruited.

Logged per decision/run:

- game frame / observation / action;
- sensory target body IDs + drive rates;
- all spike event body IDs and times;
- output-group contributions;
- top active body IDs;
- membrane summary;
- HP/position/game outcome;
- dataset/dynamics/interface provenance and hashes.

Raw spike/event data stays in Actions artifacts. Compact replay data is published to Pages.

**Gate:** PASS for post-hoc recruitment analysis.

Boundary: logs can identify associations/candidate pathways; they do not by themselves establish causal circuit mechanisms.

---

# P5 — Real-game spectator + neural visualization ✅

**Goal:** make the experiment watchable without confusing telemetry with the game itself.

Completed pipeline:

```text
baseline data
    ↓
select current public matchup
    ↓
run fresh canonical one-round spectator match
    ↓
FightingICE official headless ScreenData
    ↓ separate spectator socket
H.264 MP4
    ↓
join active body IDs to structural annotations
    ↓
GitHub Pages deploy
```

Rules:

- pixels are never exposed to the MaleCNS policy;
- `policy_pixel_access=false` is recorded;
- actual FightingICE video is the primary spectator view;
- rectangle/canvas view is explicitly labeled telemetry schematic;
- video metadata states when the video is a fresh same-character/seed spectator run rather than the exact stored telemetry trajectory.

Structural activity currently uses categorical released/canonical metadata such as `somaNeuromere`, `superclass`, `class`, and `type`. It must not be represented as geometric neuron coordinates.

**Gate:** PASS. Latest integrated run `34628459203`.

---

# P6 — Reward-design experiment ← NEXT

**Goal:** choose a reward signal without changing current action randomness/readout at the same time.

The current R0 control remains:

```text
higher final HP  +1
same final HP     0
lower final HP   -1
```

Observed problem: non-zero terminal reward is sparse under the current baseline, so terminal-only credit assignment is likely weak.

Before enabling learning, define a small pre-registered comparison in which all of these stay fixed:

- MaleCNS anatomy;
- Shiu dynamics;
- sensory interface;
- action groups;
- Poisson randomness mechanism;
- decision interval;
- character seeds;
- opponent schedule;
- plastic synapse class;
- learning-rate scale and clipping policy where possible.

Only the reward definition changes.

Candidate families to evaluate:

- **R0:** terminal HP-sign only — control.
- **R1:** terminal outcome + normalized final HP difference.
- **R2:** time-local damage differential (`damage dealt - damage taken`) plus a smaller terminal outcome bonus.

Do not reward hand-selected actions such as “move forward” or “press attack”; that would encode the desired strategy externally.

### Gate P6

PASS only after:

1. reward equations and scales are versioned;
2. identical logged trajectories can be scored offline under every candidate reward;
3. reward density/range/outlier behavior is measured on existing baseline logs;
4. one reward family is selected before weight updates are enabled.

**Output:** frozen reward specification for the first learning experiment.

---

# P7 — Canonical character-specific plasticity

**Goal:** let each character accumulate its own learned neural state across CI jobs.

Initial plasticity scope already prepared:

- existing real KC→MBON candidate edges only;
- 33,496 candidate edges;
- no new edges;
- topology immutable;
- neurotransmitter sign immutable;
- per-character multiplier/checkpoint state.

Required persistent lineages:

```text
GARNET state
ZEN state
LUD state
NEZ state
```

Each lineage must include generation, match count, update count, candidate/config hashes, state checksum, and reward-version ID.

### Gate P7

PASS only when two separate Actions runs demonstrate:

1. character checkpoint generation `N` is restored exactly;
2. a new audited match updates only that character's approved plastic state;
3. generation advances to `N+1`;
4. another character's state is unchanged;
5. restart/recovery rejects incompatible or corrupt state.

---

# P8 — Continuous learning + evaluation

**Goal:** turn the baseline scheduler into a continuous learning service after P6/P7 are frozen.

Cycle:

```text
restore 4 character states
        ↓
run bounded training matches
        ↓
post-match plasticity update
        ↓
atomic checkpoint save
        ↓
frozen evaluation matches
        ↓
video + body-ID activity + metrics
        ↓
Pages
        ↓
next scheduled job resumes
```

Train/eval must stay separate. Evaluation never changes plasticity state.

---

# P9 — League / historical opponents

**Goal:** avoid learning only against one contemporary opponent.

Later maintain:

- current character lineages;
- champion snapshots;
- historical snapshots;
- fixed baseline opponents.

Selection and opponent-sampling rules must be logged and deterministic enough to reproduce evaluation.

---

# P10 — Circuit analysis

**Goal:** use the accumulated logs to ask what neural structure was recruited during successful/unsuccessful behavior.

Planned analyses include:

- action-conditioned body/type/superclass recruitment;
- reward-event-aligned activity;
- soma-neuromere recruitment changes across generations;
- KC→MBON multiplier changes;
- persistent high-centrality/repeatedly recruited bodies;
- character-lineage divergence;
- candidate sensory→interneuron→descending/motor pathways.

Causal claims require interventions/ablations, not activity correlation alone.

---

# P11 — Controlled biological comparison

Only after the operational system and reward learning are stable, compare the biological substrate against declared controls.

Possible conditions:

- canonical MaleCNS structure;
- matched structural null/rewire where technically and scientifically valid;
- optional engineering controller as a separate benchmark.

Hold observations, actions, reward, interface, opponent schedule, compute budget, and paired seeds fixed.

Report PASS / FAIL / UNCERTAIN against predeclared practical thresholds.

---

# Immediate queue

- [x] Canonical MaleCNS + pinned Shiu LIF runtime.
- [x] Real canonical FightingICE match.
- [x] Four-character independent simulation states.
- [x] Six-pair scheduled baseline.
- [x] Body-ID spike/event logging.
- [x] Actual FightingICE ScreenData video on Pages.
- [x] Structural activity annotation on Pages.
- [ ] **Offline-score existing trajectories under R0/R1/R2.**
- [ ] Freeze first reward design.
- [ ] Demonstrate one character-specific plasticity update without enabling continuous learning.
- [ ] Demonstrate checkpoint resume across two separate Actions runs.
- [ ] Enable continuous canonical learning only after those gates pass.

---

# Definition of operational success

A visitor can open GitHub Pages and see an actual FightingICE match rendered by FightingICE itself, inspect current experiment metrics, and inspect which real MaleCNS body IDs / structural categories were active, while all heavy computation runs in GitHub/cloud infrastructure rather than a local PC.

# Definition of scientific success

Scientific success requires controlled experiments showing reproducible behavioral/learning effects and, for circuit claims, interventions or ablations that distinguish causal mechanisms from correlated activity.
