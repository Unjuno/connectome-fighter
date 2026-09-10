"""Optional live adapter, written against pyftg 2.3 public source.

Not yet end-to-end validated against the external pyftg/Java game server.
"""
from __future__ import annotations
import time
from typing import Any, Callable
from .contracts import Policy
from .observations import encode_frame, ObservationScales
from .session import Session
from .trajectory import RoundLedger

try:
    from pyftg import AIInterface, Key
except ImportError as exc:
    raise ImportError("Live bridge requires pyftg==2.3. Install .[game] in Python 3.11 first.") from exc

class FighterAI(AIInterface):
    def __init__(self, agent_name: str, policy: Policy, sink: Callable[[dict[str, Any]], None],
                 match_id: str, opponent_version: str, decision_interval: int = 4,
                 scales: ObservationScales = ObservationScales()):
        self.agent_name, self.policy = agent_name, policy
        self.ledger = RoundLedger(sink)
        self.match_prefix, self.opponent_version = match_id, opponent_version
        self.interval, self.scales = decision_interval, scales
        self.initializations = 0
        self.session: Session | None = None
        self.frame_data = None
        self.key = Key()
        self.inference_ns: list[int] = []

    def name(self) -> str:
        return self.agent_name

    def is_blind(self) -> bool:
        return False

    def initialize(self, game_data, player_number: bool):
        if self.session:
            self.session.close("reinitialize")
        self.initializations += 1
        self.game_data = game_data
        self.session = Session(self.policy, self.ledger, player_number,
                               f"{self.match_prefix}-{self.initializations}",
                               self.opponent_version, self.interval)
        self.frame_data, self.key = None, Key()

    def get_information(self, frame_data, is_control: bool):
        self.frame_data = frame_data

    def get_non_delay_frame_data(self, frame_data):
        pass

    def get_screen_data(self, screen_data):
        pass

    def get_audio_data(self, audio_data):
        pass

    def processing(self):
        if self.session is None or self.frame_data is None:
            self.key = Key()
            return
        started = time.perf_counter_ns()
        observation = encode_frame(self.frame_data, self.game_data, self.session.player, self.scales)
        keys = self.session.process(observation)
        self.key = Key(**keys)
        self.inference_ns.append(time.perf_counter_ns()-started)

    def input(self):
        return self.key

    def round_end(self, round_result):
        if self.session is None:
            raise RuntimeError("Terminal event before initialization")
        self.session.finish(int(round_result.current_round), list(round_result.remaining_hps),
                            int(round_result.elapsed_frame))
        self.frame_data, self.key = None, Key()

    def game_end(self):
        if self.session:
            self.session.close("game_end_without_round_result")

    def close(self):
        if self.session:
            self.session.close()
