# Connectome Fighter Roadmap

Primary goal:

> Run a real MaleCNS-constrained FightingICE controller reproducibly, expose auditable neural and physical spectator outputs, and evaluate controlled plasticity with separate character lineages and explicit scientific boundaries.

## Current gates — updated 2026-09-14

| Stage | Status | Evidence boundary |
|---|---|---|
| MaleCNS provenance + pinned Shiu adapter | Established project baseline | Real anatomy, simulated neural dynamics |
| MaleCNS-controlled FightingICE + body-ID logs | Established project baseline | Numeric game input; spectator pixels excluded |
| Compilerless Brian2 runtime | Verified in runtime CI | Version/path-specific compiled cache |
| FlyBody publisher software + real physics/process lifecycle | CI PASS, PR #57 | 42 software + 2 physics/process tests; engineering neural fixtures |
| Dedicated Vercel project and Next.js app | Deployed | `connectome-fighter`; separate from unrelated applications |
| Candidate evaluation videos | Operational at last API check | Research candidate, not promoted public inference |
| Real game → MaleCNS → FlyBody → browser functional E2E | CI IMPLEMENTED; result pending | `ci-stack-e2e`, PR #58; no synthetic neural fixture or cloud allocation |
| Vercel shared-LIVE deployment acceptance | BLOCKED at last check | Sandbox capacity; must not be reported as CI PASS |
| Learning-frequency/reward redesign | Not changed by infrastructure work | Existing GitHub research candidates are not production learning |
| Production reward-driven learning | OFF | Explicit promotion and rollout approval required |

No percentage is assigned: component coverage, full-stack functionality, deployment health and scientific validity are different gates.

## P0–P4 — substrate, control, state and evidence

Established: MaleCNS/Shiu control, independent character state, body-ID logs, checkpoint provenance, compilerless runtime and official FightingICE ScreenData. FlyBody uses pinned upstream MuJoCo physics with the project-defined adapter v2; this is not an identified biological motor-neuron-to-muscle map.

## P5A — Functional full-stack E2E in CI ← CURRENT

`ci-stack-e2e` starts the production session entrypoint on an ephemeral GitHub runner:

```text
SHA-verified runtime assets + tested source checkout
  → real FightingICE headless game
  → two real-connectome Shiu/Brian2 LIF workers
  → actual game-derived annotated neural decision log
  → existing neural adapter v2 + FlyBody/MuJoCo/OSMesa
  → production HTTP/state/PNG publishers
  → actual Next.js /live viewer + Chromium
```

Acceptance requires all of the following in one run, with saved evidence:

1. Asset hashes, model/anatomy identity, source checkout and dependency environment recorded.
2. Both players produce nonzero simulated spikes and nonempty annotated motor-source IDs.
3. Two progressing, fresh round/frame/decision-matching telemetry/activity/FlyBody samples; physical clocks valid; state/PNG SHA-256 bindings match.
4. Official ScreenData progresses. Exact ScreenData frame identity is not asserted without dedicated metadata.
5. Actual browser decodes the game and both physical fly images, observes both-side decision/image progression, and has no execution errors or mobile overflow.
6. The read-only game session completes without error. No training, reward modification or checkpoint promotion occurs.

CI substitutes only cloud allocation/address discovery with a fixed loopback origin. It does not mock neural inputs, game results, physics, HTTP payloads or image bytes. The production viewer rejects this wiring inside Vercel or outside standalone CI.

After P5A passes, learning-frequency and reward **design** may proceed. A Vercel billing/availability issue is not a logical prerequisite for offline experimental design. Passing CI does not authorize production learning or promotion.

## P5B — Dedicated shared-LIVE deployment acceptance (parallel infrastructure gate)

The dedicated project already exists. Verify project isolation, OIDC, runtime staging, quota/capacity, real networking, supervisor/session recovery, and repeated public arena/media/browser/FlyBody probes. `CONNECTOME_PUBLIC_BASE_URL` must explicitly select the dedicated target. Missing configuration or capacity yields SKIP/UNCERTAIN, never PASS or fallback to another application.

CI P5A cannot establish Vercel P5B. Public LIVE claims and rollout require P5B; no recorded or synthetic LIVE substitution is allowed.

## P6 — Versioned public and experimental contracts

Freeze the functional data/schema/provenance contract after P5A, with deployed-state wording kept accurate. Freeze public operational behavior after P5B. Input freshness, dropped physical time, held-input rather than lossless-replay semantics, and state/PNG hash verification must remain explicit.

## P7 — Learning frequency and reward design selection

Separate observation/decision cadence, experience collection, between-batch plasticity updates, evaluation cadence, and publication/promotion. Compare any new reward against the existing research configuration rather than treating it as a validated optimum. Predeclare victory/defeat, HP difference, timeout/draw, inactivity/stalemate and invalid/truncated-round semantics; fix evaluation seeds, opponent schedule and compute budget. Do not mix infrastructure and reward changes in one experiment.

## P8 — Character-specific persistent plasticity

Version independent character lineages with parent checkpoint, graph/interface hashes, RNG state, reward/plasticity IDs and update count. Freeze both policies within each round. Existing rolling candidates remain research artifacts; no automatic promotion to approved inference.

## P9 — Controlled learning and frozen evaluation

Restore verified state → bounded collection → between-batch update → atomic candidate publication → frozen evaluation → explicit promotion decision. Require behavioral evaluation, not merely changed weights or passing software tests. Production rollout remains gated on P5B and explicit approval.

## P10–P12 — League, interventions and matched controls

Add fixed baselines, champions and archived opponents; then circuit interventions/ablations and matched topology/weight controls. Activity correlation is not a causal biological mechanism. Biological-structure advantage requires a controlled comparison.

## Immediate queue

- [x] Separate the dedicated app from unrelated projects.
- [x] Verify publisher input expiry, rotation, restart and actual MuJoCo subprocess lifecycle.
- [x] Implement quota-independent full-stack CI and actual /live viewer.
- [ ] Inspect one complete passing P5A run and its saved artifacts; address failures rather than weakening gates.
- [ ] After P5A, freeze the experimental contract and design learning frequency/reward comparisons.
- [ ] Independently resolve dedicated deployment capacity and complete P5B public probes.
- [ ] Evaluate plasticity against frozen baselines before any promotion or production-learning decision.
