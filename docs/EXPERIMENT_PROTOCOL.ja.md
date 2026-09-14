# Experiment protocol v0

> English translation at the original compatibility path. This historical protocol is not silently promoted to the current training configuration.

## Goal

Use FightingICE as a fixed competitive environment to test whether Drosophila-derived connectome topology provides an inductive bias for learning and transfer beyond structurally matched control networks.

## Evidence classes

Every result must identify its evidence class:

1. `synthetic_fixture`: synthetic graphs or mock APIs only.
2. `live_game_control`: actual FightingICE without a biological graph.
3. `live_game_biological`: actual FightingICE with a provenance-verified biological graph.
4. `confirmatory`: preregistered conditions, seed sets, and evaluation opponents.

Never report a lower evidence class as a higher one.

## A/B design

### A: biological topology

Pin source, version, checksum, license, and preprocessing in a manifest. Match observations, action set, reward, optimizer, training budget, seeds, and evaluation opponents to condition B.

### B: rewired control

Preserve node/edge counts, each node's in/out-degree, and sign-specific in/out-degree. Swap edge targets; record rewiring seed, accepted swaps, and edge overlap. Explicitly state when adequate mixing has not been established.

### Engineering references

MLP/RNN reference policies may be evaluated separately, but must not replace or be confused with the biological A/B comparison.

## Reward

The initial main condition is terminal-only: win +1, loss -1, draw 0. Incomplete/disconnected episodes are excluded from learning. Intermediate damage rewards are separate experimental conditions.

## Evaluation measures

Candidate primary measures are held-out-opponent win rate, area under the learning curve, matches to a threshold, cross-opponent generalization, and robustness after action removal. Win rate between the two currently co-learning agents is not sufficient evidence of progress.

## H / T / D / C / U

**H — Falsifiable hypothesis.** Biological topology improves held-out-opponent sample efficiency or final performance relative to a matched rewired control.

**T — Minimum test.** Train paired A/B conditions across independent seeds with the same initialization rules and budget. Separate exploratory seeds from confirmatory seeds.

**D — Decision.** PASS only if the interval estimate for the preregistered A-minus-B metric lies sufficiently beyond a practical-effect threshold. UNCERTAIN if the interval crosses that threshold; FAIL when the result supports failure to reach it.

**C — Alternative explanations.** Check input/output routing, weight scale, network size, optimizer interactions, and overfitting to a particular opponent rather than attributing differences automatically to topology.

**U — Uncertainty.** Principal sources are biological annotations, synaptic sign/strength models, routing assumptions, RL seed variance, and opponent distribution. Report biological uncertainty separately from statistical sampling error.

## Initial implementation order

1. Finish a headless random-versus-random live FightingICE round.
2. Cross-check both players' observations, action requests, remaining HP, and terminal rewards.
3. Verify the bridge with a synthetic-graph controller.
4. Add a biological importer with fail-closed manifests and checksums.
5. Train a fixed-connectome, trainable-readout condition.
6. Compare it against matched rewiring.
7. Add topology-preserving, existing-edge-only plasticity as a separate experiment.
8. Run confirmatory held-out-opponent tests.

## Prohibited interpretations

Learning a fighting game is not evidence of recreating fly intelligence. Artificial encoder/readout performance is not a connectome-specific capability. Synthetic graphs are not biological results. Many matches from one trained policy are not independent training seeds.
