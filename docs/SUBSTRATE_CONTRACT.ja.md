# Canonical Neural Substrate Contract

> English translation retained at the original compatibility path. Dataset descriptions below preserve the source contract; this translation is not a new biological validation.

## Goal

Define what Connectome Fighter treats as its fly neural substrate. **A generic RNN/MLP or custom sigmoid recurrent network must not replace the fly substrate in the canonical control path.**

## 1. Anatomical substrate

Canonical anatomy is **MaleCNS v1.0**.

- Dataset: `male-cns:v1.0`.
- Project: FlyEM / HHMI Janelia, University of Cambridge, MRC LMB, and Google Research.
- Paper recorded by the contract: Berg et al., *Cell* (2026), DOI `10.1016/j.cell.2026.08.015`.
- Official landing page: `https://male-cns.janelia.org/`.
- Bulk data: `gs://flyem-male-cns/v1.0/`; license: CC-BY.

The dataset covers the male Drosophila central nervous system continuously across brain, optic lobes, and ventral nerve cord. The source contract records the paper's count as 166,691 neurons.

Required primary import files are `body-annotations-male-cns-v1.0-minconf-0.5.feather`, `body-neurotransmitters-male-cns-v1.0.feather`, and `connectome-weights-male-cns-v1.0-minconf-0.5.feather`. Add synapse-level partner/location tables only when required; do not make 6.8–12.7 GB synapse tables a routine dependency from the outset.

### Neuron candidate selection

Do not treat every annotation row as a neuron. Follow the paper repository's `supplemental_data/quantify-neuron-connections.ipynb`: require a defined `superclass` whose name does not contain `tbc`. Recompute this selection for v1.0 and record any discrepancy from the paper in the manifest without silently correcting it.

## 2. Connectivity is not executable brain dynamics

MaleCNS provides reconstructed wiring, synaptic connection strengths, cell annotations, and neurotransmitter predictions. It is not itself an official membrane-dynamics simulator.

Keep three components distinct: unchanged MaleCNS structure, published Drosophila LIF dynamics, and the project's artificial game interface. Do not present the interface as biological fact.

## 3. Neural dynamics

Initial canonical dynamics use Shiu et al.'s 2024 leaky integrate-and-fire model:

- Shiu et al., *Nature* 634, 210–219 (2024), DOI `10.1038/s41586-024-07763-9`.
- Reference: `https://github.com/philshiu/Drosophila_brain_model`.
- Pinned `model.py` commit: `2a83ad611cd9768f8c9723fc613ed27761a5feb5`.
- Reference simulator: Brian2.

The published model was evaluated on the FlyWire female-brain connectome. Applying it to MaleCNS is **this project's port**, not an official Google physiological model.

The initial port preserves the Shiu equations, threshold, refractory period, synaptic delay, and per-synapse weight convention while supplying MaleCNS connection strengths and transmitter identities.

The Shiu convention treats GABA/glutamate as inhibitory and acetylcholine/dopamine/octopamine/serotonin as excitatory. MaleCNS also contains histamine: never silently merge it into another category. The port explicitly versions/hashes `histamine = inhibitory`, motivated in the source contract by inhibitory histamine-gated chloride transmission in the fly visual system. This remains an added adapter assumption, not an unchanged part of the Shiu reference.

For missing or `unclear` `consensus_nt`, do not invent a sign. Measure coverage and explicitly declare exclusion, fallback, or sensitivity-analysis policy in the manifest.

## 4. Artificial-network boundary

The canonical path must not use an MLP, GRU/LSTM/RNN, custom sigmoid core, GNN as the brain itself, or a learned latent encoder that replaces neural activity. Tensor libraries such as PyTorch may be used as numerical tools; they must not conceal an artificial trainable policy replacing the fly substrate.

## 5. Independent character brains

GARNET, ZEN, LUD, and NEZ may share immutable anatomy assets. They must not share membrane/synaptic state, RNG state, episode history, plasticity state, or character checkpoints. Anatomy sharing is a memory optimization; simulation states represent separate individuals.

## 6. Game interface

Mapping FightingICE state into sensory populations and motor/descending activity into game actions is artificial and must be versioned. Record game-feature-to-body routing, stimulation rate/current, selected type/superclass/modality, output body IDs, aggregation rule, chosen action, and every output group's contribution.

Learning an interface does not make it the biological brain itself. Prefer a fixed mapping for the initial canonical gate.

## 7. Analysis-grade logs

Post-hoc analysis of recruited structure is a first-class requirement. Each decision window must retain character/lineage/checkpoint, frame/observation/action, externally stimulated body IDs and drive, spike IDs and times/counts, membrane summary, available type/superclass/class/side/neuromere, transmitter identity/confidence, motor/descending contributions, dataset/graph hash, dynamics version/parameter hash, and interface version.

Pin a hash-addressed static metadata table joinable by body ID instead of duplicating annotations per run. Separate `decisions.jsonl` from event-compressed `spikes.parquet` so connectivity joins can support later recruitment, pathway, hub, and sensor-to-motor analyses. Full membrane traces are large: retain spike events and selected summaries as normal evidence, and full traces only for selected matches.

## 8. Legacy status

The FlyWire/Shiu v783 continuous trainer, `brain.py` sigmoid recurrent core, PPO-readout checkpoints, and `training-state` release are not canonical MaleCNS evidence. Preserve them as implementation/bridge history, not as inherited MaleCNS learning generations.

## 9. Acceptance gate

Before resuming scheduled canonical learning, require:

1. Official MaleCNS imports with recorded URLs, sizes, and hashes.
2. Unique verified joins across body IDs, weights, and transmitter predictions.
3. Release-specific candidate/NT coverage with no implicit unknown-sign completion.
4. Small-circuit LIF golden tests matching the pinned reference.
5. A completed FightingICE round through MaleCNS, LIF spikes, and actions.
6. Replay containing actual MaleCNS body IDs and simulated activity traces.
7. Independent simulation states for all four characters.

The historical contract kept scheduled learning disabled until all seven passed. Current operational status must be read from the current workflow and `STATUS.md`, not inferred from this translation.
