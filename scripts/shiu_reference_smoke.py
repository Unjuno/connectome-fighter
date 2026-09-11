"""Execute the pinned Shiu et al. Brian2 model on a deterministic tiny circuit.

This gate intentionally calls the published reference `model.py` directly. It
is not a reimplementation of the neural dynamics. Its role is to prove that the
pinned reference environment is executable and to record a small deterministic
spike signature before MaleCNS data are adapted into the same input contract.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import tempfile

import pandas as pd
from brian2 import Network, defaultclock, mV, ms, start_scope

EXPECTED = {
    "v_0_mV": -52.0,
    "v_rst_mV": -52.0,
    "v_th_mV": -45.0,
    "t_mbr_ms": 20.0,
    "tau_ms": 5.0,
    "t_rfc_ms": 2.2,
    "t_dly_ms": 1.8,
    "w_syn_mV": 0.275,
}


def load_reference(path: Path):
    spec = importlib.util.spec_from_file_location("pinned_shiu_model", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import reference model: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scalar(value, unit) -> float:
    return float(value / unit)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-model", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    reference = load_reference(args.reference_model)
    p = reference.default_params
    observed_params = {
        "v_0_mV": scalar(p["v_0"], mV),
        "v_rst_mV": scalar(p["v_rst"], mV),
        "v_th_mV": scalar(p["v_th"], mV),
        "t_mbr_ms": scalar(p["t_mbr"], ms),
        "tau_ms": scalar(p["tau"], ms),
        "t_rfc_ms": scalar(p["t_rfc"], ms),
        "t_dly_ms": scalar(p["t_dly"], ms),
        "w_syn_mV": scalar(p["w_syn"], mV),
    }
    for key, expected in EXPECTED.items():
        actual = observed_params[key]
        if abs(actual - expected) > 1e-12:
            raise AssertionError(f"Reference parameter drift: {key}={actual}, expected={expected}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # The reference loader only requires row count/index from completeness.
        pd.DataFrame({"dummy": [1, 1]}, index=[1001, 1002]).to_csv(tmp / "completeness.csv")
        # A single strong excitatory edge lets neuron 0 trigger neuron 1 after
        # the published synaptic delay. Connectivity is a synapse-count-like
        # multiplier exactly as expected by reference create_model().
        pd.DataFrame({
            "Presynaptic_Index": [0],
            "Postsynaptic_Index": [1],
            "Excitatory x Connectivity": [200],
        }).to_parquet(tmp / "connectivity.parquet", index=False)

        start_scope()
        defaultclock.dt = 0.1 * ms
        neu, syn, spk = reference.create_model(
            tmp / "completeness.csv", tmp / "connectivity.parquet", p
        )
        # Deterministic initial trigger, avoiding Poisson randomness.
        neu.v = p["v_0"]
        neu.v[0] = -44 * mV
        net = Network(neu, syn, spk)
        net.run(20 * ms)

        trains = spk.spike_trains()
        spike_ms = {
            str(i): [round(float(t / ms), 6) for t in trains[i]]
            for i in range(2)
        }
        if not spike_ms["0"]:
            raise AssertionError("Reference presynaptic neuron did not spike")
        if not spike_ms["1"]:
            raise AssertionError("Reference postsynaptic neuron did not spike")
        if spike_ms["1"][0] <= spike_ms["0"][0]:
            raise AssertionError("Postsynaptic spike did not follow presynaptic spike")

    result = {
        "status": "PASS",
        "reference_model": str(args.reference_model),
        "brian2_dt_ms": 0.1,
        "parameters": observed_params,
        "tiny_circuit": {
            "neurons": 2,
            "edges": 1,
            "signed_connectivity": 200,
            "spike_times_ms": spike_ms,
        },
        "interpretation": (
            "Published Shiu reference dynamics executed directly. This does not yet "
            "validate the MaleCNS structural adapter or full-CNS simulation."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
