#!/usr/bin/env python3
"""Build a lightweight spectator-only MaleCNS X-Z context atlas.

This is not an all-neuron rendering. It deterministically selects released
MaleCNS v1.0 skeletons across soma-neuromere/root-side and superclass strata,
fetches their official SWC centerlines, and stores a decimated X-Z projection.
The atlas provides whole-CNS anatomical context behind clip-active real SWCs;
it is never available to the controller or learning path.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.error

from build_malecns_skeleton_projection import BASE, fetch_swc, parse_projection


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>", "null"}:
        return None
    return text


def score(seed: int, salt: str, body_id: int) -> bytes:
    return hashlib.sha256(f"{seed}:{salt}:{body_id}".encode()).digest()


def read_rows(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"bodyId", "superclass"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"structure index lacks required columns: {sorted(required)}")
        rows: list[dict[str, object]] = []
        for row in reader:
            try:
                body_id = int(row["bodyId"])
            except (TypeError, ValueError):
                continue
            rows.append({
                "body_id": body_id,
                "superclass": clean(row.get("superclass")),
                "soma_neuromere": clean(row.get("somaNeuromere")),
                "root_side": clean(row.get("rootSide")),
            })
    if not rows:
        raise ValueError("structure index contains no valid body IDs")
    return rows


def deterministic_sample(
    rows: list[dict[str, object]],
    *,
    seed: int,
    per_neuromere_side: int,
    per_superclass: int,
    max_bodies: int,
) -> list[dict[str, object]]:
    by_body = {int(row["body_id"]): row for row in rows}
    selected: dict[int, dict[str, object]] = {}

    neuromere_groups: dict[str, list[int]] = {}
    for row in rows:
        neuromere = row.get("soma_neuromere")
        if not neuromere:
            continue
        side = row.get("root_side") or "unknown"
        key = f"{neuromere}|{side}"
        neuromere_groups.setdefault(key, []).append(int(row["body_id"]))
    for key in sorted(neuromere_groups):
        bodies = sorted(neuromere_groups[key], key=lambda body: score(seed, f"neuromere:{key}", body))
        for body in bodies[:per_neuromere_side]:
            selected[body] = by_body[body]

    superclass_groups: dict[str, list[int]] = {}
    for row in rows:
        superclass = row.get("superclass")
        if superclass:
            superclass_groups.setdefault(str(superclass), []).append(int(row["body_id"]))
    for key in sorted(superclass_groups):
        bodies = sorted(superclass_groups[key], key=lambda body: score(seed, f"superclass:{key}", body))
        for body in bodies[:per_superclass]:
            selected[body] = by_body[body]

    if len(selected) < max_bodies:
        remaining = [body for body in by_body if body not in selected]
        remaining.sort(key=lambda body: score(seed, "global-fill", body))
        for body in remaining:
            selected[body] = by_body[body]
            if len(selected) >= max_bodies:
                break

    ordered = sorted(selected.values(), key=lambda row: score(seed, "final-order", int(row["body_id"])))
    return ordered[:max_bodies]


def fetch_with_retries(body_id: int, timeout: float, retries: int) -> str:
    error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            return fetch_swc(body_id, timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            error = exc
            if attempt + 1 < retries:
                time.sleep(min(2.0, 0.35 * (attempt + 1)))
    assert error is not None
    raise error


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--structure-index", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", type=int, default=20260912)
    p.add_argument("--per-neuromere-side", type=int, default=4)
    p.add_argument("--per-superclass", type=int, default=6)
    p.add_argument("--max-bodies", type=int, default=128)
    p.add_argument("--max-segments-per-body", type=int, default=48)
    p.add_argument("--min-loaded-bodies", type=int, default=48)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--retries", type=int, default=3)
    args = p.parse_args()
    for name in ("per_neuromere_side", "per_superclass", "max_bodies", "max_segments_per_body", "min_loaded_bodies"):
        if getattr(args, name) <= 0:
            p.error(f"--{name.replace('_', '-')} must be positive")
    if args.min_loaded_bodies > args.max_bodies:
        p.error("--min-loaded-bodies cannot exceed --max-bodies")

    rows = read_rows(args.structure_index)
    selected = deterministic_sample(
        rows,
        seed=args.seed,
        per_neuromere_side=args.per_neuromere_side,
        per_superclass=args.per_superclass,
        max_bodies=args.max_bodies,
    )
    if len(selected) < args.min_loaded_bodies:
        raise RuntimeError(f"only {len(selected)} atlas bodies could be selected")

    segments: list[list[float]] = []
    loaded: list[dict[str, object]] = []
    failures: dict[int, str] = {}
    global_x: list[float] = []
    global_z: list[float] = []

    for index, row in enumerate(selected, start=1):
        body_id = int(row["body_id"])
        try:
            swc = fetch_with_retries(body_id, args.timeout, args.retries)
            body_segments, bounds = parse_projection(swc, args.max_segments_per_body)
            segments.extend(body_segments)
            global_x.extend([bounds["x_min"], bounds["x_max"]])
            global_z.extend([bounds["z_min"], bounds["z_max"]])
            loaded.append({
                "body_id": body_id,
                "superclass": row.get("superclass"),
                "soma_neuromere": row.get("soma_neuromere"),
                "root_side": row.get("root_side"),
                "segments": len(body_segments),
            })
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            failures[body_id] = f"{type(exc).__name__}: {exc}"
        if index % 16 == 0:
            print(json.dumps({"progress": index, "selected": len(selected), "loaded": len(loaded), "failed": len(failures)}))

    if len(loaded) < args.min_loaded_bodies:
        raise RuntimeError(
            f"atlas coverage below minimum: loaded={len(loaded)} minimum={args.min_loaded_bodies} failures={len(failures)}"
        )
    if not segments:
        raise RuntimeError("atlas contains no released SWC segments")

    selected_neuromeres = sorted({str(row["soma_neuromere"]) for row in loaded if row.get("soma_neuromere")})
    selected_superclasses = sorted({str(row["superclass"]) for row in loaded if row.get("superclass")})
    selected_sides = sorted({str(row["root_side"]) for row in loaded if row.get("root_side")})

    payload = {
        "schema_version": 1,
        "kind": "male-cns-context-atlas-xz",
        "dataset": "male-cns:v1.0",
        "purpose": "spectator-only-released-skeleton-context-atlas",
        "policy_access": False,
        "atlas_kind": "deterministic-stratified-released-skeleton-sample",
        "projection": "x-z",
        "coordinate_space": "MaleCNS EM",
        "coordinate_units": "8 nm",
        "source_base": BASE,
        "selection": {
            "seed": args.seed,
            "per_neuromere_side": args.per_neuromere_side,
            "per_superclass": args.per_superclass,
            "max_bodies": args.max_bodies,
            "max_segments_per_body": args.max_segments_per_body,
        },
        "coverage": {
            "source_rows": len(rows),
            "selected_bodies": len(selected),
            "loaded_bodies": len(loaded),
            "failed_bodies": len(failures),
            "soma_neuromeres": selected_neuromeres,
            "superclasses": selected_superclasses,
            "root_sides": selected_sides,
        },
        "bounds": {
            "x_min": min(global_x), "x_max": max(global_x),
            "z_min": min(global_z), "z_max": max(global_z),
        },
        "segments": segments,
        "bodies": loaded,
        "failed_body_ids": {str(k): v for k, v in failures.items()},
        "interpretation_boundary": (
            "This is a deterministic stratified sample of official released MaleCNS SWC centerlines used only as a lightweight whole-CNS context layer. "
            "It is not an all-neuron rendering, calcium signal, membrane voltage map, functional assignment, or policy input. "
            "Clip-active SWCs are overlaid separately from recorded spike body IDs."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "selected_bodies": len(selected),
        "loaded_bodies": len(loaded),
        "failed_bodies": len(failures),
        "segments": len(segments),
        "soma_neuromeres": len(selected_neuromeres),
        "superclasses": len(selected_superclasses),
        "root_sides": selected_sides,
        "bytes": args.out.stat().st_size,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
