"""CPU inference benchmark for a normalized graph + routing; no game and no learning.

Reports hardware/runtime conditions with median and range. This is an
engineering benchmark, not evidence of behavioral performance.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import time


def cpu_model() -> str:
    try:
        for line in Path('/proc/cpuinfo').read_text(errors='ignore').splitlines():
            if line.lower().startswith('model name'):
                return line.split(':', 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or 'unknown'


def max_rss_mib() -> float:
    # Linux ru_maxrss is KiB.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--graph-dir', type=Path, required=True)
    p.add_argument('--routing', type=Path, required=True)
    p.add_argument('--threads', type=int, default=1)
    p.add_argument('--repeats', type=int, default=5)
    p.add_argument('--neural-steps', type=int, default=1)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    if args.threads <= 0 or args.repeats <= 0 or args.neural_steps <= 0:
        p.error('threads/repeats/neural-steps must be positive')

    import numpy as np
    import torch
    from connectome_fighter.graph import load_graph
    from connectome_fighter.routing import validate_routing
    from connectome_fighter.brain import ConnectomeActorCritic
    from connectome_fighter.contracts import OBS_DIM

    torch.set_num_threads(args.threads)
    torch.manual_seed(1)
    rss0 = max_rss_mib()
    t0 = time.perf_counter()
    graph = load_graph(args.graph_dir, require_biological=True)
    graph_load_s = time.perf_counter() - t0
    rss_graph = max_rss_mib()
    routing = json.loads(args.routing.read_text())
    validate_routing(graph, routing)

    t0 = time.perf_counter()
    model = ConnectomeActorCritic(
        graph, routing['input_nodes'], routing['output_nodes'],
        input_features=routing['input_features'],
        input_polarities=routing['input_polarities'],
        input_scale=float(routing['selection']['input_scale']),
        neural_steps=args.neural_steps, plastic=False,
    ).eval()
    model_build_s = time.perf_counter() - t0
    rss_model = max_rss_mib()

    state = torch.zeros(1, graph.n_nodes, dtype=torch.float32)
    observation = torch.linspace(-1, 1, OBS_DIM, dtype=torch.float32).reshape(1, -1)
    times = []
    with torch.no_grad():
        # First call is reported separately rather than discarded silently.
        t0 = time.perf_counter()
        logits, value, state = model(observation, state)
        first_forward_s = time.perf_counter() - t0
        for _ in range(args.repeats):
            t0 = time.perf_counter()
            logits, value, state = model(observation, state)
            times.append(time.perf_counter() - t0)
    report = {
        'status': 'engineering_benchmark_only',
        'biological_graph_loaded': True,
        'behavioral_result': False,
        'learning_performed': False,
        'backend': 'torch-cpu',
        'dtype': 'float32',
        'batch': 1,
        'threads': args.threads,
        'cpu_model': cpu_model(),
        'logical_cpu_count_visible': os.cpu_count(),
        'python': platform.python_version(),
        'torch': torch.__version__,
        'numpy': np.__version__,
        'nodes': graph.n_nodes,
        'edges': graph.n_edges,
        'input_neurons': len(routing['input_nodes']),
        'output_neurons': len(routing['output_nodes']),
        'neural_steps_per_forward': args.neural_steps,
        'graph_load_s': graph_load_s,
        'model_build_s': model_build_s,
        'first_forward_s': first_forward_s,
        'measured_forwards': args.repeats,
        'forward_s_median': statistics.median(times),
        'forward_s_min': min(times),
        'forward_s_max': max(times),
        'max_rss_mib_start': rss0,
        'max_rss_mib_after_graph': rss_graph,
        'max_rss_mib_after_model': rss_model,
        'max_rss_mib_end': max_rss_mib(),
        'finite_output': bool(torch.isfinite(logits).all() and torch.isfinite(value).all() and torch.isfinite(state).all()),
        'graph_sha256': graph.fingerprint(),
        'routing_sha256': routing['routing_sha256'],
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not report['finite_output']:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
