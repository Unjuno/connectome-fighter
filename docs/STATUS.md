# Status

Canonical production path: **MaleCNS v1.0 anatomy + pinned Shiu et al. LIF dynamics + FightingICE v7.1**.

Production reward-driven learning is currently **OFF**. Existing reward/plasticity/checkpoint workflows are engineering or exploratory evidence unless explicitly promoted. They are not a continuously learning production lineage.

## Production public LIVE — PASS

Viewer: **https://liveunjuno.vercel.app/connectome**

The primary public arena is one fixed shared Vercel broadcast, not one match per viewer.

```text
GitHub runtime release + approved inference state
        ↓
SHA-addressed persistent runtime Sandbox snapshot
        ↓
connectome-live-broadcast
(one shared ephemeral Vercel Sandbox)
        ↓
FightingICE + two MaleCNS/Shiu workers
        ↓
/state + /events live telemetry
        ↓
all viewers observe the same bout
```

Public contract:

- `mode=single-shared-live-broadcast`;
- `audience_scope=shared-global`;
- fixed broadcast target `connectome-live-broadcast`;
- public individual match creation is disabled;
- `learning_enabled=false`;
- `policy_pixel_access=false`;
- runtime archive SHA identifies the immutable runtime base;
- screen pixels, SWC geometry and decorative fly rendering are spectator-only;
- recorded clips are not substituted and labelled as LIVE.

Current production matchup is **GARNET approved generation-2 inference vs ZEN canonical baseline**. ZEN has candidate lineage evidence, but the ZEN candidate checkpoint is not the state served in the current LIVE. Therefore the public bout is not described as trained-vs-trained.

The center fight visualization uses actual FightingICE telemetry for fly `x/y`, facing and action pose. Wingbeat is presentation-only.

## Production Vercel inference proof — PASS

Current verified production runtime evidence on 2026-09-12:

- runtime archive SHA-256: `f4016e3a2f79968a3305818ad3b4ef2197802e36c647660c1ab524b098f27205`;
- runtime archive size: **439,024,170 bytes**;
- runtime base: `connectome-runtime-f4016e3a2f79968a`;
- runtime snapshot: `snap_s5HpePEfgiNNAsLgE9UKsvOVwY5u`;
- Python `3.10.21` / Brian2 `2.5.1` / Cython `0.29.36` / NumPy `1.24.0`;
- included neurons: **156,675**;
- recurrent runtime synapses: **6,025,920**;
- compilerless Brian2 Cython cache reuse: **verified**;
- cache contents: **30 files / 15 shared objects / 5,776,256 bytes**;
- cache tree SHA-256: `772cf23de36484d12e9355334f116bad71b8a8d30e42531cc93b90e3670dcd92`;
- host-specific `-march=native`: **excluded** from the portable cache;
- real FightingICE frame advancement: **verified**;
- decision telemetry from both MaleCNS workers: **verified**;
- compilerless release E2E: Actions `34690428080` — **PASS**;
- independent production smoke: Actions `34690567057` — **PASS**.

The current proof observed round 1 / frame **181**, GARNET decision index **3**, ZEN decision index **3**, and **9,245 / 9,098** network spikes respectively. This establishes real Vercel execution of FightingICE plus two MaleCNS workers; it is not evidence of trained-vs-trained performance.

Machine-readable proof: [`site/data/runtime-proof.json`](../site/data/runtime-proof.json).

## Shared LIVE lifecycle — PASS

The public broadcast no longer inherits the diagnostic 30-second post-fight hold plus 30-second post-session hold. `CONNECTOME_PUBLIC_BROADCAST=true` uses 1-second defaults for both holds; ordinary one-shot diagnostics retain the 30-second defaults and error state remains observable for 30 seconds.

Sampled production observations after the new runtime was adopted:

- previous bout running observed at `2026-09-12T11:15:47Z`;
- next bout booting observed at `2026-09-12T11:15:54Z`;
- the same next bout running observed at `2026-09-12T11:16:01Z`.

These timestamps are sampling bounds, not an exact downtime measurement. They demonstrate that the prior intentional ~60-second terminal hold is no longer present.

The shared-LIVE supervisor also recycles terminal/stopped fixed-name Sandboxes from the current runtime base rather than trying to restart a dead Vercel session.

## Runtime snapshot / compilerless Cython — PASS

The canonical backend remains **Brian2 Cython**. Vercel Sandbox images do not provide a C compiler, so the required extensions are precompiled in GitHub Actions under the production path identity and released only after the same worker reaches `ready` with the compiler unavailable.

The immutable runtime bundle is staged once into a runtime-archive-SHA-addressed persistent Sandbox. Its filesystem snapshot is used as the source for the shared LIVE Sandbox. Character inference state remains separately manifest/SHA verified.

This is a deployment and cold-start optimization. It does not modify MaleCNS topology or the pinned Shiu dynamics.

## Canonical substrate and control — PASS

- anatomy: **MaleCNS v1.0**;
- dynamics: pinned Shiu reference commit `2a83ad611cd9768f8c9723fc613ed27761a5feb5`;
- game: **FightingICE v7.1 + pyftg 2.3 + Java 21**;
- strict runtime adapter: **156,675 neurons / 6,025,920 recurrent synapses**;
- FightingICE numeric observations drive selected real MaleCNS sensory bodies through observation-dependent Poisson input;
- the whole pinned Shiu LIF network advances;
- selected real output-body spike groups choose actions using deterministic spike-count argmax;
- no epsilon-greedy/random action injection is used in the canonical path;
- body-ID spike events and game telemetry are retained for analysis.

The old FlyWire/custom-sigmoid/PPO route is legacy engineering evidence only.

## Checkpoint lineage

Current scientific wording:

- **GARNET generation 2 — APPROVED INFERENCE**: verified cross-run restore/update evidence and approved `arena-inference-latest` read-only handoff; used by production LIVE.
- **ZEN generation 2 — CANDIDATE LINEAGE**: independent state/RNG/history and cross-run generation resume proven; not promoted to production learned inference.
- **LUD generation 2 — CANDIDATE LINEAGE**: same boundary.
- **NEZ generation 2 — CANDIDATE LINEAGE**: same boundary.

This supports the statement that all four characters have cross-run-resumable lineage plumbing. It does **not** establish a four-character production-trained league.

## Four-character baseline / public match log — PASS

`.github/workflows/malecns-baseline-batch.yml` runs all six pairings every six hours and may also be dispatched manually:

- GARNET–ZEN;
- GARNET–LUD;
- GARNET–NEZ;
- ZEN–LUD;
- ZEN–NEZ;
- LUD–NEZ.

Baseline runs use unchanged weights. Public normalized match logs are written to `site/data/matches.json`, with summary state in `site/data/status.json`. These are evaluation/logging runs, not production learning.

The current public data is draw-heavy and therefore is not sufficient evidence for a stable fighter ranking. Reward tuning is intentionally deferred until the public/runtime surface is frozen.

## GitHub research / training ledger — PASS

GitHub Pages / Actions are the system of record for:

- canonical substrate and dynamics;
- training workflows;
- reward/plasticity contracts;
- checkpoint lineage and hashes;
- approved inference handoff;
- normalized/public match evidence;
- runtime provenance and checksums;
- raw Actions artifacts and logs;
- scientific interpretation boundaries.

Vercel is the presentation/inference surface, not the long-term learning ledger.

## MaleCNS morphology / neural visualization — PASS

The flat MaleCNS annotation table does not expose physical `pos_x/pos_y/pos_z`; those coordinates are not invented.

Released MaleCNS SWC centerlines are used for X–Z anatomical context in MaleCNS EM coordinates. The current public context atlas is a deterministic representative sample, not a complete rendering of all ~156k included neurons. Live highlighted body IDs come from real decision-window telemetry.

Morphology, annotations and visualization remain spectator-only and do not affect action selection.

## Historical rolling-video spectator — RETAINED EVIDENCE, NOT PRIMARY LIVE

The earlier pipeline that generated six FightingICE rounds, encoded official 960×640 ScreenData to H.264, and rotated `latest / previous-1 / previous-2` remains useful regression evidence for renderer, activity-timeline and SWC export plumbing.

It is no longer the primary production arena. The recorded rolling-video workflow is retained for **manual/engineering verification** and must not be presented as the current LIVE implementation.

## Reward/plasticity evidence — NOT production learning

Exploratory workflows have established engineering mechanisms including:

- offline reward re-scoring;
- project-defined MBON valence partitions;
- bounded KC→MBON multiplier updates;
- durable checkpoint pack/restore across separate Actions runs.

Those mechanisms remain research evidence. Continuous production reward-driven learning is still OFF.

## Current gate — Public Surface Freeze

Before reward tuning or continuous learning is promoted, keep the following fixed and regression-tested:

1. production `/api/connectome/live` remains `single-shared-live-broadcast`;
2. public match creation remains disabled;
3. one fixed `connectome-live-broadcast` target serves all viewers;
4. runtime archive SHA and runtime-base identity agree;
5. production telemetry reaches `frame > 0` and both MaleCNS decision indices advance;
6. `learning_enabled=false` and `policy_pixel_access=false` remain true;
7. GARNET is labelled approved while ZEN/LUD/NEZ remain candidate unless separately promoted by evidence;
8. README, STATUS, public-surface documentation and CI agree on the same architecture;
9. failure/warming states are explicit and no fabricated LIVE fallback is introduced.

`.github/workflows/public-surface-contract.yml` guards the static architecture wording. `.github/workflows/vercel-live-arena-smoke.yml` verifies the real production shared-LIVE contract after runtime publication. `.github/workflows/precompile-arena-brian2-cython-cache.yml` now uses the same shared-LIVE contract for its final release E2E rather than the retired per-session POST path.

## Not yet demonstrated

- a frozen production reward specification;
- continuous production learning;
- reproducible behavioral improvement caused by MaleCNS plasticity;
- four approved learned character lineages advancing continuously;
- stable champion/archive league learning;
- causal circuit mechanism from activity alone;
- biological-structure advantage over matched controls.

These claims remain explicitly unproven.
