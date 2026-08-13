"""
factory_placement_API.py

One function: give it a factory digital-twin JSON, get back the optimal
worker -> job placement JSON. No HTTP server, no CLI - just calls
predict_new_factory.py's inference and optimize_factory_assignment.py's
Hungarian-algorithm solver directly, in-process.

    factory JSON (dict)
        --build_new_factory_graph()-->  HeteroData
        --predict_with_model()-------->  per-(worker, job) compatibility predictions
        --build_utility_matrix()------>  workers x jobs utility matrix
        --solve_assignment()---------->  Hungarian algorithm -> optimal pairing
        --format_assignment()--------->  result dict

Nothing here is reimplemented - this file only chains the existing functions
from predict_new_factory.py and optimize_factory_assignment.py.

USE AS A LIBRARY (this is the intended integration point):

    from training.scripts.factory_placement_API import place_factory

    result = place_factory(factory_doc)   # factory_doc = dict, matches the factory schema
    # result == {"predictions": [...], "optimal_assignment": {...}}

The checkpoint is loaded once on first call and cached in-process (see
_get_cached_model()), so repeated calls to place_factory() from the same
process are cheap - no need to manage a model object yourself. If you want
explicit control instead (e.g. a custom checkpoint path per call, or to
force a reload), call load_model_once() yourself and pass model/device in.
"""

import logging
from pathlib import Path
from typing import Optional

import torch

from training.scripts.GNN_train import load_predictor
from training.scripts.predict_new_factory import (
    PREDICT_CONFIG,
    build_new_factory_graph,
    predict_with_model,
)
from training.scripts.optimize_factory_assignment import (
    DEFAULT_WEIGHTS,
    build_utility_matrix,
    format_assignment,
    solve_assignment,
)

logger = logging.getLogger(__name__)

# in-process cache so place_factory() can be called repeatedly without the
# caller having to manage a model object - populated lazily on first call
_CACHED_MODEL = None
_CACHED_DEVICE = None
_CACHED_CHECKPOINT_PATH = None


def load_model_once(checkpoint_path: Path = None, device=None):
    """Loads the checkpoint ONCE. Reuse the returned (model, device) across
    every predict_and_optimize() call instead of letting each call reload
    the checkpoint from disk - same reasoning as predict_new_factory.py's
    run_batch()."""
    checkpoint_path = checkpoint_path or Path(PREDICT_CONFIG["CHECKPOINT_PATH"])
    device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_predictor(checkpoint_path, device=device)
    model.eval()
    return model, device


def _get_cached_model(checkpoint_path: Optional[Path] = None):
    """Lazily loads and caches the model in-process. Reloads only if a
    different checkpoint_path is requested than what's currently cached."""
    global _CACHED_MODEL, _CACHED_DEVICE, _CACHED_CHECKPOINT_PATH

    resolved_path = Path(checkpoint_path) if checkpoint_path else Path(PREDICT_CONFIG["CHECKPOINT_PATH"])

    if _CACHED_MODEL is None or resolved_path != _CACHED_CHECKPOINT_PATH:
        _CACHED_MODEL, _CACHED_DEVICE = load_model_once(resolved_path)
        _CACHED_CHECKPOINT_PATH = resolved_path

    return _CACHED_MODEL, _CACHED_DEVICE


def _merge_weights(overrides: Optional[dict]) -> dict:
    weights = {k: list(v) for k, v in DEFAULT_WEIGHTS.items()}
    for field, value in (overrides or {}).items():
        if field not in weights:
            raise ValueError(f"Unknown weight field '{field}' - choose from {list(weights)}")
        weights[field][0] = float(value)
    return {k: tuple(v) for k, v in weights.items()}


def predict_and_optimize(
    factory: dict,
    model=None,
    device=None,
    checkpoint_path: Path = None,
    weights: dict = None,
) -> dict:
    """Core function: give it a factory digital-twin JSON (already parsed
    into a dict), get back {"predictions": [...], "optimal_assignment": {...}}.

    If model/device aren't passed in, the checkpoint is loaded fresh for
    this single call. For repeated calls, prefer place_factory() below,
    which caches the model automatically, or pass a preloaded model here
    yourself via load_model_once()."""
    if model is None:
        model, device = load_model_once(checkpoint_path, device)

    graph_data = build_new_factory_graph(factory)
    results = predict_with_model(model, factory, graph_data, device)

    if not results:
        raise ValueError("No evaluable (worker, job) pairs in this factory.")

    merged_weights = _merge_weights(weights)
    utility, worker_ids, job_ids, job_meta, raw_by_cell = build_utility_matrix(results, merged_weights)
    valid_pairs = solve_assignment(utility)
    assignment = format_assignment(valid_pairs, worker_ids, job_ids, job_meta, raw_by_cell, utility)

    return {
        "predictions": results,
        "optimal_assignment": assignment,
    }


def place_factory(
    factory: dict,
    weights: Optional[dict] = None,
    checkpoint_path: Optional[Path] = None,
) -> dict:
    """READY-TO-CALL entry point: JSON in, JSON out.

    Args:
        factory: factory digital-twin dict, matching the schema
            build_hetero_graph() / predict_new_factory.py expects.
        weights: optional override dict, e.g.
            {"overall_compatibility_score": 1.0, "throughput_multiplier": 0.3}.
            Fields not listed keep their default weight (0, except
            overall_compatibility_score=1.0). Pass None to use the defaults.
        checkpoint_path: optional path to a specific model checkpoint.
            Defaults to PREDICT_CONFIG["CHECKPOINT_PATH"]. The model is
            loaded once and cached in-process; pass a different path to
            force loading a different checkpoint.

    Returns:
        {
            "predictions": [ {worker_id, job_id, job_title, asset_id,
                               overall_compatibility_score,
                               throughput_multiplier, error_multiplier,
                               fatigue_accumulation_rate,
                               stress_sensitivity_factor}, ... ],
            "optimal_assignment": {
                "assignments": [ {worker_id, job_id, job_title, asset_id,
                                   utility, ...raw fields}, ... ],
                "total_utility": float,
                "unassigned_workers": [...],
                "unassigned_jobs": [...],
            }
        }
    """
    model, device = _get_cached_model(checkpoint_path)
    return predict_and_optimize(factory, model=model, device=device, weights=weights)