# Connectome Fighter Roadmap

Primary goal:

> Run a real MaleCNS-constrained FightingICE controller in reproducible cloud infrastructure, expose one auditable shared LIVE inference surface, preserve analysis-grade neural/checkpoint provenance, and only then enable controlled reward-driven plasticity with separate character lineages.

Canonical control path:

```text
FightingICE numeric observation
        ↓
versioned project-defined sensory interface
        ↓
MaleCNS v1.0 real body-ID connectivity
        ↓
pinned Shiu et al. LIF dynamics
        ↓
versioned output-body groups
        ↓
FightingICE action
```

No MLP/RNN/custom-sigmoid/PPO controller replaces the fly neural substrate in the canonical path.

---

## Current state

| Stage | Status | Evidence / note |
|---|---|---|
| MaleCNS provenance + Shiu adapter | **PASS** | 156,675 neurons / 6,025,920 runtime synapses |
| Pinned Shiu LIF reference runtime | **PASS** | upstream `model.py` executes directly |
| MaleCNS-controlled FightingICE | **PASS** | independent Brian2 workers |
| Four-character baseline | **PASS** | all 6 pairings in Actions; no production weight updates |
| Body-ID spike/decision logs | **PASS** | spike parquet + game traces |
| Brian2 Cython compilerless runtime | **PASS** | precompiled cache verified without compiler |
| SHA-addressed persistent runtime base | **PASS** | runtime archive SHA → persistent Sandbox snapshot |
| One shared Vercel LIVE | **PASS** | fixed `connectome-live-broadcast` target |
| Real LIVE telemetry | **PASS** | frame > 0, x/y/action and both MaleCNS decisions verified |
| Public inference provenance UI | **PASS** | GARNET approved / ZEN baseline / candidates separated |
| Released MaleCNS SWC context | **PASS** | official EM centerlines, spectator-only |
| Historical ScreenData/H.264 export | **PASS** | retained as manual regression evidence |
| GARNET generation 2 | **APPROVED INFERENCE** | production read-only handoff |
| ZEN / LUD / NEZ generation 2 | **CANDIDATE** | cross-run lineage/resume evidence only |
| Continuous reward-driven learning | **OFF** | intentionally deferred |
| Four-character production-trained league | **NOT ESTABLISHED** | candidate lineage ≠ approved learned fighters |
| League/champion training | **NOT RUN** | later |
| Biological-vs-control causal comparison | **NOT RUN** | later |

Production viewer: `https://liveunjuno.vercel.app/connectome`

Canonical public contract: [`docs/PUBLIC_SURFACE_SPLIT.md`](docs/PUBLIC_SURFACE_SPLIT.md)

Current evidence/status: [`docs/STATUS.md`](docs/STATUS.md)

---

# P0 — Canonical biological substrate ✅

MaleCNS v1.0 supplies the anatomy and the pinned Shiu et al. code supplies LIF neural dynamics. Transmitter filtering, graph thresholding and game I/O are separately manifest-recorded assumptions. Legacy FlyWire/custom-network/PPO work is engineering history only.

**Gate: PASS.**

---

# P1 — Real MaleCNS → FightingICE control ✅

Numeric FightingICE observations stimulate selected real MaleCNS bodies through observation-dependent Poisson input. The whole LIF network advances and selected real output-body spike groups choose FightingICE actions.

**Gate: PASS.**

---

# P2 — Character-specific independent state ✅

GARNET / ZEN / LUD / NEZ maintain independent simulation state and RNG. Read-only anatomy/runtime assets can be shared; mutable neural state cannot.

This proves independent simulation identity. It does not by itself prove learned behavioral divergence.

**Gate: PASS.**

---

# P3 — Baseline + analysis logging ✅

The scheduled baseline records behavior while production learning remains off.

Logged evidence includes:

- game frame / observation / action / HP / position;
- stimulated sensory body IDs and rates;
- spike-event body IDs and biological times;
- output-body contributions;
- membrane summaries;
- outcomes;
- dataset/dynamics/interface provenance.

Current baseline schedule is every six hours. These runs are evaluation/logging, not training.

**Gate: PASS.**

---

# P4 — Renderer / morphology regression evidence ✅

The former rolling-video spectator proved that official FightingICE 960×640 `ScreenData` can be captured separately from the policy, encoded to H.264, aligned with body-ID activity and enriched with released MaleCNS SWC morphology.

That path is now **historical/manual regression evidence**, not the primary production LIVE. Its hourly schedule has been removed.

Pixels, SWC geometry and visualization annotations never enter the policy.

**Gate: PASS as regression evidence.**

---

# P5 — One shared production Vercel LIVE ✅

Current operational architecture:

```text
GitHub runtime release + approved inference state
        ↓
SHA-addressed persistent runtime snapshot
        ↓
fixed connectome-live-broadcast Sandbox
        ↓
FightingICE + two MaleCNS/Shiu workers
        ↓
/state + /events
        ↓
all viewers observe the same LIVE bout
```

Public contract:

- one fixed public broadcast target;
- no per-viewer match creation;
- `learning_enabled=false`;
- `policy_pixel_access=false`;
- exact runtime archive SHA/runtime-base provenance;
- real `frame > 0` telemetry;
- real x/y/action/facing data;
- both MaleCNS decision indices advance;
- recorded clips are never substituted and labelled LIVE;
- terminal/stopped shared Sandboxes are recycled from the current runtime base.

Current LIVE state:

- P1: **GARNET generation 2 approved inference**
- P2: **ZEN canonical baseline**
- ZEN/LUD/NEZ generation-2 candidate states are not served as production learned fighters.

**Gate: PASS.**

---

# P6 — Public Surface Freeze ← CURRENT

Before reward tuning changes behavior, freeze the observable and provenance contracts.

Required contracts:

- Vercel `/api/connectome/live` shared-broadcast schema;
- public session POST rejection;
- runtime SHA/runtime-base identity;
- live telemetry fields used by the arena;
- body-ID activity schema;
- SWC visualization boundary;
- checkpoint status wording;
- README / STATUS / ROADMAP / Pages / Vercel UI consistency;
- explicit warming/error states;
- no fabricated LIVE fallback.

Regression gates:

1. static `public-surface-contract` CI passes;
2. production shared-LIVE smoke resolves the current runtime release;
3. public individual-session POST returns the expected rejection;
4. shared LIVE reaches `ready=true`, `status=running`;
5. `frame > 0` and both MaleCNS decision indices are observed;
6. x/y/action telemetry exists for both sides;
7. public page identifies `GARNET G2 approved · ZEN baseline`;
8. ZEN/LUD/NEZ candidate lineage is visibly separated from production-served state;
9. learning and policy-pixel access remain disabled.

Reward tuning starts only after this surface remains stable across ordinary runtime/session turnover.

---

# P7 — Reward-design selection

Production learning remains OFF until one reward contract is selected.

Simple reference control:

```text
win   +1
loss  -1
draw   0
```

Current public baseline is extremely draw-heavy, so reward density and timeout/stalemate semantics must be measured rather than guessed.

Reward candidates must be compared while keeping fixed:

- MaleCNS/Shiu substrate;
- sensory mapping;
- action groups;
- Poisson randomness mechanism;
- decision interval;
- opponent schedule;
- plastic synapse class/update scale;
- runtime/game versions;
- evaluation seeds and compute budget.

Do not encode hand-designed preferred actions such as “move forward” or “attack” into reward unless that is explicitly the experiment being tested.

### Gate P7

PASS only when:

1. reward equation is versioned;
2. timeout/stalemate semantics are explicit;
3. existing trajectories can be rescored offline;
4. reward density/range is measured;
5. train/eval conditions are frozen;
6. one reward contract is selected before production weight updates.

---

# P8 — Character-specific persistent plasticity

After P7, maintain four independent learned states:

```text
GARNET state
ZEN state
LUD state
NEZ state
```

Prepared plasticity work targets declared existing KC→MBON candidate edges only. No new topology is created and transmitter sign remains immutable unless a separately declared experiment explicitly changes that assumption.

Each checkpoint must record:

- character and generation;
- parent checkpoint identity;
- match/update counts;
- code/data/interface/reward/plasticity IDs;
- RNG state;
- file hashes.

**Gate:** separate Actions runs restore generation N exactly, update only the intended character, atomically publish N+1, and reject damaged/incompatible state.

---

# P9 — Continuous learning + frozen evaluation

Target cycle:

```text
restore latest verified character state
        ↓
run one bounded training unit
        ↓
apply approved plasticity
        ↓
atomically publish generation N+1
        ↓
frozen evaluation fights (no updates)
        ↓
metrics / neural logs / provenance
        ↓
approved inference promotion only when evidence supports it
```

Exactly one canonical trainer advances a lineage at a time. Train and eval must remain distinct.

---

# P10 — League / archive

Add frozen champions and historical checkpoints so current characters are not judged only against co-evolving contemporaries. Opponent sampling and champion replacement rules must be explicit and logged.

---

# P11 — Circuit analysis

Use accumulated logs and learned-state diffs for:

- action/reward-conditioned body recruitment;
- neuromere / superclass / cell-type recruitment;
- event-aligned activity;
- KC→MBON multiplier changes;
- character-lineage divergence;
- repeated candidate pathways;
- targeted intervention / ablation.

Activity correlation is not causality. Causal claims require interventions.

---

# P12 — Biological-vs-control comparison

Only after learning is stable, compare canonical MaleCNS against declared matched controls while holding observation, action, reward, interface, opponents, compute budget and seeds fixed.

Report **PASS / FAIL / UNCERTAIN** against predeclared effect thresholds.

---

# Immediate queue

- [x] Canonical MaleCNS + pinned Shiu LIF runtime.
- [x] Real MaleCNS-controlled FightingICE.
- [x] Four independent character simulation states.
- [x] Analysis-grade body-ID logs.
- [x] Compilerless canonical Brian2 Cython runtime.
- [x] SHA-addressed persistent runtime base.
- [x] One shared Vercel LIVE.
- [x] Real production frame/decision/x/y/action telemetry gate.
- [x] GARNET G2 approved inference handoff.
- [x] ZEN/LUD/NEZ G2 candidate cross-run lineage evidence.
- [x] Public provenance panel separating served state from candidates.
- [x] Static public-surface architecture CI.
- [x] Remove hourly recorded-spectator schedule; retain manual regression path.
- [ ] Complete documentation/metadata consistency sweep.
- [ ] Observe Public Surface Freeze over ordinary LIVE lifecycle/recovery.
- [ ] Freeze timeout/stalemate and reward contract.
- [ ] Promote controlled character-specific plasticity only after reward freeze.
- [ ] Enable sequential continuous canonical training.
- [ ] Add champion/archive evaluation.
- [ ] Run causal circuit and biological-control experiments.

---

# Operational success

A visitor opens the Vercel arena and observes the same real FightingICE/MaleCNS process as every other viewer, with live fighter telemetry, neural activity, anatomical context, explicit runtime provenance and unambiguous checkpoint status. Failure/warming states remain visible rather than being replaced by synthetic or recorded LIVE content.

# Scientific success

Scientific success begins only after controlled reward/plasticity experiments demonstrate reproducible behavioral change under frozen evaluation conditions. Causal circuit claims require interventions or ablations rather than activity visualization alone.
