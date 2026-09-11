"""Construct the full strict MaleCNS network with the pinned Shiu reference code.

No artificial neural network is used here. The script imports upstream
`model.py`, passes converted MaleCNS tables to `create_model()`, and advances the
Brian2 network briefly to verify that the published LIF equations and the full
runtime-sized structural adapter are executable together.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import resource
import time

from brian2 import Network, ms, prefs, start_scope


def load_reference(path: Path):
    spec = importlib.util.spec_from_file_location("pinned_shiu_model", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import reference model: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rss_mib() -> float:
    # Linux ru_maxrss is KiB.
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-model", type=Path, required=True)
    p.add_argument("--adapter-dir", type=Path, required=True)
    p.add_argument("--run-ms", type=float, default=20.0)
    p.add_argument("--codegen-target", choices=["numpy", "cython"], default="cython")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.run_ms <= 0:
        p.error("--run-ms must be positive")

    # Backend choice is an engineering/runtime choice only. Neuron equations,
    # thresholds, synaptic delay and weights remain those in pinned upstream
    # Shiu model.py. Fail rather than silently falling back to a slower target.
    prefs.codegen.target = args.codegen_target

    manifest = json.loads((args.adapter_dir / "manifest.json").read_text(encoding="utf-8"))
    reference = load_reference(args.reference_model)
    start_scope()

    t0 = time.perf_counter()
    neu, syn, spk = reference.create_model(
        args.adapter_dir / "completeness.csv",
        args.adapter_dir / "connectivity.parquet",
        reference.default_params,
    )
    build_seconds = time.perf_counter() - t0
    after_build_rss = rss_mib()

    expected_neurons = int(manifest["counts"]["included_neurons"])
    expected_edges = int(manifest["counts"]["runtime_edges"])
    if len(neu) != expected_neurons:
        raise AssertionError(f"Neuron count mismatch: {len(neu)} != {expected_neurons}")
    if len(syn) != expected_edges:
        raise AssertionError(f"Synapse count mismatch: {len(syn)} != {expected_edges}")

    net = Network(neu, syn, spk)
    t1 = time.perf_counter()
    net.run(args.run_ms * ms)
    run_seconds = time.perf_counter() - t1
    result = {
        "status": "PASS",
        "dataset": manifest["dataset"],
        "adapter": manifest["adapter"],
        "histamine_mode": manifest["histamine_mode"],
        "min_connection_weight": manifest["min_connection_weight"],
        "neurons": len(neu),
        "synapses": len(syn),
        "reference_commit": manifest["shiu_reference_commit"],
        "codegen_target": str(prefs.codegen.target),
        "build_seconds": build_seconds,
        "run_ms": args.run_ms,
        "run_wall_seconds": run_seconds,
        "wall_seconds_per_biological_ms": run_seconds / args.run_ms,
        "peak_rss_mib": rss_mib(),
        "rss_after_build_mib": after_build_rss,
        "spikes_during_quiet_smoke": int(spk.num_spikes),
        "interpretation": (
            "Full strict MaleCNS structural adapter was accepted and advanced by the "
            "pinned Shiu Brian2 reference dynamics. Codegen target changes execution "
            "only, not the published model equations. No game input or learning was applied."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
