# Connectome Fighter

A research and engineering testbed for a **persistent Drosophila-connectome-constrained fighter** that resumes from checkpoints, keeps learning through FightingICE matches, evaluates against a checkpoint league, and publishes watchable fights on GitHub Pages.

[Training Arena](https://unjuno.github.io/connectome-fighter/) · [日本語](README.ja.md)

## Primary product loop

```text
latest checkpoint
      ↓
additional FightingICE training
      ↓
new checkpoint
      ↓
evaluate vs champion / archive / fixed baselines
      ↓
export replay + metrics
      ↓
GitHub Pages spectator
      ↓
next job restores checkpoint and continues
```

GitHub-hosted Actions jobs are bounded rather than persistent, so training is split into chunks joined by durable checkpoints. If near-24/7 compute becomes necessary, the trainer can move to a self-hosted runner while Actions remains the scheduler/orchestrator and Pages remains the spectator UI.

See [`docs/CONTINUOUS_TRAINING.ja.md`](docs/CONTINUOUS_TRAINING.ja.md) and [milestone #5](https://github.com/Unjuno/connectome-fighter/issues/5).

## Current scope

- FightingICE 7.1 + pyftg 2.3 live-game bridge
- numeric observation → controller → 8-action bridge
- terminal-only reward contract: win `+1`, loss `-1`, draw `0`
- deterministic two-sided trace/audit layer
- reproducible FlyWire/Shiu v783 graph import pipeline
- biological-topology and degree/sign-preserving rewired-control graph layer
- sparse connectome-constrained recurrent-controller engineering scaffold
- CI and a GitHub Pages spectator scaffold

## Current limitation

The resumable RL trainer and checkpoint round-trip are not complete yet. The Pages site has the status/replay data contract and viewer scaffold, but no real learned replay is published yet. `brain.py` is also an engineering recurrent scaffold, not a reproduction of the Shiu et al. LIF model.

## Quick checks

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python scripts/smoke_core.py
```

Live FightingICE integration requires the upstream game runtime and `pyftg==2.3`.

## Research boundary

“the persistent fighter learns” and “the biological Drosophila topology is better than matched controls” are different claims. The latter requires the separate matched-rewire A/B protocol with observation, action, reward, training budget, seeds, and held-out opponents held constant.

## License

Project-authored source code is MIT licensed. FightingICE, connectome datasets, papers, and other third-party resources retain their own licenses and terms; see `THIRD_PARTY.md`.
