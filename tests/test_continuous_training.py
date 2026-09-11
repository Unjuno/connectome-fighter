import copy
import json
import torch

from connectome_fighter.characters import CHARACTER_SEEDS, CHARACTERS
from connectome_fighter.checkpoint import load_checkpoint, save_checkpoint
from connectome_fighter.learning import PPOConfig, initialize_heads, make_optimizer, ppo_update
from connectome_fighter.state_bundle import package_state, restore_state


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


def test_double_buffered_state_bundle_roundtrip(tmp_path):
    cfg = PPOConfig(epochs=1)
    state = tmp_path / "state"
    state.mkdir()
    for character in CHARACTERS:
        heads = initialize_heads(5, CHARACTER_SEEDS[character])
        opt = make_optimizer(heads, cfg)
        save_checkpoint(
            state / f"brain-{character}.pt", character=character,
            actor=heads.actor, critic=heads.critic, optimizer=opt,
            generation=4, training_matches=8, updates=4,
            graph_hash="c" * 64, routing_hash="d" * 64, code_sha="test",
            hyperparameters=cfg.as_dict(),
        )
    (state / "league-state.json").write_text(json.dumps({"chunks": 4}), encoding="utf-8")
    publish = tmp_path / "publish"
    pointer = package_state(state, publish)
    assert pointer["active_slot"] == "a"
    restored = tmp_path / "restored"
    result = restore_state(publish, restored)
    assert result["generation"] == 4 and result["chunk"] == 4
    for character in CHARACTERS:
        loaded = load_checkpoint(restored / f"brain-{character}.pt", expected_character=character)
        assert loaded["metadata"]["generation"] == 4
