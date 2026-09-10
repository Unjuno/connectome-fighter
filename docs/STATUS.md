# Status

## Demonstrated

### M1 — live FightingICE bridge

- FightingICE v7.1 release ZIP and resource ZIP downloaded in GitHub Actions and verified by SHA-256.
- Java 21 + pyftg 2.3 headless connection completed one real ZEN-vs-ZEN round.
- Smoke condition: `--headless-mode --pyftg-mode --input-sync`, one 600-frame round.
- P1 and P2 each recorded 147 decisions.
- Final HP was `[390, 390]`; outcome reward was `[0, 0]`.
- Two-sided trace audit returned `VALID_LOG_CONTRACT`.
- Evidence: Actions run `34535409876`, commit `0307f46aba0d61e5405250d5403a25e92a9fddd7`, artifact `10175223790`.
- This proves only the game/Python/trace bridge. No connectome or learning was used.

## Implemented

- Project packaging and MIT license boundary.
- FightingICE 7.1 / pyftg 2.3 target metadata.
- Dimensionless 18-value observation contract and 8-action interface.
- Terminal-only zero-sum outcome reward.
- Append-only two-player traces and strict pair audit.
- Auditable graph loader with provenance/checksum requirements.
- Signed-degree-preserving rewiring null generator.
- Sparse graph-constrained recurrent engineering model.
- Random baseline and live pyftg adapter.
- Shiu/FlyWire table normalization script; real data conversion not yet executed.
- Offline synthetic graph/gradient smoke.
- Core CI and static GitHub Pages source.

## Not yet demonstrated

- Successful normalization/import of an actual Drosophila connectome file into this repository's graph format.
- A live FightingICE match controlled by a Drosophila-derived graph.
- PPO or another reinforcement-learning training loop.
- Self-play improvement.
- A performance advantage of biological topology over matched controls.

These states must remain explicit in reports and the dashboard.
