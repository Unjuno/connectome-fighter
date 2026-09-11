# Public arena / research ledger split

## Purpose

Connectome Fighter deliberately separates its public surfaces.

1. **Vercel public arena** — short-lived per-viewer inference and visualization.
2. **GitHub Pages / Actions research ledger** — reward, plasticity, checkpoint lineage, experiment conditions and raw evidence.

Vercel is not the system of record for research history. Reproducibility and scientific provenance remain on GitHub.

## Vercel public arena

Public URL: `https://liveunjuno.vercel.app/connectome`

Target behavior:

- create an isolated viewer-specific inference session;
- load approved frozen checkpoint state by hash;
- run FightingICE with MaleCNS v1.0 and the pinned Shiu LIF dynamics;
- stream current FightingICE HP, position, action, frame and round telemetry;
- stream current MaleCNS body-ID neural activity for both fighters;
- render released MaleCNS morphology as spectator-only context;
- discard the session after the bounded fight.

The Vercel surface must not:

- perform learning or mutate research checkpoints;
- retain a long-term match ledger;
- publish reward formulas or plasticity rationale as arena state;
- expose optimizer or training history;
- substitute a recorded fight and label it as live;
- feed screen pixels, decorative artwork or visualization state into the policy.

The UI and session API contract exist today. The production runtime image/service is still being provisioned. Until it is available, the arena must report the runtime as offline rather than fabricating a live fight.

## GitHub research ledger

Public URL: `https://unjuno.github.io/connectome-fighter/`

The research surface publishes or links:

- canonical substrate and dynamics;
- current experiment phase;
- versioned reward contract;
- versioned plasticity contract;
- fixed comparison controls;
- normalized match evidence;
- checkpoint proof releases;
- GitHub Actions artifacts and logs;
- interpretation boundaries.

During Pages deployment, canonical JSON under `configs/` is copied into `site/research-data/` so displayed parameter values cannot silently drift from the versioned experiment contract.

## Training to arena inference handoff

Research checkpoints are not exposed directly as mutable arena state.

`publish-arena-inference-snapshot` extracts only the state required for read-only inference from an approved canonical checkpoint and publishes it under the rolling `arena-inference-latest` release.

The handoff manifest contains only fields required to identify and verify the inference state, including:

- character;
- generation;
- state filename;
- state SHA-256;
- canonical model identifier;
- read-only inference contract.

Reward formulas, plasticity rationale, match ledgers and research history remain on GitHub research surfaces.

At present, only **GARNET generation 2** has verified cross-run canonical checkpoint resume evidence. The project must not describe the public arena as a four-character production-trained league until independent approved lineages exist for the other characters.

## Scientific boundary

- **MaleCNS anatomy** — canonical biological structure.
- **Pinned Shiu LIF** — canonical dynamics layer used by this project.
- **Game observation → sensory input** — project-defined experimental interface.
- **FightingICE reward** — project-defined reinforcement signal.
- **Game reward → plasticity mapping** — project-defined learning assumption.
- **Morphology / fight visualization** — spectator-only output.

Moving verified inference state to Vercel does not change these scientific boundaries.
