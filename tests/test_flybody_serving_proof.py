"""Engineering fixtures only: these tests never contact production or prove biology."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit
import zlib

SPEC = importlib.util.spec_from_file_location(
    "flybody_serving_proof", Path(__file__).resolve().parents[1] / "scripts/verify_live_flybody.py")
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)
BASE = "https://connectome-fighter.vercel.app"


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def png(shift=0, blank=False):
    row = bytes(960) if blank else bytes((n + shift) % 256 for n in range(960))
    raw = (b"\0" + row) * 240
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 320, 240, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def fixture(step=1):
    images = {"p1": png(step), "p2": png(step + 3)}
    decision = {"round": 1, "frame": step * 60, "decision_index": step}
    live = {"status": "running", "round": 1, "frame": step * 60,
            "brain": {s: {"decision_index": step} for s in images}}
    activity = {"kind": "male-cns-live-anatomy-activity", "policy_access": False,
                "sides": {s: dict(decision) for s in images}}
    state = {"schema_version": 2, "publisher": proof.PUBLISHER,
             "kind": "malecns-flybody-live-physics", "policy_access": False,
             "game_telemetry_position_used": False, "adapter": proof.ADAPTER,
             "mujoco_gl": "osmesa", "upstream": {"repository": "TuragaLab/flybody", "commit": proof.UPSTREAM},
             "stale_after_seconds": 30.0, "render": {"width": 320, "height": 240, "frames": step},
             "sides": {}}
    for side, raw in images.items():
        state["sides"][side] = {"decision": dict(decision), "input_status": "fresh",
                                "input_age_seconds": 0.1, "input_epoch": 0,
                                "png_sha256": hashlib.sha256(raw).hexdigest(),
                                "neural_command": {"adapter": proof.ADAPTER, "drive": 0.5,
                                                   "source_spikes": 16.0, "source_body_ids": [101]},
                                "physics": {"action_dimension": 59, "sim_steps": 16 * step,
                                            "control_timestep_seconds": 0.002, "sim_time_seconds": 0.032 * step,
                                            "dropped_time_seconds": 0.0, "pending_time_seconds": 0.0,
                                            "resets": 0, "timebase": "executed-physics-control-steps"}}
    endpoints = {"telemetry_url": BASE + "/telemetry.json", "activity_url": BASE + "/activity.json",
                 "flybody_state_url": BASE + "/flybody.json", "flybody_p1_url": BASE + "/flybody-p1.png",
                 "flybody_p2_url": BASE + "/flybody-p2.png"}
    control = {"ready": True, "status": "running", "learning_enabled": False, "policy_pixel_access": False,
               "flybody_policy_access": False, "flybody_game_telemetry_position_used": False,
               "flybody_neural_adapter": proof.ADAPTER, "runtime_archive_sha256": "a" * 64, **endpoints}
    return {"control": control, "telemetry": live, "activity": activity, "state": state, "images": images,
            "endpoints": endpoints, "runtime_archive_sha256": "a" * 64, "metrics": {}}


class ServingProofTests(unittest.TestCase):
    def setUp(self):
        self.sample = fixture()

    def validate(self, sample=None):
        s = sample or self.sample
        return proof.validate_snapshot(s["telemetry"], s["activity"], s["state"], s["images"])

    def test_v2_matched_snapshot_passes(self):
        self.assertEqual(self.validate()["p1"]["width"], 320)

    def test_old_schema_and_missing_publisher_rejected(self):
        for field, value in (("schema_version", 1), ("publisher", None)):
            with self.subTest(field=field), self.assertRaises(proof.ProofError):
                s = fixture(); s["state"][field] = value; self.validate(s)

    def test_state_hash_required_and_checked_on_both_sides(self):
        for side in ("p1", "p2"):
            for value in (None, "f" * 64):
                with self.subTest(side=side, value=value), self.assertRaises(proof.ProofError):
                    s = fixture(); s["state"]["sides"][side]["png_sha256"] = value; self.validate(s)

    def test_individually_valid_pngs_from_other_tick_rejected(self):
        self.sample["images"]["p2"] = png(99)
        with self.assertRaisesRegex(proof.ProofError, "hash mismatch"):
            self.validate()

    def test_stale_missing_or_expired_input_rejected(self):
        for status, age in (("stale", 31), ("missing", None), ("fresh", 30), ("fresh", -1)):
            with self.subTest(status=status, age=age), self.assertRaises(proof.ProofError):
                s = fixture(); s["state"]["sides"]["p1"].update(input_status=status, input_age_seconds=age)
                self.validate(s)

    def test_neural_activity_must_match_each_identity_component(self):
        for side in ("p1", "p2"):
            for field in ("round", "frame", "decision_index"):
                with self.subTest(side=side, field=field), self.assertRaises(proof.ProofError):
                    s = fixture(); s["activity"]["sides"][side][field] += 1; self.validate(s)

    def test_telemetry_must_match(self):
        self.sample["telemetry"]["brain"]["p2"]["decision_index"] = 9
        with self.assertRaises(proof.ProofError): self.validate()

    def test_missing_or_boolean_identity_does_not_coerce_to_integer(self):
        for value in (None, True, "1", -1):
            with self.subTest(value=value), self.assertRaises(proof.ProofError):
                proof.identity({"round": 1, "frame": 60, "decision_index": value})

    def test_nonfinite_negative_and_inconsistent_physics_clock_rejected(self):
        for field, value in (("control_timestep_seconds", float("nan")), ("sim_time_seconds", 99),
                             ("dropped_time_seconds", -1), ("sim_steps", 0), ("resets", True)):
            with self.subTest(field=field), self.assertRaises(proof.ProofError):
                s = fixture(); s["state"]["sides"]["p1"]["physics"][field] = value; self.validate(s)

    def test_command_requires_real_positive_body_id_shape(self):
        for value in (None, [True], [0], ["101"], []):
            with self.subTest(value=value), self.assertRaises(proof.ProofError):
                s = fixture(); s["state"]["sides"]["p1"]["neural_command"]["source_body_ids"] = value
                self.validate(s)

    def test_provenance_or_spectator_boundary_mismatch_rejected(self):
        for field, value in (("policy_access", True), ("game_telemetry_position_used", True),
                             ("mujoco_gl", "egl"), ("adapter", "wrong"), ("upstream", {})):
            with self.subTest(field=field), self.assertRaises(proof.ProofError):
                s = fixture(); s["state"][field] = value; self.validate(s)

    def test_control_boundaries_cannot_be_omitted_or_enabled(self):
        for field in ("learning_enabled", "policy_pixel_access", "flybody_policy_access",
                      "flybody_game_telemetry_position_used"):
            with self.subTest(field=field), self.assertRaises(proof.ProofError):
                c = fixture()["control"]; c.pop(field); proof.validate_control(c)

    def test_png_crc_blank_and_truncated_images_rejected(self):
        data = bytearray(png()); data[40] ^= 1
        for raw in (bytes(data), png(blank=True), png()[:-1], png() + b"trailing"):
            with self.subTest(size=len(raw)), self.assertRaises(proof.ProofError): proof.png_metrics(raw)

    def test_http503_capacity_json_is_preserved_and_classified(self):
        body = {"status": "capacity-blocked", "provider_error_code": "payment_required",
                "blocked_until": "2026-10-01T00:00:00Z"}
        error = HTTPError(BASE + "/api/live", 503, "unavailable", {}, io.BytesIO(json.dumps(body).encode()))
        with patch.object(proof, "urlopen", side_effect=error):
            status, raw = proof.http_get(BASE + "/api/live", 1)
        self.assertEqual(status, 503)
        with self.assertRaises(proof.CapacityBlocked): proof.json_response((status, raw))

    def test_nonquota_errors_are_not_capacity(self):
        for response in ((503, b'{"status":"warming"}'), (401, b'{"error":"login"}'),
                         (200, b'[]'), (200, b'{"value":NaN}')):
            with self.subTest(response=response), self.assertRaises(proof.ProofError) as caught:
                proof.json_response(response)
            self.assertNotIsInstance(caught.exception, proof.CapacityBlocked)

    def test_unrelated_or_credentialed_urls_are_refused(self):
        for url in ("https://liveunjuno.vercel.app", "https://hiroeco-public-demo.vercel.app",
                    "https://liveunjuno-123.vercel.app", "http://example.test", "https://user:pass@example.test"):
            with self.subTest(url=url), self.assertRaises(proof.ProofError): proof.safe_url(url)

    def test_cache_buster_preserves_existing_query(self):
        url = proof.cache_bust(BASE + "/flybody.json?x=1&_proof=old")
        self.assertIn("x=1", url); self.assertEqual(url.count("_proof="), 1); self.assertNotIn("old", url)

    def test_two_progressing_samples_pass(self):
        self.assertTrue(proof.progressed(fixture(1), fixture(2)))

    def test_static_or_partially_progressing_sample_cannot_pass(self):
        self.assertFalse(proof.progressed(self.sample, self.sample))
        s = fixture(2); s["state"]["sides"]["p2"]["decision"] = self.sample["state"]["sides"]["p2"]["decision"]
        self.assertFalse(proof.progressed(self.sample, s))

    def test_frozen_png_or_zero_drive_cannot_prove_motion(self):
        for field, value in (("png_sha256", self.sample["state"]["sides"]["p1"]["png_sha256"]),
                             ("neural_command", {"drive": 0})):
            with self.subTest(field=field):
                s = fixture(2); s["state"]["sides"]["p1"][field] = value
                self.assertFalse(proof.progressed(self.sample, s))

    def test_session_or_runtime_changes_cannot_be_joined(self):
        for field in ("input_epoch", "resets", "endpoint", "runtime"):
            with self.subTest(field=field):
                s = fixture(2)
                if field == "input_epoch": s["state"]["sides"]["p1"][field] = 1
                elif field == "resets": s["state"]["sides"]["p1"]["physics"][field] = 1
                elif field == "endpoint": s["endpoints"]["telemetry_url"] += "?new=1"
                else: s["runtime_archive_sha256"] = "b" * 64
                self.assertFalse(proof.progressed(self.sample, s))

    def test_capacity_stops_after_one_request_and_writes_uncertain_report(self):
        calls = []
        def get(url, timeout):
            calls.append(url)
            return 503, b'{"capacity_blocked":true,"provider_error_code":"payment_required"}'
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            code = proof.run_probe(BASE, folder, attempts=4, interval=0, getter=get)
            report = json.loads((Path(folder) / "report.json").read_text())
        self.assertEqual((code, len(calls), report["result"]), (2, 1, "UNCERTAIN"))

    def test_get_only_collection_and_evidence_output(self):
        state = {"step": 0, "calls": []}
        def get(url, timeout):
            path = urlsplit(url).path; state["calls"].append(path)
            if path == "/api/live": state["step"] += 1
            sample = fixture(state["step"])
            names = {"/api/live": "control", "/flybody.json": "state", "/telemetry.json": "telemetry",
                     "/activity.json": "activity"}
            if path in names: return 200, json.dumps(sample[names[path]]).encode()
            return 200, sample["images"]["p1" if path == "/flybody-p1.png" else "p2"]
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            code = proof.run_probe(BASE, folder, attempts=3, interval=0, getter=get)
            report = json.loads((Path(folder) / "report.json").read_text())
            self.assertTrue((Path(folder) / "first/p1.png").exists())
            self.assertTrue((Path(folder) / "second/state.json").exists())
        self.assertEqual((code, report["result"], state["step"]), (0, "PASS", 2))
        self.assertNotIn("/api/runtime-base", state["calls"])

    def test_polling_retains_baseline_until_both_sides_advance(self):
        first, partial, final = fixture(1), fixture(2), fixture(2)
        partial["state"]["sides"]["p2"]["decision"]["decision_index"] = 1
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()), \
                patch.object(proof, "collect", side_effect=[first, partial, final]):
            self.assertEqual(proof.run_probe(BASE, folder, attempts=3, interval=0), 0)

    def test_exhausted_network_errors_never_pass(self):
        def get(url, timeout): raise OSError("network unavailable")
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            code = proof.run_probe(BASE, folder, attempts=2, interval=0, getter=get)
            report = json.loads((Path(folder) / "report.json").read_text())
        self.assertNotEqual(code, 0); self.assertEqual(report["result"], "UNCERTAIN")


if __name__ == "__main__":
    unittest.main()
