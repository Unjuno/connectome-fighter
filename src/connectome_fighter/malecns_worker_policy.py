"""Policy client for a persistent per-character MaleCNS + Shiu LIF worker."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import numpy as np

from .contracts import Decision
from .malecns_trace import DynamicsIdentity, InterfaceIdentity, MaleCNSTraceWriter


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


class MaleCNSWorkerPolicy:
    """FightingICE policy backed by a real-body-ID Shiu LIF worker.

    The worker contains the recurrent neural simulation. This client has no
    trainable artificial neural network; it only forwards observations and
    records returned spikes/actions/provenance.
    """

    def __init__(
        self,
        *,
        character: str,
        seed: int,
        version: str,
        python_executable: str,
        worker_script: str | Path,
        reference_model: str | Path,
        adapter_dir: str | Path,
        interface_path: str | Path,
        trace_root: str | Path,
        run_id: str,
    ) -> None:
        self.character = str(character)
        self.seed = int(seed)
        self.version = str(version)
        self.adapter_dir = Path(adapter_dir)
        self.interface_path = Path(interface_path)
        self.trace_root = Path(trace_root)
        self.trace_root.mkdir(parents=True, exist_ok=True)
        self._stderr_path = self.trace_root / "worker-stderr.log"
        self._stderr_handle = self._stderr_path.open("w", encoding="utf-8")
        cmd = [
            str(python_executable), str(worker_script),
            "--reference-model", str(reference_model),
            "--adapter-dir", str(adapter_dir),
            "--interface", str(interface_path),
            "--seed", str(seed),
            "--character", self.character,
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr_handle,
            text=True,
            bufsize=1,
        )
        if self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("Failed to create MaleCNS worker pipes")
        line = self._proc.stdout.readline()
        if not line:
            self._proc.wait(timeout=10)
            raise RuntimeError(f"MaleCNS worker exited before ready; see {self._stderr_path}")
        ready = json.loads(line)
        if ready.get("kind") != "ready":
            raise RuntimeError(f"Unexpected MaleCNS worker greeting: {ready}")
        self._ready = ready

        structural = json.loads((self.adapter_dir / "manifest.json").read_text(encoding="utf-8"))
        interface = json.loads(self.interface_path.read_text(encoding="utf-8"))
        dynamics = DynamicsIdentity(
            model_name="Shiu-LIF-on-MaleCNS-v1",
            source_doi="10.1038/s41586-024-07763-9",
            source_code=(
                "https://github.com/philshiu/Drosophila_brain_model/commit/"
                + structural["shiu_reference_commit"]
            ),
            parameter_set={
                **ready["parameters"],
                "adapter": structural["adapter"],
                "min_connection_weight": structural["min_connection_weight"],
                "histamine_mode": structural["histamine_mode"],
            },
        )
        interface_identity = InterfaceIdentity(
            version=interface["interface_id"],
            observation_contract="connectome_fighter.observations:v1",
            sensory_mapping_sha256=_stable_hash(interface["input"]),
            output_mapping_sha256=_stable_hash(interface["output"]),
        )
        dataset_hashes = {
            **{f"source_{k}": v for k, v in structural["source_hashes"].items()},
            **{f"adapter_{k}": v for k, v in structural["output_hashes"].items()},
            "interface_sha256": interface["interface_sha256"],
        }
        self._trace = MaleCNSTraceWriter(
            self.trace_root,
            run_id=run_id,
            character=self.character,
            dataset_id=structural["dataset"],
            dataset_hashes=dataset_hashes,
            dynamics=dynamics,
            interface=interface_identity,
            rng_seed=self.seed,
            initial_state_sha256=ready["initial_state_sha256"],
        )
        self._context_frame: int | None = None
        self._context_round: int | None = None
        self._decision_index = 0
        self._last_telemetry: dict[str, Any] | None = None
        self._closed = False

    def _rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("MaleCNS worker policy is closed")
        assert self._proc.stdin is not None and self._proc.stdout is not None
        self._proc.stdin.write(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")
        self._proc.stdin.flush()
        line = self._proc.stdout.readline()
        if not line:
            rc = self._proc.poll()
            raise RuntimeError(f"MaleCNS worker terminated unexpectedly (rc={rc}); see {self._stderr_path}")
        response = json.loads(line)
        if response.get("kind") == "error":
            raise RuntimeError(response.get("error", "MaleCNS worker error"))
        return response

    def set_context(self, *, frame: int, round_id: int) -> None:
        self._context_frame = int(frame)
        self._context_round = int(round_id)

    def reset(self) -> None:
        self._last_telemetry = None
        if not self._closed:
            self._rpc({"command": "reset"})

    def act(self, observation: np.ndarray) -> Decision:
        if self._context_frame is None:
            raise RuntimeError("MaleCNS policy did not receive decision frame context")
        obs = np.asarray(observation, dtype=np.float32)
        if obs.shape != (18,) or not np.isfinite(obs).all():
            raise ValueError("MaleCNS policy expects finite observation[18]")
        response = self._rpc({"command": "act", "observation": obs.astype(float).tolist()})
        if response.get("kind") != "decision":
            raise RuntimeError(f"Unexpected MaleCNS worker response: {response}")

        action = int(response["action"])
        sensory_drive = [(int(body), float(rate)) for body, rate in response["sensory_drive"]]
        output_contributions = [
            (str(group), int(body), float(value))
            for group, body, value in response["output_contributions"]
        ]
        self._trace.append_decision(
            decision_index=self._decision_index,
            frame=self._context_frame,
            biological_time_start_ms=float(response["biological_time_start_ms"]),
            biological_time_end_ms=float(response["biological_time_end_ms"]),
            observation=obs.tolist(),
            action=action,
            sensory_drive=sensory_drive,
            output_contributions=output_contributions,
            membrane_summary={str(k): float(v) for k, v in response["membrane_summary"].items()},
        )
        spike_events = [(float(t), int(body)) for t, body in response["spikes"]]
        self._trace.append_spikes(
            decision_index=self._decision_index,
            events=spike_events,
        )
        unique_bodies = len({body for _, body in spike_events})
        self._last_telemetry = {
            "canonical_model": "male-cns:v1.0 + pinned Shiu LIF",
            "character": self.character,
            "round_id": self._context_round,
            "biological_time_start_ms": response["biological_time_start_ms"],
            "biological_time_end_ms": response["biological_time_end_ms"],
            "total_spikes": int(response["total_spikes"]),
            "unique_spike_bodies": int(unique_bodies),
            "group_spike_counts": response["group_spike_counts"],
            "top_spike_bodies": response["top_spike_bodies"],
            "membrane_summary": response["membrane_summary"],
            "trace_decision_index": self._decision_index,
        }
        self._decision_index += 1
        return Decision(action=action, log_prob=0.0, value=0.0, policy_version=self.version)

    def telemetry(self) -> dict[str, Any] | None:
        return self._last_telemetry

    def close(self) -> None:
        if self._closed:
            return
        try:
            try:
                self._rpc({"command": "close"})
            except Exception:
                pass
            if self._proc.poll() is None:
                try:
                    self._proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait(timeout=5)
        finally:
            self._trace.close()
            self._stderr_handle.close()
            self._closed = True

    @property
    def worker_ready(self) -> dict[str, Any]:
        return dict(self._ready)
