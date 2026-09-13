# Status

Canonical control path: **MaleCNS v1.0 anatomy + pinned Shiu et al. LIF dynamics + FightingICE v7.1**.

Production reward-driven learning is **OFF**.

## Dedicated public deployment — IMPLEMENTED, E2E PENDING

The public control/viewer app now lives in this repository (`app/`, `lib/`). It is explicitly isolated from unrelated Vercel projects.

Contract:

- dedicated Vercel project only;
- current project identity comes from `VERCEL_PROJECT_ID`;
- no hard-coded legacy project ID;
- repository variable `CONNECTOME_PUBLIC_BASE_URL` selects the production smoke target;
- missing production URL causes smoke jobs to skip, never to fall back to another site;
- root viewer `/`;
- control API `/api/live`;
- runtime materialization `/api/runtime-base`;
- one fixed `connectome-fighter-live-broadcast` target;
- `mode=single-shared-live-broadcast`;
- `audience_scope=shared-global`;
- `learning_enabled=false`;
- `policy_pixel_access=false`.

A dedicated production URL is **not considered verified** until `vercel-live-arena-smoke`, media smoke, browser smoke, and FlyBody same-decision smoke pass against that dedicated URL.

## Runtime publication separation — IMPLEMENTED

Runtime publication no longer stages into Vercel directly.

```text
publish-arena-runtime-bundle
  → precompile-arena-brian2-cython-cache
  → publish-flybody-runtime-addon
  → immutable rolling GitHub release
```

The dedicated Vercel app observes that release and owns SHA-addressed runtime-base staging. This removes the previous possibility that a release workflow could mutate an unrelated Vercel project.

The runtime base bakes in FightingICE font support and OSMesa together with the runtime archive before snapshotting.

## FlyBody physical embodiment — CI PASS

- upstream: `TuragaLab/flybody`;
- pinned commit: `d015e9bfe441bd90ae431bac24c55cb74bdbce26`;
- adapter: `malecns-annotated-motor-to-flybody-tripod-v2`;
- action dimension: **59**;
- backend: **OSMesa**;
- zero neural motor drive: phase-invariant neutral action, no active gait;
- neural drive: changes real FlyBody actuator commands and diverges the MuJoCo trajectory;
- FightingICE x/y/action is not used to position the FlyBody body;
- FlyBody policy access: **false**.

This is a project-defined MaleCNS→actuator interface, not a claimed biological motor-neuron→muscle map.

## Same-decision publication contract

When dedicated production compute is available, P1/P2 FlyBody state must match the live FightingICE/MaleCNS identity exactly:

- same round;
- same frame;
- same decision index;
- FlyBody adapter v2;
- `sim_steps > 0`;
- action dimension 59;
- real neural source body IDs;
- nonblank 320×240 physical FlyBody renders.

Until that dedicated production smoke passes, production FlyBody E2E remains **NOT YET VERIFIED**.

## Canonical substrate and control — PASS

- anatomy: **MaleCNS v1.0**;
- dynamics: pinned Shiu reference commit `2a83ad611cd9768f8c9723fc613ed27761a5feb5`;
- game: **FightingICE v7.1 + pyftg 2.3 + Java 21**;
- strict adapter: approximately **156,675 neurons / 6,025,920 recurrent synapses**;
- numeric FightingICE observations drive selected real sensory bodies through observation-dependent Poisson input;
- whole pinned Shiu LIF network advances;
- real output-body spike groups choose actions by deterministic spike-count argmax.

## Compilerless runtime — PASS

Canonical Brian2 remains Cython. GitHub Actions precompile the required cache under production path identity and verify compilerless reuse before publishing runtime assets.

## Checkpoint lineage

- **GARNET generation 2 — APPROVED INFERENCE**.
- **ZEN — canonical baseline in the shared LIVE contract**.
- ZEN/LUD/NEZ candidate training histories remain research evidence and are not auto-promoted.

## Research / training ledger — PASS

GitHub Pages / Actions remain the system of record for training workflows, reward/plasticity contracts, checkpoint lineage, match evidence, runtime provenance, raw artifacts, and scientific interpretation boundaries.

## Not yet demonstrated

- dedicated Vercel production E2E after project separation;
- frozen production reward semantics;
- continuous production learning;
- reproducible behavioral improvement caused by MaleCNS plasticity;
- four approved learned lineages advancing continuously;
- causal biological circuit mechanism from activity alone;
- biological-structure advantage over matched controls.
