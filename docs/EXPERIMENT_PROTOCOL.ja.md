# Experiment Protocol v0 (historical reference)

English-only compatibility document. This is the original confirmatory comparison protocol, not the active exploratory colosseum configuration.

## Goal

Use FightingICE as a fixed competitive environment to test whether Drosophila-derived topology provides a useful inductive bias for learning and transfer relative to structurally matched control networks.

## Evidence classes

1. `synthetic_fixture`: synthetic graphs or mock APIs only.
2. `live_game_control`: actual FightingICE without a biological graph.
3. `live_game_biological`: actual FightingICE with a provenance-verified biological graph.
4. `confirmatory`: preregistered conditions, seed sets, and opponents.

Never report a lower evidence class as a higher one.

## A/B design

**A: biological topology.** Freeze source, version, checksum, license, and preprocessing in a manifest. Match observations, actions, reward, optimizer, training budget, seeds, and opponents with B.

**B: rewired control.** Preserve node/edge counts, per-node in/out degree, and sign-specific degree. Swap edge targets and record the rewiring seed, accepted swaps, and original-edge overlap. Explicitly report when mixing has not been established.

An MLP/RNN may be an engineering reference outside the canonical path, but must not be confused with the primary biological A/B comparison.

## Initial reward

The original primary condition is terminal-only: win +1, loss -1, draw 0. Incomplete/disconnected episodes are excluded. Intermediate damage rewards belong to separate conditions.

## Evaluation quantities

Candidate primary outcomes are held-out opponent win rate, learning-curve area, matches to threshold, cross-opponent generalization, and robustness after action removal. Self-play win rate between the two changing participants is not sufficient evidence of progress.

## H / T / D / C / U

**H — Falsifiable hypothesis:** biological topology improves sample efficiency or final performance against unseen opponents relative to matched rewiring.

**T — Minimum test:** paired A/B training across multiple independent seeds using identical initialization rules and budgets. Separate exploratory from confirmatory seeds.

**D — Decision:** PASS only when the interval estimate for the preregistered A-minus-B effect lies sufficiently above the practical-effect threshold. UNCERTAIN when the interval crosses it. FAIL when evidence supports falling short.

**C — Alternatives:** examine routing, weight scale, network size, optimizer interactions, and opponent overfitting as explanations distinct from topology.

**U — Uncertainty:** report annotation uncertainty, sign/strength assumptions, routing assumptions, training-seed variance, and opponent-distribution uncertainty. Separate biological uncertainty from statistical sampling error.

## Original implementation order

Complete a headless random-vs-random fight; reconcile both agents' observations, actions, HP, and terminal rewards; validate the bridge with a synthetic controller; add a fail-closed biological importer; train the legacy fixed-connectome/readout condition; compare matched rewiring; separately test learning only existing edge weights under fixed topology; then conduct held-out confirmatory evaluation.

The custom synthetic/readout stages are historical engineering checks, not canonical MaleCNS evidence.

## Interpretation prohibitions

Learning a fighting game does not reproduce fly intelligence. Encoder/readout performance is not automatically a connectome-specific capability. Synthetic graphs are not biological results. Many matches from one trained policy are not multiple independent training seeds.
