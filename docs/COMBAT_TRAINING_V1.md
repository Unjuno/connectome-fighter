# Combat learning experiment v1

## Objective and evidence boundary

The user-facing target is decisive, visibly effective fighting-game play. Success means higher win rate and better damage trades against fixed and held-out opponents, not more button presses, more generations, or more changed synapses. This initial experiment does not establish strong play.

The canonical policy remains MaleCNS connectivity plus pinned Shiu LIF. The KC-to-MBON update is the existing depression-only, bounded-magnitude rule. No learned MLP/PPO controller replaces the neural substrate. Its ability to acquire fighting skill is an empirical question, not guaranteed by the reward specification.

## Experimental reward: R2e-combat-v1

| Component | Starting coefficient and scope |
|---|---|
| Victory / defeat | +2 / -2 at a completed terminal state |
| Damage differential | (damage dealt minus damage taken), normalized by 400 HP |
| Damage-exchanging draw | -0.05 at terminal |
| No-damage draw | -0.25 at terminal |
| Fast winning KO | At most +0.25, proportional to the unused fraction of the 3600-frame limit; no bonus for losing, simultaneous KO, or timeout wins |
| Engagement potential | Weight 0.05; existing 180-pixel engineering band and 960-pixel scale; discount one; potential zero at all terminal states |

All rewards are dimensionless engineering utility. HP and stage pixels are game quantities, not physiological SI measurements. The distance band is not a measured attack range. These coefficients are a versioned exploratory starting point, not empirically optimal values.

Negative overkill HP is clamped at zero for damage accounting. No direct attack-button, movement, action-diversity or survival reward is provided. Incomplete, truncated, non-trainable, nonfinite, regressed, or policy-changing traces fail closed. Infrastructure failure is not a losing game.

For equal initial state, terminal-corrected potential differences telescope to the same shaping total regardless of the path. Therefore proximity loops cannot increase that total. This does not imply invariance or convergence of this sign-dependent KC/MBON plasticity rule. The no-damage draw penalty deliberately changes the objective and is not zero-sum.

## Three different clocks

| Clock | Configuration |
|---|---|
| CI wake-up request | Every ten minutes, at minutes 3/13/23/33/43/53 UTC |
| Neural action decision | Every 60 FightingICE frames, unchanged in this first reward experiment |
| Weight update | Once after one completed 3600-frame-maximum training round, outside gameplay |

The GitHub schedule is best effort: jobs may be delayed or dropped. The single-writer concurrency group never cancels a running update. A pending request may be superseded. The system resumes the latest verified checkpoint rather than replaying missed time slots. No guaranteed ten-minute completion or spending increase is claimed.

Set repository variable `CONNECTOME_TRAINING_PAUSED=true` or disable the workflow to stop further scheduled training/publication. This does not cancel an already running read-only computation. No billing changes are made. Logs/artifacts have three-day retention; published candidate/video assets persist for audit.

## Cycle and publication

1. Pin GitHub release asset IDs, byte digests and sizes for runtime and source checkpoint.
2. On first use, explicitly fork R2d-v0 into R2e without changing inherited weights or the old release. Preserve parent metadata and config identity. Subsequent runs resume `combat-training-v1`.
3. Evaluate the unmodified candidate against ZEN with fixed seeds 800101/20202 and record actual ScreenData.
4. Collect one full training round against a baseline ZEN/LUD/NEZ rotation. Derive fresh training seeds from the inherited generation, separate from fixed evaluation seeds.
5. Apply audited R2e signals to existing eligible KC-to-MBON edges. Preserve topology, sign, learning rate 0.01, eligibility decay 0.9, and multiplier bounds 0.8–1.0.
6. Materialize the updated state and repeat the same frozen evaluation. Neither evaluation updates weights.
7. Main-branch publication, in a separate write-authorized job, exposes the new candidate and both actual videos. PR jobs never publish. Video URLs are run-addressed and existing bytes cannot be replaced. Update the three public status records and append-only history together.

The trainer workflow is now named `combat-candidate-training`. Legacy `canonical-continuous-training` workflow-run consumers are not triggered; this cycle owns its evaluations and history, avoiding competing automatic publishers. Old manual R2d evaluation workflows remain historical tools, not the new automatic lane.

## Assessment before claiming improvement

A before/after result on one reused seed is a local regression indicator, not held-out generalization. The next assessment must include independent seeds, baseline and archived opponents, role/character effects, win rate, damage differential, KO completion time conditional on winning, no-damage draws, and uncertainty intervals. A large terminal reward does not prove effective credit assignment. If contact remains rare, test action-decision interval and fixed sensor/motor routing as separate interventions rather than silently changing several variables together.

**H:** R2e-trained candidates improve held-out combat metrics relative to their inherited R2d checkpoint under matched evaluation conditions.

**T:** Keep this small repeated-run lane exploratory. Before a strength claim, preregister opponent/seed sets and a practical improvement threshold, use paired conditions and independent training replicas, and bound the total compute budget.

**D:** Passing software, complete-round, checkpoint and video audits permits publishing research evidence only. Strength remains UNCERTAIN until the preregistered performance criterion is met.

**C:** Reward sparsity, 60-frame control latency, an uninformative output mapping, sign-specific credit assignment, depression saturation, or overfitting a fixed opponent can prevent improvement.

**U:** Keep biological/model uncertainty, training-seed variance, opponent effects, scheduler delay and numerical/runtime variation separate. No fabricated measurement uncertainty is assigned before repeated measurements exist.

## Primary references and implementation documentation

- Ng, Harada and Russell (1999), *Policy invariance under reward transformations: theory and application to reward shaping*. Author publication page: https://wordpress.andrewng.org/index.php/publication/policy-invariance-under-reward-transformations-theory-and-application-to-reward-shaping/
- Aso et al. (2014), eLife, DOI 10.7554/eLife.04580. MBON valence evidence does not identify a FightingICE reinforcement pathway.
- Shiu et al. (2024), Nature, DOI 10.1038/s41586-024-07763-9. Applying the neural model to this game and MaleCNS is a project extension.
- GitHub workflow syntax: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub scheduled-workflow limitations: https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
