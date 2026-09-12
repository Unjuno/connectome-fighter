# Public LIVE / research ledger split

## Purpose

Connectome Fighter deliberately separates its public surfaces.

1. **Vercel public LIVE** — one globally shared FightingICE/MaleCNS live broadcast. Vercel performs read-only inference only.
2. **GitHub Pages / Actions research ledger** — training, reward, plasticity, checkpoint lineage, runtime provenance, experiment conditions, normalized/public logs and raw evidence.

Vercel is not the system of record for research history. Reproducibility, learning evidence and scientific provenance remain on GitHub.

## Vercel public LIVE

Public URL: `https://liveunjuno.vercel.app/connectome`

The primary arena is a **single shared live broadcast**. It does not create one fight per viewer. A fixed-name Vercel Sandbox, `connectome-live-broadcast`, is the only public broadcast target and all viewers observe the same stream and telemetry.

Shared LIVE contract:

- exactly one public broadcast target;
- viewer count does not multiply FightingICE/MaleCNS Sandboxes;
- public viewers cannot POST-create individual matches;
- `learning_enabled=false`;
- `policy_pixel_access=false`;
- immutable runtime is supplied from a persistent runtime snapshot addressed by the runtime archive SHA-256;
- after a bout ends, the same shared broadcast target starts the next bout;
- terminal/stopped shared Sandboxes are recycled from the current runtime base;
- Vercel never performs weight updates or rewrites research checkpoints.

The current LIVE matchup is **GARNET approved generation-2 checkpoint vs ZEN canonical baseline**. ZEN is not an approved learned checkpoint, so this is not described as trained-vs-trained.

The Vercel surface displays:

- shared P1/P2, HP, position, action, round and frame telemetry;
- decision-window MaleCNS spike activity for both sides;
- released MaleCNS SWC-derived X–Z morphology and anatomical context;
- shared LIVE connection, warming and error state;
- a fly-shaped fight visualization whose position/facing/action come from live FightingICE telemetry; wingbeat is presentation-only;
- public inference provenance separating served state from candidate lineage evidence.

The Vercel surface must not:

- perform learning or mutate research checkpoints;
- retain the long-term research match ledger;
- present reward formulas or plasticity rationale as arena state;
- expose optimizer/training history as runtime state;
- substitute a recorded fight and label it LIVE;
- feed screen pixels, decorative artwork, morphology or visualization state into the policy.

When LIVE is unavailable, the page must report warming/error state rather than fabricate activity.

### Spectator morphology boundary

The `malecns-context-atlas-v1` background is a deterministic representative sample derived from released MaleCNS v1.0 SWC skeletons. It is anatomical context, not an all-neuron rendering. Live morphology highlighting is spectator-only and never enters policy input.

## GitHub research / training ledger

Public URL: `https://unjuno.github.io/connectome-fighter/`

GitHub publishes or links:

- canonical substrate and dynamics;
- training workflows;
- versioned reward and plasticity contracts;
- fixed comparison controls;
- normalized/public match logs;
- checkpoint lineage and resume evidence;
- approved inference handoff;
- arena runtime provenance and checksums;
- GitHub Actions artifacts and logs;
- interpretation boundaries.

Training belongs on GitHub Actions. Vercel only receives state that has been explicitly approved for read-only inference.

During Pages deployment, canonical JSON under `configs/` is copied into `site/research-data/` so displayed parameters cannot silently drift from the versioned experiment contract. Current production runtime proof is published separately as `site/data/runtime-proof.json`.

## Training → LIVE inference handoff

Research checkpoints are not exposed directly as mutable Vercel state.

`publish-arena-inference-snapshot` extracts only the state required for read-only inference from an approved canonical checkpoint and publishes it under the rolling `arena-inference-latest` release.

The handoff manifest identifies and verifies inference state, including:

- character;
- generation;
- state filename;
- state SHA-256;
- canonical model identifier;
- read-only inference contract.

Reward formulas, plasticity rationale, match ledgers and research history remain on GitHub research surfaces.

### Current checkpoint-lineage status

- **GARNET generation 2** — approved read-only inference state in `arena-inference-latest`; used by the production shared LIVE.
- **ZEN / LUD / NEZ generation 2** — independent state/RNG/history and cross-run generation resume proven as candidate lineages; not promoted to production learned fighters.

Therefore the project can state that all four characters have cross-run-resumable lineage evidence, but it must not claim a four-character production-trained league.

## Runtime snapshot / compilerless Cython boundary

The Vercel runtime bundle is not downloaded and rebuilt for each viewer. The immutable bundle is staged into a runtime-archive-SHA-addressed persistent Sandbox, and that filesystem snapshot is the source for the fixed shared LIVE Sandbox.

The runtime base contains immutable runtime assets only. Character state is verified separately through the `arena-inference-latest` manifest and SHA.

The canonical Brian2 code-generation target remains **Cython**. Vercel Sandbox images have no C compiler, so GitHub Actions precompile the required Cython extension cache while reproducing the production executable path and then prove that the same MaleCNS worker reaches `ready` with the compiler unavailable. Host-specific `-march=native` output is excluded from the portable cache.

This is a deployment/cold-start/portability optimization. It does not alter MaleCNS topology or the pinned Shiu dynamics.

## Current production inference proof — 2026-09-12

Production evidence established the current compilerless runtime and real Vercel inference path with:

- runtime archive SHA-256 `f4016e3a2f79968a3305818ad3b4ef2197802e36c647660c1ab524b098f27205`;
- runtime archive size `439024170` bytes;
- runtime base `connectome-runtime-f4016e3a2f79968a`;
- runtime snapshot `snap_s5HpePEfgiNNAsLgE9UKsvOVwY5u`;
- Python `3.10.21`, Brian2 `2.5.1`, Cython `0.29.36`, NumPy `1.24.0`;
- 156,675 included neurons;
- 6,025,920 runtime recurrent synapses;
- compilerless cache reuse verified;
- cache tree SHA-256 `772cf23de36484d12e9355334f116bad71b8a8d30e42531cc93b90e3670dcd92`;
- 30 cache files / 15 shared objects / 5,776,256 bytes;
- host-specific `-march=native` excluded;
- real FightingICE frame advancement and decisions from both MaleCNS workers;
- compilerless release E2E Actions `34690428080` — PASS;
- independent production smoke Actions `34690567057` — PASS.

The proof telemetry observed round 1 / frame **181**, GARNET decision **3**, ZEN decision **3**, and **9,245 / 9,098** network spikes. The proof bout used **GARNET approved generation-2 checkpoint vs ZEN canonical baseline**. It proves production inference plumbing, not trained-vs-trained performance.

Machine-readable proof: [`site/data/runtime-proof.json`](../site/data/runtime-proof.json).

### Shared LIVE handoff timing

Public broadcast sessions now use 1-second post-fight and post-session hold defaults; ordinary one-shot diagnostics retain the 30-second defaults. Sampled production observations showed a previous running bout at `11:15:47Z`, the next bout booting at `11:15:54Z`, and that same next bout running at `11:16:01Z`. These are sampling bounds rather than an exact downtime measurement, but the prior intentional 30s+30s terminal hold is no longer present.

## Public-surface freeze gate

Before reward tuning or continuous learning is promoted, the following must stay true:

1. `/api/connectome/live` reports `mode=single-shared-live-broadcast` and `audience_scope=shared-global`;
2. exactly one fixed public broadcast target is used;
3. `learning_enabled=false` and `policy_pixel_access=false` on public LIVE telemetry;
4. runtime archive SHA and runtime-base identity agree;
5. production telemetry reaches `frame > 0` and both MaleCNS sides emit decision indices;
6. GARNET is labelled approved while ZEN/LUD/NEZ remain candidate unless separately promoted by evidence;
7. README, Pages and workflow checks do not regress to the retired viewer-specific architecture;
8. public failure states are shown as warming/error, never replaced by fabricated LIVE content;
9. compilerless runtime release E2E and the independent production smoke both use the same shared-LIVE contract.

## Scientific boundary

- **MaleCNS anatomy** — canonical biological structure.
- **Pinned Shiu LIF** — canonical dynamics layer used by this project.
- **Brian2 Cython precompile/cache** — deployment optimization, not a dynamics replacement.
- **Game observation → sensory input** — project-defined experimental interface.
- **FightingICE reward** — project-defined reinforcement signal.
- **Game reward → plasticity mapping** — project-defined learning assumption.
- **SWC/context-atlas/live visualization** — spectator-only output.

Moving verified inference state to Vercel does not change these scientific boundaries.
