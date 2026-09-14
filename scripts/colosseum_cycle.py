#!/usr/bin/env python3
"""Run one bounded candidate cycle: parent evaluation, collection, update, evaluation.

Invoked on GitHub's runner, not on Vercel. Real MaleCNS/Shiu/FightingICE only.
Publication is a separate trusted-main job. No approved-inference writes.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time

REPO = "Unjuno/connectome-fighter"
LINEAGE = "colosseum-r3-v1"
PROTOCOL = "colosseum-fixed-full-round-v1"
FRAME_LIMIT = 3600
DECISION_INTERVAL = 15
P1 = "GARNET"
EVAL_P2 = "ZEN"
EVAL_SEEDS = (800101, 20202)
ROOT = Path(__file__).resolve().parents[1]


def stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n")


def run(args, **kwargs):
    return subprocess.run([str(v) for v in args], check=True, **kwargs)


def release(tag, *, missing_ok=False):
    p = subprocess.run(["gh", "api", f"repos/{REPO}/releases/tags/{tag}"], capture_output=True, text=True)
    if p.returncode:
        if missing_ok and "HTTP 404" in p.stderr:
            return None
        raise RuntimeError(f"Cannot resolve release {tag}: {p.stderr[:500]}")
    return json.loads(p.stdout)


def asset(rel, name, target):
    matches = [x for x in rel["assets"] if x["name"] == name and x["state"] == "uploaded"]
    if len(matches) != 1:
        raise ValueError(f"Unique uploaded asset required: {name}")
    selected = matches[0]
    expected = str(selected.get("digest", ""))
    if not expected.startswith("sha256:") or len(expected) != 71:
        raise ValueError(f"Asset digest missing: {name}")
    with Path(target).open("wb") as handle:
        run(["gh", "api", f"repos/{REPO}/releases/assets/{selected['id']}", "-H", "Accept: application/octet-stream"], stdout=handle)
    if digest(target) != expected[7:]:
        raise ValueError(f"Asset checksum mismatch: {name}")
    return {"release_tag": rel["tag_name"], "asset_id": selected["id"], "sha256": expected[7:]}


def restore(out):
    """Resume only a hash-bound candidate, or explicitly fork the legacy lane."""
    folder = out / "checkpoint"
    folder.mkdir(parents=True)
    pointer = release("colosseum-latest", missing_ok=True)
    previous_index = None
    if pointer:
        asset(pointer, "status.json", out / "previous-status.json")
        previous_index = json.loads((out / "previous-status.json").read_text())
        if previous_index.get("lineage") != LINEAGE or previous_index.get("status") != "evaluation-ready":
            raise ValueError("Invalid latest colosseum pointer")
        tag = previous_index["checkpoint"]["release_tag"]
        selected = release(tag)
        identity = asset(selected, "candidate.tar.gz", out / "source.tar.gz")
        if identity["sha256"] != previous_index["checkpoint"]["archive_sha256"]:
            raise ValueError("Pointer/archive identity mismatch")
        expected_members = {"state/GARNET.npz", "state/GARNET.npz.json", "lineage.json"}
    else:
        selected = release("canonical-training-latest")
        identity = asset(selected, "garnet-training-latest.tar.gz", out / "source.tar.gz")
        expected_members = {"state/GARNET.npz", "state/GARNET.npz.json"}
    with tarfile.open(out / "source.tar.gz", "r:gz") as tar:
        found = set()
        for member in tar.getmembers():
            name = member.name.removeprefix("./")
            if name not in expected_members:
                continue
            if not member.isfile() or member.size > 64 * 1024 * 1024:
                raise ValueError("Invalid checkpoint member")
            dest = folder / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            found.add(name)
        if found != expected_members:
            raise ValueError("Required checkpoint members missing")
    write(out / "source-identity.json", identity)
    return folder, previous_index, identity


def config_object(path):
    from update_malecns_valence_plasticity import plasticity_config
    raw = json.loads(Path(path).read_text())
    return plasticity_config(raw, raw["reward_config"])


def prepare_state(folder, candidates, previous, source):
    from connectome_fighter.valence_plasticity import load_state, save_state
    state_path = folder / "state/GARNET.npz"
    import pandas as pd
    n = len(pd.read_parquet(candidates))
    cfg = config_object(ROOT / "configs/plasticity_colosseum_v1.json")
    old_cfg = cfg if previous else config_object(ROOT / "configs/plasticity_valence_v0.json")
    state = load_state(state_path, expected_character=P1, n_candidates=n,
                       expected_candidate_sha256=digest(candidates), config=old_cfg)
    if previous:
        if previous["training"]["state_sha256"] != digest(state_path):
            raise ValueError("Restored state differs from published pointer")
        lineage = json.loads((folder / "lineage.json").read_text())
        if lineage["id"] != LINEAGE:
            raise ValueError("Wrong lineage")
    else:
        lineage = {"id": LINEAGE, "created_at": stamp(), "fork_parent": {
            **source, "state_sha256": digest(state_path), "generation": state.generation,
            "matches": state.matches, "reward_id": old_cfg.reward_id,
            "plasticity_config_sha256": old_cfg.fingerprint()},
            "new_reward_id": cfg.reward_id, "new_config_sha256": cfg.fingerprint(),
            "fork_rule": "Copy parent multipliers exactly; reset season counters; do not reinterpret legacy generations."}
        before = state.multipliers.copy()
        state.config_sha256 = cfg.fingerprint()
        state.generation = state.matches = state.update_events = 0
        save_state(state_path, state, cfg)
        import numpy as np
        with np.load(state_path, allow_pickle=False) as z:
            if not np.array_equal(before, z["multipliers"]):
                raise ValueError("Fork altered inherited multipliers")
        write(folder / "lineage.json", lineage)
    return state_path, lineage


def round_metrics(row):
    if row.get("terminated") is not True or row.get("truncated") is not False:
        raise ValueError("Incomplete match cannot produce a colosseum result")
    from collections import Counter
    hps = [max(0, int(v)) for v in row["remaining_hps"]]
    ts = row["transitions"]
    counts = Counter(str(t["action"]) for t in ts)
    distances = [abs(float(t["display"]["p1"]["x"]) - float(t["display"]["p2"]["x"])) for t in ts]
    return {"winner": P1 if hps[0] > hps[1] else EVAL_P2 if hps[0] < hps[1] else "DRAW",
            "p1_hp": hps[0], "p2_hp": hps[1], "hp_margin": hps[0] - hps[1],
            "damage_dealt_hp": 400 - hps[1], "damage_taken_hp": 400 - hps[0],
            "no_damage_draw": hps == [400, 400],
            "elapsed_frame": row["elapsed_frame"], "elapsed_seconds": row["elapsed_frame"] / 60.0,
            "ended_by": "KO" if min(hps) <= 0 else "TIME_LIMIT" if row["elapsed_frame"] >= FRAME_LIMIT else "ROUND_END",
            "decisions": len(ts), "action_counts": dict(counts),
            "mean_separation_px": sum(distances) / len(distances),
            "contact_fraction": sum(d <= 180 for d in distances) / len(distances)}


def match(runtime, out, name, adapter, opponent, seeds, *, trainable=False, video=False):
    work = out / name
    work.mkdir()
    py = runtime / (runtime / "runtime/python311.path").read_text().strip()
    ref = runtime / (runtime / "runtime/python310.path").read_text().strip()
    wrapper = out / "reference-python"
    wrapper.write_text(f'#!/bin/sh\nexport PYTHONPATH="{runtime}/runtime/site310"\nexec "{ref}" "$@"\n')
    wrapper.chmod(0o755)
    env = {**os.environ, "PYTHONPATH": f"{runtime}/repo/src:{runtime}/runtime/site311",
           "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
    java = runtime / "runtime/jre21/bin/java"
    j = str(java) if java.exists() else "java"
    log = (work / "fightingice.log").open("wb")
    proc = subprocess.Popen([j, "-cp", "FightingICE.jar:./lib/*:./lib/lwjgl/*:./lib/lwjgl/natives/linux/amd64/*:./lib/grpc/*",
                             "Main", "--headless-mode", "--pyftg-mode", "--input-sync", "--limithp", "400", "400",
                             "--port", "31417", "-r", "1", "-f", str(FRAME_LIMIT)],
                            cwd=runtime / "fightingice", stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    client = None
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("FightingICE exited before startup")
            if "Socket server is started" in (work / "fightingice.log").read_text(errors="replace"):
                break
            time.sleep(0.25)
        else:
            raise TimeoutError("FightingICE startup")
        cmd = [py, runtime / "repo/scripts/run_game_malecns_lif.py", "--host", "127.0.0.1", "--port", "31417",
               "--character-p1", P1, "--character-p2", opponent, "--seed-p1", seeds[0], "--seed-p2", seeds[1],
               "--reference-python", wrapper, "--reference-model", runtime / "shiu/model.py",
               "--adapter-dir", runtime / "data/malecns-shiu-strict-v1", "--adapter-dir-p1", adapter,
               "--interface", runtime / "data/interface.json", "--decision-interval", DECISION_INTERVAL,
               "--games", "1", "--expected-rounds", "1", "--timeout", "720",
               "--run-id", name, "--out", work]
        if trainable:
            cmd += ["--trainable-trace"]
        if video:
            cmd += ["--spectator-video", work / "round.mp4", "--spectator-fps", "10"]
        with (work / "client.log").open("wb") as handle:
            client = subprocess.Popen([str(x) for x in cmd], env=env, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
            rc = client.wait(timeout=780)
            if rc:
                raise RuntimeError(f"Canonical game client failed: {name}, rc={rc}")
        status = json.loads((work / name / "status.json").read_text())
        if (status["status"] != "COMPLETED_WITH_VALIDATED_CANONICAL_TRACES"
                or status["learning_performed"] is not False
                or status["trace_trainable"] != trainable
                or status["completed_rounds_per_agent"] != [1, 1]):
            raise ValueError("Round audit failed")
        for worker in status["workers"]:
            if worker["neurons"] != 156675 or worker["synapses"] != 6025920:
                raise ValueError("Unexpected canonical substrate")
        rows = [json.loads(line) for line in (work / name / "p1.jsonl").read_text().splitlines() if line]
        if len(rows) != 1:
            raise ValueError("Exactly one completed round required")
        result = round_metrics(rows[0])
        if result["winner"] == EVAL_P2:
            result["winner"] = opponent
        write(work / "result.json", result)
        return result
    finally:
        for child in (client, proc):
            if child is not None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL); child.wait(timeout=5)
        log.close()


def materialize(runtime, state, dest):
    py = runtime / (runtime / "runtime/python311.path").read_text().strip()
    env = {**os.environ, "PYTHONPATH": f"{runtime}/repo/src:{runtime}/runtime/site311"}
    run([py, runtime / "repo/scripts/materialize_malecns_valence_adapter.py",
         "--base-adapter", runtime / "data/malecns-shiu-strict-v1",
         "--candidates", runtime / "data/malecns-valence-v1/kc_mbon_valence_candidates.parquet",
         "--state", state, "--character", P1,
         "--plasticity-config", ROOT / "configs/plasticity_colosseum_v1.json", "--out", dest], env=env)


def video_info(path):
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size", "-show_entries",
             "stream=width,height,codec_name", "-of", "json", path], capture_output=True, text=True)
    probe = json.loads(p.stdout); stream = probe["streams"][0]
    duration = float(probe["format"]["duration"])
    if stream["codec_name"] != "h264" or (stream["width"], stream["height"]) != (960, 640) or not 0 < duration <= 75:
        raise ValueError("Invalid recorded evaluation video")
    return {"codec": "h264", "width": 960, "height": 640, "fps": 10, "duration_seconds": duration,
            "bytes": path.stat().st_size, "sha256": digest(path)}


def cycle(runtime, out, run_number):
    started = time.monotonic()
    out.mkdir(parents=True, exist_ok=False)
    candidates = runtime / "data/malecns-valence-v1/kc_mbon_valence_candidates.parquet"
    folder, previous, source = restore(out)
    state, lineage = prepare_state(folder, candidates, previous, source)
    parent_meta = json.loads(Path(str(state) + ".json").read_text())
    parent_hash = digest(state)
    materialize(runtime, state, out / "parent-adapter")
    parent = match(runtime, out, "parent-evaluation", out / "parent-adapter", EVAL_P2, EVAL_SEEDS, video=True)
    if digest(state) != parent_hash:
        raise ValueError("Evaluation changed candidate state")
    opponent = ("ZEN", "LUD", "NEZ")[parent_meta["generation"] % 3]
    training_seeds = (900000 + run_number, 1900000 + run_number)
    training_result = match(runtime, out, "training", out / "parent-adapter", opponent, training_seeds, trainable=True)
    if digest(state) != parent_hash:
        raise ValueError("Weights changed during collection")
    py = runtime / (runtime / "runtime/python311.path").read_text().strip()
    run([py, ROOT / "scripts/update_malecns_valence_plasticity.py", "--character", P1, "--side", "1",
         "--round-trace", out / "training/training/p1.jsonl", "--spikes", out / "training/training/p1-brain/spikes.parquet",
         "--candidates", candidates, "--reward-config", ROOT / "configs/reward_colosseum_v1.json",
         "--plasticity-config", ROOT / "configs/plasticity_colosseum_v1.json", "--state", state,
         "--out-summary", out / "update.json"])
    update = json.loads((out / "update.json").read_text())
    if update["status"] != "PASS" or update["updates"]["potentiated_edges"] != 0:
        raise ValueError("Plasticity audit failed")
    meta = json.loads(Path(str(state) + ".json").read_text())
    if meta["generation"] != parent_meta["generation"] + 1:
        raise ValueError("Generation must advance once per completed collection round")
    child_hash = digest(state)
    materialize(runtime, state, out / "child-adapter")
    child = match(runtime, out, "child-evaluation", out / "child-adapter", EVAL_P2, EVAL_SEEDS, video=True)
    if digest(state) != child_hash:
        raise ValueError("Post-update evaluation changed weights")
    tag = f"colosseum-g{meta['generation']:06d}-r{os.environ['GITHUB_RUN_ID']}-a{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    publish = out / "publish"; publish.mkdir()
    for name, src in (("parent-round.mp4", "parent-evaluation"), ("round.mp4", "child-evaluation")):
        shutil.copy2(out / src / "round.mp4", publish / name)
    with tarfile.open(publish / "candidate.tar.gz", "w:gz") as tar:
        for name in ("state/GARNET.npz", "state/GARNET.npz.json", "lineage.json"):
            tar.add(folder / name, arcname=name)
    with tarfile.open(publish / "evidence.tar.gz", "w:gz") as tar:
        for name in ("parent-evaluation", "training", "child-evaluation", "update.json", "source-identity.json"):
            tar.add(out / name, arcname=name)
    def evaluation(m, result, filename):
        return {"schema_version": 2, "kind": "post-update-candidate-round-evaluation", "status": "COMPLETED",
                "evaluated_at": stamp(), "candidate_only": True, "served_by_vercel": False, "auto_promotion": False,
                "policy_pixel_access": False, "lineage": LINEAGE, "character": P1, "opponent": EVAL_P2,
                "generation": m["generation"], "matches": m["matches"], "model": m["model"], "reward_id": m["reward_id"],
                "state_sha256": m["state_sha256"], "result": result,
                "evaluation": {"protocol": PROTOCOL, "rounds": 1, "fixed_opponent": True,
                               "seed_p1": EVAL_SEEDS[0], "seed_p2": EVAL_SEEDS[1], "round_frame_limit": FRAME_LIMIT,
                               "nominal_game_fps": 60, "configured_round_limit_seconds": 60,
                               "decision_interval_frames": DECISION_INTERVAL},
                "video": {**video_info(publish / filename), "asset_url": f"https://github.com/{REPO}/releases/download/{tag}/{filename}"},
                "interpretation_boundary": "One fixed-seed diagnostic, not a strength estimate. Recorded evaluation; no automatic promotion."}
    training = {"lineage": LINEAGE, "generation": meta["generation"], "matches": meta["matches"],
                "updated_at": stamp(), "state_sha256": child_hash, "reward_id": meta["reward_id"],
                "update_summary": update["updates"], "signal_summary": update["signals"],
                "auto_promotion": False, "served_by_vercel": False, "opponent": opponent,
                "seeds": list(training_seeds), "result": training_result}
    row = {"generation": meta["generation"], "evaluated_at": stamp(), "state_sha256": child_hash,
           "result": child, "parent_result": parent, "paired_hp_margin_change": child["hp_margin"] - parent["hp_margin"]}
    history = ((previous or {}).get("history", []) + [row])[-24:]
    status = {"schema_version": 1, "kind": "colosseum-season-status", "lineage": LINEAGE,
              "ready": True, "status": "evaluation-ready", "latest": evaluation(meta, child, "round.mp4"),
              "previous": evaluation(parent_meta, parent, "parent-round.mp4"), "training": training,
              "history": history, "fork": lineage["fork_parent"],
              "schedule": {"cron_utc": "3,13,23,33,43,53 * * * *", "requested_interval_minutes": 10,
                           "actual_timing_guaranteed": False, "single_writer": True},
              "checkpoint": {"release_tag": tag, "archive_sha256": digest(publish / "candidate.tar.gz")},
              "diagnostics": {"paired_hp_margin_change": row["paired_hp_margin_change"],
                              "saturated_fraction": None, "strength_demonstrated": False},
              "runtime_seconds": time.monotonic() - started,
              "source_run_url": f"https://github.com/{REPO}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
              "source_commit": os.environ.get("GITHUB_SHA"),
              "reward_config_sha256": digest(ROOT / "configs/reward_colosseum_v1.json"),
              "plasticity_config_sha256": digest(ROOT / "configs/plasticity_colosseum_v1.json"),
              "production_learning_enabled": False}
    import numpy as np
    with np.load(state, allow_pickle=False) as z:
        status["diagnostics"]["saturated_fraction"] = float(np.mean(z["multipliers"] <= 0.800001))
    write(publish / "status.json", status)
    files = {p.name: digest(p) for p in publish.iterdir() if p.is_file()}
    write(publish / "checksums.json", files)
    print(json.dumps({"cycle": "PASS", "generation": meta["generation"], "parent": parent, "child": child,
                      "publication_performed": False, "strength_demonstrated": False}, indent=2))


def publish(folder):
    """Only the trusted main job calls this after the complete cycle succeeded."""
    if os.environ.get("GITHUB_REF") != "refs/heads/main" or os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        raise ValueError("Publication is restricted to trusted main")
    checksums = json.loads((folder / "checksums.json").read_text())
    for name, sha in checksums.items():
        if Path(name).name != name or digest(folder / name) != sha:
            raise ValueError("Publication artifact checksum mismatch")
    status = json.loads((folder / "status.json").read_text())
    if status["lineage"] != LINEAGE or status["status"] != "evaluation-ready":
        raise ValueError("Not a completed colosseum cycle")
    tag = status["checkpoint"]["release_tag"]
    if not tag.startswith("colosseum-g"):
        raise ValueError("Disallowed publication tag")
    # Never --clobber immutable generation assets. Pointer advances last.
    args = ["gh", "release", "create", tag, "--repo", REPO, "--target", os.environ["GITHUB_SHA"], "--prerelease",
            "--title", f"Colosseum candidate generation {status['training']['generation']}",
            "--notes", "Experimental candidate and paired fixed-seed evaluation. No approved inference promotion."]
    run(args + sorted(folder.iterdir()))
    # Resolve the uploaded release, bind every immutable byte to GitHub's digest.
    rel = release(tag)
    by_name = {a["name"]: a for a in rel["assets"]}
    for name, sha in checksums.items():
        if by_name.get(name, {}).get("digest") != f"sha256:{sha}":
            raise ValueError(f"Uploaded generation digest mismatch: {name}")
    if release("colosseum-latest", missing_ok=True) is None:
        run(["gh", "release", "create", "colosseum-latest", "--repo", REPO, "--target", os.environ["GITHUB_SHA"],
             "--prerelease", "--title", "Colosseum latest completed candidate", "--notes", "Atomic status pointer; candidate-only, not approved inference."])
    run(["gh", "release", "upload", "colosseum-latest", folder / "status.json", "--repo", REPO, "--clobber"])
    print(json.dumps({"published": tag, "pointer": "colosseum-latest", "approved_inference_changed": False}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-root", type=Path)
    p.add_argument("--out", type=Path, default=Path("runs/colosseum-cycle"))
    p.add_argument("--publish", type=Path)
    args = p.parse_args()
    def interrupted(*_):
        raise KeyboardInterrupt("Cycle interrupted; incomplete cycles are never published")
    signal.signal(signal.SIGTERM, interrupted)
    if args.publish:
        publish(args.publish.resolve())
    elif args.runtime_root:
        cycle(args.runtime_root.resolve(), args.out.resolve(), int(os.environ["GITHUB_RUN_NUMBER"]))
    else:
        p.error("--runtime-root or --publish required")


if __name__ == "__main__":
    main()
