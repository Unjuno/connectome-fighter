import copy
import torch

from connectome_fighter.characters import CHARACTER_SEEDS, CHARACTERS
from connectome_fighter.checkpoint import load_checkpoint, save_checkpoint
from connectome_fighter.learning import PPOConfig, initialize_heads, make_optimizer, ppo_update


def test_character_brains_initialize_independently():
    weights = []
    for character in CHARACTERS:
        heads = initialize_heads(5, CHARACTER_SEEDS[character])
        weights.append(heads.actor.weight.detach().clone())
    assert all(not torch.equal(weights[0], other) for other in weights[1:])


def test_checkpoint_roundtrip_and_character_guard(tmp_path):
    cfg = PPOConfig(epochs=1)
    heads = initialize_heads(5, CHARACTER_SEEDS["ZEN"])
    opt = make_optimizer(heads, cfg)
    path = tmp_path / "brain-ZEN.pt"
    meta = save_checkpoint(
        path, character="ZEN", actor=heads.actor, critic=heads.critic, optimizer=opt,
        generation=3, training_matches=12, updates=3,
        graph_hash="a" * 64, routing_hash="b" * 64, code_sha="test",
        hyperparameters=cfg.as_dict(),
    )
    loaded = load_checkpoint(path, expected_character="ZEN",
                             expected_graph_hash="a" * 64, expected_routing_hash="b" * 64)
    assert loaded["metadata"]["checkpoint_id"] == meta["checkpoint_id"] == "zen-g000003"
    try:
        load_checkpoint(path, expected_character="LUD")
    except ValueError:
        pass
    else:
        raise AssertionError("cross-character checkpoint load must be rejected")


def test_ppo_updates_readout_only():
    cfg = PPOConfig(epochs=2, learning_rate=1e-3)
    heads = initialize_heads(5, CHARACTER_SEEDS["GARNET"])
    opt = make_optimizer(heads, cfg)
    before = copy.deepcopy(heads.actor.state_dict())
    rounds = [{
        "kind": "round", "terminated": True, "outcome_reward": 1.0,
        "transitions": [
            {"action": 0, "log_prob": -2.0, "value": 0.0,
             "brain": {"readout_features": [0.1, 0.2, 0.3, 0.4, 0.5]}},
            {"action": 1, "log_prob": -2.0, "value": 0.0,
             "brain": {"readout_features": [0.2, 0.3, 0.4, 0.5, 0.6]}},
        ],
    }]
    metrics = ppo_update(heads, opt, rounds, cfg)
    assert metrics["rounds"] == 1 and metrics["transitions"] == 2
    assert any(not torch.equal(before[k], heads.actor.state_dict()[k]) for k in before)
