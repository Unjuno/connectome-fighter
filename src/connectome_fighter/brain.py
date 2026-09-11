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
            static = torch.sparse_coo_tensor(
                indices, sign * base, (self.n_nodes, self.n_nodes)
            ).coalesce()
            self.register_buffer("static_matrix", static)

    @property
    def plastic(self) -> bool:
        return self.theta is not None

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
        values = torch.relu(observation[:, self.features] * self.polarities) * self.input_scale
        return drive.index_add(1, self.nodes, values)


class ConnectomeActorCritic(nn.Module):
    def __init__(self, graph: Graph, input_nodes: list[int], output_nodes: list[int], *,
                 input_features: list[int] | None = None,
                 input_polarities: list[int] | None = None,
                 input_scale: float = 0.25,
                 plastic: bool = False, gain: float = 0.1, leak: float = 0.5,
                 neural_steps: int = 4,
                 shared_core: SparseGraphCore | None = None):
        super().__init__()
        if (not output_nodes or len(set(output_nodes)) != len(output_nodes)
            or min(output_nodes) < 0 or max(output_nodes) >= graph.n_nodes
            or set(input_nodes) & set(output_nodes) or neural_steps <= 0):
            raise ValueError("Use unique, valid, disjoint input/output nodes and positive steps")
        if shared_core is None:
            self.core = SparseGraphCore(graph, plastic=plastic, gain=gain, leak=leak)
        else:
            if shared_core.n_nodes != graph.n_nodes or shared_core.graph_hash != graph.fingerprint():
                raise ValueError("Shared core does not match graph")
            if shared_core.plastic:
                raise ValueError("A mutable/plastic core must not be shared between competing agents")
            if plastic:
                raise ValueError("plastic=True conflicts with immutable shared_core")
            self.core = shared_core
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
    """Inference wrapper with private recurrent state and activity telemetry."""
    def __init__(self, model: ConnectomeActorCritic, version: str, seed: int = 0,
                 *, node_ids: tuple[str, ...] | None = None,
                 node_positions: np.ndarray | None = None,
                 brain_bounds: tuple[np.ndarray, np.ndarray] | None = None,
                 coordinate_space: str | None = None,
                 activity_top_k: int = 12):
        if not version:
            raise ValueError("Policy version is required")
        if activity_top_k <= 0:
            raise ValueError("activity_top_k must be positive")
        if node_ids is not None and len(node_ids) != model.core.n_nodes:
            raise ValueError("node_ids length does not match model")
        if node_positions is not None:
            node_positions = np.asarray(node_positions, dtype=np.float32)
            if node_positions.shape != (model.core.n_nodes, 3):
                raise ValueError("node_positions must have shape [n_nodes, 3]")
        self.model, self.version = model.eval(), version
        self.node_ids = node_ids
        self.node_positions = node_positions
        self.activity_top_k = int(activity_top_k)
        self.brain_space = None
        if brain_bounds is not None:
            lo, hi = (np.asarray(x, dtype=np.float32) for x in brain_bounds)
            if lo.shape != (3,) or hi.shape != (3,) or not np.all(np.isfinite(lo)) or not np.all(np.isfinite(hi)):
                raise ValueError("Invalid brain coordinate bounds")
            self.brain_space = {
                "bounds_min": lo.tolist(),
                "bounds_max": hi.tolist(),
                "coordinate_space": coordinate_space or "FlyWire annotation coordinates",
            }
        device = next(model.parameters()).device
        self.generator = torch.Generator(device=device).manual_seed(seed)
        self._last_telemetry: dict | None = None
        self.reset()

    def reset(self):
        self.state = self.model.core.base.new_zeros((1, self.model.core.n_nodes))
        self._last_telemetry = None

    def _node_item(self, idx: int, value: float) -> dict:
        item = {"node_index": int(idx), "value": float(value)}
        if self.node_ids is not None:
            item["node_id"] = self.node_ids[idx]
        if self.node_positions is not None:
            position = self.node_positions[idx]
            if bool(np.isfinite(position).all()):
                item["position"] = [float(x) for x in position]
        return item

    @torch.no_grad()
    def act(self, observation: np.ndarray) -> Decision:
        x = torch.tensor(np.array(observation, copy=True), dtype=torch.float32,
                         device=self.state.device).unsqueeze(0)
        previous_state = self.state
        logits, value, self.state = self.model(x, self.state)
        log_probs = torch.log_softmax(logits, dim=-1)
        action = int(torch.multinomial(log_probs.exp(), 1, generator=self.generator).item())

        readout = self.state[0, self.model.output_nodes]
        k = min(self.activity_top_k, self.state.shape[-1])
        top_values, top_indices = torch.topk(self.state[0], k=k)
        top = [self._node_item(idx, val) for idx, val in zip(top_indices.tolist(), top_values.tolist())]

        # Positive state change is a clearer spectator signal than absolute state
        # alone: it highlights neurons most activated by this decision interval.
        delta = self.state[0] - previous_state[0]
        delta_values, delta_indices = torch.topk(delta, k=k)
        top_change = [
            self._node_item(idx, val)
            for idx, val in zip(delta_indices.tolist(), delta_values.tolist())
            if val > 0
        ]

        dk = min(self.activity_top_k, readout.numel())
        desc_values, desc_local = torch.topk(readout, k=dk)
        output_nodes = self.model.output_nodes.tolist()
        descending = [
            self._node_item(int(output_nodes[local_idx]), val)
            for local_idx, val in zip(desc_local.tolist(), desc_values.tolist())
        ]
        activation = {
            "mean": float(self.state.mean()),
            "max": float(self.state.max()),
            "fraction_gt_0_75": float((self.state > 0.75).float().mean()),
            "top_global": top,
            "top_change": top_change,
            "top_descending": descending,
        }
        if self.brain_space is not None:
            activation["brain_space"] = self.brain_space
        self._last_telemetry = {
            # These fixed-connectome features are the sufficient input for the
            # trainable actor/critic heads in PPO-readout-v1.
            "readout_features": readout.to(dtype=torch.float32).cpu().tolist(),
            "activation": activation,
        }
        return Decision(action, float(log_probs[0, action]), float(value[0]), self.version)

    def telemetry(self) -> dict | None:
        return self._last_telemetry
