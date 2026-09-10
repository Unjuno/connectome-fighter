"""Sparse graph-constrained recurrent model; NOT a reproduction of Shiu LIF.

The anatomical graph can be real. The sigmoid dynamics, artificial routing,
and gradient learning are modelling assumptions. All states are dimensionless.
"""
from __future__ import annotations
import numpy as np
import torch
from torch import nn
from .graph import Graph
from .contracts import Decision, N_ACTIONS, OBS_DIM

class SparseGraphCore(nn.Module):
    def __init__(self, graph: Graph, *, plastic: bool = False,
                 gain: float = 0.1, leak: float = 0.5):
        super().__init__()
        if not np.isfinite(gain) or gain <= 0 or not 0 < leak <= 1:
            raise ValueError("Invalid gain/leak")
        self.n_nodes, self.leak = graph.n_nodes, float(leak)
        self.graph_hash = graph.fingerprint()
        self.register_buffer("indices", torch.tensor(np.stack([graph.dst, graph.src]), dtype=torch.int64))
        self.register_buffer("base", torch.tensor(graph.magnitude.copy()) * gain)
        self.register_buffer("sign", torch.tensor(graph.sign.copy()))
        if plastic:
            self.theta = nn.Parameter(torch.zeros(graph.n_edges))
        else:
            self.register_parameter("theta", None)

    def weights(self) -> torch.Tensor:
        factor = 1.0 if self.theta is None else 2 * torch.sigmoid(self.theta)
        return self.sign * self.base * factor

    def forward(self, drive: torch.Tensor, state: torch.Tensor) -> torch.Tensor:
        if drive.shape != state.shape or state.ndim != 2 or state.shape[-1] != self.n_nodes:
            raise ValueError("Expected drive and state of shape [batch, n_nodes]")
        matrix = torch.sparse_coo_tensor(self.indices, self.weights(),
                                        (self.n_nodes, self.n_nodes)).coalesce()
        recurrent = torch.sparse.mm(matrix, state.T).T
        return (1-self.leak)*state + self.leak*torch.sigmoid(recurrent+drive)

class FixedRouting(nn.Module):
    """Seeded sparse artificial encoder, deliberately disjoint from readout nodes."""
    def __init__(self, n_nodes: int, input_nodes: list[int], obs_dim: int = OBS_DIM, seed: int = 0):
        super().__init__()
        if not input_nodes or len(set(input_nodes)) != len(input_nodes) or min(input_nodes) < 0 or max(input_nodes) >= n_nodes:
            raise ValueError("Invalid unique input-node list")
        rng = np.random.default_rng(seed)
        self.n_nodes, self.obs_dim = n_nodes, obs_dim
        self.register_buffer("nodes", torch.tensor(input_nodes, dtype=torch.int64))
        self.register_buffer("features", torch.tensor(rng.integers(obs_dim, size=len(input_nodes)), dtype=torch.int64))
        self.register_buffer("gains", torch.tensor(rng.choice([-1., 1.], size=len(input_nodes)), dtype=torch.float32))

    def forward(self, observation: torch.Tensor) -> torch.Tensor:
        if observation.ndim != 2 or observation.shape[-1] != self.obs_dim:
            raise ValueError("Unexpected observation shape")
        drive = observation.new_zeros((observation.shape[0], self.n_nodes))
        values = observation[:, self.features] * self.gains
        return drive.index_add(1, self.nodes, values)

class ConnectomeActorCritic(nn.Module):
    def __init__(self, graph: Graph, input_nodes: list[int], output_nodes: list[int], *,
                 plastic: bool = False, gain: float = 0.1, leak: float = 0.5,
                 neural_steps: int = 4, routing_seed: int = 0):
        super().__init__()
        if (not output_nodes or len(set(output_nodes)) != len(output_nodes)
            or min(output_nodes) < 0 or max(output_nodes) >= graph.n_nodes
            or set(input_nodes) & set(output_nodes) or neural_steps <= 0):
            raise ValueError("Use unique, valid, disjoint input/output nodes and positive steps")
        self.core = SparseGraphCore(graph, plastic=plastic, gain=gain, leak=leak)
        self.routing = FixedRouting(graph.n_nodes, input_nodes, seed=routing_seed)
        self.register_buffer("output_nodes", torch.tensor(output_nodes, dtype=torch.int64))
        self.actor = nn.Linear(len(output_nodes), N_ACTIONS)
        self.critic = nn.Linear(len(output_nodes), 1)
        self.neural_steps = neural_steps

    def forward(self, observation: torch.Tensor, state: torch.Tensor):
        drive = self.routing(observation)
        for _ in range(self.neural_steps):
            state = self.core(drive, state)
        features = state[:, self.output_nodes]
        return self.actor(features), self.critic(features).squeeze(-1), state

class NeuralPolicy:
    """Inference wrapper. Separate instance/state/random stream for each fighter."""
    def __init__(self, model: ConnectomeActorCritic, version: str, seed: int = 0):
        if not version:
            raise ValueError("Policy version is required")
        self.model, self.version = model.eval(), version
        device = next(model.parameters()).device
        self.generator = torch.Generator(device=device).manual_seed(seed)
        self.reset()

    def reset(self):
        self.state = self.model.core.base.new_zeros((1, self.model.core.n_nodes))

    @torch.no_grad()
    def act(self, observation: np.ndarray) -> Decision:
        x = torch.tensor(np.array(observation, copy=True), device=self.state.device).unsqueeze(0)
        logits, value, self.state = self.model(x, self.state)
        log_probs = torch.log_softmax(logits, dim=-1)
        action = int(torch.multinomial(log_probs.exp(), 1, generator=self.generator).item())
        return Decision(action, float(log_probs[0, action]), float(value[0]), self.version)
