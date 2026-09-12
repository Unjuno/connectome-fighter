#!/usr/bin/env python3
"""Fail CI when public documentation/workflows drift from the shared-LIVE contract."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
        raise SystemExit(f"{path}: retired public architecture text returned: {found}")


def main() -> int:
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
        "GARNET generation 2 = APPROVED INFERENCE",
        "ZEN generation 2 = CANDIDATE LINEAGE",
        "continuous production reward-driven learning は OFF",
        "Public Surface Freeze",
    )
    forbid(
        "README.ja.md",
        "GitHub Actions（毎時）",
        "3本rolling queue",
        "Vercel 30秒poll",
        "rolling spectatorを複数scheduled run",
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
        "single-shared-live-broadcast",
        "connectome-live-broadcast",
        "Historical rolling-video spectator — RETAINED EVIDENCE, NOT PRIMARY LIVE",
        "Current gate — Public Surface Freeze",
    )
    forbid(
        "docs/STATUS.md",
        "Current production spectator — PASS",
        "Vercel viewer polls every 30 s",
        "P6 — freeze spectator/data contracts",
    )

    require(
        "docs/PUBLIC_SURFACE_SPLIT.md",
        "single shared live broadcast",
        "connectome-live-broadcast",
        "learning_enabled=false",
        "policy_pixel_access=false",
        "Public-surface freeze gate",
    )
    forbid(
        "docs/PUBLIC_SURFACE_SPLIT.md",
        "short-lived per-viewer inference",
        "isolated viewer-specific inference session",
        "production runtime image/service is still being provisioned",
    )

    require(
        "docs/PUBLIC_SURFACE_SPLIT.ja.md",
        "single shared live broadcast",
        "GARNET approved generation-2 inference vs ZEN canonical baseline",
        "Production reward-driven learning は現在 **OFF**",
        "Public Surface Freeze gate",
        "毎時 schedule は停止済み",
    )

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
        "GARNET generation 2",
        "candidate cross-run resume proven",
    )
    require(
        "site/app.js",
        "Public Surface Freeze · data:",
        "Project gate: Public Surface Freeze; latest baseline data phase:",
    )

    require(
        ".github/workflows/vercel-live-arena-smoke.yml",
        "/api/connectome/live",
        "single-shared-live-broadcast",
        "shared-global",
        "connectome-live-broadcast",
        "shared_broadcast_only",
    )
    forbid(
        ".github/workflows/vercel-live-arena-smoke.yml",
        "per-viewer-live-sandbox",
        "Launch real GARNET vs ZEN session from runtime snapshot",
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

    print("public-surface contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
