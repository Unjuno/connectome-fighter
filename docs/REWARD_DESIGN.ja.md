# Reward design for canonical MaleCNS training

> English translation of the historical reward investigation, retained at the original compatibility path. Numbers below are reports from the cited historical runs, not new measurements. Proposals and frozen conditions retain their original scope; they do not override current versioned configurations.

## Goal

Compare only the external FightingICE modulatory signal **without changing MaleCNS/pinned-Shiu action generation**. The original investigation rescored existing trajectories offline before enabling learning or freezing reward density, scale, and timing.

## Fixed conditions

Fix MaleCNS v1.0 anatomy, pinned Shiu LIF dynamics, observation-driven Poisson randomness, output-group spike-count argmax, no external epsilon-greedy/random action injection, a 60-FightingICE-frame decision interval, and hash-pinned action mapping. Treat GARNET/ZEN/LUD/NEZ as separate individuals and rescore the same trajectories for each reward candidate.

The scheduled baseline retained the Poisson mechanism but used deterministic, distinct seed blocks per chunk so six-hour runs did not repeat an identical random sequence.

## First offline comparison

Canonical four-character baseline run `34620984683` contained six pairings, 48 game rounds, 96 player-specific brain-round reward sequences, and 960 decision windows. No learning or weight update was performed. Run `34629201168` rescored R0/R1/R2 offline and passed its checks.

### Observed sparsity

- Nonzero R0 terminal signs: 2/960 decisions, 0.2083%.
- Nonzero terminal outcomes: 2/96 brain-rounds, 2.0833%.
- Nonzero damage-difference decisions: 4/960, 0.4167%.
- Brain-rounds with damage signal: 2/96.
- Largest final HP margin: 20 HP.

Only one ZEN–NEZ match exchanged damage in that chunk. Two damage windows produce four signed local signals when both players are counted. The main problem was insufficient game interaction and scarce reward events, not the absolute magnitude of +1.

## R0 — terminal HP sign (control)

Reward only final HP order: win +1, draw 0, loss -1. This is simple and close to the game objective. In the recorded chunk, 47/48 rounds were no-damage or equal-HP draws; decision-level nonzero density was 0.2083%. Retain R0 as a control, but the data gave little basis for using it alone as the first learning reward.

## R1 — terminal sign plus normalized final HP margin

On the final decision, add final self-minus-opponent HP divided by 400 to the terminal sign. The largest 20-HP margin changed magnitude from 1.00 to 1.05. Density was unchanged from R0: 0.2083% of decisions and 2.0833% of brain-rounds. Margin information increased, but sparsity did not improve.

## R2a — local damage differential plus terminal outcome

For each window, use damage dealt minus damage taken, divided by 10 HP, multiplied by the damage coefficient. Add a weighted terminal sign on the last decision.

The offline grid used damage coefficients 0.05, 0.10, 0.25, 0.50, and 1.00, crossed with terminal coefficients 0.25, 0.50, and 1.00. Local timing improved, but the representative decision-level nonzero rate remained approximately 0.625%, roughly three times R0 and still sparse.

Both damage windows occurred during B actions. The naive policy already strongly favored B, so immediately training on R2a might reinforce an initial accident. R2a can improve temporal credit assignment but does not by itself solve no-contact draws.

## R2b — R2a plus a no-damage draw penalty (historical provisional candidate)

Apply a small negative signal on the final decision only if neither player's HP ever decreased and final HP is equal. Do not directly reward forward movement, attack-button selection, or approaching. Treat an uneventful timeout as an explicit engineering failure mode.

Use terminal +1/-1 for wins/losses; negative stalemate coefficient for a no-damage draw; zero for other draws; retain local weighted damage differences. Run `34629518296` performed the offline comparison and passed.

No-damage draws comprised 94/96 brain-rounds, 97.92%. Any positive penalty magnitude produced 100/960 nonzero decisions (10.4167%) and 96/96 brain-rounds with some nonzero signal. However, 97 of the 100 nonzero signals were negative, so a large penalty creates strong sign imbalance.

### Historical provisional scales

The proposed hierarchy was terminal win/loss ±1.00, a 10-HP differential ±0.10, and a no-damage draw penalty from -0.02 to -0.05.

| Penalty magnitude | Nonzero decision rate | Mean absolute decision reward | Maximum absolute signal |
|---|---|---|---|
| 0.02 | 10.4167% | 0.00446 | 1.0 |
| 0.05 | 10.4167% | 0.00740 | 1.0 |

All brain-rounds received a nonzero signal. The proposal retained damage weight 0.10, terminal weight 1.0, and stalemate magnitude 0.02–0.05 pending another independent Poisson-seed chunk's contact and damage measurements.

R2b is not zero-sum: both individuals receive negative reward on a no-damage draw. This is explicitly an engineering shaping assumption, not a biological fact.

## R3 — valence/compartment-specific DAN gating (later biological comparison)

R0/R1/R2 use an external scalar. Mushroom-body dopaminergic modulation is compartment-specific; KC-to-MBON plasticity should not automatically be modeled as one global mushroom-body update. A later condition would use MaleCNS DAN/MBON compartment annotations to map positive and negative valence through separate pathways. The game-outcome-to-DAN mapping remains an artificial, versioned interface, distinct from anatomy.

## Separation from the plasticity rule

At the time of this document, the `reward_plasticity.py` extension allowed changes only to existing KC-to-MBON candidate edges, with fixed topology and transmitter sign. It accepted terminal -1/0/+1, depressed eligible magnitudes for positive reward, and strengthened them for negative reward: an anti-Hebbian-style proposal.

R2a/R2b require continuous local signals, so the proposal required freezing reward semantics before extending the plasticity API to a temporal modulatory sequence. Do not change reward choice and plasticity direction/rate together. The current `valence_plasticity.py` depression-only path is a separate version; this historical paragraph is not its specification.

## Original adoption gate

1. Rescore R0/R1/R2a/R2b on at least two independent Poisson-seed chunks.
2. Compare density, mean absolute magnitude, maximum magnitude, and sign imbalance.
3. Preserve action randomness, readout, anatomy, LIF, and game interface.
4. Freeze selected coefficients in a versioned configuration.
5. Enable one character/one match and audit changed weights.
6. Demonstrate checkpoint resume in a separate Actions run before continuous learning.

## Do not reward directly

In the initial comparison, do not reward moving forward, pressing attack, approaching, action diversity itself, or avoiding NEUTRAL. Such rewards make it harder to separate circuits improving game outcomes from circuits merely emitting designer-selected actions.

## Primary literature recorded by the investigation

- Hige T, Aso Y, Rubin GM, Turner GC. *Plasticity-driven individualization of olfactory coding in mushroom body output neurons.* Nature 526, 258–262 (2015). DOI `10.1038/nature15396`.
- Felsenberg J et al. *Re-evaluation of learned information in Drosophila.* Nature 544, 240–244 (2017). DOI `10.1038/nature21716`.
- Felsenberg J et al. *Dopaminergic mechanism underlying reward-encoding of punishment omission during reversal learning in Drosophila.* Nature Communications 12, 1115 (2021). DOI `10.1038/s41467-021-21388-w`.
- *Dopamine-mediated interactions between short- and long-term memory dynamics.* Nature (2024). DOI `10.1038/s41586-024-07819-w`. The recorded interpretation concerns compartmental DAN/MBON interactions and bidirectional anti-Hebbian KC-to-MBON plasticity.

## Interpretation boundary

Game outcomes, damage, and stalemate are external engineering signals, not identified endogenous fly dopamine signals. Using MaleCNS anatomy does not make game-outcome-to-DAN mapping biological.
