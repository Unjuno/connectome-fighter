# Reward Design for Canonical MaleCNS Training (historical analysis)

This English-only compatibility document preserves the original offline R0/R1/R2 analysis. Its historical learning-disabled statements and 60-frame comparison are not the current schedule. The active exploratory reward is documented in [COLOSSEUM.md](COLOSSEUM.md).

## Purpose and fixed conditions

The original design compared external FightingICE modulatory signals without changing behavior generation. Existing trajectories were rescored offline before choosing signal density, scale, and timing; no learning was enabled in those comparisons.

Anatomy was MaleCNS v1.0, dynamics the pinned Shiu LIF, sensory randomness observation-driven Poisson spikes, and action readout output-group spike-count argmax. External epsilon-greedy/random action injection was absent. The decision interval was 60 game frames; a fixed interface hash controlled action mapping. GARNET, ZEN, LUD, and NEZ were independent individuals. Reward candidates rescored the same trajectories. Baseline chunks used different deterministic Poisson seed blocks rather than repeating the same random sequence every six hours.

## First offline comparison: recorded historical evidence

Canonical four-character baseline Actions run `34620984683` contained six pairings, 48 game rounds, 96 brain-rounds (each game counted separately for P1 and P2 reward sequences), and 960 decision windows, without learning or weight updates. Run `34629201168` rescored R0/R1/R2 offline and passed its comparison checks.

Reported sparsity:

- Nonzero terminal-sign decisions: 2/960 (0.2083%).
- Nonzero terminal outcomes: 2/96 brain-rounds (2.0833%).
- Decisions with nonzero damage differential: 4/960 (0.4167%).
- Brain-rounds with damage signals: 2/96.
- Largest final HP margin: 20 HP.

Only one ZEN–NEZ game in that chunk exchanged damage. Its two damage windows yield four signed local signals when both players are counted. The immediate issue was rare interaction, not the absolute size of a +1 victory reward.

## R0: terminal HP sign (control)

Win +1, draw 0, loss -1. This is simple and close to the game objective, but 47 of 48 games were no-damage or equal-HP draws. The recorded decision-level nonzero rate was 0.2083%. Preserve it as a control; the initial data offered little support for using it alone to start learning.

## R1: terminal sign plus normalized final HP margin

At the final decision, add the final self-minus-opponent HP margin divided by 400 to the outcome sign. A 20 HP margin changed magnitude from 1.00 to 1.05. Density was identical to R0: 0.2083% of decisions and 2.0833% of brain-rounds. Margin information increased, but sparsity did not improve.

## R2a: local damage differential plus terminal outcome

For each decision, compare HP with the next observation. One damage unit is 10 HP; multiply net dealt-minus-taken damage units by a damage weight. Add a signed terminal bonus at the last decision.

The offline grid used damage weights 0.05, 0.10, 0.25, 0.50, and 1.00, and terminal weights 0.25, 0.50, and 1.00. Representative nonzero-decision density was about 0.625%: roughly three times R0, but still sparse. Both damage windows happened after action B, which already dominated the naive policy, so reinforcement could lock in an initial accident. Local damage improves timing but does not by itself solve no-contact draws.

## R2b: R2a plus a no-damage draw penalty

On a draw in which neither player's HP ever decreased, apply a small negative terminal signal. This penalizes an uneventful timeout rather than directly rewarding forward movement, attacks, or approach. Damaging draws retain zero terminal reward; wins/losses retain +1/-1.

Offline comparison run `34629518296` passed. No-damage draws accounted for 94/96 brain-rounds (97.92%). For any positive stalemate-penalty magnitude, the same trajectories had 100/960 nonzero decisions (10.4167%) and nonzero signals in all 96 brain-rounds. However, 97 of the 100 nonzero signals were negative.

Historical provisional scales were terminal +1/-1, 10 HP net damage +0.10/-0.10, and a no-damage draw penalty from -0.02 to -0.05. At penalty magnitude 0.02 the recorded mean absolute decision signal was 0.00446; at 0.05 it was 0.00740. Both retained 10.4167% density and maximum absolute signal 1.0.

These were candidates, not final choices. Independent seed chunks were required before freezing coefficients. R2b is not zero-sum: both participants can receive a negative no-damage penalty. That is engineering shaping, not a biological fact.

## Historical R3 proposal: compartment-specific DAN gating

The original document used the heading R3 for a future biological comparison using DAN/MBON compartments and separate positive/negative pathways. That historical label is **not** the configuration ID `R3-colosseum-v1` introduced later. Game-outcome-to-DAN mapping remains an artificial interface and must be versioned independently of anatomical wiring.

## Separation from plasticity

At the time of this analysis, `reward_plasticity.py` was described as an anti-Hebbian project extension: existing real KC–MBON candidates only, fixed topology/signs, terminal -1/0/+1, depression for positive reward and strengthening for negative reward. Continuous local signals required extending that API after freezing the reward definition.

This historical description must not be confused with the later **depression-only valence-channel updater** used by the canonical candidate lane. Reward choice, plasticity direction, and learning-rate changes require explicit separate identities.

## Original adoption gates

Offline-score R0/R1/R2a/R2b on at least two independent Poisson seed chunks; compare density, mean absolute signal, maximum signal, and sign imbalance; hold anatomy, dynamics, action randomness, readout, and interface fixed; version the chosen coefficients; audit one character and one match of weight updates; then demonstrate checkpoint resume in another run before continuous learning.

## Quantities not directly rewarded

Forward movement, attack-button presses, proximity, action diversity, and avoiding NEUTRAL were not direct reward targets in the original comparison. Rewarding those quantities risks confusing improved game outcomes with designer-specified behavior.

## Primary literature recorded in the original analysis

- Hige et al., *Plasticity-driven individualization of olfactory coding in mushroom body output neurons*, Nature (2015), DOI `10.1038/nature15396`.
- Felsenberg et al., *Re-evaluation of learned information in Drosophila*, Nature (2017), DOI `10.1038/nature21716`.
- Felsenberg et al., *Dopaminergic mechanism underlying reward-encoding of punishment omission during reversal learning in Drosophila*, Nature Communications (2021), DOI `10.1038/s41467-021-21388-w`.
- *Dopamine-mediated interactions between short- and long-term memory dynamics*, Nature (2024), DOI `10.1038/s41586-024-07819-w`; the original analysis cites compartmental DAN/MBON interactions and bidirectional anti-Hebbian KC–MBON plasticity.

## Interpretation boundary

Game wins, damage, and stalemates are external engineering signals, not identified endogenous fly dopamine signals. Biological anatomy does not make the game-to-modulator interface biological ground truth.
