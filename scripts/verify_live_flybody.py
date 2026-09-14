#!/usr/bin/env python3
"""Read-only FlyBody v2 serving proof; no training or deployment mutations.

PASS requires two progressing, hash-bound snapshots. The decision identifies
held neural input, not lossless replay or a biological innervation map.
Only the publisher's RGB8, filter-0 PNG format is accepted. Python >=3.11;
standard library only. All durations are seconds, phases radians, hashes hex.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct
import time
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import zlib

ADAPTER = "malecns-annotated-motor-to-flybody-tripod-v2"
PUBLISHER = "malecns-flybody-publisher-v2"
UPSTREAM = "d015e9bfe441bd90ae431bac24c55cb74bdbce26"
MAX_BYTES = 4 * 1024 * 1024


class ProofError(ValueError):
    """A snapshot is not sufficient evidence; never silently pass it."""


class CapacityBlocked(ProofError):
    def __init__(self, body):
        super().__init__("capacity-blocked")
        self.details = {k: body.get(k) for k in
                        ("status", "provider_error_code", "blocked_until")}


def require(ok, message):
    if not ok:
        raise ProofError(message)


def object_at(value, key):
    child = value.get(key) if isinstance(value, dict) else None
    require(isinstance(child, dict), f"missing object: {key}")
    return child


def number(value, label, *, positive=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0), f"invalid {label}")
    return value


def counter(value, label, *, positive=False):
    require(type(value) is int, f"invalid integer {label}")
    return number(value, label, positive=positive)


def safe_url(url):
    require(isinstance(url, str), "missing endpoint URL")
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    require(p.scheme == "https" and host and not p.username and not p.password
            and not p.fragment, "endpoint must be credential-free HTTPS")
    require(host != "liveunjuno.vercel.app" and not host.startswith("liveunjuno-")
            and not host.startswith("hiroeco-public-demo"), "unrelated project refused")
    return url


def cache_bust(url):
    p = urlsplit(safe_url(url))
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != "_proof"]
    query.append(("_proof", str(time.time_ns())))
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(query), ""))


def http_get(url, timeout):
    request = Request(cache_bust(url), headers={"Cache-Control": "no-cache"})
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as error:
        response = error  # Preserve JSON on 503; curl -f discarded quota evidence.
    with response:
        raw = response.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES, "response exceeds byte limit")
        return response.status, raw


def json_response(response):
    status, raw = response
    try:
        body = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ProofError(f"HTTP {status}: invalid JSON") from error
    require(isinstance(body, dict), "JSON response must be an object")
    if (body.get("status") == "capacity-blocked" or body.get("capacity_blocked") is True
            or body.get("provider_error_code") == "payment_required"):
        raise CapacityBlocked(body)
    require(status == 200, f"HTTP {status}: not ready")
    return body


def png_metrics(raw):
    require(raw[:8] == b"\x89PNG\r\n\x1a\n" and len(raw) <= MAX_BYTES, "invalid PNG")
    offset, compressed, header, ended = 8, bytearray(), None, False
    while offset + 12 <= len(raw):
        size = struct.unpack_from(">I", raw, offset)[0]
        end = offset + 12 + size
        require(end <= len(raw), "truncated PNG chunk")
        kind = raw[offset + 4:offset + 8]
        data = raw[offset + 8:end - 4]
        crc = struct.unpack_from(">I", raw, end - 4)[0]
        require(zlib.crc32(kind + data) & 0xffffffff == crc, "PNG CRC mismatch")
        if header is None:
            require(kind == b"IHDR" and size == 13, "missing PNG IHDR")
            header = struct.unpack(">IIBBBBB", data)
            require(header == (320, 240, 8, 2, 0, 0, 0), "unexpected PNG format/dimensions")
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            require(size == 0 and end == len(raw), "invalid PNG end")
            ended = True
            break
        else:
            raise ProofError("unexpected publisher PNG chunk")
        offset = end
    require(ended and compressed, "incomplete PNG")
    expected = 240 * (1 + 320 * 3)
    inflater = zlib.decompressobj()
    try:
        pixels = inflater.decompress(compressed, expected + 1)
    except zlib.error as error:
        raise ProofError("invalid PNG compressed data") from error
    require(len(pixels) == expected and inflater.eof and not inflater.unused_data
            and not inflater.unconsumed_tail, "invalid PNG decoded length")
    rows = [pixels[y * 961:(y + 1) * 961] for y in range(240)]
    require(all(row[0] == 0 for row in rows), "unexpected PNG filter")
    values = b"".join(row[1:] for row in rows)
    mean = sum(values) / len(values)
    std = math.sqrt(max(0.0, sum(v * v for v in values) / len(values) - mean * mean))
    unique = len({values[i:i + 3] for i in range(0, len(values), 3)})
    require(std >= 2.0 and unique >= 8, "blank physical image")
    return {"width": 320, "height": 240, "unique_rgb": unique, "channel_std": std}


def identity(value):
    require(isinstance(value, dict), "missing decision identity")
    return tuple(counter(value.get(k), k, positive=(k != "round"))
                 for k in ("round", "frame", "decision_index"))


def validate_snapshot(live, activity, state, images):
    require(live.get("status") == "running", "telemetry not running")
    require(activity.get("kind") == "male-cns-live-anatomy-activity"
            and activity.get("policy_access") is False, "invalid neural activity contract")
    require(state.get("schema_version") == 2 and state.get("publisher") == PUBLISHER
            and state.get("kind") == "malecns-flybody-live-physics", "publisher v2 required")
    require(state.get("policy_access") is False and state.get("game_telemetry_position_used") is False,
            "spectator boundary violated")
    require(state.get("adapter") == ADAPTER and state.get("mujoco_gl") == "osmesa"
            and state.get("upstream") == {"repository": "TuragaLab/flybody", "commit": UPSTREAM},
            "FlyBody provenance mismatch")
    render = object_at(state, "render")
    require((render.get("width"), render.get("height")) == (320, 240), "state render dimensions")
    counter(render.get("frames"), "render frames", positive=True)
    stale = number(state.get("stale_after_seconds"), "stale timeout", positive=True)
    metrics = {}
    for side in ("p1", "p2"):
        item = object_at(object_at(state, "sides"), side)
        decision = identity(item.get("decision"))
        brain = object_at(object_at(live, "brain"), side)
        expected = identity({"round": live.get("round"), "frame": live.get("frame"),
                             "decision_index": brain.get("decision_index")})
        require(decision == expected == identity(object_at(object_at(activity, "sides"), side)),
                f"{side}: neural/telemetry/physics identity mismatch")
        require(item.get("input_status") == "fresh", f"{side}: stale/missing neural input")
        require(number(item.get("input_age_seconds"), "input age") < stale, "input expired")
        counter(item.get("input_epoch"), "input epoch")
        command = object_at(item, "neural_command")
        require(command.get("adapter") == ADAPTER, "command adapter mismatch")
        require(number(command.get("drive"), "neural drive") <= 1, "neural drive out of range")
        number(command.get("source_spikes"), "source spikes")
        ids = command.get("source_body_ids")
        require(isinstance(ids, list) and all(type(v) is int and v > 0 for v in ids), "invalid body IDs")
        if command["drive"] > 0:
            require(ids and command["source_spikes"] > 0, "driven body has no neural source")
        physics = object_at(item, "physics")
        require(physics.get("action_dimension") == 59
                and physics.get("timebase") == "executed-physics-control-steps", "invalid physical contract")
        steps = counter(physics.get("sim_steps"), "sim steps", positive=True)
        dt = number(physics.get("control_timestep_seconds"), "control timestep", positive=True)
        elapsed = number(physics.get("sim_time_seconds"), "sim time", positive=True)
        require(math.isclose(elapsed, steps * dt, rel_tol=1e-7, abs_tol=1e-9), "physics clock mismatch")
        number(physics.get("dropped_time_seconds"), "dropped time")
        number(physics.get("pending_time_seconds"), "pending time")
        counter(physics.get("resets"), "resets")
        raw = images.get(side)
        require(isinstance(raw, bytes), "missing PNG bytes")
        require(item.get("png_sha256") == hashlib.sha256(raw).hexdigest(), f"{side}: state/PNG hash mismatch")
        metrics[side] = png_metrics(raw)
    return metrics


def validate_control(body):
    require(body.get("ready") is True and body.get("status") == "running", "control plane warming")
    for key in ("learning_enabled", "policy_pixel_access", "flybody_policy_access",
                "flybody_game_telemetry_position_used"):
        require(body.get(key) is False, f"control boundary: {key}")
    require(body.get("flybody_neural_adapter") == ADAPTER, "control adapter mismatch")
    return {k: safe_url(body.get(k)) for k in
            ("telemetry_url", "activity_url", "flybody_state_url", "flybody_p1_url", "flybody_p2_url")}


def collect(base, getter, timeout):
    control = json_response(getter(base.rstrip("/") + "/api/live", timeout))
    endpoints = validate_control(control)
    state = json_response(getter(endpoints["flybody_state_url"], timeout))
    keys = ("telemetry_url", "activity_url", "flybody_p1_url", "flybody_p2_url")
    # Fetch siblings together; matching hashes, not request order, establish binding.
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = dict(zip(keys, pool.map(lambda key: getter(endpoints[key], timeout), keys)))
    live = json_response(responses["telemetry_url"])
    activity = json_response(responses["activity_url"])
    images = {}
    for side in ("p1", "p2"):
        status, raw = responses[f"flybody_{side}_url"]
        require(status == 200, f"{side}: PNG HTTP {status}")
        images[side] = raw
    metrics = validate_snapshot(live, activity, state, images)
    return {"state": state, "telemetry": live, "activity": activity,
            "images": images, "metrics": metrics, "endpoints": endpoints,
            "runtime_archive_sha256": control.get("runtime_archive_sha256")}


def same_session(first, second):
    if (first["endpoints"] != second["endpoints"] or
            first["runtime_archive_sha256"] != second["runtime_archive_sha256"]):
        return False
    a, b = first["state"], second["state"]
    if b["render"]["frames"] < a["render"]["frames"]:
        return False
    for side in ("p1", "p2"):
        old, new = a["sides"][side], b["sides"][side]
        if (old["input_epoch"] != new["input_epoch"]
                or old["physics"]["resets"] != new["physics"]["resets"]
                or new["physics"]["sim_steps"] < old["physics"]["sim_steps"]):
            return False
    return True


def progressed(first, second):
    if not same_session(first, second):
        return False
    a, b = first["state"], second["state"]
    if b["render"]["frames"] <= a["render"]["frames"]:
        return False
    for side in ("p1", "p2"):
        old, new = a["sides"][side], b["sides"][side]
        previous, current = identity(old["decision"]), identity(new["decision"])
        advance = (current[0] > previous[0] or (current[0] == previous[0]
                   and current[1] > previous[1] and current[2] > previous[2]))
        if (old["input_epoch"] != new["input_epoch"] or not advance
                or old["physics"]["resets"] != new["physics"]["resets"]
                or new["physics"]["sim_steps"] <= old["physics"]["sim_steps"]
                or new["physics"]["sim_time_seconds"] <= old["physics"]["sim_time_seconds"]
                or old["png_sha256"] == new["png_sha256"]
                or new["neural_command"]["drive"] <= 0):
            return False
    return True


def save_sample(folder, sample):
    folder.mkdir(parents=True, exist_ok=True)
    for key in ("state", "telemetry", "activity", "metrics"):
        (folder / f"{key}.json").write_text(json.dumps(sample[key], indent=2, allow_nan=False) + "\n")
    for side, raw in sample["images"].items():
        (folder / f"{side}.png").write_bytes(raw)


def run_probe(base, output, *, attempts=80, max_seconds=180.0, interval=1.0, getter=http_get):
    safe_url(base)
    parsed_base = urlsplit(base)
    require(parsed_base.path in ("", "/") and not parsed_base.query, "base URL must be an origin")
    counter(attempts, "attempt count", positive=True)
    number(max_seconds, "deadline", positive=True)
    number(interval, "retry interval")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max_seconds
    first, report, code = None, {"result": "UNCERTAIN", "reason": "no matched snapshots"}, 1
    for attempt in range(1, attempts + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        report["attempts"] = attempt
        try:
            sample = collect(base, getter, min(5.0, max(0.05, remaining / 3)))
            if first is not None and progressed(first, sample):
                save_sample(output / "first", first)
                save_sample(output / "second", sample)
                report.update(result="PASS", reason="two progressing hash-bound neural/physics snapshots",
                              runtime_archive_sha256=sample["runtime_archive_sha256"])
                code = 0
                break
            # Keep the baseline until BOTH sides progress, even when their
            # decisions arrive on different polls. Rebase only on a restart.
            if first is None or not same_session(first, sample):
                first = sample
            report["reason"] = "awaiting both-side decision/physics/image progression"
        except CapacityBlocked as error:
            report.update(result="UNCERTAIN", reason="capacity-blocked", capacity=error.details)
            code = 2
            break  # No further requests after a provider capacity error.
        except (ProofError, OSError, TimeoutError) as error:
            report["reason"] = str(error)
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
    report.update(checked_at=datetime.now(timezone.utc).isoformat(),
                  proof_kind="public-flybody-v2-serving", max_seconds=max_seconds,
                  interpretation_boundary="Serving integrity and observed progression only; not causal biology, lossless replay, or realtime-speed proof.")
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, sort_keys=True))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, default=Path("runs/flybody-serving-proof"))
    parser.add_argument("--max-seconds", type=float, default=180.0)
    args = parser.parse_args()
    try:
        return run_probe(args.base_url, args.output, max_seconds=args.max_seconds)
    except ProofError as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
