"""Terminal-only round reward and versioned, append-only decision traces."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable
import json
import math
import numbers
import threading
from .contracts import Decision, Observation, player_index, action_keys

def round_reward(remaining_hps: list[int], player: bool) -> float:
    idx = player_index(player)
    if len(remaining_hps) != 2:
        raise ValueError("RoundResult must contain two HP values")
    if any(not isinstance(hp, numbers.Integral) or isinstance(hp, bool) for hp in remaining_hps):
        raise ValueError("HP values must be integers")
    hp = [max(0, int(x)) for x in remaining_hps]
    return float((hp[idx] > hp[1-idx]) - (hp[idx] < hp[1-idx]))

class JsonlSink:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def __call__(self, item: dict[str, Any]) -> None:
        line = json.dumps(item, ensure_ascii=False, allow_nan=False)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

class RoundLedger:
    def __init__(self, sink: Callable[[dict[str, Any]], None]):
        self.sink = sink
        self.records: list[dict[str, Any]] = []
        self.round_id: int | None = None
        self.player: bool | None = None
        self.opponent_version = ""
        self.match_id = ""
        self._finished: set[tuple[str, int, bool]] = set()
        self.completed = 0

    def begin(self, match_id: str, round_id: int, player: bool, opponent_version: str) -> None:
        player_index(player)
        if self.round_id is not None:
            raise RuntimeError("Cannot begin before ending/aborting the previous round")
        if not match_id or not opponent_version or round_id < 0:
            raise ValueError("Incomplete round identity")
        if (match_id, round_id, player) in self._finished:
            raise RuntimeError("Round identity reused")
        self.match_id, self.round_id, self.player = match_id, round_id, player
        self.opponent_version, self.records = opponent_version, []

    def append(self, obs: Observation, choice: Decision) -> None:
        if self.round_id != obs.round_id:
            raise RuntimeError("Observation belongs to another round")
        if self.records and obs.frame <= self.records[-1]["frame"]:
            raise ValueError("Frames must strictly increase within a round")
        if self.records and choice.policy_version != self.records[0]["policy_version"]:
            raise RuntimeError("Updating the policy during a round is prohibited")
        self.records.append({"frame": obs.frame, "observation": obs.vector.tolist(),
                             "action": int(choice.action), "log_prob": choice.log_prob,
                             "value": choice.value, "policy_version": choice.policy_version,
                             "reward": 0.0, "facing_right": bool(obs.facing_right),
                             "requested_keys": action_keys(choice.action, obs.facing_right)})

    def finish(self, match_id: str, round_id: int, player: bool,
               remaining_hps: list[int], elapsed_frame: int) -> bool:
        player_index(player)
        key = (match_id, round_id, player)
        if key in self._finished:
            return False
        if self.round_id != round_id or self.player is not player or self.match_id != match_id:
            raise RuntimeError("Mismatched terminal event; never silently attach it")
        if elapsed_frame <= 0 or (self.records and elapsed_frame < self.records[-1]["frame"]):
            raise ValueError("Invalid terminal frame")
        reward = round_reward(remaining_hps, player)
        if self.records:
            self.records[-1]["reward"] = reward
        payload = {"kind": "round", "match_id": match_id, "round_id": round_id,
                   "player_index": player_index(player), "opponent_version": self.opponent_version,
                   "remaining_hps": list(map(int, remaining_hps)), "elapsed_frame": elapsed_frame,
                   "outcome_reward": reward, "terminated": True, "truncated": False,
                   "trainable": bool(self.records), "transitions": self.records}
        self.sink(payload)
        self._finished.add(key)
        self.completed += 1
        self.round_id, self.records = None, []
        return True

    def abort(self, reason: str) -> None:
        if self.round_id is None:
            return
        self.sink({"kind": "aborted_round", "match_id": self.match_id, "round_id": self.round_id,
                   "reason": reason, "terminated": False, "truncated": True,
                   "trainable": False, "outcome_reward": None,
                   "n_decisions": len(self.records)})
        self.round_id, self.records = None, []

def terminal_returns(rewards: list[float], gamma: float = 1.0) -> list[float]:
    if not 0 < gamma <= 1 or any(not math.isfinite(x) for x in rewards):
        raise ValueError("Invalid discount or reward")
    result, acc = [], 0.0
    for reward in reversed(rewards):
        acc = reward + gamma * acc
        result.append(acc)
    return result[::-1]
