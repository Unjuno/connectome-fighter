from pathlib import Path


def test_public_live_publication_gate_keeps_observation_boundaries():
    text = (Path(__file__).resolve().parents[1] / "docs" / "LIVE_PUBLICATION_GATE.md").read_text(encoding="utf-8")
    for needle in [
        "official `ScreenData`",
        "policy_pixel_access=false",
        "real sensory-body drive",
        "official released MaleCNS v1.0 SWC",
        "320 CSS px",
        "never auto-promoted",
    ]:
        assert needle in text
