"""
Training_sample_generator.py (deterministic / no-LLM version)

Same job as the original: turn each synthetic factory doc under INPUT_DIR
into a set of worker-job compatibility evaluations, then build + save the
HeteroData graph for GNN_train.py. The ONLY thing that changed is *how* the
5-field evaluation (overall_compatibility_score, throughput_multiplier,
error_multiplier, fatigue_accumulation_rate, stress_sensitivity_factor) is
produced: instead of calling an LLM agent per (worker, job) pair, it's now a
closed-form function of the O*NET-grounded fields already baked into each
worker/job by generate_synthetic_factories.py (baseline_physical_stamina,
cognitive_resilience, required_cognitive_focus, task_complexity,
physical_demand_level, error_severity, shift_context, asset environmental
factors).

This means:
  - No agent_registry_service / call_llm_service imports, no asyncio, no
    retries, no checkpoint/staging machinery (all of that existed to handle
    a flaky/slow network call that no longer exists here).
  - Fully reproducible: re-running on the same factory files produces byte-
    identical evaluations, because jitter is seeded per (worker_id, job_id)
    rather than drawn from global random state.
  - "llm_reasoning" is kept as the output key name (not renamed to e.g.
    "derivation_reasoning") only because compatibility_eval.schema.json /
    downstream code may still expect that key. If you control that schema,
    consider renaming it - it's no longer LLM-derived.

CAVEAT: the formulas below are a reasonable, documented heuristic (each term
maps to a specific comparison your schema already tracks - demand vs.
ability, task complexity vs. experience, fatigue vs. stamina), not a
validated ground truth. Calibrate the weights (see WEIGHTS below) against
the real garment-productivity / Indonesian fatigue-study data discussed
earlier before trusting these labels for anything beyond pipeline
validation.

run : python -m training.scripts.Training_sample_generator
"""

import json
import logging
import random
from pathlib import Path

from tqdm import tqdm

import torch

from training.scripts.factory_graph_utils import (
    ASSET_CATEGORY_VOCAB,
    ASSET_FEATURE_DIM,
    EDGE_LABEL_FIELDS,
    ERROR_SEVERITY_VOCAB,
    GENDER_VOCAB,
    JOB_FEATURE_DIM,
    PHYSICAL_DEMAND_VOCAB,
    VIBRATION_VOCAB,
    WORKER_FEATURE_DIM,
    build_hetero_graph,
    flatten_pair_items,
    load_input,
)

logger = logging.getLogger(__name__)

validation = True

CONFIG = {
    'INPUT_DIR': "./training/datasets/formatted/validation/onet_based_factories",
    'OUTPUT_DIR': "./training/datasets/formatted/validation/onet_based_gnn_training_data/",
    'GRAPH_OUTPUT_DIR': "./training/datasets/formatted/validation/onet_based_gnn_graphs/",
    'GRAPH_MANIFEST_FILE': "./training/datasets/formatted/validation/onet_based_graph_manifest/manifest.json",
    'MATRIX_OUTPUT_DIR': "./training/datasets/formatted/validation/onet_based_compatibility_matrices/",
    'SPLIT_RATIOS': {'train': 0.8, 'val': 0.1, 'test': 0.1},
    # how far individual pairs are allowed to drift from the formula's raw
    # output before clipping to _EVAL_BOUNDS - the "little differences" knob
    'JITTER': 0.05,
}

if validation == False:
    CONFIG = {
        'INPUT_DIR': "./training/datasets/formatted/train/onet_based_factories",
        'OUTPUT_DIR': "./training/datasets/formatted/train/onet_based_gnn_training_data/",
        'GRAPH_OUTPUT_DIR': "./training/datasets/formatted/train/onet_based_gnn_graphs/",
        'GRAPH_MANIFEST_FILE': "./training/datasets/formatted/train/onet_based_graph_manifest/manifest.json",
        'MATRIX_OUTPUT_DIR': "./training/datasets/formatted/train/onet_based_compatibility_matrices/",
        'SPLIT_RATIOS': {'train': 0.8, 'val': 0.1, 'test': 0.1},
        # how far individual pairs are allowed to drift from the formula's raw
        # output before clipping to _EVAL_BOUNDS - the "little differences" knob
        'JITTER': 0.05,
    }

# matches compatibility_eval.schema.json's evaluations.* bounds - same
# bounds the original LLM-based version validated against, now used to clip
# the formula's output instead of validating an LLM response
_EVAL_BOUNDS = {
    "overall_compatibility_score": (0.0, 1.0),
    "throughput_multiplier": (0.8, 1.2),
    "error_multiplier": (0.4, 1.5),
    "fatigue_accumulation_rate": (0.3, 1.5),
    "stress_sensitivity_factor": (0.4, 1.0),
}

# categorical -> numeric mappings for the formula below. Independent of
# factory_graph_utils's *_VOCAB constants (those are almost certainly
# one-hot index orderings for the GNN's feature tensors, not severity
# weights) - kept local and named so the mapping's intent is unambiguous.
_PHYSICAL_DEMAND_TO_SCORE = {"low": 0.25, "medium": 0.55, "high": 0.85}
_ERROR_SEVERITY_TO_SCORE = {"low": 0.20, "moderate": 0.45, "high": 0.70, "critical": 0.95}


def _clip(x: float, lo: float, hi: float) -> float:
    return round(min(max(x, lo), hi), 4)


def compute_deterministic_evaluation(worker: dict, job: dict, asset: dict, jitter: float) -> dict:
    """Closed-form worker-job compatibility evaluation. Every term is a gap
    between a job demand and a worker ability that's already in your schema
    - no free parameters beyond the WEIGHTS below, no LLM call, no network
    I/O. Returns the same {"evaluations": {...5 fields}, "llm_reasoning":
    str} shape the LLM path used to produce, so rebuild_output()/
    build_hetero_graph() need no changes downstream."""

    demo = worker.get("demographics", {}) or {}
    shift = worker.get("shift_context", {}) or {}
    demands = job.get("demands", {}) or {}
    env = (asset or {}).get("environmental_factors", {}) or {}

    stamina = float(demo.get("baseline_physical_stamina", 0.5))
    resilience = float(demo.get("cognitive_resilience", 0.5))
    experience_norm = min(float(demo.get("years_of_experience", 0)) / 15.0, 1.0)

    physical_demand_val = _PHYSICAL_DEMAND_TO_SCORE.get(demands.get("physical_demand_level"), 0.55)
    cognitive_focus_needed = float(demands.get("required_cognitive_focus", 0.5))
    task_complexity = float(demands.get("task_complexity", 0.5))
    error_severity_val = _ERROR_SEVERITY_TO_SCORE.get(demands.get("error_severity"), 0.45)

    hours_today = float(shift.get("hours_worked_today", 0.0))
    consecutive_shifts = float(shift.get("consecutive_shifts", 0))
    fatigue_load = min(hours_today / 12.0, 1.0) * 0.6 + min(consecutive_shifts / 6.0, 1.0) * 0.4

    env_strain = float(env.get("physical_strain_index", 0.3))
    noise_db = env.get("noise_level_db")
    noise_norm = _clip(((noise_db - 40) / 60.0) if noise_db is not None else 0.3, 0.0, 1.0)

    # positive gap = job demands more than the worker brings
    physical_gap = physical_demand_val - stamina
    cognitive_gap = cognitive_focus_needed - resilience
    complexity_gap = task_complexity - experience_norm

    # deterministic per-pair jitter (NOT global random state) - reruns on
    # the same worker/job pair always produce the same number
    rng = random.Random(f"{worker.get('worker_id')}|{job.get('job_id')}")

    def j(x: float) -> float:
        return x + rng.uniform(-jitter, jitter)

    overall = _clip(
        j(1.0 - 0.45 * max(physical_gap, 0) - 0.35 * max(cognitive_gap, 0) - 0.20 * max(complexity_gap, 0)),
        *_EVAL_BOUNDS["overall_compatibility_score"],
    )
    throughput = _clip(
        j(1.0 + 0.20 * (stamina - physical_demand_val) + 0.10 * (experience_norm - task_complexity)
          - 0.05 * fatigue_load),
        *_EVAL_BOUNDS["throughput_multiplier"],
    )
    error_mult = _clip(
        j(1.0 + error_severity_val * (0.5 * max(cognitive_gap, 0) + 0.5 * max(complexity_gap, 0))
          + 0.15 * fatigue_load),
        *_EVAL_BOUNDS["error_multiplier"],
    )
    fatigue_rate = _clip(
        j(0.3 + 0.5 * fatigue_load + 0.3 * env_strain - 0.25 * stamina),
        *_EVAL_BOUNDS["fatigue_accumulation_rate"],
    )
    stress = _clip(
        j(0.4 + 0.30 * max(cognitive_gap, 0) + 0.20 * error_severity_val + 0.10 * noise_norm),
        *_EVAL_BOUNDS["stress_sensitivity_factor"],
    )

    reasoning = (
        f"Deterministic formula (no LLM): physical_gap={physical_gap:.2f} "
        f"(demand={physical_demand_val:.2f} vs stamina={stamina:.2f}), "
        f"cognitive_gap={cognitive_gap:.2f} (focus_needed={cognitive_focus_needed:.2f} vs "
        f"resilience={resilience:.2f}), complexity_gap={complexity_gap:.2f} "
        f"(task={task_complexity:.2f} vs experience_norm={experience_norm:.2f}), "
        f"fatigue_load={fatigue_load:.2f}, env_strain={env_strain:.2f}, noise_norm={noise_norm:.2f}, "
        f"error_severity_weight={error_severity_val:.2f}; +/-{jitter} jitter seeded per pair."
    )

    values = {
        "overall_compatibility_score": overall,
        "throughput_multiplier": throughput,
        "error_multiplier": error_mult,
        "fatigue_accumulation_rate": fatigue_rate,
        "stress_sensitivity_factor": stress,
    }
    return {
        "evaluations": {field: values[field] for field in EDGE_LABEL_FIELDS},
        "llm_reasoning": reasoning,  # key name kept for schema/downstream compatibility - see module docstring
    }


# --------------------------------------------------------------------------
# Compatibility matrix (compatibility_matrix.schema.json) - previously not
# produced at all; Training_sample_generator only wrote the flat
# 'synthetic_compatibility_evaluations' list. This builds the nested
# per-worker -> per-job matrix the schema describes, from that same flat
# evaluations list, so nothing about compute_deterministic_evaluation or the
# graph-building step needs to change.
# --------------------------------------------------------------------------

def build_compatibility_matrix(doc: dict, evaluations: list, failed_pairs: list) -> dict | None:
    """Returns a dict validating against compatibility_matrix.schema.json,
    or None if there are zero evaluations (schema requires
    compatibility_matrix to have minProperties: 1, so an empty matrix can't
    be written)."""
    if not evaluations:
        return None

    from datetime import datetime, timezone

    workers_by_id = {w["worker_id"]: w for w in doc.get("workers", [])}
    jobs_by_id = {j["job_id"]: j for j in doc.get("job_descriptions", [])}
    # jobs carry stage_id (post schema-fix), not a free-text step name - resolve
    # the human-readable step name via process_stages for the matrix's display field
    stage_name_by_id = {s["stage_id"]: s["stage_name"] for s in doc.get("process_stages", [])}

    matrix = {}
    best_scores = {}
    for ev in evaluations:
        worker_id, job_id = ev["worker_id"], ev["job_id"]
        worker = workers_by_id.get(worker_id, {})
        job = jobs_by_id.get(job_id, {})

        entry = matrix.setdefault(worker_id, {
            "worker_name": worker.get("name", worker_id),
            "best_job_id": job_id,
            "jobs": {},
        })
        entry["jobs"][job_id] = {
            "job_title": job.get("job_title", ""),
            "workflow_step": stage_name_by_id.get(job.get("stage_id"), job.get("stage_id", "")),
            "asset_id": ev["asset_id"],
            "attempts": 1,  # deterministic formula - always resolves in one pass, no retries
            "evaluations": ev["evaluations"],
            "llm_reasoning": ev["llm_reasoning"],
        }

        score = ev["evaluations"]["overall_compatibility_score"]
        if score > best_scores.get(worker_id, -1.0):
            best_scores[worker_id] = score
            entry["best_job_id"] = job_id

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "worker_count": len(workers_by_id),
        "job_count": len(jobs_by_id),
        "pair_count": len(evaluations) + len(failed_pairs),
        "evaluated_pairs": len(evaluations),
        "retries": 0,  # no LLM call to retry
        "failed_pairs": failed_pairs,
    }
    return {"meta": meta, "compatibility_matrix": matrix}


# --------------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------------

def get_output_path(input_path: Path) -> Path:
    return Path(CONFIG['OUTPUT_DIR']) / (input_path.stem + ".json")


def get_graph_output_path(input_path: Path) -> Path:
    return Path(CONFIG['GRAPH_OUTPUT_DIR']) / (input_path.stem + ".pt")


def get_matrix_output_path(input_path: Path) -> Path:
    return Path(CONFIG['MATRIX_OUTPUT_DIR']) / (input_path.stem + ".json")


# --------------------------------------------------------------------------
# Per-file processing (sync - no network call means no need for
# asyncio/retries/checkpointing; a full 101-factory run is CPU-only and fast)
# --------------------------------------------------------------------------

def process_file(filepath: Path) -> dict:
    doc = load_input(filepath)
    content_items = flatten_pair_items(doc)  # (worker_id, job_id, asset_id, prompt_text) - prompt_text unused now

    workers_by_id = {w["worker_id"]: w for w in doc.get("workers", [])}
    jobs_by_id = {j["job_id"]: j for j in doc.get("job_descriptions", [])}
    assets_by_id = {a["asset_id"]: a for a in doc.get("assets", [])}

    evaluations = []
    failed_pairs = []  # compatibility_matrix.schema.json shape: [{worker_id, job_id, error}]
    for worker_id, job_id, asset_id, _prompt_text in content_items:
        worker = workers_by_id.get(worker_id)
        job = jobs_by_id.get(job_id)
        asset = assets_by_id.get(asset_id)
        if worker is None or job is None:
            error = f"missing {'worker' if worker is None else 'job'} record"
            failed_pairs.append({"worker_id": worker_id, "job_id": job_id, "error": error})
            logger.warning(f"{filepath.name}: pair (worker={worker_id}, job={job_id}) {error} - skipped.")
            continue

        result = compute_deterministic_evaluation(worker, job, asset, jitter=CONFIG['JITTER'])
        evaluations.append({
            "worker_id": worker_id,
            "job_id": job_id,
            "asset_id": asset_id,
            "evaluations": result["evaluations"],
            "llm_reasoning": result["llm_reasoning"],
        })

    if failed_pairs:
        logger.warning(f"{filepath.name}: skipped {len(failed_pairs)} pair(s) with missing worker/job records")

    doc['synthetic_compatibility_evaluations'] = evaluations

    out_path = get_output_path(filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    matrix = build_compatibility_matrix(doc, evaluations, failed_pairs)
    matrix_path = None
    if matrix is not None:
        matrix_path = get_matrix_output_path(filepath)
        matrix_path.parent.mkdir(parents=True, exist_ok=True)
        matrix_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        logger.warning(f"{filepath.name}: zero evaluations - compatibility matrix not written "
                        f"(schema requires at least one worker entry)")

    graph_data, edges_skipped = build_hetero_graph(doc, evaluations)
    graph_path = get_graph_output_path(filepath)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(graph_data, graph_path)

    return {
        "filename": filepath.name,
        "factory_id": doc.get('factory_info', {}).get('factory_id', 'unknown'),
        "graph_path": str(graph_path),
        "matrix_path": str(matrix_path) if matrix_path else None,
        "split": graph_data['split'],
        "num_workers": graph_data['worker'].x.size(0),
        "num_jobs": graph_data['job'].x.size(0),
        "num_assets": graph_data['asset'].x.size(0),
        "num_compatibility_edges": graph_data['worker', 'compatible_with', 'job'].edge_index.size(1),
        "edges_skipped": edges_skipped,
    }


# --------------------------------------------------------------------------
# Manifest (unchanged shape from the LLM version, so GNN_train.py /
# GNN_cross_validation.py need no changes)
# --------------------------------------------------------------------------

def write_manifest(entries_by_filename: dict):
    manifest_path = Path(CONFIG['GRAPH_MANIFEST_FILE'])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    graphs = sorted(entries_by_filename.values(), key=lambda e: e['filename'])
    manifest = {
        "feature_dims": {
            "worker": WORKER_FEATURE_DIM,
            "job": JOB_FEATURE_DIM,
            "asset": ASSET_FEATURE_DIM,
        },
        "edge_label_fields": EDGE_LABEL_FIELDS,
        "vocabularies": {
            "gender": GENDER_VOCAB,
            "physical_demand_level": PHYSICAL_DEMAND_VOCAB,
            "error_severity": ERROR_SEVERITY_VOCAB,
            "vibration_hazard_level": VIBRATION_VOCAB,
            "asset_category": ASSET_CATEGORY_VOCAB,
        },
        "split_ratios": CONFIG['SPLIT_RATIOS'],
        "generation_method": "deterministic_onet_formula",  # was "llm" in the original pipeline
        "num_graphs": len(graphs),
        "graphs": graphs,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def run_pipeline():
    import os
    os.makedirs(CONFIG['OUTPUT_DIR'], exist_ok=True)
    os.makedirs(CONFIG['GRAPH_OUTPUT_DIR'], exist_ok=True)

    input_files = sorted(Path(CONFIG['INPUT_DIR']).glob("*.json"))
    if not input_files:
        print(f"No input files found under {CONFIG['INPUT_DIR']}")
        return

    manifest_entries = {}
    failed = []
    for filepath in tqdm(input_files, desc="Factories", unit="file"):
        try:
            manifest_entries[filepath.name] = process_file(filepath)
        except Exception as e:
            logger.exception(f"{filepath.name} failed")
            failed.append((filepath.name, str(e)))

    write_manifest(manifest_entries)

    print(f"\nDone. {len(manifest_entries)}/{len(input_files)} factories processed.")
    print(f"Graph manifest: {CONFIG['GRAPH_MANIFEST_FILE']} ({len(manifest_entries)} graph(s))")
    if failed:
        print(f"{len(failed)} file(s) failed:")
        for name, err in failed:
            print(f"  {name}: {err}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_pipeline()

    # run : python -m training.scripts.Training_sample_generator