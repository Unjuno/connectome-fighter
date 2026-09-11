# Connectome Fighter Roadmap

Primary goal:

> Run real MaleCNS-constrained FightingICE fighters entirely in cloud infrastructure, retain analysis-grade neural logs, expose a rolling watchable arena, and only then enable controlled reward-driven plasticity with separate character lineages.

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
versioned output-body groups
        ↓
FightingICE action
```

No MLP/RNN/custom-sigmoid controller replaces the fly neural substrate in the canonical path.

---

## Current state

| Stage | Status | Evidence / note |
|---|---|---|
| MaleCNS provenance + Shiu adapter | **PASS** | 156,675 neurons / 6,025,920 runtime synapses |
| Pinned Shiu LIF reference runtime | **PASS** | upstream `model.py` executes directly |
| MaleCNS-controlled FightingICE | **PASS** | independent per-fighter Brian2 workers |
| Four-character baseline | **PASS** | all 6 pairings run in Actions |
| Body-ID spike/decision logs | **PASS** | full spike parquet + game traces |
| Real FightingICE video | **PASS** | official 960×640 ScreenData, separate spectator socket |
| ~1 minute clips | **PASS** | 6 real rounds / clip, not slowed footage |
| Rolling 3-clip queue | **PASS** | latest + previous 2 via release assets |
| Vercel pseudo-live viewer | **PASS** | 30 s polling + next-clip countdown |
| Playback-synchronized neural activity | **PASS** | decision-window body-ID activity |
| Released MaleCNS SWC morphology | **PASS** | official 8 nm EM centerlines, spectator-only |
| Continuous reward learning | **OFF** | intentionally not promoted yet |
| Four persistent learned character lineages | **NOT RUN** | after reward gate |
| League/champion training | **NOT RUN** | later |
| Biological-vs-control causal comparison | **NOT RUN** | later |

Proven morphology-enabled rolling spectator run: Actions `34636313291` — **PASS**.

Viewer: `https://liveunjuno.vercel.app/connectome`

Detailed spectator contract: [`docs/SPECTATOR_PIPELINE.ja.md`](docs/SPECTATOR_PIPELINE.ja.md).

---

# P0 — Canonical biological substrate ✅

MaleCNS v1.0 is the anatomy and the pinned Shiu et al. LIF code supplies the neural time dynamics. Transmitter filtering, graph thresholding and the artificial game interface are manifest-recorded separately. Legacy FlyWire/custom-sigmoid/PPO work is engineering evidence only.

**Gate: PASS.**

---

# P1 — Real MaleCNS → FightingICE control ✅

Numeric FightingICE observations stimulate selected real MaleCNS bodies through Poisson input. The whole LIF network advances, real output-body spike counts select an action, and audited FightingICE rounds complete.

**Gate: PASS.**

---

# P2 — Character-specific independent neural states ✅

GARNET / ZEN / LUD / NEZ use independent mutable simulation state and RNG. Read-only anatomy assets can be shared, but membrane/synaptic state is not shared.

Learning is still OFF, so this gate proves independent simulation identity, not learned divergence.

**Gate: PASS.**

---

# P3 — Continuous baseline + analysis logging ✅

The baseline scheduler records behavior before production plasticity is enabled.

Logged data includes:

- game frame / observation / action / HP / position;
- stimulated sensory body IDs and rates;
- all spike-event body IDs and biological times;
- output-body contributions;
- membrane summary;
- outcome;
- canonical dataset/dynamics/interface provenance.

This supports post-hoc recruitment analysis. It does not by itself establish causal circuit mechanisms.

**Gate: PASS.**

---

# P4 — Real-game video spectator ✅

FightingICE itself renders the game in headless mode. A separate pyftg stream receives official 960×640 `ScreenData` and encodes H.264 video. Pixels never enter the MaleCNS policy.

Six real 600-frame rounds are recorded into an approximately one-minute clip. The video is not a rectangle reconstruction and is not time-stretched footage.

**Gate: PASS.**

---

# P5 — Rolling Vercel arena + neural visualization ✅

Operational architecture:

```text
GitHub Actions hourly
  ↓
select next of 6 character pairings
  ↓
6 canonical FightingICE rounds
  ↓
~1 minute real ScreenData MP4
  ↓
body-ID spike log
  ├─ decision-window structure activity
  └─ released SWC morphology for top active bodies
  ↓
latest / previous-1 / previous-2
  ↓
queue.json + stable Release assets
  ↓
Vercel /connectome polls every 30 s
```

Completed viewer behavior:

- NOW + PREVIOUS 1 + PREVIOUS 2;
- countdown from `next_expected_at`;
- automatic switch when `current_clip_id` changes;
- four-character W/L/D and win rate;
- recent experiment logs;
- P1/P2 body-ID activity synchronized to video playback;
- `somaNeuromere`, `superclass`, `type` activity summaries;
- official MaleCNS SWC X–Z morphology projection;
- currently active top bodies rendered brighter/thicker;
- direct link to Actions evidence.

The flat annotation table did not expose physical `pos_x/y/z`; those coordinates were not invented. Geometry comes from separately released official SWC skeletons in MaleCNS EM coordinates (8 nm units).

After each full six-pair spectator epoch, character Poisson seeds advance so the next epoch does not replay exactly the same stochastic sequence.

**Gate: PASS.**

---

# P6 — Freeze spectator/data contracts ← CURRENT CLOSEOUT

Before production learning changes behavior, freeze these interfaces:

- queue schema;
- stable video asset names;
- body-ID spike schema;
- decision-window activity timeline;
- SWC visualization boundary;
- Vercel polling behavior;
- evidence/run links.

Minimum regression gate:

1. a scheduled rolling run completes;
2. queue remains exactly ≤3 clips;
3. video is 45–100 s, H.264, 960×640;
4. P1/P2 activity timeline is non-empty;
5. released SWC morphology loads for at least one body per side;
6. Vercel state API returns the new `current_clip_id` without a viewer redeploy;
7. learning remains disabled during this gate.

This is the final infrastructure gate before reward selection.

---

# P7 — Reward-design selection

Production learning remains OFF until one reward contract is selected.

Current simple control:

```text
win   +1
loss  -1
draw   0
```

The user's current hypothesis is that the game itself may provide enough selection pressure if timeout/stalemate handling is designed carefully. A key comparison is whether a no-progress timeout should penalize both fighters rather than produce zero reward.

Reward candidates must be compared while keeping fixed:

- MaleCNS/Shiu substrate;
- sensory mapping;
- action groups;
- Poisson randomness mechanism;
- decision interval;
- opponent schedule;
- plastic synapse class and update scale.

Do not reward manually desired actions such as “move forward” or “press attack”.

Existing reward/plasticity/checkpoint workflows are **smoke experiments**, not the production training lineage. Their results may inform P7, but do not imply that continuous learning has been enabled.

### Gate P7

PASS only when:

1. reward equation is versioned;
2. timeout/stalemate semantics are explicit;
3. existing trajectories can be rescored offline;
4. reward density/range is measured;
5. one reward is frozen before production weight updates.

---

# P8 — Character-specific persistent plasticity

After P7, maintain four independent learned states:

```text
GARNET state
ZEN state
LUD state
NEZ state
```

Initial prepared plasticity scope is existing KC→MBON candidate edges only. No new topology is created and transmitter sign remains immutable.

Each checkpoint must record generation, match/update counts, code/data/interface/reward IDs, RNG state and checksum.

**Gate:** separate Actions runs must restore generation N exactly, update only the intended character, advance to N+1, and reject damaged/incompatible state.

---

# P9 — Continuous learning + frozen evaluation

Cycle:

```text
restore character states
        ↓
training fights
        ↓
post-match approved plasticity
        ↓
atomic checkpoint
        ↓
frozen evaluation fights (no update)
        ↓
video + activity + metrics
        ↓
rolling Vercel arena
```

Train/eval must stay distinct.

---

# P10 — League / archive

Add frozen champions and historical checkpoints so a current character cannot be judged only against a co-evolving contemporary opponent. Opponent sampling and champion replacement rules must be logged.

---

# P11 — Circuit analysis

Use accumulated logs and learned-state diffs for:

- action/reward-conditioned body recruitment;
- neuromere / superclass / cell-type recruitment;
- playback/event-aligned activity;
- KC→MBON multiplier changes;
- character-lineage divergence;
- repeated candidate pathways;
- targeted intervention / ablation.

Activity correlation is not causality; causal claims require interventions.

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
- [x] Real FightingICE ScreenData recording.
- [x] Six-round ~1 minute clips.
- [x] Rolling latest + previous two queue.
- [x] Vercel 30 s polling / countdown.
- [x] Playback-synchronized structural activity.
- [x] Official MaleCNS SWC morphology visualization.
- [ ] Freeze P6 spectator/data schema after scheduled regression run.
- [ ] Select timeout/stalemate semantics and reward contract.
- [ ] Promote a character-specific plasticity lineage only after reward freeze.
- [ ] Enable continuous canonical learning.
- [ ] Add champion/archive evaluation.
- [ ] Run causal circuit and biological-control experiments.

---

# Operational success

A visitor can open the Vercel arena and watch actual FightingICE clips generated entirely in cloud infrastructure, switch among the current and previous two fights, see when the next clip is expected, inspect four-character results, and watch the two MaleCNS neural activity displays change with playback using real body-ID spikes and released morphology.

# Scientific success

Scientific success begins only after controlled reward/plasticity experiments demonstrate reproducible behavioral change, and causal circuit claims require interventions or ablations rather than activity visualization alone.
