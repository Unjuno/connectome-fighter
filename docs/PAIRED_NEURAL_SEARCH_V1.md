# Paired neural search v1 — bounded pilot

## Adopted design and scope

This is a separate engineering experiment, not an unannounced modification of
approved inference. P1 remains the real MaleCNS/Shiu LIF controller. Only audited
existing positive KC-to-MBON edge magnitudes are changed. The search can recover
previously depressed magnitudes, so it is explicitly NOT the old monotonic
depression-only biological hypothesis. No MLP, heuristic game controller or
synthetic neural graph replaces P1.

The pilot does not publish to approved inference and does not automatically
promote a checkpoint. Its artifacts include the selected candidate state, raw
game/neural traces and real videos. No production policy, FlyBody policy boundary,
or unrelated project is changed by this experiment.

## Control readout fixed for this pilot

Earlier real-game diagnostics showed that the canonical absolute output-group
spike-count argmax was dominated by a stationary B-group rate bias. Shortening
the action-hold cadence from 60 to 30 or 15 frames did not produce damage in the
cadence diagnostic, so cadence remains fixed at 60 frames for this experiment.

A project-defined EMA-residual readout is therefore fixed before the weight
search. For each of the seven existing neural output groups, it subtracts an
exponential moving neural baseline and selects the largest positive residual.
It uses neural history only: no FightingICE position, HP, engine action, pixels,
or other privileged game state enters this readout. It is interface engineering,
not a claim of biological motor decoding.

The held-out readout-selection experiment used three seed pairs with the same
checkpoint, 60-frame cadence, 20 ms neural window and canonical ZEN opponent.
EMA-residual improved combat score in two of the three pairs. Across those three
pairs canonical dealt 0 HP, while EMA-residual dealt 135 HP in total and had
+75 HP aggregate net advantage relative to canonical. One seed pair worsened,
so this evidence selects a training-control candidate; it is not a general
strength claim.

## Rewards

Combat uses terminal outcome (+1/0/-1) plus 0.02 times normalized final HP
advantage, given equal 400/400 initial HP. Moving, button presses, spikes, fast
losses and damage-free draws receive no extra reward.

The neutral-dummy curriculum uses 0.1 times approach progress, 0.4 for any actual
damage dealt, and 0.5 times damage dealt divided by 400. Approach progress is the
fractional reduction from initial horizontal distance to the minimum recorded
delayed-frame distance. Repeated back-and-forth does not accumulate progress.
The dummy never attacks or moves intentionally; actual game physics still runs.
This is a different training objective, never evidence of competitive strength.

No reward coefficient is changed in the EMA-readout paired-search pilot. Readout
selection and reward changes are deliberately not confounded in one experiment.

Incomplete, regressed, healing, nonfinite, non-400/400 or non-frozen traces fail.
Overkill HP is clamped to zero. Recorded frame coverage and gaps are disclosed.
Per-frame delayed observations are only logged by the spectator, not given to
the policy as privileged input. Combat and curriculum are scored separately.

## Variable and unit definitions

| Symbol | Meaning | SI/unit | Definition/range | Type |
|---|---|---|---|---|
| theta | Search coordinates | dimensionless | eight real numbers, initially zero | vector |
| u | Gaussian direction | dimensionless | independent standard normal coordinates | random vector |
| sigma | Search scale | dimensionless | 0.04 | scalar |
| M | Number of paired directions | dimensionless | four | integer |
| F | Measured trial score | dimensionless | curriculum 0..1; combat -1.02..1.02 | scalar |
| g | Antithetic gradient estimate | dimensionless | mean((Fplus-Fminus)*u)/(2*sigma) | vector |
| parent | Inherited edge multipliers | dimensionless | verified checkpoint, 0.8..1.0 | vector |
| group | Fixed artificial edge partition | dimensionless | SHA-256 of experiment ID and synapse index, modulo 8 | integer vector |
| H | Maximum HP | game HP, not SI | 400 | scalar |
| distance | Delayed FrameData separation | game pixels, not SI | absolute P1/P2 horizontal difference | scalar |

All score terms and optimizer coordinates are dimensionless. HP and distances
are divided by quantities in the same game units; no physiological calibration
is implied. The zero coordinate exactly preserves inherited float32 multipliers.
Effective multipliers are clip(parent + theta[group], 0.8, 1.0). Clipping is part
of the scored objective. Gaussian smoothing permits gradient estimation even
with clipping and argmax-like decisions; it does not guarantee an informative
signal.

## Fixed protocol

The pilot fixes decision interval 60 game frames, neural window 20 ms, and P1
readout `ema-residual`. It does not confound cadence, readout and reward changes.
Both actors are frozen throughout each 3600-frame-maximum round. Training seed is
910001; validation seeds are 910101 and 910102. Canonical combat comparison uses
800101/20202 and is a candidate gate, not a held-out strength estimate.

1. Resolve one runtime and one parent checkpoint by release asset IDs/digests.
2. Verify structural/reference/game/interface hashes and checkpoint config.
3. Run the parent twice against the neutral dummy and require identical recorded
   metrics under the same seed.
4. Execute four plus/minus Gaussian perturbation pairs through EMA-residual.
   Alternate execution order.
5. Estimate g; propose 0.05*g, bounded to Euclidean norm 0.02. Identical paired
   scores produce exactly zero update.
6. A nonzero proposal must strictly improve the training curriculum score before
   it proceeds to the validation gate.
7. On both separate validation seeds, the proposal must not reduce curriculum
   score or damage dealt; at least one validation seed must strictly improve
   curriculum score.
8. Compare parent and proposal against an actual canonical ZEN brain. The
   proposal must not reduce combat score. This is a safety gate against obvious
   dummy-only regressions, not evidence of general competitive strength.
9. Only a proposal passing all three gates is marked as an accepted candidate.
   Otherwise the parent multipliers are retained. There is no auto-promotion.

The process remains bounded by a 1500 s experiment budget and a 35 minute job.
Runtime portable Python 3.10/site310 is used for Brian2, portable Python
3.11/site311 for bridge and optimizer, Java 21 and official headless ScreenData.
Thread limits are one for BLAS/OpenMP. Hardware, versions, runtime identity,
exact source and video hashes are saved. Game time and wall/recording duration
remain separate.

## Acceptance and interpretation

**H:** With the held-out-selected temporal readout fixed, symmetric perturbations
within the existing KC-MBON subspace can produce measurable curriculum-score
differences and a bounded candidate that does not regress the measured ZEN
combat condition.

**T:** Four antithetic pairs, repeated parent, strictly bounded proposal, two
separate curriculum validation seeds and a canonical-combat nondegradation gate.
This small pilot does not estimate a reliable win rate.

**D:** Software/complete-round/hash checks permit execution PASS. Equal scores
mean NO UPDATE, not failed infrastructure. A candidate is accepted only after
training gain, held-out curriculum gate and measured combat nondegradation.
Acceptance remains candidate-only and is not a strength claim.

**C:** Weak neural sensitivity, insufficient edge subspace, clipping, opponent or
seed effects, action-interface limitations, or inadequate search scale can still
make paired differences uninformative or unstable. One failed candidate does not
prove all neural learning impossible.

**U:** Seed/opponent effects, limited directions, one canonical-combat gate and
clipping dominate uncertainty. No confidence bound, general strength percentage,
or biological interpretation is assigned without broader independent data.

Reference: Salimans et al., Evolution Strategies as a Scalable Alternative to
Reinforcement Learning, arXiv:1703.03864. This project applies a bounded
parameter-search method; it does not claim to identify endogenous fly learning.
