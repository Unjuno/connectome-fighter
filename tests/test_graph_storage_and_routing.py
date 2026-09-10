import csv
import hashlib
import json
import numpy as np
import torch
from connectome_fighter.graph import Graph, load_graph, synthetic_graph
from connectome_fighter.brain import FixedRouting, SparseGraphCore, ConnectomeActorCritic


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_compact_npz_biological_loader(tmp_path):
    nodes = tmp_path / 'nodes.csv'
    with nodes.open('w', newline='') as f:
        w = csv.writer(f); w.writerow(['node_id']); w.writerows([['10'], ['20'], ['30']])
    edges = tmp_path / 'edges.npz'
    np.savez_compressed(edges,
                        src=np.array([0, 0, 1], dtype=np.int64),
                        dst=np.array([1, 2, 2], dtype=np.int64),
                        magnitude=np.array([2, 3, 4], dtype=np.float32),
                        sign=np.array([1, -1, 1], dtype=np.int8))
    manifest = {
        'kind': 'biological', 'scope': 'whole_brain',
        'source_url': 'https://example.invalid/data', 'source_version': 'test',
        'source_sha256': '0' * 64, 'license': 'test-only',
        'preprocessing': 'unit-test fixture', 'edge_storage': 'npz_v1',
        'edges_sorted_pre_post': True,
        'processed_files_sha256': {'nodes.csv': sha(nodes), 'edges.npz': sha(edges)},
    }
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    g = load_graph(tmp_path, require_biological=True)
    assert g.node_ids == ('10', '20', '30')
    assert g.n_edges == 3
    assert np.array_equal(g.sign, [1, -1, 1])


def test_half_wave_routing_never_injects_negative_drive():
    route = FixedRouting(4, [0, 1], input_features=[0, 0], input_polarities=[1, -1], input_scale=0.5)
    positive = route(torch.tensor([[2.0] + [0.0] * 17]))
    negative = route(torch.tensor([[-2.0] + [0.0] * 17]))
    assert torch.all(positive >= 0) and torch.all(negative >= 0)
    assert positive[0, 0].item() == 1.0 and positive[0, 1].item() == 0.0
    assert negative[0, 0].item() == 0.0 and negative[0, 1].item() == 1.0


def test_two_models_can_share_only_immutable_core():
    graph = synthetic_graph(32, 4)
    core = SparseGraphCore(graph, plastic=False)
    m1 = ConnectomeActorCritic(graph, list(range(8)), list(range(16, 24)), shared_core=core, neural_steps=1)
    m2 = ConnectomeActorCritic(graph, list(range(8)), list(range(16, 24)), shared_core=core, neural_steps=1)
    assert m1.core is core and m2.core is core
    assert m1.actor is not m2.actor


def test_plastic_core_cannot_be_shared_between_competitors():
    graph = synthetic_graph(32, 5)
    core = SparseGraphCore(graph, plastic=True)
    try:
        ConnectomeActorCritic(graph, list(range(8)), list(range(16, 24)), shared_core=core, neural_steps=1)
    except ValueError as exc:
        assert 'mutable/plastic' in str(exc)
    else:
        raise AssertionError('plastic shared core was accepted')
