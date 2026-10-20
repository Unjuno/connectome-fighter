"""Actual updater entrypoint: R2f credit, R2e checkpoint and external objective."""
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

from connectome_fighter.combat_checkpoint import config_from_json
from connectome_fighter.combat_reward import reward_sequence as canonical_sequence
from connectome_fighter.combat_reward_r2f import reward_sequence as r2f_sequence
from connectome_fighter.valence_plasticity import load_state, sha256_file
from scripts import update_malecns_valence_plasticity as updater

ROOT = Path(__file__).resolve().parents[1]
REWARD = ROOT/"configs/reward_r2e_combat_v1.json"
CREDIT = ROOT/"configs/reward_r2f_credit_balanced_v1.json"
PLASTIC = ROOT/"configs/plasticity_combat_v1.json"


def test_real_updater_cli_uses_r2f_credit_and_keeps_r2e_checkpoint(tmp_path,monkeypatch):
    cands=tmp_path/"candidates.parquet"
    spikes=tmp_path/"spikes.parquet"
    trace=tmp_path/"trainable.jsonl"
    state=tmp_path/"GARNET.npz"
    out=tmp_path/"update.json"
    cands.write_bytes(b"fixture candidate bytes")
    spikes.write_bytes(b"fixture spike bytes")
    channels=pd.DataFrame({
        "synapse_index":[0,1],
        "body_pre":[101,101],
        "body_post":[102,103],
        "mbon_valence_channel":["avoidance_associated","approach_associated"],
        "sign":[1,1],
    })
    rows=pd.DataFrame({"decision_index":[0,0,0,1,1,1,2,2,2],
                       "body_id":[101,102,103,101,102,103,101,102,103]})
    monkeypatch.setattr(pd,"read_parquet",lambda path: channels.copy() if Path(path)==cands else rows.copy())
    game={
        "kind":"round","terminated":True,"truncated":False,"trainable":True,
        "player_index":0,"elapsed_frame":3600,"remaining_hps":[400,350],
        "transitions":[
            {"frame":f,"policy_version":"frozen","brain":{"trace_decision_index":i},
             "display":{"p1":{"hp":400,"x":0},"p2":{"hp":400,"x":x}}}
            for i,(f,x) in enumerate([(1,500),(61,350),(121,200)])
        ],
    }
    trace.write_text(json.dumps(game)+"\n",encoding="utf-8")
    argv=[
        "update_malecns_valence_plasticity.py","--character","GARNET","--side","1",
        "--round-trace",str(trace),"--spikes",str(spikes),"--candidates",str(cands),
        "--reward-config",str(REWARD),"--learning-credit-config",str(CREDIT),
        "--plasticity-config",str(PLASTIC),"--state",str(state),"--out-summary",str(out),
    ]
    monkeypatch.setattr(sys,"argv",argv)
    assert updater.main()==0
    data=json.loads(out.read_text())
    canonical=canonical_sequence(game,0,json.loads(REWARD.read_text()))
    modified=r2f_sequence(game,0,json.loads(CREDIT.read_text()))
    assert data["reward_id"]=="R2e-combat-v1"
    assert data["external_evaluation_reward_id"]=="R2e-combat-v1"
    assert data["learning_credit_id"]=="R2f-credit-balanced-v1"
    assert data["learning_credit_sha256"]==sha256_file(CREDIT)
    assert data["signals"]["sum"]==pytest.approx(sum(x["signal"] for x in modified))
    assert data["signals"]["sum"]!=pytest.approx(sum(x["signal"] for x in canonical))
    assert data["updates"]["potentiated_edges"]==0
    cfg=config_from_json(json.loads(PLASTIC.read_text()))
    loaded=load_state(state,expected_character="GARNET",n_candidates=2,
                      expected_candidate_sha256=sha256_file(cands),config=cfg)
    assert loaded.generation==1
    meta=json.loads(state.with_suffix(".npz.json").read_text())
    assert meta["learning_credit_id"]==data["learning_credit_id"]
    assert meta["learning_credit_sha256"]==sha256_file(CREDIT)
    assert meta["external_evaluation_reward_id"]==data["reward_id"]
    assert updater.main()==0
    meta2=json.loads(state.with_suffix(".npz.json").read_text())
    assert meta2["generation"]==2
    assert meta2["learning_credit_id"]=="R2f-credit-balanced-v1"
    meta2["learning_credit_id"]="untracked"
    state.with_suffix(".npz.json").write_text(json.dumps(meta2))
    with pytest.raises(ValueError,match="credit"):
        updater.main()


def test_main_trainer_actively_passes_r2f_credit_and_keeps_external_r2e():
    source=(ROOT/"scripts/combat_training_run.py").read_text()
    assert "CREDIT_CONFIG = ROOT/'configs/reward_r2f_credit_balanced_v1.json'" in source
    assert "'--learning-credit-config',CREDIT_CONFIG" in source
    assert "gate=paired_evaluation_suite_gate(gate_cases,reward_config)" in source
    assert "reward_config=r2e_spec" in source
    assert "'learning_credit_id':LEARNING_CREDIT_ID" in source
    assert "'served_by_vercel':False" in source
