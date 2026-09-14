# Canonical Neural Substrate Contract

English-only compatibility path. This preserves the substrate contract; the current exploratory training schedule is documented in [COLOSSEUM.md](COLOSSEUM.md).

## Purpose

Define what Connectome Fighter treats as its fly neural substrate. The canonical control path must not substitute a generic RNN/MLP or a custom sigmoid recurrent network for the fly substrate.

## 1. Anatomical substrate

Canonical anatomy is **MaleCNS v1.0**, dataset `male-cns:v1.0`. The original source record identifies FlyEM/HHMI Janelia, University of Cambridge, MRC LMB, and Google Research; Berg et al., *Cell* (2026), DOI `10.1016/j.cell.2026.08.015`; official landing page `https://male-cns.janelia.org/`; bulk root `gs://flyem-male-cns/v1.0/`; CC-BY license.

MaleCNS spans the male Drosophila brain, optic lobes, and ventral nerve cord. The source paper reports 166,691 neurons. That literature count is distinct from the project's filtered runtime count.

The canonical import initially uses:

- `body-annotations-male-cns-v1.0-minconf-0.5.feather`
- `body-neurotransmitters-male-cns-v1.0.feather`
- `connectome-weights-male-cns-v1.0-minconf-0.5.feather`

Add synapse-level partner/location tables only when necessary; do not routinely load the 6.8–12.7 GB tables from the outset.

### Neuron candidate selection

Not every annotation row is a neuron. The initial candidate rule follows `supplemental_data/quantify-neuron-connections.ipynb` in the paper repository: superclass must be present and must not contain `tbc`. Recompute this for v1.0 and record differences from the paper count in the manifest rather than silently correcting them.

## 2. Connectivity is not executable neural dynamics

MaleCNS provides reconstructed wiring, connection strengths, cell annotations, and transmitter predictions. It is not itself a simulator that evolves membrane potentials. Distinguish biological structure, published neural dynamics, and the project-defined game interface.

## 3. Neural dynamics

The initial canonical dynamics use Shiu et al., *Nature* 634, 210–219 (2024), DOI `10.1038/s41586-024-07763-9`. Reference code is `https://github.com/philshiu/Drosophila_brain_model`, with `model.py` pinned at `2a83ad611cd9768f8c9723fc613ed27761a5feb5`, using Brian2.

The Shiu model was evaluated on the female FlyWire brain. Applying it to MaleCNS is a **project port**, not an official physiological model released for MaleCNS. Initially preserve the reference equations, threshold, refractory periods, delays, and weight conventions while supplying MaleCNS connectivity and transmitter identities.

The reference convention treats GABA/glutamate as inhibitory and acetylcholine/dopamine/octopamine/serotonin as excitatory. The MaleCNS adapter additionally treats histamine as inhibitory, explicitly versioning and hashing this extension rather than silently folding it into a reference category. This is an adapter assumption, motivated by histamine-gated chloride-channel inhibition in the fly visual system, not an unchanged Shiu reference rule.

Do not silently assign signs to unclear or missing `consensus_nt`. Measure coverage first and document exclusion, fallback, or sensitivity-analysis decisions.

## 4. Artificial-neural-network boundary

Do not insert an MLP, GRU/LSTM/RNN, custom sigmoid core, GNN presented as the brain, or trainable latent encoder that replaces neural activity into the canonical path. Tensor libraries may be computational tools; a trainable artificial network must not replace the fly substrate.

## 5. Separate individuals

GARNET, ZEN, LUD, and NEZ may share immutable anatomy, but not membrane/synaptic state, RNG state, episode history, plasticity state, or character-specific checkpoints. Sharing anatomy is a memory optimization, not shared simulation state.

## 6. Game interface

Game-feature-to-sensory and neural-output-to-action mappings are artificial, versioned interfaces. Log feature/body mapping, stimulation rates or currents, selected types/superclasses/modalities, output IDs, aggregation rules, selected actions, and each output group's contribution. Any learned interface remains distinct from the substrate. Initial canonical checks prefer a fixed mapping.

## 7. Post-hoc logs

Each decision window records character/lineage/checkpoint, game frame/observation/action, stimulated IDs and drive, spike IDs/times/counts, membrane summary, available type/class/side/neuromere annotations, transmitter identity/confidence, motor/descending contribution, dataset hash, dynamics/parameter identity, and interface version.

Do not duplicate static annotations for every run. Pin a metadata table and join by body ID. Separate `decisions.jsonl` from event-compressed `spikes.parquet`, allowing later connectivity joins, recruitment analysis, pathway/hub analysis, and sensory-to-motor analysis. Full all-neuron membrane traces are expensive; retain event-compressed spikes and state summaries by default, and full traces only for selected matches.

## 8. Legacy paths

The older FlyWire/Shiu v783 continuous trainer, `brain.py` sigmoid core, PPO readout checkpoints, and `training-state` release are engineering history, not canonical MaleCNS learning generations.

## 9. Original acceptance gates

Record official input URLs, sizes, and hashes; uniquely validate ID/weight/transmitter joins; record release-specific candidates and NT coverage without silent sign assignment; match small-circuit golden tests to pinned reference equations; complete an actual FightingICE round through MaleCNS/LIF spikes; expose real body IDs with activity logs; and establish independent character simulation state. Historical scheduled learning was deferred until those checks passed. Current functional CI and exploratory scheduling are tracked separately in the roadmap.
