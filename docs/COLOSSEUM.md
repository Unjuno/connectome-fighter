# Colosseum: English-Only Candidate Season

## Objective and present limits

The goal is visibly competent FightingICE play from the canonical MaleCNS/Shiu control path. A new generation, a changed weight, a high shaped return, or a rendered fly is not evidence of strength. Require actual damage, decisive outcomes, repeatable gains over the parent, and later held-out opponent/seed evaluation.

This is an exploratory **candidate-only** season, `colosseum-r3-v1`. The existing depression-only KC–MBON update is retained. It has finite weight bounds and no demonstrated guarantee of useful fighting strategies; saturation and lack of behavioral change must be reported rather than concealed. No MLP/PPO replacement, invented neuroscience, automatic promotion, or fake LIVE imagery is introduced.

## Three separate clocks

| Clock | Setting | Meaning |
|---|---|---|
| GitHub schedule | `3,13,23,33,43,53 * * * *`, UTC | Request a cycle every ten minutes; timing is best-effort |
| Game decision | 15 frames at nominal 60 game frames/s | 250 ms of game time, not wall-clock inference latency |
| Weight update | After one completed collection round | Never change weights during a fight or evaluation |

GitHub can delay or drop scheduled starts. One concurrency lock covers training and publication, and active updates are not canceled by a new tick. A cycle may exceed ten minutes. Set repository variable `COLOSSEUM_PAUSED=true` to pause this workflow. No billing plan is changed.

Official scheduler references: `https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule` and `https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule`.

## Cycle and publication

1. Resolve the prebuilt runtime by immutable asset ID and SHA-256; reuse its Python 3.10/Brian2/Cython environment and separate Python 3.11 bridge at the expected absolute path. Overlay the tested checkout's project source, without republishing the runtime.
2. Restore the latest colosseum candidate. On the first cycle only, validate and explicitly fork the legacy `canonical-training-latest` checkpoint. Copy multipliers exactly, preserve the legacy parent identity, and reset season counters. The old R2d lineage is not overwritten or reinterpreted.
3. Evaluate the parent against the canonical ZEN baseline with seeds 800101/20202, 3600-frame horizon, and the new 15-frame decision interval. Record the entire round's official ScreenData.
4. Collect one full 3600-frame training round against the rotating frozen ZEN/LUD/NEZ baseline. Training Poisson seeds are disjoint from the diagnostic seeds and recorded per run.
5. Apply `R3-colosseum-v1` through the existing valence-channel plasticity rule. Materialize the child and replay the exact diagnostic opponent/seeds/horizon/decision interval without learning.
6. Publish an immutable generation release containing the candidate, parent/child videos, checksums, and raw evidence. Only then replace the single `colosseum-latest/status.json` pointer. The site polls this pointer; cycles do not commit status to main or force a web rebuild.

PR runs exercise real training and evaluation **locally on the runner**, with read-only repository permissions and no publication. A separate trusted-main job owns publication. Incomplete cycles never advance the pointer. The old six-hour R2d learner becomes manual-only.

## Reward definition

All reward quantities are dimensionless engineering signals. HP and pixels are game coordinates, not SI physical measurements.

| Symbol | Meaning | Unit | Definition/range | Type |
|---|---|---|---|---|
| t | Decision interval index | 1 | Integers from 0 through T-1 | Integer scalar |
| T | Number of decision intervals | 1 | Positive integer | Integer scalar |
| h | Initial HP scale | game HP, no SI unit | 400 | Scalar |
| d_t | HP dealt during interval t | game HP, no SI unit | Nonnegative, overkill excluded | Scalar |
| a_t | HP taken during interval t | game HP, no SI unit | Nonnegative, overkill excluded | Scalar |
| x_t | Horizontal fighter separation | game px, no SI unit | Absolute difference of reported positions | Scalar |
| Phi_t | Bounded engagement potential | 1 | -min(max(x_t-180,0)/960,1); Phi_T=0 | Scalar |
| b | Net-damage weight | 1 | 0.5 | Scalar |
| c | Engagement weight | 1 | 0.05 | Scalar |
| z | Terminal result reward | 1 | Win +1; loss -1; damaging draw -0.1; no-damage draw -0.25 | Scalar |
| r_t | Per-decision reward | 1 | Net damage plus potential difference; add z at last interval | Scalar |

For each interval, `r_t = b*(d_t-a_t)/h + c*(Phi_(t+1)-Phi_t)`. Add `z` only at the final interval. The discount is 1. A completed trainable trace is required; missing identities, nonfinite values, reversed time, HP increases, and truncations are rejected.

**Unit check:** HP divided by HP is dimensionless; pixels divided by pixels are dimensionless; every summed reward term is therefore dimensionless. Ten HP of net damage yields 0.0125, not the previous 0.10.

**Bounded movement check:** summing consecutive potential differences cancels each intermediate potential once with a plus sign and once with a minus sign. The total shaping is therefore `c*(Phi_T-Phi_0) = -c*Phi_0`, between 0 and 0.05. Back-and-forth movement cannot accumulate unlimited return. A no-damage draw consequently stays between -0.25 and -0.20. Reaching contact alone does not make it a successful round.

**Important limitation:** this telescoping arithmetic is not a policy-invariance proof for the project's sign-sensitive, nonlinear depression-only learner. Positive and negative signals target different valence channels. Distance shaping and draw penalties are explicit experimental choices, not known fly dopamine signals or guaranteed improvements. The historical document's proposed compartmental “R3” is distinct from the exact config ID `R3-colosseum-v1`.

## Plasticity and frequency

Learning rate remains 0.01 per unit modulatory signal; multiplier bounds remain 0.8–1.0; topology and transmitter signs remain fixed. The eligibility decay is the fourth root of 0.9 per 15-frame decision, so four decisions retain the previous 0.9 decay over 60 game frames. The LIF decision window remains 20 ms; faster game decisions therefore increase simulated neural time per game second. This is a new protocol, not a reward-only confirmatory comparison with legacy results.

## Evaluation and falsifiable plan

**H:** the new candidate season can improve game outcomes against frozen opponents, rather than merely increasing update counts.

**T:** each cycle records paired parent/child diagnostics under identical conditions. For a strength claim, freeze a selected candidate and its parent; use a preregistered held-out panel of at least three opponent policies and 20 seed pairs per opponent. These 60 matches per policy are a proposed minimum, not completed evidence and not a power guarantee. Do not tune on those seeds. Avoid repeated significance-based stopping; finish the predefined panel.

**D:** functional PASS means complete audited rounds, valid checkpoint continuity, and correct publication. Improvement remains UNCERTAIN after a single paired match. A later strength decision requires a prespecified practically meaningful win-rate effect and uncertainty interval above the chosen threshold, without opponent-specific collapse. No automated promotion is currently authorized.

**C:** degenerate no-contact play, attacks outside range, loss of necessary connections from depression, action-mapping bottlenecks, opponent overfitting, or compute saturation can invalidate the learning hypothesis. A more frequent cron cannot repair those defects.

**U:** key uncertainties are Poisson seeds, opponent coverage, structural/model assumptions, partial game observations, sparse reward and the restricted plasticity rule. Report statistical intervals separately from model uncertainty; no combined standard uncertainty or coverage factor is estimated from the current single-seed diagnostics.

## Three uses of the evidence

Computational neuroscience: audit which annotated bodies and existing edges participate, without claiming native biological fighting circuits. Reinforcement learning: distinguish reward accumulation, credit assignment, and held-out performance. Distributed systems/HCI: publish immutable results through one atomic status pointer and clearly separate recorded challenges from LIVE.

## English-only scope

Active UI, document text, error/status messages, and browser selectors are English. Compatibility `.ja.md` paths also contain English. Historical Git commits and binary screenshots are retained as evidence, not rewritten. The Unicode reader regression preserves its test payload through escaped literals. `scripts/check_english.py` checks tracked text for reintroduced Japanese/CJK content.
