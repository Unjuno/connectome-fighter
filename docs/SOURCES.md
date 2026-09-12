# Sources and upstream resources

Use canonical publications/data releases in experiment manifests rather than this list alone.

## Biological/connectome references

- Shiu PK et al. *A Drosophila computational brain model reveals sensorimotor processing.* Nature (2024). DOI: `10.1038/s41586-024-07763-9`.
- Dorkenwald S et al. *Neuronal wiring diagram of an adult brain.* Nature (2024). DOI: `10.1038/s41586-024-07558-y`.
- Bates AS et al. Brain-and-nerve-cord connectome resource (BANC), Nature (2026). DOI: `10.1038/s41586-026-10735-w`.

## Embodied fruit-fly physics

- TuragaLab/flybody: `https://github.com/TuragaLab/flybody`
- Runtime pin used by the public neural-embodiment side channel: commit `d015e9bfe441bd90ae431bac24c55cb74bdbce26`.
- Vaxenburg R et al. *Whole-body physics simulation of fruit fly locomotion.* Nature **643**, 1312–1320 (2025). DOI: `10.1038/s41586-025-09029-4`.
- Upstream software license inspected at the pinned repository: Apache License 2.0.
- The FlyBody rigid-body geometry, joints, actuators and MuJoCo dynamics are upstream physical-model assets. The mapping from MaleCNS body-ID activity to FlyBody actuator commands in this repository is a separately versioned project-defined experimental interface; it is not asserted to be a native motor-neuron-to-muscle innervation map.

## Game/runtime resources

- FightingICE: `https://github.com/TeamFightingICE/FightingICE`
- pyftg: `https://github.com/TeamFightingICE/pyftg`
- Project release target: FightingICE v7.1, pyftg 2.3; see `configs/game_release.json`.

## Reproducibility rule

Record the exact dataset URL/version, SHA-256, license/terms, preprocessing steps, processed-file hashes, code commit, dependency lock information, seeds, and hardware for every confirmatory run. A citation does not substitute for a data provenance record.
