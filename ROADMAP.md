# Connectome Fighter Roadmap

Primary goal:

> Run a real MaleCNS-constrained FightingICE controller in reproducible cloud infrastructure, expose one auditable shared LIVE inference surface, preserve analysis-grade neural/checkpoint provenance, and only then enable controlled reward-driven plasticity with separate character lineages.

## Current gates

| Stage | Status | Note |
|---|---|---|
| MaleCNS provenance + Shiu adapter | **PASS** | ~156,675 neurons / 6,025,920 recurrent synapses |
| MaleCNS-controlled FightingICE | **PASS** | independent Brian2 workers |
| Body-ID neural logs | **PASS** | sensory, spikes, motor contributors |
| Compilerless Brian2 Cython runtime | **PASS** | precompiled cache verified |
| Neural-driven FlyBody MuJoCo physics | **PASS in CI** | 59 actuators, OSMesa, adapter v2 |
| Dedicated Next.js public app | **IMPLEMENTED** | isolated in this repo |
| Dedicated Vercel production project | **PENDING DEPLOYMENT/VERIFICATION** | must not reuse unrelated projects |
| Same-decision production FlyBody E2E | **NOT YET VERIFIED** | requires dedicated production compute |
| Continuous reward-driven learning | **OFF** | intentionally deferred |

## P0–P4 — substrate, control, state, logs, renderer evidence ✅

Canonical MaleCNS/Shiu control, independent character state, body-ID logging, and spectator ScreenData/morphology paths are established. Visualization remains outside policy input.

## P5 — Dedicated shared LIVE ← CURRENT

Required architecture:

```text
GitHub runtime release
  → compilerless Brian2 cache
  → pinned FlyBody addon
  → SHA-addressed persistent runtime base
  → connectome-fighter-live-broadcast
  → FightingICE + two MaleCNS workers + FlyBody physics
  → one dedicated public viewer
```

Gate:

1. dedicated Vercel project exists;
2. it serves this repository's root Next.js app;
3. `/api/runtime-base` stages only under that project's `VERCEL_PROJECT_ID`;
4. `/api/live` reaches `ready=true`, `status=running`;
5. GARNET vs ZEN shared-global broadcast is observed;
6. learning and policy-pixel access remain false;
7. official ScreenData is nonblank;
8. real annotated MaleCNS activity is nonempty;
9. FlyBody P1/P2 renders are nonblank real MuJoCo frames;
10. FlyBody round/frame/decision exactly match live MaleCNS/FightingICE telemetry.

No other Vercel project may be used as a fallback target.

## P6 — Public surface freeze

After P5 passes repeatedly, freeze API schemas, runtime provenance, approved/candidate wording, failure states, and scientific boundaries. Warming/capacity failures must remain explicit; no synthetic or recorded LIVE substitute is allowed.

## P7 — Reward design selection

Production learning remains OFF until reward semantics, stalemate/timeout semantics, evaluation seeds, opponent schedule, and compute budget are frozen. Reward changes must be isolated from infrastructure changes.

## P8 — Character-specific persistent plasticity

Maintain independent character states and version every checkpoint with parent identity, hashes, RNG state, reward/plasticity IDs, and update counts. No auto-promotion into public inference.

## P9 — Continuous learning + frozen evaluation

Only after reward/plasticity gates pass: restore latest verified state → bounded training → approved update → atomic candidate publication → frozen evaluation → explicit promotion decision.

## P10–P12 — league, circuit interventions, matched controls

Add champion/archive evaluation, causal interventions/ablations, and biological-vs-control comparisons under predeclared metrics. Activity correlation alone is not causality.

## Immediate queue

- [x] Canonical MaleCNS + pinned Shiu LIF runtime.
- [x] Real MaleCNS-controlled FightingICE.
- [x] Compilerless runtime bundle.
- [x] Neural-driven real FlyBody physics contract.
- [x] Dedicated public app implementation.
- [x] Remove direct Vercel staging from runtime release workflows.
- [x] Make production smoke require an explicit dedicated base URL.
- [ ] Merge dedicated-web contract after CI.
- [ ] Create/deploy `connectome-fighter-live` dedicated Vercel project.
- [ ] Set `CONNECTOME_PUBLIC_BASE_URL` to the dedicated production URL.
- [ ] Pass dedicated arena/media/browser/FlyBody production smokes.
- [ ] Observe lifecycle recovery before freezing the public surface.
- [ ] Resume reward/plasticity work only after the public/runtime boundary is stable.
