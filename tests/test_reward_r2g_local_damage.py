"""R2g CPU contracts, distinct from actual FightingICE strength validation."""
import copy
import json
from pathlib import Path
import pytest
from connectome_fighter import combat_reward as r2e
from connectome_fighter import combat_reward_r2g as r2g

ROOT=Path(__file__).resolve().parents[1]
CREDIT=json.loads((ROOT/'configs/reward_r2g_local_damage_credit_v1.json').read_text())
BASE=json.loads((ROOT/'configs/reward_r2e_combat_v1.json').read_text())


def trace(hps=(390,350),elapsed=3600):
    return {
        'kind':'round','terminated':True,'truncated':False,'trainable':True,
        'player_index':0,'remaining_hps':list(hps),'elapsed_frame':elapsed,
        'transitions':[
            {'frame':f,'policy_version':'frozen','brain':{'trace_decision_index':i},
             'display':{'p1':{'hp':400,'x':0},'p2':{'hp':400,'x':pos}}}
            for i,(f,pos) in enumerate(zip((1,61,121),(500,400,300)))
        ]
    }


@pytest.mark.parametrize('final',[(390,350),(350,390),(400,400),(350,350),(350,0),(0,350)])
def test_terminal_only_credit_removed_but_actual_local_game_signal_preserved(final):
    t=trace(final,elapsed=1800 if 0 in final else 3600)
    full=r2e.reward_sequence(t,0,BASE)
    adjusted=r2g.reward_sequence(t,0,CREDIT)
    assert len(full)==len(adjusted)
    assert all(z['terminal_reward']==0 and z['finish_bonus']==0 for z in adjusted)
    assert all(u['damage_reward']==v['damage_reward'] and u['potential_reward']==v['potential_reward']
               for u,v in zip(full,adjusted))
    assert all(z['learning_reward_id']==r2g.REWARD_ID for z in adjusted)
    assert [z['canonical_r2e_signal'] for z in adjusted]==[z['signal'] for z in full]
    assert sum(z['signal'] for z in adjusted)==pytest.approx(
        sum(z['damage_reward']+z['potential_reward'] for z in full))


def test_original_combat_selection_metric_is_identical():
    m={'p1_hp':390,'p2_hp':350,'damage_dealt_hp':50,'damage_taken_hp':10,'elapsed_frame':3600}
    assert r2g.evaluation_utility(m,CREDIT)==r2e.paired_evaluation_utility(m,BASE)
    cases=[{'case_id':name,'opponent':name,'seed_p1':800000+i,'seed_p2':30000+i,
            'before':m,'after':m} for i,name in enumerate(['ZEN','LUD','NEZ'])]
    assert r2g.evaluation_suite_gate(cases,CREDIT)==r2e.paired_evaluation_suite_gate(cases,BASE)


def test_zero_terminal_credit_no_action_button_reward():
    a=trace();b=copy.deepcopy(a)
    for x in b['transitions']:x['action']='B';x['requested_keys']={'B':True}
    assert r2g.reward_sequence(a,0,CREDIT)==r2g.reward_sequence(b,0,CREDIT)


def test_explicit_config_identity_and_terminal_gains_are_immutable():
    r2g.validate_config(CREDIT)
    assert CREDIT['base_reward']==BASE
    assert CREDIT['automatic_promotion'] is False
    for field,value in [
        ('terminal_win_loss_gain',0.01),('terminal_ko_bonus_gain',0.5),
        ('no_damage_draw_credit',-0.25),('ordinary_draw_credit',-0.05),
        ('terminal_ko_bonus_gain',float('nan'))]:
        c=copy.deepcopy(CREDIT);c['training_credit'][field]=value
        with pytest.raises(ValueError):
            r2g.validate_config(c)
    c=copy.deepcopy(CREDIT);c['evaluation_reward_id']=r2g.REWARD_ID
    with pytest.raises(ValueError):
        r2g.validate_config(c)
    c=copy.deepcopy(CREDIT);c['base_reward']['terminal']['win']=1
    with pytest.raises(ValueError):
        r2g.validate_config(c)


def test_incomplete_non_trainable_or_falsified_round_fails_closed():
    for change in ({'trainable':False},{'terminated':False},{'truncated':True},
                   {'elapsed_frame':3599},{'player_index':1}):
        t=trace();t.update(change)
        with pytest.raises(ValueError):
            r2g.reward_sequence(t,0,CREDIT)


def test_component_tampering_rejected():
    full=r2e.reward_sequence(trace(),0,BASE)
    bad=copy.deepcopy(full);bad[-1]['signal']+=0.1
    with pytest.raises(ValueError):
        r2g.rebalance_events(bad,CREDIT)
    bad=copy.deepcopy(full);bad[0]['terminal_reward']=2
    with pytest.raises(ValueError):
        r2g.rebalance_events(bad,CREDIT)


def test_updater_dispatches_both_historical_r2f_and_new_r2g_explicitly():
    from scripts.update_malecns_valence_plasticity import reward_sequence as routed
    assert routed(trace(),0,BASE)==r2e.reward_sequence(trace(),0,BASE)
    from connectome_fighter import combat_reward_r2f as r2f
    old=json.loads((ROOT/'configs/reward_r2f_credit_balanced_v1.json').read_text())
    assert routed(trace(),0,old)==r2f.reward_sequence(trace(),0,old)
    assert r2g.reward_sequence(trace(),0,CREDIT)[-1]['terminal_reward']==0
