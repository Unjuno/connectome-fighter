"""Engineering reward fixtures; not evidence of learned fighting strength."""
import copy
import json
from pathlib import Path
import pytest
from connectome_fighter.combat_reward import paired_evaluation_gate, paired_evaluation_utility, reward_sequence, validate_config

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT/'configs/reward_r2e_combat_v1.json').read_text())


def trace(final=(400,400), elapsed=3600, positions=(500,400,300)):
    return {'kind':'round','terminated':True,'truncated':False,'trainable':True,
            'player_index':0,'remaining_hps':list(final),'elapsed_frame':elapsed,
            'transitions':[{'frame':f, 'policy_version':'fixed', 'brain':{'trace_decision_index':i},
                'display':{'p1':{'hp':400,'x':0},'p2':{'hp':400,'x':d}}}
                for i,(f,d) in enumerate(zip((1,61,121),positions))]}


def test_no_damage_draw_is_negative_despite_proximity_shaping():
    e = reward_sequence(trace(),0,CFG)
    assert e[-1]['terminal_reward'] == -.25
    assert sum(x['signal'] for x in e) < 0


def test_win_damage_and_early_ko_bonus():
    e = reward_sequence(trace((350,0),elapsed=1800),0,CFG)
    assert e[-1]['terminal_reward'] == 2
    assert e[-1]['finish_bonus'] == .125
    assert sum(x['damage_reward'] for x in e) == pytest.approx(350/400)


def test_no_fast_loss_bonus():
    e = reward_sequence(trace((0,350),elapsed=1800),0,CFG)
    assert e[-1]['terminal_reward'] == -2
    assert e[-1]['finish_bonus'] == 0


def test_timeout_win_has_no_ko_bonus():
    assert reward_sequence(trace((400,350)),0,CFG)[-1]['finish_bonus']==0


def test_damage_draw_penalty():
    assert reward_sequence(trace((350,350)),0,CFG)[-1]['terminal_reward']==-.05


def test_negative_overkill_hp_not_extra_reward():
    assert reward_sequence(trace((350,-100),1800),0,CFG)==reward_sequence(trace((350,0),1800),0,CFG)


def test_potential_return_independent_of_loop_or_terminal_proximity():
    traces=[trace(positions=(500,100,500)),trace(positions=(500,450,100)),trace(positions=(500,500,500))]
    vals=[sum(e['potential_reward'] for e in reward_sequence(t,0,CFG)) for t in traces]
    assert vals == pytest.approx([.05*320/960]*3)


def test_no_action_button_reward():
    a=trace(); b=copy.deepcopy(a)
    for row in b['transitions']: row.update(action='C',requested_keys={'C':True})
    assert reward_sequence(a,0,CFG)==reward_sequence(b,0,CFG)


@pytest.mark.parametrize('key,value',[('terminated',False),('truncated',True),('trainable',False),('kind','aborted'),('elapsed_frame',600),('elapsed_frame',3601),('player_index',1)])
def test_bad_round_is_not_trainable(key,value):
    t=trace(); t[key]=value
    with pytest.raises(ValueError): reward_sequence(t,0,CFG)


def test_offline_scoring_does_not_authorize_update():
    t=trace();t['trainable']=False
    assert reward_sequence(t,0,CFG,require_trainable=False)
    with pytest.raises(ValueError): reward_sequence(t,0,CFG)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,None,'400',401])
def test_invalid_hp(value):
    t=trace();t['remaining_hps'][0]=value
    with pytest.raises(ValueError): reward_sequence(t,0,CFG)


def test_policy_version_must_be_frozen():
    t=trace();t['transitions'][1]['policy_version']='changed'
    with pytest.raises(ValueError): reward_sequence(t,0,CFG)


def test_regressed_identity():
    t=trace();t['transitions'][1]['brain']['trace_decision_index']=0
    with pytest.raises(ValueError): reward_sequence(t,0,CFG)


def test_missing_decision_has_no_fallback():
    t=trace();t['transitions'][0]['brain']={}
    with pytest.raises(ValueError): reward_sequence(t,0,CFG)


def test_changed_coefficients_need_new_version():
    cfg=copy.deepcopy(CFG); cfg['terminal']['win']=100
    with pytest.raises(ValueError): validate_config(cfg)


def test_mirror_side_damage_and_outcome():
    t=trace((300,100)); e=reward_sequence(t,0,CFG);t['player_index']=1; f=reward_sequence(t,1,CFG)
    assert e[-1]['damage_reward']==-f[-1]['damage_reward']
    assert e[-1]['terminal_reward']==-f[-1]['terminal_reward']



def evaluation(p1_hp=400, p2_hp=355, elapsed=3600):
    return {
        'p1_hp': p1_hp,
        'p2_hp': p2_hp,
        'damage_dealt_hp': 400-p2_hp,
        'damage_taken_hp': 400-p1_hp,
        'elapsed_frame': elapsed,
    }


def test_paired_gate_rejects_regressive_update():
    before=evaluation(400,355)
    after=evaluation(400,390)
    gate=paired_evaluation_gate(before,after,CFG)
    assert gate['accepted_update'] is False
    assert gate['after_utility'] < gate['before_utility']


def test_paired_gate_requires_strict_improvement():
    base=evaluation(400,370)
    assert paired_evaluation_gate(base,copy.deepcopy(base),CFG)['accepted_update'] is False
    assert paired_evaluation_gate(base,evaluation(400,360),CFG)['accepted_update'] is True


def test_paired_utility_matches_terminal_plus_net_damage_for_timeout_win():
    assert paired_evaluation_utility(evaluation(390,360),CFG) == pytest.approx(2.0 + 30/400)


def test_paired_utility_rejects_inconsistent_damage():
    bad=evaluation();bad['damage_dealt_hp']=0
    with pytest.raises(ValueError): paired_evaluation_utility(bad,CFG)
