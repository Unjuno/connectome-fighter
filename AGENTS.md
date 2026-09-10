# Implementation rules

1. Never silently replace missing biological data with a synthetic graph.
2. Never report mock tests or synthetic fixtures as live-game or biological results.
3. Keep the game observation contract fixed within a confirmatory experiment.
4. Do not expose non-delay FightingICE state to the policy when evaluating the delayed-observation condition.
5. Freeze both policies during an individual round; apply learning updates between collection batches.
6. Record policy version, graph fingerprint, seeds, dependency versions, and experiment configuration with every run.
7. Treat incomplete/disconnected rounds as truncated and non-trainable in the terminal-only baseline.
8. Compare biological topology against matched nulls before attributing an effect to connectome structure.
9. Preserve third-party licenses and dataset terms; do not vendor external game/data assets without explicit permission.
10. A passing test proves only the contract exercised by that test.
