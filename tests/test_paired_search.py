import copy
import numpy as np
import pytest
from connectome_fighter.paired_search import group_indices, multipliers, propose, score_round


def episode(hps=(400,400), end=3600, xs=(480,480)):
    samples=[{'frame':1, 'p1':{'hp':400,'x':0},'p2':{'hp':400,'x':xs[0]}},
             {'frame':61,'p1':{'hp':400,'x':0},'p2':{'hp':400,'x':xs[1]}}]
    row={'kind':'round','terminated':True,'truncated':False,'player_index':0,
         'elapsed_frame':end,'remaining_hps':list(hps),
         'transitions':[{'frame':s['frame'],'policy_version':'fixed','action':6,'display':s,
                         'brain':{'trace_decision_index':i}} for i,s in enumerate(samples)]}
    return row,samples


def test_zero_draw():
    r=score_round(*episode())
    assert r['combat_score']==r['curriculum_score']==0


def test_win_and_loss_symmetry():
    row,samples=episode((380,0),100)
    a=score_round(row,samples);row['player_index']=1
    b=score_round(row,samples,side=1)
    assert a['combat_score']==pytest.approx(-b['combat_score'])
    assert a['combat_score']==pytest.approx(1.019)


def test_progress_cannot_outscore_hit():
    assert score_round(*episode(xs=(480,0)))['curriculum_score'] < score_round(*episode((400,399)))['curriculum_score']


def test_overkill_capped():
    assert score_round(*episode((400,-20),100))['curriculum_score']==.9


def test_minimum_distance_not_movement_count():
    row,samples=episode(xs=(480,240))
    a=score_round(row,samples)
    samples += [{'frame':f,'p1':{'hp':400,'x':0},'p2':{'hp':400,'x':x}} for f,x in [(62,480),(63,240)]]
    assert score_round(row,samples)['curriculum_score']==a['curriculum_score']==.05


@pytest.mark.parametrize('change',[{'truncated':True},{'terminated':False},{'kind':'other'},{'elapsed_frame':80},{'player_index':1},{'remaining_hps':[401,400]},{'remaining_hps':[float('nan'),400]}])
def test_invalid_round(change):
    row,samples=episode();row.update(change)
    with pytest.raises(ValueError):score_round(row,samples)


@pytest.mark.parametrize('mode',['policy','order','partial','health','sample-order','sample-partial','x'])
def test_invalid_input(mode):
    row,samples=copy.deepcopy(episode())
    if mode=='policy':row['transitions'][1]['policy_version']='changed'
    if mode=='order':row['transitions'][1]['brain']['trace_decision_index']=0
    if mode=='partial':row['transitions'][0]['frame']=2
    if mode=='health':samples[0]['p1']['hp']=399
    if mode=='sample-order':samples[1]['frame']=1
    if mode=='sample-partial':samples[0]['frame']=2
    if mode=='x':samples[0]['p1']['x']=float('inf')
    with pytest.raises(ValueError):score_round(row,samples)


def test_groups_repeat_and_cover():
    g=group_indices(np.arange(1000));assert set(g)==set(range(8));assert np.array_equal(g,group_indices(np.arange(1000)))


def test_zero_step_preserves_parent():
    p=np.array([1,.99,.8],dtype=np.float32)
    assert np.array_equal(p,multipliers(p,np.zeros(2),np.array([0,0,1])))


def test_bound_and_recover_direction():
    p=np.array([1,.99,.8],dtype=np.float32)
    assert np.allclose(multipliers(p,np.array([-.4,.4]),np.array([0,0,1])),[.8,.8,1])


def test_equal_scores_exact_zero():
    g,s=propose(np.ones((4,8)),[-.25]*4,[-.25]*4)
    assert not np.any(g) and not np.any(s)


def test_difference_sign_and_bound():
    u=np.array([[1.,0],[0,1]])
    g,s=propose(u,[1,0],[0,1])
    assert g[0]>0 and g[1]<0 and np.linalg.norm(s)==pytest.approx(.02)


def test_linear_objective_estimator():
    rng=np.random.default_rng(7);u=rng.normal(size=(100000,2));target=np.array([2.,-1.]);sigma=.04
    g,_=propose(u,sigma*(u@target),-sigma*(u@target),sigma=sigma)
    assert np.allclose(g,target,atol=.03)


@pytest.mark.parametrize('kind',['scores','directions','sigma'])
def test_invalid_estimator(kind):
    u=np.ones((2,2));p=np.ones(2);sigma=.04
    if kind=='scores':p[0]=np.nan
    if kind=='directions':u[0,0]=np.inf
    if kind=='sigma':sigma=0
    with pytest.raises(ValueError):propose(u,p,np.zeros(2),sigma=sigma)
