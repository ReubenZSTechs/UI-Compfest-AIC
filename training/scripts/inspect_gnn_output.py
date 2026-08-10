"""
Quick inspection of Training_sample_generator.py's outputs. Run from the
project root:

    python inspect_gnn_output.py

Checks, in order:
  1. the graph manifest (how many graphs, split assignment, edge counts)
  2. one rebuilt factory JSON (the human-readable evaluations)
  3. one .pt HeteroData graph (actual tensors going into the GNN)
"""

import json
from pathlib import Path

import torch

MANIFEST_PATH = Path("./training/data/formatted/syntetic_graph_manifest/manifest.json")
OUTPUT_DIR = Path("./training/data/formatted/syntetic_gnn_training_data/")
GRAPH_DIR = Path("./training/data/formatted/syntetic_gnn_graphs/")


def inspect_manifest():
    print("=" * 70)
    print("MANIFEST")
    print("=" * 70)
    if not MANIFEST_PATH.exists():
        print(f"  not found: {MANIFEST_PATH}")
        return None
    manifest = json.loads(MANIFEST_PATH.read_text())
    print(f"  num_graphs: {manifest['num_graphs']}")
    print(f"  feature_dims: {manifest['feature_dims']}")
    print(f"  edge_label_fields: {manifest['edge_label_fields']}")
    print()
    for g in manifest["graphs"]:
        print(f"  [{g['filename']}] split={g['split']:<5} "
              f"workers={g['num_workers']:<3} jobs={g['num_jobs']:<3} "
              f"assets={g['num_assets']:<3} "
              f"compat_edges={g['num_compatibility_edges']:<4} "
              f"skipped={g['edges_skipped']}")
    return manifest


def inspect_rebuilt_json(filename_stem: str):
    print()
    print("=" * 70)
    print(f"REBUILT JSON: {filename_stem}.json")
    print("=" * 70)
    path = OUTPUT_DIR / f"{filename_stem}.json"
    if not path.exists():
        print(f"  not found: {path}")
        return
    doc = json.loads(path.read_text())
    evals = doc.get("synthetic_compatibility_evaluations", [])
    print(f"  {len(evals)} evaluated pair(s)")
    for ev in evals[:3]:
        print(f"  worker={ev['worker_id']} job={ev['job_id']} asset={ev['asset_id']}")
        print(f"    evaluations: {ev['evaluations']}")
        print(f"    reasoning:   {ev['llm_reasoning'][:120]}")
    if len(evals) > 3:
        print(f"  ... and {len(evals) - 3} more")


def inspect_graph(filename_stem: str):
    print()
    print("=" * 70)
    print(f"GRAPH: {filename_stem}.pt")
    print("=" * 70)
    path = GRAPH_DIR / f"{filename_stem}.pt"
    if not path.exists():
        print(f"  not found: {path}")
        return
    data = torch.load(path, weights_only=False)

    print(f"  factory_id: {data['factory_id']}   split: {data['split']}")
    for node_type in ("worker", "job", "asset"):
        x = data[node_type].x
        print(f"  node[{node_type}]: {x.shape[0]} nodes, {x.shape[1]}-dim features")

    edge = data['worker', 'compatible_with', 'job']
    n_edges = edge.edge_index.size(1)
    print(f"  edge[worker -> compatible_with -> job]: {n_edges} edges")
    if n_edges > 0:
        print(f"    edge_attr shape: {tuple(edge.edge_attr.shape)}")
        print(f"    first 3 edge_attr rows (overall_score, throughput, error, fatigue, stress):")
        for row in edge.edge_attr[:3].tolist():
            print(f"      {[round(v, 3) for v in row]}")
        # sanity: is this actually weighted, or is every edge the same value?
        # (a real red flag if every score is identical - e.g. leftover empty/default data)
        scores = edge.edge_attr[:, 0].tolist()
        print(f"    overall_compatibility_score range: "
              f"min={min(scores):.3f} max={max(scores):.3f} "
              f"({'all identical - suspicious!' if min(scores) == max(scores) and n_edges > 1 else 'varies, looks real'})")


if __name__ == "__main__":
    manifest = inspect_manifest()
    if manifest and manifest["graphs"]:
        # inspect the first graph in the manifest in detail
        first_stem = Path(manifest["graphs"][0]["filename"]).stem
        inspect_rebuilt_json(first_stem)
        inspect_graph(first_stem)

    # python -m training.scripts.inspect_gnn_output