"""Validation for reproducible game<->connectome routing specifications."""
from __future__ import annotations
from typing import Any
from .graph import Graph
from .contracts import OBS_DIM


def validate_routing(graph: Graph, routing: dict[str, Any]) -> None:
    required = {
        "input_nodes", "input_root_ids", "input_features", "input_polarities",
        "output_nodes", "output_root_ids", "selection", "routing_sha256"
    }
    missing = sorted(required - set(routing))
    if missing:
        raise ValueError(f"Routing missing fields: {missing}")
    ins = routing["input_nodes"]
    in_ids = routing["input_root_ids"]
    feats = routing["input_features"]
    pol = routing["input_polarities"]
    outs = routing["output_nodes"]
    out_ids = routing["output_root_ids"]
    if not (len(ins) == len(in_ids) == len(feats) == len(pol)) or not ins:
        raise ValueError("Input routing arrays are inconsistent")
    if len(outs) != len(out_ids) or not outs:
        raise ValueError("Output routing arrays are inconsistent")
    if len(set(ins)) != len(ins) or len(set(outs)) != len(outs):
        raise ValueError("Routing contains duplicate graph nodes")
    if set(ins) & set(outs):
        raise ValueError("Input and output populations must be disjoint")
    for idx, root in zip(ins, in_ids):
        if type(idx) is not int or not 0 <= idx < graph.n_nodes or graph.node_ids[idx] != str(root):
            raise ValueError("Input routing index/root-id mismatch")
    for idx, root in zip(outs, out_ids):
        if type(idx) is not int or not 0 <= idx < graph.n_nodes or graph.node_ids[idx] != str(root):
            raise ValueError("Output routing index/root-id mismatch")
    if any(type(x) is not int or not 0 <= x < OBS_DIM for x in feats):
        raise ValueError("Invalid observation feature index")
    if any(x not in (-1, 1) for x in pol):
        raise ValueError("Invalid half-wave polarity")
    selection = routing["selection"]
    if selection.get("input_super_class") != "sensory" or selection.get("output_super_class") != "descending":
        raise ValueError("v0 biological routing must use sensory input and descending output populations")
    if selection.get("encoding") != "half_wave_positive_negative":
        raise ValueError("Unexpected routing encoding")
    scale = selection.get("input_scale")
    if not isinstance(scale, (int, float)) or isinstance(scale, bool) or not 0 < float(scale) <= 10:
        raise ValueError("Invalid routing input scale")
