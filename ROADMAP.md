# Connectome Fighter Roadmap

Primary goal: reproducible real-connectome game control, auditable neural and physical spectators, then controlled learning experiments. Functional CI acceptance and public deployment acceptance are separate gates.

## Current gates — 2026-09-14

| Stage | Status | Evidence boundary |
|---|---|---|
| MaleCNS + pinned Shiu LIF game control | Established; exercised in full-stack CI | Real anatomy, simulated spikes, numeric game observations |
| Compilerless Brian2 runtime | CI verified | Version/path-specific compiled cache |
| FlyBody publisher software / physical process lifecycle | CI PASS, PR #57 | 42 software + 2 physics/process tests, engineering input fixtures |
| Real game → MaleCNS → FlyBody → browser | **CI PASS**, run 34827207269, head 8a5e72d | Actual game-derived neural activity; 2 rounds; no mocked HTTP or neural fixture |
| Dedicated Next.js and Vercel project | Deployed | Existing video home remains separate from new /live viewer |
| Dedicated Vercel shared LIVE | **Deployment E2E pending** | Last observed Sandbox capacity block; not established by local CI |
| Learning-frequency / reward redesign | **Next design stage** | Existing research candidate is a comparator, not a validated optimum |
| Production reward-driven learning | **OFF** | No automatic promotion or rollout permission |

No completion percentage is assigned: component tests, functional integration, deployment health and scientific validity are different claims.

## P0–P4 — substrate, control, state and evidence

Established: real MaleCNS anatomy, pinned Shiu LIF, independent character state, body-ID logs, compilerless runtime and official FightingICE ScreenData. FlyBody uses upstream MuJoCo with the project-defined adapter v2, not an identified biological motor-neuron-to-muscle map.

## P5A — Functional full-stack E2E in CI

`ci-stack-e2e` runs:

```text
verified runtime asset + exact source checkout
  → real headless FightingICE
  → two actual MaleCNS/Shiu LIF workers
  → game-derived annotated decision log
  → neural adapter v2 + FlyBody/MuJoCo/OSMesa
  → production HTTP / state / PNG output
  → actual Next.js /live + Chromium
```

The passing run completed two 600-frame read-only rounds and recorded 20 decisions per side. Both workers reported 156,675 neurons and 6,025,920 synapses. Browser samples progressed from round 1/frame 241/decision 4 to frame 541/decision 9, with both FlyBody PNG hashes changing and real images decoded. HTTP-selected source events were also checked against the independently saved raw decision log.

Artifact 10340228330 has ZIP SHA-256 `63651a830afcc4ee8447bcb39161fdd9e3b3478a7bd1c6499d22e1e624bbae78`. This is functional evidence, not Vercel or biological experimental validation. Subsequent source changes must rerun CI; this record refers specifically to the named run.

### Alignment contract

A slow renderer cannot reliably join three independently sampled latest values. `/decision-snapshot` therefore selects previously observed events by session/round/frame/P1/P2 decision identity. It does not relabel the latest state. The history is bounded to 64 events per side, each at most 128 KiB, and selected source age must be under 30 seconds. Missing, cross-session, expired or inconsistent source identities fail closed. Only running sessions are accepted.

FlyBody identities, selected telemetry/activity and PNG hashes must agree. Official ScreenData is independently sampled; exact ScreenData frame identity and lossless physical replay are **not** claimed. Both the executed physical time and dropped wall time remain visible.

### Dependency and execution boundary

CI resolves a release asset ID and its byte SHA once at run start, downloads that ID and checks the bytes. The descriptor, biological/model hashes, dependency environment, exact tested source and raw results are saved. This avoids permanently pinning a deletable asset ID from a rolling release while preserving per-run identity. It is not a claim that a mutable release tag is immutable.

CI substitutes only cloud allocation/address discovery with fixed loopback networking. It does not mock neural events, game results, physics, HTTP payloads or images. The /live server refuses CI loopback wiring inside Vercel or outside standalone CI. The existing root candidate-evaluation page is not replaced.

After P5A passes, learning-frequency and reward **design** may proceed. Passing CI does not authorize production learning or promotion.

## P5B — Dedicated shared-LIVE deployment acceptance

In parallel, verify dedicated-project isolation, OIDC, runtime staging, capacity, real networking, supervisor recovery and repeated public probes against `CONNECTOME_PUBLIC_BASE_URL`. Public probes must follow the selected-decision contract rather than assuming the independent latest endpoints are frame-locked.

Missing configuration or capacity means SKIP/UNCERTAIN: never PASS or fallback to another application. CI P5A cannot establish P5B. Public LIVE availability claims and rollout require P5B; no recorded or synthetic LIVE substitution is allowed.

## P6 — Versioned public and experimental contracts

Freeze the functional contract with P5A evidence. Keep production acceptance separate until P5B passes. Preserve source-age limits, held-input semantics, state/PNG hashes, execution-time reporting and approved/candidate wording. The font probe now consumes the entire listing to avoid a false SIGPIPE failure under Bash pipefail.

## P7 — Learning frequency and reward design selection ← NEXT

Separate observation/decision cadence, collection batches, between-batch plasticity, evaluation cadence, and publication/promotion. Specify win/loss, HP difference, timeout/draw, inactivity and truncated-round semantics. Freeze seeds, opponent schedule and compute budget. Compare against existing research settings and a no-update baseline; do not change infrastructure and reward rules in one experiment.

## P8 — Character-specific persistent plasticity

Version independent lineages with parent checkpoint, graph/interface hashes, RNG state, reward/plasticity IDs and update count. Freeze both policies within each round. Existing rolling candidates remain research artifacts, not automatically approved inference.

## P9 — Controlled learning and frozen evaluation

Restore verified state → bounded collection → between-batch update → atomic candidate → frozen evaluation → explicit promotion decision. Changed weights or passing software tests alone do not show behavioral improvement. Production rollout still requires P5B and explicit approval.

## P10–P12 — League, interventions and matched controls

Evaluate fixed baselines, champions and archived opponents; then interventions/ablations and matched topology/weight controls. Activity correlation is not causality. Biological-structure advantage requires controlled comparisons.

## Immediate queue

- [x] Separate the dedicated application from unrelated projects.
- [x] Verify real FlyBody publisher lifecycle.
- [x] Pass full functional game/neural/physics/browser CI and inspect evidence.
- [ ] Revalidate the final PR head and merge the CI/snapshot contract.
- [ ] Design learning-frequency/reward comparisons without starting or promoting training automatically.
- [ ] Independently complete dedicated production acceptance after compute capacity is available.

## Exploratory colosseum season

See [COLOSSEUM.md](docs/COLOSSEUM.md) for the ten-minute requested candidate cycle, R3 reward, 15-frame game decisions, paired diagnostics, English-only surfaces, and immutable result publication. This is separate from approved inference and Vercel acceptance; no stronger-play claim or automatic promotion is implied.
