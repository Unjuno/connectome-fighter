#!/usr/bin/env python3
"""Fail CI when public documentation/workflows drift from the shared-LIVE contract."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIRED_RUNTIME_SHA256 = {
    "b4511a0d5287384d2ca130ef58b40adb2786c6b0968ec961d5b41af13441d510",
    "f4016e3a2f79968a3305818ad3b4ef2197802e36c647660c1ab524b098f27205",
}
CAUSAL_PROOF_FLAGS = {
    "sensory_drive_body_ids_and_rates",
    "whole_network_activity",
    "motor_output_contributors",
    "seven_action_group_counts",
    "selected_action_matches_max_group",
    "real_fightingice_xy_hp_action",
    "all_fields_same_decision_window",
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(path: str, *needles: str) -> None:
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing required public-surface contract text: {missing}")


def forbid(path: str, *needles: str) -> None:
    text = read(path)
    found = [needle for needle in needles if needle in text]
    if found:
        raise SystemExit(f"{path}: retired public architecture/proof text returned: {found}")


def validate_runtime_proof() -> dict:
    path = ROOT / "site/data/runtime-proof.json"
    proof = json.loads(path.read_text(encoding="utf-8"))
    if proof.get("kind") != "connectome-fighter-production-runtime-proof":
        raise SystemExit("site/data/runtime-proof.json: unexpected kind")
    if int(proof.get("schema_version", 0)) < 2:
        raise SystemExit("site/data/runtime-proof.json: causal proof requires schema >= 2")

    sha = str(proof.get("runtime_archive_sha256") or "")
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise SystemExit("site/data/runtime-proof.json: invalid runtime SHA-256")
    if sha in RETIRED_RUNTIME_SHA256:
        raise SystemExit("site/data/runtime-proof.json: retired runtime SHA cannot be current proof")
    expected_base = f"connectome-runtime-{sha[:16]}"
    if proof.get("runtime_base") != expected_base:
        raise SystemExit(f"site/data/runtime-proof.json: runtime_base must be {expected_base}")
    if not str(proof.get("runtime_snapshot_id") or "").startswith("snap_"):
        raise SystemExit("site/data/runtime-proof.json: missing runtime snapshot ID")

    if proof.get("canonical_model") != "MaleCNS v1.0 + pinned Shiu LIF":
        raise SystemExit("site/data/runtime-proof.json: canonical model mismatch")
    if proof.get("compilerless_reuse_verified") is not True:
        raise SystemExit("site/data/runtime-proof.json: compilerless reuse not verified")
    if proof.get("host_specific_march_native") is not False:
        raise SystemExit("site/data/runtime-proof.json: host-specific native code must be false")
    if int(proof.get("neurons", 0)) <= 150_000 or int(proof.get("recurrent_synapses", 0)) <= 1_000_000:
        raise SystemExit("site/data/runtime-proof.json: implausible model dimensions")
    if int(proof.get("shared_object_count", 0)) < 1:
        raise SystemExit("site/data/runtime-proof.json: no precompiled shared objects")

    if proof.get("broadcast_target") != "connectome-live-broadcast" or proof.get("audience_scope") != "shared-global":
        raise SystemExit("site/data/runtime-proof.json: public broadcast contract mismatch")
    if proof.get("p1") != "GARNET" or proof.get("p1_state") != "generation-2-approved-inference":
        raise SystemExit("site/data/runtime-proof.json: served P1 state mismatch")
    if proof.get("p2") != "ZEN" or proof.get("p2_state") != "canonical-baseline":
        raise SystemExit("site/data/runtime-proof.json: served P2 state mismatch")
    if proof.get("learning_enabled") is not False or proof.get("policy_pixel_access") is not False:
        raise SystemExit("site/data/runtime-proof.json: public policy boundary mismatch")

    if int(proof.get("telemetry_schema_version", 0)) < 3:
        raise SystemExit("site/data/runtime-proof.json: production LIVE must prove telemetry schema >= 3")
    if int(proof.get("rounds_per_shared_process", 0)) != 6:
        raise SystemExit("site/data/runtime-proof.json: production shared process must prove six rounds")
    causal = proof.get("causal_live_contract") or {}
    missing_flags = sorted(flag for flag in CAUSAL_PROOF_FLAGS if causal.get(flag) is not True)
    if missing_flags:
        raise SystemExit(f"site/data/runtime-proof.json: incomplete causal LIVE proof flags: {missing_flags}")

    telemetry = proof.get("proof_telemetry") or {}
    if int(telemetry.get("frame", 0)) <= 0:
        raise SystemExit("site/data/runtime-proof.json: proof frame must be > 0")
    if int(telemetry.get("rounds_per_session", 0)) != 6:
        raise SystemExit("site/data/runtime-proof.json: proof telemetry must be six-round shared execution")
    if int(telemetry.get("p1_decision_index", 0)) <= 0 or int(telemetry.get("p2_decision_index", 0)) <= 0:
        raise SystemExit("site/data/runtime-proof.json: both proof decision indices must be > 0")
    for side in ("p1", "p2"):
        action = str(telemetry.get(f"{side}_action") or "")
        groups = telemetry.get(f"{side}_action_group_spikes") or {}
        if action not in {"FORWARD", "BACKWARD", "UP", "DOWN", "A", "B", "C"}:
            raise SystemExit(f"site/data/runtime-proof.json: unsupported proof action for {side}: {action!r}")
        if set(groups) != {"FORWARD", "BACKWARD", "UP", "DOWN", "A", "B", "C"}:
            raise SystemExit(f"site/data/runtime-proof.json: incomplete seven-group proof for {side}")
        if int(groups[action]) != max(int(value) for value in groups.values()):
            raise SystemExit(f"site/data/runtime-proof.json: {side} action does not match maximal group")
        sensory = telemetry.get(f"{side}_top_sensory_drive") or {}
        if int(sensory.get("body_id", 0)) <= 0 or float(sensory.get("rate_hz", 0)) <= 0:
            raise SystemExit(f"site/data/runtime-proof.json: missing real sensory proof for {side}")
    return proof


def main() -> int:
    proof = validate_runtime_proof()
    runtime_sha = str(proof["runtime_archive_sha256"])
    runtime_base = str(proof["runtime_base"])
    snapshot_id = str(proof["runtime_snapshot_id"])

    require(
        "README.md",
        "single shared Vercel LIVE",
        "connectome-live-broadcast",
        "continuous production reward-driven learning: **OFF**",
        "GARNET generation 2",
        "ZEN / LUD / NEZ generation 2",
    )
    forbid(
        "README.md",
        "production per-viewer Vercel execution",
        "intended public runtime is **per-viewer",
        "short-lived viewer-specific runtime",
        "production runtime image/service is still being provisioned",
    )

    require(
        "README.ja.md",
        "1つの shared read-only LIVE broadcast",
        "Neural activity → action → fight",
        "GARNET generation 2 = APPROVED INFERENCE",
        "ZEN generation 2 = CANDIDATE LINEAGE",
        "continuous production reward-driven learning は OFF",
        "Public Surface Freeze",
        runtime_sha,
        runtime_base,
        snapshot_id,
        "site/data/runtime-proof.json",
    )
    forbid(
        "README.ja.md",
        "GitHub Actions（毎時）",
        "3本rolling queue",
        "Vercel 30秒poll",
        "rolling spectatorを複数scheduled run",
        *RETIRED_RUNTIME_SHA256,
    )

    require(
        "ROADMAP.md",
        "One shared Vercel LIVE",
        "P6 — Public Surface Freeze ← CURRENT",
        "GARNET generation 2",
        "ZEN / LUD / NEZ generation 2",
        "hourly schedule has been removed",
    )
    forbid(
        "ROADMAP.md",
        "Vercel pseudo-live viewer",
        "P6 — Freeze spectator/data contracts",
        "GitHub Actions hourly",
        "Vercel /connectome polls every 30 s",
    )

    require(
        "docs/STATUS.md",
        "Production public LIVE — PASS",
        "Neural activity → action → fight — PASS",
        "single-shared-live-broadcast",
        "connectome-live-broadcast",
        "Historical rolling-video spectator — RETAINED EVIDENCE, NOT PRIMARY LIVE",
        "Current gate — Public Surface Freeze",
        runtime_sha,
        runtime_base,
        snapshot_id,
        "site/data/runtime-proof.json",
    )
    forbid(
        "docs/STATUS.md",
        "Current production spectator — PASS",
        "Vercel viewer polls every 30 s",
        "P6 — freeze spectator/data contracts",
        *RETIRED_RUNTIME_SHA256,
    )

    require(
        "docs/PUBLIC_SURFACE_SPLIT.md",
        "single shared live broadcast",
        "Causal LIVE visualization",
        "connectome-live-broadcast",
        "learning_enabled=false",
        "policy_pixel_access=false",
        "Public-surface freeze gate",
        runtime_sha,
        runtime_base,
        snapshot_id,
        "site/data/runtime-proof.json",
    )
    forbid(
        "docs/PUBLIC_SURFACE_SPLIT.md",
        "short-lived per-viewer inference",
        "isolated viewer-specific inference session",
        "production runtime image/service is still being provisioned",
        *RETIRED_RUNTIME_SHA256,
    )

    require(
        "docs/PUBLIC_SURFACE_SPLIT.ja.md",
        "single shared live broadcast",
        "Neural activity → action → fight",
        "GARNET approved generation-2 inference vs ZEN canonical baseline",
        "Production reward-driven learning は現在 **OFF**",
        "Public Surface Freeze gate",
        "毎時 schedule は停止済み",
        runtime_sha,
        runtime_base,
        snapshot_id,
        "site/data/runtime-proof.json",
    )
    forbid("docs/PUBLIC_SURFACE_SPLIT.ja.md", *RETIRED_RUNTIME_SHA256)

    require(
        "docs/SPECTATOR_PIPELINE.ja.md",
        "現在の production LIVE 仕様ではありません",
        "one shared real LIVE",
        "毎時 cron は停止済み",
        "regression / archival evidence",
    )
    forbid(
        "docs/SPECTATOR_PIPELINE.ja.md",
        "Connectome Fighter の観戦系は「真のリアルタイム配信」ではなく",
        "GitHub Actions (hourly)",
        "Vercel /connectome polls every 30 s",
    )

    require(
        "site/index.html",
        "one globally shared read-only LIVE fight",
        "Causal shared LIVE: sensory → network → motor → action → fight",
        "GARNET generation 2",
        "candidate cross-run resume proven",
        runtime_sha,
        runtime_base,
        snapshot_id,
        "runtime-proof.json",
    )
    forbid("site/index.html", *RETIRED_RUNTIME_SHA256)
    require(
        "site/app.js",
        "Public Surface Freeze · data:",
        "Project gate: Public Surface Freeze; latest baseline data phase:",
        "./data/runtime-proof.json",
        "renderRuntimeProof",
    )

    require(
        ".github/workflows/vercel-live-arena-smoke.yml",
        "/api/connectome/live",
        "single-shared-live-broadcast",
        "shared-global",
        "connectome-live-broadcast",
        "shared_broadcast_only",
        "Require synchronized sensory-to-motor FightingICE telemetry",
        "rounds_per_session == 6",
        "sensory_drive",
        "output_contributions",
        "5 · selected action",
    )
    forbid(
        ".github/workflows/vercel-live-arena-smoke.yml",
        "per-viewer-live-sandbox",
        "Launch real GARNET vs ZEN session from runtime snapshot",
    )

    require(
        ".github/workflows/precompile-arena-brian2-cython-cache.yml",
        "Wait for Vercel to observe exact postprocessed release",
        "Require shared LIVE to adopt exact runtime base",
        "single-shared-live-broadcast",
        "connectome-live-broadcast",
        "Compilerless shared Vercel LIVE produced no real two-brain decision before deadline.",
    )
    forbid(
        ".github/workflows/precompile-arena-brian2-cython-cache.yml",
        "Launch GARNET checkpoint vs ZEN canonical baseline",
        "-X POST \"$BASE/api/connectome/session\"",
        "STATUS_URL",
    )

    require(
        ".github/workflows/render-fightingice-video.yml",
        "Historical ScreenData/video regression workflow",
        "workflow_dispatch:",
        "never substituted for LIVE",
    )
    forbid(
        ".github/workflows/render-fightingice-video.yml",
        "cron: '17 * * * *'",
        "schedule:",
    )

    print(
        "public-surface contract: PASS "
        f"runtime={runtime_sha[:16]} base={runtime_base} "
        f"telemetry=v{proof['telemetry_schema_version']} rounds={proof['rounds_per_shared_process']} causal=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
