# Attempt-based combat curriculum v1

## Failure addressed

The previous trainer selected ZEN/LUD/NEZ from the accepted candidate generation.
A rejected proposal retains that generation, so every retry selected the same
opponent. At generation 40 this meant LUD-only retries despite the documented
rotation. Changing training seeds did not change the opponent.

## Versioned correction

`workflow-attempt-round-robin-v1` selects the training opponent from the positive
`GITHUB_RUN_NUMBER`, independently of accepted generation or prior game outcome.
Consecutive workflow numbers cycle through ZEN, LUD, and NEZ. Rerunning a workflow
retains its opponent. Missing or invalid identity fails before runtime loading.
Cancelled, skipped, scheduled, and PR runs can leave gaps in completed main runs;
this protocol does not claim perfectly balanced completed-game counts.

This changes only the proposal-generating opponent curriculum. R2e-combat-v1,
EMA-residual, 60-frame action cadence, the 20-ms neural window, learning rate 0.01,
eligibility decay 0.9, depression-only bounds, and the three-opponent validation
gate remain unchanged. Existing run-ID/generation training seed arithmetic is
preserved. No evaluation trace is used as a plasticity training trace.

## Evidence on every completed attempt

The environment and accepted candidate manifest record `training_curriculum`.
The final result JSON and console output also retain curriculum, `signal_summary`
and `update_summary`, including rejected proposals. This makes saturation and
step-size diagnostics inspectable in Actions logs, rather than only in an
expiring artifact. A failure without update evidence does not invent diagnostics.
Failures remain failures; rejected candidates do not advance published weights.

## Verification and interpretation

Software tests cover rotation with unchanged generation, deterministic retries,
invalid identity, seed-arithmetic preservation, and execution of the trainer's
actual finalization block for accepted, rejected, and failed software fixtures.
These fixtures are not biological traces or evidence of fighting strength.

**H:** Attempt-based selection eliminates generation-locked opponent choice.
**T:** Exercise consecutive run numbers without changing generation; inspect real
main-run curriculum records and validation before/after metrics.
**D:** The software contract passes when all three opponents are selected over
three consecutive workflow numbers and every available diagnostic is preserved.
Combat-strength improvement remains UNCERTAIN pending independent evaluation.
**C:** Queue gaps can skew completed-game balance; incorrect credit assignment,
large steps, or fixed-suite selection overfitting can still prevent improvement.
**U:** This fix does not estimate training-seed or opponent variance and does not
justify a learning-rate or reward-coefficient change by itself.

Reference: GitHub Actions variables reference, `GITHUB_RUN_NUMBER`.
https://docs.github.com/en/actions/reference/workflows-and-actions/variables
