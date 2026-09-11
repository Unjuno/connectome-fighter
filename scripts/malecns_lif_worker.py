"""Persistent JSON-line worker for one MaleCNS + pinned Shiu LIF brain.

The recurrent neural dynamics are created by the upstream Shiu `model.py`
reference implementation. This worker only adds the explicitly artificial game
interface: variable-rate Poisson sources into selected sensory bodies and a
spike-count readout over selected descending/motor bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from brian2 import (
    Hz, Network, PoissonGroup, Synapses, mV, ms, prefs,
    seed as brian_seed, start_scope,
)

ACTIVE_ACTIONS = ["FORWARD", "BACKWARD", "UP", "DOWN", "A", "B", "C"]


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def load_reference(path: Path):
    spec = importlib.util.spec_from_file_location("pinned_shiu_model", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import reference model: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-model", type=Path, required=True)
    p.add_argument("--adapter-dir", type=Path, required=True)
    p.add_argument("--interface", type=Path, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--character", required=True)
    p.add_argument("--codegen-target", choices=["cython", "numpy"], default="cython")
    args = p.parse_args()

    prefs.codegen.target = args.codegen_target
    interface = json.loads(args.interface.read_text(encoding="utf-8"))
    structural = json.loads((args.adapter_dir / "manifest.json").read_text(encoding="utf-8"))
    completeness = pd.read_csv(args.adapter_dir / "completeness.csv", index_col=0)
    body_ids = completeness.index.to_numpy(dtype=np.int64, copy=True)
    if len(body_ids) != structural["counts"]["included_neurons"]:
        raise ValueError("Completeness table/manifest neuron count mismatch")

    input_indices: list[int] = []
    input_features: list[int] = []
    input_polarities: list[int] = []
    input_body_ids: list[int] = []
    for channel in interface["input"]["channels"]:
        for body, idx in zip(channel["body_ids"], channel["shiu_indices"]):
            input_body_ids.append(int(body))
            input_indices.append(int(idx))
            input_features.append(int(channel["feature_index"]))
            input_polarities.append(int(channel["polarity"]))
    if len(input_indices) != len(set(input_indices)):
        raise ValueError("Input target neurons must be unique")

    output_action = np.full(len(body_ids), -1, dtype=np.int8)
    output_group_name: dict[int, str] = {}
    for action_offset, name in enumerate(ACTIVE_ACTIONS, start=1):
        group = interface["output"]["groups"][name]
        for idx in group["shiu_indices"]:
            idx = int(idx)
            if output_action[idx] != -1:
                raise ValueError("Output body assigned to multiple actions")
            output_action[idx] = action_offset
            output_group_name[idx] = name

    reference = load_reference(args.reference_model)
    start_scope()
    brian_seed(args.seed)
    params = reference.default_params
    neu, recurrent_syn, spike_monitor = reference.create_model(
        args.adapter_dir / "completeness.csv",
        args.adapter_dir / "connectivity.parquet",
        params,
    )
    if len(neu) != len(body_ids):
        raise ValueError("Reference model neuron count mismatch")

    # Match Shiu `poi()` semantics for stimulated targets: target refractory is
    # disabled and each Poisson event changes v by w_syn*f_poi. Only event rate
    # is generalized here from fixed 150 Hz to an observation-driven [0,150] Hz.
    input_index_array = np.asarray(input_indices, dtype=np.int64)
    neu.rfc[input_index_array] = 0 * ms
    n_inputs = len(input_indices)
    poisson = PoissonGroup(n_inputs, rates=np.zeros(n_inputs) * Hz, name="game_poisson_input")
    input_syn = Synapses(
        poisson, neu, model="w : volt", on_pre="v_post += w", name="game_poisson_synapses"
    )
    input_syn.connect(i=np.arange(n_inputs), j=input_index_array)
    input_syn.w = params["w_syn"] * params["f_poi"]

    net = Network(neu, recurrent_syn, spike_monitor, poisson, input_syn)
    poisson.rates = np.zeros(n_inputs) * Hz
    net.store("baseline")

    max_rate_hz = float(interface["input"]["max_poisson_rate_hz"])
    window_ms = float(interface["decision"]["window_ms"])
    neutral_min = int(interface["decision"]["neutral_min_spikes"])
    input_features_arr = np.asarray(input_features, dtype=np.int64)
    input_polarities_arr = np.asarray(input_polarities, dtype=np.float64)
    input_body_ids_arr = np.asarray(input_body_ids, dtype=np.int64)
    reset_count = 0

    parameters = {
        "v_0_mV": float(params["v_0"] / mV),
        "v_rst_mV": float(params["v_rst"] / mV),
        "v_th_mV": float(params["v_th"] / mV),
        "t_mbr_ms": float(params["t_mbr"] / ms),
        "tau_ms": float(params["tau"] / ms),
        "t_rfc_ms": float(params["t_rfc"] / ms),
        "t_dly_ms": float(params["t_dly"] / ms),
        "w_syn_mV": float(params["w_syn"] / mV),
        "f_poi": int(params["f_poi"]),
        "stimulated_target_rfc_ms": 0.0,
        "codegen_target": str(prefs.codegen.target),
    }
    initial_identity = {
        "dataset": structural["dataset"],
        "structural_output_hashes": structural["output_hashes"],
        "reference_commit": structural["shiu_reference_commit"],
        "parameters": parameters,
        "character": args.character,
        "seed": args.seed,
    }
    emit({
        "kind": "ready",
        "character": args.character,
        "neurons": len(neu),
        "synapses": len(recurrent_syn),
        "interface_sha256": interface["interface_sha256"],
        "parameters": parameters,
        "initial_state_sha256": stable_hash(initial_identity),
    })

    for raw_line in sys.stdin:
        if not raw_line.strip():
            continue
        request = json.loads(raw_line)
        command = request.get("command")
        if command == "close":
            emit({"kind": "closed"})
            return 0
        if command == "reset":
            net.restore("baseline")
            reset_count += 1
            brian_seed(args.seed + reset_count)
            poisson.rates = np.zeros(n_inputs) * Hz
            emit({"kind": "reset", "reset_count": reset_count, "biological_time_ms": float(net.t / ms)})
            continue
        if command != "act":
            emit({"kind": "error", "error": f"unknown command: {command}"})
            continue

        observation = np.asarray(request.get("observation"), dtype=np.float64)
        if observation.shape != (18,) or not np.isfinite(observation).all():
            emit({"kind": "error", "error": "observation must be finite length 18"})
            continue
        clipped = np.clip(observation, -1.0, 1.0)
        rates_hz = np.maximum(0.0, clipped[input_features_arr] * input_polarities_arr) * max_rate_hz
        poisson.rates = rates_hz * Hz

        spike_start = int(spike_monitor.num_spikes)
        biological_start = float(net.t / ms)
        net.run(window_ms * ms)
        biological_end = float(net.t / ms)
        new_i = np.asarray(spike_monitor.i[spike_start:], dtype=np.int64)
        new_t = np.asarray(spike_monitor.t[spike_start:] / ms, dtype=np.float64)

        labels = output_action[new_i] if len(new_i) else np.empty(0, dtype=np.int8)
        output_labels = labels[labels > 0]
        group_counts = np.bincount(output_labels, minlength=8)[1:8].astype(np.int64)
        max_count = int(group_counts.max()) if len(group_counts) else 0
        if max_count < neutral_min:
            action = 0
        else:
            action = int(np.flatnonzero(group_counts == max_count)[0]) + 1

        output_spike_indices = new_i[labels > 0] if len(new_i) else np.empty(0, dtype=np.int64)
        contributions = []
        if len(output_spike_indices):
            unique_idx, counts = np.unique(output_spike_indices, return_counts=True)
            for idx, count in zip(unique_idx.tolist(), counts.tolist()):
                contributions.append([
                    output_group_name[int(idx)], int(body_ids[int(idx)]), float(count)
                ])

        sensory_drive = [
            [int(body), float(rate)]
            for body, rate in zip(input_body_ids_arr.tolist(), rates_hz.tolist())
            if rate > 0
        ]
        spikes = [
            [float(t), int(body_ids[int(i)])]
            for t, i in zip(new_t.tolist(), new_i.tolist())
        ]
        v = np.asarray(neu.v[:] / mV, dtype=np.float64)
        g = np.asarray(neu.g[:] / mV, dtype=np.float64)
        if len(new_i):
            u, c = np.unique(new_i, return_counts=True)
            order = np.argsort(c)[::-1][:20]
            top_spikes = [[int(body_ids[int(u[j])]), int(c[j])] for j in order]
        else:
            top_spikes = []

        emit({
            "kind": "decision",
            "action": action,
            "biological_time_start_ms": biological_start,
            "biological_time_end_ms": biological_end,
            "sensory_drive": sensory_drive,
            "group_spike_counts": {
                name: int(group_counts[i]) for i, name in enumerate(ACTIVE_ACTIONS)
            },
            "output_contributions": contributions,
            "spikes": spikes,
            "total_spikes": len(spikes),
            "top_spike_bodies": top_spikes,
            "membrane_summary": {
                "v_mean_mV": float(v.mean()),
                "v_min_mV": float(v.min()),
                "v_max_mV": float(v.max()),
                "g_mean_mV": float(g.mean()),
                "g_min_mV": float(g.min()),
                "g_max_mV": float(g.max()),
            },
        })

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
