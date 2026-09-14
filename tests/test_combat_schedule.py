"""Validate scheduling/write boundaries, not achieved training throughput."""
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_legacy_r2e_requires_explicit_manual_opt_in():
    raw=(ROOT/'.github/workflows/continuous-training.yml').read_text();d=yaml.safe_load(raw)
    trigger=d.get('on',d.get(True))
    assert d['name']=='combat-candidate-training'
    assert trigger=={'workflow_dispatch':None}
    assert d['concurrency']=={'group':'canonical-continuous-training-single-writer','cancel-in-progress':False}
    assert d['permissions']=={'contents':'read'}
    condition=d['jobs']['train-and-evaluate']['if']
    assert 'CONNECTOME_TRAINING_PAUSED' in condition
    assert "github.event_name == 'workflow_dispatch'" in condition
    assert "CONNECTOME_LEGACY_R2E_ENABLED == 'true'" in condition
    publish=d['jobs']['publish'];assert publish['permissions']=={'contents':'write'}
    assert "github.event_name != 'pull_request'" in publish['if']
    assert "github.ref == 'refs/heads/main'" in publish['if']
    assert publish['needs']=='train-and-evaluate'
    assert all(j['timeout-minutes']<=25 for j in d['jobs'].values())
    assert d['env']['TRAINING_TAG']=='combat-training-v1'
    assert d['env']['SEED_TAG']=='canonical-training-latest'
    assert 'gh release upload arena-inference-latest' not in raw
    assert 'VERCEL_TOKEN' not in raw and 'vercel deploy' not in raw


def test_paired_training_is_the_recurring_single_writer():
    raw=(ROOT/'.github/workflows/paired-neural-training.yml').read_text();d=yaml.safe_load(raw)
    trigger=d.get('on',d.get(True))
    assert d['name']=='paired-neural-training'
    assert trigger['schedule']==[{'cron':'7,17,27,37,47,57 * * * *'}]
    assert d['concurrency']=={'group':'canonical-continuous-training-single-writer','cancel-in-progress':False}
    assert d['permissions']=={'contents':'read'}
    assert 'CONNECTOME_TRAINING_PAUSED' in d['jobs']['cycle']['if']
    publish=d['jobs']['publish'];assert publish['permissions']=={'contents':'write'}
    assert "github.event_name != 'pull_request'" in publish['if']
    assert "github.ref == 'refs/heads/main'" in publish['if']
    assert publish['needs']=='cycle'
    assert all(j['timeout-minutes']<=30 for j in d['jobs'].values())
    assert 'paired_training_release.py publish' in raw
    assert 'git push' not in raw and 'VERCEL_TOKEN' not in raw


def test_actual_pipeline_contains_both_frozen_evaluations_and_no_promotion():
    source=(ROOT/'scripts/combat_training_run.py').read_text()
    assert "match('before'" in source and "match('after'" in source and "match('training'" in source
    assert "'--decision-interval','60'" in source and "'-f','3600'" in source
    assert "'auto_promotion':False" in source and "'served_by_vercel':False" in source
    publisher=(ROOT/'scripts/publish_combat_candidate.py').read_text()
    assert 'upload_immutable' in publisher and 'immutable publication collision' in publisher
    assert "spec['source_commit']==os.environ['GITHUB_SHA']" in publisher
    assert 'arena-inference-latest' not in publisher
