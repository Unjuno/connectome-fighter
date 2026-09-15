"""Active paired scheduling boundary; legacy R2e scorer remains a comparator."""
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]


def test_five_minute_paired_lane_replaces_legacy_writer():
    raw=(ROOT/'.github/workflows/continuous-training.yml').read_text();d=yaml.safe_load(raw)
    trigger=d.get('on',d.get(True))
    assert d['name']=='paired-candidate-training'
    assert trigger['schedule']==[{'cron':'2,7,12,17,22,27,32,37,42,47,52,57 * * * *'}]
    assert d['concurrency']=={'group':'canonical-continuous-training-single-writer','cancel-in-progress':False}
    assert d['permissions']=={'contents':'read'}
    assert 'CONNECTOME_TRAINING_PAUSED' in d['jobs']['train-and-evaluate']['if']
    publish=d['jobs']['publish'];assert publish['permissions']=={'contents':'write'}
    assert "github.event_name != 'pull_request'" in publish['if']
    assert "github.ref == 'refs/heads/main'" in publish['if']
    assert publish['needs']=='train-and-evaluate'
    assert all(j['timeout-minutes']<=35 for j in d['jobs'].values())
    assert '--persistent' in raw and 'paired_rollout_io.py publish' in raw
    assert 'combat_training_run.py' not in raw and 'update_malecns_valence_plasticity.py' not in raw
    assert 'VERCEL_TOKEN' not in raw and 'vercel deploy' not in raw


def test_actual_pipeline_contains_both_frozen_evaluations_and_no_promotion():
    # The old implementation is retained, not silently rewritten as a new algorithm.
    source=(ROOT/'scripts/combat_training_run.py').read_text()
    assert "match('before'" in source and "match('after'" in source and "match('training'" in source
    assert "'--decision-interval','60'" in source and "'-f','3600'" in source
    assert "'auto_promotion':False" in source and "'served_by_vercel':False" in source
    publisher=(ROOT/'scripts/publish_combat_candidate.py').read_text()
    assert 'upload_immutable' in publisher and 'immutable publication collision' in publisher
    assert "spec['source_commit']==os.environ['GITHUB_SHA']" in publisher
    assert 'arena-inference-latest' not in publisher
