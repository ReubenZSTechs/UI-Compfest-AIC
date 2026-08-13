"""
optimize_factory_assignment.py

Turns predict_new_factory.py's per-(worker, job) predictions into ONE
optimal worker -> job assignment for the whole factory - "worker 1 -> job/
machine X, worker 2 -> job/machine Y, ..." - by solving it as a linear
assignment problem (Hungarian algorithm), instead of just picking each job's
top-1 worker independently. Picking per-job winners independently can select
the SAME worker for multiple jobs and leave other jobs unfilled; the
Hungarian algorithm finds the single set of pairings that maximizes total
utility across the whole factory at once, with each worker and each job
used at most once.

OBJECTIVE: a weighted combination of the 5 predicted fields (default: just
overall_compatibility_score). throughput_multiplier is "higher is better"
as-is; error_multiplier / fatigue_accumulation_rate / stress_sensitivity_
factor are "lower is better", so they're inverted (1/x) before weighting -
that way every term in the weighted sum still means "bigger utility = better
placement" and can be combined consistently.

RECTANGULAR CASE: if there are more workers than jobs (typical - e.g. 13
workers vs 8 jobs in a small synthetic factory), scipy's
linear_sum_assignment handles that directly: the smaller side (jobs) gets
fully matched to its best workers, the rest of the workers are reported as
"unassigned" rather than forced into a bad-fit slot. Same the other way if
jobs > workers.

INPUT: the *_predictions.json file(s) predict_new_factory.py writes -
{worker_id, job_id, job_title, asset_id, overall_compatibility_score,
throughput_multiplier, error_multiplier, fatigue_accumulation_rate,
stress_sensitivity_factor} per (worker, job) pair.

run:
    python -m training.scripts.optimize_factory_assignment predictions/factory_0001_predictions.json
    python -m training.scripts.optimize_factory_assignment --dir predictions/validation/
    python -m training.scripts.optimize_factory_assignment factory_0001_predictions.json \
        --weights overall_compatibility_score=1.0 throughput_multiplier=0.3 error_multiplier=0.3
"""

import argparse
import json
import logging
from pathlib import Path

import numpy as np

try:
    from scipy.optimize import linear_sum_assignment
except ImportError as e:
    raise ImportError(
        "optimize_factory_assignment.py needs scipy for the Hungarian algorithm "
        "(scipy.optimize.linear_sum_assignment). Install with: pip install scipy"
    ) from e

logger = logging.getLogger(__name__)

# Which predicted fields count toward the assignment objective, and their
# direction: True = higher is better (used as-is), False = lower is better
# (inverted to 1/x before weighting). Default: only overall_compatibility_score
# counts (weight 1.0); everything else has weight 0 unless overridden via
# --weights on the CLI.
DEFAULT_WEIGHTS = {
    "overall_compatibility_score": (1.0, True),
    "throughput_multiplier": (0.0, True),
    "error_multiplier": (0.0, False),
    "fatigue_accumulation_rate": (0.0, False),
    "stress_sensitivity_factor": (0.0, False),
}


def load_predictions(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def compute_utility(entry: dict, weights: dict) -> float:
    """Single scalar utility per (worker, job) pair from the weighted fields."""
    utility = 0.0
    for field, (weight, higher_is_better) in weights.items():
        if weight == 0.0:
            continue
        value = entry[field]
        utility += weight * (value if higher_is_better else (1.0 / value if value else 0.0))
    return utility


def build_utility_matrix(predictions: list, weights: dict):
    """Pivots the flat prediction list into a (workers x jobs) utility
    matrix. Missing pairs (a worker never evaluated against some job) get
    -inf utility so the solver can never pick them."""
    worker_ids = sorted({p["worker_id"] for p in predictions})
    job_ids = sorted({p["job_id"] for p in predictions})
    w_idx = {w: i for i, w in enumerate(worker_ids)}
    j_idx = {j: i for i, j in enumerate(job_ids)}

    job_meta = {p["job_id"]: {"job_title": p["job_title"], "asset_id": p["asset_id"]} for p in predictions}

    utility = np.full((len(worker_ids), len(job_ids)), -np.inf)
    raw_by_cell = {}
    for p in predictions:
        wi, ji = w_idx[p["worker_id"]], j_idx[p["job_id"]]
        utility[wi, ji] = compute_utility(p, weights)
        raw_by_cell[(wi, ji)] = p

    return utility, worker_ids, job_ids, job_meta, raw_by_cell


def solve_assignment(utility: np.ndarray):
    """Hungarian algorithm maximizes utility by minimizing -utility. Works
    directly on rectangular matrices (unequal worker/job counts) - the
    smaller dimension gets fully matched, the rest are left unassigned."""
    cost = -utility
    row_idx, col_idx = linear_sum_assignment(cost)
    # drop any pair that landed on a -inf cell (never-evaluated pair) -
    # only possible with an incomplete prediction set
    return [(r, c) for r, c in zip(row_idx, col_idx) if np.isfinite(utility[r, c])]


def format_assignment(valid_pairs, worker_ids, job_ids, job_meta, raw_by_cell, utility) -> dict:
    assigned_workers = {r for r, _ in valid_pairs}
    assigned_jobs = {c for _, c in valid_pairs}

    rows = []
    for r, c in sorted(valid_pairs, key=lambda rc: -utility[rc]):
        entry = raw_by_cell[(r, c)]
        rows.append({
            "worker_id": worker_ids[r],
            "job_id": job_ids[c],
            "job_title": job_meta[job_ids[c]]["job_title"],
            "asset_id": job_meta[job_ids[c]]["asset_id"],
            "utility": round(float(utility[r, c]), 4),
            "overall_compatibility_score": entry["overall_compatibility_score"],
            "throughput_multiplier": entry["throughput_multiplier"],
            "error_multiplier": entry["error_multiplier"],
            "fatigue_accumulation_rate": entry["fatigue_accumulation_rate"],
            "stress_sensitivity_factor": entry["stress_sensitivity_factor"],
        })

    unassigned_workers = [worker_ids[i] for i in range(len(worker_ids)) if i not in assigned_workers]
    unassigned_jobs = [job_ids[i] for i in range(len(job_ids)) if i not in assigned_jobs]

    return {
        "assignments": rows,
        "total_utility": round(float(sum(r["utility"] for r in rows)), 4),
        "unassigned_workers": unassigned_workers,
        "unassigned_jobs": unassigned_jobs,
    }


def print_assignment(result: dict, factory_name: str = ""):
    header = f"Optimal assignment{f' - {factory_name}' if factory_name else ''}"
    print(f"\n{header}\n{'=' * len(header)}")
    for r in result["assignments"]:
        print(
            f"  {r['worker_id']:14s} -> {r['job_id']:14s} ({r['job_title']:26s} {r['asset_id']:14s})  "
            f"score={r['overall_compatibility_score']:.3f}  utility={r['utility']:.3f}"
        )
    print(f"\nTotal utility: {result['total_utility']:.3f}  "
          f"({len(result['assignments'])} pair(s) assigned)")
    if result["unassigned_workers"]:
        print(f"Unassigned workers ({len(result['unassigned_workers'])}): "
              f"{', '.join(result['unassigned_workers'])}")
    if result["unassigned_jobs"]:
        print(f"Unassigned jobs ({len(result['unassigned_jobs'])}): "
              f"{', '.join(result['unassigned_jobs'])}")


def optimize_one(predictions_path: Path, weights: dict, output_path: Path = None) -> dict:
    predictions = load_predictions(predictions_path)
    if not predictions:
        raise ValueError(f"{predictions_path}: no predictions to assign")

    utility, worker_ids, job_ids, job_meta, raw_by_cell = build_utility_matrix(predictions, weights)
    valid_pairs = solve_assignment(utility)
    result = format_assignment(valid_pairs, worker_ids, job_ids, job_meta, raw_by_cell, utility)

    print_assignment(result, factory_name=predictions_path.stem)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Saved assignment -> {output_path}")

    return result


def parse_weight_args(weight_strs: list) -> dict:
    """--weights field=value pairs override DEFAULT_WEIGHTS' weight (keeps
    the built-in higher_is_better direction for that field)."""
    weights = {k: list(v) for k, v in DEFAULT_WEIGHTS.items()}
    for item in weight_strs or []:
        field, _, value = item.partition("=")
        if field not in weights:
            raise ValueError(f"Unknown field '{field}' - choose from {list(weights)}")
        weights[field][0] = float(value)
    return {k: tuple(v) for k, v in weights.items()}


def main():
    parser = argparse.ArgumentParser(
        description="Solve the optimal worker->job assignment from predict_new_factory.py output "
                    "(Hungarian algorithm, maximizes total utility)."
    )
    parser.add_argument("predictions_json", nargs="?", default=None,
                         help="Path to one factory's *_predictions.json file.")
    parser.add_argument("--dir", default="./training/datasets/formatted/validation/predictions/",
                         help="Folder of *_predictions.json files to batch-optimize.")
    parser.add_argument("--output", default=None,
                         help="Single-file mode: where to save the assignment JSON.")
    parser.add_argument("--output-dir", default="./training/datasets/formatted/validation/assignments/",
                         help="Batch mode: folder to write one <factory>_assignment.json per input file.")
    parser.add_argument("--weights", nargs="*", default=None,
                         help="Override objective weights, e.g. --weights overall_compatibility_score=1.0 "
                              "throughput_multiplier=0.3 error_multiplier=0.3. Fields not listed keep "
                              "their default weight (0, except overall_compatibility_score=1.0).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    weights = parse_weight_args(args.weights)

    if args.dir:
        in_dir = Path(args.dir)
        out_dir = Path(args.output_dir)
        files = sorted(in_dir.glob("*_predictions.json")) or sorted(in_dir.glob("*.json"))
        if not files:
            raise ValueError(f"No prediction JSON files found under {in_dir}")
        for f in files:
            out_path = out_dir / f"{f.stem.replace('_predictions', '')}_assignment.json"
            optimize_one(f, weights, output_path=out_path)
        return

    if not args.predictions_json:
        parser.error("Provide a predictions_json path or --dir.")
        return

    output_path = Path(args.output) if args.output else None
    optimize_one(Path(args.predictions_json), weights, output_path=output_path)


if __name__ == "__main__":
    main()

    # run : python -m training.scripts.optimize_factory_assignment training/datasets/formatted/validation/predictions/factory_0001_predictions.json
    # or  : python -m training.scripts.optimize_factory_assignment --dir training/datasets/formatted/validation/predictions/

    # use this : python -m training.scripts.optimize_factory_assignment