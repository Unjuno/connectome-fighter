#!/usr/bin/env python3
"""Precompile and prove the arena Brian2 Cython cache without a runtime compiler.

This helper is intentionally infrastructure-only: it launches the canonical
MaleCNS + pinned Shiu worker twice with identical model/interface inputs.  The
first launch is allowed to compile Brian2 Cython extensions into the arena
bundle.  The second launch receives an empty PATH; reaching the worker's
``ready`` handshake therefore proves that the required code objects were loaded
from the precompiled cache rather than compiled at viewer runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

PORTABLE_CYTHON_GCC_FLAGS = [
    "-w",
    "-O3",
    "-ffast-math",
    "-fno-finite-math-only",
    "-std=c++11",
]


def stable_json_sha(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def parse_worker_output(stdout: str) -> tuple[dict[str, Any], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    ready = next((row for row in rows if row.get("kind") == "ready"), None)
    closed = next((row for row in rows if row.get("kind") == "closed"), None)
    if ready is None or closed is None:
        raise RuntimeError(f"worker did not emit ready+closed handshakes: {rows[-4:]}")
    return ready, closed


def run_worker(
    *,
    executable: Path,
    worker: Path,
    reference_model: Path,
    adapter_dir: Path,
    interface: Path,
    cache_dir: Path,
    site310: Path,
    character: str,
    seed: int,
    timeout_sec: int,
    compilerless: bool,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(site310)
    env["CONNECTOME_BRIAN_CYTHON_CACHE_DIR"] = str(cache_dir)
    env.pop("CC", None)
    env.pop("CXX", None)
    if compilerless:
        # The Python executable is absolute. Any cache miss that asks distutils
        # to spawn cc/c++ will fail immediately because no compiler is on PATH.
        env["PATH"] = "/__connectome_no_compiler__"

    command = [
        str(executable),
        str(worker),
        "--reference-model",
        str(reference_model),
        "--adapter-dir",
        str(adapter_dir),
        "--interface",
        str(interface),
        "--seed",
        str(seed),
        "--character",
        character,
        "--codegen-target",
        "cython",
    ]
    result = subprocess.run(
        command,
        input='{"command":"close"}\n',
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout_sec,
        check=False,
    )
    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-80:])
        signal_note = ""
        if result.returncode < 0:
            signal_note = f" (signal={-result.returncode})"
        raise RuntimeError(
            f"worker exited {result.returncode}{signal_note} (compilerless={compilerless})\n{stderr_tail}"
        )
    ready, _ = parse_worker_output(result.stdout)
    if ready.get("parameters", {}).get("codegen_target") != "cython":
        raise RuntimeError("worker did not use the canonical Cython codegen target")
    if ready.get("parameters", {}).get("cython_cache_dir") != str(cache_dir):
        raise RuntimeError("worker did not use the requested arena Cython cache directory")
    return ready


def cache_tree(cache_dir: Path) -> tuple[str, int, int, int]:
    files = sorted(path for path in cache_dir.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    shared_objects = 0
    total_bytes = 0
    for path in files:
        rel = path.relative_to(cache_dir).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(hashlib.sha256(data).digest())
        total_bytes += len(data)
        if path.suffix == ".so":
            shared_objects += 1
    return digest.hexdigest(), len(files), shared_objects, total_bytes


def runtime_versions(executable: Path, site310: Path) -> dict[str, Any]:
    code = (
        "import json,sys,numpy,Cython,brian2;"
        "print(json.dumps({'sys_executable':sys.executable,'python':sys.version.split()[0],"
        "'numpy':numpy.__version__,'cython':Cython.__version__,'brian2':brian2.__version__},sort_keys=True))"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(site310)
    env.pop("CC", None)
    env.pop("CXX", None)
    raw = subprocess.check_output([str(executable), "-c", code], text=True, env=env)
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--vercel-root", type=Path, required=True)
    parser.add_argument("--character", default="GARNET")
    parser.add_argument("--seed", type=int, default=20260912)
    parser.add_argument("--timeout-sec", type=int, default=1800)
    args = parser.parse_args()

    runtime_root = args.runtime_root.resolve()
    vercel_root = args.vercel_root.absolute()
    if not runtime_root.is_dir():
        raise SystemExit(f"runtime root missing: {runtime_root}")
    if not vercel_root.exists():
        raise SystemExit(f"Vercel-path runtime root missing: {vercel_root}")

    python_rel = (runtime_root / "runtime" / "python310.path").read_text(encoding="utf-8").strip()
    executable = vercel_root / python_rel
    site310 = vercel_root / "runtime" / "site310"
    worker = vercel_root / "repo" / "scripts" / "malecns_lif_worker.py"
    reference_model = vercel_root / "shiu" / "model.py"
    adapter_dir = vercel_root / "data" / "malecns-shiu-strict-v1"
    interface = vercel_root / "data" / "interface.json"
    cache_dir = vercel_root / "runtime" / "brian2-cython-cache"

    for required in (executable, site310, worker, reference_model, adapter_dir, interface):
        if not required.exists():
            raise SystemExit(f"required runtime asset missing: {required}")

    # Never reuse compiled objects from the downloaded rolling release while
    # rebuilding it. The previous cache may have been produced on another CPU
    # with Brian2's historical -march=native default. Reusing such a .so can
    # SIGILL before the new portable flags are ever applied.
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    first = run_worker(
        executable=executable,
        worker=worker,
        reference_model=reference_model,
        adapter_dir=adapter_dir,
        interface=interface,
        cache_dir=cache_dir,
        site310=site310,
        character=args.character,
        seed=args.seed,
        timeout_sec=args.timeout_sec,
        compilerless=False,
    )

    tree_sha, file_count, shared_object_count, total_bytes = cache_tree(cache_dir)
    if shared_object_count < 1:
        raise RuntimeError("Brian2 precompile produced no shared objects")

    second = run_worker(
        executable=executable,
        worker=worker,
        reference_model=reference_model,
        adapter_dir=adapter_dir,
        interface=interface,
        cache_dir=cache_dir,
        site310=site310,
        character=args.character,
        seed=args.seed,
        timeout_sec=args.timeout_sec,
        compilerless=True,
    )
    if first.get("initial_state_sha256") != second.get("initial_state_sha256"):
        raise RuntimeError("compilerless cache reuse changed the initial-state identity")
    if first.get("neurons") != second.get("neurons") or first.get("synapses") != second.get("synapses"):
        raise RuntimeError("compilerless cache reuse changed model dimensions")

    versions = runtime_versions(executable, site310)
    if versions.get("sys_executable") != str(executable):
        raise RuntimeError(
            f"sys.executable mismatch: {versions.get('sys_executable')} != {executable}"
        )

    manifest = {
        "schema_version": 2,
        "kind": "connectome-fighter-brian2-cython-cache",
        "canonical_model": "MaleCNS v1.0 + pinned Shiu LIF",
        "codegen_target": "cython",
        "expected_sys_executable": str(executable),
        "compiler_key_environment": {"CC": None, "CXX": None},
        "portable_compile_args": PORTABLE_CYTHON_GCC_FLAGS,
        "host_specific_march_native": False,
        "versions": versions,
        "compilerless_reuse_verified": True,
        "proof_character": args.character,
        "proof_seed": args.seed,
        "neurons": int(first["neurons"]),
        "synapses": int(first["synapses"]),
        "interface_sha256": first["interface_sha256"],
        "initial_state_sha256": first["initial_state_sha256"],
        "cache_tree_sha256": tree_sha,
        "cache_file_count": file_count,
        "shared_object_count": shared_object_count,
        "cache_size_bytes": total_bytes,
    }
    out = runtime_root / "runtime" / "brian2-cython-cache-manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"cache_manifest_sha256={hashlib.sha256(out.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
