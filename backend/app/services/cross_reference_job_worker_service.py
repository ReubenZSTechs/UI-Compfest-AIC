from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Sequence

EVALUATION_BOUNDS = {
    "overall_compatibility_score": (0.0, 1.0),
    "throughput_multiplier": (0.8, 1.2),
    "error_multiplier": (0.4, 1.5),
    "fatigue_accumulation_rate": (0.3, 1.5),
    "stress_sensitivity_factor": (0.4, 1.0),
}

MIN_REASONING_LENGTH = 40

REPAIR_TEMPLATE = (
    "PERBAIKAN\n"
    "Respons sebelumnya ditolak dengan alasan: {reason}. "
    "Ulangi penilaian untuk pasangan yang sama dan pastikan seluruh nilai berada di dalam "
    "rentang yang diizinkan serta llm_reasoning terisi dalam bahasa Indonesia."
)


class CompatibilityPairError(RuntimeError):
    pass


class CompatibilityEvaluationError(RuntimeError):
    def __init__(self, message: str, failures: Sequence[dict[str, Any]]):
        super().__init__(message)
        self.failures = list(failures)


def read_jobs(factory: dict[str, Any]) -> list[dict[str, Any]]:
    return factory.get("job_descriptions") or factory.get("job_desks") or []


def read_stage_id(job: dict[str, Any]) -> str:
    for key in ("stage_id", "workflow_step"):
        value = job.get(key)
        if value:
            return str(value)

    raise KeyError(
        f"Job {job.get('job_id') or job.get('allocation_id') or '?'} tidak memuat stage_id maupun workflow_step"
    )


def index_assets(factory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {asset["asset_id"]: asset for asset in factory.get("assets", [])}


def build_pair_prompt(worker: dict[str, Any], job: dict[str, Any],
                      asset: dict[str, Any]) -> str:
    payload = {
        "worker": {
            "worker_id": worker["worker_id"],
            "name": worker["name"],
            "demographics": worker["demographics"],
            "shift_context": worker["shift_context"],
        },
        "job": {
            "job_id": job["job_id"],
            "job_title": job["job_title"],
            "workflow_step": read_stage_id(job),
            "demands": job["demands"],
            "qc_requirement": job.get("qc_requirement", ""),
            "metric_derivation_reasoning": job.get("metric_derivation_reasoning", ""),
        },
        "asset": {
            "asset_id": asset["asset_id"],
            "asset_name": asset["asset_name"],
            "category": asset.get("category"),
            "is_automated": asset.get("is_automated"),
            "environmental_factors": asset["environmental_factors"],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def validate_evaluations(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise ValueError("field evaluations tidak ada atau bukan objek")

    unknown = set(raw.keys()) - set(EVALUATION_BOUNDS.keys())
    if unknown:
        raise ValueError(f"field tak dikenal pada evaluations: {sorted(unknown)}")

    validated: dict[str, float] = {}

    for name, (low, high) in EVALUATION_BOUNDS.items():
        value = raw.get(name)

        if value is None:
            raise ValueError(f"{name} tidak diisi")

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} bukan angka: {value!r}")

        number = float(value)

        if math.isnan(number) or math.isinf(number):
            raise ValueError(f"{name} bukan angka berhingga")

        if number < low or number > high:
            raise ValueError(f"{name} bernilai {number} di luar rentang {low}-{high}")

        validated[name] = round(number, 2)

    return validated


def validate_reasoning(raw: Any) -> str:
    if not isinstance(raw, str):
        raise ValueError("llm_reasoning tidak ada atau bukan teks")

    cleaned = " ".join(raw.split()).strip()

    if len(cleaned) < MIN_REASONING_LENGTH:
        raise ValueError(f"llm_reasoning terlalu pendek ({len(cleaned)} karakter)")

    return cleaned


def evaluate_pair(agent: Any, worker: dict[str, Any], job: dict[str, Any],
                  asset: dict[str, Any], max_attempts: int = 3,
                  backoff_seconds: float = 1.5) -> dict[str, Any]:
    prompt = build_pair_prompt(worker, job, asset)
    last_reason: Optional[str] = None

    for attempt in range(1, max_attempts + 1):
        payload = prompt if last_reason is None else (
            f"{prompt}\n\n{REPAIR_TEMPLATE.format(reason=last_reason)}"
        )

        try:
            result = agent.generate_structured(user_prompt=payload)

            if not isinstance(result, dict):
                raise ValueError("respons agent bukan objek JSON")

            entry = {
                "job_title": job["job_title"],
                "stage_id": read_stage_id(job=job),
                "asset_id": asset["asset_id"],
                "attempts": attempt,
                "evaluations": validate_evaluations(result.get("evaluations")),
                "llm_reasoning": validate_reasoning(result.get("llm_reasoning")),
            }
            return entry

        except Exception as error:
            last_reason = f"{type(error).__name__}: {error}"

            if attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)

    raise CompatibilityPairError(last_reason or "kegagalan tidak diketahui")


def assemble_matrix(results: Sequence[dict[str, Any]], workers: Sequence[dict[str, Any]],
                    jobs: Sequence[dict[str, Any]], failures: Sequence[dict[str, Any]],
                    pair_count: int) -> dict[str, Any]:
    matrix: dict[str, Any] = {}

    for worker in workers:
        matrix[worker["worker_id"]] = {
            "worker_name": worker["name"],
            "best_job_id": None,
            "jobs": {},
        }

    retries = 0

    for result in results:
        worker_id = result["worker_id"]
        matrix[worker_id]["jobs"][result["job_id"]] = result["entry"]
        retries += result["entry"]["attempts"] - 1

    for worker_id in list(matrix.keys()):
        record = matrix[worker_id]

        if not record["jobs"]:
            matrix.pop(worker_id)
            continue

        record["best_job_id"] = max(
            record["jobs"],
            key=lambda job_id: record["jobs"][job_id]["evaluations"]["overall_compatibility_score"],
        )

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "worker_count": len(workers),
            "job_count": len(jobs),
            "pair_count": pair_count,
            "evaluated_pairs": len(results),
            "retries": retries,
            "failed_pairs": list(failures),
        },
        "compatibility_matrix": matrix,
    }


def generate_compatibility_matrix(factory: dict[str, Any], workers: Sequence[dict[str, Any]],
                                  agent: Any, max_workers: int = 4, max_attempts: int = 3,
                                  strict: bool = True,
                                  progress: Optional[Callable[[int, int], None]] = None
                                  ) -> dict[str, Any]:
    if agent is None:
        raise ValueError("Agent kompatibilitas wajib disediakan. Mode deterministik tidak tersedia.")

    jobs = read_jobs(factory)
    assets = index_assets(factory)
    worker_list = list(workers)

    pairs = [(worker, job) for worker in worker_list for job in jobs
             if job.get("assigned_asset_id") in assets]

    if not pairs:
        raise ValueError("Tidak ada pasangan pekerja-job yang bisa dievaluasi.")

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    total = len(pairs)

    def run(pair: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
        worker, job = pair
        asset = assets[job["assigned_asset_id"]]

        try:
            entry = evaluate_pair(agent, worker, job, asset, max_attempts=max_attempts)
            return {"worker_id": worker["worker_id"], "job_id": job["job_id"], "entry": entry}

        except CompatibilityPairError as error:
            return {
                "worker_id": worker["worker_id"],
                "job_id": job["job_id"],
                "error": str(error),
            }

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        for done, outcome in enumerate(pool.map(run, pairs), start=1):
            if "entry" in outcome:
                results.append(outcome)
            else:
                failures.append(outcome)

            if progress is not None:
                progress(done, total)

    if failures and strict:
        raise CompatibilityEvaluationError(
            f"{len(failures)} dari {total} pasangan gagal dievaluasi agent.",
            failures,
        )

    return assemble_matrix(results, worker_list, jobs, failures, total)