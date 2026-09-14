"""Engineering reward invariants. These do not establish learning efficacy."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('colosseum_reward', ROOT/'src/connectome_fighter/colosseum_reward.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
CFG = json.loads((ROOT/'configs/reward_colosseum_v1.json').read_text())


def row(points=((400,400,480), (400,400,180)), terminal=(400,400)):
    return {'kind':'round','terminated':True,'truncated':False,'trainable':True,'player_index':0,
            'elapsed_frame':3600,'remaining_hps':list(terminal),
            'transitions':[{'frame':1+i*15,'brain':{'trace_decision_index':i},
                            'action':1,'display':{'p1':{'hp':a,'x':0},'p2':{'hp':b,'x':d}}}
                           for i,(a,b,d) in enumerate(points)]}


class RewardContract(unittest.TestCase):
    def test_no_damage_approach_still_negative(self):
        self.assertLess(sum(x['signal'] for x in m.reward_sequence(row(),0,CFG)),0)
    def test_win_positive(self):
        self.assertGreater(sum(x['signal'] for x in m.reward_sequence(row(terminal=(400,0)),0,CFG)),1)
    def test_loss_negative(self):
        self.assertLess(sum(x['signal'] for x in m.reward_sequence(row(terminal=(0,400)),0,CFG)),-1)
    def test_damaged_draw_not_no_damage_draw(self):
        es=m.reward_sequence(row(terminal=(300,300)),0,CFG)
        self.assertEqual(es[-1]['outcome'],'draw');self.assertEqual(es[-1]['terminal_reward'],-0.1)
    def test_no_action_bonus(self):
        a=row();b=copy.deepcopy(a)
        for t in b['transitions']:t['action']=6;t['spikes']=999999
        self.assertEqual(m.reward_sequence(a,0,CFG),m.reward_sequence(b,0,CFG))
    def test_distance_oscillation_not_farmable(self):
        a=row(points=((400,400,480),(400,400,180)))
        b=row(points=((400,400,480),(400,400,180),(400,400,480),(400,400,180)))
        self.assertAlmostEqual(sum(x['potential_reward'] for x in m.reward_sequence(a,0,CFG)),sum(x['potential_reward'] for x in m.reward_sequence(b,0,CFG)))
    def test_terminal_distance_does_not_change_total_shaping(self):
        a=row(points=((400,400,480),(400,400,180)))
        b=row(points=((400,400,480),(400,400,900)))
        self.assertAlmostEqual(sum(x['signal'] for x in m.reward_sequence(a,0,CFG)),sum(x['signal'] for x in m.reward_sequence(b,0,CFG)))
    def test_damage_normalized_by_max_hp(self):
        es=m.reward_sequence(row(terminal=(400,390)),0,CFG)
        self.assertAlmostEqual(sum(x['damage_reward'] for x in es),0.0125)
    def test_overkill_is_not_extra_reward(self):
        a=m.reward_sequence(row(terminal=(400,0)),0,CFG)
        b=m.reward_sequence(row(terminal=(400,-50)),0,CFG)
        self.assertEqual(a,b)
    def test_second_player_damage_sign(self):
        r=row(terminal=(300,400));r['player_index']=1
        es=m.reward_sequence(r,1,CFG);self.assertEqual(es[-1]['outcome'],'win')
        self.assertGreater(sum(x['damage_reward'] for x in es),0)
    def test_truncation_rejected(self):
        r=row();r['truncated']=True
        with self.assertRaises(ValueError):m.reward_sequence(r,0,CFG)
    def test_nontrainable_rejected(self):
        r=row();r['trainable']=False
        with self.assertRaises(ValueError):m.reward_sequence(r,0,CFG)
    def test_missing_terminal_rejected(self):
        r=row();r['terminated']=False
        with self.assertRaises(ValueError):m.reward_sequence(r,0,CFG)
    def test_invalid_identity_rejected(self):
        r=row();r['transitions'][1]['brain']['trace_decision_index']=0
        with self.assertRaises(ValueError):m.reward_sequence(r,0,CFG)
    def test_backwards_frame_rejected(self):
        r=row();r['transitions'][1]['frame']=0
        with self.assertRaises(ValueError):m.reward_sequence(r,0,CFG)
    def test_nan_rejected(self):
        r=row();r['remaining_hps'][0]=float('nan')
        with self.assertRaises(ValueError):m.reward_sequence(r,0,CFG)
    def test_healing_rejected(self):
        r=row(points=((390,400,480),(400,400,180)))
        with self.assertRaises(ValueError):m.reward_sequence(r,0,CFG)
    def test_wrong_player_rejected(self):
        with self.assertRaises(ValueError):m.reward_sequence(row(),1,CFG)
    def test_invalid_reward_identity_rejected(self):
        c=copy.deepcopy(CFG);c['id']='legacy'
        with self.assertRaises(ValueError):m.reward_sequence(row(),0,c)
    def test_auxiliary_dominance_rejected(self):
        c=copy.deepcopy(CFG);c['damage_weight']=5
        with self.assertRaises(ValueError):m.reward_sequence(row(),0,c)
    def test_game_time_eligibility_preserved(self):
        c=json.loads((ROOT/'configs/plasticity_colosseum_v1.json').read_text())
        self.assertAlmostEqual(c['eligibility_decay_per_decision']**4,0.9)
    def test_ten_minute_schedule_and_no_auto_promotion(self):
        text=(ROOT/'.github/workflows/colosseum-training.yml').read_text()
        self.assertIn("cron: '3,13,23,33,43,53 * * * *'",text)
        self.assertIn('cancel-in-progress: false',text)
        self.assertNotIn('arena-inference-latest',text)
        self.assertNotIn('schedule:',(ROOT/'.github/workflows/continuous-training.yml').read_text())

if __name__=='__main__':unittest.main()
