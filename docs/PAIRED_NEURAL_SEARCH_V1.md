# Paired neural search v1 — bounded pilot

## Adopted design and scope

This implements the user-approved analytical proposal as a separate experiment,
not an unannounced modification of R2e or approved inference. P1 remains the real
MaleCNS/Shiu LIF controller. Only audited existing positive KC-to-MBON edge
magnitudes are changed. The search can recover previously depressed magnitudes,
so it is explicitly NOT the old monotonic depression-only biological hypothesis.
No MLP, heuristic game controller or synthetic neural graph replaces P1.

The initial pilot does not create a second recurring scheduler and does not
publish to the production viewer or existing candidate pointer. Its artifacts
include the selected checkpoint, raw game/neural traces and real videos. The
old R2e scheduler is not stopped by this experiment. No automatic promotion.

## Rewards

Combat uses terminal outcome (+1/0/-1) plus 0.02 times normalized final HP
advantage, given equal 400/400 initial HP. Equivalently, outcome is paid once and
HP-advantage differences are summed without discount. Moving, button presses,
spikes, fast losses and damage-free draws receive no extra reward.

The neutral-dummy curriculum uses 0.1 times approach progress, 0.4 for any actual
damage dealt, and 0.5 times damage dealt divided by 400. Approach progress is the
fractional reduction from initial horizontal distance to the minimum recorded
delayed-frame distance. Repeated back-and-forth does not accumulate progress.
The dummy never attacks or moves intentionally; actual game physics still runs.
This is a different training objective, never evidence of competitive strength.

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
with clipping and argmax actions; it does not guarantee an informative signal.

## Fixed protocol

The pilot fixes decision interval 60 game frames and neural window 20 ms. It does
not confound cadence with reward or neural-time changes. Both actors are frozen
throughout each 3600-frame-maximum round. Training seed is 910001; validation
seeds 910101/910102 are not used for candidate selection. Canonical comparison
uses the existing fixed seed 800101/20202 and is not a held-out strength test.

1. Resolve one runtime and one parent checkpoint by release asset IDs/digests.
2. Verify structural/reference/game/interface hashes and checkpoint config.
3. Run the parent twice against the neutral dummy; require identical recorded
   metrics and decision-activity signatures under the same seed.
4. Execute four plus/minus Gaussian perturbation pairs. Alternate order.
5. Estimate g; propose 0.05*g, bounded to Euclidean norm 0.02. Identical paired
   scores produce exactly zero update, including identical negative scores.
6. Test a nonzero proposal against the same training condition. Retain it only
   for strict curriculum improvement; otherwise retain parent weights.
7. For an accepted proposal only, compare two separate validation seeds. These
   report exploratory generalization; they do not select or promote the child.
8. Run parent/selected candidates against an actual canonical ZEN brain and
   record both official ScreenData videos. No-change candidates still run again.

Twelve games when paired scores are equal; up to seventeen with a proposal and
two paired validation conditions. Overall process budget 1500 s, job 35 minutes.
Runtime portable Python 3.10/site310 for Brian2, portable Python 3.11/site311 for
bridge and optimizer, Java 21 and official headless ScreenData. Thread limits are
one for BLAS/OpenMP. Hardware, versions, runtime identity, exact source and video
hashes are saved. Game time and wall/recording duration remain separate.

## Acceptance and interpretation

**H:** Within this bounded KC-MBON subspace, symmetric perturbations can produce
measurable curriculum-score differences and a candidate with improved contact.
**T:** Four pairs, repeated parent, strictly bounded proposal, separate validation
and canonical combat. This small pilot does not estimate a reliable win rate.
**D:** Software/complete-round/hash checks permit execution PASS. Equal scores
mean NO UPDATE, not a failed infrastructure run and not learning success. A
strict training gain is a candidate-only acceptance, not a strength claim.
**C:** Weak sensitivity, saturated routing, single-key action limits, sampling,
low-dimensional grouping or an insufficient search scale can make every pair
uninformative. This does not prove all neural learning impossible.
**U:** Seed/opponent effects, limited directions and clipping dominate uncertainty.
No improvement percentage, confidence bound or biological interpretation is
assigned without suitable independent data.

Reference: Salimans et al., Evolution Strategies as a Scalable Alternative to
Reinforcement Learning, arXiv:1703.03864. This experiment applies a bounded
parameter-search method, not a claim of identified endogenous fly learning.
