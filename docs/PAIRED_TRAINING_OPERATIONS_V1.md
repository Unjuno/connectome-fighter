# Persistent paired neural training v1

## Adopted scope

This rollout builds on the merged, actually executed PR #65 pilot, rather than
applying the older attached alternative on top of it. P1 remains MaleCNS/Shiu
LIF. The single active recurring learning lane becomes `paired-neural-training`.
The old R2e workflow is retained for explicitly enabled manual historical runs;
its schedule and automatic push starts are removed. Old R2e releases, artifacts,
weights and the approved production inference release are not overwritten.

The public `/training` page reports the current experiment. The root page links
to it and retains the old evaluation archive. `/live` remains independent.
English is used throughout project-owned additions.

## Reward and optimizer contract

The exact, versioned values are in `configs/paired_training_v1.json`, checked
against executable constants. The already-audited `paired_search.score_round`
implements both scores without changing P1 observations.

Combat: victory +1, draw 0, defeat -1, plus normalized final HP advantage with
weight 0.02. Both fighters start at 400 HP. Overkill is clamped; incomplete,
healing, nonfinite and changing-policy traces fail closed. There is no attack-key
bonus, activity bonus, extra no-contact penalty, or fast-loss reward.

Practice: 0.1 approach progress, 0.4 for actual damage, 0.5 normalized damage.
The opponent is explicitly neutral. Distance progress is the reduction of the
minimum *observed delayed-frame* distance, not repeated movement rewards.
Practice success does not establish fighting strength.

The equations, variable meanings, dimensionless units and interpretation of the
Gaussian-smoothed objective remain documented in PAIRED_NEURAL_SEARCH_V1.md.
No existing biological hypothesis is silently relabeled: recovery of existing
KC-MBON magnitudes is allowed within 0.8..1.0. This is a project optimizer.

## Cycle and persistence

Each cycle requests two Gaussian antithetic pairs instead of the pilot's four,
to reduce the work per published cycle. The grouping remains eight deterministic
artificial groups, sigma 0.04, learning rate 0.05, proposed step norm at most 0.02.
Action decisions remain every 60 game frames, with 20 ms neural simulation per
decision. Neither clock is silently changed to make training look faster.

1. Pin runtime/seed release asset IDs, digests and sizes; restore the isolated
   paired state when present. Missing/corrupt successors never silently reset.
2. Start from the persisted coordinates over the original inherited multipliers.
3. Repeat the parent under the same practice seed and require identical metrics.
4. Run two plus/minus pairs using a fresh seed block and fresh directions for this
   completed cycle. Cycles advance even when no weights change; updates do not.
5. Equal paired scores imply zero step and exact parent retention. A nonzero
   proposal needs strict practice gain followed by non-regressing results on two
   other seeds, positive mean gain, and no worse dealt/taken damage there.
6. Record frozen parent and selected candidates against canonical ZEN using the
   existing fixed seed. This is a local diagnostic, not held-out strength proof.
7. Persist original arrays, coordinates, grouping, runtime/config identity,
   numerical weight hash, file hash and accepted-update count. A changed file or
   a new cycle alone is not a learned update.

Eight real full rounds when there is no proposal; at most thirteen if a proposal
and two confirmation pairs are needed. Process deadline 1500 seconds; job limit
30 minutes. Runtime and CPU/BLAS conditions, source, videos and raw evidence are
saved. Reference Python 3.10/site310 and bridge Python 3.11/site311 are isolated.

## Schedule, publication and stopping

Requested starts: UTC minutes 7/17/27/37/47/57, every hour. The shared single-writer
concurrency group does not cancel an active cycle. A pending request may be
superseded. GitHub may delay scheduled runs; no ten-minute completion guarantee
is made. Each cycle performs multiple comparisons, not a mandatory weight update.

Only main-branch publication has contents:write. PR computations cannot publish.
The publisher verifies all state/video bytes and the tested run/commit, uploads
immutable `paired-cycle-RUN-ATTEMPT` assets, then replaces one JSON receipt in
`paired-training-latest`. Exact predecessor/counter checks reject stale writers.
No generated JSON is rebased into main and no old R2e public record is overwritten.
The viewer fetches this single consistent receipt and validates its schema and
run-addressed URLs. It shows stale or missing data explicitly. Records are not
LIVE footage; unmatched FlyBody/neural images are not added to these recordings.

Set `CONNECTOME_TRAINING_PAUSED=true` or disable this workflow to stop subsequent
cycles. This does not terminate a round already running. Manual R2e additionally
requires `CONNECTOME_LEGACY_R2E_ENABLED=true`. Do not run that historical lane
concurrently as a strength comparator without fixing its protocol first.

Raw CI artifacts retain three days. Run-addressed public videos and state receipts
persist; the UI lists at most 30 recent cycles and links full immutable reports.
No billing plan, unrelated app or approved inference is changed. Repeated
zero-signal results are a reason to review control/routing, not proof of progress.

## Acceptance

Software tests cover persistence, zero-update semantics, rejection and schedule
isolation. Browser tests use visibly labeled engineering videos only. Real-game
CI, main-only publication, subsequent resume and Vercel frontend serving are
separate gates. Record each observed result; do not infer strength from green CI.
