# Connectome Fighter

Connectome Fighter is a cloud research testbed that connects the **MaleCNS v1.0 Drosophila connectome** to FightingICE through a pinned implementation of the Shiu et al. leaky integrate-and-fire dynamics. The project records real MaleCNS body-ID activity, keeps game I/O mappings explicit, and separates biological structure from project-defined reinforcement and plasticity assumptions.

**[Public arena](https://liveunjuno.vercel.app/connectome)** · [Research ledger](https://unjuno.github.io/connectome-fighter/) · [Status](docs/STATUS.md) · [Roadmap](ROADMAP.md) · [Public surface contract](docs/PUBLIC_SURFACE_SPLIT.md)

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
- exact cross-run checkpoint restore proof: **PASS for GARNET generation 2**
- read-only arena inference snapshot handoff: **PASS for GARNET generation 2**
- four independently trained production fighter checkpoints: **NOT YET ESTABLISHED**
- production per-viewer Vercel execution of FightingICE + MaleCNS: **NOT YET ACTIVE**

Latest evidence and implementation gates are maintained in [`docs/STATUS.md`](docs/STATUS.md).

## Public surfaces

### Vercel arena

The intended public runtime is **per-viewer, read-only inference**:

```text
approved inference checkpoint(s)
        ↓
short-lived viewer-specific runtime
        ↓
FightingICE + MaleCNS + pinned Shiu LIF
        ↓
live fight telemetry + neural activity
        ↓
browser visualization
```

The Vercel surface must not perform learning or rewrite research checkpoints. It must also not substitute a recorded video and label it as a live session.

The UI and session contract are implemented, but the production runtime image/service is still being provisioned. Until that runtime is available, the public arena reports the runtime as offline rather than fabricating a live fight.

### GitHub Pages / Actions

GitHub is the research and provenance surface. It publishes or preserves:

- reward definitions;
- plasticity assumptions;
- checkpoint lineage and hashes;
- experiment controls;
- normalized evidence;
- raw Actions artifacts and logs.

## Learning status

Continuous canonical learning is **not currently claimed as production-active**.

The repository contains reward/plasticity smoke contracts and a verified GARNET generation-2 resume/update proof. Before a four-character learned league is claimed, each character needs its own persistent checkpoint lineage, RNG history and independently updated state.

## Reward experiments

The recommended first comparison is deliberately simple:

1. **A — terminal only:** win `+1`, loss `-1`, draw `0`;
2. **B — terminal + no-damage timeout penalty:** same terminal reward plus a small penalty only when a timeout/draw has no damage;
3. **C — shaped candidate:** the existing versioned damage + engagement + terminal contract.

Keep model, game version, observation/action interface, compute budget, seeds and evaluation opponents fixed across conditions. Compare decisive-match rate, nonzero-damage rate, time-to-first-hit, W/L/D, action diversity and recruited-circuit diversity.

## Repository language

Canonical code, public UI, GitHub Pages and canonical research documentation are maintained in English. Historical non-English documents should not be linked as canonical specifications.

## License

Project-authored source code is MIT licensed. FightingICE, MaleCNS/connectome data, papers and other third-party resources retain their own licenses and terms; see [`THIRD_PARTY.md`](THIRD_PARTY.md).
