# R2f credit-balanced reward candidate (October 19, 2026)

**Status: active candidate-training credit on main once merged; R2e remains the frozen external performance score and checkpoint fingerprint. Research candidate, never approved LIVE inference or auto-promotion. Actual improvement remains unverified.**

## 1. Measured motivation

- [Real MaleCNS/Shiu training run 39205782160](https://github.com/Unjuno/connectome-fighter/actions/runs/39205782160): GARNET generation 49 against NEZ, 3,600 FightingICE frames, 60 decisions, 30 HP dealt, 40 HP taken, lost the training round. The proposed Gen50 update failed frozen ZEN/LUD/NEZ evaluation: mean canonical R2e utility 2.179167 to 1.358333, including a win-to-draw regression against NEZ. **Gen50 was rejected, not published**.
- The recorded training reward components over 60 windows were damage -0.025, distance potential +0.015625, terminal -2.0, total **-2.009375**. Approximately 94.77% of the *observed mean multiplier decrease* occurred at the final decision. The final window also contains nonterminal components, and exponential/clipped synaptic updates are nonlinear: this is temporal concentration, **not causal attribution** to the terminal component.
- A distinct short [baseline batch 39201908982](https://github.com/Unjuno/connectome-fighter/actions/runs/39201908982) saw 47/48 zero-damage draws in **600-frame** baseline fights. Do not pool it with the 3,600-frame Gen49 learning-round distribution.
- [PR #86](https://github.com/Unjuno/connectome-fighter/pull/86) (remove only no-damage penalty) and [PR #87](https://github.com/Unjuno/connectome-fighter/pull/87) (multiply only terminal credit by 0.1) failed their preregistered behavioral selection gates. Smaller terminal magnitude **does not imply** better fighting.

## 2. Versioned intervention

Preserve the external fighting-performance evaluation objective exactly as R2e, but fork the input to the KC-MBON plasticity updater under a **different** reward ID: `R2f-credit-balanced-v1`.

| Component | Original R2e learning credit | R2f research learning credit | R2f external evaluation |
|---|---:|---:|---|
| Terminal win / loss | +2 / -2 | **+1 / -1** | Original R2e unchanged |
| No-damage draw at timeout | -0.25 | **0** | Original R2e unchanged |
| Draw with exchanged damage | -0.05 | **0** | Original R2e unchanged |
| Fast winning KO bonus, maximum | +0.25 | **+0.125** | Original R2e unchanged |
| Net damage component | (dealt - taken) HP / 400 HP | Unchanged | Unchanged |
| Distance potential | Weight 0.05, band 180 game px, scale 960 game px | Unchanged | Same R2e definition |
| Neural/game cadence | 60-frame decisions / 20-ms neural window | Unchanged | Unchanged |
| KC-MBON learning rate, eligibility decay, bounds | 0.01 / 0.9 / [0.8, 1] | Unchanged | Unchanged |

A zero-damage outcome cannot provide evidence of a successful combat maneuver; assigning a large negative terminal modulation to the approach-associated pathway on such a round can suppress credit indiscriminately. Setting its *terminal* credit to zero avoids that particular mechanism, while any actually observed approach-related potential signal remains. This change does **not** create contacts or reward button presses.

The win/loss credit gain of 0.5 and the draw-credit change are two independent factors altered in the combined R2f candidate. To identify the contribution of each, execute a 2x2 experiment: unchanged R2e; win/loss gain 0.5 alone; draw neutralization alone; and both combined (R2f). No direct reward for FORWARD, attack keys, action entropy, survival time, or action frequency is added.

## 3. Equation, complete variable dictionary, and dimension check

The project-defined reward *modulation* in one decision window is

\[
s_t = d_t + p_t + g_T T_t + g_K K_t + D_t.
\]

Nonterminal decisions have \(T_t = K_t = D_t = 0\). At a completed game terminal, \(T_t\) denotes only the R2e winning/losing outcome, \(K_t\) only a valid winning-KO timing bonus, and \(D_t\) the ordinary or zero-damage draw term. R2f fixes \(g_T=g_K=0.5\) and \(D_t=0\). R2e uses both gains equal to 1 and its existing draw penalties.

| Symbol | Meaning | SI unit | Definition | Range / assumptions | Type |
|---|---|---|---|---|---|
| \(s_t\) | KC-MBON modulatory reward at decision t | 1 | Sum in equation | Finite, complete and trainable round | Real scalar |
| \(d_t\) | Normalized damage differential | 1 | (HP dealt - HP taken) / 400 HP | Finite game-HP changes, no healing | Real scalar |
| \(p_t\) | Potential shaping increment | 1 | \(0.05[\Phi(x_{t+1})-\Phi(x_t)]\) | Terminal potential is zero | Real scalar |
| \(\Phi(x)\) | Engineering distance potential | 1 | \(-\min(\max(x-180,0),960)/960\) | Game-pixel units throughout | Real scalar |
| \(x_t\) | Horizontal P1–P2 separation | Non-SI game px | Absolute difference of character x coordinates | Nonnegative finite | Real scalar |
| \(T_t\) | Terminal R2e outcome signal | 1 | Win +2, loss -2, draw 0 | Only at last decision | Real scalar |
| \(K_t\) | Source fast-winning-KO bonus | 1 | R2e bonus, 0 to 0.25 | Zero for loss/draw/non-KO | Real scalar |
| \(D_t\) | Draw-only terminal credit | 1 | R2f 0; R2e -0.25 or -0.05 | Only at last decision | Real scalar |
| \(g_T\) | Terminal outcome modulation gain | 1 | R2f 0.5 | Fixed in this version | Real scalar |
| \(g_K\) | KO timing modulation gain | 1 | R2f 0.5 | Fixed in this version | Real scalar |
| \(t\) | Decision index | 1 | Zero-based integer index | Nonnegative, less than number of decisions | Integer scalar |

**Dimensional check:** HP / HP and pixel / pixel both cancel. Every summand has SI dimension one, making \(s_t\) dimensionless. Game HP and game pixels are not SI joules or metres.

**Recorded-trace arithmetic, NOT training:** On run 39205782160, simply replacing the last loss signal -2 with -1 while keeping the observed damage and potential fixed gives -0.025 + 0.015625 - 1 = **-1.009375**, compared with R2e -2.009375. This counterfactual does **not** produce new weights, new game actions, wins, or measured strength.

## 4. Implementation and execution safety

- `src/connectome_fighter/combat_reward_r2f.py` reuses strict canonical R2e round validation, enforces reward-component consistency and terminal placement, and changes only the resulting modulatory credit. Its evaluation utility and validation gate explicitly delegate to R2e.
- `configs/reward_r2f_credit_balanced_v1.json` and `configs/plasticity_r2f_credit_balanced_v1.json` record immutable semantics. Mutating coefficients without incrementing the reward identity fails validation.
- `scripts/update_malecns_valence_plasticity.py` routes only the explicit R2f ID to the new scorer; the existing R2e branch remains textually unchanged.
- `src/connectome_fighter/combat_reward_r2f_checkpoint.py` and `scripts/fork_r2f_candidate.py` create a new hash-audited *research* state with the same inherited graph/candidate SHA, weights, counters and plasticity parameters, never replacing the source checkpoint.
- `tests/test_reward_r2f_credit_balanced.py` checks wins, losses, draws, early KO, unchanged local credit, rejected malformed rounds and tampering, R2e parity, and immutable checkpoint forking. `.github/workflows/reward-r2f-research-contract.yml` runs CPU-only software tests, not real game retraining.

To fork an already-verified R2e checkpoint into a **new** local research destination:

```bash
python scripts/fork_r2f_candidate.py \
  --source-state /verified/r2e/state/GARNET.npz \
  --research-state runs/r2f/parent/GARNET.npz
```

Only apply the existing spike/candidate-table updater to that *research* state with explicit `--reward-config configs/reward_r2f_credit_balanced_v1.json` and `--plasticity-config configs/plasticity_r2f_credit_balanced_v1.json`, plus a provenance-verified complete real-game round. Once deployed to the main combat-candidate-training workflow, R2f is used for every complete real-game training update and its ID and byte hash are recorded in each checkpoint, candidate history, and rejected-run result. Until the first main-branch update finishes, actual R2f learning remains unverified.

**Runtime assumptions:** FightingICE 7.1, pyftg 2.3, Java 21, MaleCNS v1.0, pinned Shiu LIF, reference Brian2 2.5.1 / NumPy 1.24.0 / Cython 0.29.36, Python 3.10 Brian2 compiled cache at its pinned path/ABI, and Python 3.11 game bridge. CI contract tests use Ubuntu 24.04, Python 3.11, NumPy 1.26.4, pandas 2.2.3, pytest 8.3.5 (CPU only). Compilerless Cython caching cannot be transferred across incompatible Python ABIs or runtime paths. No full-system performance benchmark is asserted.

## 5. H / T / D / C / U

**H — falsifiable:** Relative to an unchanged R2e parent at the same independently seeded training conditions, R2f improves mean R2e *held-out* evaluation utility by at least +0.05 per game (dimensionless engineering threshold), without win/draw/loss regressions or lower rates of real damage/contact. The value +0.05 is a declared exploratory decision threshold, not an empirically calibrated minimum important effect.

**T — minimum experiment:** Hold MaleCNS data/hash, Shiu dynamics, game, sensors/readout, learning rate, clip bounds, decision interval, initial Gen49 checkpoint, compute budget and training-opponent schedule fixed. Run the four 2x2 factor arms with **at least three independent training seeds each** and at least two unused evaluation seed pairs each for ZEN/LUD/NEZ, matched across arms (minimum 12 training games and 72 evaluation games). Predeclare all seeds; do not recycle the fixed training-publication or PR #87 selection seeds as fresh holdouts. If the pilot suggests benefit, use at least 10 independent training seeds per arm for a preregistered confirmatory study. Measure R2e utility, win/loss/draw, HP differential, contact and damage rates, time to first hit, action entropy/concentration, synaptic bound saturation, and training/validation separation. Stop as UNCERTAIN if the defined budget expires without adequate independent observations.

**D — PASS / FAIL / UNCERTAIN:** Software PASS covers only reward identity, arithmetic, invariants and checkpoint integrity. Exploratory behavioral PASS requires mean paired held-out R2e utility improvement >= +0.05, strict improvement in at least 2/3 of matched cases, zero outcome-class regressions, and no drop in real-contact rate. Confirmatory PASS further requires the lower bound of a preregistered 95% interval, clustered by **independent training seed**, to exceed +0.05. Otherwise FAIL if evidence supports harm/nonachievement, or UNCERTAIN if statistical precision is insufficient. Games from one learned policy are **not** independent training replicates.

**C — competing explanations:** Lower terminal gain may remove beneficial winning credit; neutral draw may eliminate a useful negative update; the two interventions may interact; bounded depression-only plasticity is irreversible without a separate recovery mechanism; a 60-frame control interval, inadequate action routing or opponent weakness could dominate reward tweaks; and frozen selection seeds may cause overfitting.

**U — uncertainty:** Training seed, opponent/seed distribution, neural Poisson randomness, graph annotation and channel partition, nonlinear multiplier clipping, float32 storage vs float64 updates, Python/Cython/NumPy ABI, simulation-clock and scheduler differences, and provenance mismatches. The single frozen source trace does not estimate a combined standard uncertainty \(u_c\) for treatment efficacy, so **\(u_c\): not estimated; \(k\): not assigned**.

## 6. Cross-disciplinary evidence and self-check

Computational neuroscience: the project-defined reward→KC-MBON sign map is not an experimentally established biological FightingICE reward mechanism. Primary references: Shiu et al., *Nature* (2024), DOI [10.1038/s41586-024-07763-9](https://doi.org/10.1038/s41586-024-07763-9); Aso et al., *eLife* (2014), DOI [10.7554/eLife.04580](https://doi.org/10.7554/eLife.04580).

Reinforcement learning/control: a partially observed recurrent neural controller using sign-dependent synaptic depression does not inherit an unconditional policy-invariance guarantee from potential-based reward-shaping theory. Reference: Ng, Harada and Russell (1999), *Policy invariance under reward transformations*.

Statistics/causal design: matched seed blocks, factorial ablation, independent training replicas and holdout independence are necessary to attribute a change to an intervention.

Reproducible systems: pin every source/graph hash, runtime ABI, candidate state and exact code commit, reject truncated games and record CI/test boundaries.

**ERROR CHECK:** The existing R2e reward function, training workflow, public application, approved model and releases remain unchanged. R2f requires explicit routing and explicit source-to-research checkpoint fork. Real-source algebra is -0.025 + 0.015625 - 1 = -1.009375. No claim of combat improvement follows from that equality.


## 7. Main-branch activation and rollback

The **canonical GitHub Actions combat-candidate-training lane** invokes the updater with the pinned R2f learning-credit JSON, and requires the R2f ID and SHA-256 in `update.json`, checkpoint metadata, and all final results. External assessment, public utility, generation counter, training opponent rotation, readout, 60-frame action cadence, and brain model remain unchanged from R2e. Source Gen49 weights are inherited byte-for-byte until a full, trainable 3,600-frame match is evaluated and the plasticity updater runs.

A candidate is only published when the old R2e fixed ZEN/LUD/NEZ acceptance gate improves; otherwise the candidate state is discarded and the same parent Gen49 is retried. A published R2f-updated candidate can be resumed only when its versioned learning-credit file SHA matches exactly. This is **production candidate-training** but **not enabled learning inside Vercel LIVE**, and does not automatically serve or approve a newly trained policy.

To roll back the training semantics, revert the integration commit on main and retain the source checkpoint and per-run immutable provenance. If an R2f-updated generation was already accepted, do **not** relabel those weights as R2e-trained: explicitly fork or restore the earlier accepted R2e checkpoint before changing the active credit. Preserve R2f run artifacts and their immutable SHA receipts for audit.

The project never treats a green GitHub Actions job as evidence that the model became a stronger fighter; `accepted_update` and the fixed paired evaluation must be inspected separately.
