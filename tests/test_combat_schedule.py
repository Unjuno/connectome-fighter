"""Validate scheduling/write boundaries, not achieved training throughput."""
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_self_chaining_single_writer_with_hourly_watchdog_and_read_only_pr_jobs():
    raw=(ROOT/'.github/workflows/continuous-training.yml').read_text();d=yaml.safe_load(raw)
    trigger=d.get('on',d.get(True))
    assert d['name']=='combat-candidate-training'
    assert trigger['schedule']==[{'cron':'17 * * * *'}]
    assert 'workflow_dispatch' in trigger
    assert d['concurrency']=={'group':'canonical-continuous-training-single-writer','cancel-in-progress':False}
    assert d['permissions']=={'contents':'read'}
    assert 'CONNECTOME_TRAINING_PAUSED' in d['jobs']['train-and-evaluate']['if']
    publish=d['jobs']['publish'];assert publish['permissions']=={'contents':'write'}
    assert "github.event_name != 'pull_request'" in publish['if']
    assert "github.ref == 'refs/heads/main'" in publish['if']
    assert publish['needs']=='train-and-evaluate'
    loop=d['jobs']['continue-loop']
    assert loop['needs']==['train-and-evaluate','publish']
    assert loop['permissions']=={'actions':'write','contents':'read'}
    assert loop['timeout-minutes']==5
    assert "github.event_name != 'pull_request'" in loop['if']
    assert "github.ref == 'refs/heads/main'" in loop['if']
    assert "CONNECTOME_TRAINING_PAUSED" in loop['if']
    assert "needs.train-and-evaluate.result == 'success'" in loop['if']
    assert "needs.publish.result == 'success'" in loop['if'] and "needs.publish.result == 'skipped'" in loop['if']
    loop_raw=str(loop)
    assert 'sleep 120' in loop_raw
    assert 'status=queued' in loop_raw and 'status=in_progress' in loop_raw
    assert 'GITHUB_RUN_ID' in loop_raw
    assert '/dispatches' in loop_raw and 'ref=main' in loop_raw
    assert all(j['timeout-minutes']<=25 for j in d['jobs'].values())
    assert d['env']['TRAINING_TAG']=='combat-training-v1'
    assert d['env']['SEED_TAG']=='canonical-training-latest'
    assert 'gh release upload arena-inference-latest' not in raw
    assert 'VERCEL_TOKEN' not in raw and 'vercel deploy' not in raw


def test_actual_pipeline_contains_both_frozen_evaluations_and_no_promotion():
    source=(ROOT/'scripts/combat_training_run.py').read_text()
    assert "match('before'" in source and "match('after'" in source and "match('training'" in source
    assert "'--decision-interval','60'" in source and "'-f','3600'" in source
    assert "'--readout-mode-p1',READOUT_MODE" in source and "'--readout-mode-p2','canonical'" in source
    assert "READOUT_MODE = 'ema-residual'" in source and "READOUT_CONTRACT = 'malecns-temporal-readout-v1'" in source
    assert "'schedule_minutes':None" in source
    assert "'mode': 'bounded-self-chain-with-hourly-watchdog'" in source
    assert "'self_chain_hold_seconds': 120" in source
    assert "'watchdog_cron': '17 * * * *'" in source
    assert "'guaranteed_interval': False" in source
    assert "'schedule_minutes':10" not in source
    assert "'auto_promotion':False" in source and "'served_by_vercel':False" in source
    publisher=(ROOT/'scripts/publish_combat_candidate.py').read_text()
    assert 'upload_immutable' in publisher and 'immutable publication collision' in publisher
    assert "spec['source_commit']==os.environ['GITHUB_SHA']" in publisher
    assert 'arena-inference-latest' not in publisher
