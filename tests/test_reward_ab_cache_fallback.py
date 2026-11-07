"""Historical reward A/B must reconstruct missing anatomy cache, never silently substitute fake data."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_historical_ab_regenerates_missing_pinned_valence_partition():
    source=(ROOT/'.github/workflows/reward-plasticity-ab.yml').read_text()
    cfg=yaml.safe_load(source)
    assert cfg['name']=='reward-plasticity-ab'
    steps=cfg['jobs']['condition']['steps']
    valence=next(s for s in steps if s.get('name')=='Restore valence partition cache')
    assert valence['uses']=='actions/cache@v4'
    assert valence['id']=='valence-cache'
    assert valence['with']['key']=='${{ env.VALENCE_CACHE_KEY }}'
    assert valence['with'].get('fail-on-cache-miss') is not True
    rebuild=next(s for s in steps if s.get('name')=='Rebuild valence partition from pinned MaleCNS anatomy on cache miss')
    assert rebuild['if']=="steps.valence-cache.outputs.cache-hit != 'true'"
    cmd=rebuild['run']
    assert 'set -euo pipefail' in cmd
    assert 'build_malecns_valence_partition.py' in cmd
    assert '--metadata data/processed/malecns-shiu-strict-v1/neuron_metadata.parquet' in cmd
    assert '--connectivity data/processed/malecns-shiu-strict-v1/connectivity.parquet' in cmd
    assert '--adapter-manifest data/processed/malecns-shiu-strict-v1/manifest.json' in cmd
    assert '--out-dir data/processed/malecns-valence-v1' in cmd
    verify=next(s for s in steps if s.get('name')=='Verify partition identity and anatomical invariants')
    # Invariants must be checked on cache hit as well as after fresh rebuild.
    assert 'if' not in verify
    check=verify['run']
    assert "assert len(c)==33496" in check
    for invariant in ('topology_changed','weights_changed','signs_changed','learning_applied'):
        assert f"m['invariants']['{invariant}'] is False" in check
    assert "assert (c['sign']==1).all()" in check
    assert "c['synapse_index'].is_unique" in check
    assert "mbon_valence_channel" in check
    assert cfg['jobs']['condition']['strategy']['matrix']['include'][0]['label']=='control'
    assert 'R2g-local-damage-credit-v1' not in source
