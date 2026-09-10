"""Offline integration/gradient smoke. Synthetic data, NO fighting or RL result."""
from __future__ import annotations
import argparse
import json
import platform
from pathlib import Path
import torch
from connectome_fighter.graph import synthetic_graph, rewire_signed_degrees
from connectome_fighter.brain import ConnectomeActorCritic
from connectome_fighter.contracts import OBS_DIM

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/smoke_report.json")
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.manual_seed(7)
    g = synthetic_graph(32, 7)
    shuffled, audit = rewire_signed_degrees(g, 192, 11)
    net = ConnectomeActorCritic(g, list(range(8)), list(range(16, 32)), plastic=True)
    optimizer = torch.optim.Adam(net.parameters(), lr=1e-3)
    state = torch.zeros(2, 32)
    old = net.core.theta.detach().clone()
    log_probs = []
    for _ in range(8):
        logits, values, state = net(torch.randn(2, OBS_DIM), state)
        log_probs.append(torch.log_softmax(logits, -1)[:, 5])
    outcomes = torch.tensor([1., -1.])
    loss = -(torch.stack(log_probs).sum(0)*outcomes).mean()
    optimizer.zero_grad(); loss.backward()
    finite = all(p.grad is None or bool(torch.isfinite(p.grad).all()) for p in net.parameters())
    optimizer.step()
    report = {
        "status": "engineering_smoke_only", "real_game_run": False, "biological_data_used": False,
        "ppo_training_run": False, "python": platform.python_version(), "torch": torch.__version__,
        "numpy": __import__("numpy").__version__, "backend": "cpu", "dtype": "float32", "batch": 2,
        "nodes": g.n_nodes, "edges": g.n_edges, "neural_steps_per_decision": net.neural_steps,
        "unroll_decisions": 8, "finite_gradients": finite,
        "edge_parameters_changed": bool(torch.any(net.core.theta.detach() != old)),
        "edge_signs_preserved": bool(torch.equal(torch.sign(net.core.weights()), net.core.sign)),
        "graph_hash": g.fingerprint(), "rewired_hash": shuffled.fingerprint(), "rewire_audit": audit,
    }
    path = Path(args.out); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))
    if not (finite and report["edge_parameters_changed"] and report["edge_signs_preserved"]):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
