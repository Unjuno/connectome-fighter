# Connectome Fighter

Connectome Fighter is a cloud research testbed that connects the **MaleCNS v1.0 Drosophila connectome** to FightingICE through a pinned implementation of the Shiu et al. leaky integrate-and-fire dynamics. The project records real MaleCNS body-ID activity, keeps game I/O mappings explicit, and separates biological structure from project-defined reinforcement and plasticity assumptions.

**[Public LIVE](https://liveunjuno.vercel.app/connectome)** · [Research ledger](https://unjuno.github.io/connectome-fighter/) · [Status](docs/STATUS.md) · [Roadmap](ROADMAP.md) · [Public surface contract](docs/PUBLIC_SURFACE_SPLIT.md)

## Canonical control path

```text
FightingICE numeric observation
        ↓
versioned project-defined Poisson sensory interface
        ↓
MaleCNS v1.0 real connectivity
        ↓
pinned Shiu et al. LIF dynamics
        ↓
real output-body spike counts
        ↓
versioned action groups
        ↓
FightingICE action
```

The canonical path does **not** replace the fly substrate with an MLP, RNN, PPO policy network, or the repository's older custom sigmoid scaffold. Legacy FlyWire/custom-network components are engineering history only.

## Scientific boundaries

- MaleCNS anatomy is biological data.
- Shiu LIF dynamics are a published neural-dynamics model applied to that anatomy.
- FightingICE feature-to-sensory and output-to-action mappings are project-defined interfaces, not biological claims.
- Reward and plasticity rules are research-added assumptions and must remain versioned.
- Visualization is spectator-only. Screen pixels, decorative graphics and morphology rendering are never policy inputs.
- Neural activity is not treated as proof of causal biological function. Causal claims require interventions or ablations.

## Current demonstrated state

- MaleCNS v1.0 provenance/import: **PASS**
- pinned Shiu LIF reference/runtime: **PASS**
- strict runtime: approximately **156,675 neurons / 6,025,920 recurrent synapses** under the project filter
- real MaleCNS-controlled FightingICE rounds: **PASS**
- separate neural state and RNG per character: **PASS**
- body-ID spike/event logs: **PASS**
- released MaleCNS SWC X–Z morphology projection: **PASS**
- compilerless Brian2 Cython runtime bundle: **PASS**
- SHA-addressed persistent Vercel runtime base: **PASS**
- production single shared Vercel LIVE with real FightingICE + two MaleCNS workers: **PASS**
- **GARNET generation 2**: approved read-only inference state
- **ZEN / LUD / NEZ generation 2**: candidate cross-run lineages; not promoted to production learned fighters
- four independently trained production fighter checkpoints: **NOT YET ESTABLISHED**
- continuous production reward-driven learning: **OFF**

Latest evidence and implementation gates are maintained in [`docs/STATUS.md`](docs/STATUS.md).

## Public surfaces

### Vercel public LIVE

The production arena is one **single shared read-only LIVE broadcast**. All viewers observe the same fixed-name Vercel Sandbox, `connectome-live-broadcast`; audience size does not create additional FightingICE/MaleCNS sessions.

```text
GitHub-approved inference state
        ↓
SHA-addressed persistent runtime snapshot
        ↓
fixed-name shared Vercel LIVE Sandbox
        ↓
FightingICE + MaleCNS + pinned Shiu LIF
        ↓
shared live telemetry / neural activity
        ↓
all viewers
```

Current LIVE matchup: **GARNET approved generation-2 checkpoint vs ZEN canonical baseline**. This must not be described as trained-vs-trained.

The Vercel surface:

- performs read-only inference only;
- exposes shared FightingICE HP, position, action, round and frame telemetry;
- exposes decision-window MaleCNS activity for both sides;
- renders released MaleCNS morphology and the fly-shaped fight visualization as spectator-only output;
- never feeds screen pixels, morphology or decorative visualization back into the policy;
- never mutates checkpoints or performs weight updates;
- never substitutes a recorded fight and labels it LIVE.

If the shared runtime is warming or unavailable, the public page reports that state instead of fabricating a fight.

### GitHub Pages / Actions

GitHub is the research, training and provenance surface. It publishes or preserves:

- canonical substrate and dynamics;
- training workflows and experiment controls;
- reward and plasticity contracts;
- normalized/public match logs;
- checkpoint lineage, hashes and resume evidence;
- approved inference handoff manifests;
- arena runtime provenance and checksums;
- raw Actions artifacts and logs.

Vercel is not the system of record for learning history.

## Runtime boundary

The canonical runtime keeps **Brian2 Cython** code generation. Because Vercel Sandbox images do not provide a C compiler, GitHub Actions precompiles the required Cython extensions using the production path identity and proves compilerless cache reuse before publishing the runtime bundle. This is a deployment optimization; it does not replace the MaleCNS topology or Shiu dynamics.

The runtime archive is staged once into a SHA-addressed persistent Sandbox and its filesystem snapshot is used as the source of the shared LIVE Sandbox. Mutable character state remains a separately hash-verified inference handoff.

## Learning status

Continuous canonical learning is **not production-active**.

GARNET generation 2 is the approved inference checkpoint. ZEN, LUD and NEZ have independent generation-2 cross-run candidate lineage evidence, but candidate lineage plumbing is not equivalent to a four-character production-trained league.

Current scheduled baseline and spectator workflows produce evaluation/logging evidence without production weight updates. Reward tuning and continuous training remain downstream of the public-surface/runtime freeze.

## Reward experiments

Reward design is intentionally not being promoted while the public/runtime contracts are still being frozen. Existing reward/plasticity workflows remain research or engineering evidence.

When reward experiments resume, model, game version, observation/action interface, compute budget, seeds and evaluation opponents must remain fixed so reward changes can be isolated from infrastructure changes.

## Repository language

Canonical code, public UI, GitHub Pages and canonical research documentation are maintained in English. Historical non-English documents may remain as translations or archival context but must not contradict the canonical contract.

## License

Project-authored source code is MIT licensed. FightingICE, MaleCNS/connectome data, papers and other third-party resources retain their own licenses and terms; see [`THIRD_PARTY.md`](THIRD_PARTY.md).
