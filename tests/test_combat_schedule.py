"""Validate scheduling/write boundaries, not achieved training throughput."""
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_half_hourly_single_writer_with_read_only_pr_jobs():
    raw = (ROOT / '.github/workflows/continuous-training.yml').read_text()
    workflow = yaml.safe_load(raw)
    trigger = workflow.get('on', workflow.get(True))
    assert workflow['name'] == 'combat-candidate-training'
    assert trigger['schedule'] == [{'cron': '17,47 * * * *'}]
    assert 'workflow_dispatch' in trigger
    # The job is scheduled twice per hour, not chained after its completion.
    assert 'push' not in trigger
    minutes = [17, 47]
    assert minutes[1] - minutes[0] == 30
    assert minutes[0] + 60 - minutes[1] == 30
    concurrency = workflow['concurrency']
    assert concurrency['cancel-in-progress'] is False
    assert 'canonical-continuous-training-single-writer' in concurrency['group']
    assert 'pull_request.number' in concurrency['group']
    assert 'combat-training-pr-' in concurrency['group']
    assert workflow['permissions'] == {'contents': 'read'}
    jobs = workflow['jobs']
    assert 'continue-loop' not in jobs
    assert 'gh api --method POST' not in raw
    assert 'sleep 120' not in raw
    assert 'CONNECTOME_TRAINING_PAUSED' in jobs['train-and-evaluate']['if']
    assert "github.event_name != 'pull_request'" in jobs['train-and-evaluate']['if']
    publish = jobs['publish']
    assert publish['permissions'] == {'contents': 'write'}
    assert "github.event_name != 'pull_request'" in publish['if']
    assert "github.ref == 'refs/heads/main'" in publish['if']
    assert publish['needs'] == 'train-and-evaluate'
    assert all(job['timeout-minutes'] <= 25 for job in jobs.values())
    assert workflow['env']['TRAINING_TAG'] == 'combat-training-v1'
    assert workflow['env']['SEED_TAG'] == 'canonical-training-latest'
    assert 'gh release upload arena-inference-latest' not in raw
    assert 'VERCEL_TOKEN' not in raw and 'vercel deploy' not in raw


def test_actual_pipeline_contains_both_frozen_evaluations_and_no_promotion():
    source=(ROOT/'scripts/combat_training_run.py').read_text()
    assert "match('before'" in source and "match('after'" in source and "match('training'" in source
    assert "'--decision-interval','60'" in source and "'-f','3600'" in source
    assert "'--readout-mode-p1',READOUT_MODE" in source and "'--readout-mode-p2','canonical'" in source
    assert "READOUT_MODE = 'ema-residual'" in source and "READOUT_CONTRACT = 'malecns-temporal-readout-v1'" in source
    assert "paired_evaluation_suite_gate" in source
    assert "'case_id':'zen-validation-v1','opponent':'ZEN','seed_p1':810101,'seed_p2':31001" in source
    assert "'case_id':'lud-validation-v1','opponent':'LUD','seed_p1':810202,'seed_p2':31002" in source
    assert "'case_id':'nez-validation-v1','opponent':'NEZ','seed_p1':810303,'seed_p2':31003" in source
    assert "'protocol':'fixed-three-opponent-validation-v1'" in source
    assert "validation_before=evaluate_suite('validation-before',before_adapter)" in source
    assert "validation_after=evaluate_suite('validation-after',after_adapter)" in source
    assert "LEGACY_EVALUATION = {'opponent':'ZEN','seed_p1':800101,'seed_p2':20202}" in source
    assert "'schedule_minutes':30" in source
    assert "'mode': 'scheduled-30-minute-single-writer'" in source
    assert "'interval_minutes': 30" in source
    assert "'schedule_cron': '17,47 * * * *'" in source
    assert "'guaranteed_interval': False" in source
    assert "'self_dispatch_enabled': False" in source
    assert "'manual_dispatch_allowed': True" in source
    assert "'schedule_minutes':10" not in source
    assert "'auto_promotion':False" in source and "'served_by_vercel':False" in source
    publisher=(ROOT/'scripts/publish_combat_candidate.py').read_text()
    assert 'upload_immutable' in publisher and 'immutable publication collision' in publisher
    assert "spec['source_commit']==os.environ['GITHUB_SHA']" in publisher
    assert 'arena-inference-latest' not in publisher
