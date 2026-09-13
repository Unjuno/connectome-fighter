#!/usr/bin/env python3
"""Validate the dedicated Connectome public/research boundary.

Historical runtime-proof JSON remains evidence for the neural/FightingICE runtime that
was exercised before the dedicated Vercel-project split. It is intentionally not used
to claim that the newly separated production deployment has passed E2E.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLYBODY_COMMIT = "d015e9bfe441bd90ae431bac24c55cb74bdbce26"
FLYBODY_ADAPTER = "malecns-annotated-motor-to-flybody-tripod-v2"
BROADCAST_TARGET = "connectome-fighter-live-broadcast"
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
        raise SystemExit(f"{path}: missing required dedicated-public contract text: {missing}")


def forbid(path: str, *needles: str) -> None:
    text = read(path)
    found = [needle for needle in needles if needle in text]
    if found:
        raise SystemExit(f"{path}: forbidden legacy/public-boundary text returned: {found}")


def validate_historical_runtime_proof() -> dict:
    path = ROOT / "site/data/runtime-proof.json"
    proof = json.loads(path.read_text(encoding="utf-8"))
    if proof.get("kind") != "connectome-fighter-production-runtime-proof":
        raise SystemExit("site/data/runtime-proof.json: unexpected kind")
    if int(proof.get("schema_version", 0)) < 2:
        raise SystemExit("site/data/runtime-proof.json: historical causal proof requires schema >= 2")

    sha = str(proof.get("runtime_archive_sha256") or "")
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise SystemExit("site/data/runtime-proof.json: invalid historical runtime SHA-256")
    if proof.get("runtime_base") != f"connectome-runtime-{sha[:16]}":
        raise SystemExit("site/data/runtime-proof.json: historical runtime/base identity mismatch")
    if not str(proof.get("runtime_snapshot_id") or "").startswith("snap_"):
        raise SystemExit("site/data/runtime-proof.json: historical snapshot ID missing")
    if proof.get("canonical_model") != "MaleCNS v1.0 + pinned Shiu LIF":
        raise SystemExit("site/data/runtime-proof.json: canonical model mismatch")
    if proof.get("compilerless_reuse_verified") is not True:
        raise SystemExit("site/data/runtime-proof.json: compilerless reuse not verified")
    if proof.get("host_specific_march_native") is not False:
        raise SystemExit("site/data/runtime-proof.json: host-specific native code must be false")
    if int(proof.get("neurons", 0)) <= 150_000 or int(proof.get("recurrent_synapses", 0)) <= 1_000_000:
        raise SystemExit("site/data/runtime-proof.json: implausible historical model dimensions")
    if proof.get("learning_enabled") is not False or proof.get("policy_pixel_access") is not False:
        raise SystemExit("site/data/runtime-proof.json: historical policy boundary mismatch")
    if int(proof.get("telemetry_schema_version", 0)) < 3:
        raise SystemExit("site/data/runtime-proof.json: historical telemetry schema must be >= 3")
    if int(proof.get("rounds_per_shared_process", 0)) != 6:
        raise SystemExit("site/data/runtime-proof.json: historical shared process must prove six rounds")

    causal = proof.get("causal_live_contract") or {}
    missing_flags = sorted(flag for flag in CAUSAL_PROOF_FLAGS if causal.get(flag) is not True)
    if missing_flags:
        raise SystemExit(f"site/data/runtime-proof.json: incomplete historical causal proof: {missing_flags}")

    telemetry = proof.get("proof_telemetry") or {}
    if int(telemetry.get("frame", 0)) <= 0:
        raise SystemExit("site/data/runtime-proof.json: historical proof frame must be > 0")
    if int(telemetry.get("p1_decision_index", 0)) <= 0 or int(telemetry.get("p2_decision_index", 0)) <= 0:
        raise SystemExit("site/data/runtime-proof.json: historical decisions must be > 0")
    for side in ("p1", "p2"):
        action = str(telemetry.get(f"{side}_action") or "")
        groups = telemetry.get(f"{side}_action_group_spikes") or {}
        allowed = {"FORWARD", "BACKWARD", "UP", "DOWN", "A", "B", "C"}
        if action not in allowed or set(groups) != allowed:
            raise SystemExit(f"site/data/runtime-proof.json: incomplete action proof for {side}")
        if int(groups[action]) != max(int(value) for value in groups.values()):
            raise SystemExit(f"site/data/runtime-proof.json: {side} action is not maximal group")
    return proof


def validate_no_legacy_public_target() -> None:
    legacy_host = "liveunjuno.vercel" + ".app"
    legacy_project = "prj_T1i5PPgfjHXAKGLf9Gmoboae" + "61Tk"
    paths = [
        "README.md",
        "README.ja.md",
        "ROADMAP.md",
        "docs/STATUS.md",
        "docs/PUBLIC_SURFACE_SPLIT.md",
        "docs/PUBLIC_SURFACE_SPLIT.ja.md",
        "site/index.html",
        "app/api/live/route.ts",
        "app/api/runtime-base/route.ts",
        "lib/vercel-sandbox.ts",
        "lib/runtime-base.ts",
        "lib/connectome-broadcast.ts",
    ]
    for path in paths:
        forbid(path, legacy_host, legacy_project)


def main() -> int:
    proof = validate_historical_runtime_proof()
    validate_no_legacy_public_target()

    require(
        "README.md",
        "Dedicated public architecture",
        BROADCAST_TARGET,
        FLYBODY_COMMIT,
        FLYBODY_ADAPTER,
        "FightingICE x/y/action values do not position the FlyBody body",
        "dedicated Vercel shared-LIVE E2E: **NOT YET VERIFIED**",
        "continuous production reward-driven learning: **OFF**",
    )
    require(
        "README.ja.md",
        BROADCAST_TARGET,
        FLYBODY_COMMIT,
        FLYBODY_ADAPTER,
        "FightingICE の x/y/action を FlyBody の位置やposeにコピーしません",
        "dedicated Vercel shared-LIVE E2E: **NOT YET VERIFIED**",
        "continuous production reward-driven learning: **OFF**",
    )
    require(
        "ROADMAP.md",
        "P5 — Dedicated shared LIVE ← CURRENT",
        BROADCAST_TARGET,
        "Dedicated Vercel production project",
        "Same-decision production FlyBody E2E",
        "No other Vercel project may be used as a fallback target",
    )
    require(
        "docs/STATUS.md",
        "Dedicated public deployment — IMPLEMENTED, E2E PENDING",
        BROADCAST_TARGET,
        "FlyBody physical embodiment — CI PASS",
        FLYBODY_COMMIT,
        FLYBODY_ADAPTER,
        "action dimension: **59**",
        "production FlyBody E2E remains **NOT YET VERIFIED**",
    )
    require(
        "docs/PUBLIC_SURFACE_SPLIT.md",
        "Dedicated Vercel LIVE",
        "CONNECTOME_PUBLIC_BASE_URL",
        "/api/runtime-base",
        "/api/live",
        BROADCAST_TARGET,
        FLYBODY_COMMIT,
        FLYBODY_ADAPTER,
        "FightingICE x/y/action does not position or pose the physical FlyBody",
        "production E2E status is **NOT YET VERIFIED**",
    )
    require(
        "docs/PUBLIC_SURFACE_SPLIT.ja.md",
        "Dedicated Vercel LIVE",
        "CONNECTOME_PUBLIC_BASE_URL",
        BROADCAST_TARGET,
        FLYBODY_COMMIT,
        FLYBODY_ADAPTER,
        "FightingICE x/y/actionをFlyBodyのposition/poseへコピーしません",
    )
    require(
        "site/index.html",
        "Dedicated deployment workflow",
        "deployment E2E pending",
        "FightingICE x/y/action does not position the FlyBody body",
        "./data/training-history.json",
        "Append-only public candidate generation ledger",
    )
    require(
        "app/live-client.tsx",
        "Official FightingICE ScreenData",
        "MaleCNS activity drives the actual FlyBody MuJoCo fly.",
        "No SVG or FightingICE-position puppet is substituted here.",
        "FightingICE x/y/action do not position the FlyBody body.",
        "same-decision aligned",
    )
    require(
        "app/api/live/route.ts",
        FLYBODY_COMMIT,
        FLYBODY_ADAPTER,
        'flybody_policy_access: false',
        'flybody_game_telemetry_position_used: false',
        'learning_enabled: false',
        'policy_pixel_access: false',
    )
    require(
        "lib/vercel-sandbox.ts",
        "process.env.VERCEL_PROJECT_ID",
        "process.env.VERCEL_OIDC_TOKEN",
        "payment_required",
    )
    require(
        "lib/connectome-broadcast.ts",
        BROADCAST_TARGET,
        'CONNECTOME_MUJOCO_GL: "osmesa"',
        'CONNECTOME_LEARNING_ENABLED: "false"',
        'CONNECTOME_POLICY_PIXEL_ACCESS: "false"',
    )

    require(
        ".github/workflows/vercel-live-arena-smoke.yml",
        "CONNECTOME_PUBLIC_BASE_URL",
        "/api/live",
        BROADCAST_TARGET,
        "Require synchronized sensory-to-motor FightingICE telemetry",
        "rounds_per_session==6",
        "sensory_drive",
        "output_contributions",
    )
    forbid(
        ".github/workflows/vercel-live-arena-smoke.yml",
        "/api/connectome/session",
        "Launch real GARNET vs ZEN session from runtime snapshot",
    )
    require(
        ".github/workflows/precompile-arena-brian2-cython-cache.yml",
        "Publish compilerless canonical runtime assets",
        "Repack deterministic runtime archive",
        "Deployment staging is intentionally owned by the dedicated Connectome Vercel project",
    )
    forbid(
        ".github/workflows/precompile-arena-brian2-cython-cache.yml",
        "/api/connectome/runtime-base",
        "/api/connectome/live",
        "PUBLIC_BASE",
    )
    require(
        ".github/workflows/publish-flybody-runtime-addon.yml",
        "precompile-arena-brian2-cython-cache",
        FLYBODY_COMMIT,
        FLYBODY_ADAPTER,
        "zero_phase_invariant",
        "action_dim':59",
        "Deterministically repack and replace rolling runtime assets",
    )
    require(
        ".github/workflows/deploy-dedicated-vercel.yml",
        "connectome-fighter-live",
        "CONNECTOME_VERCEL_TOKEN",
        "vercel project add",
        "vercel deploy --prod",
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
        "dedicated public-surface contract: PASS "
        f"historical_runtime={str(proof['runtime_archive_sha256'])[:16]} "
        f"broadcast={BROADCAST_TARGET} flybody_adapter={FLYBODY_ADAPTER} production_e2e=pending"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
