"""Analysis-first trace format for the canonical MaleCNS simulator.

The format deliberately separates immutable structural metadata from dynamic
neural events. Dynamic logs refer to real MaleCNS body IDs and never replace
those IDs with learned latent units.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

TRACE_SCHEMA = 1


def _stable_json_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _finite(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True)
class DynamicsIdentity:
    model_name: str
    source_doi: str
    source_code: str
    parameter_set: dict[str, Any]

    def fingerprint(self) -> str:
        return _stable_json_hash(asdict(self))


@dataclass(frozen=True)
class InterfaceIdentity:
    version: str
    observation_contract: str
    sensory_mapping_sha256: str
    output_mapping_sha256: str

    def fingerprint(self) -> str:
        return _stable_json_hash(asdict(self))


class MaleCNSTraceWriter:
    """Write event-compressed canonical run evidence.

    Files written beneath ``root``:
      * run-manifest.json: provenance and deterministic simulation identity
      * decisions.jsonl: game state, input drive, output contribution, action
      * spikes.parquet: one row per spike event, keyed by real MaleCNS body ID

    Static body annotations are not duplicated here. The run manifest pins the
    source annotation hash so offline analysis can join body IDs losslessly.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        run_id: str,
        character: str,
        dataset_id: str,
        dataset_hashes: dict[str, str],
        dynamics: DynamicsIdentity,
        interface: InterfaceIdentity,
        rng_seed: int,
        initial_state_sha256: str,
    ) -> None:
        if not run_id or not character or not dataset_id:
            raise ValueError("run_id, character and dataset_id are required")
        if not dataset_hashes or any(not k or not v for k, v in dataset_hashes.items()):
            raise ValueError("dataset hashes must be non-empty")
        if rng_seed < 0 or not initial_state_sha256:
            raise ValueError("invalid RNG seed or initial-state hash")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.decisions_path = self.root / "decisions.jsonl"
        self.spikes_path = self.root / "spikes.parquet"
        self._spike_rows: list[dict[str, Any]] = []
        self._last_decision = -1
        self._closed = False
        manifest = {
            "schema_version": TRACE_SCHEMA,
            "run_id": run_id,
            "character": character,
            "dataset": dataset_id,
            "dataset_hashes": dict(sorted(dataset_hashes.items())),
            "dynamics": {
                **asdict(dynamics),
                "sha256": dynamics.fingerprint(),
            },
            "interface": {
                **asdict(interface),
                "sha256": interface.fingerprint(),
            },
            "rng_seed": int(rng_seed),
            "initial_state_sha256": initial_state_sha256,
            "dynamic_identity": "real MaleCNS body IDs; no learned latent neuron IDs",
        }
        (self.root / "run-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    def append_decision(
        self,
        *,
        decision_index: int,
        frame: int,
        biological_time_start_ms: float,
        biological_time_end_ms: float,
        observation: Iterable[float],
        action: int,
        sensory_drive: Iterable[tuple[int, float]],
        output_contributions: Iterable[tuple[str, int, float]],
        membrane_summary: dict[str, float],
    ) -> None:
        if self._closed:
            raise RuntimeError("trace writer is closed")
        if decision_index != self._last_decision + 1:
            raise ValueError("decision_index must be contiguous")
        if frame < 0 or action < 0:
            raise ValueError("frame/action must be non-negative")
        start = _finite(biological_time_start_ms, "biological_time_start_ms")
        end = _finite(biological_time_end_ms, "biological_time_end_ms")
        if end <= start:
            raise ValueError("biological decision window must have positive duration")
        obs = [_finite(x, "observation") for x in observation]
        drive = [
            {"body_id": int(body), "drive": _finite(value, "sensory drive")}
            for body, value in sensory_drive
        ]
        if any(x["body_id"] <= 0 for x in drive):
            raise ValueError("MaleCNS body IDs must be positive")
        outputs = [
            {
                "group": str(group),
                "body_id": int(body),
                "contribution": _finite(value, "output contribution"),
            }
            for group, body, value in output_contributions
        ]
        if any(not x["group"] or x["body_id"] <= 0 for x in outputs):
            raise ValueError("invalid output contribution identity")
        membrane = {str(k): _finite(v, f"membrane_summary[{k}]") for k, v in membrane_summary.items()}
        row = {
            "schema_version": TRACE_SCHEMA,
            "decision_index": int(decision_index),
            "frame": int(frame),
            "biological_time_start_ms": start,
            "biological_time_end_ms": end,
            "observation": obs,
            "action": int(action),
            "sensory_drive": drive,
            "output_contributions": outputs,
            "membrane_summary": membrane,
        }
        with self.decisions_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
        self._last_decision = decision_index

    def append_spikes(
        self,
        *,
        decision_index: int,
        events: Iterable[tuple[float, int]],
    ) -> None:
        if self._closed:
            raise RuntimeError("trace writer is closed")
        if decision_index < 0 or decision_index > self._last_decision:
            raise ValueError("spikes must reference an emitted decision window")
        for time_ms, body_id in events:
            time_ms = _finite(time_ms, "spike time")
            body_id = int(body_id)
            if time_ms < 0 or body_id <= 0:
                raise ValueError("invalid spike event")
            self._spike_rows.append({
                "decision_index": int(decision_index),
                "time_ms": time_ms,
                "body_id": body_id,
            })

    def close(self) -> None:
        if self._closed:
            return
        df = pd.DataFrame(self._spike_rows, columns=["decision_index", "time_ms", "body_id"])
        if not df.empty:
            df = df.astype({"decision_index": "int32", "time_ms": "float32", "body_id": "int64"})
            df.sort_values(["decision_index", "time_ms", "body_id"], inplace=True, kind="stable")
        df.to_parquet(self.spikes_path, index=False, compression="zstd")
        self._closed = True

    def __enter__(self) -> "MaleCNSTraceWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
