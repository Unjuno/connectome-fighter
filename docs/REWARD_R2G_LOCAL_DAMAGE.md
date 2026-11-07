# R2g local damage credit: production candidate-training intervention

**Status:** versioned experimental production *candidate-training*, not approved FightingICE/Vercel LIVE inference. The accepted model can advance only through the unchanged frozen R2e win/damage utility and win/draw/loss no-regression gate.

## Motivation from actual real-game data

The accepted GARNET lineage remains **Gen49**. On November 7, 2026, the most recent 20 completed canonical R2f training proposals were all rejected; 20/20 full updates and 20/20 backtracked 25% updates failed the same frozen three-opponent R2e gate. Mean full-step R2e utility delta was about -0.974 and the mean quarter-step delta about -1.241, both relative to the unchanged Gen49 parent. The 25% reduction has no demonstrated benefit. These 20 trials share the **same** Gen49 parent and deterministic ZEN/LUD/NEZ selection seeds, so they are not 20 independent confirmations of general fighting strength.

The 600-frame scheduled MaleCNS baseline on November 7 produced 48/48 no-damage draws. This is a **distinct baseline protocol**, not a sample of 3600-frame GARNET learning games. It diagnoses reward sparsity, not an observed result of this R2g treatment.

R2f terminal win/loss learning credit (+/-1) is often much larger than the small real damage-window credits on a 60-decision 3600-frame match. Changing only the size of the terminal signal or the size of the final multiplier step has repeatedly failed to produce an accepted stronger candidate. This motivates a different, falsifiable *temporal attribution* hypothesis.

## Frozen R2e objective and new local credit

Compute the **original R2e reward sequence from the full, trainable, immutable, complete FightingICE game trace** first. Preserve that original R2e game utility as the external selection metric. Then supply the KC-MBON plasticity updater with an R2g modulation signal containing only:
- HP damage dealt minus HP damage taken, divided by the frozen 400 game-HP normalization;
- The original difference of distance potentials, using the existing 180-game-pixel contact band, 960-game-pixel stage width, and 0.05 dimensionless weight.

Remove **all terminal modulation**: win/loss, ordinary draw, no-damage draw, and early winning KO bonus each have *zero training-credit value*. This is **not** a change to the actual game result: wins, losses, HP differential and KO status still count identically toward R2e acceptance. No specific action, button, motion direction, action diversity, survival or artificial neural activity earns a separate reward.

### Variable dictionary and unit check

| Symbol | Meaning | SI unit | Definition | Valid domain and conditions | Type |
|---|---|---|---|---|---|
| `s_t` | Local KC-MBON modulatory signal at decision `t` | 1 | `d_t + p_t` | Finite, validated original R2e event only | Real scalar |
| `d_t` | Damage differential modulation | 1 | `(HP dealt - HP taken) / 400 game HP` | Actual observed game HP changes, no healing | Real scalar |
| `p_t` | Existing engagement potential modulation | 1 | `0.05 * (potential_next - potential_now)` | Original R2e potential, zero terminal potential | Real scalar |
| `t` | Neural decision index | 1 | Contiguous zero-based real-game decision count | Integer in the complete game trace | Integer scalar |

**Dimension check:** game HP divided by game HP is dimensionless; potential is defined as game pixels divided by game pixels, also dimensionless. Each term in `s_t` therefore has SI dimension one. Game pixels and hit points are not physical SI units.

## Identity and production boundaries

- Reward ID: `R2g-local-damage-credit-v1`, immutable `configs/reward_r2g_local_damage_credit_v1.json`.
- Only the learning-credit signal changes. Original R2e reward JSON and the external objective remain byte-identical; no redefinition of a higher score.
- Preserve genuine MaleCNS v1.0 anatomy (about 156,675 neurons), pinned Shiu LIF dynamics, actual FightingICE v7.1 matches, the 60-game-frame decision interval and existing depression-only bounded KC-MBON topology, signs and multipliers in [0.8, 1.0].
- The accepted Gen49 R2e checkpoint remains the parent. No weights change until a complete game has been played and candidate weights have passed the R2e validation gate.
- The actual trainer calls the updater with `--learning-credit-config configs/reward_r2g_local_damage_credit_v1.json`; `update.json`, new checkpoint metadata, public status and history carry the R2g credit ID and exact SHA256.
- A published accepted R2g checkpoint must resume using the same R2g credit bytes. An accepted older R2f checkpoint must **not** be silently relabeled R2g; that case requires an explicit audited fork and is rejected by the dependency resolver.
- If the full candidate fails, the existing `r2g-local-damage-backtrack-v1` step produces exactly one 25% synaptic-change alternative and evaluates real frozen games on the same original R2e suite. This is a multiple-hypothesis selection mechanism; both candidates can be rejected. No relaxation of acceptance, no auto-promotion and no LIVE learning.

## Falsifiable verification plan — H/T/D/C/U

**H (hypothesis):** Relative to R2f's uninformative terminal modulation, R2g produces a larger fraction of accepted **R2e-evaluated** updates without increased win/draw/loss regressions. A strict acceptance rate above zero over a prespecified first 20 independent *training attempts* is an exploratory software-operational milestone, not a causal performance guarantee.

**T (minimum test):** Continue actual fixed-code training from Gen49, log 20 sequential R2g match attempts (same actual opponent rotation, deterministic validation seeds and unchanged hardware/backend). Record both full and, when needed, quarter-step R2e evaluation. Compare against archived 20 R2f attempts descriptively; separately run future matched-seed R2f/R2g experiments on predeclared untouched training seeds with independent evaluation seeds before causal claims.

**D (PASS/FAIL/UNCERTAIN):** CI software PASS requires exact byte-hash identity, validated game traces, no topology/sign/potentiation changes and R2e evaluation parity. Candidate PASS requires the unchanged R2e gate: strictly positive average paired utility, improvement on at least two of three opponents, no outcome regressions. Otherwise reject without publishing. If 0/20 R2g updates are accepted, the exploratory R2g acceptance hypothesis FAILS for that sample; this does not prove all possible local-credit policies fail. General fighting strength remains UNCERTAIN absent a fresh holdout.

**C (competing explanations):** Local damage signals may be too sparse; external FightingICE observations or 60-frame action scheduling may prevent contact; KC-MBON depression-only updates may have wrong valence targeting, limited controllability or saturation; the fixed evaluation suite may penalize valid new policies.

**U (uncertainty):** Training seed/Poisson spike noise, opponent setup, R2e fixed-seed overfit, Brian2 Cython ABI and numerical float32 weight rounding, stage position conventions, scheduler drift and game-to-neural latency are material uncertainties. No defensible combined standard uncertainty `u_c` or coverage factor `k` is assigned from the 20 correlated historic Gen49 experiments. Code-quality PASS alone is not biological or fighting-performance evidence.

## Cross-disciplinary review

The intervention draws on reinforcement learning (temporal credit assignment), computational neuroscience (eligibility-weighted synaptic depression) and control theory (observability and action latency), with statistical design (independent held-out seed evaluation). Relevant primary sources: Shiu et al. (2024), DOI 10.1038/s41586-024-07763-9; Aso et al. (2014), DOI 10.7554/eLife.04580. Neither paper identifies this game reward as a natural Drosophila dopamine signal.

**ERROR CHECK:** no new synthetic controller, no new game reward for buttons, no R2e metric change, no graph rewiring, no automatic LIVE promotion, and no claim of improved fighting from code alone.
