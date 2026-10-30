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
| Training-cycle request | On completion, a single main-branch successor is requested **not earlier than 30 minutes after this workflow started**, using the GitHub-authoritative `run_started_at`; optional operator `workflow_dispatch` |
| Scheduler behavior | Hourly `17 * * * *` UTC cron is a best-effort **recovery watchdog**. The self-chain checks queued/in-progress siblings and does not start a duplicate run |
| Neural action decision | Every 60 FightingICE frames |
| Weight update | Once after one completed 3600-frame-maximum training round, outside gameplay |

The lane remains single-writer and does not cancel an active learning run. The completed workflow waits only until 1,800 seconds have elapsed since its GitHub server-side start timestamp; it then requests **one** next main-branch workflow if no active or queued sibling exists. This is a *minimum request interval*, not an exact new job start guarantee; runner allocation, cancelled jobs, failed publication and delayed GitHub dispatch can increase the actual interval. The hourly cron watchdog recovers a broken chain on a best-effort basis; it is not an independent 30-minute scheduler. The loop resumes after a clean accepted/rejected update or an infrastructure failure in training, but not after intentional cancellation or a publication failure. A main-branch workflow-file push seeds the new loop after deployment. Explicit manual `workflow_dispatch` remains possible. PRs do not run real training or publish.

Set repository variable `CONNECTOME_TRAINING_PAUSED=true` or disable the workflow to stop future training/publication (the cron job may still enter its inexpensive contract-test stage). This does not cancel an already running training job. No billing changes are made. Logs/artifacts have three-day retention; published candidate/video assets persist for audit.

## Cycle and publication

1. Pin GitHub release asset IDs, byte digests and sizes for runtime and source checkpoint.
2. On first use, explicitly fork R2d-v0 into R2e without changing inherited weights or the old release. Preserve parent metadata and config identity. Subsequent runs resume `combat-training-v1`.
3. Evaluate the unmodified candidate against the legacy ZEN comparability anchor at seeds 800101/20202 and record actual ScreenData. This anchor remains useful for the public replay but is no longer the candidate-selection gate.
4. Evaluate the unmodified candidate on the fixed validation suite: ZEN 810101/31001, LUD 810202/31002, and NEZ 810303/31003. These seeds are separate from the rotating training seeds and from the legacy replay anchor.
5. Collect one full training round against the baseline ZEN/LUD/NEZ rotation. Derive fresh training seeds from the inherited generation and GitHub run ID.
6. Apply audited **R2f learning credit** to existing eligible KC-to-MBON edges while **keeping the R2e external evaluation**. Preserve topology, sign, base plasticity learning rate 0.01, eligibility decay 0.9, decision interval 60, and multiplier bounds 0.8–1.0.
7. Materialize the updated state and repeat the same three validation cases plus the legacy ZEN comparability anchor. None of these evaluations updates weights. When the full KC-MBON proposal is rejected, construct **one** hash-checked, fixed-size backtracked proposal with 25% of the full per-edge change, and test that separate actual MaleCNS checkpoint on the same three opponents under frozen R2e scoring. This is proposal-size backtracking, not another reward or action-label intervention.
8. Compute R2e terminal-plus-net-damage utility for every validation pair, including the optional backtracked proposal. Publication requires all of the following **without relaxation**: positive mean paired utility change, strict improvement on at least two of the three opponents, and no regression in win/draw/loss outcome class on any opponent. If the full proposal fails and the fixed 0.25 proposal also fails, discard both and retain the accepted parent. The legacy 800101/20202 ZEN replay is excluded from this acceptance decision.
9. Main-branch publication, in a separate write-authorized job, exposes only an accepted candidate and the two legacy-anchor videos. PR jobs never publish. Video URLs are run-addressed and existing bytes cannot be replaced. The training status also records the three-opponent before/after validation evidence.
10. After an accepted publication or a clean rejection, request one next training attempt after the start-anchored half-hour hold and a sibling check. The hourly watchdog can also initiate a recovery run. Rejected generations do not advance the checkpoint; the next attempt uses a deterministic run-ID seed salt so it does not repeat the same training trace.

The trainer workflow is now named `combat-candidate-training`. Legacy `canonical-continuous-training` workflow-run consumers are not triggered; this cycle owns its evaluations and history, avoiding competing automatic publishers. Old manual R2d evaluation workflows remain historical tools, not the new automatic lane.

## Operational caveats and scientific identity

- The self-chain normally occupies a runner during the remaining part of its 30-minute hold (approximately 15–20 minutes for a 10–15-minute training job). This consumes additional GitHub Actions compute minutes. Runs may still be late; the design does not provide a hard real-time SLA.
- The backtracking treatment is fixed and versioned as `r2f-trust-region-backtrack-v1`, `proposal_step_scale=0.25`. The original full proposal is evaluated first. Both full and reduced weight proposals and their R2e gates are logged, and any reduced accepted checkpoint records its precise source hashes, multiplier step scale, and R2f credit bytes. No synapse is added, potentiated or redirected to another channel.
- Examining two step sizes on the same three fixed validation opponents is a **multiple-testing risk**; acceptance is provisional research evidence, not independent strength validation or approved LIVE inference. Independent holdout opponents/seeds and a controlled R2e/R2f comparison are still required before claiming improvement.
- If the backtracking proposal triggers a validation/runtime error, the main run fails closed and does not publish. The next isolated run may retry via the self-chain after a training failure; a failed publication is **not** automatically retried by the chain.
- The same `combat-training-v1` release checkpoint is used only after passing the unchanged R2e gate. Vercel LIVE remains `learning_enabled=false` with no auto-promotion.

## Assessment before claiming improvement

The three-opponent before/after gate reduces selection pressure toward one fixed ZEN seed, but it remains a small deterministic validation suite and therefore is not held-out generalization evidence. The next assessment must use an independent seed set that never participates in publication decisions, plus baseline and archived opponents, role/character effects, win rate, damage differential, KO completion time conditional on winning, no-damage draws, and uncertainty intervals. A large terminal reward does not prove effective credit assignment. If contact remains rare, test action-decision interval and fixed sensor/motor routing as separate interventions rather than silently changing several variables together.

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
