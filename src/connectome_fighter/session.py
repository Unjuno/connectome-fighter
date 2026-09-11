"""Callback state machine, independent of Java and pyftg."""
from __future__ import annotations
from typing import Any
from .contracts import Policy, Observation, Action, action_keys, player_index
from .trajectory import RoundLedger


class Session:
    def __init__(self, policy: Policy, ledger: RoundLedger, player: bool,
                 match_id: str, opponent_version: str, decision_interval: int = 4):
        player_index(player)
        if decision_interval <= 0:
            raise ValueError("decision_interval must be positive")
        self.policy, self.ledger, self.player = policy, ledger, player
        self.match_id, self.opponent_version = match_id, opponent_version
        self.interval = decision_interval
        self.current_round: int | None = None
        self.last_seen = -1
        self.last_decision = -1
        self.keys = action_keys(Action.NEUTRAL, True)
        self.frame_gaps = 0

    def process(self, obs: Observation | None, *, display: dict[str, Any] | None = None) -> dict[str, bool]:
        if obs is None:
            self.keys = action_keys(Action.NEUTRAL, True)
            return self.keys.copy()
        if obs.round_id != self.current_round:
            self.ledger.abort("new_round_without_terminal_event")
            self.policy.reset()
            self.ledger.begin(self.match_id, obs.round_id, self.player, self.opponent_version)
            self.current_round = obs.round_id
            self.last_seen, self.last_decision = -1, -1
            self.keys = action_keys(Action.NEUTRAL, obs.facing_right)
        if obs.frame == self.last_seen:
            return self.keys.copy()
        if obs.frame < self.last_seen:
            raise RuntimeError("Frame number regressed within a round")
        if self.last_seen >= 0:
            self.frame_gaps += max(0, obs.frame-self.last_seen-1)
        self.last_seen = obs.frame
        if self.last_decision < 0 or obs.frame-self.last_decision >= self.interval:
            decision = self.policy.act(obs.vector)
            telemetry = None
            telemetry_fn = getattr(self.policy, "telemetry", None)
            if callable(telemetry_fn):
                telemetry = telemetry_fn()
            self.ledger.append(obs, decision, brain=telemetry, display=display)
            self.last_decision = obs.frame
            self.keys = action_keys(decision.action, obs.facing_right)
        return self.keys.copy()

    def finish(self, round_id: int, hps: list[int], elapsed_frame: int) -> bool:
        if self.current_round is None and self.ledger.round_id is None:
            if (self.match_id, round_id, self.player) not in self.ledger._finished:
                self.ledger.begin(self.match_id, round_id, self.player, self.opponent_version)
        done = self.ledger.finish(self.match_id, round_id, self.player, hps, elapsed_frame)
        if done:
            self.keys = action_keys(Action.NEUTRAL, True)
            self.current_round, self.last_seen, self.last_decision = None, -1, -1
            self.policy.reset()
        return done

    def close(self, reason: str = "connection_closed_without_terminal_event") -> None:
        self.ledger.abort(reason)
        self.keys = action_keys(Action.NEUTRAL, True)
