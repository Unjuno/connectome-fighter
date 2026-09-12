from pathlib import Path


def test_official_frame_publisher_is_spectator_only():
    root = Path(__file__).resolve().parents[1]
    frame = (root / "src/connectome_fighter/fightingice_live_frame.py").read_text(encoding="utf-8")
    runner = (root / "scripts/run_live_screen_publisher.py").read_text(encoding="utf-8")
    start = (root / "deploy/arena-runtime/start-session.sh").read_text(encoding="utf-8")
    proxy = (root / "deploy/arena-runtime/bootstrap-proxy.mjs").read_text(encoding="utf-8")

    assert "StreamInterface" in frame
    class_source = frame.split("class FightingICELiveFramePublisher", 1)[1]
    # The explicit negative safety flag is expected; control-policy APIs are not.
    assert '"policy_pixel_access": False' in class_source
    assert "Decision(" not in class_source
    assert "def act(" not in class_source
    assert "observation" not in class_source.lower()
    assert "gateway.register_stream" in runner
    assert "run_live_screen_publisher.py" in start
    assert "--screen-file" in start
    assert "'/screen.png'" in proxy
    assert "image/png" in proxy
