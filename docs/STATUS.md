# Status

Canonical production path: **MaleCNS v1.0 anatomy + pinned Shiu et al. LIF dynamics + FightingICE v7.1**.

Production reward-driven learning is currently **OFF**. Existing reward/plasticity/checkpoint workflows are research or engineering evidence unless explicitly promoted.

## Production public LIVE — PASS

Viewer: **https://liveunjuno.vercel.app/connectome**

The public arena is one fixed shared Vercel broadcast:

- `mode=single-shared-live-broadcast`;
- `audience_scope=shared-global`;
- fixed target `connectome-live-broadcast`;
- public per-viewer match creation disabled;
- `learning_enabled=false`;
- `policy_pixel_access=false`;
- all viewers attach to the same SSE/state telemetry;
- viewer presence can extend the same shared Sandbox session near expiry; viewer count never multiplies fight processes;
- shared public process executes **6 FightingICE rounds per bootstrap**;
- recorded clips are not substituted and labelled LIVE.

Current matchup: **GARNET approved generation-2 inference vs ZEN canonical baseline**. ZEN/LUD/NEZ generation-2 states remain candidate lineage evidence and are not served as approved learned fighters.

## Neural activity → action → fight — PASS

The public page and production telemetry synchronize one canonical decision window end-to-end:

1. real MaleCNS sensory body IDs and Poisson rates;
2. recurrent whole-network spikes, active body count, biological window and membrane summary;
3. real output-body motor contributors;
4. all seven action-group spike counts;
5. selected action and actual FightingICE x/y, facing and HP state.

Fly position is the real FightingICE position, fly pose is driven by the selected action, and the damage pulse is driven by real HP loss. Body-ID activity without released physical coordinates is shown as a non-spatial index; no anatomical coordinates are invented.

The strict production smoke verifies schema v3, six-round warm execution, non-empty sensory/motor telemetry, all seven action groups, selected-action/max-group consistency, and the public five-stage causal UI.

## Production Vercel inference proof — PASS

Current verified production evidence on 2026-09-12:

- runtime archive SHA-256: `f304bc4f0e7c19faca517a550f36dd566cb2f8b34e9a33627370aa3fec074004`;
- runtime archive size: **439,021,953 bytes**;
- runtime base: `connectome-runtime-f304bc4f0e7c19fa`;
- runtime snapshot: `snap_GnmkXhXrF8QAbow2cxdqDq3q9rL5`;
- Python `3.10.21` / Brian2 `2.5.1` / Cython `0.29.36` / NumPy `1.24.0`;
- included neurons: **156,675**;
- recurrent runtime synapses: **6,025,920**;
- compilerless Brian2 Cython cache reuse: **verified**;
- cache contents: **30 files / 15 shared objects / 5,776,256 bytes**;
- host-specific `-march=native`: **excluded**;
- telemetry schema: **3**;
- shared rounds per process: **6**;
- compilerless release E2E: Actions `34700529205` — **PASS**;
- strict production causal-LIVE smoke: Actions `34700813732` — **PASS**.

Observed strict-smoke sample: round 1 / frame **421**, GARNET decision **7**, ZEN decision **7**, **8,971 / 8,813** network spikes. Both sides selected `B`; the `B` output group was maximal (55 and 56 spikes respectively). Real sensory-body drive and real motor-body contributions were present in the same decision window.

Machine-readable proof: [`site/data/runtime-proof.json`](../site/data/runtime-proof.json).

## Shared LIVE lifecycle — PASS

- public broadcast post-fight/post-session holds remain short;
- ordinary one-shot diagnostics retain longer observability;
- terminal/stopped fixed-name Sandboxes are recycled from the current runtime base;
- one public bootstrap runs six rounds before a process recycle;
- `/api/connectome/live` acts as an idempotent audience heartbeat;
- when the shared session is near expiry and viewers are present, the same session is extended rather than forking a viewer-specific process;
- the long-running supervisor command timeout is aligned to Vercel Sandbox's five-hour ceiling.

No viewer heartbeat means no audience-driven extension, so an idle ephemeral broadcast can expire naturally.

## Runtime snapshot / compilerless Cython — PASS

The canonical backend remains **Brian2 Cython**. Vercel Sandbox images do not provide a C compiler, so required extensions are precompiled in GitHub Actions under production path identity and released only after compilerless reuse reaches worker `ready`.

The immutable runtime archive is staged once into a SHA-addressed persistent Sandbox; its snapshot is the source of the public ephemeral LIVE Sandbox. Character state remains separately manifest/SHA verified.

## Canonical substrate and control — PASS

- anatomy: **MaleCNS v1.0**;
- dynamics: pinned Shiu reference commit `2a83ad611cd9768f8c9723fc613ed27761a5feb5`;
- game: **FightingICE v7.1 + pyftg 2.3 + Java 21**;
- strict adapter: **156,675 neurons / 6,025,920 recurrent synapses**;
- numeric FightingICE observations drive selected real sensory bodies through observation-dependent Poisson input;
- whole pinned Shiu LIF network advances;
- real output-body spike groups choose actions by deterministic spike-count argmax;
- no epsilon-greedy/random action injection in the canonical path.

## Checkpoint lineage

- **GARNET generation 2 — APPROVED INFERENCE**: used by production LIVE.
- **ZEN generation 2 — CANDIDATE LINEAGE**.
- **LUD generation 2 — CANDIDATE LINEAGE**.
- **NEZ generation 2 — CANDIDATE LINEAGE**.

All four have cross-run-resumable lineage plumbing; this does **not** establish a four-character production-trained league.

## Four-character baseline / public match log — PASS

`.github/workflows/malecns-baseline-batch.yml` evaluates all six pairings every six hours with unchanged weights and updates normalized public logs. These are evaluation/logging runs, not production learning.

The public data remains draw-heavy; reward tuning is intentionally downstream of the runtime/public-surface freeze.

## GitHub research / training ledger — PASS

GitHub Pages / Actions are the system of record for training workflows, reward/plasticity contracts, checkpoint lineage, approved inference handoff, match evidence, runtime provenance, Actions artifacts and scientific interpretation boundaries. Vercel is the presentation/inference surface.

## Historical rolling-video spectator — RETAINED EVIDENCE, NOT PRIMARY LIVE

The older six-round ScreenData→H.264 pipeline remains manual regression evidence for renderer/activity/SWC plumbing. It is not the primary production LIVE and its hourly schedule remains removed.

## Reward/plasticity evidence — NOT production learning

Offline reward re-scoring, project-defined MBON valence partitions, bounded KC→MBON updates and cross-run checkpoint restore have engineering evidence. Continuous production reward-driven learning remains OFF.

## Current gate — Public Surface Freeze

The frozen production contract now includes:

1. one `single-shared-live-broadcast` target for all viewers;
2. no public per-viewer session creation;
3. runtime SHA/base/snapshot identity checks;
4. schema-v3 causal telemetry and six-round warm execution;
5. both MaleCNS decision indices and real FightingICE x/y/HP/action;
6. real sensory drive and real motor contributors;
7. seven-group/action consistency;
8. explicit approved-vs-candidate provenance;
9. viewer heartbeat without per-viewer compute multiplication;
10. explicit warming/error state and no fabricated LIVE fallback.

`.github/workflows/public-surface-contract.yml`, `.github/workflows/vercel-live-arena-smoke.yml`, and `.github/workflows/precompile-arena-brian2-cython-cache.yml` guard these boundaries.

## Not yet demonstrated

- frozen production reward semantics;
- continuous production learning;
- reproducible behavioral improvement caused by MaleCNS plasticity;
- four approved learned lineages advancing continuously;
- causal biological circuit mechanism from activity alone;
- biological-structure advantage over matched controls.
