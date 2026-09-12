# Public LIVE / research ledger split

## Purpose

Connectome Fighter deliberately separates its public surfaces.

1. **Vercel public LIVE** — one globally shared FightingICE/MaleCNS read-only inference broadcast.
2. **GitHub Pages / Actions research ledger** — training workflows, reward/plasticity contracts, checkpoint lineage, runtime provenance, normalized/public logs and raw evidence.

Vercel is not the system of record for research history. Learning evidence and scientific provenance remain on GitHub.

## Vercel public LIVE

Public URL: `https://liveunjuno.vercel.app/connectome`

The primary arena is a **single shared live broadcast**. A fixed-name Vercel Sandbox, `connectome-live-broadcast`, is the only public target; viewer count does not create additional FightingICE/MaleCNS processes.

Shared LIVE contract:

- `mode=single-shared-live-broadcast`;
- `audience_scope=shared-global`;
- public viewers cannot POST-create individual matches;
- `learning_enabled=false`;
- `policy_pixel_access=false`;
- immutable runtime comes from a runtime-SHA-addressed persistent snapshot;
- the public process runs six FightingICE rounds per bootstrap;
- viewer status reads act as an idempotent shared heartbeat and may extend the same Sandbox session near expiry;
- no viewer-specific compute session is created by that heartbeat;
- terminal/stopped shared Sandboxes are recycled from the current runtime base;
- Vercel never mutates research checkpoints or performs learning.

Current matchup: **GARNET approved generation-2 inference vs ZEN canonical baseline**. ZEN/LUD/NEZ generation-2 states remain candidate lineages and are not served as approved learned fighters.

## Causal LIVE visualization

For the same canonical decision window, the Vercel page shows:

1. real MaleCNS sensory body IDs and Poisson input rates;
2. recurrent whole-network spike load, active-body count, biological window and membrane summary;
3. real output-body motor contributors;
4. all seven action-group spike counts;
5. selected action and actual FightingICE x/y, facing and HP.

The fly-shaped fighter is an embodiment of the actual game state: position comes from live FightingICE x/y, pose comes from the selected MaleCNS action, and damage pulses come from HP loss. It is not a separate random animation or a claim of Drosophila biomechanics.

Body IDs without released spatial coordinates are rendered as a **non-spatial activity index**. No anatomical coordinates are fabricated. Screen pixels, morphology and presentation state never enter policy input.

When LIVE is unavailable, the page shows warming/error state instead of substituting recorded or fabricated activity.

## GitHub research / training ledger

Public URL: `https://unjuno.github.io/connectome-fighter/`

GitHub publishes or preserves:

- canonical substrate/dynamics and fixed game interface;
- training and evaluation workflows;
- reward/plasticity contracts;
- checkpoint lineage and resume evidence;
- approved inference handoff;
- normalized/public match logs;
- runtime provenance/checksums;
- Actions artifacts/logs;
- scientific interpretation boundaries.

Continuous production reward-driven learning is currently **OFF**. Vercel receives only state explicitly approved for read-only inference.

## Training → LIVE inference handoff

`publish-arena-inference-snapshot` extracts only inference state from an approved checkpoint and publishes it under `arena-inference-latest`. State files and metadata are SHA-verified before Vercel materialization. Reward rationale, match ledgers and training history remain on GitHub.

Current lineage:

- **GARNET generation 2** — approved read-only inference, served in LIVE.
- **ZEN / LUD / NEZ generation 2** — candidate cross-run lineage evidence, not production-approved learned fighters.

## Runtime snapshot / compilerless Cython boundary

The runtime bundle is staged once into a runtime-archive-SHA-addressed persistent Sandbox; that filesystem snapshot is the source for the public shared Sandbox. The runtime is not downloaded/rebuilt for each viewer.

Canonical Brian2 code generation remains **Cython**. GitHub Actions reproduce the production executable path, precompile the required cache and prove the same MaleCNS worker reaches `ready` with the compiler unavailable. Host-specific `-march=native` output is excluded.

This is deployment optimization, not a dynamics replacement.

## Current production inference proof — 2026-09-12

- runtime archive SHA-256 `f304bc4f0e7c19faca517a550f36dd566cb2f8b34e9a33627370aa3fec074004`;
- runtime archive size `439021953` bytes;
- runtime base `connectome-runtime-f304bc4f0e7c19fa`;
- runtime snapshot `snap_GnmkXhXrF8QAbow2cxdqDq3q9rL5`;
- Python `3.10.21`, Brian2 `2.5.1`, Cython `0.29.36`, NumPy `1.24.0`;
- 156,675 neurons / 6,025,920 recurrent synapses;
- compilerless Cython reuse verified;
- telemetry schema **v3**;
- **6 rounds per shared process**;
- compilerless release E2E Actions `34700529205` — PASS;
- strict production causal-LIVE smoke Actions `34700813732` — PASS.

The strict smoke observed round 1 / frame **421**, decision index **7** on both sides, and **8,971 / 8,813** whole-network spikes. Both selected `B`; `B` was the maximal action group (55 and 56 spikes). Non-empty real sensory drive and motor-output contributor lists were present in that same decision window.

Machine-readable proof: [`site/data/runtime-proof.json`](../site/data/runtime-proof.json).

## Shared LIVE lifecycle

The public process keeps six rounds warm per bootstrap. Audience reads of `/api/connectome/live` are shared maintenance heartbeats: near session expiry they extend the same Vercel session rather than create a new viewer-specific one. Without viewers or release-smoke traffic, no audience-driven extension is issued and the ephemeral Sandbox may expire naturally.

The long-running supervisor command uses Vercel's five-hour Sandbox ceiling; the initial Sandbox timeout remains bounded and extension is best-effort.

## Public-surface freeze gate

Before reward tuning or continuous learning is promoted, the following must remain true:

1. one `single-shared-live-broadcast` / `shared-global` target;
2. no public individual-session creation;
3. `learning_enabled=false` and `policy_pixel_access=false`;
4. exact runtime SHA/base/snapshot adoption;
5. schema-v3 telemetry with six-round warm execution;
6. real FightingICE x/y/HP/action and both MaleCNS decisions;
7. non-empty real sensory drive and motor contributors;
8. all seven action-group counts and selected-action/max-group consistency;
9. approved-vs-candidate provenance remains explicit;
10. warming/error is explicit and no fake LIVE fallback exists.

## Scientific boundary

- MaleCNS anatomy — biological structure.
- Pinned Shiu LIF — canonical dynamics used by this project.
- Brian2 Cython precompile/cache — deployment optimization.
- Game observation → sensory input — project-defined experimental interface.
- FightingICE reward / reward→plasticity — project-defined research assumptions.
- LIVE/SWC/fly visualization — spectator-only output.
