"""Sparse graph-constrained recurrent model; NOT a reproduction of Shiu LIF.

The anatomical graph can be real. The sigmoid dynamics, artificial game-to-
sensory routing, and gradient learning are modelling assumptions. All states
and drives are dimensionless.
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
        indices = torch.tensor(np.stack([graph.dst, graph.src]), dtype=torch.int64)
        base = torch.tensor(graph.magnitude.copy(), dtype=torch.float32) * gain
        sign = torch.tensor(graph.sign.copy(), dtype=torch.float32)
        self.register_buffer("indices", indices)
        self.register_buffer("base", base)
        self.register_buffer("sign", sign)
        if plastic:
            self.theta = nn.Parameter(torch.zeros(graph.n_edges, dtype=torch.float32))
            self.register_buffer("static_matrix", None)
        else:
            self.register_parameter("theta", None)
            # Coalescing millions of edges is expensive. A fixed-connectome
            # condition must pay this cost once, not once per neural update.
            static = torch.sparse_coo_tensor(
                indices, sign * base, (self.n_nodes, self.n_nodes)
            ).coalesce()
            self.register_buffer("static_matrix", static)

    def weights(self) -> torch.Tensor:
        factor = 1.0 if self.theta is None else 2 * torch.sigmoid(self.theta)
        return self.sign * self.base * factor

    def matrix(self) -> torch.Tensor:
        if self.theta is None:
            return self.static_matrix
        return torch.sparse_coo_tensor(
            self.indices, self.weights(), (self.n_nodes, self.n_nodes)
        ).coalesce()

    def forward(self, drive: torch.Tensor, state: torch.Tensor) -> torch.Tensor:
        if drive.shape != state.shape or state.ndim != 2 or state.shape[-1] != self.n_nodes:
            raise ValueError("Expected drive and state of shape [batch, n_nodes]")
        recurrent = torch.sparse.mm(self.matrix(), state.T).T
        return (1-self.leak)*state + self.leak*torch.sigmoid(recurrent+drive)


class FixedRouting(nn.Module):
    """Explicit artificial game-feature -> selected sensory-neuron routing."""
    def __init__(self, n_nodes: int, input_nodes: list[int], *,
                 input_features: list[int] | None = None,
                 input_polarities: list[int] | None = None,
                 input_scale: float = 0.25,
                 obs_dim: int = OBS_DIM):
        super().__init__()
        if (not input_nodes or len(set(input_nodes)) != len(input_nodes)
            or min(input_nodes) < 0 or max(input_nodes) >= n_nodes):
            raise ValueError("Invalid unique input-node list")
        if not np.isfinite(input_scale) or input_scale <= 0:
            raise ValueError("input_scale must be finite and positive")
        if input_features is None:
            input_features = [i % obs_dim for i in range(len(input_nodes))]
        if input_polarities is None:
            input_polarities = [1] * len(input_nodes)
        if not (len(input_nodes) == len(input_features) == len(input_polarities)):
            raise ValueError("Routing arrays must have equal length")
        if any(type(x) is not int or not 0 <= x < obs_dim for x in input_features):
            raise ValueError("Invalid feature index")
        if any(x not in (-1, 1) for x in input_polarities):
            raise ValueError("Polarity must be +1 or -1")
        self.n_nodes, self.obs_dim, self.input_scale = n_nodes, obs_dim, float(input_scale)
        self.register_buffer("nodes", torch.tensor(input_nodes, dtype=torch.int64))
        self.register_buffer("features", torch.tensor(input_features, dtype=torch.int64))
        self.register_buffer("polarities", torch.tensor(input_polarities, dtype=torch.float32))

    def forward(self, observation: torch.Tensor) -> torch.Tensor:
        if observation.ndim != 2 or observation.shape[-1] != self.obs_dim:
            raise ValueError("Unexpected observation shape")
        drive = observation.new_zeros((observation.shape[0], self.n_nodes))
        # Half-wave coding: polarity + receives max(x,0), polarity - receives max(-x,0).
        values = torch.relu(observation[:, self.features] * self.polarities) * self.input_scale
        return drive.index_add(1, self.nodes, values)


class ConnectomeActorCritic(nn.Module):
    def __init__(self, graph: Graph, input_nodes: list[int], output_nodes: list[int], *,
                 input_features: list[int] | None = None,
                 input_polarities: list[int] | None = None,
                 input_scale: float = 0.25,
                 plastic: bool = False, gain: float = 0.1, leak: float = 0.5,
                 neural_steps: int = 4):
        super().__init__()
        if (not output_nodes or len(set(output_nodes)) != len(output_nodes)
            or min(output_nodes) < 0 or max(output_nodes) >= graph.n_nodes
            or set(input_nodes) & set(output_nodes) or neural_steps <= 0):
            raise ValueError("Use unique, valid, disjoint input/output nodes and positive steps")
        self.core = SparseGraphCore(graph, plastic=plastic, gain=gain, leak=leak)
        self.routing = FixedRouting(
            graph.n_nodes, input_nodes, input_features=input_features,
            input_polarities=input_polarities, input_scale=input_scale
        )
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
        x = torch.tensor(np.array(observation, copy=True), dtype=torch.float32,
                         device=self.state.device).unsqueeze(0)
        logits, value, self.state = self.model(x, self.state)
        log_probs = torch.log_softmax(logits, dim=-1)
        action = int(torch.multinomial(log_probs.exp(), 1, generator=self.generator).item())
        return Decision(action, float(log_probs[0, action]), float(value[0]), self.version)
