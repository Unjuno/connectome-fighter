"""Double-buffered durable state bundles for GitHub Release storage.

A workflow writes the *inactive* slot completely, verifies it locally, then
publishes ``state-pointer.json`` last.  A failed upload therefore leaves the
previous active slot intact and resumable.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil
from typing import Any

from .characters import CHARACTERS
from .checkpoint import checkpoint_filename, load_checkpoint, sha256_file

BUNDLE_SCHEMA = 1
POINTER_NAME = "state-pointer.json"


def _json_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _active_slot(state_dir: Path) -> str | None:
    pointer = state_dir / POINTER_NAME
    if not pointer.is_file():
        return None
    payload = json.loads(pointer.read_text(encoding="utf-8"))
    slot = payload.get("active_slot")
    if slot not in {"a", "b"}:
        raise ValueError("Invalid state pointer slot")
    return str(slot)


def package_state(state_dir: str | Path, publish_dir: str | Path) -> dict[str, Any]:
    state_dir = Path(state_dir)
    publish_dir = Path(publish_dir)
    publish_dir.mkdir(parents=True, exist_ok=True)
    current = _active_slot(state_dir)
    slot = "b" if current == "a" else "a"

    league_path = state_dir / "league-state.json"
    if not league_path.is_file():
        raise FileNotFoundError(league_path)
    league = json.loads(league_path.read_text(encoding="utf-8"))
    chunk = int(league.get("chunks", -1))
    if chunk < 0:
        raise ValueError("Invalid league chunk counter")

    characters: dict[str, Any] = {}
    for character in CHARACTERS:
        source = state_dir / checkpoint_filename(character)
        payload = load_checkpoint(source, expected_character=character)
        metadata = dict(payload["metadata"])
        asset = f"slot-{slot}-brain-{character}.pt"
        target = publish_dir / asset
        shutil.copyfile(source, target)
        digest = sha256_file(target)
        if digest != metadata.get("sha256", digest):
            # save_checkpoint returns sha in caller metadata, but the serialized
            # metadata intentionally does not self-contain its own file hash.
            pass
        characters[character] = {
            "asset": asset,
            "sha256": digest,
            "checkpoint_id": metadata["checkpoint_id"],
            "generation": int(metadata["generation"]),
            "training_matches": int(metadata["training_matches"]),
            "graph_hash": metadata["graph_hash"],
            "routing_hash": metadata["routing_hash"],
        }

    league_asset = f"slot-{slot}-league-state.json"
    shutil.copyfile(league_path, publish_dir / league_asset)
    league_sha = sha256_file(publish_dir / league_asset)
    manifest = {
        "schema_version": BUNDLE_SCHEMA,
        "slot": slot,
        "chunk": chunk,
        "characters": characters,
        "league": {"asset": league_asset, "sha256": league_sha},
    }
    manifest_asset = f"slot-{slot}-manifest.json"
    manifest_path = publish_dir / manifest_asset
    _write_json(manifest_path, manifest)
    manifest_file_sha = sha256_file(manifest_path)
    pointer = {
        "schema_version": BUNDLE_SCHEMA,
        "active_slot": slot,
        "chunk": chunk,
        "manifest": manifest_asset,
        "manifest_sha256": manifest_file_sha,
        "bundle_fingerprint": _json_sha256(manifest),
    }
    _write_json(publish_dir / POINTER_NAME, pointer)
    return pointer


def restore_state(download_dir: str | Path, state_dir: str | Path) -> dict[str, Any]:
    download_dir = Path(download_dir)
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    pointer_path = download_dir / POINTER_NAME
    if not pointer_path.is_file():
        raise FileNotFoundError(pointer_path)
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("schema_version") != BUNDLE_SCHEMA or pointer.get("active_slot") not in {"a", "b"}:
        raise ValueError("Unsupported durable state pointer")
    manifest_path = download_dir / str(pointer["manifest"])
    if sha256_file(manifest_path) != pointer.get("manifest_sha256"):
        raise ValueError("Durable state manifest checksum mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != BUNDLE_SCHEMA or manifest.get("slot") != pointer["active_slot"]:
        raise ValueError("Durable state manifest/pointer mismatch")
    if int(manifest.get("chunk", -1)) != int(pointer.get("chunk", -2)):
        raise ValueError("Durable state chunk mismatch")

    graph_hashes: set[str] = set()
    routing_hashes: set[str] = set()
    generations: set[int] = set()
    for character in CHARACTERS:
        item = manifest.get("characters", {}).get(character)
        if not isinstance(item, dict):
            raise ValueError(f"Missing durable checkpoint entry for {character}")
        source = download_dir / str(item["asset"])
        if sha256_file(source) != item.get("sha256"):
            raise ValueError(f"Durable checkpoint checksum mismatch for {character}")
        canonical = state_dir / checkpoint_filename(character)
        shutil.copyfile(source, canonical)
        digest = sha256_file(canonical)
        canonical.with_suffix(canonical.suffix + ".sha256").write_text(
            f"{digest}  {canonical.name}\n", encoding="utf-8"
        )
        payload = load_checkpoint(canonical, expected_character=character)
        meta = payload["metadata"]
        if meta["checkpoint_id"] != item["checkpoint_id"] or int(meta["generation"]) != int(item["generation"]):
            raise ValueError(f"Durable checkpoint metadata mismatch for {character}")
        graph_hashes.add(str(meta["graph_hash"]))
        routing_hashes.add(str(meta["routing_hash"]))
        generations.add(int(meta["generation"]))

    if len(graph_hashes) != 1 or len(routing_hashes) != 1 or len(generations) != 1:
        raise ValueError("Character checkpoints are not one coherent training generation")

    league = manifest.get("league", {})
    league_source = download_dir / str(league.get("asset", ""))
    if sha256_file(league_source) != league.get("sha256"):
        raise ValueError("League state checksum mismatch")
    shutil.copyfile(league_source, state_dir / "league-state.json")
    shutil.copyfile(pointer_path, state_dir / POINTER_NAME)
    return {
        "chunk": int(pointer["chunk"]),
        "generation": generations.pop(),
        "graph_hash": graph_hashes.pop(),
        "routing_hash": routing_hashes.pop(),
        "active_slot": pointer["active_slot"],
    }
