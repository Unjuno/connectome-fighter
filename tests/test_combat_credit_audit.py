"""R2g score attribution is grounded in the same validated real-game trace contract."""
import copy
import json
from pathlib import Path

import pytest

from connectome_fighter import combat_reward_r2g
from connectome_fighter.combat_credit_audit import audit_r2g_credit

ROOT=Path(__file__).resolve().parents[1]
R2G=json.loads((ROOT/'configs/reward_r2g_local_damage_credit_v1.json').read_text())


def trace(final=(390,350),elapsed=3600):
    return {
        'kind':'round','terminated':True,'truncated':False,'trainable':True,
        'player_index':0,'remaining_hps':list(final),'elapsed_frame':elapsed,
        'transitions':[
            {'frame':f,'policy_version':'frozen',
             'brain':{'trace_decision_index':i},
             'display':{'p1':{'hp':400,'x':0},'p2':{'hp':400,'x':d}}}
            for i,(f,d) in enumerate([(1,500),(61,350),(121,200)])
        ],
    }


@pytest.mark.parametrize("final,elapsed,terminal",[
    ((390,350),3600,2.0),
    ((350,390),3600,-2.0),
    ((400,400),3600,-0.25),
    ((350,350),3600,-0.05),
    ((350,0),1800,2.0),
])
def test_credit_audit_preserves_actual_r2g_signal_and_recovers_removed_reward(final,elapsed,terminal):
    events=combat_reward_r2g.reward_sequence(trace(final,elapsed),0,R2G)
    audit=audit_r2g_credit(events)
    assert audit['learning_credit_id']=='R2g-local-damage-credit-v1'
    assert audit['decision_windows']==len(events)==3
    assert audit['net_terminal_credit']==0.0
    assert audit['removed_terminal_credit']==pytest.approx(terminal)
    assert audit['net_damage_credit']==pytest.approx(sum(e['damage_reward'] for e in events))
    assert audit['net_potential_credit']==pytest.approx(sum(e['potential_reward'] for e in events))
    assert audit['net_modulatory_credit']==pytest.approx(sum(e['signal'] for e in events))
    assert audit['canonical_r2e_net_credit']==pytest.approx(sum(e['canonical_r2e_signal'] for e in events))
    assert audit['nonzero_modulation_windows']==sum(e['signal']!=0 for e in events)
    assert audit['positive_windows']+audit['negative_windows']==audit['nonzero_modulation_windows']
    assert audit['removed_ko_bonus_credit']==pytest.approx(0.125 if elapsed==1800 else 0.0)
    assert audit['gross_absolute_modulatory_credit']>=abs(audit['net_modulatory_credit'])-1e-12


@pytest.mark.parametrize('tamper',[
    lambda x: x[0].update(learning_reward_id='R2e-combat-v1'),
    lambda x: x[0].update(decision_index=99),
    lambda x: x[1].update(decision_index=0),
    lambda x: x[0].update(last=True),
    lambda x: x[-1].update(terminal_reward=1.0),
    lambda x: x[-1].update(finish_bonus=0.125),
    lambda x: x[1].update(signal=1.0),
    lambda x: x[1].update(canonical_r2e_signal=float('nan')),
])
def test_credit_audit_rejects_mutation_or_nonlocal_credit(tamper):
    events=combat_reward_r2g.reward_sequence(trace(),0,R2G)
    events=copy.deepcopy(events)
    tamper(events)
    with pytest.raises(ValueError):
        audit_r2g_credit(events)


def test_credit_audit_empty_and_nonlist_rejected():
    for events in ([],None,{}):
        with pytest.raises(ValueError):
            audit_r2g_credit(events)
