# Persistent paired candidate training

## Scope

This change extends the real-game pilot merged in PR #65. It does not replace
P1 with a conventional learned network or a scripted fighting controller.
The neutral dummy is an explicitly separate curriculum opponent. Existing
approved inference, the old R2e release, FlyBody and unrelated applications are
not modified. New site content remains English.

The recurring workflow replaces `.github/workflows/continuous-training.yml`.
It is not a second candidate-learning writer. The old R2e Python implementation
is retained as a historical comparator; it is not invoked by the new schedule.
The original artifact-only paired pilot remains available without a schedule.

## Explicit reward and execution contract

| Parameter | Value | Unit / type / interpretation |
|---|---|---|
| Combat terminal outcome | win +1, draw 0, loss -1 | dimensionless scalar |
| Combat HP coefficient | 0.02 | dimensionless scalar; HP advantage normalized by 400 game HP |
| Curriculum approach weight | 0.1 | dimensionless scalar; best recorded distance reduction relative to start |
| Curriculum first effective hit | 0.4 | dimensionless scalar, once per trial |
| Curriculum damage weight | 0.5 | dimensionless scalar; actual dealt damage normalized by 400 game HP |
| Action-button bonus | none | no payment for commands without outcomes |
| Maximum HP | 400 per side | game units, not a physiological SI quantity |
| Decision interval | 60 game frames | integer count, unchanged from pilot |
| Neural window | 0.020 seconds | simulated neural time per decision, unchanged |
| Search groups | 8 | integer; fixed artificial partition of existing KC–MBON edges |
| Antithetic directions per cycle | 4 | integer; eight real probe games |
| Search standard deviation | 0.04 | dimensionless optimizer-coordinate scalar |
| Proposal step norm cap | 0.02 | dimensionless optimizer-coordinate norm |
| Multiplier bounds | 0.8 to 1.0 | dimensionless; recovery allowed, sign/topology preserved |
| Wake-up request | every 300 seconds | wall-clock request, not guaranteed completion |
| Per-experiment timeout | 1800 seconds | wall clock; failure does not update the pointer |
| Training job limit | 35 minutes | includes setup, game execution, packaging and upload |
| Short-lived CI evidence | 3 days | artifacts; run-addressed release evidence persists |

HP and horizontal distances are divided by quantities in the same game units.
The two scores and optimizer coordinates are dimensionless. No physiological
calibration, identified endogenous reward pathway or improvement guarantee is
implied. This uses the previously approved analytical reward, not the abandoned
COMBAT-v1 coefficient proposal or the old R2e sign-to-channel update.

## Persistence and information

Every completed cycle advances a separate experiment cursor. Fresh direction,
training, proposal-selection and validation seeds derive from that cursor,
including cycles with zero accepted updates. A no-change cycle preserves the
effective weight hash and model generation. Accepted updates advance generation
once; archive hashes and weight identities are separately labeled.

The first cycle explicitly seeds from the verified R2e candidate. Later cycles
resume the exact checkpoint referenced by the last coherent published record.
Missing/corrupt paired state cannot silently reset learning or fall back to R2e.
Membership, bounds, protocol, effective-weight and file digests are checked.
Changes to anatomy, reference model, interface, game, worker, observation encoder,
action contract or session code require an explicit new lineage.

Both signs use the same condition within a pair. A nonzero proposal is selected
on another seed, not the probe seed. Curriculum selection also rejects reduced
actual damage. Two additional validation seeds are recorded after an accepted
proposal. They do not imply strong-play validation or production promotion.

The initial phase is the neutral-dummy curriculum. Three consecutive accepted
cycles must each deal at least 40 HP on both validation seeds before the next
cycle switches to the combat objective. This is a versioned exploratory
curriculum transition, not a claim of generalization. Combat continues to use a
frozen canonical ZEN opponent; a diverse held-out league is still required for a
strength claim. No-change cycles remain valid evidence, not learning success.

The unchanged complete-round checks and official video rendering are retained.
Cycles use 12 real games without a proposal, up to 18 with selection/validation.
A faster wake-up does not make neural decisions faster or force useful updates.
Requests are single-writer and do not cancel an in-flight cycle. Pending requests
can be superseded by GitHub; missed slots are not replayed as extra learning.

## Publication and public view

The main-only publication job verifies saved raw scores, the paired gradient,
seed assignments, checkpoint identities, both frozen evaluations and media
hashes. It publishes run-and-attempt-addressed release assets without clobbering
existing bytes. Only after verification does it advance
`site/data/paired-latest.json` using a normal Git push. Fresh worktrees and three
bounded attempts preserve unrelated main updates. A newer candidate or changed
parent is never overwritten.

The single JSON envelope includes both evaluations, current training metadata,
a bounded recent-cycle history and the exact next resume asset. It prevents
mixing separately fetched 'latest' documents. `/api/evaluation` prefers this
coherent result; genuine absence before first publication may expose historical
R2e records, but malformed data, 403, 5xx and timeouts are not treated as absence.
The `/training` console separates cycles, accepted updates, curriculum/competition
and before/after recorded results. Viewer pause is not a training stop. The root
viewer gets an explicit training-console link and no-update notice.

Set `CONNECTOME_TRAINING_PAUSED=true` as a repository variable to prevent new
training/publication jobs from entering. This does not kill an already running
computation. Disable the workflow to stop wake-up requests as well. No billing
plan is changed by this rollout.

## Acceptance boundary

Before merge, require reward/lineage/publication tests, English and Web checks,
actual Next.js build and the actual persistent paired cycle in PR CI. PR runs
cannot publish. After merge separately verify main publication, at least one
subsequent resume, the exact Vercel frontend commit and the public result.

The local bundle evidence covers software and local Git races only. It does not
establish that this recurring integration has run a real game or been deployed.
The prior PR #65 pilot is a separate historical result: twelve real games,
zero paired score differences, no accepted update and no demonstrated strength.

Official operational reference:
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
