"""
Inferensi model GNN kompatibilitas pekerja x job desk.

Membungkus checkpoint `best_compatibility_predictor.pt` (hasil
`training/scripts/GNN_train.py`) menjadi satu service yang bisa dipanggil
langsung dari backend maupun dari harness Streamlit di tests/services.

Alur singkat:

    factory (digital twin) + workers
        -> fitur node (worker / job / asset) + edge index heterogen
        -> GraphSAGE encoder heterogen + edge head
        -> 5 metrik kompatibilitas per pasangan (skala asli, bukan normalized)

Dua bentuk keluaran disediakan:

  * `predict_compatibility()` - daftar datar satu record per pasangan,
    bentuknya sama persis dengan blok `predictions` pada
    sample_output_result.json.
  * `generate_compatibility_matrix()` - matriks bersarang identik dengan
    keluaran `cross_reference_job_worker_service.generate_compatibility_matrix`
    (jalur Agent C / compatibility_eval_agent.yaml), termasuk `evaluations`
    dan `llm_reasoning` yang lolos validator schema yang sama.

CATATAN DEPENDENSI: forward pass di sini adalah reimplementasi murni PyTorch
dari `SAGEConv` + `to_hetero(aggr="mean")`, jadi service ini TIDAK butuh
torch_geometric terpasang - hanya `torch`. Bobot yang dipakai tetap bobot
asli dari checkpoint (nama parameternya dibuat identik dengan model latih,
sehingga `load_state_dict(strict=True)` yang memverifikasi kecocokannya).
Kesetaraan numeriknya sudah dicek terhadap jalur torch_geometric asli
(selisih maksimum ~1e-7).
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

import torch
from torch import nn

from .cross_reference_job_worker_service import (
    EVALUATION_BOUNDS,
    assemble_matrix,
    index_assets,
    read_jobs,
    read_stage_id,
    validate_evaluations,
    validate_reasoning,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_MODEL_PATH = PROJECT_ROOT / "training" / "datasets" / "formatted" / "checkpoints" / "best_compatibility_predictor.pt"

MODEL_PATH_ENV_VAR = "GNN_COMPATIBILITY_MODEL_PATH"

GENDER_VOCAB = ["male", "female", "unspecified"]
PHYSICAL_DEMAND_VOCAB = ["low", "medium", "high"]
ERROR_SEVERITY_VOCAB = ["low", "moderate", "high", "critical"]
VIBRATION_VOCAB = ["low", "medium", "high"]
ASSET_CATEGORY_VOCAB = [
    "machine", "measuring_equipment", "conveyor_automation",
    "environmental_chamber", "manual_station",
]

WORKER_FEATURE_DIM = 1 + len(GENDER_VOCAB) + 1 + 1 + 1 + 1 + 1   # = 9
JOB_FEATURE_DIM = 1 + len(PHYSICAL_DEMAND_VOCAB) + 1 + len(ERROR_SEVERITY_VOCAB)  # = 9
ASSET_FEATURE_DIM = len(ASSET_CATEGORY_VOCAB) + 1 + 1 + 1 + 1 + 1 + len(VIBRATION_VOCAB) + 1  # = 14

EDGE_LABEL_FIELDS = [
    "overall_compatibility_score",
    "throughput_multiplier",
    "error_multiplier",
    "fatigue_accumulation_rate",
    "stress_sensitivity_factor",
]

class GNNCompatibilityError(RuntimeError):
    """Checkpoint tidak bisa dimuat, atau graf tidak bisa dibangun dari input."""


# --------------------------------------------------------------------------
# Feature builders
# --------------------------------------------------------------------------

def _one_hot(value: Any, vocab: Sequence[str]) -> list[float]:
    vec = [0.0] * len(vocab)
    if value in vocab:
        vec[vocab.index(value)] = 1.0
    return vec


def _minmax(val: Any, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (float(val) - lo) / (hi - lo)))


def _log_scale(val: Any, cap: float) -> float:
    val = max(0.0, float(val))
    return min(1.0, math.log1p(val) / math.log1p(cap))


def _require(mapping: dict[str, Any], key: str, owner: str) -> Any:
    if key not in mapping:
        raise GNNCompatibilityError(f"{owner} tidak memuat field wajib '{key}'")
    return mapping[key]


def worker_features(worker: dict[str, Any]) -> list[float]:
    who = worker.get("worker_id", "?")
    demo = _require(worker, "demographics", f"worker {who}")
    shift = _require(worker, "shift_context", f"worker {who}")

    feats = [_minmax(_require(demo, "age", f"worker {who} demographics"), 16, 75)]
    feats += _one_hot(demo.get("gender"), GENDER_VOCAB)
    feats += [min(float(_require(demo, "years_of_experience", f"worker {who} demographics")), 50) / 50.0]
    feats += [float(_require(demo, "baseline_physical_stamina", f"worker {who} demographics"))]
    feats += [float(_require(demo, "cognitive_resilience", f"worker {who} demographics"))]
    feats += [_minmax(_require(shift, "hours_worked_today", f"worker {who} shift_context"), 0, 24)]
    feats += [min(float(_require(shift, "consecutive_shifts", f"worker {who} shift_context")), 14) / 14.0]

    assert len(feats) == WORKER_FEATURE_DIM
    return feats


def job_features(job: dict[str, Any]) -> list[float]:
    what = job.get("job_id", "?")
    demands = _require(job, "demands", f"job {what}")

    feats = [float(_require(demands, "required_cognitive_focus", f"job {what} demands"))]
    feats += _one_hot(demands.get("physical_demand_level"), PHYSICAL_DEMAND_VOCAB)
    feats += [float(_require(demands, "task_complexity", f"job {what} demands"))]
    feats += _one_hot(demands.get("error_severity"), ERROR_SEVERITY_VOCAB)

    assert len(feats) == JOB_FEATURE_DIM
    return feats


def asset_features(asset: dict[str, Any]) -> list[float]:
    which = asset.get("asset_id", "?")
    env = _require(asset, "environmental_factors", f"asset {which}")

    feats = _one_hot(asset.get("category"), ASSET_CATEGORY_VOCAB)
    feats += [1.0 if asset.get("is_automated") else 0.0]
    feats += [_log_scale(asset.get("units_available", 0), 100)]
    feats += [_log_scale(asset.get("base_throughput_capacity", 0), 1000)]
    feats += [_log_scale(asset.get("operational_cost_per_hour", 0), 1000)]
    feats += [_minmax(_require(env, "noise_level_db", f"asset {which} environmental_factors"), 30, 95)]
    feats += _one_hot(env.get("vibration_hazard_level"), VIBRATION_VOCAB)
    feats += [float(_require(env, "physical_strain_index", f"asset {which} environmental_factors"))]

    assert len(feats) == ASSET_FEATURE_DIM
    return feats


def _rel_key(edge_type: tuple[str, str, str]) -> str:
    """Nama modul per relasi, mengikuti konvensi penamaan to_hetero
    ('__'.join(edge_type)) supaya state_dict checkpoint langsung cocok."""
    return "__".join(edge_type)


class _RelationalSAGEConv(nn.Module):
    def __init__(self, in_src: int, in_dst: int, out_channels: int):
        super().__init__()
        self.lin_l = nn.Linear(in_src, out_channels, bias=True)
        self.lin_r = nn.Linear(in_dst, out_channels, bias=False)

    def forward(self, x_src: torch.Tensor, x_dst: torch.Tensor,
                edge_index: torch.Tensor) -> torch.Tensor:
        aggregated = x_src.new_zeros((x_dst.size(0), x_src.size(1)))

        if edge_index.numel():
            src, dst = edge_index[0], edge_index[1]
            counts = x_src.new_zeros((x_dst.size(0), 1))
            aggregated.index_add_(0, dst, x_src.index_select(0, src))
            counts.index_add_(0, dst, x_src.new_ones((src.size(0), 1)))
            aggregated = aggregated / counts.clamp(min=1.0)

        return self.lin_l(aggregated) + self.lin_r(x_dst)


class _HeteroSAGEEncoder(nn.Module):
    """Dua lapis SAGEConv per relasi; keluaran tiap tipe node adalah
    rata-rata (aggr="mean") dari seluruh relasi yang bermuara ke tipe itu."""

    def __init__(self, node_types: Sequence[str], edge_types: Sequence[tuple[str, str, str]],
                 dims: dict[str, dict[str, tuple[int, int, int]]]):
        super().__init__()
        self.node_types = list(node_types)
        self.edge_types = [tuple(e) for e in edge_types]
        self.num_layers = len(dims)

        for layer_name, per_relation in dims.items():
            setattr(self, layer_name, nn.ModuleDict({
                key: _RelationalSAGEConv(*shape) for key, shape in per_relation.items()
            }))

    def forward(self, x_dict: dict[str, torch.Tensor],
                edge_index_dict: dict[tuple[str, str, str], torch.Tensor]
                ) -> dict[str, torch.Tensor]:
        h_dict = x_dict

        for layer in range(1, self.num_layers + 1):
            convs = getattr(self, f"conv{layer}")
            buckets: dict[str, list[torch.Tensor]] = {nt: [] for nt in self.node_types}

            for edge_type in self.edge_types:
                src, _, dst = edge_type
                conv = convs[_rel_key(edge_type)]
                edge_index = edge_index_dict.get(edge_type)
                if edge_index is None:
                    edge_index = torch.empty((2, 0), dtype=torch.long, device=h_dict[src].device)
                buckets[dst].append(conv(h_dict[src], h_dict[dst], edge_index))

            out_dict = {}
            for node_type in self.node_types:
                parts = buckets[node_type]
                if parts:
                    out_dict[node_type] = parts[0] if len(parts) == 1 else torch.stack(parts, dim=0).mean(dim=0)
                else:
                    # tipe node tanpa relasi masuk: to_hetero mengembalikan None
                    # di sini; nol berdimensi benar menjaga pipeline tetap jalan
                    width = convs[_rel_key(self.edge_types[0])].lin_l.out_features
                    out_dict[node_type] = h_dict[node_type].new_zeros((h_dict[node_type].size(0), width))

            # relu antar lapis, tidak setelah lapis terakhir (lihat GraphSAGEEncoder)
            h_dict = {k: v.relu() for k, v in out_dict.items()} if layer < self.num_layers else out_dict

        return h_dict


class CompatibilityPredictor(nn.Module):
    """Padanan inferensi dari CompatibilityPredictor di GNN_train.py.

    Nama parameternya sengaja identik ('encoder.conv1.<relasi>.lin_l.weight',
    'edge_head.0.weight', ...) supaya state_dict checkpoint bisa dimuat
    dengan strict=True - itulah pengaman bahwa arsitektur di sini benar-benar
    arsitektur yang dilatih.
    """

    def __init__(self, encoder: _HeteroSAGEEncoder, out_channels: int,
                 hidden_channels: int, num_targets: int):
        super().__init__()
        self.encoder = encoder
        self.edge_head = nn.Sequential(
            nn.Linear(out_channels * 2, hidden_channels),
            nn.ReLU(),
            nn.Linear(hidden_channels, num_targets),
            nn.Sigmoid(),
        )

    def forward(self, x_dict, edge_index_dict, worker_idx, job_idx) -> torch.Tensor:
        embeddings = self.encoder(x_dict, edge_index_dict)
        pair = torch.cat([embeddings["worker"][worker_idx], embeddings["job"][job_idx]], dim=-1)
        return self.edge_head(pair)


def _encoder_dims_from_state_dict(state_dict: dict[str, torch.Tensor],
                                  edge_types: Sequence[tuple[str, str, str]]
                                  ) -> dict[str, dict[str, tuple[int, int, int]]]:
    """Baca lebar tiap Linear langsung dari bentuk tensor checkpoint, supaya
    modul yang dibangun selalu cocok dengan bobot yang akan dimuat (tidak
    perlu menebak feature_dims / hidden_channels)."""
    layers = sorted({
        key.split(".")[1] for key in state_dict
        if key.startswith("encoder.conv")
    })

    dims: dict[str, dict[str, tuple[int, int, int]]] = {}
    for layer_name in layers:
        per_relation = {}
        for edge_type in edge_types:
            key = _rel_key(edge_type)
            prefix = f"encoder.{layer_name}.{key}"
            try:
                lin_l = state_dict[f"{prefix}.lin_l.weight"]
                lin_r = state_dict[f"{prefix}.lin_r.weight"]
            except KeyError as error:
                raise GNNCompatibilityError(
                    f"Checkpoint tidak memuat bobot untuk relasi {edge_type} pada {layer_name}: {error}"
                ) from error
            per_relation[key] = (lin_l.shape[1], lin_r.shape[1], lin_l.shape[0])
        dims[layer_name] = per_relation

    if not dims:
        raise GNNCompatibilityError("Checkpoint tidak memuat bobot encoder sama sekali.")

    return dims


class LoadedModel:
    """Model beserta metadata checkpoint yang dibutuhkan untuk menafsirkan
    keluarannya (urutan field dan batas skala tiap metrik)."""

    def __init__(self, model: CompatibilityPredictor, edge_label_fields: Sequence[str],
                 eval_bounds: dict[str, tuple[float, float]], metadata, device: torch.device,
                 source_path: Path):
        self.model = model
        self.edge_label_fields = list(edge_label_fields)
        self.eval_bounds = dict(eval_bounds)
        self.metadata = metadata
        self.device = device
        self.source_path = source_path

        self._lo = torch.tensor([self.eval_bounds[f][0] for f in self.edge_label_fields],
                                dtype=torch.float, device=device)
        self._hi = torch.tensor([self.eval_bounds[f][1] for f in self.edge_label_fields],
                                dtype=torch.float, device=device)

    def unnormalize(self, normalized: torch.Tensor) -> torch.Tensor:
        """Kembalikan keluaran sigmoid [0,1] ke skala asli tiap metrik."""
        return normalized * (self._hi - self._lo) + self._lo

    @torch.no_grad()
    def infer(self, x_dict: dict[str, torch.Tensor],
              edge_index_dict: dict[tuple[str, str, str], torch.Tensor],
              worker_idx: torch.Tensor, job_idx: torch.Tensor) -> torch.Tensor:
        """Tensor [num_pairs, 5] pada skala asli, kolomnya mengikuti
        `self.edge_label_fields`."""
        self.model.eval()
        return self.unnormalize(self.model(x_dict, edge_index_dict, worker_idx, job_idx))


def resolve_model_path(model_path: Optional[str | Path] = None) -> Path:
    if model_path is not None:
        return Path(model_path).expanduser().resolve()

    override = os.environ.get(MODEL_PATH_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()

    return DEFAULT_MODEL_PATH


def load_model(model_path: Optional[str | Path] = None,
               device: Optional[str | torch.device] = None) -> LoadedModel:
    """Muat checkpoint .pt dan rekonstruksi model siap inferensi.

    Hasilnya di-cache per (path, mtime, device) sehingga pemanggilan berulang
    dari Streamlit tidak membaca ulang file; checkpoint yang ditimpa (mtime
    berubah) otomatis dimuat ulang.
    """
    path = resolve_model_path(model_path)

    if not path.exists():
        raise GNNCompatibilityError(
            f"Checkpoint GNN tidak ditemukan di {path}. "
            f"Latih ulang lewat `python -m training.scripts.GNN_train`, "
            f"atau set env {MODEL_PATH_ENV_VAR} ke lokasi file .pt yang benar."
        )

    resolved_device = torch.device(device) if device is not None else torch.device("cpu")
    return _load_model_cached(str(path), path.stat().st_mtime_ns, str(resolved_device))


@lru_cache(maxsize=4)
def _load_model_cached(path_str: str, mtime_ns: int, device_str: str) -> LoadedModel:
    path = Path(path_str)
    device = torch.device(device_str)

    try:
        checkpoint = torch.load(path, map_location=device, weights_only=False)
    except Exception as error:
        raise GNNCompatibilityError(f"Gagal membaca checkpoint {path}: {type(error).__name__}: {error}") from error

    if not isinstance(checkpoint, dict) or "state_dict" not in checkpoint:
        raise GNNCompatibilityError(
            f"{path} bukan checkpoint hasil GNN_train.run_training() "
            f"(tidak ada key 'state_dict')."
        )

    state_dict = checkpoint["state_dict"]
    node_types, edge_types = checkpoint["metadata"]
    edge_types = [tuple(e) for e in edge_types]

    edge_label_fields = list(checkpoint.get("edge_label_fields", EDGE_LABEL_FIELDS))
    eval_bounds = {k: tuple(v) for k, v in checkpoint.get("eval_bounds", EVALUATION_BOUNDS).items()}

    missing = [f for f in edge_label_fields if f not in eval_bounds]
    if missing:
        raise GNNCompatibilityError(f"eval_bounds pada checkpoint tidak memuat batas untuk: {missing}")

    encoder = _HeteroSAGEEncoder(node_types, edge_types, _encoder_dims_from_state_dict(state_dict, edge_types))

    head_in = state_dict["edge_head.0.weight"].shape[1]
    hidden_channels = state_dict["edge_head.0.weight"].shape[0]
    num_targets = state_dict["edge_head.2.weight"].shape[0]

    if num_targets != len(edge_label_fields):
        raise GNNCompatibilityError(
            f"edge_head memprediksi {num_targets} nilai tapi edge_label_fields berisi "
            f"{len(edge_label_fields)} field - checkpoint tidak konsisten."
        )

    model = CompatibilityPredictor(
        encoder=encoder,
        out_channels=head_in // 2,
        hidden_channels=hidden_channels,
        num_targets=num_targets,
    )

    try:
        model.load_state_dict(state_dict, strict=True)
    except Exception as error:
        raise GNNCompatibilityError(
            f"Bobot checkpoint tidak cocok dengan arsitektur inferensi di service ini "
            f"({type(error).__name__}: {error}). Kemungkinan GNN_train.py sudah berubah "
            f"arsitekturnya - sesuaikan gnn_compatibility_service.py."
        ) from error

    model.to(device).eval()

    return LoadedModel(
        model=model,
        edge_label_fields=edge_label_fields,
        eval_bounds=eval_bounds,
        metadata=(list(node_types), edge_types),
        device=device,
        source_path=path,
    )


class GraphInputs:
    """Tensor siap-pakai untuk satu pabrik, plus pemetaan balik ke pasangan
    (worker, job, asset) supaya keluaran model bisa diberi label lagi."""

    def __init__(self, x_dict, edge_index_dict, worker_idx, job_idx, pairs):
        self.x_dict = x_dict
        self.edge_index_dict = edge_index_dict
        self.worker_idx = worker_idx
        self.job_idx = job_idx
        self.pairs = pairs  # list[(worker, job, asset)]

    def __len__(self) -> int:
        return len(self.pairs)


def build_graph_inputs(factory: dict[str, Any], workers: Sequence[dict[str, Any]],
                       device: Optional[torch.device] = None) -> GraphInputs:
    """Bangun graf heterogen satu pabrik + daftar pasangan kandidat.

    factory : digital twin (factory_info / assets / job_descriptions).
    workers : daftar profil pekerja (boleh dari worker_profile["workers"]).
    """
    device = device or torch.device("cpu")

    jobs = read_jobs(factory)
    assets = list(factory.get("assets") or [])
    worker_list = list(workers)

    if not worker_list:
        raise GNNCompatibilityError("Tidak ada pekerja pada input.")
    if not jobs:
        raise GNNCompatibilityError("Tidak ada job desk pada input.")
    if not assets:
        raise GNNCompatibilityError("Tidak ada aset pada input.")

    assets_by_id = index_assets(factory)

    worker_pos = {w["worker_id"]: i for i, w in enumerate(worker_list)}
    job_pos = {j["job_id"]: i for i, j in enumerate(jobs)}
    asset_pos = {a["asset_id"]: i for i, a in enumerate(assets)}

    x_dict = {
        "worker": torch.tensor([worker_features(w) for w in worker_list], dtype=torch.float, device=device),
        "job": torch.tensor([job_features(j) for j in jobs], dtype=torch.float, device=device),
        "asset": torch.tensor([asset_features(a) for a in assets], dtype=torch.float, device=device),
    }

    # edge struktural job -> asset (mesin yang dipakai tiap pos kerja)
    ja_src, ja_dst = [], []
    for job in jobs:
        asset_id = job.get("assigned_asset_id")
        if asset_id in asset_pos:
            ja_src.append(job_pos[job["job_id"]])
            ja_dst.append(asset_pos[asset_id])

    # seluruh pasangan kandidat worker x job (job tanpa aset valid dilewati,
    # sama seperti generate_compatibility_matrix pada jalur agent)
    pairs: list[tuple[dict, dict, dict]] = []
    cw_src, cw_dst = [], []
    for worker in worker_list:
        for job in jobs:
            asset = assets_by_id.get(job.get("assigned_asset_id"))
            if asset is None:
                continue
            pairs.append((worker, job, asset))
            cw_src.append(worker_pos[worker["worker_id"]])
            cw_dst.append(job_pos[job["job_id"]])

    if not pairs:
        raise GNNCompatibilityError(
            "Tidak ada pasangan pekerja-job yang bisa dievaluasi: seluruh job desk "
            "menunjuk assigned_asset_id yang tidak ada di daftar aset."
        )

    def _edge(src: list[int], dst: list[int]) -> torch.Tensor:
        if not src:
            return torch.empty((2, 0), dtype=torch.long, device=device)
        return torch.tensor([src, dst], dtype=torch.long, device=device)

    edge_index_dict = {
        ("job", "uses_asset", "asset"): _edge(ja_src, ja_dst),
        ("asset", "rev_uses_asset", "job"): _edge(ja_dst, ja_src),
        ("worker", "compatible_with", "job"): _edge(cw_src, cw_dst),
        ("job", "rev_compatible_with", "worker"): _edge(cw_dst, cw_src),
    }

    return GraphInputs(
        x_dict=x_dict,
        edge_index_dict=edge_index_dict,
        worker_idx=torch.tensor(cw_src, dtype=torch.long, device=device),
        job_idx=torch.tensor(cw_dst, dtype=torch.long, device=device),
        pairs=pairs,
    )


def predict_compatibility(factory: dict[str, Any], workers: Sequence[dict[str, Any]],
                          model_path: Optional[str | Path] = None,
                          device: Optional[str | torch.device] = None) -> list[dict[str, Any]]:
    """Jalankan model untuk satu pabrik dan kembalikan satu record datar per
    pasangan pekerja x job.

    Bentuk tiap record sama dengan blok `predictions` pada
    sample_output_result.json:

        {"worker_id", "job_id", "job_title", "asset_id",
         "overall_compatibility_score", "throughput_multiplier",
         "error_multiplier", "fatigue_accumulation_rate",
         "stress_sensitivity_factor"}

    Nilainya float mentah dari model (belum dibulatkan); pembulatan dua
    desimal dilakukan di `generate_compatibility_matrix()` agar lolos
    validator schema Agent C.
    """
    loaded = load_model(model_path, device)
    graph = build_graph_inputs(factory, workers, device=loaded.device)

    scores = loaded.infer(graph.x_dict, graph.edge_index_dict, graph.worker_idx, graph.job_idx)

    predictions = []
    for row, (worker, job, asset) in zip(scores.tolist(), graph.pairs):
        record = {
            "worker_id": worker["worker_id"],
            "job_id": job["job_id"],
            "job_title": job.get("job_title"),
            "asset_id": asset["asset_id"],
        }
        record.update({field: value for field, value in zip(loaded.edge_label_fields, row)})
        predictions.append(record)

    return predictions


def build_optimal_assignment(predictions: Sequence[dict[str, Any]],
                             utility_field: str = "overall_compatibility_score"
                             ) -> dict[str, Any]:
    """Penugasan greedy satu pekerja - satu pos kerja: urutkan seluruh
    pasangan dari utilitas tertinggi, ambil kalau pekerja dan job-nya
    belum terpakai. Padanan blok `optimal_assignment` pada
    sample_output_result.json.

    Greedy, bukan optimum global (Hungarian) - cukup sebagai baseline
    pembanding untuk penempatan dari RL di tahap berikutnya.
    """
    ordered = sorted(predictions, key=lambda p: p.get(utility_field, 0.0), reverse=True)

    used_workers: set[str] = set()
    used_jobs: set[str] = set()
    assignments = []

    for prediction in ordered:
        if prediction["worker_id"] in used_workers or prediction["job_id"] in used_jobs:
            continue
        used_workers.add(prediction["worker_id"])
        used_jobs.add(prediction["job_id"])

        entry = {
            "worker_id": prediction["worker_id"],
            "job_id": prediction["job_id"],
            "job_title": prediction.get("job_title"),
            "asset_id": prediction.get("asset_id"),
            "utility": round(float(prediction.get(utility_field, 0.0)), 4),
        }
        entry.update({f: prediction[f] for f in EDGE_LABEL_FIELDS if f in prediction})
        assignments.append(entry)

    return {
        "assignments": assignments,
        "unassigned_workers": sorted({p["worker_id"] for p in predictions} - used_workers),
        "unassigned_jobs": sorted({p["job_id"] for p in predictions} - used_jobs),
        "total_utility": round(sum(a["utility"] for a in assignments), 4),
    }


def infer_factory(factory: dict[str, Any], workers: Optional[Sequence[dict[str, Any]]] = None,
                  model_path: Optional[str | Path] = None,
                  device: Optional[str | torch.device] = None) -> dict[str, Any]:
    """Bungkus satu file input pabrik menjadi dokumen keluaran lengkap
    {"predictions": [...], "optimal_assignment": {...}} - bentuk yang sama
    dengan sample_output_result.json.

    `workers` boleh dikosongkan bila daftar pekerja sudah ada di dalam
    `factory["workers"]` (format digital twin sintetis).
    """
    worker_list = list(workers) if workers is not None else list(factory.get("workers") or [])
    predictions = predict_compatibility(factory, worker_list, model_path=model_path, device=device)
    return {
        "predictions": predictions,
        "optimal_assignment": build_optimal_assignment(predictions),
    }


_DEMAND_LEVEL = {"low": 0.2, "medium": 0.5, "high": 0.8}


def _fmt(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def build_reasoning(worker: dict[str, Any], job: dict[str, Any], asset: dict[str, Any],
                    evaluations: dict[str, float]) -> str:
    """Susun llm_reasoning deterministik untuk satu pasangan."""
    demo = worker.get("demographics", {})
    shift = worker.get("shift_context", {})
    demands = job.get("demands", {})
    env = asset.get("environmental_factors", {})

    name = worker.get("name") or worker["worker_id"]
    title = job.get("job_title") or job["job_id"]

    stamina = demo.get("baseline_physical_stamina")
    resilience = demo.get("cognitive_resilience")
    experience = demo.get("years_of_experience")
    focus = demands.get("required_cognitive_focus")
    demand_level = demands.get("physical_demand_level")
    severity = demands.get("error_severity")
    strain = env.get("physical_strain_index")
    noise = env.get("noise_level_db")
    hours = shift.get("hours_worked_today")
    consecutive = shift.get("consecutive_shifts")

    physical_gap = None
    if isinstance(stamina, (int, float)) and demand_level in _DEMAND_LEVEL:
        physical_gap = _DEMAND_LEVEL[demand_level] - float(stamina)

    cognitive_gap = None
    if isinstance(resilience, (int, float)) and isinstance(focus, (int, float)):
        cognitive_gap = float(focus) - float(resilience)

    basis = (
        f"Model GNN menilai {name} pada pos {title} dengan skor kompatibilitas "
        f"{_fmt(evaluations['overall_compatibility_score'])} dari stamina {_fmt(stamina)} "
        f"melawan tuntutan fisik {demand_level or 'n/a'} dan cognitive_resilience "
        f"{_fmt(resilience)} terhadap required_cognitive_focus {_fmt(focus)}."
    )

    strengths = []
    if isinstance(experience, (int, float)):
        strengths.append(f"pengalaman {int(experience)} tahun")
    if evaluations["throughput_multiplier"] >= 1.0:
        strengths.append(f"throughput {_fmt(evaluations['throughput_multiplier'])} di atas kapasitas dasar")
    if evaluations["error_multiplier"] <= 1.0:
        strengths.append(f"error_multiplier {_fmt(evaluations['error_multiplier'])} menekan peluang salah")

    weaknesses = []
    if physical_gap is not None and physical_gap > 0.10:
        weaknesses.append(f"stamina tertinggal {_fmt(physical_gap)} dari tuntutan fisik")
    if cognitive_gap is not None and cognitive_gap > 0.10:
        weaknesses.append(f"fokus yang dituntut melebihi resiliensi kognitif sebesar {_fmt(cognitive_gap)}")
    if evaluations["throughput_multiplier"] < 1.0:
        weaknesses.append(f"throughput {_fmt(evaluations['throughput_multiplier'])} justru memperlambat lini")
    if evaluations["error_multiplier"] > 1.0:
        weaknesses.append(
            f"error_multiplier {_fmt(evaluations['error_multiplier'])} pada pos ber-error_severity {severity or 'n/a'}"
        )
    if evaluations["fatigue_accumulation_rate"] >= 0.7:
        weaknesses.append(
            f"fatigue {_fmt(evaluations['fatigue_accumulation_rate'])} setelah {_fmt(hours, 1)} jam kerja "
            f"dan {consecutive if consecutive is not None else 'n/a'} shift beruntun"
        )
    if evaluations["stress_sensitivity_factor"] >= 0.7:
        weaknesses.append(
            f"stress_sensitivity {_fmt(evaluations['stress_sensitivity_factor'])} di lingkungan "
            f"{_fmt(noise, 0)} dB dengan physical_strain_index {_fmt(strain)}"
        )

    if not weaknesses:
        weaknesses.append(
            f"beban aset {asset.get('asset_name') or asset['asset_id']} tetap menyisakan fatigue "
            f"{_fmt(evaluations['fatigue_accumulation_rate'])} dan stress "
            f"{_fmt(evaluations['stress_sensitivity_factor'])} yang perlu dipantau"
        )

    strength_text = (
        f"Sisi kuatnya {', '.join(strengths[:2])}." if strengths
        else "Tidak ada sisi kuat yang menonjol dari pasangan ini."
    )
    weakness_text = f"Sisi lemahnya {', '.join(weaknesses[:2])}."

    return " ".join([basis, strength_text, weakness_text])


def generate_compatibility_matrix(factory: dict[str, Any], workers: Sequence[dict[str, Any]],
                                  model_path: Optional[str | Path] = None,
                                  device: Optional[str | torch.device] = None,
                                  progress: Optional[Callable[[int, int], None]] = None
                                  ) -> dict[str, Any]:
    loaded = load_model(model_path, device)
    graph = build_graph_inputs(factory, workers, device=loaded.device)

    scores = loaded.infer(graph.x_dict, graph.edge_index_dict, graph.worker_idx, graph.job_idx)

    jobs = read_jobs(factory)
    worker_list = list(workers)
    total = len(graph.pairs)

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for done, (row, (worker, job, asset)) in enumerate(zip(scores.tolist(), graph.pairs), start=1):
        raw = {field: value for field, value in zip(loaded.edge_label_fields, row)}

        try:
            evaluations = validate_evaluations(raw)
            entry = {
                "job_title": job["job_title"],
                "stage_id": read_stage_id(job),
                "asset_id": asset["asset_id"],
                "attempts": 1,
                "evaluations": evaluations,
                "llm_reasoning": validate_reasoning(build_reasoning(worker, job, asset, evaluations)),
            }
            results.append({"worker_id": worker["worker_id"], "job_id": job["job_id"], "entry": entry})

        except Exception as error:
            failures.append({
                "worker_id": worker["worker_id"],
                "job_id": job["job_id"],
                "error": f"{type(error).__name__}: {error}",
            })

        if progress is not None:
            progress(done, total)

    matrix = assemble_matrix(results, worker_list, jobs, failures, total)
    matrix["meta"]["source"] = "gnn"
    matrix["meta"]["model_path"] = str(loaded.source_path)
    matrix["meta"]["model_fields"] = list(loaded.edge_label_fields)

    return matrix


def _main(argv: Iterable[str]) -> int:
    args = list(argv)
    if not args:
        print(__doc__)
        print(f"pemakaian: python -m backend.app.services.gnn_compatibility_service <factory.json> [checkpoint.pt]")
        return 1

    factory = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    checkpoint = args[1] if len(args) > 1 else None
    print(json.dumps(infer_factory(factory, model_path=checkpoint), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv[1:]))