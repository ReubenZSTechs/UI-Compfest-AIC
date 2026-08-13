"""
Pure, dependency-light factory-graph utilities: turning a factory digital
twin JSON into features and a PyG HeteroData graph. No LLM calls, no asyncio,
no backend/ imports - just json/torch/hashlib/math.

This is split out of Training_sample_generator.py on purpose: that script
also imports aiofiles, yaml (via backend.app.services.agent_registry_service),
and the LLM agent client to generate compatibility LABELS during training
data generation. Anything that only needs to BUILD a graph from an existing
factory doc - prediction/inference being the main case - should import from
here instead, so it doesn't drag in dependencies it never uses.

Training_sample_generator.py imports these same functions from this module
(rather than redefining them) so there's a single source of truth for the
feature/vocab layout - the training pipeline and the prediction pipeline can
never quietly drift out of sync with each other.
"""

import hashlib
import json
import logging
import math
from pathlib import Path

import torch
from torch_geometric.data import HeteroData

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# File reading
# --------------------------------------------------------------------------

def read_text_robust(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def load_input(path: Path) -> dict:
    """Load one factory digital twin JSON: {factory_info, assets, job_descriptions, workers, ...}"""
    return json.loads(read_text_robust(path))


def get_jobs(doc: dict):
    """job_descriptions per factory_md.schema.json; some digital-twin files
    were produced under an older key name, so fall back to job_desks."""
    return doc.get('job_descriptions', doc.get('job_desks', []))


# --------------------------------------------------------------------------
# Pair construction
# --------------------------------------------------------------------------

def build_pair_prompt(worker: dict, job: dict, asset: dict) -> str:
    """Serialize one worker + one job_desk + its asset into the compact
    JSON block used as the basis for one compatibility evaluation. Kept here
    (rather than only where the LLM is called) since flatten_pair_items uses
    it regardless of whether the caller ends up sending it to an LLM."""
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
    Walk doc['workers'] x get_jobs(doc) in stable order and return a flat
    list of (worker_id, job_id, asset_id, prompt_text) tuples, one entry per
    worker-job combination whose compatibility should be evaluated. Pairs
    whose job points at a missing asset are skipped.
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


# --------------------------------------------------------------------------
# GNN graph construction - node types: worker, job, asset
# edge types : (job, uses_asset, asset)          structural
#              (asset, rev_uses_asset, job)       reverse, structural
#              (worker, compatible_with, job)     LABELED - edge_attr is the
#                                                  5-dim LLM evaluation vector
#              (job, rev_compatible_with, worker) reverse, structural only
#
# Categorical vocabularies are hardcoded from the schema enums rather than
# fit per-file, so every factory's graph uses the same feature layout and
# dimensionality - required both for batching graphs from different
# factories into one GNN training run, AND for a new factory's graph to be
# dimensionally compatible with a model trained on other factories.
# --------------------------------------------------------------------------

GENDER_VOCAB = ["male", "female", "unspecified"]
PHYSICAL_DEMAND_VOCAB = ["low", "medium", "high"]
ERROR_SEVERITY_VOCAB = ["low", "moderate", "high", "critical"]
VIBRATION_VOCAB = ["low", "medium", "high"]
ASSET_CATEGORY_VOCAB = [
    "machine", "measuring_equipment", "conveyor_automation",
    "environmental_chamber", "manual_station",
]

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
    split_ratios = {'train': 0.8, 'val': 0.1, 'test': 0.1}
    digest = hashlib.sha256(factory_id.encode('utf-8')).hexdigest()
    frac = (int(digest[:8], 16) % 10_000) / 10_000
    cum = 0.0
    for split_name, ratio in split_ratios.items():
        cum += ratio
        if frac < cum:
            return split_name
    return 'train'


def build_hetero_graph(doc: dict, evaluations: list) -> tuple:
    """Build one HeteroData graph for a factory from its digital twin doc
    and a list of {worker_id, job_id, asset_id, evaluations, llm_reasoning}
    records. Pass evaluations=[] for a factory with no labels yet (e.g. a
    brand-new factory being scored for inference) - the compatible_with /
    rev_compatible_with edges simply come back empty. Returns
    (data, n_edges_skipped)."""
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
