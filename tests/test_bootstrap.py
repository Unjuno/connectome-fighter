import numpy as np
import torch
from connectome_fighter.contracts import Action, action_keys, player_index, OBS_DIM
from connectome_fighter.trajectory import round_reward
from connectome_fighter.graph import synthetic_graph, rewire_signed_degrees
from connectome_fighter.brain import ConnectomeActorCritic


def test_player_number_contract():
    assert player_index(True) == 0
    assert player_index(False) == 1
    for bad in (0, 1, None):
        try:
            player_index(bad)
        except TypeError:
            pass
        else:
            raise AssertionError('non-bool player id accepted')


def test_directional_action_mapping():
    assert action_keys(Action.FORWARD, True)['R']
    assert action_keys(Action.FORWARD, False)['L']
    assert action_keys(Action.BACKWARD, True)['L']


def test_terminal_reward_is_zero_sum():
    for hp in ([300, 100], [0, 0], [-5, -2], [1, 2]):
        assert round_reward(list(hp), True) + round_reward(list(hp), False) == 0


def test_signed_degree_rewire_preserves_core_invariants():
    graph = synthetic_graph(32, seed=3)
    shuffled, audit = rewire_signed_degrees(graph, swaps=128, seed=9)
    assert shuffled.n_nodes == graph.n_nodes
    assert shuffled.n_edges == graph.n_edges
    assert audit['accepted_swaps'] == 128
    for sign in (-1, 1):
        a = graph.sign == sign
        b = shuffled.sign == sign
        assert np.array_equal(np.bincount(graph.src[a], minlength=graph.n_nodes),
                              np.bincount(shuffled.src[b], minlength=graph.n_nodes))
        assert np.array_equal(np.bincount(graph.dst[a], minlength=graph.n_nodes),
                              np.bincount(shuffled.dst[b], minlength=graph.n_nodes))


def test_plastic_connectome_keeps_recorded_signs_and_receives_gradient():
    torch.manual_seed(1)
    graph = synthetic_graph(32, seed=1)
    net = ConnectomeActorCritic(graph, list(range(8)), list(range(16, 32)), plastic=True)
    state = torch.zeros(2, graph.n_nodes)
    logits, values, state = net(torch.randn(2, OBS_DIM), state)
    loss = logits.square().mean() + values.square().mean()
    loss.backward()
    assert net.core.theta.grad is not None
    assert torch.isfinite(net.core.theta.grad).all()
    assert torch.equal(torch.sign(net.core.weights()), net.core.sign)
