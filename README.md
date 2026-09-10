# Connectome Fighter

Research scaffold for testing whether connectome-constrained controllers learn competitive policies differently from matched control networks in FightingICE.

[Project dashboard](https://unjuno.github.io/connectome-fighter/) · [日本語](README.ja.md)

## Scope

- FightingICE 7.1 + pyftg 2.3 bridge
- deterministic trace/audit layer for two-player matches
- connectome-constrained controller scaffold
- matched rewiring/control experiments
- GitHub Actions tests and a static Pages dashboard

No biological result is claimed by this repository. Synthetic fixtures, mock API tests, and live-game runs are recorded as distinct evidence classes.

## Quick checks

```bash
python -m pip install -e '.[test]'
python -m pytest -q
python scripts/smoke_core.py
```

Live FightingICE integration is a separate milestone and requires the upstream game runtime and `pyftg==2.3`.

## Research question

Does a verified Drosophila-derived wiring topology provide measurable learning or transfer advantages over topology-matched rewired controls under identical observations, actions, rewards, training budgets, seeds, and evaluation opponents?

## License

Project-authored source code is MIT licensed. FightingICE, connectome datasets, papers, and other third-party resources retain their own licenses and terms; see `THIRD_PARTY.md`.
