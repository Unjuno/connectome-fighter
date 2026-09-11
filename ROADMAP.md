# Connectome Fighter Roadmap

Primary product goal:

> Keep a Drosophila-connectome-constrained fighter learning across many separate training jobs, preserve its lineage, and let people watch current and historical fights from GitHub Pages.

The scientific A/B test (biological topology vs matched rewires) is built on top of that operational system. Continuous learning is not itself evidence that biological wiring is superior.

## Design principles

1. **Persistent identity** — a fighter is a checkpoint lineage, not one CI process.
2. **Bounded training chunks** — GitHub Actions jobs resume, train, checkpoint, evaluate, publish, and stop cleanly.
3. **Train/eval separation** — evaluation never updates weights.
4. **Reproducibility** — every checkpoint records code, graph, routing, optimizer, RNG, generation, and match counts.
5. **Spectator-first telemetry** — every evaluation run can export browser-readable fight telemetry.
6. **No silent biology invention** — artificial sensory/action routing is versioned and recorded separately from biological graph data.
7. **One writer** — only one workflow may advance a lineage at a time.

---

## Current baseline

| Area | Status | Evidence / note |
|---|---|---|
| FightingICE 7.1 ↔ Python bridge | **PASS** | Audited Random-vs-Random headless round completed |
| FlyWire/Shiu v783 graph import | **PASS / hardening** | 138,639 neurons and 15,091,983 directed edges normalized; compact representation/routing validation continues |
| Connectome-driven live fight | **NOT YET GATED** | Next operational milestone |
| Persistent RL across jobs | **NOT IMPLEMENTED** | Issue #3 |
| Continuous league | **NOT IMPLEMENTED** | Issue #5 |
| Pages spectator | **SKELETON EXISTS** | Static status page and spectator data contract exist |
| Biological topology A/B | **NOT RUN** | Issue #4 |

---

# Phase 0 — Stabilize the biological runtime

**Objective:** make the real connectome cheap and deterministic enough to use repeatedly inside fight loops.

### Work

- Finalize compact graph format (`nodes` + compact edge arrays).
- Validate pinned sensory and descending-neuron routing.
- Cache immutable graph/runtime inputs between CI runs.
- Reuse the fixed sparse graph object across both fighters when topology is identical.
- Benchmark graph load, one neural update, one decision, and one full round.
- Record peak RSS and wall-clock throughput.

### Gate P0

PASS only when:

- the biological graph loads from provenance-checked inputs;
- routing hashes are stable;
- one controller step is deterministic for a fixed state/seed;
- a full round can run without OOM;
- runtime metrics are recorded in CI.

**Output:** reproducible connectome runtime artifact + benchmark report.

---

# Phase 1 — First connectome-controlled fight

**Objective:** prove that the real graph is actually in the game-control path.

### Architecture

```text
FightingICE observation
        ↓
versioned feature encoder
        ↓
annotation-derived sensory pool
        ↓
fixed Drosophila connectome dynamics
        ↓
annotation-derived descending pool
        ↓
untrained action readout
        ↓
FightingICE action
```

### Work

- Add `ConnectomePolicy` to the live pyftg bridge.
- Reset neural state at the documented episode boundary.
- Export policy/checkpoint IDs into every trajectory.
- Add an ablation that bypasses the connectome; it must produce detectably different execution provenance.
- Run ConnectomePolicy vs RandomPolicy and ConnectomePolicy vs ConnectomePolicy.

### Gate P1

PASS only when:

- at least one complete FightingICE round is controlled through the real graph;
- both sides' traces pass the pair audit;
- the trace contains graph hash + routing hash + controller version;
- disconnect/truncation is never converted into a loss;
- connectome bypass detection is tested.

**Output:** first real `connectome → FightingICE` replay.

---

# Phase 2 — Durable checkpoint lineage

**Objective:** make one fighter survive across separate GitHub Actions jobs.

### Checkpoint schema

Each checkpoint must contain at least:

- schema version;
- generation / lineage ID;
- readout/value-head parameters;
- optimizer state;
- RNG states;
- total training matches and update count;
- code commit SHA;
- connectome graph hash;
- routing hash;
- action/observation contract version;
- training algorithm + hyperparameters;
- SHA-256 of the checkpoint package.

### Storage policy

- Actions cache: immutable dependencies only.
- Durable rolling checkpoint: repository-associated durable storage (initially a rolling Release asset or equivalent).
- Champion/archive snapshots: immutable historical checkpoints.
- Keep the latest known-good checkpoint so a corrupt write cannot destroy the lineage.

### Gate P2

PASS only when:

1. workflow run A creates checkpoint `g=N`;
2. a separate workflow run B restores exactly `g=N`;
3. run B advances to `g=N+1` without restarting;
4. split-run continuation matches uninterrupted continuation within documented determinism limits;
5. checksum/metadata validation rejects a damaged or incompatible checkpoint.

**Output:** persistent fighter identity independent of any one CI process.

---

# Phase 3 — First persistent reinforcement learning

**Objective:** make the fighter measurably improve while the biological graph remains fixed.

### Initial learning scope

For the first learning milestone:

- connectome topology: **fixed**;
- internal graph weights: **fixed**;
- sensory routing: **fixed**;
- trainable: action readout + value head only;
- primary reward: win `+1`, loss `-1`, draw `0`;
- evaluation: no weight update.

Use one documented RL algorithm first. PPO is the current default candidate; changing algorithm is a later A/B, not part of initial pipeline debugging.

### Opponents

Start with a mixed opponent pool:

- RandomPolicy;
- a simple scripted baseline;
- frozen earlier checkpoints;
- current self-play peer.

Do not evaluate progress only against the current co-evolving opponent.

### Metrics

- total training matches;
- win/draw/loss vs fixed baselines;
- Elo or another explicitly defined rating for league visualization;
- learning-curve AUC;
- action entropy;
- checkpoint generation;
- wall-clock throughput.

### Gate P3

PASS only when:

- at least two independent Actions training jobs resume the same lineage;
- later checkpoints outperform generation 0 on at least one frozen baseline under a predeclared evaluation protocol;
- evaluation traces are marked non-trainable;
- no evaluation fight updates model state;
- all learning curves retain independent training seed identity.

This gate proves **persistent learning**, not biological superiority.

**Output:** the first continuously learning fly fighter.

---

# Phase 4 — Continuous Actions training loop

**Objective:** make training recur automatically without requiring a manual restart.

### Workflow cycle

```text
restore latest checkpoint
        ↓
validate graph/routing/checkpoint hashes
        ↓
train for bounded wall-clock or match budget
        ↓
atomic checkpoint save
        ↓
evaluate vs league/fixed baselines
        ↓
export replay + metrics
        ↓
publish spectator data
        ↓
job exits cleanly
        ↓
next scheduled job resumes
```

### CI policy

- Use a concurrency group with **one training writer**.
- Do not cancel an in-progress run during checkpoint commit.
- Leave safety margin below hosted-runner job limits.
- Prefer a configurable training chunk (for example, a few hours or a fixed match count) rather than trying to keep one process alive forever.
- Manual `workflow_dispatch` remains available for debugging.
- Scheduled runs can be enabled only after checkpoint resume is proven.

### Failure handling

- no checkpoint advancement on failed audit;
- no loss reward for transport failure;
- keep last known-good generation;
- surface stale/failed training status on Pages.

### Gate P4

PASS only when the lineage automatically advances through multiple scheduled workflow runs without manual state repair.

**Output:** CI-hosted continuous training service.

---

# Phase 5 — GitHub Pages spectator

**Objective:** make the system observable as a game, not just as logs.

### Pages v1

Show:

- current generation;
- lineage/checkpoint ID;
- total matches;
- current champion;
- latest evaluation W/D/L;
- Elo/rating history;
- learning curve;
- last successful training time;
- graph/routing version;
- latest fight replay.

### Replay format

Actions exports browser-readable telemetry, for example:

```json
{
  "p1_checkpoint": "fly-g00421",
  "p2_checkpoint": "champion-g00380",
  "frames": [
    {"frame": 0, "p1": {"hp": 400, "x": 100, "action": "NEUTRAL"}, "p2": {"hp": 400, "x": 300, "action": "NEUTRAL"}}
  ]
}
```

Pages replays telemetry in JavaScript; FightingICE/Java does not run in the browser.

### Pages v2

- timeline scrubber;
- pause/speed controls;
- current vs champion selector;
- current vs archived generation selector;
- matchup history;
- checkpoint lineage graph;
- downloadable evaluation metadata.

Optional later feature: rendered MP4/GIF of selected evaluation fights. Telemetry replay remains the canonical reproducible representation.

### Gate P5

PASS only when a newly completed evaluation fight appears on Pages automatically, with both checkpoint IDs and a working replay.

**Output:** public spectator arena.

---

# Phase 6 — Population / league learning

**Objective:** avoid one fighter overfitting to one contemporary opponent.

### Start small

Maintain several roles:

- **learner** — current trainable lineage;
- **champion** — best frozen checkpoint by declared selection rule;
- **archive** — periodic historical checkpoints;
- **baselines** — fixed random/scripted policies.

### Opponent sampling

The exact mixture is a tunable experimental parameter. A starting policy can mix:

- self-play/current peer;
- champion;
- archived generations;
- fixed baselines.

Do not hard-code a scientifically meaningful conclusion into the opponent distribution; record it per training run.

### Gate P6

PASS only when:

- opponent identity/distribution is logged;
- champion replacement is deterministic from declared metrics;
- historical opponents remain reproducible;
- catastrophic forgetting can be detected against the archive.

**Output:** evolving fighter league rather than a single two-agent arms race.

---

# Phase 7 — Biological topology A/B

**Objective:** answer the research question after the training platform is trustworthy.

### Conditions

A. verified Drosophila-derived topology  
B. degree/sign-preserving rewired topology  
C. optional engineering baseline (RNN/MLP or other declared controller)

Hold constant:

- observations;
- actions;
- routing rule;
- reward;
- trainable parameter classes;
- initialization rule;
- training/evaluation opponents;
- optimizer and hyperparameters;
- match/compute budget;
- paired seeds where applicable.

### Primary outcomes

- sample efficiency / matches-to-threshold;
- learning-curve AUC;
- held-out opponent performance;
- robustness to action/sensory ablation;
- transfer to changed action spaces/opponents.

### Gate P7

Report **PASS / FAIL / UNCERTAIN** against a prespecified practical effect threshold and uncertainty interval. Do not select only environments in which the biological graph wins.

**Output:** first defensible topology result.

---

# Phase 8 — Scale beyond hosted CI

**Trigger:** hosted Actions becomes the bottleneck, not before.

Keep GitHub Actions as orchestration and Pages as spectator UI, but move training execution to a self-hosted CPU/GPU runner or external compute node.

The checkpoint, telemetry, evaluation, and Pages contracts must remain unchanged so infrastructure can be swapped without changing the experiment definition.

**Output:** near-continuous higher-throughput training without redesigning the project.

---

# Priority order

| Priority | Phase | Why now? |
|---|---|---|
| **P0** | Stabilize connectome runtime | Training cannot be trusted or afforded otherwise |
| **P1** | Real connectome-controlled fight | Proves the graph is genuinely in the control loop |
| **P2** | Durable checkpoints | Required for any CI-based continuous identity |
| **P3** | Persistent RL | First actual learning result |
| **P4** | Scheduled continuous training | Turns experiments into a continuously evolving agent |
| **P5** | Spectator Pages | Makes fights visible and operational state observable |
| **P6** | League/population | Improves robustness and creates interesting matchups |
| **P7** | Biological A/B | Scientific comparison only after pipeline validation |
| **P8** | Self-hosted scale | Only when CI throughput becomes limiting |

---

# Near-term execution queue

The next implementation sequence is intentionally narrow:

- [ ] **T1** Finish compact graph + routing validation.
- [ ] **T2** Run one audited real-connectome-controlled FightingICE round.
- [ ] **T3** Implement versioned/checksummed checkpoint save/load.
- [ ] **T4** Prove resume across two separate workflow runs.
- [ ] **T5** Add fixed-connectome PPO/readout training.
- [ ] **T6** Train for two or more chunks and verify measurable progression against frozen baselines.
- [ ] **T7** Export one evaluation replay to `site/data/`.
- [ ] **T8** Make Pages automatically show the latest real fight.
- [ ] **T9** Enable scheduled training with a single-writer concurrency lock.
- [ ] **T10** Add champion/archive league.
- [ ] **T11** Begin real-vs-rewired confirmatory A/B.

The project should not advance to T9 until T4 is proven. It should not make biological-topology claims before T11.

---

# Definition of success

The operational project is successful when a visitor can open GitHub Pages and see:

> a named fly-fighter lineage that has accumulated real FightingICE training matches across multiple CI jobs, its current and historical performance, and a replay of a recent evaluation fight.

The scientific project is successful only later, if controlled experiments establish a reproducible effect of the biological topology relative to matched alternatives.
