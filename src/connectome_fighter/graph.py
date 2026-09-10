"""Auditable graph ingestion. No implicit biological-data download or fallback."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
import json
import numpy as np

@dataclass(frozen=True)
class Graph:
    node_ids: tuple[str, ...]
    src: np.ndarray
    dst: np.ndarray
    magnitude: np.ndarray
    sign: np.ndarray
    manifest: dict

    def __post_init__(self) -> None:
        if not self.node_ids or len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("Missing or duplicate neuron IDs")
        if any(not isinstance(x, str) or not x for x in self.node_ids):
            raise TypeError("Neuron IDs must be nonempty strings; never float64 IDs")
        arrays = {}
        for name, dtype in [("src", np.int64), ("dst", np.int64),
                            ("magnitude", np.float32), ("sign", np.float32)]:
            raw = np.asarray(getattr(self, name))
            if name in ("src", "dst") and not np.issubdtype(raw.dtype, np.integer):
                raise TypeError("Graph endpoints must be integer indices")
            arrays[name] = np.array(raw, dtype=dtype, copy=True)
        if any(x.ndim != 1 for x in arrays.values()) or len({len(x) for x in arrays.values()}) != 1:
            raise ValueError("Edge arrays must be one-dimensional and equally sized")
        if len(arrays["src"]) == 0:
            raise ValueError("Empty graph")
        if (min(arrays["src"].min(), arrays["dst"].min()) < 0 or
                max(arrays["src"].max(), arrays["dst"].max()) >= len(self.node_ids)):
            raise ValueError("Edge endpoint is out of range")
        if not np.isfinite(arrays["magnitude"]).all() or np.any(arrays["magnitude"] <= 0):
            raise ValueError("Magnitudes must be finite and strictly positive")
        if not np.isin(arrays["sign"], [-1, 1]).all():
            raise ValueError("Unknown transmitter sign must be resolved explicitly upstream")
        pairs = np.stack([arrays["src"], arrays["dst"]], axis=1)
        if len(np.unique(pairs, axis=0)) != len(pairs):
            raise ValueError("Duplicate neuron pairs: explicitly aggregate synapses before import")
        for name, arr in arrays.items():
            arr.flags.writeable = False
            object.__setattr__(self, name, arr)

    @property
    def n_nodes(self) -> int:
        return len(self.node_ids)

    @property
    def n_edges(self) -> int:
        return len(self.src)

    def fingerprint(self) -> str:
        h = hashlib.sha256(json.dumps(self.node_ids, separators=(",", ":")).encode())
        for value in (self.src.astype("<i8"), self.dst.astype("<i8"),
                      self.magnitude.astype("<f4"), self.sign.astype("<f4")):
            h.update(value.tobytes())
        return h.hexdigest()

    def require_biological(self) -> None:
        required = ("source_url", "source_version", "source_sha256", "license", "preprocessing", "scope")
        if self.manifest.get("kind") not in ("biological", "biological_rewired"):
            raise ValueError("Synthetic graph prohibited in biological experiment mode")
        if any(not self.manifest.get(k) for k in required):
            raise ValueError("Biological graph lacks provenance fields")
        digest = self.manifest["source_sha256"]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid source SHA256")
        if self.manifest["scope"] not in ("whole_brain", "induced_subgraph", "coarse_grained", "other"):
            raise ValueError("Declare whether this is a whole graph, subgraph, or abstraction")

def load_graph(directory: str | Path, *, require_biological: bool = True) -> Graph:
    directory = Path(directory)
    with (directory / "nodes.csv").open(newline="", encoding="utf-8") as f:
        nodes = tuple(row["node_id"] for row in csv.DictReader(f))
    mapping = {node_id: idx for idx, node_id in enumerate(nodes)}
    src, dst, magnitude, sign = [], [], [], []
    with (directory / "edges.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                src.append(mapping[row["pre_id"]]); dst.append(mapping[row["post_id"]])
            except KeyError as exc:
                raise ValueError(f"Unknown edge endpoint: {exc}") from exc
            magnitude.append(float(row["magnitude"])); sign.append(float(row["sign"]))
    manifest = json.loads((directory / "manifest.json").read_text())
    g = Graph(nodes, np.asarray(src, dtype=np.int64), np.asarray(dst, dtype=np.int64),
              np.asarray(magnitude), np.asarray(sign), manifest)
    if require_biological:
        g.require_biological()
        checksums = manifest.get("processed_files_sha256", {})
        for filename in ("nodes.csv", "edges.csv"):
            expected = checksums.get(filename)
            if not isinstance(expected, str) or len(expected) != 64:
                raise ValueError(f"Missing processed-file checksum: {filename}")
            actual = hashlib.sha256()
            with (directory / filename).open("rb") as raw:
                for block in iter(lambda: raw.read(1024*1024), b""):
                    actual.update(block)
            if actual.hexdigest() != expected:
                raise ValueError(f"Processed-file checksum mismatch: {filename}")
    return g

def synthetic_graph(n_nodes: int = 32, seed: int = 0) -> Graph:
    """Explicit engineering fixture, NOT a fly connectome."""
    if n_nodes < 8:
        raise ValueError("Synthetic fixture requires at least eight nodes")
    rng = np.random.default_rng(seed)
    src = np.repeat(np.arange(n_nodes, dtype=np.int64), 3)
    dst = np.concatenate([(i + np.array([1, 3, 5])) % n_nodes for i in range(n_nodes)])
    node_sign = rng.choice(np.array([-1, 1]), size=n_nodes, p=[.2, .8])
    return Graph(tuple(f"synthetic-{i}" for i in range(n_nodes)), src, dst,
                 rng.uniform(.5, 1.5, size=len(src)), node_sign[src],
                 {"kind": "synthetic", "seed": seed, "scope": "engineering_fixture"})

def rewire_signed_degrees(graph: Graph, swaps: int, seed: int) -> tuple[Graph, dict]:
    """Directed double-edge swaps within the same sign."""
    if swaps <= 0 or np.any(graph.src == graph.dst):
        raise ValueError("Use positive swaps and explicitly remove/retain autapses before this null")
    rng = np.random.default_rng(seed)
    src, dst = graph.src.copy(), graph.dst.copy()
    edges = set(zip(src.tolist(), dst.tolist()))
    candidates = [np.flatnonzero(graph.sign == s) for s in (-1, 1)]
    candidates = [x for x in candidates if len(x) >= 2]
    if not candidates:
        raise ValueError("No sign group has swappable edges")
    completed = attempts = 0
    while completed < swaps and attempts < max(1000, swaps*100):
        attempts += 1
        group = candidates[int(rng.integers(len(candidates)))]
        e1, e2 = rng.choice(group, 2, replace=False)
        a, b, c, d = int(src[e1]), int(dst[e1]), int(src[e2]), int(dst[e2])
        if a == c or b == d or a == d or c == b or (a, d) in edges or (c, b) in edges:
            continue
        edges.remove((a, b)); edges.remove((c, d))
        edges.add((a, d)); edges.add((c, b))
        dst[e1], dst[e2] = d, b
        completed += 1
    if completed != swaps:
        raise RuntimeError(f"Requested {swaps} accepted swaps, obtained {completed}; null rejected")
    manifest = {**graph.manifest, "kind": ("biological_rewired" if graph.manifest.get("kind") == "biological"
                                         else "synthetic_rewired"),
                "parent_graph_sha256": graph.fingerprint(), "rewire_seed": seed,
                "accepted_swaps": completed}
    result = Graph(graph.node_ids, src, dst, graph.magnitude, graph.sign, manifest)
    overlap = len(edges & set(zip(graph.src.tolist(), graph.dst.tolist()))) / graph.n_edges
    return result, {"accepted_swaps": completed, "attempts": attempts,
                    "edge_overlap_fraction": overlap, "mixing_certified": False}
