# Connectome Fighter

Connectome Fighter is a cloud research testbed that connects the **MaleCNS v1.0 Drosophila connectome** to FightingICE through a pinned implementation of the Shiu et al. leaky integrate-and-fire dynamics. The project records real MaleCNS body-ID activity, keeps game I/O mappings explicit, and separates biological structure from project-defined reinforcement, plasticity, and embodiment assumptions.

**Dedicated LIVE:** deployment target is configured through the repository variable `CONNECTOME_PUBLIC_BASE_URL`; no unrelated Vercel project is a valid Connectome target. · [Research ledger](https://unjuno.github.io/connectome-fighter/) · [Status](docs/STATUS.md) · [Roadmap](ROADMAP.md) · [Public surface contract](docs/PUBLIC_SURFACE_SPLIT.md)

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

The canonical path does **not** replace the fly substrate with an MLP, RNN, PPO policy network, or the repository's older custom sigmoid scaffold.

## Physical FlyBody spectator

The physical fly is the upstream `TuragaLab/flybody` MuJoCo body pinned at commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26`.

```text
annotated MaleCNS motor / descending activity
        ↓
project-defined bounded adapter
        ↓
59 FlyBody actuators
        ↓
MuJoCo physics
        ↓
FlyBody render
```

The adapter is `malecns-annotated-motor-to-flybody-tripod-v2`. It is a project interface, **not** a claimed biological motor-neuron→muscle map. FightingICE x/y/action values do not position the FlyBody body. Zero neural motor drive produces no active gait. FlyBody, FightingICE ScreenData, and neural anatomy are spectator outputs and never policy inputs.

## Scientific boundaries

- MaleCNS anatomy is biological data.
- Shiu LIF dynamics are a published neural-dynamics model applied to that anatomy.
- FightingICE feature-to-sensory and output-to-action mappings are project-defined interfaces.
- MaleCNS→FlyBody actuator mapping is project-defined.
- Reward and plasticity rules are research-added assumptions and remain versioned.
- Neural activity is not treated as proof of causal biological function; causal claims require interventions or ablations.

## Current demonstrated state

- MaleCNS v1.0 provenance/import: **PASS**
- pinned Shiu LIF reference/runtime: **PASS**
- strict runtime: approximately **156,675 neurons / 6,025,920 recurrent synapses** under the project filter
- real MaleCNS-controlled FightingICE rounds: **PASS**
- body-ID spike/event logs: **PASS**
- compilerless Brian2 Cython runtime bundle: **PASS**
- FlyBody real MuJoCo physics contract: **PASS in independent CI**
- FlyBody action dimension: **59**
- neural-drive-vs-zero trajectory divergence: **PASS**
- dedicated Next.js public control/viewer implementation: **DEPLOYED; production compute E2E remains separate**
- dedicated Vercel shared-LIVE E2E: **NOT YET VERIFIED**
- GARNET generation 2: approved read-only inference state
- ZEN canonical baseline: current P2 serving contract
- continuous production reward-driven learning: **OFF**

The prior unrelated `Unjuno/live` application is not a Connectome deployment target and is not modified by the dedicated workflows.

## Dedicated public architecture

```text
GitHub rolling runtime release
        ↓
SHA-addressed persistent runtime base
  (runtime + FightingICE fonts + OSMesa)
        ↓
fixed-name connectome-fighter-live-broadcast Sandbox
        ↓
FightingICE + two MaleCNS/Shiu workers
        ↓
Official ScreenData + neural activity + FlyBody physics
        ↓
one shared public viewer surface
```

The dedicated app lives in this repository under `app/` and `lib/`. Its control API is `/api/live`; runtime materialization is `/api/runtime-base`. It reads the Vercel deployment's own `VERCEL_PROJECT_ID` and contains no hard-coded identifier for another Vercel project.

Production smoke workflows use `CONNECTOME_PUBLIC_BASE_URL`. If that variable is unset, they skip rather than falling back to another site.

## Runtime publication boundary

Runtime publication is GitHub-only:

`publish-arena-runtime-bundle → precompile-arena-brian2-cython-cache → publish-flybody-runtime-addon`.

These workflows publish immutable release assets but do not stage them into a Vercel project. The dedicated Vercel control plane owns runtime-base staging. This prevents release jobs from mutating an unrelated deployment.

## Colosseum candidate season

The English-only candidate experiment is described in [COLOSSEUM.md](docs/COLOSSEUM.md). Its workflow requests one bounded cycle every ten minutes. Each cycle records parent evaluation, full-round collection, a post-round update, and paired child evaluation. Results remain experimental; a completed cycle is not proof of stronger play. The historical R2d learner is manual-only.

## Learning status

Continuous canonical learning is **not production-active**. Candidate training and append-only lineage history remain on GitHub and cannot auto-promote into the Vercel inference state.

## License

Project-authored source code is MIT licensed. FightingICE, MaleCNS/connectome data, FlyBody, papers, and other third-party resources retain their own licenses and terms; see [`THIRD_PARTY.md`](THIRD_PARTY.md).
