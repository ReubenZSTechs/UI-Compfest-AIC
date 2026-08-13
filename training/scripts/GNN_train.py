"""
GNN training on the factory HeteroData graphs produced by
Training_sample_generator.py (the `.pt` files under GRAPH_OUTPUT_DIR, indexed
by GRAPH_MANIFEST_FILE / manifest.json).

Node/edge types match build_hetero_graph() in that script:

    node types : worker, job, asset
    edge types : (job,   'uses_asset',         asset)   structural
                 (asset, 'rev_uses_asset',      job)     structural (reverse)
                 (worker,'compatible_with',     job)     LABELED, edge_attr is
                                                          the 5-dim eval vector
                 (job,   'rev_compatible_with', worker)  structural only
                                                          (no edge_attr, by
                                                          design - see
                                                          Training_sample_generator.py)

    one graph == one factory (.pt file); manifest.json lists every graph with
    its train/val/test split (assign_split() is deterministic per factory_id,
    so re-running the generator never reshuffles a factory across splits) and
    the fixed feature dims / edge_label_fields to use here.

This is a STARTER draft, same spirit as the generator scripts it pairs with:
it validates the full pipeline shape (load -> batch heterogeneous graphs ->
GraphSAGE -> predict the 5-dim compatibility vector) rather than being a
tuned model.

run : python -m training.scripts.GNN_train
"""

import json
import logging

from pathlib import Path

import torch
from torch.utils.data import Dataset
from torch_geometric.loader import DataLoader
from torch_geometric.nn import SAGEConv, to_hetero

logger = logging.getLogger(__name__)

validation = False

def get_val_state():
    return validation

CONFIG = {
    'MANIFEST_FILE': "./training/datasets/formatted/train/onet_based_graph_manifest/manifest.json",
    'GRAPH_DIR': "./training/datasets/formatted/train/onet_based_gnn_graphs/",  # override for stale manifest graph_path entries; None to trust the manifest as-is
    'SAVE_PATH': "./training/datasets/formatted/train/checkpoints/onet_based_best_compatibility_predictor.pt",
    'EPOCHS': 100,
    'BATCH_SIZE': 8,
    'LR': 1e-3,
    'HIDDEN_CHANNELS': 64,
    'OUT_CHANNELS': 32,
}

# --------------------------------------------------------------------------
# Bounds each edge_attr field was validated against in
# Training_sample_generator.py (_EVAL_BOUNDS). Used to min-max normalize
# targets to [0, 1] for training and to unnormalize for reporting - the 5
# fields have very different scales (e.g. throughput_multiplier lives in
# [0.8, 1.2] while overall_compatibility_score lives in [0.0, 1.0]), and
# training directly on raw values makes the loss dominated by whichever
# field has the widest range.
# --------------------------------------------------------------------------

EDGE_LABEL_FIELDS = [
    "overall_compatibility_score",
    "throughput_multiplier",
    "error_multiplier",
    "fatigue_accumulation_rate",
    "stress_sensitivity_factor",
]

EVAL_BOUNDS = {
    "overall_compatibility_score": (0.0, 1.0),
    "throughput_multiplier": (0.8, 1.2),
    "error_multiplier": (0.4, 1.5),
    "fatigue_accumulation_rate": (0.3, 1.5),
    "stress_sensitivity_factor": (0.4, 1.0),
}

_LO = torch.tensor([EVAL_BOUNDS[f][0] for f in EDGE_LABEL_FIELDS], dtype=torch.float)
_HI = torch.tensor([EVAL_BOUNDS[f][1] for f in EDGE_LABEL_FIELDS], dtype=torch.float)


def normalize_targets(y: torch.Tensor) -> torch.Tensor:
    return (y - _LO.to(y.device)) / (_HI.to(y.device) - _LO.to(y.device))


def unnormalize_preds(y: torch.Tensor) -> torch.Tensor:
    return y * (_HI.to(y.device) - _LO.to(y.device)) + _LO.to(y.device)


# --------------------------------------------------------------------------
# Dataset: one manifest, N per-factory .pt graphs, filtered by split
# --------------------------------------------------------------------------

class FactoryGraphDataset(Dataset):
    """Loads the pre-built HeteroData graphs listed in manifest.json for one
    split ('train' / 'val' / 'test'). Graphs with zero compatible_with edges
    (e.g. a factory with no evaluable pairs) are skipped for training/eval
    since there's nothing to supervise on.

    NOTE: does NOT raise if a split is empty. assign_split() in the generator
    hash-buckets each factory by factory_id, so with only a handful of
    factories total it's common for a whole split (usually val/test at
    10% each) to land empty just by chance - that's a small-N artifact of
    the split, not a sign anything is broken. Callers (see main()) decide
    how to degrade when a split comes back empty."""

    def __init__(self, manifest_path: Path, split: str, graph_dir: Path = None):
        """
        graph_dir: optional override directory for the .pt files. manifest.json's
        graph_path is whatever CONFIG['GRAPH_OUTPUT_DIR'] was in the generator at
        generation time, baked in as a literal string - if the repo/folder has
        since been renamed or moved, or the generator's CONFIG has changed, those
        paths go stale. Pass graph_dir to ignore the recorded directory and just
        take each entry's filename, resolved under graph_dir instead.
        """
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.feature_dims = manifest["feature_dims"]
        self.edge_label_fields = manifest["edge_label_fields"]
        assert self.edge_label_fields == EDGE_LABEL_FIELDS, (
            "manifest.json edge_label_fields don't match this script's EDGE_LABEL_FIELDS; "
            "regenerate the manifest or update EVAL_BOUNDS/EDGE_LABEL_FIELDS above."
        )

        self.paths = []
        missing = []
        for entry in manifest["graphs"]:
            if entry["split"] != split:
                continue
            if entry["num_compatibility_edges"] == 0:
                continue
            path = (graph_dir / Path(entry["graph_path"]).name) if graph_dir else Path(entry["graph_path"])
            if path.exists():
                self.paths.append(path)
            else:
                missing.append((entry["filename"], path))

        if missing:
            preview = "\n".join(f"  {fn} -> {p}" for fn, p in missing[:5])
            more = f"\n  ... and {len(missing) - 5} more" if len(missing) > 5 else ""
            logger.warning(
                f"split={split!r} has {len(missing)} graph(s) listed in the manifest "
                f"whose .pt file doesn't exist on disk (skipped):\n{preview}{more}\n"
                f"This means manifest.json's recorded graph_path is stale relative to where "
                f"the files actually live. Set CONFIG['GRAPH_DIR'] to the actual folder, "
                f"or re-run the generator to rebuild the manifest."
            )

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        data = torch.load(self.paths[idx], weights_only=False)
        # torch.save() of a HeteroData stores factory_id/split as plain
        # python values on the object; PyG's batching only wants
        # tensor-shaped node/edge stores, so drop those two before batching
        # and keep them out-of-band if you need them for debugging.
        data.pop("factory_id") if "factory_id" in data else None
        data.pop("split") if "split" in data else None
        return data


# --------------------------------------------------------------------------
# Model: heterogeneous GraphSAGE encoder (worker/job/asset) + edge-regression
# head predicting the 5-dim compatibility vector for ('worker',
# 'compatible_with', 'job') edges.
#
# CAVEAT worth knowing before trusting results: message passing here runs
# over 'rev_compatible_with' (job -> worker), which is the *unlabeled*
# structural mirror of the exact edges being predicted. A worker/job pair
# that has an edge at all is therefore visible to the encoder as "these two
# are connected" even before the prediction head runs - i.e. this is
# transductive link-attribute regression, not true edge existence
# prediction. For research validity beyond "does the pipeline shape work",
# either mask the target edge out of the message-passing graph per batch
# (edge dropout on 'compatible_with' / 'rev_compatible_with') or hold out
# whole worker-job pairs so the model never sees them in either role.
# --------------------------------------------------------------------------

class GraphSAGEEncoder(torch.nn.Module):
    def __init__(self, hidden_channels: int, out_channels: int):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), hidden_channels)
        self.conv2 = SAGEConv((-1, -1), out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index)
        return x


class CompatibilityPredictor(torch.nn.Module):
    def __init__(self, metadata, hidden_channels: int = 64, out_channels: int = 32,
                 num_targets: int = len(EDGE_LABEL_FIELDS)):
        super().__init__()
        base_encoder = GraphSAGEEncoder(hidden_channels, out_channels)
        self.encoder = to_hetero(base_encoder, metadata, aggr="mean")
        self.edge_head = torch.nn.Sequential(
            torch.nn.Linear(out_channels * 2, hidden_channels),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_channels, num_targets),
            torch.nn.Sigmoid(),  # targets are normalized to [0, 1]
        )

    def forward(self, x_dict, edge_index_dict, worker_idx, job_idx):
        embeddings = self.encoder(x_dict, edge_index_dict)
        w_emb = embeddings["worker"][worker_idx]
        j_emb = embeddings["job"][job_idx]
        pair = torch.cat([w_emb, j_emb], dim=-1)
        return self.edge_head(pair)


# --------------------------------------------------------------------------
# Train / eval loops
# --------------------------------------------------------------------------

def run_epoch(model, loader, optimizer, loss_fn, device, train: bool):
    model.train() if train else model.eval()
    total_loss, total_edges = 0.0, 0

    for batch in loader:
        batch = batch.to(device)
        worker_idx, job_idx = batch["worker", "compatible_with", "job"].edge_index
        targets = normalize_targets(batch["worker", "compatible_with", "job"].edge_attr)

        if train:
            optimizer.zero_grad()
            preds = model(batch.x_dict, batch.edge_index_dict, worker_idx, job_idx)
            loss = loss_fn(preds, targets)
            loss.backward()
            optimizer.step()
        else:
            with torch.no_grad():
                preds = model(batch.x_dict, batch.edge_index_dict, worker_idx, job_idx)
                loss = loss_fn(preds, targets)

        n = targets.size(0)
        total_loss += loss.item() * n
        total_edges += n

    return total_loss / max(total_edges, 1)


@torch.no_grad()
def evaluate_per_field_mae(model, loader, device):
    model.eval()
    abs_err = torch.zeros(len(EDGE_LABEL_FIELDS))
    count = 0
    for batch in loader:
        batch = batch.to(device)
        worker_idx, job_idx = batch["worker", "compatible_with", "job"].edge_index
        targets_raw = batch["worker", "compatible_with", "job"].edge_attr
        preds = unnormalize_preds(model(batch.x_dict, batch.edge_index_dict, worker_idx, job_idx))
        abs_err += (preds - targets_raw).abs().sum(dim=0).cpu()
        count += targets_raw.size(0)
    mae = abs_err / max(count, 1)
    return {field: mae[i].item() for i, field in enumerate(EDGE_LABEL_FIELDS)}


def load_predictor(checkpoint_path: Path, device=None) -> CompatibilityPredictor:
    """Reload a CompatibilityPredictor saved by run_training() below, fully
    reconstructed (no need to know hidden_channels/out_channels/metadata
    ahead of time - they're stored in the checkpoint). Example:

        model = load_predictor(Path(CONFIG['SAVE_PATH']))
        model.eval()
        with torch.no_grad():
            preds = unnormalize_preds(model(data.x_dict, data.edge_index_dict, worker_idx, job_idx))
    """
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = CompatibilityPredictor(
        metadata=checkpoint["metadata"],
        hidden_channels=checkpoint["hidden_channels"],
        out_channels=checkpoint["out_channels"],
        num_targets=len(checkpoint["edge_label_fields"]),
    ).to(device)
    model.load_state_dict(checkpoint["state_dict"])
    return model


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def run_training(manifest_path: str = None, graph_dir: str = None, save_path: str = None,
                  epochs: int = None, batch_size: int = None, lr: float = None,
                  hidden_channels: int = None, out_channels: int = None):
    """Runs the full train/val/test loop and saves the best checkpoint.
    Every argument falls back to CONFIG when not passed, so this can be
    called as-is with no arguments for the default run, or with overrides
    for a one-off experiment without editing CONFIG."""
    manifest_path = Path(manifest_path or CONFIG['MANIFEST_FILE'])
    graph_dir = Path(graph_dir or CONFIG['GRAPH_DIR']) if (graph_dir or CONFIG['GRAPH_DIR']) else None
    save_path = Path(save_path or CONFIG['SAVE_PATH'])
    epochs = epochs or CONFIG['EPOCHS']
    batch_size = batch_size or CONFIG['BATCH_SIZE']
    lr = lr or CONFIG['LR']
    hidden_channels = hidden_channels or CONFIG['HIDDEN_CHANNELS']
    out_channels = out_channels or CONFIG['OUT_CHANNELS']

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_ds = FactoryGraphDataset(manifest_path, "train", graph_dir=graph_dir)
    if len(train_ds) == 0:
        raise ValueError(
            f"No usable graphs found for split='train' in {manifest_path}. "
            f"Nothing to train on - check the generator actually produced graphs "
            f"with num_compatibility_edges > 0, and that the .pt files exist "
            f"(see any WARNING above about missing files - check CONFIG['GRAPH_DIR'])."
        )

    val_ds = FactoryGraphDataset(manifest_path, "val", graph_dir=graph_dir)
    test_ds = FactoryGraphDataset(manifest_path, "test", graph_dir=graph_dir)

    # Small factory counts frequently leave val/test empty (see
    # FactoryGraphDataset docstring). Rather than crash, fall back to
    # monitoring/reporting on the train set itself and say so loudly -
    # results from that fallback are NOT held-out and shouldn't be trusted
    # as a generalization estimate. The real fix is more factories, or
    # rebalancing assign_split() in the generator for small N (e.g. round-
    # robin assignment instead of hash-bucketing when total graphs < ~20).
    if len(val_ds) == 0:
        logger.warning("val split is empty - falling back to train graphs for validation. "
                        "val_loss below is NOT a held-out estimate.")
        val_ds = train_ds
    if len(test_ds) == 0:
        logger.warning("test split is empty - falling back to train graphs for testing. "
                        "test metrics below are NOT a held-out estimate.")
        test_ds = train_ds

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    logger.info(f"train/val/test graphs: {len(train_ds)}/{len(val_ds)}/{len(test_ds)}")

    # metadata (node types, edge types) is identical across graphs by
    # construction (build_hetero_graph always emits the same 4 edge types),
    # so any single graph is enough to infer it for to_hetero()
    sample = train_ds[0]
    model = CompatibilityPredictor(
        metadata=sample.metadata(),
        hidden_channels=hidden_channels,
        out_channels=out_channels,
    ).to(device)

    # lazy modules (SAGEConv with in_channels=-1) need one forward pass
    # before their parameters exist, hence before creating the optimizer
    with torch.no_grad():
        sample = sample.to(device)
        w_idx, j_idx = sample["worker", "compatible_with", "job"].edge_index
        model(sample.x_dict, sample.edge_index_dict, w_idx, j_idx)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = torch.nn.MSELoss()

    # checkpoint payload beyond state_dict: everything needed to reconstruct
    # this exact model architecture and interpret its predictions later,
    # without having to remember what config this run used.
    checkpoint_meta = {
        "metadata": sample.metadata(),
        "hidden_channels": hidden_channels,
        "out_channels": out_channels,
        "edge_label_fields": EDGE_LABEL_FIELDS,
        "eval_bounds": EVAL_BOUNDS,
        "feature_dims": train_ds.feature_dims,
    }

    save_path.parent.mkdir(parents=True, exist_ok=True)

    best_val = float("inf")
    for epoch in range(epochs):
        train_loss = run_epoch(model, train_loader, optimizer, loss_fn, device, train=True)
        val_loss = run_epoch(model, val_loader, optimizer, loss_fn, device, train=False)
        if val_loss < best_val:
            best_val = val_loss
            torch.save({"state_dict": model.state_dict(), **checkpoint_meta}, save_path)
        if epoch % 10 == 0 or epoch == epochs - 1:
            logger.info(f"epoch {epoch:3d} | train_loss {train_loss:.4f} | val_loss {val_loss:.4f}")

    checkpoint = torch.load(save_path, weights_only=False)
    model.load_state_dict(checkpoint["state_dict"])
    test_loss = run_epoch(model, test_loader, optimizer, loss_fn, device, train=False)
    per_field_mae = evaluate_per_field_mae(model, test_loader, device)

    print(f"\nTest loss (normalized MSE): {test_loss:.4f}")
    print("Test MAE per field (raw scale):")
    for field, mae in per_field_mae.items():
        print(f"  {field:32s} {mae:.4f}")
    print(f"\nBest checkpoint saved to: {save_path}")


if __name__ == "__main__":
    if validation == True:
        print("Train only")
    else:
        logging.basicConfig(level=logging.INFO)
        run_training()

    # run : python -m training.scripts.GNN_train