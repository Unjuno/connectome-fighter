# Reward experiment: terminal signal vs anti-stall penalty vs shaping

This document defines the first reward comparison before any candidate is promoted to production continuous learning.

## H — Hypotheses

**H1.** A terminal-only objective may be scientifically clean but too sparse for the current MaleCNS/FightingICE interface, producing many low-engagement draws.

**H2.** Adding a small penalty only to zero-damage draws/timeouts may increase engagement without directly rewarding a particular action or prescribing how to fight.

**H3.** Dense damage/engagement shaping may improve short-horizon learning efficiency, but any benefit must be separated from reward-induced behavioral bias.

## T — Treatments

### A: `R3a-terminal-v0`

- win: `+1`
- loss: `-1`
- ordinary draw: `0`
- zero-damage draw: `0`
- damage shaping: disabled (`weight = 0`)
- engagement shaping: disabled

This is the minimal outcome-only control.

### B: `R3b-terminal-nodamage-v0`

- win: `+1`
- loss: `-1`
- ordinary draw with nonzero damage: `0`
- zero-damage draw/timeout: `-0.1`
- damage shaping: disabled (`weight = 0`)
- engagement shaping: disabled

This changes only the degenerate zero-damage outcome. It does not reward moving forward, attacking, pressing a specific button, or occupying a particular distance.

### C: `R2d-v0`

Existing shaped smoke contract:

- terminal outcome reward;
- no-damage draw penalty `-0.01`;
- damage-differential shaping;
- engagement-potential shaping.

C is an engineering-shaped comparison condition, not the default scientific control.

## D — Data and decision criteria

Measure all conditions using the same checkpointing cadence and report distributions across seeds, not only aggregate means.

Primary behavioral metrics:

- nonzero-damage match rate;
- time to first hit;
- decisive-match rate;
- W/L/D;
- damage differential;
- action entropy and action-frequency vector;
- timeout rate.

Neural / circuit-use metrics:

- active body-ID count per decision window;
- unique recruited body IDs per match;
- output-group spike distribution;
- concentration of activity across repeatedly dominant bodies;
- change in KC→MBON multiplier distribution.

Safety / integrity metrics:

- topology unchanged;
- transmitter/sign unchanged;
- no potentiation when the depression-only invariant is active;
- exact checkpoint hash and generation lineage;
- no epsilon-greedy or action-specific reward.

A candidate should not be promoted only because it produces more damage. Promotion requires improved engagement without a pathological action collapse or unstable checkpoint dynamics.

## C — Controls held fixed

Across A/B/C, hold constant:

- MaleCNS v1.0 anatomy and filtering;
- pinned Shiu LIF implementation and parameters;
- FightingICE v7.1;
- observation encoder;
- sensory-body mapping;
- output-body/action mapping;
- decision interval;
- KC→MBON candidate edge set;
- plasticity learning rate, eligibility decay and multiplier bounds;
- initial checkpoint generation;
- training match budget;
- evaluation match budget;
- seed schedule;
- evaluation opponents;
- no epsilon-greedy;
- no action-specific reward.

The matched plasticity files for A and B differ from the existing smoke file only in the referenced reward contract.

## U — Uncertainty and interpretation

- A failure of terminal-only learning does not imply that biological flies require the B or C signal.
- A success of B does not establish zero-damage aversion as a biological reward pathway.
- C may learn faster because it carries more information, but that can also impose a stronger experimenter prior.
- The project should report both learning efficiency and induced behavioral/circuit bias.

## Recommended first run

Run **A vs B first** with matched compute. Use C only as the shaped reference condition.

If A and B are both ineffective, then compare C rather than repeatedly adding ad-hoc action rewards. In particular, do not reward the `B` action or any other specific FightingICE action; earlier canonical baseline behavior already showed a strong action-frequency imbalance, so action-specific reward would confound the experiment.
