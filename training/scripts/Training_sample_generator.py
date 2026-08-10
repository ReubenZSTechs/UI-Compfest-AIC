import asyncio
import aiofiles
import hashlib
import json
import math
import re
import logging
import os
import sys

from asyncio import Semaphore
from collections import defaultdict
from pathlib import Path
from tqdm import tqdm

import torch
from torch_geometric.data import HeteroData

# backend/app/services/agent_registry_service.py imports `app.core...` as if
# backend/ itself were on sys.path (not just the project root), so add it
# here - otherwise `python -m training.scripts.Training_sample_generator`
# from the project root fails with `ModuleNotFoundError: No module named 'app'`
_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.app.services.agent_registry_service import get_agent, AgentRole
from backend.app.services.call_llm_service import Agent

logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: str) -> str:
    text = _THINK_BLOCK_RE.sub("", text)
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


CONFIG = {
    'INPUT_DIR': "./training/datasets/formatted/syntetic_factories",
    'OUTPUT_DIR': "./training/datasets/formatted/syntetic_gnn_training_data/",
    'STAGING_DIR': "./training/datasets/formatted/staging_gnn_training_data/",
    'CHECKPOINT_FILE': "./training/datasets/formatted/checkpoints/checkpoint_gnn_training_data.jsonl",
    'AGENT_ROLE': "gnn_training_data_generator",
    'MAX_PARALLEL_FILES': 2,
    'RETRIES': 3,
    'RETRY_DELAY': 1.0,
    'CHECKPOINT_INTERVAL': 1,
    'GRAPH_OUTPUT_DIR': "./training/datasets/formatted/syntetic_gnn_graphs/",
    'GRAPH_MANIFEST_FILE': "./training/datasets/formatted/syntetic_graph_manifest/manifest.json",
    'SPLIT_RATIOS': {'train': 0.8, 'val': 0.1, 'test': 0.1},
}


# --------------------------------------------------------------------------
# Helpers for reading input + building/splitting the worker x job_desk pairs
# --------------------------------------------------------------------------

def read_text_robust(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def load_input(path: Path) -> dict:
    """Load one factory digital twin JSON: {factory_info, assets, job_desks, workers, ...}"""
    return json.loads(read_text_robust(path))


def get_output_path(input_path: Path) -> Path:
    return Path(CONFIG['OUTPUT_DIR']) / (input_path.stem + ".json")


def get_staging_path(input_path: Path) -> Path:
    return Path(CONFIG['STAGING_DIR']) / (input_path.stem + ".jsonl")


def get_graph_output_path(input_path: Path) -> Path:
    return Path(CONFIG['GRAPH_OUTPUT_DIR']) / (input_path.stem + ".pt")


# --------------------------------------------------------------------------
# Pair construction: every (worker, job_desk) combination is a candidate
# compatibility edge to synthetically evaluate, not just the ones that
# actually occurred on the factory floor.
# --------------------------------------------------------------------------

def build_pair_prompt(worker: dict, job: dict, asset: dict) -> str:
    """Serialize one worker + one job_desk + its asset into the compact
    JSON block fed to the LLM as the basis for one compatibility evaluation."""
    payload = {
        "worker": {
            "worker_id": worker["worker_id"],
            "demographics": worker["demographics"],
            "shift_context": worker["shift_context"],
        },
        "job": {
            "job_id": job["job_id"],
            "job_title": job["job_title"],
            "demands": job["demands"],
        },
        "asset": {
            "asset_id": asset["asset_id"],
            "asset_name": asset["asset_name"],
            "is_automated": asset["is_automated"],
            "environmental_factors": asset["environmental_factors"],
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def flatten_pair_items(doc: dict):
    """
    Walk doc['workers'] x get_jobs(doc) (job_descriptions, falling back to
    the older job_desks key) in stable order and return a flat list of
    (worker_id, job_id, asset_id, prompt_text) tuples, one entry per
    worker-job combination whose compatibility should be synthetically
    evaluated. Pairs whose job points at a missing asset are skipped.
    """
    items = []
    assets_by_id = {a['asset_id']: a for a in doc.get('assets', [])}
    for worker in doc.get('workers', []):
        for job in get_jobs(doc):
            asset = assets_by_id.get(job.get('assigned_asset_id'))
            if asset is None:
                continue
            prompt_text = build_pair_prompt(worker, job, asset)
            items.append((worker['worker_id'], job['job_id'], job['assigned_asset_id'], prompt_text))
    return items


def count_processable_items(path: Path):
    try:
        doc = load_input(path)
    except Exception:
        return None
    return len(flatten_pair_items(doc))


def get_jobs(doc: dict):
    """job_descriptions per factory_md.schema.json; some digital-twin files
    were produced under an older key name, so fall back to job_desks."""
    return doc.get('job_descriptions', doc.get('job_desks', []))


# --------------------------------------------------------------------------
# GNN graph construction: turn one factory digital twin + its LLM-evaluated
# worker x job pairs into a heterogeneous PyG graph.
#
#   node types : worker, job, asset
#   edge types : (job, uses_asset, asset)          structural, from job_descriptions
#                (asset, rev_uses_asset, job)       reverse, structural
#                (worker, compatible_with, job)     LABELED - edge_attr is the
#                                                    5-dim LLM evaluation vector
#                (job, rev_compatible_with, worker) reverse, structural only
#                                                    (no edge_attr - avoids
#                                                    leaking the label back in
#                                                    as a message-passing input)
#
# Categorical vocabularies are hardcoded from the schema enums rather than
# fit per-file, so every factory's graph uses the same feature layout and
# dimensionality - required for batching graphs from different factories
# into one GNN training run.
# --------------------------------------------------------------------------

GENDER_VOCAB = ["male", "female", "unspecified"]
PHYSICAL_DEMAND_VOCAB = ["low", "medium", "high"]
ERROR_SEVERITY_VOCAB = ["low", "moderate", "high", "critical"]
VIBRATION_VOCAB = ["low", "medium", "high"]
ASSET_CATEGORY_VOCAB = [
    "machine", "measuring_equipment", "conveyor_automation",
    "environmental_chamber", "manual_station",
]

# feature vector layout, fixed and documented so the GNN model definition
# can hardcode its input dims rather than introspecting graphs at train time
WORKER_FEATURE_DIM = 1 + len(GENDER_VOCAB) + 1 + 1 + 1 + 1 + 1  # = 9
JOB_FEATURE_DIM = 1 + len(PHYSICAL_DEMAND_VOCAB) + 1 + len(ERROR_SEVERITY_VOCAB)  # = 9
ASSET_FEATURE_DIM = len(ASSET_CATEGORY_VOCAB) + 1 + 1 + 1 + 1 + 1 + len(VIBRATION_VOCAB) + 1  # = 14
EDGE_LABEL_FIELDS = [
    "overall_compatibility_score",
    "throughput_multiplier",
    "error_multiplier",
    "fatigue_accumulation_rate",
    "stress_sensitivity_factor",
]


def _one_hot(value, vocab):
    vec = [0.0] * len(vocab)
    if value in vocab:
        vec[vocab.index(value)] = 1.0
    else:
        logger.warning(f"Value {value!r} not in vocab {vocab}; leaving one-hot all-zero.")
    return vec


def _minmax(val, lo, hi):
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))


def _log_scale(val, cap):
    val = max(0.0, float(val))
    return min(1.0, math.log1p(val) / math.log1p(cap))


def worker_features(w: dict) -> list:
    demo = w['demographics']
    shift = w['shift_context']
    feats = [_minmax(demo['age'], 16, 75)]
    feats += _one_hot(demo['gender'], GENDER_VOCAB)
    feats += [min(demo['years_of_experience'], 50) / 50.0]
    feats += [demo['baseline_physical_stamina']]
    feats += [demo['cognitive_resilience']]
    feats += [_minmax(shift['hours_worked_today'], 0, 24)]
    feats += [min(shift['consecutive_shifts'], 14) / 14.0]
    assert len(feats) == WORKER_FEATURE_DIM
    return feats


def job_features(j: dict) -> list:
    d = j['demands']
    feats = [d['required_cognitive_focus']]
    feats += _one_hot(d['physical_demand_level'], PHYSICAL_DEMAND_VOCAB)
    feats += [d['task_complexity']]
    feats += _one_hot(d['error_severity'], ERROR_SEVERITY_VOCAB)
    assert len(feats) == JOB_FEATURE_DIM
    return feats


def asset_features(a: dict) -> list:
    ef = a['environmental_factors']
    feats = _one_hot(a['category'], ASSET_CATEGORY_VOCAB)
    feats += [1.0 if a['is_automated'] else 0.0]
    feats += [_log_scale(a['units_available'], 100)]
    feats += [_log_scale(a['base_throughput_capacity'], 1000)]
    feats += [_log_scale(a['operational_cost_per_hour'], 1000)]
    feats += [_minmax(ef['noise_level_db'], 30, 95)]
    feats += _one_hot(ef['vibration_hazard_level'], VIBRATION_VOCAB)
    feats += [ef['physical_strain_index']]
    assert len(feats) == ASSET_FEATURE_DIM
    return feats


def assign_split(factory_id: str) -> str:
    """Deterministic train/val/test assignment keyed on factory_id, so the
    same factory always lands in the same split across re-runs."""
    digest = hashlib.sha256(factory_id.encode('utf-8')).hexdigest()
    frac = (int(digest[:8], 16) % 10_000) / 10_000
    cum = 0.0
    for split_name, ratio in CONFIG['SPLIT_RATIOS'].items():
        cum += ratio
        if frac < cum:
            return split_name
    return 'train'


def build_hetero_graph(doc: dict, evaluations: list) -> tuple:
    """Build one HeteroData graph for a factory from its digital twin doc
    and the list of {worker_id, job_id, asset_id, evaluations, llm_reasoning}
    records produced by rebuild_output(). Returns (data, n_edges_skipped)."""
    factory_id = doc.get('factory_info', {}).get('factory_id', 'unknown')
    workers = doc.get('workers', [])
    jobs = get_jobs(doc)
    assets = doc.get('assets', [])

    worker_idx = {w['worker_id']: i for i, w in enumerate(workers)}
    job_idx = {j['job_id']: i for i, j in enumerate(jobs)}
    asset_idx = {a['asset_id']: i for i, a in enumerate(assets)}

    data = HeteroData()

    data['worker'].x = torch.tensor([worker_features(w) for w in workers], dtype=torch.float) \
        if workers else torch.empty((0, WORKER_FEATURE_DIM), dtype=torch.float)
    data['worker'].node_id = [w['worker_id'] for w in workers]

    data['job'].x = torch.tensor([job_features(j) for j in jobs], dtype=torch.float) \
        if jobs else torch.empty((0, JOB_FEATURE_DIM), dtype=torch.float)
    data['job'].node_id = [j['job_id'] for j in jobs]

    data['asset'].x = torch.tensor([asset_features(a) for a in assets], dtype=torch.float) \
        if assets else torch.empty((0, ASSET_FEATURE_DIM), dtype=torch.float)
    data['asset'].node_id = [a['asset_id'] for a in assets]

    # structural job -> asset edges (which physical asset each job runs on)
    ja_src, ja_dst = [], []
    for j in jobs:
        aid = j.get('assigned_asset_id')
        if aid in asset_idx and j['job_id'] in job_idx:
            ja_src.append(job_idx[j['job_id']])
            ja_dst.append(asset_idx[aid])
    data['job', 'uses_asset', 'asset'].edge_index = (
        torch.tensor([ja_src, ja_dst], dtype=torch.long) if ja_src
        else torch.empty((2, 0), dtype=torch.long)
    )
    data['asset', 'rev_uses_asset', 'job'].edge_index = (
        torch.tensor([ja_dst, ja_src], dtype=torch.long) if ja_src
        else torch.empty((2, 0), dtype=torch.long)
    )

    # labeled worker -> job compatibility edges (the GNN training targets)
    src, dst, edge_attr = [], [], []
    skipped = 0
    for ev in evaluations:
        wid, jid = ev['worker_id'], ev['job_id']
        if wid not in worker_idx or jid not in job_idx:
            skipped += 1
            continue
        e = ev['evaluations']
        if any(field not in e for field in EDGE_LABEL_FIELDS):
            skipped += 1
            continue
        src.append(worker_idx[wid])
        dst.append(job_idx[jid])
        edge_attr.append([e[field] for field in EDGE_LABEL_FIELDS])

    data['worker', 'compatible_with', 'job'].edge_index = (
        torch.tensor([src, dst], dtype=torch.long) if src
        else torch.empty((2, 0), dtype=torch.long)
    )
    data['worker', 'compatible_with', 'job'].edge_attr = (
        torch.tensor(edge_attr, dtype=torch.float) if edge_attr
        else torch.empty((0, len(EDGE_LABEL_FIELDS)), dtype=torch.float)
    )
    data['job', 'rev_compatible_with', 'worker'].edge_index = (
        torch.tensor([dst, src], dtype=torch.long) if src
        else torch.empty((2, 0), dtype=torch.long)
    )

    data['factory_id'] = factory_id
    data['split'] = assign_split(factory_id)

    return data, skipped


# --------------------------------------------------------------------------
# Async checkpoint manager (file-level progress, unchanged from before)
# --------------------------------------------------------------------------

class CheckpointManager:
    def __init__(self, checkpoint_filepath: Path):
        self.checkpoint_filepath = checkpoint_filepath
        self._lock = asyncio.Lock()
        self._state = {}  # dict[filename, dict]

    async def load(self):
        if not self.checkpoint_filepath.exists():
            return
        async with aiofiles.open(self.checkpoint_filepath, "r", encoding="utf-8") as f:
            async for line in f:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    self._state[record['filename']] = record
        logger.info(f"Loaded checkpoints for {len(self._state)} file(s)")

    def get_chunk_idx(self, filename: str) -> int:
        return self._state.get(filename, {}).get('curr_idx', 0)

    def is_completed(self, filename: str) -> bool:
        return self._state.get(filename, {}).get('status') == 'completed'

    def completed_files(self) -> set:
        return {fn for fn, rec in self._state.items() if rec.get('status') == 'completed'}

    async def _dump_record(self):
        tmp_path = self.checkpoint_filepath.with_suffix(".tmp")
        self.checkpoint_filepath.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
            for record in self._state.values():
                await f.write(json.dumps(record, ensure_ascii=False) + "\n")
        tmp_path.replace(self.checkpoint_filepath)

    async def save_progress(self, filename: str, curr_idx: int):
        async with self._lock:
            self._state[filename] = {
                'filename': filename,
                'curr_idx': curr_idx,
                'status': 'in_progress'
            }
            await self._dump_record()

    async def mark_completed(self, filename: str):
        async with self._lock:
            self._state[filename] = {
                'filename': filename,
                'curr_idx': -1,
                'status': 'completed'
            }
            await self._dump_record()


# --------------------------------------------------------------------------
# LLM call with retries, run in a thread executor (agent client is sync)
# --------------------------------------------------------------------------

async def process_with_retry(agent: Agent, text: str, max_retries: int, retry_delay: float):
    """gnn_compatibility_generator_agent.yaml has structured_output.enabled=true
    against compatibility_eval.schema.json, so this route must call
    .generate_structured() (grammar-constrained JSON decoding), not
    .generate_process_response() (freeform text) - calling the wrong method
    is why previous runs never produced usable evaluations even once real
    pairs were flowing through. Returns the raw structured result (dict, or
    occasionally a JSON string depending on the client) on success, None if
    every retry was exhausted."""
    loop = asyncio.get_event_loop()
    for attempt in range(max_retries):
        try:
            result = await loop.run_in_executor(
                None,
                lambda: agent.generate_structured(user_prompt=text)
            )
            if result:
                return result
        except Exception as e:
            logger.warning(f"Process attempt {attempt + 1}/{max_retries} failed: {e}")
        await asyncio.sleep(retry_delay * (attempt + 1))
    return None


# --------------------------------------------------------------------------
# Defensive validation of the model's structured compatibility-evaluation
# output. generate_structured() with strict:true should already return
# schema-valid output, but this is a second layer of defense: one malformed
# pair should be dropped and logged, never silently corrupt the graph.
# --------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

# top-level shape of compatibility_eval.schema.json: {"evaluations": {...5
# numeric fields...}, "llm_reasoning": str} - NOT a flat 6-key object
_REQUIRED_EVAL_TOP_FIELDS = ["evaluations", "llm_reasoning"]

# matches compatibility_eval.schema.json's evaluations.* bounds
_EVAL_BOUNDS = {
    "overall_compatibility_score": (0.0, 1.0),
    "throughput_multiplier": (0.8, 1.2),
    "error_multiplier": (0.4, 1.5),
    "fatigue_accumulation_rate": (0.3, 1.5),
    "stress_sensitivity_factor": (0.4, 1.0),
}


def parse_structured_evaluation(result):
    """Normalize + validate one agent response against compatibility_eval.schema.json's
    real shape: {"evaluations": {overall_compatibility_score, throughput_multiplier,
    error_multiplier, fatigue_accumulation_rate, stress_sensitivity_factor},
    "llm_reasoning": str}. Returns {"evaluations": {...5 fields...}, "llm_reasoning": str}
    on success, or None (logging why) on any validation failure."""
    if result is None:
        return None

    # generate_structured() should hand back a dict already, but normalize a
    # couple of other plausible return shapes defensively rather than assume
    if isinstance(result, str):
        cleaned = _JSON_FENCE_RE.sub("", strip_thinking(result)).strip()
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse structured output as JSON. Raw (truncated): {cleaned[:200]!r}")
            return None
    elif hasattr(result, "model_dump"):
        result = result.model_dump()

    if not isinstance(result, dict):
        logger.warning(f"Structured output was not a dict/JSON object: {type(result)!r}; skipping.")
        return None

    missing = [f for f in _REQUIRED_EVAL_TOP_FIELDS if f not in result]
    if missing:
        logger.warning(f"Structured output missing top-level field(s) {missing}; skipping. "
                        f"Got keys: {list(result.keys())}")
        return None

    evaluations = result["evaluations"]
    if not isinstance(evaluations, dict):
        logger.warning("Structured output 'evaluations' was not an object; skipping.")
        return None

    missing_metrics = [f for f in EDGE_LABEL_FIELDS if f not in evaluations]
    if missing_metrics:
        logger.warning(f"Structured output 'evaluations' missing field(s) {missing_metrics}; skipping.")
        return None

    for field, (lo, hi) in _EVAL_BOUNDS.items():
        val = evaluations.get(field)
        if not isinstance(val, (int, float)) or not (lo <= val <= hi):
            logger.warning(f"Evaluation field '{field}'={val!r} out of bounds [{lo}, {hi}]; skipping.")
            return None

    llm_reasoning = result.get("llm_reasoning")
    if not isinstance(llm_reasoning, str) or not llm_reasoning.strip():
        logger.warning("Structured output 'llm_reasoning' missing/empty; skipping.")
        return None

    return {
        "evaluations": {field: evaluations[field] for field in EDGE_LABEL_FIELDS},
        "llm_reasoning": llm_reasoning,
    }


# --------------------------------------------------------------------------
# Per-file worker
# --------------------------------------------------------------------------

async def process_file(filepath: Path, agent: Agent, checkpoint_manager: CheckpointManager,
                        semaphore: Semaphore, file_pbar: tqdm):
    filename = filepath.name

    if checkpoint_manager.is_completed(filename):
        logger.info(f"Skipping {filename} - completed")
        file_pbar.update(1)
        # graph .pt file was already written on the run that completed this
        # file; nothing new to report in the manifest
        return filename, True, None, None

    async with semaphore:
        try:
            doc = load_input(filepath)
            content_items = flatten_pair_items(doc)

            if not content_items:
                # no evaluable worker/job pairs (e.g. no assets matched) -
                # still emit an (edge-less) graph so downstream loaders don't
                # have to special-case a missing file for this factory
                graph_data, _ = build_hetero_graph(doc, [])
                graph_path = get_graph_output_path(filepath)
                graph_path.parent.mkdir(parents=True, exist_ok=True)
                torch.save(graph_data, graph_path)

                await checkpoint_manager.mark_completed(filename)
                file_pbar.update(1)
                graph_meta = {
                    "filename": filename,
                    "factory_id": doc.get('factory_info', {}).get('factory_id', 'unknown'),
                    "graph_path": str(graph_path),
                    "split": graph_data['split'],
                    "num_workers": graph_data['worker'].x.size(0),
                    "num_jobs": graph_data['job'].x.size(0),
                    "num_assets": graph_data['asset'].x.size(0),
                    "num_compatibility_edges": 0,
                    "edges_skipped": 0,
                }
                return filename, True, None, graph_meta

            start_pos = checkpoint_manager.get_chunk_idx(filename)
            staging_path = get_staging_path(filepath)
            staging_path.parent.mkdir(parents=True, exist_ok=True)

            chunk_pbar = tqdm(
                total=len(content_items),
                initial=start_pos,
                desc=f"  {filename}",
                unit="pair",
                leave=False,
            )

            # append mode: resuming a partially-done file just picks up
            # writing further lines onto the existing staging jsonl
            try:
                async with aiofiles.open(staging_path, "a", encoding="utf-8") as f:
                    for pos in range(start_pos, len(content_items)):
                        worker_id, job_id, asset_id, prompt_text = content_items[pos]

                        processed_result = await process_with_retry(
                            agent, prompt_text, CONFIG['RETRIES'], CONFIG['RETRY_DELAY']
                        )
                        if processed_result is None:
                            # all retries exhausted with no response (e.g. timeouts) —
                            # raise instead of silently recording an empty result and
                            # advancing the checkpoint past this pair. The file
                            # will be retried from this exact pair on next run.
                            raise RuntimeError(
                                f"Pair (worker={worker_id}, job={job_id}) in {filename} produced no "
                                f"response after {CONFIG['RETRIES']} retries"
                            )
                        evaluation = parse_structured_evaluation(processed_result)

                        record = {
                            "worker_id": worker_id,
                            "job_id": job_id,
                            "asset_id": asset_id,
                            "evaluation_raw": processed_result if isinstance(processed_result, (dict, list))
                                               else str(processed_result),
                            "evaluation": evaluation,
                        }
                        await f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        await f.flush()

                        if (pos + 1) % CONFIG['CHECKPOINT_INTERVAL'] == 0 or (pos + 1) == len(content_items):
                            await checkpoint_manager.save_progress(filename, pos + 1)

                        chunk_pbar.update(1)
            finally:
                # always close the bar, even if a pair above raised
                chunk_pbar.close()

            # rebuild the full document now that every pair has been evaluated
            evaluations = await rebuild_output(doc, staging_path, get_output_path(filepath))

            # build and save this factory's heterogeneous GNN graph
            graph_data, edges_skipped = build_hetero_graph(doc, evaluations)
            graph_path = get_graph_output_path(filepath)
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(graph_data, graph_path)

            graph_meta = {
                "filename": filename,
                "factory_id": doc.get('factory_info', {}).get('factory_id', 'unknown'),
                "graph_path": str(graph_path),
                "split": graph_data['split'],
                "num_workers": graph_data['worker'].x.size(0),
                "num_jobs": graph_data['job'].x.size(0),
                "num_assets": graph_data['asset'].x.size(0),
                "num_compatibility_edges": graph_data['worker', 'compatible_with', 'job'].edge_index.size(1),
                "edges_skipped": edges_skipped,
            }

            await checkpoint_manager.mark_completed(filename)
            file_pbar.update(1)
            logger.info(f"{filename} completed")
            return filename, True, None, graph_meta

        except Exception as e:
            file_pbar.update(1)
            return filename, False, str(e), None


async def rebuild_output(doc: dict, staging_path: Path, out_path: Path):
    """
    Read the staged per-pair results back and add a top-level
    'synthetic_compatibility_evaluations' array to the original factory
    document, same shape as init_state.json's llm_compatibility_and_evaluations
    (worker_id, job_id, asset_id, evaluations{...}, llm_reasoning), so it can
    be pooled directly into GNN training data alongside the real evaluations.
    Pairs where parsing/validation failed (evaluation is None) are dropped,
    with a count logged for visibility.
    """
    records = []
    async with aiofiles.open(staging_path, "r", encoding="utf-8") as f:
        async for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    evaluations = []
    skipped = 0
    for rec in records:
        evaluation = rec.get('evaluation')
        if evaluation is None:
            skipped += 1
            continue
        evaluations.append({
            "worker_id": rec['worker_id'],
            "job_id": rec['job_id'],
            "asset_id": rec['asset_id'],
            "evaluations": evaluation['evaluations'],
            "llm_reasoning": evaluation['llm_reasoning'],
        })

    if skipped:
        logger.warning(f"{staging_path.stem}: dropped {skipped} pair(s) with invalid/unparseable evaluations")

    doc['synthetic_compatibility_evaluations'] = evaluations

    out_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(out_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(doc, ensure_ascii=False, indent=2))

    return evaluations


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def load_existing_manifest() -> dict:
    """Manifest entries keyed by filename, so re-runs can merge in newly
    produced graphs without losing entries from files completed earlier."""
    manifest_path = Path(CONFIG['GRAPH_MANIFEST_FILE'])
    if not manifest_path.exists():
        return {}
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {entry['filename']: entry for entry in raw.get('graphs', [])}
    except Exception:
        logger.warning("Could not parse existing graph manifest; starting fresh.")
        return {}


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
        "num_graphs": len(graphs),
        "graphs": graphs,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


async def run_pipeline(max_parallel_files: int = None):
    os.makedirs(CONFIG['OUTPUT_DIR'], exist_ok=True)
    os.makedirs(CONFIG['STAGING_DIR'], exist_ok=True)
    os.makedirs(CONFIG['GRAPH_OUTPUT_DIR'], exist_ok=True)

    all_input_files = sorted(Path(CONFIG['INPUT_DIR']).glob("*.json"))

    checkpoint_manager = CheckpointManager(Path(CONFIG['CHECKPOINT_FILE']))
    await checkpoint_manager.load()

    manifest_entries = load_existing_manifest()

    completed_files = checkpoint_manager.completed_files()
    input_files = [fp for fp in all_input_files if fp.name not in completed_files]

    if not input_files:
        print("Nothing to do — all files already processed.")
        write_manifest(manifest_entries)
        return

    process_agent = get_agent(AgentRole(CONFIG['AGENT_ROLE']))
    semaphore = Semaphore(max_parallel_files or CONFIG['MAX_PARALLEL_FILES'])

    file_pbar = tqdm(total=len(input_files), desc="Files", unit="file", position=0)

    tasks = [
        process_file(fp, process_agent, checkpoint_manager, semaphore, file_pbar)
        for fp in input_files
    ]

    results = await asyncio.gather(*tasks)
    file_pbar.close()

    failed = [name for name, success, err, _ in results if not success]
    for name, success, err, graph_meta in results:
        if not success:
            tqdm.write(f"FAILED -> {name}: {err}")
        elif graph_meta is not None:
            manifest_entries[graph_meta['filename']] = graph_meta

    write_manifest(manifest_entries)

    print(f"\nDone. {len(checkpoint_manager.completed_files())}/{len(all_input_files)} total completed.")
    print(f"Graph manifest: {CONFIG['GRAPH_MANIFEST_FILE']} ({len(manifest_entries)} graph(s))")
    if failed:
        print(f"{len(failed)} file(s) failed: {failed}")


if __name__ == "__main__":
    asyncio.run(run_pipeline())

    # run : python -m training.scripts.Training_sample_generator