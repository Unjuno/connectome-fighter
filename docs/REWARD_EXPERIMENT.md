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


## Gen49 terminal-credit gain counterfactual

Recent Gen49 training attempts show a broader credit-assignment problem than the
zero-damage timeout case alone. Main-branch run 2311 won its training round but
the resulting R2e proposal regressed the fixed publication suite. Main-branch
run 2312 lost its training round and also regressed that suite.

Inspection of immutable training artifacts shows that the final R2e terminal
outcome event dominates the one-match KC->MBON depression:

- winning evidence: the terminal +2 event accounts for about 90.8% of the mean
  multiplier decrease;
- losing evidence: the terminal -2 event accounts for about 90.6% of the mean
  multiplier decrease.

The local damage and engagement events therefore provide only about one tenth
of the total one-match weight movement in these examples. This suggests that
the external combat objective and the plasticity credit signal should be tested
separately.

The experiment keeps `R2e-combat-v1` unchanged as the external objective. It
does not define a new reward. Instead, only the terminal outcome/finish
component is multiplied by a gain of `0.1` before it reaches the experimental
KC->MBON modulatory update. Damage and engagement-potential components remain at
their canonical R2e values. The gain is calibrated from the observed source
artifacts: reducing the terminal contribution by roughly tenfold makes its
expected weight effect comparable to the accumulated nonterminal effect
(`+/-2 -> effective +/-0.2`).

The experiment must first reproduce two immutable Gen49 control proposals
byte-for-byte:

- win run 2311: ZEN, seeds 986465 / 949593;
- loss run 2312: LUD, seeds 961650 / 875148.

It then evaluates the parent, both canonical R2e control proposals, and both
terminal-gain treatments on a separate six-case selection suite with two
previously unused seeds each for ZEN, LUD, and NEZ. A treatment is considered
supportive only when it has positive mean canonical utility versus both its
control proposal and the Gen49 parent, improves at least 4/6 paired cases versus
each, and causes no win/draw/loss outcome regression versus either.

Both the winning and losing training traces must satisfy that rule before the
gain can advance to a new confirmatory holdout. A mixed result is evidence that
a single terminal gain is not yet robust enough. None of these results can
publish a canonical checkpoint automatically.

The terminal-gain state is explicitly marked
`canonical_training_eligible=false`. The experiment changes no topology,
transmitter sign, action reward, policy readout, decision cadence, production
LIVE configuration, or canonical continuous-learning settings. The
reward-to-KC/MBON mapping remains a project-defined engineering interface, not
an identified endogenous Drosophila reinforcement pathway.
