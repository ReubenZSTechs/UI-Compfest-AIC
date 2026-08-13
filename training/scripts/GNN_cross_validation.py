"""
K-fold cross-validation over ALL factory graphs listed in manifest.json,
reusing the model + train/eval loop from GNN_train.py.

Why this exists instead of just run_training()'s fixed 80/10/10 split:
with a small number of factories, assign_split()'s hash-bucketing can put
almost all the "signal" test factories into one lucky/unlucky split, so a
single test_loss / MAE number is noisy and easy to over- or under-trust.
K-fold rotates every factory through the test role exactly once and reports
mean +/- std across folds - a much more honest read on "does this generalize"
than one fixed split, especially while your factory count is small.

This does NOT read manifest.json's 'split' field at all - folds are built
fresh from every usable graph (num_compatibility_edges > 0), independent of
whatever assign_split() assigned at generation time.

run : python -m training.scripts.GNN_cross_validation
      python -m training.scripts.GNN_cross_validation --k 5 --epochs 100
"""

import argparse
import json
import logging
import random
import statistics
from pathlib import Path

import torch
from torch.utils.data import Dataset
from torch_geometric.loader import DataLoader

from training.scripts.GNN_train import (
    CONFIG as TRAIN_CONFIG,
    EDGE_LABEL_FIELDS,
    EVAL_BOUNDS,
    CompatibilityPredictor,
    evaluate_per_field_mae,
    run_epoch,
    get_val_state,
)

logger = logging.getLogger(__name__)

validation = get_val_state()

CV_CONFIG = {
    "MANIFEST_FILE": TRAIN_CONFIG["MANIFEST_FILE"],
    "GRAPH_DIR": TRAIN_CONFIG["GRAPH_DIR"],
    "SAVE_DIR": "./training/datasets/formatted/train/checkpoints/onet_based_cv_folds/",
    "K": 5,
    "VAL_FRACTION": 0.15,   # slice of each fold's train+val pool held out for early-stopping checkpoint selection
    "EPOCHS": TRAIN_CONFIG["EPOCHS"],
    "BATCH_SIZE": TRAIN_CONFIG["BATCH_SIZE"],
    "LR": TRAIN_CONFIG["LR"],
    "HIDDEN_CHANNELS": TRAIN_CONFIG["HIDDEN_CHANNELS"],
    "OUT_CHANNELS": TRAIN_CONFIG["OUT_CHANNELS"],
    "SEED": 42,
}


class FactoryGraphSubset(Dataset):
    """Same loading behavior as GNN_train.py's FactoryGraphDataset, but takes
    an explicit list of .pt paths instead of filtering a manifest by a fixed
    'split' field - lets fold membership be decided here instead."""

    def __init__(self, paths: list):
        self.paths = paths

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        data = torch.load(self.paths[idx], weights_only=False)
        data.pop("factory_id") if "factory_id" in data else None
        data.pop("split") if "split" in data else None
        return data


def load_all_graph_paths(manifest_path: Path, graph_dir: Path = None):
    """Every graph in the manifest with at least one compatibility edge -
    graphs with zero labeled edges can't contribute to supervised loss, same
    filter FactoryGraphDataset uses."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    edge_label_fields = manifest["edge_label_fields"]
    assert edge_label_fields == EDGE_LABEL_FIELDS, (
        "manifest.json edge_label_fields don't match GNN_train.py's EDGE_LABEL_FIELDS; "
        "regenerate the manifest or update EVAL_BOUNDS/EDGE_LABEL_FIELDS there."
    )

    paths, missing = [], []
    for entry in manifest["graphs"]:
        if entry["num_compatibility_edges"] == 0:
            continue
        path = (graph_dir / Path(entry["graph_path"]).name) if graph_dir else Path(entry["graph_path"])
        (paths if path.exists() else missing).append(path if path.exists() else (entry["filename"], path))

    if missing:
        preview = "\n".join(f"  {fn} -> {p}" for fn, p in missing[:5])
        logger.warning(
            f"{len(missing)} graph(s) listed in the manifest are missing on disk (skipped):\n{preview}\n"
            f"Set --graph-dir to the actual folder if paths have gone stale."
        )
    return paths


def make_kfolds(paths: list, k: int, seed: int) -> list:
    """Deterministic shuffle + round-robin split into k folds of nearly-equal
    size. Round-robin (not contiguous slicing) keeps fold sizes balanced
    even when len(paths) isn't a multiple of k."""
    shuffled = list(paths)
    random.Random(seed).shuffle(shuffled)
    return [shuffled[i::k] for i in range(k)]


def train_one_fold(train_paths, val_paths, test_paths, device, epochs, batch_size, lr,
                    hidden_channels, out_channels, fold_idx, k):
    train_ds = FactoryGraphSubset(train_paths)
    val_ds = FactoryGraphSubset(val_paths)
    test_ds = FactoryGraphSubset(test_paths)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    logger.info(
        f"[fold {fold_idx + 1}/{k}] train/val/test graphs: "
        f"{len(train_ds)}/{len(val_ds)}/{len(test_ds)}"
    )

    sample = train_ds[0]
    model = CompatibilityPredictor(
        metadata=sample.metadata(), hidden_channels=hidden_channels, out_channels=out_channels
    ).to(device)

    # lazy modules need one forward pass before params exist / optimizer is built
    with torch.no_grad():
        s = sample.to(device)
        w_idx, j_idx = s["worker", "compatible_with", "job"].edge_index
        model(s.x_dict, s.edge_index_dict, w_idx, j_idx)

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = torch.nn.MSELoss()

    best_val = float("inf")
    best_state = None
    for epoch in range(epochs):
        train_loss = run_epoch(model, train_loader, optimizer, loss_fn, device, train=True)
        val_loss = run_epoch(model, val_loader, optimizer, loss_fn, device, train=False)
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k2: v.clone() for k2, v in model.state_dict().items()}
        if epoch % 10 == 0 or epoch == epochs - 1:
            logger.info(f"[fold {fold_idx + 1}] epoch {epoch:3d} | train {train_loss:.4f} | val {val_loss:.4f}")

    model.load_state_dict(best_state)
    test_loss = run_epoch(model, test_loader, optimizer, loss_fn, device, train=False)
    per_field_mae = evaluate_per_field_mae(model, test_loader, device)

    return model, sample, {
        "fold": fold_idx,
        "n_train": len(train_ds),
        "n_val": len(val_ds),
        "n_test": len(test_ds),
        "test_loss": test_loss,
        **per_field_mae,
    }


def run_cross_validation(manifest_path=None, graph_dir=None, save_dir=None, k=None,
                          val_fraction=None, epochs=None, batch_size=None, lr=None,
                          hidden_channels=None, out_channels=None, seed=None):
    manifest_path = Path(manifest_path or CV_CONFIG["MANIFEST_FILE"])
    graph_dir = Path(graph_dir or CV_CONFIG["GRAPH_DIR"]) if (graph_dir or CV_CONFIG["GRAPH_DIR"]) else None
    save_dir = Path(save_dir or CV_CONFIG["SAVE_DIR"])
    k = k or CV_CONFIG["K"]
    val_fraction = val_fraction if val_fraction is not None else CV_CONFIG["VAL_FRACTION"]
    epochs = epochs or CV_CONFIG["EPOCHS"]
    batch_size = batch_size or CV_CONFIG["BATCH_SIZE"]
    lr = lr or CV_CONFIG["LR"]
    hidden_channels = hidden_channels or CV_CONFIG["HIDDEN_CHANNELS"]
    out_channels = out_channels or CV_CONFIG["OUT_CHANNELS"]
    seed = seed if seed is not None else CV_CONFIG["SEED"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    all_paths = load_all_graph_paths(manifest_path, graph_dir)
    if len(all_paths) < k:
        raise ValueError(
            f"Only {len(all_paths)} usable graph(s) found but k={k} folds requested. "
            f"Generate more factories, or lower --k."
        )

    folds = make_kfolds(all_paths, k=k, seed=seed)
    save_dir.mkdir(parents=True, exist_ok=True)

    fold_results = []
    for fold_idx in range(k):
        test_paths = folds[fold_idx]
        train_val_paths = [p for j, fold in enumerate(folds) if j != fold_idx for p in fold]

        rng = random.Random(seed + fold_idx)
        rng.shuffle(train_val_paths)
        n_val = max(1, round(len(train_val_paths) * val_fraction)) if len(train_val_paths) > 1 else 0
        val_paths = train_val_paths[:n_val] or train_val_paths  # fall back to reusing train if too few graphs
        train_paths = train_val_paths[n_val:] or train_val_paths

        model, sample, metrics = train_one_fold(
            train_paths, val_paths, test_paths, device,
            epochs, batch_size, lr, hidden_channels, out_channels, fold_idx, k,
        )
        fold_results.append(metrics)

        fold_ckpt_path = save_dir / f"fold_{fold_idx}_predictor.pt"
        torch.save({
            "state_dict": model.state_dict(),
            "metadata": sample.metadata(),
            "hidden_channels": hidden_channels,
            "out_channels": out_channels,
            "edge_label_fields": EDGE_LABEL_FIELDS,
            "eval_bounds": EVAL_BOUNDS,
        }, fold_ckpt_path)
        logger.info(f"[fold {fold_idx + 1}/{k}] test_loss {metrics['test_loss']:.4f} | saved -> {fold_ckpt_path}")

    print_cv_summary(fold_results, k)
    return fold_results


def print_cv_summary(fold_results: list, k: int):
    print(f"\n{'=' * 60}\n{k}-fold cross-validation results\n{'=' * 60}")
    for r in fold_results:
        print(
            f"fold {r['fold'] + 1}: test_loss={r['test_loss']:.4f}  "
            f"(train={r['n_train']} val={r['n_val']} test={r['n_test']})"
        )

    metric_names = ["test_loss"] + EDGE_LABEL_FIELDS
    print(f"\n{'metric':32s} {'mean':>10s} {'std':>10s}")
    for name in metric_names:
        values = [r[name] for r in fold_results]
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        print(f"{name:32s} {mean:10.4f} {std:10.4f}")


def main():
    parser = argparse.ArgumentParser(description="K-fold cross-validation for the compatibility GNN.")
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--graph-dir", default=None)
    parser.add_argument("--save-dir", default=None)
    parser.add_argument("--k", type=int, default=None)
    parser.add_argument("--val-fraction", type=float, default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--hidden-channels", type=int, default=None)
    parser.add_argument("--out-channels", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    run_cross_validation(
        manifest_path=args.manifest, graph_dir=args.graph_dir, save_dir=args.save_dir,
        k=args.k, val_fraction=args.val_fraction, epochs=args.epochs, batch_size=args.batch_size,
        lr=args.lr, hidden_channels=args.hidden_channels, out_channels=args.out_channels, seed=args.seed,
    )


if __name__ == "__main__":
    if validation == True:
        print("Train only")
    else:
        main()

    # run : python -m training.scripts.GNN_cross_validation