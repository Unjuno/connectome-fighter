# Roadmap

## M1 — live game control
Run RandomPolicy vs RandomPolicy in FightingICE 7.1 headlessly, record both traces, and pass `audit_pair` without using any connectome.

## M2 — verified biological graph import
Convert one canonical Drosophila connectome release into `nodes.csv`, `edges.csv`, and `manifest.json`. Fail closed on missing provenance/checksums.

## M3 — fixed-connectome learning
Keep graph topology/internal weights fixed and train only the game readout. Establish that the collection/learning pipeline works before attributing anything to topology.

## M4 — matched A/B topology test
Compare the verified graph against sign/degree-preserving rewired controls under identical observation/action/reward/training conditions.

## M5 — internal plasticity
Keep topology/sign constraints fixed while making existing edge magnitudes trainable. Treat this as a separate experiment from M3/M4.

## M6 — self-play population and held-out evaluation
Train against a population/history of opponents and evaluate on held-out opponents so current self-play win rate is not the sole progress metric.

## M7 — confirmatory runs
Freeze protocol, code commit, data hashes, seeds, evaluation set, and stopping rules. Report uncertainty and all prespecified comparisons.
