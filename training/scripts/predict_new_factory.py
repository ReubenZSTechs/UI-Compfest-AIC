"""
Loads a trained CompatibilityPredictor checkpoint and runs inference on a
NEW factory (one not used in training) - no LLM calls, no ground-truth
labels needed.

Pipeline for one new factory:
    factory JSON  --build_hetero_graph()-->  HeteroData (no compatible_with
                                               edges yet, since there's
                                               nothing to predict from)
                  --flatten_pair_items()-->   which (worker, job) pairs are
                                               actually evaluable (job has a
                                               resolvable assigned_asset_id)
                  --load_predictor()------>   trained model
                  --model.forward()-------->  5-dim compatibility vector
                                               per (worker, job) pair
                  --unnormalize_preds()---->  raw-scale predictions
                  --rank per job----------->  best-fit worker(s) per job
                  --save--------------------> predictions.json (+ optional
                                               .pt graph if you want to keep
                                               the built graph itself)

IMPORTANT: build_hetero_graph() is reused as-is from Training_sample_generator.py
so the new factory's feature vectors line up EXACTLY with what the model was
trained on (same vocab, same one-hot ordering, same feature dims). Do not
recompute features by hand here.

run: python -m training.scripts.predict_new_factory /path/to/new_factory.json
     python -m training.scripts.predict_new_factory --generate   (makes one
         synthetic factory on the fly instead of reading a file)
     python -m training.scripts.predict_new_factory --factory-dir /path/to/validation_factories/
         (batch mode: loads the checkpoint ONCE, then runs inference on every
         *.json factory in the folder - see run_batch() below)
"""

import argparse
import json
import logging
from pathlib import Path

import torch

# Pure graph-building functions only - no aiofiles/yaml/backend agent deps.
# Training_sample_generator.py imports these same functions from here too,
# so both pipelines are guaranteed to build graphs the same way.
from training.scripts.factory_graph_utils import (
    build_hetero_graph,
    flatten_pair_items,
    get_jobs,
    load_input,
)
from training.scripts.GNN_train import CONFIG as TRAIN_CONFIG
from training.scripts.GNN_train import EDGE_LABEL_FIELDS, load_predictor, unnormalize_preds

logger = logging.getLogger(__name__)

PREDICT_CONFIG = {
    "CHECKPOINT_PATH": TRAIN_CONFIG["SAVE_PATH"],
    "OUTPUT_PATH": "./training/datasets/formatted/validation/predictions/new_factory_predictions.json",
    "TOP_K_PER_JOB": 3,
}


def build_new_factory_graph(doc: dict):
    """Same builder used at training time, called with evaluations=[] since
    a brand-new factory has no LLM-evaluated compatibility labels yet - that
    absence is exactly why we're predicting. This also means the
    (worker, compatible_with, job) / (job, rev_compatible_with, worker)
    edges come back empty, which happens to match the leak-free message
    passing setup used during training/eval (see mask_target_edges in
    GNN_train.py) - the encoder never sees a pre-existing compatibility
    edge for a factory it's predicting on, by construction."""
    graph_data, _ = build_hetero_graph(doc, evaluations=[])
    return graph_data


def build_prediction_pairs(doc: dict, graph_data):
    """Every (worker, job) pair whose job resolves to a real asset (same
    filter Training_sample_generator.py uses for training pairs), mapped to
    node indices in graph_data so they can be fed straight into the model."""
    worker_id_to_idx = {wid: i for i, wid in enumerate(graph_data["worker"].node_id)}
    job_id_to_idx = {jid: i for i, jid in enumerate(graph_data["job"].node_id)}
    jobs_by_id = {j["job_id"]: j for j in get_jobs(doc)}

    pairs = []
    for worker_id, job_id, asset_id, _prompt_text in flatten_pair_items(doc):
        w_idx = worker_id_to_idx.get(worker_id)
        j_idx = job_id_to_idx.get(job_id)
        if w_idx is None or j_idx is None:
            continue
        pairs.append({
            "worker_id": worker_id,
            "job_id": job_id,
            "job_title": jobs_by_id[job_id]["job_title"],
            "asset_id": asset_id,
            "w_idx": w_idx,
            "j_idx": j_idx,
        })

    if not pairs:
        raise ValueError(
            "No evaluable (worker, job) pairs found for this factory - check "
            "that job_descriptions[].assigned_asset_id resolves to a real "
            "asset_id and that workers[] is non-empty."
        )
    return pairs


@torch.no_grad()
def predict_with_model(model, doc: dict, graph_data, device) -> list:
    """Same forward-pass + unnormalize + reshape logic predict_compatibility()
    used to do inline, split out so a batch run can load the checkpoint once
    and call this per factory instead of re-loading it from disk every time."""
    pairs = build_prediction_pairs(doc, graph_data)

    graph_data = graph_data.to(device)
    worker_idx = torch.tensor([p["w_idx"] for p in pairs], dtype=torch.long, device=device)
    job_idx = torch.tensor([p["j_idx"] for p in pairs], dtype=torch.long, device=device)

    preds = unnormalize_preds(
        model(graph_data.x_dict, graph_data.edge_index_dict, worker_idx, job_idx)
    ).cpu()

    results = []
    for pair, pred_row in zip(pairs, preds):
        entry = {
            "worker_id": pair["worker_id"],
            "job_id": pair["job_id"],
            "job_title": pair["job_title"],
            "asset_id": pair["asset_id"],
        }
        entry.update({field: pred_row[i].item() for i, field in enumerate(EDGE_LABEL_FIELDS)})
        results.append(entry)
    return results


def predict_compatibility(doc: dict, graph_data, checkpoint_path: Path, device=None) -> list:
    """Single-factory convenience wrapper: loads the checkpoint, runs
    predict_with_model() once, returns results. Kept for the single-file /
    --generate CLI paths below - batch mode uses predict_with_model()
    directly so the checkpoint is only loaded once for the whole folder."""
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_predictor(checkpoint_path, device=device)
    model.eval()
    return predict_with_model(model, doc, graph_data, device)


def rank_best_worker_per_job(results: list, top_k: int = 3) -> dict:
    """Groups predictions by job_id, sorted by overall_compatibility_score
    descending - the "who should we place here" view."""
    by_job = {}
    for r in results:
        by_job.setdefault(r["job_id"], []).append(r)
    ranked = {}
    for job_id, rows in by_job.items():
        rows_sorted = sorted(rows, key=lambda r: r["overall_compatibility_score"], reverse=True)
        ranked[job_id] = rows_sorted[:top_k]
    return ranked


def print_rankings(ranked: dict):
    for job_id, rows in ranked.items():
        job_title = rows[0]["job_title"]
        print(f"\n{job_id} ({job_title}) - top {len(rows)} candidate(s):")
        for r in rows:
            print(
                f"  {r['worker_id']:14s} "
                f"score={r['overall_compatibility_score']:.3f}  "
                f"throughput_x={r['throughput_multiplier']:.3f}  "
                f"error_x={r['error_multiplier']:.3f}  "
                f"fatigue_rate={r['fatigue_accumulation_rate']:.3f}  "
                f"stress_sens={r['stress_sensitivity_factor']:.3f}"
            )


def save_results(results: list, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Saved {len(results)} predictions to {out_path}")


def run_batch(factory_dir: Path, checkpoint_path: Path, output_dir: Path, top_k: int, device=None) -> dict:
    """Loads the checkpoint ONCE, then runs the full predict -> rank -> save
    flow for every *.json factory found directly under factory_dir (non-
    recursive - each file is expected to be one factory digital-twin doc,
    same shape gen_factory()/load_input() produce). A per-factory failure
    (bad JSON, zero evaluable pairs, etc.) is logged and skipped rather than
    aborting the whole batch - see summary['failed'] for what to fix."""
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_predictor(checkpoint_path, device=device)
    model.eval()

    factory_files = sorted(factory_dir.glob("*.json"))
    if not factory_files:
        raise ValueError(f"No *.json factory files found under {factory_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    succeeded, failed = [], []

    for filepath in factory_files:
        try:
            doc = load_input(filepath)
            graph_data = build_new_factory_graph(doc)
            results = predict_with_model(model, doc, graph_data, device)

            ranked = rank_best_worker_per_job(results, top_k=top_k)
            print(f"\n=== {filepath.name} ===")
            print_rankings(ranked)

            out_path = output_dir / f"{filepath.stem}_predictions.json"
            save_results(results, out_path)
            succeeded.append(filepath.name)
        except Exception as e:
            logger.exception(f"{filepath.name}: prediction failed, skipping")
            failed.append({"filename": filepath.name, "error": str(e)})

    print(f"\nBatch done. {len(succeeded)}/{len(factory_files)} factories predicted -> {output_dir}")
    if failed:
        print(f"{len(failed)} factory(s) failed:")
        for f in failed:
            print(f"  {f['filename']}: {f['error']}")

    return {"succeeded": succeeded, "failed": failed, "output_dir": str(output_dir)}


def main():
    parser = argparse.ArgumentParser(description="Predict worker-job compatibility for a new factory.")
    parser.add_argument("factory_json", nargs="?", default=None,
                         help="Path to a new factory digital-twin JSON. Omit with --generate or --factory-dir.")
    parser.add_argument("--generate", action="store_true",
                         help="Generate one synthetic factory on the fly instead of reading a file.")
    parser.add_argument("--factory-dir", default=None,
                         help="Folder of factory JSONs to batch-predict (e.g. a validation set). "
                              "Loads the checkpoint once, predicts on every *.json file in the folder.")
    parser.add_argument("--checkpoint", default=PREDICT_CONFIG["CHECKPOINT_PATH"])
    parser.add_argument("--output", default=PREDICT_CONFIG["OUTPUT_PATH"],
                         help="Single-factory mode: output file path. Ignored in --factory-dir mode "
                              "(use --output-dir instead).")
    parser.add_argument("--output-dir", default="./training/datasets/formatted/predictions/validation/",
                         help="Batch mode only: folder to write one <factory>_predictions.json per input factory.")
    parser.add_argument("--top-k", type=int, default=PREDICT_CONFIG["TOP_K_PER_JOB"])
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.factory_dir:
        run_batch(
            factory_dir=Path(args.factory_dir),
            checkpoint_path=Path(args.checkpoint),
            output_dir=Path(args.output_dir),
            top_k=args.top_k,
        )
        return

    if args.generate:
        from training.scripts.generate_synthetic_factories import gen_factory
        from training.scripts.onet_lookup import OnetProfiles
        # idx chosen well outside the training generator's NUM_FACTORIES range
        # so factory_id/worker_id/job_id namespaces don't collide with training data
        onet = OnetProfiles()
        doc = gen_factory(idx=9001, onet=onet)
    elif args.factory_json:
        doc = load_input(Path(args.factory_json))
    else:
        parser.error("Provide a factory_json path, --generate, or --factory-dir.")
        return

    graph_data = build_new_factory_graph(doc)
    results = predict_compatibility(doc, graph_data, Path(args.checkpoint))

    ranked = rank_best_worker_per_job(results, top_k=args.top_k)
    print_rankings(ranked)

    save_results(results, Path(args.output))


if __name__ == "__main__":
    main()

    # run : python -m training.scripts.predict_new_factory --factory-dir ./training/datasets/formatted/validation/onet_based_factories/ --output-dir ./training/datasets/formatted/validation/predictions/